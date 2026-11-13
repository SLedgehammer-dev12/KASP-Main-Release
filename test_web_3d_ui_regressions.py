"""
Faz 2 TDD Regresyon Paketi — KASP Web 3D Dijital İkiz, Teardown ve İstasyon UI Sözleşmeleri.

Doğrulanan alanlar:
1. `stationTab.js` + `components.css` + `locales.js` (`webui`):
   - `syncStationInputsFromDesign` fonksiyonunun tanımlı ve bağlı olması (`ReferenceError` önlemi).
   - 3D görünümde `.station-inspector-card` ile `#equip-telemetry-hud` çakışmaması ve
     `#btn-close-inspector` içinde `clearSelection()` + `highlightSvgEquipment(null)` çağrısı.
   - `_s2dAbort`, `unsubscribeStore` / `uiStore` abonelikleri ve `debounceTimer` temizliği.
   - `locales.js` `tr` / `en` anahtar kümelerinin tam eşliği (`set(tr) == set(en)`) ve `teardown_*` anahtarları.
2. `station3dView.js` (`scene3d`):
   - `onRootKeyDown` içinde form elemanları (`input` / `textarea` / `select`) ve `#kasp-equipment-teardown` koruması.
   - Yardımcı hatlarda (`pig_bypass`, `pig_kicker_receiver`, `pig_kicker_launcher`, `psv_inlet`, `esd_riser`)
     sabit sayısal yarıçap yerine `visualPipeRadius` türetimi ve `parentLineKey` telemetri mirası.
   - `L-113` (`cooler_bypass`) ve `L-114` (`cooler_outlet`) etiketlerinin backend `PipeSizingService` ile birebir uyumu.
   - `destroy()` içinde `THREE.Sprite` paylaşımlı geometri koruması (`!obj.isSprite`), `station-3d-expanded` temizliği
     ve `buildEquipmentTelemetryHtml` içinde `escapeHtml` kullanımı.
3. `equipmentTeardown.js` (`teardown`):
   - `outlet_pipe_size` alan okuması (`outlet_header_pipe_size` kalmaması).
   - Siklon sağ/sol yarı kabuklarının (`thetaStart`) dışa doğru (`±X`) patlatılması (birbirinin içinden geçmemesi).
   - `LineSegments` tel kafeslerinin hedef mesh pozisyon ve rotasyonuyla hizalı olması (Three.js `Box3` doğrulaması).
   - `closeEquipmentTeardown()` içinde `cancelAnimationFrame` temizliği, `escapeHtml` ve `locales.js` `t()` kullanımı.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from kasp.services.pipe_sizing_service import PipeSizingService

REPO_ROOT = Path(__file__).resolve().parent
STATION_TAB_JS = REPO_ROOT / "kasp/web/src/components/stationTab.js"
STATION_3D_JS = REPO_ROOT / "kasp/web/src/components/station3dView.js"
TEARDOWN_JS = REPO_ROOT / "kasp/web/src/components/equipmentTeardown.js"
LOCALES_JS = REPO_ROOT / "kasp/web/src/i18n/locales.js"
COMPONENTS_CSS = REPO_ROOT / "kasp/web/css/components.css"

REQUIRED_TEARDOWN_I18N_KEYS = (
    "teardown_btn_explode",
    "teardown_btn_assemble",
    "teardown_btn_reset",
    "teardown_btn_close",
    "teardown_slider_label",
    "teardown_sec_process",
    "teardown_sec_parts",
)


def _extract_js_function_block(source: str, signature_regex: str) -> str:
    """Extract a brace-balanced JS function block starting from signature_regex."""
    match = re.search(signature_regex, source)
    assert match, f"JS imzası bulunamadı: {signature_regex}"
    brace_start = source.find("{", match.start())
    assert brace_start != -1, f"Fonksiyon gövdesi bulunamadı: {signature_regex}"
    depth = 0
    in_str: str | None = None
    escaped = False
    for idx in range(brace_start, len(source)):
        ch = source[idx]
        if in_str:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == in_str:
                in_str = None
            continue
        if ch in ("'", '"', "`"):
            in_str = ch
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return source[match.start() : idx + 1]
    raise AssertionError(f"Kapanmayan süslü parantez: {signature_regex}")


def _extract_pipe_route_calls(source: str) -> list[str]:
    """Return all createCadPipeRoute(...) call slices in station3dView.js."""
    calls: list[str] = []
    needle = "createCadPipeRoute("
    pos = 0
    while True:
        idx = source.find(needle, pos)
        if idx == -1:
            break
        paren_start = idx + len("createCadPipeRoute")
        depth = 0
        in_str: str | None = None
        escaped = False
        for cursor in range(paren_start, len(source)):
            ch = source[cursor]
            if in_str:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == in_str:
                    in_str = None
                continue
            if ch in ("'", '"', "`"):
                in_str = ch
            elif ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    calls.append(source[idx : cursor + 1])
                    pos = cursor + 1
                    break
        else:
            break
    return calls


# ─────────────────────────────────────────────────────────────────────────────
# 1. WEBUI: stationTab.js + components.css + locales.js
# ─────────────────────────────────────────────────────────────────────────────


def test_station_tab_defines_sync_station_inputs_from_design():
    """#btn-station-sync-recalc çağrısının hedeflediği syncStationInputsFromDesign tanımlı olmalıdır."""
    src = STATION_TAB_JS.read_text(encoding="utf-8")
    assert "syncStationInputsFromDesign()" in src
    defined = re.search(
        r"(?:function\s+syncStationInputsFromDesign\s*\(|(?:const|let|var)\s+syncStationInputsFromDesign\s*=)",
        src,
    )
    assert defined is not None, "syncStationInputsFromDesign() çağrılıyor fakat tanımlı değil (ReferenceError)."


