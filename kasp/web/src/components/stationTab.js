/**
 * KASP Compressor Station Modeling & Animated Process Flow Tab Component (stationTab.js)
 * Implements full process flow verified against BOTAŞ Adapazarı PFD (0-NGTL0-CS-I-001-4000):
 * - Mainline tie-ins with Pig Receivers and Pig Launchers
 * - 48" Suction Header with dynamic Filter & Multi-Cyclone Separators (A, B, C...)
 * - Condensate Drainage System with LCVs and Condensate Tanks (Note 14)
 * - Cartridge Filter Separators (A, B, C...) with PDT transmitters
 * - Unit Building Shelter with N parallel Turbo-Compressor trains (30"x16" nozzles - Note 32)
 * - Individual Hot Gas Anti-Surge Recycle Loops with fast-acting ASV valves
 * - 48" Discharge Header & 48" Station-wide Recycle Line (Note 13)
 * - Fin-Fan Gas Air Coolers with Gas Cooler By-Pass & TCV secondary control (Note 17)
 * - Station Relief Valves (PSV) & Station Blowdown (BDV) to Emergency Vent
 * - BOTAŞ Adapazarı PFD Reference Drawing Modal Viewer
 */

import { icon } from "../../vendor/icons.js";
import {
  projectStore,
  setModuleResult,
  setStationData,
  convertFlowWithMW,
  convertPressureToBarA,
  convertPressureUnit,
  convertTempToC,
  resolveAmbientBarA,
  escapeHtml,
} from "../store/projectStore.js";
import { showToast, uiStore } from "../store/uiStore.js";
import { t } from "../i18n/locales.js";
import { api } from "../api/client.js";
import { createStation3dView } from "./station3dView.js";

// Same unit menus as the design sidebar so station inputs stay familiar.
const STATION_FLOW_UNITS = ["kg/s", "Sm³/h", "Nm³/h", "kg/h", "MMSCFD", "MMSCMD"];
const STATION_PRESSURE_UNITS = ["bar(a)", "bar(g)", "kPa", "psi"];

function stationFlowDisplay(kgs, unit, gasComp) {
  const value = Number(kgs);
  if (!Number.isFinite(value)) return 0;
  if (!unit || unit === "kg/s") return value;
  const converted = convertFlowWithMW(value, "kg/s", unit, gasComp);
  return Number.isFinite(converted) ? converted : value;
}

function stationFlowToKgs(displayValue, unit, gasComp) {
  const value = Number(displayValue);
  if (!Number.isFinite(value) || value <= 0) return NaN;
  if (!unit || unit === "kg/s") return value;
  return convertFlowWithMW(value, unit, "kg/s", gasComp);
}

function stationPressureDisplay(barA, unit) {
  const value = Number(barA);
  if (!Number.isFinite(value)) return 0;
  return convertPressureUnit(value, "bar(a)", unit || "bar(a)");
}

function stationPressureToBarA(displayValue, unit) {
  const value = Number(displayValue);
  if (!Number.isFinite(value) || value <= 0) return NaN;
  return convertPressureToBarA(value, unit || "bar(a)");
}

function roundDisplay(value) {
  const num = Number(value);
  if (!Number.isFinite(num)) return "";
  return Math.round(num * 100) / 100;
}

const STATION_2D_FOCUS_ZONES = {
  all: { x: 0, y: 0, w: 1180, h: 580, label: "Tüm Tesis" },
  pig_r: { x: 0, y: 120, w: 320, h: 280, label: "PIG-R Giriş" },
  filtration: { x: 160, y: 60, w: 300, h: 460, label: "Siklon & Kartuş Filtre" },
  compressors: { x: 350, y: 70, w: 430, h: 420, label: "Ünite Binası & Kompresörler" },
  cooler: { x: 730, y: 90, w: 320, h: 360, label: "Hava Soğutucu & Baypas" },
  psv_bdv: { x: 860, y: 80, w: 320, h: 360, label: "PSV / BDV & PIG-L" },
};

function renderStation2dViewport(data, lang) {
  return `
    <div id="station-2d-viewport" tabindex="0" class="station-canvas-container" style="min-height: 560px; position: relative; overflow: hidden; user-select: none; outline: none;">
      <style>
        #station-2d-viewport.station-2d-expanded {
          position: fixed !important;
          inset: 0 !important;
          width: 100vw !important;
          height: 100vh !important;
          z-index: 9999 !important;
          background: var(--color-surface, #0f172a) !important;
          border-radius: 0 !important;
          padding: 16px !important;
        }
        #station-2d-viewport.station-2d-expanded svg {
          width: 100% !important;
          height: 100% !important;
        }
        #station-2d-viewport.pid-hide-tags .isa-instrument-group {
          opacity: 0;
          pointer-events: none;
          transition: opacity 150ms ease;
        }
      </style>
      <div class="station-2d-toolbar" style="position: absolute; top: 10px; right: 10px; z-index: 15; display: flex; flex-wrap: wrap; align-items: center; gap: 4px; background: rgba(15, 23, 42, 0.88); backdrop-filter: blur(6px); padding: 4px 8px; border-radius: 16px; border: 1px solid rgba(255,255,255,0.16); max-width: calc(100% - 20px);">
        <select id="select-2d-focus-equip" aria-label="${escapeHtml(t("select_2d_focus", lang))}" style="background: #1e293b; color: #e2e8f0; border: 1px solid rgba(255,255,255,0.2); border-radius: 10px; padding: 2px 6px; font-size: 10.5px; cursor: pointer;">
          <option value="all">${escapeHtml(t("select_2d_focus", lang))}</option>
          <option value="pig_r">${escapeHtml(t("station_focus_pig_r", lang))}</option>
          <option value="filtration">${escapeHtml(t("station_focus_filtration", lang))}</option>
          <option value="compressors">${escapeHtml(t("station_focus_compressors", lang))}</option>
          <option value="cooler">${escapeHtml(t("station_focus_cooler", lang))}</option>
          <option value="psv_bdv">${escapeHtml(t("station_focus_psv_bdv", lang))}</option>
        </select>
        <span id="pid-zoom-badge" style="font-family: var(--font-mono); font-size: 10px; font-weight: 700; color: #38bdf8; padding: 2px 6px; background: rgba(56,189,248,0.12); border-radius: 8px;">%100</span>
        <button type="button" id="btn-2d-zoom-in" class="btn btn-sm" title="${escapeHtml(t("btn_2d_zoom_in", lang))}" style="padding: 2px 7px; font-size: 11px; font-weight: 700;">+</button>
        <button type="button" id="btn-2d-zoom-out" class="btn btn-sm" title="${escapeHtml(t("btn_2d_zoom_out", lang))}" style="padding: 2px 7px; font-size: 11px; font-weight: 700;">−</button>
        <button type="button" id="btn-2d-zoom-reset" class="btn btn-sm" title="${escapeHtml(t("btn_2d_zoom_reset", lang))} (0)" style="padding: 2px 7px; font-size: 10.5px;">${escapeHtml(t("btn_2d_zoom_reset", lang))}</button>
        <button type="button" id="btn-2d-toggle-tags" class="btn btn-sm" aria-pressed="true" title="${escapeHtml(t("btn_2d_tags", lang))}" style="padding: 2px 7px; font-size: 10.5px;">🏷️ ${escapeHtml(t("btn_2d_tags", lang))}</button>
        <button type="button" id="btn-2d-fullscreen" class="btn btn-sm" aria-pressed="false" title="${escapeHtml(t("btn_3d_fullscreen", lang))}" style="padding: 2px 7px; font-size: 10.5px;">⛶ ${escapeHtml(t("btn_3d_fullscreen", lang))}</button>
        <button type="button" id="btn-2d-export-svg" class="btn btn-sm btn-primary" title="${escapeHtml(t("btn_2d_export_svg", lang))}" style="padding: 2px 8px; font-size: 10.5px;">${escapeHtml(t("btn_2d_export_svg", lang))}</button>
        <button type="button" id="btn-2d-export-png" class="btn btn-sm" title="${escapeHtml(t("btn_2d_export_png", lang))}" style="padding: 2px 8px; font-size: 10.5px;">${escapeHtml(t("btn_2d_export_png", lang))}</button>
      </div>
      ${renderStationSvg(data)}
    </div>
  `;
}

function bindStation2dControls(container, lang) {
  container._s2dAbort?.abort();
  const ac = new AbortController();
  container._s2dAbort = ac;
  const viewport = container.querySelector("#station-2d-viewport");
  if (!viewport) return;
  const svg = viewport.querySelector("svg");
  if (!svg) return;

  const BASE_W = 1180;
  const BASE_H = 580;
  let vb = { x: 0, y: 0, w: BASE_W, h: BASE_H };
  let isPanning = false;
  let didDrag = false;
  let startX = 0;
  let startY = 0;
  let startVb = { ...vb };

  const zoomBadge = viewport.querySelector("#pid-zoom-badge");

  function applyViewBox() {
    svg.setAttribute("viewBox", `${vb.x.toFixed(2)} ${vb.y.toFixed(2)} ${vb.w.toFixed(2)} ${vb.h.toFixed(2)}`);
    if (zoomBadge) {
      const pct = Math.round((BASE_W / vb.w) * 100);
      zoomBadge.textContent = `%${pct}`;
    }
  }

  function zoomBy(factor, cx = vb.x + vb.w / 2, cy = vb.y + vb.h / 2) {
    const nextW = Math.min(BASE_W / 0.35, Math.max(BASE_W / 4.0, vb.w * factor));
    const ratio = nextW / vb.w;
    const nextH = vb.h * ratio;
    vb = {
      x: cx - (cx - vb.x) * ratio,
      y: cy - (cy - vb.y) * ratio,
      w: nextW,
      h: nextH,
    };
    applyViewBox();
  }

  viewport.querySelector("#btn-2d-zoom-in")?.addEventListener("click", () => zoomBy(0.8));
  viewport.querySelector("#btn-2d-zoom-out")?.addEventListener("click", () => zoomBy(1.25));
  viewport.querySelector("#btn-2d-zoom-reset")?.addEventListener("click", () => {
    vb = { x: 0, y: 0, w: BASE_W, h: BASE_H };
    const sel = viewport.querySelector("#select-2d-focus-equip");
    if (sel) sel.value = "all";
    applyViewBox();
  });

  viewport.querySelector("#select-2d-focus-equip")?.addEventListener("change", (ev) => {
    const zone = STATION_2D_FOCUS_ZONES[ev.target.value] || STATION_2D_FOCUS_ZONES.all;
    vb = { x: zone.x, y: zone.y, w: zone.w, h: zone.h };
    applyViewBox();
  });

  const tagsBtn = viewport.querySelector("#btn-2d-toggle-tags");
  tagsBtn?.addEventListener("click", () => {
    const hidden = viewport.classList.toggle("pid-hide-tags");
    tagsBtn.setAttribute("aria-pressed", hidden ? "false" : "true");
  });

  viewport.addEventListener("keydown", (ev) => {
    if (ev.key === "+" || ev.key === "=") {
      ev.preventDefault();
      zoomBy(0.8);
    } else if (ev.key === "-" || ev.key === "_") {
      ev.preventDefault();
      zoomBy(1.25);
    } else if (ev.key === "0") {
      ev.preventDefault();
      vb = { x: 0, y: 0, w: BASE_W, h: BASE_H };
      applyViewBox();
    }
  });

  const fsBtn = viewport.querySelector("#btn-2d-fullscreen");
  function set2dFullscreen(expanded) {
    const isExp = !!expanded;
    viewport.classList.toggle("station-2d-expanded", isExp);
    if (fsBtn) {
      fsBtn.setAttribute("aria-pressed", isExp ? "true" : "false");
      fsBtn.textContent = isExp
        ? `⛶ ${t("btn_3d_exit_fullscreen", lang)}`
        : `⛶ ${t("btn_3d_fullscreen", lang)}`;
    }
  }
  fsBtn?.addEventListener("click", () => {
    set2dFullscreen(!viewport.classList.contains("station-2d-expanded"));
  });
  window.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape" && viewport.classList.contains("station-2d-expanded")) {
      set2dFullscreen(false);
    }
  }, { signal: ac.signal });

  viewport.querySelector("#btn-2d-export-svg")?.addEventListener("click", () => {
    const clone = svg.cloneNode(true);
    clone.setAttribute("viewBox", `0 0 ${BASE_W} ${BASE_H}`);
    const xml = new XMLSerializer().serializeToString(clone);
    const blob = new Blob([xml], { type: "image/svg+xml;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "kasp_station_pid.svg";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showToast(t("toast_2d_svg_exported", lang), "success");
  });

  viewport.querySelector("#btn-2d-export-png")?.addEventListener("click", () => {
    const clone = svg.cloneNode(true);
    clone.setAttribute("viewBox", `0 0 ${BASE_W} ${BASE_H}`);
    clone.setAttribute("width", String(BASE_W * 2));
    clone.setAttribute("height", String(BASE_H * 2));
    const xml = new XMLSerializer().serializeToString(clone);
    const svgBlob = new Blob([xml], { type: "image/svg+xml;charset=utf-8" });
    const url = URL.createObjectURL(svgBlob);
    const img = new Image();
    img.onload = () => {
      const canvas = document.createElement("canvas");
      canvas.width = BASE_W * 2;
      canvas.height = BASE_H * 2;
      const ctx = canvas.getContext("2d");
      ctx.fillStyle = "#0b1120";
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(img, 0, 0);
      URL.revokeObjectURL(url);
      canvas.toBlob((pngBlob) => {
        if (!pngBlob) return;
        const pngUrl = URL.createObjectURL(pngBlob);
        const a = document.createElement("a");
        a.href = pngUrl;
        a.download = "kasp_station_pid.png";
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(pngUrl);
        showToast(t("toast_2d_png_exported", lang), "success");
      }, "image/png");
    };
    img.src = url;
  });

  svg.addEventListener("wheel", (ev) => {
    ev.preventDefault();
    const rect = svg.getBoundingClientRect();
    const fx = rect.width > 0 ? (ev.clientX - rect.left) / rect.width : 0.5;
    const fy = rect.height > 0 ? (ev.clientY - rect.top) / rect.height : 0.5;
    zoomBy(ev.deltaY < 0 ? 0.88 : 1.14, vb.x + fx * vb.w, vb.y + fy * vb.h);
  }, { passive: false });

  svg.addEventListener("pointerdown", (ev) => {
    if (ev.button !== 0 || ev.target.closest(".station-2d-toolbar")) return;
    isPanning = true;
    didDrag = false;
    startX = ev.clientX;
    startY = ev.clientY;
    startVb = { ...vb };
  });

  window.addEventListener("pointermove", (ev) => {
    if (!isPanning) return;
    const dx = ev.clientX - startX;
    const dy = ev.clientY - startY;
    if (!didDrag && Math.hypot(dx, dy) > 4) didDrag = true;
    if (!didDrag) return;
    const rect = svg.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) return;
    vb = {
      ...startVb,
      x: startVb.x - (dx / rect.width) * startVb.w,
      y: startVb.y - (dy / rect.height) * startVb.h,
    };
    applyViewBox();
  }, { signal: ac.signal });

  window.addEventListener("pointerup", () => {
    isPanning = false;
  }, { signal: ac.signal });

  svg.addEventListener("click", (ev) => {
    if (didDrag) {
      ev.stopPropagation();
      didDrag = false;
    }
  }, true);
}

function stationProcessSignature(inputs) {
  return JSON.stringify({
    flow: inputs?.flow ?? inputs?.mass_flow,
    flow_unit: inputs?.flow_unit,
    p_in: inputs?.p_in,
    p_in_unit: inputs?.p_in_unit,
    p_out: inputs?.p_out,
    p_out_unit: inputs?.p_out_unit,
    t_in: inputs?.t_in,
    t_in_unit: inputs?.t_in_unit,
    num_units: inputs?.num_units,
    gas_comp: inputs?.gas_comp,
    ambient_temp: inputs?.ambient_temp,
    ambient_pressure: inputs?.ambient_pressure,
    altitude: inputs?.altitude,
  });
}

function normalizeWarningItem(w, prefix = "") {
  let msg = "";
  if (typeof w === "string") msg = w.trim();
  else if (w && typeof w === "object" && w.message) {
    msg = w.field ? `[${w.field}] ${w.message}` : String(w.message).trim();
  }
  if (!msg) return "";
  if (prefix && !msg.startsWith("[") && !msg.toUpperCase().startsWith(prefix.replace(/[\[\]]/g, "").toUpperCase())) {
    return `${prefix} ${msg}`;
  }
  return msg;
}

function collectStationWarnings(stationData) {
  if (!stationData) return [];
  const seen = new Set();
  const warnedErosionTags = new Set();
  const list = [];
  const canonicalKey = (str) =>
    String(str || "")
      .replace(/^(\[[^\]]+\]\s*|ASV:\s*|PCV:\s*|TCV:\s*|PSV:\s*|Hava Soğutucu:\s*|Boru Ağı:\s*)/i, "")
      .trim()
      .toLowerCase();

  const pushAll = (arr, prefix = "") => {
    if (!Array.isArray(arr)) return;
    for (const item of arr) {
      const text = normalizeWarningItem(item, prefix);
      const key = canonicalKey(text);
      if (text && key && !seen.has(key)) {
        seen.add(key);
        list.push(text);
        const tagMatch = text.match(/\b(L-\d{3})\b/);
        if (tagMatch && /erozyon|hız/i.test(text)) {
          warnedErosionTags.add(tagMatch[1]);
        }
      }
    }
  };

  pushAll(stationData.warnings);
  const eq = stationData.equipment_sizing || {};
  pushAll(eq.turbo_compressors?.anti_surge_valve_sizing_warnings, "[ASV]");
  pushAll(eq.turbo_compressors?.anti_surge_valve_sizing?.warnings, "[ASV]");
  pushAll(eq.station_recycle?.pcv_sizing_warnings, "[PCV]");
  pushAll(eq.station_recycle?.pcv_sizing?.warnings, "[PCV]");
  pushAll(eq.air_coolers?.cooler_bypass_valve_sizing_warnings, "[TCV]");
  pushAll(eq.air_coolers?.cooler_bypass_valve_sizing?.warnings, "[TCV]");
  pushAll(eq.air_coolers?.detailed_design_warnings, "[Hava Soğutucu]");
  pushAll(eq.safety_relief_and_blowdown?.psv_sizing_warnings, "[PSV]");
  pushAll(eq.safety_relief_and_blowdown?.psv_sizing?.warnings, "[PSV]");
  pushAll(eq.esd_sizing?.warnings, "[ESD/BDV]");
  pushAll(stationData.station_piping?.warnings, "[Borulama]");

  const linesMap = stationData.station_piping?.lines || {};
  const netMaxVel = Number(stationData.station_piping?.max_velocity_ms || 20.0);
  for (const line of Object.values(linesMap)) {
    if (!line || typeof line !== "object") continue;
    const tag = line.tag || line.line_id || "Hat";
    const evr = Number(line.erosion_ratio_pct || 0);
    const vel = Number(line.actual_velocity_ms || 0);
    const lineMaxVel = Number(line.max_velocity_ms || netMaxVel || 20.0);
    if (!warnedErosionTags.has(tag)) {
      if (evr >= 100.0) {
        pushAll([`${tag} (${line.name || ""}): API RP 14E erozyon hızı aşıldı (EVR=%${evr.toFixed(1)}, v=${vel.toFixed(2)} m/s).`], "[Erozyon]");
      } else if (evr >= 80.0 || vel > lineMaxVel) {
        pushAll([`${tag} (${line.name || ""}): İzin verilen hız / erozyon sınırı yakın veya aşıldı (EVR=%${evr.toFixed(1)}, v=${vel.toFixed(2)} / ${lineMaxVel.toFixed(1)} m/s).`], "[Erozyon]");
      }
    }
    if (line.standard_recommendation && line.standard_recommendation.is_sufficient === false) {
      pushAll([`${tag}: Seçilen et kalınlığı standart minimum değerin altında.`], "[Borulama]");
    }
  }
  return list;
}

