/**
 * KASP Equipment Teardown Viewer
 * ------------------------------------------------------------
 * Interactive exploded-view popup for the three main gas-conditioning
 * equipment groups: fin-fan gas cooler, vertical cyclone separator and
 * horizontal cartridge filter separator.
 *
 * The module is framework-free: it uses the global THREE build already loaded
 * by the web app and works in the OpenCode browser and in standalone
 * Antigravity/Agent-Skills sessions that load the same vendor bundle.
 */

import { uiStore } from "../store/uiStore.js";
import { t } from "../i18n/locales.js";
import { escapeHtml } from "../store/projectStore.js";

const OVERLAY_ID = "kasp-equipment-teardown";

const COLORS = {
  shell: 0xb8c0c8,
  shellDark: 0x7d8791,
  blue: 0x2d6fa8,
  yellow: 0xe2c400,
  internal: 0x4f8f9a,
  copper: 0xb87333,
  dark: 0x303843,
  accent: 0x38bdf8,
  green: 0x2f7f6f,
};

function resolveLang(ctx = {}) {
  return ctx.lang || uiStore?.getState?.()?.lang || "tr";
}

function infoRows(key, ctx, lang = "tr") {
  const isEn = lang === "en";
  const eq = ctx.eq || {};
  const sm = ctx.sm || {};
  const suc = ctx.sucLine || {};
  const nCyc = Number(ctx.numCyclones || eq.cyclones?.installed_count || 2);
  const nFlt = Number(ctx.numFilters || eq.cartridge_filters?.installed_count || 2);
  const nBay = Number(ctx.numCoolerBays || eq.air_coolers?.bay_count || 2);

  const pSuc = Number(sm.suction_pressure_bar) > 0 ? Number(sm.suction_pressure_bar) : 45.0;
  const tSuc =
    sm.suction_temp_c ??
    ctx.nodes?.mainline_suction?.temp_c ??
    eq.esd_sizing?.auto_inputs?.suction_t_c ??
    15.0;
  const dpCyc = Number(eq.cyclones?.pressure_drop_bar ?? 0.15);
  const dpFlt = Number(eq.cartridge_filters?.clean_dp_bar ?? 0.10);

  if (key === "cyclones") {
    const opCyc = Number(eq.cyclones?.operating_count || Math.max(1, nCyc - 1));
    const flowCyc =
      eq.cyclones?.flow_per_unit_kgs ??
      (Number(sm.total_mass_flow_kgs) > 0
        ? (Number(sm.total_mass_flow_kgs) / opCyc).toFixed(2)
        : 12.0);
    const endTag = `V-${100 + nCyc}`;
    return [
      [isEn ? "Equipment" : "Ekipman", `V-101 … ${endTag} · ${nCyc} ${isEn ? "units" : "ünite"}`],
      [isEn ? "Process pressure" : "Proses basıncı", `${pSuc} bar(a)`],
      [isEn ? "Pressure drop" : "Basınç düşümü", `${dpCyc} bar`],
      [isEn ? "Inlet temperature" : "Giriş sıcaklığı", `${tSuc} °C`],
      [isEn ? "Unit mass flow" : "Ünite debisi", `${flowCyc} kg/s`],
      [isEn ? "Liquid / solid knockout" : "Sıvı / katı ayırma", `> %${eq.cyclones?.liquid_knockout_pct ?? 99.5} · > 10 µm`],
      [isEn ? "Inlet branch" : "Giriş branşmanı", eq.cyclones?.inlet_pipe_size || `${suc.nominal_size_in || '10"'} NPS`],
      [isEn ? "Configuration" : "Konfigürasyon", isEn ? `${opCyc} duty + 1 standby` : `${opCyc} aktif + 1 yedek`],
    ];
  }
  if (key === "cartridge_filters") {
    const opFlt = Number(eq.cartridge_filters?.operating_count || Math.max(1, nFlt - 1));
    const flowFlt =
      eq.cartridge_filters?.flow_per_unit_kgs ??
      (Number(sm.total_mass_flow_kgs) > 0
        ? (Number(sm.total_mass_flow_kgs) / opFlt).toFixed(2)
        : 12.0);
    const pFltIn = Math.max(0.5, pSuc - dpCyc);
    const pFltOut = Math.max(0.5, pFltIn - dpFlt);
    const endTag = `F-${100 + nFlt}`;
    return [
      [isEn ? "Equipment" : "Ekipman", `F-101 … ${endTag} · ${nFlt} ${isEn ? "units" : "ünite"}`],
      [isEn ? "Inlet / outlet pressure" : "Giriş / çıkış basıncı", `${pFltIn.toFixed(2)} → ${pFltOut.toFixed(2)} bar(a)`],
      [isEn ? "Clean filter ΔP" : "Temiz filtre ΔP", `${dpFlt} bar (${isEn ? "max." : "maks."} 0.70 bar)`],
      [isEn ? "Filtration grade" : "Filtrasyon", eq.cartridge_filters?.filter_efficiency_micron || (isEn ? "0.3 µm · 99.98% aerosol retention" : "0.3 µm · %99.98 aerosol tutma")],
      [isEn ? "Unit mass flow" : "Ünite debisi", `${flowFlt} kg/s`],
      [isEn ? "Inlet branch" : "Giriş branşmanı", eq.cartridge_filters?.inlet_pipe_size || '12" NPS'],
      [isEn ? "Configuration" : "Konfigürasyon", isEn ? `${opFlt} duty + 1 standby` : `${opFlt} aktif + 1 yedek`],
      [isEn ? "Instrumentation" : "Enstrümantasyon", isEn ? "PDT differential pressure transmitter" : "PDT diferansiyel basınç transmitteri"],
    ];
  }
  if (key === "air_coolers") {
    const fansPerBay = Number(eq.air_coolers?.fans_per_bay || 2);
    const totalFans = Number(eq.air_coolers?.total_fans || nBay * fansPerBay);
    const inHdr = eq.air_coolers?.inlet_header_pipe_size || '6"';
    const outHdr = eq.air_coolers?.outlet_pipe_size || eq.air_coolers?.riser_pipe_size || '6"';
    const rows = [
      [isEn ? "Equipment" : "Ekipman", `E-101 · ${nBay} fin-fan bay`],
      [isEn ? "Inlet temperature" : "Giriş sıcaklığı", `${eq.air_coolers?.inlet_temp_c ?? 79.0} °C`],
      [isEn ? "Outlet temperature" : "Çıkış sıcaklığı", `${eq.air_coolers?.outlet_temp_c ?? 45.0} °C`],
      [isEn ? "Total heat duty" : "Toplam ısıl yük", `${eq.air_coolers?.total_heat_duty_mw ?? 14.8} MWth`],
      [isEn ? "Fan configuration" : "Fan konfigürasyonu", isEn ? `${totalFans} VFD fans (${fansPerBay}/bay)` : `${totalFans} adet VFD fan (${fansPerBay}/bay)`],
      [isEn ? "Gas pressure drop" : "Gaz basınç kaybı", `${eq.air_coolers?.pressure_drop_bar ?? 0.45} bar`],
      ["Inlet / outlet header", `${inHdr} / ${outHdr}`],
    ];
    const design = eq.air_coolers?.detailed_design;
    if (design) {
      rows.push([
        isEn ? "API 661 area" : "API 661 alan",
        `${Number(design.actual_area_m2 || 0).toFixed(1)} m² (%${Number(design.overdesign_pct || 0).toFixed(1)} overdesign)`,
      ]);
      rows.push([
        isEn ? "Fan power / tip speed" : "Fan gücü / uç hızı",
        `${Number(design.fan_power_kw || 0).toFixed(1)} kW · ${Number(design.fan_tip_speed_ms || 0).toFixed(1)} m/s`,
      ]);
    }
    return rows;
  }
  return [[isEn ? "Equipment" : "Ekipman", String(key)]];
}