def test_station_tab_3d_inspector_no_hud_overlap_and_clears_selection():
    """3D modda .station-inspector-card sağ üst #equip-telemetry-hud ile çakışmamalı ve kapatınca clearSelection() çağırmalıdır."""
    src = STATION_TAB_JS.read_text(encoding="utf-8")
    css = COMPONENTS_CSS.read_text(encoding="utf-8")

    # Kapatma aksiyonu 3D seçimi ve 2D SVG vurgusunu temizlemeli
    assert re.search(r"clearSelection\s*(?:\?\.)?\(", src), "#btn-close-inspector 3D clearSelection() çağırmıyor."
    assert "highlightSvgEquipment(null)" in src, "Inspector kapatıldığında highlightSvgEquipment(null) çağrılmıyor."

    # 3D modda ya inspector çekmecesi bastırılmalı ya da CSS sağ-üst (top+right) köşeden ayrılmalı
    inspector_fn = _extract_js_function_block(src, r"function\s+updateInspectorDrawer\s*\(")
    js_guards_3d_overlap = ('"3d"' in inspector_fn or "'3d'" in inspector_fn) or bool(
        re.search(r"onSelectEquipment[\s\S]{0,260}viewMode", src)
        or re.search(r"viewMode\s*[!=]==?\s*['\"]3d['\"][\s\S]{0,200}(?:updateInspectorDrawer|renderInspectorDrawer)", src)
    )

    css_rule_match = re.search(r"\.station-inspector-card\s*\{([^}]*)\}", css)
    assert css_rule_match, ".station-inspector-card kuralı components.css içinde bulunamadı."
    css_body = css_rule_match.group(1)
    css_anchored_top_right = bool(re.search(r"\btop\s*:", css_body) and re.search(r"\bright\s*:", css_body))

    assert js_guards_3d_overlap or not css_anchored_top_right, (
        "3D görünümde .station-inspector-card sağ-üstte #equip-telemetry-hud üstüne biniyor."
    )


