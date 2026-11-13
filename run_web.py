"""KASP Web Platform Server Launcher (run_web.py).

Starts the FastAPI + Modular ES6 web platform for local engineering use
and opens the web UI in the default system browser once healthy.
"""

import argparse
import os
import socket
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

# Set environment defaults for local web platform
os.environ.setdefault("KASP_API_ENABLE", "1")
os.environ.setdefault("KASP_API_TOKEN", "kasp-local-token")
os.environ.setdefault("KASP_API_HOST", "127.0.0.1")
try:
    _mpl_dir = Path.home() / ".kasp" / "mplconfig"
    _mpl_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(_mpl_dir))
except OSError:
    pass


def _ensure_std_streams() -> None:
    """Windowed PyInstaller bundles (console=False) set stdout/stderr to None.

    Redirect them to a rotating/appendable user log file so Uvicorn's logger
    never fails with AttributeError: 'NoneType' object has no attribute 'isatty'.
    """
    if sys.stdout is not None and sys.stderr is not None:
        return
    try:
        log_dir = Path.home() / ".kasp" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        stream = open(log_dir / "kasp-web.log", "a", encoding="utf-8", buffering=1)
    except OSError:
        stream = open(os.devnull, "w", encoding="utf-8")
    if sys.stdout is None:
        sys.stdout = stream
    if sys.stderr is None:
        sys.stderr = stream


def find_available_port(preferred_ports=(8080, 8000, 8081, 8082), host: str = "127.0.0.1") -> int:
    """Return the first preferred port that can be bound, or an ephemeral free port."""
    for port in preferred_ports:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((host, port))
                return port
            except OSError:
                continue
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, 0))
        return int(s.getsockname()[1])


def _wait_and_open_browser(url: str, health_url: str, timeout_s: float = 45.0) -> None:
    """Poll /api/health until ready, then open the web UI in the default browser."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(health_url, timeout=1.0) as resp:
                if resp.status == 200:
                    webbrowser.open(url, new=2)
                    return
        except Exception:
            time.sleep(0.25)


def _get_web_version() -> str:
    try:
        from release_metadata import WEB_RELEASE_VERSION
        return WEB_RELEASE_VERSION
    except Exception:
        return "4.1.1-web"


def main(argv=None) -> None:
    _ensure_std_streams()

    parser = argparse.ArgumentParser(description="KASP Web Platform Launcher")
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not automatically open the system web browser",
    )
    args, _ = parser.parse_known_args(argv)

    import uvicorn
    from kasp.api.server import app as kasp_web_app

    host = os.environ.get("KASP_API_HOST", "127.0.0.1")
    specified_port = os.environ.get("KASP_API_PORT")
    port = int(specified_port) if specified_port else find_available_port(host=host)
    os.environ["KASP_API_PORT"] = str(port)

    version = _get_web_version()
    url = f"http://{host}:{port}/"
    health_url = f"http://{host}:{port}/api/health"

    print("============================================================")
    print(f"KASP Web Platform v{version} Starting...")
    print(f"URL: {url}")
    print(f"API Docs: {url}docs")
    print("============================================================", flush=True)

    no_browser = args.no_browser or os.environ.get("KASP_WEB_NO_BROWSER", "").lower() in (
        "1",
        "true",
        "yes",
    )
    if not no_browser:
        threading.Thread(
            target=_wait_and_open_browser,
            args=(url, health_url),
            daemon=True,
        ).start()

    uvicorn.run(
        kasp_web_app,
        host=host,
        port=port,
        log_level="info",
        use_colors=not getattr(sys, "frozen", False),
    )


if __name__ == "__main__":
    main()
