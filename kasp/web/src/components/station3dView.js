/**
 * KASP 3D Compressor Station Digital Twin (station3dView.js)
 * Built to match both the BOTAŞ Adapazarı 3D CAD Model (Navisworks/AutoCAD Plant 3D)
 * and the LNG Project 3D Digital Twin architecture (terminal_3d_viewer.py & pipe_3d_viewer.py).
 *
 * Complete 3D Plant Features:
 * 1. Main 48" Natural Gas Pipeline (Underground dark-brown to Above-ground CAD yellow transitions),
 *    Pig Receiver (PIG-R) & Pig Launcher (PIG-L) traps, ESDVs, Blowdown/Vent stacks, North Pipe Rack.
 * 2. Process Filtration & Cooling Yard:
 *    - MFS (Multi-Cyclone Filter Separators) with 2-tier steel platform, U-loops, valves, condensate drains
 *    - CFS (Cartridge Filter Separators) horizontal vessels on saddles with overhead loops & walkways
 *    - GAS COOLER (Fin-Fan Air Cooler bank) on blue braced structural steel legs, 4 pairs of tall vertical
 *      yellow pipe risers, spinning VFD fans, and TCV By-Pass line (Note 17)
 *    - TEMPORARY WASTE STORAGE AREA (angled NE buildings)
 * 3. Internal Station Piping & Manifold Corridor:
 *    - 3 parallel yellow headers (48" Suction, Recycle Note 13, 48" Discharge)
 *    - 3D U-shaped expansion/crossover loops (Π-bends) with long-radius elbows
 *    - Weld-neck flanges, ball/plug valves, yellow handwheels, gas-over-oil actuators, steel platforms
 *    - 3D Cyan flow direction arrows (→) on yellow pipes + animated flow particles
 *    - East Header valve pit & translucent future-extension envelope
 * 4. Dynamic N+1 Individual Turbo-Compressor Unit Buildings (COMPRESSOR-01 .. COMPRESSOR-05+):
 *    - Individual brown gabled acoustic buildings with green 3D roof labels
 *    - Side turbine exhaust stack, combustion air intake filter house, lube oil cooler, local electrical room
 *    - Structural X-Ray / Cutaway Mode (COMPRESSOR-04 default, or All Units toggle): exposes blue structural
 *      steel portal columns, roof trusses, brown purlins, overhead bridge crane, GT + Compressor package,
 *      and internal yellow suction/discharge/anti-surge ASV piping with handwheels and walkways
 * 5. Auxiliary & Control Buildings Compound (South):
 *    - AUXILIARY & CONTROL BUILDING + TRANSFORMER 1 & 2 yard
 *    - GENERATOR & M.V. ROOM
 *    - FIRE WATER BUILDING & TANK + red perimeter fire hydrants
 *    - AIR COMPRESSOR BUILDING, GUARD SHELTER, Administration/Workshop Building
 * 6. Perimeter Double Security Wire Fence (Proses Tel Çiti) & 7.0 M. WIDE ROAD Asphalt Loop Network
 *    with white lane arrows, road labels, and dark-brown cable/pipe trench road crossings.
 */

import { uiStore } from "../store/uiStore.js";
import { t } from "../i18n/locales.js";
import { escapeHtml } from "../store/projectStore.js";
import { openEquipmentTeardown, closeEquipmentTeardown } from "./equipmentTeardown.js";

