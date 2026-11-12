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

function infoRows(key, ctx) {
  const eq = ctx.eq || {};
  const sm = ctx.sm || {};
  const suc = ctx.sucLine || {};
  const nCyc = ctx.numCyclones || eq.cyclones?.installed_count || 2;
  const nFlt = ctx.numFilters || eq.cartridge_filters?.installed_count || 2;
  const nBay = ctx.numCoolerBays || eq.air_coolers?.bay_count || 2;

  if (key === "cyclones") {
    return [
      ["Ekipman", `V-101 … V-10${nCyc} · ${nCyc} ünite`],
      ["Proses basıncı", `${sm.suction_pressure_bar || 20.0} bar(a)`],
      ["Basınç düşümü", `${eq.cyclones?.pressure_drop_bar || 0.15} bar`],
      ["Giriş sıcaklığı", `${sm.suction_temp_c || 25.0} °C`],
      ["Ünite debisi", `${eq.cyclones?.flow_per_unit_kgs || 12.0} kg/s`],
      ["Sıvı / katı ayırma", "> %99.5 · > 10 µm"],
      ["Giriş branşmanı", eq.cyclones?.inlet_pipe_size || `${suc.nominal_size_in || '10"'} NPS`],
      ["Konfigürasyon", `${eq.cyclones?.operating_count || (nCyc - 1)} aktif + 1 yedek`],
    ];
  }
  if (key === "cartridge_filters") {
    return [
      ["Ekipman", `F-101 … F-10${nFlt} · ${nFlt} ünite`],
      ["Giriş / çıkış basıncı", `${(sm.suction_pressure_bar || 20.0)} → ${((sm.suction_pressure_bar || 20.0) - 0.25).toFixed(2)} bar(a)`],
      ["Temiz filtre ΔP", `${eq.cartridge_filters?.clean_dp_bar || 0.10} bar (maks. 0.70 bar)`],
      ["Filtrasyon", "0.3 µm · %99.98 aerosol tutma"],
      ["Ünite debisi", `${eq.cartridge_filters?.flow_per_unit_kgs || 12.0} kg/s`],
      ["Giriş branşmanı", eq.cartridge_filters?.inlet_pipe_size || "12\" NPS"],
      ["Konfigürasyon", `${eq.cartridge_filters?.operating_count || (nFlt - 1)} aktif + 1 yedek`],
      ["Enstrümantasyon", "PDT diferansiyel basınç transmitteri"],
    ];
  }
  if (key === "air_coolers") {
    const rows = [
      ["Ekipman", `E-101 · ${nBay} fin-fan bay`],
      ["Giriş sıcaklığı", `${eq.air_coolers?.inlet_temp_c || 79.0} °C`],
      ["Çıkış sıcaklığı", `${eq.air_coolers?.outlet_temp_c || 45.0} °C`],
      ["Toplam ısıl yük", `${eq.air_coolers?.total_heat_duty_mw || 14.8} MWth`],
      ["Fan konfigürasyonu", `${eq.air_coolers?.total_fans || (nBay * 2)} adet VFD fan`],
      ["Gaz basınç kaybı", `${eq.air_coolers?.pressure_drop_bar || 0.45} bar`],
      ["Inlet / outlet header", `${eq.air_coolers?.inlet_header_pipe_size || '6"'} / ${eq.air_coolers?.outlet_header_pipe_size || '6"'}`],
    ];
    const design = eq.air_coolers?.detailed_design;
    if (design) {
      rows.push(["API 661 alan", `${Number(design.actual_area_m2 || 0).toFixed(1)} m² (%${Number(design.overdesign_pct || 0).toFixed(1)} overdesign)`]);
      rows.push(["Fan gücü / uç hızı", `${Number(design.fan_power_kw || 0).toFixed(1)} kW · ${Number(design.fan_tip_speed_ms || 0).toFixed(1)} m/s`]);
    }
    return rows;
  }
  return [["Ekipman", key]];
}

