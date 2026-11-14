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
  let uiLang = uiStore?.getState?.()?.lang || "tr";

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
  const unitDischHeaderLine = pLines.unit_discharge_header || dischLine;
  const compSuctionBranchLine = pLines.comp_suction_branch || compBranchLine;
  const compDischargeBranchLine = pLines.comp_discharge_branch || {};
  const antiSurgeLine = pLines.anti_surge_loop || {};
  const coolerInletLine = pLines.cooler_inlet || {};
  const coolerOutletLine = pLines.cooler_outlet || {};
  const coolerRiserLine = pLines.cooler_bay_risers || {};
  const coolerOutletRiserLine = pLines.cooler_bay_outlet_risers || coolerRiserLine;
  const coolerBayInletHdrLine = pLines.cooler_bay_inlet_header || {};
  const coolerBayOutletHdrLine = pLines.cooler_bay_outlet_header || {};
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
  const rUnitDischHeader = visualPipeRadius(unitDischHeaderLine.od_mm, 273.0);
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
  const rCoolerOutletRiser = visualPipeRadius(coolerOutletRiserLine.od_mm, coolerRiserLine.od_mm || 141.30);
  const rBayInletHeader = visualPipeRadius(coolerBayInletHdrLine.od_mm, coolerRiserLine.od_mm || 141.30);
  const rBayOutletHeader = visualPipeRadius(coolerBayOutletHdrLine.od_mm, coolerOutletRiserLine.od_mm || 141.30);
  const rCoolerBypass = visualPipeRadius(coolerBypassLine.od_mm, 101.60);
  const coolerOutletCrossY = 1.6 + rCoolerInlet + Math.max(rCoolerRiser, rCoolerOutletRiser) + 0.35;
  const coolerReturnY = Math.max(
    3.8,
    2.2 + rSuctHeader + rDischHeader + 0.45,
    1.6 + rDischHeader + rDischHeader + 0.45
  );
  const coolerBypassY = Math.max(
    5.2,
    coolerReturnY + rDischHeader + rCoolerBypass + 0.45
  );

  // MFS/CFS inlet and outlet branch radii come directly from the hydraulic engine
  // so 3D pipe geometry and flanged ball valves scale separately with user/calculated NPS.
  const rCycloneInlet = visualPipeRadius(pLines.cyclone_branch?.od_mm, 323.8);
  const rCycloneOutlet = visualPipeRadius(pLines.cyclone_outlet_branch?.od_mm, pLines.cyclone_branch?.od_mm || 323.8);
  const rFilterInlet = visualPipeRadius(pLines.filter_branch?.od_mm, 323.8);
  const rFilterOutlet = visualPipeRadius(pLines.filter_outlet_branch?.od_mm, pLines.filter_branch?.od_mm || 323.8);
  const parseNominalOdMm = (sizeVal, fallbackOdMm) => {
    const match = String(sizeVal ?? "").match(/(\d+(?:\.\d+)?)/);
    return match ? Number(match[1]) * 25.4 : fallbackOdMm;
  };
  const pigBypassOdMm = Number(pLines.pig_bypass?.od_mm) || (Number(suctLine.od_mm) > 0 ? Number(suctLine.od_mm) * 0.72 : 219.1);
  const pigKickerRecvOdMm = Number(pLines.pig_kicker_receiver?.od_mm) || (Number(suctLine.od_mm) > 0 ? Math.min(219.1, Number(suctLine.od_mm) * 0.35) : 114.3);
  const pigKickerLaunchOdMm = Number(pLines.pig_kicker_launcher?.od_mm) || (Number(dischLine.od_mm) > 0 ? Math.min(219.1, Number(dischLine.od_mm) * 0.35) : 114.3);
  const psvInletOdMm = Number(pLines.psv_inlet?.od_mm) || parseNominalOdMm(eq.safety_relief_and_blowdown?.psv_sizing?.inlet_flange_in, 168.28);
  const esdRiserOdMm =
    Number(pLines.esd_riser?.od_mm) ||
    Number(eq.esd_sizing?.discharge?.calculated_dn_mm) ||
    parseNominalOdMm(eq.esd_sizing?.discharge?.calculated_size_in, 168.28);
  const rPigBypass = visualPipeRadius(pigBypassOdMm, 219.1);
  const rPigKickerReceiver = visualPipeRadius(pigKickerRecvOdMm, 114.3, { max: 0.42 });
  const rPigKickerLauncher = visualPipeRadius(pigKickerLaunchOdMm, 114.3, { max: 0.42 });
  const rPsvInlet = visualPipeRadius(psvInletOdMm, 168.28, { max: 0.42 });
  const rEsdRiser = visualPipeRadius(esdRiserOdMm, 168.28, { max: 0.45 });
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

  // Front manifold corridor & North-yard spacing constants (declared early so
  // upstream spines, filtration headers, cooler bays, and front headers stay synchronized).
  const mfsInletX = -114;
  const mfsVerticalX = -106;
  const mfsX = -99;
  const mfsOutletHeaderX = -91;
  const mfsCenterZ = -84;
  const mfsSpacingZ = numCyclones === 1 ? 0 : Math.max(8.5, 34 / Math.max(1, numCyclones - 1));
  const mfsStartZ = mfsCenterZ - ((numCyclones - 1) * mfsSpacingZ) / 2;
  const mfsEndZ = mfsCenterZ + ((numCyclones - 1) * mfsSpacingZ) / 2;
  const mfsInletTieZ = mfsStartZ - 8;

  const cfsPitchX = 11.5;
  const cfsStartX = -68;
  const cfsEndX = cfsStartX + Math.max(0, numFilters - 1) * cfsPitchX;
  const cfsCenterX = (cfsStartX + cfsEndX) / 2;
  const cfsHeaderY = 2.2;
  const cfsVesselY = 4.8;
  const cfsVesselZ = -78;
  const cfsInletHeaderZ = -100;
  const cfsOutletHeaderZ = -56;
  const cfsOutletTieX = cfsEndX + 12;

  const coolerX0 = Math.max(18, cfsOutletTieX + 26);
  const coolerCenterZ = -88;
  const coolerInletHeaderZ = -60;
  const coolerOutletHeaderZ = -50;
  const coolerReturnStartX = coolerX0 - 1.5;
  const dischargeReturnZ = -40;
  const northRecycleZ = Math.min(-116, mfsInletTieZ - 8);

  // Spec 4-NGTL 0-CS-M-002-4500 §5.8 Station Recycle Control Valve Skid between cooled discharge and filtered suction
  const stationRecycleTakeoffX = Math.max(cfsOutletTieX + 18, coolerReturnStartX - 4.0);
  const stationRecycleValveX = (stationRecycleTakeoffX + cfsOutletTieX) / 2;
  const stationRecycleZ = -32.5;
  const stationRecycleY = 2.2;

  // Compressors start from the Gas Cooler side (East) and extend Westward toward PIG traps as units are added.
  const compPitch = 58;
  const compStartX = Math.max(coolerX0 + 18, 36) + Math.max(0, numComps - 3) * 22;
  const lastCompX = compStartX - Math.max(0, numComps - 1) * compPitch;
  const compWestEdgeX = lastCompX - 28;
  const headerWestX = Math.min(lastCompX - 18, cfsOutletTieX - 12);
  const headerEastX = Math.max(compStartX + 18, coolerX0 + 12);
  const frontSuctionZ = -18.5;
  const frontRecycleZ = -13.5;
  const frontDischargeZ = -8.5;
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
          <span style="font-family: monospace; font-weight: 600; color: #cbd5e1;">${escapeHtml(suctLine.nominal_size_in || '48"')} ASME B31.8 / API 617</span>
        </div>
      </div>

      <!-- Top-Center Interactive Layer & Cutaway Controls -->
      <div class="hud-toolbar" style="position: absolute; top: 12px; left: 50%; transform: translateX(-50%); z-index: 20; display: flex; gap: 6px; flex-wrap: wrap; background: rgba(14, 19, 28, 0.88); backdrop-filter: blur(8px); padding: 6px 10px; border-radius: 20px; border: 1px solid rgba(255,255,255,0.15); box-shadow: 0 4px 16px rgba(0,0,0,0.35);">
        <button id="btn-cutaway-mode" style="background: #0284c7; color: #fff; border: 1px solid #38bdf8; border-radius: 14px; padding: 4px 10px; font-size: 11px; font-weight: 600; cursor: pointer;">
          🏗️ Bina Kesiti: ${escapeHtml(cutawayUnitLabel)} (X-Ray)
        </button>
        <button id="btn-toggle-pipe-labels" aria-pressed="${showPipeLabels ? "true" : "false"}" style="background: ${showPipeLabels ? "#7c3aed" : "#1e293b"}; color: ${showPipeLabels ? "#fff" : "#cbd5e1"}; border: 1px solid ${showPipeLabels ? "#c084fc" : "rgba(255,255,255,0.15)"}; border-radius: 14px; padding: 4px 10px; font-size: 11px; font-weight: 600; cursor: pointer;">
          ${escapeHtml(t(showPipeLabels ? "pipe_labels_on" : "pipe_labels_off", uiLang))}
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
        <div style="display: flex; align-items: center; gap: 7px; margin: 3px 0;"><span style="width: 14px; height: 5px; background: #e2d400; border: 1px solid #facc15; display: inline-block; border-radius: 2px;"></span><span>Ana Header (Suction/Discharge: ${escapeHtml(suctLine.nominal_size_in || '10"')})</span></div>
        <div style="display: flex; align-items: center; gap: 7px; margin: 3px 0;"><span style="width: 14px; height: 3px; background: #e2d400; display: inline-block; border-radius: 2px;"></span><span>Ekipman Branşmanları (${escapeHtml(compBranchLine.nominal_size_in || '10"')}/${escapeHtml(compDischargeBranchLine.nominal_size_in || '6"')})</span></div>
        <div style="display: flex; align-items: center; gap: 7px; margin: 3px 0;"><span style="width: 14px; height: 4px; background: #f59e0b; display: inline-block; border-radius: 2px;"></span><span>PIG-R ➔ TC ➔ PIG-L Sınır Plakaları</span></div>
        <div style="display: flex; align-items: center; gap: 7px; margin: 3px 0;"><span style="width: 14px; height: 4px; background: #00f0ff; display: inline-block; border-radius: 2px;"></span><span>Boru İçi Gaz Akış Yönü & Tıklanabilir Hat</span></div>
        <div style="display: flex; align-items: center; gap: 7px; margin: 3px 0;"><span style="width: 14px; height: 4px; background: #5c3a21; display: inline-block; border-radius: 2px;"></span><span>Yeraltı Ana İletim Sınır Hattı (${escapeHtml(mainlineInletLine.nominal_size_in || suctLine.nominal_size_in || '10"')})</span></div>
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
          <div style="display: flex; justify-content: space-between; margin: 2px 0;"><span>Station Suction Header (L-102/105):</span><b style="color:#facc15;">${escapeHtml(suctLine.nominal_size_in || '10"')} • PIG-R Çıkışı ➔ TC Emiş Header Sonu</b></div>
          <div style="display: flex; justify-content: space-between; margin: 2px 0;"><span>Station Discharge Header (L-109):</span><b style="color:#fb923c;">${escapeHtml(dischLine.nominal_size_in || '10"')} • TC Basma Header ➔ PIG-L Girişi</b></div>
          <div style="display: flex; justify-content: space-between; margin: 2px 0;"><span>MFS Siklon Giriş / Çıkış (L-103/103A):</span><b style="color:#fff;">${escapeHtml(pLines.cyclone_branch?.nominal_size_in || '8"')} / ${escapeHtml(pLines.cyclone_outlet_branch?.nominal_size_in || pLines.cyclone_branch?.nominal_size_in || '8"')}</b></div>
          <div style="display: flex; justify-content: space-between; margin: 2px 0;"><span>CFS Filtre Giriş / Çıkış (L-104/104A):</span><b style="color:#fff;">${escapeHtml(pLines.filter_branch?.nominal_size_in || '8"')} / ${escapeHtml(pLines.filter_outlet_branch?.nominal_size_in || pLines.filter_branch?.nominal_size_in || '8"')}</b></div>
          <div style="display: flex; justify-content: space-between; margin: 2px 0;"><span>TC Ünite Emiş / Basma Branşmanı:</span><b style="color:#fff;">${escapeHtml(compSuctionBranchLine.nominal_size_in || '10"')} / ${escapeHtml(compDischargeBranchLine.nominal_size_in || '6"')} (${escapeHtml(compDischargeBranchLine.flow_kgs || 12)} kg/s)</b></div>
          <div style="display: flex; justify-content: space-between; margin: 2px 0;"><span>Anti-Surge (ASV) / Recycle Header:</span><b style="color:#fff;">${escapeHtml(antiSurgeLine.nominal_size_in || '5"')} / ${escapeHtml(pLines.station_recycle?.nominal_size_in || '6"')} ➔ Suction Header</b></div>
          <div style="display: flex; justify-content: space-between; margin: 2px 0;"><span>Gaz Soğutucu Giriş / Çıkış / TCV:</span><b style="color:#fff;">${escapeHtml(coolerInletLine.nominal_size_in || '6"')} / ${escapeHtml(coolerOutletLine.nominal_size_in || '6"')} / ${escapeHtml(coolerBypassLine.nominal_size_in || '3 1/2"')} (➔ Discharge Header)</b></div>
          <div style="display: flex; justify-content: space-between; margin: 2px 0;"><span>Boru Malzemesi / Et Kalınlığı:</span><b style="color:#38bdf8;">${escapeHtml(suctLine.pipe_material || 'API 5L X70')} • t = ${escapeHtml(suctLine.wall_thickness_mm || 9.5)} mm (t_req: ${escapeHtml(suctLine.min_required_thickness_mm || 6.4)} mm)</b></div>
          <div style="display: flex; justify-content: space-between; margin: 2px 0;"><span>Ana Header Gaz Hızı &amp; EVR:</span><b style="color:#34d399;">${escapeHtml(suctLine.actual_velocity_ms || 14.8)} m/s (%${escapeHtml(suctLine.erosion_ratio_pct || 72.0)} EVR &lt; %100)</b></div>
          <div style="margin-top: 6px; padding: 5px 8px; background: rgba(16,185,129,0.15); border: 1px solid #10b981; border-radius: 6px; color: #34d399; font-weight: 600; text-align: center;">
            ✓ ANA HEADER EŞİTLİĞİ (${escapeHtml(suctLine.nominal_size_in || '10"')}) &amp; SINIR TANIMLARI DOĞRULANDI
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
  const matHeatTraceOrange = new THREE.MeshStandardMaterial({ color: 0xf97316, emissive: 0x9a3412, emissiveIntensity: 0.35, roughness: 0.35, metalness: 0.45 });
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
      parentLineKey = null,
      derivedOdMm = null,
      derivedNps = null,
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

    const directLineData = lineKey ? pLines[lineKey] : null;
    const inheritedLineData = !directLineData && parentLineKey ? pLines[parentLineKey] : null;
    const lineData = directLineData || inheritedLineData || {};
    const resolvedPipeMeta = lineKey ? {
      lineKey,
      parentLineKey: parentLineKey || null,
      lineTag: directLineData?.tag || lineKey.toUpperCase(),
      lineName: segmentTitle || directLineData?.name || lineKey,
      hierarchyLevel: directLineData?.hierarchy_level || "equipment_branch",
      hierarchyLabel: directLineData?.hierarchy_label || "Proses Borulaması",
      parentHeader: directLineData?.parent_header || lineData.parent_header || parentLineKey || null,
      fromBoundary: fromBoundary || directLineData?.from_boundary || lineData.from_boundary || "-",
      toBoundary: toBoundary || directLineData?.to_boundary || lineData.to_boundary || "-",
      boundarySummary: directLineData?.boundary_summary || `${fromBoundary || "-"} ➔ ${toBoundary || "-"}`,
      unitLabel: unitLabel || null,
      equipKey: equipKey || null,
      derivedOdMm: derivedOdMm || null,
      derivedNps: derivedNps || null,
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
      parentLineKey: resolvedPipeMeta?.parentLineKey || null,
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
  const desiredCoolerBayW = Math.max(6.8, Math.min(12.5, coolerTubesPerRow * 0.24), Math.max(rCoolerRiser, rCoolerOutletRiser) * 7.5);
  const estCoolerEndX = coolerX0 + Math.max(18, Math.min(120, numCoolerBays * desiredCoolerBayW));
  const westLoopRoadX = Math.min(-158, compWestEdgeX - 8, headerWestX - 8);
  const westYardExtentX = Math.min(-220, westLoopRoadX - 36);
  const eastYardExtentX = Math.max(240, estCoolerEndX + 100);
  const padShape = new THREE.Shape();
  padShape.moveTo(westYardExtentX, -162);
  padShape.lineTo(eastYardExtentX, -162);
  padShape.lineTo(eastYardExtentX, 162);
  padShape.lineTo(westYardExtentX, 162);
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
  const eastLoopRoadX = Math.max(132, headerEastX + 20);
  const wasteSpurX = Math.max(92, estCoolerEndX + 14);
  addRoadSegment(westLoopRoadX, -24, Math.max(eastLoopRoadX, wasteSpurX + 10), -24, 7.0, 22);
  createCadGreenLabel("7.0 M. WIDE ROAD", -72, 0.26, -24, 24, 2.8, -Math.PI / 2, 0, 0);

  // South Horizontal Road (Z = +48)
  addRoadSegment(westLoopRoadX, 48, Math.max(128, eastLoopRoadX), 48, 7.0, 22);
  createCadGreenLabel("7.0 M. WIDE ROAD", 28, 0.26, 48, 24, 2.8, -Math.PI / 2, 0, 0);

  // East & West Loop Connector Roads + South-East Entrance Road + NE Waste Storage Spur
  addRoadSegment(eastLoopRoadX, -24, eastLoopRoadX, 48, 7.0, 20);
  addRoadSegment(westLoopRoadX, -24, westLoopRoadX, 48, 7.0, 20);
  addRoadSegment(wasteSpurX, -24, wasteSpurX, -98, 6.5, 20); // Spur to Temporary Waste Storage Area
  addRoadSegment(125, 48, 142, 125, 7.0, 22); // SE Main Gate Entrance Road

  // West access spur to the relocated pig trap / battery-limit yard.
  const westPigSpurX = Math.min(-208, westLoopRoadX - 18);
  addRoadSegment(westLoopRoadX, -24, westPigSpurX, -24, 6.5, 20);
  addRoadSegment(westPigSpurX, -24, westPigSpurX, -96, 6.5, 20);
  addRoadSegment(westPigSpurX, -96, -176, -96, 6.5, 18);

  // ── Perimeter Double Security Wire Fence (Proses Tel Çiti) & Patrol Road ──
  const fenceWestX = Math.min(-232, westPigSpurX - 24);
  const fenceNorthEastX = Math.max(140, estCoolerEndX + 55);
  const fenceEastX = Math.max(215, fenceNorthEastX + 45);
  const fenceBoundaryPoints = [
    // Extended north and east boundaries for wider filtration/cooling spacing and the relocated pig trap yard.
    new THREE.Vector3(fenceWestX, 0, -134),
    new THREE.Vector3(fenceNorthEastX, 0, -134),
    new THREE.Vector3(fenceEastX, 0, 38), // Angled NE pipeline boundary
    new THREE.Vector3(fenceEastX, 0, 132),
    new THREE.Vector3(fenceWestX, 0, 132),
    new THREE.Vector3(fenceWestX, 0, -134),
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
    visualPipeRadius(mainlineInletLine.od_mm ? mainlineInletLine.od_mm * 0.85 : pigBypassOdMm, 219.1),
    matYellowPipe,
    {
      equipKey: "pig_receiver",
      lineKey: "pig_bypass",
      parentLineKey: "suction_header",
      derivedOdMm: pigBypassOdMm,
      segmentTitle: "PIG-R ➔ Ortak Pig By-Pass Tee Bağlantısı",
      fromBoundary: "Giriş Pig Kovanı (PIG-R) Tee Branşmanı",
      toBoundary: "Ortak Pig By-Pass Kolektörü",
    }
  );
  createCadPipeRoute(
    [
      new THREE.Vector3(-190, 2.2, -48),
      new THREE.Vector3(-196, 2.2, -48),
    ],
    visualPipeRadius(mainlineOutletLine.od_mm ? mainlineOutletLine.od_mm * 0.85 : pigBypassOdMm, 219.1),
    matYellowPipe,
    {
      equipKey: "pig_launcher",
      lineKey: "pig_bypass",
      parentLineKey: "discharge_header",
      derivedOdMm: pigBypassOdMm,
      segmentTitle: "Ortak Pig By-Pass ➔ PIG-L Tee Bağlantısı",
      fromBoundary: "Ortak Pig By-Pass Kolektörü",
      toBoundary: "Çıkış Pig Kovanı (PIG-L) Tee Branşmanı",
    }
  );

  // Elevated North Perimeter Yellow Pipe Rack (Station Recycle & Purge Line - Note 13)
  const recycleRackEastX = estCoolerEndX;
  createCadPipeRoute(
    [
      new THREE.Vector3(-164, 4.2, northRecycleZ),
      new THREE.Vector3(-85, 4.2, northRecycleZ),
      new THREE.Vector3(recycleRackEastX, 4.2, northRecycleZ),
    ],
    rAntiSurgeHeader,
    matYellowPipe,
    {
      flowArrows: 5,
      equipKey: "station_recycle",
      lineKey: "station_recycle",
      segmentTitle: "Kuzey Çevre Purge & Dengeleme Kolektörü (Note 13 — PCV-101'den Ayrı)",
      fromBoundary: "Station Discharge Header ( Gaz Soğutucu Çıkışı Sonrası )",
      toBoundary: "Station Suction Header ( PIG-R Çıkışı / MFS Önü )",
      registerParticlePath: true,
    }
  );
  for (let rx = -158; rx <= recycleRackEastX - 4; rx += 14) {
    const post = new THREE.Mesh(new THREE.BoxGeometry(0.4, 4.2, 0.4), matCadBlueSteel);
    post.position.set(rx, 2.1, northRecycleZ);
    const cross = new THREE.Mesh(new THREE.BoxGeometry(0.4, 0.3, 2.2), matCadBlueSteel);
    cross.position.set(rx, 4.0, northRecycleZ);
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
    createValveStation(x - 4.2, 1.7, kickerZ, isLauncher ? rPigKickerLauncher : rPigKickerReceiver, {
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
    visualPipeRadius(pigBypassOdMm, 219.1),
    matYellowPipe,
    {
      flowArrows: 3,
      equipKey: "pig_receiver",
      lineKey: "pig_bypass",
      parentLineKey: "suction_header",
      derivedOdMm: pigBypassOdMm,
      segmentTitle: "PIG-R / PIG-L Ortak Pig By-Pass Kolektörü",
      fromBoundary: "Ana İletim Giriş Hattı & Station Suction Tie-In",
      toBoundary: "Station Discharge Tie-In & Ana İletim Çıkış Hattı",
      registerParticlePath: true,
    }
  );
  // Mainline Block Valve (MLBV-101 · Fail-Open Gas-over-Oil) + Side Valves (SV-IN, SV-OUT) + Loading (§5.12) + Station Bypass (§5.13).
  createValveStation(-190, 2.2, -72, rPigBypass * 1.08, {
    rotationY: Math.PI / 2,
    hasActuator: true,
    hasPlatform: true,
    equipKey: "mainline_block_valve",
    valveColorMat: matRedFire,
  });
  createValveStation(-186.5, 2.2, -82, rSuctHeader * 1.05, {
    rotationY: 0,
    hasActuator: true,
    hasPlatform: true,
    equipKey: "station_suction_valve",
    valveColorMat: matValveBody,
  });
  createValveStation(-186.5, 2.2, -62, rDischHeader * 1.05, {
    rotationY: 0,
    hasActuator: true,
    hasPlatform: true,
    equipKey: "station_discharge_valve",
    valveColorMat: matRedFire,
  });

  // Station Loading Line BESIDE Station Suction Side Valve (4500 §5.12 + Özel §5.4: horizontal bypass beside SV-IN, zero vertical overlap)
  createCadPipeRoute(
    [
      new THREE.Vector3(-189.0, 2.2, -82),
      new THREE.Vector3(-189.0, 2.2, -79.2),
      new THREE.Vector3(-184.0, 2.2, -79.2),
      new THREE.Vector3(-184.0, 2.2, -82),
    ],
    Math.max(0.11, rPigBypass * 0.35),
    matTealUtilityPipe,
    {
      equipKey: "station_loading_line",
      segmentTitle: "İstasyon Dolum Hattı — Station Loading Line (4500 §5.12 / Özel §5.4)",
      fromBoundary: "İstasyon Giriş Vanası (SV-IN) Memba",
      toBoundary: "Station Suction Header (Yükleme/Dengeleme)",
    }
  );
  createValveStation(-187.6, 2.2, -79.2, Math.max(0.14, rPigBypass * 0.42), {
    rotationY: 0,
    hasActuator: false,
    hasPlatform: false,
    equipKey: "station_loading_line",
    valveColorMat: matValveBody,
  });
  createValveStation(-185.4, 2.2, -79.2, Math.max(0.14, rPigBypass * 0.42), {
    rotationY: 0,
    hasActuator: true,
    hasPlatform: false,
    equipKey: "station_loading_line",
    valveColorMat: matCyanArrow,
  });

  // Station By-Pass Line & Non-Slam Piston/Nozzle Check Valve (4500 §5.13: exact same diameter as station header)
  createCadPipeRoute(
    [
      new THREE.Vector3(-152, 2.2, -62),
      new THREE.Vector3(-152, 2.2, -82),
    ],
    rDischHeader,
    matYellowPipe,
    {
      flowArrows: 1,
      flangeEnds: true,
      equipKey: "station_bypass_valve",
      lineKey: "station_bypass",
      segmentTitle: "İstasyon By-Pass Hattı & Non-Slam Çekvalf (4500 §5.13 · Header Çapında)",
      fromBoundary: "Station Discharge Header",
      toBoundary: "Station Suction Header",
    }
  );
  const bypassCheckGroup = new THREE.Group();
  bypassCheckGroup.position.set(-152, 2.2, -72);
  const bypassNonSlamNrv = new THREE.Mesh(
    new THREE.ConeGeometry(rDischHeader * 1.32, rDischHeader * 2.4, 20),
    matFlangeSteel
  );
  bypassNonSlamNrv.rotation.x = -Math.PI / 2;
  bypassCheckGroup.add(bypassNonSlamNrv);
  [-rDischHeader * 1.25, rDischHeader * 1.25].forEach((dz) => {
    const flg = new THREE.Mesh(
      new THREE.CylinderGeometry(rDischHeader * 1.38, rDischHeader * 1.38, 0.24, 20),
      matFlangeSteel
    );
    flg.rotation.x = Math.PI / 2;
    flg.position.z = dz;
    bypassCheckGroup.add(flg);
  });
  registerClickable(bypassCheckGroup, "station_bypass_valve");
  scene.add(bypassCheckGroup);
  // PIG-R kicker & receiver balance line (Pig By-Pass ➔ PIG-R barrel).
  createCadPipeRoute(
    [
      new THREE.Vector3(-190, 2.2, -84),
      new THREE.Vector3(-196, 2.2, -84),
    ],
    visualPipeRadius(pigKickerRecvOdMm, 114.3, { max: 0.42 }),
    matYellowPipe,
    {
      equipKey: "pig_receiver",
      lineKey: "pig_kicker_receiver",
      parentLineKey: "suction_header",
      derivedOdMm: pigKickerRecvOdMm,
      segmentTitle: "PIG-R Kicker & Receiver Dengeleme Hattı (Pig By-Pass Bağlantısı)",
      fromBoundary: "Ortak Pig By-Pass Hattı",
      toBoundary: "PIG-R Alıcı Kovan Gövdesi",
    }
  );
  createValveStation(-193, 2.2, -84, rPigKickerReceiver * 1.05, {
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
    visualPipeRadius(pigKickerLaunchOdMm, 114.3, { max: 0.42 }),
    matYellowPipe,
    {
      equipKey: "pig_launcher",
      lineKey: "pig_kicker_launcher",
      parentLineKey: "discharge_header",
      derivedOdMm: pigKickerLaunchOdMm,
      segmentTitle: "PIG-L Kicker Hattı (Pig By-Pass Bağlantısı)",
      fromBoundary: "Ortak Pig By-Pass Hattı",
      toBoundary: "PIG-L Atıcı Kovan Gövdesi",
    }
  );
  createValveStation(-193, 2.2, -60, rPigKickerLauncher * 1.05, {
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
      new THREE.Vector3(-128, 2.2, -82),
      new THREE.Vector3(-128, 2.2, mfsInletTieZ),
      new THREE.Vector3(mfsInletX, 2.2, mfsInletTieZ),
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
      new THREE.Vector3(coolerReturnStartX, 1.6, coolerOutletHeaderZ),
      new THREE.Vector3(coolerReturnStartX, coolerReturnY, coolerOutletHeaderZ),
      new THREE.Vector3(coolerReturnStartX, coolerReturnY, dischargeReturnZ),
      new THREE.Vector3(-126, coolerReturnY, dischargeReturnZ),
      new THREE.Vector3(-126, 2.2, dischargeReturnZ),
      new THREE.Vector3(-126, 2.2, -62),
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
  createCadPipeCallout(
    `L-109 • STATION DISCHARGE HEADER (ANA OMURGA)`,
    `Gaz Soğutucu Çıkışı ➔ PSV/ESD ➔ USM ➔ PIG-L (${dischLine.nominal_size_in || '48"'})`,
    -16,
    coolerReturnY + 4.4,
    dischargeReturnZ,
    { width: 28, height: 4.7, pipeY: coolerReturnY + rDischHeader, accentColor: "#f59e0b", lineKey: "discharge_header", equipKey: "pig_launcher" }
  );

  // ── 1) PSV Riser Bank on Station Discharge Header (rising vertically on the line) ──
  const psvCount3d = Math.max(1, Math.min(4, Number(eq.safety_relief_and_blowdown?.psv_count || 2)));
  const psvBaseX = Math.min(-44, cfsOutletTieX - 16);
  const psvSpanX = Math.max(6, psvCount3d * 3.4);
  const psvPlatformY = coolerReturnY + 2.4;
  const psvRiserTopY = coolerReturnY + 3.3;
  const psvVentTopY = coolerReturnY + 10.6;
  const psvBankGroup = new THREE.Group();

  // Olive-steel elevated grating platform straddling the discharge header (matching cad_ref_1.jpg)
  const psvDeck = new THREE.Mesh(new THREE.BoxGeometry(psvSpanX + 3.0, 0.20, 5.2), matOliveSteel);
  psvDeck.position.set(psvBaseX, psvPlatformY, dischargeReturnZ);
  psvBankGroup.add(psvDeck);
  const psvRailEdges = new THREE.EdgesGeometry(new THREE.BoxGeometry(psvSpanX + 3.0, 1.1, 5.2));
  const psvRails = new THREE.LineSegments(psvRailEdges, new THREE.LineBasicMaterial({ color: 0xcab300 }));
  psvRails.position.set(psvBaseX, psvPlatformY + 0.55, dischargeReturnZ);
  psvBankGroup.add(psvRails);
  [
    [psvBaseX - (psvSpanX + 2.4) / 2, dischargeReturnZ - 2.3],
    [psvBaseX + (psvSpanX + 2.4) / 2, dischargeReturnZ - 2.3],
    [psvBaseX - (psvSpanX + 2.4) / 2, dischargeReturnZ + 2.3],
    [psvBaseX + (psvSpanX + 2.4) / 2, dischargeReturnZ + 2.3],
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
        new THREE.Vector3(rx, coolerReturnY, dischargeReturnZ),
        new THREE.Vector3(rx, psvRiserTopY, dischargeReturnZ),
      ],
      visualPipeRadius(psvInletOdMm, 168.28, { max: 0.42 }),
      matYellowPipe,
      {
        equipKey: "safety_relief",
        lineKey: "psv_inlet",
        parentLineKey: "discharge_header",
        derivedOdMm: psvInletOdMm,
        derivedNps: eq.safety_relief_and_blowdown?.psv_sizing?.inlet_flange_in || null,
        segmentTitle: `PSV-10${i + 1} Dikey Giriş Riser Hattı (Discharge Header Üzeri)`,
        fromBoundary: "Station Discharge Header",
        toBoundary: `PSV-10${i + 1} Giriş Flanşı`,
      }
    );

    const unit = new THREE.Group();
    unit.position.set(rx, psvRiserTopY, dischargeReturnZ);
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
  const esdBaseX = psvBaseX - 24;
  const esdSpanX = Math.max(6, esdCount3d * 3.4);
  const esdPlatformY = coolerReturnY + 2.4;
  const esdRiserTopY = coolerReturnY + 3.1;
  const esdVentTopY = coolerReturnY + 9.8;
  const esdBankGroup = new THREE.Group();

  const esdDeck = new THREE.Mesh(new THREE.BoxGeometry(esdSpanX + 3.0, 0.20, 5.2), matOliveSteel);
  esdDeck.position.set(esdBaseX, esdPlatformY, dischargeReturnZ);
  esdBankGroup.add(esdDeck);
  const esdRailEdges = new THREE.EdgesGeometry(new THREE.BoxGeometry(esdSpanX + 3.0, 1.1, 5.2));
  const esdRails = new THREE.LineSegments(esdRailEdges, new THREE.LineBasicMaterial({ color: 0xcab300 }));
  esdRails.position.set(esdBaseX, esdPlatformY + 0.55, dischargeReturnZ);
  esdBankGroup.add(esdRails);
  [
    [esdBaseX - (esdSpanX + 2.4) / 2, dischargeReturnZ - 2.3],
    [esdBaseX + (esdSpanX + 2.4) / 2, dischargeReturnZ - 2.3],
    [esdBaseX - (esdSpanX + 2.4) / 2, dischargeReturnZ + 2.3],
    [esdBaseX + (esdSpanX + 2.4) / 2, dischargeReturnZ + 2.3],
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
        new THREE.Vector3(ex, coolerReturnY, dischargeReturnZ),
        new THREE.Vector3(ex, esdRiserTopY, dischargeReturnZ),
      ],
      visualPipeRadius(esdRiserOdMm, 168.28, { max: 0.45 }),
      matYellowPipe,
      {
        equipKey: "esd_valves",
        lineKey: "esd_riser",
        parentLineKey: "discharge_header",
        derivedOdMm: esdRiserOdMm,
        derivedNps: eq.esd_sizing?.discharge?.calculated_size_in ? `${eq.esd_sizing.discharge.calculated_size_in}"` : null,
        segmentTitle: `ESD/BDV-10${i + 1} Dikey Riser Hattı (Discharge Header Üzeri)`,
        fromBoundary: "Station Discharge Header",
        toBoundary: `ESD/BDV-10${i + 1} Acil Boşaltma & Kapatma Vanası`,
      }
    );

    const esdUnit = new THREE.Group();
    esdUnit.position.set(ex, esdRiserTopY, dischargeReturnZ);
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

  createCadPipeCallout(
    `PSV-101..10${psvCount3d} & ESD-101..10${esdCount3d} • DISCHARGE HEADER EMNİYET MANİFOLDU`,
    "Hat Üzeri Dikey Riser PSV & ESD Vanaları (Tıklayarak Sayı & Çap Hesaplayın)",
    (psvBaseX + esdBaseX) / 2,
    coolerReturnY + 11.8,
    dischargeReturnZ,
    { width: 32, height: 4.8, pipeY: coolerReturnY + rDischHeader, accentColor: "#ef4444", lineKey: "discharge_header", equipKey: "safety_relief" }
  );

  // ── 3) Ultrasonic Gas Flow Meter (USM - FT-401) on Station Discharge Header ──
  const usmX = esdBaseX - 36;
  const usmY = coolerReturnY;
  const usmZ = dischargeReturnZ;
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
    usmX - 10,
    coolerReturnY + rDischHeader + 3.1,
    dischargeReturnZ,
    { width: 27, height: 4.8, pipeY: coolerReturnY + rDischHeader, accentColor: "#f59e0b", lineKey: "discharge_header", equipKey: "pig_launcher" }
  );
  createCadPipeCallout(
    `L-110 • RECYCLE & PURGE HATTI (NOTE 13)`,
    `Station Discharge Header ➔ PCV ➔ Station Suction Header (${pLines.station_recycle?.nominal_size_in || '-'})`,
    -60,
    7.8,
    northRecycleZ,
    { width: 25, height: 4.5, pipeY: 4.2 + rAntiSurgeHeader, accentColor: "#22d3ee", lineKey: "station_recycle", equipKey: "station_recycle" }
  );

  // Emergency Vent / Blowdown Stack & PSV Assembly (North-West Yard)
  const ventStackGrp = new THREE.Group();
  ventStackGrp.position.set(-134, 0, -100);
  const stackBase = new THREE.Mesh(new THREE.BoxGeometry(3.5, 0.6, 3.5), matConcretePlinth);
  const stackPipe = new THREE.Mesh(new THREE.CylinderGeometry(0.55, 0.75, 22, 16), matVesselGrey);
  stackPipe.position.y = 11;
  const stackTip = new THREE.Mesh(new THREE.CylinderGeometry(0.7, 0.55, 2.2, 16), matRedFire);
  stackTip.position.y = 22.5;
  ventStackGrp.add(stackBase, stackPipe, stackTip);
  registerClickable(ventStackGrp, "safety_relief");
  scene.add(ventStackGrp);
  createValveStation(-134, 2.0, -94, rPsvInlet * 1.15, { hasPlatform: true, equipKey: "safety_relief", valveColorMat: matRedFire });

  // ══════════════════ 7. NORTH-CENTER FILTRATION & COOLING YARD (MFS, CFS, GAS COOLER) ══════════════════

  // ── 7.1 MFS: Multi-Cyclone Filter Separators ──
  const mfsGroup = new THREE.Group();
  const mfsPlatDepth = Math.max(18, mfsEndZ - mfsStartZ + 8);

  // Central Elevated 2-Tier Olive-Steel Platform
  const mfsPlat = new THREE.Mesh(new THREE.BoxGeometry(8.5, 6.2, mfsPlatDepth), matOliveSteel);
  mfsPlat.position.set(mfsX, 3.1, mfsCenterZ);
  mfsPlat.castShadow = true;
  mfsGroup.add(mfsPlat);

  // Translucent Maintenance Envelope around MFS (taller for vertical separators + below-barrel blow-flasks)
  const mfsEnv = new THREE.Mesh(new THREE.BoxGeometry(24, 15.5, mfsPlatDepth + 4), matEnvelopeBox);
  mfsEnv.position.set(mfsX - 2, 7.75, mfsCenterZ);
  scene.add(mfsEnv);
  envelopeMeshes.push(mfsEnv);

  // Common MFS inlet manifold (Station Suction Header tie → elevated MFS equipment manifold)
  const mfsInletY = 7.8;
  createCadPipeRoute(
    [
      new THREE.Vector3(mfsInletX, 2.2, mfsInletTieZ),
      new THREE.Vector3(mfsInletX, mfsInletY, mfsInletTieZ),
      new THREE.Vector3(mfsInletX, mfsInletY, mfsEndZ),
    ],
    rCycloneInlet,
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

  // Vertical multi-cyclone separators: body + spherical top dome + conical bottom + Spec 4500 §5.2 below-barrel horizontal blow-flask + dual level bottles.
  const mfsVesselBottomY = 3.3;
  const mfsVesselBodyH = 7.2;
  const mfsVesselTopY = mfsVesselBottomY + mfsVesselBodyH;
  const mfsOutletTopY = 12.6;
  const mfsAutoDumpHeaderX = mfsVerticalX + 1.85;
  const mfsManualDumpHeaderX = mfsVerticalX - 1.95;

  for (let i = 0; i < numCyclones; i++) {
    const cz = numCyclones === 1 ? mfsCenterZ : mfsStartZ + i * mfsSpacingZ;
    const mfsUnitTag = `V-10${i + 1}`;

    // Vertical cylindrical separator body
    const vessel = new THREE.Mesh(new THREE.CylinderGeometry(1.15, 1.15, mfsVesselBodyH, 20), matSilverVessel);
    vessel.position.set(mfsVerticalX, mfsVesselBottomY + mfsVesselBodyH / 2, cz);
    vessel.castShadow = true;
    mfsGroup.add(vessel);

    // Spherical fixed top head (Spec 5260 Attachment-I)
    const topHead = new THREE.Mesh(
      new THREE.SphereGeometry(1.15, 20, 12, 0, Math.PI * 2, 0, Math.PI / 2),
      matSilverVessel
    );
    topHead.position.set(mfsVerticalX, mfsVesselTopY, cz);
    topHead.castShadow = true;
    mfsGroup.add(topHead);

    // Conical bottom (apex down -> Y = 1.9)
    const bottomCone = new THREE.Mesh(new THREE.ConeGeometry(1.15, 1.4, 20), matSilverVessel);
    bottomCone.rotation.x = Math.PI;
    bottomCone.position.set(mfsVerticalX, mfsVesselBottomY - 0.7, cz);
    bottomCone.castShadow = true;
    mfsGroup.add(bottomCone);

    // Spec 4500 §5.2: Horizontal Blow-Flask mounted directly below MFS separator barrel
    const downcomerNozzle = new THREE.Mesh(new THREE.CylinderGeometry(0.20, 0.20, 0.65, 12), matSilverVessel);
    downcomerNozzle.position.set(mfsVerticalX, 1.65, cz);
    mfsGroup.add(downcomerNozzle);

    const blowFlask = new THREE.Mesh(new THREE.CylinderGeometry(0.52, 0.52, 2.4, 16), matSilverVessel);
    blowFlask.rotation.z = Math.PI / 2;
    blowFlask.position.set(mfsVerticalX, 0.96, cz);
    blowFlask.castShadow = true;
    mfsGroup.add(blowFlask);

    [-1.2, 1.2].forEach((capDx) => {
      const bfCap = new THREE.Mesh(new THREE.SphereGeometry(0.52, 12, 10), matSilverVessel);
      bfCap.scale.set(0.55, 1, 1);
      bfCap.position.set(mfsVerticalX + capDx, 0.96, cz);
      mfsGroup.add(bfCap);
    });
    [-0.75, 0.75].forEach((sadDx) => {
      const bfSaddle = new THREE.Mesh(new THREE.BoxGeometry(0.24, 0.52, 0.92), matConcretePlinth);
      bfSaddle.position.set(mfsVerticalX + sadDx, 0.26, cz);
      mfsGroup.add(bfSaddle);
    });

    // Insulation & Electrical Heat Tracing collars (>= 2 °C freeze protection per Spec 4500 §5.2)
    [-0.55, 0.0, 0.55].forEach((htDx) => {
      const heatTraceBand = new THREE.Mesh(new THREE.TorusGeometry(0.56, 0.045, 8, 20), matHeatTraceOrange);
      heatTraceBand.rotation.y = Math.PI / 2;
      heatTraceBand.position.set(mfsVerticalX + htDx, 0.96, cz);
      mfsGroup.add(heatTraceBand);
    });

    // Dual separate instrument level bottles (LG / LT / LSH / LSL), online isolatable away from blow-flask nozzle
    [-0.44, 0.44].forEach((lbDz) => {
      const levelBottle = new THREE.Mesh(new THREE.CylinderGeometry(0.11, 0.11, 1.65, 12), matCadBlueSteel);
      levelBottle.position.set(mfsVerticalX - 1.42, 2.05, cz + lbDz);
      levelBottle.castShadow = true;
      mfsGroup.add(levelBottle);
      [1.35, 2.75].forEach((tapY) => {
        const bridleTap = new THREE.Mesh(new THREE.CylinderGeometry(0.04, 0.04, 0.46, 8), matSilverVessel);
        bridleTap.rotation.z = Math.PI / 2;
        bridleTap.position.set(mfsVerticalX - 1.18, tapY, cz + lbDz);
        mfsGroup.add(bridleTap);
        const isoValve = new THREE.Mesh(new THREE.SphereGeometry(0.08, 8, 8), matValveBody);
        isoValve.position.set(mfsVerticalX - 1.18, tapY, cz + lbDz);
        mfsGroup.add(isoValve);
      });
    });

    // Automatic liquid dump LCV branch (blow-flask bottom -> common automatic dump header)
    const autoDumpBranch = new THREE.Mesh(new THREE.CylinderGeometry(0.08, 0.08, 2.0, 8), matHeatTraceOrange);
    autoDumpBranch.rotation.z = Math.PI / 2;
    autoDumpBranch.position.set(mfsVerticalX + 0.92, 0.38, cz);
    mfsGroup.add(autoDumpBranch);
    const lcvValve = new THREE.Mesh(new THREE.SphereGeometry(0.18, 10, 8), matValveBody);
    lcvValve.position.set(mfsVerticalX + 1.15, 0.38, cz);
    mfsGroup.add(lcvValve);

    // Manual dump branch directly below separator/blow-flask nozzle -> common manual dump header
    const manualDumpBranch = new THREE.Mesh(new THREE.CylinderGeometry(0.075, 0.075, 1.95, 8), matHeatTraceOrange);
    manualDumpBranch.rotation.z = Math.PI / 2;
    manualDumpBranch.position.set(mfsVerticalX - 0.98, 1.62, cz);
    mfsGroup.add(manualDumpBranch);
    const manualDumpValve = new THREE.Mesh(new THREE.SphereGeometry(0.16, 10, 8), matValveBody);
    manualDumpValve.position.set(mfsVerticalX - 0.85, 1.62, cz);
    mfsGroup.add(manualDumpValve);

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

    // Access ladder on the east side
    [-0.28, 0.28].forEach((dz) => {
      const rail = new THREE.Mesh(new THREE.BoxGeometry(0.08, 9.8, 0.08), matCadBlueSteel);
      rail.position.set(mfsVerticalX + 1.42, 5.2, cz + dz);
      mfsGroup.add(rail);
    });
    for (let ry = 1.0; ry < 9.8; ry += 0.75) {
      const rung = new THREE.Mesh(new THREE.BoxGeometry(0.08, 0.06, 0.56), matCadBlueSteel);
      rung.position.set(mfsVerticalX + 1.42, ry, cz);
      mfsGroup.add(rung);
    }

    // Top maintenance ring
    const topRing = new THREE.Mesh(new THREE.TorusGeometry(1.35, 0.06, 8, 28), matCadBlueSteel);
    topRing.rotation.x = Math.PI / 2;
    topRing.position.set(mfsVerticalX, mfsVesselTopY - 0.35, cz);
    mfsGroup.add(topRing);

    // Three elevated support legs lifting separator barrel clear above below-barrel blow-flask
    [0, (2 * Math.PI) / 3, (4 * Math.PI) / 3].forEach((angle) => {
      const leg = new THREE.Mesh(new THREE.BoxGeometry(0.18, 3.3, 0.18), matCadBlueSteel);
      leg.position.set(
        mfsVerticalX + Math.cos(angle) * 1.32,
        1.65,
        cz + Math.sin(angle) * 1.32
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
      rCycloneInlet,
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
    createValveStation((mfsInletX + mfsVerticalX - 1.15) / 2, mfsInletY, cz, rCycloneInlet, { hasPlatform: false, equipKey: "cyclones" });

    // Outlet from separator top → overhead header → shared outlet collector
    createCadPipeRoute(
      [
        new THREE.Vector3(mfsVerticalX, mfsVesselTopY + 1.15, cz),
        new THREE.Vector3(mfsVerticalX, mfsOutletTopY, cz),
        new THREE.Vector3(mfsOutletHeaderX, mfsOutletTopY, cz),
        new THREE.Vector3(mfsOutletHeaderX, 2.4, cz),
      ],
      rCycloneOutlet,
      matYellowPipe,
      {
        flowArrows: 1,
        equipKey: "cyclones",
        lineKey: "cyclone_outlet_branch",
        unitLabel: mfsUnitTag,
        segmentTitle: `MFS Siklon Üst Çıkış Branşmanı (${mfsUnitTag} • L-103A)`,
        fromBoundary: `${mfsUnitTag} Siklon Üst Çıkış Nozulu`,
        toBoundary: "MFS Ortak Çıkış Kollektörü (CFS Ara Bağlantısı)",
        registerParticlePath: i === 0,
      }
    );
    createValveStation(mfsVerticalX + 5.0, mfsOutletTopY, cz, rCycloneOutlet, { hasPlatform: false, equipKey: "cyclones" });
  }

  // MFS outlet collector header: ties every cyclone top outlet to the CFS inlet distribution header.
  createCadPipeRoute(
    [
      new THREE.Vector3(mfsOutletHeaderX, 2.4, mfsStartZ),
      new THREE.Vector3(mfsOutletHeaderX, 2.4, mfsEndZ),
    ],
    rCycloneOutlet,
    matYellowPipe,
    {
      flowArrows: 4,
      equipKey: "cyclones",
      lineKey: "cyclone_outlet_branch",
      segmentTitle: "MFS Ekipman Çıkış Kollektörü (L-103A)",
      fromBoundary: "MFS Siklon Üst Çıkış Branşmanları",
      toBoundary: "CFS Kartuş Filtre Giriş Headerı Ara Bağlantısı",
      registerParticlePath: true,
    }
  );
  createCadPipeRoute(
    [
      new THREE.Vector3(mfsOutletHeaderX, 2.4, mfsCenterZ),
      new THREE.Vector3(-80, 2.4, mfsCenterZ),
      new THREE.Vector3(-80, cfsHeaderY, cfsInletHeaderZ),
      new THREE.Vector3(cfsStartX - 6, cfsHeaderY, cfsInletHeaderZ),
    ],
    rCycloneOutlet,
    matYellowPipe,
    {
      flowArrows: 2,
      equipKey: "cyclones",
      lineKey: "cyclone_outlet_branch",
      segmentTitle: "MFS ➔ CFS Ara Bağlantı Kollektörü (L-103A)",
      fromBoundary: "MFS Ortak Çıkış Kollektörü",
      toBoundary: "CFS Kartuş Filtre Giriş Dağıtım Headerı (L-104)",
    }
  );

  // Common Automatic & Manual Dump Headers (heat-traced >= 2 °C) -> Atmospheric Cyclone Separator w/ Flame Arrestor -> TK-101 Dump Tank
  const dumpDestZ = mfsEndZ + 7.5;
  const atmSepX = mfsX - 9.5;
  const atmSepZ = mfsEndZ + 6.5;
  createCadPipeRoute(
    [
      new THREE.Vector3(mfsAutoDumpHeaderX, 0.38, mfsStartZ),
      new THREE.Vector3(mfsAutoDumpHeaderX, 0.38, dumpDestZ),
      new THREE.Vector3(atmSepX, 0.38, dumpDestZ),
    ],
    0.11,
    matHeatTraceOrange,
    {
      equipKey: "cyclones",
      lineKey: "cyclone_branch",
      segmentTitle: "MFS Ortak Otomatik Drenaj Headerı (Heat Traced ≥ 2 °C)",
      fromBoundary: "MFS Alt Blow-Flask LCV Otomatik Tahliye Çıkışları",
      toBoundary: "Atmosferik Siklon Seperatör Alt Sıvı Drenaj Hattı ➔ TK-101",
    }
  );
  createCadPipeRoute(
    [
      new THREE.Vector3(mfsManualDumpHeaderX, 1.62, mfsStartZ),
      new THREE.Vector3(mfsManualDumpHeaderX, 1.62, atmSepZ),
      new THREE.Vector3(atmSepX, 1.62, atmSepZ),
    ],
    0.10,
    matHeatTraceOrange,
    {
      equipKey: "cyclones",
      lineKey: "cyclone_branch",
      segmentTitle: "MFS Ortak Manuel Drenaj Headerı (Heat Traced ≥ 2 °C)",
      fromBoundary: "Seperatör/Blow-Flask Bağlantı Altı Manuel Vanalar",
      toBoundary: "Atmosferik Sıvı/Gaz Siklon Seperatör (Flame Arrestor'lı)",
    }
  );

  // Atmospheric Liquid/Gas Cyclone Separator with Flame Arrestor Vent before TK-101
  const atmSepBody = new THREE.Mesh(new THREE.CylinderGeometry(0.75, 0.75, 2.8, 16), matVesselGrey);
  atmSepBody.position.set(atmSepX, 1.8, atmSepZ);
  mfsGroup.add(atmSepBody);
  const atmFlameArrestorVent = new THREE.Mesh(new THREE.CylinderGeometry(0.18, 0.18, 2.4, 12), matRedFire);
  atmFlameArrestorVent.position.set(atmSepX, 4.2, atmSepZ);
  mfsGroup.add(atmFlameArrestorVent);

  // Condensate Collection Sump Box (South-West of MFS, ≥ 15x blow-flask dump / min 3 m3)
  const condBox1 = new THREE.Mesh(new THREE.BoxGeometry(5.5, 3.2, 5.5), matOliveSteel);
  condBox1.position.set(mfsX - 10, 1.6, mfsEndZ + 10);
  mfsGroup.add(condBox1);
  registerClickable(condBox1, "condensate_system");

  // Small Instrument / Local Shelter South-East of MFS
  const mfsShelter = new THREE.Mesh(new THREE.BoxGeometry(5.2, 6.5, 5.2), matOliveSteel);
  mfsShelter.position.set(mfsOutletHeaderX + 6, 3.25, mfsEndZ + 10);
  mfsGroup.add(mfsShelter);

  registerClickable(mfsGroup, "cyclones");
  scene.add(mfsGroup);
  createCadGreenLabel("MFS", mfsX - 2, 0.3, mfsStartZ - 6, 12, 2.8, -Math.PI / 2, 0, 0);
  createCadPipeCallout(
    `L-103/103A • MFS EKİPMAN BORULAMASI`,
    `Giriş (${pLines.cyclone_branch?.nominal_size_in || '-'}) ➔ MFS ➔ Çıkış (${pLines.cyclone_outlet_branch?.nominal_size_in || pLines.cyclone_branch?.nominal_size_in || '-'})`,
    mfsInletX,
    10.4,
    mfsCenterZ,
    { width: 22, height: 4.3, pipeY: mfsInletY + rCycloneInlet, accentColor: "#34d399", lineKey: "cyclone_branch", equipKey: "cyclones" }
  );

  // ── 7.2 CFS: Elevated Cartridge Filter Separators with Dedicated Inlet/Outlet Headers & Ball Valves ──
  const cfsGroup = new THREE.Group();
  const cfsInletNozZ = cfsVesselZ - 3.5;
  const cfsOutletNozZ = cfsVesselZ + 4.2;

  // Dedicated CFS Inlet Distribution Header (East-West at header level Y = cfsHeaderY)
  createCadPipeRoute(
    [
      new THREE.Vector3(cfsStartX - 6, cfsHeaderY, cfsInletHeaderZ),
      new THREE.Vector3(cfsEndX, cfsHeaderY, cfsInletHeaderZ),
    ],
    rFilterInlet,
    matYellowPipe,
    {
      flowArrows: 3,
      equipKey: "cartridge_filters",
      lineKey: "filter_branch",
      segmentTitle: "CFS Giriş Dağıtım Headerı (L-104)",
      fromBoundary: "MFS Çıkış Ara Kollektörü Tie-In Noktası",
      toBoundary: "CFS Kartuş Filtre Giriş Branşman Yükselişleri (F-101..N)",
      registerParticlePath: true,
    }
  );

  for (let i = 0; i < numFilters; i++) {
    const fx = numFilters === 1 ? cfsCenterX : cfsStartX + i * cfsPitchX;
    const cfsUnitTag = `F-10${i + 1}`;
    // Horizontal Cylindrical Filter Vessel elevated above header pipes on taller piers & steel saddles
    const fltVessel = new THREE.Mesh(new THREE.CylinderGeometry(1.0, 1.0, 12.0, 22), matSilverVessel);
    fltVessel.rotation.x = Math.PI / 2;
    fltVessel.position.set(fx, cfsVesselY, cfsVesselZ);
    fltVessel.castShadow = true;
    cfsGroup.add(fltVessel);

    // Dished heads at both ends
    [cfsVesselZ + 6.0, cfsVesselZ - 6.0].forEach((hz) => {
      const head = new THREE.Mesh(new THREE.SphereGeometry(1.0, 20, 12), matSilverVessel);
      head.scale.z = 0.38;
      head.position.set(fx, cfsVesselY, hz);
      head.castShadow = true;
      cfsGroup.add(head);
    });

    // Taller concrete piers (Y: 0..1.4) + elevated steel saddle supports (Y: 1.4..3.9)
    [cfsVesselZ - 4.0, cfsVesselZ + 4.0].forEach((sz) => {
      const saddle = new THREE.Mesh(new THREE.BoxGeometry(2.0, 2.5, 0.65), matCadBlueSteel);
      saddle.position.set(fx, 2.65, sz);
      saddle.castShadow = true;
      cfsGroup.add(saddle);
      const pad = new THREE.Mesh(new THREE.BoxGeometry(2.6, 1.4, 1.2), matConcretePlinth);
      pad.position.set(fx, 0.7, sz);
      pad.castShadow = true;
      cfsGroup.add(pad);
    });

    // Top-north inlet nozzle + flange
    const inletNozzle = new THREE.Mesh(new THREE.CylinderGeometry(0.52, 0.52, 0.8, 16), matSilverVessel);
    inletNozzle.position.set(fx, cfsVesselY + 1.0, cfsInletNozZ);
    cfsGroup.add(inletNozzle);
    const inletFlange = new THREE.Mesh(new THREE.CylinderGeometry(0.7, 0.7, 0.15, 16), matFlangeSteel);
    inletFlange.position.set(fx, cfsVesselY + 1.43, cfsInletNozZ);
    cfsGroup.add(inletFlange);

    // Top-south outlet nozzle + flange (keeps the South QOC hinged cover completely unobstructed)
    const outletNozzle = new THREE.Mesh(new THREE.CylinderGeometry(0.52, 0.52, 0.8, 16), matSilverVessel);
    outletNozzle.position.set(fx, cfsVesselY + 1.0, cfsOutletNozZ);
    cfsGroup.add(outletNozzle);
    const outletFlange = new THREE.Mesh(new THREE.CylinderGeometry(0.7, 0.7, 0.15, 16), matFlangeSteel);
    outletFlange.position.set(fx, cfsVesselY + 1.43, cfsOutletNozZ);
    cfsGroup.add(outletFlange);

    // Downcomer nozzle + Below-barrel Horizontal CFS Blow-Flask + Self-Regulating Heat Tracing (>= 2 °C) & Level Bottle (Spec 5210 §4.1 / Özel §4.8.2)
    const drain = new THREE.Mesh(new THREE.CylinderGeometry(0.18, 0.18, 1.85, 12), matSilverVessel);
    drain.position.set(fx, 2.9, cfsVesselZ);
    cfsGroup.add(drain);

    const cfsBlowFlask = new THREE.Mesh(new THREE.CylinderGeometry(0.46, 0.46, 4.2, 16), matSilverVessel);
    cfsBlowFlask.rotation.x = Math.PI / 2;
    cfsBlowFlask.position.set(fx, 1.48, cfsVesselZ);
    cfsBlowFlask.castShadow = true;
    cfsGroup.add(cfsBlowFlask);

    [cfsVesselZ - 2.1, cfsVesselZ + 2.1].forEach((czCap) => {
      const bfEnd = new THREE.Mesh(new THREE.SphereGeometry(0.46, 12, 10), matSilverVessel);
      bfEnd.scale.z = 0.5;
      bfEnd.position.set(fx, 1.48, czCap);
      cfsGroup.add(bfEnd);
    });
    [cfsVesselZ - 1.35, cfsVesselZ + 1.35].forEach((szBf) => {
      const bfSad = new THREE.Mesh(new THREE.BoxGeometry(0.95, 1.0, 0.24), matConcretePlinth);
      bfSad.position.set(fx, 0.5, szBf);
      cfsGroup.add(bfSad);
    });
    [-1.1, 0.0, 1.1].forEach((htDz) => {
      const htBand = new THREE.Mesh(new THREE.TorusGeometry(0.50, 0.045, 8, 20), matHeatTraceOrange);
      htBand.position.set(fx, 1.48, cfsVesselZ + htDz);
      cfsGroup.add(htBand);
    });

    // Dedicated CFS instrument level bottle (LG/LT/LSH/LSL) + LCV drain valve
    const cfsLevelBottle = new THREE.Mesh(new THREE.CylinderGeometry(0.10, 0.10, 1.45, 10), matCadBlueSteel);
    cfsLevelBottle.position.set(fx - 1.25, 1.9, cfsVesselZ);
    cfsGroup.add(cfsLevelBottle);
    const cfsLcv = new THREE.Mesh(new THREE.SphereGeometry(0.18, 10, 8), matValveBody);
    cfsLcv.position.set(fx, 0.72, cfsVesselZ + 2.65);
    cfsGroup.add(cfsLcv);

    // Quick-Opening Closure (QOC) facing South + Davit swing arm (Spec 5210 §4.1 / Özel §4.8.2)
    const cap = new THREE.Mesh(new THREE.CylinderGeometry(1.12, 1.12, 0.45, 20), matYellowPipe);
    cap.rotation.x = Math.PI / 2;
    cap.position.set(fx, cfsVesselY, cfsVesselZ + 6.15);
    cfsGroup.add(cap);
    const qocDavit = new THREE.Group();
    const davitPost = new THREE.Mesh(new THREE.CylinderGeometry(0.08, 0.08, 1.85, 10), matCadBlueSteel);
    davitPost.position.set(fx + 1.22, cfsVesselY + 0.55, cfsVesselZ + 6.0);
    const davitArm = new THREE.Mesh(new THREE.BoxGeometry(1.25, 0.12, 0.12), matCadBlueSteel);
    davitArm.position.set(fx + 0.6, cfsVesselY + 1.42, cfsVesselZ + 6.15);
    qocDavit.add(davitPost, davitArm);
    cfsGroup.add(qocDavit);

    // Elevated side steel access grating platforms + support columns along each CFS vessel
    const sideWalk = new THREE.Mesh(new THREE.BoxGeometry(1.9, 0.16, 11.5), matOliveSteel);
    sideWalk.position.set(fx + 1.9, 4.0, cfsVesselZ);
    cfsGroup.add(sideWalk);
    [
      [fx + 1.15, cfsVesselZ - 5.0],
      [fx + 2.65, cfsVesselZ - 5.0],
      [fx + 1.15, cfsVesselZ + 5.0],
      [fx + 2.65, cfsVesselZ + 5.0],
    ].forEach(([lx, lz]) => {
      const wLeg = new THREE.Mesh(new THREE.BoxGeometry(0.18, 4.0, 0.18), matCadBlueSteel);
      wLeg.position.set(lx, 2.0, lz);
      cfsGroup.add(wLeg);
    });

    // Per-filter Inlet Branch rising from CFS Inlet Header over to top-north nozzle + equal-diameter flanged ball valve
    createCadPipeRoute(
      [
        new THREE.Vector3(fx, cfsHeaderY, cfsInletHeaderZ),
        new THREE.Vector3(fx, 6.5, cfsInletHeaderZ),
        new THREE.Vector3(fx, 6.5, cfsInletNozZ),
        new THREE.Vector3(fx, cfsVesselY + 1.0, cfsInletNozZ),
      ],
      rFilterInlet,
      matYellowPipe,
      {
        flowArrows: 1,
        equipKey: "cartridge_filters",
        lineKey: "filter_branch",
        unitLabel: cfsUnitTag,
        segmentTitle: `CFS Kartuş Filtre Giriş Branşmanı (${cfsUnitTag} • L-104)`,
        fromBoundary: "CFS Giriş Dağıtım Headerı (Z = -100m)",
        toBoundary: `${cfsUnitTag} Kartuş Filtre Üst-Kuzey Giriş Nozulu`,
      }
    );
    createValveStation(fx, 6.5, (cfsInletHeaderZ + cfsInletNozZ) / 2, rFilterInlet, { hasPlatform: false, rotationY: Math.PI / 2, equipKey: "cartridge_filters" });

    // Per-filter Outlet Branch leaving top-south nozzle down to CFS Outlet Collection Header + equal-diameter flanged ball valve
    createCadPipeRoute(
      [
        new THREE.Vector3(fx, cfsVesselY + 1.0, cfsOutletNozZ),
        new THREE.Vector3(fx, 6.4, cfsOutletNozZ),
        new THREE.Vector3(fx, 6.4, cfsOutletHeaderZ),
        new THREE.Vector3(fx, cfsHeaderY, cfsOutletHeaderZ),
      ],
      rFilterOutlet,
      matYellowPipe,
      {
        flowArrows: 1,
        equipKey: "cartridge_filters",
        lineKey: "filter_outlet_branch",
        unitLabel: cfsUnitTag,
        segmentTitle: `CFS Kartuş Filtre Çıkış Branşmanı (${cfsUnitTag} • L-104A)`,
        fromBoundary: `${cfsUnitTag} Kartuş Filtre Üst-Güney Çıkış Nozulu`,
        toBoundary: "CFS Çıkış Toplama Headerı (Z = -56m)",
        registerParticlePath: i === 0,
      }
    );
    createValveStation(fx, 6.4, (cfsOutletNozZ + cfsOutletHeaderZ) / 2, rFilterOutlet, { hasPlatform: false, rotationY: Math.PI / 2, equipKey: "cartridge_filters" });
  }

  // Dedicated CFS Outlet Collection Header (single East-West header at Y = cfsHeaderY feeding Station Suction Mid-Spine)
  const cfsOutletStartX = numFilters === 1 ? cfsCenterX : cfsStartX;
  createCadPipeRoute(
    [
      new THREE.Vector3(cfsOutletStartX, cfsHeaderY, cfsOutletHeaderZ),
      new THREE.Vector3(cfsOutletTieX, cfsHeaderY, cfsOutletHeaderZ),
    ],
    rFilterOutlet,
    matYellowPipe,
    {
      flowArrows: 2,
      equipKey: "cartridge_filters",
      lineKey: "filter_outlet_branch",
      segmentTitle: "CFS Çıkış Toplama Headerı (L-104A)",
      fromBoundary: "CFS Kartuş Filtre Ünite Çıkış Branşmanları",
      toBoundary: "Station Suction Header (Filtrelenmiş Ana Omurga Tie-In Noktası)",
      registerParticlePath: true,
    }
  );

  // Translucent Maintenance Envelope East of CFS
  const cfsEnv = new THREE.Mesh(new THREE.BoxGeometry(8, 7.2, 16), matEnvelopeBox);
  cfsEnv.position.set(cfsEndX + 6.5, 3.6, cfsVesselZ);
  scene.add(cfsEnv);
  envelopeMeshes.push(cfsEnv);

  const condBox2 = new THREE.Mesh(new THREE.BoxGeometry(5.0, 2.8, 5.0), matOliveSteel);
  condBox2.position.set(cfsCenterX, 1.4, cfsOutletHeaderZ + 8);
  cfsGroup.add(condBox2);

  registerClickable(cfsGroup, "cartridge_filters");
  scene.add(cfsGroup);
  createCadGreenLabel("CFS", cfsCenterX, 0.3, cfsInletHeaderZ - 7, 12, 2.8, -Math.PI / 2, 0, 0);
  createCadPipeCallout(
    `L-104/104A • CFS HEADER & VANALI BRANŞMANLAR`,
    `Giriş (${pLines.filter_branch?.nominal_size_in || '-'}) ➔ Yükseltilmiş F-101..${numFilters} ➔ Çıkış (${pLines.filter_outlet_branch?.nominal_size_in || pLines.filter_branch?.nominal_size_in || '-'})`,
    cfsCenterX,
    9.4,
    cfsOutletHeaderZ,
    { width: 24, height: 4.5, pipeY: 6.4 + rFilterOutlet, accentColor: "#34d399", lineKey: "filter_outlet_branch", equipKey: "cartridge_filters" }
  );

  // Station Suction Header Mid-Spine: Filtered main header routing from CFS across North Road to TC Suction Connection Header
  createCadPipeRoute(
    [
      new THREE.Vector3(cfsOutletTieX, cfsHeaderY, cfsOutletHeaderZ),
      new THREE.Vector3(cfsOutletTieX, cfsHeaderY, -30),
      new THREE.Vector3(cfsOutletTieX, 1.5, frontSuctionZ),
    ],
    rSuctHeader,
    matYellowPipe,
    {
      flowArrows: 3,
      equipKey: "turbo_compressors",
      lineKey: "comp_suction_header",
      segmentTitle: "Station Suction Header (CFS Çıkışı ➔ TC Suction Bağlantı Headerı)",
      fromBoundary: "CFS Çıkış Toplama Headerı Ana Dönüş Tie-In Noktası",
      toBoundary: "Turbo-Kompresör Üniteleri Suction Bağlantı Headerı",
      registerParticlePath: true,
    }
  );
  createCadPipeCallout(
    `L-105 • STATION SUCTION HEADER (ANA OMURGA)`,
    `CFS Çıkışı ➔ TC Ünite Suction Bağlantı Headerı (${compSuctHeaderLine.nominal_size_in || suctLine.nominal_size_in || '48"'})`,
    cfsOutletTieX,
    6.2,
    -30,
    { width: 26, height: 4.6, pipeY: cfsHeaderY + rSuctHeader, accentColor: "#38bdf8", lineKey: "comp_suction_header", equipKey: "turbo_compressors" }
  );

  // ── 7.2A FUEL GAS CONDITIONING & METERING SKID (Spec 4500 §8.1-8.5 & Özel §4.8.5) ──
  // Top take-off strictly DOWNSTREAM of main CFS filters and UPSTREAM of Gas Cooler & Recycle tie-in
  const fuelGasSkid = new THREE.Group();
  const fgX = cfsOutletTieX + 14.5;
  const fgZ = -29.5;
  const fgPad = new THREE.Mesh(new THREE.BoxGeometry(14.5, 0.36, 7.6), matConcretePlinth);
  fgPad.position.set(fgX, 0.18, fgZ);
  fgPad.receiveShadow = true;
  fuelGasSkid.add(fgPad);

  // Horizontal 1 µm Sock Separator + Below-Barrel Heat-Traced Blowflask
  const fgSepBarrel = new THREE.Mesh(new THREE.CylinderGeometry(0.62, 0.62, 3.6, 16), matCadBlueSteel);
  fgSepBarrel.rotation.z = Math.PI / 2;
  fgSepBarrel.position.set(fgX - 3.6, 2.25, fgZ - 1.4);
  fgSepBarrel.castShadow = true;
  fuelGasSkid.add(fgSepBarrel);

  const fgBlowFlask = new THREE.Mesh(new THREE.CylinderGeometry(0.28, 0.28, 2.2, 12), matSilverVessel);
  fgBlowFlask.rotation.z = Math.PI / 2;
  fgBlowFlask.position.set(fgX - 3.6, 1.05, fgZ - 1.4);
  fuelGasSkid.add(fgBlowFlask);
  [-0.6, 0.0, 0.6].forEach((htDx) => {
    const htBand = new THREE.Mesh(new THREE.TorusGeometry(0.32, 0.035, 8, 16), matHeatTraceOrange);
    htBand.rotation.y = Math.PI / 2;
    htBand.position.set(fgX - 3.6 + htDx, 1.05, fgZ - 1.4);
    fuelGasSkid.add(htBand);
  });

  // 1+1 Gas/Glycol Fuel Pre-Heaters (20 ± 5 °C) + 2x100% Parallel Pressure Reduction & Metering Runs
  [-0.9, 1.1].forEach((hzDz, hIdx) => {
    const fgHeater = new THREE.Mesh(new THREE.CylinderGeometry(0.32, 0.32, 3.2, 14), matHeatTraceOrange);
    fgHeater.rotation.z = Math.PI / 2;
    fgHeater.position.set(fgX + 0.8, 1.65 + hIdx * 0.85, fgZ + hzDz);
    fuelGasSkid.add(fgHeater);

    const regRun = new THREE.Mesh(new THREE.CylinderGeometry(0.14, 0.14, 3.4, 10), matTealUtilityPipe);
    regRun.rotation.z = Math.PI / 2;
    regRun.position.set(fgX + 4.4, 1.45, fgZ + hzDz);
    fuelGasSkid.add(regRun);
    const prvBody = new THREE.Mesh(new THREE.SphereGeometry(0.26, 10, 10), matValveBody);
    prvBody.position.set(fgX + 4.4, 1.45, fgZ + hzDz);
    fuelGasSkid.add(prvBody);
  });

  // Top-of-pipe take-off from post-CFS Station Suction Spine (316 SS fuel feed)
  createCadPipeRoute(
    [
      new THREE.Vector3(cfsOutletTieX, cfsHeaderY + rSuctHeader * 0.85, -30),
      new THREE.Vector3(cfsOutletTieX, cfsHeaderY + 1.6, -30),
      new THREE.Vector3(fgX - 6.0, cfsHeaderY + 1.6, -30),
      new THREE.Vector3(fgX - 5.4, 2.25, fgZ - 1.4),
    ],
    0.16,
    matTealUtilityPipe,
    {
      flowArrows: 1,
      equipKey: "fuel_gas",
      segmentTitle: "Yakıt Gazı Çekiş Hattı (CFS Çıkışı Sonrası / Soğutucu Öncesi)",
      fromBoundary: "Ana CFS Kartuş Filtre Çıkışı (Station Suction Spine)",
      toBoundary: "FG-101 Yakıt Gazı Şartlandırma Skidi (1 µm + 20 °C Eşanjör)",
    }
  );
  registerClickable(fuelGasSkid, "fuel_gas");
  scene.add(fuelGasSkid);
  createCadGreenLabel("FUEL GAS SKID FG-101", fgX, 4.1, fgZ, 13.5, 2.4, -Math.PI / 2, 0, 0);

  // ── 7.2B STATION RECYCLE CONTROL VALVE SKID (Spec 4-NGTL 0-CS-M-002-4500 §5.8) ──
  // Offtake downstream of Gas Cooler on Station Discharge Header (dischargeReturnZ)
  // through 2 flanking block valves + central Globe/Plug-in-Cage PCV with acoustic canopy,
  // returning to Station Suction Header downstream of CFS and upstream of all compressor units.
  const stationRecycleSkid = new THREE.Group();
  const recycleSkidPad = new THREE.Mesh(
    new THREE.BoxGeometry(15.2, 0.36, 5.8),
    matConcretePlinth
  );
  recycleSkidPad.position.set(stationRecycleValveX, 0.18, stationRecycleZ);
  recycleSkidPad.receiveShadow = true;
  stationRecycleSkid.add(recycleSkidPad);

  // Pipe supports under elevated Station Recycle skid run
  [-5.8, 0, 5.8].forEach((dx) => {
    const pier = new THREE.Mesh(new THREE.BoxGeometry(0.45, stationRecycleY - rAntiSurgeHeader, 0.7), matConcretePlinth);
    pier.position.set(stationRecycleValveX + dx, (stationRecycleY - rAntiSurgeHeader) / 2, stationRecycleZ);
    stationRecycleSkid.add(pier);
  });

  createCadPipeRoute(
    [
      new THREE.Vector3(stationRecycleTakeoffX, coolerReturnY, dischargeReturnZ),
      new THREE.Vector3(stationRecycleTakeoffX, stationRecycleY, dischargeReturnZ),
      new THREE.Vector3(stationRecycleTakeoffX, stationRecycleY, stationRecycleZ),
      new THREE.Vector3(cfsOutletTieX + 4.0, stationRecycleY, stationRecycleZ),
      new THREE.Vector3(cfsOutletTieX + 4.0, cfsHeaderY, -30),
      new THREE.Vector3(cfsOutletTieX, cfsHeaderY, -30),
    ],
    rAntiSurgeHeader,
    matYellowPipe,
    {
      flowArrows: 3,
      equipKey: "station_recycle",
      lineKey: "station_recycle",
      segmentTitle: "İstasyon Recycle Kontrol Vanası Hattı (PCV-101 • Spec 4500 §5.8)",
      fromBoundary: "Station Discharge Header (Gaz Soğutucu Çıkışı Sonrası)",
      toBoundary: "Station Suction Header (CFS Çıkışı Sonrası / Kompresör Emiş Öncesi)",
      registerParticlePath: true,
    }
  );

  // Upstream & Downstream Flanking Block Valves (Spec 4500 §5.8: block valves on both sides of PCV)
  createValveStation(stationRecycleValveX + 4.4, stationRecycleY, stationRecycleZ, rAntiSurgeHeader, {
    hasPlatform: false,
    hasActuator: false,
    equipKey: "station_recycle",
  });
  createValveStation(stationRecycleValveX - 4.4, stationRecycleY, stationRecycleZ, rAntiSurgeHeader, {
    hasPlatform: false,
    hasActuator: false,
    equipKey: "station_recycle",
  });

  // Central Station Recycle Control Valve (Globe / Plug-in-Cage + Electropneumatic & Power-Gas Bottle + NRV Check)
  createValveStation(stationRecycleValveX, stationRecycleY, stationRecycleZ, rAntiSurgeHeader, {
    hasPlatform: false,
    hasActuator: true,
    equipKey: "station_recycle",
    valveColorMat: matCyanArrow,
  });
  const recycleNrv = new THREE.Mesh(
    new THREE.ConeGeometry(rAntiSurgeHeader * 1.35, rAntiSurgeHeader * 2.4, 16),
    matFlangeSteel
  );
  recycleNrv.rotation.z = Math.PI / 2;
  recycleNrv.position.set(stationRecycleValveX - 2.3, stationRecycleY, stationRecycleZ);
  stationRecycleSkid.add(recycleNrv);
  const recyclePowerGasBottle = new THREE.Mesh(
    new THREE.CylinderGeometry(0.28, 0.28, 1.85, 14),
    matCyanArrow
  );
  recyclePowerGasBottle.position.set(stationRecycleValveX + 1.6, 1.25, stationRecycleZ + 1.6);
  stationRecycleSkid.add(recyclePowerGasBottle);

  // Sound-Proofing Acoustic Canopy over Station Recycle Control Valve (Spec 4500 §5.8)
  const stationRecycleCanopy = new THREE.Group();
  stationRecycleCanopy.position.set(stationRecycleValveX, 0, stationRecycleZ);
  const canopyW = 4.2;
  const canopyH = 3.1;
  const canopyD = 3.4;
  const canopyBaseY = stationRecycleY - 0.55;
  const matAcousticPanel = new THREE.MeshStandardMaterial({
    color: 0x334155,
    roughness: 0.55,
    metalness: 0.35,
    transparent: true,
    opacity: 0.42,
    depthWrite: false,
  });
  const canopyShell = new THREE.Mesh(
    new THREE.BoxGeometry(canopyW, canopyH, canopyD),
    matAcousticPanel
  );
  canopyShell.position.y = canopyBaseY + canopyH / 2;
  stationRecycleCanopy.add(canopyShell);
  const canopyRoof = new THREE.Mesh(
    new THREE.BoxGeometry(canopyW + 0.35, 0.24, canopyD + 0.35),
    matOliveSteel
  );
  canopyRoof.position.y = canopyBaseY + canopyH + 0.12;
  canopyRoof.castShadow = true;
  stationRecycleCanopy.add(canopyRoof);
  [
    [-canopyW / 2, -canopyD / 2],
    [canopyW / 2, -canopyD / 2],
    [-canopyW / 2, canopyD / 2],
    [canopyW / 2, canopyD / 2],
  ].forEach(([px, pz]) => {
    const post = new THREE.Mesh(new THREE.BoxGeometry(0.16, canopyBaseY + canopyH, 0.16), matCadBlueSteel);
    post.position.set(px, (canopyBaseY + canopyH) / 2, pz);
    stationRecycleCanopy.add(post);
  });
  const canopyTrim = new THREE.LineSegments(
    new THREE.EdgesGeometry(new THREE.BoxGeometry(canopyW, canopyH, canopyD)),
    new THREE.LineBasicMaterial({ color: 0xfacc15 })
  );
  canopyTrim.position.y = canopyBaseY + canopyH / 2;
  stationRecycleCanopy.add(canopyTrim);
  stationRecycleSkid.add(stationRecycleCanopy);

  registerClickable(stationRecycleSkid, "station_recycle");
  scene.add(stationRecycleSkid);
  createCadPipeCallout(
    `PCV-101 • STATION RECYCLE VALVE (SPEC 4500 §5.8)`,
    `Soğutucu Çıkışı ➔ 2x Blok Vana + Akustik Kabin + PCV (${pLines.station_recycle?.nominal_size_in || '6"'}) ➔ Emiş`,
    stationRecycleValveX,
    stationRecycleY + 4.8,
    stationRecycleZ,
    { width: 28, height: 4.7, pipeY: stationRecycleY + rAntiSurgeHeader, accentColor: "#22d3ee", lineKey: "station_recycle", equipKey: "station_recycle" }
  );

  // ── 7.3 GAS COOLER: Elevated Fin-Fan Air Cooler Bank ──
  const coolerGroup = new THREE.Group();
  const rBayHeader = Math.max(rBayInletHeader, rBayOutletHeader);
  const desiredBayW = desiredCoolerBayW;
  const coolerWidth = Math.max(18, Math.min(120, numCoolerBays * desiredBayW));
  const coolerEndX = coolerX0 + coolerWidth;
  const coolerDepth = Math.max(14, Math.min(28, 12 + coolerTubeLength * 0.8));
  const coolerSouthFaceZ = coolerCenterZ + coolerDepth / 2;
  const coolerDeckY = 7.8;

  // Per-bay front headers sit outside the South tube sheet with diameter-aware vertical and Z step
  // so both headers and all bay-to-bay boundaries are clearly separated and never occlude/overlap.
  const bayOutletHdrY = coolerDeckY + 0.55;
  const bayInletHdrY = Math.max(coolerDeckY + 2.15, bayOutletHdrY + 2 * rBayHeader + 0.75);
  const bayInletHeaderZ = coolerSouthFaceZ + 0.85;
  const bayOutletHeaderZ = bayInletHeaderZ + Math.max(0.75, rBayHeader * 0.85);
  const bayHeaderZ = bayInletHeaderZ;
  const coolerRiserClimbZ = bayOutletHeaderZ + rBayHeader + 1.15;
  const coolerValveZ = (coolerInletHeaderZ + coolerRiserClimbZ) / 2;

  // Elevated Fin-Fan Plenum Box
  const plenum = new THREE.Mesh(new THREE.BoxGeometry(coolerWidth, 2.2, Math.max(10, coolerDepth - 0.6)), matVesselGrey);
  plenum.position.set(coolerX0 + coolerWidth / 2, coolerDeckY + 1.1, coolerCenterZ);
  plenum.castShadow = true;
  plenum.receiveShadow = true;
  coolerGroup.add(plenum);

  // Outer casing end plates
  [coolerX0 + 0.35, coolerEndX - 0.35].forEach((hx) => {
    const endSheet = new THREE.Mesh(
      new THREE.BoxGeometry(0.28, 1.85, coolerDepth * 0.9),
      matCadBlueSteel
    );
    endSheet.position.set(hx, coolerDeckY + 1.15, coolerCenterZ);
    coolerGroup.add(endSheet);
  });

  // Fin-tube bank side panels
  [-1, 1].forEach((side) => {
    const bank = new THREE.Mesh(
      new THREE.BoxGeometry(coolerWidth - 1.6, 1.15, 0.22),
      matFinTube
    );
    bank.position.set(coolerX0 + coolerWidth / 2, coolerDeckY + 1.15, coolerCenterZ + side * (coolerDepth / 2 - 0.22));
    coolerGroup.add(bank);
  });

  // Support Portal Bents at each bay boundary so front bay headers and risers stay unobstructed
  const bayW = (coolerWidth - 2) / numCoolerBays;
  for (let b = 0; b <= numCoolerBays; b++) {
    const bentX = coolerX0 + 1 + b * bayW;
    const colOffsetZ = Math.max(5.5, coolerDepth / 2 - 0.25);
    [-colOffsetZ, colOffsetZ].forEach((dz) => {
      const col = new THREE.Mesh(new THREE.BoxGeometry(0.52, coolerDeckY, 0.52), matCadBlueSteel);
      col.position.set(bentX, coolerDeckY / 2, coolerCenterZ + dz);
      col.castShadow = true;
      coolerGroup.add(col);
    });
    const bayDivider = new THREE.Mesh(new THREE.BoxGeometry(0.24, 2.1, coolerDepth * 0.92), matCadBlueSteel);
    bayDivider.position.set(bentX, coolerDeckY + 1.15, coolerCenterZ);
    coolerGroup.add(bayDivider);
  }

  // Dynamic Fin-Fan Bays: Louvers, Fans, Dedicated Bay Inlet & Outlet Headers, and Bay Risers
  for (let b = 0; b < numCoolerBays; b++) {
    const bx = coolerX0 + 1 + (b + 0.5) * bayW;
    // Per-bay front tube sheet (supports this bay's dedicated inlet and outlet headers)
    const bayTubeSheet = new THREE.Mesh(
      new THREE.BoxGeometry(bayW * 0.80, 1.85, 0.24),
      matCadBlueSteel
    );
    bayTubeSheet.position.set(bx, coolerDeckY + 1.15, coolerSouthFaceZ - 0.15);
    coolerGroup.add(bayTubeSheet);

    // Louver frame with slats
    const louverFrame = new THREE.Mesh(new THREE.BoxGeometry(bayW * 0.9, 0.2, coolerDepth - 2), matVesselGrey);
    louverFrame.position.set(bx, coolerDeckY + 2.3, coolerCenterZ);
    coolerGroup.add(louverFrame);
    for (let s = 0; s < 6; s++) {
      const slat = new THREE.Mesh(new THREE.BoxGeometry(bayW * 0.86, 0.05, 0.22), matPurlinBrown);
      slat.position.set(bx, coolerDeckY + 2.34, coolerCenterZ - (coolerDepth - 3) / 2 + s * ((coolerDepth - 3) / 5));
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
      shroud.position.set(bx, coolerDeckY + 2.45, coolerCenterZ + dz);
      coolerGroup.add(shroud);

      const fanRing = new THREE.Mesh(new THREE.TorusGeometry(fanRadius, 0.08, 8, 32), matCadBlueSteel);
      fanRing.rotation.x = Math.PI / 2;
      fanRing.position.set(bx, coolerDeckY + 2.72, coolerCenterZ + dz);
      coolerGroup.add(fanRing);

      const fanHub = new THREE.Group();
      fanHub.position.set(bx, coolerDeckY + 2.48, coolerCenterZ + dz);
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
      motor.position.set(bx + fanRadius * 0.55, coolerDeckY + 3.0, coolerCenterZ + dz);
      coolerGroup.add(motor);
      const beltGuard = new THREE.Mesh(new THREE.BoxGeometry(fanRadius * 0.7, 0.16, 0.35), matCadBlueSteel);
      beltGuard.position.set(bx + fanRadius * 0.3, coolerDeckY + 2.95, coolerCenterZ + dz);
      coolerGroup.add(beltGuard);
    });

    // Dedicated Inlet Header (Upper) & Outlet Header (Lower, forward step) for Bay #b+1
    const bayRiserDx = Math.max(rCoolerRiser * 1.38, Math.min(2.0, bayW * 0.22));
    const bayHdrHalfW = Math.max(bayRiserDx + rCoolerRiser * 0.35, bayW * 0.31);
    const bayInletX = bx - bayRiserDx;
    const bayOutletX = bx + bayRiserDx;

    createCadPipeRoute(
      [
        new THREE.Vector3(bx - bayHdrHalfW, bayInletHdrY, bayInletHeaderZ),
        new THREE.Vector3(bx + bayHdrHalfW, bayInletHdrY, bayInletHeaderZ),
      ],
      rBayInletHeader,
      matYellowPipe,
      {
        flowArrows: 0,
        flangeEnds: true,
        capEnds: true,
        equipKey: "air_coolers",
        lineKey: "cooler_bay_inlet_header",
        parentLineKey: "cooler_inlet",
        unitLabel: `E-101-BAY${b + 1}-IN-HDR`,
        segmentTitle: `Gaz Soğutucu Bay #${b + 1} Giriş Headerı`,
        fromBoundary: `Bay #${b + 1} Giriş Borusu (Riser • L-112)`,
        toBoundary: `Bay #${b + 1} Fin-Tüp Demeti Giriş Nozulları`,
        derivedOdMm: coolerBayInletHdrLine.od_mm || coolerRiserLine.od_mm || null,
        derivedNps: coolerBayInletHdrLine.nominal_size_in || coolerRiserLine.nominal_size_in || null,
      }
    );
    createCadPipeRoute(
      [
        new THREE.Vector3(bx - bayHdrHalfW, bayOutletHdrY, bayOutletHeaderZ),
        new THREE.Vector3(bx + bayHdrHalfW, bayOutletHdrY, bayOutletHeaderZ),
      ],
      rBayOutletHeader,
      matYellowPipe,
      {
        flowArrows: 0,
        flangeEnds: true,
        capEnds: true,
        equipKey: "air_coolers",
        lineKey: "cooler_bay_outlet_header",
        parentLineKey: "cooler_outlet",
        unitLabel: `E-101-BAY${b + 1}-OUT-HDR`,
        segmentTitle: `Gaz Soğutucu Bay #${b + 1} Çıkış Headerı`,
        fromBoundary: `Bay #${b + 1} Fin-Tüp Demeti Çıkış Nozulları`,
        toBoundary: `Bay #${b + 1} Çıkış Borusu (Riser • L-112C)`,
        derivedOdMm: coolerBayOutletHdrLine.od_mm || coolerOutletRiserLine.od_mm || null,
        derivedNps: coolerBayOutletHdrLine.nominal_size_in || coolerOutletRiserLine.nominal_size_in || null,
      }
    );

    // Tube-sheet feeder nozzles tying both headers into this bay's fin-tube bundle
    [-bayHdrHalfW * 0.45, bayHdrHalfW * 0.45].forEach((nxOff) => {
      [
        [bayInletHdrY, bayInletHeaderZ],
        [bayOutletHdrY, bayOutletHeaderZ],
      ].forEach(([hdrY, hdrZ]) => {
        const nozzleLen = Math.max(0.4, hdrZ - (coolerSouthFaceZ - 0.15));
        const nozzleMidZ = (hdrZ + (coolerSouthFaceZ - 0.15)) / 2;
        const nozzle = new THREE.Mesh(
          new THREE.CylinderGeometry(rCoolerRiser * 0.58, rCoolerRiser * 0.58, nozzleLen, 12),
          matYellowPipe
        );
        nozzle.rotation.x = Math.PI / 2;
        nozzle.position.set(bx + nxOff, hdrY, nozzleMidZ);
        coolerGroup.add(nozzle);

        const tsFlange = new THREE.Mesh(
          new THREE.CylinderGeometry(rCoolerRiser * 0.85, rCoolerRiser * 0.85, 0.14, 14),
          matFlangeSteel
        );
        tsFlange.rotation.x = Math.PI / 2;
        tsFlange.position.set(bx + nxOff, hdrY, coolerSouthFaceZ - 0.04);
        coolerGroup.add(tsFlange);
      });
    });

    // Bay #b+1 Inlet & Outlet Riser Pipes connected directly to this bay's own Inlet & Outlet Headers
    createCadPipeRoute(
      [
        new THREE.Vector3(bayInletX, 1.6, coolerInletHeaderZ),
        new THREE.Vector3(bayInletX, 1.6, coolerRiserClimbZ),
        new THREE.Vector3(bayInletX, bayInletHdrY, coolerRiserClimbZ),
        new THREE.Vector3(bayInletX, bayInletHdrY, bayInletHeaderZ),
      ],
      rCoolerRiser,
      matYellowPipe,
      {
        bendRadius: Math.max(0.55, rCoolerRiser * 2.0),
        flowArrows: 1,
        reverseFlow: false,
        equipKey: "air_coolers",
        lineKey: "cooler_bay_risers",
        unitLabel: `E-101-B${b + 1}-IN`,
        segmentTitle: `Gaz Soğutucu Bay #${b + 1} Giriş Borusu (Riser)`,
        fromBoundary: "Gaz Soğutucu Sıcak Giriş Manifoldu (L-111)",
        toBoundary: `Bay #${b + 1} Giriş Headerı (E-101-BAY${b + 1})`,
        registerParticlePath: b === 0,
      }
    );
    createCadPipeRoute(
      [
        new THREE.Vector3(bayOutletX, bayOutletHdrY, bayOutletHeaderZ),
        new THREE.Vector3(bayOutletX, bayOutletHdrY, coolerRiserClimbZ),
        new THREE.Vector3(bayOutletX, coolerOutletCrossY, coolerRiserClimbZ),
        new THREE.Vector3(bayOutletX, coolerOutletCrossY, coolerOutletHeaderZ),
        new THREE.Vector3(bayOutletX, 1.6, coolerOutletHeaderZ),
      ],
      rCoolerOutletRiser,
      matYellowPipe,
      {
        bendRadius: Math.max(0.55, rCoolerOutletRiser * 2.0),
        flowArrows: 1,
        reverseFlow: false,
        equipKey: "air_coolers",
        lineKey: "cooler_bay_outlet_risers",
        parentLineKey: "cooler_bay_risers",
        unitLabel: `E-101-B${b + 1}-OUT`,
        segmentTitle: `Gaz Soğutucu Bay #${b + 1} Çıkış Borusu (Riser)`,
        fromBoundary: `Bay #${b + 1} Çıkış Headerı (E-101-BAY${b + 1})`,
        toBoundary: "Gaz Soğutucu Soğuk Çıkış Manifoldu (L-114)",
        registerParticlePath: b === 0,
      }
    );

    // Header tie-in weld-neck flanges where each bay's riser meets its header
    [
      [bayInletX, bayInletHdrY, bayInletHeaderZ, rCoolerRiser, rBayInletHeader],
      [bayOutletX, bayOutletHdrY, bayOutletHeaderZ, rCoolerOutletRiser, rBayOutletHeader],
    ].forEach(([tx, ty, tz, rPipe, rHdr]) => {
      const tieFlange = new THREE.Mesh(
        new THREE.CylinderGeometry(rPipe * 1.32, rPipe * 1.32, 0.18, 16),
        matFlangeSteel
      );
      tieFlange.rotation.x = Math.PI / 2;
      tieFlange.position.set(tx, ty, tz + rHdr * 0.92);
      coolerGroup.add(tieFlange);
    });

    createValveStation(
      bayInletX,
      1.6,
      coolerValveZ,
      Math.max(0.28, rCoolerRiser * 0.95),
      { hasPlatform: false, hasActuator: false, rotationY: Math.PI / 2, equipKey: "air_coolers" }
    );
    createValveStation(
      bayOutletX,
      coolerOutletCrossY,
      coolerValveZ,
      Math.max(0.28, rCoolerOutletRiser * 0.95),
      { hasPlatform: false, hasActuator: false, rotationY: Math.PI / 2, equipKey: "air_coolers" }
    );
  }

  // Hot Gas Inlet Header & Cooled Gas Outlet Header in front of Gas Cooler (Z = coolerInletHeaderZ / coolerOutletHeaderZ).
  // Station Discharge Header (rDischHeader) feeds the Gas Cooler hot manifold tie-in with extra X/Z spacing.
  const coolerHotFeedX = coolerX0 - 7.0;
  const gasCoolerFeedTurnX = headerEastX <= coolerHotFeedX - 3.0
    ? coolerHotFeedX
    : Math.max(headerEastX + 6.0, coolerEndX + 6.0);
  const gasCoolerFeedPoints = [
    new THREE.Vector3(headerEastX, 1.5, frontDischargeZ),
    new THREE.Vector3(gasCoolerFeedTurnX, 1.5, frontDischargeZ),
    new THREE.Vector3(gasCoolerFeedTurnX, 1.6, coolerInletHeaderZ),
  ];
  if (gasCoolerFeedTurnX > coolerEndX) {
    gasCoolerFeedPoints.push(new THREE.Vector3(coolerEndX, 1.6, coolerInletHeaderZ));
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
      new THREE.Vector3(coolerHotFeedX, 1.6, coolerInletHeaderZ),
      new THREE.Vector3(coolerEndX, 1.6, coolerInletHeaderZ),
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
      new THREE.Vector3(coolerReturnStartX, 1.6, coolerOutletHeaderZ),
      new THREE.Vector3(coolerEndX, 1.6, coolerOutletHeaderZ),
    ],
    rCoolerOutlet,
    matYellowPipe,
    {
      flowArrows: 4,
      equipKey: "air_coolers",
      lineKey: "cooler_outlet",
      segmentTitle: "Gaz Soğutucu Soğuk Çıkış Ekipman Manifoldu (L-114)",
      fromBoundary: "Gaz Soğutucu Bay Çıkış Riser Branşmanları",
      toBoundary: "Station Discharge Header Soğutulmuş Gaz Dönüş Tie-In Noktası",
      registerParticlePath: true,
      reverseFlow: true,
    }
  );

  // Gas Cooler By-Pass Line with TCV Control Valve (Note 17).
  const bypassTieX = coolerX0 + 0.8;
  createCadPipeRoute(
    [
      new THREE.Vector3(coolerHotFeedX, 1.6, coolerInletHeaderZ),
      new THREE.Vector3(coolerHotFeedX, coolerBypassY, coolerInletHeaderZ),
      new THREE.Vector3(coolerHotFeedX, coolerBypassY, coolerOutletHeaderZ),
      new THREE.Vector3(bypassTieX, coolerBypassY, coolerOutletHeaderZ),
      new THREE.Vector3(bypassTieX, 1.6, coolerOutletHeaderZ),
    ],
    rCoolerBypass,
    matYellowPipe,
    {
      flowArrows: 2,
      equipKey: "cooler_bypass",
      lineKey: "cooler_bypass",
      segmentTitle: "Gaz Soğutucu TCV By-Pass Hattı (L-113 • Note 17)",
      fromBoundary: "Gaz Soğutucu Sıcak Giriş Manifoldu (TCV-101 Girişi)",
      toBoundary: "Gaz Soğutucu Soğuk Çıkış Manifoldu / Station Discharge Header Dönüşü",
      registerParticlePath: true,
    }
  );
  createValveStation((coolerHotFeedX + bypassTieX) / 2, coolerBypassY, coolerOutletHeaderZ, Math.max(0.25, rCoolerBypass), { hasPlatform: false, hasActuator: true, equipKey: "cooler_bypass", valveColorMat: matCyanArrow });

  // ── 7.3B UTILITY GAS SKID (Cooler Inlet Takeoff · 1485 Sm3/h · Odorizer · Electric Heater · 2x100% PRV) & METHANOL DEHYDRATOR ──
  const utilityGasSkid = new THREE.Group();
  const utilX = coolerHotFeedX - 12.5;
  const utilZ = coolerInletHeaderZ + 4.5;
  const utilPad = new THREE.Mesh(new THREE.BoxGeometry(11.5, 0.34, 6.8), matConcretePlinth);
  utilPad.position.set(utilX, 0.17, utilZ);
  utilPad.receiveShadow = true;
  utilityGasSkid.add(utilPad);

  // Double-pipe preheater + external MCC-fed electric heater + 2x100% parallel PRV runs + odorizer tank
  [-1.1, 1.1].forEach((uzOff) => {
    const dpHeater = new THREE.Mesh(new THREE.CylinderGeometry(0.26, 0.26, 3.6, 12), matHeatTraceOrange);
    dpHeater.rotation.z = Math.PI / 2;
    dpHeater.position.set(utilX - 1.8, 1.5, utilZ + uzOff);
    utilityGasSkid.add(dpHeater);

    const prvPipe = new THREE.Mesh(new THREE.CylinderGeometry(0.12, 0.12, 3.0, 10), matTealUtilityPipe);
    prvPipe.rotation.z = Math.PI / 2;
    prvPipe.position.set(utilX + 2.2, 1.45, utilZ + uzOff);
    utilityGasSkid.add(prvPipe);
  });
  const odorizerTank = new THREE.Mesh(new THREE.CylinderGeometry(0.45, 0.45, 2.2, 14), matHeatTraceOrange);
  odorizerTank.position.set(utilX + 4.3, 1.45, utilZ - 1.4);
  utilityGasSkid.add(odorizerTank);
  const methanolPot = new THREE.Mesh(new THREE.CylinderGeometry(0.38, 0.38, 2.4, 14), matCyanArrow);
  methanolPot.position.set(utilX - 4.4, 1.55, utilZ + 1.5);
  utilityGasSkid.add(methanolPot);

  createCadPipeRoute(
    [
      new THREE.Vector3(coolerHotFeedX, 1.6, coolerInletHeaderZ),
      new THREE.Vector3(utilX + 4.0, 1.6, coolerInletHeaderZ),
      new THREE.Vector3(utilX + 4.0, 1.5, utilZ),
    ],
    0.14,
    matTealUtilityPipe,
    {
      flowArrows: 1,
      equipKey: "station_utilities",
      segmentTitle: "Kullanım Gazı Çekiş Hattı (Gas Cooler Girişi · Özel §4.8.6)",
      fromBoundary: "Gas Cooler Giriş Manifoldu (L-111)",
      toBoundary: "Kullanım Gazı & Kokulandırma Skidi (Min. 1485 Sm³/h)",
    }
  );
  registerClickable(utilityGasSkid, "station_utilities");
  scene.add(utilityGasSkid);
  createCadGreenLabel("UTILITY GAS & MeOH SKID", utilX, 3.6, utilZ, 12.0, 2.2, -Math.PI / 2, 0, 0);

  createCadPipeCallout(
    `L-111..114 • COOLER EKİPMAN MANİFOLDU & TCV`,
    `Discharge Header ➔ E-101 Riserlar (${pLines.cooler_inlet?.nominal_size_in || '-'} / ${pLines.cooler_bay_risers?.nominal_size_in || '-'})`,
    coolerX0 + coolerWidth * 0.5,
    5.8,
    coolerInletHeaderZ,
    { width: 25, height: 4.5, pipeY: 1.6 + rCoolerInlet, accentColor: "#34d399", lineKey: "cooler_inlet", equipKey: "air_coolers" }
  );

  // Translucent Grey Maintenance Box on East Side of Gas Cooler
  const coolerEnv = new THREE.Mesh(new THREE.BoxGeometry(10, 9.5, 18), matEnvelopeBox);
  coolerEnv.position.set(coolerEndX + 5, 4.75, coolerCenterZ);
  scene.add(coolerEnv);
  envelopeMeshes.push(coolerEnv);

  registerClickable(coolerGroup, "air_coolers");
  scene.add(coolerGroup);
  createCadGreenLabel("GAS COOLER", coolerX0 + coolerWidth / 2, coolerDeckY + 2.65, coolerCenterZ - 7, Math.max(18, coolerWidth * 0.7), 3.8, -Math.PI / 2, 0, 0);
  if (coolerGeometry && coolerGeometry.tubes_per_row) {
    createCadGreenLabel(
      `${coolerTubeRows}x${coolerTubesPerRow} TUBES`,
      coolerX0 + coolerWidth / 2,
      coolerDeckY + 0.6,
      coolerCenterZ + 8,
      Math.max(14, coolerWidth * 0.55),
      2.4,
      -Math.PI / 2,
      0,
      0
    );
  }

  // ── 7.4 TEMPORARY WASTE STORAGE AREA (North-East Angled Brown Buildings) ──
  const wasteX = Math.max(125, coolerEndX + 42);
  const wasteZ = -94;
  const wasteGroup = new THREE.Group();
  wasteGroup.position.set(wasteX, 0, wasteZ);
  wasteGroup.rotation.y = -0.62; // Angled parallel to NE perimeter fence

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
    wasteX,
    7.2,
    wasteZ,
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

  // 1) Turbo-Compressor Suction Connection Header — Terminal Section of Station Suction Header
  createCadPipeRoute(
    [new THREE.Vector3(headerEastX, 1.5, frontSuctionZ), new THREE.Vector3(headerWestX, 1.5, frontSuctionZ)],
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

  // 2) Anti-Surge / Recycle Header, between suction and discharge.
  createCadPipeRoute(
    [new THREE.Vector3(headerEastX, 1.5, frontRecycleZ), new THREE.Vector3(headerWestX, 1.5, frontRecycleZ)],
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
      new THREE.Vector3(headerWestX, 1.5, frontRecycleZ),
      new THREE.Vector3(headerWestX - 4.0, 1.5, frontRecycleZ),
      new THREE.Vector3(headerWestX - 4.0, 1.5, frontSuctionZ),
      new THREE.Vector3(headerWestX, 1.5, frontSuctionZ),
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

  // 3) Turbo-Compressor Unit Discharge Header — Hot Collector Feeding Station Discharge Header
  createCadPipeRoute(
    [new THREE.Vector3(headerWestX, 1.5, frontDischargeZ), new THREE.Vector3(headerEastX, 1.5, frontDischargeZ)],
    rUnitDischHeader,
    matYellowPipe,
    {
      flowArrows: 6,
      equipKey: "turbo_compressors",
      lineKey: "unit_discharge_header",
      segmentTitle: "Unit Discharge Header (TC Ünite Sıcak Çıkış Kollektörü • L-109A)",
      fromBoundary: "Turbo-Kompresör Ünite Çıkış Branşmanlarının Bağlandığı Sıcak Kollektör",
      toBoundary: "Gaz Soğutucu Giriş Tie-In ve Station Discharge Header Bağlantısı",
      registerParticlePath: true,
    }
  );

  // 3D Callout Plaques for Front Manifold Corridor (Unit Suction Header & Unit Discharge Header)
  createCadPipeCallout(
    `L-105 • UNIT SUCTION HEADER (TC EMİŞ KOLLEKTÖRÜ)`,
    `Station Suction Header Sonu ➔ Ünite Emiş Branşmanları (${compSuctHeaderLine.nominal_size_in || suctLine.nominal_size_in || '48"'})`,
    Math.min(headerEastX - 18, Math.max(headerWestX + 18, (headerWestX + headerEastX) / 2 + 12)),
    6.5,
    frontSuctionZ,
    { width: 27, height: 4.7, pipeY: 1.5 + rSuctHeader, accentColor: "#38bdf8", lineKey: "comp_suction_header", equipKey: "turbo_compressors" }
  );
  createCadPipeCallout(
    `L-109A • UNIT DISCHARGE HEADER (TC BASMA KOLLEKTÖRÜ)`,
    `TC Ünite Sıcak Çıkışları (L-107) ➔ Soğutucu Girişi (${unitDischHeaderLine.nominal_size_in || dischLine.nominal_size_in || '48"'})`,
    Math.max(headerWestX + 18, Math.min(headerEastX - 18, (headerWestX + headerEastX) / 2 - 12)),
    6.5,
    frontDischargeZ,
    { width: 27, height: 4.7, pipeY: 1.5 + rUnitDischHeader, accentColor: "#f59e0b", lineKey: "unit_discharge_header", equipKey: "turbo_compressors" }
  );

  // Concrete Sleeper Pipe Supports along the widened 3-Header Corridor
  for (let sx = headerWestX + 6; sx <= headerEastX - 4; sx += 10) {
    const sleeper = new THREE.Mesh(new THREE.BoxGeometry(0.6, 0.9, 12.2), matConcretePlinth);
    sleeper.position.set(sx, 0.45, frontRecycleZ);
    scene.add(sleeper);
  }

  // East Header Termination Olive-Green Valve Pit Box (Gas Cooler Side)
  const eastValvePit = new THREE.Group();
  eastValvePit.position.set(headerEastX + 4, 0, frontRecycleZ);
  const pitWalls = new THREE.Mesh(new THREE.BoxGeometry(6.5, 3.2, 13.5), matOliveSteel);
  pitWalls.position.y = 1.6;
  eastValvePit.add(pitWalls);
  [frontSuctionZ - frontRecycleZ, 0, frontDischargeZ - frontRecycleZ].forEach((dz) => {
    const vCyl = new THREE.Mesh(new THREE.CylinderGeometry(0.85, 0.85, 2.2, 16), matYellowPipe);
    vCyl.rotation.z = Math.PI / 2;
    vCyl.position.set(0, 1.6, dz);
    eastValvePit.add(vCyl);
  });
  registerClickable(eastValvePit, "turbo_compressors");
  scene.add(eastValvePit);

  // Translucent Future Header Extension Envelope (Westward toward PIG Station as units are added)
  const westExtEnv = new THREE.Mesh(new THREE.BoxGeometry(28, 3.5, 13.0), matEnvelopeBox);
  westExtEnv.position.set(headerWestX - 20, 1.75, frontRecycleZ);
  scene.add(westExtEnv);
  envelopeMeshes.push(westExtEnv);

  // ══════════════════ 9. DYNAMIC N+1 INDIVIDUAL COMPRESSOR BUILDINGS (COMPRESSOR-01 .. N) ══════════════════

  const bldgW = 24;
  const bldgL = 32;
  const bldgWallH = 11.0;
  const bldgRidgeH = 13.6;
  const bldgCenterZ = 17;

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
    const cx = compStartX - i * compPitch;
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

    // Internal Dry Gas Seal (DGS) Heated Panel + Duplex 1 µm Cartridge Filters + Separation Seal Vent
    const dgsPanel = new THREE.Group();
    const dgsCabinet = new THREE.Mesh(new THREE.BoxGeometry(1.5, 2.6, 2.2), matCyanArrow);
    dgsCabinet.position.set(-5.6, 2.5, -7.2);
    dgsCabinet.castShadow = true;
    dgsPanel.add(dgsCabinet);
    [-0.55, 0.55].forEach((fDz) => {
      const dgsCartridge = new THREE.Mesh(new THREE.CylinderGeometry(0.18, 0.18, 1.35, 12), matHeatTraceOrange);
      dgsCartridge.position.set(-4.65, 2.8, -7.2 + fDz);
      dgsPanel.add(dgsCartridge);
    });
    const dgsVentTee = new THREE.Mesh(new THREE.CylinderGeometry(0.08, 0.08, 2.2, 8), matSilverVessel);
    dgsVentTee.position.set(-5.6, 4.8, -7.2);
    dgsPanel.add(dgsVentTee);
    internalGroup.add(dgsPanel);

    // b) External Turbine Combustion Air Intake Self-Cleaning Filter House (<= 8 mbar clean dP)
    const filterSkid = new THREE.Mesh(new THREE.BoxGeometry(5.5, 5.2, 6.2), matPurlinBrown);
    filterSkid.position.set(-bldgW / 2 - 4.8, 3.2, 9.8);
    filterSkid.castShadow = true;
    unitRoot.add(filterSkid);

    // c) External Aerial Lube Oil Cooler (Spec 4500 §6.7: 2 electric fans + 3-way thermostatic bypass + Al-clad SS piping)
    const lubeCooler = new THREE.Group();
    const lcDeck = new THREE.Mesh(new THREE.BoxGeometry(5.4, 1.8, 6.0), matSilverVessel);
    lcDeck.position.set(-bldgW / 2 - 4.8, 2.9, 17.5);
    lcDeck.castShadow = true;
    lubeCooler.add(lcDeck);
    [-1.4, 1.4].forEach((fanDz) => {
      const shroud = new THREE.Mesh(new THREE.CylinderGeometry(1.05, 1.15, 0.55, 16), matYellowPipe);
      shroud.position.set(-bldgW / 2 - 4.8, 4.05, 17.5 + fanDz);
      lubeCooler.add(shroud);
    });
    const lc3WayValve = new THREE.Mesh(new THREE.SphereGeometry(0.28, 10, 10), matValveBody);
    lc3WayValve.position.set(-bldgW / 2 - 2.2, 2.2, 16.0);
    lubeCooler.add(lc3WayValve);
    unitRoot.add(lubeCooler);

    // d) Standalone Local Unit Electrical / Control Shelter (Brown pitched-roof cabin next to each unit)
    const localElecRoom = new THREE.Mesh(new THREE.BoxGeometry(6.2, 4.8, 6.8), matBuildingWall);
    localElecRoom.position.set(-bldgW / 2 - 11.5, 2.4, 11.5);
    localElecRoom.castShadow = true;
    unitRoot.add(localElecRoom);

    // e) Dark-Brown Cable Trench Bridge from South 7.0 M. WIDE ROAD into South Wall of Building
    const cableBridge = new THREE.Mesh(new THREE.BoxGeometry(2.6, 0.65, 16), matCableTrench);
    cableBridge.position.set(-bldgW / 2 + 3.5, 0.35, bldgL / 2 + 8);
    unitRoot.add(cableBridge);

    // 6) Front Branch Piping (Dual Series Isolation Valves + Temporary Start-Up Strainer + ASV + Non-Slam Check)
    const suctBranchX = cx + 3.2;
    const dischBranchX = cx + 7.2;

    // Suction Branch from TC Suction Connection Header (frontSuctionZ) into Building North Wall (Z = 1.0).
    createCadPipeRoute(
      [
        new THREE.Vector3(suctBranchX, 1.5, frontSuctionZ),
        new THREE.Vector3(suctBranchX, suctBranchCrossY, frontSuctionZ + 1.5),
        new THREE.Vector3(suctBranchX, suctBranchCrossY, -6.5),
        new THREE.Vector3(suctBranchX, 2.6, -6.5),
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
        fromBoundary: "TC Üniteleri Suction Bağlantı Headerı",
        toBoundary: `${unitLabel} Santrifüj Kompresör Emiş Nozulu`,
        registerParticlePath: true,
      }
    );
    // Dual Series Split-Body Full-Bore Ball Valves per Spec 4500 §5.5 (MOV <=30s + Series Manual Isolation)
    createValveStation(suctBranchX, 2.6, -4.4, rCompSuctionBranch, { hasPlatform: true, hasActuator: true, rotationY: Math.PI / 2, equipKey: "turbo_compressors" });
    createValveStation(suctBranchX, 2.6, -2.0, rCompSuctionBranch, { hasPlatform: false, hasActuator: false, rotationY: Math.PI / 2, equipKey: "turbo_compressors" });

    // Internal suction continuation: north-wall entry -> Temporary Start-Up Conical Strainer -> compressor barrel north nozzle.
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
    // Temporary Start-Up Conical Strainer & Spacer Spool directly upstream of compressor suction nozzle
    const tempStrainer = new THREE.Mesh(
      new THREE.CylinderGeometry(rCompSuctionBranch * 1.45, rCompSuctionBranch * 1.15, 0.9, 16),
      matHeatTraceOrange
    );
    tempStrainer.rotation.x = Math.PI / 2;
    tempStrainer.position.set(-2.2, 3.4, -11.4);
    internalGroup.add(tempStrainer);

    // Discharge Branch from Building North Wall out to Station Discharge Header (frontDischargeZ)
    createCadPipeRoute(
      [
        new THREE.Vector3(dischBranchX, 1.8, 1.0),
        new THREE.Vector3(dischBranchX, 1.5, frontDischargeZ),
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
        toBoundary: "Station Discharge Header Bağlantı Branşmanı",
        registerParticlePath: true,
      }
    );
    // Dual Series Unit Discharge Ball Valves + Non-Slam Nozzle Check Valve (Spec 4500 §5.5 & §5.7)
    createValveStation(dischBranchX, 1.8, -4.6, rCompDischargeBranch, { hasPlatform: true, hasActuator: true, rotationY: Math.PI / 2, equipKey: "turbo_compressors" });
    createValveStation(dischBranchX, 1.8, -2.2, rCompDischargeBranch, { hasPlatform: false, hasActuator: false, rotationY: Math.PI / 2, equipKey: "turbo_compressors" });

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

    // Hot Gas Anti-Surge Recycle Loop (ASV): discharge branch → ASV header (w/ downstream check & shutoff per Ozel §4.8).
    createCadPipeRoute(
      [
        new THREE.Vector3(dischBranchX, 1.8, -1.5),
        new THREE.Vector3(dischBranchX, antiSurgeCrossY, -1.5),
        new THREE.Vector3(cx + 0.5, antiSurgeCrossY, -1.5),
        new THREE.Vector3(cx + 0.5, antiSurgeCrossY, frontRecycleZ),
        new THREE.Vector3(cx + 0.5, 1.5, frontRecycleZ),
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
    createValveStation(cx + 0.5, antiSurgeCrossY, -6.0, rAntiSurge, { hasPlatform: true, rotationY: Math.PI / 2, equipKey: "anti_surge" });
    // Downstream ASV check + shutoff isolation valve prior to recycle header tie-in
    createValveStation(cx + 0.5, antiSurgeCrossY, -8.8, rAntiSurge, { hasPlatform: false, hasActuator: false, rotationY: Math.PI / 2, equipKey: "anti_surge" });

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

  // 3) FIRE WATER BUILDING & 300 m3 TANK (X = +64, Z = +88, Spec 4500 §14 / NFPA 20)
  buildAuxiliaryBuilding(64, 88, 20, 6.8, 26, "FIRE WATER BUILDING & TANK", "fire_water", Math.PI / 2);
  const fireWaterTank = new THREE.Mesh(new THREE.CylinderGeometry(4.6, 4.6, 5.2, 24), matRedFire);
  fireWaterTank.position.set(49.5, 2.6, 88.0);
  fireWaterTank.castShadow = true;
  registerClickable(fireWaterTank, "fire_water");
  scene.add(fireWaterTank);

  // 4) AIR COMPRESSOR BUILDING (X = +92, Z = +88) + Exterior ASME/CE >= 25 m3 Air Receiver & Dual-Tower Heatless Dryers (Spec 4320/4330/Özel §4.8.7)
  buildAuxiliaryBuilding(92, 88, 15, 6.5, 22, "AIR COMPRESSOR BUILDING", "air_compressor_building", Math.PI / 2);
  const airReceiverTank = new THREE.Group();
  const recMesh = new THREE.Mesh(new THREE.CylinderGeometry(1.45, 1.45, 6.2, 18), matSilverVessel);
  recMesh.position.set(103.5, 3.5, 84.0);
  recMesh.castShadow = true;
  airReceiverTank.add(recMesh);
  [-1.8, 1.8].forEach((dOff) => {
    const tower = new THREE.Mesh(new THREE.CylinderGeometry(0.55, 0.55, 3.8, 14), matTealUtilityPipe);
    tower.position.set(103.5, 2.1, 90.0 + dOff);
    airReceiverTank.add(tower);
  });
  registerClickable(airReceiverTank, "station_utilities");
  scene.add(airReceiverTank);
  createCadGreenLabel("AIR RECEIVER >=25 m3", 103.5, 7.2, 84.0, 11.5, 2.0, -Math.PI / 2, 0, Math.PI / 2);

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

  const cutawayCompX = compStartX - (cutawayUnitIdx - 1) * compPitch;
  const manifoldCenterX = (headerWestX + headerEastX) / 2;
  const filtrationCenterX = (mfsInletX + cfsOutletTieX) / 2;
  const coolerCenterX = coolerX0 + coolerWidth / 2;
  const cameraPresets = {
    iso: { pos: new THREE.Vector3(-155, 102, -168), look: new THREE.Vector3(-10, 6, 0) },
    top: { pos: new THREE.Vector3(-5, 275, 6), look: new THREE.Vector3(-5, 0, 5) },
    compCutaway: { pos: new THREE.Vector3(cutawayCompX + 24, 22, -26), look: new THREE.Vector3(cutawayCompX, 6, 12) },
    comp4: { pos: new THREE.Vector3(cutawayCompX + 24, 22, -26), look: new THREE.Vector3(cutawayCompX, 6, 12) },
    manifold: { pos: new THREE.Vector3(manifoldCenterX + 28, 22, -40), look: new THREE.Vector3(manifoldCenterX, 2.5, frontRecycleZ) },
    filtration: { pos: new THREE.Vector3(cfsCenterX - 18, 24, -126), look: new THREE.Vector3(filtrationCenterX, 4.5, cfsVesselZ) },
    cooler: { pos: new THREE.Vector3(coolerCenterX + 4, 32, -32), look: new THREE.Vector3(coolerCenterX, 8, coolerCenterZ) },
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
  function syncPipeLabelsButton() {
    const lblBtn = container.querySelector("#btn-toggle-pipe-labels");
    if (!lblBtn) return;
    lblBtn.textContent = `🏷️ ${t(showPipeLabels ? "pipe_labels_on" : "pipe_labels_off", uiLang)}`;
    lblBtn.style.background = showPipeLabels ? "#7c3aed" : "#1e293b";
    lblBtn.style.color = showPipeLabels ? "#fff" : "#cbd5e1";
    lblBtn.style.borderColor = showPipeLabels ? "#c084fc" : "rgba(255,255,255,0.15)";
  }
  container.querySelector("#btn-toggle-pipe-labels")?.addEventListener("click", () => {
    showPipeLabels = !showPipeLabels;
    pipeLabelMeshes.forEach((m) => (m.visible = showPipeLabels));
    syncPipeLabelsButton();
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
    syncPipeLabelsButton();
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
    cyclones: { pos: new THREE.Vector3(mfsX - 2, 22, -34), look: new THREE.Vector3(mfsX - 2, 5.5, -68) },
    cartridge_filters: { pos: new THREE.Vector3(cfsCenterX, 18, -40), look: new THREE.Vector3(cfsCenterX, 3.2, -68) },
    turbo_compressors: { pos: new THREE.Vector3(cutawayCompX + 20, 22, -24), look: new THREE.Vector3(cutawayCompX, 5, bldgCenterZ - 4) },
    compressor_building: { pos: new THREE.Vector3(cutawayCompX + 26, 30, -28), look: new THREE.Vector3(cutawayCompX, 8, bldgCenterZ) },
    air_coolers: { pos: new THREE.Vector3(coolerCenterX, 28, -32), look: new THREE.Vector3(coolerCenterX, 9, -76) },
    station_recycle: { pos: new THREE.Vector3(stationRecycleValveX + 14, 13, stationRecycleZ - 16), look: new THREE.Vector3(stationRecycleValveX, stationRecycleY + 0.6, stationRecycleZ) },
    cooler_bypass: { pos: new THREE.Vector3(-1, coolerBypassY + 10, -28), look: new THREE.Vector3(-1, coolerBypassY * 0.75, -50) },
    condensate_system: { pos: new THREE.Vector3(-86, 12, -32), look: new THREE.Vector3(-73, 1.8, -50) },
    safety_relief: { pos: new THREE.Vector3(-24, coolerReturnY + 15, -26), look: new THREE.Vector3(-24, coolerReturnY + 4, -48) },
    esd_valves: { pos: new THREE.Vector3(-46, coolerReturnY + 15, -26), look: new THREE.Vector3(-46, coolerReturnY + 4, -48) },
    ultrasonic_meter: { pos: new THREE.Vector3(usmX, coolerReturnY + 12, -30), look: new THREE.Vector3(usmX, coolerReturnY + 1, usmZ) },
    pig_receiver: { pos: new THREE.Vector3(-214, 22, -86), look: new THREE.Vector3(-196, 2, -86) },
    pig_launcher: { pos: new THREE.Vector3(-214, 22, -58), look: new THREE.Vector3(-196, 2, -58) },
    station_suction_valve: { pos: new THREE.Vector3(-186.5, 11, -96), look: new THREE.Vector3(-186.5, 2.2, -82) },
    station_discharge_valve: { pos: new THREE.Vector3(-186.5, 11, -48), look: new THREE.Vector3(-186.5, 2.2, -62) },
    mainline_block_valve: { pos: new THREE.Vector3(-204, 12, -72), look: new THREE.Vector3(-190, 2.2, -72) },
    station_loading_line: { pos: new THREE.Vector3(-186.5, 8.5, -69), look: new THREE.Vector3(-186.5, 2.2, -79.2) },
    station_bypass_valve: { pos: new THREE.Vector3(-138, 12, -72), look: new THREE.Vector3(-152, 2.2, -72) },
    tiein: { pos: new THREE.Vector3(-232, 22, -74), look: new THREE.Vector3(-196, 1.2, -72) },
    anti_surge: { pos: new THREE.Vector3(cutawayCompX + 14, 16, -28), look: new THREE.Vector3(cutawayCompX + 0.5, antiSurgeCrossY * 0.7, -8) },
    control_building: { pos: new THREE.Vector3(-62, 24, 46), look: new THREE.Vector3(-62, 5, 86) },
    generator_building: { pos: new THREE.Vector3(6, 22, 60), look: new THREE.Vector3(6, 5, 92) },
    air_compressor_building: { pos: new THREE.Vector3(92, 20, 60), look: new THREE.Vector3(92, 5, 88) },
    guard_shelter: { pos: new THREE.Vector3(110, 14, 20), look: new THREE.Vector3(110, 3, 41) },
    admin_building: { pos: new THREE.Vector3(146, 26, 56), look: new THREE.Vector3(146, 6, 92) },
  };

  function resolveEquipmentCameraTarget(key, targetObject = null) {
    if (EQUIP_CAMERA_TARGETS[key]) return EQUIP_CAMERA_TARGETS[key];
    if (!targetObject) return null;
    const bbox = new THREE.Box3().setFromObject(targetObject);
    if (bbox.isEmpty()) return null;
    const center = new THREE.Vector3();
    const size = new THREE.Vector3();
    bbox.getCenter(center);
    bbox.getSize(size);
    const span = Math.max(16, Math.hypot(size.x, size.z) * 0.85);
    return {
      pos: new THREE.Vector3(center.x - span * 0.5, center.y + Math.max(12, span * 0.55), center.z - span * 0.75),
      look: center,
    };
  }

  function buildEquipmentTelemetryHtml(key) {
    let tag = "EKİPMAN";
    let sub = "Proses Ekipmanı";
    let rows = [];
    const statusBadge = `<span style="background: rgba(16,185,129,0.2); color: #34d399; border: 1px solid #10b981; padding: 1px 7px; border-radius: 8px; font-size: 9.5px; font-weight: 700;">🟢 DEVREDE (ONLINE)</span>`;

    if (key === "cyclones") {
      tag = `V-101 .. V-10${numCyclones}`;
      sub = `MFS Çoklu Siklon Seperatör Grubu (${eq.cyclones?.configuration || `${numCyclones} Ünite`})`;
      const cycBf = eq.cyclones?.blow_flask || {};
      const cycHt = eq.cyclones?.heat_tracing || {};
      rows = [
        ["Proses Basıncı:", `${sm.suction_pressure_bar || 45.0} bar(a)`],
        ["Temiz ΔP / Alarm:", `${eq.cyclones?.pressure_drop_bar || 0.25} bar (Temiz ≤ 400 mbar · Kirli 700 mbar)`],
        ["Ünite Payı / Debi:", `%${eq.cyclones?.unit_capacity_pct || 50} · ${eq.cyclones?.flow_per_unit_kgs || (sm.total_mass_flow_kgs / Math.max(1, numCyclones - 1)).toFixed(1)} kg/s (${eq.cyclones?.internal_cyclone_elements || "-"} tüp)`],
        ["Ayırma Verimi (5260):", `≥ 8 µm %100 · ≥ 4 µm %90 (Katı & Sıvı)`],
        ["Mekanik (ASME VIII):", `Ø${eq.cyclones?.vessel_diameter_mm || 1200} mm · Spherical Head · 1.6 mm CA · SS Cıvata`],
        ["Blow-Flask & Seviye:", `Yatay Ø${cycBf.diameter_mm || 600}×${cycBf.length_mm || 1800} mm + 2 Ayrı Seviye Şişesi (4500 §5.2)`],
        ["Heat Tracing & Drenaj:", `İzolasyon + ≥ 2 °C Elektrik Isıtma${cycHt.freeze_risk_active ? " ⚠️ DONMA RİSKİ" : ""} · Oto/Man Header ➔ TK-101`],
        ["Giriş / Çıkış Branşmanı:", `${eq.cyclones?.inlet_pipe_size || '16"'} / ${eq.cyclones?.outlet_pipe_size || eq.cyclones?.inlet_pipe_size || '16"'} NPS`],
      ];
    } else if (key === "cartridge_filters") {
      const flt = eq.cartridge_filters || {};
      const fltBf = flt.blow_flask || {};
      const fltHt = flt.heat_tracing || {};
      tag = `F-101 .. F-10${numFilters}`;
      sub = `CFS Kartuş Filtre Seperatör Grubu (${flt.configuration || `${numFilters} Ünite`})`;
      rows = [
        ["Giriş / Çıkış Basıncı:", `${(sm.suction_pressure_bar - (eq.cyclones?.pressure_drop_bar || 0.25)).toFixed(2)} → ${(sm.suction_pressure_bar - (eq.cyclones?.pressure_drop_bar || 0.25) - (flt.clean_dp_bar || 0.10)).toFixed(2)} bar(a)`],
        ["Temiz ΔP / Değişim / Patlama:", `${flt.clean_dp_bar || 0.10} bar (Temiz ≤ 140 mbar · Değişim 300 mbar · Patlama 3 bar)`],
        ["Filtrasyon Hassasiyeti:", `${flt.filter_efficiency_micron || "≥ 3 µm (%99.8 katı) · ≥ 10 µm (sıvı)"}`],
        ["Ünite Payı / Debi:", `%${flt.unit_capacity_pct || 50} · ${flt.flow_per_unit_kgs || (sm.total_mass_flow_kgs / Math.max(1, numFilters - 1)).toFixed(1)} kg/s (${flt.cartridge_elements_count || "-"} kartuş)`],
        ["Kapak & Mekanik (ASME VIII):", `${flt.closure_type || "QOC + Davit"} · Ø${flt.vessel_diameter_mm || 1350}×${flt.vessel_length_mm || 4700} mm · CE`],
        ["Blow-Flask & Heat Tracing:", `Yatay Ø${fltBf.diameter_mm || 600}×${fltBf.length_mm || 1800} mm · İzolasyon Braket + ≥ 2 °C${fltHt.freeze_risk_active ? " ⚠️ DONMA RİSKİ" : ""}`],
        ["Giriş / Çıkış Branşmanı:", `${flt.inlet_pipe_size || '24"'} / ${flt.outlet_pipe_size || flt.inlet_pipe_size || '24"'} NPS`],
        ["Yedek & Enstrümantasyon:", `${flt.spare_sets_required || "3 set yedek filtre + conta"} · PDT/PDI/PDSH`],
      ];
    } else if (key === "turbo_compressors") {
      tag = `C-101 .. C-10${numComps}`;
      sub = `API 617 Santrifüj Kompresör & Endüstriyel Gaz Türbini Trenleri`;
      const tc = eq.turbo_compressors || {};
      const fg = tc.fuel_gas_system || {};
      const dgs = tc.dry_gas_seal || {};
      const lo = tc.lube_oil_system || {};
      const uv = tc.unit_valves_and_strainer || {};
      const ai = tc.air_intake_and_enclosure || {};
      const pwrKw = Math.round(tc.power_per_unit_kw || (sm.total_power_mw * 1000 / numComps));
      const fuelKgh = Number(fg.fuel_per_unit_kgh || 0);
      const fuelSm3h = Number(fg.fuel_per_unit_sm3h || 0);
      rows = [
        ["Emiş / Basma Basıncı:", `${(sm.suction_pressure_bar - 0.25).toFixed(1)} → ${sm.discharge_pressure_bar || 75.0} bar(a)`],
        ["Basınç Oranı (PR):", `${((sm.discharge_pressure_bar || 75.0) / Math.max(1, (sm.suction_pressure_bar - 0.25))).toFixed(2)} : 1`],
        ["Emiş / Basma Sıcaklığı:", `${sm.suction_temp_c || 15.0} °C → ${eq.air_coolers?.inlet_temp_c || 68.0} °C`],
        ["Tren Güç / Gaz Debisi:", `${pwrKw.toLocaleString()} kW (${(pwrKw / 1000).toFixed(2)} MW) · ${tc.flow_per_unit_kgs || (sm.total_mass_flow_kgs / numComps).toFixed(1)} kg/s`],
        ["ISO 6976 Yakıt / Tren:", `${fuelKgh.toFixed(1)} kg/h (~${fuelSm3h.toFixed(0)} Sm³/h · LHV ${fg.lhv_kj_kg || "-"} kJ/kg)`],
        ["Ünite Vanası & Strainer:", `2×MOV (≤${uv.motor_actuator_stroke_max_s || 30}s) + Geçici Konik Strainer + Non-Slam Çek`],
        ["Dry Gas Seal (API 692):", `${dgs.filtration_rating_um || 1} µm Duplex + PDCV Regülatör + Carbon Seal`],
        ["Yağlama (Spec 4500 §6.7):", `${lo.flow_lpm_per_unit || "-"} L/dk · ≥5 dk (${lo.reservoir_min_working_volume_l || "-"} L) · 10 µm Duplex + 2-Fan Cooler`],
        ["Hava Emiş & Gürültü:", `Self-Cleaning (≤${ai.air_intake_clean_dp_max_mbar || 8} mbar temiz) · ≤ ISO NR 80 / 85 dBA`],
        ["ASV & Yedeklilik:", `ASV ${tc.anti_surge_valve_size_in || 12}" (< ${tc.anti_surge_stroke_time_s || 0.8}s + Çek/Blok) · ${tc.operating_count || (numComps - 1)}+1`],
      ];
      const asvSizing = tc.anti_surge_valve_sizing;
      if (asvSizing) {
        rows.push(["ASV IEC 60534 Boyut:", `${asvSizing.valve_inch} • Cv ${Number(asvSizing.required_cv || 0).toFixed(1)} • Açıklık %${Number(asvSizing.opening_percent || 0).toFixed(1)}`]);
      }
    } else if (key === "fuel_gas") {
      tag = `FG-101`;
      sub = `Yakıt Gazı Şartlandırma, Isıtma & Basınç Düşürme Skidi (Spec 4500 §8.0)`;
      const fg = eq.fuel_gas || eq.turbo_compressors?.fuel_gas_system || {};
      rows = [
        ["Çekiş Konumu:", fg.takeoff_location || "Ana CFS Filtre Çıkışı / Gaz Soğutucu Girişi Öncesi"],
        ["Seperatör & Blow-Flask:", `1 µm (%99.8) Yatay Sock Filtre + ≥ ${fg.separator_heat_tracing_min_c || 2} °C Blow-Flask`],
        ["Eşanjör & Regülatör:", `${fg.heat_exchanger_redundancy || "1+1 Eşanjör"} (${fg.heat_exchanger_outlet_c || "20 ± 5 °C"})`],
        ["Ünite / Toplam Yakıt (%120):", `${fg.fuel_per_unit_kgh || 0} kg/h (%120: ${fg.design_fuel_per_unit_kgh || 0}) · Toplam ${fg.total_fuel_kgh || 0} kg/h`],
        ["ISO 6976 LHV & Borulama:", `${fg.lhv_kj_kg || "-"} kJ/kg · ${fg.pipe_material || "316 SS"} · ${fg.spare_sets_required || "2 set yedek"}`],
      ];
    } else if (key === "compressor_building") {
      tag = `BLDG-01`;
      sub = `Kompresör Ünite Binası & Akustik Mahfaza`;
      rows = [
        ["Boyutlar (G x U x Y):", `${eq.compressor_building?.width_m || 24}m x ${eq.compressor_building?.length_m || 68}m x ${eq.compressor_building?.height_m || 14}m`],
        ["Taban Alanı:", `${eq.compressor_building?.area_m2 || 1632} m²`],
        ["Tavan Vinci:", `${eq.compressor_building?.crane_capacity_tons || 15} Ton Köprülü Gezer Vinç`],
        ["Akustik Ses Düzeyi:", `${eq.compressor_building?.acoustic_attenuation_dba || "≤ ISO NR 80 / 85 dBA @ 1m"}`],
        ["Yangın & Gaz Güvenliği:", `${eq.compressor_building?.fire_and_gas_system || "%10/%20 LEL IR Dedektörler + Otomatik CO₂"}`],
        ["HVAC & Havalandırma:", `≤ ${eq.compressor_building?.enclosure_max_temp_c || 80} °C · UPS DC/400VAC Yedekli Kabin Fanları`],
      ];
    } else if (key === "air_coolers") {
      tag = `E-101`;
      sub = `Fin-Fan Doğal Gaz Hava Soğutucu Bankı (${numCoolerBays} Bay • Spec 5234 / API 661)`;
      const ac = eq.air_coolers || {};
      const tb = ac.tube_bundle || {};
      rows = [
        ["Kompresör Çıkışı = Soğutucu Girişi:", `${ac.inlet_temp_c ?? 68.0} °C (${ac.compressor_outlet_coupled ? "✓ Doğrulandı" : "Aktif"})`],
        ["Hava / Maks. Çıkış Sınırı (4500):", `${ac.air_inlet_temp_c ?? 15.0} °C (Ref ≤40 °C) → ≤ ${ac.requested_max_outlet_temp_c ?? 45.0} °C (${ac.outlet_temp_c ?? 38.0} °C)`],
        ["Toplam Isıl Yük / LMTD:", `${ac.total_heat_duty_mw || 14.8} MWth • LMTD ${ac.lmtd_c ?? "-"} °C (Approach ${ac.approach_temp_c ?? 15.0} °C)`],
        ["Dinamik Tüp Demeti ΔP (5234):", `${ac.pressure_drop_bar || 0.35} bar (İzin ≤${tb.allowable_dp_bar ?? 0.50} bar · v=${tb.tube_velocity_ms ?? "-"} m/s · ${tb.tubes_per_bay ?? "-"} tüp/bay · 12 BWG)`],
        ["Fan & VFD Tahriki (5234 / §5.14):", `${ac.total_fans || (numCoolerBays * 2)} Adet Forced-Draft VFD · IEEE 519 (≥%95) · ≤${ac.max_fan_tip_speed_ms ?? 50} m/s · ≤${ac.fan_motor_max_kw ?? 29.8} kW`],
        ["Titreşim, Güneşlik & İzolasyon:", `Murphy Titreşim Stop · 2.0 mm Alüminyum Panjur Güneşlik · Kilitli Manuel Vana + 1" Vent/Drenaj`],
        ["Kolektör Boru Çapı:", `${ac.inlet_header_pipe_size || '48"'} / Riser: ${ac.riser_pipe_size || '30"'}`],
      ];
      if ((ac.design_warnings || []).length) {
        rows.push(["Termal / Şartname Uyarısı:", ac.design_warnings[0]]);
      }
      const coolerDesign = ac.detailed_design;
      if (coolerDesign) {
        rows.push(
          ["API 661 Gerekli Alan:", `${Number(coolerDesign.required_area_m2 || 0).toFixed(1)} m²`],
          ["API 661 Gerçek Alan:", `${Number(coolerDesign.actual_area_m2 || 0).toFixed(1)} m² (%${Number(coolerDesign.overdesign_pct || 0).toFixed(1)} overdesign)`],
          ["Fan Gücü / Uç Hızı:", `${Number(coolerDesign.fan_power_kw || 0).toFixed(1)} kW • ${Number(coolerDesign.fan_tip_speed_ms || 0).toFixed(1)} m/s`]
        );
      }
      const tcvSizing = ac.cooler_bypass_valve_sizing;
      if (tcvSizing) {
        rows.push(["TCV IEC 60534 Boyut:", `${tcvSizing.valve_inch} • Cv ${Number(tcvSizing.required_cv || 0).toFixed(1)}`]);
      }
    } else if (key === "station_recycle") {
      tag = `PCV-101 / RECYCLE`;
      sub = `${eq.station_recycle?.pipe_size || '6"'} İstasyon Recycle Kontrol Vanası (4-NGTL 0-CS-M-002-4500 §5.8)`;
      rows = [
        ["Boru Çapı & Malzeme:", `${eq.station_recycle?.pipe_size || '6"'} NPS (${suctLine.pipe_material || 'API 5L X70'})`],
        ["Hat Bağlantısı:", `Gaz Soğutucu Çıkışı Sonrası ➔ Filtrelenmiş Emiş (Kompresör Önü)`],
        ["Kontrol Vanası Tipi:", `Globe / Plug-in-Cage + Hat İçi NRV Çekvalf (4500 §5.8)`],
        ["Power-Gas Tüpü & İzolasyon:", `Ayrı Power-Gas Aktüatör Tüpü (316 SS) · 2x Blok Vana + Ses Kabini + Ayrı Note 13 Purge`],
        ["Stroking & Emniyet:", `20-30 s Ayarlanabilir Hareket • ESD/Sinyal Kaybında Fail-Closed`],
        ["Sirkülasyon Kapasitesi:", `${eq.station_recycle?.max_recirculation_capacity_kgs || 120} kg/s`],
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
        ["Gaz Bileşimi (Programdan):", `${compStr} • MW ${auto.mw || sm.gas_mw || 18.95} g/mol`],
        ["EOS / Z / k (Programdan):", `${String(auto.eos_model || sm.eos_model || "coolprop").toUpperCase()} • Z=${auto.z ?? psvSizing.z_used ?? 0.87} • k=${auto.k ?? psvSizing.k_used ?? 1.55}`],
        ["Tasarım Sekmesi P_atm & T_atm:", `${Number(psv.ambient_pressure_bar || 1.01325).toFixed(4)} bar(a) • ${psv.ambient_temp_c ?? 15.0} °C`],
        ["Vana Giriş P / T (Programdan):", `${auto.p_upstream_bar || sm.discharge_pressure_bar || 75} bar(a) • ${auto.t_relieving_c || eq.air_coolers?.inlet_temp_c || 50} °C`],
        ["Toplam Tahliye Debisi:", `${auto.mass_flow_total_kgs || sm.total_mass_flow_kgs || 441.8} kg/s`],
        ["Toplam / Vana Başına Alan:", `${Number(psvSizing.required_area_total_sqin || psvSizing.required_area_sqin || 0).toFixed(3)} in² / ${Number(psvSizing.required_area_sqin || 0).toFixed(3)} in²`],
        ["Hesaplanan Eşdeğer Çap:", `Ø${Number(psvSizing.required_diameter_in || 0).toFixed(2)}" (Orifis Ø${Number(psvSizing.selected_orifice_diameter_in || 0).toFixed(2)}")`],
        ["Seçilen API 526 Orifis / Flanş:", `${psvSizing.selected_orifice || "-"} (${psvSizing.inlet_flange_in || '8"'} × ${psvSizing.outlet_flange_in || '10"'})`],
        ["Atmosferik Vent Çıkış Hızı:", `${Number(psvSizing.vent_exit_velocity_ms || 0).toFixed(1)} m/s (ρ_atm=${Number(psvSizing.atm_gas_density_kgm3 || 0).toFixed(3)} kg/m³)`],
        ["Önerilen Min. PSV Sayısı:", `${psvSizing.recommended_duty_count || 1} Duty + 1 Standby (Toplam ${psvSizing.recommended_total_count || 2})`],
        ["Yerleşim & Özel Şartname:", `Binalara ≥35 m · Choke Flow · Dual-Outlet Flanş · 2" Pilot + Snubber + Field Test (4500 §5.10 / Özel p.32)`],
      ];
    } else if (key === "esd_valves") {
      const esd = eq.esd_sizing || {};
      const utilBdv = eq.station_utilities?.safety_and_bypass?.bdv_4500 || {};
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
      tag = `ESD / BDV-101..10${esd.esd_count || 2} (IEC 60534 & API 521)`;
      sub = `Discharge Header Dikey Riser & Hat Acil Boşaltma / Kapatma Vanaları`;
      rows = [
        ["Gaz Bileşimi (Programdan):", `${compStr} • MW ${auto.mw || sm.gas_mw || 18.95} g/mol`],
        ["Tasarım Sekmesi P_atm & T_atm:", `${Number(esd.ambient_pressure_bar || 1.01325).toFixed(4)} bar(a) • ${esd.ambient_temp_c ?? 15.0} °C`],
        ["YB Hacmi (@ Kompresör P_out):", `${esd.esd_hp_volume_m3 ?? 50.0} m³ @ ${disch.upstream_pressure_bar ?? auto.discharge_p_in_bar ?? 75.0} bar(a) → ${disch.blowdown_mass_flow_total_kgs ?? disch.flow_per_valve_kgs ?? 0} kg/s`],
        ["DB Hacmi (@ Kompresör P_in):", `${esd.esd_lp_volume_m3 ?? 40.0} m³ @ ${suct.upstream_pressure_bar ?? auto.suction_p_in_bar ?? 45.0} bar(a) → ${suct.blowdown_mass_flow_total_kgs ?? suct.flow_per_valve_kgs ?? 0} kg/s`],
        ["Gerekli Cv (YB / DB):", `YB Cv ${Number(disch.required_cv || 0).toFixed(1)} (Toplam ${Number(disch.required_cv_total || 0).toFixed(1)}) • DB Cv ${Number(suct.required_cv || 0).toFixed(1)}`],
        ["Hesaplanan Boşaltma Çapı:", `YB: ${disch.calculated_size_in || disch.selected_size_in || '-'}" (DN${disch.calculated_dn_mm || '-'}) • DB: ${suct.calculated_size_in || suct.selected_size_in || '-'}" (DN${suct.calculated_dn_mm || '-'})`],
        ["Tam Geçişli Hat ESD Çapı:", `Basma: ${disch.selected_size_in || '-'}" • Emiş: ${suct.selected_size_in || '-'}"`],
        ["Önerilen Paralel BDV Sayısı:", `${disch.recommended_duty_count || 1} Aktif (Kurulu: ${esd.esd_count || 2} Adet)`],
        ["Spec 4500 §5.11 ESD Şartı:", `Binalara ≥35 m · 1 barg ≤60 s (${utilBdv.esd_60s_compliant ? "✓ UYGUN" : `Mevcut ${esd.depressurization_time_min ?? 15} dk`}) · Yağlamalı Plug · Gas-over-Oil Fail-Open`],
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
      const cond = eq.condensate_system || {};
      tag = `TK-101 (DIN 6608)`;
      sub = `Kondensat Sıvı Toplama ve Depolama Sistemi (${cond.design_standard || "DIN 6608 / St37 · Spec 5250"})`;
      rows = [
        ["Tank Hacmi & Standart:", `${cond.collection_tank_volume_m3 || 15} m³ (Baz ${cond.spec_5250_base_tank_m3 || 5} m³ · 15× Blow-Flask=${cond.min_15x_blowflask_m3 || 3} m³ · 2 bar Test)`],
        ["Ex-Proof Dalgıç Pompa:", `${cond.pump_flow_m3h || 10}±20% m³/h @ ${cond.pump_head_m || 5} m (${cond.pump_motor_kw || 4} kW · Spec 4190)`],
        ["Drenaj & Enstrümantasyon:", `${cond.source_drains || "MFS & CFS Blow-Flask → Atmosferik Siklon"} · LI/LSL/LSH`],
        ["Kaplama & Vent:", `${cond.coating || "İç Sentetik + Dış Kömür Katranı Epoksi (5420)"} · Alev Tutucu (Note 14)`],
      ];
    } else if (key === "pig_receiver") {
      const pig = eq.pigging || {};
      tag = `PIG-R-56"x48"`;
      sub = `Suction Pig Alıcı Kovanı & İstasyon Yan Vanaları (4500 §5.4, §5.12–13)`;
      rows = [
        ["Kovan Ölçüsü:", `${pig.receiver || 'PIG-R 56"x48" (ANSI Class 600)'}`],
        ["İşletme Basıncı:", `${sm.suction_pressure_bar || 45.0} bar(a)`],
        ["İstasyon Yan & Ana Vana:", `${pig.side_valves || "Gas-over-Oil Fail-Closed"} · ΔP Kilidi: ${pig.dp_interlock_barg || "0.5–4.0 barg"}`],
        ["Loading & Station Bypass:", `${pig.loading_line || "4500 §5.12 Loading"} · ${pig.station_bypass_check || "4500 §5.13 Non-Slam Check Bypass"}`],
        ["Kicker & Scraper Tee:", `≥%50 Branşmanda Scraper-Barred Tee · Manyetik Pinger`],
      ];
    } else if (key === "cooler_bypass") {
      tag = `TCV-101 BY-PASS`;
      sub = `Gaz Soğutucu By-Pass & Sıcaklık Kontrol Hattı (Spec 4500 §5.14 / Note 17)`;
      rows = [
        ["Vana & Aktüatör Tipi:", `Termostatik ON/OFF Baypas · Gas-over-Oil Hidrolik · Fail-Open`],
        ["By-Pass Debisi:", `Maks. %35 İstasyon Debisi`],
        ["Birincil Kontrol:", `Forced-Draft VFD Fanlar (IEEE 519 · SCS 4-20 mA)`],
        ["İkincil Kontrol:", `TCV Sıcak Gaz Karıştırma Baypası`],
        ["Boru Malzemesi:", `${suctLine.pipe_material || 'API 5L X70'}`],
        ["Görev:", `Kış aylarında / düşük debide aşırı soğumayı önlemek · Sinyal kaybında Fail-Open`],
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
    } else if (key === "air_compressor_building" || key === "station_utilities") {
      const util = eq.station_utilities || {};
      const ca = util.compressed_air || {};
      const ug = util.utility_gas || {};
      const pg = util.power_gas || {};
      const hg = util.heating_glycol || {};
      const sb = util.safety_and_bypass || {};
      tag = key === "station_utilities" ? `UTIL-101..401` : `BLDG-UTIL / AIR`;
      sub = key === "station_utilities"
        ? `Power Gas (MeOH), Kullanım Gazı (≥1485 Sm³/h), Basınçlı Hava & 90/70 °C Glikol Sistemleri`
        : `Enstrüman ve Tesis Servis Havası Binası (Spec 4320 / 4330 / Özel §4.8.7)`;
      rows = [
        ["Basınçlı Hava & Kurutucu:", `${ca.demand_nm3h || "-"} Nm³/h · ${ca.compressor_configuration || "1+1 %100 VFD Eş-Yaşlandırma"}`],
        ["Hava Kalitesi & Tank (4320/4330):", `${ca.dewpoint_c ?? -40} °C Çiy Noktası (Alarm ${ca.high_dewpoint_alarm_c ?? -20} °C) · Tank ${ca.receiver_volume_m3 ?? 25} m³ (≥${ca.holdup_time_min ?? 10} dk) · ≥304 SS`],
        ["Kullanım Gazı Skidi (Özel §4.8.6):", `Çekiş: ${ug.takeoff_location || "Gas Cooler Girişi"} · Kapasite ${ug.calculated_demand_sm3h || 1485} Sm³/h (Min 1485) · Harici MCC Elektrik Isıtıcı + Odorizer + PE`],
        ["Power Gas & Metanol Dehidratör:", `${pg.design_pressure_bar ?? 82.5} bar(g) (%110 MAOP) · Hammerschmidt ΔT=${pg.methanol_dehydrator?.hammerschmidt_depression_c ?? "-"} °C · 1\" Drop / 1/2\" SS`],
        ["Isıtma Glikol & Emniyet (§11 / §5.12-13):", `${hg.heat_load_kw || "-"} kWth (${hg.medium || "90/70 °C %50/%50 Glikol"} · 2×70% Kazan · 3×50% Pompa) · ${sb.station_bypass_check || "Non-Slam Check Bypass"}`],
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
    } else if (key === "fire_water") {
      const fw = eq.station_utilities?.fire_water || {};
      tag = `FW-101 / F&G`;
      sub = `Yangın Suyu, F&G Algılama & Söndürme Sistemi (4500 §14 / NFPA 20)`;
      rows = [
        ["Depolama Tankı:", `${fw.tank_volume_m3 ?? 300} m³ Yangın Suyu Tankı`],
        ["Pompa Grubu:", `${fw.pumps || "NFPA 20: 1 Elektrikli + 1 Dizel + 1 Jockey"}`],
        ["Hidrant & F&G:", `${fw.ring_main_hydrants || "Çevre Ring Hidrant + %20 LEL IR / UV-IR"}`],
        ["Türbin Kabini Söndürme:", `${fw.turbine_enclosure_suppression || "Otomatik CO2 / Temiz Gaz"}`],
      ];
    } else if (key === "station_suction_valve" || key === "station_discharge_valve") {
      const sv = key === "station_suction_valve" ? (eq.station_suction_valve || {}) : (eq.station_discharge_valve || {});
      tag = sv.tag || (key === "station_suction_valve" ? "SV-IN" : "SV-OUT");
      sub = `${sv.name || "İstasyon Yan Vanası"} (4500 §5.4 / Özel §5.4)`;
      rows = [
        ["Vana Standardı:", `${sv.standard || "API 6D QSL 2 · Block & Bleed Küresel"}`],
        ["Aktüatör & Fail-Safe:", `${sv.actuator || "Gas-over-Oil"} · ${sv.fail_action || "Fail-Closed"}`],
        ["ΔP Kilidi:", `${sv.dp_interlock || "0.5–4.0 barg ayarlanabilir"}`],
        ["Gövde Vent / Yağlama:", `${sv.body_vent_class || "1500 Class küresel + sürgülü vana"}`],
      ];
    } else if (key === "mainline_block_valve") {
      const ml = eq.mainline_block_valve || {};
      tag = ml.tag || "MLBV-101";
      sub = `${ml.name || "Ana Hat Blok Vanası"} (4500 §5.4)`;
      rows = [
        ["Çap & Standart:", `${ml.nominal_size || suctLine.nominal_size_in || '48"'} · ${ml.standard || "API 6D QSL 2"}`],
        ["Aktüatör & Fail-Safe:", `${ml.actuator || "Gas-over-Oil"} · ${ml.fail_action || "Fail-Open"}`],
        ["ΔP Kilidi:", `${ml.dp_interlock || "0.5–4.0 barg ayarlanabilir"}`],
        ["Yerleşim:", `${ml.pit_installation || "Vent & drenajlı vana çukuru"}`],
      ];
    } else if (key === "station_loading_line") {
      const ld = eq.station_loading_line || {};
      tag = ld.tag || "LV-101 / LV-102";
      sub = `${ld.name || "İstasyon Dolum Hattı"} (4500 §5.12 / Özel §5.4)`;
      rows = [
        ["Konum:", `SV-IN (İstasyon Giriş Vanası) Etrafında By-Pass`],
        ["Memba Vanası:", `${ld.upstream_valve || "Flanşlı Küresel Vana"}`],
        ["Mansap Vanası:", `${ld.downstream_valve || "Flanşlı Globe Vana · Kapalı Limit Switch Alarmı"}`],
        ["Uzaktan Kontrol:", `${ld.remote_control_ozel_5_4 ? "Aktif (Özel §5.4 uzaktan açma-kapama)" : "Manuel"}`],
      ];
    } else if (key === "station_bypass_valve") {
      const bp = eq.station_bypass_valve || {};
      tag = bp.tag || "NRV-BP-101";
      sub = `${bp.name || "İstasyon By-Pass Non-Slam Çekvalf"} (4500 §5.13)`;
      rows = [
        ["Vana Tipi:", `${bp.valve_type || "Piston / Nozul Non-Slam Çekvalf"}`],
        ["Bağlantı Yeri:", `${bp.tie_in_location || "Discharge (Soğutucu sonrası, USM öncesi) ↔ Suction"}`],
        ["Çap:", `${bp.nominal_size || suctLine.nominal_size_in || '48"'}`],
      ];
    } else if (key === "pig_launcher" || key === "tiein") {
      const pig = eq.pigging || {};
      tag = `PIG-R / PIG-L`;
      sub = `${suctLine.nominal_size_in || '48"'} Doğal Gaz Ana Hat & Pig Kovanları (4500 §5.4, §5.12–13)`;
      rows = [
        ["Ana Hat Çapı:", `${suctLine.nominal_size_in || '48"'} NPS (OD: ${suctLine.od_mm || 1219} mm) ${suctLine.pipe_material || 'API 5L X70'}`],
        ["Kovan Ölçüsü:", `${pig.receiver || 'PIG-R'} / ${pig.launcher || 'PIG-L'}`],
        ["Blok Vana & ΔP Kilidi:", `${pig.mainline_block_valve || "Gas-over-Oil Fail-Open"} · ΔP: ${pig.dp_interlock_barg || "0.5–4.0 barg"}`],
        ["Loading & Bypass:", `${pig.loading_line || "Loading (§5.12)"} · ${pig.station_bypass_check || "Non-Slam Check (§5.13)"}`],
        ["İşletme Basıncı:", `${sm.suction_pressure_bar || 45} bar(a) Emiş • ${sm.discharge_pressure_bar || 75} bar(a) Basma`],
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
    if (key === "air_coolers") {
      const ac = eq.air_coolers || {};
      const airTempVal = ac.air_inlet_temp_c ?? sm.ambient_temp_c ?? 15.0;
      const maxOutVal = ac.requested_max_outlet_temp_c ?? 45.0;
      interactiveFormHtml = `
        <div style="background: rgba(15,23,42,0.85); border: 1px solid rgba(52,211,153,0.40); border-radius: 6px; padding: 8px; margin-bottom: 10px;">
          <div style="font-size: 10.5px; font-weight: 700; color: #34d399; margin-bottom: 6px;">
            ❄️ Gas Cooler Hava &amp; Maks. Çıkış Sıcaklığı (Kullanıcı Girişi)
          </div>
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 6px; font-size: 10px;">
            <label style="color:#cbd5e1; display:flex; flex-direction:column; gap:2px;">
              Hava Sıcaklığı (°C)
              <input type="number" id="hud-cooler-air-temp" step="0.5" min="-30" max="60" value="${escapeHtml(airTempVal)}" style="background:#0f172a; color:#f8fafc; border:1px solid #334155; border-radius:4px; padding:2px 4px; font-size:10px; font-family:monospace;" />
            </label>
            <label style="color:#cbd5e1; display:flex; flex-direction:column; gap:2px;">
              Maks. Gaz Çıkışı (°C)
              <input type="number" id="hud-cooler-max-out-temp" step="0.5" min="15" max="90" value="${escapeHtml(maxOutVal)}" style="background:#0f172a; color:#f8fafc; border:1px solid #334155; border-radius:4px; padding:2px 4px; font-size:10px; font-family:monospace;" />
            </label>
          </div>
          <button id="btn-hud-calc-cooler" style="margin-top: 7px; width: 100%; background: #059669; color: #fff; border: 1px solid #34d399; border-radius: 5px; padding: 5px 8px; font-size: 10.5px; font-weight: 700; cursor: pointer;">
            🧮 Gas Cooler &amp; Akış Aşağı Hatları Güncelle
          </button>
        </div>
      `;
    } else if (key === "safety_relief") {
      const psv = eq.safety_relief_and_blowdown || {};
      const psvSetVal = psv.psv_set_pressure_bar ?? 82.5;
      const psvOverVal = psv.psv_overpressure_pct ?? 10;
      const psvBackVal = psv.psv_back_pressure_bar ?? psv.ambient_pressure_bar ?? 1.01325;
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
              <input type="number" id="hud-psv-set" step="0.5" value="${escapeHtml(psvSetVal)}" style="background:#0f172a; color:#f8fafc; border:1px solid #334155; border-radius:4px; padding:2px 4px; font-size:10px; font-family:monospace;" />
            </label>
            <label style="color:#cbd5e1; display:flex; flex-direction:column; gap:2px;">
              Aşırı Basınç (%)
              <input type="number" id="hud-psv-over" step="1" min="1" max="25" value="${escapeHtml(psvOverVal)}" style="background:#0f172a; color:#f8fafc; border:1px solid #334155; border-radius:4px; padding:2px 4px; font-size:10px; font-family:monospace;" />
            </label>
            <label style="color:#cbd5e1; display:flex; flex-direction:column; gap:2px;">
              Karşı Basınç (bar a, boş=P_atm)
              <input type="number" id="hud-psv-back" step="0.01" placeholder="${escapeHtml(Number(psv.ambient_pressure_bar || 1.01325).toFixed(4))}" value="${escapeHtml(psvBackVal)}" style="background:#0f172a; color:#f8fafc; border:1px solid #334155; border-radius:4px; padding:2px 4px; font-size:10px; font-family:monospace;" />
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
      const hpVolVal = esd.esd_hp_volume_m3 ?? 50.0;
      const lpVolVal = esd.esd_lp_volume_m3 ?? 40.0;
      interactiveFormHtml = `
        <div style="background: rgba(15,23,42,0.85); border: 1px solid rgba(239,68,68,0.40); border-radius: 6px; padding: 8px; margin-bottom: 10px;">
          <div style="font-size: 10.5px; font-weight: 700; color: #f87171; margin-bottom: 6px;">
            🚨 ESD / BDV Hacim, Sayı &amp; Çap Girdileri (Kullanıcı Girişi)
          </div>
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 6px; font-size: 10px;">
            <label style="color:#cbd5e1; display:flex; flex-direction:column; gap:2px;">
              YB Borulama Hacmi (m³, @ P_out)
              <input type="number" id="hud-esd-hp-vol" step="5" min="1" max="5000" value="${escapeHtml(hpVolVal)}" style="background:#0f172a; color:#f8fafc; border:1px solid #334155; border-radius:4px; padding:2px 4px; font-size:10px; font-family:monospace;" />
            </label>
            <label style="color:#cbd5e1; display:flex; flex-direction:column; gap:2px;">
              DB Borulama Hacmi (m³, @ P_in)
              <input type="number" id="hud-esd-lp-vol" step="5" min="1" max="5000" value="${escapeHtml(lpVolVal)}" style="background:#0f172a; color:#f8fafc; border:1px solid #334155; border-radius:4px; padding:2px 4px; font-size:10px; font-family:monospace;" />
            </label>
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
              <input type="number" id="hud-esd-dp" step="0.05" min="0.05" value="${escapeHtml(esdDpVal)}" style="background:#0f172a; color:#f8fafc; border:1px solid #334155; border-radius:4px; padding:2px 4px; font-size:10px; font-family:monospace;" />
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
              <input type="number" id="hud-esd-bdv-time" step="1" min="1" max="60" value="${escapeHtml(bdvTimeVal)}" style="width:70px; background:#0f172a; color:#f8fafc; border:1px solid #334155; border-radius:4px; padding:2px 4px; font-size:10px; font-family:monospace;" />
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
          <div style="font-size: 13px; font-weight: 800; color: #38bdf8; letter-spacing: 0.5px;">${escapeHtml(tag)}</div>
          <div style="font-size: 10.5px; color: #94a3b8; margin-top: 1px;">${escapeHtml(sub)}</div>
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
                <td style="padding: 3px 0; color: #94a3b8;">${escapeHtml(lbl)}</td>
                <td style="padding: 3px 0; text-align: right; font-family: monospace; font-weight: 600; color: #f8fafc;">${escapeHtml(val)}</td>
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

  const AUX_PIPE_PARENT_MAP = {
    pig_bypass: "suction_header",
    pig_kicker_receiver: "suction_header",
    pig_kicker_launcher: "discharge_header",
    psv_inlet: "discharge_header",
    esd_riser: "discharge_header",
  };

  function buildPipeTelemetryHtml(pipeMeta) {
    const directLine = pLines[pipeMeta?.lineKey] || null;
    const parentKey = pipeMeta?.parentLineKey || AUX_PIPE_PARENT_MAP[pipeMeta?.lineKey] || null;
    const parentLine = parentKey ? pLines[parentKey] : null;
    const lineData = directLine || parentLine || {};
    const isDischSide =
      parentKey === "discharge_header" ||
      String(pipeMeta?.lineKey || "").includes("disch") ||
      String(pipeMeta?.lineKey || "").includes("cooler") ||
      pipeMeta?.lineKey === "psv_inlet" ||
      pipeMeta?.lineKey === "esd_riser";

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

    const od = directLine
      ? Number(directLine.od_mm || 0)
      : Number(pipeMeta?.derivedOdMm || lineData.od_mm || (isDischSide ? dischHeaderOdMm : suctHeaderOdMm) || 0);
    const computedNps = od > 0 ? `${Math.max(1, Math.round(od / 25.4))}"` : "-";
    const nps = escapeHtml(
      directLine
        ? directLine.nominal_size_in || computedNps
        : pipeMeta?.derivedNps || computedNps
    );
    const sch = escapeHtml(
      directLine
        ? directLine.schedule || "-"
        : lineData.schedule || (isDischSide ? "Sch 80" : "Sch 40")
    );
    const odRatio = parentLine && Number(parentLine.od_mm) > 0 && od > 0 ? od / Number(parentLine.od_mm) : 1;
    const thick = directLine
      ? Number(directLine.wall_thickness_mm || 0)
      : Number(
          (parentLine?.wall_thickness_mm
            ? Number(parentLine.wall_thickness_mm) * Math.max(0.45, Math.min(1.0, odRatio))
            : 0) || (od > 0 ? Math.max(6.35, od * 0.022) : 0)
        );
    const treq = directLine
      ? Number(directLine.min_required_thickness_mm || 0)
      : Number(
          (parentLine?.min_required_thickness_mm
            ? Number(parentLine.min_required_thickness_mm) * Math.max(0.45, Math.min(1.0, odRatio))
            : 0) || (thick > 0 ? thick * 0.78 : 0)
        );
    const baseFlow = Number(lineData.flow_kgs || sm.total_mass_flow_kgs || 120.0);
    const flow = directLine
      ? Number(directLine.flow_kgs || 0)
      : Number((baseFlow * Math.max(0.08, Math.min(1.0, odRatio * odRatio))).toFixed(1));
    const press = directLine
      ? Number(directLine.pressure_bar || 0)
      : Number(lineData.pressure_bar || (isDischSide ? sm.discharge_pressure_bar || 75.0 : sm.suction_pressure_bar || 45.0));
    const vel = directLine
      ? Number(directLine.actual_velocity_ms || 0)
      : Number(lineData.actual_velocity_ms || (isDischSide ? 14.5 : 12.8));
    const evr = directLine
      ? Number(directLine.erosion_ratio_pct || 0)
      : Number(lineData.erosion_ratio_pct || 42.0);
    const dp = directLine
      ? Number(directLine.pressure_drop_bar_per_100m || 0)
      : Number(lineData.pressure_drop_bar_per_100m || 0.035);

    const maxVelLimit = Number(lineData.max_velocity_ms || stationData?.station_piping?.max_velocity_ms || 20.0);
    const indivNps = escapeHtml(lineData.individual_nominal_size_in || nps);
    const acceptableSummary = escapeHtml(lineData.acceptable_diameters_summary || nps);

    const rows = [
      ["Anma Çapı & OD:", `${nps} (${od ? od.toFixed(1) + " mm" : "-"} • Sch ${sch})`],
      ["Tekil Min. / Uygulanan Çap:", `${indivNps} → ${nps}${lineData.header_size_equalized ? " (Ortak Header)" : ""}`],
      ["Hız Limiti Uygun Çaplar:", acceptableSummary],
      ["Et Kalınlığı / Barlow:", `${thick ? thick.toFixed(2) + " mm" : "-"} (t_req: ${treq ? treq.toFixed(2) + " mm" : "-"})`],
      ["Tasarım Debisi & Basınç:", `${flow.toFixed(1)} kg/s @ ${press.toFixed(1)} bar(a)`],
      ["Gaz Hızı / Sınır & EVR:", `${vel.toFixed(2)} / ≤ ${maxVelLimit.toFixed(1)} m/s (%${evr.toFixed(1)} EVR)`],
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

      <div style="background: rgba(0,0,0,0.25); border-radius: 6px; padding: 6px 8px; margin-bottom: 8px;">
        <table style="width: 100%; border-collapse: collapse; font-size: 10.5px;">
          <tbody>
            ${rows.map(([lbl, val]) => `
              <tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
                <td style="padding: 3px 0; color: #94a3b8;">${escapeHtml(lbl)}</td>
                <td style="padding: 3px 0; text-align: right; font-family: monospace; font-weight: 600; color: #f8fafc;">${val}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>

      <div style="background: rgba(15,23,42,0.85); border: 1px solid rgba(250,204,21,0.35); border-radius: 6px; padding: 6px 8px; margin-bottom: 8px; display: flex; align-items: center; justify-content: space-between; gap: 6px; font-size: 10px;">
        <span style="color: #fde047; font-weight: 700;">Maks. Gaz Hızı Sınırı (m/s):</span>
        <div style="display: flex; align-items: center; gap: 5px;">
          <input type="number" id="hud-pipe-max-vel" step="0.5" min="2" max="60" value="${escapeHtml(maxVelLimit)}" style="width: 58px; background: #0f172a; color: #f8fafc; border: 1px solid #334155; border-radius: 4px; padding: 2px 4px; font-size: 10px; font-family: monospace;" />
          <button id="btn-hud-calc-pipe-vel" style="background: #ca8a04; color: #fff; border: 1px solid #facc15; border-radius: 4px; padding: 3px 7px; font-size: 10px; font-weight: 700; cursor: pointer;">Uygula</button>
        </div>
      </div>

      <div style="display: flex; gap: 8px;">
        <button id="btn-pipe-flyto" style="flex: 1; background: #0284c7; color: #fff; border: 1px solid #38bdf8; border-radius: 6px; padding: 5px 8px; font-size: 10.5px; font-weight: 600; cursor: pointer;">
          🎯 Hatta Yaklaş (Fly-To)
        </button>
        ${pipeMeta?.equipKey ? `<button id="btn-pipe-open-equip" style="flex: 1; background: #334155; color: #f8fafc; border: 1px solid rgba(255,255,255,0.22); border-radius: 6px; padding: 5px 8px; font-size: 10.5px; font-weight: 600; cursor: pointer;">${escapeHtml(t("pipe_hud_open_equip", uiLang))}</button>` : ""}
      </div>
    `;
  }

  let activeInspectedPipe = null;

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
    activeInspectedPipe = { pipeMeta, targetObject };

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
        activeInspectedPipe = null;
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

      hudEl.querySelector("#btn-hud-calc-pipe-vel")?.addEventListener("click", () => {
        if (typeof options.onUpdateSafetyInputs !== "function") return;
        const maxVel = parseFloat(hudEl.querySelector("#hud-pipe-max-vel")?.value);
        if (Number.isFinite(maxVel) && maxVel >= 2.0 && maxVel <= 60.0) {
          options.onUpdateSafetyInputs({ max_velocity_ms: maxVel });
        }
      });
    }
    return true;
  }

  function selectAndInspectEquipment(key, targetObject) {
    if (!key) return;
    activeInspectedPipe = null;

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
        const camTarget = resolveEquipmentCameraTarget(key, target);
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

      hudEl.querySelector("#btn-hud-calc-cooler")?.addEventListener("click", () => {
        if (typeof options.onUpdateSafetyInputs !== "function") return;
        const airRaw = hudEl.querySelector("#hud-cooler-air-temp")?.value;
        const maxOutRaw = hudEl.querySelector("#hud-cooler-max-out-temp")?.value;
        const airVal = parseFloat(airRaw);
        const maxOutVal = parseFloat(maxOutRaw);
        options.onUpdateSafetyInputs({
          cooler_air_temp_c: airRaw !== "" && Number.isFinite(airVal) ? airVal : "",
          cooler_max_outlet_temp_c: Number.isFinite(maxOutVal) && maxOutVal >= 15.0 ? maxOutVal : 45.0,
        });
      });

      hudEl.querySelector("#btn-hud-calc-psv")?.addEventListener("click", () => {
        if (typeof options.onUpdateSafetyInputs !== "function") return;
        const psvCount = parseInt(hudEl.querySelector("#hud-psv-count")?.value || "2", 10);
        const psvDuty = parseInt(hudEl.querySelector("#hud-psv-duty")?.value || "1", 10);
        const psvSet = parseFloat(hudEl.querySelector("#hud-psv-set")?.value);
        const psvOver = parseFloat(hudEl.querySelector("#hud-psv-over")?.value);
        const psvBackRaw = hudEl.querySelector("#hud-psv-back")?.value;
        const psvBack = parseFloat(psvBackRaw);
        const psvType = hudEl.querySelector("#hud-psv-type")?.value || "conventional";
        options.onUpdateSafetyInputs({
          psv_count: Number.isFinite(psvCount) ? psvCount : 2,
          psv_duty_count: Number.isFinite(psvDuty) ? Math.min(psvCount, psvDuty) : 1,
          psv_set_pressure_bar: Number.isFinite(psvSet) && psvSet > 0 ? psvSet : "",
          psv_overpressure_pct: Number.isFinite(psvOver) && psvOver > 0 ? psvOver : 10,
          psv_back_pressure_bar: psvBackRaw !== "" && Number.isFinite(psvBack) && psvBack > 0 ? psvBack : "",
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
        const hpVol = parseFloat(hudEl.querySelector("#hud-esd-hp-vol")?.value);
        const lpVol = parseFloat(hudEl.querySelector("#hud-esd-lp-vol")?.value);
        options.onUpdateSafetyInputs({
          esd_count: Number.isFinite(esdCount) ? esdCount : 2,
          esd_duty_count: Number.isFinite(esdDuty) ? Math.min(esdCount, esdDuty) : 1,
          esd_allowable_dp_bar: Number.isFinite(esdDp) && esdDp > 0 ? esdDp : 0.5,
          esd_valve_type: esdType,
          bdv_depressurization_time_min: Number.isFinite(bdvTime) && bdvTime > 0 ? bdvTime : 15,
          esd_hp_volume_m3: Number.isFinite(hpVol) && hpVol > 0 ? hpVol : 50.0,
          esd_lp_volume_m3: Number.isFinite(lpVol) && lpVol > 0 ? lpVol : 40.0,
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

  const fullscreenBtn = container.querySelector("#btn-toggle-3d-fullscreen");

  const unsubUi = uiStore ? uiStore.subscribe((ui) => {
    if (ui.lang && ui.lang !== uiLang) {
      uiLang = ui.lang;
      syncPipeLabelsButton();
      if (fullscreenBtn && rootEl) {
        const isExp = rootEl.classList.contains("station-3d-expanded");
        fullscreenBtn.textContent = isExp
          ? `⛶ ${t("btn_3d_exit_fullscreen", uiLang)}`
          : `⛶ ${t("btn_3d_fullscreen", uiLang)}`;
      }
      if (activeInspectedPipe) {
        selectAndInspectPipe(activeInspectedPipe.pipeMeta, activeInspectedPipe.targetObject);
      }
      syncToolbarAria();
    }
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
      fullscreenBtn.title = fullscreenBtn.textContent.replace(/\s+/g, " ").trim();
    }
    requestAnimationFrame(() => onResize());
  }
  fullscreenBtn?.addEventListener("click", () => {
    set3dFullscreen(!rootEl?.classList.contains("station-3d-expanded"));
  });

  function onRootPointerDown(ev) {
    if (
      ev.target &&
      typeof ev.target.closest === "function" &&
      !ev.target.closest("button, input, textarea, select, label, [contenteditable='true'], #equip-telemetry-hud, #pipe-section-overlay")
    ) {
      rootEl.focus({ preventScroll: true });
    }
  }
  function onRootKeyDown(ev) {
    if (ev.ctrlKey || ev.metaKey || ev.altKey) return;
    const tgt = ev.target;
    if (
      tgt &&
      (tgt.tagName === "INPUT" ||
        tgt.tagName === "TEXTAREA" ||
        tgt.tagName === "SELECT" ||
        tgt.isContentEditable ||
        (typeof tgt.closest === "function" &&
          tgt.closest("input, textarea, select, [contenteditable='true']")))
    ) {
      return;
    }
    if (document.getElementById("kasp-equipment-teardown")) return;
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
      activeInspectedPipe = null;
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
      parentLineKey: route.parentLineKey || null,
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
      activeInspectedPipe = null;
      // Tear down any open exploded-view overlay before disposing the main scene.
      closeEquipmentTeardown();
      if (animationFrameId) cancelAnimationFrame(animationFrameId);
      if (pointerMoveRaf) cancelAnimationFrame(pointerMoveRaf);
      if (unsubUi) unsubUi();
      document.removeEventListener("visibilitychange", onVisibilityChange);
      window.removeEventListener("resize", onResize);
      if (rootEl) {
        rootEl.classList.remove("station-3d-expanded");
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

      // Recursive disposal of meshes, lines, points, sprites, geometries and materials.
      // Guard !obj.isSprite so Three.js r128 shared singleton Sprite geometry is not disposed.
      scene.traverse((obj) => {
        if (obj.isMesh || obj.isLine || obj.isPoints || obj.isSprite) {
          if (obj.geometry && !obj.isSprite) {
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
        const camTarget = resolveEquipmentCameraTarget(key, obj);
        if (camTarget) {
          flyToCamera(camTarget.pos, camTarget.look);
        }
      }
    },
    clearSelection: () => {
      activeInspectedPipe = null;
      const hudEl = container.querySelector("#equip-telemetry-hud");
      if (hudEl) hudEl.style.display = "none";
      rootEl?.removeAttribute("data-inspect");
      if (selectedHighlightBox) selectedHighlightBox.visible = false;
    },
  };
}
