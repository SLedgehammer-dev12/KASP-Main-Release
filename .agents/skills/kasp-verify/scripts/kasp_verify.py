#!/usr/bin/env python3
"""KASP verification CLI — OpenHands-style control loop, stdlib only.

Inspired by OpenHands ``.agents/skills/verify-openhands``: launch an isolated
stack, prove it is healthy, turn every user step into a rerunnable command and
keep evidence after cleanup.

Commands
--------
    doctor                      read-only environment + skill contract checks
    serve [--port N]            start an isolated ``run_web.py`` instance
    status [--run DIR]          report process + HTTP health
    stop [--run DIR]            stop only the instance owned by this run
    api [--run DIR] [--login]   probe public/auth API contracts
    features                    list the KASP feature map (stable IDs)
    evidence add|list           append or read the pass/fail ledger
    selftest                    test the CLI helpers without touching a server

Every command prints one JSON object. Exit codes: 0 ok, 1 action failed,
2 usage, 3 environment.

No third-party dependency is required. Credentials are read from the
environment and never written to disk or printed.
"""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[4]
SKILLS_DIR = ROOT / ".agents" / "skills"
STATE_DIR = ROOT / ".kasp-verify"
RUNS_DIR = STATE_DIR / "runs"
GLOBAL_EVIDENCE_DIR = STATE_DIR / "evidence"
FEATURES_FILE = SKILLS_DIR / "kasp-verify" / "references" / "features.json"

HOST = "127.0.0.1"
DEFAULT_TOKEN = os.environ.get("KASP_VERIFY_TOKEN") or os.environ.get(
    "KASP_API_TOKEN"
) or "kasp-local-token"

RESULT_STYLES = {
    "pass": "✅",
    "fail": "❌",
    "blocked": "⛔",
    "not-run": "➖",
    "xfail": "⚠️",
    "xpass": "❗",
}


class CliError(RuntimeError):
    def __init__(self, message: str, exit_code: int = 1, **extra: Any) -> None:
        super().__init__(message)
        self.exit_code = exit_code
        self.extra = extra


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def emit(payload: dict[str, Any], exit_code: int = 0) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    raise SystemExit(exit_code)


def fail(message: str, exit_code: int = 1, **extra: Any) -> None:
    raise CliError(message, exit_code, **extra)


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------


def is_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
    except (OSError, ValueError):
        return False
    return True