export function createStation3dView(container, stationData, onSelectEquipment, options = {}) {
  if (!window.THREE) {
    container.innerHTML = `
      <div style="flex: 1; display: flex; align-items: center; justify-content: center; color: var(--color-danger); min-height: 580px;">
        Three.js WebGL kütüphanesi yüklenemedi.
      </div>
    `;
    return { destroy: () => {}, getState: () => null };
  }

  const THREE = window.THREE;
  let isDestroyed = false;
  let animationFrameId = null;
  const uiLang = uiStore?.getState?.()?.lang || "tr";

  // Restore previous view state if re-mounting across calculations or tab switches
  const savedState = options.initialState || container.__kasp_3d_state__ || null;

  // Parse dynamic sizing & summary from station_service.py
  const eq = stationData?.equipment_sizing || {};
  const sm = stationData?.station_summary || {};
  const pLines = stationData?.station_piping?.lines || {};
  const pArch = stationData?.station_piping?.piping_architecture || {};
  const suctLine = pLines.suction_header || {};
  const compSuctHeaderLine = pLines.comp_suction_header || suctLine;
  const compBranchLine = pLines.comp_suction_branch || {};
  const dischLine = pLines.discharge_header || {};
  const compSuctionBranchLine = pLines.comp_suction_branch || compBranchLine;
  const compDischargeBranchLine = pLines.comp_discharge_branch || {};
  const antiSurgeLine = pLines.anti_surge_loop || {};
  const coolerInletLine = pLines.cooler_inlet || {};
  const coolerOutletLine = pLines.cooler_outlet || {};
  const coolerRiserLine = pLines.cooler_bay_risers || {};
  const coolerBypassLine = pLines.cooler_bypass || {};
  const mainlineInletLine = pLines.mainline_inlet || suctLine;
  const mainlineOutletLine = pLines.mainline_outlet || dischLine;
  const TEARDOWN_KEYS = new Set(["air_coolers", "cyclones", "cartridge_filters"]);
  // One visual scale for every sized process line. The scene keeps a CAD
  // exaggeration, but all radii are proportional to the ASME OD selected by
  // the hydraulic engine, so larger/smaller lines stay visually comparable.
  const visualPipeRadius = (odMm, fallbackOdMm, opts = {}) => {
    const { min = 0.16, max = 1.05, exaggeration = 2.8 } = opts;
    const od = Number(odMm) > 0 ? Number(odMm) : Number(fallbackOdMm);
    return Math.max(min, Math.min(max, (Number(od) || 0) / 1000.0 * exaggeration));
  };

  // Main Station Spine Radii (Station Suction Header & Station Discharge Header)
  // declared upfront so all crossing elevations respect full main-header diameters.
  const rMainlineInlet = visualPipeRadius(mainlineInletLine.od_mm, 273.0);
  const rMainlineOutlet = visualPipeRadius(mainlineOutletLine.od_mm, 273.0);
  const rSuctHeader = visualPipeRadius(suctLine.od_mm, 273.0);
  const rAntiSurgeHeader = visualPipeRadius(pLines.station_recycle?.od_mm, 168.28);
  const rDischHeader = visualPipeRadius(dischLine.od_mm, 273.0);
  const rCompSuctionBranch = visualPipeRadius(compSuctionBranchLine.od_mm, 273.0);
  const rCompDischargeBranch = visualPipeRadius(compDischargeBranchLine.od_mm, 168.28);
  const rAntiSurge = visualPipeRadius(antiSurgeLine.od_mm, 141.30);

  // Cooler line radii and dynamic crossing elevations.
  // Station Discharge Header return (z = -48, radius rDischHeader) passes above
  // both the filtered Station Suction Header (x = -12, y = 2.2, radius rSuctHeader)
  // and the hot Station Discharge Header feed (x = -4, y = 1.6, radius rDischHeader).
  const rCoolerInlet = visualPipeRadius(coolerInletLine.od_mm, 168.28);
  const rCoolerOutlet = visualPipeRadius(coolerOutletLine.od_mm, 168.28);
  const rCoolerRiser = visualPipeRadius(coolerRiserLine.od_mm, 141.30);
  const rCoolerBypass = visualPipeRadius(coolerBypassLine.od_mm, 101.60);
  const coolerOutletCrossY = 1.6 + rCoolerInlet + rCoolerRiser + 0.35;
  const coolerReturnY = Math.max(
    3.8,
    2.2 + rSuctHeader + rDischHeader + 0.45,
    1.6 + rDischHeader + rDischHeader + 0.45
  );
  const coolerBypassY = Math.max(
    5.2,
    coolerReturnY + rDischHeader + rCoolerBypass + 0.45
  );

  // MFS/CFS branch radii are taken from the same station-piping line objects
  // that feed the 3D pipes, so every flanged ball valve matches its pipe.
  const rCycloneBranch = visualPipeRadius(pLines.cyclone_branch?.od_mm, 323.8);
  const rFilterBranch = visualPipeRadius(pLines.filter_branch?.od_mm, 323.8);
  const numCyclones = Math.max(1, eq.cyclones?.installed_count || ((eq.cyclones?.operating_count || 1) + 1));
  const numFilters = Math.max(1, eq.cartridge_filters?.installed_count || ((eq.cartridge_filters?.operating_count || 1) + 1));
  const numComps = Math.max(1, eq.turbo_compressors?.installed_count || ((eq.turbo_compressors?.operating_count || 1) + 1));
  const numCoolerBays = Math.max(2, eq.air_coolers?.bay_count || 2);
  const coolerDesign = eq.air_coolers?.detailed_design || {};
  const coolerGeometry = coolerDesign.geometry || {};
  const coolerTubeRows = Math.max(1, Number(coolerGeometry.tube_rows || 4));
  const coolerTubesPerRow = Math.max(1, Number(coolerGeometry.tubes_per_row || 24));
  const coolerTubeLength = Math.max(1.0, Number(coolerGeometry.tube_length || 6.0));
  const coolerFansPerBay = Math.max(1, Math.min(4, Number(coolerGeometry.n_fans || 2)));
  const coolerFanDiameter = Math.max(0.8, Number(coolerGeometry.fan_diameter || 2.44));

  // Front manifold corridor constants (declared before section 7 because the
  // gas-cooler inlet tap uses headerEastX).
  const compPitch = 52;
  const compStartX = -120;
  const lastCompX = compStartX + Math.max(0, numComps - 1) * compPitch;
  const headerWestX = -132;
  const headerEastX = Math.max(lastCompX + 22, -10);
  const cutawayUnitIdx = Math.min(4, numComps);
  const cutawayUnitLabel = `COMPRESSOR-${String(cutawayUnitIdx).padStart(2, "0")}`;

  // Interactive View State (restored if previously active)
  let themeMode = savedState?.themeMode || "cad"; // "cad" (Daylight Plant 3D) or "night" (Dark LNG HUD theme)
  let cutawayMode = savedState?.cutawayMode || "unitCutaway"; // "unitCutaway", "all", "none"
  let showEnvelopes = savedState?.showEnvelopes !== undefined ? savedState.showEnvelopes : true;
  let showFlowParticles = savedState?.showFlowParticles !== undefined ? savedState.showFlowParticles : true;
  let showPipeLabels = savedState?.showPipeLabels !== undefined ? savedState.showPipeLabels : true;
  let showPipeSectionModal = false;

  // Root DOM with LNG-style Glassmorphic HUD, Legend, Layer Controls & Pill Camera Bar
  container.innerHTML = `
    <div id="station-3d-root" style="position: relative; width: 100%; height: 100%; min-height: 420px; overflow: hidden; background: #7aa0dc; border-radius: var(--radius-md); user-select: none; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
      
      <style>
        #station-3d-root { container-type: inline-size; container-name: s3d; }
        #station-3d-root[data-inspect="1"] .hud-legend { display: none !important; }
        #station-3d-root.station-3d-expanded { position: fixed !important; inset: 0 !important; width: 100vw !important; height: 100vh !important; z-index: 9999 !important; border-radius: 0 !important; }
        #station-3d-root button { transition: filter 120ms ease, transform 120ms ease; }
        #station-3d-root button:hover { filter: brightness(1.18); }
        #station-3d-root button:active { transform: translateY(1px); }
        #station-3d-root button:focus-visible { outline: 2px solid #facc15; outline-offset: 2px; }
        #station-3d-root .hud-presets, #station-3d-root .hud-toolbar { scrollbar-width: none; }
        #station-3d-root .hud-presets::-webkit-scrollbar, #station-3d-root .hud-toolbar::-webkit-scrollbar { display: none; }
        @container s3d (max-width: 980px) {
          .hud-legend { display: none !important; }
          .hud-panel { min-width: 0 !important; max-width: 250px; font-size: 10px !important; padding: 8px 10px !important; }
          .hud-toolbar { top: auto !important; bottom: 58px !important; flex-wrap: nowrap !important; overflow-x: auto; max-width: 96%; }
          .hud-toolbar button, .hud-presets button { white-space: nowrap; flex-shrink: 0; }
          .hud-presets { flex-wrap: nowrap !important; overflow-x: auto; border-radius: 18px !important; }
          #pipe-section-overlay { bottom: 108px !important; }
        }
        @container s3d (max-width: 620px) {
          .hud-panel .hud-extra { display: none !important; }
          #equip-telemetry-hud { width: calc(100% - 24px) !important; max-height: 55%; overflow-y: auto; }
        }
      </style>

      <!-- WebGL Canvas Mount -->
      <div id="three-canvas-mount" style="width: 100%; height: 100%; min-height: 420px; cursor: grab;"></div>

      <!-- Top-Left LNG-Style Telemetry HUD Panel -->
      <div class="hud-panel" style="position: absolute; top: 12px; left: 12px; z-index: 20; background: rgba(14, 19, 28, 0.88); border: 1px solid rgba(255,255,255,0.14); border-radius: 8px; padding: 11px 14px; min-width: 265px; backdrop-filter: blur(8px); box-shadow: 0 8px 24px rgba(0,0,0,0.45); color: #e6edf3; font-size: 11px;">
        <div style="font-size: 12px; font-weight: 700; color: #38bdf8; letter-spacing: 0.4px; display: flex; align-items: center; justify-content: space-between; margin-bottom: 7px; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 5px;">
          <span>⚡ KOMPRESÖR İSTASYONU DİJİTAL İKİZ (3D)</span>
          <span style="background: rgba(16,185,129,0.2); color: #34d399; border: 1px solid #10b981; padding: 1px 6px; border-radius: 8px; font-size: 9px;">CANLI</span>
        </div>
        <div style="display: flex; justify-content: space-between; margin: 3px 0; color: #94a3b8;">
          <span>Ana Hat Giriş / Çıkış:</span>
          <span style="font-family: monospace; font-weight: 600; color: #f8fafc;">${sm.suction_pressure_bar || 45} → ${sm.discharge_pressure_bar || 75} bar</span>
        </div>
        <div style="display: flex; justify-content: space-between; margin: 3px 0; color: #94a3b8;">
          <span>Süreç Sıcaklığı (Emiş/Çıkış):</span>
          <span style="font-family: monospace; font-weight: 600; color: #f8fafc;">${sm.suction_temp_c || 15}°C → ${eq.air_coolers?.outlet_temp_c || 38}°C</span>
        </div>
        <div style="display: flex; justify-content: space-between; margin: 3px 0; color: #94a3b8;">
          <span>Toplam Gaz Debisi:</span>
          <span style="font-family: monospace; font-weight: 600; color: #facc15;">${sm.total_mass_flow_kgs || 180} kg/s (${sm.volumetric_flow_mmscmd || 22.1} MMSCMD)</span>
        </div>
        <div style="display: flex; justify-content: space-between; margin: 3px 0; color: #94a3b8;">
          <span>Ünite Binaları & Güç:</span>
          <span style="font-family: monospace; font-weight: 600; color: #38bdf8;">${numComps} Ünite (${(sm.total_power_mw / Math.max(1, eq.turbo_compressors?.operating_count || 1)).toFixed(1)} MW/ün • ${sm.total_power_mw || 24.5} MW)</span>
        </div>
        <div class="hud-extra" style="display: flex; justify-content: space-between; margin: 3px 0; color: #94a3b8;">
          <span>Yakıt Tüketimi (İstasyon):</span>
          <span style="font-family: monospace; font-weight: 600; color: #10b981;">${((sm.total_power_mw || 24.5) * 195).toFixed(0)} kg/h (~${(((sm.total_power_mw || 24.5) * 195)/0.772).toFixed(0)} Sm³/h)</span>
        </div>
        <div class="hud-extra" style="display: flex; justify-content: space-between; margin: 3px 0; color: #94a3b8;">
          <span>Filtreleme & Soğutma:</span>
          <span style="font-family: monospace; font-weight: 600; color: #34d399;">${numCyclones} MFS • ${numFilters} CFS • ${numCoolerBays} Fan Bay</span>
        </div>
        <div class="hud-extra" style="display: flex; justify-content: space-between; margin-top: 6px; padding-top: 5px; border-top: 1px dashed rgba(255,255,255,0.12); color: #94a3b8;">
          <span>Boru & Saha Standartı:</span>
          <span style="font-family: monospace; font-weight: 600; color: #cbd5e1;">${suctLine.nominal_size_in || '48"'} ASME B31.8 / API 617</span>
        </div>
      </div>

      <!-- Top-Center Interactive Layer & Cutaway Controls -->
      <div class="hud-toolbar" style="position: absolute; top: 12px; left: 50%; transform: translateX(-50%); z-index: 20; display: flex; gap: 6px; flex-wrap: wrap; background: rgba(14, 19, 28, 0.88); backdrop-filter: blur(8px); padding: 6px 10px; border-radius: 20px; border: 1px solid rgba(255,255,255,0.15); box-shadow: 0 4px 16px rgba(0,0,0,0.35);">
        <button id="btn-cutaway-mode" style="background: #0284c7; color: #fff; border: 1px solid #38bdf8; border-radius: 14px; padding: 4px 10px; font-size: 11px; font-weight: 600; cursor: pointer;">
          🏗️ Bina Kesiti: ${cutawayUnitLabel} (X-Ray)
        </button>
        <button id="btn-toggle-pipe-labels" aria-pressed="${showPipeLabels ? "true" : "false"}" style="background: ${showPipeLabels ? "#7c3aed" : "#1e293b"}; color: ${showPipeLabels ? "#fff" : "#cbd5e1"}; border: 1px solid ${showPipeLabels ? "#c084fc" : "rgba(255,255,255,0.15)"}; border-radius: 14px; padding: 4px 10px; font-size: 11px; font-weight: 600; cursor: pointer;">
          ${escapeHtml(t("pipe_labels_toggle", uiLang))}
        </button>
        <button id="btn-toggle-envelopes" style="background: #1e293b; color: #e2e8f0; border: 1px solid rgba(255,255,255,0.15); border-radius: 14px; padding: 4px 10px; font-size: 11px; font-weight: 600; cursor: pointer;">
          📦 Bakım Hacimleri: Açık
        </button>
        <button id="btn-toggle-particles" style="background: #059669; color: #fff; border: 1px solid #34d399; border-radius: 14px; padding: 4px 10px; font-size: 11px; font-weight: 600; cursor: pointer;">
          💨 Akış Okları & Parçacıklar: Açık
        </button>
        <button id="btn-pipe-cutaway-inspector" style="background: #b45309; color: #fff; border: 1px solid #fbbf24; border-radius: 14px; padding: 4px 10px; font-size: 11px; font-weight: 600; cursor: pointer;">
          🔬 180° Boru İçi Akış Kesiti
        </button>
        <button id="btn-theme-mode" style="background: #1e293b; color: #e2e8f0; border: 1px solid rgba(255,255,255,0.15); border-radius: 14px; padding: 4px 10px; font-size: 11px; font-weight: 600; cursor: pointer;">
          ☀️ Mod: CAD Gündüz
        </button>
        <button id="btn-toggle-3d-fullscreen" type="button" aria-pressed="false" title="${escapeHtml(t("btn_3d_fullscreen", uiLang))} (F)" style="background: #1e293b; color: #e2e8f0; border: 1px solid rgba(255,255,255,0.15); border-radius: 14px; padding: 4px 10px; font-size: 11px; font-weight: 600; cursor: pointer;">
          ⛶ ${escapeHtml(t("btn_3d_fullscreen", uiLang))}
        </button>
      </div>

      <!-- Top-Right CAD Legend Panel -->
      <div class="hud-legend" style="position: absolute; top: 12px; right: 12px; z-index: 20; background: rgba(14, 19, 28, 0.88); border: 1px solid rgba(255,255,255,0.14); border-radius: 8px; padding: 10px 13px; font-size: 10.5px; color: #cbd5e1; backdrop-filter: blur(8px); max-width: 252px;">
        <div style="font-weight: 700; color: #94a3b8; margin-bottom: 5px; text-transform: uppercase; font-size: 9.5px; letter-spacing: 0.4px;">CAD Katman & Boru Sınır Lejantı</div>
        <div style="display: flex; align-items: center; gap: 7px; margin: 3px 0;"><span style="width: 14px; height: 5px; background: #e2d400; border: 1px solid #facc15; display: inline-block; border-radius: 2px;"></span><span>Ana Header (Suction/Discharge: ${suctLine.nominal_size_in || '10"'})</span></div>
        <div style="display: flex; align-items: center; gap: 7px; margin: 3px 0;"><span style="width: 14px; height: 3px; background: #e2d400; display: inline-block; border-radius: 2px;"></span><span>Ekipman Branşmanları (${compBranchLine.nominal_size_in || '10"'}/${compDischargeBranchLine.nominal_size_in || '6"'})</span></div>
        <div style="display: flex; align-items: center; gap: 7px; margin: 3px 0;"><span style="width: 14px; height: 4px; background: #f59e0b; display: inline-block; border-radius: 2px;"></span><span>PIG-R ➔ TC ➔ PIG-L Sınır Plakaları</span></div>
        <div style="display: flex; align-items: center; gap: 7px; margin: 3px 0;"><span style="width: 14px; height: 4px; background: #00f0ff; display: inline-block; border-radius: 2px;"></span><span>Boru İçi Gaz Akış Yönü & Tıklanabilir Hat</span></div>
        <div style="display: flex; align-items: center; gap: 7px; margin: 3px 0;"><span style="width: 14px; height: 4px; background: #5c3a21; display: inline-block; border-radius: 2px;"></span><span>Yeraltı Ana İletim Sınır Hattı (${mainlineInletLine.nominal_size_in || suctLine.nominal_size_in || '10"'})</span></div>
        <div style="display: flex; align-items: center; gap: 7px; margin: 3px 0;"><span style="width: 14px; height: 4px; background: #0077be; display: inline-block; border-radius: 2px;"></span><span>Çelik Karkas & Soğutucu Taşıyıcıları</span></div>
        <div style="display: flex; align-items: center; gap: 7px; margin: 3px 0;"><span style="width: 14px; height: 4px; background: #8c735b; display: inline-block; border-radius: 2px;"></span><span>Ünite & Kontrol Binaları Kaplaması</span></div>
        <div style="display: flex; align-items: center; gap: 7px; margin: 3px 0;"><span style="width: 14px; height: 4px; background: #d91414; display: inline-block; border-radius: 2px;"></span><span>Yangın Hidrant Hattı & ESD Vanalar</span></div>
      </div>

      <!-- Interactive In-Canvas Floating Equipment / Pipe Telemetry HUD Card -->
      <div id="equip-telemetry-hud" style="display: none; position: absolute; top: 12px; right: 12px; z-index: 30; width: 356px; max-width: calc(100% - 24px); background: rgba(14, 19, 28, 0.94); border: 1px solid #38bdf8; border-radius: 10px; padding: 12px 14px; color: #f8fafc; backdrop-filter: blur(12px); box-shadow: 0 12px 36px rgba(0,0,0,0.65); font-size: 11px;">
      </div>

      <!-- 180° Pipe Internal Flow Cutaway Mini-Inspector Overlay (from LNG pipe_3d_viewer.py) -->
      <div id="pipe-section-overlay" style="display: none; position: absolute; bottom: 64px; left: 16px; z-index: 25; width: 490px; max-width: calc(100% - 32px); background: rgba(14, 19, 28, 0.94); border: 1px solid #fbbf24; border-radius: 10px; padding: 12px 14px; color: #f8fafc; backdrop-filter: blur(10px); box-shadow: 0 12px 32px rgba(0,0,0,0.6);">
        <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(255,255,255,0.12); padding-bottom: 6px; margin-bottom: 8px;">
          <span style="font-size: 12px; font-weight: 700; color: #fbbf24;">🔬 180° Ana Header &amp; Sınır Kesit Analizi (ASME B36.10M / API 5L)</span>
          <button id="btn-close-pipe-section" aria-label="180 derece boru kesit analizini kapat" style="background: none; border: none; color: #94a3b8; cursor: pointer; font-size: 14px;">✕</button>
        </div>
        <div style="font-size: 11px; line-height: 1.5; color: #cbd5e1;">
          <div style="display: flex; justify-content: space-between; margin: 2px 0;"><span>Station Suction Header (L-102/105):</span><b style="color:#facc15;">${suctLine.nominal_size_in || '10"'} • PIG-R Çıkışı ➔ TC Emiş Header Sonu</b></div>
          <div style="display: flex; justify-content: space-between; margin: 2px 0;"><span>Station Discharge Header (L-109):</span><b style="color:#fb923c;">${dischLine.nominal_size_in || '10"'} • TC Basma Header ➔ PIG-L Girişi</b></div>
          <div style="display: flex; justify-content: space-between; margin: 2px 0;"><span>MFS / CFS Ekipman Branşmanları:</span><b style="color:#fff;">${pLines.cyclone_branch?.nominal_size_in || '8"'} / ${pLines.filter_branch?.nominal_size_in || '8"'} (➔ Station Suction Header)</b></div>
          <div style="display: flex; justify-content: space-between; margin: 2px 0;"><span>TC Ünite Emiş / Basma Branşmanı:</span><b style="color:#fff;">${compSuctionBranchLine.nominal_size_in || '10"'} / ${compDischargeBranchLine.nominal_size_in || '6"'} (${compDischargeBranchLine.flow_kgs || 12} kg/s)</b></div>
          <div style="display: flex; justify-content: space-between; margin: 2px 0;"><span>Anti-Surge (ASV) / Recycle Header:</span><b style="color:#fff;">${antiSurgeLine.nominal_size_in || '5"'} / ${pLines.station_recycle?.nominal_size_in || '6"'} ➔ Suction Header</b></div>
          <div style="display: flex; justify-content: space-between; margin: 2px 0;"><span>Gaz Soğutucu Giriş / Çıkış / TCV:</span><b style="color:#fff;">${coolerInletLine.nominal_size_in || '6"'} / ${coolerOutletLine.nominal_size_in || '6"'} / ${coolerBypassLine.nominal_size_in || '3 1/2"'} (➔ Discharge Header)</b></div>
          <div style="display: flex; justify-content: space-between; margin: 2px 0;"><span>Boru Malzemesi / Et Kalınlığı:</span><b style="color:#38bdf8;">${suctLine.pipe_material || 'API 5L X70'} • t = ${suctLine.wall_thickness_mm || 9.5} mm (t_req: ${suctLine.min_required_thickness_mm || 6.4} mm)</b></div>
          <div style="display: flex; justify-content: space-between; margin: 2px 0;"><span>Ana Header Gaz Hızı &amp; EVR:</span><b style="color:#34d399;">${suctLine.actual_velocity_ms || 14.8} m/s (%${suctLine.erosion_ratio_pct || 72.0} EVR &lt; %100)</b></div>
          <div style="margin-top: 6px; padding: 5px 8px; background: rgba(16,185,129,0.15); border: 1px solid #10b981; border-radius: 6px; color: #34d399; font-weight: 600; text-align: center;">
            ✓ ANA HEADER EŞİTLİĞİ (${suctLine.nominal_size_in || '10"'}) &amp; SINIR TANIMLARI DOĞRULANDI
          </div>
        </div>
      </div>

      <!-- Bottom-Center LNG-Style Camera Preset Bar -->
      <div class="hud-presets" style="position: absolute; bottom: 12px; left: 50%; transform: translateX(-50%); z-index: 20; background: rgba(14, 19, 28, 0.92); border: 1px solid rgba(255,255,255,0.16); border-radius: 24px; padding: 6px 12px; display: flex; gap: 6px; flex-wrap: wrap; justify-content: center; backdrop-filter: blur(8px); box-shadow: 0 6px 20px rgba(0,0,0,0.45); width: max-content; max-width: 96%;">
        <button class="cam-preset-btn" data-cam="iso" style="background: #1f6feb; color: #fff; border: 1px solid #58a6ff; border-radius: 14px; padding: 4px 10px; font-size: 11px; font-weight: 600; cursor: pointer;">
          🌐 Genel Saha (CAD İzometrik)
        </button>
        <button class="cam-preset-btn" data-cam="top" style="background: #21262d; color: #c9d1d9; border: 1px solid rgba(255,255,255,0.12); border-radius: 14px; padding: 4px 10px; font-size: 11px; font-weight: 600; cursor: pointer;">
          🛰️ Vaziyet Planı (Üst Bakış)
        </button>
        <button class="cam-preset-btn" data-cam="compCutaway" style="background: #21262d; color: #c9d1d9; border: 1px solid rgba(255,255,255,0.12); border-radius: 14px; padding: 4px 10px; font-size: 11px; font-weight: 600; cursor: pointer;">
          🏗️ ${cutawayUnitLabel} (İç Kesit & Vanalar)
        </button>
        <button class="cam-preset-btn" data-cam="manifold" style="background: #21262d; color: #c9d1d9; border: 1px solid rgba(255,255,255,0.12); border-radius: 14px; padding: 4px 10px; font-size: 11px; font-weight: 600; cursor: pointer;">
          🔀 Kolektör & U-Genleşme Döngüleri
        </button>
        <button class="cam-preset-btn" data-cam="filtration" style="background: #21262d; color: #c9d1d9; border: 1px solid rgba(255,255,255,0.12); border-radius: 14px; padding: 4px 10px; font-size: 11px; font-weight: 600; cursor: pointer;">
          🧹 MFS & CFS Filtre Sahası
        </button>
        <button class="cam-preset-btn" data-cam="cooler" style="background: #21262d; color: #c9d1d9; border: 1px solid rgba(255,255,255,0.12); border-radius: 14px; padding: 4px 10px; font-size: 11px; font-weight: 600; cursor: pointer;">
          ❄️ Gas Cooler & By-Pass
        </button>
        <button class="cam-preset-btn" data-cam="tiein" style="background: #21262d; color: #c9d1d9; border: 1px solid rgba(255,255,255,0.12); border-radius: 14px; padding: 4px 10px; font-size: 11px; font-weight: 600; cursor: pointer;">
          🐷 Ana Hat & Pig Kovanları
        </button>
        <button class="cam-preset-btn" data-cam="control" style="background: #21262d; color: #c9d1d9; border: 1px solid rgba(255,255,255,0.12); border-radius: 14px; padding: 4px 10px; font-size: 11px; font-weight: 600; cursor: pointer;">
          🏢 Kontrol & Yardımcı Binalar
        </button>
      </div>

    </div>
  `;

  const rootEl = container.querySelector("#station-3d-root");
  const canvasMount = container.querySelector("#three-canvas-mount");
  const width = canvasMount.clientWidth || 1100;
  const height = canvasMount.clientHeight || 640;

  // ══════════════════ 1. SCENE, CAMERA & RENDERER SETUP ══════════════════
  const scene = new THREE.Scene();
  const cadSkyColor = new THREE.Color(0x7ca2de);
  const nightSkyColor = new THREE.Color(0x090d16);
  scene.background = cadSkyColor.clone();
  scene.fog = new THREE.FogExp2(0x7ca2de, 0.0012);

  const camera = new THREE.PerspectiveCamera(42, width / height, 0.5, 2500);
  if (savedState?.camPos) {
    camera.position.set(savedState.camPos.x, savedState.camPos.y, savedState.camPos.z);
  } else {
    camera.position.set(-145, 95, -155);
  }

  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
  renderer.setSize(width, height);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  if (THREE.ACESFilmicToneMapping) {
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.05;
  }
  renderer.domElement.style.display = "block"; // satır içi boşluk/kaydırma çubuğu önlenir
  renderer.domElement.style.touchAction = "none"; // dokunmatik döndürme/yakınlaştırma sayfayı kaydırmasın
  canvasMount.appendChild(renderer.domElement);

  let controls = null;
  if (THREE.OrbitControls) {
    controls = new THREE.OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.06;
    controls.maxPolarAngle = Math.PI / 2 - 0.015;
    controls.minDistance = 8;
    controls.maxDistance = 650;
    if (savedState?.camTarget) {
      controls.target.set(savedState.camTarget.x, savedState.camTarget.y, savedState.camTarget.z);
    } else {
      controls.target.set(-10, 8, 5);
    }
    controls.update();
  }

  // Smooth Camera Fly-To state
  const targetCamPos = new THREE.Vector3();
  const targetLookAt = new THREE.Vector3();
  let isCameraTransitioning = false;

  function flyToCamera(posVec, lookVec, activeBtn = null) {
    targetCamPos.copy(posVec);
    targetLookAt.copy(lookVec);
    isCameraTransitioning = true;
    if (activeBtn) {
      container.querySelectorAll(".cam-preset-btn").forEach((b) => {
        b.style.background = "#21262d";
        b.style.color = "#c9d1d9";
        b.style.borderColor = "rgba(255,255,255,0.12)";
      });
      activeBtn.style.background = "#1f6feb";
      activeBtn.style.color = "#ffffff";
      activeBtn.style.borderColor = "#58a6ff";
    }
  }

  // ══════════════════ 2. LIGHTING ══════════════════
  const ambientLight = new THREE.AmbientLight(0xeef4ff, 0.78);
  scene.add(ambientLight);

  const sunLight = new THREE.DirectionalLight(0xfffbeb, 1.15);
  sunLight.position.set(-130, 210, -140);
  sunLight.castShadow = true;
  sunLight.shadow.mapSize.width = 2048;
  sunLight.shadow.mapSize.height = 2048;
  sunLight.shadow.camera.near = 15;
  sunLight.shadow.camera.far = 700;
  const shadowSpan = 230;
  sunLight.shadow.camera.left = -shadowSpan;
  sunLight.shadow.camera.right = shadowSpan;
  sunLight.shadow.camera.top = shadowSpan;
  sunLight.shadow.camera.bottom = -shadowSpan;
  scene.add(sunLight);

  const fillLight = new THREE.DirectionalLight(0x93c5fd, 0.4);
  fillLight.position.set(160, 90, 140);
  scene.add(fillLight);

  // ══════════════════ 3. AUTHENTIC CAD PLANT 3D MATERIALS ══════════════════
  const matProcessGround = new THREE.MeshStandardMaterial({ color: 0xcbe0f9, roughness: 0.92, metalness: 0.02 });
  const matSouthConcrete = new THREE.MeshStandardMaterial({ color: 0xc4c8ce, roughness: 0.88, metalness: 0.05 });
  const matRoadAsphalt = new THREE.MeshStandardMaterial({ color: 0x2b2e34, roughness: 0.9, metalness: 0.05 });
  const matRoadCurb = new THREE.MeshStandardMaterial({ color: 0x94a3b8, roughness: 0.8 });
  const matWhitePaint = new THREE.MeshBasicMaterial({ color: 0xffffff });

  // Piping & Valves
  const matYellowPipe = new THREE.MeshStandardMaterial({ color: 0xe2d400, roughness: 0.32, metalness: 0.45 });
  const matBuriedPipe = new THREE.MeshStandardMaterial({ color: 0x5c3a21, roughness: 0.65, metalness: 0.25 });
  const matTealUtilityPipe = new THREE.MeshStandardMaterial({ color: 0x00b4d8, roughness: 0.35, metalness: 0.5 });
  const matCyanArrow = new THREE.MeshBasicMaterial({ color: 0x00f5ff });
  const matFlangeSteel = new THREE.MeshStandardMaterial({ color: 0xd4c800, roughness: 0.28, metalness: 0.65 });
  const matValveBody = new THREE.MeshStandardMaterial({ color: 0xdfd000, roughness: 0.35, metalness: 0.5 });
  const matHandwheel = new THREE.MeshStandardMaterial({ color: 0xfacc15, roughness: 0.3, metalness: 0.4 });
  const matActuator = new THREE.MeshStandardMaterial({ color: 0x64748b, roughness: 0.4, metalness: 0.7 });
  const matRedFire = new THREE.MeshStandardMaterial({ color: 0xd91414, roughness: 0.35, metalness: 0.4 });

  // Structural & Buildings
  const matCadBlueSteel = new THREE.MeshStandardMaterial({ color: 0x0077be, roughness: 0.38, metalness: 0.65 });
  const matOliveSteel = new THREE.MeshStandardMaterial({ color: 0x706535, roughness: 0.55, metalness: 0.45 });
  const matPurlinBrown = new THREE.MeshStandardMaterial({ color: 0x7a6855, roughness: 0.6, metalness: 0.35 });
  const matBuildingWall = new THREE.MeshStandardMaterial({ color: 0x8c735b, roughness: 0.72, metalness: 0.15 });
  const matBuildingRoof = new THREE.MeshStandardMaterial({ color: 0x786049, roughness: 0.75, metalness: 0.18 });
  const matSkidEnclosure = new THREE.MeshStandardMaterial({ color: 0x937666, roughness: 0.55, metalness: 0.3 });
  const matCableTrench = new THREE.MeshStandardMaterial({ color: 0x3d2b35, roughness: 0.75, metalness: 0.2 });
  const matConcretePlinth = new THREE.MeshStandardMaterial({ color: 0x78716c, roughness: 0.85 });
  const matVesselGrey = new THREE.MeshStandardMaterial({ color: 0x78756e, roughness: 0.42, metalness: 0.6 });
  const matSilverVessel = new THREE.MeshStandardMaterial({ color: 0xb8c0c8, roughness: 0.38, metalness: 0.72 });
  const matFanBlade = new THREE.MeshStandardMaterial({ color: 0x9aa4ae, roughness: 0.5, metalness: 0.55 });
  const matFinTube = new THREE.MeshStandardMaterial({ color: 0x2f7f6f, roughness: 0.5, metalness: 0.5 });
  const matInternalMesh = new THREE.MeshStandardMaterial({ color: 0x5d8f99, roughness: 0.6, metalness: 0.35, side: THREE.DoubleSide });
  const matFenceWire = new THREE.MeshBasicMaterial({ color: 0x334155, wireframe: true, transparent: true, opacity: 0.55 });
  const matFencePost = new THREE.MeshStandardMaterial({ color: 0x475569, roughness: 0.5, metalness: 0.7 });

  const matEnvelopeBox = new THREE.MeshStandardMaterial({
    color: 0x94a3b8,
    roughness: 0.3,
    metalness: 0.1,
    transparent: true,
    opacity: 0.28,
    depthWrite: false,
    side: THREE.DoubleSide,
  });

  // Collections for animation & interactivity
  const interactiveObjects = [];
  const envelopeMeshes = [];
  const pipeLabelMeshes = [];
  const pipeRouteGroupsByLineKey = new Map();
  const flowArrowMeshes = [];
  const flowParticleMeshes = [];
  const spinningFans = [];
  const compressorBuildingRefs = []; // Stores { exteriorGroup, cutawayGroup, index }
  const pipeRoutes = []; // Debug/audit registry of all procedural pipe routes

  function registerClickable(object3d, equipKey) {
    object3d.traverse((child) => {
      if (child.isMesh) {
        child.userData.equipKey = equipKey;
        interactiveObjects.push(child);
      }
    });
  }

  function registerPipeClickable(object3d, pipeMeta, equipKey = null) {
    object3d.userData.pipeMeta = pipeMeta;
    if (equipKey) object3d.userData.equipKey = equipKey;
    object3d.traverse((child) => {
      if (child.isMesh || child.isSprite) {
        child.userData.isPipeMesh = true;
        child.userData.pipeMeta = pipeMeta;
        if (equipKey) child.userData.equipKey = equipKey;
        interactiveObjects.push(child);
      }
    });
  }

  // ══════════════════ 4. PROCEDURAL GEOMETRY HELPERS (LNG + CAD STYLE) ══════════════════

  /**
   * Builds a smooth 3D rounded path with long-radius elbows (QuadraticBezierCurve3)
   * exactly like LNG terminal_3d_viewer.py buildRoundedPath().
   */
  function buildRoundedPath(points, bendRadius = 1.6) {
    const path = new THREE.CurvePath();
    if (points.length < 2) return path;
    let segStart = points[0].clone();

    for (let i = 1; i < points.length - 1; i++) {
      const prev = points[i - 1];
      const curr = points[i];
      const next = points[i + 1];
      const vIn = new THREE.Vector3().subVectors(curr, prev);
      const vOut = new THREE.Vector3().subVectors(next, curr);
      const lenIn = vIn.length();
      const lenOut = vOut.length();
      if (lenIn < 1e-4 || lenOut < 1e-4) continue;

      const dIn = vIn.clone().normalize();
      const dOut = vOut.clone().normalize();
      const dot = Math.max(-1, Math.min(1, dIn.dot(dOut)));
      const angle = Math.acos(dot);

      if (angle < 0.05) {
        path.add(new THREE.LineCurve3(segStart, curr.clone()));
        segStart = curr.clone();
        continue;
      }

      const trim = Math.min(bendRadius * Math.tan(angle / 2), lenIn * 0.42, lenOut * 0.42);
      const bendStart = curr.clone().addScaledVector(dIn, -trim);
      const bendEnd = curr.clone().addScaledVector(dOut, trim);

      if (segStart.distanceTo(bendStart) > 1e-3) {
        path.add(new THREE.LineCurve3(segStart, bendStart));
      }
      path.add(new THREE.QuadraticBezierCurve3(bendStart, curr.clone(), bendEnd));
      segStart = bendEnd;
    }

    const lastPt = points[points.length - 1].clone();
    if (segStart.distanceTo(lastPt) > 1e-3) {
      path.add(new THREE.LineCurve3(segStart, lastPt));
    }
    return path;
  }

  /**
   * Creates a continuous 3D pipe with optional cyan directional flow chevrons (→)
   * and weld-neck flange rings at intervals.
   */
  function createCadPipeRoute(points, radius = 0.6, mat = matYellowPipe, opts = {}) {
    const {
      bendRadius = Math.max(1.2, radius * 2.5),
      tubularSegments = 64,
      flowArrows = 0,
      reverseFlow = false,
      flangeEnds = true,
      equipKey = null,
      lineKey = null,
      segmentTitle = null,
      fromBoundary = null,
      toBoundary = null,
      unitLabel = null,
      registerParticlePath = false,
      capEnds = true,
    } = opts;

    const group = new THREE.Group();
    const curvePath = buildRoundedPath(points, bendRadius);
    const tubeGeo = new THREE.TubeGeometry(curvePath, tubularSegments, radius, 16, false);
    const tubeMesh = new THREE.Mesh(tubeGeo, mat);
    tubeMesh.castShadow = true;
    tubeMesh.receiveShadow = true;
    group.add(tubeMesh);

    // Weld-like spherical caps close the open TubeGeometry ends. Without these,
    // the tube ends are open circles and can show visible holes at junctions
    // and at route terminations (surface-integrity issue).
    if (capEnds) {
      [0.0, 1.0].forEach((t) => {
        const pt = curvePath.getPoint(t);
        const cap = new THREE.Mesh(
          new THREE.SphereGeometry(radius * 1.02, 12, 8),
          mat
        );
        cap.position.copy(pt);
        cap.castShadow = true;
        group.add(cap);
      });
    }

    // Optional weld-neck flanges at ends
    if (flangeEnds && points.length >= 2) {
      [0.02, 0.98].forEach((t) => {
        const pt = curvePath.getPoint(t);
        const tan = curvePath.getTangent(t).normalize();
        const flg = new THREE.Mesh(
          new THREE.CylinderGeometry(radius * 1.38, radius * 1.38, radius * 0.35, 16),
          matFlangeSteel
        );
        flg.position.copy(pt);
        flg.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), tan);
        group.add(flg);
      });
    }

    // Cyan 3D Flow Arrows mounted along the pipe surface (matching CAD screenshots)
    if (flowArrows > 0) {
      for (let i = 1; i <= flowArrows; i++) {
        const t = i / (flowArrows + 1);
        const pt = curvePath.getPoint(t);
        const tan = curvePath.getTangent(t).normalize();
        if (reverseFlow) tan.negate();

        const arrowGrp = new THREE.Group();
        const shaft = new THREE.Mesh(new THREE.CylinderGeometry(radius * 0.18, radius * 0.18, radius * 1.8, 8), matCyanArrow);
        shaft.position.y = -radius * 0.3;
        const head = new THREE.Mesh(new THREE.ConeGeometry(radius * 0.42, radius * 1.1, 10), matCyanArrow);
        head.position.y = radius * 0.8;
        arrowGrp.add(shaft, head);

        arrowGrp.position.copy(pt).add(new THREE.Vector3(0, radius * 1.12, 0));
        arrowGrp.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), tan);
        group.add(arrowGrp);
        flowArrowMeshes.push(arrowGrp);
      }
    }

    // Animated Flow Particles along the pipe
    if (registerParticlePath) {
      const pCount = Math.max(2, flowArrows);
      for (let k = 0; k < pCount; k++) {
        const sphere = new THREE.Mesh(
          new THREE.SphereGeometry(radius * 0.45, 8, 8),
          matCyanArrow
        );
        const flowVelocityFactor = Math.min(2.5, Math.max(0.4, (sm.total_mass_flow_kgs || 100) / 75));
        sphere.userData = {
          curve: curvePath,
          t: k / pCount,
          speed: (0.08 + Math.random() * 0.03) * flowVelocityFactor * (reverseFlow ? -1 : 1),
          offsetY: radius * 1.12,
        };
        scene.add(sphere);
        flowParticleMeshes.push(sphere);
      }
    }

    const lineData = lineKey ? (pLines[lineKey] || {}) : {};
    const resolvedPipeMeta = lineKey ? {
      lineKey,
      lineTag: lineData.tag || lineKey.toUpperCase(),
      lineName: segmentTitle || lineData.name || lineKey,
      hierarchyLevel: lineData.hierarchy_level || "equipment_branch",
      hierarchyLabel: lineData.hierarchy_label || "Proses Borulaması",
      parentHeader: lineData.parent_header || null,
      fromBoundary: fromBoundary || lineData.from_boundary || "-",
      toBoundary: toBoundary || lineData.to_boundary || "-",
      boundarySummary: lineData.boundary_summary || `${fromBoundary || "-"} ➔ ${toBoundary || "-"}`,
      unitLabel: unitLabel || null,
      equipKey: equipKey || null,
    } : null;

    if (resolvedPipeMeta) {
      registerPipeClickable(group, resolvedPipeMeta, equipKey);
      if (!pipeRouteGroupsByLineKey.has(lineKey)) {
        pipeRouteGroupsByLineKey.set(lineKey, []);
      }
      pipeRouteGroupsByLineKey.get(lineKey).push(group);
    } else if (equipKey) {
      registerClickable(group, equipKey);
    }

    scene.add(group);
    pipeRoutes.push({
      equipKey,
      lineKey: resolvedPipeMeta?.lineKey || null,
      lineTag: resolvedPipeMeta?.lineTag || null,
      lineName: resolvedPipeMeta?.lineName || null,
      hierarchyLevel: resolvedPipeMeta?.hierarchyLevel || null,
      parentHeader: resolvedPipeMeta?.parentHeader || null,
      fromBoundary: resolvedPipeMeta?.fromBoundary || null,
      toBoundary: resolvedPipeMeta?.toBoundary || null,
      radius,
      points: points.map((p) => [p.x, p.y, p.z]),
      first: [points[0].x, points[0].y, points[0].z],
      last: [points[points.length - 1].x, points[points.length - 1].y, points[points.length - 1].z],
    });
    return group;
  }

  /**
   * Builds a complete industrial Flanged Ball/Plug Valve Assembly with:
   * - Bolted inlet/outlet weld-neck flanges
   * - Spherical/box valve body
   * - Vertical stem + gearbox + yellow manual handwheel (Torus) + top actuator cylinder
   * - Optional elevated steel operator grating platform with handrails & ladder
   */
  function createValveStation(x, y, z, radius = 0.65, opts = {}) {
    const {
      rotationY = 0,
      hasActuator = true,
      hasPlatform = false,
      equipKey = null,
      valveColorMat = matValveBody,
    } = opts;

    const grp = new THREE.Group();
    grp.position.set(x, y, z);
    grp.rotation.y = rotationY;

    // Left & Right Weld-Neck Flanges (bolted flanged connections)
    [-radius * 1.5, radius * 1.5].forEach((dx, flangeIdx) => {
      const flg = new THREE.Mesh(
        new THREE.CylinderGeometry(radius * 1.45, radius * 1.45, radius * 0.35, 18),
        matFlangeSteel
      );
      flg.rotation.z = Math.PI / 2;
      flg.position.x = dx;
      grp.add(flg);

      const faceX = dx + (flangeIdx === 0 ? -radius * 0.20 : radius * 0.20);
      const raisedFace = new THREE.Mesh(
        new THREE.CylinderGeometry(radius * 1.06, radius * 1.06, radius * 0.10, 18),
        matFlangeSteel
      );
      raisedFace.rotation.z = Math.PI / 2;
      raisedFace.position.x = faceX;
      grp.add(raisedFace);

      // Six bolts on the flange face make the flanged connection readable.
      for (let boltIdx = 0; boltIdx < 6; boltIdx++) {
        const angle = (boltIdx * Math.PI * 2) / 6;
        const bolt = new THREE.Mesh(
          new THREE.CylinderGeometry(radius * 0.085, radius * 0.085, radius * 0.34, 8),
          matActuator
        );
        bolt.rotation.z = Math.PI / 2;
        bolt.position.set(
          faceX,
          Math.cos(angle) * radius * 1.15,
          Math.sin(angle) * radius * 1.15
        );
        grp.add(bolt);
      }
    });
    grp.userData.nominalPipeRadius = radius;

    // Spherical Valve Body
    const body = new THREE.Mesh(new THREE.SphereGeometry(radius * 1.35, 16, 16), valveColorMat);
    body.castShadow = true;
    grp.add(body);

    // Bonnet & Stem
    const bonnet = new THREE.Mesh(new THREE.CylinderGeometry(radius * 0.45, radius * 0.55, radius * 1.8, 12), matValveBody);
    bonnet.position.y = radius * 1.5;
    grp.add(bonnet);

    // Yellow Manual Handwheel (Side-mounted Torus + Spokes)
    const wheelRadius = Math.max(0.55, radius * 0.95);
    const handwheel = new THREE.Mesh(new THREE.TorusGeometry(wheelRadius, 0.08, 8, 18), matHandwheel);
    handwheel.position.set(0, radius * 2.1, radius * 0.95);
    grp.add(handwheel);
    const spoke1 = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.05, wheelRadius * 1.9, 6), matHandwheel);
    spoke1.position.copy(handwheel.position);
    const spoke2 = spoke1.clone();
    spoke2.rotation.z = Math.PI / 2;
    grp.add(spoke1, spoke2);

    // Gas-over-Oil / Pneumatic Actuator Cylinder on top
    if (hasActuator) {
      const act = new THREE.Mesh(new THREE.CylinderGeometry(radius * 0.65, radius * 0.65, radius * 1.7, 14), matActuator);
      act.position.y = radius * 2.9;
      grp.add(act);
    }

    // Steel Operator Access Platform around Valve (as seen in CAD screenshots)
    if (hasPlatform) {
      const platGrp = new THREE.Group();
      const deckY = -radius * 0.6;
      const pW = radius * 5.2;
      const pD = radius * 4.6;
      const deck = new THREE.Mesh(new THREE.BoxGeometry(pW, 0.16, pD), matOliveSteel);
      deck.position.set(0, deckY, 0);
      platGrp.add(deck);

      // 4 Support Legs to ground
      const legH = Math.max(0.5, y + deckY);
      [
        [-pW / 2 + 0.15, -pD / 2 + 0.15],
        [pW / 2 - 0.15, -pD / 2 + 0.15],
        [-pW / 2 + 0.15, pD / 2 - 0.15],
        [pW / 2 - 0.15, pD / 2 - 0.15],
      ].forEach(([lx, lz]) => {
        const leg = new THREE.Mesh(new THREE.BoxGeometry(0.16, legH, 0.16), matOliveSteel);
        leg.position.set(lx, deckY - legH / 2, lz);
        platGrp.add(leg);
      });

      // Perimeter Handrail Wireframe
      const railGeo = new THREE.BoxGeometry(pW, 1.05, pD);
      const railEdges = new THREE.EdgesGeometry(railGeo);
      const railSegments = new THREE.LineSegments(railEdges, new THREE.LineBasicMaterial({ color: 0xcab300 }));
      railSegments.position.set(0, deckY + 0.55, 0);
      platGrp.add(railSegments);

      grp.add(platGrp);
    }

    if (equipKey) registerClickable(grp, equipKey);
    scene.add(grp);
    return grp;
  }

  /**
   * Creates flat 3D CAD Green Text Plaques (matching the extruded green text in Plant 3D / Navisworks:
   * "GAS COOLER", "MFS", "CFS", "COMPRESSOR-01..05", "7.0 M. WIDE ROAD", "AUXILIARY & CONTROL BUILDING").
   */
  function createCadGreenLabel(text, x, y, z, width = 18, height = 3.2, rotX = -Math.PI / 2, rotY = 0, rotZ = 0) {
    const canvas = document.createElement("canvas");
    canvas.width = 1024;
    canvas.height = 192;
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Subtle dark drop shadow for crisp readability from all angles
    ctx.font = "900 76px 'Segoe UI', Arial, sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.lineWidth = 10;
    ctx.strokeStyle = "rgba(0, 35, 20, 0.85)";
    ctx.strokeText(text, canvas.width / 2, canvas.height / 2);

    ctx.fillStyle = "#00d67f";
    ctx.fillText(text, canvas.width / 2, canvas.height / 2);

    const tex = new THREE.CanvasTexture(canvas);
    tex.anisotropy = 4;
    const mat = new THREE.MeshBasicMaterial({
      map: tex,
      transparent: true,
      side: THREE.DoubleSide,
      depthWrite: false,
    });
    const mesh = new THREE.Mesh(new THREE.PlaneGeometry(width, height), mat);
    mesh.position.set(x, y, z);
    mesh.rotation.set(rotX, rotY, rotZ);
    scene.add(mesh);
    return mesh;
  }

  /**
   * Creates an elevated 3D CAD Piping & Battery-Limit Callout Plaque with a vertical
   * leader pin down to the pipe centerline. Supports toggling via #btn-toggle-pipe-labels
   * and direct raycast click inspection of the referenced process line.
   */
  function createCadPipeCallout(titleText, subText, x, y, z, opts = {}) {
    const {
      width = 23,
      height = 4.6,
      pipeY = 1.6,
      accentColor = "#38bdf8",
      lineKey = null,
      equipKey = null,
      fromBoundary = null,
      toBoundary = null,
    } = opts;

    const calloutGrp = new THREE.Group();

    const canvas = document.createElement("canvas");
    canvas.width = 1024;
    canvas.height = 224;
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Dark CAD HUD callout plate with crisp colored accent border
    ctx.fillStyle = "rgba(9, 16, 30, 0.90)";
    ctx.strokeStyle = accentColor;
    ctx.lineWidth = 8;
    ctx.beginPath();
    ctx.roundRect(10, 10, canvas.width - 20, canvas.height - 20, 24);
    ctx.fill();
    ctx.stroke();

    // Left vertical category bar
    ctx.fillStyle = accentColor;
    ctx.fillRect(24, 28, 14, canvas.height - 56);

    // Primary line tag + name
    ctx.font = "800 42px 'Segoe UI', Arial, sans-serif";
    ctx.textAlign = "left";
    ctx.textBaseline = "middle";
    ctx.fillStyle = "#f8fafc";
    ctx.fillText(String(titleText || ""), 58, 78, canvas.width - 84);

    // Secondary boundary description
    ctx.font = "600 31px 'Segoe UI', Arial, sans-serif";
    ctx.fillStyle = "#cbd5e1";
    ctx.fillText(String(subText || ""), 58, 150, canvas.width - 84);

    const tex = new THREE.CanvasTexture(canvas);
    tex.anisotropy = 4;
    const plaqueMat = new THREE.SpriteMaterial({
      map: tex,
      transparent: true,
      depthWrite: false,
    });
    const plaqueSprite = new THREE.Sprite(plaqueMat);
    plaqueSprite.position.set(x, y, z);
    plaqueSprite.scale.set(width, height, 1);
    calloutGrp.add(plaqueSprite);

    // Leader stem + anchor collar at pipe elevation
    const stemBottomY = Math.min(y - height * 0.45, pipeY);
    const stemH = Math.max(0.4, (y - height * 0.42) - stemBottomY);
    const stemMat = new THREE.MeshBasicMaterial({ color: new THREE.Color(accentColor) });
    const stem = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.06, stemH, 8), stemMat);
    stem.position.set(x, stemBottomY + stemH / 2, z);
    calloutGrp.add(stem);

    const anchorDot = new THREE.Mesh(new THREE.SphereGeometry(0.22, 10, 8), stemMat);
    anchorDot.position.set(x, stemBottomY, z);
    calloutGrp.add(anchorDot);

    if (lineKey) {
      const lineData = pLines[lineKey] || {};
      const pipeMeta = {
        lineKey,
        lineTag: lineData.tag || lineKey.toUpperCase(),
        lineName: lineData.name || titleText,
        hierarchyLevel: lineData.hierarchy_level || "equipment_branch",
        hierarchyLabel: lineData.hierarchy_label || "Proses Borulaması",
        parentHeader: lineData.parent_header || null,
        fromBoundary: fromBoundary || lineData.from_boundary || "-",
        toBoundary: toBoundary || lineData.to_boundary || "-",
        boundarySummary: lineData.boundary_summary || `${fromBoundary || "-"} ➔ ${toBoundary || "-"}`,
        equipKey: equipKey || null,
      };
      registerPipeClickable(calloutGrp, pipeMeta, equipKey);
    }

    calloutGrp.visible = showPipeLabels;
    pipeLabelMeshes.push(calloutGrp);
    scene.add(calloutGrp);
    return calloutGrp;
  }

  // ══════════════════ 5. SITE TERRAIN, ROADS & PERIMETER SECURITY FENCE ══════════════════

  // Main Process Gravel Pad with 2 buried-pipeline cutaway trench windows along the PIG-R / PIG-L axis (x = -196)
  const padShape = new THREE.Shape();
  padShape.moveTo(-210, -155);
  padShape.lineTo(210, -155);
  padShape.lineTo(210, 155);
  padShape.lineTo(-210, 155);
  padShape.closePath();

  const pigTrenchCorridors = [
    { xMin: -198.4, xMax: -193.6, zMin: -140, zMax: -103.5 }, // PIG-R buried 22.5° offset trench
    { xMin: -198.4, xMax: -193.6, zMin: -40.5, zMax: -8 },    // PIG-L buried 22.5° offset trench
  ];
  pigTrenchCorridors.forEach((tc) => {
    const hole = new THREE.Path();
    // Shape is rotated -PI/2 around X so shape.y maps to -world.z
    hole.moveTo(tc.xMin, -tc.zMax);
    hole.lineTo(tc.xMax, -tc.zMax);
    hole.lineTo(tc.xMax, -tc.zMin);
    hole.lineTo(tc.xMin, -tc.zMin);
    hole.closePath();
    padShape.holes.push(hole);
  });

  const mainPad = new THREE.Mesh(new THREE.ShapeGeometry(padShape), matProcessGround);
  mainPad.rotation.x = -Math.PI / 2;
  mainPad.receiveShadow = true;
  scene.add(mainPad);

  // Buried pipeline inspection trenches so the underground 22.5° hot-bend S-offset remains clearly visible
  const matTrenchWall = new THREE.MeshStandardMaterial({ color: 0x6b5344, roughness: 0.92, metalness: 0.05 });
  const matTrenchSoilCover = new THREE.MeshStandardMaterial({
    color: 0x7a5e48,
    roughness: 0.9,
    metalness: 0.04,
    transparent: true,
    opacity: 0.22,
    depthWrite: false,
  });
  pigTrenchCorridors.forEach((tc) => {
    const w = tc.xMax - tc.xMin;
    const len = tc.zMax - tc.zMin;
    const cx = (tc.xMin + tc.xMax) / 2;
    const cz = (tc.zMin + tc.zMax) / 2;
    const depth = 2.0;

    const floor = new THREE.Mesh(new THREE.BoxGeometry(w, 0.14, len), matTrenchWall);
    floor.position.set(cx, -depth, cz);
    floor.receiveShadow = true;
    scene.add(floor);

    [-w / 2, w / 2].forEach((ox) => {
      const sideWall = new THREE.Mesh(new THREE.BoxGeometry(0.16, depth, len), matTrenchWall);
      sideWall.position.set(cx + ox, -depth / 2, cz);
      scene.add(sideWall);
    });
    [-len / 2, len / 2].forEach((oz) => {
      const endWall = new THREE.Mesh(new THREE.BoxGeometry(w, depth, 0.16), matTrenchWall);
      endWall.position.set(cx, -depth / 2, cz + oz);
      scene.add(endWall);
    });

    const translucentSoil = new THREE.Mesh(new THREE.PlaneGeometry(w, len), matTrenchSoilCover);
    translucentSoil.rotation.x = -Math.PI / 2;
    translucentSoil.position.set(cx, -0.02, cz);
    scene.add(translucentSoil);
  });

  // Subtle CAD reference grid
  const cadGrid = new THREE.GridHelper(400, 40, 0x93b4db, 0xb5cfee);
  cadGrid.position.y = 0.03;
  scene.add(cadGrid);

  // South Auxiliary & Control Concrete Compound Apron (Light Grey Slab, Z: +53 to +124)
  const southApron = new THREE.Mesh(new THREE.BoxGeometry(265, 0.16, 70), matSouthConcrete);
  southApron.position.set(-12, 0.08, 88);
  southApron.receiveShadow = true;
  scene.add(southApron);

  // ── 7.0 M. WIDE ROAD Network (North Road, South Road, West/East Connectors, NE Waste Spur) ──
  function addRoadSegment(x1, z1, x2, z2, roadWidth = 7.0, arrowStep = 24) {
    const dx = x2 - x1;
    const dz = z2 - z1;
    const len = Math.hypot(dx, dz);
    const angle = Math.atan2(dx, dz);
    const cx = (x1 + x2) / 2;
    const cz = (z1 + z2) / 2;

    // Curb base
    const curb = new THREE.Mesh(new THREE.BoxGeometry(roadWidth + 0.8, 0.12, len + 0.8), matRoadCurb);
    curb.position.set(cx, 0.06, cz);
    curb.rotation.y = angle;
    curb.receiveShadow = true;
    scene.add(curb);

    // Asphalt surface
    const road = new THREE.Mesh(new THREE.BoxGeometry(roadWidth, 0.18, len), matRoadAsphalt);
    road.position.set(cx, 0.11, cz);
    road.rotation.y = angle;
    road.receiveShadow = true;
    scene.add(road);

    // White Directional Lane Arrows (→) & Edge Markers (□) as seen in Screenshot (4)
    const nArrows = Math.max(1, Math.floor((len - 12) / arrowStep));
    for (let i = 0; i < nArrows; i++) {
      const f = (i + 0.6) / nArrows;
      const ax = x1 + dx * f;
      const az = z1 + dz * f;

      const arrowShaft = new THREE.Mesh(new THREE.BoxGeometry(0.22, 0.02, 2.2), matWhitePaint);
      arrowShaft.position.set(ax, 0.21, az);
      arrowShaft.rotation.y = angle;
      scene.add(arrowShaft);

      // Edge curb white squares
      [-roadWidth / 2 + 0.35, roadWidth / 2 - 0.35].forEach((sideOffset) => {
        const mark = new THREE.Mesh(new THREE.BoxGeometry(0.45, 0.03, 0.45), matWhitePaint);
        mark.position.set(
          ax + Math.cos(angle) * sideOffset,
          0.21,
          az - Math.sin(angle) * sideOffset
        );
        mark.rotation.y = angle;
        scene.add(mark);
      });
    }
  }

  // North Horizontal Road (Z = -24)
  addRoadSegment(-152, -24, 122, -24, 7.0, 22);
  createCadGreenLabel("7.0 M. WIDE ROAD", -72, 0.26, -24, 24, 2.8, -Math.PI / 2, 0, 0);

  // South Horizontal Road (Z = +48)
  addRoadSegment(-152, 48, 128, 48, 7.0, 22);
  createCadGreenLabel("7.0 M. WIDE ROAD", 28, 0.26, 48, 24, 2.8, -Math.PI / 2, 0, 0);

  // East & West Loop Connector Roads + South-East Entrance Road + NE Waste Storage Spur
  addRoadSegment(122, -24, 122, 48, 7.0, 20);
  addRoadSegment(-152, -24, -152, 48, 7.0, 20);
  addRoadSegment(62, -24, 62, -92, 6.5, 20); // Spur to Temporary Waste Storage Area
  addRoadSegment(125, 48, 142, 125, 7.0, 22); // SE Main Gate Entrance Road

  // West access spur to the relocated pig trap / battery-limit yard.
  addRoadSegment(-152, -24, -208, -24, 6.5, 20);
  addRoadSegment(-208, -24, -208, -96, 6.5, 20);
  addRoadSegment(-208, -96, -176, -96, 6.5, 18);

  // ── Perimeter Double Security Wire Fence (Proses Tel Çiti) & Patrol Road ──
  const fenceBoundaryPoints = [
    // Extended west boundary to accommodate the relocated pig trap yard.
    new THREE.Vector3(-232, 0, -124),
    new THREE.Vector3(78, 0, -124),
    new THREE.Vector3(178, 0, 38), // Angled NE pipeline boundary matching screenshots (0), (1), (2)
    new THREE.Vector3(178, 0, 128),
    new THREE.Vector3(-232, 0, 128),
    new THREE.Vector3(-232, 0, -124),
  ];

  function buildPerimeterSecurityFence(pts) {
    const fenceGroup = new THREE.Group();
    const fenceH = 2.8;

    for (let i = 0; i < pts.length - 1; i++) {
      const p1 = pts[i];
      const p2 = pts[i + 1];
      const dx = p2.x - p1.x;
      const dz = p2.z - p1.z;
      const segLen = Math.hypot(dx, dz);
      const angle = Math.atan2(dx, dz);
      const cx = (p1.x + p2.x) / 2;
      const cz = (p1.z + p2.z) / 2;

      // Perimeter security patrol track between double fence
      const track = new THREE.Mesh(new THREE.BoxGeometry(3.2, 0.08, segLen), matRoadAsphalt);
      track.position.set(cx, 0.04, cz);
      track.rotation.y = angle;
      fenceGroup.add(track);

      // Inner & Outer wire mesh panels (-1.3m and +1.3m offset)
      [-1.3, 1.3].forEach((offset) => {
        const nx = Math.cos(angle) * offset;
        const nz = -Math.sin(angle) * offset;
        const panel = new THREE.Mesh(
          new THREE.PlaneGeometry(segLen, fenceH, Math.max(4, Math.floor(segLen / 4)), 3),
          matFenceWire
        );
        panel.position.set(cx + nx, fenceH / 2, cz + nz);
        panel.rotation.y = angle + Math.PI / 2;
        fenceGroup.add(panel);

        // Fence posts every 6m with barbed-wire top rail
        const nPosts = Math.floor(segLen / 6);
        for (let k = 0; k <= nPosts; k++) {
          const f = k / Math.max(1, nPosts);
          const px = p1.x + dx * f + nx;
          const pz = p1.z + dz * f + nz;
          const post = new THREE.Mesh(new THREE.CylinderGeometry(0.08, 0.08, fenceH + 0.5, 6), matFencePost);
          post.position.set(px, (fenceH + 0.5) / 2, pz);
          fenceGroup.add(post);
        }
      });
    }
    scene.add(fenceGroup);
  }
  buildPerimeterSecurityFence(fenceBoundaryPoints);

  // ══════════════════ 6. NORTH-WEST MAINLINE TIE-IN & PIG TRAPS YARD ══════════════════

  // Buried Mainline Natural Gas Pipelines (Dark Brown #5c3a21):
  // Exit PIG-R (-Z) and PIG-L (+Z) strictly along the pig-trap Z-axis (x = -196)
  // with a double 22.5° induction hot-bend S-offset (no 90° elbows):
  //   1st 22.5° hot bend pitches down from trap centerline (y = 2.2 m) into soil,
  //   2nd 22.5° hot bend returns horizontal at buried cover depth (y = -1.2 m).
  const PIG_HOT_BEND_ANGLE_RAD = Math.PI / 8; // 22.5°
  const PIG_HOT_BEND_SLOPE_TAN = Math.tan(PIG_HOT_BEND_ANGLE_RAD);

  function buildPigTrapAxialHotBendPoints({
    axisX = -196,
    topY = 2.2,
    buriedY = -1.2,
    startZ,
    approachLen = 2.5,
    tailLen = 30.0,
    directionZ = -1,
  }) {
    const deltaY = Math.abs(topY - buriedY);
    const horizOffsetZ = deltaY / PIG_HOT_BEND_SLOPE_TAN;
    const bend1Z = startZ + directionZ * approachLen;
    const bend2Z = bend1Z + directionZ * horizOffsetZ;
    const endZ = bend2Z + directionZ * tailLen;
    const soilEntryZ = bend1Z + directionZ * (topY / PIG_HOT_BEND_SLOPE_TAN);
    return {
      points: [
        new THREE.Vector3(axisX, topY, startZ),
        new THREE.Vector3(axisX, topY, bend1Z),
        new THREE.Vector3(axisX, buriedY, bend2Z),
        new THREE.Vector3(axisX, buriedY, endZ),
      ],
      bend1Z,
      bend2Z,
      soilEntryZ,
      endZ,
    };
  }

  function buildSoilTransitionCollar(x, z, pipeRadius) {
    const collar = new THREE.Mesh(
      new THREE.CylinderGeometry(pipeRadius * 1.65, pipeRadius * 1.85, 0.9, 18),
      matConcretePlinth
    );
    collar.position.set(x, 0.08, z);
    collar.rotation.x = Math.PI / 2 - PIG_HOT_BEND_ANGLE_RAD;
    collar.castShadow = true;
    scene.add(collar);
  }

  const pigInletOffset = buildPigTrapAxialHotBendPoints({
    axisX: -196,
    topY: 2.2,
    buriedY: -1.2,
    startZ: -96.0,
    approachLen: 2.5,
    tailLen: 31.0,
    directionZ: -1,
  });
  createCadPipeRoute(
    [...pigInletOffset.points].reverse(),
    rMainlineInlet,
    matBuriedPipe,
    {
      bendRadius: Math.max(4.5, rMainlineInlet * 6.5),
      flowArrows: 3,
      flangeEnds: true,
      equipKey: "pig_receiver",
      lineKey: "mainline_inlet",
      segmentTitle: "Ana İletim Giriş Hattı (PIG-R Aksı 22.5° Çift Hot-Bend Offset)",
      fromBoundary: "BOTAŞ Ana İletim Hattı Giriş Tie-In Noktası (Yeraltı -1.2 m)",
      toBoundary: "Giriş Pig Kovanı (PIG-R) Aksı Çift 22.5° Hot-Bend & ESDV Flanşı",
      registerParticlePath: true,
    }
  );
  buildSoilTransitionCollar(-196, pigInletOffset.soilEntryZ, rMainlineInlet);

  const pigOutletOffset = buildPigTrapAxialHotBendPoints({
    axisX: -196,
    topY: 2.2,
    buriedY: -1.2,
    startZ: -48.0,
    approachLen: 2.5,
    tailLen: 27.0,
    directionZ: 1,
  });
  createCadPipeRoute(
    pigOutletOffset.points,
    rMainlineOutlet,
    matBuriedPipe,
    {
      bendRadius: Math.max(4.5, rMainlineOutlet * 6.5),
      flowArrows: 3,
      flangeEnds: true,
      equipKey: "pig_launcher",
      lineKey: "mainline_outlet",
      segmentTitle: "Ana İletim Çıkış Hattı (PIG-L Aksı 22.5° Çift Hot-Bend Offset)",
      fromBoundary: "Çıkış Pig Kovanı (PIG-L) Aksı ESDV Flanşı & 22.5° Hot-Bend",
      toBoundary: "BOTAŞ Ana İletim Hattı Çıkış Tie-In Noktası (Yeraltı -1.2 m)",
      registerParticlePath: true,
    }
  );
  buildSoilTransitionCollar(-196, pigOutletOffset.soilEntryZ, rMainlineOutlet);

  // Separate tee stubs joining the PIG-R / PIG-L barrels to the common pig by-pass header (x = -190)
  createCadPipeRoute(
    [
      new THREE.Vector3(-196, 2.2, -96),
      new THREE.Vector3(-190, 2.2, -96),
    ],
    Math.max(0.5, rMainlineInlet * 0.85),
    matYellowPipe,
    {
      equipKey: "pig_receiver",
      lineKey: "pig_bypass",
      segmentTitle: "PIG-R ➔ Ortak Pig By-Pass Tee Bağlantısı",
    }
  );
  createCadPipeRoute(
    [
      new THREE.Vector3(-190, 2.2, -48),
      new THREE.Vector3(-196, 2.2, -48),
    ],
    Math.max(0.5, rMainlineOutlet * 0.85),
    matYellowPipe,
    {
      equipKey: "pig_launcher",
      lineKey: "pig_bypass",
      segmentTitle: "Ortak Pig By-Pass ➔ PIG-L Tee Bağlantısı",
    }
  );

  // Elevated North Perimeter Yellow Pipe Rack (Station Recycle & Purge Line - Note 13)
  createCadPipeRoute(
    [
      new THREE.Vector3(-160, 4.2, -104),
      new THREE.Vector3(-85, 4.2, -104),
      new THREE.Vector3(55, 4.2, -104),
    ],
    rAntiSurgeHeader,
    matYellowPipe,
    {
      flowArrows: 5,
      equipKey: "station_recycle",
      lineKey: "station_recycle",
      segmentTitle: "İstasyon Ana Sirkülasyon & Purge Hattı (Note 13)",
      fromBoundary: "Station Discharge Header ( Gaz Soğutucu Çıkışı Sonrası )",
      toBoundary: "Station Suction Header ( PIG-R Çıkışı / MFS Önü )",
      registerParticlePath: true,
    }
  );
  for (let rx = -155; rx <= 50; rx += 12) {
    const post = new THREE.Mesh(new THREE.BoxGeometry(0.4, 4.2, 0.4), matCadBlueSteel);
    post.position.set(rx, 2.1, -104);
    const cross = new THREE.Mesh(new THREE.BoxGeometry(0.4, 0.3, 2.2), matCadBlueSteel);
    cross.position.set(rx, 4.0, -104);
    scene.add(post, cross);
  }

  // Pig Receiver (PIG-R) & Pig Launcher (PIG-L) Skids — relocated to the
  // extended west battery-limit yard. Barrels run along Z and the quick-opening
  // closures face each other across the pigging aisle.
  function buildPigTrapStation(x, z, labelText, equipKey, isLauncher = false) {
    const grp = new THREE.Group();
    grp.position.set(x, 0, z);
    const closureSign = isLauncher ? -1 : 1; // receiver door faces +Z, launcher door faces -Z

    // Concrete Foundation Slab (trap axis along Z)
    const slab = new THREE.Mesh(new THREE.BoxGeometry(10, 0.4, 24), matConcretePlinth);
    slab.position.y = 0.2;
    grp.add(slab);

    // Major Barrel (56") + Minor Barrel (48") in CAD Yellow/Olive
    const majorBarrel = new THREE.Mesh(new THREE.CylinderGeometry(1.15, 1.15, 10, 24), matYellowPipe);
    majorBarrel.rotation.x = Math.PI / 2;
    majorBarrel.position.set(0, 2.2, 0);
    majorBarrel.castShadow = true;
    grp.add(majorBarrel);

    const minorBarrel = new THREE.Mesh(new THREE.CylinderGeometry(0.85, 0.85, 7, 24), matYellowPipe);
    minorBarrel.rotation.x = Math.PI / 2;
    minorBarrel.position.set(0, 2.2, -closureSign * 6.5);
    minorBarrel.castShadow = true;
    grp.add(minorBarrel);

    // Quick-Opening Closure Door facing the opposite trap
    const closure = new THREE.Mesh(new THREE.CylinderGeometry(1.3, 1.3, 0.6, 20), matOliveSteel);
    closure.rotation.x = Math.PI / 2;
    closure.position.set(0, 2.2, closureSign * 7.2);
    grp.add(closure);

    // Closure hinge / davit arm makes the facing orientation readable.
    const hinge = new THREE.Mesh(new THREE.BoxGeometry(0.35, 2.0, 0.35), matValveBody);
    hinge.position.set(1.55, 3.6, closureSign * 7.4);
    grp.add(hinge);
    const davit = new THREE.Mesh(new THREE.BoxGeometry(2.4, 0.25, 0.25), matValveBody);
    davit.position.set(1.7, 4.6, closureSign * 7.4);
    grp.add(davit);

    // Saddle Supports along the Z axis
    [-5, 0, 5, 9].forEach((sz) => {
      const saddle = new THREE.Mesh(new THREE.BoxGeometry(2.4, 1.8, 0.6), matConcretePlinth);
      saddle.position.set(0, 1.1, sz * -closureSign);
      grp.add(saddle);
    });

    // Operator Grating Platform alongside the trap
    const walk = new THREE.Mesh(new THREE.BoxGeometry(2.8, 0.18, 16), matOliveSteel);
    walk.position.set(2.6, 1.8, 0);
    grp.add(walk);
    for (let hz = -7; hz <= 7; hz += 3.5) {
      const rail = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.05, 1.1, 6), matFencePost);
      rail.position.set(4.0, 2.4, hz);
      grp.add(rail);
    }
    const handrail = new THREE.Mesh(new THREE.BoxGeometry(0.08, 0.08, 15), matFencePost);
    handrail.position.set(4.0, 2.95, 0);
    grp.add(handrail);

    // Translucent Maintenance Envelope Box
    const env = new THREE.Mesh(new THREE.BoxGeometry(11, 5.5, 24), matEnvelopeBox);
    env.position.set(0, 2.75, 0);
    grp.add(env);
    envelopeMeshes.push(env);

    registerClickable(grp, equipKey);
    scene.add(grp);

    // Isolation MOV/ESDV at the pipeline-side minor barrel end
    const isolationZ = z - closureSign * 10.8;
    createValveStation(x, 2.2, isolationZ, isLauncher ? rDischHeader * 1.15 : rSuctHeader * 1.15, {
      rotationY: Math.PI / 2,
      hasPlatform: true,
      equipKey,
      valveColorMat: equipKey === "pig_launcher" ? matRedFire : matValveBody,
    });

    // Kicker (launcher) / receiver balance connection on the closure side.
    const kickerZ = z + closureSign * 4.2;
    createValveStation(x - 4.2, 1.7, kickerZ, 0.38, {
      rotationY: Math.PI / 2,
      hasActuator: false,
      hasPlatform: false,
      equipKey,
    });
    createCadGreenLabel(
      labelText,
      x - 9.5,
      0.3,
      z,
      17,
      2.4,
      -Math.PI / 2,
      Math.PI / 2,
      0
    );
  }

  buildPigTrapStation(-196, -86, `${suctLine.nominal_size_in || '48"'} PIG RECEIVER`, "pig_receiver", false);
  buildPigTrapStation(-196, -58, `${dischLine.nominal_size_in || '48"'} PIG LAUNCHER`, "pig_launcher", true);

  // ── Pig by-pass / kicker / receiver manifold ──────────────────────────────
  // Common pig by-pass header (x = -190, z = -96 .. -48) joins station inlet,
  // station suction header, PIG-R kicker, line valve, PIG-L kicker, station
  // discharge header, and station outlet.
  createCadPipeRoute(
    [
      new THREE.Vector3(-190, 2.2, -96),
      new THREE.Vector3(-190, 2.2, -82),
      new THREE.Vector3(-190, 2.2, -62),
      new THREE.Vector3(-190, 2.2, -48),
    ],
    Math.max(0.55, rSuctHeader * 0.72),
    matYellowPipe,
    {
      flowArrows: 3,
      equipKey: "pig_receiver",
      lineKey: "pig_bypass",
      segmentTitle: "PIG-R / PIG-L Ortak Pig By-Pass Kolektörü",
      fromBoundary: "Ana İletim Giriş Hattı & Station Suction Tie-In",
      toBoundary: "Station Discharge Tie-In & Ana İletim Çıkış Hattı",
      registerParticlePath: true,
    }
  );
  // Mainline by-pass Line Valve between suction (z = -82) and discharge (z = -62) tie-ins.
  createValveStation(-190, 2.2, -72, Math.max(0.52, rSuctHeader * 0.78), {
    rotationY: Math.PI / 2,
    hasActuator: true,
    hasPlatform: true,
    equipKey: "pig_receiver",
    valveColorMat: matRedFire,
  });
  // PIG-R kicker & receiver balance line (Pig By-Pass ➔ PIG-R barrel).
  createCadPipeRoute(
    [
      new THREE.Vector3(-190, 2.2, -84),
      new THREE.Vector3(-196, 2.2, -84),
    ],
    0.34,
    matYellowPipe,
    {
      equipKey: "pig_receiver",
      lineKey: "pig_kicker_receiver",
      segmentTitle: "PIG-R Kicker & Receiver Dengeleme Hattı (Pig By-Pass Bağlantısı)",
      fromBoundary: "Ortak Pig By-Pass Hattı",
      toBoundary: "PIG-R Alıcı Kovan Gövdesi",
    }
  );
  createValveStation(-193, 2.2, -84, 0.35, {
    rotationY: 0,
    hasActuator: true,
    hasPlatform: false,
    equipKey: "pig_receiver",
  });
  // PIG-L kicker line (Pig By-Pass ➔ PIG-L barrel).
  createCadPipeRoute(
    [
      new THREE.Vector3(-190, 2.2, -60),
      new THREE.Vector3(-196, 2.2, -60),
    ],
    0.34,
    matYellowPipe,
    {
      equipKey: "pig_launcher",
      lineKey: "pig_kicker_launcher",
      segmentTitle: "PIG-L Kicker Hattı (Pig By-Pass Bağlantısı)",
      fromBoundary: "Ortak Pig By-Pass Hattı",
      toBoundary: "PIG-L Atıcı Kovan Gövdesi",
    }
  );
  createValveStation(-193, 2.2, -60, 0.35, {
    rotationY: 0,
    hasActuator: true,
    hasPlatform: false,
    equipKey: "pig_launcher",
  });

  // Station Suction Header Upstream Spine (PIG by-pass ➔ MFS Inlet Manifold Tie-In)
  createCadPipeRoute(
    [
      new THREE.Vector3(-190, 2.2, -82),
      new THREE.Vector3(-160, 2.2, -82),
      new THREE.Vector3(-122, 2.2, -82),
      new THREE.Vector3(-92, 2.2, -82),
      new THREE.Vector3(-92, 2.2, -92),
      new THREE.Vector3(-72, 2.2, -92),
    ],
    rSuctHeader,
    matYellowPipe,
    {
      flowArrows: 3,
      equipKey: "pig_receiver",
      lineKey: "suction_header",
      segmentTitle: "Station Suction Header (Pig By-Pass ➔ MFS Kollektörü)",
      fromBoundary: "Ortak Pig By-Pass Hattı Emiş Bağlantısı",
      toBoundary: "MFS Çoklu Siklon Giriş Manifoldu Bağlantısı (TC Suction Header'a Devam Eden Ana Omurga)",
      registerParticlePath: true,
    }
  );

  // Station Discharge Header Downstream Spine (Gas Cooler Cooled Return ➔ PSV & ESD Risers ➔ Ultrasonic Meter ➔ Pig By-Pass).
  createCadPipeRoute(
    [
      new THREE.Vector3(-0.5, 1.6, -48),
      new THREE.Vector3(-0.5, coolerReturnY, -48),
      new THREE.Vector3(-98, coolerReturnY, -48),
      new THREE.Vector3(-98, 2.2, -62),
      new THREE.Vector3(-160, 2.2, -62),
      new THREE.Vector3(-190, 2.2, -62),
    ],
    rDischHeader,
    matYellowPipe,
    {
      flowArrows: 4,
      equipKey: "pig_launcher",
      lineKey: "discharge_header",
      segmentTitle: "Station Discharge Header (Soğutucu Dönüşü ➔ PSV/ESD ➔ USM ➔ Pig By-Pass)",
      fromBoundary: "TC Ünite Çıkış Hatları Bağlantı Headerı (Gaz Soğutucu Çıkış Tie-In)",
      toBoundary: "Ortak Pig By-Pass Hattı Basma Bağlantısı",
      registerParticlePath: true,
    }
  );

  // ── 1) PSV Riser Bank on Station Discharge Header (rising vertically on the line) ──
  const psvCount3d = Math.max(1, Math.min(4, Number(eq.safety_relief_and_blowdown?.psv_count || 2)));
  const psvBaseX = -24;
  const psvSpanX = Math.max(6, psvCount3d * 3.4);
  const psvPlatformY = coolerReturnY + 2.4;
  const psvRiserTopY = coolerReturnY + 3.3;
  const psvVentTopY = coolerReturnY + 10.6;
  const psvBankGroup = new THREE.Group();

  // Olive-steel elevated grating platform straddling the discharge header (matching cad_ref_1.jpg)
  const psvDeck = new THREE.Mesh(new THREE.BoxGeometry(psvSpanX + 3.0, 0.20, 5.2), matOliveSteel);
  psvDeck.position.set(psvBaseX, psvPlatformY, -48);
  psvBankGroup.add(psvDeck);
  const psvRailEdges = new THREE.EdgesGeometry(new THREE.BoxGeometry(psvSpanX + 3.0, 1.1, 5.2));
  const psvRails = new THREE.LineSegments(psvRailEdges, new THREE.LineBasicMaterial({ color: 0xcab300 }));
  psvRails.position.set(psvBaseX, psvPlatformY + 0.55, -48);
  psvBankGroup.add(psvRails);
  [
    [psvBaseX - (psvSpanX + 2.4) / 2, -50.3],
    [psvBaseX + (psvSpanX + 2.4) / 2, -50.3],
    [psvBaseX - (psvSpanX + 2.4) / 2, -45.7],
    [psvBaseX + (psvSpanX + 2.4) / 2, -45.7],
  ].forEach(([lx, lz]) => {
    const leg = new THREE.Mesh(new THREE.BoxGeometry(0.22, psvPlatformY, 0.22), matOliveSteel);
    leg.position.set(lx, psvPlatformY / 2, lz);
    psvBankGroup.add(leg);
  });

  for (let i = 0; i < psvCount3d; i++) {
    const offset = (i - (psvCount3d - 1) / 2) * 3.2;
    const rx = psvBaseX + offset;

    // Vertical riser teeing straight up from the discharge header
    createCadPipeRoute(
      [
        new THREE.Vector3(rx, coolerReturnY, -48),
        new THREE.Vector3(rx, psvRiserTopY, -48),
      ],
      0.30,
      matYellowPipe,
      {
        equipKey: "safety_relief",
        lineKey: "psv_inlet",
        segmentTitle: `PSV-10${i + 1} Dikey Giriş Riser Hattı (Discharge Header Üzeri)`,
        fromBoundary: "Station Discharge Header",
        toBoundary: `PSV-10${i + 1} Giriş Flanşı`,
      }
    );

    const unit = new THREE.Group();
    unit.position.set(rx, psvRiserTopY, -48);
    const inFlg = new THREE.Mesh(new THREE.CylinderGeometry(0.52, 0.52, 0.18, 16), matFlangeSteel);
    unit.add(inFlg);
    const blockValve = new THREE.Mesh(new THREE.CylinderGeometry(0.36, 0.36, 0.55, 14), matValveBody);
    blockValve.position.y = 0.38;
    unit.add(blockValve);
    const body = new THREE.Mesh(new THREE.CylinderGeometry(0.42, 0.50, 1.15, 16), matValveBody);
    body.position.y = 1.22;
    unit.add(body);
    const bonnet = new THREE.Mesh(new THREE.CylinderGeometry(0.24, 0.35, 1.05, 14), matRedFire);
    bonnet.position.y = 2.30;
    unit.add(bonnet);
    const cap = new THREE.Mesh(new THREE.SphereGeometry(0.24, 12, 8), matActuator);
    cap.position.y = 2.92;
    unit.add(cap);

    // Side discharge nozzle + vertical atmospheric relief stack rising straight up
    const sideNozzle = new THREE.Mesh(new THREE.CylinderGeometry(0.25, 0.25, 1.1, 12), matYellowPipe);
    sideNozzle.rotation.x = Math.PI / 2;
    sideNozzle.position.set(0, 1.35, -0.65);
    unit.add(sideNozzle);
    const ventPipeH = psvVentTopY - (psvRiserTopY + 1.35);
    const ventPipe = new THREE.Mesh(new THREE.CylinderGeometry(0.26, 0.30, ventPipeH, 14), matVesselGrey);
    ventPipe.position.set(0, 1.35 + ventPipeH / 2, -1.15);
    unit.add(ventPipe);
    const arrestorTip = new THREE.Mesh(new THREE.CylinderGeometry(0.38, 0.26, 1.1, 14), matRedFire);
    arrestorTip.position.set(0, 1.35 + ventPipeH + 0.55, -1.15);
    unit.add(arrestorTip);

    psvBankGroup.add(unit);
  }
  registerClickable(psvBankGroup, "safety_relief");
  scene.add(psvBankGroup);

  // ── 2) ESD / Blowdown Riser Bank on Station Discharge Header (rising vertically on the line) ──
  const esdCount3d = Math.max(1, Math.min(6, Number(eq.esd_sizing?.esd_count || 2)));
  const esdBaseX = -46;
  const esdSpanX = Math.max(6, esdCount3d * 3.4);
  const esdPlatformY = coolerReturnY + 2.4;
  const esdRiserTopY = coolerReturnY + 3.1;
  const esdVentTopY = coolerReturnY + 9.8;
  const esdBankGroup = new THREE.Group();

  const esdDeck = new THREE.Mesh(new THREE.BoxGeometry(esdSpanX + 3.0, 0.20, 5.2), matOliveSteel);
  esdDeck.position.set(esdBaseX, esdPlatformY, -48);
  esdBankGroup.add(esdDeck);
  const esdRailEdges = new THREE.EdgesGeometry(new THREE.BoxGeometry(esdSpanX + 3.0, 1.1, 5.2));
  const esdRails = new THREE.LineSegments(esdRailEdges, new THREE.LineBasicMaterial({ color: 0xcab300 }));
  esdRails.position.set(esdBaseX, esdPlatformY + 0.55, -48);
  esdBankGroup.add(esdRails);
  [
    [esdBaseX - (esdSpanX + 2.4) / 2, -50.3],
    [esdBaseX + (esdSpanX + 2.4) / 2, -50.3],
    [esdBaseX - (esdSpanX + 2.4) / 2, -45.7],
    [esdBaseX + (esdSpanX + 2.4) / 2, -45.7],
  ].forEach(([lx, lz]) => {
    const leg = new THREE.Mesh(new THREE.BoxGeometry(0.22, esdPlatformY, 0.22), matOliveSteel);
    leg.position.set(lx, esdPlatformY / 2, lz);
    esdBankGroup.add(leg);
  });

  for (let i = 0; i < esdCount3d; i++) {
    const offset = (i - (esdCount3d - 1) / 2) * 3.2;
    const ex = esdBaseX + offset;

    createCadPipeRoute(
      [
        new THREE.Vector3(ex, coolerReturnY, -48),
        new THREE.Vector3(ex, esdRiserTopY, -48),
      ],
      0.32,
      matYellowPipe,
      {
        equipKey: "esd_valves",
        lineKey: "esd_riser",
        segmentTitle: `ESD/BDV-10${i + 1} Dikey Riser Hattı (Discharge Header Üzeri)`,
        fromBoundary: "Station Discharge Header",
        toBoundary: `ESD/BDV-10${i + 1} Acil Boşaltma & Kapatma Vanası`,
      }
    );

    const esdUnit = new THREE.Group();
    esdUnit.position.set(ex, esdRiserTopY, -48);
    const flgLow = new THREE.Mesh(new THREE.CylinderGeometry(0.54, 0.54, 0.18, 16), matFlangeSteel);
    esdUnit.add(flgLow);
    const valveSphere = new THREE.Mesh(new THREE.SphereGeometry(0.52, 16, 12), matRedFire);
    valveSphere.position.y = 0.62;
    esdUnit.add(valveSphere);
    const actuator = new THREE.Mesh(new THREE.CylinderGeometry(0.32, 0.32, 0.95, 14), matActuator);
    actuator.rotation.z = Math.PI / 2;
    actuator.position.set(0.68, 0.62, 0);
    esdUnit.add(actuator);
    const flgHigh = new THREE.Mesh(new THREE.CylinderGeometry(0.50, 0.50, 0.18, 16), matFlangeSteel);
    flgHigh.position.y = 1.24;
    esdUnit.add(flgHigh);
    const stackH = esdVentTopY - (esdRiserTopY + 1.24);
    const stackPipe = new THREE.Mesh(new THREE.CylinderGeometry(0.28, 0.32, stackH, 14), matVesselGrey);
    stackPipe.position.y = 1.24 + stackH / 2;
    esdUnit.add(stackPipe);
    const stackTip = new THREE.Mesh(new THREE.CylinderGeometry(0.40, 0.28, 1.0, 14), matRedFire);
    stackTip.position.y = 1.24 + stackH + 0.5;
    esdUnit.add(stackTip);

    esdBankGroup.add(esdUnit);
  }
  registerClickable(esdBankGroup, "esd_valves");
  scene.add(esdBankGroup);

  // Mainline full-bore ESD isolation valves on discharge and suction headers
  createValveStation(-56, coolerReturnY, -48, Math.max(0.78, rDischHeader * 1.15), {
    hasActuator: true,
    hasPlatform: true,
    equipKey: "esd_valves",
    valveColorMat: matRedFire,
  });
  createValveStation(-102, 2.2, -82, Math.max(0.72, rSuctHeader * 1.15), {
    hasActuator: true,
    hasPlatform: true,
    equipKey: "esd_valves",
    valveColorMat: matRedFire,
  });

  createCadPipeCallout(
    `PSV-101..10${psvCount3d} & ESD-101..10${esdCount3d} • DISCHARGE HEADER EMNİYET MANİFOLDU`,
    "Hat Üzeri Dikey Riser PSV & ESD Vanaları (Tıklayarak Sayı & Çap Hesaplayın)",
    -35,
    coolerReturnY + 11.8,
    -48,
    { width: 32, height: 4.8, pipeY: coolerReturnY + rDischHeader, accentColor: "#ef4444", lineKey: "discharge_header", equipKey: "safety_relief" }
  );

  // ── 3) Ultrasonic Gas Flow Meter (USM - FT-401) on Station Discharge Header ──
  const usmX = -74;
  const usmY = coolerReturnY;
  const usmZ = -48;
  const usmGroup = new THREE.Group();
  usmGroup.position.set(usmX, usmY, usmZ);

  // Precision machined USM spool body + upstream flow conditioner spool
  const usmRadius = Math.max(0.68, rDischHeader * 1.18);
  const usmSpool = new THREE.Mesh(
    new THREE.CylinderGeometry(usmRadius, usmRadius, 3.6, 24),
    matCadBlueSteel
  );
  usmSpool.rotation.z = Math.PI / 2;
  usmGroup.add(usmSpool);

  // Heavy ANSI weld-neck flanges (flow conditioner, USM inlet, USM outlet)
  [-3.8, -1.8, 1.8].forEach((dx) => {
    const flg = new THREE.Mesh(
      new THREE.CylinderGeometry(usmRadius * 1.38, usmRadius * 1.38, 0.32, 20),
      matFlangeSteel
    );
    flg.rotation.z = Math.PI / 2;
    flg.position.x = dx;
    usmGroup.add(flg);
  });

  // 8-path chordal ultrasonic transducer pockets / bosses in X-pattern
  [-1.0, -0.35, 0.35, 1.0].forEach((dx) => {
    [
      [0, usmRadius * 0.85, usmRadius * 0.85, Math.PI / 4],
      [0, usmRadius * 0.85, -usmRadius * 0.85, -Math.PI / 4],
      [0, -usmRadius * 0.85, usmRadius * 0.85, (3 * Math.PI) / 4],
      [0, -usmRadius * 0.85, -usmRadius * 0.85, -(3 * Math.PI) / 4],
    ].forEach(([, dy, dz, ang]) => {
      const boss = new THREE.Mesh(new THREE.CylinderGeometry(0.11, 0.14, 0.55, 10), matSilverVessel);
      boss.position.set(dx, dy, dz);
      boss.rotation.x = ang;
      usmGroup.add(boss);
    });
  });

  // Top-mounted SPU / flow computer transmitter enclosure (FT-401)
  const usmPost = new THREE.Mesh(new THREE.CylinderGeometry(0.10, 0.10, 1.25, 10), matSilverVessel);
  usmPost.position.set(0, usmRadius + 0.6, 0);
  usmGroup.add(usmPost);
  const usmHead = new THREE.Mesh(new THREE.BoxGeometry(1.1, 0.85, 0.75), matCadBlueSteel);
  usmHead.position.set(0, usmRadius + 1.35, 0);
  usmGroup.add(usmHead);

  // Access platform under the ultrasonic meter run
  const usmDeck = new THREE.Mesh(new THREE.BoxGeometry(8.5, 0.18, 4.6), matOliveSteel);
  usmDeck.position.set(-0.8, -usmRadius - 0.55, 0);
  usmGroup.add(usmDeck);
  const usmLegH = Math.max(0.5, usmY - usmRadius - 0.55);
  [
    [-4.8, -2.1],
    [3.2, -2.1],
    [-4.8, 2.1],
    [3.2, 2.1],
  ].forEach(([lx, lz]) => {
    const leg = new THREE.Mesh(new THREE.BoxGeometry(0.18, usmLegH, 0.18), matOliveSteel);
    leg.position.set(lx, -usmRadius - 0.55 - usmLegH / 2, lz);
    usmGroup.add(leg);
  });

  registerClickable(usmGroup, "ultrasonic_meter");
  scene.add(usmGroup);

  createCadPipeCallout(
    `FT-401 • ULTRASONIC FLOW METER (${dischLine.nominal_size_in || '40"'} AGA-9)`,
    `8-Path Chordal Gaz Ölçüm İstasyonu • Hız: ${eq.ultrasonic_meter?.gas_velocity_ms || dischLine.actual_velocity_ms || 15.0} m/s`,
    usmX,
    coolerReturnY + usmRadius + 3.6,
    usmZ,
    { width: 28, height: 4.5, pipeY: coolerReturnY + rDischHeader, accentColor: "#38bdf8", lineKey: "discharge_header", equipKey: "ultrasonic_meter" }
  );

  // 3D Battery-Limit & Main-Header Callouts in North-West Pig Trap & Recycle Yard
  createCadPipeCallout(
    `L-101/115 • 22.5° ÇİFT HOT BEND OFFSET (PIG-R / PIG-L)`,
    `Kovan Aksında Toprağa Giriş & Yeraltı Yatay Offset (-1.2 m)`,
    -196,
    11.2,
    -72,
    { width: 17, height: 3.0, pipeY: 2.2, accentColor: "#a855f7", lineKey: "mainline_inlet", equipKey: "tiein" }
  );
  createCadPipeCallout(
    `L-102 • STATION SUCTION HEADER (BAŞLANGIÇ)`,
    `Sınır: PIG by-pass ➔ MFS & TC Suction Header (${suctLine.nominal_size_in || '48"'})`,
    -170,
    6.4,
    -82,
    { width: 26, height: 4.8, pipeY: 2.2 + rSuctHeader, accentColor: "#38bdf8", lineKey: "suction_header", equipKey: "pig_receiver" }
  );
  createCadPipeCallout(
    `L-109 • STATION DISCHARGE HEADER (PIG-L BİTİŞ SINIRI)`,
    `TC Çıkış Headerı & Soğutucu ➔ PIG-L Giriş MOV (${dischLine.nominal_size_in || '48"'})`,
    -76,
    coolerReturnY + rDischHeader + 3.1,
    -48,
    { width: 27, height: 4.8, pipeY: coolerReturnY + rDischHeader, accentColor: "#f59e0b", lineKey: "discharge_header", equipKey: "pig_launcher" }
  );
  createCadPipeCallout(
    `L-110 • RECYCLE & PURGE HATTI (NOTE 13)`,
    `Station Discharge Header ➔ PCV ➔ Station Suction Header (${pLines.station_recycle?.nominal_size_in || '-'})`,
    -60,
    7.8,
    -104,
    { width: 25, height: 4.5, pipeY: 4.2 + rAntiSurgeHeader, accentColor: "#22d3ee", lineKey: "station_recycle", equipKey: "station_recycle" }
  );

  // Emergency Vent / Blowdown Stack & PSV Assembly (North-West Yard)
  const ventStackGrp = new THREE.Group();
  ventStackGrp.position.set(-106, 0, -96);
  const stackBase = new THREE.Mesh(new THREE.BoxGeometry(3.5, 0.6, 3.5), matConcretePlinth);
  const stackPipe = new THREE.Mesh(new THREE.CylinderGeometry(0.55, 0.75, 22, 16), matVesselGrey);
  stackPipe.position.y = 11;
  const stackTip = new THREE.Mesh(new THREE.CylinderGeometry(0.7, 0.55, 2.2, 16), matRedFire);
  stackTip.position.y = 22.5;
  ventStackGrp.add(stackBase, stackPipe, stackTip);
  registerClickable(ventStackGrp, "safety_relief");
  scene.add(ventStackGrp);
  createValveStation(-106, 2.0, -91, 0.55, { hasPlatform: true, equipKey: "safety_relief", valveColorMat: matRedFire });

  // ══════════════════ 7. NORTH-CENTER FILTRATION & COOLING YARD (MFS, CFS, GAS COOLER) ══════════════════

  // ── 7.1 MFS: Multi-Cyclone Filter Separators (X: -72 to -46, Z: -88 to -46) ──
  const mfsGroup = new THREE.Group();
  const mfsX = -60;
  const mfsStartZ = -80;
  const mfsSpacingZ = numCyclones === 1 ? 0 : 24 / Math.max(1, numCyclones - 1);
  const mfsPlatDepth = Math.max(18, numCyclones * 7.5);

  // Central Elevated 2-Tier Olive-Steel Platform (matching Screenshot 0 & 2)
  const mfsPlat = new THREE.Mesh(new THREE.BoxGeometry(8.5, 6.2, mfsPlatDepth), matOliveSteel);
  mfsPlat.position.set(mfsX, 3.1, -68);
  mfsPlat.castShadow = true;
  mfsGroup.add(mfsPlat);

  // Translucent Maintenance Envelope around MFS (taller for vertical separators)
  const mfsEnv = new THREE.Mesh(new THREE.BoxGeometry(24, 13, mfsPlatDepth + 4), matEnvelopeBox);
  mfsEnv.position.set(mfsX - 2, 6.5, -68);
  scene.add(mfsEnv);
  envelopeMeshes.push(mfsEnv);

  // Common MFS inlet manifold (Station Suction Header tie → elevated MFS equipment manifold)
  const mfsInletX = -72;
  const mfsInletY = 6.6;
  createCadPipeRoute(
    [
      new THREE.Vector3(mfsInletX, 2.2, -92),
      new THREE.Vector3(mfsInletX, mfsInletY, -92),
      new THREE.Vector3(mfsInletX, mfsInletY, mfsStartZ + 24),
    ],
    rCycloneBranch,
    matYellowPipe,
    {
      flowArrows: 2,
      equipKey: "cyclones",
      lineKey: "cyclone_branch",
      segmentTitle: "MFS Ekipman Giriş Manifoldu (L-103)",
      fromBoundary: "Station Suction Header MFS Giriş Branşman Bağlantısı",
      toBoundary: "MFS Siklon Seperatör Ünite Giriş Nozulları (V-101..N)",
      registerParticlePath: true,
    }
  );

  // Vertical multi-cyclone separators: body + top dome + conical bottom.
  // The previous horizontal/inclined vessel bodies were rotated on the Z axis.
  const mfsVerticalX = mfsX - 6.0;
  const mfsVesselBottomY = 1.4;
  const mfsVesselBodyH = 7.2;
  const mfsVesselTopY = mfsVesselBottomY + mfsVesselBodyH;
  const mfsOutletHeaderX = mfsX + 5.5;
  const mfsOutletTopY = 10.6;

  for (let i = 0; i < numCyclones; i++) {
    const cz = numCyclones === 1 ? -68 : mfsStartZ + i * mfsSpacingZ;
    const mfsUnitTag = `V-10${i + 1}`;

    // Vertical cylindrical separator body
    const vessel = new THREE.Mesh(new THREE.CylinderGeometry(1.15, 1.15, mfsVesselBodyH, 20), matSilverVessel);
    vessel.position.set(mfsVerticalX, mfsVesselBottomY + mfsVesselBodyH / 2, cz);
    vessel.castShadow = true;
    mfsGroup.add(vessel);

    // Dished top head
    const topHead = new THREE.Mesh(
      new THREE.SphereGeometry(1.15, 20, 12, 0, Math.PI * 2, 0, Math.PI / 2),
      matSilverVessel
    );
    topHead.position.set(mfsVerticalX, mfsVesselTopY, cz);
    topHead.castShadow = true;
    mfsGroup.add(topHead);

    // Conical bottom (apex down)
    const bottomCone = new THREE.Mesh(new THREE.ConeGeometry(1.15, 1.4, 20), matSilverVessel);
    bottomCone.rotation.x = Math.PI;
    bottomCone.position.set(mfsVerticalX, mfsVesselBottomY - 0.7, cz);
    bottomCone.castShadow = true;
    mfsGroup.add(bottomCone);

    // Inlet / outlet nozzles and flanges
    const inletNozzle = new THREE.Mesh(new THREE.CylinderGeometry(0.55, 0.55, 0.9, 16), matSilverVessel);
    inletNozzle.rotation.z = Math.PI / 2;
    inletNozzle.position.set(mfsVerticalX - 1.45, mfsInletY, cz);
    mfsGroup.add(inletNozzle);

    const inletFlange = new THREE.Mesh(new THREE.CylinderGeometry(0.72, 0.72, 0.16, 16), matFlangeSteel);
    inletFlange.rotation.z = Math.PI / 2;
    inletFlange.position.set(mfsVerticalX - 1.92, mfsInletY, cz);
    mfsGroup.add(inletFlange);

    const outletNozzle = new THREE.Mesh(new THREE.CylinderGeometry(0.52, 0.52, 0.8, 16), matSilverVessel);
    outletNozzle.position.set(mfsVerticalX, mfsVesselTopY + 1.25, cz);
    mfsGroup.add(outletNozzle);

    const outletFlange = new THREE.Mesh(new THREE.CylinderGeometry(0.7, 0.7, 0.16, 16), matFlangeSteel);
    outletFlange.position.set(mfsVerticalX, mfsVesselTopY + 1.68, cz);
    mfsGroup.add(outletFlange);

    // Bottom drain nozzle
    const drainNozzle = new THREE.Mesh(new THREE.CylinderGeometry(0.22, 0.22, 0.65, 12), matSilverVessel);
    drainNozzle.position.set(mfsVerticalX, 0.45, cz);
    mfsGroup.add(drainNozzle);
    const drainValve = new THREE.Mesh(new THREE.SphereGeometry(0.32, 12, 10), matValveBody);
    drainValve.position.set(mfsVerticalX, 0.9, cz);
    mfsGroup.add(drainValve);

    // Access ladder on the east side
    [-0.28, 0.28].forEach((dz) => {
      const rail = new THREE.Mesh(new THREE.BoxGeometry(0.08, 8.2, 0.08), matCadBlueSteel);
      rail.position.set(mfsVerticalX + 1.42, 4.3, cz + dz);
      mfsGroup.add(rail);
    });
    for (let ry = 1.0; ry < 8.2; ry += 0.75) {
      const rung = new THREE.Mesh(new THREE.BoxGeometry(0.08, 0.06, 0.56), matCadBlueSteel);
      rung.position.set(mfsVerticalX + 1.42, ry, cz);
      mfsGroup.add(rung);
    }

    // Top maintenance ring
    const topRing = new THREE.Mesh(new THREE.TorusGeometry(1.35, 0.06, 8, 28), matCadBlueSteel);
    topRing.rotation.x = Math.PI / 2;
    topRing.position.set(mfsVerticalX, mfsVesselTopY - 0.35, cz);
    mfsGroup.add(topRing);

    // Three support legs around the conical bottom
    [0, (2 * Math.PI) / 3, (4 * Math.PI) / 3].forEach((angle) => {
      const leg = new THREE.Mesh(new THREE.BoxGeometry(0.16, 1.4, 0.16), matCadBlueSteel);
      leg.position.set(
        mfsVerticalX + Math.cos(angle) * 1.25,
        0.7,
        cz + Math.sin(angle) * 1.25
      );
      leg.castShadow = true;
      mfsGroup.add(leg);
    });

    // Inlet branch from the common inlet header into the separator side
    createCadPipeRoute(
      [
        new THREE.Vector3(mfsInletX, mfsInletY, cz),
        new THREE.Vector3(mfsVerticalX - 1.15, mfsInletY, cz),
      ],
      rCycloneBranch,
      matYellowPipe,
      {
        flowArrows: 1,
        equipKey: "cyclones",
        lineKey: "cyclone_branch",
        unitLabel: mfsUnitTag,
        segmentTitle: `MFS Siklon Giriş Branşmanı (${mfsUnitTag})`,
        fromBoundary: "Station Suction Header MFS Giriş Manifoldu",
        toBoundary: `${mfsUnitTag} Siklon Seperatör Giriş Nozulu`,
      }
    );
    createValveStation(mfsVerticalX - 3.0, mfsInletY, cz, rCycloneBranch, { hasPlatform: false, equipKey: "cyclones" });

    // Outlet from separator top → overhead header → shared outlet collector
    createCadPipeRoute(
      [
        new THREE.Vector3(mfsVerticalX, mfsVesselTopY + 1.15, cz),
        new THREE.Vector3(mfsVerticalX, mfsOutletTopY, cz),
        new THREE.Vector3(mfsOutletHeaderX, mfsOutletTopY, cz),
        new THREE.Vector3(mfsOutletHeaderX, 2.4, cz),
      ],
      rCycloneBranch,
      matYellowPipe,
      {
        flowArrows: 1,
        equipKey: "cyclones",
        lineKey: "cyclone_branch",
        unitLabel: mfsUnitTag,
        segmentTitle: `MFS Siklon Üst Çıkış Branşmanı (${mfsUnitTag})`,
        fromBoundary: `${mfsUnitTag} Siklon Üst Çıkış Nozulu`,
        toBoundary: "MFS Ortak Çıkış Kollektörü (CFS Ara Bağlantısı)",
        registerParticlePath: i === 0,
      }
    );
    createValveStation(mfsVerticalX + 3.2, mfsOutletTopY, cz, rCycloneBranch, { hasPlatform: false, equipKey: "cyclones" });
  }

  // MFS outlet collector header: ties every cyclone top outlet to the CFS inlet.
  createCadPipeRoute(
    [
      new THREE.Vector3(mfsOutletHeaderX, 2.4, mfsStartZ),
      new THREE.Vector3(mfsOutletHeaderX, 2.4, mfsStartZ + 24),
    ],
    rCycloneBranch,
    matYellowPipe,
    {
      flowArrows: 4,
      equipKey: "cyclones",
      lineKey: "cyclone_branch",
      segmentTitle: "MFS Ekipman Çıkış Kollektörü",
      fromBoundary: "MFS Siklon Üst Çıkış Branşmanları",
      toBoundary: "CFS Kartuş Filtre Giriş Manifoldu Ara Bağlantısı",
      registerParticlePath: true,
    }
  );
  createCadPipeRoute(
    [
      new THREE.Vector3(mfsOutletHeaderX, 2.4, -76),
      new THREE.Vector3(mfsX + 8.0, 2.4, -76),
    ],
    rCycloneBranch,
    matYellowPipe,
    {
      flowArrows: 1,
      equipKey: "cyclones",
      lineKey: "cyclone_branch",
      segmentTitle: "MFS ➔ CFS Ara Bağlantı Kollektörü",
      fromBoundary: "MFS Ortak Çıkış Kollektörü",
      toBoundary: "CFS Kartuş Filtre Giriş Manifoldu",
    }
  );

  // Condensate Collection Sump Box (South-West of MFS, Note 14)
  const condBox1 = new THREE.Mesh(new THREE.BoxGeometry(5.5, 3.2, 5.5), matOliveSteel);
  condBox1.position.set(-73, 1.6, -50);
  mfsGroup.add(condBox1);
  registerClickable(condBox1, "condensate_system");

  // Small Instrument / Local Shelter South-East of MFS (seen in Screenshot 0 & 1)
  const mfsShelter = new THREE.Mesh(new THREE.BoxGeometry(5.2, 6.5, 5.2), matOliveSteel);
  mfsShelter.position.set(-48, 3.25, -40);
  mfsGroup.add(mfsShelter);

  registerClickable(mfsGroup, "cyclones");
  scene.add(mfsGroup);
  createCadGreenLabel("MFS", mfsX - 2, 0.3, -90, 12, 2.8, -Math.PI / 2, 0, 0);
  createCadPipeCallout(
    `L-103 • MFS EKİPMAN BORULAMASI`,
    `Ana Suction Header ➔ Siklon Seperatörler (${pLines.cyclone_branch?.nominal_size_in || '-'})`,
    mfsInletX,
    10.4,
    -74,
    { width: 22, height: 4.3, pipeY: mfsInletY + rCycloneBranch, accentColor: "#34d399", lineKey: "cyclone_branch", equipKey: "cyclones" }
  );

  // ── 7.2 CFS: Cartridge Filter Separators (X: -40 to -14, Z: -85 to -52) ──
  const cfsGroup = new THREE.Group();
  const cfsStartX = -38;
  const cfsSpacingX = numFilters === 1 ? 0 : 18 / Math.max(1, numFilters - 1);

  for (let i = 0; i < numFilters; i++) {
    const fx = numFilters === 1 ? -29 : cfsStartX + i * cfsSpacingX;
    const cfsUnitTag = `F-10${i + 1}`;
    // Horizontal Cylindrical Filter Vessel oriented North-South (matching Screenshot 0, 1, 2)
    const fltVessel = new THREE.Mesh(new THREE.CylinderGeometry(1.0, 1.0, 11.5, 22), matSilverVessel);
    fltVessel.rotation.x = Math.PI / 2;
    fltVessel.position.set(fx, 2.5, -68);
    fltVessel.castShadow = true;
    cfsGroup.add(fltVessel);

    // Dished heads at both ends
    [-62.25, -73.75].forEach((hz) => {
      const head = new THREE.Mesh(new THREE.SphereGeometry(1.0, 20, 12), matSilverVessel);
      head.scale.z = 0.38;
      head.position.set(fx, 2.5, hz);
      head.castShadow = true;
      cfsGroup.add(head);
    });

    // Saddle supports
    [-72.0, -64.0].forEach((sz) => {
      const saddle = new THREE.Mesh(new THREE.BoxGeometry(1.9, 1.35, 0.55), matCadBlueSteel);
      saddle.position.set(fx, 0.68, sz);
      saddle.castShadow = true;
      cfsGroup.add(saddle);
      const pad = new THREE.Mesh(new THREE.BoxGeometry(2.4, 0.18, 0.9), matConcretePlinth);
      pad.position.set(fx, 0.09, sz);
      cfsGroup.add(pad);
    });

    // Top inlet nozzle + flange
    const inletNozzle = new THREE.Mesh(new THREE.CylinderGeometry(0.52, 0.52, 0.8, 16), matSilverVessel);
    inletNozzle.position.set(fx, 3.5, -71);
    cfsGroup.add(inletNozzle);
    const inletFlange = new THREE.Mesh(new THREE.CylinderGeometry(0.7, 0.7, 0.15, 16), matFlangeSteel);
    inletFlange.position.set(fx, 3.93, -71);
    cfsGroup.add(inletFlange);

    // End outlet nozzle + flange
    const outletNozzle = new THREE.Mesh(new THREE.CylinderGeometry(0.52, 0.52, 0.8, 16), matSilverVessel);
    outletNozzle.rotation.x = Math.PI / 2;
    outletNozzle.position.set(fx, 2.5, -61.85);
    cfsGroup.add(outletNozzle);
    const outletFlange = new THREE.Mesh(new THREE.CylinderGeometry(0.7, 0.7, 0.15, 16), matFlangeSteel);
    outletFlange.rotation.x = Math.PI / 2;
    outletFlange.position.set(fx, 2.5, -61.4);
    cfsGroup.add(outletFlange);

    // Bottom drain nozzle
    const drain = new THREE.Mesh(new THREE.CylinderGeometry(0.2, 0.2, 0.6, 12), matSilverVessel);
    drain.position.set(fx, 1.35, -68);
    cfsGroup.add(drain);

    // Quick-opening filter cover facing South
    const cap = new THREE.Mesh(new THREE.CylinderGeometry(1.12, 1.12, 0.45, 20), matYellowPipe);
    cap.rotation.x = Math.PI / 2;
    cap.position.set(fx, 2.5, -62.1);
    cfsGroup.add(cap);

    // Side steel access platforms along each CFS vessel
    const sideWalk = new THREE.Mesh(new THREE.BoxGeometry(1.8, 0.15, 11), matOliveSteel);
    sideWalk.position.set(fx + 1.8, 2.0, -68);
    cfsGroup.add(sideWalk);

    // Overhead Yellow Inlet U-bend into CFS top nozzle
    createCadPipeRoute(
      [
        new THREE.Vector3(mfsX + 8.0, 2.4, -76),
        new THREE.Vector3(fx, 2.4, -76),
        new THREE.Vector3(fx, 4.8, -73),
        new THREE.Vector3(fx, 3.2, -71),
      ],
      rFilterBranch,
      matYellowPipe,
      {
        flowArrows: 1,
        equipKey: "cartridge_filters",
        lineKey: "filter_branch",
        unitLabel: cfsUnitTag,
        segmentTitle: `CFS Kartuş Filtre Giriş Branşmanı (${cfsUnitTag})`,
        fromBoundary: "MFS Çıkış Ara Kollektörü",
        toBoundary: `${cfsUnitTag} Kartuş Filtre Üst Giriş Nozulu`,
      }
    );
    createValveStation(fx - 2.5, 2.4, -76, rFilterBranch, { hasPlatform: false, equipKey: "cartridge_filters" });

    // Outlet from end nozzle to the common CFS outlet header
    createCadPipeRoute(
      [
        new THREE.Vector3(fx, 2.5, -61.4),
        new THREE.Vector3(fx, 2.5, -59.2),
        new THREE.Vector3(fx, 2.2, -57),
      ],
      rFilterBranch,
      matYellowPipe,
      {
        flowArrows: 1,
        equipKey: "cartridge_filters",
        lineKey: "filter_branch",
        unitLabel: cfsUnitTag,
        segmentTitle: `CFS Kartuş Filtre Çıkış Branşmanı (${cfsUnitTag})`,
        fromBoundary: `${cfsUnitTag} Kartuş Filtre Çıkış Nozulu`,
        toBoundary: "CFS Ortak Çıkış Manifoldu (Station Suction Header Bağlantısı)",
        registerParticlePath: i === 0,
      }
    );
    createValveStation(fx, 2.5, -59.2, rFilterBranch, { hasPlatform: false, rotationY: Math.PI / 2, equipKey: "cartridge_filters" });
  }

  // Common CFS outlet collector header (single pipe, no duplicated overlap)
  const cfsOutletStartX = numFilters === 1 ? -29 : cfsStartX;
  createCadPipeRoute(
    [
      new THREE.Vector3(cfsOutletStartX, 2.2, -57),
      new THREE.Vector3(-12, 2.2, -57),
    ],
    rFilterBranch,
    matYellowPipe,
    {
      flowArrows: 2,
      equipKey: "cartridge_filters",
      lineKey: "filter_branch",
      segmentTitle: "CFS Ekipman Çıkış Kollektörü (L-104)",
      fromBoundary: "CFS Kartuş Filtre Ünite Çıkış Nozulları",
      toBoundary: "Station Suction Header (Filtrelenmiş Ana Omurga Tie-In Noktası)",
      registerParticlePath: true,
    }
  );

  // Translucent Maintenance Envelope East of CFS + Metering Platform
  const cfsEnv = new THREE.Mesh(new THREE.BoxGeometry(9, 5.5, 16), matEnvelopeBox);
  cfsEnv.position.set(-12, 2.75, -68);
  scene.add(cfsEnv);
  envelopeMeshes.push(cfsEnv);

  const condBox2 = new THREE.Mesh(new THREE.BoxGeometry(5.0, 2.8, 5.0), matOliveSteel);
  condBox2.position.set(-18, 1.4, -52);
  cfsGroup.add(condBox2);

  registerClickable(cfsGroup, "cartridge_filters");
  scene.add(cfsGroup);
  createCadGreenLabel("CFS", -29, 0.3, -90, 12, 2.8, -Math.PI / 2, 0, 0);
  createCadPipeCallout(
    `L-104 • CFS EKİPMAN BORULAMASI`,
    `MFS Çıkışı ➔ CFS ➔ Station Suction Header (${pLines.filter_branch?.nominal_size_in || '-'})`,
    -29,
    7.6,
    -61,
    { width: 22, height: 4.3, pipeY: 2.5 + rFilterBranch, accentColor: "#34d399", lineKey: "filter_branch", equipKey: "cartridge_filters" }
  );

  // Station Suction Header Mid-Spine: Filtered main header routing from CFS across North Road to TC Suction Connection Header
  createCadPipeRoute(
    [
      new THREE.Vector3(-12, 2.2, -57),
      new THREE.Vector3(-12, 2.2, -32),
      new THREE.Vector3(-32, 2.2, -32),
      new THREE.Vector3(-32, 1.5, -16.2),
    ],
    rSuctHeader,
    matYellowPipe,
    {
      flowArrows: 3,
      equipKey: "turbo_compressors",
      lineKey: "comp_suction_header",
      segmentTitle: "Station Suction Header (CFS Çıkışı ➔ TC Suction Bağlantı Headerı)",
      fromBoundary: "CFS Çıkış Manifoldu Ana Header Dönüş Tie-In Noktası",
      toBoundary: "Turbo-Kompresör Üniteleri Suction Bağlantı Headerı",
      registerParticlePath: true,
    }
  );
  createCadPipeCallout(
    `L-105 • STATION SUCTION HEADER (ANA OMURGA)`,
    `CFS Çıkışı ➔ TC Ünite Suction Bağlantı Headerı (${compSuctHeaderLine.nominal_size_in || suctLine.nominal_size_in || '48"'})`,
    -22,
    6.2,
    -32,
    { width: 26, height: 4.6, pipeY: 2.2 + rSuctHeader, accentColor: "#38bdf8", lineKey: "comp_suction_header", equipKey: "turbo_compressors" }
  );

  // ── 7.3 GAS COOLER: Elevated Fin-Fan Air Cooler Bank (X: -2 to +44, Z: -92 to -56) ──
  const coolerGroup = new THREE.Group();
  const coolerX0 = 2;
  const desiredBayW = Math.max(3.2, Math.min(10.0, coolerTubesPerRow * 0.22));
  const coolerWidth = Math.max(16, Math.min(80, numCoolerBays * desiredBayW));
  const coolerEndX = coolerX0 + coolerWidth;
  const coolerDepth = Math.max(14, Math.min(28, 12 + coolerTubeLength * 0.8));
  const coolerDeckY = 7.8;

  // Riser top elevation stays inside the plenum (top y = 10.0). The previous
  // y = 10.6 run grazed the fan shrouds/louvers; y = 9.5 gives a clean entry.
  const coolerRiserTopY = coolerDeckY + 1.7;

  // Elevated Fin-Fan Plenum Box
  const plenum = new THREE.Mesh(new THREE.BoxGeometry(coolerWidth, 2.2, coolerDepth), matVesselGrey);
  plenum.position.set(coolerX0 + coolerWidth / 2, coolerDeckY + 1.1, -76);
  plenum.castShadow = true;
  plenum.receiveShadow = true;
  coolerGroup.add(plenum);

  // Tube-bundle end sheets and side headers (visible fin-fan details)
  [coolerX0 + 0.35, coolerEndX - 0.35].forEach((hx) => {
    const tubeSheet = new THREE.Mesh(
      new THREE.BoxGeometry(0.28, 1.75, coolerDepth * 0.9),
      matCadBlueSteel
    );
    tubeSheet.position.set(hx, coolerDeckY + 1.15, -76);
    coolerGroup.add(tubeSheet);

    const header = new THREE.Mesh(
      new THREE.CylinderGeometry(0.34, 0.34, coolerDepth * 0.9, 16),
      matVesselGrey
    );
    header.rotation.x = Math.PI / 2;
    header.position.set(hx < coolerX0 + coolerWidth / 2 ? coolerX0 - 0.05 : coolerEndX + 0.05, coolerDeckY + 1.15, -76);
    coolerGroup.add(header);
  });

  // Fin-tube bank side panels
  [-1, 1].forEach((side) => {
    const bank = new THREE.Mesh(
      new THREE.BoxGeometry(coolerWidth - 1.6, 1.15, 0.22),
      matFinTube
    );
    bank.position.set(coolerX0 + coolerWidth / 2, coolerDeckY + 1.15, -76 + side * (coolerDepth / 2 - 0.18));
    coolerGroup.add(bank);
  });

  // Dynamic Fin-Fan Bays on top + Spinning Induced-Draft Fan Blades
  const bayW = (coolerWidth - 2) / numCoolerBays;
  for (let b = 0; b < numCoolerBays; b++) {
    const bx = coolerX0 + 1 + (b + 0.5) * bayW;
    // Louver frame with slats
    const louverFrame = new THREE.Mesh(new THREE.BoxGeometry(bayW * 0.9, 0.2, coolerDepth - 2), matVesselGrey);
    louverFrame.position.set(bx, coolerDeckY + 2.3, -76);
    coolerGroup.add(louverFrame);
    for (let s = 0; s < 6; s++) {
      const slat = new THREE.Mesh(new THREE.BoxGeometry(bayW * 0.86, 0.05, 0.22), matPurlinBrown);
      slat.position.set(bx, coolerDeckY + 2.34, -76 - (coolerDepth - 3) / 2 + s * ((coolerDepth - 3) / 5));
      coolerGroup.add(slat);
    }

    // Spinning Fans per Bay (geometry-synced count)
    const fanSpan = Math.max(1.0, coolerDepth - 5.0);
    const fanOffsets = [];
    for (let f = 0; f < coolerFansPerBay; f++) {
      const t = coolerFansPerBay === 1 ? 0.5 : f / (coolerFansPerBay - 1);
      fanOffsets.push(-fanSpan / 2 + t * fanSpan);
    }
    fanOffsets.forEach((dz) => {
      const fanRadius = Math.max(0.7, Math.min(2.6, Math.min(coolerFanDiameter / 2, bayW * 0.42)));
      const shroud = new THREE.Mesh(
        new THREE.CylinderGeometry(fanRadius, fanRadius, 0.55, 24, 1, true),
        matVesselGrey
      );
      shroud.position.set(bx, coolerDeckY + 2.45, -76 + dz);
      coolerGroup.add(shroud);

      const fanRing = new THREE.Mesh(new THREE.TorusGeometry(fanRadius, 0.08, 8, 32), matCadBlueSteel);
      fanRing.rotation.x = Math.PI / 2;
      fanRing.position.set(bx, coolerDeckY + 2.72, -76 + dz);
      coolerGroup.add(fanRing);

      const fanHub = new THREE.Group();
      fanHub.position.set(bx, coolerDeckY + 2.48, -76 + dz);
      const hub = new THREE.Mesh(new THREE.CylinderGeometry(0.24, 0.24, 0.3, 14), matActuator);
      fanHub.add(hub);
      const bladeLen = Math.max(1.2, fanRadius * 1.85);
      for (let f = 0; f < 6; f++) {
        const blade = new THREE.Mesh(new THREE.BoxGeometry(bladeLen, 0.07, 0.5), matFanBlade);
        blade.rotation.y = (f * Math.PI) / 3;
        blade.rotation.x = 0.16;
        blade.position.x = Math.cos((f * Math.PI) / 3) * bladeLen * 0.5;
        blade.position.z = -Math.sin((f * Math.PI) / 3) * bladeLen * 0.5;
        fanHub.add(blade);
      }
      coolerGroup.add(fanHub);
      spinningFans.push(fanHub);

      // Fan motor and belt guard above the fan deck
      const motor = new THREE.Mesh(new THREE.CylinderGeometry(0.34, 0.34, 0.55, 16), matActuator);
      motor.position.set(bx + fanRadius * 0.55, coolerDeckY + 3.0, -76 + dz);
      coolerGroup.add(motor);
      const beltGuard = new THREE.Mesh(new THREE.BoxGeometry(fanRadius * 0.7, 0.16, 0.35), matCadBlueSteel);
      beltGuard.position.set(bx + fanRadius * 0.3, coolerDeckY + 2.95, -76 + dz);
      coolerGroup.add(beltGuard);
    });
  }

  // Support Portal Legs & Tall Yellow Risers scaled to coolerWidth
  const numRiserPairs = Math.max(2, Math.min(5, Math.floor(numCoolerBays * 0.75) + 1));
  for (let r = 0; r < numRiserPairs; r++) {
    const rx = coolerX0 + 4 + r * ((coolerWidth - 8) / Math.max(1, numRiserPairs - 1));

    // Blue Steel Support Frame Columns (South & North legs)
    [-8.2, 8.2].forEach((dz) => {
      const col = new THREE.Mesh(new THREE.BoxGeometry(0.55, coolerDeckY, 0.55), matCadBlueSteel);
      col.position.set(rx, coolerDeckY / 2, -76 + dz);
      col.castShadow = true;
      coolerGroup.add(col);
    });

    // Blue Diagonal X-Bracing on South Face (vividly visible in Screenshot 0, 2, 3)
    const brace1 = new THREE.Mesh(new THREE.BoxGeometry(0.25, coolerDeckY * 1.15, 0.25), matCadBlueSteel);
    brace1.position.set(rx, coolerDeckY / 2, -67.8);
    brace1.rotation.z = 0.32;
    const brace2 = brace1.clone();
    brace2.rotation.z = -0.32;
    coolerGroup.add(brace1, brace2);

    // Tall Vertical Yellow Inlet & Outlet Pipe Risers climbing the South Face into Cooler Top.
    // The cold outlet riser rises immediately above the hot inlet header (y = 3.0)
    // before running south. Previously it ran on the ground from z = -48 to -65.5
    // and physically crossed the hot header at z = -54.
    [-1.1, 1.1].forEach((dx, idx) => {
      const riserX = rx + dx;
      const riserPoints = idx === 0
        ? [
            new THREE.Vector3(riserX, 1.6, -54),
            new THREE.Vector3(riserX, 1.6, -65.5),
            new THREE.Vector3(riserX, coolerRiserTopY, -65.5),
            new THREE.Vector3(riserX, coolerRiserTopY, -71),
          ]
        : [
            new THREE.Vector3(riserX, 1.6, -48),
            new THREE.Vector3(riserX, coolerOutletCrossY, -48),
            new THREE.Vector3(riserX, coolerOutletCrossY, -65.5),
            new THREE.Vector3(riserX, coolerRiserTopY, -65.5),
            new THREE.Vector3(riserX, coolerRiserTopY, -71),
          ];
      createCadPipeRoute(
        riserPoints,
        rCoolerRiser,
        matYellowPipe,
        {
          flowArrows: 1,
          reverseFlow: idx === 1,
          equipKey: "air_coolers",
          lineKey: "cooler_bay_risers",
          unitLabel: `E-101-R${r + 1}`,
          segmentTitle: idx === 0
            ? `Gaz Soğutucu Bay Giriş Riser Branşmanı (#${r + 1})`
            : `Gaz Soğutucu Bay Çıkış Riser Branşmanı (#${r + 1})`,
          fromBoundary: idx === 0
            ? "Gaz Soğutucu Sıcak Giriş Manifoldu (L-111)"
            : "Fin-Fan Tüp Demeti Çıkış Headerı (E-101)",
          toBoundary: idx === 0
            ? "Fin-Fan Tüp Demeti Giriş Headerı (E-101)"
            : "Gaz Soğutucu Soğuk Çıkış Manifoldu (L-113)",
          registerParticlePath: r === 0,
        }
      );
      createValveStation(
        riserX,
        idx === 0 ? 1.6 : coolerOutletCrossY,
        -58,
        Math.max(0.28, rCoolerRiser * 0.95),
        { hasPlatform: false, equipKey: "air_coolers" }
      );
    });
  }

  // Hot Gas Inlet Header & Cooled Gas Outlet Header in front of Gas Cooler (Z: -54 and -48).
  // Station Discharge Header (rDischHeader) feeds the Gas Cooler hot manifold tie-in:
  //   - 2-unit layout: x = -5.0 keeps >= 4.5 m X-clearance from cold return riser (x = -0.5).
  //   - 3+ unit layout: turns north east of coolerEndX + 4.5 to clear all headers.
  const gasCoolerFeedTurnX = headerEastX <= -6
    ? -5.0
    : Math.max(headerEastX + 4.5, coolerEndX + 4.5);
  const gasCoolerFeedPoints = [
    new THREE.Vector3(headerEastX, 1.5, -11.0),
    new THREE.Vector3(gasCoolerFeedTurnX, 1.5, -11.0),
    new THREE.Vector3(gasCoolerFeedTurnX, 1.6, -54.0),
  ];
  if (gasCoolerFeedTurnX > coolerEndX) {
    gasCoolerFeedPoints.push(new THREE.Vector3(coolerEndX, 1.6, -54.0));
  }
  createCadPipeRoute(
    gasCoolerFeedPoints,
    rDischHeader,
    matYellowPipe,
    {
      flowArrows: 4,
      equipKey: "air_coolers",
      lineKey: "discharge_header",
      segmentTitle: "Station Discharge Header (TC Çıkış Headerı ➔ Gaz Soğutucu Giriş Tie-In)",
      fromBoundary: "Turbo-Kompresör Ünite Çıkış Hatları Bağlantı Headerı",
      toBoundary: "Gaz Soğutucu Giriş Manifoldu Bağlantısı (PIG-L'ye Devam Eden Ana Omurga)",
      registerParticlePath: true,
    }
  );
  createCadPipeRoute(
    [
      new THREE.Vector3(-5.0, 1.6, -54),
      new THREE.Vector3(coolerEndX, 1.6, -54),
    ],
    rCoolerInlet,
    matYellowPipe,
    {
      flowArrows: 4,
      equipKey: "air_coolers",
      lineKey: "cooler_inlet",
      segmentTitle: "Gaz Soğutucu Sıcak Giriş Ekipman Manifoldu (L-111)",
      fromBoundary: "Station Discharge Header Gaz Soğutucu Giriş Tie-In Noktası",
      toBoundary: "Gaz Soğutucu Bay Giriş Riser Branşmanları",
      registerParticlePath: true,
      reverseFlow: gasCoolerFeedTurnX > coolerEndX,
    }
  );
  createCadPipeRoute(
    [
      new THREE.Vector3(-0.5, 1.6, -48),
      new THREE.Vector3(coolerEndX, 1.6, -48),
    ],
    rCoolerOutlet,
    matYellowPipe,
    {
      flowArrows: 4,
      equipKey: "air_coolers",
      lineKey: "cooler_outlet",
      segmentTitle: "Gaz Soğutucu Soğuk Çıkış Ekipman Manifoldu (L-113)",
      fromBoundary: "Gaz Soğutucu Bay Çıkış Riser Branşmanları",
      toBoundary: "Station Discharge Header Soğutulmuş Gaz Dönüş Tie-In Noktası",
      registerParticlePath: true,
      reverseFlow: true,
    }
  );

  // Gas Cooler By-Pass Line with TCV Control Valve (Note 17).
  // Lifts from hot inlet manifold (x = -5.0, z = -54) above coolerReturnY and
  // drops into cold outlet manifold at x = 3.2 (between cold return x = -0.5 and first riser x = 7.1).
  const bypassTieX = 3.2;
  createCadPipeRoute(
    [
      new THREE.Vector3(-5.0, 1.6, -54),
      new THREE.Vector3(-5.0, coolerBypassY, -54),
      new THREE.Vector3(-5.0, coolerBypassY, -48),
      new THREE.Vector3(bypassTieX, coolerBypassY, -48),
      new THREE.Vector3(bypassTieX, 1.6, -48),
    ],
    rCoolerBypass,
    matYellowPipe,
    {
      flowArrows: 2,
      equipKey: "cooler_bypass",
      lineKey: "cooler_bypass",
      segmentTitle: "Gaz Soğutucu TCV By-Pass Hattı (L-114 • Note 17)",
      fromBoundary: "Gaz Soğutucu Sıcak Giriş Manifoldu (TCV-101 Girişi)",
      toBoundary: "Gaz Soğutucu Soğuk Çıkış Manifoldu / Station Discharge Header Dönüşü",
      registerParticlePath: true,
    }
  );
  createValveStation(1.4, coolerBypassY, -48, Math.max(0.25, rCoolerBypass), { hasPlatform: false, equipKey: "cooler_bypass" });

  createCadPipeCallout(
    `L-111..114 • COOLER EKİPMAN MANİFOLDU & TCV`,
    `Discharge Header ➔ E-101 Riserlar (${pLines.cooler_inlet?.nominal_size_in || '-'} / ${pLines.cooler_bay_risers?.nominal_size_in || '-'})`,
    coolerX0 + coolerWidth * 0.5,
    5.8,
    -54,
    { width: 25, height: 4.5, pipeY: 1.6 + rCoolerInlet, accentColor: "#34d399", lineKey: "cooler_inlet", equipKey: "air_coolers" }
  );

  // Translucent Grey Maintenance Box on East Side of Gas Cooler
  const coolerEnv = new THREE.Mesh(new THREE.BoxGeometry(10, 9.5, 18), matEnvelopeBox);
  coolerEnv.position.set(coolerEndX + 5, 4.75, -76);
  scene.add(coolerEnv);
  envelopeMeshes.push(coolerEnv);

  registerClickable(coolerGroup, "air_coolers");
  scene.add(coolerGroup);
  createCadGreenLabel("GAS COOLER", coolerX0 + coolerWidth / 2, coolerDeckY + 2.65, -83, Math.max(18, coolerWidth * 0.7), 3.8, -Math.PI / 2, 0, 0);
  if (coolerGeometry && coolerGeometry.tubes_per_row) {
    createCadGreenLabel(
      `${coolerTubeRows}x${coolerTubesPerRow} TUBES`,
      coolerX0 + coolerWidth / 2,
      coolerDeckY + 0.6,
      -68,
      Math.max(14, coolerWidth * 0.55),
      2.4,
      -Math.PI / 2,
      0,
      0
    );
  }

  // ── 7.4 TEMPORARY WASTE STORAGE AREA (North-East Angled Brown Buildings, X: +75 to +110, Z: -102 to -60) ──
  const wasteGroup = new THREE.Group();
  wasteGroup.position.set(92, 0, -82);
  wasteGroup.rotation.y = -0.62; // Angled parallel to NE perimeter fence as in Screenshot (1) & (2)

  const wasteBldg1 = new THREE.Mesh(new THREE.BoxGeometry(26, 6.5, 16), matBuildingWall);
  wasteBldg1.position.set(-14, 3.25, -8);
  wasteBldg1.castShadow = true;
  const wasteBldg2 = new THREE.Mesh(new THREE.BoxGeometry(24, 6.5, 16), matBuildingWall);
  wasteBldg2.position.set(14, 3.25, 10);
  wasteBldg2.castShadow = true;
  const wasteApron = new THREE.Mesh(new THREE.BoxGeometry(58, 0.15, 42), matBuildingRoof);
  wasteApron.position.set(0, 0.08, 0);
  wasteGroup.add(wasteBldg1, wasteBldg2, wasteApron);
  scene.add(wasteGroup);

  createCadGreenLabel(
    "TEMPORARY WASTE STORAGE AREA",
    92,
    7.2,
    -82,
    46,
    3.4,
    -Math.PI / 2,
    0,
    -0.62
  );

  // ══════════════════ 8. FRONT MANIFOLD CORRIDOR & U-EXPANSION LOOPS (Z: -18 to -8) ══════════════════

  // 3 Parallel Yellow Main Headers running West-to-East in front of Compressor Buildings.
  // Main-header radii (rSuctHeader, rAntiSurgeHeader, rDischHeader, rCompSuctionBranch,
  // rCompDischargeBranch, rAntiSurge) are computed upfront in Section 1.
  const suctBranchCrossY = Math.max(
    3.6,
    1.5 + Math.max(rAntiSurgeHeader, rDischHeader) + rCompSuctionBranch + 0.45
  );
  const antiSurgeCrossY = Math.max(
    2.6 + rCompSuctionBranch + rAntiSurge + 0.40,
    1.5 + rDischHeader + rAntiSurge + 0.45
  );

  // 1) Turbo-Compressor Suction Connection Header — Terminal Section of Station Suction Header (Z = -16.2)
  createCadPipeRoute(
    [new THREE.Vector3(headerEastX, 1.5, -16.2), new THREE.Vector3(headerWestX, 1.5, -16.2)],
    rSuctHeader,
    matYellowPipe,
    {
      flowArrows: 6,
      equipKey: "turbo_compressors",
      lineKey: "comp_suction_header",
      segmentTitle: "TC Üniteleri Suction Bağlantı Headerı (Station Suction Header Bitiş Kollektörü)",
      fromBoundary: "CFS Çıkışından Gelen Filtrelenmiş Station Suction Header Omurgası",
      toBoundary: "Turbo-Kompresör Üniteleri Suction Bağlantı Headerı Kör Flanşı (Bitiş Sınırı)",
      registerParticlePath: true,
    }
  );

  // 2) Anti-Surge / Recycle Header (Z = -13.6), between suction and discharge.
  createCadPipeRoute(
    [new THREE.Vector3(headerEastX, 1.5, -13.6), new THREE.Vector3(headerWestX, 1.5, -13.6)],
    rAntiSurgeHeader,
    matYellowPipe,
    {
      flowArrows: 4,
      equipKey: "anti_surge",
      lineKey: "station_recycle",
      segmentTitle: "Ortak Anti-Surge & Recycle Ara Kollektörü",
      fromBoundary: "Ünite ASV Geri Dönüş Hatları (L-108)",
      toBoundary: "Station Suction Header Batı Dönüş Bağlantısı",
      registerParticlePath: true,
    }
  );

  // Single anti-surge header tie to the suction header at the west end.
  createCadPipeRoute(
    [
      new THREE.Vector3(headerWestX, 1.5, -13.6),
      new THREE.Vector3(headerWestX - 4.0, 1.5, -13.6),
      new THREE.Vector3(headerWestX - 4.0, 1.5, -16.2),
      new THREE.Vector3(headerWestX, 1.5, -16.2),
    ],
    rAntiSurgeHeader,
    matYellowPipe,
    {
      flowArrows: 1,
      equipKey: "anti_surge",
      lineKey: "station_recycle",
      segmentTitle: "Anti-Surge Ara Header ➔ Station Suction Header Tie-In",
      fromBoundary: "Ortak Anti-Surge & Recycle Ara Headerı",
      toBoundary: "TC Suction Bağlantı Headerı Batı Ucu",
      registerParticlePath: false,
    }
  );

  // 3) Turbo-Compressor Discharge Connection Header — Starting Section of Station Discharge Header (Z = -11.0)
  createCadPipeRoute(
    [new THREE.Vector3(headerWestX, 1.5, -11.0), new THREE.Vector3(headerEastX, 1.5, -11.0)],
    rDischHeader,
    matYellowPipe,
    {
      flowArrows: 6,
      equipKey: "turbo_compressors",
      lineKey: "discharge_header",
      segmentTitle: "Station Discharge Header (TC Ünite Çıkış Bağlantı Headerı Başlangıcı)",
      fromBoundary: "Turbo-Kompresör Ünite Çıkış Hatlarının Bağlandığı Discharge Header Başlangıcı",
      toBoundary: "Gaz Soğutucu Giriş Tie-In ve Çıkış Pig Kovanı (PIG-L) Yönü",
      registerParticlePath: true,
    }
  );

  // 3D Callout Plaques for Front Manifold Corridor (Station Suction End & Station Discharge Start)
  createCadPipeCallout(
    `L-105 • TC SUCTION HEADER (SUCTION BİTİŞ SINIRI)`,
    `Station Suction Header Sonu ➔ Ünite Emiş Branşmanları (${compSuctHeaderLine.nominal_size_in || suctLine.nominal_size_in || '48"'})`,
    Math.min(headerEastX - 14, -46),
    6.5,
    -16.2,
    { width: 27, height: 4.7, pipeY: 1.5 + rSuctHeader, accentColor: "#38bdf8", lineKey: "comp_suction_header", equipKey: "turbo_compressors" }
  );
  createCadPipeCallout(
    `L-109 • STATION DISCHARGE HEADER (BAŞLANGIÇ)`,
    `TC Ünite Çıkış Hatları (L-107) ➔ Soğutucu & PIG-L (${dischLine.nominal_size_in || '48"'})`,
    Math.max(headerWestX + 24, -104),
    6.5,
    -11.0,
    { width: 27, height: 4.7, pipeY: 1.5 + rDischHeader, accentColor: "#f59e0b", lineKey: "discharge_header", equipKey: "turbo_compressors" }
  );

  // Concrete Sleeper Pipe Supports along the 3-Header Corridor
  for (let sx = headerWestX + 6; sx <= headerEastX - 4; sx += 10) {
    const sleeper = new THREE.Mesh(new THREE.BoxGeometry(0.6, 0.9, 7.5), matConcretePlinth);
    sleeper.position.set(sx, 0.45, -13.6);
    scene.add(sleeper);
  }

  // East Header Termination Olive-Green Valve Pit Box
  const eastValvePit = new THREE.Group();
  eastValvePit.position.set(headerEastX + 4, 0, -13.6);
  const pitWalls = new THREE.Mesh(new THREE.BoxGeometry(6.5, 3.2, 8.8), matOliveSteel);
  pitWalls.position.y = 1.6;
  eastValvePit.add(pitWalls);
  [-2.6, 0, 2.6].forEach((dz) => {
    const vCyl = new THREE.Mesh(new THREE.CylinderGeometry(0.85, 0.85, 2.2, 16), matYellowPipe);
    vCyl.rotation.z = Math.PI / 2;
    vCyl.position.set(0, 1.6, dz);
    eastValvePit.add(vCyl);
  });
  registerClickable(eastValvePit, "station_recycle");
  scene.add(eastValvePit);

  // Translucent Future Header Extension Envelope
  const eastExtEnv = new THREE.Mesh(new THREE.BoxGeometry(32, 3.5, 8.5), matEnvelopeBox);
  eastExtEnv.position.set(headerEastX + 24, 1.75, -13.6);
  scene.add(eastExtEnv);
  envelopeMeshes.push(eastExtEnv);

  // ══════════════════ 9. DYNAMIC N+1 INDIVIDUAL COMPRESSOR BUILDINGS (COMPRESSOR-01 .. N) ══════════════════

  const bldgW = 24;
  const bldgL = 32;
  const bldgWallH = 11.0;
  const bldgRidgeH = 13.6;
  const bldgCenterZ = 16;

  /**
   * Builds a pitched roof geometry (triangular prism) for industrial buildings.
   */
  function createGabledRoofMesh(w, l, rise, mat) {
    const shape = new THREE.Shape();
    shape.moveTo(-w / 2 - 0.6, 0);
    shape.lineTo(0, rise);
    shape.lineTo(w / 2 + 0.6, 0);
    shape.closePath();

    const extrudeSettings = { depth: l + 0.8, bevelEnabled: false };
    const geo = new THREE.ExtrudeGeometry(shape, extrudeSettings);
    geo.translate(0, 0, -(l + 0.8) / 2);
    const mesh = new THREE.Mesh(geo, mat);
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    return mesh;
  }

  for (let i = 0; i < numComps; i++) {
    const cx = numComps === 1 ? -60 : compStartX + i * compPitch;
    const unitNumStr = String(i + 1).padStart(2, "0");
    const unitLabel = `COMPRESSOR-${unitNumStr}`;

    const unitRoot = new THREE.Group();
    unitRoot.position.set(cx, 0, bldgCenterZ);

    // 1) Concrete Foundation Plinth & Floor Slab
    const plinth = new THREE.Mesh(new THREE.BoxGeometry(bldgW + 1.2, 1.2, bldgL + 1.2), matConcretePlinth);
    plinth.position.y = 0.6;
    plinth.receiveShadow = true;
    unitRoot.add(plinth);

    // 2) INTERNAL STRUCTURAL STEEL & TURBO-COMPRESSOR PACKAGE (Always built so Cutaway/X-Ray can reveal it!)
    const internalGroup = new THREE.Group();

    // 6 Bays of CAD Blue (#0077be) Structural Steel Portal Frames (Columns + Pitched Roof Trusses)
    const nFrames = 6;
    for (let f = 0; f < nFrames; f++) {
      const fz = -bldgL / 2 + 1.2 + f * ((bldgL - 2.4) / (nFrames - 1));

      // West & East Blue H-Columns
      [-bldgW / 2 + 0.4, bldgW / 2 - 0.4].forEach((colX) => {
        const col = new THREE.Mesh(new THREE.BoxGeometry(0.45, bldgWallH, 0.45), matCadBlueSteel);
        col.position.set(colX, 1.2 + bldgWallH / 2, fz);
        col.castShadow = true;
        internalGroup.add(col);
      });

      // Pitched Roof Truss Rafters + Horizontal Bottom Chord
      const tieChord = new THREE.Mesh(new THREE.BoxGeometry(bldgW - 0.6, 0.3, 0.3), matCadBlueSteel);
      tieChord.position.set(0, 1.2 + bldgWallH, fz);
      internalGroup.add(tieChord);

      [-1, 1].forEach((side) => {
        const rafterLen = Math.hypot(bldgW / 2, bldgRidgeH - bldgWallH);
        const rafterAngle = Math.atan2(bldgRidgeH - bldgWallH, bldgW / 2);
        const rafter = new THREE.Mesh(new THREE.BoxGeometry(rafterLen, 0.32, 0.32), matCadBlueSteel);
        rafter.position.set((side * bldgW) / 4, 1.2 + bldgWallH + (bldgRidgeH - bldgWallH) / 2, fz);
        rafter.rotation.z = -side * rafterAngle;
        internalGroup.add(rafter);
      });
    }

    // Longitudinal Crane Runway Girders (Blue) & Overhead Bridge Crane (Yellow/Blue)
    [-bldgW / 2 + 1.1, bldgW / 2 - 1.1].forEach((gx) => {
      const craneRail = new THREE.Mesh(new THREE.BoxGeometry(0.35, 0.55, bldgL - 2), matCadBlueSteel);
      craneRail.position.set(gx, 9.8, 0);
      internalGroup.add(craneRail);
    });
    const bridgeGirder = new THREE.Mesh(new THREE.BoxGeometry(bldgW - 2.2, 0.65, 1.4), matYellowPipe);
    bridgeGirder.position.set(0, 10.3, -4);
    internalGroup.add(bridgeGirder);

    // Brown Longitudinal Roof Purlins & Side Wall Girts (as seen on COMPRESSOR-04 in Screenshot 3 & 4)
    for (let px = -bldgW / 2 + 2; px <= bldgW / 2 - 2; px += 3.2) {
      const py = 1.2 + bldgWallH + (1 - Math.abs(px) / (bldgW / 2)) * (bldgRidgeH - bldgWallH);
      const purlin = new THREE.Mesh(new THREE.BoxGeometry(0.18, 0.22, bldgL - 1), matPurlinBrown);
      purlin.position.set(px, py, 0);
      internalGroup.add(purlin);
    }

    // Internal Gas Turbine + Centrifugal Compressor Skid Enclosure (Brown/Taupe Acoustic Box + Barrel)
    const gtSkid = new THREE.Mesh(new THREE.BoxGeometry(7.2, 4.6, 13.5), matSkidEnclosure);
    gtSkid.position.set(-2.2, 3.5, 2.5);
    gtSkid.castShadow = true;
    internalGroup.add(gtSkid);

    const compBarrel = new THREE.Mesh(new THREE.CylinderGeometry(1.75, 1.75, 4.8, 24), matSkidEnclosure);
    compBarrel.rotation.x = Math.PI / 2;
    compBarrel.position.set(-2.2, 3.4, -7.2);
    compBarrel.castShadow = true;
    internalGroup.add(compBarrel);

    // Internal Yellow Suction & Discharge Piping is built below as connected
    // routes from the building wall to the compressor barrel nozzles.
    // (Previous decorative inPipe1/inPipe2 meshes were disconnected and removed.)

    // Internal Teal/Blue Overhead Utility Piping & Cyan Instrument Stanchions (Screenshot 3)
    const utilPipe = new THREE.Mesh(new THREE.CylinderGeometry(0.14, 0.14, bldgW - 2, 8), matTealUtilityPipe);
    utilPipe.rotation.z = Math.PI / 2;
    utilPipe.position.set(0, 4.2, -14.8);
    internalGroup.add(utilPipe);
    [-5.5, 0.5, 5.5].forEach((ix) => {
      const instBox = new THREE.Mesh(new THREE.BoxGeometry(0.9, 1.1, 0.45), matCyanArrow);
      instBox.position.set(ix, 3.8, -14.8);
      internalGroup.add(instBox);
    });

    unitRoot.add(internalGroup);

    // 3) EXTERIOR CLADDING WALLS & GABLED ROOF GROUP (Toggled off when unit is in Cutaway/X-Ray Mode!)
    const exteriorCladdingGroup = new THREE.Group();

    const wallsBox = new THREE.Mesh(new THREE.BoxGeometry(bldgW, bldgWallH, bldgL), matBuildingWall);
    wallsBox.position.y = 1.2 + bldgWallH / 2;
    wallsBox.castShadow = true;
    wallsBox.receiveShadow = true;
    exteriorCladdingGroup.add(wallsBox);

    const gabledRoof = createGabledRoofMesh(bldgW, bldgL, bldgRidgeH - bldgWallH, matBuildingRoof);
    gabledRoof.position.y = 1.2 + bldgWallH;
    exteriorCladdingGroup.add(gabledRoof);

    // 2 Cyan Circular Roof Exhaust Vents on West Roof Slope (Screenshot 1 & 2)
    [-6, 6].forEach((vz) => {
      const vent = new THREE.Mesh(new THREE.CylinderGeometry(0.75, 0.75, 0.9, 16), matTealUtilityPipe);
      vent.position.set(-bldgW / 4, bldgRidgeH + 0.1, vz);
      exteriorCladdingGroup.add(vent);
    });

    // 3 Louver Windows on West Wall (Screenshot 4)
    [3.5, 6.8, 10.0].forEach((wy) => {
      const win = new THREE.Mesh(new THREE.BoxGeometry(0.25, 1.6, 2.2), matConcretePlinth);
      win.position.set(-bldgW / 2 - 0.05, wy, -8);
      exteriorCladdingGroup.add(win);
    });

    unitRoot.add(exteriorCladdingGroup);

    // 4) Green 3D Roof Label ("COMPRESSOR-01" .. "COMPRESSOR-05") along East Roof Slope
    createCadGreenLabel(
      unitLabel,
      cx + bldgW / 4 + 1.2,
      bldgRidgeH + 0.65,
      bldgCenterZ,
      26,
      3.4,
      -Math.PI / 2,
      0,
      Math.PI / 2
    );

    // 5) External Per-Unit Ancillaries (Always visible outside West/South-West of Building)
    // a) Vertical gas-turbine exhaust stack, same colour as the turbine skid.
    // The stack is perpendicular to grade and connected to the GT enclosure by
    // a horizontal transition duct + elbow (previous model was tilted 0.38 rad).
    const stackX = -bldgW / 2 - 3.6;
    const stackZ = 3.5;
    const stackH = 15.0;
    const stackBaseY = 0.6;
    const stackRadius = 1.15;
    const stackPlinth = new THREE.Mesh(new THREE.BoxGeometry(3.2, 0.6, 3.2), matConcretePlinth);
    stackPlinth.position.set(stackX, 0.3, stackZ);
    stackPlinth.receiveShadow = true;
    unitRoot.add(stackPlinth);

    const exhaustStack = new THREE.Mesh(
      new THREE.CylinderGeometry(stackRadius, stackRadius, stackH, 20),
      matSkidEnclosure
    );
    exhaustStack.position.set(stackX, stackBaseY + stackH / 2, stackZ);
    exhaustStack.castShadow = true;
    unitRoot.add(exhaustStack);

    const stackRim = new THREE.Mesh(
      new THREE.CylinderGeometry(stackRadius * 1.06, stackRadius * 1.06, 0.35, 20),
      matSkidEnclosure
    );
    stackRim.position.set(stackX, stackBaseY + stackH - 0.175, stackZ);
    unitRoot.add(stackRim);

    // Horizontal transition from the GT skid west face to the vertical stack.
    const ductY = 5.4;
    const ductStartX = -5.8;
    const ductLength = Math.abs(stackX - ductStartX);
    const exhaustTransition = new THREE.Mesh(
      new THREE.CylinderGeometry(0.9, 0.9, ductLength, 16),
      matSkidEnclosure
    );
    exhaustTransition.rotation.z = Math.PI / 2;
    exhaustTransition.position.set((stackX + ductStartX) / 2, ductY, stackZ);
    exhaustTransition.castShadow = true;
    unitRoot.add(exhaustTransition);

    const exhaustElbow = new THREE.Mesh(new THREE.SphereGeometry(1.0, 16, 12), matSkidEnclosure);
    exhaustElbow.position.set(stackX, ductY, stackZ);
    exhaustElbow.castShadow = true;
    unitRoot.add(exhaustElbow);

    // b) External Turbine Combustion Air Intake Filter House & Lube Oil Cooler Skid (SW of Building)
    const filterSkid = new THREE.Mesh(new THREE.BoxGeometry(5.5, 5.2, 7.5), matPurlinBrown);
    filterSkid.position.set(-bldgW / 2 - 4.8, 3.2, 11.5);
    filterSkid.castShadow = true;
    unitRoot.add(filterSkid);

    // c) Standalone Local Unit Electrical / Control Shelter (Brown pitched-roof cabin next to each unit)
    const localElecRoom = new THREE.Mesh(new THREE.BoxGeometry(6.2, 4.8, 6.8), matBuildingWall);
    localElecRoom.position.set(-bldgW / 2 - 11.5, 2.4, 11.5);
    localElecRoom.castShadow = true;
    unitRoot.add(localElecRoom);

    // d) Dark-Brown Cable Trench Bridge from South 7.0 M. WIDE ROAD into South Wall of Building
    const cableBridge = new THREE.Mesh(new THREE.BoxGeometry(2.6, 0.65, 16), matCableTrench);
    cableBridge.position.set(-bldgW / 2 + 3.5, 0.35, bldgL / 2 + 8);
    unitRoot.add(cableBridge);

    // 6) Front Branch Piping (Suction In, Discharge Out, Anti-Surge ASV Loop & Signature U-Crossover Loop)
    const suctBranchX = cx + 3.2;
    const dischBranchX = cx + 7.2;

    // Suction Branch from TC Suction Connection Header (Z = -16.2) into Building North Wall (Z = 0).
    createCadPipeRoute(
      [
        new THREE.Vector3(suctBranchX, 1.5, -16.2),
        new THREE.Vector3(suctBranchX, suctBranchCrossY, -15.0),
        new THREE.Vector3(suctBranchX, suctBranchCrossY, -9.5),
        new THREE.Vector3(suctBranchX, 2.6, -9.5),
        new THREE.Vector3(suctBranchX, 2.6, 1.0),
      ],
      rCompSuctionBranch,
      matYellowPipe,
      {
        flowArrows: 2,
        equipKey: "turbo_compressors",
        lineKey: "comp_suction_branch",
        unitLabel,
        segmentTitle: `${unitLabel} Emiş Branşmanı (L-106)`,
        fromBoundary: "TC Üniteleri Suction Bağlantı Headerı (Z = -16.2m)",
        toBoundary: `${unitLabel} Santrifüj Kompresör Emiş Nozulu`,
        registerParticlePath: true,
      }
    );
    createValveStation(suctBranchX, 2.6, -5.2, rCompSuctionBranch, { hasPlatform: true, equipKey: "turbo_compressors" });

    // Internal suction continuation: north-wall entry -> compressor barrel north nozzle.
    createCadPipeRoute(
      [
        new THREE.Vector3(suctBranchX, 2.6, 1.0),
        new THREE.Vector3(suctBranchX, 2.6, 4.6),
        new THREE.Vector3(suctBranchX, 3.4, 4.6),
        new THREE.Vector3(cx - 2.2, 3.4, 4.6),
        new THREE.Vector3(cx - 2.2, 3.4, 6.4),
      ],
      rCompSuctionBranch,
      matYellowPipe,
      {
        flowArrows: 2,
        equipKey: "turbo_compressors",
        lineKey: "comp_suction_branch",
        unitLabel,
        segmentTitle: `${unitLabel} Bina İçi Emiş Nozul Hattı (L-106)`,
        fromBoundary: `${unitLabel} Kuzey Duvar Girişi`,
        toBoundary: `${unitLabel} Kompresör Emiş Flanşı`,
        registerParticlePath: true,
      }
    );

    // Discharge Branch from Building North Wall out to Station Discharge Header (Z = -11.0)
    createCadPipeRoute(
      [
        new THREE.Vector3(dischBranchX, 1.8, 1.0),
        new THREE.Vector3(dischBranchX, 1.5, -11.0),
      ],
      rCompDischargeBranch,
      matYellowPipe,
      {
        flowArrows: 2,
        equipKey: "turbo_compressors",
        lineKey: "comp_discharge_branch",
        unitLabel,
        segmentTitle: `${unitLabel} Basma Branşmanı (L-107)`,
        fromBoundary: `${unitLabel} Santrifüj Kompresör Basma Nozulu / Çekvalf`,
        toBoundary: "Station Discharge Header Bağlantı Branşmanı (Z = -11.0m)",
        registerParticlePath: true,
      }
    );
    createValveStation(dischBranchX, 1.8, -4.5, rCompDischargeBranch, { hasPlatform: true, equipKey: "turbo_compressors" });

    // Internal discharge continuation: compressor barrel south nozzle -> north-wall entry.
    createCadPipeRoute(
      [
        new THREE.Vector3(cx - 2.2, 5.0, 11.2),
        new THREE.Vector3(cx - 2.2, 6.5, 11.2),
        new THREE.Vector3(cx - 2.2, 6.5, 12.4),
        new THREE.Vector3(dischBranchX, 6.5, 12.4),
        new THREE.Vector3(dischBranchX, 1.8, 12.4),
        new THREE.Vector3(dischBranchX, 1.8, 1.0),
      ],
      rCompDischargeBranch,
      matYellowPipe,
      {
        flowArrows: 2,
        equipKey: "turbo_compressors",
        lineKey: "comp_discharge_branch",
        unitLabel,
        segmentTitle: `${unitLabel} Bina İçi Basma Nozul Hattı (L-107)`,
        fromBoundary: `${unitLabel} Kompresör Basma Flanşı`,
        toBoundary: "Station Discharge Header Bağlantı Branşmanı",
        registerParticlePath: true,
      }
    );

    // Hot Gas Anti-Surge Recycle Loop (ASV): discharge branch → ASV header.
    createCadPipeRoute(
      [
        new THREE.Vector3(dischBranchX, 1.8, -2.0),
        new THREE.Vector3(dischBranchX, antiSurgeCrossY, -2.0),
        new THREE.Vector3(cx + 0.5, antiSurgeCrossY, -2.0),
        new THREE.Vector3(cx + 0.5, antiSurgeCrossY, -13.6),
        new THREE.Vector3(cx + 0.5, 1.5, -13.6),
      ],
      rAntiSurge,
      matYellowPipe,
      {
        flowArrows: 1,
        equipKey: "anti_surge",
        lineKey: "anti_surge_loop",
        unitLabel,
        segmentTitle: `${unitLabel} ASV Anti-Surge Loop Hattı (L-108)`,
        fromBoundary: `${unitLabel} Basma Branşmanı (Çekvalf Önü)`,
        toBoundary: "Ortak Anti-Surge / Suction Geri Dönüş Headerı",
      }
    );
    createValveStation(cx + 0.5, antiSurgeCrossY, -7.6, rAntiSurge, { hasPlatform: true, equipKey: "anti_surge" });

    if (i === 0) {
      createCadPipeCallout(
        `L-106/107 • TC ÜNİTE BRANŞMAN BORULAMASI`,
        `Suction (${compSuctionBranchLine.nominal_size_in || '-'}) & Discharge (${compDischargeBranchLine.nominal_size_in || '-'}) ➔ Ana Header`,
        cx + 5.2,
        antiSurgeCrossY + 3.2,
        -5.0,
        { width: 25, height: 4.5, pipeY: suctBranchCrossY, accentColor: "#34d399", lineKey: "comp_suction_branch", equipKey: "turbo_compressors" }
      );
    }

    registerClickable(unitRoot, "turbo_compressors");
    registerClickable(exteriorCladdingGroup, "compressor_building");
    scene.add(unitRoot);

    compressorBuildingRefs.push({
      index: i + 1,
      exteriorGroup: exteriorCladdingGroup,
      internalGroup,
    });
  }

  // Apply initial Cutaway State (active cutaway unit open in structural X-Ray mode, matching Screenshot 1, 3, 4)
  function applyCutawayState() {
    compressorBuildingRefs.forEach((ref) => {
      if (cutawayMode === "all") {
        ref.exteriorGroup.visible = false;
      } else if (cutawayMode === "unitCutaway" || cutawayMode === "unit4") {
        ref.exteriorGroup.visible = ref.index !== cutawayUnitIdx;
      } else {
        ref.exteriorGroup.visible = true;
      }
    });
  }
  applyCutawayState();

  // North-South Dark Brown Cable/Pipe Trench Crossings across North Road (seen in Screenshot 0, 1, 4)
  [-45, -18].forEach((tx) => {
    const northCrossing = new THREE.Mesh(new THREE.BoxGeometry(2.8, 0.65, 58), matCableTrench);
    northCrossing.position.set(tx, 0.35, -22);
    scene.add(northCrossing);
  });

  // ══════════════════ 10. SOUTH AUXILIARY, CONTROL & UTILITY BUILDINGS ZONE ══════════════════

  function buildAuxiliaryBuilding(x, z, w, h, d, labelText, equipKey = "compressor_building", rotLabelZ = 0) {
    const grp = new THREE.Group();
    grp.position.set(x, 0, z);

    const body = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), matBuildingWall);
    body.position.y = h / 2;
    body.castShadow = true;
    body.receiveShadow = true;
    grp.add(body);

    const roof = createGabledRoofMesh(w, d, 2.4, matBuildingRoof);
    roof.position.y = h;
    grp.add(roof);

    registerClickable(grp, equipKey);
    scene.add(grp);

    if (labelText) {
      createCadGreenLabel(labelText, x, h + 2.8, z, Math.max(20, w * 0.95), 3.0, -Math.PI / 2, 0, rotLabelZ);
    }
    return grp;
  }

  // 1) AUXILIARY & CONTROL BUILDING (X = -62, Z = +86) + TRANSFORMER 1 & 2 Yard
  const ctrlBldg = buildAuxiliaryBuilding(-62, 86, 66, 7.5, 26, "AUXILIARY & CONTROL BUILDING", "control_building");
  // Entrance canopy & Transformer Bays on South Facade
  const canopy = new THREE.Mesh(new THREE.BoxGeometry(12, 5.5, 8), matBuildingRoof);
  canopy.position.set(6, 2.75, -16);
  ctrlBldg.add(canopy);
  createCadGreenLabel("TRANSFORMER 1 & 2", -48, 1.2, 104, 22, 2.2, -Math.PI / 2, 0, 0);

  // 2) GENERATOR & M.V. ROOM (X = +6, Z = +92)
  buildAuxiliaryBuilding(6, 92, 28, 6.8, 18, "GENERATOR & M.V. ROOM", "generator_building");

  // 3) FIRE WATER BUILDING & TANK (X = +64, Z = +88)
  buildAuxiliaryBuilding(64, 88, 20, 6.8, 26, "FIRE WATER BUILDING & TANK", "safety_relief", Math.PI / 2);

  // 4) AIR COMPRESSOR BUILDING (X = +92, Z = +88)
  buildAuxiliaryBuilding(92, 88, 15, 6.5, 22, "AIR COMPRESSOR BUILDING", "air_compressor_building", Math.PI / 2);

  // 5) GUARD SHELTER at South-East Compressor Road Bend (X = +110, Z = +41)
  buildAuxiliaryBuilding(110, 41, 6.5, 3.8, 5.5, "GUARD SHELTER", "guard_shelter");

  // 6) South-East Administration / Workshop Building outside East Road (X = +146, Z = +92)
  buildAuxiliaryBuilding(146, 92, 20, 7.2, 54, "ADMINISTRATION & WORKSHOP", "admin_building", Math.PI / 2);

  // Red Fire Hydrants & ESD Junction Boxes around Process & Compressor Perimeter (as seen in CAD screenshots)
  [
    [-110, -32], [-65, -32], [-15, -32], [35, -32], [85, -32],
    [-110, 40], [-55, 40], [5, 40], [65, 40],
  ].forEach(([hx, hz]) => {
    const hydrant = new THREE.Mesh(new THREE.BoxGeometry(1.6, 1.8, 1.6), matRedFire);
    hydrant.position.set(hx, 0.9, hz);
    scene.add(hydrant);
  });

  // ══════════════════ 11. UI TOOLBAR & CAMERA PRESET BINDINGS ══════════════════

  const cutawayCompX = numComps === 1 ? -60 : compStartX + (cutawayUnitIdx - 1) * compPitch;
  const cameraPresets = {
    iso: { pos: new THREE.Vector3(-145, 95, -155), look: new THREE.Vector3(-10, 6, 5) },
    top: { pos: new THREE.Vector3(-5, 255, 6), look: new THREE.Vector3(-5, 0, 5) },
    compCutaway: { pos: new THREE.Vector3(cutawayCompX + 24, 22, -26), look: new THREE.Vector3(cutawayCompX, 6, 12) },
    comp4: { pos: new THREE.Vector3(cutawayCompX + 24, 22, -26), look: new THREE.Vector3(cutawayCompX, 6, 12) },
    manifold: { pos: new THREE.Vector3(18, 18, -32), look: new THREE.Vector3(-12, 3, -10) },
    filtration: { pos: new THREE.Vector3(-45, 36, -118), look: new THREE.Vector3(-45, 4, -68) },
    cooler: { pos: new THREE.Vector3(24, 30, -30), look: new THREE.Vector3(22, 7, -72) },
    tiein: { pos: new THREE.Vector3(-232, 22, -74), look: new THREE.Vector3(-192, 0.2, -72) },
    control: { pos: new THREE.Vector3(-25, 55, 155), look: new THREE.Vector3(-15, 5, 85) },
  };

  container.querySelectorAll(".cam-preset-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const key = btn.getAttribute("data-cam");
      const preset = cameraPresets[key];
      if (preset) {
        flyToCamera(preset.pos, preset.look, btn);
      }
    });
  });

  // Cutaway Mode Button (Cycles: Unit X-Ray -> All Units X-Ray -> All Closed)
  container.querySelector("#btn-cutaway-mode")?.addEventListener("click", (e) => {
    if (cutawayMode === "unitCutaway" || cutawayMode === "unit4") {
      cutawayMode = "all";
      e.currentTarget.textContent = "🏗️ Bina Kesiti: Tüm Binalar (X-Ray)";
      e.currentTarget.style.background = "#0284c7";
    } else if (cutawayMode === "all") {
      cutawayMode = "none";
      e.currentTarget.textContent = "🏠 Bina Kesiti: Tümü Kapalı";
      e.currentTarget.style.background = "#1e293b";
    } else {
      cutawayMode = "unitCutaway";
      e.currentTarget.textContent = `🏗️ Bina Kesiti: ${cutawayUnitLabel} (X-Ray)`;
      e.currentTarget.style.background = "#0284c7";
    }
    applyCutawayState();
  });

  // Pipe Labels & Battery-Limit Plaques Toggle
  container.querySelector("#btn-toggle-pipe-labels")?.addEventListener("click", (e) => {
    showPipeLabels = !showPipeLabels;
    pipeLabelMeshes.forEach((m) => (m.visible = showPipeLabels));
    e.currentTarget.style.background = showPipeLabels ? "#7c3aed" : "#1e293b";
    e.currentTarget.style.color = showPipeLabels ? "#fff" : "#cbd5e1";
    e.currentTarget.style.borderColor = showPipeLabels ? "#c084fc" : "rgba(255,255,255,0.15)";
    syncToolbarAria();
  });

  // Maintenance Envelopes Toggle
  container.querySelector("#btn-toggle-envelopes")?.addEventListener("click", (e) => {
    showEnvelopes = !showEnvelopes;
    envelopeMeshes.forEach((m) => (m.visible = showEnvelopes));
    e.currentTarget.textContent = showEnvelopes ? "📦 Bakım Hacimleri: Açık" : "📦 Bakım Hacimleri: Gizli";
    e.currentTarget.style.background = showEnvelopes ? "#0284c7" : "#1e293b";
  });

  // Flow Arrows & Particles Toggle
  container.querySelector("#btn-toggle-particles")?.addEventListener("click", (e) => {
    showFlowParticles = !showFlowParticles;
    flowArrowMeshes.forEach((m) => (m.visible = showFlowParticles));
    flowParticleMeshes.forEach((m) => (m.visible = showFlowParticles));
    e.currentTarget.textContent = showFlowParticles
      ? "💨 Akış Okları & Parçacıklar: Açık"
      : "💨 Akış Okları & Parçacıklar: Gizli";
    e.currentTarget.style.background = showFlowParticles ? "#059669" : "#1e293b";
  });

  // 180° Pipe Cutaway Inspector Popup Toggle
  const pipeOverlay = container.querySelector("#pipe-section-overlay");
  container.querySelector("#btn-pipe-cutaway-inspector")?.addEventListener("click", () => {
    showPipeSectionModal = !showPipeSectionModal;
    if (pipeOverlay) pipeOverlay.style.display = showPipeSectionModal ? "block" : "none";
    if (showPipeSectionModal) {
      flyToCamera(cameraPresets.compCutaway.pos, cameraPresets.compCutaway.look);
    }
  });
  container.querySelector("#btn-close-pipe-section")?.addEventListener("click", () => {
    showPipeSectionModal = false;
    if (pipeOverlay) pipeOverlay.style.display = "none";
  });

  // Day (CAD Plant 3D) / Night (LNG Dark HUD) Theme Switcher
  function applyTheme(mode) {
    themeMode = mode;
    const isNight = themeMode === "night";
    scene.background.copy(isNight ? nightSkyColor : cadSkyColor);
    scene.fog.color.copy(isNight ? nightSkyColor : cadSkyColor);
    if (rootEl) rootEl.style.background = isNight ? "#090d16" : "#7aa0dc";
    matProcessGround.color.setHex(isNight ? 0x131c2e : 0xcbe0f9);
    matSouthConcrete.color.setHex(isNight ? 0x1e293b : 0xc4c8ce);
    ambientLight.intensity = isNight ? 0.38 : 0.78;
    sunLight.intensity = isNight ? 0.65 : 1.15;
    const themeBtn = container.querySelector("#btn-theme-mode");
    if (themeBtn) {
      themeBtn.textContent = isNight ? "🌙 Mod: Gece (Koyu HUD)" : "☀️ Mod: CAD Gündüz";
    }
  }

  container.querySelector("#btn-theme-mode")?.addEventListener("click", () => {
    applyTheme(themeMode === "cad" ? "night" : "cad");
  });

  // Apply restored state if re-mounted
  if (themeMode === "night") {
    applyTheme("night");
  }
  if (!showPipeLabels) {
    pipeLabelMeshes.forEach((m) => (m.visible = false));
    const lblBtn = container.querySelector("#btn-toggle-pipe-labels");
    if (lblBtn) {
      lblBtn.style.background = "#1e293b";
      lblBtn.style.color = "#cbd5e1";
      lblBtn.style.borderColor = "rgba(255,255,255,0.15)";
    }
  }
  if (!showEnvelopes) {
    envelopeMeshes.forEach((m) => (m.visible = false));
    const envBtn = container.querySelector("#btn-toggle-envelopes");
    if (envBtn) {
      envBtn.textContent = "📦 Bakım Hacimleri: Gizli";
      envBtn.style.background = "#1e293b";
    }
  }
  if (!showFlowParticles) {
    flowArrowMeshes.forEach((m) => (m.visible = false));
    flowParticleMeshes.forEach((m) => (m.visible = false));
    const partBtn = container.querySelector("#btn-toggle-particles");
    if (partBtn) {
      partBtn.textContent = "💨 Akış Okları & Parçacıklar: Gizli";
      partBtn.style.background = "#1e293b";
    }
  }
  applyCutawayState();

  // UX: toggle düğmelerinin erişilebilir durumu (aria-pressed) ve tooltip senkronu
  function syncToolbarAria() {
    const set = (sel, pressed) => container.querySelector(sel)?.setAttribute("aria-pressed", String(!!pressed));
    set("#btn-cutaway-mode", cutawayMode !== "none");
    set("#btn-toggle-pipe-labels", showPipeLabels);
    set("#btn-toggle-envelopes", showEnvelopes);
    set("#btn-toggle-particles", showFlowParticles);
    set("#btn-pipe-cutaway-inspector", showPipeSectionModal);
    set("#btn-theme-mode", themeMode === "night");
    container.querySelectorAll("#station-3d-root .hud-toolbar button, #station-3d-root .hud-presets button").forEach((b) => {
      b.title = b.textContent.replace(/\s+/g, " ").trim();
    });
  }
  syncToolbarAria();
  rootEl?.addEventListener("click", syncToolbarAria);

  // ══════════════════ 12. RAYCASTING & LIVE TELEMETRY HUD ══════════════════
  const raycaster = new THREE.Raycaster();
  const mouse = new THREE.Vector2();
  let pointerDownPos = { x: 0, y: 0 };
  let selectedHighlightBox = null;
  const selectionBaseScale = new THREE.Vector3(1, 1, 1);
  let selectionPulsePhase = 0;

  const EQUIP_CAMERA_TARGETS = {
    cyclones: { pos: new THREE.Vector3(-10, 22, -35), look: new THREE.Vector3(-6, 6, -68) },
    cartridge_filters: { pos: new THREE.Vector3(-18, 18, -42), look: new THREE.Vector3(-12, 4, -68) },
    turbo_compressors: { pos: new THREE.Vector3(-22, 26, 2), look: new THREE.Vector3(-22, 8, 30) },
    compressor_building: { pos: new THREE.Vector3(-25, 36, -10), look: new THREE.Vector3(-25, 12, 30) },
    air_coolers: { pos: new THREE.Vector3(30, 28, -50), look: new THREE.Vector3(30, 10, -80) },
    station_recycle: { pos: new THREE.Vector3(50, 16, 10), look: new THREE.Vector3(45, 2, -14) },
    cooler_bypass: { pos: new THREE.Vector3(20, 20, -60), look: new THREE.Vector3(20, 6, -80) },
    condensate_system: { pos: new THREE.Vector3(25, 12, -45), look: new THREE.Vector3(25, 2, -68) },
    safety_relief: { pos: new THREE.Vector3(-24, 18, -28), look: new THREE.Vector3(-24, 6, -48) },
    esd_valves: { pos: new THREE.Vector3(-46, 18, -28), look: new THREE.Vector3(-46, 6, -48) },
    ultrasonic_meter: { pos: new THREE.Vector3(-74, 15, -30), look: new THREE.Vector3(-74, 4, -48) },
    pig_receiver: { pos: new THREE.Vector3(-214, 22, -86), look: new THREE.Vector3(-196, 2, -86) },
    pig_launcher: { pos: new THREE.Vector3(-214, 22, -58), look: new THREE.Vector3(-196, 2, -58) },
    tiein: { pos: new THREE.Vector3(-85, 20, -80), look: new THREE.Vector3(-85, 2, -104) },
    anti_surge: { pos: new THREE.Vector3(-22, 20, -8), look: new THREE.Vector3(-22, 2, -18) },
    control_building: { pos: new THREE.Vector3(-30, 24, 60), look: new THREE.Vector3(-30, 8, 90) },
    generator_building: { pos: new THREE.Vector3(6, 22, 60), look: new THREE.Vector3(6, 5, 92) },
    air_compressor_building: { pos: new THREE.Vector3(92, 20, 60), look: new THREE.Vector3(92, 5, 88) },
    guard_shelter: { pos: new THREE.Vector3(110, 14, 20), look: new THREE.Vector3(110, 3, 41) },
    admin_building: { pos: new THREE.Vector3(146, 26, 56), look: new THREE.Vector3(146, 6, 92) },
  };

  function buildEquipmentTelemetryHtml(key) {
    let tag = "EKİPMAN";
    let sub = "Proses Ekipmanı";
    let rows = [];
    const statusBadge = `<span style="background: rgba(16,185,129,0.2); color: #34d399; border: 1px solid #10b981; padding: 1px 7px; border-radius: 8px; font-size: 9.5px; font-weight: 700;">🟢 DEVREDE (ONLINE)</span>`;

    if (key === "cyclones") {
      tag = `V-101 .. V-10${numCyclones}`;
      sub = `MFS Çoklu Siklon Seperatör Grubu (${numCyclones} Ünite)`;
      rows = [
        ["Proses Basıncı:", `${sm.suction_pressure_bar || 45.0} bar(a)`],
        ["Basınç Düşümü (ΔP):", `${eq.cyclones?.pressure_drop_bar || 0.15} bar`],
        ["Giriş Sıcaklığı:", `${sm.suction_temp_c || 15.0} °C`],
        ["Ünite Başına Debi:", `${eq.cyclones?.flow_per_unit_kgs || (sm.total_mass_flow_kgs / numCyclones).toFixed(1)} kg/s`],
        ["Sıvı/Katı Ayırma:", `> %99.5 (> 10 µm damlacık)`],
        ["Giriş Branşmanı:", `${eq.cyclones?.inlet_pipe_size || '30" NPS'} (${suctLine.pipe_material || 'API 5L X70'})`],
        ["Konfigürasyon:", `${eq.cyclones?.operating_count || (numCyclones - 1)} Aktif + 1 Otomatik Yedek`],
        ["Drenaj Çıkışı:", `LCV Seviye Kontrol Vanası ➔ TK-101`],
      ];
    } else if (key === "cartridge_filters") {
      tag = `F-101 .. F-10${numFilters}`;
      sub = `CFS Kartuş Filtre Seperatör Grubu (${numFilters} Ünite)`;
      rows = [
        ["Giriş / Çıkış Basıncı:", `${(sm.suction_pressure_bar - 0.15).toFixed(2)} → ${(sm.suction_pressure_bar - 0.25).toFixed(2)} bar(a)`],
        ["Temiz Filtre ΔP:", `${eq.cartridge_filters?.clean_dp_bar || 0.10} bar (Maks: 0.70 bar)`],
        ["Filtreleme Hassasiyeti:", `0.3 µm (%99.98 aerosol tutma)`],
        ["Ünite Başına Debi:", `${eq.cartridge_filters?.flow_per_unit_kgs || (sm.total_mass_flow_kgs / numFilters).toFixed(1)} kg/s`],
        ["Giriş Branşmanı:", `${eq.cartridge_filters?.inlet_pipe_size || '30" NPS'}`],
        ["Konfigürasyon:", `${eq.cartridge_filters?.operating_count || (numFilters - 1)} Aktif + 1 Yedek`],
        ["Diferansiyel Basınç:", `PDT Basınç Transmiteri Aktif`],
      ];
    } else if (key === "turbo_compressors") {
      tag = `C-101 .. C-10${numComps}`;
      sub = `API 617 Santrifüj Kompresör & Gaz Türbini Trenleri`;
      const pwrKw = Math.round(eq.turbo_compressors?.power_per_unit_kw || (sm.total_power_mw * 1000 / numComps));
      rows = [
        ["Emiş / Basma Basıncı:", `${(sm.suction_pressure_bar - 0.25).toFixed(1)} → ${sm.discharge_pressure_bar || 75.0} bar(a)`],
        ["Basınç Oranı (PR):", `${((sm.discharge_pressure_bar || 75.0) / Math.max(1, (sm.suction_pressure_bar - 0.25))).toFixed(2)} : 1`],
        ["Emiş / Basma Sıcaklığı:", `${sm.suction_temp_c || 15.0} °C → ${eq.air_coolers?.inlet_temp_c || 68.0} °C`],
        ["Tren Başına Şaft Gücü:", `${pwrKw.toLocaleString()} kW (${(pwrKw / 1000).toFixed(2)} MW)`],
        ["Tren Başına Gaz Debisi:", `${eq.turbo_compressors?.flow_per_unit_kgs || (sm.total_mass_flow_kgs / numComps).toFixed(1)} kg/s`],
        ["Tren Başına Yakıt:", `${(pwrKw * 0.195).toFixed(1)} kg/h (~${((pwrKw * 0.195)/0.772).toFixed(0)} Sm³/h)`],
        ["Nozul Ölçüsü:", `${eq.turbo_compressors?.suction_nozzle_size_in || '10"'} / ${eq.turbo_compressors?.discharge_nozzle_size_in || '6"'}`],
        ["Anti-Surge Vanası (ASV):", `ASV ${eq.turbo_compressors?.anti_surge_valve_size_in || 12}" (< ${eq.turbo_compressors?.anti_surge_stroke_time_s || 1.5}s Stroking)`],
        ["Surge Sınır Debisi:", `${eq.turbo_compressors?.surge_limit_flow_kgs || (sm.total_mass_flow_kgs / numComps * 0.65).toFixed(1)} kg/s`],
        ["Yedeklilik Modeli:", `${eq.turbo_compressors?.operating_count || (numComps - 1)} Aktif + 1 Hazır Yedek (N+1)`],
      ];
      const asvSizing = eq.turbo_compressors?.anti_surge_valve_sizing;
      if (asvSizing) {
        rows.push(["ASV IEC 60534 Boyut:", `${asvSizing.valve_inch} • Cv ${Number(asvSizing.required_cv || 0).toFixed(1)} • Açıklık %${Number(asvSizing.opening_percent || 0).toFixed(1)}`]);
      }
    } else if (key === "compressor_building") {
      tag = `BLDG-01`;
      sub = `Kompresör Ünite Binası & Akustik Mahfaza`;
      rows = [
        ["Boyutlar (G x U x Y):", `${eq.compressor_building?.width_m || 24}m x ${eq.compressor_building?.length_m || 68}m x ${eq.compressor_building?.height_m || 14}m`],
        ["Taban Alanı:", `${eq.compressor_building?.area_m2 || 1632} m²`],
        ["Tavan Vinci:", `${eq.compressor_building?.crane_capacity_tons || 15} Ton Köprülü Gezer Vinç`],
        ["Akustik Ses Düzeyi:", `< 85 dBA @ 1m (Çift Kat Taşyünü)`],
        ["Yangın & Gaz Güvenliği:", `%20 LEL IR Dedektörler + Otomatik CO₂`],
        ["HVAC & Havalandırma:", `Basınçlandırılmış Ex-Proof Hava Besleme`],
      ];
    } else if (key === "air_coolers") {
      tag = `E-101`;
      sub = `Fin-Fan Doğal Gaz Hava Soğutucu Bankı (${numCoolerBays} Bay)`;
      rows = [
        ["Giriş Sıcaklığı (Basma):", `${eq.air_coolers?.inlet_temp_c || 68.0} °C`],
        ["Çıkış Sıcaklığı (Hat):", `${eq.air_coolers?.outlet_temp_c || 38.0} °C (Boru kaplama limiti)`],
        ["Toplam Isıl Yük:", `${eq.air_coolers?.total_heat_duty_mw || 14.8} MWth`],
        ["Fan Konfigürasyonu:", `${eq.air_coolers?.total_fans || (numCoolerBays * 2)} Adet Induced-Draft VFD Fan`],
        ["Gaz Basınç Kaybı (ΔP):", `${eq.air_coolers?.pressure_drop_bar || 0.45} bar`],
        ["TCV By-Pass Hattı:", `Aktif (Kış aylarında sıcak gaz karıştırma - Note 17)`],
        ["Kolektör Boru Çapı:", `${eq.air_coolers?.inlet_header_pipe_size || '48"'} / Riser: ${eq.air_coolers?.riser_pipe_size || '30"'}`],
      ];
      const coolerDesign = eq.air_coolers?.detailed_design;
      if (coolerDesign) {
        rows.push(
          ["API 661 Gerekli Alan:", `${Number(coolerDesign.required_area_m2 || 0).toFixed(1)} m²`],
          ["API 661 Gerçek Alan:", `${Number(coolerDesign.actual_area_m2 || 0).toFixed(1)} m² (%${Number(coolerDesign.overdesign_pct || 0).toFixed(1)} overdesign)`],
          ["Fan Gücü / Uç Hızı:", `${Number(coolerDesign.fan_power_kw || 0).toFixed(1)} kW • ${Number(coolerDesign.fan_tip_speed_ms || 0).toFixed(1)} m/s`]
        );
      }
      const tcvSizing = eq.air_coolers?.cooler_bypass_valve_sizing;
      if (tcvSizing) {
        rows.push(["TCV IEC 60534 Boyut:", `${tcvSizing.valve_inch} • Cv ${Number(tcvSizing.required_cv || 0).toFixed(1)}`]);
      }
    } else if (key === "station_recycle") {
      tag = `RECYCLE-01`;
      sub = `${eq.station_recycle?.pipe_size || '48"'} İstasyon Ana Sirkülasyon & Purge Hattı (Note 13)`;
      rows = [
        ["Boru Çapı & Malzeme:", `${eq.station_recycle?.pipe_size || '48"'} NPS (${suctLine.pipe_material || 'API 5L X70'})`],
        ["Sirkülasyon Kapasitesi:", `${eq.station_recycle?.max_recirculation_capacity_kgs || 120} kg/s (%100 İstasyon Debisi)`],
        ["Kontrol Vanası:", `PCV Kademeli Basınç Düşürücü Düşük Gürültülü Trim`],
        ["İşlev:", `Hat süpürme (purge), ilk devreye alma & rölanti`],
      ];
      const pcvSizing = eq.station_recycle?.pcv_sizing;
      if (pcvSizing) {
        rows.push(["PCV IEC 60534 Boyut:", `${pcvSizing.valve_inch} • Cv ${Number(pcvSizing.required_cv || 0).toFixed(1)} • Açıklık %${Number(pcvSizing.opening_percent || 0).toFixed(1)}`]);
      }
    } else if (key === "safety_relief") {
      const psv = eq.safety_relief_and_blowdown || {};
      const auto = psv.auto_inputs || {};
      const psvSizing = psv.psv_sizing || {};
      const compStr = auto.gas_comp
        ? Object.entries(auto.gas_comp)
            .filter(([, v]) => Number(v) > 0)
            .slice(0, 4)
            .map(([k, v]) => `${k} %${Number(v).toFixed(1)}`)
            .join(", ")
        : "CH4 %85, C2H6 %7...";
      tag = `PSV-101..10${psv.psv_count || 2} (API 520 / 526)`;
      sub = `Discharge Header Dikey Riser Emniyet Tahliye Vanaları`;
      rows = [
        ["Gaz Bileşimi (Programdan):", `${escapeHtml(compStr)} • MW ${auto.mw || sm.gas_mw || 18.95} g/mol`],
        ["EOS / Z / k (Programdan):", `${String(auto.eos_model || sm.eos_model || "coolprop").toUpperCase()} • Z=${auto.z ?? psvSizing.z_used ?? 0.87} • k=${auto.k ?? psvSizing.k_used ?? 1.55}`],
        ["Vana Giriş P / T (Programdan):", `${auto.p_upstream_bar || sm.discharge_pressure_bar || 75} bar(a) • ${auto.t_relieving_c || eq.air_coolers?.inlet_temp_c || 50} °C`],
        ["Toplam Tahliye Debisi:", `${auto.mass_flow_total_kgs || sm.total_mass_flow_kgs || 441.8} kg/s`],
        ["Toplam / Vana Başına Alan:", `${Number(psvSizing.required_area_total_sqin || psvSizing.required_area_sqin || 0).toFixed(3)} in² / ${Number(psvSizing.required_area_sqin || 0).toFixed(3)} in²`],
        ["Hesaplanan Eşdeğer Çap:", `Ø${Number(psvSizing.required_diameter_in || 0).toFixed(2)}" (Orifis Ø${Number(psvSizing.selected_orifice_diameter_in || 0).toFixed(2)}")`],
        ["Seçilen API 526 Orifis / Flanş:", `${psvSizing.selected_orifice || "-"} (${psvSizing.inlet_flange_in || '8"'} × ${psvSizing.outlet_flange_in || '10"'})`],
        ["Önerilen Min. PSV Sayısı:", `${psvSizing.recommended_duty_count || 1} Duty + 1 Standby (Toplam ${psvSizing.recommended_total_count || 2})`],
      ];
    } else if (key === "esd_valves") {
      const esd = eq.esd_sizing || {};
      const auto = esd.auto_inputs || {};
      const suct = esd.suction || {};
      const disch = esd.discharge || {};
      const compStr = auto.gas_comp
        ? Object.entries(auto.gas_comp)
            .filter(([, v]) => Number(v) > 0)
            .slice(0, 4)
            .map(([k, v]) => `${k} %${Number(v).toFixed(1)}`)
            .join(", ")
        : "CH4 %85, C2H6 %7...";
      tag = `ESD / BDV-101..10${esd.esd_count || 2} (IEC 60534)`;
      sub = `Discharge Header Dikey Riser & Hat Acil Kapatma Vanaları`;
      rows = [
        ["Gaz Bileşimi (Programdan):", `${escapeHtml(compStr)} • MW ${auto.mw || sm.gas_mw || 18.95} g/mol`],
        ["Basma Giriş P / T (Programdan):", `${auto.discharge_p_in_bar || sm.discharge_pressure_bar || 74.6} bar(a) • ${auto.discharge_t_c || 45.0} °C`],
        ["Emiş Giriş P / T (Programdan):", `${auto.suction_p_in_bar || sm.suction_pressure_bar || 50.7} bar(a) • ${auto.suction_t_c || 19.0} °C`],
        ["Vana Başına / Toplam Debi:", `${disch.flow_per_valve_kgs || sm.total_mass_flow_kgs || 441.8} kg/s / ${auto.mass_flow_total_kgs || sm.total_mass_flow_kgs || 441.8} kg/s`],
        ["ESD Gerekli Cv (Vana / Toplam):", `Cv ${Number(disch.required_cv || 0).toFixed(0)} / Toplam Cv ${Number(disch.required_cv_total || disch.required_cv || 0).toFixed(0)}`],
        ["Hesaplanan Aerodinamik Çap:", `Basma: ${disch.calculated_size_in || disch.selected_size_in || '-'}" (DN${disch.calculated_dn_mm || disch.selected_dn_mm || '-'}) • Emiş: ${suct.calculated_size_in || suct.selected_size_in || '-'}"`],
        ["Tam Geçişli Hat ESD Çapı:", `Basma: ${disch.selected_size_in || '-'}" • Emiş: ${suct.selected_size_in || '-'}"`],
        ["Önerilen Paralel ESD Sayısı:", `${disch.recommended_duty_count || 1} Aktif (Kurulu: ${esd.esd_count || 2} Adet)`],
      ];
    } else if (key === "ultrasonic_meter") {
      const usm = eq.ultrasonic_meter || {};
      tag = `${usm.tag || "FT-401"} • ULTRASONIC METER`;
      sub = `${usm.meter_type || "8-Path Chordal Ultrasonic Flow Meter (AGA-9)"}`;
      rows = [
        ["Anma Çapı (Header):", `${usm.nominal_size_in || dischLine.nominal_size_in || '40"'}`],
        ["Hat Basıncı & Sıcaklığı:", `${usm.pressure_bar_a || sm.discharge_pressure_bar || 74.6} bar(a) • ${usm.temperature_c || 45.0} °C`],
        ["Kütlesel Debi:", `${usm.mass_flow_kgs || sm.total_mass_flow_kgs || 441.8} kg/s`],
        ["Gerçek Hacimsel Debi (Q_act):", `${usm.actual_volumetric_flow_m3h || 26500} m³/h (ACMH)`],
        ["Standart Debi:", `${usm.standard_flow_mmscmd || sm.volumetric_flow_mmscmd || 47.5} MMSCMD`],
        ["Hat Gaz Hızı:", `${usm.gas_velocity_ms || dischLine.actual_velocity_ms || 15.8} m/s (Maks: ${usm.max_recommended_velocity_ms || 25.0} m/s)`],
        ["Ses Hızı (Speed of Sound):", `${usm.speed_of_sound_ms || 410.0} m/s • ρ=${usm.gas_density_kgm3 || 60.0} kg/m³`],
        ["Doğruluk & Düz Boru:", `${usm.accuracy_class || "±0.15%"} • ${usm.straight_run_requirement || "10D / 5D"}`],
      ];
    } else if (key === "condensate_system") {
      tag = `TK-101`;
      sub = `Kondensat Sıvı Toplama ve Depolama Sistemi`;
      rows = [
        ["Tank Hacmi:", `${eq.condensate_system?.collection_tank_volume_m3 || 15} m³`],
        ["Tahmini Sıvı Üretimi:", `${eq.condensate_system?.estimated_liquid_rate_m3h || 0.45} m³/h`],
        ["Drenaj Kaynağı:", `MFS & CFS Seviye Kontrol Vanaları (LCV)`],
        ["Vent Koruması:", `Alev Tutuculu Atmosferik Havalık (Note 14)`],
      ];
    } else if (key === "pig_receiver") {
      tag = `PIG-R-56"x48"`;
      sub = `Suction Pig Alıcı Kovanı (Ana Hat Emişi)`;
      rows = [
        ["Kovan Ölçüsü:", `PIG-R 56"x48" (ANSI Class 600)`],
        ["İşletme Basıncı:", `${sm.suction_pressure_bar || 45.0} bar(a)`],
        ["Hızlı Açılır Kapak:", `Band-lock / Clamp tipi • PIG-L kapısına dönük`],
        ["Kicker / Dengeleme:", `PIG by-pass hattına receiver & dengeleme bağlantısı`],
        ["İzolasyon:", `Full-Bore Motorlu Küresel Vana (MOV/ESDV)`],
      ];
    } else if (key === "cooler_bypass") {
      tag = `TCV-101 BY-PASS`;
      sub = `Gaz Soğutucu By-Pass & Sıcaklık Kontrol Hattı (Note 17)`;
      rows = [
        ["Vana Tipi:", `TCV Sıcaklık Kontrollü Oransal Vana`],
        ["By-Pass Debisi:", `Maks. %35 İstasyon Debisi`],
        ["Birincil Kontrol:", `Hava Soğutucu Fanlarında VFD Frekans Kontrolü`],
        ["İkincil Kontrol:", `TCV Sıcak Gaz Karıştırma Baypası`],
        ["Boru Malzemesi:", `${suctLine.pipe_material || 'API 5L X70'}`],
        ["Görev:", `Kış aylarında / düşük debide aşırı soğumayı önlemek`],
      ];
      const tcv = eq.air_coolers?.cooler_bypass_valve_sizing;
      if (tcv) {
        rows.push(["TCV IEC 60534 Boyut:", `${tcv.valve_inch} • Cv ${Number(tcv.required_cv || 0).toFixed(1)} • Açıklık %${Number(tcv.opening_percent || 0).toFixed(1)}`]);
      }
    } else if (key === "anti_surge") {
      tag = `ASV-101`;
      sub = `Hızlı Anti-Surge Geri Dönüş Valfi & Sıcak Gaz Loop`;
      const asvSize = eq.turbo_compressors?.anti_surge_valve_size_in || 12;
      rows = [
        ["Vana Çapı:", `ASV ${asvSize}" (Küresel / Kafesli Trim)`],
        ["Bağlantı:", `ASV loop → anti-surge header → suction header`],
        ["ASV Loop Çapı:", `${antiSurgeLine.nominal_size_in || '5"'} (${antiSurgeLine.flow_kgs || 8.16} kg/s)`],
        ["ASV Header Çapı:", `${pLines.station_recycle?.nominal_size_in || '6"'} (mevcut ara header)`],
        ["Stroking Süresi:", `< ${eq.turbo_compressors?.anti_surge_stroke_time_s || 1.5} saniye (Tam Açılma)`],
        ["Surge Sınır Debisi:", `${eq.turbo_compressors?.surge_limit_flow_kgs || (sm.total_mass_flow_kgs / numComps * 0.65).toFixed(1)} kg/s`],
        ["Kontrol Mantığı:", `SLL + %10 ASCL Emniyet Çizgisi`],
        ["Akustik İyileştirme:", `Kademeli difüzör trim / düşük gürültülü trim`],
      ];
      const asv = eq.turbo_compressors?.anti_surge_valve_sizing;
      if (asv) {
        rows.push(["IEC 60534 Boyut:", `${asv.valve_inch} • Cv ${Number(asv.required_cv || 0).toFixed(1)} • Açıklık %${Number(asv.opening_percent || 0).toFixed(1)}`]);
      }
    } else if (key === "control_building") {
      tag = `BLDG-CTRL / SCADA`;
      sub = `Merkezi Kontrol ve Yardımcı Tesisler Binası`;
      rows = [
        ["Kontrol Mimarisi:", `DCS & SCADA Yedekli Çift Sunucu`],
        ["Emniyet Sistemi (SIS):", `IEC 61508 / 61511 SIL-3 Emniyet PLC`],
        ["Kesintisiz Güç (UPS):", `2 x %100 Statik UPS & Akü Grubu (4 Saat Otonomi)`],
        ["Yangın & Gaz (F&G):", `%20 LEL IR Dedektörler + UV/IR Alev Algılama`],
        ["Pozitif Basınç (HVAC):", `Ex-Proof Pozitif Basınçlı İklimlendirme`],
      ];
    } else if (key === "generator_building") {
      tag = `BLDG-GEN & MV`;
      sub = `Acil Durum Jeneratörü & O.G. Şalt Binası`;
      rows = [
        ["Jeneratör Tipi:", `Dizel Motorlu Standby Acil Durum Jeneratör Seti`],
        ["Gerilim Seviyesi:", `6.6 kV Orta Gerilim / 400 V Alçak Gerilim`],
        ["Transfer Süresi (ATS):", `< 15 Saniye Otomatik Şebeke Transferi`],
        ["Şalt Hücreleri:", `SF6 Gaz Yalıtımlı / Vakumlu O.G. Kesiciler`],
      ];
    } else if (key === "air_compressor_building") {
      tag = `BLDG-UTIL / AIR`;
      sub = `Enstrüman ve Tesis Servis Havası Binası`;
      rows = [
        ["Hava Basıncı:", `7.5 - 10.0 bar(g) Basınçlı Enstrüman Havası`],
        ["Kompresör Tipi:", `2 x %100 Yağsız Vidalı Kompresör (1 Asil + 1 Yedek)`],
        ["Hava Kalitesi:", `ISO 8573-1 Sınıf 1.2.1 (-40°C Çiy Noktası)`],
        ["Hava Tankı & Kurutucu:", `Dikey Hava Alıcı Kap + Çift Kuleli Desikant`],
      ];
    } else if (key === "guard_shelter") {
      tag = `SHELTER-GUARD`;
      sub = `Tesis Ana Güvenlik & Giriş-Çıkış Nizamiyesi`;
      rows = [
        ["Güvenlik Seviyesi:", `BOTAŞ Kritik Tesis Çevre Güvenlik Standardı`],
        ["Giriş Kontrolü:", `Otomatik Bariyer + CCTV Plaka Tanıma Sistemi`],
        ["Çevre Güvenliği:", `360° Termal ve Optik Gece Görüş Kameraları`],
      ];
    } else if (key === "admin_building") {
      tag = `BLDG-ADMIN / WKSH`;
      sub = `İdari Yönetim ve Bakım Atölyesi Binası`;
      rows = [
        ["İşlev Alanları:", `Saha Mühendislik Ofisleri, Laboratuvar, Atölye`],
        ["Bakım Vinci:", `3 Tonluk Gezer Köprülü Vinç`],
        ["Kritik Yedek Parça:", `Vana Trimleri, Mekanik Salmastralar & Filtre Stoğu`],
      ];
    } else if (key === "pig_launcher" || key === "tiein") {
      tag = `PIG-R / PIG-L`;
      sub = `${suctLine.nominal_size_in || '48"'} Doğal Gaz Ana Hat & Pig Kovanları`;
      rows = [
        ["Ana Hat Çapı:", `${suctLine.nominal_size_in || '48"'} NPS (OD: ${suctLine.od_mm || 1219} mm) ${suctLine.pipe_material || 'API 5L X70'}`],
        ["Kovan Ölçüsü:", `PIG-R 56"x48" / PIG-L 56"x48" (ANSI Class 900)`],
        ["Oryantasyon:", `Kapaklar karşılıklı • Batarya limiti batı sahasında`],
        ["İşletme Basıncı:", `${sm.suction_pressure_bar || 45} bar(a) Emiş • ${sm.discharge_pressure_bar || 75} bar(a) Basma`],
        ["By-Pass / Kicker:", `Ortak by-pass hattı • hat vanası • PIG-L kicker bağlantısı`],
      ];
    } else {
      tag = key.toUpperCase();
      sub = `İstasyon Yardımcı Tesisi / Ünitesi`;
      rows = [
        ["Durum:", `Aktif`],
        ["Standart:", `BOTAŞ Standart Şartnamesi`],
      ];
    }

    let interactiveFormHtml = "";
    if (key === "safety_relief") {
      const psv = eq.safety_relief_and_blowdown || {};
      const psvSetVal = psv.psv_set_pressure_bar ?? 82.5;
      const psvOverVal = psv.psv_overpressure_pct ?? 10;
      const psvBackVal = psv.psv_back_pressure_bar ?? 1.01325;
      const psvTypeVal = psv.psv_valve_type || "conventional";
      const psvCountVal = Number(psv.psv_count || 2);
      const psvDutyVal = Number(psv.psv_duty_count || 1);
      interactiveFormHtml = `
        <div style="background: rgba(15,23,42,0.85); border: 1px solid rgba(56,189,248,0.35); border-radius: 6px; padding: 8px; margin-bottom: 10px;">
          <div style="font-size: 10.5px; font-weight: 700; color: #38bdf8; margin-bottom: 6px;">
            🛡️ PSV Sayı &amp; Çap Hesaplama Girdileri (Kullanıcı Girişi)
          </div>
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 6px; font-size: 10px;">
            <label style="color:#cbd5e1; display:flex; flex-direction:column; gap:2px;">
              Toplam PSV Adedi
              <select id="hud-psv-count" style="background:#0f172a; color:#f8fafc; border:1px solid #334155; border-radius:4px; padding:2px 4px; font-size:10px;">
                ${[1, 2, 3, 4].map((n) => `<option value="${n}" ${psvCountVal === n ? "selected" : ""}>${n} Adet</option>`).join("")}
              </select>
            </label>
            <label style="color:#cbd5e1; display:flex; flex-direction:column; gap:2px;">
              Eşzamanlı (Duty) PSV
              <select id="hud-psv-duty" style="background:#0f172a; color:#f8fafc; border:1px solid #334155; border-radius:4px; padding:2px 4px; font-size:10px;">
                ${[1, 2, 3, 4].map((n) => `<option value="${n}" ${psvDutyVal === n ? "selected" : ""}>${n} Duty</option>`).join("")}
              </select>
            </label>
            <label style="color:#cbd5e1; display:flex; flex-direction:column; gap:2px;">
              Set Basıncı (bar g)
              <input type="number" id="hud-psv-set" step="0.5" value="${psvSetVal}" style="background:#0f172a; color:#f8fafc; border:1px solid #334155; border-radius:4px; padding:2px 4px; font-size:10px; font-family:monospace;" />
            </label>
            <label style="color:#cbd5e1; display:flex; flex-direction:column; gap:2px;">
              Aşırı Basınç (%)
              <input type="number" id="hud-psv-over" step="1" min="1" max="25" value="${psvOverVal}" style="background:#0f172a; color:#f8fafc; border:1px solid #334155; border-radius:4px; padding:2px 4px; font-size:10px; font-family:monospace;" />
            </label>
            <label style="color:#cbd5e1; display:flex; flex-direction:column; gap:2px;">
              Karşı Basınç (bar a)
              <input type="number" id="hud-psv-back" step="0.05" value="${psvBackVal}" style="background:#0f172a; color:#f8fafc; border:1px solid #334155; border-radius:4px; padding:2px 4px; font-size:10px; font-family:monospace;" />
            </label>
            <label style="color:#cbd5e1; display:flex; flex-direction:column; gap:2px;">
              PSV Vana Tipi
              <select id="hud-psv-type" style="background:#0f172a; color:#f8fafc; border:1px solid #334155; border-radius:4px; padding:2px 4px; font-size:10px;">
                <option value="conventional" ${psvTypeVal === "conventional" ? "selected" : ""}>Conventional</option>
                <option value="balanced_bellows" ${psvTypeVal === "balanced_bellows" ? "selected" : ""}>Balanced Bellows</option>
                <option value="pilot" ${psvTypeVal === "pilot" ? "selected" : ""}>Pilot Operated</option>
              </select>
            </label>
          </div>
          <button id="btn-hud-calc-psv" style="margin-top: 7px; width: 100%; background: #059669; color: #fff; border: 1px solid #34d399; border-radius: 5px; padding: 5px 8px; font-size: 10.5px; font-weight: 700; cursor: pointer;">
            🧮 PSV Sayı &amp; Çapını Hesapla
          </button>
        </div>
      `;
    } else if (key === "esd_valves") {
      const esd = eq.esd_sizing || {};
      const esdCountVal = Number(esd.esd_count || 2);
      const esdDutyVal = Number(esd.esd_duty_count || 1);
      const esdDpVal = esd.allowable_dp_bar ?? 0.5;
      const esdTypeVal = esd.valve_type || "full_bore_ball";
      const bdvTimeVal = esd.depressurization_time_min ?? 15;
      interactiveFormHtml = `
        <div style="background: rgba(15,23,42,0.85); border: 1px solid rgba(239,68,68,0.40); border-radius: 6px; padding: 8px; margin-bottom: 10px;">
          <div style="font-size: 10.5px; font-weight: 700; color: #f87171; margin-bottom: 6px;">
            🚨 ESD / BDV Sayı &amp; Çap Hesaplama Girdileri (Kullanıcı Girişi)
          </div>
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 6px; font-size: 10px;">
            <label style="color:#cbd5e1; display:flex; flex-direction:column; gap:2px;">
              Toplam ESD/BDV Adedi
              <select id="hud-esd-count" style="background:#0f172a; color:#f8fafc; border:1px solid #334155; border-radius:4px; padding:2px 4px; font-size:10px;">
                ${[1, 2, 3, 4, 5, 6].map((n) => `<option value="${n}" ${esdCountVal === n ? "selected" : ""}>${n} Adet</option>`).join("")}
              </select>
            </label>
            <label style="color:#cbd5e1; display:flex; flex-direction:column; gap:2px;">
              Eşzamanlı Aktif ESD
              <select id="hud-esd-duty" style="background:#0f172a; color:#f8fafc; border:1px solid #334155; border-radius:4px; padding:2px 4px; font-size:10px;">
                ${[1, 2, 3, 4, 5, 6].map((n) => `<option value="${n}" ${esdDutyVal === n ? "selected" : ""}>${n} Aktif</option>`).join("")}
              </select>
            </label>
            <label style="color:#cbd5e1; display:flex; flex-direction:column; gap:2px;">
              İzin Verilen ΔP (bar)
              <input type="number" id="hud-esd-dp" step="0.05" min="0.05" value="${esdDpVal}" style="background:#0f172a; color:#f8fafc; border:1px solid #334155; border-radius:4px; padding:2px 4px; font-size:10px; font-family:monospace;" />
            </label>
            <label style="color:#cbd5e1; display:flex; flex-direction:column; gap:2px;">
              ESD Vana Tipi
              <select id="hud-esd-type" style="background:#0f172a; color:#f8fafc; border:1px solid #334155; border-radius:4px; padding:2px 4px; font-size:10px;">
                <option value="full_bore_ball" ${esdTypeVal === "full_bore_ball" ? "selected" : ""}>Full-Bore Ball</option>
                <option value="ball" ${esdTypeVal === "ball" ? "selected" : ""}>Ball</option>
                <option value="butterfly" ${esdTypeVal === "butterfly" ? "selected" : ""}>Butterfly</option>
                <option value="gate" ${esdTypeVal === "gate" ? "selected" : ""}>Gate</option>
              </select>
            </label>
            <label style="grid-column: 1 / -1; color:#cbd5e1; display:flex; justify-content:space-between; align-items:center; gap:6px;">
              <span>Hedef Boşaltma Süresi (dk, API 521)</span>
              <input type="number" id="hud-esd-bdv-time" step="1" min="1" max="60" value="${bdvTimeVal}" style="width:70px; background:#0f172a; color:#f8fafc; border:1px solid #334155; border-radius:4px; padding:2px 4px; font-size:10px; font-family:monospace;" />
            </label>
          </div>
          <button id="btn-hud-calc-esd" style="margin-top: 7px; width: 100%; background: #dc2626; color: #fff; border: 1px solid #f87171; border-radius: 5px; padding: 5px 8px; font-size: 10.5px; font-weight: 700; cursor: pointer;">
            🧮 ESD Sayı &amp; Çapını Hesapla
          </button>
        </div>
      `;
    }

    return `
      <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px; border-bottom: 1px solid rgba(255,255,255,0.12); padding-bottom: 6px;">
        <div>
          <div style="font-size: 13px; font-weight: 800; color: #38bdf8; letter-spacing: 0.5px;">${tag}</div>
          <div style="font-size: 10.5px; color: #94a3b8; margin-top: 1px;">${sub}</div>
        </div>
        <div style="display: flex; align-items: center; gap: 6px;">
          ${statusBadge}
          <button id="btn-close-telemetry-hud" aria-label="Telemetri kartını kapat" style="background: none; border: none; color: #94a3b8; cursor: pointer; font-size: 14px; padding: 0 4px; line-height: 1;">✕</button>
        </div>
      </div>

      <div style="background: rgba(0,0,0,0.25); border-radius: 6px; padding: 6px 8px; margin-bottom: 10px;">
        <table style="width: 100%; border-collapse: collapse; font-size: 10.5px;">
          <tbody>
            ${rows.map(([lbl, val]) => `
              <tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
                <td style="padding: 3px 0; color: #94a3b8;">${lbl}</td>
                <td style="padding: 3px 0; text-align: right; font-family: monospace; font-weight: 600; color: #f8fafc;">${val}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>

      ${interactiveFormHtml}

      <div style="display: flex; gap: 8px;">
        <button id="btn-telemetry-flyto" style="flex: 1; background: #0284c7; color: #fff; border: 1px solid #38bdf8; border-radius: 6px; padding: 5px 8px; font-size: 10.5px; font-weight: 600; cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 4px;">
          <span>🎯 Kamerayı Yaklaştır (Fly-To)</span>
        </button>
        ${TEARDOWN_KEYS.has(key) ? `<button id="btn-telemetry-teardown" style="flex: 1; background: #b45309; color: #fff; border: 1px solid #fbbf24; border-radius: 6px; padding: 5px 8px; font-size: 10.5px; font-weight: 700; cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 4px;"><span>🔧 Teardown Aç</span></button>` : ""}
      </div>
    `;
  }

  function buildPipeTelemetryHtml(pipeMeta) {
    const lineData = pLines[pipeMeta?.lineKey] || {};
    const tag = escapeHtml(pipeMeta?.lineTag || lineData.tag || "L-100");
    const unitSuffix = pipeMeta?.unitLabel ? ` • ${escapeHtml(pipeMeta.unitLabel)}` : "";
    const sub = `${escapeHtml(pipeMeta?.lineName || lineData.name || "Proses Borulaması")}${unitSuffix}`;
    const level = pipeMeta?.hierarchyLevel || lineData.hierarchy_level || "equipment_branch";
    const levelLabel = escapeHtml(pipeMeta?.hierarchyLabel || lineData.hierarchy_label || "Ekipman Borulaması");
    const badgeColors = level === "main_header"
      ? { bg: "rgba(245,158,11,0.20)", fg: "#fbbf24", border: "#f59e0b" }
      : level === "mainline_tie_in"
        ? { bg: "rgba(168,85,247,0.22)", fg: "#d8b4fe", border: "#a855f7" }
        : { bg: "rgba(16,185,129,0.20)", fg: "#34d399", border: "#10b981" };
    const hierarchyBadge = `<span style="background: ${badgeColors.bg}; color: ${badgeColors.fg}; border: 1px solid ${badgeColors.border}; padding: 1px 7px; border-radius: 8px; font-size: 9.5px; font-weight: 700;">${levelLabel}</span>`;

    const fromBound = escapeHtml(pipeMeta?.fromBoundary || lineData.from_boundary || "-");
    const toBound = escapeHtml(pipeMeta?.toBoundary || lineData.to_boundary || "-");
    const parentHdr = escapeHtml(
      pipeMeta?.parentHeader ||
      lineData.parent_header ||
      (level === "main_header" ? "Ana İstasyon Kollektör Omurgası (Suction = Discharge Ortak NPS)" : "Ana İletim Tie-In")
    );

    const nps = escapeHtml(lineData.nominal_size_in || "-");
    const od = Number(lineData.od_mm || 0);
    const sch = escapeHtml(lineData.schedule || "-");
    const thick = Number(lineData.wall_thickness_mm || 0);
    const treq = Number(lineData.min_required_thickness_mm || 0);
    const flow = Number(lineData.flow_kgs || 0);
    const press = Number(lineData.pressure_bar || 0);
    const vel = Number(lineData.actual_velocity_ms || 0);
    const evr = Number(lineData.erosion_ratio_pct || 0);
    const dp = Number(lineData.pressure_drop_bar_per_100m || 0);

    const rows = [
      ["Anma Çapı & OD:", `${nps} (${od ? od.toFixed(1) + " mm" : "-"} • Sch ${sch})`],
      ["Et Kalınlığı / Barlow:", `${thick ? thick.toFixed(2) + " mm" : "-"} (t_req: ${treq ? treq.toFixed(2) + " mm" : "-"})`],
      ["Tasarım Debisi & Basınç:", `${flow.toFixed(1)} kg/s @ ${press.toFixed(1)} bar(a)`],
      ["Gaz Hızı & Erozyon:", `${vel.toFixed(2)} m/s (%${evr.toFixed(1)} EVR)`],
      ["Birim Basınç Kaybı:", `${dp.toFixed(3)} bar / 100m`],
      ["Boru Malzemesi:", escapeHtml(lineData.pipe_material || suctLine.pipe_material || "API 5L X70")],
    ];

    return `
      <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px; border-bottom: 1px solid rgba(255,255,255,0.12); padding-bottom: 6px;">
        <div>
          <div style="font-size: 13px; font-weight: 800; color: #facc15; letter-spacing: 0.5px;">${tag}</div>
          <div style="font-size: 10.5px; color: #cbd5e1; margin-top: 1px;">${sub}</div>
        </div>
        <div style="display: flex; align-items: center; gap: 6px;">
          ${hierarchyBadge}
          <button id="btn-close-telemetry-hud" aria-label="Boru sınır kartını kapat" style="background: none; border: none; color: #94a3b8; cursor: pointer; font-size: 14px; padding: 0 4px; line-height: 1;">✕</button>
        </div>
      </div>

      <div style="background: rgba(15, 23, 42, 0.78); border: 1px solid rgba(56, 189, 248, 0.35); border-radius: 6px; padding: 6px 8px; margin-bottom: 8px; font-size: 10px; line-height: 1.45;">
        <div style="margin-bottom: 3px;"><span style="color: #94a3b8;">${escapeHtml(t("pipe_hud_start", uiLang))}</span> <strong style="color: #38bdf8;">${fromBound}</strong></div>
        <div style="margin-bottom: 3px;"><span style="color: #94a3b8;">${escapeHtml(t("pipe_hud_end", uiLang))}</span> <strong style="color: #fbbf24;">${toBound}</strong></div>
        <div><span style="color: #94a3b8;">${escapeHtml(t("pipe_hud_parent", uiLang))}</span> <span style="color: #e2e8f0; font-weight: 600;">${parentHdr}</span></div>
      </div>

      <div style="background: rgba(0,0,0,0.25); border-radius: 6px; padding: 6px 8px; margin-bottom: 10px;">
        <table style="width: 100%; border-collapse: collapse; font-size: 10.5px;">
          <tbody>
            ${rows.map(([lbl, val]) => `
              <tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
                <td style="padding: 3px 0; color: #94a3b8;">${lbl}</td>
                <td style="padding: 3px 0; text-align: right; font-family: monospace; font-weight: 600; color: #f8fafc;">${val}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>

      <div style="display: flex; gap: 8px;">
        <button id="btn-pipe-flyto" style="flex: 1; background: #0284c7; color: #fff; border: 1px solid #38bdf8; border-radius: 6px; padding: 5px 8px; font-size: 10.5px; font-weight: 600; cursor: pointer;">
          🎯 Hatta Yaklaş (Fly-To)
        </button>
        ${pipeMeta?.equipKey ? `<button id="btn-pipe-open-equip" style="flex: 1; background: #334155; color: #f8fafc; border: 1px solid rgba(255,255,255,0.22); border-radius: 6px; padding: 5px 8px; font-size: 10.5px; font-weight: 600; cursor: pointer;">${escapeHtml(t("pipe_hud_open_equip", uiLang))}</button>` : ""}
      </div>
    `;
  }

  function ensureSelectionHighlightBox() {
    if (!selectedHighlightBox) {
      const boxGeo = new THREE.BoxGeometry(1, 1, 1);
      const edgesGeo = new THREE.EdgesGeometry(boxGeo);
      const edgesMat = new THREE.LineBasicMaterial({ color: 0x00f0ff, linewidth: 2.5, transparent: true, opacity: 0.9 });
      selectedHighlightBox = new THREE.LineSegments(edgesGeo, edgesMat);
      selectedHighlightBox.renderOrder = 999;
      scene.add(selectedHighlightBox);
    }
    return selectedHighlightBox;
  }

  function selectAndInspectPipe(pipeMeta, targetObject = null) {
    if (!pipeMeta || !pipeMeta.lineKey) return false;

    ensureSelectionHighlightBox();

    // Compute combined bounding box for main headers (entire spine) or clicked route group
    const bbox = new THREE.Box3();
    const routeGroups = pipeRouteGroupsByLineKey.get(pipeMeta.lineKey) || [];
    if (pipeMeta.hierarchyLevel === "main_header" && routeGroups.length > 0) {
      routeGroups.forEach((grp) => bbox.expandByObject(grp));
    } else if (targetObject) {
      let rootGroup = targetObject;
      while (rootGroup && rootGroup.parent && rootGroup.parent !== scene) {
        rootGroup = rootGroup.parent;
      }
      bbox.setFromObject(rootGroup || targetObject);
    } else if (routeGroups.length > 0) {
      routeGroups.forEach((grp) => bbox.expandByObject(grp));
    }

    const focusCenter = new THREE.Vector3(-25, 3, -32);
    const focusSize = new THREE.Vector3(20, 6, 20);
    if (!bbox.isEmpty()) {
      bbox.getSize(focusSize);
      bbox.getCenter(focusCenter);
      selectedHighlightBox.position.copy(focusCenter);
      selectionBaseScale.set(
        Math.max(2.0, focusSize.x * 1.06),
        Math.max(2.0, focusSize.y * 1.15),
        Math.max(2.0, focusSize.z * 1.06)
      );
      selectedHighlightBox.scale.copy(selectionBaseScale);
      selectedHighlightBox.visible = true;
    }

    const hudEl = container.querySelector("#equip-telemetry-hud");
    if (hudEl) {
      hudEl.innerHTML = buildPipeTelemetryHtml(pipeMeta);
      hudEl.style.display = "block";
      rootEl?.setAttribute("data-inspect", "1");

      hudEl.querySelector("#btn-close-telemetry-hud")?.addEventListener("click", () => {
        hudEl.style.display = "none";
        rootEl?.removeAttribute("data-inspect");
        if (selectedHighlightBox) selectedHighlightBox.visible = false;
      });

      hudEl.querySelector("#btn-pipe-flyto")?.addEventListener("click", () => {
        const span = Math.max(18, Math.hypot(focusSize.x, focusSize.z) * 0.55);
        flyToCamera(
          new THREE.Vector3(focusCenter.x - span * 0.45, Math.max(18, span * 0.55), focusCenter.z - span * 0.65),
          focusCenter.clone()
        );
      });

      hudEl.querySelector("#btn-pipe-open-equip")?.addEventListener("click", () => {
        const eqKey = pipeMeta.equipKey;
        if (!eqKey) return;
        const eqObj =
          interactiveObjects.find((o) => o.userData?.equipKey === eqKey && !o.userData?.isPipeMesh) ||
          interactiveObjects.find((o) => o.userData?.equipKey === eqKey);
        if (eqObj) {
          selectAndInspectEquipment(eqKey, eqObj);
        }
      });
    }
    return true;
  }

  function selectAndInspectEquipment(key, targetObject) {
    if (!key) return;

    // 1. Calculate / Update 3D Selection Highlight Box
    let rootGroup = targetObject;
    while (rootGroup && rootGroup.parent && rootGroup.parent !== scene) {
      rootGroup = rootGroup.parent;
    }
    const target = rootGroup || targetObject;

    ensureSelectionHighlightBox();

    const bbox = new THREE.Box3().setFromObject(target);
    if (!bbox.isEmpty()) {
      const size = new THREE.Vector3();
      const center = new THREE.Vector3();
      bbox.getSize(size);
      bbox.getCenter(center);
      selectedHighlightBox.position.copy(center);
      selectionBaseScale.set(Math.max(1.5, size.x * 1.08), Math.max(1.5, size.y * 1.08), Math.max(1.5, size.z * 1.08));
      selectedHighlightBox.scale.copy(selectionBaseScale);
      selectedHighlightBox.visible = true;
    }

    // 2. Render In-Canvas Glassmorphism Telemetry HUD
    const hudEl = container.querySelector("#equip-telemetry-hud");
    if (hudEl) {
      hudEl.innerHTML = buildEquipmentTelemetryHtml(key);
      hudEl.style.display = "block";
      rootEl?.setAttribute("data-inspect", "1");

      hudEl.querySelector("#btn-close-telemetry-hud")?.addEventListener("click", () => {
        hudEl.style.display = "none";
        rootEl?.removeAttribute("data-inspect");
        if (selectedHighlightBox) selectedHighlightBox.visible = false;
      });

      hudEl.querySelector("#btn-telemetry-flyto")?.addEventListener("click", () => {
        const camTarget = EQUIP_CAMERA_TARGETS[key];
        if (camTarget) {
          flyToCamera(camTarget.pos, camTarget.look);
        }
      });

      const openTeardown = () => {
        const titles = {
          air_coolers: ["Gas Cooler · Fin-Fan Teardown", "E-101 · API 661 fin-fan hava soğutucu söküm görünümü"],
          cyclones: ["Siklon Seperatör · Teardown", "V-101 · Dikey çoklu siklon seperatör söküm görünümü"],
          cartridge_filters: ["Kartuş Filtre Seperatör · Teardown", "F-101 · Yatay koaleser filtre söküm görünümü"],
        };
        const [title, subtitle] = titles[key] || ["Ekipman Teardown", "KASP 3D Digital Twin"];
        openEquipmentTeardown(key, {
          eq,
          sm,
          sucLine: suctLine,
          numCyclones,
          numFilters,
          numCoolerBays,
          title,
          subtitle,
        });
      };
      hudEl.querySelector("#btn-telemetry-teardown")?.addEventListener("click", openTeardown);

      hudEl.querySelector("#btn-hud-calc-psv")?.addEventListener("click", () => {
        if (typeof options.onUpdateSafetyInputs !== "function") return;
        const psvCount = parseInt(hudEl.querySelector("#hud-psv-count")?.value || "2", 10);
        const psvDuty = parseInt(hudEl.querySelector("#hud-psv-duty")?.value || "1", 10);
        const psvSet = parseFloat(hudEl.querySelector("#hud-psv-set")?.value);
        const psvOver = parseFloat(hudEl.querySelector("#hud-psv-over")?.value);
        const psvBack = parseFloat(hudEl.querySelector("#hud-psv-back")?.value);
        const psvType = hudEl.querySelector("#hud-psv-type")?.value || "conventional";
        options.onUpdateSafetyInputs({
          psv_count: Number.isFinite(psvCount) ? psvCount : 2,
          psv_duty_count: Number.isFinite(psvDuty) ? Math.min(psvCount, psvDuty) : 1,
          psv_set_pressure_bar: Number.isFinite(psvSet) && psvSet > 0 ? psvSet : "",
          psv_overpressure_pct: Number.isFinite(psvOver) && psvOver > 0 ? psvOver : 10,
          psv_back_pressure_bar: Number.isFinite(psvBack) && psvBack > 0 ? psvBack : 1.01325,
          psv_valve_type: psvType,
        });
      });

      hudEl.querySelector("#btn-hud-calc-esd")?.addEventListener("click", () => {
        if (typeof options.onUpdateSafetyInputs !== "function") return;
        const esdCount = parseInt(hudEl.querySelector("#hud-esd-count")?.value || "2", 10);
        const esdDuty = parseInt(hudEl.querySelector("#hud-esd-duty")?.value || "1", 10);
        const esdDp = parseFloat(hudEl.querySelector("#hud-esd-dp")?.value);
        const esdType = hudEl.querySelector("#hud-esd-type")?.value || "full_bore_ball";
        const bdvTime = parseFloat(hudEl.querySelector("#hud-esd-bdv-time")?.value);
        options.onUpdateSafetyInputs({
          esd_count: Number.isFinite(esdCount) ? esdCount : 2,
          esd_duty_count: Number.isFinite(esdDuty) ? Math.min(esdCount, esdDuty) : 1,
          esd_allowable_dp_bar: Number.isFinite(esdDp) && esdDp > 0 ? esdDp : 0.5,
          esd_valve_type: esdType,
          bdv_depressurization_time_min: Number.isFinite(bdvTime) && bdvTime > 0 ? bdvTime : 15,
        });
      });
    }

    // 3. Keep bottom inspector drawer in sync
    if (onSelectEquipment) {
      onSelectEquipment(key);
    }
  }

  function onPointerDown(event) {
    pointerDownPos = { x: event.clientX, y: event.clientY };
    renderer.domElement.style.cursor = "grabbing";
    isCameraTransitioning = false; // Hand control immediately to user on click/drag
  }

  let pointerMoveRaf = null;
  let lastPointerEvent = null;

  function processPointerMove() {
    pointerMoveRaf = null;
    if (isDestroyed || !lastPointerEvent || !renderer) return;
    const rect = renderer.domElement.getBoundingClientRect();
    if (!rect || rect.width <= 0 || rect.height <= 0) return;
    mouse.x = ((lastPointerEvent.clientX - rect.left) / rect.width) * 2 - 1;
    mouse.y = -((lastPointerEvent.clientY - rect.top) / rect.height) * 2 + 1;

    raycaster.setFromCamera(mouse, camera);
    const hits = raycaster.intersectObjects(interactiveObjects, true);
    if (hits.length > 0) {
      renderer.domElement.style.cursor = "pointer";
    } else {
      renderer.domElement.style.cursor = "grab";
    }
  }

  function onPointerMove(event) {
    lastPointerEvent = event;
    if (!pointerMoveRaf) {
      pointerMoveRaf = requestAnimationFrame(processPointerMove);
    }
  }

  function onPointerUp(event) {
    renderer.domElement.style.cursor = "grab";
    // Only trigger click-to-inspect if user didn't drag the camera
    const moveDist = Math.hypot(event.clientX - pointerDownPos.x, event.clientY - pointerDownPos.y);
    if (moveDist > 6) return;

    const rect = renderer.domElement.getBoundingClientRect();
    mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

    raycaster.setFromCamera(mouse, camera);
    const hits = raycaster.intersectObjects(interactiveObjects, true);
    if (hits.length > 0) {
      let pipeObj = hits[0].object;
      while (pipeObj && !pipeObj.userData?.pipeMeta && pipeObj.parent) {
        pipeObj = pipeObj.parent;
      }
      if (pipeObj?.userData?.pipeMeta) {
        selectAndInspectPipe(pipeObj.userData.pipeMeta, pipeObj);
        return;
      }

      let obj = hits[0].object;
      while (obj && !obj.userData?.equipKey && obj.parent) {
        obj = obj.parent;
      }
      const key = obj?.userData?.equipKey;
      if (key) {
        selectAndInspectEquipment(key, obj);
      }
    }
  }

  renderer.domElement.addEventListener("pointerdown", onPointerDown);
  renderer.domElement.addEventListener("pointermove", onPointerMove);
  renderer.domElement.addEventListener("pointerup", onPointerUp);

  // ══════════════════ 13. ANIMATION LOOP ══════════════════
  const clock = new THREE.Clock();
  let isPaused = false;

  function shouldAnimate() {
    if (isDestroyed || document.hidden) return false;
    if (uiStore && uiStore.getState().activeTab !== "station") return false;
    return true;
  }

  function tick() {
    if (isDestroyed) return;
    if (!shouldAnimate()) {
      isPaused = true;
      animationFrameId = null;
      return;
    }
    isPaused = false;
    animationFrameId = requestAnimationFrame(tick);
    const delta = Math.min(clock.getDelta(), 0.1);

    // 1. Spin Gas Cooler Fin-Fans
    spinningFans.forEach((fan) => {
      fan.rotation.y += delta * 4.5;
    });

    // 2. Advance Flow Particles along 3D Pipe Curves
    if (showFlowParticles) {
      flowParticleMeshes.forEach((p) => {
        const ud = p.userData;
        ud.t = (ud.t + delta * ud.speed + 1.0) % 1.0;
        const pt = ud.curve.getPoint(ud.t);
        p.position.set(pt.x, pt.y + (ud.offsetY || 0), pt.z);
      });
    }

    // 3. Pulse 3D Selection Highlight Box
    if (selectedHighlightBox && selectedHighlightBox.visible) {
      selectionPulsePhase += delta * 4.5;
      const pulseFactor = 1.0 + 0.025 * Math.sin(selectionPulsePhase);
      selectedHighlightBox.scale.set(
        selectionBaseScale.x * pulseFactor,
        selectionBaseScale.y * pulseFactor,
        selectionBaseScale.z * pulseFactor
      );
    }

    // 4. Smooth Camera Fly-To Interpolation
    if (isCameraTransitioning && controls) {
      camera.position.lerp(targetCamPos, 0.08);
      controls.target.lerp(targetLookAt, 0.08);
      if (camera.position.distanceTo(targetCamPos) < 0.8) {
        isCameraTransitioning = false;
      }
    }

    if (controls) controls.update();
    renderer.render(scene, camera);
  }

  function resumeAnimation() {
    if (!isDestroyed && isPaused && shouldAnimate()) {
      clock.getDelta(); // flush clock delta to prevent jump
      tick();
    }
  }

  const unsubUi = uiStore ? uiStore.subscribe((ui) => {
    if (ui.activeTab === "station") {
      resumeAnimation();
    }
  }) : null;

  function onVisibilityChange() {
    if (!document.hidden) {
      resumeAnimation();
    }
  }
  document.addEventListener("visibilitychange", onVisibilityChange);

  tick();

  // ══════════════════ 13b. KLAVYE ERGONOMİSİ & TAM EKRAN ══════════════════
  // 1-8: kamera ön ayarları • R: izometrik sıfırla • F: tam ekran • Esc: tam ekrandan çık / seçimi kapat
  const KEY_PRESETS = ["iso", "top", "compCutaway", "manifold", "filtration", "cooler", "tiein", "control"];
  const fullscreenBtn = container.querySelector("#btn-toggle-3d-fullscreen");
  function set3dFullscreen(expanded) {
    if (!rootEl) return;
    const isExp = !!expanded;
    rootEl.classList.toggle("station-3d-expanded", isExp);
    if (fullscreenBtn) {
      fullscreenBtn.setAttribute("aria-pressed", isExp ? "true" : "false");
      fullscreenBtn.textContent = isExp
        ? `⛶ ${t("btn_3d_exit_fullscreen", uiLang)}`
        : `⛶ ${t("btn_3d_fullscreen", uiLang)}`;
      fullscreenBtn.style.background = isExp ? "#0284c7" : "#1e293b";
      fullscreenBtn.style.borderColor = isExp ? "#38bdf8" : "rgba(255,255,255,0.15)";
    }
    requestAnimationFrame(() => onResize());
  }
  fullscreenBtn?.addEventListener("click", () => {
    set3dFullscreen(!rootEl?.classList.contains("station-3d-expanded"));
  });

  function onRootPointerDown(ev) {
    if (!ev.target.closest("button, #equip-telemetry-hud, #pipe-section-overlay")) rootEl.focus({ preventScroll: true });
  }
  function onRootKeyDown(ev) {
    if (ev.ctrlKey || ev.metaKey || ev.altKey) return;
    const k = ev.key;
    if (/^[1-8]$/.test(k) || k === "r" || k === "R") {
      const name = k === "r" || k === "R" ? "iso" : KEY_PRESETS[Number(k) - 1];
      const preset = cameraPresets[name];
      const btn = container.querySelector(`.cam-preset-btn[data-cam="${name}"]`);
      if (preset) flyToCamera(preset.pos, preset.look, btn);
      ev.preventDefault();
    } else if (k === "f" || k === "F") {
      set3dFullscreen(!rootEl?.classList.contains("station-3d-expanded"));
      ev.preventDefault();
    } else if (k === "Escape") {
      if (rootEl?.classList.contains("station-3d-expanded")) {
        set3dFullscreen(false);
        ev.preventDefault();
        return;
      }
      const hudEl = container.querySelector("#equip-telemetry-hud");
      if (hudEl) hudEl.style.display = "none";
      rootEl.removeAttribute("data-inspect");
      if (selectedHighlightBox) selectedHighlightBox.visible = false;
      showPipeSectionModal = false;
      if (pipeOverlay) pipeOverlay.style.display = "none";
      syncToolbarAria();
    }
  }
  if (rootEl) {
    rootEl.setAttribute("tabindex", "0");
    rootEl.setAttribute("role", "application");
    rootEl.setAttribute("aria-label", "3D istasyon görünümü. Klavye: 1-8 kamera, R sıfırla, Escape seçimi kapat");
    rootEl.style.outline = "none";
    rootEl.addEventListener("pointerdown", onRootPointerDown);
    rootEl.addEventListener("keydown", onRootKeyDown);
  }

  // ══════════════════ 14. RESIZE OBSERVER & CLEANUP ══════════════════
  function onResize() {
    if (isDestroyed) return;
    const w = canvasMount.clientWidth;
    const h = canvasMount.clientHeight;
    if (w <= 0 || h <= 0) return;
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    renderer.setSize(w, h);
  }
  window.addEventListener("resize", onResize);

  let resizeObserver = null;
  if (typeof ResizeObserver !== "undefined") {
    resizeObserver = new ResizeObserver(() => onResize());
    resizeObserver.observe(canvasMount);
  }

  // Debug/audit bridge used by automated geometry checks and visual capture.
  // Safe to overwrite on each 3D mount; no application logic depends on it.
  window.__KASP_3D__ = {
    scene,
    camera,
    renderer,
    controls,
    interactiveObjects,
    pipeRoutes,
    pipeLabelMeshes,
    inspect: (key) => {
      const obj =
        interactiveObjects.find((o) => o.userData?.equipKey === key && !o.userData?.isPipeMesh) ||
        interactiveObjects.find((o) => o.userData?.equipKey === key);
      if (obj) selectAndInspectEquipment(key, obj);
      return !!obj;
    },
    inspectPipe: (lineKey) => {
      const groups = pipeRouteGroupsByLineKey.get(lineKey) || [];
      const firstGroup = groups[0] || null;
      const pipeMeta = firstGroup?.userData?.pipeMeta || (pLines[lineKey] ? {
        lineKey,
        lineTag: pLines[lineKey].tag || lineKey.toUpperCase(),
        lineName: pLines[lineKey].name || lineKey,
        hierarchyLevel: pLines[lineKey].hierarchy_level || "equipment_branch",
        hierarchyLabel: pLines[lineKey].hierarchy_label || "Proses Borulaması",
        parentHeader: pLines[lineKey].parent_header || null,
        fromBoundary: pLines[lineKey].from_boundary || "-",
        toBoundary: pLines[lineKey].to_boundary || "-",
      } : null);
      if (!pipeMeta) return false;
      return selectAndInspectPipe(pipeMeta, firstGroup);
    },
    capture: () => {
      renderer.render(scene, camera);
      return renderer.domElement.toDataURL("image/png");
    },
    audit: () => pipeRoutes.map((route) => ({
      equipKey: route.equipKey,
      lineKey: route.lineKey,
      lineTag: route.lineTag,
      lineName: route.lineName,
      hierarchyLevel: route.hierarchyLevel,
      parentHeader: route.parentHeader,
      fromBoundary: route.fromBoundary,
      toBoundary: route.toBoundary,
      radius: route.radius,
      first: route.first,
      last: route.last,
      points: route.points,
    })),
  };

  function getCurrentState() {
    return {
      camPos: camera ? camera.position.clone() : new THREE.Vector3(-145, 95, -155),
      camTarget: controls ? controls.target.clone() : new THREE.Vector3(-10, 8, 5),
      themeMode,
      cutawayMode,
      showPipeLabels,
      showEnvelopes,
      showFlowParticles,
    };
  }

  return {
    destroy: () => {
      isDestroyed = true;
      // Tear down any open exploded-view overlay before disposing the main scene.
      closeEquipmentTeardown();
      if (animationFrameId) cancelAnimationFrame(animationFrameId);
      if (pointerMoveRaf) cancelAnimationFrame(pointerMoveRaf);
      if (unsubUi) unsubUi();
      document.removeEventListener("visibilitychange", onVisibilityChange);
      window.removeEventListener("resize", onResize);
      if (rootEl) {
        rootEl.removeEventListener("click", syncToolbarAria);
        rootEl.removeEventListener("pointerdown", onRootPointerDown);
        rootEl.removeEventListener("keydown", onRootKeyDown);
      }
      if (resizeObserver) resizeObserver.disconnect();
      if (renderer && renderer.domElement) {
        renderer.domElement.removeEventListener("pointerdown", onPointerDown);
        renderer.domElement.removeEventListener("pointermove", onPointerMove);
        renderer.domElement.removeEventListener("pointerup", onPointerUp);
      }
      if (selectedHighlightBox) {
        scene.remove(selectedHighlightBox);
        selectedHighlightBox.geometry?.dispose();
        selectedHighlightBox.material?.dispose();
        selectedHighlightBox = null;
      }
      if (controls) {
        controls.dispose();
        controls = null;
      }
      // Save state before disposal
      container.__kasp_3d_state__ = getCurrentState();

      // Recursive disposal of meshes, lines, points, sprites, geometries and materials
      scene.traverse((obj) => {
        if (obj.isMesh || obj.isLine || obj.isPoints || obj.isSprite) {
          if (obj.geometry) {
            obj.geometry.dispose();
          }
          if (obj.material) {
            if (Array.isArray(obj.material)) {
              obj.material.forEach((mat) => {
                if (mat.map) mat.map.dispose();
                mat.dispose();
              });
            } else {
              if (obj.material.map) obj.material.map.dispose();
              obj.material.dispose();
            }
          }
        }
      });

      renderer.dispose();
      renderer.forceContextLoss?.();
      if (window.__KASP_3D__ && window.__KASP_3D__.scene === scene) {
        window.__KASP_3D__ = null;
      }
      canvasMount.innerHTML = "";
    },
    getState: getCurrentState,
    selectEquipment: (key) => {
      const obj =
        interactiveObjects.find((o) => o.userData?.equipKey === key && !o.userData?.isPipeMesh) ||
        interactiveObjects.find((o) => o.userData?.equipKey === key);
      if (obj) {
        selectAndInspectEquipment(key, obj);
        const camTarget = EQUIP_CAMERA_TARGETS[key];
        if (camTarget) {
          flyToCamera(camTarget.pos, camTarget.look);
        }
      }
    },
    clearSelection: () => {
      const hudEl = container.querySelector("#equip-telemetry-hud");
      if (hudEl) hudEl.style.display = "none";
      rootEl?.removeAttribute("data-inspect");
      if (selectedHighlightBox) selectedHighlightBox.visible = false;
    },
  };
}