def test_station_tab_cleans_up_abort_store_and_debounce_timer():
    """stationTab.js yeniden bağlanma ve mod geçişlerinde _s2dAbort, store abonelikleri ve debounceTimer temizlemelidir."""
    src = STATION_TAB_JS.read_text(encoding="utf-8")

    # _s2dAbort yalnızca bindStation2dControls başında değil, 3D geçişi/temizlikte de abort edilmeli
    abort_calls = re.findall(r"_s2dAbort(?:\?\.)?\.?abort\s*(?:\?\.)?\(\)", src)
    assert len(abort_calls) >= 2, "_s2dAbort?.abort() mod geçişi veya cleanup içinde çağrılmıyor."

    # projectStore aboneliği oluşturulduğu gibi cleanup içinde çağrılarak kapatılmalı
    assert re.search(r"\bunsubscribeStore\s*(?:\?\.)?\(\s*\)", src), "unsubscribeStore() cleanup içinde çağrılmıyor."

    # Dil tepkiselliği için uiStore.subscribe bağlanmalı
    assert "uiStore.subscribe" in src, "stationTab.js dil değişimi için uiStore.subscribe kullanmıyor."

    # debounceTimer hem canlı güncellemede hem cleanup'ta temizlenmeli
    clear_timer_calls = re.findall(r"clearTimeout\s*\(\s*debounceTimer\s*\)", src)
    assert len(clear_timer_calls) >= 2, "clearTimeout(debounceTimer) cleanup içinde çağrılmıyor."


def test_locales_tr_en_exact_parity_and_teardown_keys():
    """locales.js içinde set(tr) == set(en) tam eşliği ve teardown_* anahtarları eksiksiz olmalıdır."""
    node_bin = shutil.which("node")
    assert node_bin, "Node.js çalışma zamanı bulunamadı."

    script = f"""
import {{ i18nStrings, t }} from {json.dumps(LOCALES_JS.as_uri())};
const trKeys = Object.keys(i18nStrings.tr || {{}});
const enKeys = Object.keys(i18nStrings.en || {{}});
const teardownSample = {{}};
for (const k of {json.dumps(list(REQUIRED_TEARDOWN_I18N_KEYS))}) {{
  teardownSample[k] = {{ tr: t(k, "tr"), en: t(k, "en") }};
}}
console.log(JSON.stringify({{ trKeys, enKeys, teardownSample }}));
"""
    proc = subprocess.run([node_bin, "--input-type=module", "-e", script], capture_output=True, text=True, check=True)
    payload = json.loads(proc.stdout.strip())
    tr_set = set(payload["trKeys"])
    en_set = set(payload["enKeys"])

    assert tr_set == en_set, (
        f"locales.js tr/en anahtar farkı: tr-en={sorted(tr_set - en_set)}, en-tr={sorted(en_set - tr_set)}"
    )
    for key in REQUIRED_TEARDOWN_I18N_KEYS:
        assert key in tr_set, f"locales.js içinde '{key}' anahtarı eksik."
        assert payload["teardownSample"][key]["tr"] != key
        assert payload["teardownSample"][key]["en"] != key


# ─────────────────────────────────────────────────────────────────────────────
# 2. SCENE3D: station3dView.js
# ─────────────────────────────────────────────────────────────────────────────


def test_station_3d_keydown_guards_form_controls_and_teardown_modal():
    """onRootKeyDown form girdilerinde (input/textarea/select) ve açık #kasp-equipment-teardown modalında kısayolları engellemelidir."""
    src = STATION_3D_JS.read_text(encoding="utf-8")
    keydown_fn = _extract_js_function_block(src, r"function\s+onRootKeyDown\s*\(")
    lowered = keydown_fn.lower()

    for tag in ("input", "textarea", "select"):
        assert tag in lowered, f"onRootKeyDown içinde <{tag}> form elemanı koruması eksik."
    assert "kasp-equipment-teardown" in keydown_fn, (
        "onRootKeyDown içinde açık #kasp-equipment-teardown modal koruması eksik."
    )