function partButton(part, idx) {
  return `<button class="kt-part-btn" data-part="${idx}" style="display:flex;align-items:center;gap:8px;width:100%;text-align:left;background:rgba(255,255,255,.04);border:1px solid rgba(148,163,184,.18);border-radius:7px;padding:6px 8px;color:#e2e8f0;font-size:11px;cursor:pointer;margin:4px 0;">
    <span style="width:9px;height:9px;border-radius:50%;background:${part.cssColor};box-shadow:0 0 8px ${part.cssColor};flex:none;"></span>
    <span style="font-weight:700;">${part.name}</span>
  </button>`;
}

export function openEquipmentTeardown(key, context = {}) {
  const THREE = window.THREE;
  if (!THREE) return;
  closeEquipmentTeardown();

  const overlay = document.createElement("div");
  overlay.id = OVERLAY_ID;
  overlay.style.cssText = "position:fixed;inset:0;z-index:10050;background:rgba(2,6,17,.84);backdrop-filter:blur(10px);display:flex;align-items:center;justify-content:center;padding:18px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;";
  overlay.innerHTML = `
    <div style="width:min(1420px,98vw);height:min(880px,94vh);background:linear-gradient(145deg,#0b1220 0%,#0d1728 48%,#08111d 100%);border:1px solid #1e3a5f;border-radius:16px;box-shadow:0 28px 90px rgba(0,0,0,.7);display:flex;flex-direction:column;overflow:hidden;">
      <div style="display:flex;align-items:center;justify-content:space-between;gap:14px;padding:14px 18px;border-bottom:1px solid rgba(148,163,184,.18);background:rgba(15,23,42,.72);">
        <div>
          <div style="font-size:16px;font-weight:900;color:#f8fafc;letter-spacing:.3px;">🔧 ${context.title || "Ekipman Teardown"}</div>
          <div style="font-size:11px;color:#94a3b8;margin-top:2px;">${context.subtitle || "Interactive exploded view · KASP 3D Digital Twin"}</div>
        </div>
        <div style="display:flex;align-items:center;gap:8px;">
          <span style="font-size:10px;font-weight:700;color:#34d399;border:1px solid rgba(52,211,153,.5);background:rgba(16,185,129,.12);padding:4px 9px;border-radius:20px;">● CANLI MODEL</span>
          <button id="kt-close" style="background:rgba(255,255,255,.06);border:1px solid rgba(148,163,184,.25);color:#e2e8f0;border-radius:8px;width:34px;height:34px;font-size:17px;cursor:pointer;">✕</button>
        </div>
      </div>
      <div style="display:grid;grid-template-columns:340px minmax(0,1fr);min-height:0;flex:1;">
        <aside style="border-right:1px solid rgba(148,163,184,.16);background:rgba(8,15,28,.58);padding:14px;overflow:auto;">
          <div style="font-size:10px;font-weight:800;letter-spacing:.12em;text-transform:uppercase;color:#38bdf8;margin-bottom:8px;">Ekipman Bilgileri</div>
          <table style="width:100%;border-collapse:collapse;font-size:10.5px;">
            <tbody>
              ${infoRows(key, context).map(([l, v]) => `<tr style="border-bottom:1px solid rgba(148,163,184,.09);"><td style="padding:5px 0;color:#94a3b8;vertical-align:top;">${l}</td><td style="padding:5px 0;text-align:right;color:#f8fafc;font-weight:700;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;">${v}</td></tr>`).join("")}
            </tbody>
          </table>
          <div style="height:1px;background:rgba(148,163,184,.14);margin:14px 0;"></div>
          <div style="font-size:10px;font-weight:800;letter-spacing:.12em;text-transform:uppercase;color:#fbbf24;margin-bottom:8px;">Sökülebilir Parçalar</div>
          <div id="kt-parts"></div>
          <div id="kt-part-desc" style="margin-top:10px;padding:9px 10px;border-radius:8px;background:rgba(56,189,248,.08);border:1px solid rgba(56,189,248,.22);color:#bae6fd;font-size:10.5px;line-height:1.45;min-height:54px;">Parça seçmek için listeye veya model üzerindeki etikete tıklayın.</div>
        </aside>
        <section style="position:relative;min-width:0;min-height:0;">
          <div id="kt-viewer" style="position:absolute;inset:0;"></div>
          <div id="kt-labels" style="position:absolute;inset:0;pointer-events:none;overflow:hidden;"></div>
          <div style="position:absolute;left:14px;bottom:14px;right:14px;display:flex;align-items:center;gap:10px;flex-wrap:wrap;padding:10px 12px;border-radius:10px;background:rgba(8,15,28,.82);border:1px solid rgba(148,163,184,.18);backdrop-filter:blur(8px);">
            <span style="font-size:10px;font-weight:800;color:#94a3b8;letter-spacing:.08em;">SÖKÜM</span>
            <input id="kt-explode" type="range" min="0" max="1" step="0.01" value="0.35" style="flex:1;min-width:120px;accent-color:#38bdf8;" />
            <button id="kt-explode-btn" class="kt-ctrl" style="background:#0284c7;border-color:#38bdf8;color:#fff;">⏏ Sök</button>
            <button id="kt-assemble-btn" class="kt-ctrl">🧩 Topla</button>
            <button id="kt-rotate-btn" class="kt-ctrl" style="background:rgba(56,189,248,.15);border-color:#38bdf8;color:#bae6fd;">⟳ Döndür: Açık</button>
            <button id="kt-reset-btn" class="kt-ctrl">⌂ Sıfırla</button>
          </div>
          <div style="position:absolute;top:14px;right:14px;padding:6px 9px;border-radius:8px;background:rgba(8,15,28,.7);border:1px solid rgba(148,163,184,.16);font-size:10px;color:#94a3b8;">Sürükle: döndür · Tekerlek: yakınlaştır</div>
        </section>
      </div>
    </div>
    <style>
      .kt-ctrl{background:rgba(255,255,255,.06);border:1px solid rgba(148,163,184,.25);color:#e2e8f0;border-radius:7px;padding:6px 10px;font-size:10.5px;font-weight:700;cursor:pointer;}
      .kt-ctrl:hover{background:rgba(56,189,248,.15);border-color:#38bdf8;}
      .kt-part-btn:hover{background:rgba(56,189,248,.12)!important;border-color:rgba(56,189,248,.55)!important;}
      .kt-part-btn.is-active{background:rgba(56,189,248,.2)!important;border-color:#38bdf8!important;}
      .kt-label{position:absolute;transform:translate(-50%,-50%);pointer-events:auto;cursor:pointer;white-space:nowrap;font-size:10px;font-weight:800;color:#e2e8f0;background:rgba(3,7,18,.78);border:1px solid rgba(56,189,248,.5);border-radius:12px;padding:3px 8px;box-shadow:0 4px 14px rgba(0,0,0,.45);}
      .kt-label:before{content:"";position:absolute;left:50%;top:100%;width:1px;height:16px;background:rgba(56,189,248,.5);}
    </style>
  `;
  document.body.appendChild(overlay);

  const viewer = overlay.querySelector("#kt-viewer");
  const labelsBox = overlay.querySelector("#kt-labels");
  const partsBox = overlay.querySelector("#kt-parts");
  const descBox = overlay.querySelector("#kt-part-desc");
  const explodeSlider = overlay.querySelector("#kt-explode");

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
    controls.target.set(0, 1.6, 0);
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
  const matHalfShell = new THREE.MeshStandardMaterial({ color: COLORS.shell, roughness: 0.36, metalness: 0.75, side: THREE.DoubleSide });
  const matHalfShellDark = new THREE.MeshStandardMaterial({ color: COLORS.shellDark, roughness: 0.46, metalness: 0.62, side: THREE.DoubleSide });
  const matGhostShell = new THREE.MeshStandardMaterial({ color: COLORS.shell, roughness: 0.42, metalness: 0.55, transparent: true, opacity: 0.30, side: THREE.DoubleSide, depthWrite: false });
  const matGhostShellDark = new THREE.MeshStandardMaterial({ color: COLORS.shellDark, roughness: 0.48, metalness: 0.55, transparent: true, opacity: 0.26, side: THREE.DoubleSide, depthWrite: false });

  const root = new THREE.Group();
  scene.add(root);
  const parts = [];

  const addPart = (name, desc, group, explode, labelAnchor, cssColor = "#38bdf8") => {
    root.add(group);
    parts.push({ name, desc, group, explode: new THREE.Vector3(...explode), base: group.position.clone(), labelAnchor: new THREE.Vector3(...labelAnchor), cssColor });
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

  const buildCooler = () => {
    const structure = new THREE.Group();
    [[-2.6, -1.8], [2.6, -1.8], [-2.6, 1.8], [2.6, 1.8]].forEach(([x, z]) => {
      structure.add(makeMesh(new THREE.BoxGeometry(0.18, 1.5, 0.18), matBlue, [x, 0.75, z]));
    });
    structure.add(makeMesh(new THREE.BoxGeometry(5.6, 0.18, 0.18), matBlue, [0, 1.45, -1.8]));
    structure.add(makeMesh(new THREE.BoxGeometry(5.6, 0.18, 0.18), matBlue, [0, 1.45, 1.8]));
    structure.add(makeMesh(new THREE.BoxGeometry(0.18, 0.18, 3.8), matBlue, [-2.6, 1.45, 0]));
    structure.add(makeMesh(new THREE.BoxGeometry(0.18, 0.18, 3.8), matBlue, [2.6, 1.45, 0]));
    addPart("Çelik Karkas", "Kolonlar, ana kirişler ve fan platformu taşıyıcı çerçevesi.", structure, [0, -1.05, 0], [0, 0.2, 2.1], "#2d6fa8");

    const plenum = new THREE.Group();
    plenum.add(makeMesh(new THREE.BoxGeometry(5.2, 0.72, 3.4), matShellDark, [0, 1.86, 0]));
    plenum.add(makeMesh(new THREE.BoxGeometry(4.9, 0.12, 0.16), matBlue, [0, 2.22, -1.68]));
    plenum.add(makeMesh(new THREE.BoxGeometry(4.9, 0.12, 0.16), matBlue, [0, 2.22, 1.68]));
    addPart("Plenum Odası", "Fanların çektiği havayı fin-tüp demetine yönlendiren kapalı hava odası.", plenum, [0, -0.5, 0], [0, 1.9, 0], "#94a3b8");

    const bundle = new THREE.Group();
    bundle.add(makeMesh(new THREE.BoxGeometry(4.8, 0.78, 2.9), matGreen, [0, 2.58, 0]));
    [-2.42, 2.42].forEach((x) => {
      bundle.add(makeMesh(new THREE.BoxGeometry(0.12, 0.95, 3.0), matBlue, [x, 2.58, 0]));
      bundle.add(makeMesh(new THREE.CylinderGeometry(0.22, 0.22, 3.0, 14), matShell, [x + (x < 0 ? -0.18 : 0.18), 2.1, 0], [Math.PI / 2, 0, 0]));
    });
    for (let i = 0; i < 12; i++) {
      bundle.add(makeMesh(new THREE.BoxGeometry(0.06, 0.66, 2.8), matCopper, [-2.1 + i * 0.38, 2.58, 0]));
    }
    addPart("Fin-Tüp Demeti", "Kanatlı tüpler, tüp tabloları ve inlet/outlet header bağlantıları.", bundle, [0, 0.55, 0], [0, 2.7, 0], "#2f7f6f");

    const fans = new THREE.Group();
    [-1.25, 1.25].forEach((x) => {
      const ring = makeMesh(new THREE.TorusGeometry(1.02, 0.07, 8, 30), matBlue, [x, 3.4, 0], [Math.PI / 2, 0, 0]);
      fans.add(ring);
      const shroud = makeMesh(new THREE.CylinderGeometry(1.02, 1.02, 0.3, 24, 1, true), matShellDark, [x, 3.36, 0]);
      fans.add(shroud);
      const hub = makeMesh(new THREE.CylinderGeometry(0.17, 0.17, 0.2, 14), matDark, [x, 3.42, 0]);
      fans.add(hub);
      for (let b = 0; b < 6; b++) {
        const blade = makeMesh(new THREE.BoxGeometry(1.65, 0.06, 0.36), matShell, [
          x + Math.cos((b * Math.PI) / 3) * 0.82,
          3.43,
          Math.sin((b * Math.PI) / 3) * 0.82,
        ]);
        blade.rotation.set(0.14, -(b * Math.PI) / 3, 0);
        fans.add(blade);
      }
      fans.add(makeMesh(new THREE.CylinderGeometry(0.26, 0.26, 0.42, 14), matDark, [x + 0.82, 3.82, 0]));
      fans.add(makeMesh(new THREE.BoxGeometry(0.85, 0.08, 0.18), matBlue, [x + 0.4, 3.78, 0]));
    });
    addPart("Fan Grubu", "İki adet VFD fan, fan halkaları, göbek, kanatlar, motor ve kayış muhafazası.", fans, [0, 1.45, 0], [0, 3.55, 0], "#38bdf8");

    const louvers = new THREE.Group();
    louvers.add(makeMesh(new THREE.BoxGeometry(5.3, 0.1, 3.3), matShellDark, [0, 4.05, 0]));
    for (let i = 0; i < 7; i++) {
      louvers.add(makeMesh(new THREE.BoxGeometry(5.0, 0.05, 0.26), matDark, [0, 4.1, -1.32 + i * 0.44]));
    }
    addPart("Louver Kapağı", "Hava çıkış louverları; fan çekme kaybını ve yağmur girişini sınırlar.", louvers, [0, 2.05, 0], [0, 4.2, 0], "#fbbf24");

    const headers = new THREE.Group();
    [-2.95, 2.95].forEach((x) => {
      headers.add(makeMesh(new THREE.CylinderGeometry(0.32, 0.32, 3.2, 16), matYellow, [x, 2.05, 0], [Math.PI / 2, 0, 0]));
      headers.add(makeMesh(new THREE.CylinderGeometry(0.42, 0.42, 0.18, 16), matYellow, [x, 2.05, -1.62], [Math.PI / 2, 0, 0]));
      headers.add(makeMesh(new THREE.CylinderGeometry(0.42, 0.42, 0.18, 16), matYellow, [x, 2.05, 1.62], [Math.PI / 2, 0, 0]));
    });
    addPart("Inlet / Outlet Header", "Sıcak gaz giriş ve soğutulmuş gaz çıkış headerları; nozullar ve kör flanşlar.", headers, [0, 0.1, 0], [-2.95, 2.05, 0], "#e2c400");

    camera.position.set(9.2, 7.2, 13.0);
    if (controls) controls.target.set(0, 2.3, 0);
  };

  const buildCyclone = () => {
    const shellA = new THREE.Group();
    const shellAMesh = makeMesh(new THREE.CylinderGeometry(0.95, 0.95, 3.6, 28, 1, true, 0, Math.PI), matGhostShell, [0, 2.25, 0]);
    shellA.add(shellAMesh);
    shellA.add(new THREE.LineSegments(new THREE.EdgesGeometry(shellAMesh.geometry), new THREE.LineBasicMaterial({ color: 0x9fd8ff, transparent: true, opacity: 0.55 })));
    addPart("Sol Gövde Kabuğu", "Silindirik basınç kabuğunun yarısı; teardown için yana açılır.", shellA, [-0.65, 0, 0], [-0.95, 2.3, 0], "#b8c0c8");

    const shellB = new THREE.Group();
    const shellBMesh = makeMesh(new THREE.CylinderGeometry(0.95, 0.95, 3.6, 28, 1, true, Math.PI, Math.PI), matGhostShellDark, [0, 2.25, 0]);
    shellB.add(shellBMesh);
    shellB.add(new THREE.LineSegments(new THREE.EdgesGeometry(shellBMesh.geometry), new THREE.LineBasicMaterial({ color: 0x9fd8ff, transparent: true, opacity: 0.55 })));
    addPart("Sağ Gövde Kabuğu", "Kabuğun diğer yarısı; iç vorteks bulucu ve giriş bölgesini açığa çıkarır.", shellB, [0.65, 0, 0], [0.95, 2.3, 0], "#7d8791");

    const head = new THREE.Group();
    head.add(makeMesh(new THREE.SphereGeometry(0.95, 24, 14, 0, Math.PI * 2, 0, Math.PI / 2), matShell, [0, 4.05, 0]));
    head.add(makeMesh(new THREE.CylinderGeometry(0.34, 0.34, 0.62, 16), matShell, [0, 4.78, 0]));
    head.add(makeMesh(new THREE.CylinderGeometry(0.48, 0.48, 0.12, 16), matFlangeMat(), [0, 5.1, 0]));
    addPart("Üst Başlık & Outlet Nozulu", "Dished üst başlık, gaz çıkış nozulu ve kör flanş.", head, [0, 1.3, 0], [0, 4.9, 0], "#b8c0c8");

    const cone = new THREE.Group();
    cone.add(makeMesh(new THREE.ConeGeometry(0.95, 1.15, 24), matShell, [0, -0.12, 0], [Math.PI, 0, 0]));
    cone.add(makeMesh(new THREE.CylinderGeometry(0.18, 0.18, 0.55, 12), matShellDark, [0, -0.78, 0]));
    addPart("Konik Alt & Drenaj", "Katı/sıvı toplama konisi ve drenaj nozulu.", cone, [0, -1.15, 0], [0, -0.4, 0], "#94a3b8");

    const inlet = new THREE.Group();
    inlet.add(makeMesh(new THREE.CylinderGeometry(0.34, 0.34, 0.9, 16), matYellow, [-1.35, 3.05, 0], [0, 0, Math.PI / 2]));
    inlet.add(makeMesh(new THREE.CylinderGeometry(0.48, 0.48, 0.12, 16), matYellow, [-1.82, 3.05, 0], [0, 0, Math.PI / 2]));
    addPart("Teğetsel Giriş Nozulu", "Gazı silindirik gövdeye teğetsel olarak veren inlet nozulu ve flanşı.", inlet, [-1.2, 0.25, 0], [-1.8, 3.05, 0], "#e2c400");

    const internal = new THREE.Group();
    internal.add(makeMesh(new THREE.CylinderGeometry(0.42, 0.42, 2.1, 18, 1, true), matInternal, [0, 3.0, 0]));
    internal.add(makeMesh(new THREE.CylinderGeometry(0.55, 0.55, 0.22, 18), matCopper, [0, 4.02, 0]));
    internal.add(makeMesh(new THREE.ConeGeometry(0.42, 0.9, 18), matCopper, [0, 1.75, 0]));
    for (let i = 0; i < 8; i++) {
      internal.add(makeMesh(new THREE.TorusGeometry(0.46, 0.025, 6, 18), matInternal, [0, 2.05 + i * 0.22, 0], [Math.PI / 2, 0, 0]));
    }
    addPart("Vorteks Bulucu / İç Eleman", "Merkezi vorteks bulucu tüp, üst bafle ve iç akış yönlendiricileri.", internal, [0, 0.35, 0], [0, 3.0, 0], "#4f8f9a");

    const support = new THREE.Group();
    for (let i = 0; i < 3; i++) {
      const a = (i * Math.PI * 2) / 3;
      support.add(makeMesh(new THREE.BoxGeometry(0.14, 1.0, 0.14), matBlue, [Math.cos(a) * 1.05, -0.05, Math.sin(a) * 1.05]));
    }
    support.add(makeMesh(new THREE.TorusGeometry(1.03, 0.06, 8, 28), matBlue, [0, -0.5, 0], [Math.PI / 2, 0, 0]));
    addPart("Destek & Skirt", "Üç ayaklı destek ve konik alt çevresindeki taşıyıcı halka.", support, [0, -0.55, 0], [0, -0.2, 1.15], "#2d6fa8");

    camera.position.set(8.6, 7.2, 10.8);
    if (controls) controls.target.set(0, 2.0, 0);
  };

  const matFlangeMat = () => new THREE.MeshStandardMaterial({ color: 0xd4c800, roughness: 0.3, metalness: 0.65 });

  const buildFilter = () => {
    const shell = new THREE.Group();
    const shellMesh = makeMesh(new THREE.CylinderGeometry(0.92, 0.92, 4.2, 28), matGhostShell, [0, 1.65, 0], [Math.PI / 2, 0, 0]);
    shell.add(shellMesh);
    shell.add(new THREE.LineSegments(new THREE.EdgesGeometry(shellMesh.geometry), new THREE.LineBasicMaterial({ color: 0x9fd8ff, transparent: true, opacity: 0.55 })));
    shell.add(makeMesh(new THREE.BoxGeometry(0.1, 1.7, 4.2), matBlue, [-0.92, 1.65, 0]));
    shell.add(makeMesh(new THREE.BoxGeometry(0.1, 1.7, 4.2), matBlue, [0.92, 1.65, 0]));
    addPart("Basınç Kabuğu", "Yatay filtre/koaleser basınç kabuğu; teardown sırasında yukarı kalkar. İç elemanlar yarı saydam kabuktan görünür.", shell, [0, 1.15, 0], [0, 2.6, 0], "#b8c0c8");

    const heads = new THREE.Group();
    [-2.15, 2.15].forEach((z) => {
      const h = makeMesh(new THREE.SphereGeometry(0.92, 24, 14), matShell, [0, 1.65, z]);
      h.scale.z = 0.4;
      heads.add(h);
    });
    addPart("Dished Kapaklar", "Her iki uçtaki bombeli kapaklar; bir uçta outlet nozulu bulunur.", heads, [0, 0, 0], [0, 1.65, 2.4], "#94a3b8");

    const inlet = new THREE.Group();
    inlet.add(makeMesh(new THREE.CylinderGeometry(0.36, 0.36, 0.72, 16), matYellow, [0, 2.6, -0.8]));
    inlet.add(makeMesh(new THREE.CylinderGeometry(0.5, 0.5, 0.12, 16), matYellow, [0, 2.98, -0.8]));
    addPart("Üst Giriş Nozulu", "Gazı koaleser elemanların üzerine yönlendiren üst inlet nozulu.", inlet, [0, 0.8, 0], [0, 2.9, -0.8], "#e2c400");

    const outlet = new THREE.Group();
    outlet.add(makeMesh(new THREE.CylinderGeometry(0.36, 0.36, 0.72, 16), matYellow, [0, 1.65, 2.48], [Math.PI / 2, 0, 0]));
    outlet.add(makeMesh(new THREE.CylinderGeometry(0.5, 0.5, 0.12, 16), matYellow, [0, 1.65, 2.85], [Math.PI / 2, 0, 0]));
    addPart("Outlet Nozulu", "Filtrelenmiş gazı CFS outlet header'ına veren uç nozulu.", outlet, [0, 0.25, 1.1], [0, 1.65, 2.8], "#e2c400");

    const coalescer = new THREE.Group();
    coalescer.add(makeMesh(new THREE.CylinderGeometry(0.62, 0.62, 1.5, 24, 1, true), matInternal, [0, 1.65, 0.25], [Math.PI / 2, 0, 0]));
    for (let i = 0; i < 7; i++) {
      coalescer.add(makeMesh(new THREE.TorusGeometry(0.63, 0.025, 6, 22), matCopper, [0, 1.65, -0.35 + i * 0.2], [Math.PI / 2, 0, 0]));
    }
    addPart("Koaleser Eleman", "Damlacık birleştirici koaleser paketi; sıvıyı büyütüp yerçekimiyle ayırır.", coalescer, [-0.65, 0.15, 0], [-0.6, 1.65, 0.2], "#4f8f9a");

    const cartridges = new THREE.Group();
    for (let i = 0; i < 9; i++) {
      const a = (i * Math.PI * 2) / 9;
      cartridges.add(makeMesh(new THREE.CylinderGeometry(0.15, 0.15, 1.1, 12), matGreen, [Math.cos(a) * 0.48, 1.65, -1.25 + Math.sin(a) * 0.48], [Math.PI / 2, 0, 0]));
    }
    addPart("Kartuş Filtreler", "0.3 µm kartuş filtre demeti; ince aerosol ve toz tutma kademesi.", cartridges, [0.65, 0.15, 0], [0.55, 1.65, -1.1], "#2f7f6f");

    const saddles = new THREE.Group();
    [-1.35, 1.35].forEach((z) => {
      saddles.add(makeMesh(new THREE.BoxGeometry(1.65, 0.9, 0.48), matBlue, [0, 0.55, z]));
      saddles.add(makeMesh(new THREE.BoxGeometry(2.0, 0.16, 0.85), matDark, [0, 0.08, z]));
    });
    addPart("Saddle Destekler", "İki adet yatay sehpa; basınç kabuğunu taşır ve drenaj açıklığı bırakır.", saddles, [0, -0.8, 0], [0, 0.25, 1.55], "#2d6fa8");

    camera.position.set(8.2, 7.0, 10.8);
    if (controls) controls.target.set(0, 1.6, 0);
  };

  if (key === "air_coolers") buildCooler();
  else if (key === "cyclones") buildCyclone();
  else if (key === "cartridge_filters") buildFilter();
  else buildCooler();

  // Parts list
  partsBox.innerHTML = parts.map((p, i) => partButton(p, i)).join("");
  const partListButtons = [...partsBox.querySelectorAll(".kt-part-btn")];

  // 3D labels
  const labelEls = parts.map((p, i) => {
    const el = document.createElement("div");
    el.className = "kt-label";
    el.dataset.part = String(i);
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

  function selectPart(idx) {
    selectedPart = idx;
    partListButtons.forEach((btn, i) => btn.classList.toggle("is-active", i === idx));
    parts.forEach((p, i) => {
      p.group.scale.setScalar(i === idx ? 1.035 : 1.0);
    });
    const p = parts[idx];
    if (p) {
      descBox.innerHTML = `<b style="color:#f8fafc;">${p.name}</b><br>${p.desc}`;
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

  const onExplodeInput = () => {
    targetExplode = Number(explodeSlider.value);
  };
  explodeSlider.addEventListener("input", onExplodeInput);
  overlay.querySelector("#kt-explode-btn").addEventListener("click", () => {
    targetExplode = 1;
    explodeSlider.value = "1";
  });
  overlay.querySelector("#kt-assemble-btn").addEventListener("click", () => {
    targetExplode = 0;
    explodeSlider.value = "0";
  });
  const rotateBtn = overlay.querySelector("#kt-rotate-btn");
  rotateBtn.addEventListener("click", () => {
    autoRotate = !autoRotate;
    rotateBtn.textContent = autoRotate ? "⟳ Döndür: Açık" : "⟳ Döndür: Kapalı";
  });
  overlay.querySelector("#kt-reset-btn").addEventListener("click", () => {
    targetExplode = 0.35;
    explodeSlider.value = "0.35";
    if (controls) {
      camera.position.set(key === "air_coolers" ? 8.6 : 7.0, 6.3, 9.6);
      controls.target.set(0, key === "air_coolers" ? 2.2 : 1.9, 0);
      controls.update();
    }
  });

  const close = () => closeEquipmentTeardown();
  overlay.querySelector("#kt-close").addEventListener("click", close);
  overlay.addEventListener("click", (event) => {
    if (event.target === overlay) close();
  });
  const onKey = (event) => {
    if (event.key === "Escape") close();
  };
  window.addEventListener("keydown", onKey);

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

  let lastT = performance.now();
  const tmp = new THREE.Vector3();
  const project = new THREE.Vector3();

  const animate = (now) => {
    if (!running) return;
    const dt = Math.min(0.05, (now - lastT) / 1000);
    lastT = now;

    explode += (targetExplode - explode) * Math.min(1, dt * 8.5);
    parts.forEach((p) => {
      p.group.position.copy(p.base).addScaledVector(p.explode, explode);
    });

    if (autoRotate && !(controls && controls.state === -1)) {
      // OrbitControls has no public state flag in all builds; rotate the root.
      root.rotation.y += dt * 0.16;
    } else if (!autoRotate) {
      // keep user orbit
    }

    if (controls) controls.update();

    // labels
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
    requestAnimationFrame(animate);
  };
  requestAnimationFrame(animate);

  // store cleanup on overlay so closeEquipmentTeardown can dispose
  overlay.__kaspTeardown = { renderer, scene, camera, controls, render: () => renderer.render(scene, camera) };
  overlay.__kaspCleanup = () => {
    running = false;
    window.removeEventListener("keydown", onKey);
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
    overlay.remove();
  };

  // initial selection
  if (parts.length) selectPart(0);
}

export function closeEquipmentTeardown() {
  const existing = document.getElementById(OVERLAY_ID);
  if (existing) {
    if (typeof existing.__kaspCleanup === "function") existing.__kaspCleanup();
    else existing.remove();
  }
}