function renderInfoTableRows(key, context, lang) {
  return infoRows(key, context, lang)
    .map(
      ([l, v]) =>
        `<tr style="border-bottom:1px solid rgba(148,163,184,.09);"><td style="padding:5px 0;color:#94a3b8;vertical-align:top;">${escapeHtml(l)}</td><td style="padding:5px 0;text-align:right;color:#f8fafc;font-weight:700;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;">${escapeHtml(v)}</td></tr>`
    )
    .join("");
}

function partButton(part, idx, isActive = false) {
  const safeColor = escapeHtml(part.cssColor);
  return `<button type="button" class="kt-part-btn${isActive ? " is-active" : ""}" data-part="${idx}" aria-pressed="${isActive ? "true" : "false"}" style="display:flex;align-items:center;gap:8px;width:100%;text-align:left;background:rgba(255,255,255,.04);border:1px solid rgba(148,163,184,.18);border-radius:7px;padding:6px 8px;color:#e2e8f0;font-size:11px;cursor:pointer;margin:4px 0;">
    <span style="width:9px;height:9px;border-radius:50%;background:${safeColor};box-shadow:0 0 8px ${safeColor};flex:none;"></span>
    <span style="font-weight:700;">${escapeHtml(part.name)}</span>
  </button>`;
}