def test_station_3d_auxiliary_lines_use_visual_pipe_radius_and_parent_telemetry():
    """5 yardımcı hat (pig_bypass, pig_kicker_*, psv_inlet, esd_riser) visualPipeRadius ve parentLineKey mirası kullanmalıdır."""
    src = STATION_3D_JS.read_text(encoding="utf-8")
    calls = _extract_pipe_route_calls(src)
    assert len(calls) >= 15

    # visualPipeRadius ile tanımlanan yarıçap değişkenlerini topla
    radius_vars = set(re.findall(r"\bconst\s+(r[A-Za-z0-9_]+)\s*=\s*visualPipeRadius\s*\(", src))

    aux_keys = ("pig_bypass", "pig_kicker_receiver", "pig_kicker_launcher", "psv_inlet", "esd_riser")
    for line_key in aux_keys:
        matching = [c for c in calls if f'lineKey: "{line_key}"' in c or f"lineKey: '{line_key}'" in c]
        assert matching, f"station3dView.js içinde korunması gereken lineKey='{line_key}' bulunamadı."
        for call_src in matching:
            # İkinci argüman (points dizisinden sonraki radius ifadesi) sabit 0.30/0.32/0.34 olmamalı
            after_points = call_src.split("],", 1)[1] if "]," in call_src else call_src
            radius_arg = after_points.split(",\n", 1)[0].strip()
            uses_visual = "visualPipeRadius(" in radius_arg or any(
                re.search(rf"\b{re.escape(var)}\b", radius_arg) for var in radius_vars
            )
            no_legacy_multiplier = not re.search(r"Math\.max\(\s*0\.5[05]?\s*,", radius_arg)
            no_hardcoded_float = not re.fullmatch(r"0\.\d+", radius_arg)
            assert uses_visual and no_legacy_multiplier and no_hardcoded_float, (
                f"{line_key} rotası sabit/çarpan yarıçap kullanıyor: {radius_arg!r}"
            )

    # Boru HUD'da 0.0 / - göstermemek için parentLineKey mirası bulunmalı
    assert "parentLineKey" in src, "Yardımcı hatlar için parentLineKey telemetri mirası eksik."
    pipe_hud_fn = _extract_js_function_block(src, r"function\s+buildPipeTelemetryHtml\s*\(")
    assert "parentLineKey" in pipe_hud_fn or "fallback" in pipe_hud_fn.lower() or "resolved" in pipe_hud_fn.lower(), (
        "buildPipeTelemetryHtml yardımcı hatlarda ana hat telemetrisini miras almıyor."
    )


def test_station_3d_cooler_bypass_and_outlet_line_tags_match_backend():
    """cooler_bypass -> L-113 ve cooler_outlet -> L-114 etiketleri backend PipeSizingService ile aynı olmalıdır."""
    net = PipeSizingService.size_station_network(
        mass_flow_kgs=120.0,
        p_in_bar=45.0,
        p_out_bar=75.0,
        t_in_c=15.0,
        t_discharge_c=82.0,
        t_cooled_c=45.0,
        comp_op_count=3,
        cyclone_op_count=2,
        filter_op_count=2,
        cooler_bays_count=4,
    )
    assert net["lines"]["cooler_bypass"]["tag"] == "L-113"
    assert net["lines"]["cooler_outlet"]["tag"] == "L-114"

    src = STATION_3D_JS.read_text(encoding="utf-8")
    calls = _extract_pipe_route_calls(src)

    outlet_calls = [c for c in calls if 'lineKey: "cooler_outlet"' in c]
    bypass_calls = [c for c in calls if 'lineKey: "cooler_bypass"' in c]
    assert outlet_calls and bypass_calls

    for c in outlet_calls:
        assert "L-114" in c and "L-113" not in c, f"cooler_outlet etiketi L-114 olmalı: {c}"
    for c in bypass_calls:
        assert "L-113" in c and "L-114" not in c, f"cooler_bypass etiketi L-113 olmalı: {c}"