export function renderStationTab(container) {
  if (typeof container._stationCleanup === "function") {
    container._stationCleanup();
  }

  let stationData = null;
  let isLoading = false;
  let selectedEquip = null;
  let isPfdModalOpen = false;
  let viewMode = "3d"; // "3d" (default WebGL model), "2d", "split"
  let active3dInstance = null;
  let isParamsPanelOpen = true;
  let provenanceSourceFilter = "all";
  let provenanceSearchQuery = "";
  let debounceTimer = null;

  const projState = projectStore.getState();

  function toKgs(value, unit, gasComp) {
    const raw = Number(value) || 0;
    if (raw <= 0) return 0;
    return convertFlowWithMW(raw, unit || "kg/s", "kg/s", gasComp || projectStore.getState().inputs?.gas_comp);
  }

  const initFlow = toKgs(
    projState?.inputs?.flow ?? projState?.inputs?.mass_flow ?? 120.0,
    projState?.inputs?.flow_unit || "kg/s",
    projState?.inputs?.gas_comp
  );
  const initPin = convertPressureToBarA(projState?.inputs?.p_in ?? 45.0, projState?.inputs?.p_in_unit || "bar(a)") || 45.0;
  const initPout = convertPressureToBarA(projState?.inputs?.p_out ?? 75.0, projState?.inputs?.p_out_unit || "bar(a)") || 75.0;
  const initTin = convertTempToC(projState?.inputs?.t_in ?? 25.0, projState?.inputs?.t_in_unit || "°C");

  const projectFlowUnit = String(projState?.inputs?.flow_unit || "kg/s");
  const projectPinUnit = String(projState?.inputs?.p_in_unit || "bar(a)");
  const projectPoutUnit = String(projState?.inputs?.p_out_unit || "bar(a)");
  // Station panel shows discharge pressure in bar(g) by default (design keeps bar(a)).
  const initialPoutUnit =
    STATION_PRESSURE_UNITS.includes(projectPoutUnit) && projectPoutUnit !== "bar(a)"
      ? projectPoutUnit
      : "bar(g)";
  let stationInputs = {
    mass_flow: Math.round(Number(initFlow) * 1e6) / 1e6,
    mass_flow_unit: STATION_FLOW_UNITS.includes(projectFlowUnit) ? projectFlowUnit : "kg/s",
    p_in: Math.round(Number(initPin) * 10000) / 10000,
    p_in_unit: STATION_PRESSURE_UNITS.includes(projectPinUnit) ? projectPinUnit : "bar(a)",
    p_out: Math.round(Number(initPout) * 10000) / 10000,
    p_out_unit: initialPoutUnit,
    t_in: Math.round(Number(initTin) * 10) / 10,
    comp_op_count: Number(projState?.inputs?.num_units || 0),
    cyclone_op_count: 0,
    filter_op_count: 0,
    cooler_bays_count: 0,
    pipe_material: "API 5L X70",
    design_factor_F: 0.50,
    pipe_standard: "BOTAŞ",
    psl_level: "PSL2",
    max_velocity_ms: 20.0,
    suction_equiv_length_m: 120.0,
    discharge_equiv_length_m: 150.0,
    cyclone_inlet_pipe_size: "",
    cyclone_outlet_pipe_size: "",
    filter_inlet_pipe_size: "",
    filter_outlet_pipe_size: "",
    cooler_air_temp_c: "",
    cooler_max_outlet_temp_c: 45.0,
    // Safety valve sizing overrides; empty strings let the engine derive values from Design Tab.
    psv_set_pressure_bar: "",
    psv_overpressure_pct: 10,
    psv_back_pressure_bar: "",
    psv_valve_type: "conventional",
    psv_count: 2,
    psv_duty_count: 1,
    esd_count: 2,
    esd_duty_count: 1,
    esd_allowable_dp_bar: 0.5,
    esd_valve_type: "full_bore_ball",
    bdv_depressurization_time_min: 15,
    esd_hp_volume_m3: 50.0,
    esd_lp_volume_m3: 40.0,
  };

  let last3dState = null;
  function abort2dControls() {
    if (container._s2dAbort) {
      container._s2dAbort.abort();
      container._s2dAbort = null;
    }
  }

  function destroy3d() {
    if (active3dInstance) {
      if (typeof active3dInstance.getState === "function") {
        last3dState = active3dInstance.getState();
      }
      active3dInstance.destroy();
      active3dInstance = null;
    }
  }

  function setStationBusyState(busy) {
    container.classList.toggle("is-station-busy", !!busy);
    container.setAttribute("aria-busy", busy ? "true" : "false");
    const recalcBtn = container.querySelector("#btn-recalc-station");
    if (recalcBtn) recalcBtn.disabled = !!busy;
    const applyBtn = container.querySelector("#btn-apply-station-params");
    if (applyBtn) applyBtn.disabled = !!busy;
  }

  async function fetchStationData() {
    isLoading = true;
    if (!stationData) {
      render();
    } else {
      setStationBusyState(true);
    }
    const proj = projectStore.getState();
    let didUpdateData = false;
    try {
      const mergedInputs = {
        ...proj.inputs,
        mass_flow: stationInputs.mass_flow,
        flow: stationInputs.mass_flow,
        flow_unit: "kg/s",
        p_in: stationInputs.p_in,
        p_in_unit: "bar(a)",
        p_out: stationInputs.p_out,
        p_out_unit: "bar(a)",
        t_in: stationInputs.t_in,
        t_in_unit: "°C",
        pipe_material: stationInputs.pipe_material,
        design_factor_F: stationInputs.design_factor_F,
        pipe_standard: stationInputs.pipe_standard,
        psl_level: stationInputs.psl_level,
        max_velocity_ms: Number(stationInputs.max_velocity_ms) > 0 ? Number(stationInputs.max_velocity_ms) : 20.0,
        suction_equiv_length_m: Number(stationInputs.suction_equiv_length_m) > 0 ? Number(stationInputs.suction_equiv_length_m) : 120.0,
        discharge_equiv_length_m: Number(stationInputs.discharge_equiv_length_m) > 0 ? Number(stationInputs.discharge_equiv_length_m) : 150.0,
        cooler_max_outlet_temp_c:
          stationInputs.cooler_max_outlet_temp_c !== "" && Number.isFinite(Number(stationInputs.cooler_max_outlet_temp_c))
            ? Number(stationInputs.cooler_max_outlet_temp_c)
            : 45.0,
        psv_overpressure_pct: stationInputs.psv_overpressure_pct,
        psv_valve_type: stationInputs.psv_valve_type,
        psv_count: stationInputs.psv_count,
        psv_duty_count: stationInputs.psv_duty_count,
        esd_count: stationInputs.esd_count,
        esd_duty_count: stationInputs.esd_duty_count,
        esd_allowable_dp_bar: stationInputs.esd_allowable_dp_bar,
        esd_valve_type: stationInputs.esd_valve_type,
        bdv_depressurization_time_min: stationInputs.bdv_depressurization_time_min,
        esd_hp_volume_m3: Number(stationInputs.esd_hp_volume_m3) > 0 ? Number(stationInputs.esd_hp_volume_m3) : 50.0,
        esd_lp_volume_m3: Number(stationInputs.esd_lp_volume_m3) > 0 ? Number(stationInputs.esd_lp_volume_m3) : 40.0,
        ambient_temp: proj.inputs?.ambient_temp ?? 15.0,
        ambient_pressure: proj.inputs?.ambient_pressure ?? 101.325,
        altitude: proj.inputs?.altitude ?? 0,
      };
      if (stationInputs.cooler_air_temp_c !== "" && stationInputs.cooler_air_temp_c != null && Number.isFinite(Number(stationInputs.cooler_air_temp_c))) {
        mergedInputs.cooler_air_temp_c = Number(stationInputs.cooler_air_temp_c);
      } else {
        delete mergedInputs.cooler_air_temp_c;
      }
      if (stationInputs.psv_back_pressure_bar !== "" && stationInputs.psv_back_pressure_bar != null && Number.isFinite(Number(stationInputs.psv_back_pressure_bar))) {
        mergedInputs.psv_back_pressure_bar = Number(stationInputs.psv_back_pressure_bar);
      } else {
        delete mergedInputs.psv_back_pressure_bar;
      }
      if (stationInputs.psv_set_pressure_bar !== "" && stationInputs.psv_set_pressure_bar != null) {
        mergedInputs.psv_set_pressure_bar = Number(stationInputs.psv_set_pressure_bar);
      }
      if (stationInputs.comp_op_count > 0) mergedInputs.comp_op_count = stationInputs.comp_op_count;
      else delete mergedInputs.comp_op_count;

      if (stationInputs.cyclone_op_count > 0) mergedInputs.cyclone_op_count = stationInputs.cyclone_op_count;
      else delete mergedInputs.cyclone_op_count;

      if (stationInputs.filter_op_count > 0) mergedInputs.filter_op_count = stationInputs.filter_op_count;
      else delete mergedInputs.filter_op_count;

      if (stationInputs.cooler_bays_count > 0) mergedInputs.cooler_bays_count = stationInputs.cooler_bays_count;
      else delete mergedInputs.cooler_bays_count;

      if (stationInputs.cyclone_inlet_pipe_size) mergedInputs.cyclone_inlet_pipe_size = stationInputs.cyclone_inlet_pipe_size;
      else delete mergedInputs.cyclone_inlet_pipe_size;

      if (stationInputs.cyclone_outlet_pipe_size) mergedInputs.cyclone_outlet_pipe_size = stationInputs.cyclone_outlet_pipe_size;
      else delete mergedInputs.cyclone_outlet_pipe_size;

      if (stationInputs.filter_inlet_pipe_size) mergedInputs.filter_inlet_pipe_size = stationInputs.filter_inlet_pipe_size;
      else delete mergedInputs.filter_inlet_pipe_size;

      if (stationInputs.filter_outlet_pipe_size) mergedInputs.filter_outlet_pipe_size = stationInputs.filter_outlet_pipe_size;
      else delete mergedInputs.filter_outlet_pipe_size;

      stationData = await api.post("/api/v1/calculations/station", {
        inputs: mergedInputs,
        design_results: proj.results,
      });
      const cachedAirCooler = projectStore.getState().modules?.air_cooler?.results;
      if (cachedAirCooler && stationData?.equipment_sizing?.air_coolers) {
        stationData.equipment_sizing.air_coolers.detailed_design = cachedAirCooler;
      }
      setStationData(stationData);
      didUpdateData = true;
    } catch (err) {
      console.error("Station data fetch error:", err);
      showToast(t("toast_station_fetch_err", uiStore.getState().lang) + err.message, "danger");
    } finally {
      isLoading = false;
      setStationBusyState(false);
      if (didUpdateData || !stationData) {
        render();
      }
    }
  }

  function triggerLiveUpdateDebounced() {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      fetchStationData();
    }, 380);
  }

  let lastResultsRef = projectStore.getState().results;
  let lastThermoSig = JSON.stringify({
    gas_comp: projState?.inputs?.gas_comp,
    eos_model: projState?.inputs?.eos_model,
    calc_method: projState?.inputs?.calc_method,
    poly_eff: projState?.inputs?.poly_eff,
  });
  let lastProcessSig = stationProcessSignature(projState?.inputs || {});
  let lastDesignFlowUnit = projectFlowUnit;
  let lastDesignPinUnit = projectPinUnit;
  let lastDesignPoutUnit = projectPoutUnit;

  function syncStationInputsFromDesign(sourceInputs = projectStore.getState()?.inputs) {
    const inp = sourceInputs || {};
    lastProcessSig = stationProcessSignature(inp);
    const rawF = Number(inp.flow ?? inp.mass_flow ?? 0);
    const fKgs = Math.round(toKgs(rawF, inp.flow_unit || "kg/s", inp.gas_comp) * 1e6) / 1e6;
    const pin = Math.round(convertPressureToBarA(inp.p_in || 0, inp.p_in_unit || "bar(a)") * 10000) / 10000;
    const pout = Math.round(convertPressureToBarA(inp.p_out || 0, inp.p_out_unit || "bar(a)") * 10000) / 10000;
    const tin = Math.round(convertTempToC(inp.t_in ?? 25.0, inp.t_in_unit || "°C") * 10) / 10;

    if (fKgs > 0) stationInputs.mass_flow = fKgs;
    if (pin > 0) stationInputs.p_in = pin;
    if (pout > 0) stationInputs.p_out = pout;
    if (Number.isFinite(tin)) stationInputs.t_in = tin;

    // Follow design unit changes, but do not overwrite a local unit choice
    // when only design values change.
    const flowUnit = String(inp.flow_unit || "kg/s");
    const pinUnit = String(inp.p_in_unit || "bar(a)");
    const poutUnit = String(inp.p_out_unit || "bar(a)");
    if (flowUnit !== lastDesignFlowUnit) {
      lastDesignFlowUnit = flowUnit;
      if (STATION_FLOW_UNITS.includes(flowUnit)) stationInputs.mass_flow_unit = flowUnit;
    }
    if (pinUnit !== lastDesignPinUnit) {
      lastDesignPinUnit = pinUnit;
      if (STATION_PRESSURE_UNITS.includes(pinUnit)) stationInputs.p_in_unit = pinUnit;
    }
    if (poutUnit !== lastDesignPoutUnit) {
      lastDesignPoutUnit = poutUnit;
      if (STATION_PRESSURE_UNITS.includes(poutUnit)) {
        stationInputs.p_out_unit = poutUnit === "bar(a)" ? "bar(g)" : poutUnit;
      }
    }

    const nUnits = Number(inp.num_units || 0);
    if (nUnits > 0) stationInputs.comp_op_count = nUnits;
  }

  const unsubscribeStore = projectStore.subscribe(() => {
    const s = projectStore.getState();
    if (s?.inputs && !isLoading) {
      let changed = false;

      // Sync from design inputs only when the process data itself changed.
      // Station-local overrides must survive stationData/module/store updates.
      const nextProcessSig = stationProcessSignature(s.inputs);
      if (nextProcessSig !== lastProcessSig) {
        syncStationInputsFromDesign(s.inputs);
        changed = true;
      }

      const nextSig = JSON.stringify({
        gas_comp: s.inputs.gas_comp,
        eos_model: s.inputs.eos_model,
        calc_method: s.inputs.calc_method,
        poly_eff: s.inputs.poly_eff,
      });
      if (nextSig !== lastThermoSig) {
        lastThermoSig = nextSig;
        changed = true;
      }
      if (s.results !== lastResultsRef) {
        lastResultsRef = s.results;
        changed = true;
      }
      if (changed) triggerLiveUpdateDebounced();
    }
  });

  let currentLang = uiStore.getState().lang || "tr";
  const unsubscribeUi = uiStore.subscribe((ui) => {
    const nextLang = ui?.lang || "tr";
    if (nextLang !== currentLang) {
      currentLang = nextLang;
      render();
    }
  });

  function clearEquipmentSelection() {
    selectedEquip = null;
    highlightSvgEquipment(null);
    active3dInstance?.clearSelection?.();
    updateInspectorDrawer();
  }

  function updateInspectorDrawer() {
    const inspMount = container.querySelector("#station-inspector-mount");
    if (!inspMount) return;
    if (!selectedEquip || !stationData) {
      inspMount.innerHTML = "";
      return;
    }
    const { equipment_sizing: eq, station_summary: sm } = stationData;
    const gasComp = projectStore.getState().inputs?.gas_comp;
    const lang = uiStore.getState().lang || "tr";
    inspMount.innerHTML = renderInspectorDrawer(selectedEquip, eq, sm, gasComp, viewMode, lang);
    inspMount.querySelector("#btn-close-inspector")?.addEventListener("click", clearEquipmentSelection);
    inspMount.querySelector("#btn-detailed-air-cooler")?.addEventListener("click", async (event) => {
      const btn = event.currentTarget;
      const detail = inspMount.querySelector("#air-cooler-detail");
      const originalText = btn.textContent;
      btn.disabled = true;
      btn.textContent = t("btn_calculating", uiStore.getState().lang);
      if (detail) detail.innerHTML = `<div style="font-size:11px;color:var(--color-text-secondary);">API 661 detaylı tasarım çalışıyor...</div>`;
      try {
        const inputs = projectStore.getState().inputs;
        const dischargeNode = (stationData.nodes || []).find(n => n.id === "N05_COMPRESSOR_DISCHARGE") || stationData.nodes?.[4] || {};
        const eosLower = String(inputs.eos_model || "pr").toLowerCase();
        const acEos = eosLower === "srk" ? "SRK" : (eosLower === "coolprop" || eosLower === "gerg2008" ? "HEOS" : "PR");
        const acObj = stationData.equipment_sizing?.air_coolers || {};
        const airInC = Number.isFinite(Number(acObj.air_inlet_temp_c))
          ? Number(acObj.air_inlet_temp_c)
          : Number(inputs.ambient_temp ?? 15.0);
        const airOutC = Number.isFinite(Number(acObj.air_outlet_temp_c))
          ? Number(acObj.air_outlet_temp_c)
          : airInC + 15.0;
        const payload = {
          composition: inputs.gas_comp,
          eos: acEos,
          mass_flow_kgs: stationInputs.mass_flow,
          p_in_bar: stationInputs.p_out,
          p_out_bar: Math.max(1.0, stationInputs.p_out - (acObj.pressure_drop_bar || 0.4)),
          t_in_c: acObj.inlet_temp_c ?? dischargeNode.temp_c ?? 80.0,
          t_out_c: acObj.outlet_temp_c ?? 45.0,
          air_in_c: airInC,
          air_out_c: airOutC,
          auto_size: true,
        };
        const res = await api.post("/api/v1/modules/air_cooler/calculate", { payload });
        setModuleResult("air_cooler", res);
        if (stationData?.equipment_sizing?.air_coolers) {
          stationData.equipment_sizing.air_coolers.detailed_design = res.results || null;
          setStationData(stationData);
          mount3dView();
        }
        const r = res.results || {};
        if (detail) {
          detail.innerHTML = `
            <table class="kasp-table" style="font-size:10px;">
              <tr><td>Isıl Yük</td><td>${Number(r.heat_duty_kw || 0).toFixed(0)} kW</td></tr>
              <tr><td>Gerekli / Gerçek Alan</td><td>${Number(r.required_area_m2 || 0).toFixed(1)} / ${Number(r.actual_area_m2 || 0).toFixed(1)} m²</td></tr>
              <tr><td>Overdesign</td><td>%${Number(r.overdesign_pct || 0).toFixed(1)}</td></tr>
              <tr><td>Gaz ΔP</td><td>${Number(r.gas_pressure_drop_bar || 0).toFixed(3)} bar</td></tr>
              <tr><td>Fan Gücü</td><td>${Number(r.fan_power_kw || 0).toFixed(1)} kW</td></tr>
              <tr><td>Fan Uç Hızı</td><td>${Number(r.fan_tip_speed_ms || 0).toFixed(1)} m/s</td></tr>
              <tr><td>Geometri</td><td>${escapeHtml(r.geometry?.tube_rows || '-')} sıra × ${escapeHtml(r.geometry?.tubes_per_row || '-')} tüp</td></tr>
            </table>
            ${(res.warnings || []).length ? `<div role="alert" style="font-size:10px;color:#f59e0b;margin-top:4px;">${res.warnings.map(w => escapeHtml(w)).join("<br>")}</div>` : ''}
          `;
        }
      } catch (err) {
        if (detail) detail.innerHTML = `<div role="alert" style="font-size:11px;color:#ef4444;">Hata: ${escapeHtml(err.message)}</div>`;
      } finally {
        btn.disabled = false;
        btn.textContent = originalText;
      }
    });
  }

  function highlightSvgEquipment(key) {
    container.querySelectorAll(".station-equip-group").forEach((el) => {
      if (key && el.getAttribute("data-equip-key") === key) {
        el.classList.add("active-selected");
      } else {
        el.classList.remove("active-selected");
      }
    });
  }

  function updatePfdModal() {
    const modalMount = container.querySelector("#station-pfd-modal-mount");
    if (!modalMount) return;
    if (!isPfdModalOpen) {
      modalMount.innerHTML = "";
      return;
    }
    const lang = uiStore.getState().lang || "tr";
    modalMount.innerHTML = renderBotasPfdModal(lang);
    const closePfd = () => {
      isPfdModalOpen = false;
      updatePfdModal();
    };
    modalMount.querySelector("#btn-close-pfd-modal")?.addEventListener("click", closePfd);
    modalMount.querySelector("#btn-footer-close-pfd-modal")?.addEventListener("click", closePfd);
    modalMount.querySelector("#botas-pfd-backdrop")?.addEventListener("click", (e) => {
      if (e.target.id === "botas-pfd-backdrop") closePfd();
    });
  }

  function updatePrCardSubline() {
    const sublineEl = container.querySelector("#station-pr-subline");
    if (!sublineEl || !stationData?.station_summary) return;
    const sm = stationData.station_summary;
    sublineEl.innerHTML = `${stationPressureDisplay(sm.suction_pressure_bar, stationInputs.p_in_unit)} ${escapeHtml(stationInputs.p_in_unit)} → ${stationPressureDisplay(sm.discharge_pressure_bar, stationInputs.p_out_unit)} ${escapeHtml(stationInputs.p_out_unit)} • T_in: ${stationInputs.t_in.toFixed(1)}°C`;
  }

  function bindLiveParamsControls() {
    container.querySelector("#btn-toggle-params-panel")?.addEventListener("click", () => {
      isParamsPanelOpen = !isParamsPanelOpen;
      updateLiveParamsMount();
    });

    const activeGas = projectStore.getState().inputs?.gas_comp;

    const flowSlider = container.querySelector("#slider-param-flow");
    const flowInput = container.querySelector("#input-param-flow");
    flowSlider?.addEventListener("input", (e) => {
      const kgs = Number(e.target.value);
      stationInputs.mass_flow = kgs;
      if (flowInput) {
        flowInput.value = roundDisplay(stationFlowDisplay(kgs, stationInputs.mass_flow_unit, activeGas));
      }
      triggerLiveUpdateDebounced();
    });
    flowInput?.addEventListener("change", (e) => {
      const kgs = stationFlowToKgs(e.target.value, stationInputs.mass_flow_unit, activeGas);
      if (!Number.isFinite(kgs) || kgs <= 0) return;
      stationInputs.mass_flow = Math.round(kgs * 1e6) / 1e6;
      if (flowSlider) {
        flowSlider.value = Math.min(Number(flowSlider.max), Math.max(Number(flowSlider.min), stationInputs.mass_flow));
      }
      triggerLiveUpdateDebounced();
    });

    container.querySelector("#select-param-flow-unit")?.addEventListener("change", (e) => {
      const typed = parseFloat(flowInput?.value);
      const oldUnit = stationInputs.mass_flow_unit || "kg/s";
      const shown = roundDisplay(stationFlowDisplay(stationInputs.mass_flow, oldUnit, activeGas));
      if (Number.isFinite(typed) && typed > 0 && Math.abs(typed - Number(shown)) > 1e-6) {
        const kgs = stationFlowToKgs(typed, oldUnit, activeGas);
        if (Number.isFinite(kgs) && kgs > 0) stationInputs.mass_flow = Math.round(kgs * 1e6) / 1e6;
      }
      stationInputs.mass_flow_unit = e.target.value;
      updateLiveParamsMount();
    });

    const pinSlider = container.querySelector("#slider-param-pin");
    const pinInput = container.querySelector("#input-param-pin");
    pinSlider?.addEventListener("input", (e) => {
      const barA = Number(e.target.value);
      stationInputs.p_in = barA;
      if (pinInput) pinInput.value = stationPressureDisplay(barA, stationInputs.p_in_unit);
      if (stationInputs.p_out <= barA) {
        stationInputs.p_out = Math.round(barA * 1.5);
        const poutInput = container.querySelector("#input-param-pout");
        const poutSlider = container.querySelector("#slider-param-pout");
        if (poutInput) poutInput.value = stationPressureDisplay(stationInputs.p_out, stationInputs.p_out_unit);
        if (poutSlider) poutSlider.value = stationInputs.p_out;
      }
      triggerLiveUpdateDebounced();
    });
    pinInput?.addEventListener("change", (e) => {
      const barA = stationPressureToBarA(e.target.value, stationInputs.p_in_unit);
      if (!Number.isFinite(barA) || barA <= 0) return;
      stationInputs.p_in = Math.round(barA * 10000) / 10000;
      if (stationInputs.p_out <= stationInputs.p_in) {
        stationInputs.p_out = Math.round(stationInputs.p_in * 1.5 * 10000) / 10000;
        const poutInput = container.querySelector("#input-param-pout");
        const poutSlider = container.querySelector("#slider-param-pout");
        if (poutInput) poutInput.value = stationPressureDisplay(stationInputs.p_out, stationInputs.p_out_unit);
        if (poutSlider) poutSlider.value = stationInputs.p_out;
      }
      if (pinSlider) {
        pinSlider.value = Math.min(Number(pinSlider.max), Math.max(Number(pinSlider.min), stationInputs.p_in));
      }
      triggerLiveUpdateDebounced();
    });

    container.querySelector("#select-param-pin-unit")?.addEventListener("change", (e) => {
      const typed = parseFloat(pinInput?.value);
      const oldUnit = stationInputs.p_in_unit || "bar(a)";
      const shown = Number(stationPressureDisplay(stationInputs.p_in, oldUnit));
      if (Number.isFinite(typed) && typed > 0 && Math.abs(typed - shown) > 1e-6) {
        const barA = stationPressureToBarA(typed, oldUnit);
        if (Number.isFinite(barA) && barA > 0) stationInputs.p_in = Math.round(barA * 10000) / 10000;
      }
      stationInputs.p_in_unit = e.target.value;
      updateLiveParamsMount();
      updatePrCardSubline();
    });

    const poutSlider = container.querySelector("#slider-param-pout");
    const poutInput = container.querySelector("#input-param-pout");
    poutSlider?.addEventListener("input", (e) => {
      const barA = Number(e.target.value);
      stationInputs.p_out = barA;
      if (poutInput) poutInput.value = stationPressureDisplay(barA, stationInputs.p_out_unit);
      triggerLiveUpdateDebounced();
    });
    poutInput?.addEventListener("change", (e) => {
      const barA = stationPressureToBarA(e.target.value, stationInputs.p_out_unit);
      if (!Number.isFinite(barA) || barA <= 0) return;
      stationInputs.p_out = Math.round(barA * 10000) / 10000;
      if (poutSlider) {
        poutSlider.value = Math.min(Number(poutSlider.max), Math.max(Number(poutSlider.min), stationInputs.p_out));
      }
      triggerLiveUpdateDebounced();
    });

    container.querySelector("#select-param-pout-unit")?.addEventListener("change", (e) => {
      const typed = parseFloat(poutInput?.value);
      const oldUnit = stationInputs.p_out_unit || "bar(a)";
      const shown = Number(stationPressureDisplay(stationInputs.p_out, oldUnit));
      if (Number.isFinite(typed) && typed > 0 && Math.abs(typed - shown) > 1e-6) {
        const barA = stationPressureToBarA(typed, oldUnit);
        if (Number.isFinite(barA) && barA > 0) stationInputs.p_out = Math.round(barA * 10000) / 10000;
      }
      stationInputs.p_out_unit = e.target.value;
      updateLiveParamsMount();
      updatePrCardSubline();
    });

    container.querySelector("#select-param-comps")?.addEventListener("change", (e) => {
      stationInputs.comp_op_count = parseInt(e.target.value, 10);
      fetchStationData();
    });

    container.querySelector("#select-param-cyclones")?.addEventListener("change", (e) => {
      stationInputs.cyclone_op_count = parseInt(e.target.value, 10);
      fetchStationData();
    });

    container.querySelector("#select-param-filters")?.addEventListener("change", (e) => {
      stationInputs.filter_op_count = parseInt(e.target.value, 10);
      fetchStationData();
    });

    container.querySelector("#select-param-coolers")?.addEventListener("change", (e) => {
      stationInputs.cooler_bays_count = parseInt(e.target.value, 10);
      fetchStationData();
    });

    container.querySelector("#select-param-material")?.addEventListener("change", (e) => {
      stationInputs.pipe_material = e.target.value;
      fetchStationData();
    });

    container.querySelector("#select-param-standard")?.addEventListener("change", (e) => {
      stationInputs.pipe_standard = e.target.value;
      fetchStationData();
    });

    container.querySelector("#select-param-psl")?.addEventListener("change", (e) => {
      stationInputs.psl_level = e.target.value;
      fetchStationData();
    });

    container.querySelector("#input-param-max-vel")?.addEventListener("change", (e) => {
      const parsed = parseFloat(e.target.value);
      stationInputs.max_velocity_ms = Number.isFinite(parsed) && parsed > 0 ? Math.max(2.0, Math.min(60.0, parsed)) : 20.0;
      triggerLiveUpdateDebounced();
    });

    container.querySelector("#input-param-suct-len")?.addEventListener("change", (e) => {
      const parsed = parseFloat(e.target.value);
      stationInputs.suction_equiv_length_m = Number.isFinite(parsed) && parsed > 0 ? Math.max(1.0, Math.min(50000.0, parsed)) : 120.0;
      triggerLiveUpdateDebounced();
    });

    container.querySelector("#input-param-disch-len")?.addEventListener("change", (e) => {
      const parsed = parseFloat(e.target.value);
      stationInputs.discharge_equiv_length_m = Number.isFinite(parsed) && parsed > 0 ? Math.max(1.0, Math.min(50000.0, parsed)) : 150.0;
      triggerLiveUpdateDebounced();
    });

    container.querySelector("#select-param-cyc-in")?.addEventListener("change", (e) => {
      stationInputs.cyclone_inlet_pipe_size = e.target.value;
      fetchStationData();
    });

    container.querySelector("#select-param-cyc-out")?.addEventListener("change", (e) => {
      stationInputs.cyclone_outlet_pipe_size = e.target.value;
      fetchStationData();
    });

    container.querySelector("#select-param-flt-in")?.addEventListener("change", (e) => {
      stationInputs.filter_inlet_pipe_size = e.target.value;
      fetchStationData();
    });

    container.querySelector("#select-param-flt-out")?.addEventListener("change", (e) => {
      stationInputs.filter_outlet_pipe_size = e.target.value;
      fetchStationData();
    });

    container.querySelector("#input-param-design-f")?.addEventListener("change", (e) => {
      const parsed = parseFloat(e.target.value);
      if (Number.isFinite(parsed) && parsed >= 0.2 && parsed <= 0.8) {
        stationInputs.design_factor_F = parsed;
        triggerLiveUpdateDebounced();
      }
    });

    container.querySelector("#input-param-cooler-air")?.addEventListener("change", (e) => {
      const raw = e.target.value.trim();
      stationInputs.cooler_air_temp_c = raw === "" ? "" : Number(raw);
      triggerLiveUpdateDebounced();
    });

    container.querySelector("#input-param-cooler-max-out")?.addEventListener("change", (e) => {
      const parsed = parseFloat(e.target.value);
      stationInputs.cooler_max_outlet_temp_c = Number.isFinite(parsed) ? parsed : 45.0;
      triggerLiveUpdateDebounced();
    });

    container.querySelector("#input-param-psv-set")?.addEventListener("change", (e) => {
      const raw = e.target.value.trim();
      stationInputs.psv_set_pressure_bar = raw === "" ? "" : Number(raw);
      triggerLiveUpdateDebounced();
    });
    container.querySelector("#input-param-psv-overpressure")?.addEventListener("change", (e) => {
      stationInputs.psv_overpressure_pct = Number(e.target.value);
      triggerLiveUpdateDebounced();
    });
    container.querySelector("#input-param-psv-backpressure")?.addEventListener("change", (e) => {
      const raw = e.target.value.trim();
      stationInputs.psv_back_pressure_bar = raw === "" ? "" : Number(raw);
      triggerLiveUpdateDebounced();
    });
    container.querySelector("#select-param-psv-type")?.addEventListener("change", (e) => {
      stationInputs.psv_valve_type = e.target.value;
      triggerLiveUpdateDebounced();
    });
    container.querySelector("#select-param-psv-count")?.addEventListener("change", (e) => {
      stationInputs.psv_count = parseInt(e.target.value, 10);
      triggerLiveUpdateDebounced();
    });
    container.querySelector("#select-param-psv-duty")?.addEventListener("change", (e) => {
      stationInputs.psv_duty_count = parseInt(e.target.value, 10);
      triggerLiveUpdateDebounced();
    });
    container.querySelector("#select-param-esd-count")?.addEventListener("change", (e) => {
      stationInputs.esd_count = parseInt(e.target.value, 10);
      triggerLiveUpdateDebounced();
    });
    container.querySelector("#select-param-esd-duty")?.addEventListener("change", (e) => {
      stationInputs.esd_duty_count = parseInt(e.target.value, 10);
      triggerLiveUpdateDebounced();
    });
    container.querySelector("#input-param-esd-dp")?.addEventListener("change", (e) => {
      stationInputs.esd_allowable_dp_bar = Number(e.target.value);
      triggerLiveUpdateDebounced();
    });
    container.querySelector("#select-param-esd-type")?.addEventListener("change", (e) => {
      stationInputs.esd_valve_type = e.target.value;
      triggerLiveUpdateDebounced();
    });
    container.querySelector("#input-param-esd-bdv-time")?.addEventListener("change", (e) => {
      stationInputs.bdv_depressurization_time_min = Number(e.target.value);
      triggerLiveUpdateDebounced();
    });
    container.querySelector("#input-param-esd-hp-vol")?.addEventListener("change", (e) => {
      const parsed = parseFloat(e.target.value);
      stationInputs.esd_hp_volume_m3 = Number.isFinite(parsed) && parsed > 0 ? parsed : 50.0;
      triggerLiveUpdateDebounced();
    });
    container.querySelector("#input-param-esd-lp-vol")?.addEventListener("change", (e) => {
      const parsed = parseFloat(e.target.value);
      stationInputs.esd_lp_volume_m3 = Number.isFinite(parsed) && parsed > 0 ? parsed : 40.0;
      triggerLiveUpdateDebounced();
    });

    container.querySelector("#btn-apply-station-params")?.addEventListener("click", () => {
      fetchStationData();
    });

    container.querySelector("#btn-reset-station-params")?.addEventListener("click", () => {
      const cur = projectStore.getState().inputs || {};
      stationInputs = {
        mass_flow: 120.0,
        mass_flow_unit: stationInputs.mass_flow_unit || "kg/s",
        p_in: 45.0,
        p_in_unit: stationInputs.p_in_unit || "bar(a)",
        p_out: 75.0,
        p_out_unit: stationInputs.p_out_unit || "bar(g)",
        t_in: Math.round(convertTempToC(cur.t_in ?? 25.0, cur.t_in_unit || "°C") * 10) / 10,
        comp_op_count: 0,
        cyclone_op_count: 0,
        filter_op_count: 0,
        cooler_bays_count: 0,
        pipe_material: "API 5L X70",
        design_factor_F: 0.50,
        pipe_standard: "BOTAŞ",
        psl_level: "PSL2",
        max_velocity_ms: 20.0,
        suction_equiv_length_m: 120.0,
        discharge_equiv_length_m: 150.0,
        cyclone_inlet_pipe_size: "",
        cyclone_outlet_pipe_size: "",
        filter_inlet_pipe_size: "",
        filter_outlet_pipe_size: "",
        cooler_air_temp_c: "",
        cooler_max_outlet_temp_c: 45.0,
        psv_set_pressure_bar: "",
        psv_overpressure_pct: 10,
        psv_back_pressure_bar: "",
        psv_valve_type: "conventional",
        psv_count: 2,
        psv_duty_count: 1,
        esd_count: 2,
        esd_duty_count: 1,
        esd_allowable_dp_bar: 0.5,
        esd_valve_type: "full_bore_ball",
        bdv_depressurization_time_min: 15,
        esd_hp_volume_m3: 50.0,
        esd_lp_volume_m3: 40.0,
      };
      fetchStationData();
    });
  }

  function updateLiveParamsMount() {
    const paramsMount = container.querySelector("#station-params-mount");
    if (!paramsMount) return;
    const projInputs = projectStore.getState().inputs || {};
    const lang = uiStore.getState().lang || "tr";
    paramsMount.innerHTML = renderLiveParamsBar(stationInputs, isParamsPanelOpen, projInputs.gas_comp, lang, stationData, projInputs);
    bindLiveParamsControls();
    bindProvenanceControls();
  }

  function bindProvenanceControls() {
    const provMount = container.querySelector("#station-provenance-mount");
    if (!provMount) return;
    provMount.querySelectorAll("[data-prov-filter]").forEach((btn) => {
      btn.addEventListener("click", () => {
        provenanceSourceFilter = btn.getAttribute("data-prov-filter") || "all";
        updateProvenanceMount();
      });
    });
    const searchInput = provMount.querySelector("#input-prov-search");
    searchInput?.addEventListener("input", (e) => {
      provenanceSearchQuery = e.target.value || "";
      updateProvenanceMount(true);
    });
  }

  function updateProvenanceMount(preserveFocus = false) {
    const provMount = container.querySelector("#station-provenance-mount");
    if (!provMount || !stationData) return;
    const lang = uiStore.getState().lang || "tr";
    const selStart = preserveFocus ? provMount.querySelector("#input-prov-search")?.selectionStart : null;
    provMount.innerHTML = renderParameterProvenancePanel(
      stationData.parameter_sources,
      provenanceSourceFilter,
      provenanceSearchQuery,
      lang
    );
    bindProvenanceControls();
    if (preserveFocus) {
      const nextInput = provMount.querySelector("#input-prov-search");
      if (nextInput) {
        nextInput.focus();
        if (selStart != null) nextInput.setSelectionRange(selStart, selStart);
      }
    }
  }

  function mount3dView() {
    const mount = container.querySelector("#station-3d-mount");
    if (!mount || !stationData) {
      destroy3d();
      return;
    }
    const previousState = last3dState;
    destroy3d();
    try {
      active3dInstance = createStation3dView(
        mount,
        stationData,
        (equipKey) => {
          selectedEquip = equipKey;
          highlightSvgEquipment(equipKey);
          updateInspectorDrawer();
        },
        {
          initialState: previousState || last3dState,
          onUpdateSafetyInputs: (updates) => {
            Object.assign(stationInputs, updates || {});
            fetchStationData();
          },
        }
      );
    } catch (err) {
      console.error("3D sahne oluşturulamadı:", err);
      active3dInstance = null;
      mount.innerHTML = `
        <div role="alert" style="height: 100%; min-height: 320px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 10px; padding: 24px; text-align: center; background: var(--color-surface); color: var(--color-text);">
          <div style="font-size: 32px;">⚠️</div>
          <div style="font-weight: 700;">3D görünüm başlatılamadı</div>
          <div style="font-size: 12px; color: var(--color-text-secondary); max-width: 420px;">
            Tarayıcınızda WebGL kullanılamıyor olabilir (donanım hızlandırma kapalı veya GPU sürücü hatası).
            2D P&amp;ID akış şeması tüm ekipman verisiyle çalışmaya devam eder.
          </div>
          <button type="button" class="btn btn-sm btn-primary" id="btn-3d-fallback-2d">📐 2D P&amp;ID Görünümüne Geç</button>
        </div>`;
      mount.querySelector("#btn-3d-fallback-2d")?.addEventListener("click", () => {
        viewMode = "2d";
        render();
      });
    }
    if (selectedEquip && active3dInstance) {
      active3dInstance.selectEquipment(selectedEquip);
      highlightSvgEquipment(selectedEquip);
    }
  }

  function render() {
    abort2dControls();
    destroy3d();
    const lang = uiStore.getState().lang || "tr";

    if (isLoading && !stationData) {
      container.innerHTML = `
        <div style="flex: 1; display: flex; align-items: center; justify-content: center; gap: 10px; color: var(--color-text-secondary); min-height: 400px;">
          ${icon("refreshCw", 24, "station-fan-blade")}
          <span>${escapeHtml(t("station_loading_calc", lang))}</span>
        </div>
      `;
      return;
    }

    if (!stationData) {
      container.innerHTML = `
        <div style="flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 16px; min-height: 400px;">
          <p style="color: var(--color-text-secondary);">${escapeHtml(t("station_loading_init", lang))}</p>
          <button id="btn-refresh-station" class="btn btn-primary">
            ${icon("play", 14)}
            <span>${escapeHtml(t("station_btn_start", lang))}</span>
          </button>
        </div>
      `;
      container.querySelector("#btn-refresh-station")?.addEventListener("click", fetchStationData);
      return;
    }

    const { station_summary: sm, equipment_sizing: eq, nodes } = stationData;
    const activeGasComp = projectStore.getState().inputs?.gas_comp;
    const stationWarnings = collectStationWarnings(stationData);
    const currentDesignSig = stationProcessSignature(projectStore.getState().inputs || {});
    const isStationStale = !!lastProcessSig && lastProcessSig !== currentDesignSig;

    container.innerHTML = `
      <div style="flex: 1; padding: 16px 20px; overflow-y: auto; display: flex; flex-direction: column; gap: 14px;">
        ${
          isStationStale
            ? `<div id="station-stale-banner" role="status" style="display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 8px 12px; border-radius: var(--radius-md); background: rgba(245, 158, 11, 0.12); border: 1px solid rgba(245, 158, 11, 0.35); color: #d97706; font-size: 12px; font-weight: 600;">
                <span>${escapeHtml(t("station_stale_msg", lang))}</span>
                <button type="button" id="btn-station-sync-recalc" class="btn btn-sm btn-primary">${escapeHtml(t("station_stale_btn", lang))}</button>
              </div>`
            : ""
        }
        <!-- Top Summary Cards -->
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 10px;">
          <div class="card" style="padding: 10px 14px;">
            <div style="font-size: 11px; color: var(--color-text-secondary); text-transform: uppercase; font-weight: 600;">
              ${escapeHtml(t("station_card_flow", lang))}
            </div>
            <div style="font-size: 18px; font-weight: 700; color: var(--color-primary); margin-top: 4px;">
              ${escapeHtml(sm.total_mass_flow_kgs)} <span style="font-size: 12px; font-weight: 400;">kg/s</span>
            </div>
            <div style="font-size: 11px; color: var(--color-text-secondary); margin-top: 2px;">
              ${escapeHtml(sm.volumetric_flow_mmscmd)} MMSCMD • MW: ${escapeHtml(sm.gas_mw)} g/mol
            </div>
          </div>

          <div class="card" style="padding: 10px 14px;">
            <div style="font-size: 11px; color: var(--color-text-secondary); text-transform: uppercase; font-weight: 600;">
              ${escapeHtml(t("station_card_pr", lang))}
            </div>
            <div style="font-size: 18px; font-weight: 700; color: #0ea5e9; margin-top: 4px;">
              ${escapeHtml(sm.pressure_ratio)} : 1
            </div>
            <div id="station-pr-subline" style="font-size: 11px; color: var(--color-text-secondary); margin-top: 2px;">
              ${stationPressureDisplay(sm.suction_pressure_bar, stationInputs.p_in_unit)} ${escapeHtml(stationInputs.p_in_unit)} → ${stationPressureDisplay(sm.discharge_pressure_bar, stationInputs.p_out_unit)} ${escapeHtml(stationInputs.p_out_unit)} • T_in: ${stationInputs.t_in.toFixed(1)}°C
            </div>
          </div>

          <div class="card" style="padding: 10px 14px;">
            <div style="font-size: 11px; color: var(--color-text-secondary); text-transform: uppercase; font-weight: 600;">
              ${escapeHtml(t("station_card_power", lang))}
            </div>
            <div style="font-size: 18px; font-weight: 700; color: #f59e0b; margin-top: 4px;">
              ${escapeHtml(sm.total_power_mw)} <span style="font-size: 12px; font-weight: 400;">MW</span>
            </div>
            <div style="font-size: 11px; color: var(--color-text-secondary); margin-top: 2px;">
              ${(sm.total_power_kw * 1.34102 / 1000).toFixed(1)}k HP • ${escapeHtml(eq.turbo_compressors.configuration)}
            </div>
          </div>

          <div class="card" style="padding: 10px 14px;">
            <div style="font-size: 11px; color: var(--color-text-secondary); text-transform: uppercase; font-weight: 600;">
              ${escapeHtml(t("station_card_cooler", lang))}
            </div>
            <div style="font-size: 18px; font-weight: 700; color: #10b981; margin-top: 4px;">
              ${escapeHtml(sm.cooler_heat_duty_mw)} <span style="font-size: 12px; font-weight: 400;">MWth</span>
            </div>
            <div style="font-size: 11px; color: var(--color-text-secondary); margin-top: 2px;">
              ${escapeHtml(eq.air_coolers.bay_count)} Fin-Fan Bay • ${escapeHtml(t("station_card_outlet", lang))}: ${escapeHtml(eq.air_coolers.outlet_temp_c)}°C
            </div>
          </div>

          <div class="card" style="padding: 10px 14px; display: flex; flex-direction: column; justify-content: space-between;">
            <div>
              <div style="font-size: 11px; color: var(--color-text-secondary); text-transform: uppercase; font-weight: 600;">
                ${escapeHtml(t("station_card_dynamic", lang))}
              </div>
              <div style="font-size: 12px; font-weight: 600; color: var(--color-text); margin-top: 4px;">
                ${escapeHtml(eq.cyclones.operating_count)}+1 ${escapeHtml(t("station_unit_cyclones", lang))} • ${escapeHtml(eq.cartridge_filters.operating_count)}+1 ${escapeHtml(t("station_unit_filters", lang))}
              </div>
              <div style="font-size: 11px; color: var(--color-text-secondary);">
                ${escapeHtml(eq.turbo_compressors.operating_count)}+1 ${escapeHtml(t("station_unit_trains", lang))} • ${escapeHtml(eq.compressor_building.area_m2)} m² ${escapeHtml(t("station_unit_building", lang))}
              </div>
            </div>
            <div style="display: flex; gap: 6px; margin-top: 6px;">
              <button id="btn-recalc-station" class="btn btn-sm btn-secondary" style="flex: 1; padding: 2px 6px; font-size: 11px;" title="${escapeHtml(t("station_btn_recalc_title", lang))}">
                ${icon("refreshCw", 12)}
                <span>${escapeHtml(t("station_btn_recalc", lang))}</span>
              </button>
              <button id="btn-view-botas-pfd" class="btn btn-sm btn-primary" style="flex: 1.4; padding: 2px 6px; font-size: 11px;" title="${escapeHtml(t("station_btn_pfd_title", lang))}">
                ${icon("fileText", 12)}
                <span>${escapeHtml(t("station_btn_pfd", lang))}</span>
              </button>
            </div>
          </div>
        </div>

        ${
          stationWarnings.length > 0
            ? `
            <div id="station-warnings-note" role="note" style="padding: 8px 12px; border-radius: var(--radius-md); background: rgba(245, 158, 11, 0.08); border: 1px solid rgba(245, 158, 11, 0.30); color: var(--color-text); display: flex; justify-content: space-between; align-items: center; gap: 10px; flex-wrap: wrap;">
              <div style="font-size: 11.5px; font-weight: 600; color: #f59e0b;">
                ℹ️ ${escapeHtml(t("station_warnings_title", lang))} (${stationWarnings.length}) — Not: Detaylı liste sayfa sonundadır.
              </div>
              <div style="display: flex; align-items: center; gap: 8px;">
                <span class="badge badge-warning" style="font-size: 10px;">IEC 60534 / API 520 / API RP 14E</span>
                <a href="#station-warnings-banner" class="btn btn-sm btn-secondary" style="font-size: 10.5px; padding: 2px 8px; text-decoration: none;">Listeye Git ↓</a>
              </div>
            </div>
            `
            : ""
        }

        <!-- Live Station Operating Parameters & Dynamic Pipe Sizing Bar (Natural Gas Flow Calc) -->
        <div id="station-params-mount">
          ${renderLiveParamsBar(stationInputs, isParamsPanelOpen, activeGasComp, lang, stationData, projectStore.getState().inputs || {})}
        </div>

        <!-- View Mode Selector Bar & Quick Legend -->
        <div style="display: flex; justify-content: space-between; align-items: center; background: var(--color-surface); padding: 8px 14px; border-radius: var(--radius-md); border: 1px solid var(--color-border); flex-wrap: wrap; gap: 8px;">
          <div style="display: flex; gap: 6px; align-items: center;">
            <span style="font-size: 11px; font-weight: 700; color: var(--color-text-secondary); margin-right: 4px; text-transform: uppercase;">${escapeHtml(t("station_view_label", lang))}</span>
            <button id="btn-mode-3d" class="btn btn-sm ${viewMode === '3d' ? 'btn-primary' : 'btn-secondary'}" style="font-size: 12px; font-weight: 600; display: flex; align-items: center; gap: 6px;">
              <span>${escapeHtml(t("station_mode_3d", lang))}</span>
            </button>
            <button id="btn-mode-2d" class="btn btn-sm ${viewMode === '2d' ? 'btn-primary' : 'btn-secondary'}" style="font-size: 12px; font-weight: 600; display: flex; align-items: center; gap: 6px;">
              <span>${escapeHtml(t("station_mode_2d", lang))}</span>
            </button>
            <button id="btn-mode-split" class="btn btn-sm ${viewMode === 'split' ? 'btn-primary' : 'btn-secondary'}" style="font-size: 12px; font-weight: 600; display: flex; align-items: center; gap: 6px;">
              <span>${escapeHtml(t("station_mode_split", lang))}</span>
            </button>
          </div>

          <div style="display: flex; gap: 10px; align-items: center; font-size: 11px; color: var(--color-text-secondary); flex-wrap: wrap;">
            <span style="display: flex; align-items: center; gap: 4px;"><span style="display: inline-block; width: 10px; height: 3px; background: #e2d400;"></span> ${escapeHtml(t("station_leg_piping", lang))}</span>
            <span style="display: flex; align-items: center; gap: 4px;"><span style="display: inline-block; width: 10px; height: 3px; background: #00f0ff;"></span> ${escapeHtml(t("station_leg_flow", lang))}</span>
            <span style="display: flex; align-items: center; gap: 4px;"><span style="display: inline-block; width: 10px; height: 3px; background: #0077be;"></span> ${escapeHtml(t("station_leg_steel", lang))}</span>
            <span style="display: flex; align-items: center; gap: 4px;"><span style="display: inline-block; width: 10px; height: 3px; background: #8c735b;"></span> ${escapeHtml(t("station_leg_buildings", lang))}</span>
            <span style="display: flex; align-items: center; gap: 4px;"><span style="display: inline-block; width: 10px; height: 3px; background: #2b2e34;"></span> ${escapeHtml(t("station_leg_road", lang))}</span>
          </div>
        </div>

        <!-- Main Visualizer Area -->
        <div id="station-main-viewer" data-view-mode="${escapeHtml(viewMode)}" style="position: relative;">
          ${
            viewMode === "3d"
              ? `<div id="station-3d-mount" style="width: 100%; height: clamp(440px, 74vh, 780px); border-radius: var(--radius-lg); overflow: hidden; border: 1px solid var(--color-border); background: #7aa0dc;"></div>`
              : viewMode === "2d"
              ? renderStation2dViewport(stationData, lang)
              : `<div class="station-split-grid">
                   <div id="station-3d-mount" style="height: 100%; border-radius: var(--radius-lg); overflow: hidden; border: 1px solid var(--color-border); background: #7aa0dc;"></div>
                   ${renderStation2dViewport(stationData, lang)}
                 </div>`
          }

          <!-- Equipment Inspector Drawer Container -->
          <div id="station-inspector-mount">
            ${selectedEquip ? renderInspectorDrawer(selectedEquip, eq, sm, activeGasComp, viewMode, lang) : ""}
          </div>
        </div>

        <!-- 8-Nodal Telemetry Table -->
        <div class="card" style="padding: 12px;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; flex-wrap: wrap; gap: 6px;">
            <div style="font-size: 13px; font-weight: 700; display: flex; align-items: center; gap: 6px;">
              ${icon("activity", 14, "text-primary")}
              <span>${escapeHtml(t("station_nodes_title", lang))}</span>
            </div>
            <span style="font-size: 11px; color: var(--color-text-secondary);">${escapeHtml(t("station_doc_no", lang))}</span>
          </div>

          <table class="kasp-table" style="font-size: 11px;">
            <thead>
              <tr>
                <th>${escapeHtml(t("station_col_node_id", lang))}</th>
                <th>${escapeHtml(t("station_col_node_desc", lang))}</th>
                <th style="text-align: right;">${escapeHtml(t("station_col_pressure", lang))}</th>
                <th style="text-align: right;">${escapeHtml(t("station_col_temp", lang))}</th>
                <th style="text-align: right;">${escapeHtml(t("station_col_flow", lang))}</th>
                <th>${escapeHtml(t("station_col_phase", lang))}</th>
                <th>${escapeHtml(t("station_col_state", lang))}</th>
              </tr>
            </thead>
            <tbody>
              ${nodes.map(n => `
                <tr>
                  <td style="font-family: var(--font-mono); font-weight: 700; color: ${escapeHtml(n.color)};">${escapeHtml(n.id)}</td>
                  <td style="font-weight: 600;">${escapeHtml(n.name)}</td>
                  <td style="text-align: right; font-family: var(--font-mono); font-weight: 600;">${Number(n.pressure_bar || 0).toFixed(2)}</td>
                  <td style="text-align: right; font-family: var(--font-mono);">${Number(n.temp_c || 0).toFixed(1)}</td>
                  <td style="text-align: right; font-family: var(--font-mono);">${Number(n.flow_kgs || 0).toFixed(1)}</td>
                  <td><span class="badge badge-neutral" style="font-size: 10px;">${escapeHtml(n.phase)}</span></td>
                  <td style="color: var(--color-text-secondary); font-size: 11px;">${escapeHtml(n.state_desc)}</td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        </div>

        <!-- ASME B36.10M / API 5L Natural Gas Flow Calc Pipe Sizing Matrix Table -->
        ${renderPipeSizingTable(stationData.station_piping)}

        <!-- Equipment & Piping Parameter Provenance & Dynamic Coupling Audit Matrix -->
        <div id="station-provenance-mount">
          ${renderParameterProvenancePanel(stationData.parameter_sources, provenanceSourceFilter, provenanceSearchQuery, lang)}
        </div>

        ${
          stationWarnings.length > 0
            ? `
            <div id="station-warnings-banner" role="alert" aria-live="polite" style="padding: 10px 14px; border-radius: var(--radius-md); background: rgba(245, 158, 11, 0.10); border: 1px solid rgba(245, 158, 11, 0.35); color: var(--color-text);">
              <div style="display: flex; justify-content: space-between; align-items: center; gap: 8px; margin-bottom: 6px;">
                <div style="font-size: 12px; font-weight: 700; color: #f59e0b;">
                  ⚠️ ${escapeHtml(t("station_warnings_title", lang))} (${stationWarnings.length})
                </div>
                <span class="badge badge-warning" style="font-size: 10px;">IEC 60534 / API 520 / API RP 14E</span>
              </div>
              <ul style="margin: 0; padding-left: 18px; font-size: 11px; line-height: 1.45; color: var(--color-text);">
                ${stationWarnings.map(w => `<li>${escapeHtml(w)}</li>`).join("")}
              </ul>
            </div>
            `
            : ""
        }

        <!-- BOTAŞ Adapazarı PFD Lightbox Modal -->
        <div id="station-pfd-modal-mount">
          ${isPfdModalOpen ? renderBotasPfdModal(lang) : ""}
        </div>

      </div>
    `;

    container.querySelector("#btn-station-sync-recalc")?.addEventListener("click", () => {
      syncStationInputsFromDesign();
      fetchStationData();
    });

    // Mode switching handlers
    container.querySelector("#btn-mode-3d")?.addEventListener("click", () => {
      if (viewMode !== "3d") {
        viewMode = "3d";
        render();
      }
    });

    container.querySelector("#btn-mode-2d")?.addEventListener("click", () => {
      if (viewMode !== "2d") {
        viewMode = "2d";
        render();
      }
    });

    container.querySelector("#btn-mode-split")?.addEventListener("click", () => {
      if (viewMode !== "split") {
        viewMode = "split";
        render();
      }
    });

    // Mount 3D scene if applicable
    if (viewMode === "3d" || viewMode === "split") {
      mount3dView();
    }
    if (viewMode === "2d" || viewMode === "split") {
      bindStation2dControls(container, lang);
    }

    // Inspector Close & Air Cooler Detail handlers
    if (selectedEquip) {
      updateInspectorDrawer();
    }

    // Event Bindings
    container.querySelector("#btn-recalc-station")?.addEventListener("click", () => {
      fetchStationData();
    });

    bindLiveParamsControls();
    bindProvenanceControls();

    container.querySelector("#btn-view-botas-pfd")?.addEventListener("click", () => {
      isPfdModalOpen = true;
      updatePfdModal();
    });
    if (isPfdModalOpen) {
      updatePfdModal();
    }

    // Inspector & 3D Sync Click Handlers on SVG elements (for 2D / split view)
    container.querySelectorAll(".station-equip-group").forEach(el => {
      el.addEventListener("click", () => {
        const equipKey = el.getAttribute("data-equip-key");
        if (equipKey) {
          selectedEquip = equipKey;
          highlightSvgEquipment(equipKey);
          updateInspectorDrawer();
          if (active3dInstance) {
            active3dInstance.selectEquipment(equipKey);
          }
        }
      });
    });
  }

  function cleanupStationTab() {
    clearTimeout(debounceTimer);
    debounceTimer = null;
    abort2dControls();
    destroy3d();
    if (typeof unsubscribeStore === "function") unsubscribeStore();
    if (typeof unsubscribeUi === "function") unsubscribeUi();
    if (container._stationCleanup === cleanupStationTab) {
      container._stationCleanup = null;
    }
  }
  container._stationCleanup = cleanupStationTab;

  // Auto-fetch on mount
  fetchStationData();
  return { destroy: cleanupStationTab };
}

/**
 * Helper to render an ISA 5.1 compliant instrument bubble with live DCS readout.
 */
function renderIsaBubble(cx, cy, tapX, tapY, tagCode, loopNum, valStr, unitStr, color = "#38bdf8") {
  const isTapBelow = tapY >= cy;
  const leadStartY = isTapBelow ? cy + 13 : cy - 13;
  const pillY = isTapBelow ? cy - 27 : cy + 15;

  return `
    <g class="isa-instrument-group" style="cursor: default;">
      <title>${tagCode}-${loopNum}: ${valStr} ${unitStr}</title>
      <!-- Instrument Process Tap Lead Line -->
      <line x1="${cx}" y1="${leadStartY}" x2="${tapX}" y2="${tapY}" stroke="${color}" stroke-width="1.2" stroke-dasharray="2 2" opacity="0.85" />
      <circle cx="${tapX}" cy="${tapY}" r="2.5" fill="${color}" />

      <!-- ISA 5.1 Instrument Circle (Field / DCS Mounted) -->
      <circle cx="${cx}" cy="${cy}" r="13" fill="#0b1120" stroke="${color}" stroke-width="1.6" />
      <line x1="${cx - 13}" y1="${cy}" x2="${cx + 13}" y2="${cy}" stroke="${color}" stroke-width="1" opacity="0.5" />
      
      <!-- ISA Functional Tag & Loop Number -->
      <text x="${cx}" y="${cy - 3}" fill="${color}" font-size="7.5" font-weight="700" font-family="var(--font-mono)" text-anchor="middle">${tagCode}</text>
      <text x="${cx}" y="${cy + 8}" fill="#94a3b8" font-size="6.5" font-weight="600" font-family="var(--font-mono)" text-anchor="middle">${loopNum}</text>

      <!-- DCS Readout Pill -->
      <g transform="translate(${cx - 24}, ${pillY})">
        <rect width="48" height="12" rx="3" fill="#030712" stroke="${color}" stroke-width="0.8" opacity="0.95" />
        <text x="24" y="9" fill="#f8fafc" font-size="7" font-weight="600" font-family="var(--font-mono)" text-anchor="middle">${valStr} ${unitStr}</text>
      </g>
    </g>
  `;
}

/**
 * Renders high-fidelity P&ID SVG with dynamic units, cyclones, filters, coolers, and animated flow.
 */
function renderStationSvg(data) {
  const { equipment_sizing: eq, station_summary: sm, nodes = [] } = data;
  const numCyclones = eq.cyclones.operating_count + 1;
  const numFilters = eq.cartridge_filters.operating_count + 1;
  const numComps = eq.turbo_compressors.operating_count + 1;
  const numCoolers = eq.air_coolers.bay_count;
  const pLines = data.station_piping?.lines || {};
  const npsLabel = (key, fallback) => (pLines[key]?.nominal_size_in || fallback).replace('"', '');
  const suctionNps = npsLabel("suction_header", "48");
  const dischargeNps = npsLabel("discharge_header", `${suctionNps}"`);
  const recycleNps = npsLabel("station_recycle", "48");
  const compSuctionNps = npsLabel("comp_suction_branch", "30");
  const suctionVal = parseInt(suctionNps, 10) || 48;
  const dischargeVal = parseInt(dischargeNps, 10) || suctionVal;
  const pigReceiverBarrel = `${suctionVal + 8}"x${suctionVal}"`;
  const pigLauncherBarrel = `${dischargeVal + 8}"x${dischargeVal}"`;

  // Extract nodal values safely
  const n1Temp = nodes[0]?.temp_c ? nodes[0].temp_c.toFixed(1) : "20.0";
  const n4Pres = nodes[3]?.pressure_bar ? nodes[3].pressure_bar.toFixed(1) : "44.6";
  const n5Temp = nodes[4]?.temp_c ? nodes[4].temp_c.toFixed(1) : "43.8";
  const n7Pres = nodes[6]?.pressure_bar ? nodes[6].pressure_bar.toFixed(1) : "74.6";
  const n8Pres = nodes[7]?.pressure_bar ? nodes[7].pressure_bar.toFixed(1) : "74.6";

  return `
    <svg viewBox="0 0 1180 580" style="width: 100%; height: auto; display: block;" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <style>
          .station-equip-group {
            cursor: pointer;
            transition: filter 0.25s ease, transform 0.2s ease;
          }
          .station-equip-group:hover rect,
          .station-equip-group:hover polygon,
          .station-equip-group:hover circle:not(.station-equip-no-glow) {
            filter: drop-shadow(0 0 6px rgba(56, 189, 248, 0.75));
          }
          .station-equip-group.active-selected rect,
          .station-equip-group.active-selected polygon,
          .station-equip-group.active-selected circle:not(.station-equip-no-glow) {
            stroke: #fbbf24 !important;
            stroke-width: 3px !important;
            filter: drop-shadow(0 0 12px rgba(251, 191, 36, 0.95)) !important;
          }
          .isa-instrument-group {
            transition: transform 0.2s ease, opacity 0.2s ease;
          }
          .isa-instrument-group:hover {
            filter: drop-shadow(0 0 6px #38bdf8);
          }
        </style>

        <!-- Gradients -->
        <linearGradient id="grad-suction" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stop-color="#38bdf8" />
          <stop offset="100%" stop-color="#0284c7" />
        </linearGradient>
        <linearGradient id="grad-discharge" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stop-color="#f87171" />
          <stop offset="100%" stop-color="#dc2626" />
        </linearGradient>
        <linearGradient id="grad-cooled" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stop-color="#34d399" />
          <stop offset="100%" stop-color="#059669" />
        </linearGradient>
        <linearGradient id="grad-shelter" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stop-color="#1e293b" stop-opacity="0.15" />
          <stop offset="100%" stop-color="#0f172a" stop-opacity="0.3" />
        </linearGradient>

        <!-- Valve Marker / Symbols -->
        <marker id="arrow-blue" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="#0ea5e9" />
        </marker>
        <marker id="arrow-red" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="#ef4444" />
        </marker>
        <marker id="arrow-green" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="#10b981" />
        </marker>
        <marker id="arrow-amber" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="#f59e0b" />
        </marker>
      </defs>

      <!-- Grid Background Lines -->
      <pattern id="station-grid" width="40" height="40" patternUnits="userSpaceOnUse">
        <path d="M 40 0 L 0 0 0 40" fill="none" stroke="currentColor" stroke-opacity="0.05" stroke-width="1" />
      </pattern>
      <rect width="1180" height="580" fill="url(#station-grid)" />

      <!-- ══════════════════ 1. MAINLINE INLET & PIG RECEIVER (X: 30 - 150) ══════════════════ -->
      <g class="station-equip-group" data-equip-key="pig_receiver">
        <!-- Mainline Pipe Incoming -->
        <line x1="20" y1="210" x2="80" y2="210" stroke="#0ea5e9" stroke-width="8" stroke-linecap="round" />
        <line x1="20" y1="210" x2="80" y2="210" stroke="#bae6fd" stroke-width="3" class="station-flow-fast" />
        <text x="25" y="195" fill="#0ea5e9" font-size="10" font-weight="700">${escapeHtml(suctionNps)}" BATI KARADENİZ</text>
        <text x="25" y="232" fill="var(--color-text-secondary)" font-size="9">${sm.suction_pressure_bar} bar</text>

        <!-- Pig Receiver Vessel (Horizontal Capsule) -->
        <rect x="75" y="185" width="65" height="50" rx="14" fill="#334155" stroke="#0ea5e9" stroke-width="2" />
        <line x1="140" y1="185" x2="140" y2="235" stroke="#f59e0b" stroke-width="3" />
        <path d="M 140 195 L 147 210 L 140 225 Z" fill="#f59e0b" />
        <text x="107" y="212" fill="#ffffff" font-size="8" font-weight="700" text-anchor="middle">PIG-R</text>
        <text x="107" y="224" fill="#38bdf8" font-size="7" font-weight="600" text-anchor="middle">${escapeHtml(pigReceiverBarrel)}</text>
        <text x="107" y="248" fill="var(--color-text-secondary)" font-size="8" text-anchor="middle">Pig Alıcı Kovan</text>
      </g>

      <!-- Suction ISA 5.1 Field Instruments -->
      ${renderIsaBubble(45, 155, 45, 210, "PT", "101", sm.suction_pressure_bar.toFixed(1), "bar", "#38bdf8")}
      ${renderIsaBubble(85, 140, 85, 185, "TT", "101", n1Temp, "°C", "#38bdf8")}
      ${renderIsaBubble(135, 140, 135, 185, "FT", "101", sm.total_mass_flow_kgs.toFixed(1), "kg/s", "#38bdf8")}

      <!-- Tie-in line from Pig Receiver to Suction Header + SV-IN & Loading Line (§5.4, §5.12) -->
      <path d="M 107 185 L 107 120 L 180 120" fill="none" stroke="#0ea5e9" stroke-width="6" stroke-linejoin="round" />
      <path d="M 107 185 L 107 120 L 180 120" fill="none" stroke="#ffffff" stroke-width="2" class="station-flow-line" />
      <g class="station-equip-group" data-equip-key="station_suction_valve">
        <circle cx="145" cy="120" r="9" fill="#0f172a" stroke="#38bdf8" stroke-width="2" />
        <path d="M 139 115 L 151 125 M 151 115 L 139 125" stroke="#38bdf8" stroke-width="2" />
        <rect x="142" y="106" width="6" height="5" fill="#38bdf8" />
        <text x="145" y="139" fill="#38bdf8" font-size="7" font-weight="700" text-anchor="middle">SV-IN</text>
      </g>
      <g class="station-equip-group" data-equip-key="station_loading_line">
        <path d="M 127 120 L 127 92 L 163 92 L 163 120" fill="none" stroke="#14b8a6" stroke-width="2.5" stroke-linejoin="round" />
        <circle cx="137" cy="92" r="4.5" fill="#0f172a" stroke="#14b8a6" stroke-width="1.5" />
        <circle cx="153" cy="92" r="4.5" fill="#0f172a" stroke="#22d3ee" stroke-width="1.5" />
        <text x="145" y="83" fill="#2dd4bf" font-size="6.5" font-weight="700" text-anchor="middle">LOADING (§5.12)</text>
      </g>
      <!-- Mainline Block Valve MLBV-101 (§5.4) -->
      <g class="station-equip-group" data-equip-key="mainline_block_valve">
        <path d="M 55 210 L 55 545 L 1130 545 L 1130 260" fill="none" stroke="#64748b" stroke-width="3" stroke-dasharray="6 4" />
        <circle cx="590" cy="545" r="9" fill="#0f172a" stroke="#f59e0b" stroke-width="2" />
        <path d="M 584 540 L 596 550 M 596 540 L 584 550" stroke="#f59e0b" stroke-width="2" />
        <text x="590" y="564" fill="#fbbf24" font-size="7.5" font-weight="700" text-anchor="middle">MLBV-101 (Ana Hat Blok Vana • Fail-Open §5.4)</text>
      </g>

      <!-- ══════════════════ 2. 48" SUCTION HEADER & DYNAMIC CYCLONES (X: 180 - 280) ══════════════════ -->
      <!-- Suction Header Manifold Bar -->
      <rect x="180" y="112" width="16" height="320" rx="6" fill="#0284c7" stroke="#38bdf8" stroke-width="2" />
      <text x="188" y="98" fill="#0284c7" font-size="9" font-weight="700" text-anchor="middle">${escapeHtml(suctionNps)}" SUCTION HEADER</text>

      <!-- Separation Differential Pressure & Suction Transmitters -->
      ${renderIsaBubble(240, 65, 240, 112, "PDT", "101", "0.20", "Δbar", "#0ea5e9")}
      ${renderIsaBubble(322, 65, 322, 130, "PDT", "102", "0.20", "Δbar", "#2563eb")}
      ${renderIsaBubble(367, 85, 367, 140, "PT", "201", n4Pres, "bar", "#1d4ed8")}

      <!-- Dynamic Cyclone Separators -->
      ${renderDynamicCyclonesSvg(numCyclones, eq.cyclones)}

      <!-- Intermediate Header linking Cyclones to Filters -->
      <rect x="270" y="130" width="12" height="280" rx="4" fill="#2563eb" stroke="#60a5fa" stroke-width="1.5" />

      <!-- Dynamic Cartridge Filters -->
      ${renderDynamicFiltersSvg(numFilters, eq.cartridge_filters)}

      <!-- Filtered Header into Compressor Suction -->
      <rect x="360" y="140" width="14" height="260" rx="4" fill="#1d4ed8" stroke="#93c5fd" stroke-width="1.5" />
      <text x="367" y="128" fill="#1d4ed8" font-size="8" font-weight="700" text-anchor="middle">${escapeHtml(compSuctionNps)}" COMP. SUCTION</text>

      <!-- ══════════════════ CONDENSATE TANK & DRAIN LINES (BOTAŞ PFD Note 14 & 15) ══════════════════ -->
      <g class="station-equip-group" data-equip-key="condensate_system">
        <!-- Horizontal Condensate Tank -->
        <rect x="215" y="465" width="145" height="36" rx="10" fill="#1e293b" stroke="#92400e" stroke-width="2" />
        <text x="287" y="485" fill="#fef3c7" font-size="9" font-weight="700" text-anchor="middle">KONDENSAT TANKI (Note 14)</text>
        <text x="287" y="496" fill="#fbbf24" font-size="7" text-anchor="middle">LCV Seviye Kontrol Drenajı • ${eq.condensate_system?.collection_tank_volume_m3 || 15} m³</text>
        
        <!-- Flame Arrester Vent Stack -->
        <line x1="345" y1="465" x2="345" y2="435" stroke="#92400e" stroke-width="2" />
        <polygon points="340,435 350,435 345,425" fill="#92400e" />
        <text x="345" y="420" fill="#92400e" font-size="7" font-weight="700" text-anchor="middle">VENT [F]</text>
      </g>

      <!-- ══════════════════ 3. COMPRESSOR SHELTER & TURBO-COMPRESSOR TRAINS (X: 400 - 740) ══════════════════ -->
      <g class="station-equip-group" data-equip-key="compressor_building">
        <!-- Shelter Outline -->
        <rect x="400" y="110" width="340" height="340" rx="10" fill="url(#grad-shelter)" stroke="#eab308" stroke-width="2" stroke-dasharray="6 3" />
        <!-- Crane beam -->
        <line x1="410" y1="130" x2="730" y2="130" stroke="#ca8a04" stroke-width="3" />
        <text x="570" y="126" fill="#ca8a04" font-size="10" font-weight="700" text-anchor="middle">
          ÜNİTE BİNASI (Compressor Shelter) • 15 Ton Vinç • ${eq.compressor_building.area_m2} m²
        </text>
      </g>

      <!-- Dynamic Turbo-Compressor Packages Inside Shelter -->
      ${renderDynamicCompressorTrainsSvg(numComps, eq.turbo_compressors)}

      <!-- ══════════════════ 4. 48" DISCHARGE HEADER (X: 750 - 775) ══════════════════ -->
      <!-- Common Discharge Header Manifold -->
      <rect x="750" y="130" width="16" height="300" rx="6" fill="#b91c1c" stroke="#f87171" stroke-width="2" />
      <text x="758" y="108" fill="#ef4444" font-size="9" font-weight="700" text-anchor="middle">${escapeHtml(dischargeNps)}" DISCHARGE HEADER</text>
      <text x="758" y="445" fill="#ef4444" font-size="9" text-anchor="middle">${sm.discharge_pressure_bar} bar</text>

      <!-- Discharge Header Transmitters -->
      ${renderIsaBubble(740, 75, 750, 130, "PT", "202", sm.discharge_pressure_bar.toFixed(1), "bar", "#ef4444")}
      ${renderIsaBubble(790, 75, 790, 260, "TT", "202", n5Temp, "°C", "#ef4444")}

      <!-- ══════════════════ 5. ANTI-SURGE / RECYCLE HEADER (Note 13) ══════════════════ -->
      <g class="station-equip-group" data-equip-key="station_recycle">
        <!-- Recycle pipe running top from X=758 around shelter to X=188 -->
        <path d="M 758 130 L 758 60 L 188 60 L 188 112" fill="none" stroke="#f97316" stroke-width="5" stroke-linejoin="round" />
        <path d="M 758 130 L 758 60 L 188 60 L 188 112" fill="none" stroke="#ffffff" stroke-width="1.5" class="station-flow-line" />
        
        <!-- Station Recycle Control Valve (PCV) -->
        <circle cx="470" cy="60" r="14" fill="#334155" stroke="#f97316" stroke-width="2" />
        <path d="M 462 53 L 478 67 M 478 53 L 462 67" stroke="#f97316" stroke-width="2" />
        <rect x="466" y="40" width="8" height="8" fill="#f97316" />
        <text x="470" y="32" fill="#f97316" font-size="9" font-weight="700" text-anchor="middle">${escapeHtml(recycleNps)}" ANTI-SURGE / RECYCLE HEADER</text>
      </g>

      <!-- Main Header pipe to Air Coolers -->
      <path d="M 766 260 L 810 260" fill="none" stroke="#ef4444" stroke-width="8" />
      <path d="M 766 260 L 810 260" fill="none" stroke="#fecaca" stroke-width="3" class="station-flow-fast" />

      <!-- ══════════════════ 6. FIN-FAN AIR COOLERS & GAS COOLER BY-PASS (Note 17) ══════════════════ -->
      ${renderDynamicCoolersSvg(numCoolers, eq.air_coolers)}

      <!-- GAS COOLER BY-PASS LINE WITH TCV (BOTAŞ PFD Note 17) -->
      <g class="station-equip-group" data-equip-key="cooler_bypass">
        <path d="M 790 260 L 790 350 L 965 350 L 965 260" fill="none" stroke="#f59e0b" stroke-width="3" stroke-linejoin="round" />
        <path d="M 790 260 L 790 350 L 965 350 L 965 260" fill="none" stroke="#ffffff" stroke-width="1" class="station-flow-line" />
        
        <!-- TCV Valve Symbol -->
        <circle cx="875" cy="350" r="10" fill="#334155" stroke="#f59e0b" stroke-width="1.5" />
        <path d="M 870 345 L 880 355 M 880 345 L 870 355" stroke="#f59e0b" stroke-width="1.5" />
        <rect x="872" y="337" width="6" height="6" fill="#f59e0b" />
        <text x="875" y="372" fill="#f59e0b" font-size="8" font-weight="700" text-anchor="middle">GAS COOLER BY-PASS (TCV - Note 17)</text>
      </g>
      ${renderIsaBubble(875, 412, 875, 360, "TCV", "101", "By-Pass", "%0", "#f59e0b")}

      <!-- Cooled Gas Pipe leaving coolers -->
      <path d="M 940 260 L 980 260" fill="none" stroke="#10b981" stroke-width="8" />
      <path d="M 940 260 L 980 260" fill="none" stroke="#a7f3d0" stroke-width="3" class="station-flow-fast" />

      <!-- Air Cooler Transmitters -->
      ${renderIsaBubble(965, 180, 965, 260, "TT", "301", eq.air_coolers.outlet_temp_c.toFixed(1), "°C", "#10b981")}
      ${renderIsaBubble(1010, 195, 980, 260, "PT", "301", n7Pres, "bar", "#10b981")}

      <!-- ══════════════════ 7. SAFETY RELIEF (PSV & BLOWDOWN BDV) (X: 980 - 1030) ══════════════════ -->
      <g class="station-equip-group" data-equip-key="safety_relief">
        <!-- Relief stub vertical up -->
        <path d="M 990 260 L 990 170" fill="none" stroke="#ef4444" stroke-width="4" />
        
        <!-- PSV Symbol -->
        <polygon points="980,185 1000,185 990,170" fill="#dc2626" stroke="#ffffff" stroke-width="1.5" />
        <circle cx="990" cy="162" r="7" fill="#f87171" />
        <line x1="990" y1="155" x2="990" y2="120" stroke="#dc2626" stroke-width="3" />
        <line x1="980" y1="120" x2="1000" y2="120" stroke="#dc2626" stroke-width="3" />
        <text x="990" y="110" fill="#ef4444" font-size="8" font-weight="700" text-anchor="middle">STATION RELIEF (PSV)</text>
        <text x="990" y="145" fill="var(--color-text-secondary)" font-size="8" text-anchor="middle">${eq.safety_relief_and_blowdown.psv_set_pressure_bar} bar</text>

        <!-- Blowdown BDV stub vertical down -->
        <path d="M 990 260 L 990 350" fill="none" stroke="#e11d48" stroke-width="4" />
        <circle cx="990" cy="350" r="10" fill="#334155" stroke="#e11d48" stroke-width="2" />
        <path d="M 984 345 L 996 355 M 996 345 L 984 355" stroke="#e11d48" stroke-width="2" />
        <rect x="987" y="360" width="6" height="8" fill="#e11d48" />
        <text x="990" y="380" fill="#e11d48" font-size="8" font-weight="700" text-anchor="middle">BLOWDOWN (BDV)</text>
        <text x="990" y="392" fill="var(--color-text-secondary)" font-size="7" text-anchor="middle">1 barg ≤ 60 s ESD / ${eq.esd_sizing?.depressurization_time_min ?? 15} dk</text>
      </g>
      ${renderIsaBubble(1040, 125, 990, 162, "PSV", "101", eq.safety_relief_and_blowdown.psv_set_pressure_bar.toFixed(1), "bar", "#dc2626")}
      ${renderIsaBubble(1040, 350, 990, 350, "BDV", "101", "ESD", "Vent", "#e11d48")}

      <!-- Gas Cooler Inlet Utility Gas + Compressed Air & Power Gas Skid -->
      <g class="station-equip-group" data-equip-key="station_utilities">
        <path d="M 795 260 L 795 452 L 820 452" fill="none" stroke="#14b8a6" stroke-width="2" stroke-dasharray="3 2" />
        <rect x="820" y="432" width="160" height="36" rx="5" fill="#0f172a" stroke="#14b8a6" stroke-width="1.4" />
        <text x="900" y="446" fill="#2dd4bf" font-size="7.5" font-weight="700" text-anchor="middle">YARDIMCI TESİSLER (UTIL-101..401)</text>
        <text x="900" y="458" fill="#94a3b8" font-size="6.5" text-anchor="middle">Kullanım Gazı ≥1485 Sm³/h · Hava ≥25 m³ (-40°C)</text>
      </g>

      <!-- Station By-Pass Non-Slam Check (§5.13: Cooler sonrası, USM öncesi Discharge ↔ Suction) -->
      <g class="station-equip-group" data-equip-key="station_bypass_valve">
        <path d="M 970 260 L 970 42 L 188 42 L 188 112" fill="none" stroke="#a855f7" stroke-width="3" stroke-dasharray="5 3" stroke-linejoin="round" />
        <polygon points="586,35 586,49 572,42" fill="#a855f7" stroke="#ffffff" stroke-width="1" />
        <text x="580" y="29" fill="#c084fc" font-size="7.5" font-weight="700" text-anchor="middle">İSTASYON BY-PASS &amp; NON-SLAM ÇEKVALF (NRV-BP-101 • 4500 §5.13)</text>
      </g>

      <!-- Ultrasonic Flow Meter Skid (USM-101 • 4500 §5.9) & Station Discharge Side Valve (SV-OUT • 4500 §5.4) -->
      <g class="station-equip-group" data-equip-key="ultrasonic_meter">
        <rect x="1004" y="246" width="24" height="28" rx="4" fill="#0f172a" stroke="#38bdf8" stroke-width="1.8" />
        <text x="1016" y="263" fill="#38bdf8" font-size="7" font-weight="700" text-anchor="middle">USM</text>
      </g>
      <g class="station-equip-group" data-equip-key="station_discharge_valve">
        <circle cx="1038" cy="260" r="8.5" fill="#0f172a" stroke="#ef4444" stroke-width="2" />
        <path d="M 1033 255 L 1043 265 M 1043 255 L 1033 265" stroke="#ef4444" stroke-width="2" />
        <text x="1038" y="282" fill="#f87171" font-size="7" font-weight="700" text-anchor="middle">SV-OUT</text>
      </g>

      <!-- ══════════════════ 8. PIG LAUNCHER & MAINLINE DISCHARGE (X: 1040 - 1160) ══════════════════ -->
      <g class="station-equip-group" data-equip-key="pig_launcher">
        <line x1="990" y1="260" x2="1050" y2="260" stroke="#10b981" stroke-width="8" />
        
        <!-- Pig Launcher Barrel -->
        <rect x="1050" y="235" width="60" height="50" rx="14" fill="#334155" stroke="#10b981" stroke-width="2" />
        <line x1="1050" y1="235" x2="1050" y2="285" stroke="#10b981" stroke-width="3" />
        <path d="M 1050 245 L 1043 260 L 1050 275 Z" fill="#10b981" />
        <text x="1080" y="260" fill="#ffffff" font-size="8" font-weight="700" text-anchor="middle">PIG-L</text>
        <text x="1080" y="272" fill="#6ee7b7" font-size="7" font-weight="600" text-anchor="middle">${escapeHtml(pigLauncherBarrel)}</text>
        <text x="1080" y="298" fill="var(--color-text-secondary)" font-size="8" text-anchor="middle">Pig Atıcı Kovan</text>

        <!-- Mainline Out -->
        <line x1="1110" y1="260" x2="1170" y2="260" stroke="#10b981" stroke-width="8" stroke-linecap="round" />
        <line x1="1110" y1="260" x2="1170" y2="260" stroke="#ecfdf5" stroke-width="3" class="station-flow-fast" />
        <text x="1165" y="232" fill="#10b981" font-size="10" font-weight="700" text-anchor="end">${escapeHtml(dischargeNps)}" ANA HAT BASMA</text>
        <text x="1165" y="280" fill="var(--color-text-secondary)" font-size="9" text-anchor="end">${eq.air_coolers.outlet_temp_c}°C • ${n8Pres} bar</text>
      </g>

      <!-- Mainline Discharge Transmitters -->
      ${renderIsaBubble(1090, 180, 1090, 260, "PT", "401", n8Pres, "bar", "#10b981")}
      ${renderIsaBubble(1140, 180, 1140, 260, "FT", "401", sm.total_mass_flow_kgs.toFixed(1), "kg/s", "#10b981")}

    </svg>
  `;
}