export function openEquipmentTeardown(key, context = {}) {
  const THREE = window.THREE;
  if (!THREE) return;
  closeEquipmentTeardown();

  const previousFocus =
    typeof document !== "undefined" && document.activeElement && typeof document.activeElement.focus === "function"
      ? document.activeElement
      : null;

  let currentLang = resolveLang(context);
  const titleText = context.title || (currentLang === "en" ? "Equipment Teardown" : "Ekipman Teardown");
  const subtitleText = context.subtitle || "Interactive exploded view · KASP 3D Digital Twin";
  const closeLabel = t("teardown_btn_close", currentLang);

  const overlay = document.createElement("div");
  overlay.id = OVERLAY_ID;
  overlay.setAttribute("role", "dialog");
  overlay.setAttribute("aria-modal", "true");
  overlay.setAttribute("aria-labelledby", "kt-dialog-title");
  overlay.style.cssText =
    "position:fixed;inset:0;z-index:10050;background:rgba(2,6,17,.84);backdrop-filter:blur(10px);display:flex;align-items:center;justify-content:center;padding:18px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;";
  overlay.innerHTML = `
    <div class="kt-modal-card" style="width:min(1420px,98vw);height:min(880px,94vh);background:linear-gradient(145deg,#0b1220 0%,#0d1728 48%,#08111d 100%);border:1px solid #1e3a5f;border-radius:16px;box-shadow:0 28px 90px rgba(0,0,0,.7);display:flex;flex-direction:column;overflow:hidden;">
      <div style="display:flex;align-items:center;justify-content:space-between;gap:14px;padding:14px 18px;border-bottom:1px solid rgba(148,163,184,.18);background:rgba(15,23,42,.72);">
        <div>
          <div id="kt-dialog-title" style="font-size:16px;font-weight:900;color:#f8fafc;letter-spacing:.3px;">🔧 ${escapeHtml(titleText)}</div>
          <div style="font-size:11px;color:#94a3b8;margin-top:2px;">${escapeHtml(subtitleText)}</div>
        </div>
        <div style="display:flex;align-items:center;gap:8px;">
          <span id="kt-live-badge" style="font-size:10px;font-weight:700;color:#34d399;border:1px solid rgba(52,211,153,.5);background:rgba(16,185,129,.12);padding:4px 9px;border-radius:20px;">${currentLang === "en" ? "● LIVE 3D" : "● CANLI MODEL"}</span>
          <button id="kt-close" type="button" aria-label="${escapeHtml(closeLabel)}" title="${escapeHtml(closeLabel)}" style="background:rgba(255,255,255,.06);border:1px solid rgba(148,163,184,.25);color:#e2e8f0;border-radius:8px;width:34px;height:34px;font-size:17px;cursor:pointer;">✕</button>
        </div>
      </div>
      <div class="kt-modal-grid" style="display:grid;grid-template-columns:340px minmax(0,1fr);min-height:0;flex:1;">
        <aside class="kt-sidebar" style="border-right:1px solid rgba(148,163,184,.16);background:rgba(8,15,28,.58);padding:14px;overflow:auto;">
          <div id="kt-sec-process" style="font-size:10px;font-weight:800;letter-spacing:.12em;text-transform:uppercase;color:#38bdf8;margin-bottom:8px;">${escapeHtml(t("teardown_sec_process", currentLang))}</div>
          <table style="width:100%;border-collapse:collapse;font-size:10.5px;">
            <tbody id="kt-info-tbody">
              ${renderInfoTableRows(key, context, currentLang)}
            </tbody>
          </table>
          <div style="height:1px;background:rgba(148,163,184,.14);margin:14px 0;"></div>
          <div id="kt-sec-parts" style="font-size:10px;font-weight:800;letter-spacing:.12em;text-transform:uppercase;color:#fbbf24;margin-bottom:8px;">${escapeHtml(t("teardown_sec_parts", currentLang))}</div>
          <div id="kt-parts"></div>
          <div id="kt-part-desc" aria-live="polite" style="margin-top:10px;padding:9px 10px;border-radius:8px;background:rgba(56,189,248,.08);border:1px solid rgba(56,189,248,.22);color:#bae6fd;font-size:10.5px;line-height:1.45;min-height:54px;"></div>
        </aside>
        <section class="kt-stage" style="position:relative;min-width:0;min-height:0;">
          <div id="kt-viewer" style="position:absolute;inset:0;"></div>
          <div id="kt-labels" style="position:absolute;inset:0;pointer-events:none;overflow:hidden;"></div>
          <div class="kt-toolbar" style="position:absolute;left:14px;bottom:14px;right:14px;display:flex;align-items:center;gap:10px;flex-wrap:wrap;padding:10px 12px;border-radius:10px;background:rgba(8,15,28,.82);border:1px solid rgba(148,163,184,.18);backdrop-filter:blur(8px);">
            <label id="kt-slider-label" for="kt-explode" style="font-size:10px;font-weight:800;color:#94a3b8;letter-spacing:.08em;">${escapeHtml(t("teardown_slider_label", currentLang))}</label>
            <input id="kt-explode" type="range" min="0" max="1" step="0.01" value="0.35" aria-label="${escapeHtml(t("teardown_slider_label", currentLang))}" style="flex:1;min-width:120px;accent-color:#38bdf8;" />
            <button id="kt-explode-btn" type="button" class="kt-ctrl" style="background:#0284c7;border-color:#38bdf8;color:#fff;">⏏ ${escapeHtml(t("teardown_btn_explode", currentLang))}</button>
            <button id="kt-assemble-btn" type="button" class="kt-ctrl">🧩 ${escapeHtml(t("teardown_btn_assemble", currentLang))}</button>
            <button id="kt-rotate-btn" type="button" class="kt-ctrl" aria-pressed="true" style="background:rgba(56,189,248,.15);border-color:#38bdf8;color:#bae6fd;"></button>
            <button id="kt-reset-btn" type="button" class="kt-ctrl">⌂ ${escapeHtml(t("teardown_btn_reset", currentLang))}</button>
          </div>
          <div id="kt-hint" style="position:absolute;top:14px;right:14px;padding:6px 9px;border-radius:8px;background:rgba(8,15,28,.7);border:1px solid rgba(148,163,184,.16);font-size:10px;color:#94a3b8;"></div>
        </section>
      </div>
    </div>
    <style>
      .kt-ctrl{background:rgba(255,255,255,.06);border:1px solid rgba(148,163,184,.25);color:#e2e8f0;border-radius:7px;padding:6px 10px;font-size:10.5px;font-weight:700;cursor:pointer;}
      .kt-ctrl:hover{background:rgba(56,189,248,.15);border-color:#38bdf8;}
      .kt-part-btn:hover{background:rgba(56,189,248,.12)!important;border-color:rgba(56,189,248,.55)!important;}
      .kt-part-btn.is-active{background:rgba(56,189,248,.2)!important;border-color:#38bdf8!important;}
      .kt-label{position:absolute;transform:translate(-50%,-50%);pointer-events:auto;cursor:pointer;white-space:nowrap;font-size:10px;font-weight:800;color:#e2e8f0;background:rgba(3,7,18,.78);border:1px solid rgba(56,189,248,.5);border-radius:12px;padding:3px 8px;box-shadow:0 4px 14px rgba(0,0,0,.45);font-family:inherit;}
      .kt-label.is-active{background:rgba(2,132,199,.88);border-color:#fbbf24;color:#fff;}
      .kt-label:focus-visible,.kt-part-btn:focus-visible,.kt-ctrl:focus-visible,#kt-close:focus-visible{outline:2px solid #38bdf8;outline-offset:2px;}
      .kt-label:before{content:"";position:absolute;left:50%;top:100%;width:1px;height:16px;background:rgba(56,189,248,.5);}
      @media (max-width: 860px) {
        .kt-modal-card{width:100vw!important;height:95vh!important;border-radius:12px!important;}
        .kt-modal-grid{grid-template-columns:1fr!important;grid-template-rows:minmax(250px,52%) minmax(0,48%);}
        .kt-stage{order:1;min-height:250px;}
        .kt-sidebar{order:2;border-right:none!important;border-top:1px solid rgba(148,163,184,.16);}
        .kt-toolbar{left:8px!important;right:8px!important;bottom:8px!important;padding:7px 9px!important;gap:6px!important;}
      }
    </style>
  `;
  document.body.appendChild(overlay);

  const viewer = overlay.querySelector("#kt-viewer");
  const labelsBox = overlay.querySelector("#kt-labels");
  const partsBox = overlay.querySelector("#kt-parts");
  const descBox = overlay.querySelector("#kt-part-desc");
  const explodeSlider = overlay.querySelector("#kt-explode");
  const closeBtn = overlay.querySelector("#kt-close");
  const rotateBtn = overlay.querySelector("#kt-rotate-btn");
  const hintBox = overlay.querySelector("#kt-hint");

  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.setClearColor(0x000000, 0);
  if (THREE.ACESFilmicToneMapping) {
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.0;
  }
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  viewer.appendChild(renderer.domElement);
  renderer.domElement.style.width = "100%";
  renderer.domElement.style.height = "100%";
  renderer.domElement.style.display = "block";

  const scene = new THREE.Scene();
  scene.fog = new THREE.FogExp2(0x08111d, 0.018);
  const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 300);
  camera.position.set(8.5, 6.5, 10.5);

  const controls = THREE.OrbitControls ? new THREE.OrbitControls(camera, renderer.domElement) : null;
  if (controls) {
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.minDistance = 3.4;
    controls.maxDistance = 26;
    controls.maxPolarAngle = Math.PI * 0.93;
    controls.target.set(0, 1.8, 0);
    controls.autoRotate = true;
    controls.autoRotateSpeed = 1.2;
  }

  scene.add(new THREE.HemisphereLight(0xdbeafe, 0x0b1220, 0.85));
  const keyLight = new THREE.DirectionalLight(0xffffff, 1.35);
  keyLight.position.set(9, 14, 8);
  keyLight.castShadow = true;
  keyLight.shadow.mapSize.set(1024, 1024);
  scene.add(keyLight);
  const fillLight = new THREE.DirectionalLight(0x60a5fa, 0.6);
  fillLight.position.set(-10, 7, -8);
  scene.add(fillLight);
  const rimLight = new THREE.DirectionalLight(0xfbbf24, 0.35);
  rimLight.position.set(2, 4, -12);
  scene.add(rimLight);

  const grid = new THREE.GridHelper(28, 28, 0x1e3a5f, 0x10263d);
  grid.position.y = -0.01;
  scene.add(grid);
  const ground = new THREE.Mesh(
    new THREE.CircleGeometry(13, 48),
    new THREE.MeshStandardMaterial({ color: 0x07101d, roughness: 0.95, metalness: 0.05 })
  );
  ground.rotation.x = -Math.PI / 2;
  ground.position.y = -0.03;
  ground.receiveShadow = true;
  scene.add(ground);

  const matShell = new THREE.MeshStandardMaterial({ color: COLORS.shell, roughness: 0.36, metalness: 0.75 });
  const matShellDark = new THREE.MeshStandardMaterial({ color: COLORS.shellDark, roughness: 0.46, metalness: 0.62 });
  const matBlue = new THREE.MeshStandardMaterial({ color: COLORS.blue, roughness: 0.42, metalness: 0.55 });
  const matYellow = new THREE.MeshStandardMaterial({ color: COLORS.yellow, roughness: 0.38, metalness: 0.45 });
  const matInternal = new THREE.MeshStandardMaterial({ color: COLORS.internal, roughness: 0.48, metalness: 0.45 });
  const matCopper = new THREE.MeshStandardMaterial({ color: COLORS.copper, roughness: 0.4, metalness: 0.65 });
  const matDark = new THREE.MeshStandardMaterial({ color: COLORS.dark, roughness: 0.52, metalness: 0.55 });
  const matGreen = new THREE.MeshStandardMaterial({ color: COLORS.green, roughness: 0.48, metalness: 0.45 });
  const matGhostShell = new THREE.MeshStandardMaterial({
    color: COLORS.shell,
    roughness: 0.42,
    metalness: 0.55,
    transparent: true,
    opacity: 0.30,
    side: THREE.DoubleSide,
    depthWrite: false,
  });
  const matGhostShellDark = new THREE.MeshStandardMaterial({
    color: COLORS.shellDark,
    roughness: 0.48,
    metalness: 0.55,
    transparent: true,
    opacity: 0.26,
    side: THREE.DoubleSide,
    depthWrite: false,
  });
  const matFlange = new THREE.MeshStandardMaterial({ color: 0xd4c800, roughness: 0.3, metalness: 0.65 });

  const root = new THREE.Group();
  scene.add(root);
  const parts = [];

  const addPart = (name, desc, group, explode, labelAnchor, cssColor = "#38bdf8") => {
    root.add(group);
    parts.push({
      name,
      desc,
      group,
      explode: new THREE.Vector3(...explode),
      base: group.position.clone(),
      labelAnchor: new THREE.Vector3(...labelAnchor),
      cssColor,
    });
    return group;
  };

  const makeMesh = (geo, mat, position = [0, 0, 0], rotation = [0, 0, 0]) => {
    const m = new THREE.Mesh(geo, mat);
    m.position.set(...position);
    m.rotation.set(...rotation);
    m.castShadow = true;
    m.receiveShadow = true;
    return m;
  };

  const makeEdgeLines = (mesh, color = 0x9fd8ff, opacity = 0.55) => {
    const edges = new THREE.LineSegments(
      new THREE.EdgesGeometry(mesh.geometry),
      new THREE.LineBasicMaterial({ color, transparent: true, opacity })
    );
    edges.position.copy(mesh.position);
    edges.rotation.copy(mesh.rotation);
    edges.scale.copy(mesh.scale);
    return edges;
  };

  const buildCooler = () => {
    const eq = context.eq || {};
    const nBay = Number(context.numCoolerBays || eq.air_coolers?.bay_count || 2);
    const fansPerBay = Number(eq.air_coolers?.fans_per_bay || 2);
    const totalFans = Number(eq.air_coolers?.total_fans || nBay * fansPerBay);

    const structure = new THREE.Group();
    [[-2.6, -1.8], [2.6, -1.8], [-2.6, 1.8], [2.6, 1.8]].forEach(([x, z]) => {
      structure.add(makeMesh(new THREE.BoxGeometry(0.18, 1.48, 0.18), matBlue, [x, 0.74, z]));
    });
    structure.add(makeMesh(new THREE.BoxGeometry(5.6, 0.16, 0.18), matBlue, [0, 1.44, -1.8]));
    structure.add(makeMesh(new THREE.BoxGeometry(5.6, 0.16, 0.18), matBlue, [0, 1.44, 1.8]));
    structure.add(makeMesh(new THREE.BoxGeometry(0.18, 0.16, 3.8), matBlue, [-2.6, 1.44, 0]));
    structure.add(makeMesh(new THREE.BoxGeometry(0.18, 0.16, 3.8), matBlue, [2.6, 1.44, 0]));
    addPart(
      "Çelik Karkas",
      "Kolonlar, ana kirişler ve fan platformu taşıyıcı çerçevesi.",
      structure,
      [0, 0, 0],
      [0, 0.55, 2.05],
      "#2d6fa8"
    );

    const plenum = new THREE.Group();
    plenum.add(makeMesh(new THREE.BoxGeometry(5.2, 0.68, 3.4), matShellDark, [0, 1.9, 0]));
    plenum.add(makeMesh(new THREE.BoxGeometry(4.9, 0.1, 0.16), matBlue, [0, 2.26, -1.68]));
    plenum.add(makeMesh(new THREE.BoxGeometry(4.9, 0.1, 0.16), matBlue, [0, 2.26, 1.68]));
    addPart(
      "Plenum Odası",
      "Fanların çektiği havayı fin-tüp demetine yönlendiren kapalı hava odası.",
      plenum,
      [0, 0.35, 0],
      [0, 1.95, 0],
      "#94a3b8"
    );

    const bundle = new THREE.Group();
    bundle.add(makeMesh(new THREE.BoxGeometry(4.7, 0.72, 2.9), matGreen, [0, 2.72, 0]));
    [-2.42, 2.42].forEach((x) => {
      bundle.add(makeMesh(new THREE.BoxGeometry(0.12, 0.86, 3.0), matBlue, [x, 2.72, 0]));
      bundle.add(
        makeMesh(
          new THREE.CylinderGeometry(0.18, 0.18, 3.0, 14),
          matShell,
          [x + (x < 0 ? -0.14 : 0.14), 2.55, 0],
          [Math.PI / 2, 0, 0]
        )
      );
    });
    for (let i = 0; i < 12; i++) {
      bundle.add(makeMesh(new THREE.BoxGeometry(0.06, 0.62, 2.8), matCopper, [-2.09 + i * 0.38, 2.72, 0]));
    }
    addPart(
      "Fin-Tüp Demeti",
      "Kanatlı tüpler, tüp tabloları ve tüp kutusu bağlantıları.",
      bundle,
      [0, 0.95, 0],
      [0, 2.85, 0],
      "#2f7f6f"
    );

    const inletHeader = new THREE.Group();
    inletHeader.add(makeMesh(new THREE.CylinderGeometry(0.28, 0.28, 3.2, 16), matYellow, [-3.18, 2.55, 0], [Math.PI / 2, 0, 0]));
    inletHeader.add(makeMesh(new THREE.CylinderGeometry(0.38, 0.38, 0.16, 16), matYellow, [-3.18, 2.55, -1.62], [Math.PI / 2, 0, 0]));
    inletHeader.add(makeMesh(new THREE.CylinderGeometry(0.38, 0.38, 0.16, 16), matYellow, [-3.18, 2.55, 1.62], [Math.PI / 2, 0, 0]));
    addPart(
      "Inlet Header",
      "Sıcak gaz giriş kolektörü, branşman nozulları ve kör flanşlar.",
      inletHeader,
      [-0.95, 0.95, 0],
      [-3.18, 2.55, 0],
      "#e2c400"
    );

    const outletHeader = new THREE.Group();
    outletHeader.add(makeMesh(new THREE.CylinderGeometry(0.28, 0.28, 3.2, 16), matYellow, [3.18, 2.55, 0], [Math.PI / 2, 0, 0]));
    outletHeader.add(makeMesh(new THREE.CylinderGeometry(0.38, 0.38, 0.16, 16), matYellow, [3.18, 2.55, -1.62], [Math.PI / 2, 0, 0]));
    outletHeader.add(makeMesh(new THREE.CylinderGeometry(0.38, 0.38, 0.16, 16), matYellow, [3.18, 2.55, 1.62], [Math.PI / 2, 0, 0]));
    addPart(
      "Outlet Header",
      "Soğutulmuş gaz çıkış kolektörü ve flanş bağlantıları.",
      outletHeader,
      [0.95, 0.95, 0],
      [3.18, 2.55, 0],
      "#e2c400"
    );

    const fans = new THREE.Group();
    [-1.25, 1.25].forEach((x) => {
      const ring = makeMesh(new THREE.TorusGeometry(1.02, 0.07, 8, 30), matBlue, [x, 3.5, 0], [Math.PI / 2, 0, 0]);
      fans.add(ring);
      const shroud = makeMesh(new THREE.CylinderGeometry(1.02, 1.02, 0.28, 24, 1, true), matShellDark, [x, 3.46, 0]);
      fans.add(shroud);
      const hub = makeMesh(new THREE.CylinderGeometry(0.17, 0.17, 0.2, 14), matDark, [x, 3.52, 0]);
      fans.add(hub);
      for (let b = 0; b < 6; b++) {
        const blade = makeMesh(new THREE.BoxGeometry(1.65, 0.06, 0.36), matShell, [
          x + Math.cos((b * Math.PI) / 3) * 0.82,
          3.53,
          Math.sin((b * Math.PI) / 3) * 0.82,
        ]);
        blade.rotation.set(0.14, -(b * Math.PI) / 3, 0);
        fans.add(blade);
      }
      fans.add(makeMesh(new THREE.CylinderGeometry(0.26, 0.26, 0.38, 14), matDark, [x + 0.82, 3.88, 0]));
      fans.add(makeMesh(new THREE.BoxGeometry(0.85, 0.08, 0.18), matBlue, [x + 0.4, 3.84, 0]));
    });
    addPart(
      "Fan Grubu",
      `Temsili bay üzerinde ${fansPerBay} adet VFD fan (bank toplamı: ${nBay} bay · ${totalFans} fan).`,
      fans,
      [0, 1.75, 0],
      [0, 3.65, 0],
      "#38bdf8"
    );

    const louvers = new THREE.Group();
    louvers.add(makeMesh(new THREE.BoxGeometry(5.3, 0.1, 3.3), matShellDark, [0, 4.22, 0]));
    for (let i = 0; i < 7; i++) {
      louvers.add(makeMesh(new THREE.BoxGeometry(5.0, 0.05, 0.26), matDark, [0, 4.28, -1.32 + i * 0.44]));
    }
    addPart(
      "Louver Kapağı",
      "Hava çıkış louverları; fan çekme kaybını ve yağmur girişini sınırlar.",
      louvers,
      [0, 2.55, 0],
      [0, 4.35, 0],
      "#fbbf24"
    );

    camera.position.set(9.4, 7.4, 13.2);
    if (controls) controls.target.set(0, 2.5, 0);
  };

  const buildCyclone = () => {
    // thetaStart = Math.PI .. 2*Math.PI sits on -X (left side) and explodes toward -X
    const shellLeft = new THREE.Group();
    const shellLeftMesh = makeMesh(
      new THREE.CylinderGeometry(0.95, 0.95, 3.2, 28, 1, true, Math.PI, Math.PI),
      matGhostShell,
      [0, 3.7, 0]
    );
    shellLeft.add(shellLeftMesh);
    shellLeft.add(makeEdgeLines(shellLeftMesh));
    addPart(
      "Sol Gövde Kabuğu",
      "Silindirik basınç kabuğunun sol (-X) yarısı; teardown için sola açılır.",
      shellLeft,
      [-0.9, 0, 0],
      [-0.95, 3.7, 0],
      "#b8c0c8"
    );

    // thetaStart = 0 .. Math.PI sits on +X (right side) and explodes toward +X
    const shellRight = new THREE.Group();
    const shellRightMesh = makeMesh(
      new THREE.CylinderGeometry(0.95, 0.95, 3.2, 28, 1, true, 0, Math.PI),
      matGhostShellDark,
      [0, 3.7, 0]
    );
    shellRight.add(shellRightMesh);
    shellRight.add(makeEdgeLines(shellRightMesh));
    addPart(
      "Sağ Gövde Kabuğu",
      "Kabuğun sağ (+X) yarısı; iç vorteks bulucu ve giriş bölgesini açığa çıkarır.",
      shellRight,
      [0.9, 0, 0],
      [0.95, 3.7, 0],
      "#7d8791"
    );

    const head = new THREE.Group();
    head.add(makeMesh(new THREE.SphereGeometry(0.95, 24, 14, 0, Math.PI * 2, 0, Math.PI / 2), matShell, [0, 5.32, 0]));
    head.add(makeMesh(new THREE.CylinderGeometry(0.34, 0.34, 0.56, 16), matShell, [0, 6.02, 0]));
    head.add(makeMesh(new THREE.CylinderGeometry(0.48, 0.48, 0.12, 16), matFlange, [0, 6.36, 0]));
    addPart(
      "Üst Başlık & Outlet Nozulu",
      "Dished üst başlık, gaz çıkış nozulu ve kör flanş.",
      head,
      [0, 1.35, 0],
      [0, 6.2, 0],
      "#b8c0c8"
    );

    const cone = new THREE.Group();
    cone.add(makeMesh(new THREE.ConeGeometry(0.95, 1.0, 24), matShell, [0, 1.58, 0], [Math.PI, 0, 0]));
    cone.add(makeMesh(new THREE.CylinderGeometry(0.18, 0.18, 0.44, 12), matShellDark, [0, 0.86, 0]));
    addPart(
      "Konik Alt & Drenaj",
      "Katı/sıvı toplama konisi ve LCV drenaj nozulu.",
      cone,
      [0, -0.6, 0],
      [0, 1.25, 0],
      "#94a3b8"
    );

    const inlet = new THREE.Group();
    inlet.add(makeMesh(new THREE.CylinderGeometry(0.32, 0.32, 0.84, 16), matYellow, [-1.42, 4.45, 0], [0, 0, Math.PI / 2]));
    inlet.add(makeMesh(new THREE.CylinderGeometry(0.46, 0.46, 0.12, 16), matYellow, [-1.9, 4.45, 0], [0, 0, Math.PI / 2]));
    addPart(
      "Teğetsel Giriş Nozulu",
      "Gazı silindirik gövdeye teğetsel olarak veren inlet nozulu ve flanşı.",
      inlet,
      [-1.35, 0.15, 0],
      [-1.9, 4.45, 0],
      "#e2c400"
    );

    const internal = new THREE.Group();
    internal.add(makeMesh(new THREE.CylinderGeometry(0.42, 0.42, 1.85, 18, 1, true), matInternal, [0, 4.1, 0]));
    internal.add(makeMesh(new THREE.CylinderGeometry(0.55, 0.55, 0.2, 18), matCopper, [0, 5.12, 0]));
    internal.add(makeMesh(new THREE.ConeGeometry(0.42, 0.78, 18), matCopper, [0, 2.78, 0]));
    for (let i = 0; i < 7; i++) {
      internal.add(makeMesh(new THREE.TorusGeometry(0.46, 0.025, 6, 18), matInternal, [0, 3.28 + i * 0.22, 0], [Math.PI / 2, 0, 0]));
    }
    addPart(
      "Vorteks Bulucu / İç Eleman",
      "Merkezi vorteks bulucu tüp, üst bafle ve iç akış yönlendiricileri.",
      internal,
      [0, 0.3, 0],
      [0, 4.1, 0],
      "#4f8f9a"
    );

    const support = new THREE.Group();
    for (let i = 0; i < 3; i++) {
      const a = (i * Math.PI * 2) / 3;
      support.add(makeMesh(new THREE.BoxGeometry(0.14, 2.0, 0.14), matBlue, [Math.cos(a) * 1.16, 1.0, Math.sin(a) * 1.16]));
    }
    support.add(makeMesh(new THREE.TorusGeometry(1.15, 0.06, 8, 28), matBlue, [0, 1.94, 0], [Math.PI / 2, 0, 0]));
    addPart(
      "Destek & Skirt",
      "Üç ayaklı destek ve konik alt çevresindeki taşıyıcı halka.",
      support,
      [0, 0, 0],
      [0, 0.85, 1.24],
      "#2d6fa8"
    );

    camera.position.set(8.8, 7.6, 11.4);
    if (controls) controls.target.set(0, 3.2, 0);
  };

  const buildFilter = () => {
    const shell = new THREE.Group();
    const shellMesh = makeMesh(
      new THREE.CylinderGeometry(0.92, 0.92, 4.0, 28, 1, true),
      matGhostShell,
      [0, 1.85, 0],
      [Math.PI / 2, 0, 0]
    );
    shell.add(shellMesh);
    shell.add(makeEdgeLines(shellMesh));
    shell.add(makeMesh(new THREE.BoxGeometry(0.08, 0.22, 3.9), matBlue, [-0.98, 1.85, 0]));
    shell.add(makeMesh(new THREE.BoxGeometry(0.08, 0.22, 3.9), matBlue, [0.98, 1.85, 0]));
    addPart(
      "Basınç Kabuğu",
      "Yatay filtre/koaleser basınç kabuğu; teardown sırasında yukarı kalkar. İç elemanlar yarı saydam kabuktan görünür.",
      shell,
      [0, 1.75, 0],
      [0, 2.82, 0],
      "#b8c0c8"
    );

    const rearClosure = new THREE.Group();
    const rearCap = makeMesh(
      new THREE.SphereGeometry(0.92, 24, 14, 0, Math.PI * 2, 0, Math.PI / 2),
      matShellDark,
      [0, 1.85, -2.02],
      [-Math.PI / 2, 0, 0]
    );
    rearCap.scale.y = 0.42;
    rearClosure.add(rearCap);
    addPart(
      "Hızlı Açılır Kapak",
      "Kartuş değişimi için eksenel (-Z) açılan hızlı kapak (quick-opening closure).",
      rearClosure,
      [0, 0, -1.35],
      [0, 1.85, -2.38],
      "#7d8791"
    );

    const frontHead = new THREE.Group();
    const frontCap = makeMesh(
      new THREE.SphereGeometry(0.92, 24, 14, 0, Math.PI * 2, 0, Math.PI / 2),
      matShell,
      [0, 1.85, 2.02],
      [Math.PI / 2, 0, 0]
    );
    frontCap.scale.y = 0.42;
    frontHead.add(frontCap);
    addPart(
      "Dished Başlık",
      "Çıkış tarafındaki bombeli basınç başlığı; eksenel (+Z) yönde ayrılır.",
      frontHead,
      [0, 0, 1.25],
      [0, 1.85, 2.38],
      "#94a3b8"
    );

    const inlet = new THREE.Group();
    inlet.add(makeMesh(new THREE.CylinderGeometry(0.34, 0.34, 0.64, 16), matYellow, [0, 3.12, -0.85]));
    inlet.add(makeMesh(new THREE.CylinderGeometry(0.48, 0.48, 0.12, 16), matYellow, [0, 3.5, -0.85]));
    addPart(
      "Üst Giriş Nozulu",
      "Gazı filtre gövdesine yönlendiren üst inlet nozulu ve flanşı.",
      inlet,
      [0, 2.35, 0],
      [0, 3.52, -0.85],
      "#e2c400"
    );

    const outlet = new THREE.Group();
    outlet.add(makeMesh(new THREE.CylinderGeometry(0.34, 0.34, 0.66, 16), matYellow, [0, 1.85, 2.78], [Math.PI / 2, 0, 0]));
    outlet.add(makeMesh(new THREE.CylinderGeometry(0.48, 0.48, 0.12, 16), matYellow, [0, 1.85, 3.17], [Math.PI / 2, 0, 0]));
    addPart(
      "Outlet Nozulu",
      "Filtrelenmiş gazı CFS outlet header'ına veren eksenel uç nozulu.",
      outlet,
      [0, 0, 1.85],
      [0, 1.85, 3.15],
      "#e2c400"
    );

    const coalescer = new THREE.Group();
    coalescer.add(makeMesh(new THREE.CylinderGeometry(0.6, 0.6, 1.35, 24, 1, true), matInternal, [0, 1.85, 0.65], [Math.PI / 2, 0, 0]));
    for (let i = 0; i < 6; i++) {
      coalescer.add(makeMesh(new THREE.TorusGeometry(0.61, 0.024, 8, 22), matCopper, [0, 1.85, 0.15 + i * 0.2], [0, 0, 0]));
    }
    addPart(
      "Koaleser Eleman",
      "Damlacık birleştirici koaleser paketi; sıvıyı büyütüp yerçekimiyle ayırır.",
      coalescer,
      [0, 0, 0.65],
      [-0.55, 1.85, 0.65],
      "#4f8f9a"
    );

    const cartridges = new THREE.Group();
    for (let i = 0; i < 9; i++) {
      const a = (i * Math.PI * 2) / 9;
      cartridges.add(
        makeMesh(
          new THREE.CylinderGeometry(0.14, 0.14, 1.1, 12),
          matGreen,
          [Math.cos(a) * 0.48, 1.85 + Math.sin(a) * 0.48, -1.15],
          [Math.PI / 2, 0, 0]
        )
      );
    }
    addPart(
      "Kartuş Filtreler",
      "0.3 µm kartuş filtre demeti; hızlı açılır kapaktan eksenel olarak çekilir.",
      cartridges,
      [0, 0, -0.75],
      [0.52, 2.25, -1.15],
      "#2f7f6f"
    );

    const saddles = new THREE.Group();
    [-1.35, 1.35].forEach((z) => {
      saddles.add(makeMesh(new THREE.BoxGeometry(1.65, 0.56, 0.46), matBlue, [0, 0.62, z]));
      saddles.add(makeMesh(new THREE.BoxGeometry(2.0, 0.14, 0.82), matDark, [0, 0.27, z]));
    });
    addPart(
      "Saddle Destekler",
      "İki adet yatay sehpa; basınç kabuğunu taşır ve drenaj açıklığı bırakır.",
      saddles,
      [0, -0.18, 0],
      [0, 0.42, 1.55],
      "#2d6fa8"
    );

    camera.position.set(8.4, 7.0, 11.2);
    if (controls) controls.target.set(0, 1.85, 0);
  };

  if (key === "air_coolers") buildCooler();
  else if (key === "cyclones") buildCyclone();
  else if (key === "cartridge_filters") buildFilter();
  else buildCooler();

  const initialCamPos = camera.position.clone();
  const initialTarget = controls ? controls.target.clone() : new THREE.Vector3(0, 2.0, 0);
  if (!controls) camera.lookAt(initialTarget);

  // Parts list
  partsBox.innerHTML = parts.map((p, i) => partButton(p, i, i === 0)).join("");
  const partListButtons = [...partsBox.querySelectorAll(".kt-part-btn")];

  // 3D labels as accessible buttons
  const labelEls = parts.map((p, i) => {
    const el = document.createElement("button");
    el.type = "button";
    el.className = "kt-label";
    el.dataset.part = String(i);
    el.setAttribute("aria-pressed", "false");
    el.textContent = p.name;
    el.addEventListener("click", (event) => {
      event.stopPropagation();
      selectPart(i);
    });
    labelsBox.appendChild(el);
    return { part: p, el };
  });

  let selectedPart = -1;
  let explode = 0.35;
  let targetExplode = 0.35;
  let autoRotate = true;
  let running = true;
  let rafId = null;

  function syncLocalizedUi(lang) {
    currentLang = lang || "tr";
    const isEn = currentLang === "en";
    const closeLbl = t("teardown_btn_close", currentLang);
    closeBtn.setAttribute("aria-label", closeLbl);
    closeBtn.setAttribute("title", closeLbl);
    const liveBadge = overlay.querySelector("#kt-live-badge");
    if (liveBadge) liveBadge.textContent = isEn ? "● LIVE 3D" : "● CANLI MODEL";
    const secProc = overlay.querySelector("#kt-sec-process");
    if (secProc) secProc.textContent = t("teardown_sec_process", currentLang);
    const secParts = overlay.querySelector("#kt-sec-parts");
    if (secParts) secParts.textContent = t("teardown_sec_parts", currentLang);
    const sliderLbl = overlay.querySelector("#kt-slider-label");
    const sliderTxt = t("teardown_slider_label", currentLang);
    if (sliderLbl) sliderLbl.textContent = sliderTxt;
    explodeSlider.setAttribute("aria-label", sliderTxt);
    const expBtn = overlay.querySelector("#kt-explode-btn");
    if (expBtn) expBtn.textContent = `⏏ ${t("teardown_btn_explode", currentLang)}`;
    const asmBtn = overlay.querySelector("#kt-assemble-btn");
    if (asmBtn) asmBtn.textContent = `🧩 ${t("teardown_btn_assemble", currentLang)}`;
    const rstBtn = overlay.querySelector("#kt-reset-btn");
    if (rstBtn) rstBtn.textContent = `⌂ ${t("teardown_btn_reset", currentLang)}`;
    rotateBtn.textContent = autoRotate
      ? isEn
        ? "⟳ Auto-Rotate: On"
        : "⟳ Döndür: Açık"
      : isEn
        ? "⟳ Auto-Rotate: Off"
        : "⟳ Döndür: Kapalı";
    rotateBtn.setAttribute("aria-pressed", String(autoRotate));
    if (hintBox) {
      hintBox.textContent = isEn
        ? "Drag: rotate · Wheel: zoom · Esc: close"
        : "Sürükle: döndür · Tekerlek: yakınlaştır · Esc: kapat";
    }
    const infoTbody = overlay.querySelector("#kt-info-tbody");
    if (infoTbody) {
      infoTbody.innerHTML = renderInfoTableRows(key, context, currentLang);
    }
    if (selectedPart < 0) {
      descBox.textContent = isEn
        ? "Select a part from the list or click a 3D label."
        : "Parça seçmek için listeye veya model üzerindeki etikete tıklayın.";
    }
  }

  function selectPart(idx) {
    selectedPart = idx;
    partListButtons.forEach((btn, i) => {
      const active = i === idx;
      btn.classList.toggle("is-active", active);
      btn.setAttribute("aria-pressed", String(active));
    });
    labelEls.forEach(({ el }, i) => {
      const active = i === idx;
      el.classList.toggle("is-active", active);
      el.setAttribute("aria-pressed", String(active));
    });
    parts.forEach((p, i) => {
      p.group.scale.setScalar(i === idx ? 1.035 : 1.0);
    });
    const p = parts[idx];
    if (p) {
      descBox.innerHTML = `<b style="color:#f8fafc;">${escapeHtml(p.name)}</b><br>${escapeHtml(p.desc)}`;
    }
  }

  partListButtons.forEach((btn) => {
    btn.addEventListener("click", () => selectPart(Number(btn.dataset.part)));
    btn.addEventListener("mouseenter", () => {
      const p = parts[Number(btn.dataset.part)];
      if (p) p.group.scale.setScalar(1.02);
    });
    btn.addEventListener("mouseleave", () => {
      const p = parts[Number(btn.dataset.part)];
      if (p) p.group.scale.setScalar(Number(btn.dataset.part) === selectedPart ? 1.035 : 1.0);
    });
  });

  explodeSlider.addEventListener("input", () => {
    targetExplode = Number(explodeSlider.value);
  });
  overlay.querySelector("#kt-explode-btn").addEventListener("click", () => {
    targetExplode = 1;
    explodeSlider.value = "1";
  });
  overlay.querySelector("#kt-assemble-btn").addEventListener("click", () => {
    targetExplode = 0;
    explodeSlider.value = "0";
  });
  rotateBtn.addEventListener("click", () => {
    autoRotate = !autoRotate;
    if (controls) controls.autoRotate = autoRotate;
    syncLocalizedUi(currentLang);
  });
  overlay.querySelector("#kt-reset-btn").addEventListener("click", () => {
    targetExplode = 0.35;
    explodeSlider.value = "0.35";
    root.rotation.set(0, 0, 0);
    camera.position.copy(initialCamPos);
    if (controls) {
      controls.target.copy(initialTarget);
      controls.update();
    } else {
      camera.lookAt(initialTarget);
    }
  });

  const close = () => closeEquipmentTeardown();
  closeBtn.addEventListener("click", close);
  overlay.addEventListener("click", (event) => {
    if (event.target === overlay) close();
  });

  const onKey = (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      close();
      return;
    }
    if (event.key === "Tab") {
      const focusables = [...overlay.querySelectorAll("button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex='-1'])")];
      if (!focusables.length) return;
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
  };
  window.addEventListener("keydown", onKey, true);

  const unsubUi =
    typeof uiStore?.subscribe === "function"
      ? uiStore.subscribe((state) => {
          const nextLang = state?.lang || "tr";
          if (nextLang !== currentLang) syncLocalizedUi(nextLang);
        })
      : null;

  let resizeObserver = null;
  const resize = () => {
    const w = Math.max(1, viewer.clientWidth);
    const h = Math.max(1, viewer.clientHeight);
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  };
  resize();
  if (window.ResizeObserver) {
    resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(viewer);
  }
  window.addEventListener("resize", resize);

  syncLocalizedUi(currentLang);
  if (parts.length) selectPart(0);
  closeBtn.focus?.();

  let lastT = performance.now();
  const project = new THREE.Vector3();

  const animate = (now) => {
    if (!running) return;
    const dt = Math.min(0.05, (now - lastT) / 1000);
    lastT = now;

    explode += (targetExplode - explode) * Math.min(1, dt * 8.5);
    parts.forEach((p) => {
      p.group.position.copy(p.base).addScaledVector(p.explode, explode);
    });

    if (controls) {
      controls.autoRotate = autoRotate;
      controls.update();
    } else if (autoRotate) {
      root.rotation.y += dt * 0.16;
    }

    // Project 3D part anchors to 2D button labels
    labelEls.forEach(({ part, el }) => {
      project.copy(part.labelAnchor);
      part.group.localToWorld(project);
      project.project(camera);
      const visible = project.z > -1 && project.z < 1;
      if (!visible) {
        el.style.display = "none";
        return;
      }
      el.style.display = "block";
      const w = viewer.clientWidth;
      const h = viewer.clientHeight;
      el.style.left = `${(project.x * 0.5 + 0.5) * w}px`;
      el.style.top = `${(-project.y * 0.5 + 0.5) * h}px`;
    });

    renderer.render(scene, camera);
    if (running) {
      rafId = requestAnimationFrame(animate);
    }
  };
  rafId = requestAnimationFrame(animate);

  // Store cleanup on overlay so closeEquipmentTeardown can dispose all WebGL/DOM resources
  overlay.__kaspTeardown = { renderer, scene, camera, controls, render: () => renderer.render(scene, camera) };
  overlay.__kaspCleanup = () => {
    running = false;
    if (rafId !== null) {
      cancelAnimationFrame(rafId);
      rafId = null;
    }
    if (unsubUi) unsubUi();
    window.removeEventListener("keydown", onKey, true);
    window.removeEventListener("resize", resize);
    if (resizeObserver) resizeObserver.disconnect();
    if (controls && controls.dispose) controls.dispose();
    scene.traverse((o) => {
      if (o.geometry) o.geometry.dispose();
      if (o.material) {
        if (Array.isArray(o.material)) o.material.forEach((m) => m.dispose());
        else o.material.dispose();
      }
    });
    renderer.dispose();
    renderer.forceContextLoss?.();
    overlay.remove();
    if (previousFocus && typeof previousFocus.focus === "function") {
      try {
        previousFocus.focus();
      } catch (_) {
        // ignore detached node focus errors
      }
    }
  };
}

export function closeEquipmentTeardown() {
  const existing = document.getElementById(OVERLAY_ID);
  if (existing) {
    if (typeof existing.__kaspCleanup === "function") existing.__kaspCleanup();
    else existing.remove();
  }
}