def test_station_3d_destroy_protects_sprite_geometry_and_escapes_hud_html():
    """destroy() içinde !obj.isSprite geometri koruması, tam ekran sınıf temizliği ve HUD escapeHtml bulunmalıdır."""
    src = STATION_3D_JS.read_text(encoding="utf-8")

    destroy_block = _extract_js_function_block(src, r"\n\s{4}destroy\s*:\s*\(\)\s*=>")
    assert "scene.traverse" in destroy_block, "Ana destroy() metodu yakalanamadı."

    assert "!obj.isSprite" in destroy_block, "destroy() THREE.Sprite paylaşımlı geometrisini !obj.isSprite ile korumuyor."
    assert "station-3d-expanded" in destroy_block, "destroy() tam ekran station-3d-expanded sınıfını temizlemiyor."

    equip_hud_fn = _extract_js_function_block(src, r"function\s+buildEquipmentTelemetryHtml\s*\(")
    assert "escapeHtml(" in equip_hud_fn, "buildEquipmentTelemetryHtml dinamik değerlerde escapeHtml() kullanmıyor."


# ─────────────────────────────────────────────────────────────────────────────
# 3. TEARDOWN: equipmentTeardown.js
# ─────────────────────────────────────────────────────────────────────────────


def test_equipment_teardown_single_source_outlet_pipe_size_and_cleanup_contracts():
    """equipmentTeardown.js outlet_pipe_size okumalı, cancelAnimationFrame, escapeHtml ve locales t() kullanmalıdır."""
    src = TEARDOWN_JS.read_text(encoding="utf-8")

    assert "outlet_header_pipe_size" not in src, "Eski/geçersiz outlet_header_pipe_size alanı hâlâ kullanılıyor."
    assert "outlet_pipe_size" in src, "air_coolers.outlet_pipe_size alanı okunmuyor."
    assert "cancelAnimationFrame" in src, "closeEquipmentTeardown RAF döngüsünü cancelAnimationFrame ile durdurmuyor."
    assert "escapeHtml(" in src, "equipmentTeardown.js dinamik metinlerde escapeHtml() kullanmıyor."
    assert re.search(r'from\s+["\']\.\./i18n/locales\.js["\']', src), (
        "equipmentTeardown.js metinleri ../i18n/locales.js t() üzerinden çözmüyor."
    )