/**
 * Renders dynamic Cyclone Separators with LCV drain lines to condensate tank.
 */
function renderDynamicCyclonesSvg(count, info) {
  const startY = 140;
  const spacing = count > 1 ? 260 / (count - 1) : 0;

  let svg = `<g class="station-equip-group" data-equip-key="cyclones">`;
  for (let i = 0; i < count; i++) {
    const y = count === 1 ? 270 : startY + i * spacing;
    const isSpare = i === count - 1;

    svg += `
      <!-- Header to Cyclone Line -->
      <path d="M 196 ${y} L 225 ${y}" fill="none" stroke="#0ea5e9" stroke-width="4" />
      <path d="M 196 ${y} L 225 ${y}" fill="none" stroke="#bae6fd" stroke-width="1.5" class="station-flow-line" />

      <!-- Cyclone Vertical Vessel Body with cone bottom + below-barrel Horizontal Blow-Flask -->
      <rect x="225" y="${y - 22}" width="24" height="28" rx="4" fill="#1e293b" stroke="${isSpare ? '#94a3b8' : '#0ea5e9'}" stroke-width="1.5" />
      <polygon points="225,${y + 6} 249,${y + 6} 237,${y + 18}" fill="#1e293b" stroke="${isSpare ? '#94a3b8' : '#0ea5e9'}" stroke-width="1.5" />
      <!-- Dual separate instrument level bottles (LG/LT/LSH/LSL) -->
      <line x1="221" y1="${y + 2}" x2="221" y2="${y + 22}" stroke="#38bdf8" stroke-width="1.2" />
      <line x1="253" y1="${y + 2}" x2="253" y2="${y + 22}" stroke="#38bdf8" stroke-width="1.2" />
      <!-- Horizontal Blow-Flask + >=2°C heat tracing band -->
      <rect x="224" y="${y + 22}" width="26" height="10" rx="4" fill="#0f172a" stroke="#f97316" stroke-width="1.2" />

      <!-- Auto LCV & Manual dump drain lines to Condensate Tank -->
      <line x1="237" y1="${y + 32}" x2="237" y2="${y + 42}" stroke="#f97316" stroke-width="1.5" />
      <circle cx="237" cy="${y + 42}" r="3" fill="#b45309" />
      <path d="M 237 ${y + 45} L 237 465" fill="none" stroke="#92400e" stroke-width="1" stroke-dasharray="2 2" />

      <!-- Swirl icon inside -->
      <path d="M 233 ${y - 10} Q 237 ${y - 14} 241 ${y - 10} Q 237 ${y - 6} 233 ${y - 2}" fill="none" stroke="#38bdf8" stroke-width="1" />
      
      <text x="237" y="${y}" fill="#ffffff" font-size="7" font-weight="700" text-anchor="middle">S-${i + 1}</text>
      <text x="237" y="${y + 54}" fill="var(--color-text-secondary)" font-size="7" text-anchor="middle">
        ${isSpare ? 'Yedek' : `${info.flow_per_unit_kgs} k/s`}
      </text>

      <!-- Cyclone to Intermediate Header Line -->
      <path d="M 249 ${y} L 270 ${y}" fill="none" stroke="#2563eb" stroke-width="4" />
    `;
  }
  svg += `
    <text x="237" y="100" fill="#0ea5e9" font-size="8" font-weight="700" text-anchor="middle">MFS SİKLON (${count})</text>
    <text x="237" y="110" fill="#f97316" font-size="6.5" font-weight="700" text-anchor="middle">≥8µm %100 · Blow-Flask</text>
  </g>`;
  return svg;
}