def process_command(pid: int) -> str:
    """Return the command line for *pid* using ``ps`` (POSIX)."""
    try:
        out = subprocess.run(
            ["ps", "-p", str(pid), "-o", "command="],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def port_free(port: int, host: str = HOST) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def free_port(start: int = 8090, end: int = 8199) -> int:
    for port in range(start, end + 1):
        if port_free(port):
            return port
    fail(f"No free port in {start}-{end}.", 3)


def http_request(
    url: str,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    opener: urllib.request.OpenerDirector | None = None,
    timeout: float = 10.0,
) -> dict[str, Any]:
    body = None
    final_headers = {"Accept": "application/json", "User-Agent": "kasp-verify/1"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        final_headers["Content-Type"] = "application/json"
    if headers:
        final_headers.update(headers)
    request = urllib.request.Request(url, data=body, method=method, headers=final_headers)
    try:
        with (opener or urllib.request.build_opener()).open(request, timeout=timeout) as response:
            raw = response.read()
            parsed: Any = None
            if raw:
                try:
                    parsed = json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    parsed = None
            return {
                "status": response.status,
                "json": parsed,
                "text": raw.decode("utf-8", errors="replace")[:400],
            }
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            parsed = None
        return {
            "status": exc.code,
            "json": parsed,
            "text": raw.decode("utf-8", errors="replace")[:400],
        }
    except (urllib.error.URLError, OSError) as exc:
        return {"status": 0, "json": None, "text": str(exc), "error": type(exc).__name__}


def health(base_url: str, timeout: float = 3.0) -> dict[str, Any]:
    return http_request(f"{base_url}/api/health", timeout=timeout)


def wait_for_health(base_url: str, timeout_s: float) -> tuple[bool, dict[str, Any]]:
    deadline = time.monotonic() + timeout_s
    last: dict[str, Any] = {}
    while time.monotonic() < deadline:
        last = health(base_url, timeout=2.0)
        if last.get("status") == 200 and isinstance(last.get("json"), dict):
            if last["json"].get("status") in {"healthy", "ok", "degraded"}:
                return True, last
        time.sleep(0.4)
    return False, last


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def load_state(run_dir: Path) -> dict[str, Any]:
    run_json = run_dir / "run.json"
    if not run_json.exists():
        fail(f"No run.json in {run_dir}.", 3)
    try:
        return json.loads(run_json.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"Corrupt run.json in {run_dir}: {exc}", 3)


def resolve_run(run_arg: str | None) -> tuple[Path, dict[str, Any]]:
    raw = run_arg or os.environ.get("KASP_VERIFY_RUN")
    if raw:
        run_dir = Path(raw)
        if not run_dir.is_absolute():
            run_dir = ROOT / run_dir
        return run_dir, load_state(run_dir)

    live: list[tuple[Path, dict[str, Any]]] = []
    for run_json in sorted(RUNS_DIR.glob("*/run.json")):
        try:
            state = json.loads(run_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if state.get("status") in {"starting", "running"} and is_alive(state.get("pid")):
            live.append((run_json.parent, state))
    if len(live) == 1:
        return live[0]
    if not live:
        fail("No live KASP run. Start one with: kasp_verify.py serve", 3)
    fail(
        "Multiple live KASP runs. Pass --run DIR (or export KASP_VERIFY_RUN).",
        2,
        runs=[{"run": str(path), "base_url": state.get("base_url")} for path, state in live],
    )


# ---------------------------------------------------------------------------
# Skill frontmatter lint (Agent Skills contract, shared by OpenCode/Antigravity)
# ---------------------------------------------------------------------------


def _strip_scalar(value: str) -> str:
    value = value.strip()
    if value[:1] in {"'", '"'} and value[-1:] == value[:1]:
        return value[1:-1]
    return value


def parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---"):
        raise ValueError("missing opening '---'")
    lines = text.splitlines()
    try:
        end = lines.index("---", 1)
    except ValueError as exc:
        raise ValueError("missing closing '---'") from exc

    data: dict[str, str] = {}
    idx = 1
    while idx < end:
        line = lines[idx]
        if not line.strip() or line.lstrip().startswith("#"):
            idx += 1
            continue
        if line.startswith((" ", "\t")):
            idx += 1
            continue
        if ":" not in line:
            raise ValueError(f"invalid frontmatter line: {line!r}")
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value in {">", ">-", "|", "|-", ">+", "|+"}:
            collected: list[str] = []
            idx += 1
            while idx < end and (lines[idx].startswith((" ", "\t")) or not lines[idx].strip()):
                collected.append(lines[idx].strip())
                idx += 1
            data[key] = " ".join(part for part in collected if part)
            continue
        data[key] = _strip_scalar(value)
        idx += 1
    return data


def lint_skills() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    names: dict[str, str] = {}
    for skill_file in sorted(SKILLS_DIR.glob("*/SKILL.md")):
        folder = skill_file.parent.name
        errors: list[str] = []
        try:
            meta = parse_frontmatter(skill_file.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            results.append(
                {"name": folder, "path": str(skill_file.relative_to(ROOT)), "status": "fail", "errors": [str(exc)]}
            )
            continue
        name = meta.get("name", "")
        description = meta.get("description", "")
        if not name:
            errors.append("missing name")
        elif name != folder:
            errors.append(f"name '{name}' does not match folder '{folder}'")
        elif name in names:
            errors.append(f"duplicate name, also used by {names[name]}")
        else:
            names[name] = str(skill_file.relative_to(ROOT))
        if len(description) < 30:
            errors.append("description must be at least 30 characters")
        results.append(
            {
                "name": name or folder,
                "path": str(skill_file.relative_to(ROOT)),
                "status": "fail" if errors else "ok",
                "errors": errors,
            }
        )
    return results


# ---------------------------------------------------------------------------
# doctor
# ---------------------------------------------------------------------------


def _check(name: str, status: str, detail: str) -> dict[str, str]:
    return {"name": name, "status": status, "detail": detail}


def command_doctor(args: argparse.Namespace) -> None:
    checks: list[dict[str, str]] = []

    checks.append(
        _check(
            "repo-root",
            "ok" if (ROOT / "main.py").exists() and (ROOT / "kasp").is_dir() else "fail",
            str(ROOT),
        )
    )

    py = sys.version_info
    checks.append(
        _check(
            "python",
            "ok" if py >= (3, 10) else "fail",
            f"{py.major}.{py.minor}.{py.micro} (requires >= 3.10)",
        )
    )

    for module in ("fastapi", "uvicorn", "httpx"):
        found = shutil.which("python3") is not None and _module_available(module)
        checks.append(_check(f"dep:{module}", "ok" if found else "fail", "importable" if found else "missing"))
    checks.append(
        _check(
            "dep:CoolProp",
            "ok" if _module_available("CoolProp") else "warn",
            "importable" if _module_available("CoolProp") else "missing; EOS falls back",
        )
    )

    web_assets = [
        "kasp/web/index.html",
        "kasp/web/src/main.js",
        "kasp/web/src/components/station3dView.js",
        "kasp/web/vendor/three.min.js",
    ]
    missing = [path for path in web_assets if not (ROOT / path).exists()]
    checks.append(
        _check("web-assets", "ok" if not missing else "fail", "all present" if not missing else f"missing: {', '.join(missing)}")
    )

    db_path = ROOT / "kasp_database.db"
    checks.append(
        _check(
            "database",
            "ok" if db_path.exists() else "warn",
            f"{db_path.name} present" if db_path.exists() else "kasp_database.db missing; login/users unavailable",
        )
    )

    node = shutil.which("node")
    if not node:
        checks.append(_check("node", "warn", "not found; JS syntax checks unavailable"))
    else:
        try:
            version = subprocess.run([node, "-v"], capture_output=True, text=True, timeout=5, check=False).stdout.strip()
            major = int(re.sub(r"\D", "", version.split(".")[0]) or 0)
            checks.append(_check("node", "ok" if major >= 18 else "warn", f"{version} (requires >= 18)"))
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            checks.append(_check("node", "warn", f"version check failed: {exc}"))

    skill_results = lint_skills()
    bad_skills = [item for item in skill_results if item["status"] != "ok"]
    checks.append(
        _check(
            "skills",
            "fail" if bad_skills else "ok",
            f"{len(skill_results)} skills, {len(bad_skills)} invalid",
        )
    )

    registry = FEATURES_FILE
    try:
        features = json.loads(registry.read_text(encoding="utf-8"))
        ids = [item.get("id") for item in features]
        registry_ok = bool(features) and len(ids) == len(set(ids)) and all(item.get("expected") for item in features)
        checks.append(
            _check(
                "feature-map",
                "ok" if registry_ok else "fail",
                f"{len(features)} features in {registry.relative_to(ROOT)}",
            )
        )
    except (OSError, json.JSONDecodeError) as exc:
        checks.append(_check("feature-map", "fail", f"cannot read features.json: {exc}"))

    opencode_config = ROOT / ".opencode" / "opencode.json"
    try:
        config = json.loads(opencode_config.read_text(encoding="utf-8"))
        paths = config.get("skills", {}).get("paths", [])
        wired = ".agents/skills" in paths
        checks.append(
            _check(
                "opencode-wiring",
                "ok" if wired else "warn",
                f"skill paths: {paths}" if wired else "'.agents/skills' not listed in .opencode/opencode.json",
            )
        )
    except (OSError, json.JSONDecodeError) as exc:
        checks.append(_check("opencode-wiring", "warn", f"config not readable: {exc}"))

    checks.append(
        _check(
            "agents-md",
            "ok" if (ROOT / "AGENTS.md").exists() else "warn",
            "root AGENTS.md present" if (ROOT / "AGENTS.md").exists() else "root AGENTS.md missing",
        )
    )

    manifest_path = ROOT / ".agents" / "harness.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        harnesses = manifest.get("harnesses", {})
        manifest_ok = (
            manifest.get("skillRoot") == ".agents/skills"
            and {"opencode", "antigravity"}.issubset(harnesses)
            and bool(manifest.get("validation"))
        )
        checks.append(
            _check(
                "harness-manifest",
                "ok" if manifest_ok else "fail",
                f"skillRoot={manifest.get('skillRoot')} harnesses={sorted(harnesses)}",
            )
        )
    except (OSError, json.JSONDecodeError) as exc:
        checks.append(_check("harness-manifest", "fail", f"cannot read .agents/harness.json: {exc}"))

    busy = [port for port in (8000, 8080, 8081) if not port_free(port)]
    checks.append(
        _check(
            "ports",
            "ok",
            "free: 8000/8080/8081" if not busy else f"in use (fine, isolated runs avoid them): {busy}",
        )
    )

    failed = [item for item in checks if item["status"] == "fail"]
    warned = [item for item in checks if item["status"] == "warn"]
    status = "fail" if failed else ("warn" if warned else "ok")
    emit(
        {
            "command": "doctor",
            "ok": status != "fail",
            "status": status,
            "root": str(ROOT),
            "checks": checks,
            "skills": skill_results,
        },
        0 if status != "fail" else 1,
    )


def _module_available(name: str) -> bool:
    import importlib.util

    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


# ---------------------------------------------------------------------------
# serve / status / stop
# ---------------------------------------------------------------------------


def _tail(path: Path, lines: int = 40) -> list[str]:
    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:]
    except OSError:
        return []


def command_serve(args: argparse.Namespace) -> None:
    if args.port:
        port = int(args.port)
        if not port_free(port):
            fail(f"Port {port} is already in use. Omit --port to pick a free one.", 3)
    else:
        port = free_port()

    stamp = time.strftime("%Y%m%d-%H%M%S")
    run_dir = RUNS_DIR / f"{stamp}-{os.getpid()}"
    suffix = 1
    while run_dir.exists():
        suffix += 1
        run_dir = RUNS_DIR / f"{stamp}-{os.getpid()}-{suffix}"
    run_dir.mkdir(parents=True, exist_ok=True)
    log_path = run_dir / "server.log"

    env = os.environ.copy()
    env.update(
        {
            "KASP_API_ENABLE": "1",
            "KASP_API_HOST": HOST,
            "KASP_API_PORT": str(port),
            "KASP_API_TOKEN": DEFAULT_TOKEN,
            "PYTHONUNBUFFERED": "1",
        }
    )

    log_handle = log_path.open("w", encoding="utf-8")
    process = subprocess.Popen(
        [sys.executable, "run_web.py"],
        cwd=ROOT,
        env=env,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        text=True,
    )
    log_handle.close()

    base_url = f"http://{HOST}:{port}"
    state: dict[str, Any] = {
        "version": 1,
        "run_id": run_dir.name,
        "root": str(ROOT),
        "host": HOST,
        "port": port,
        "base_url": base_url,
        "pid": process.pid,
        "pgid": process.pid,
        "log": str(log_path),
        "started_at": now_iso(),
        "status": "starting",
    }
    write_json(run_dir / "run.json", state)
    (STATE_DIR / "last_run").write_text(str(run_dir), encoding="utf-8")

    ready, health_result = wait_for_health(base_url, args.timeout)
    if not ready:
        state["status"] = "failed"
        state["stopped_at"] = now_iso()
        state["failure"] = health_result
        write_json(run_dir / "run.json", state)
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except OSError:
            pass
        emit(
            {
                "command": "serve",
                "ok": False,
                "run": str(run_dir),
                "base_url": base_url,
                "health": health_result,
                "log_tail": _tail(log_path),
            },
            1,
        )

    index = http_request(f"{base_url}/", timeout=10)
    index_ok = index.get("status") == 200 and "kasp" in str(index.get("text", "")).lower()
    state["status"] = "running"
    state["health"] = health_result.get("json")
    state["index_ok"] = index_ok
    write_json(run_dir / "run.json", state)

    emit(
        {
            "command": "serve",
            "ok": index_ok,
            "run": str(run_dir),
            "base_url": base_url,
            "pid": process.pid,
            "health": health_result.get("json"),
            "index_status": index.get("status"),
            "next": f"export KASP_VERIFY_RUN={run_dir}",
        },
        0 if index_ok else 1,
    )


def command_status(args: argparse.Namespace) -> None:
    run_dir, state = resolve_run(args.run)
    alive = is_alive(state.get("pid"))
    probe = health(state.get("base_url", ""), timeout=3)
    healthy = probe.get("status") == 200
    if not alive and state.get("status") not in {"stopped", "failed"}:
        state["status"] = "stale"
        write_json(run_dir / "run.json", state)
    emit(
        {
            "command": "status",
            "ok": alive and healthy,
            "run": str(run_dir),
            "state": state.get("status"),
            "pid_alive": alive,
            "base_url": state.get("base_url"),
            "health": probe.get("json") or probe.get("text"),
            "log": state.get("log"),
        },
        0 if (alive and healthy) else 1,
    )


def command_stop(args: argparse.Namespace) -> None:
    run_dir, state = resolve_run(args.run)
    pid = state.get("pid")
    if not is_alive(pid):
        state["status"] = "stopped"
        state.setdefault("stopped_at", now_iso())
        write_json(run_dir / "run.json", state)
        emit({"command": "stop", "ok": True, "run": str(run_dir), "detail": "already stopped"})

    command = process_command(int(pid))
    if command and "run_web.py" not in command:
        fail(
            f"Refusing to stop PID {pid}: command does not look like run_web.py ({command[:120]}).",
            1,
        )

    try:
        os.killpg(int(pid), signal.SIGTERM)
    except OSError:
        try:
            os.kill(int(pid), signal.SIGTERM)
        except OSError:
            pass

    deadline = time.monotonic() + args.timeout
    while time.monotonic() < deadline and is_alive(int(pid)):
        time.sleep(0.2)

    forced = False
    if is_alive(int(pid)):
        forced = True
        try:
            os.killpg(int(pid), signal.SIGKILL)
        except OSError:
            try:
                os.kill(int(pid), signal.SIGKILL)
            except OSError:
                pass

    state["status"] = "stopped"
    state["stopped_at"] = now_iso()
    state["forced"] = forced
    write_json(run_dir / "run.json", state)
    emit({"command": "stop", "ok": True, "run": str(run_dir), "forced": forced})


# ---------------------------------------------------------------------------
# api probe
# ---------------------------------------------------------------------------


def command_api(args: argparse.Namespace) -> None:
    run_dir, state = resolve_run(args.run)
    base_url = state["base_url"]
    checks: list[dict[str, Any]] = []

    for path in ("/api/health", "/api/constants"):
        result = http_request(f"{base_url}{path}")
        checks.append({"path": path, "status": result.get("status"), "ok": result.get("status") == 200})

    login_result: dict[str, Any] | None = None
    user: dict[str, Any] | None = None
    login_error: str | None = None
    username = os.environ.get("KASP_VERIFY_USER", "")
    password = os.environ.get("KASP_VERIFY_PASSWORD", "")

    if args.login or (username and password):
        if not (username and password):
            fail(
                "Login requested but KASP_VERIFY_USER / KASP_VERIFY_PASSWORD are not set.",
                2,
            )
        jar = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        login_result = http_request(
            f"{base_url}/api/v1/auth/login",
            method="POST",
            payload={"username": username, "password": password},
            opener=opener,
        )
        body = login_result.get("json") or {}
        if login_result.get("status") == 200 and isinstance(body, dict):
            csrf = body.get("csrf_token", "")
            token = body.get("token", "")
            me = http_request(
                f"{base_url}/api/v1/auth/me",
                headers={"X-CSRF-Token": csrf, "Authorization": f"Bearer {token}"},
                opener=opener,
            )
            user = (me.get("json") or {}).get("user") if isinstance(me.get("json"), dict) else None
            checks.append({"path": "/api/v1/auth/me", "status": me.get("status"), "ok": me.get("status") == 200})
            logout = http_request(
                f"{base_url}/api/v1/auth/logout",
                method="POST",
                headers={"X-CSRF-Token": csrf, "Authorization": f"Bearer {token}"},
                opener=opener,
            )
            checks.append({"path": "/api/v1/auth/logout", "status": logout.get("status"), "ok": logout.get("status") < 400})
        else:
            login_error = str((login_result.get("json") or {}).get("detail") or login_result.get("text"))
        checks.append({"path": "/api/v1/auth/login", "status": login_result.get("status"), "ok": not login_error})
    else:
        checks.append(
            {
                "path": "/api/v1/auth/login",
                "status": "skipped",
                "ok": True,
                "detail": "set KASP_VERIFY_USER and KASP_VERIFY_PASSWORD to probe auth",
            }
        )

    ok = all(item["ok"] for item in checks)
    emit(
        {
            "command": "api",
            "ok": ok,
            "run": str(run_dir),
            "base_url": base_url,
            "checks": checks,
            "user": {"username": user.get("username"), "role": user.get("role")} if user else None,
            "login_error": login_error,
        },
        0 if ok else 1,
    )


# ---------------------------------------------------------------------------
# feature map
# ---------------------------------------------------------------------------


def load_features() -> list[dict[str, Any]]:
    try:
        data = json.loads(FEATURES_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"Cannot read feature map {FEATURES_FILE}: {exc}", 3)
    return data


def command_features(args: argparse.Namespace) -> None:
    features = load_features()
    if args.area:
        features = [item for item in features if item.get("area") == args.area]
    if args.feature:
        features = [item for item in features if item.get("id") == args.feature]
        if not features:
            fail(f"Unknown feature id: {args.feature}", 2)
    emit({"command": "features", "ok": True, "count": len(features), "features": features})


# ---------------------------------------------------------------------------
# evidence
# ---------------------------------------------------------------------------


def evidence_paths(run_dir: Path | None) -> tuple[Path, Path, Path]:
    base = run_dir if run_dir else GLOBAL_EVIDENCE_DIR
    base.mkdir(parents=True, exist_ok=True)
    return base, base / "evidence.jsonl", base / "ledger.md"


def _evidence_entries(jsonl: Path) -> list[dict[str, Any]]:
    if not jsonl.exists():
        return []
    entries: list[dict[str, Any]] = []
    for line in jsonl.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def _write_ledger(ledger: Path, entries: list[dict[str, Any]]) -> None:
    counts: dict[str, int] = {}
    for entry in entries:
        counts[entry["result"]] = counts.get(entry["result"], 0) + 1
    summary = " · ".join(f"{RESULT_STYLES.get(key, key)} {key}: {value}" for key, value in sorted(counts.items()))
    lines = [
        "# KASP Verification Ledger",
        "",
        f"Updated: {now_iso()}",
        "",
        f"**Summary:** {summary or 'no evidence yet'}",
        "",
        "| Time | Feature | Result | Entry | Expected | Actual | Artifact |",
        "|---|---|---|---|---|---|---|",
    ]
    for entry in entries:
        artifact = entry.get("artifact") or ""
        if artifact:
            artifact = f"[file]({artifact})"
        row = [
            entry.get("timestamp", ""),
            entry.get("feature", ""),
            f"{RESULT_STYLES.get(entry.get('result'), '')} {entry.get('result', '')}",
            str(entry.get("entry", "")).replace("|", "\\|"),
            str(entry.get("expected", "")).replace("|", "\\|"),
            str(entry.get("actual", "")).replace("|", "\\|"),
            artifact,
        ]
        lines.append("| " + " | ".join(row) + " |")
    ledger.write_text("\n".join(lines) + "\n", encoding="utf-8")


def command_evidence(args: argparse.Namespace) -> None:
    run_dir: Path | None = None
    if args.run or os.environ.get("KASP_VERIFY_RUN"):
        run_dir, _ = resolve_run(args.run)

    if args.evidence_action == "list":
        base, jsonl, ledger = evidence_paths(run_dir)
        entries = _evidence_entries(jsonl)
        emit(
            {
                "command": "evidence list",
                "ok": True,
                "path": str(jsonl),
                "ledger": str(ledger) if ledger.exists() else None,
                "count": len(entries),
                "entries": entries,
            }
        )

    base, jsonl, ledger = evidence_paths(run_dir)
    artifact = args.artifact
    if artifact:
        artifact_path = Path(artifact)
        if not artifact_path.is_absolute():
            artifact_path = (ROOT / artifact_path).resolve()
        if not artifact_path.exists():
            fail(f"Artifact not found: {artifact_path}", 1)
        try:
            artifact = str(artifact_path.relative_to(ROOT))
        except ValueError:
            artifact = str(artifact_path)

    entry = {
        "timestamp": now_iso(),
        "feature": args.feature,
        "result": args.result,
        "entry": args.entry,
        "expected": args.expected or "",
        "actual": args.actual or "",
        "artifact": artifact or "",
        "note": args.note or "",
    }
    if entry["result"] == "fail" and not entry["actual"]:
        fail("A failed result needs --actual describing what was observed.", 2)

    with jsonl.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    entries = _evidence_entries(jsonl)
    _write_ledger(ledger, entries)
    emit(
        {
            "command": "evidence add",
            "ok": entry["result"] not in {"fail", "blocked"},
            "path": str(jsonl),
            "ledger": str(ledger),
            "entry": entry,
            "count": len(entries),
        },
        0 if entry["result"] not in {"fail", "blocked"} else 1,
    )


# ---------------------------------------------------------------------------
# selftest
# ---------------------------------------------------------------------------


def command_selftest(args: argparse.Namespace) -> None:
    checks: list[dict[str, Any]] = []

    parsed = parse_frontmatter("---\nname: demo\ndescription: >-\n  A demo skill that is long enough.\n---\n\n# Demo\n")
    checks.append(
        {
            "name": "frontmatter-block-scalar",
            "ok": parsed.get("name") == "demo" and "long enough" in parsed.get("description", ""),
        }
    )

    with tempfile.TemporaryDirectory(prefix="kasp-verify-") as tmp:
        base, jsonl, ledger = evidence_paths(Path(tmp))
        entry = {
            "timestamp": now_iso(),
            "feature": "F00",
            "result": "pass",
            "entry": "selftest",
            "expected": "ledger written",
            "actual": "ledger written",
            "artifact": "",
            "note": "",
        }
        jsonl.write_text(json.dumps(entry) + "\n", encoding="utf-8")
        _write_ledger(ledger, _evidence_entries(jsonl))
        checks.append({"name": "evidence-ledger", "ok": ledger.exists() and "F00" in ledger.read_text(encoding="utf-8")})

    features = load_features()
    ids = [item.get("id") for item in features]
    required = {"id", "area", "title", "entrypoint", "expected"}
    checks.append(
        {
            "name": "feature-registry",
            "ok": bool(features)
            and len(ids) == len(set(ids))
            and all(required.issubset(item) for item in features),
            "count": len(features),
        }
    )

    skills = lint_skills()
    checks.append(
        {
            "name": "skill-frontmatter",
            "ok": bool(skills) and all(item["status"] == "ok" for item in skills),
            "count": len(skills),
        }
    )

    ok = all(check["ok"] for check in checks)
    emit({"command": "selftest", "ok": ok, "checks": checks}, 0 if ok else 1)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kasp_verify.py",
        description="Verify KASP through the real app: doctor, serve, inspect, evidence, stop.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    doctor = sub.add_parser("doctor", help="read-only environment and skill checks")
    doctor.set_defaults(func=command_doctor)

    serve = sub.add_parser("serve", help="start an isolated web instance")
    serve.add_argument("--port", type=int, default=0, help="fixed port; default picks a free one")
    serve.add_argument("--timeout", type=float, default=60.0, help="health timeout in seconds")
    serve.set_defaults(func=command_serve)

    status = sub.add_parser("status", help="report run status")
    status.add_argument("--run", help="run directory (default: only live run)")
    status.set_defaults(func=command_status)

    stop = sub.add_parser("stop", help="stop the run's own server")
    stop.add_argument("--run", help="run directory (default: only live run)")
    stop.add_argument("--timeout", type=float, default=10.0)
    stop.set_defaults(func=command_stop)

    api = sub.add_parser("api", help="probe API contracts")
    api.add_argument("--run", help="run directory (default: only live run)")
    api.add_argument("--login", action="store_true", help="require a login probe (needs env credentials)")
    api.set_defaults(func=command_api)

    features = sub.add_parser("features", help="list the feature map")
    features.add_argument("--area")
    features.add_argument("--feature")
    features.set_defaults(func=command_features)

    evidence = sub.add_parser("evidence", help="append or read verification evidence")
    evidence_sub = evidence.add_subparsers(dest="evidence_action", required=True)
    add = evidence_sub.add_parser("add")
    add.add_argument("--run", help="run directory; omit for the global ledger")
    add.add_argument("--feature", required=True, help="feature id, e.g. F07")
    add.add_argument("--result", required=True, choices=sorted(RESULT_STYLES))
    add.add_argument("--entry", required=True, help="user entry point that was exercised")
    add.add_argument("--expected")
    add.add_argument("--actual")
    add.add_argument("--artifact", help="screenshot or file path")
    add.add_argument("--note")
    listing = evidence_sub.add_parser("list")
    listing.add_argument("--run", help="run directory; omit for the global ledger")
    evidence.set_defaults(func=command_evidence)

    selftest = sub.add_parser("selftest", help="test CLI helpers")
    selftest.set_defaults(func=command_selftest)

    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        args.func(args)
    except CliError as exc:
        print(
            json.dumps(
                {"ok": False, "error": str(exc), "exit_code": exc.exit_code, **exc.extra},
                ensure_ascii=False,
                indent=2,
            )
        )
        return exc.exit_code
    except KeyboardInterrupt:
        print(json.dumps({"ok": False, "error": "interrupted"}, ensure_ascii=False))
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