def test_equipment_teardown_3d_geometry_alignment_and_cyclone_half_shells_via_three():
    """Three.js sahnesinde siklon yarı kabukları dışa (±X) patlamalı ve LineSegments tel kafesleri mesh Box3 ile örtüşmelidir."""
    node_bin = shutil.which("node")
    assert node_bin, "Node.js çalışma zamanı bulunamadı."

    three_uri = (REPO_ROOT / "kasp/web/vendor/three.min.js").as_uri()
    teardown_uri = TEARDOWN_JS.as_uri()

    script = f"""
import fs from "node:fs";
import vm from "node:vm";

// Tarayıcı ortamı taklidi (Three.js + DOM + RAF)
const rafCallbacks = new Map();
let nextRafId = 1;
const cancelledRafIds = [];

function makeEl(tag = "div") {{
  const children = [];
  const attrs = new Map();
  const classes = new Set();
  const listeners = new Map();
  let inner = "";
  const el = {{
    tagName: String(tag).toUpperCase(),
    id: "",
    className: "",
    textContent: "",
    value: "0.35",
    dataset: {{}},
    style: new Proxy({{}}, {{ set(t, k, v) {{ t[k] = v; return true; }}, get(t, k) {{ return t[k] || ""; }} }}),
    clientWidth: 960,
    clientHeight: 640,
    children,
    classList: {{
      add: (...c) => c.forEach((x) => classes.add(x)),
      remove: (...c) => c.forEach((x) => classes.delete(x)),
      toggle: (c, force) => {{
        const next = force !== undefined ? !!force : !classes.has(c);
        if (next) classes.add(c); else classes.delete(c);
        return next;
      }},
      contains: (c) => classes.has(c),
    }},
    setAttribute: (k, v) => {{
      attrs.set(k, String(v));
      if (k === "id") el.id = String(v);
      if (k === "class") el.className = String(v);
    }},
    getAttribute: (k) => attrs.get(k) ?? null,
    removeAttribute: (k) => attrs.delete(k),
    appendChild: (child) => {{ child.parentElement = el; children.push(child); return child; }},
    prepend: (child) => {{ child.parentElement = el; children.unshift(child); return child; }},
    remove: () => {{
      if (el.parentElement) {{
        const idx = el.parentElement.children.indexOf(el);
        if (idx >= 0) el.parentElement.children.splice(idx, 1);
      }}
    }},
    focus: () => {{ globalThis.document.activeElement = el; }},
    blur: () => {{}},
    contains: (other) => other === el || children.some((c) => c.contains?.(other)),
    closest: () => null,
    addEventListener: (ev, fn) => {{
      if (!listeners.has(ev)) listeners.set(ev, []);
      listeners.get(ev).push(fn);
    }},
    removeEventListener: () => {{}},
    getBoundingClientRect: () => ({{ left: 0, top: 0, width: 960, height: 640 }}),
    querySelector: (sel) => {{
      if (sel.startsWith("#")) {{
        const id = sel.slice(1);
        const found = findInHtmlOrTree(el, (n) => n.id === id);
        if (found) return found;
        const stub = makeEl("div");
        stub.id = id;
        children.push(stub);
        return stub;
      }}
      return makeEl("div");
    }},
    querySelectorAll: (sel) => {{
      if (sel === ".kt-part-btn") {{
        const count = (inner.match(/kt-part-btn/g) || []).length;
        return Array.from({{ length: count }}, (_, i) => {{
          const b = makeEl("button");
          b.dataset.part = String(i);
          return b;
        }});
      }}
      if (sel.includes("button") || sel.includes("input")) return [makeEl("button")];
      return [];
    }},
    get innerHTML() {{ return inner; }},
    set innerHTML(v) {{ inner = String(v); }},
  }};
  return el;
}}

function findInHtmlOrTree(node, pred) {{
  if (pred(node)) return node;
  for (const c of node.children || []) {{
    const r = findInHtmlOrTree(c, pred);
    if (r) return r;
  }}
  return null;
}}

const body = makeEl("body");
globalThis.localStorage = {{
  getItem: () => null,
  setItem: () => {{}},
  removeItem: () => {{}},
}};
globalThis.performance = {{ now: () => 1000 }};
globalThis.requestAnimationFrame = (cb) => {{
  const id = nextRafId++;
  rafCallbacks.set(id, cb);
  return id;
}};
globalThis.cancelAnimationFrame = (id) => {{
  cancelledRafIds.push(id);
  rafCallbacks.delete(id);
}};
globalThis.CustomEvent = class CustomEvent {{
  constructor(type, init = {{}}) {{ this.type = type; this.detail = init.detail; }}
}};
globalThis.document = {{
  body,
  documentElement: makeEl("html"),
  activeElement: body,
  createElement: (tag) => makeEl(tag),
  getElementById: (id) => findInHtmlOrTree(body, (n) => n.id === id),
  addEventListener: () => {{}},
  removeEventListener: () => {{}},
}};
globalThis.window = globalThis;
globalThis.window.devicePixelRatio = 1;
globalThis.window.addEventListener = () => {{}};
globalThis.window.removeEventListener = () => {{}};
globalThis.window.dispatchEvent = () => true;

// Gerçek Three.js yükle ve yalnızca WebGLRenderer'ı hafiflet
const threeCode = fs.readFileSync(new URL({json.dumps(three_uri)}), "utf8");
vm.runInThisContext(threeCode);
const THREE = globalThis.THREE;
THREE.WebGLRenderer = class MockWebGLRenderer {{
  constructor() {{
    this.domElement = makeEl("canvas");
    this.shadowMap = {{ enabled: false }};
    this.toneMapping = 0;
    this.toneMappingExposure = 1.0;
  }}
  setPixelRatio() {{}}
  setClearColor() {{}}
  setSize() {{}}
  render() {{}}
  dispose() {{}}
  forceContextLoss() {{}}
}};

const mod = await import({json.dumps(teardown_uri)});

function inspectModel(key) {{
  mod.openEquipmentTeardown(key, {{
    title: "Test <img src=x onerror=1>",
    eq: {{ air_coolers: {{ inlet_header_pipe_size: '12"', outlet_pipe_size: '10"' }} }},
    sm: {{ suction_pressure_bar: 45, suction_temp_c: 18 }},
  }});
  const overlay = globalThis.document.getElementById("kasp-equipment-teardown");
  const scene = overlay.__kaspTeardown.scene;
  scene.updateMatrixWorld(true);

  // 1) root altındaki her LineSegments nesnesinin dünya Box3 merkezi ve boyutu aynı gruptaki Mesh ile eşleşmeli (GridHelper hariç)
  const root = scene.children.find((c) => c.type === "Group");
  const wireframeChecks = [];
  root.traverse((obj) => {{
    if (obj.isLineSegments) {{
      const lineBox = new THREE.Box3().setFromObject(obj);
      const lineCenter = lineBox.getCenter(new THREE.Vector3());
      const lineSize = lineBox.getSize(new THREE.Vector3());

      let hostMesh = obj.parent?.isMesh ? obj.parent : obj.parent?.children?.find((c) => c.isMesh);
      const meshBox = new THREE.Box3().setFromObject(hostMesh);
      const meshCenter = meshBox.getCenter(new THREE.Vector3());
      const meshSize = meshBox.getSize(new THREE.Vector3());

      wireframeChecks.push({{
        centerDist: lineCenter.distanceTo(meshCenter),
        sizeDist: lineSize.distanceTo(meshSize),
      }});
    }}
  }});

  // 2) Siklon için yarı kabukların t=0 ve t=1 (explode) X merkezlerini ölç
  let cycloneHalfShells = null;
  if (key === "cyclones") {{
    // Slider = 0 (birleşik) ve Slider = 1 (tam patlatılmış) simülasyonu
    const slider = overlay.querySelector("#kt-explode");
    slider.value = "0";
    // İlk animasyon adımında t -> 0'a yakınsat
    let tNow = 1000;
    for (let step = 0; step < 30; step++) {{
      tNow += 50;
      const cbs = [...rafCallbacks.values()];
      rafCallbacks.clear();
      cbs.forEach((fn) => fn(tNow));
    }}
    scene.updateMatrixWorld(true);
    const halfGroups = root.children.filter((g) => g.children.some((c) => c.isLineSegments || (c.isMesh && c.material?.transparent)));
    const assembledX = halfGroups.map((g) => new THREE.Box3().setFromObject(g).getCenter(new THREE.Vector3()).x);

    // Explode butonunu veya slider=1 tetikle
    slider.value = "1";
    // onExplodeInput dinleyicisini varsa tetikle
    const explodeBtn = findInHtmlOrTree(overlay, (n) => n.id === "kt-explode-btn");
    // Fallback: doğrudan grup pozisyon farkını yakalamak için animasyonu ilerlet
    // Eğer input listener bağlıysa onu da çağır
    cycloneHalfShells = {{ assembledX, halfCount: halfGroups.length }};
  }}

  const htmlSnapshot = overlay.innerHTML;
  const rafBeforeClose = rafCallbacks.size;
  mod.closeEquipmentTeardown();

  return {{ wireframeChecks, cycloneHalfShells, htmlSnapshot, rafBeforeClose, cancelledCount: cancelledRafIds.length }};
}}

const cyc = inspectModel("cyclones");
const flt = inspectModel("cartridge_filters");
const clr = inspectModel("air_coolers");
console.log(JSON.stringify({{ cyc, flt, clr }}));
"""
    proc = subprocess.run([node_bin, "--input-type=module", "-e", script], capture_output=True, text=True, check=True)
    result = json.loads(proc.stdout.strip())

    # 1) Siklon ve Kartuş Filtre LineSegments tel kafesleri mesh ile tam hizalı olmalı
    assert result["cyc"]["wireframeChecks"], "Siklon modelinde LineSegments tel kafesi bulunamadı."
    for chk in result["cyc"]["wireframeChecks"]:
        assert chk["centerDist"] < 0.05 and chk["sizeDist"] < 0.05, f"Siklon LineSegments hizasız: {chk}"

    assert result["flt"]["wireframeChecks"], "Kartuş filtre modelinde LineSegments tel kafesi bulunamadı."
    for chk in result["flt"]["wireframeChecks"]:
        assert chk["centerDist"] < 0.05 and chk["sizeDist"] < 0.05, f"Filtre LineSegments hizasız/dikey: {chk}"

    # 2) Siklon yarı kabuklarında thetaStart yarımküresi ile explode X yönü aynı işaretli (dışa doğru) olmalı
    src = TEARDOWN_JS.read_text(encoding="utf-8")
    cyclone_fn = _extract_js_function_block(src, r"const\s+buildCyclone\s*=\s*\(\)\s*=>")
    # Her yarı kabuk için CylinderGeometry(..., thetaStart, Math.PI) ve takip eden addPart(name, desc, group, [ex, ...]) çiftini denetle
    shell_blocks = re.findall(
        r"CylinderGeometry\([^)]*?,\s*true\s*,\s*([^,]+),\s*Math\.PI\s*\)[\s\S]*?addPart\(\s*[^,]+,\s*[^,]+,\s*[A-Za-z0-9_]+\s*,\s*\[\s*([+-]?\d+(?:\.\d+)?)",
        cyclone_fn,
    )
    assert len(shell_blocks) == 2, f"Siklon yarı kabuk tanımları beklenenden farklı: {shell_blocks}"
    for theta_expr, explode_x_str in shell_blocks:
        theta_clean = theta_expr.strip()
        explode_x = float(explode_x_str)
        # thetaStart == 0 -> sin(theta) >= 0 (+X yarımküre) -> explode_x > 0 olmalı
        # thetaStart == Math.PI (veya -Math.PI) -> sin(theta) <= 0 (-X yarımküre) -> explode_x < 0 olmalı
        if theta_clean in ("0", "0.0"):
            assert explode_x > 0, f"thetaStart=0 (+X sağ yarı kabuk) sola ({explode_x}) patlatılıyor (iç içe geçme)!"
        elif "Math.PI" in theta_clean:
            assert explode_x < 0, f"thetaStart={theta_clean} (-X sol yarı kabuk) sağa ({explode_x}) patlatılıyor (iç içe geçme)!"
        else:
            pytest.fail(f"Beklenmeyen siklon yarı kabuk thetaStart ifadesi: {theta_clean}")

    # 3) closeEquipmentTeardown çağrısı aktif RAF döngüsünü iptal etmeli ve XSS kaçışı yapmalı
    assert result["cyc"]["cancelledCount"] >= 1, "closeEquipmentTeardown() cancelAnimationFrame çağırmadı."
    assert "<img src=x onerror=1>" not in result["clr"]["htmlSnapshot"], "context.title escapeHtml() olmadan basıldı."
    assert '10"' in result["clr"]["htmlSnapshot"] or "&quot;" in result["clr"]["htmlSnapshot"], (
        "outlet_pipe_size ('10\"') bilgi tablosuna yansımadı."
    )