/**
 * Renders dynamic Cartridge Filters with LCV drain lines to condensate tank.
 */
function renderDynamicFiltersSvg(count, info) {
  const startY = 150;
  const spacing = count > 1 ? 240 / (count - 1) : 0;

  let svg = `<g class="station-equip-group" data-equip-key="cartridge_filters">`;
  for (let i = 0; i < count; i++) {
    const y = count === 1 ? 270 : startY + i * spacing;
    const isSpare = i === count - 1;

    svg += `
      <!-- Inter-header to Filter Line -->
      <path d="M 282 ${y} L 305 ${y}" fill="none" stroke="#2563eb" stroke-width="4" />

      <!-- Filter Vessel (Horizontal Capsule with internal hatched cartridge + QOC + Blow-Flask >= 2 °C) -->
      <rect x="305" y="${y - 16}" width="34" height="24" rx="7" fill="#1e293b" stroke="${isSpare ? '#94a3b8' : '#2563eb'}" stroke-width="1.5" />
      <line x1="308" y1="${y - 14}" x2="308" y2="${y + 6}" stroke="#fbbf24" stroke-width="2" />
      <line x1="316" y1="${y - 12}" x2="316" y2="${y + 4}" stroke="#60a5fa" stroke-width="1.5" stroke-dasharray="2 2" />
      <line x1="324" y1="${y - 12}" x2="324" y2="${y + 4}" stroke="#60a5fa" stroke-width="1.5" stroke-dasharray="2 2" />
      <rect x="311" y="${y + 10}" width="22" height="8" rx="3" fill="#0f172a" stroke="#f97316" stroke-width="1.1" />

      <!-- Bottom drain line to condensate tank -->
      <path d="M 322 ${y + 18} L 322 465" fill="none" stroke="#92400e" stroke-width="1" stroke-dasharray="2 2" />

      <text x="322" y="${y - 2}" fill="#ffffff" font-size="7" font-weight="700" text-anchor="middle">F-${i + 1}</text>
      <text x="322" y="${y + 27}" fill="var(--color-text-secondary)" font-size="6.5" text-anchor="middle">
        ${isSpare ? 'Yedek · QOC' : `${info.flow_per_unit_kgs} k/s`}
      </text>

      <!-- Filter to Comp Suction Header Line -->
      <path d="M 339 ${y} L 360 ${y}" fill="none" stroke="#1d4ed8" stroke-width="4" />
      <path d="M 339 ${y} L 360 ${y}" fill="none" stroke="#93c5fd" stroke-width="1.5" class="station-flow-line" />
    `;
  }
  svg += `
    <text x="322" y="100" fill="#2563eb" font-size="8" font-weight="700" text-anchor="middle">CFS KARTUŞ (${count})</text>
    <text x="322" y="110" fill="#38bdf8" font-size="6.5" font-weight="700" text-anchor="middle">≥3µm %99.8 · QOC</text>
  </g>`;
  return svg;
}

/**
 * Renders dynamic Turbo-Compressor Train Units with Individual Anti-Surge Loops.
 */
function renderDynamicCompressorTrainsSvg(count, info) {
  const startY = 160;
  const spacing = count > 1 ? 230 / (count - 1) : 0;

  let svg = `<g class="station-equip-group" data-equip-key="turbo_compressors">`;
  for (let i = 0; i < count; i++) {
    const y = count === 1 ? 270 : startY + i * spacing;
    const isSpare = i === count - 1;

    svg += `
      <!-- Train Suction Line from Header + Dual Series Ball Valves (MOV <=30s + Manual) + Temp Startup Strainer -->
      <path d="M 374 ${y} L 430 ${y}" fill="none" stroke="#1d4ed8" stroke-width="5" />
      <path d="M 374 ${y} L 430 ${y}" fill="none" stroke="#93c5fd" stroke-width="1.5" class="${isSpare ? '' : 'station-flow-line'}" />
      <rect x="383" y="${y - 4}" width="7" height="8" rx="1" fill="#0f172a" stroke="#38bdf8" stroke-width="1" />
      <rect x="395" y="${y - 4}" width="7" height="8" rx="1" fill="#0f172a" stroke="#94a3b8" stroke-width="1" />
      <polygon points="416,${y - 4} 424,${y} 416,${y + 4}" fill="#f97316" />

      <!-- Centrifugal Compressor Casing + DGS -->
      <rect x="430" y="${y - 18}" width="38" height="36" rx="6" fill="#1e3a8a" stroke="${isSpare ? '#94a3b8' : '#3b82f6'}" stroke-width="2" />
      <path d="M 438 ${y - 10} L 460 ${y - 14} L 460 ${y + 14} L 438 ${y + 10} Z" fill="#2563eb" opacity="0.8" />
      <rect x="434" y="${y + 10}" width="12" height="6" rx="1" fill="#06b6d4" />
      <text x="449" y="${y + 3}" fill="#ffffff" font-size="8" font-weight="700" text-anchor="middle">CMP-${i + 1}</text>

      <!-- Shaft Coupling -->
      <rect x="468" y="${y - 4}" width="12" height="8" fill="#64748b" />

      <!-- Gas Turbine Driver (GT) + Self-Cleaning Air Intake & Lube Oil Cooler -->
      <rect x="480" y="${y - 20}" width="54" height="40" rx="4" fill="#78350f" stroke="${isSpare ? '#94a3b8' : '#f59e0b'}" stroke-width="2" />
      <rect x="520" y="${y - 30}" width="10" height="10" fill="#475569" stroke="#94a3b8" />
      <rect x="486" y="${y + 14}" width="16" height="6" rx="1" fill="#475569" stroke="#38bdf8" stroke-width="0.8" />
      <text x="507" y="${y + 3}" fill="#fef3c7" font-size="8" font-weight="700" text-anchor="middle">GT-${i + 1}</text>
      <text x="507" y="${y + 13}" fill="#fef3c7" font-size="6" text-anchor="middle">${info.power_per_unit_kw} kW</text>

      <!-- Discharge Line from Compressor + Non-Slam Check + Dual Series Isolation Valves -->
      <path d="M 449 ${y - 18} L 449 ${y - 28} L 710 ${y - 28} L 710 ${y} L 750 ${y}" fill="none" stroke="#dc2626" stroke-width="5" />
      <path d="M 449 ${y - 18} L 449 ${y - 28} L 710 ${y - 28} L 710 ${y} L 750 ${y}" fill="none" stroke="#fca5a5" stroke-width="1.5" class="${isSpare ? '' : 'station-flow-fast'}" />
      <polygon points="675,${y - 32} 685,${y - 28} 675,${y - 24}" fill="#dc2626" />
      <rect x="690" y="${y - 32}" width="6" height="8" rx="1" fill="#0f172a" stroke="#ef4444" stroke-width="1" />
      <rect x="699" y="${y - 32}" width="6" height="8" rx="1" fill="#0f172a" stroke="#94a3b8" stroke-width="1" />

      <!-- ═════ DEDICATED ANTI-SURGE RECYCLE LOOP (HOT GAS) ═════ -->
      <!-- Taps off before check valve (X=660), ASV + downstream check & shutoff (Özel §4.8) -->
      <path d="M 660 ${y - 28} L 660 ${y + 24} L 405 ${y + 24} L 405 ${y}" fill="none" stroke="#f59e0b" stroke-width="3" stroke-linejoin="round" />
      
      <!-- Anti-Surge Valve (ASV) + Downstream Check/Block -->
      <circle cx="560" cy="${y + 24}" r="8" fill="#334155" stroke="#f59e0b" stroke-width="1.5" />
      <path d="M 555 ${y + 20} L 565 ${y + 28} M 565 ${y + 20} L 555 ${y + 28}" stroke="#f59e0b" stroke-width="1.5" />
      <rect x="557" y="${y + 11}" width="6" height="5" fill="#f59e0b" />
      <polygon points="518,${y + 21} 525,${y + 24} 518,${y + 27}" fill="#f59e0b" />
      <rect x="502" y="${y + 20}" width="7" height="8" rx="1" fill="#0f172a" stroke="#f59e0b" stroke-width="0.9" />
      <text x="560" y="${y + 38}" fill="#f59e0b" font-size="7" font-weight="600" text-anchor="middle">ASV-${i + 1} (${escapeHtml(info.anti_surge_valve_size_in)}")</text>

      <!-- Train Status Label -->
      <text x="449" y="${y + 34}" fill="${isSpare ? '#94a3b8' : '#38bdf8'}" font-size="8" font-weight="600" text-anchor="middle">
        ${isSpare ? 'Yedek Tren (Standby)' : `Tren ${i + 1} (Aktif)`}
      </text>
    `;
  }
  svg += `</g>
    <g class="station-equip-group" data-equip-key="fuel_gas">
      <path d="M 367 130 L 367 86 L 450 86" fill="none" stroke="#14b8a6" stroke-width="2" stroke-dasharray="3 2" />
      <rect x="450" y="72" width="128" height="28" rx="5" fill="#0f172a" stroke="#14b8a6" stroke-width="1.5" />
      <text x="514" y="84" fill="#2dd4bf" font-size="7.5" font-weight="700" text-anchor="middle">FG-101 YAKIT GAZI SKİDİ</text>
      <text x="514" y="94" fill="#94a3b8" font-size="6.5" text-anchor="middle">1 µm + 20 °C · CFS Sonrası / Soğutucu Öncesi</text>
    </g>`;
  return svg;
}

/**
 * Renders dynamic Fin-Fan Air Coolers with rotating fan blade graphics.
 */
function renderDynamicCoolersSvg(count, info) {
  let svg = `<g class="station-equip-group" data-equip-key="air_coolers">`;
  const startX = 815;
  const bayWidth = 36;
  const bayGap = 8;

  for (let i = 0; i < count; i++) {
    const x = startX + i * (bayWidth + bayGap);
    svg += `
      <!-- Cooler Bay Structure -->
      <rect x="${x}" y="220" width="${bayWidth}" height="80" rx="4" fill="#0f172a" stroke="#10b981" stroke-width="1.5" />
      
      <!-- Fin Tubes Graphic -->
      <line x1="${x + 4}" y1="230" x2="${x + bayWidth - 4}" y2="230" stroke="#6ee7b7" stroke-width="2" />
      <line x1="${x + 4}" y1="238" x2="${x + bayWidth - 4}" y2="238" stroke="#6ee7b7" stroke-width="2" />
      
      <!-- Fan Shroud & Spinning Fan Blade -->
      <circle cx="${x + bayWidth / 2}" cy="265" r="14" fill="#1e293b" stroke="#10b981" stroke-width="1" />
      <g class="station-fan-blade" style="transform-origin: ${x + bayWidth / 2}px 265px;">
        <ellipse cx="${x + bayWidth / 2}" cy="265" rx="12" ry="3" fill="#34d399" opacity="0.8" />
        <ellipse cx="${x + bayWidth / 2}" cy="265" rx="3" ry="12" fill="#34d399" opacity="0.8" />
      </g>
      <circle cx="${x + bayWidth / 2}" cy="265" r="3" fill="#ffffff" />

      <text x="${x + bayWidth / 2}" y="315" fill="var(--color-text-secondary)" font-size="7" text-anchor="middle">Bay ${i + 1}</text>
    `;
  }

  svg += `
    <text x="${startX + (count * 44) / 2}" y="208" fill="#10b981" font-size="9" font-weight="700" text-anchor="middle">
      HAVA SOĞUTUCULARI (${count} Bay • ${info.total_heat_duty_mw} MWth)
    </text>
  </g>`;
  return svg;
}

/**
 * Renders the floating inspection drawer when an equipment item is clicked.
 */
function renderDrawerWarnings(warningsList, lang = "tr") {
  const cleaned = (warningsList || []).map(w => normalizeWarningItem(w)).filter(Boolean);
  if (!cleaned.length) return "";
  return `
    <div role="alert" style="margin-top: 8px; padding: 6px 8px; border-radius: var(--radius-sm); background: rgba(245, 158, 11, 0.12); border: 1px solid rgba(245, 158, 11, 0.35); font-size: 10px; color: #f59e0b;">
      <div style="font-weight: 700; margin-bottom: 2px;">⚠️ ${escapeHtml(t("station_warnings_title", lang))}:</div>
      ${cleaned.map(w => `<div>• ${escapeHtml(w)}</div>`).join("")}
    </div>
  `;
}

function renderInspectorDrawer(key, eq, sm, gasComp, viewMode = "2d", lang = "tr") {
  let title = t("station_inspector_default_title", lang);
  let content = "";

  if (key === "pig_receiver") {
    const pig = eq.pigging || {};
    title = "Pig Alıcı & İstasyon Yan Vanaları (PIG-R • 4500 §5.4, §5.12–13)";
    content = `
      <div style="font-size: 11px; line-height: 1.5; color: var(--color-text);">
        <p><b>İşlev:</b> Ana iletim hattından gelen pig araçlarını yakalar; Gas-over-Oil istasyon yan vanaları (0.5–4.0 barg ΔP kilidi), Loading hattı (§5.12) ve Non-Slam Check Bypass (§5.13) ile entegredir.</p>
        <table class="kasp-table" style="font-size: 10px; margin: 8px 0;">
          <tr><td>Kovan Ölçüsü</td><td>${escapeHtml(pig.receiver || 'PIG-R-56"x48" (ANSI Class 600)')}</td></tr>
          <tr><td>İşletme Basıncı</td><td>${sm.suction_pressure_bar} bar(a)</td></tr>
          <tr><td>Yan Vana &amp; ΔP Kilidi</td><td>${escapeHtml(pig.side_valves || "Gas-over-Oil Fail-Closed")} • ${escapeHtml(pig.dp_interlock_barg || "0.5–4.0 barg")}</td></tr>
          <tr><td>Loading &amp; Station Bypass</td><td>${escapeHtml(pig.loading_line || "4500 §5.12 Loading")} • ${escapeHtml(pig.station_bypass_check || "4500 §5.13 Check Bypass")}</td></tr>
        </table>
      </div>
    `;
  } else if (key === "cyclones") {
    const cyc = eq.cyclones || {};
    const bf = cyc.blow_flask || {};
    const ht = cyc.heat_tracing || {};
    title = `MFS Çoklu Siklon Seperatörler (${cyc.configuration})`;
    content = `
      <div style="font-size: 11px; line-height: 1.5; color: var(--color-text);">
        <p><b>İşlev (Spec 5260 & 4500 §5.2):</b> Tek kademeli dikey çoklu siklon iç elemanlarıyla ≥ 8 µm katı/sıvı partikülleri %100, ≥ 4 µm partikülleri %90 tutar; gövde altı yatay Blow-Flask ve ısıtmalı (≥ 2 °C) oto/manuel drenaj manifoldlarıyla TK-101'e aktarır.</p>
        <table class="kasp-table" style="font-size: 10px; margin: 8px 0;">
          <tr><td>Çalışma Modeli</td><td>${escapeHtml(cyc.configuration || `${cyc.operating_count} Çalışan + 1 Yedek`)} (%${cyc.unit_capacity_pct ?? 50} birim kapasite)</td></tr>
          <tr><td>Ünite Debisi & İç Tüp</td><td>${cyc.flow_per_unit_kgs} kg/s (${cyc.internal_cyclone_elements ?? "-"} adet siklon tüpü)</td></tr>
          <tr><td>Basınç Kaybı (ΔP)</td><td>${cyc.pressure_drop_bar} bar (${cyc.clean_dp_mbar ?? Math.round((cyc.pressure_drop_bar || 0) * 1000)} mbar · Temiz ≤ 400 mbar / Kirli 700 mbar)</td></tr>
          <tr><td>Mekanik (ASME VIII)</td><td>Ø${cyc.vessel_diameter_mm} mm · ${escapeHtml(cyc.head_type || "Spherical Fixed")} · ${cyc.corrosion_allowance_mm ?? 1.6} mm CA · SS İç Cıvata · Manway</td></tr>
          <tr><td>Blow-Flask & Seviye</td><td>Yatay Ø${bf.diameter_mm ?? 600}×${bf.length_mm ?? 1800} mm (${bf.dump_volume_m3 ?? "-"} m³ dump) · 2 ayrı seviye şişesi (online izolasyonlu)</td></tr>
          <tr><td>Heat Tracing & Drenaj</td><td>İzolasyon + ≥ 2 °C elektrik ısıtma${ht.freeze_risk_active ? " ⚠️ Donma riski (< 2 °C)" : ""} · Atmosferik siklon + Flame Arrestor</td></tr>
          <tr><td>Giriş / Çıkış Çapı (L-103 / L-103A)</td><td>${escapeHtml(cyc.inlet_pipe_size || "-")} (${escapeHtml(cyc.inlet_velocity_ms ?? "-")} m/s) / ${escapeHtml(cyc.outlet_pipe_size || "-")} (${escapeHtml(cyc.outlet_velocity_ms ?? "-")} m/s)</td></tr>
        </table>
      </div>
    `;
  } else if (key === "cartridge_filters") {
    const flt = eq.cartridge_filters || {};
    const bf = flt.blow_flask || {};
    const ht = flt.heat_tracing || {};
    title = `CFS Kartuş Filtre Seperatörleri (${flt.configuration})`;
    content = `
      <div style="font-size: 11px; line-height: 1.5; color: var(--color-text);">
        <p><b>İşlev (Spec 5210 & Özel §4.8.2):</b> 2. kademede ≥ 3 µm katı partikülleri %99.8 ve ≥ 10 µm sıvı damlacıklarını tutarak türbin/kompresör çarkını korur; QOC kapak + Davit kolu ve gövde altı ısıtmalı Blow-Flask içerir.</p>
        <table class="kasp-table" style="font-size: 10px; margin: 8px 0;">
          <tr><td>Çalışma Modeli</td><td>${escapeHtml(flt.configuration || `${flt.operating_count} Çalışan + 1 Yedek`)} (%${flt.unit_capacity_pct ?? 50} birim kapasite)</td></tr>
          <tr><td>Filtreleme Hassasiyeti</td><td>${escapeHtml(flt.filter_efficiency_micron || "≥ 3 µm (%99.8 katı) · ≥ 10 µm (sıvı)")}</td></tr>
          <tr><td>Ünite Debisi & Eleman</td><td>${flt.flow_per_unit_kgs} kg/s (${flt.cartridge_elements_count ?? "-"} kartuş)</td></tr>
          <tr><td>Temiz / Değişim / Patlama ΔP</td><td>${flt.clean_dp_bar} bar (${flt.clean_dp_mbar ?? Math.round((flt.clean_dp_bar || 0) * 1000)} mbar · Temiz ≤ 140 mbar · Değişim 300 mbar · Patlama 3 bar)</td></tr>
          <tr><td>Kapak & Standart</td><td>${escapeHtml(flt.closure_type || "QOC + Davit")} · Ø${flt.vessel_diameter_mm ?? 1350}×${flt.vessel_length_mm ?? 4700} mm · ${escapeHtml(flt.design_code || "ASME VIII Div.1 CE")}</td></tr>
          <tr><td>Blow-Flask & Heat Tracing</td><td>Yatay Ø${bf.diameter_mm ?? 600}×${bf.length_mm ?? 1800} mm · İzolasyon Braket + ≥ 2 °C${ht.freeze_risk_active ? " ⚠️ Donma riski" : ""}</td></tr>
          <tr><td>Yedek & Enstrüman</td><td>${escapeHtml(flt.spare_sets_required || "3 set yedek filtre + 3 set kapak contası")} · PDT/PDI/PDSH & LG/LT/LSH/LSL</td></tr>
          <tr><td>Giriş / Çıkış Çapı (L-104 / L-104A)</td><td>${escapeHtml(flt.inlet_pipe_size || "-")} (${escapeHtml(flt.inlet_velocity_ms ?? "-")} m/s) / ${escapeHtml(flt.outlet_pipe_size || "-")} (${escapeHtml(flt.outlet_velocity_ms ?? "-")} m/s)</td></tr>
        </table>
      </div>
    `;
  } else if (key === "turbo_compressors") {
    const tc = eq.turbo_compressors || {};
    const fg = tc.fuel_gas_system || {};
    const dgs = tc.dry_gas_seal || {};
    const lo = tc.lube_oil_system || {};
    const uv = tc.unit_valves_and_strainer || {};
    const ai = tc.air_intake_and_enclosure || {};
    const unitFuelKgh = Number(fg.fuel_per_unit_kgh || 0);
    const unitFuelSm3h = Number(fg.fuel_per_unit_sm3h || convertFlowWithMW(unitFuelKgh, "kg/h", "Sm³/h", gasComp));
    const asvWarn = [
      ...(tc.anti_surge_valve_sizing_warnings || []),
      ...(tc.anti_surge_valve_sizing?.warnings || []),
      ...(tc.design_warnings || []),
    ];
    title = `Turbo-Kompresör Paketleri (${tc.configuration})`;
    content = `
      <div style="font-size: 11px; line-height: 1.5; color: var(--color-text);">
        <p><b>İşlev:</b> ${escapeHtml(ai.driver_type || "Endüstriyel gaz türbini")} + ${escapeHtml(ai.compressor_type || "API 617 santrifüj kompresör")} ana basınçlandırma trenleri.</p>
        <table class="kasp-table" style="font-size: 10px; margin: 8px 0;">
          <tr><td>Tren Başına Şaft Gücü</td><td>${tc.power_per_unit_kw.toLocaleString()} kW (${tc.power_per_unit_hp.toLocaleString()} HP)</td></tr>
          <tr><td>Tren Başına Gaz Debisi</td><td>${tc.flow_per_unit_kgs} kg/s · Politropik Verim %${tc.polytropic_efficiency_pct ?? "-"}</td></tr>
          <tr><td>ISO 6976 Yakıt Tüketimi / Tren</td><td>${unitFuelKgh.toFixed(1)} kg/h (~${unitFuelSm3h.toFixed(0)} Sm³/h · %120 Tasarım: ${Number(fg.design_fuel_per_unit_kgh || 0).toFixed(1)} kg/h)</td></tr>
          <tr><td>Isı Oranı & ISO 6976 LHV</td><td>${fg.heat_rate_kj_kwh || "-"} kJ/kWh (%${fg.thermal_efficiency_pct || 35} Verim) · LHV ${fg.lhv_kj_kg || "-"} kJ/kg</td></tr>
          <tr><td>Emiş / Basma Nozulu</td><td>${escapeHtml(tc.suction_nozzle_size_in)} / ${escapeHtml(tc.discharge_nozzle_size_in)}</td></tr>
          <tr><td>Ünite Vanaları & Geçici Strainer</td><td>2×MOV (≤${uv.motor_actuator_stroke_max_s || 30}s Fail-Close) + Seri Manuel + Geçici Konik Strainer + Non-Slam Çek</td></tr>
          <tr><td>Dry Gas Seal (API 692)</td><td>${escapeHtml(dgs.filter_config || "Duplex 1 µm")} · ${escapeHtml(dgs.control_mode || "PDCV")} · ${escapeHtml(dgs.separation_seal || "Carbon Seal")}</td></tr>
          <tr><td>Yağlama & Soğutma (Spec 4500 §6.7)</td><td>${lo.flow_lpm_per_unit || "-"} L/dk · Tank ≥5 dk (${lo.reservoir_min_working_volume_l || "-"} L, ≥51 cm²/L·dk) · 10 µm Duplex · 2-Fan Dış Soğutucu · UPS DC</td></tr>
          <tr><td>Türbin Hava Emiş & Marş</td><td>≤${ai.air_intake_clean_dp_max_mbar || 8} mbar temiz (7.5/12.5 mbar) · ${escapeHtml(ai.starter_system || "Ex-Proof 380V VFD")}</td></tr>
          <tr><td>Anti-Surge Valfi</td><td>ASV ${escapeHtml(tc.anti_surge_valve_size_in)}" (&lt; ${tc.anti_surge_stroke_time_s}s + Çek &amp; Blok Vana)</td></tr>
          ${tc.anti_surge_valve_sizing ? `<tr><td>ASV IEC 60534 Boyut</td><td>${escapeHtml(tc.anti_surge_valve_sizing.valve_inch)} • Cv ${Number(tc.anti_surge_valve_sizing.required_cv).toFixed(1)} • Açıklık %${Number(tc.anti_surge_valve_sizing.opening_percent).toFixed(1)} • EOS: ${escapeHtml((tc.anti_surge_valve_sizing.eos_model || "pr").toUpperCase())}</td></tr>` : ''}
          <tr><td>Yedek Parça Yükümlülüğü</td><td>2 set DGS + 2 set Yağ/Demister + 2 set Yakıt + 1 set/ünite Hava Emiş</td></tr>
        </table>
        ${renderDrawerWarnings(asvWarn, lang)}
      </div>
    `;
  } else if (key === "fuel_gas") {
    const fg = eq.fuel_gas || eq.turbo_compressors?.fuel_gas_system || {};
    title = `Yakıt Gazı Şartlandırma & Ölçüm Skidi (FG-101 · Spec 4500 §8.0)`;
    content = `
      <div style="font-size: 11px; line-height: 1.5; color: var(--color-text);">
        <p><b>Çekiş Konumu (Özel §4.8.5):</b> ${escapeHtml(fg.takeoff_location || "CFS Çıkışı Sonrası / Gaz Soğutucu Girişi Öncesi")}</p>
        <table class="kasp-table" style="font-size: 10px; margin: 8px 0;">
          <tr><td>ISO 6976:2016 LHV / HHV</td><td>${fg.lhv_kj_kg || "-"} / ${fg.hhv_kj_kg || "-"} kJ/kg (Wobbe ${fg.wobbe_index_mj_sm3 || "-"} MJ/Sm³)</td></tr>
          <tr><td>Toplam Yakıt (%100 / %120 Tasarım)</td><td>${fg.total_fuel_kgh || 0} kg/h (~${fg.total_fuel_sm3h || 0} Sm³/h) · Tasarım: ${fg.design_total_fuel_kgh || 0} kg/h</td></tr>
          <tr><td>Yakıt Seperatörü</td><td>${fg.separator_filtration_um || 1} µm (%${fg.separator_efficiency_pct || 99.8}) Yatay Sock + ≥${fg.separator_heat_tracing_min_c || 2} °C Blow-Flask</td></tr>
          <tr><td>Isıtma & Basınç Düşürme</td><td>${escapeHtml(fg.heat_exchanger_redundancy || "1+1 Eşanjör")} (${escapeHtml(fg.heat_exchanger_outlet_c || "20 ± 5 °C")}) · ${escapeHtml(fg.regulator_config || "2×100% Regülatör")}</td></tr>
          <tr><td>Malzeme & Yedek</td><td>${escapeHtml(fg.pipe_material || "316 SS")} · ${escapeHtml(fg.spare_sets_required || "2 set yedek")}</td></tr>
        </table>
      </div>
    `;
  } else if (key === "anti_surge") {
    const asvWarn = [
      ...(eq.turbo_compressors.anti_surge_valve_sizing_warnings || []),
      ...(eq.turbo_compressors.anti_surge_valve_sizing?.warnings || []),
    ];
    title = `Anti-Surge Geri Dönüş Döngüsü ve Hızlı ASV Valfi`;
    content = `
      <div style="font-size: 11px; line-height: 1.5; color: var(--color-text);">
        <p><b>İşlev:</b> Kompresörün surge bölgesine düşmesini engellemek için hızlı tepki süreli (&lt; ${eq.turbo_compressors.anti_surge_stroke_time_s}s) pnömatik valf ile basma gazını emişe yönlendirir; çıkışta çek vana + blok vana bulunur (Özel §4.8).</p>
        <table class="kasp-table" style="font-size: 10px; margin: 8px 0;">
          <tr><td>Vana Çapı</td><td>ASV ${escapeHtml(eq.turbo_compressors.anti_surge_valve_size_in)}" Hızlı Açılan Küresel/Kafesli Vana</td></tr>
          <tr><td>Stroking Süresi</td><td>&lt; ${eq.turbo_compressors.anti_surge_stroke_time_s} saniye (Tam Açılma)</td></tr>
          <tr><td>Surge Kontrol Sınırı</td><td>${eq.turbo_compressors.surge_limit_flow_kgs} kg/s</td></tr>
          <tr><td>Akustik İyileştirme</td><td>Gürültü ve titreşim önleyici kademeli difüzör trim</td></tr>
          ${eq.turbo_compressors.anti_surge_valve_sizing ? `<tr><td>IEC 60534 Kapasite</td><td>${escapeHtml(eq.turbo_compressors.anti_surge_valve_sizing.valve_inch)} • Cv ${Number(eq.turbo_compressors.anti_surge_valve_sizing.required_cv).toFixed(1)} • Gürültü ${Number(eq.turbo_compressors.anti_surge_valve_sizing.noise_db || 0).toFixed(1)} dB • EOS: ${escapeHtml((eq.turbo_compressors.anti_surge_valve_sizing.eos_model || "pr").toUpperCase())}</td></tr>` : ''}
        </table>
        ${renderDrawerWarnings(asvWarn, lang)}
      </div>
    `;
  } else if (key === "compressor_building") {
    title = "Kompresör Ünite Binası (Shelter)";
    content = `
      <div style="font-size: 11px; line-height: 1.5; color: var(--color-text);">
        <p><b>İşlev:</b> Ağır hizmet tipi akustik yalıtımlı ünite binası tüm turbo-kompresör trenlerini barındırır.</p>
        <table class="kasp-table" style="font-size: 10px; margin: 8px 0;">
          <tr><td>Boyutlar (G x U x Y)</td><td>${eq.compressor_building.width_m} x ${eq.compressor_building.length_m} x ${eq.compressor_building.height_m} m</td></tr>
          <tr><td>Toplam Taban Alanı</td><td>${eq.compressor_building.area_m2} m²</td></tr>
          <tr><td>Tavan Vinci</td><td>${eq.compressor_building.crane_capacity_tons} Ton Gezer Vinç (Dinamik Güç Ölçekli)</td></tr>
          <tr><td>Akustik İzolasyon</td><td>${escapeHtml(eq.compressor_building.acoustic_attenuation_dba)}</td></tr>
          <tr><td>Kabin Havalandırma</td><td>≤ ${eq.compressor_building.enclosure_max_temp_c || 80} °C · UPS 400VAC/DC Acil Soğutma Fanları</td></tr>
          <tr><td>Emniyet Sistemleri</td><td>${escapeHtml(eq.compressor_building.fire_and_gas_system || "Gaz Algılama (%10/%20 LEL), CO2 / Inergen Söndürme")}</td></tr>
        </table>
      </div>
    `;
  } else if (key === "station_recycle") {
    const recycleSize = eq.station_recycle.pipe_size || '48"';
    const pcvWarn = [
      ...(eq.station_recycle.pcv_sizing_warnings || []),
      ...(eq.station_recycle.pcv_sizing?.warnings || []),
    ];
    title = `${recycleSize} Anti-Surge / Recycle Header (Note 13)`;
    content = `
      <div style="font-size: 11px; line-height: 1.5; color: var(--color-text);">
        <p><b>İşlev:</b> Kompresör anti-surge (ASV) çıkışlarını toplayıp emiş kolektörüne döndürür; aynı zamanda istasyon recycle/purge hattı olarak çalışır.</p>
        <table class="kasp-table" style="font-size: 10px; margin: 8px 0;">
          <tr><td>Boru Çapı</td><td>${escapeHtml(recycleSize)} Station Recycle (Note 13 Purge'den Ayrı)</td></tr>
          <tr><td>Maks. Sirkülasyon</td><td>${eq.station_recycle.max_recirculation_capacity_kgs} kg/s</td></tr>
          <tr><td>Vana &amp; Hat İçi NRV</td><td>PCV Kademeli Trim + Hat İçi NRV Çekvalf + 2× Blok Vana + Akustik Kabin</td></tr>
          <tr><td>Power-Gas Tüpü</td><td>Ayrı Power-Gas Aktüatör Tüpü (316 SS · 20–30 s · Fail-Closed)</td></tr>
          ${eq.station_recycle.pcv_sizing ? `<tr><td>PCV IEC 60534 Boyut</td><td>${escapeHtml(eq.station_recycle.pcv_sizing.valve_inch)} • Cv ${Number(eq.station_recycle.pcv_sizing.required_cv).toFixed(1)} • Açıklık %${Number(eq.station_recycle.pcv_sizing.opening_percent).toFixed(1)} • EOS: ${escapeHtml((eq.station_recycle.pcv_sizing.eos_model || "pr").toUpperCase())}</td></tr>` : ''}
        </table>
        ${renderDrawerWarnings(pcvWarn, lang)}
      </div>
    `;
  } else if (key === "cooler_bypass") {
    const tcvWarn = [
      ...(eq.air_coolers.cooler_bypass_valve_sizing_warnings || []),
      ...(eq.air_coolers.cooler_bypass_valve_sizing?.warnings || []),
    ];
    title = "Gas Cooler By-Pass Hattı (TCV - Note 17)";
    content = `
      <div style="font-size: 11px; line-height: 1.5; color: var(--color-text);">
        <p><b>İşlev:</b> Soğuk kış aylarında veya düşük debide VFD fanlar minimum devirde dahi gazı aşırı soğutursa, termostatik ON/OFF TCV açılarak sıcak basma gazını soğuk çıkışla karıştırır.</p>
        <table class="kasp-table" style="font-size: 10px; margin: 8px 0;">
          <tr><td>Vana &amp; Aktüatör Tipi</td><td>Termostatik ON/OFF Baypas · Gas-over-Oil Hidrolik · Fail-Open (4500 §5.14)</td></tr>
          <tr><td>Baypas Boru Çapı</td><td>${escapeHtml(eq.air_coolers.bypass_line?.pipe_size || '-')} (ASME B36.10M)</td></tr>
          <tr><td>Birincil Kontrol</td><td>Forced-Draft VFD Fanlar (IEEE 519 · SCS 4-20 mA)</td></tr>
          <tr><td>İkincil Kontrol</td><td>TCV Sıcak Gaz Karıştırma Baypası (Sinyal Kaybında Fail-Open)</td></tr>
          ${eq.air_coolers.cooler_bypass_valve_sizing ? `<tr><td>TCV IEC 60534 Boyut</td><td>${escapeHtml(eq.air_coolers.cooler_bypass_valve_sizing.valve_inch)} • Cv ${Number(eq.air_coolers.cooler_bypass_valve_sizing.required_cv).toFixed(1)} • Açıklık %${Number(eq.air_coolers.cooler_bypass_valve_sizing.opening_percent).toFixed(1)} • EOS: ${escapeHtml((eq.air_coolers.cooler_bypass_valve_sizing.eos_model || "pr").toUpperCase())}</td></tr>` : ''}
        </table>
        ${renderDrawerWarnings(tcvWarn, lang)}
      </div>
    `;
  } else if (key === "condensate_system") {
    const cond = eq.condensate_system || {};
    title = "Kondensat Toplama ve Depolama Sistemi (Spec 5250 / DIN 6608)";
    content = `
      <div style="font-size: 11px; line-height: 1.5; color: var(--color-text);">
        <p><b>İşlev:</b> MFS &amp; CFS blow-flask'larından gelen sıvıyı atmosferik siklon üzerinden DIN 6608 / St37 gömülü tankta toplar.</p>
        <table class="kasp-table" style="font-size: 10px; margin: 8px 0;">
          <tr><td>Tank Hacmi &amp; Standart</td><td><b>${cond.collection_tank_volume_m3 || 15} m³</b> (${escapeHtml(cond.design_standard || "DIN 6608 / St37")} · Baz ${cond.spec_5250_base_tank_m3 || 5} m³ · 15×=${cond.min_15x_blowflask_m3 || 3} m³ · 2 bar Test)</td></tr>
          <tr><td>Ex-Proof Dalgıç Pompa</td><td>${cond.pump_flow_m3h || 10}±20% m³/h @ ${cond.pump_head_m || 5} m (${cond.pump_motor_kw || 4} kW · Spec 4190)</td></tr>
          <tr><td>Enstrüman &amp; Kaplama</td><td>${escapeHtml(cond.instrumentation || "LI/LSL/LSH + Alev Tutucu")} • ${escapeHtml(cond.coating || "İç Sentetik + Kömür Katranı Epoksi")}</td></tr>
        </table>
      </div>
    `;
  } else if (key === "air_coolers") {
    const acWarn = [
      ...(eq.air_coolers.design_warnings || eq.air_coolers.detailed_design_warnings || []),
      ...(eq.air_coolers.cooler_bypass_warnings || eq.air_coolers.cooler_bypass_valve_sizing_warnings || []),
    ];
    title = `Hava Soğutucuları (${eq.air_coolers.bay_count} Fin-Fan Bay)`;
    content = `
      <div style="font-size: 11px; line-height: 1.5; color: var(--color-text);">
        <p><b>İşlev:</b> Kompresörden çıkan sıcak doğal gazı (${eq.air_coolers.inlet_temp_c}°C) kullanıcı maks. çıkış sınırına (${eq.air_coolers.outlet_temp_c}°C) soğutur.</p>
        <table class="kasp-table" style="font-size: 10px; margin: 8px 0;">
          <tr><td>Toplam Isıl Yük &amp; LMTD</td><td>${eq.air_coolers.total_heat_duty_mw} MWth • LMTD: ${eq.air_coolers.lmtd_c ?? "-"} °C</td></tr>
          <tr><td>Gaz Giriş (= Kompresör Çıkış)</td><td><b>${eq.air_coolers.inlet_temp_c}°C</b> (${eq.air_coolers.compressor_outlet_coupled ? "✓ Doğrulandı" : "-"})</td></tr>
          <tr><td>Maks. Gaz Çıkış Sınırı / Gerçek Çıkış</td><td>${eq.air_coolers.requested_max_outlet_temp_c ?? eq.air_coolers.outlet_temp_c}°C → <b>${eq.air_coolers.outlet_temp_c}°C</b></td></tr>
          <tr><td>Soğutma Havası Giriş / Çıkış</td><td>${eq.air_coolers.air_inlet_temp_c ?? 15}°C → ${eq.air_coolers.air_outlet_temp_c ?? 30}°C</td></tr>
          <tr><td>Fan Modülü &amp; Tahrik</td><td>${eq.air_coolers.total_fans} Adet Forced-Draft VFD (IEEE 519 · ≥%95 Verim · ≤${eq.air_coolers.max_fan_tip_speed_ms ?? 50} m/s · ≤${eq.air_coolers.fan_motor_max_kw ?? 29.8} kW)</td></tr>
          <tr><td>Dinamik Tüp Demeti ΔP</td><td><b>${eq.air_coolers.pressure_drop_bar} bar</b> (İzin ≤${eq.air_coolers.tube_bundle?.allowable_dp_bar ?? 0.50} bar · v=${eq.air_coolers.tube_bundle?.tube_velocity_ms ?? "-"} m/s · 12 BWG)</td></tr>
          <tr><td>Güvenlik &amp; Güneşlik</td><td>Murphy Titreşim Stop · 2.0 mm Ekstrüde Alüminyum Panjur · Kilitli Manuel İzolasyon + 1" Vent/Drenaj</td></tr>
          ${eq.air_coolers.cooler_bypass_valve_sizing ? `<tr><td>TCV Boyut</td><td>${escapeHtml(eq.air_coolers.cooler_bypass_valve_sizing.valve_inch)} • Cv ${Number(eq.air_coolers.cooler_bypass_valve_sizing.required_cv).toFixed(1)}</td></tr>` : ''}
        </table>
        ${renderDrawerWarnings(acWarn, lang)}
        <button id="btn-detailed-air-cooler" class="btn btn-sm btn-primary" style="margin-top: 6px;">${escapeHtml(t("station_inspector_api661", lang))}</button>
        <div id="air-cooler-detail" style="margin-top: 8px;"></div>
      </div>
    `;
  } else if (key === "safety_relief") {
    const psv = eq.safety_relief_and_blowdown || {};
    const psvSizing = psv.psv_sizing || null;
    const psvWarn = [
      ...(psv.psv_sizing_warnings || []),
      ...(psvSizing?.warnings || []),
    ];
    title = `PSV Emniyet Tahliye Vanaları (PSV-101..10${psv.psv_count || 2} • API 520 / 526)`;
    content = `
      <div style="font-size: 11px; line-height: 1.5; color: var(--color-text);">
        <p><b>İşlev:</b> Gaz soğutucu çıkışı basma kollektörü üzerinde dikey yükselen (riser) API 520/526 emniyet tahliye vanaları.</p>
        <table class="kasp-table" style="font-size: 10px; margin: 8px 0;">
          <tr><td>PSV Ayar Basıncı</td><td>${psv.psv_set_pressure_bar} bar(g) (%${psv.psv_overpressure_pct || 10} aşırı basınç)</td></tr>
          <tr><td>Tasarım Sekmesi P_atm &amp; T_atm</td><td>${Number(psv.ambient_pressure_bar || 1.01325).toFixed(4)} bar(a) • ${psv.ambient_temp_c ?? 15}°C (Karşı P: ${Number(psv.psv_back_pressure_bar || 1.01325).toFixed(4)} bar a)</td></tr>
          <tr><td>Kurulu / Eşzamanlı PSV Sayısı</td><td>${psv.psv_count || 2} Adet (${psv.psv_duty_count || 1} Duty + ${Math.max(0, (psv.psv_count || 2) - (psv.psv_duty_count || 1))} Standby)</td></tr>
          <tr><td>Yerleşim &amp; Özel Şartname</td><td>Binalara ≥35 m · Choke Flow · Dual-Outlet Flanşlı · 2" Pilot + Snubber + Field Test (4500 §5.10 / Özel p.32)</td></tr>
          ${psvSizing ? `
          <tr><td>Gerekli Alan (Toplam / Vana Başına)</td><td>${Number(psvSizing.required_area_total_sqin || psvSizing.required_area_sqin).toFixed(3)} in² / ${Number(psvSizing.required_area_sqin).toFixed(3)} in² (Ø${Number(psvSizing.required_diameter_in || 0).toFixed(2)}")</td></tr>
          <tr><td>Seçilen API 526 Orifis &amp; Flanş</td><td>${escapeHtml(psvSizing.selected_orifice || '-')} (${Number(psvSizing.selected_orifice_area_sqin || 0).toFixed(3)} in² • ${escapeHtml(psvSizing.inlet_flange_in || '8"')} × ${escapeHtml(psvSizing.outlet_flange_in || '10"')})</td></tr>
          <tr><td>Atmosferik Vent Çıkış Hızı</td><td>${Number(psvSizing.vent_exit_velocity_ms || 0).toFixed(1)} m/s @ ρ_atm=${Number(psvSizing.atm_gas_density_kgm3 || 0).toFixed(3)} kg/m³</td></tr>
          <tr><td>Önerilen Min. PSV Sayısı</td><td>${psvSizing.recommended_duty_count || 1} Duty (Toplam ${psvSizing.recommended_total_count || 2})</td></tr>
          ` : ''}
        </table>
        ${renderDrawerWarnings(psvWarn, lang)}
      </div>
    `;
  } else if (key === "esd_valves") {
    const esd = eq.esd_sizing || {};
    const suct = esd.suction || {};
    const disch = esd.discharge || {};
    const esdWarn = esd.warnings || [];
    title = `ESD / BDV Acil Kapatma ve Boşaltma Vanaları (ESD-101..10${esd.esd_count || 2} • IEC 60534 / API 521)`;
    content = `
      <div style="font-size: 11px; line-height: 1.5; color: var(--color-text);">
        <p><b>İşlev:</b> Yüksek basınç (P_out) ve düşük basınç (P_in) borulama hacimlerini tasarım atmosfer şartlarına boşaltan BDV ve ana hat ESD vanaları.</p>
        <table class="kasp-table" style="font-size: 10px; margin: 8px 0;">
          <tr><td>Tasarım Sekmesi P_atm &amp; T_atm</td><td>${Number(esd.ambient_pressure_bar || 1.01325).toFixed(4)} bar(a) • ${esd.ambient_temp_c ?? 15}°C • Süre: ${esd.depressurization_time_min || 15} dk</td></tr>
          <tr><td>YB Hacim (@ P_out = ${disch.upstream_pressure_bar ?? sm.discharge_pressure_bar} bar a)</td><td><b>${esd.esd_hp_volume_m3 ?? 50} m³</b> • Envanter: ${disch.gas_inventory_kg ?? "-"} kg • Boşaltma: ${disch.blowdown_mass_flow_total_kgs ?? disch.flow_per_valve_kgs} kg/s</td></tr>
          <tr><td>DB Hacim (@ P_in = ${suct.upstream_pressure_bar ?? sm.suction_pressure_bar} bar a)</td><td><b>${esd.esd_lp_volume_m3 ?? 40} m³</b> • Envanter: ${suct.gas_inventory_kg ?? "-"} kg • Boşaltma: ${suct.blowdown_mass_flow_total_kgs ?? suct.flow_per_valve_kgs} kg/s</td></tr>
          <tr><td>YB ESD/BDV Hesaplanan / Hat Çapı</td><td><b>${escapeHtml(disch.calculated_size_in || '-')}"</b> (DN${escapeHtml(disch.calculated_dn_mm || '-')}) / Hat: ${escapeHtml(disch.selected_size_in || '-')}" • Cv ${Number(disch.required_cv || 0).toFixed(1)}</td></tr>
          <tr><td>DB ESD/BDV Hesaplanan / Hat Çapı</td><td><b>${escapeHtml(suct.calculated_size_in || '-')}"</b> (DN${escapeHtml(suct.calculated_dn_mm || '-')}) / Hat: ${escapeHtml(suct.selected_size_in || '-')}" • Cv ${Number(suct.required_cv || 0).toFixed(1)}</td></tr>
          <tr><td>Kurulu / Önerilen Aktif Sayı</td><td>${esd.esd_count || 2} Kurulu (${esd.esd_duty_count || 1} Aktif • Önerilen: ${disch.recommended_duty_count || 1})</td></tr>
          <tr><td>Spec 4500 §5.11 ESD Şartı</td><td>Binalara ≥35 m · 1 barg ≤60 s (${eq.station_utilities?.safety_and_bypass?.bdv_4500?.esd_60s_compliant ? "✓ UYGUN" : `Mevcut ${esd.depressurization_time_min ?? 15} dk`}) · Yağlamalı Plug · Gas-over-Oil Fail-Open</td></tr>
        </table>
        ${renderDrawerWarnings(esdWarn, lang)}
      </div>
    `;
  } else if (key === "ultrasonic_meter") {
    const usm = eq.ultrasonic_meter || {};
    title = `${usm.tag || "FT-401"} • Ultrasonic Gas Flow Meter (AGA Report No. 9)`;
    content = `
      <div style="font-size: 11px; line-height: 1.5; color: var(--color-text);">
        <p><b>İşlev:</b> Gaz soğutucu ve emniyet manifoldu sonrasında istasyon çıkış gaz debisini 8-path chordal ultrasonik teknolojiyle ölçer.</p>
        <table class="kasp-table" style="font-size: 10px; margin: 8px 0;">
          <tr><td>Sayaç Çapı &amp; Tipi</td><td>${escapeHtml(usm.nominal_size_in || '40"')} • ${escapeHtml(usm.meter_type || '8-Path Chordal AGA-9')}</td></tr>
          <tr><td>Kütlesel / Gerçek Hacimsel Debi</td><td>${usm.mass_flow_kgs || sm.total_mass_flow_kgs} kg/s • ${usm.actual_volumetric_flow_m3h || '-'} m³/h (ACMH)</td></tr>
          <tr><td>Gaz Hızı &amp; Ses Hızı</td><td>${usm.gas_velocity_ms || '-'} m/s • Ses Hızı: ${usm.speed_of_sound_ms || '-'} m/s</td></tr>
          <tr><td>Doğruluk &amp; Düz Boru Mesafesi</td><td>${escapeHtml(usm.accuracy_class || '±0.15%')} • ${escapeHtml(usm.straight_run_requirement || '10D / 5D')}</td></tr>
        </table>
      </div>
    `;
  } else if (key === "pig_launcher") {
    title = "Pig Atıcı (Discharge Pig Launcher - PIG-L)";
    content = `
      <div style="font-size: 11px; line-height: 1.5; color: var(--color-text);">
        <p><b>İşlev:</b> Basınçlandırılmış ve soğutulmuş gaz iletim hattına akıllı pig araçlarını fırlatır.</p>
        <table class="kasp-table" style="font-size: 10px; margin: 8px 0;">
          <tr><td>Kovan Ölçüsü</td><td>PIG-L-56"x48" (ANSI Class 900)</td></tr>
          <tr><td>İşletme Basıncı</td><td>${sm.discharge_pressure_bar} bar(a)</td></tr>
          <tr><td>Sinyal Verici</td><td>Manyetik Pinger & Geçiş Dedektörü</td></tr>
        </table>
      </div>
    `;
  } else if (key === "station_suction_valve" || key === "station_discharge_valve") {
    const sv = key === "station_suction_valve" ? (eq.station_suction_valve || {}) : (eq.station_discharge_valve || {});
    title = `${sv.tag || (key === "station_suction_valve" ? "SV-IN" : "SV-OUT")} — ${sv.name || "İstasyon Yan Vanası"}`;
    content = `
      <div style="font-size: 11px; line-height: 1.5; color: var(--color-text);">
        <p><b>İşlev:</b> İstasyon emiş/basma tarafını ana iletim hattından izole eden ESD kontrollü tam geçişli yan vanadır (4500 §5.4 / Özel §5.4).</p>
        <table class="kasp-table" style="font-size: 10px; margin: 8px 0;">
          <tr><td>Standart</td><td>${escapeHtml(sv.standard || "API 6D QSL 2 · Block & Bleed Küresel Vana")}</td></tr>
          <tr><td>Aktüatör &amp; Fail-Safe</td><td>${escapeHtml(sv.actuator || "Gas-over-Oil")} • <b>${escapeHtml(sv.fail_action || "Fail-Closed")}</b></td></tr>
          <tr><td>ΔP Kilidi</td><td>${escapeHtml(sv.dp_interlock || "0.5–4.0 barg ayarlanabilir")}</td></tr>
          <tr><td>Gövde Vent / Yağlama</td><td>${escapeHtml(sv.body_vent_class || "1500 Class küresel + sürgülü vana")}</td></tr>
        </table>
      </div>
    `;
  } else if (key === "mainline_block_valve") {
    const ml = eq.mainline_block_valve || {};
    title = `${ml.tag || "MLBV-101"} — Ana Hat Blok Vanası (4500 §5.4)`;
    content = `
      <div style="font-size: 11px; line-height: 1.5; color: var(--color-text);">
        <p><b>İşlev:</b> PIG-R ve PIG-L arasındaki ana hat izolasyon vanasıdır; istasyon devre dışıyken ana hat akışını sürdürür.</p>
        <table class="kasp-table" style="font-size: 10px; margin: 8px 0;">
          <tr><td>Aktüatör &amp; Fail-Safe</td><td>${escapeHtml(ml.actuator || "Gas-over-Oil")} • <b>${escapeHtml(ml.fail_action || "Fail-Open")}</b></td></tr>
          <tr><td>ΔP Kilidi</td><td>${escapeHtml(ml.dp_interlock || "0.5–4.0 barg ayarlanabilir")}</td></tr>
          <tr><td>Yerleşim</td><td>${escapeHtml(ml.pit_installation || "Vent & drenajlı vana çukuru (Özel §5.4)")}</td></tr>
        </table>
      </div>
    `;
  } else if (key === "station_loading_line") {
    const ld = eq.station_loading_line || {};
    title = `${ld.tag || "LV-101/102"} — İstasyon Dolum Hattı ve Vanaları (4500 §5.12)`;
    content = `
      <div style="font-size: 11px; line-height: 1.5; color: var(--color-text);">
        <p><b>İşlev:</b> İstasyon giriş yan vanası (SV-IN) etrafında bypass kurarak istasyonu kontrollü basınçlandırır.</p>
        <table class="kasp-table" style="font-size: 10px; margin: 8px 0;">
          <tr><td>Memba Vanası</td><td>${escapeHtml(ld.upstream_valve || "Flanşlı Küresel Vana")}</td></tr>
          <tr><td>Mansap Vanası</td><td>${escapeHtml(ld.downstream_valve || "Flanşlı Globe Vana · Kapalı Limit Switch Alarmı")}</td></tr>
          <tr><td>Uzaktan Kontrol</td><td>${ld.remote_control_ozel_5_4 ? "Aktif (Özel §5.4 uzaktan açma-kapama)" : "Manuel"}</td></tr>
        </table>
      </div>
    `;
  } else if (key === "station_bypass_valve") {
    const bp = eq.station_bypass_valve || {};
    title = `${bp.tag || "NRV-BP-101"} — İstasyon By-Pass Hattı &amp; Non-Slam Çekvalf (4500 §5.13)`;
    content = `
      <div style="font-size: 11px; line-height: 1.5; color: var(--color-text);">
        <p><b>İşlev:</b> İstasyon kapalıyken veya ani duruşta gazın soğutucu sonrası / USM öncesi hattan serbest geçişini sağlar.</p>
        <table class="kasp-table" style="font-size: 10px; margin: 8px 0;">
          <tr><td>Vana Tipi</td><td>${escapeHtml(bp.valve_type || "Piston / Nozul Non-Slam Çekvalf")}</td></tr>
          <tr><td>Bağlantı Yeri</td><td>${escapeHtml(bp.tie_in_location || "Discharge (Soğutucu sonrası, USM öncesi) ↔ Suction")}</td></tr>
          <tr><td>Çap</td><td>${escapeHtml(bp.nominal_size || '48"')}</td></tr>
        </table>
      </div>
    `;
  } else if (key === "control_building") {
    title = "Merkezi Kontrol ve Yardımcı Tesisler Binası (Control Building)";
    content = `
      <div style="font-size: 11px; line-height: 1.5; color: var(--color-text);">
        <p><b>İşlev:</b> İstasyonun tüm DCS, SCADA, acil durdurma (ESD), yangın/gaz algılama ve elektrik dağıtım merkezidir.</p>
        <table class="kasp-table" style="font-size: 10px; margin: 8px 0;">
          <tr><td>Kontrol Sistemi</td><td>Yedekli DCS & SCADA Sunucuları</td></tr>
          <tr><td>Emniyet Seviyesi</td><td>IEC 61508 / 61511 SIL-3 Emniyet PLC</td></tr>
          <tr><td>Kesintisiz Güç (UPS)</td><td>2 x %100 Statik UPS & Akü Grubu (4 Saat Otonomi)</td></tr>
          <tr><td>Yangın & Gaz (F&G)</td><td>%20 LEL IR Dedektörler, UV/IR Alev Algılama</td></tr>
          <tr><td>İklimlendirme</td><td>Ex-Proof Pozitif Basınçlı Havalandırma (HVAC)</td></tr>
        </table>
      </div>
    `;
  } else if (key === "generator_building") {
    title = "Acil Durum Jeneratör ve O.G. Şalt Binası";
    content = `
      <div style="font-size: 11px; line-height: 1.5; color: var(--color-text);">
        <p><b>İşlev:</b> Şebeke enerjisi kesildiğinde kritik enstrümantasyon, yağlama pompaları ve emniyet sistemlerinin enerjisini sağlar.</p>
        <table class="kasp-table" style="font-size: 10px; margin: 8px 0;">
          <tr><td>Jeneratör Tipi</td><td>Dizel Motor Tahrikli Standby Acil Durum Genset</td></tr>
          <tr><td>Gerilim Seviyesi</td><td>6.6 kV Orta Gerilim / 400 V Alçak Gerilim Baraları</td></tr>
          <tr><td>Transfer Süresi (ATS)</td><td>&lt; 15 Saniye Otomatik Şebeke Transferi</td></tr>
        </table>
      </div>
    `;
  } else if (key === "air_compressor_building" || key === "station_utilities") {
    const util = eq.station_utilities || {};
    const ca = util.compressed_air || {};
    const ug = util.utility_gas || {};
    const pg = util.power_gas || {};
    const hg = util.heating_glycol || {};
    const sb = util.safety_and_bypass || {};
    title = key === "station_utilities"
      ? "İstasyon Yardımcı Sistemleri (UTIL-101..401)"
      : "Basınçlı Hava ve Enstrüman Servis Binası (4320 / 4330)";
    content = `
      <div style="font-size: 11px; line-height: 1.5; color: var(--color-text);">
        <p><b>İşlev:</b> Power Gas (Metanol Dehidratör), Kullanım Gazı Skidi (Özel §4.8.6), Enstrüman Havası (-40 °C) ve 90/70 °C Glikol Isıtma sistemleri.</p>
        <table class="kasp-table" style="font-size: 10px; margin: 8px 0;">
          <tr><td>Basınçlı Hava &amp; Kompresör</td><td>${ca.demand_nm3h ?? "-"} Nm³/h • ${escapeHtml(ca.compressor_configuration || "1+1 %100 VFD Eş-Yaşlandırma")}</td></tr>
          <tr><td>Kurutucu &amp; ASME/CE Tank</td><td>${escapeHtml(ca.dryers || "-")} • Tank: <b>${ca.receiver_volume_m3 ?? 25} m³</b> (≥${ca.holdup_time_min ?? 10} dk) • ≥304 SS</td></tr>
          <tr><td>Kullanım Gazı Skidi</td><td>Çekiş: ${escapeHtml(ug.takeoff_location || "Gas Cooler Girişi")} • <b>${ug.calculated_demand_sm3h ?? 1485} Sm³/h</b> (Min 1485) • Harici MCC Isıtıcı + Odorizer + PE</td></tr>
          <tr><td>Power Gas &amp; Metanol</td><td>${pg.design_pressure_bar ?? "-"} bar(g) (%110 MAOP) • Hammerschmidt ΔT=${pg.methanol_dehydrator?.hammerschmidt_depression_c ?? "-"} °C • 1" Drop / 1/2" SS</td></tr>
          <tr><td>Glikol Isıtma &amp; Bypass</td><td>${hg.heat_load_kw ?? "-"} kWth (${escapeHtml(hg.medium || "90/70 °C %50 Glikol")}) • ${escapeHtml(sb.station_bypass_check || "4500 §5.13 Check Bypass")}</td></tr>
        </table>
      </div>
    `;
  } else if (key === "fire_water") {
    const fw = eq.station_utilities?.fire_water || {};
    title = "Yangın Suyu, F&G Algılama & Söndürme Sistemi (4500 §14)";
    content = `
      <div style="font-size: 11px; line-height: 1.5; color: var(--color-text);">
        <p><b>İşlev:</b> İstasyon yangın ring hidrant ağı, gaz/alev algılama ve türbin muhafaza otomatik söndürme sistemini besler.</p>
        <table class="kasp-table" style="font-size: 10px; margin: 8px 0;">
          <tr><td>Depolama Tankı</td><td><b>${fw.tank_volume_m3 ?? 300} m³</b> Yangın Suyu Tankı</td></tr>
          <tr><td>Pompa Grubu</td><td>${escapeHtml(fw.pumps || "NFPA 20: 1 Elektrikli + 1 Dizel + Jockey")}</td></tr>
          <tr><td>F&amp;G &amp; CO2 Söndürme</td><td>${escapeHtml(fw.turbine_enclosure_suppression || "Otomatik CO2")} • ${escapeHtml(fw.ring_main_hydrants || "%20 LEL IR / UV-IR")}</td></tr>
        </table>
      </div>
    `;
  } else if (key === "admin_building") {
    title = "İdari Yönetim ve Bakım Atölyesi Binası";
    content = `
      <div style="font-size: 11px; line-height: 1.5; color: var(--color-text);">
        <p><b>İşlev:</b> Saha mühendislik ofisleri, mekanik/elektrik bakım atölyeleri ve yedek parça ambarıdır.</p>
        <table class="kasp-table" style="font-size: 10px; margin: 8px 0;">
          <tr><td>Birimler</td><td>Mühendislik Odaları, Mekanik Atölye, Kalibrasyon Lab.</td></tr>
          <tr><td>Atölye Vinci</td><td>3 Tonluk Gezer Köprülü Vinç</td></tr>
        </table>
      </div>
    `;
  } else if (key === "guard_shelter") {
    title = "Tesis Ana Güvenlik & Giriş Nizamiyesi";
    content = `
      <div style="font-size: 11px; line-height: 1.5; color: var(--color-text);">
        <p><b>İşlev:</b> Saha giriş-çıkış emniyeti, CCTV çevre güvenliği ve personel geçiş kontrolüdür.</p>
        <table class="kasp-table" style="font-size: 10px; margin: 8px 0;">
          <tr><td>Güvenlik Standardı</td><td>BOTAŞ Kritik Tesis Çevre Güvenlik Standardı</td></tr>
          <tr><td>Giriş Kontrolü</td><td>Otomatik Bariyer + CCTV Plaka Tanıma Sistemi</td></tr>
        </table>
      </div>
    `;
  }

  return `
    <div class="station-inspector-card${viewMode !== "2d" ? " station-inspector-docked" : ""}">
      <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--color-border); padding-bottom: 8px; margin-bottom: 10px;">
        <div style="font-size: 12px; font-weight: 700; color: var(--color-primary);">${escapeHtml(title)}</div>
        <button id="btn-close-inspector" class="btn btn-sm btn-icon" style="padding: 2px;" aria-label="${escapeHtml(t("station_inspector_close", lang))}" title="${escapeHtml(t("station_inspector_close", lang))}">${icon("x", 12)}</button>
      </div>
      ${content}
    </div>
  `;
}

/**
 * Renders the full-screen BOTAŞ Adapazarı PFD & 3D CAD Reference Gallery lightbox modal.
 */
function renderBotasPfdModal(lang = "tr") {
  return `
    <div class="kasp-modal-backdrop" id="botas-pfd-backdrop" style="z-index: 1000; background: rgba(0, 0, 0, 0.85);">
      <div class="kasp-modal" role="dialog" aria-modal="true" style="width: 95vw; height: 92vh; max-width: 98vw; max-height: 96vh; display: flex; flex-direction: column; background: var(--color-surface);">
        
        <!-- Modal Header -->
        <div class="kasp-modal-header" style="display: flex; justify-content: space-between; align-items: center; padding: 12px 20px; border-bottom: 1px solid var(--color-border);">
          <div style="display: flex; align-items: center; gap: 10px;">
            ${icon("fileText", 20, "text-primary")}
            <div>
              <h3 style="margin: 0; font-size: 14px; font-weight: 700;">${escapeHtml(t("station_pfd_modal_title", lang))}</h3>
              <div style="font-size: 11px; color: var(--color-text-secondary);">
                Doküman No: <b>0-NGTL0-CS-I-001-4000</b> • BOTAŞ / Kontrolmatik Mühendislik • 3D Navisworks / Plant 3D &amp; PFD
              </div>
            </div>
          </div>
          <button id="btn-close-pfd-modal" class="btn btn-sm btn-icon" aria-label="${escapeHtml(t("station_pfd_close", lang))}">${icon("x", 16)}</button>
        </div>

        <!-- Drawing & 3D CAD Gallery View (Scrollable) -->
        <div style="flex: 1; overflow: auto; padding: 16px; background: #0b0f19; display: flex; flex-direction: column; gap: 18px; align-items: center;">
          <div style="width: 100%; max-width: 1400px;">
            <div style="color: #38bdf8; font-size: 13px; font-weight: 700; margin-bottom: 8px;">1. 3D CAD Referans Görünümleri (MFS, CFS, Gas Cooler, COMPRESSOR-01..05, 7.0m Yol &amp; Kontrol Binaları)</div>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(420px, 1fr)); gap: 12px;">
              <img src="/static/vendor/cad_ref_2.jpg" alt="3D CAD Vaziyet Planı" style="width: 100%; border-radius: 6px; border: 1px solid rgba(255,255,255,0.15);" />
              <img src="/static/vendor/cad_ref_3.jpg" alt="3D CAD Genel İzometrik" style="width: 100%; border-radius: 6px; border: 1px solid rgba(255,255,255,0.15);" />
              <img src="/static/vendor/cad_ref_1.jpg" alt="3D CAD Proses Sahası" style="width: 100%; border-radius: 6px; border: 1px solid rgba(255,255,255,0.15);" />
              <img src="/static/vendor/cad_ref_4.jpg" alt="3D CAD COMPRESSOR-04 İç Kesit" style="width: 100%; border-radius: 6px; border: 1px solid rgba(255,255,255,0.15);" />
              <img src="/static/vendor/cad_ref_5.jpg" alt="3D CAD Kolektör ve Ünite Binaları" style="width: 100%; border-radius: 6px; border: 1px solid rgba(255,255,255,0.15);" />
            </div>
          </div>

          <div style="width: 100%; max-width: 1400px;">
            <div style="color: #34d399; font-size: 13px; font-weight: 700; margin-bottom: 8px;">2. Proses Akış Diyagramı (PFD — 0-NGTL0-CS-I-001-4000)</div>
            <img src="/static/vendor/pfd_reference.png" alt="BOTAŞ Adapazarı PFD Referansı" style="max-width: 100%; height: auto; border-radius: 6px; box-shadow: 0 4px 20px rgba(0,0,0,0.5);" />
          </div>
        </div>

        <!-- Modal Footer -->
        <div class="kasp-modal-footer" style="padding: 10px 20px; border-top: 1px solid var(--color-border); display: flex; justify-content: space-between; align-items: center; background: var(--color-surface); font-size: 11px; color: var(--color-text-secondary);">
          <div style="display: flex; gap: 12px; align-items: center; flex-wrap: wrap;">
            <span style="font-weight: 600; color: var(--color-primary);">Doğrulanan Sistemler:</span>
            <span>48" Ana Hat &amp; Pig Kovanları</span>
            <span>•</span>
            <span>MFS Çoklu Siklon</span>
            <span>•</span>
            <span>CFS Kartuş Filtre</span>
            <span>•</span>
            <span>COMPRESSOR-01..05 (Mavi Çelik Karkas &amp; X-Ray Kesit)</span>
            <span>•</span>
            <span>Gas Cooler &amp; TCV By-Pass</span>
            <span>•</span>
            <span>7.0m Yol, Tel Çit &amp; Kontrol Binası</span>
          </div>
          <button id="btn-footer-close-pfd-modal" class="btn btn-sm btn-secondary">${escapeHtml(t("station_pfd_close", lang))}</button>
        </div>

      </div>
    </div>
  `;
}

/**
 * Renders the live interactive parameter control bar for real-time natural gas pipe sizing.
 */
function renderLiveParamsBar(inputs, isExpanded, gasComp, lang = "tr", stationData = null, designInputs = {}) {
  const mmscmdEst = convertFlowWithMW(inputs.mass_flow, "kg/s", "MMSCMD", gasComp).toFixed(2);
  const mmscmdMin = convertFlowWithMW(20, "kg/s", "MMSCMD", gasComp).toFixed(1);
  const mmscmdMax = convertFlowWithMW(300, "kg/s", "MMSCMD", gasComp).toFixed(1);
  const flowUnit = inputs.mass_flow_unit || "kg/s";
  const pinUnit = inputs.p_in_unit || "bar(a)";
  const poutUnit = inputs.p_out_unit || "bar(a)";
  const flowDisplay = roundDisplay(stationFlowDisplay(inputs.mass_flow, flowUnit, gasComp));
  const pinDisplay = stationPressureDisplay(inputs.p_in, pinUnit);
  const poutDisplay = stationPressureDisplay(inputs.p_out, poutUnit);
  const designPatmBar = resolveAmbientBarA(designInputs?.ambient_pressure ?? 101.325);
  const designTatmC = Number(designInputs?.ambient_temp ?? 15.0);
  const eq = stationData?.equipment_sizing || {};
  const piping = stationData?.station_piping || {};
  const pLines = piping?.lines || {};
  const commonHeaderNps = piping?.header_sizing_rule?.common_nominal_size_in || pLines?.suction_header?.nominal_size_in || "-";
  const compDischTempC = eq?.air_coolers?.inlet_temp_c ?? stationData?.nodes?.[4]?.temp_c ?? "-";
  const maxVelDisplay = Number(inputs.max_velocity_ms ?? 20.0).toFixed(1);
  const COMMERCIAL_NPS_KEYS = ["2", "3", "4", "6", "8", "10", "12", "14", "16", "18", "20", "24", "26", "28", "30", "32", "36", "40", "42", "48"];
  const renderBranchPipeSelect = (selectId, labelText, selectedRaw, lineObj) => {
    const cleanSelected = String(selectedRaw || "").replace(/"/g, "").trim();
    const minKey = String(lineObj?.velocity_min_key || "");
    const minNps = lineObj?.velocity_min_nominal_in || "-";
    const actualNps = lineObj?.nominal_size_in || "-";
    const actualVel = lineObj?.actual_velocity_ms != null ? Number(lineObj.actual_velocity_ms).toFixed(1) : "-";
    const meetsMin = lineObj ? lineObj.meets_min_velocity_diameter !== false : true;
    const minNum = parseFloat(minKey);
    const keysList = Array.from(new Set([...COMMERCIAL_NPS_KEYS, ...(minKey ? [minKey] : []), ...(cleanSelected ? [cleanSelected] : [])]))
      .sort((a, b) => (parseFloat(a) || 0) - (parseFloat(b) || 0));
    const optionsHtml = keysList.map((k) => {
      const kNum = parseFloat(k);
      const underMin = Number.isFinite(minNum) && Number.isFinite(kNum) && kNum < minNum;
      const suffix = underMin ? ` (⚠ < Min ${minNps})` : (minKey === k ? " (Min)" : "");
      return `<option value="${escapeHtml(k)}" ${cleanSelected === k ? "selected" : ""}>${escapeHtml(k)}" NPS${escapeHtml(suffix)}</option>`;
    }).join("");
    const statusHtml = !lineObj
      ? ""
      : meetsMin
        ? `<span style="color: #34d399;">✓ ${escapeHtml(actualNps)} • ${escapeHtml(actualVel)} m/s (Min: ${escapeHtml(minNps)})</span>`
        : `<span style="color: #f87171; font-weight: 700;">⚠ ${escapeHtml(actualNps)} • ${escapeHtml(actualVel)} m/s &gt; ${escapeHtml(maxVelDisplay)} m/s (Min: ${escapeHtml(minNps)})</span>`;
    return `
      <div style="display: flex; flex-direction: column; gap: 2px;">
        <label for="${escapeHtml(selectId)}" style="font-size: 10px; color: var(--color-text-secondary);">${escapeHtml(labelText)}</label>
        <select id="${escapeHtml(selectId)}" style="font-size: 11px; padding: 2px 4px; background: var(--color-surface); border: 1px solid ${meetsMin ? "var(--color-border)" : "#ef4444"}; border-radius: 4px; color: var(--color-text); font-family: var(--font-mono);">
          <option value="" ${!cleanSelected ? "selected" : ""}>${escapeHtml(t("station_param_pipe_auto", lang))}${minNps !== "-" ? ` (Min ${escapeHtml(minNps)})` : ""}</option>
          ${optionsHtml}
        </select>
        <div style="font-size: 9px; line-height: 1.25;">${statusHtml}</div>
      </div>
    `;
  };
  return `
    <div class="card" style="padding: 12px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-md);">
      
      <!-- Collapsible Top Summary Bar -->
      <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
        <div style="display: flex; align-items: center; gap: 8px;">
          ${icon("sliders", 16, "text-primary")}
          <div style="font-size: 12px; font-weight: 700; color: var(--color-text);">
            ${escapeHtml(t("station_params_title", lang))}
          </div>
          <span class="badge badge-success" style="font-size: 10px;">${escapeHtml(t("station_params_badge", lang))}</span>
        </div>

        <div style="display: flex; align-items: center; gap: 12px; font-size: 11px; flex-wrap: wrap;">
          <div style="color: var(--color-text-secondary);">
            ${escapeHtml(t("station_params_flow", lang))}: <strong style="color: #38bdf8; font-family: var(--font-mono);">${flowDisplay} ${escapeHtml(flowUnit)}</strong> <span style="opacity: 0.7;">(~${mmscmdEst} MMSCMD)</span>
          </div>
          <div style="color: var(--color-text-secondary);">
            ${escapeHtml(t("station_params_suction", lang))}: <strong style="color: #34d399; font-family: var(--font-mono);">${pinDisplay} ${escapeHtml(pinUnit)}</strong>
          </div>
          <div style="color: var(--color-text-secondary);">
            ${escapeHtml(t("station_params_discharge", lang))}: <strong style="color: #f59e0b; font-family: var(--font-mono);">${poutDisplay} ${escapeHtml(poutUnit)}</strong>
          </div>
          <div style="color: var(--color-text-secondary);">
            v_maks: <strong style="color: #facc15; font-family: var(--font-mono);">${Number(inputs.max_velocity_ms || 20).toFixed(1)} m/s</strong>
          </div>
          <div style="color: var(--color-text-secondary);">
            Ortak Header: <strong style="color: #38bdf8; font-family: var(--font-mono);">${escapeHtml(commonHeaderNps)}</strong>
          </div>
          <button id="btn-toggle-params-panel" class="btn btn-sm btn-secondary" style="font-size: 11px; padding: 2px 8px;">
            ${escapeHtml(t(isExpanded ? "station_params_collapse" : "station_params_expand", lang))}
          </button>
        </div>
      </div>

      <!-- Expanded Interactive Controls Grid -->
      ${isExpanded ? `
        <div style="margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--color-border); display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px;">
          
          <!-- Mass Flow Controller -->
          <div style="background: var(--color-surface-hover); padding: 8px 10px; border-radius: var(--radius-sm); border: 1px solid var(--color-border);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; gap: 6px;">
              <label style="font-size: 11px; font-weight: 600; color: var(--color-text);">Gaz Debisi</label>
              <div style="display: flex; gap: 4px; align-items: center;">
                <input type="number" id="input-param-flow" step="any" value="${flowDisplay}" style="width: 80px; font-size: 11px; padding: 2px 4px; text-align: right; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 4px; color: var(--color-text); font-family: var(--font-mono);" />
                <select id="select-param-flow-unit" class="form-select" style="width: 78px; height: 24px; font-size: 10px; padding: 0 4px;" aria-label="Debi birimi">
                  ${STATION_FLOW_UNITS.map((u) => `<option value="${u}" ${flowUnit === u ? "selected" : ""}>${u}</option>`).join("")}
                </select>
              </div>
            </div>
            <input type="range" id="slider-param-flow" min="20" max="300" step="5" value="${inputs.mass_flow}" style="width: 100%; cursor: pointer;" aria-label="Debi kaydırıcısı (kg/s)" />
            <div style="display: flex; justify-content: space-between; font-size: 9px; color: var(--color-text-secondary); margin-top: 2px;">
              <span>20 kg/s</span>
              <span>150 kg/s</span>
              <span>300 kg/s</span>
            </div>
            <div style="font-size: 9px; color: var(--color-text-secondary); margin-top: 2px;">
              Kaydırıcı: kg/s • ${mmscmdMin}–${mmscmdMax} MMSCMD
            </div>
          </div>

          <!-- Suction Pressure Controller -->
          <div style="background: var(--color-surface-hover); padding: 8px 10px; border-radius: var(--radius-sm); border: 1px solid var(--color-border);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; gap: 6px;">
              <label style="font-size: 11px; font-weight: 600; color: var(--color-text);">Emiş Basıncı P_in</label>
              <div style="display: flex; gap: 4px; align-items: center;">
                <input type="number" id="input-param-pin" step="any" value="${pinDisplay}" style="width: 72px; font-size: 11px; padding: 2px 4px; text-align: right; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 4px; color: var(--color-text); font-family: var(--font-mono);" />
                <select id="select-param-pin-unit" class="form-select" style="width: 70px; height: 24px; font-size: 10px; padding: 0 4px;" aria-label="Emiş basıncı birimi">
                  ${STATION_PRESSURE_UNITS.map((u) => `<option value="${u}" ${pinUnit === u ? "selected" : ""}>${u}</option>`).join("")}
                </select>
              </div>
            </div>
            <input type="range" id="slider-param-pin" min="25" max="60" step="1" value="${inputs.p_in}" style="width: 100%; cursor: pointer;" aria-label="Emiş basıncı kaydırıcısı (bar a)" />
            <div style="display: flex; justify-content: space-between; font-size: 9px; color: var(--color-text-secondary); margin-top: 2px;">
              <span>25 bar(a)</span>
              <span>45 bar(a) (Standart)</span>
              <span>60 bar(a)</span>
            </div>
          </div>

          <!-- Discharge Pressure Controller -->
          <div style="background: var(--color-surface-hover); padding: 8px 10px; border-radius: var(--radius-sm); border: 1px solid var(--color-border);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; gap: 6px;">
              <label style="font-size: 11px; font-weight: 600; color: var(--color-text);">Basma Basıncı P_out</label>
              <div style="display: flex; gap: 4px; align-items: center;">
                <input type="number" id="input-param-pout" step="any" value="${poutDisplay}" style="width: 72px; font-size: 11px; padding: 2px 4px; text-align: right; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 4px; color: var(--color-text); font-family: var(--font-mono);" />
                <select id="select-param-pout-unit" class="form-select" style="width: 70px; height: 24px; font-size: 10px; padding: 0 4px;" aria-label="Basma basıncı birimi">
                  ${STATION_PRESSURE_UNITS.map((u) => `<option value="${u}" ${poutUnit === u ? "selected" : ""}>${u}</option>`).join("")}
                </select>
              </div>
            </div>
            <input type="range" id="slider-param-pout" min="50" max="90" step="1" value="${inputs.p_out}" style="width: 100%; cursor: pointer;" aria-label="Basma basıncı kaydırıcısı (bar a)" />
            <div style="display: flex; justify-content: space-between; font-size: 9px; color: var(--color-text-secondary); margin-top: 2px;">
              <span>50 bar(a)</span>
              <span>75 bar(a) (Standart)</span>
              <span>90 bar(a)</span>
            </div>
          </div>

          <!-- Equipment Counts & Pipe Steel Selection -->
          <div style="background: var(--color-surface-hover); padding: 8px 10px; border-radius: var(--radius-sm); border: 1px solid var(--color-border); display: flex; flex-direction: column; gap: 6px;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <label style="font-size: 11px; font-weight: 600; color: var(--color-text);">Kompresör Trenleri:</label>
              <select id="select-param-comps" style="font-size: 11px; padding: 2px 4px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 4px; color: var(--color-text);">
                <option value="0" ${inputs.comp_op_count === 0 ? "selected" : ""}>Otomatik (Debiye Göre)</option>
                <option value="1" ${inputs.comp_op_count === 1 ? "selected" : ""}>1+1 Tren</option>
                <option value="2" ${inputs.comp_op_count === 2 ? "selected" : ""}>2+1 Tren</option>
                <option value="3" ${inputs.comp_op_count === 3 ? "selected" : ""}>3+1 Tren</option>
                <option value="4" ${inputs.comp_op_count === 4 ? "selected" : ""}>4+1 Tren (BOTAŞ)</option>
                <option value="5" ${inputs.comp_op_count === 5 ? "selected" : ""}>5+1 Tren</option>
                <option value="6" ${inputs.comp_op_count === 6 ? "selected" : ""}>6+1 Tren</option>
              </select>
            </div>

            <div style="display: flex; justify-content: space-between; align-items: center;">
              <label style="font-size: 11px; font-weight: 600; color: var(--color-text);">MFS Siklon Sayısı:</label>
              <select id="select-param-cyclones" style="font-size: 11px; padding: 2px 4px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 4px; color: var(--color-text);">
                <option value="0" ${inputs.cyclone_op_count === 0 ? "selected" : ""}>Otomatik (PFD 2+1 · %50)</option>
                <option value="2" ${inputs.cyclone_op_count === 2 ? "selected" : ""}>2+1 Ünite (PFD / BOTAŞ · %50)</option>
                <option value="3" ${inputs.cyclone_op_count === 3 ? "selected" : ""}>3+1 Ünite (%33.3)</option>
                <option value="4" ${inputs.cyclone_op_count === 4 ? "selected" : ""}>4+1 Ünite (%25)</option>
                <option value="5" ${inputs.cyclone_op_count === 5 ? "selected" : ""}>5+1 Ünite (%20)</option>
              </select>
            </div>

            <div style="display: flex; justify-content: space-between; align-items: center;">
              <label style="font-size: 11px; font-weight: 600; color: var(--color-text);">CFS Filtre Sayısı:</label>
              <select id="select-param-filters" style="font-size: 11px; padding: 2px 4px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 4px; color: var(--color-text);">
                <option value="0" ${inputs.filter_op_count === 0 ? "selected" : ""}>Otomatik (PFD 2+1 · %50)</option>
                <option value="2" ${inputs.filter_op_count === 2 ? "selected" : ""}>2+1 Ünite (PFD / BOTAŞ · %50)</option>
                <option value="3" ${inputs.filter_op_count === 3 ? "selected" : ""}>3+1 Ünite (%33.3)</option>
                <option value="4" ${inputs.filter_op_count === 4 ? "selected" : ""}>4+1 Ünite (%25)</option>
                <option value="5" ${inputs.filter_op_count === 5 ? "selected" : ""}>5+1 Ünite (%20)</option>
              </select>
            </div>

            <div style="display: flex; justify-content: space-between; align-items: center;">
              <label style="font-size: 11px; font-weight: 600; color: var(--color-text);">Hava Soğutucu Bay:</label>
              <select id="select-param-coolers" style="font-size: 11px; padding: 2px 4px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 4px; color: var(--color-text);">
                <option value="0" ${inputs.cooler_bays_count === 0 ? "selected" : ""}>Otomatik (Isıl Yüke Göre)</option>
                <option value="2" ${inputs.cooler_bays_count === 2 ? "selected" : ""}>2 Bay (4 Fan)</option>
                <option value="4" ${inputs.cooler_bays_count === 4 ? "selected" : ""}>4 Bay (8 Fan)</option>
                <option value="6" ${inputs.cooler_bays_count === 6 ? "selected" : ""}>6 Bay (12 Fan - BOTAŞ)</option>
                <option value="8" ${inputs.cooler_bays_count === 8 ? "selected" : ""}>8 Bay (16 Fan)</option>
                <option value="10" ${inputs.cooler_bays_count === 10 ? "selected" : ""}>10 Bay (20 Fan)</option>
              </select>
            </div>

            <div style="display: flex; justify-content: space-between; align-items: center;">
              <label style="font-size: 11px; font-weight: 600; color: var(--color-text);">Boru Çelik Sınıfı:</label>
              <select id="select-param-material" style="font-size: 11px; padding: 2px 4px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 4px; color: var(--color-text);">
                <option value="API 5L X70" ${inputs.pipe_material === "API 5L X70" ? "selected" : ""}>API 5L X70 (485 MPa)</option>
                <option value="API 5L X65" ${inputs.pipe_material === "API 5L X65" ? "selected" : ""}>API 5L X65 (450 MPa)</option>
                <option value="API 5L X52" ${inputs.pipe_material === "API 5L X52" ? "selected" : ""}>API 5L X52 (360 MPa)</option>
                <option value="API 5L Gr. B" ${inputs.pipe_material === "API 5L Gr. B" ? "selected" : ""}>API 5L Gr. B (245 MPa)</option>
              </select>
            </div>

            <div style="display: flex; justify-content: space-between; align-items: center;">
              <label style="font-size: 11px; font-weight: 600; color: var(--color-text);">Boru Standardı:</label>
              <select id="select-param-standard" style="font-size: 11px; padding: 2px 4px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 4px; color: var(--color-text);">
                <option value="BOTAŞ" ${inputs.pipe_standard === "BOTAŞ" ? "selected" : ""}>BOTAŞ 5120_R7</option>
                <option value="ASME B31.8 / ASME B31.4" ${inputs.pipe_standard === "ASME B31.8 / ASME B31.4" ? "selected" : ""}>API 5L / ASME B31.8</option>
                <option value="ASME B31.3" ${inputs.pipe_standard === "ASME B31.3" ? "selected" : ""}>ASME B31.3</option>
              </select>
            </div>

            <div style="display: flex; justify-content: space-between; align-items: center;">
              <label style="font-size: 11px; font-weight: 600; color: var(--color-text);">PSL Seviyesi:</label>
              <select id="select-param-psl" style="font-size: 11px; padding: 2px 4px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 4px; color: var(--color-text);">
                <option value="PSL2" ${inputs.psl_level === "PSL2" ? "selected" : ""}>PSL2</option>
                <option value="PSL1" ${inputs.psl_level === "PSL1" ? "selected" : ""}>PSL1</option>
              </select>
            </div>
          </div>

          <!-- Pipe Max Velocity + Gas Cooler User Inputs + PSV + ESD/BDV Cards -->
          <div style="grid-column: 1 / -1; display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 10px;">

            <!-- 1. Pipe Max Velocity & Common Header Sizing Card -->
            <div style="background: var(--color-surface-hover); padding: 8px 10px; border-radius: var(--radius-sm); border: 1px solid var(--color-border);">
              <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px;">
                <span style="font-size: 11px; font-weight: 700; color: var(--color-text);">📏 Boru Hız Sınırı &amp; Ortak Header Çapı</span>
                <span class="badge badge-primary" style="font-size: 9px;">Default: 20 m/s</span>
              </div>
              <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 6px;">
                <label style="font-size: 10px; color: var(--color-text-secondary); display: flex; flex-direction: column; gap: 2px;">
                  ${escapeHtml(t("station_param_max_vel", lang))}
                  <input type="number" id="input-param-max-vel" step="0.5" min="3" max="50" value="${inputs.max_velocity_ms ?? 20.0}" style="font-size: 11px; padding: 2px 4px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 4px; color: var(--color-text); font-family: var(--font-mono);" />
                </label>
                <label style="font-size: 10px; color: var(--color-text-secondary); display: flex; flex-direction: column; gap: 2px;">
                  Tasarım Faktörü (F)
                  <input type="number" id="input-param-design-f" step="0.05" min="0.3" max="0.72" value="${inputs.design_factor_F ?? 0.50}" style="font-size: 11px; padding: 2px 4px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 4px; color: var(--color-text); font-family: var(--font-mono);" />
                </label>
                <label style="font-size: 10px; color: var(--color-text-secondary); display: flex; flex-direction: column; gap: 2px;">
                  ${escapeHtml(t("station_param_suct_len", lang))}
                  <input type="number" id="input-param-suct-len" step="10" min="1" max="50000" value="${inputs.suction_equiv_length_m ?? 120.0}" style="font-size: 11px; padding: 2px 4px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 4px; color: var(--color-text); font-family: var(--font-mono);" />
                </label>
                <label style="font-size: 10px; color: var(--color-text-secondary); display: flex; flex-direction: column; gap: 2px;">
                  ${escapeHtml(t("station_param_disch_len", lang))}
                  <input type="number" id="input-param-disch-len" step="10" min="1" max="50000" value="${inputs.discharge_equiv_length_m ?? 150.0}" style="font-size: 11px; padding: 2px 4px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 4px; color: var(--color-text); font-family: var(--font-mono);" />
                </label>
              </div>
              <div style="margin-top: 6px; font-size: 9.5px; color: var(--color-text-secondary); line-height: 1.4;">
                Ekipman bağlantı boruları hariç tüm headerlarda hesaplanan en büyük çap esas alınır:
                <strong style="color: #facc15; font-family: var(--font-mono);">Station/Unit Suction &amp; Discharge = ${escapeHtml(commonHeaderNps)}</strong>
              </div>
            </div>

            <!-- 1b. MFS Cyclone & CFS Filter Inlet/Outlet Pipe Size Selection + Velocity Min Diameter Check -->
            <div style="background: var(--color-surface-hover); padding: 8px 10px; border-radius: var(--radius-sm); border: 1px solid var(--color-border);">
              <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px; gap: 6px;">
                <span style="font-size: 11px; font-weight: 700; color: var(--color-text);">🛢️ ${escapeHtml(t("station_param_pipe_diam_card", lang))}</span>
                <span class="badge badge-primary" style="font-size: 9px;">Min Çap Kontrolü: v ≤ ${escapeHtml(maxVelDisplay)} m/s</span>
              </div>
              <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 6px;">
                ${renderBranchPipeSelect("select-param-cyc-in", t("station_param_cyc_in", lang), inputs.cyclone_inlet_pipe_size, pLines.cyclone_branch)}
                ${renderBranchPipeSelect("select-param-cyc-out", t("station_param_cyc_out", lang), inputs.cyclone_outlet_pipe_size, pLines.cyclone_outlet_branch)}
                ${renderBranchPipeSelect("select-param-flt-in", t("station_param_flt_in", lang), inputs.filter_inlet_pipe_size, pLines.filter_branch)}
                ${renderBranchPipeSelect("select-param-flt-out", t("station_param_flt_out", lang), inputs.filter_outlet_pipe_size, pLines.filter_outlet_branch)}
              </div>
            </div>

            <!-- 2. Gas Cooler Air Temp & Max Gas Outlet Temp Card -->
            <div style="background: var(--color-surface-hover); padding: 8px 10px; border-radius: var(--radius-sm); border: 1px solid var(--color-border);">
              <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px;">
                <span style="font-size: 11px; font-weight: 700; color: var(--color-text);">❄️ Gaz Soğutucu (E-101) Kullanıcı Girdileri</span>
                <span class="badge badge-success" style="font-size: 9px;">T_in = Kompresör T_çıkış (${escapeHtml(compDischTempC)}°C)</span>
              </div>
              <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 6px;">
                <label style="font-size: 10px; color: var(--color-text-secondary); display: flex; flex-direction: column; gap: 2px;">
                  ${escapeHtml(t("station_param_cooler_air", lang))}
                  <input type="number" id="input-param-cooler-air" step="0.5" min="-40" max="55" value="${inputs.cooler_air_temp_c ?? ""}" placeholder="Tasarım: ${designTatmC}°C" style="font-size: 11px; padding: 2px 4px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 4px; color: var(--color-text); font-family: var(--font-mono);" />
                </label>
                <label style="font-size: 10px; color: var(--color-text-secondary); display: flex; flex-direction: column; gap: 2px;">
                  ${escapeHtml(t("station_param_cooler_max_out", lang))}
                  <input type="number" id="input-param-cooler-max-out" step="0.5" min="15" max="90" value="${inputs.cooler_max_outlet_temp_c ?? 45.0}" style="font-size: 11px; padding: 2px 4px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 4px; color: var(--color-text); font-family: var(--font-mono);" />
                </label>
              </div>
              <div style="margin-top: 6px; font-size: 9.5px; color: var(--color-text-secondary); line-height: 1.4;">
                Kompresör basma sıcaklığı (<b>${escapeHtml(compDischTempC)}°C</b>) doğrudan soğutucu girişi alınır • Çıkış: <strong style="color:#34d399;">${escapeHtml(eq?.air_coolers?.outlet_temp_c ?? "-")}°C</strong>
              </div>
            </div>

            <!-- 3. PSV Safety Valve Sizing Card -->
            <div style="background: var(--color-surface-hover); padding: 8px 10px; border-radius: var(--radius-sm); border: 1px solid var(--color-border);">
              <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px;">
                <span style="font-size: 11px; font-weight: 700; color: var(--color-text);">🛡️ PSV Sayı &amp; Çap Hesabı</span>
                <span class="badge badge-info" style="font-size: 9px;" title="Tasarım Sekmesi Saha Şartlarından Alınır">P_atm=${designPatmBar.toFixed(3)} bar • T_atm=${designTatmC}°C</span>
              </div>
              <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px;">
                <label style="font-size: 10px; color: var(--color-text-secondary); display: flex; flex-direction: column; gap: 2px;">
                  PSV Set (bar g)
                  <input type="number" id="input-param-psv-set" step="0.1" value="${inputs.psv_set_pressure_bar ?? ""}" placeholder="Oto: ${roundDisplay(Math.max(1, inputs.p_out - designPatmBar) * 1.1)}" style="font-size: 11px; padding: 2px 4px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 4px; color: var(--color-text); font-family: var(--font-mono);" />
                </label>
                <label style="font-size: 10px; color: var(--color-text-secondary); display: flex; flex-direction: column; gap: 2px;">
                  Aşırı Basınç (%)
                  <input type="number" id="input-param-psv-overpressure" step="1" min="1" max="25" value="${inputs.psv_overpressure_pct}" style="font-size: 11px; padding: 2px 4px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 4px; color: var(--color-text); font-family: var(--font-mono);" />
                </label>
                <label style="font-size: 10px; color: var(--color-text-secondary); display: flex; flex-direction: column; gap: 2px;">
                  Karşı Basınç (bar a)
                  <input type="number" id="input-param-psv-backpressure" step="0.01" value="${inputs.psv_back_pressure_bar ?? ""}" placeholder="P_atm: ${designPatmBar.toFixed(4)}" style="font-size: 11px; padding: 2px 4px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 4px; color: var(--color-text); font-family: var(--font-mono);" />
                </label>
                <label style="font-size: 10px; color: var(--color-text-secondary); display: flex; flex-direction: column; gap: 2px;">
                  Toplam PSV Adedi
                  <select id="select-param-psv-count" style="font-size: 11px; padding: 2px 4px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 4px; color: var(--color-text);">
                    ${[1, 2, 3, 4].map((n) => `<option value="${n}" ${Number(inputs.psv_count) === n ? "selected" : ""}>${n} Adet</option>`).join("")}
                  </select>
                </label>
                <label style="font-size: 10px; color: var(--color-text-secondary); display: flex; flex-direction: column; gap: 2px;">
                  Eşzamanlı Duty PSV
                  <select id="select-param-psv-duty" style="font-size: 11px; padding: 2px 4px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 4px; color: var(--color-text);">
                    ${[1, 2, 3, 4].map((n) => `<option value="${n}" ${Number(inputs.psv_duty_count) === n ? "selected" : ""}>${n} Duty</option>`).join("")}
                  </select>
                </label>
                <label style="font-size: 10px; color: var(--color-text-secondary); display: flex; flex-direction: column; gap: 2px;">
                  PSV Tipi
                  <select id="select-param-psv-type" style="font-size: 11px; padding: 2px 4px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 4px; color: var(--color-text);">
                    <option value="conventional" ${inputs.psv_valve_type === "conventional" ? "selected" : ""}>Conventional</option>
                    <option value="balanced_bellows" ${inputs.psv_valve_type === "balanced_bellows" ? "selected" : ""}>Balanced Bellows</option>
                    <option value="pilot" ${inputs.psv_valve_type === "pilot" ? "selected" : ""}>Pilot Operated</option>
                  </select>
                </label>
              </div>
            </div>

            <!-- 4. ESD / BDV Volume & Valve Sizing Card -->
            <div style="background: var(--color-surface-hover); padding: 8px 10px; border-radius: var(--radius-sm); border: 1px solid var(--color-border);">
              <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px;">
                <span style="font-size: 11px; font-weight: 700; color: var(--color-text);">🚨 ESD / BDV Hacim &amp; Çap Hesabı</span>
                <span class="badge badge-warning" style="font-size: 9px;" title="Tasarım Sekmesi Atmosfer Şartlarına Bağlı">P_atm=${designPatmBar.toFixed(3)} bar • T_atm=${designTatmC}°C</span>
              </div>
              <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px;">
                <label style="font-size: 10px; color: var(--color-text-secondary); display: flex; flex-direction: column; gap: 2px;" title="Yüksek Basınç = Kompresör Çıkış Basıncı (P_out)">
                  YB Hacim m³ (@P_out)
                  <input type="number" id="input-param-esd-hp-vol" step="5" min="1" max="5000" value="${inputs.esd_hp_volume_m3 ?? 50.0}" style="font-size: 11px; padding: 2px 4px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 4px; color: var(--color-text); font-family: var(--font-mono);" />
                </label>
                <label style="font-size: 10px; color: var(--color-text-secondary); display: flex; flex-direction: column; gap: 2px;" title="Düşük Basınç = Kompresör Giriş Basıncı (P_in)">
                  DB Hacim m³ (@P_in)
                  <input type="number" id="input-param-esd-lp-vol" step="5" min="1" max="5000" value="${inputs.esd_lp_volume_m3 ?? 40.0}" style="font-size: 11px; padding: 2px 4px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 4px; color: var(--color-text); font-family: var(--font-mono);" />
                </label>
                <label style="font-size: 10px; color: var(--color-text-secondary); display: flex; flex-direction: column; gap: 2px;">
                  Boşaltma Süresi (dk)
                  <input type="number" id="input-param-esd-bdv-time" step="1" min="1" max="60" value="${inputs.bdv_depressurization_time_min ?? 15}" style="font-size: 11px; padding: 2px 4px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 4px; color: var(--color-text); font-family: var(--font-mono);" />
                </label>
                <label style="font-size: 10px; color: var(--color-text-secondary); display: flex; flex-direction: column; gap: 2px;">
                  Toplam / Duty ESD
                  <div style="display: flex; gap: 3px;">
                    <select id="select-param-esd-count" style="width: 50%; font-size: 10.5px; padding: 2px 2px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 4px; color: var(--color-text);" aria-label="Toplam ESD">
                      ${[1, 2, 3, 4, 5, 6].map((n) => `<option value="${n}" ${Number(inputs.esd_count || 2) === n ? "selected" : ""}>${n}Top</option>`).join("")}
                    </select>
                    <select id="select-param-esd-duty" style="width: 50%; font-size: 10.5px; padding: 2px 2px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 4px; color: var(--color-text);" aria-label="Aktif ESD">
                      ${[1, 2, 3, 4, 5, 6].map((n) => `<option value="${n}" ${Number(inputs.esd_duty_count || 1) === n ? "selected" : ""}>${n}Akt</option>`).join("")}
                    </select>
                  </div>
                </label>
                <label style="font-size: 10px; color: var(--color-text-secondary); display: flex; flex-direction: column; gap: 2px;">
                  İzin Verilen ΔP (bar)
                  <input type="number" id="input-param-esd-dp" step="0.05" min="0.05" value="${inputs.esd_allowable_dp_bar}" style="font-size: 11px; padding: 2px 4px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 4px; color: var(--color-text); font-family: var(--font-mono);" />
                </label>
                <label style="font-size: 10px; color: var(--color-text-secondary); display: flex; flex-direction: column; gap: 2px;">
                  ESD Vana Tipi
                  <select id="select-param-esd-type" style="font-size: 11px; padding: 2px 4px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 4px; color: var(--color-text);">
                    <option value="full_bore_ball" ${inputs.esd_valve_type === "full_bore_ball" ? "selected" : ""}>Full-Bore Ball</option>
                    <option value="ball" ${inputs.esd_valve_type === "ball" ? "selected" : ""}>Ball</option>
                    <option value="butterfly" ${inputs.esd_valve_type === "butterfly" ? "selected" : ""}>Butterfly</option>
                    <option value="gate" ${inputs.esd_valve_type === "gate" ? "selected" : ""}>Gate</option>
                  </select>
                </label>
              </div>
            </div>
          </div>

        </div>

        <div style="display: flex; justify-content: flex-end; gap: 8px; margin-top: 10px;">
          <button id="btn-reset-station-params" class="btn btn-sm btn-secondary" style="font-size: 11px;">
            ${icon("refreshCw", 12)}
            <span>${escapeHtml(t("station_params_reset", lang))}</span>
          </button>
          <button id="btn-apply-station-params" class="btn btn-sm btn-primary" style="font-size: 11px;">
            ${icon("play", 12)}
            <span>${escapeHtml(t("station_params_apply", lang))}</span>
          </button>
        </div>
      ` : ""}

    </div>
  `;
}

/**
 * Renders the comprehensive 15-line ASME B36.10M / API 5L Natural Gas Flow Calc Pipe Sizing Matrix Table.
 */
function renderPipeSizingTable(piping) {
  const lang = uiStore?.getState?.()?.lang || "tr";
  if (!piping || Object.keys(piping).length === 0) {
    return `
      <div class="card" style="padding: 14px; text-align: center; color: var(--color-text-secondary); font-size: 12px;">
        ${icon("activity", 18, "text-primary")}
        <div style="margin-top: 6px;">${escapeHtml(t("station_pipe_loading", lang))}</div>
      </div>
    `;
  }

  const linesMap = piping.lines || piping;
  const lines = Object.values(linesMap);
  const netMaxVel = Number(piping.max_velocity_ms || 20.0);
  const headerRule = piping.header_sizing_rule || {};
  const arch = piping.piping_architecture || {};
  const mainHeaders = arch.main_headers || {};
  const suctArch = mainHeaders.station_suction_header || null;
  const unitSuctArch = mainHeaders.unit_suction_header || null;
  const unitDischArch = mainHeaders.unit_discharge_header || null;
  const dischArch = mainHeaders.station_discharge_header || null;
  const limitations = Array.isArray(arch.naming_limitations) ? arch.naming_limitations : [];
  const spec4500 = piping.spec_4500_compliance || null;
  const spec4500Html = spec4500 ? (() => {
    const sPipe = spec4500.suction_piping || {};
    const dPipe = spec4500.discharge_piping || {};
    const vChk = spec4500.velocity_check || {};
    const stress = spec4500.stress_b313_b318 || {};
    const ac = spec4500.acoustic_pulsation || {};
    const overallOk = !!spec4500.overall_compliant;
    const empS = sPipe.empirical_dp_bar || {};
    const empDHot = dPipe.empirical_hot_dp_bar || {};
    const empDCold = dPipe.empirical_cold_dp_bar || {};
    const empDischWey = Number(empDHot.weymouth || 0) + Number(empDCold.weymouth || 0);
    const badgeBorder = (ok) => ok ? "#059669" : "#dc2626";
    const badgeBg = (ok) => ok ? "rgba(16, 185, 129, 0.10)" : "rgba(239, 68, 68, 0.10)";
    const statusLabel = (ok) => ok ? "UYGUN" : "SINIR AŞIMI";
    return `
      <div id="spec-4500-compliance-panel" style="margin-bottom: 10px; padding: 10px 12px; border-radius: var(--radius-sm); background: var(--color-surface-hover); border: 1px solid ${overallOk ? "rgba(16, 185, 129, 0.45)" : "rgba(239, 68, 68, 0.55)"};">
        <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px; flex-wrap: wrap; margin-bottom: 8px;">
          <div style="font-size: 11.5px; font-weight: 700; color: var(--color-text);">
            📐 ${escapeHtml(t("spec_4500_title", lang))}
          </div>
          <div style="display: flex; align-items: center; gap: 6px; flex-wrap: wrap;">
            <span class="badge ${overallOk ? "badge-success" : "badge-danger"}" style="font-size: 10px;">
              ${escapeHtml(overallOk ? t("spec_4500_ok", lang) : t("spec_4500_fail", lang))}
            </span>
            <span class="badge badge-neutral" style="font-size: 9.5px;">${escapeHtml(spec4500.engine_source || "Compressible 20-Seg DW")}</span>
          </div>
        </div>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 8px; font-size: 10.5px;">
          <div style="padding: 8px 10px; border-radius: 6px; background: ${badgeBg(sPipe.compliant)}; border-left: 3px solid ${badgeBorder(sPipe.compliant)};">
            <div style="display: flex; justify-content: space-between; font-weight: 700; margin-bottom: 3px;">
              <span>Emiş ΔP (Scrubber Hariç)</span>
              <span style="color: ${badgeBorder(sPipe.compliant)};">${statusLabel(sPipe.compliant)}</span>
            </div>
            <div style="font-family: var(--font-mono); font-size: 12px; font-weight: 700;">
              ${Number(sPipe.dp_piping_bar ?? 0).toFixed(3)} bar <span style="font-size: 10px; font-weight: 400; color: var(--color-text-secondary);">/ ≤ ${Number(sPipe.limit_bar ?? 1.0).toFixed(1)} bar</span>
            </div>
            <div style="color: var(--color-text-secondary); margin-top: 2px; line-height: 1.35;">
              L_eq=${Number(sPipe.equiv_length_m ?? 120).toFixed(0)} m (${escapeHtml(sPipe.header_nps || "-")}) • Weymouth: ${Number(empS.weymouth ?? 0).toFixed(3)} bar • Hariç (MFS+CFS): ${Number(sPipe.dp_excluded_scrubber_bar ?? 0).toFixed(2)} bar
            </div>
          </div>
          <div style="padding: 8px 10px; border-radius: 6px; background: ${badgeBg(dPipe.compliant)}; border-left: 3px solid ${badgeBorder(dPipe.compliant)};">
            <div style="display: flex; justify-content: space-between; font-weight: 700; margin-bottom: 3px;">
              <span>Basma ΔP (Soğutucu Hariç)</span>
              <span style="color: ${badgeBorder(dPipe.compliant)};">${statusLabel(dPipe.compliant)}</span>
            </div>
            <div style="font-family: var(--font-mono); font-size: 12px; font-weight: 700;">
              ${Number(dPipe.dp_piping_bar ?? 0).toFixed(3)} bar <span style="font-size: 10px; font-weight: 400; color: var(--color-text-secondary);">/ ≤ ${Number(dPipe.limit_bar ?? 0.5).toFixed(1)} bar</span>
            </div>
            <div style="color: var(--color-text-secondary); margin-top: 2px; line-height: 1.35;">
              L_eq=${Number(dPipe.equiv_length_m ?? 150).toFixed(0)} m • Weymouth: ${empDischWey.toFixed(3)} bar • Hariç (E-101): ${Number(dPipe.dp_excluded_cooler_bar ?? 0).toFixed(2)} bar
            </div>
          </div>
          <div style="padding: 8px 10px; border-radius: 6px; background: ${badgeBg(vChk.compliant)}; border-left: 3px solid ${badgeBorder(vChk.compliant)};">
            <div style="display: flex; justify-content: space-between; font-weight: 700; margin-bottom: 3px;">
              <span>Maks. Gaz Hızı (4500 §5.1)</span>
              <span style="color: ${badgeBorder(vChk.compliant)};">${statusLabel(vChk.compliant)}</span>
            </div>
            <div style="font-family: var(--font-mono); font-size: 12px; font-weight: 700;">
              ${Number(vChk.max_actual_ms ?? 0).toFixed(2)} m/s <span style="font-size: 10px; font-weight: 400; color: var(--color-text-secondary);">/ ≤ ${Number(vChk.limit_ms ?? 20.0).toFixed(1)} m/s</span>
            </div>
            <div style="color: var(--color-text-secondary); margin-top: 2px; line-height: 1.35;">
              Belirleyici Hat: ${escapeHtml(vChk.governing_tag || "-")}
            </div>
          </div>
          <div style="padding: 8px 10px; border-radius: 6px; background: ${badgeBg(stress.compliant)}; border-left: 3px solid ${badgeBorder(stress.compliant)};">
            <div style="display: flex; justify-content: space-between; font-weight: 700; margin-bottom: 3px;">
              <span>ANSI B31.3 + ASME B31.8</span>
              <span style="color: ${badgeBorder(stress.compliant)};">${statusLabel(stress.compliant)}</span>
            </div>
            <div style="font-family: var(--font-mono); font-size: 12px; font-weight: 700;">
              %${Number(stress.b318_max_hoop_pct_smys ?? 0).toFixed(1)} SMYS <span style="font-size: 10px; font-weight: 400; color: var(--color-text-secondary);">/ ≤ %${Number(stress.b318_allowable_pct_smys ?? 50).toFixed(0)}</span>
            </div>
            <div style="color: var(--color-text-secondary); margin-top: 2px; line-height: 1.35;">
              B31.3 S_L=${Number(stress.b313_max_sustained_mpa ?? 0).toFixed(1)}/${Number(stress.b313_allowable_stress_mpa ?? 0).toFixed(1)} MPa • S_E=${Number(stress.b313_max_thermal_mpa ?? 0).toFixed(1)} MPa • Span≤${Number(stress.recommended_support_span_m ?? 7).toFixed(1)} m
            </div>
          </div>
          <div style="padding: 8px 10px; border-radius: 6px; background: ${badgeBg(ac.compliant)}; border-left: 3px solid ${badgeBorder(ac.compliant)};">
            <div style="display: flex; justify-content: space-between; font-weight: 700; margin-bottom: 3px;">
              <span>Akustik / Pulsasyon / FIV</span>
              <span style="color: ${badgeBorder(ac.compliant)};">${statusLabel(ac.compliant)}</span>
            </div>
            <div style="font-family: var(--font-mono); font-size: 12px; font-weight: 700;">
              Ma=${Number(ac.max_mach ?? 0).toFixed(3)} • ${escapeHtml(ac.fiv_risk_level || "Düşük")}
            </div>
            <div style="color: var(--color-text-secondary); margin-top: 2px; line-height: 1.35;">
              ρ·v²=${Number(ac.max_momentum_flux_pa ?? 0).toFixed(0)} Pa • f_n/f_v=${Number(ac.min_freq_separation_ratio ?? 0).toFixed(1)}x (${escapeHtml(ac.governing_tag || "-")})
            </div>
          </div>
        </div>
      </div>
    `;
  })() : "";

  const archSummaryHtml = (suctArch || dischArch) ? `
    <div style="margin-bottom: 10px; padding: 10px 12px; border-radius: var(--radius-sm); background: rgba(15, 23, 42, 0.45); border: 1px solid var(--color-border);">
      <div style="font-size: 11.5px; font-weight: 700; color: var(--color-text-primary); margin-bottom: 8px; display: flex; align-items: center; justify-content: space-between; gap: 8px; flex-wrap: wrap;">
        <span>🧭 ${escapeHtml(t("pipe_arch_title", lang))}</span>
        <div style="display: flex; gap: 6px; flex-wrap: wrap;">
          <span class="badge badge-primary" style="font-size: 10px;">v_maks ≤ ${netMaxVel.toFixed(1)} m/s</span>
          <span class="badge badge-neutral" style="font-size: 10px;">4 Ana/Ünite Header Ortak Çap: ${escapeHtml(headerRule.common_nominal_size_in || suctArch?.nominal_size_in || linesMap.suction_header?.nominal_size_in || "-")} (Belirleyici: ${escapeHtml(headerRule.governing_line_key || "-")})</span>
        </div>
      </div>
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 8px;">
        ${suctArch ? `
          <div style="padding: 8px 10px; border-radius: 6px; background: rgba(56, 189, 248, 0.08); border-left: 3px solid #38bdf8; font-size: 10.5px;">
            <div style="font-weight: 700; color: #38bdf8; margin-bottom: 3px;">${escapeHtml(suctArch.name || "Station Suction Header")} (${escapeHtml((suctArch.tags || []).join(" + "))} • ${escapeHtml(suctArch.nominal_size_in || "-")})</div>
            <div style="color: var(--color-text-secondary); line-height: 1.4;">
              <div><b>Tekil Min:</b> ${escapeHtml(linesMap.suction_header?.individual_nominal_size_in || suctArch.nominal_size_in || "-")} → <b>Ortak:</b> ${escapeHtml(suctArch.nominal_size_in || "-")}</div>
              <div><b>Sınır:</b> ${escapeHtml(suctArch.from_boundary || "-")} ➔ ${escapeHtml(suctArch.to_boundary || "-")}</div>
            </div>
          </div>
        ` : ""}
        ${unitSuctArch ? `
          <div style="padding: 8px 10px; border-radius: 6px; background: rgba(14, 165, 233, 0.08); border-left: 3px solid #0ea5e9; font-size: 10.5px;">
            <div style="font-weight: 700; color: #0ea5e9; margin-bottom: 3px;">${escapeHtml(unitSuctArch.name || "Unit Suction Header")} (${escapeHtml((unitSuctArch.tags || []).join(" + "))} • ${escapeHtml(unitSuctArch.nominal_size_in || "-")})</div>
            <div style="color: var(--color-text-secondary); line-height: 1.4;">
              <div><b>Tekil Min:</b> ${escapeHtml(linesMap.comp_suction_header?.individual_nominal_size_in || unitSuctArch.nominal_size_in || "-")} → <b>Ortak:</b> ${escapeHtml(unitSuctArch.nominal_size_in || "-")}</div>
              <div><b>Sınır:</b> ${escapeHtml(unitSuctArch.from_boundary || "-")} ➔ ${escapeHtml(unitSuctArch.to_boundary || "-")}</div>
            </div>
          </div>
        ` : ""}
        ${unitDischArch ? `
          <div style="padding: 8px 10px; border-radius: 6px; background: rgba(239, 68, 68, 0.08); border-left: 3px solid #ef4444; font-size: 10.5px;">
            <div style="font-weight: 700; color: #f87171; margin-bottom: 3px;">${escapeHtml(unitDischArch.name || "Unit Discharge Header")} (${escapeHtml((unitDischArch.tags || []).join(" + "))} • ${escapeHtml(unitDischArch.nominal_size_in || "-")})</div>
            <div style="color: var(--color-text-secondary); line-height: 1.4;">
              <div><b>Tekil Min:</b> ${escapeHtml(linesMap.unit_discharge_header?.individual_nominal_size_in || unitDischArch.nominal_size_in || "-")} → <b>Ortak:</b> ${escapeHtml(unitDischArch.nominal_size_in || "-")}</div>
              <div><b>Sınır:</b> ${escapeHtml(unitDischArch.from_boundary || "-")} ➔ ${escapeHtml(unitDischArch.to_boundary || "-")}</div>
            </div>
          </div>
        ` : ""}
        ${dischArch ? `
          <div style="padding: 8px 10px; border-radius: 6px; background: rgba(245, 158, 11, 0.08); border-left: 3px solid #f59e0b; font-size: 10.5px;">
            <div style="font-weight: 700; color: #f59e0b; margin-bottom: 3px;">${escapeHtml(dischArch.name || "Station Discharge Header")} (${escapeHtml((dischArch.tags || []).join(" + "))} • ${escapeHtml(dischArch.nominal_size_in || "-")})</div>
            <div style="color: var(--color-text-secondary); line-height: 1.4;">
              <div><b>Tekil Min:</b> ${escapeHtml(linesMap.discharge_header?.individual_nominal_size_in || dischArch.nominal_size_in || "-")} → <b>Ortak:</b> ${escapeHtml(dischArch.nominal_size_in || "-")}</div>
              <div><b>Sınır:</b> ${escapeHtml(dischArch.from_boundary || "-")} ➔ ${escapeHtml(dischArch.to_boundary || "-")}</div>
            </div>
          </div>
        ` : ""}
      </div>
      ${limitations.length > 0 ? `
        <details style="margin-top: 8px; font-size: 10.5px; color: var(--color-text-secondary);">
          <summary style="cursor: pointer; font-weight: 600; color: #fbbf24;">⚠️ Borulama İsimlendirme ve Sınırlandırma Kapsam Kısıtları (${limitations.length} Teknik Not)</summary>
          <ul style="margin: 6px 0 0 18px; padding: 0; line-height: 1.5;">
            ${limitations.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
          </ul>
        </details>
      ` : ""}
    </div>
  ` : "";

  return `
    <div class="card" style="padding: 12px;">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; flex-wrap: wrap; gap: 6px;">
        <div style="display: flex; align-items: center; gap: 6px;">
          ${icon("activity", 15, "text-primary")}
          <span style="font-size: 13px; font-weight: 700;">${escapeHtml(t("station_pipe_matrix_title", lang))}</span>
          <span class="badge badge-primary" style="font-size: 10px;">${lines.length} ${escapeHtml(t("station_pipe_lines_badge", lang))}</span>
        </div>
        <div style="font-size: 11px; color: var(--color-text-secondary); display: flex; gap: 10px; align-items: center; flex-wrap: wrap;">
          <span>Barlow: <b>t = P·D / (2·SMYS·F)</b></span>
          <span>•</span>
          <span>Hız Sınırı: <b>v ≤ ${netMaxVel.toFixed(1)} m/s</b></span>
          <span>•</span>
          <span>Erozyon: <b>API RP 14E (v &lt; 122/√ρ)</b></span>
          <span>•</span>
          <span>Sürtünme: <b>Churchill (1977)</b></span>
        </div>
      </div>

      ${archSummaryHtml}
      ${spec4500Html}

      <div tabindex="0" role="region" aria-labelledby="pipe-sizing-table-caption" style="overflow-x: auto;">
        <table class="kasp-table" style="font-size: 11px; width: 100%; white-space: nowrap;">
          <caption id="pipe-sizing-table-caption" style="text-align: left; font-size: 10.5px; color: var(--color-text-secondary); padding-bottom: 6px;">
            İstasyon Ana &amp; Ünite Header Omurgası (Station Suction, Unit Suction, Unit Discharge, Station Discharge), Hız Sınırına Göre Kabul Edilebilir Çaplar ve Ekipman Branşman Matrisi
          </caption>
          <thead>
            <tr>
              <th scope="col" style="width: 62px; position: sticky; inset-inline-start: 0; background: var(--color-surface); z-index: 2;">Hat No</th>
              <th scope="col">Proses Hattı Tanımı</th>
              <th scope="col">${escapeHtml(t("pipe_col_hierarchy", lang))}</th>
              <th scope="col">${escapeHtml(t("pipe_col_boundaries", lang))}</th>
              <th scope="col" style="text-align: right;">Debi (kg/s)</th>
              <th scope="col" style="text-align: right;">Basınç (bar a)</th>
              <th scope="col" style="text-align: center;">Seçilen Çap (NPS)</th>
              <th scope="col">${escapeHtml(t("pipe_col_acceptable_nps", lang))}</th>
              <th scope="col" style="text-align: center;">Dış Çap (OD mm)</th>
              <th scope="col" style="text-align: center;">Çizelge &amp; Kalınlık (mm)</th>
              <th scope="col" style="text-align: right;">Min. Barlow (t_req)</th>
              <th scope="col" style="text-align: right;">Standart t_min</th>
              <th scope="col" style="text-align: center;">Standart</th>
              <th scope="col" style="text-align: right;">Gaz Hızı (v m/s)</th>
              <th scope="col" style="text-align: center;">Erozyon Oranı (EVR)</th>
              <th scope="col" style="text-align: right;">ΔP (bar/100m)</th>
              <th scope="col" style="text-align: right;">Ağırlık (kg/m)</th>
              <th scope="col" style="text-align: center;">Durum</th>
            </tr>
          </thead>
          <tbody>
            ${lines.map(line => {
              const tag = line.tag || line.line_id || "-";
              const name = line.name || "-";
              const hLevel = line.hierarchy_level || "equipment_branch";
              const hLabel = line.hierarchy_label || "Proses Borulaması";
              const parentHeader = line.parent_header || null;
              const fromB = line.from_boundary || "-";
              const toB = line.to_boundary || "-";
              const fullBoundaryTitle = `${fromB} ➔ ${toB}`;
              const shortBoundary = line.boundary_summary || fullBoundaryTitle;
              const hBadgeClass = hLevel === "main_header"
                ? "badge-primary"
                : hLevel === "mainline_tie_in"
                  ? "badge-neutral"
                  : "badge-success";

              const flow = line.flow_kgs !== undefined ? line.flow_kgs : (line.flow_kg_s || 0);
              const pressure = line.pressure_bar !== undefined ? line.pressure_bar : (line.p_bar || 0);
              const nps = line.nominal_size_in || (line.selected_pipe ? line.selected_pipe.nps : "-");
              const indivNps = line.individual_nominal_size_in || null;
              const acceptableSummary = line.acceptable_diameters_summary ||
                (Array.isArray(line.acceptable_nominals) && line.acceptable_nominals.length
                  ? line.acceptable_nominals.slice(0, 5).join(", ")
                  : nps);
              const allAcceptableTitle = Array.isArray(line.acceptable_nominals) && line.acceptable_nominals.length
                ? `Hız sınırı (≤ ${Number(line.max_velocity_ms || netMaxVel).toFixed(1)} m/s) için uygun tüm ticari çaplar: ${line.acceptable_nominals.join(", ")}`
                : acceptableSummary;
              const od = line.od_mm || (line.selected_pipe ? line.selected_pipe.od_mm : 0);
              const sch = line.schedule || (line.selected_pipe ? line.selected_pipe.schedule : "-");
              const thick = line.wall_thickness_mm !== undefined ? line.wall_thickness_mm : (line.selected_pipe ? line.selected_pipe.thickness_mm : 0);
              const treq = line.min_required_thickness_mm !== undefined ? line.min_required_thickness_mm : (line.selected_pipe ? line.selected_pipe.t_req_mm : 0);
              const v = line.actual_velocity_ms !== undefined ? line.actual_velocity_ms : (line.selected_pipe ? line.selected_pipe.velocity_m_s : 0);
              const lineMaxV = Number(line.max_velocity_ms || netMaxVel || 20.0);
              const evr = line.erosion_ratio_pct !== undefined ? line.erosion_ratio_pct : (line.selected_pipe ? line.selected_pipe.evr_percent : 0);
              const dp = line.pressure_drop_bar_per_100m !== undefined ? line.pressure_drop_bar_per_100m : (line.selected_pipe ? line.selected_pipe.dp_bar_per_100m : 0);
              const weight = line.pipe_weight_kg_m !== undefined ? line.pipe_weight_kg_m : (line.selected_pipe ? line.selected_pipe.weight_kg_m : 0);
              const status = line.velocity_status || (line.selected_pipe ? line.selected_pipe.status : "OK");
              const std = line.standard_recommendation || {};
              const stdMin = std.minimum_standard_thickness_mm;
              const stdOk = std.is_sufficient !== false && !std.error;

              const vColor = v > lineMaxV ? "#ef4444" : v > lineMaxV * 0.8 ? "#f59e0b" : "#10b981";
              const evrColor = evr > 80 ? "#ef4444" : evr > 60 ? "#f59e0b" : "#10b981";
              const isStatusOk = status.includes("Optimum") || status.includes("İzin Verilen") || status === "OK";

              return `
                <tr>
                  <th scope="row" style="position: sticky; inset-inline-start: 0; background: var(--color-surface); z-index: 1; font-family: var(--font-mono); font-weight: 700; color: #38bdf8; text-align: left;">${escapeHtml(tag)}</th>
                  <td style="font-weight: 600;">${escapeHtml(name)}</td>
                  <td>
                    <span class="badge ${hBadgeClass}" style="font-size: 9.5px;">${escapeHtml(hLabel)}</span>
                    ${parentHeader ? `<div style="font-size: 9.5px; color: var(--color-text-secondary); margin-top: 2px;">↳ ${escapeHtml(parentHeader)}</div>` : ""}
                  </td>
                  <td style="font-size: 10px; color: var(--color-text-secondary); max-width: 340px; overflow: hidden; text-overflow: ellipsis;" title="${escapeHtml(fullBoundaryTitle)}">
                    ${escapeHtml(shortBoundary)}
                  </td>
                  <td style="text-align: right; font-family: var(--font-mono);">${flow.toFixed(1)}</td>
                  <td style="text-align: right; font-family: var(--font-mono);">${pressure.toFixed(1)}</td>
                  <td style="text-align: center; font-family: var(--font-mono); font-weight: 700; color: #facc15;">
                    ${escapeHtml(nps)}
                    ${indivNps && indivNps !== nps ? `<div style="font-size: 9px; font-weight: 500; color: var(--color-text-secondary);" title="Ortak header kuralı öncesi tekil minimum çap">Tekil: ${escapeHtml(indivNps)}</div>` : ""}
                  </td>
                  <td style="font-size: 10px; font-family: var(--font-mono); color: #6ee7b7; max-width: 240px; overflow: hidden; text-overflow: ellipsis;" title="${escapeHtml(allAcceptableTitle)}">
                    ${escapeHtml(acceptableSummary)}
                  </td>
                  <td style="text-align: center; font-family: var(--font-mono);">${od ? od.toFixed(1) : "-"}</td>
                  <td style="text-align: center; font-family: var(--font-mono);">
                    <span class="badge badge-neutral" style="font-size: 10px;">Sch ${escapeHtml(sch)}</span>
                    <strong style="margin-left: 4px;">${thick ? thick.toFixed(2) + " mm" : "-"}</strong>
                  </td>
                  <td style="text-align: right; font-family: var(--font-mono); color: var(--color-text-secondary);">
                    ${treq ? treq.toFixed(2) + " mm" : "-"}
                  </td>
                  <td style="text-align: right; font-family: var(--font-mono); color: var(--color-text-secondary);" title="${escapeHtml(std.tolerance_rule || "")}">
                    ${stdMin ? Number(stdMin).toFixed(2) + " mm" : "-"}
                  </td>
                  <td style="text-align: center; font-size: 10px;">
                    <span class="badge ${stdOk ? 'badge-success' : 'badge-warning'}" title="${escapeHtml(std.tolerance_rule || "")}">
                      ${escapeHtml(std.standard || "BOTAŞ")} ${escapeHtml(std.psl_level || "PSL2")}
                    </span>
                  </td>
                  <td style="text-align: right; font-family: var(--font-mono); font-weight: 700; color: ${vColor};">
                    ${v.toFixed(2)} m/s
                  </td>
                  <td style="text-align: center; font-family: var(--font-mono);">
                    <div style="display: flex; align-items: center; justify-content: center; gap: 4px;">
                      <div style="width: 44px; height: 6px; background: rgba(255,255,255,0.1); border-radius: 3px; overflow: hidden;">
                        <div style="width: ${Math.min(100, evr)}%; height: 100%; background: ${evrColor};"></div>
                      </div>
                      <span style="font-size: 10px; color: ${evrColor}; font-weight: 600;">%${evr.toFixed(1)}</span>
                    </div>
                  </td>
                  <td style="text-align: right; font-family: var(--font-mono); font-size: 10px;">
                    ${dp !== undefined ? dp.toFixed(3) : "-"}
                  </td>
                  <td style="text-align: right; font-family: var(--font-mono); font-size: 10px; color: var(--color-text-secondary);">
                    ${weight ? weight.toFixed(1) : "-"}
                  </td>
                  <td style="text-align: center;">
                    <span class="badge ${isStatusOk ? 'badge-success' : 'badge-warning'}" style="font-size: 10px;">
                      ${escapeHtml(isStatusOk ? "OK" : status)}
                    </span>
                  </td>
                </tr>
              `;
            }).join("")}
          </tbody>
        </table>
      </div>

      <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 8px; font-size: 10px; color: var(--color-text-secondary); flex-wrap: wrap; gap: 6px;">
        <div>
          <span>Boru Malzemesi: <b>${escapeHtml(piping.pipe_material || "API 5L X70")} (SMYS = 485 MPa)</b></span>
          <span style="margin: 0 6px;">•</span>
          <span>İstasyon Emniyet Tasarım Faktörü: <b>F = ${piping.design_factor_F ? piping.design_factor_F.toFixed(2) : "0.50"} (ASME B31.8 Sınıf 1 Bölüm 2 Kompresör Sahası)</b></span>
          <span style="margin: 0 6px;">•</span>
          <span>Boru Standardı: <b>${escapeHtml(piping.pipe_standard || "BOTAŞ")} ${escapeHtml(piping.psl_level || "PSL2")}</b></span>
        </div>
        <div>
          <span>Hız Kriteri: v ≤ ${netMaxVel.toFixed(1)} m/s (Kullanıcı Sınırı), v_erozyon = 122 / √ρ</span>
        </div>
      </div>
    </div>
  `;
}

const PROVENANCE_BADGE_STYLE = {
  design_tab: { labelKey: "station_src_design", bg: "rgba(56, 189, 248, 0.14)", fg: "#38bdf8", border: "rgba(56, 189, 248, 0.45)" },
  station_3d_calc: { labelKey: "station_src_calc", bg: "rgba(16, 185, 129, 0.14)", fg: "#34d399", border: "rgba(16, 185, 129, 0.45)" },
  user_input: { labelKey: "station_src_user", bg: "rgba(245, 158, 11, 0.15)", fg: "#fbbf24", border: "rgba(245, 158, 11, 0.45)" },
  fixed_default: { labelKey: "station_src_default", bg: "rgba(148, 163, 184, 0.14)", fg: "#cbd5e1", border: "rgba(148, 163, 184, 0.4)" },
};

function renderParameterProvenancePanel(paramSources, filterSource = "all", searchQuery = "", lang = "tr") {
  if (!paramSources || typeof paramSources !== "object") return "";
  const equipmentList = Array.isArray(paramSources.equipment) ? paramSources.equipment : [];
  const pipingList = Array.isArray(paramSources.piping) ? paramSources.piping : [];
  const couplingChecks = paramSources.coupling_checks || {};
  const q = String(searchQuery || "").trim().toLowerCase();

  const counts = { all: 0, design_tab: 0, station_3d_calc: 0, user_input: 0, fixed_default: 0 };
  for (const grp of [...equipmentList, ...pipingList]) {
    for (const p of grp.parameters || []) {
      counts.all += 1;
      if (counts[p.source] !== undefined) counts[p.source] += 1;
    }
  }

  function filterParams(groupName, groupTag, params) {
    return (params || []).filter((p) => {
      if (filterSource !== "all" && p.source !== filterSource) return false;
      if (!q) return true;
      const hay = `${groupName} ${groupTag} ${p.label || ""} ${p.param || ""} ${p.value ?? ""} ${p.origin || ""}`.toLowerCase();
      return hay.includes(q);
    });
  }

  function renderSourceBadge(src) {
    const meta = PROVENANCE_BADGE_STYLE[src] || PROVENANCE_BADGE_STYLE.fixed_default;
    return `<span style="display:inline-block; padding: 1px 7px; border-radius: 10px; font-size: 9.5px; font-weight: 700; background:${meta.bg}; color:${meta.fg}; border:1px solid ${meta.border}; white-space:nowrap;">${escapeHtml(t(meta.labelKey, lang))}</span>`;
  }

  function renderSectionCards(items, sectionIcon) {
    const rendered = items.map((item) => {
      const matched = filterParams(item.name || "", item.tag || item.key || "", item.parameters);
      if (!matched.length) return "";
      return `
        <details open style="border: 1px solid var(--color-border); border-radius: var(--radius-sm); background: var(--color-surface-hover); overflow: hidden;">
          <summary style="cursor: pointer; padding: 7px 10px; font-size: 11.5px; font-weight: 700; display: flex; justify-content: space-between; align-items: center; gap: 8px; background: rgba(15, 23, 42, 0.3);">
            <span>${sectionIcon} <span style="font-family: var(--font-mono); color: #38bdf8;">${escapeHtml(item.tag || item.key || "-")}</span> — ${escapeHtml(item.name || "-")}</span>
            <span class="badge badge-neutral" style="font-size: 9.5px;">${matched.length} Parametre</span>
          </summary>
          <div style="overflow-x: auto;">
            <table class="kasp-table" style="font-size: 10.5px; width: 100%; margin: 0;">
              <thead>
                <tr>
                  <th scope="col" style="width: 24%;">Parametre</th>
                  <th scope="col" style="width: 18%; text-align: right;">Aktif Değer</th>
                  <th scope="col" style="width: 16%; text-align: center;">Veri Kaynağı</th>
                  <th scope="col">Nereden Alındı / Dinamik Etkileşim Açıklaması</th>
                </tr>
              </thead>
              <tbody>
                ${matched.map((p) => `
                  <tr>
                    <td style="font-weight: 600;">
                      ${escapeHtml(p.label || p.param)}
                      <span style="display: block; font-size: 9px; font-family: var(--font-mono); color: var(--color-text-secondary);">${escapeHtml(p.param || "")}</span>
                    </td>
                    <td style="text-align: right; font-family: var(--font-mono); font-weight: 700; color: #f8fafc;">
                      ${escapeHtml(p.value ?? "-")} ${p.unit ? `<span style="font-weight: 400; color: var(--color-text-secondary);">${escapeHtml(p.unit)}</span>` : ""}
                    </td>
                    <td style="text-align: center;">${renderSourceBadge(p.source)}</td>
                    <td style="font-size: 10px; color: var(--color-text-secondary);">${escapeHtml(p.origin || "-")}</td>
                  </tr>
                `).join("")}
              </tbody>
            </table>
          </div>
        </details>
      `;
    }).filter(Boolean);

    if (!rendered.length) {
      return `<div style="padding: 10px; font-size: 11px; color: var(--color-text-secondary); text-align: center;">Seçilen filtreye uygun parametre bulunamadı.</div>`;
    }
    return `<div style="display: flex; flex-direction: column; gap: 8px;">${rendered.join("")}</div>`;
  }

  const filterButtons = [
    ["all", `${t("station_src_all", lang)} (${counts.all})`],
    ["design_tab", `${t("station_src_design", lang)} (${counts.design_tab})`],
    ["station_3d_calc", `${t("station_src_calc", lang)} (${counts.station_3d_calc})`],
    ["user_input", `${t("station_src_user", lang)} (${counts.user_input})`],
    ["fixed_default", `${t("station_src_default", lang)} (${counts.fixed_default})`],
  ];

  return `
    <div class="card" style="padding: 12px;">
      <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; flex-wrap: wrap; margin-bottom: 10px;">
        <div>
          <div style="font-size: 13px; font-weight: 700; display: flex; align-items: center; gap: 6px;">
            ${icon("layers", 15, "text-primary")}
            <span>${escapeHtml(t("station_provenance_title", lang))}</span>
          </div>
          <div style="font-size: 10.5px; color: var(--color-text-secondary); margin-top: 2px;">
            ${escapeHtml(t("station_provenance_subtitle", lang))}
          </div>
        </div>
        <div style="display: flex; gap: 6px; align-items: center; flex-wrap: wrap;">
          <input
            type="search"
            id="input-prov-search"
            value="${escapeHtml(searchQuery)}"
            placeholder="Ekipman, hat veya parametre ara..."
            aria-label="Değer kaynağı matrisinde ara"
            style="font-size: 11px; padding: 4px 8px; width: 210px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 6px; color: var(--color-text);"
          />
          ${filterButtons.map(([key, lbl]) => `
            <button
              type="button"
              data-prov-filter="${key}"
              class="btn btn-sm ${filterSource === key ? "btn-primary" : "btn-secondary"}"
              style="font-size: 10.5px; padding: 3px 8px;"
            >${escapeHtml(lbl)}</button>
          `).join("")}
        </div>
      </div>

      <!-- Dynamic Coupling Verification Banner -->
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 8px; margin-bottom: 12px;">
        <div style="padding: 7px 10px; border-radius: 6px; background: rgba(16, 185, 129, 0.10); border: 1px solid rgba(16, 185, 129, 0.35); font-size: 10.5px;">
          <div style="font-weight: 700; color: #34d399;">✓ Kompresör Çıkış = Gas Cooler Giriş</div>
          <div style="color: var(--color-text-secondary); margin-top: 2px;">N05 Basma &amp; E-101 Giriş Sıcaklığı birebir kenetli (${couplingChecks.compressor_outlet_equals_cooler_inlet ? "Doğrulandı" : "Kontrol Et"})</div>
        </div>
        <div style="padding: 7px 10px; border-radius: 6px; background: rgba(56, 189, 248, 0.10); border: 1px solid rgba(56, 189, 248, 0.35); font-size: 10.5px;">
          <div style="font-weight: 700; color: #38bdf8;">✓ 4 Ana/Ünite Header Ortak Çap Kuralı</div>
          <div style="color: var(--color-text-secondary); margin-top: 2px;">Station/Unit Suction &amp; Discharge en büyük header çapına eşit (${couplingChecks.headers_equalized_to_max_non_equipment_header ? "Doğrulandı" : "Kontrol Et"})</div>
        </div>
        <div style="padding: 7px 10px; border-radius: 6px; background: rgba(245, 158, 11, 0.10); border: 1px solid rgba(245, 158, 11, 0.35); font-size: 10.5px;">
          <div style="font-weight: 700; color: #fbbf24;">✓ ESD &amp; PSV Atmosfer Şartları</div>
          <div style="color: var(--color-text-secondary); margin-top: 2px;">P_atm &amp; T_atm Tasarım Sekmesinden dinamik alınır (${couplingChecks.esd_and_psv_coupled_to_design_ambient ? "Doğrulandı" : "Kontrol Et"})</div>
        </div>
        <div style="padding: 7px 10px; border-radius: 6px; background: rgba(168, 85, 247, 0.10); border: 1px solid rgba(168, 85, 247, 0.35); font-size: 10.5px;">
          <div style="font-weight: 700; color: #c084fc;">✓ ESD Basınç &amp; Hacim Eşleşmesi</div>
          <div style="color: var(--color-text-secondary); margin-top: 2px;">YB = P_out, DB = P_in + kullanıcı boşaltma hacimleri (${couplingChecks.esd_hp_uses_compressor_p_out_and_lp_uses_p_in ? "Doğrulandı" : "Kontrol Et"})</div>
        </div>
      </div>

      <div style="display: grid; grid-template-columns: 1fr; gap: 12px;">
        <div>
          <div style="font-size: 12px; font-weight: 700; color: var(--color-primary); margin-bottom: 6px;">⚙️ A. Proses Ekipmanları Değer Kaynakları (${equipmentList.length} Ekipman Grubu)</div>
          ${renderSectionCards(equipmentList, "⚙️")}
        </div>
        <div>
          <div style="font-size: 12px; font-weight: 700; color: #facc15; margin-bottom: 6px;">🔩 B. İstasyon Header &amp; Ekipman Borulaması Değer Kaynakları (${pipingList.length} Boru Hattı)</div>
          ${renderSectionCards(pipingList, "🔩")}
        </div>
      </div>
    </div>
  `;
}
