/**
 * KASP Project & Calculation Store
 * Central state for process design inputs, active gas mixture,
 * kij matrix overrides, calculation results, and Plotly charts.
 */

import { createStore } from "./store.js";
import { api } from "../api/client.js";
import { showToast } from "./uiStore.js";

const R_UNIVERSAL_J_MOL_K = 8.314462618;
const STD_PRESS_PA = 101325.0;
const STD_TEMP_ISO_K = 288.15; // 15°C (Sm³/h, MMSCMD)
const STD_TEMP_NORMAL_K = 273.15; // 0°C (Nm³/h)
const US_STD_PRESS_PA = 101559.8; // 14.73 psia (MMSCFD)
const US_STD_TEMP_K = 288.7056; // 60°F (MMSCFD)
const FT3_TO_M3 = 0.028316846592;

export const MOLAR_MASSES = {
  METHANE: 16.043,
  ETHANE: 30.069,
  PROPANE: 44.096,
  ISOBUTANE: 58.123,
  BUTANE: 58.123,
  ISOPENTANE: 72.150,
  PENTANE: 72.150,
  HEXANE: 86.177,
  HEPTANE: 100.204,
  OCTANE: 114.231,
  NONANE: 128.258,
  DECANE: 142.285,
  HYDROGEN: 2.016,
  HYDROGENSULFIDE: 34.082,
  NITROGEN: 28.014,
  CARBONDIOXIDE: 44.010,
  WATER: 18.015,
  OXYGEN: 31.999,
  ARGON: 39.948,
  HELIUM: 4.003,
  NEON: 20.180,
  KRYPTON: 83.798,
  XENON: 131.293,
  AIR: 28.966,
};

const ALIAS_MAP = {
  CO2: "CARBONDIOXIDE",
  "CARBON DIOXIDE": "CARBONDIOXIDE",
  CH4: "METHANE",
  H2S: "HYDROGENSULFIDE",
  "HYDROGEN SULFIDE": "HYDROGENSULFIDE",
  H2O: "WATER",
  IBUTANE: "ISOBUTANE",
  IC4H10: "ISOBUTANE",
  IPENTANE: "ISOPENTANE",
  N2: "NITROGEN",
  O2: "OXYGEN",
  H2: "HYDROGEN",
  AR: "ARGON",
  HE: "HELIUM",
  C2H6: "ETHANE",
  C3H8: "PROPANE",
  NC4H10: "BUTANE",
  C4H10: "BUTANE",
};

export function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

export function computeGasMixtureMW(gasComp) {
  if (!gasComp || typeof gasComp !== "object") return 18.2;
  let totalPct = 0;
  let weightedMw = 0;
  for (const [rawKey, rawVal] of Object.entries(gasComp)) {
    const val = parseFloat(rawVal);
    if (!Number.isFinite(val) || val <= 0) continue;
    const upper = String(rawKey || "").trim().toUpperCase();
    const canonical = ALIAS_MAP[upper] || upper;
    const compMw = MOLAR_MASSES[canonical];
    if (compMw !== undefined) {
      totalPct += val;
      weightedMw += val * compMw;
    }
  }
  if (totalPct <= 0) return 18.2;
  return weightedMw / totalPct;
}

export function computeStandardGasDensityKgm3(gasComp, condition = "iso") {
  const mwKgMol = computeGasMixtureMW(gasComp) / 1000.0;
  if (condition === "normal") {
    return (STD_PRESS_PA * mwKgMol) / (R_UNIVERSAL_J_MOL_K * STD_TEMP_NORMAL_K);
  }
  if (condition === "us_field") {
    return (US_STD_PRESS_PA * mwKgMol) / (R_UNIVERSAL_J_MOL_K * US_STD_TEMP_K);
  }
  return (STD_PRESS_PA * mwKgMol) / (R_UNIVERSAL_J_MOL_K * STD_TEMP_ISO_K);
}

export function convertPressureToBarA(val, unit = "bar(a)") {
  const num = parseFloat(val);
  if (!Number.isFinite(num)) return 0;
  const u = String(unit || "bar(a)").trim();
  if (u === "bar(g)") return num + 1.01325;
  if (u === "kPa") return num / 100.0;
  if (u === "MPa") return num * 10.0;
  if (u === "Pa") return num / 100000.0;
  if (u === "psi" || u === "psia") return num / 14.5037738;
  if (u === "psig") return (num + 14.6959488) / 14.5037738;
  if (u === "atm") return num * 1.01325;
  return num;
}

export function convertPressureUnit(val, fromU, toU) {
  const num = parseFloat(val);
  if (!Number.isFinite(num) || fromU === toU) return val;
  const barA = convertPressureToBarA(num, fromU);
  let res = barA;
  const u = String(toU || "bar(a)").trim();
  if (u === "bar(g)") res = Math.max(-1.0, barA - 1.01325);
  else if (u === "kPa") res = barA * 100.0;
  else if (u === "MPa") res = barA / 10.0;
  else if (u === "psi" || u === "psia") res = barA * 14.5037738;
  else if (u === "psig") res = Math.max(-14.5, barA * 14.5037738 - 14.6959488);
  return Math.round(res * 100) / 100;
}

export function convertTempToC(val, unit = "°C") {
  const num = parseFloat(val);
  if (!Number.isFinite(num)) return 25.0;
  const u = String(unit || "°C").trim();
  if (u === "K") return num - 273.15;
  if (u === "°F" || u === "F") return (num - 32.0) * (5.0 / 9.0);
  return num;
}

export function convertTemperatureUnit(val, fromU, toU) {
  const num = parseFloat(val);
  if (!Number.isFinite(num) || fromU === toU) return val;
  const c = convertTempToC(num, fromU);
  let res = c;
  const u = String(toU || "°C").trim();
  if (u === "K") res = c + 273.15;
  else if (u === "°F" || u === "F") res = c * (9.0 / 5.0) + 32.0;
  return Math.round(res * 10) / 10;
}

export function convertFlowWithMW(val, fromU, toU, gasComp) {
  const num = parseFloat(val);
  if (!Number.isFinite(num) || num <= 0 || fromU === toU) return Number.isFinite(num) ? num : 0;

  const mwGmol = computeGasMixtureMW(gasComp);
  const rhoIso = computeStandardGasDensityKgm3(gasComp, "iso");
  const rhoNormal = computeStandardGasDensityKgm3(gasComp, "normal");
  const rhoUs = computeStandardGasDensityKgm3(gasComp, "us_field");

  const fU = String(fromU || "kg/s").trim();
  const tU = String(toU || "kg/s").trim();
  // m³/h / ACMH is actual inlet volume and cannot be converted without inlet P/T.
  // Never silently alias it to standard (ISO) volume.
  const fActual = fU === "m³/h" || fU === "m3/h" || fU.toUpperCase() === "ACMH";
  const tActual = tU === "m³/h" || tU === "m3/h" || tU.toUpperCase() === "ACMH";
  if (fActual || tActual) return NaN;

  let kgs = num;
  if (fU === "kg/h") kgs = num / 3600.0;
  else if (fU === "t/h" || fU === "ton/h") kgs = (num * 1000.0) / 3600.0;
  else if (fU === "Sm³/h" || fU === "Sm3/h") {
    kgs = (num * rhoIso) / 3600.0;
  } else if (fU === "Nm³/h" || fU === "Nm3/h") {
    kgs = (num * rhoNormal) / 3600.0;
  } else if (fU === "MMSCMD") {
    kgs = (num * 1e6 * rhoIso) / 86400.0;
  } else if (fU === "MMSCFD") {
    kgs = (num * 1e6 * FT3_TO_M3 * rhoUs) / 86400.0;
  } else if (fU === "kmol/h" || fU === "kgmol/h") {
    kgs = (num * mwGmol) / 3600.0;
  }

  let res = kgs;
  if (tU === "kg/h") res = kgs * 3600.0;
  else if (tU === "t/h" || tU === "ton/h") res = (kgs * 3600.0) / 1000.0;
  else if (tU === "Sm³/h" || tU === "Sm3/h") {
    res = rhoIso > 0 ? (kgs * 3600.0) / rhoIso : 0;
  } else if (tU === "Nm³/h" || tU === "Nm3/h") {
    res = rhoNormal > 0 ? (kgs * 3600.0) / rhoNormal : 0;
  } else if (tU === "MMSCMD") {
    res = rhoIso > 0 ? (kgs * 86400.0) / (1e6 * rhoIso) : 0;
  } else if (tU === "MMSCFD") {
    res = rhoUs > 0 ? (kgs * 86400.0) / (1e6 * FT3_TO_M3 * rhoUs) : 0;
  } else if (tU === "kmol/h" || tU === "kgmol/h") {
    res = mwGmol > 0 ? (kgs * 3600.0) / mwGmol : 0;
  }
  return res;
}

function withoutAirCoolerModule(modules) {
  if (!modules || !modules.air_cooler) return modules || {};
  const next = { ...modules };
  delete next.air_cooler;
  return next;
}

const PROCESS_CACHE_INVALIDATION_FIELDS = new Set([
  "p_in",
  "p_in_unit",
  "p_out",
  "p_out_unit",
  "t_in",
  "t_in_unit",
  "flow",
  "flow_unit",
  "eos_model",
  "calc_method",
  "poly_eff",
  "mech_eff",
  "therm_eff",
  "num_units",
  "num_stages",
  "intercooler_t",
  "intercooler_dp_pct",
  "ambient_temp",
  "altitude",
  "humidity",
]);

const RECOMMENDATION_TRIGGER_FIELDS = new Set([
  "p_in",
  "p_in_unit",
  "p_out",
  "p_out_unit",
  "eos_model",
  "calc_method",
]);

let recDebounceTimer = null;
export function scheduleRecommendationsRefresh(delayMs = 250) {
  clearTimeout(recDebounceTimer);
  recDebounceTimer = setTimeout(() => {
    fetchRecommendations();
  }, delayMs);
}

// Single source for the web sidebar's initial form values. Keep these equal to
// the PyQt desktop startup form (kasp/ui/design_left_panel_builders.py) so an
// untouched project yields the same design calculation on both clients.
export const DEFAULT_DESIGN_INPUTS = {
  project_name: "Yeni Kompresör Projesi",
  notes: "",
  p_in: 49.65,
  p_in_unit: "bar(g)",
  p_out: 75.0,
  p_out_unit: "bar(a)",
  t_in: 19.0,
  t_in_unit: "°C",
  flow: 1985000.0,
  flow_unit: "Sm³/h",
  gas_comp: {
    METHANE: 85.0,
    ETHANE: 7.0,
    PROPANE: 4.0,
    NITROGEN: 2.0,
    CARBONDIOXIDE: 2.0,
  },
  eos_model: "coolprop",
  calc_method: "Metot 5: Huntington-RK45 Diferansiyel",
  poly_eff: 90.0,
  mech_eff: 98.0,
  therm_eff: 35.0,
  num_units: 1,
  num_stages: 1,
  intercooler_t: 40.0,
  intercooler_dp_pct: 2.0,
  ambient_temp: 15.0,
  ambient_pressure: 101.325,
  altitude: 0,
  humidity: 60,
  solver_method: "aj_nr",
  lhv_source: "kasp",
  use_consistency_iteration: false,
  max_consistency_iter: 20,
  consistency_tolerance: 0.1,
  custom_kij: {},
};

const LEGACY_EOS_MAP = {
  rk: "srk",
  "redlich-kwong": "srk",
  vdw: "pr",
  van_der_waals: "pr",
  bwrs: "gerg2008",
  "peng-robinson": "pr",
  "gerg-2008": "gerg2008",
  "aga8-dc92": "aga8",
  heos: "coolprop",
};

export function normalizeGasKey(rawKey) {
  const upper = String(rawKey || "").trim().toUpperCase();
  return ALIAS_MAP[upper] || upper;
}

export function sanitizeActiveGasComp(rawComp, fallbackComp = DEFAULT_DESIGN_INPUTS.gas_comp) {
  if (!rawComp || typeof rawComp !== "object") {
    return { ...fallbackComp };
  }
  const cleaned = {};
  for (const [rawKey, rawVal] of Object.entries(rawComp)) {
    const val = parseFloat(rawVal);
    if (!Number.isFinite(val) || val <= 0) continue;
    const key = normalizeGasKey(rawKey);
    if (!key) continue;
    cleaned[key] = Math.round(((cleaned[key] || 0) + val) * 10000) / 10000;
  }
  return Object.keys(cleaned).length > 0 ? cleaned : { ...fallbackComp };
}

export function computeInputsSignature(inputs) {
  if (!inputs || typeof inputs !== "object") return "";
  const canonical = {};
  Object.keys(inputs)
    .filter((k) => k !== "project_name")
    .sort()
    .forEach((k) => {
      const val = inputs[k];
      if (val && typeof val === "object" && !Array.isArray(val)) {
        const sortedSub = {};
        Object.keys(val)
          .sort()
          .forEach((sk) => {
            sortedSub[sk] = val[sk];
          });
        canonical[k] = sortedSub;
      } else {
        canonical[k] = val;
      }
    });
  return JSON.stringify(canonical);
}

function deriveStaleState(nextInputs, state) {
  return Boolean(
    state?.results &&
      state?.lastCalculatedSignature &&
      computeInputsSignature(nextInputs) !== state.lastCalculatedSignature
  );
}

export function hydrateProjectSnapshot(snapshot) {
  if (!snapshot || typeof snapshot !== "object") return;
  const rawInputs = snapshot.inputs && typeof snapshot.inputs === "object" ? snapshot.inputs : {};
  const rawEos = String(rawInputs.eos_model || rawInputs.eos_method || DEFAULT_DESIGN_INPUTS.eos_model)
    .trim()
    .toLowerCase();
  const normalizedEos = LEGACY_EOS_MAP[rawEos] || rawEos || DEFAULT_DESIGN_INPUTS.eos_model;
  const normalizedMethod =
    rawInputs.calc_method || rawInputs.method || DEFAULT_DESIGN_INPUTS.calc_method;
  const normalizedAmbient =
    rawInputs.ambient_temp !== undefined && rawInputs.ambient_temp !== null
      ? Number(rawInputs.ambient_temp)
      : rawInputs.t_amb !== undefined && rawInputs.t_amb !== null
        ? Number(rawInputs.t_amb)
        : DEFAULT_DESIGN_INPUTS.ambient_temp;

  const mergedInputs = {
    ...DEFAULT_DESIGN_INPUTS,
    ...rawInputs,
    eos_model: normalizedEos,
    calc_method: normalizedMethod,
    ambient_temp: Number.isFinite(normalizedAmbient) ? normalizedAmbient : DEFAULT_DESIGN_INPUTS.ambient_temp,
    gas_comp: sanitizeActiveGasComp(rawInputs.gas_comp, DEFAULT_DESIGN_INPUTS.gas_comp),
    custom_kij:
      rawInputs.custom_kij && typeof rawInputs.custom_kij === "object"
        ? { ...rawInputs.custom_kij }
        : {},
  };

  const resObj = snapshot.results && typeof snapshot.results === "object" ? snapshot.results : null;
  const loadedModules = snapshot.modules || resObj?.module_results || {};
  const loadedStation = snapshot.station_data || resObj?.station_data || null;
  const loadedUnits = Array.isArray(snapshot.selected_units)
    ? snapshot.selected_units
    : Array.isArray(resObj?.selected_units)
      ? resObj.selected_units
      : [];
  const loadedCharts = snapshot.charts || resObj?.charts || null;
  const loadedWarnings = Array.isArray(snapshot.warnings)
    ? snapshot.warnings
    : Array.isArray(resObj?.warnings)
      ? resObj.warnings
      : [];

  projectStore.setState({
    inputs: mergedInputs,
    results: resObj,
    selectedUnits: loadedUnits,
    charts: loadedCharts,
    warnings: loadedWarnings,
    modules: loadedModules,
    stationData: loadedStation,
    lastCalculatedSignature: resObj ? computeInputsSignature(mergedInputs) : null,
    isResultsStale: false,
    hasUnsavedChanges: false,
    error: null,
  });
  recalculateGasTotal();
  recalculateLiveMetrics();
  scheduleRecommendationsRefresh(50);
}

export const projectStore = createStore({
  inputs: { ...DEFAULT_DESIGN_INPUTS },
  results: null,
  warnings: [],
  selectedUnits: [],
  charts: null,
  isCalculating: false,
  lastCalculatedSignature: null,
  isResultsStale: false,
  hasUnsavedChanges: false,
  error: null,
  recommendations: null,
  kijMatrixData: null,
  liveMetrics: (() => {
    // Derive the initial PR from DEFAULT_DESIGN_INPUTS instead of a stale literal.
    const pInBar = convertPressureToBarA(DEFAULT_DESIGN_INPUTS.p_in, DEFAULT_DESIGN_INPUTS.p_in_unit);
    const pOutBar = convertPressureToBarA(DEFAULT_DESIGN_INPUTS.p_out, DEFAULT_DESIGN_INPUTS.p_out_unit);
    return {
      pr: pInBar > 0 && pOutBar > 0 ? Math.round((pOutBar / pInBar) * 1000) / 1000 : 1.0,
      delta_p_bar: Math.round((pOutBar - pInBar) * 100) / 100,
      valid: pOutBar > pInBar,
    };
  })(),
  gasTotal: 100.0,
  presets: [],
  modules: {},
  stationData: null,
});

export function markProjectSaved() {
  projectStore.setState({ hasUnsavedChanges: false });
}

export function resetDesignInputs() {
  const nextInputs = {
    ...DEFAULT_DESIGN_INPUTS,
    gas_comp: { ...DEFAULT_DESIGN_INPUTS.gas_comp },
    custom_kij: {},
  };
  projectStore.setState((s) => ({
    inputs: nextInputs,
    modules: withoutAirCoolerModule(s.modules),
    isResultsStale: deriveStaleState(nextInputs, s),
    hasUnsavedChanges: false,
    error: null,
  }));
  recalculateGasTotal();
  recalculateLiveMetrics();
  scheduleRecommendationsRefresh(50);
}

export function invalidateAirCoolerCache() {
  projectStore.setState((s) => ({
    modules: withoutAirCoolerModule(s.modules),
  }));
}

export function updateInput(field, value) {
  const shouldClearCooler = PROCESS_CACHE_INVALIDATION_FIELDS.has(field);
  projectStore.setState((s) => {
    const nextInputs = { ...s.inputs, [field]: value };
    return {
      inputs: nextInputs,
      modules: shouldClearCooler ? withoutAirCoolerModule(s.modules) : s.modules,
      isResultsStale: deriveStaleState(nextInputs, s),
      hasUnsavedChanges: true,
    };
  });
  recalculateLiveMetrics();
  if (RECOMMENDATION_TRIGGER_FIELDS.has(field)) {
    scheduleRecommendationsRefresh();
  }
}

export function updateGasComponent(component, percentage) {
  const key = normalizeGasKey(component);
  if (!key) return;
  const parsed = parseFloat(percentage);
  const safeVal = Number.isFinite(parsed) && parsed >= 0 ? parsed : 0;
  projectStore.setState((s) => {
    const nextComp = { ...s.inputs.gas_comp, [key]: safeVal };
    const nextInputs = { ...s.inputs, gas_comp: nextComp };
    return {
      inputs: nextInputs,
      modules: withoutAirCoolerModule(s.modules),
      isResultsStale: deriveStaleState(nextInputs, s),
      hasUnsavedChanges: true,
    };
  });
  recalculateGasTotal();
  scheduleRecommendationsRefresh();
}

export function addGasComponent(component, initialPct = null) {
  const key = normalizeGasKey(component);
  if (!key) return;
  projectStore.setState((s) => {
    const currentComp = s.inputs.gas_comp || {};
    if (Object.prototype.hasOwnProperty.call(currentComp, key)) {
      return {};
    }
    const currentTotal = Object.values(currentComp).reduce((a, b) => a + (parseFloat(b) || 0), 0);
    const suggested =
      initialPct !== null && Number.isFinite(parseFloat(initialPct))
        ? Math.max(0, parseFloat(initialPct))
        : currentTotal < 99.99
          ? Math.max(0, Math.round((100.0 - currentTotal) * 100) / 100)
          : 0;
    const nextComp = { ...currentComp, [key]: suggested };
    const nextInputs = { ...s.inputs, gas_comp: nextComp };
    return {
      inputs: nextInputs,
      modules: withoutAirCoolerModule(s.modules),
      isResultsStale: deriveStaleState(nextInputs, s),
      hasUnsavedChanges: true,
    };
  });
  recalculateGasTotal();
  scheduleRecommendationsRefresh();
}

export function removeGasComponent(component) {
  const key = normalizeGasKey(component);
  if (!key) return;
  projectStore.setState((s) => {
    const nextComp = { ...(s.inputs.gas_comp || {}) };
    delete nextComp[key];
    const nextInputs = { ...s.inputs, gas_comp: nextComp };
    return {
      inputs: nextInputs,
      modules: withoutAirCoolerModule(s.modules),
      isResultsStale: deriveStaleState(nextInputs, s),
      hasUnsavedChanges: true,
    };
  });
  recalculateGasTotal();
  scheduleRecommendationsRefresh();
}

export function balanceGasComponent(component) {
  const key = normalizeGasKey(component);
  if (!key) return;
  projectStore.setState((s) => {
    const currentComp = s.inputs.gas_comp || {};
    let othersSum = 0;
    for (const [k, v] of Object.entries(currentComp)) {
      if (k === key) continue;
      othersSum += parseFloat(v) || 0;
    }
    const remaining = Math.max(0, Math.round((100.0 - othersSum) * 100) / 100);
    const nextComp = { ...currentComp, [key]: remaining };
    return {
      inputs: { ...s.inputs, gas_comp: nextComp },
      modules: withoutAirCoolerModule(s.modules),
    };
  });
  recalculateGasTotal();
  fetchRecommendations();
}

export function normalizeGasComposition() {
  projectStore.setState((s) => {
    const currentComp = s.inputs.gas_comp || {};
    const entries = Object.entries(currentComp).map(([k, v]) => [k, Math.max(0, parseFloat(v) || 0)]);
    const total = entries.reduce((acc, [, v]) => acc + v, 0);
    if (total <= 0) return {};
    const nextComp = {};
    let running = 0;
    entries.forEach(([k, v], idx) => {
      if (idx === entries.length - 1) {
        nextComp[k] = Math.max(0, Math.round((100.0 - running) * 100) / 100);
      } else {
        const scaled = Math.round(((v / total) * 100.0) * 100) / 100;
        nextComp[k] = scaled;
        running += scaled;
      }
    });
    const nextInputs = { ...s.inputs, gas_comp: nextComp };
    return {
      inputs: nextInputs,
      modules: withoutAirCoolerModule(s.modules),
      isResultsStale: deriveStaleState(nextInputs, s),
      hasUnsavedChanges: true,
    };
  });
  recalculateGasTotal();
  scheduleRecommendationsRefresh();
}

export function setCustomKijOverride(pair, value) {
  projectStore.setState((s) => {
    const nextKij = { ...s.inputs.custom_kij, [pair]: parseFloat(value) };
    return {
      inputs: { ...s.inputs, custom_kij: nextKij },
      modules: withoutAirCoolerModule(s.modules),
    };
  });
}

export function clearCustomKijOverrides() {
  projectStore.setState((s) => {
    const nextInputs = { ...s.inputs, custom_kij: {} };
    return {
      inputs: nextInputs,
      modules: withoutAirCoolerModule(s.modules),
      isResultsStale: deriveStaleState(nextInputs, s),
      hasUnsavedChanges: true,
    };
  });
}

export function recalculateGasTotal() {
  const comp = projectStore.getState().inputs.gas_comp;
  const total = Object.values(comp).reduce((a, b) => a + (parseFloat(b) || 0), 0);
  projectStore.setState({ gasTotal: Math.round(total * 100) / 100 });
}

export function recalculateLiveMetrics() {
  const { p_in, p_in_unit, p_out, p_out_unit } = projectStore.getState().inputs;
  const pInBar = convertPressureToBarA(p_in, p_in_unit);
  const pOutBar = convertPressureToBarA(p_out, p_out_unit);

  if (pInBar > 0 && pOutBar > 0) {
    const pr = Math.round((pOutBar / pInBar) * 1000) / 1000;
    const dp = Math.round((pOutBar - pInBar) * 100) / 100;
    const isValid = pOutBar > pInBar;
    projectStore.setState({
      liveMetrics: { pr, delta_p_bar: dp, valid: isValid },
    });
  } else {
    projectStore.setState({
      liveMetrics: { pr: 0, delta_p_bar: 0, valid: false },
    });
  }
}

export async function fetchPresets() {
  try {
    const data = await api.get("/api/v1/meta/presets");
    projectStore.setState({ presets: data || [] });
  } catch (_) {}
}

export function applyPreset(presetId) {
  const preset = projectStore.getState().presets.find((p) => p.id === presetId);
  if (preset && preset.inputs) {
    const cleanGasComp = preset.inputs.gas_comp
      ? sanitizeActiveGasComp(preset.inputs.gas_comp, DEFAULT_DESIGN_INPUTS.gas_comp)
      : undefined;
    projectStore.setState((s) => {
      const nextInputs = {
        ...s.inputs,
        ...preset.inputs,
        ...(cleanGasComp ? { gas_comp: cleanGasComp } : {}),
      };
      return {
        inputs: nextInputs,
        modules: withoutAirCoolerModule(s.modules),
        isResultsStale: deriveStaleState(nextInputs, s),
        hasUnsavedChanges: true,
      };
    });
    recalculateGasTotal();
    recalculateLiveMetrics();
    fetchRecommendations();
    showToast(`'${preset.title}' önayarı uygulandı.`);
  }
}

let recommendationsRequestSeq = 0;
let kijRequestSeq = 0;
let designRequestSeq = 0;

export async function fetchRecommendations() {
  const requestId = ++recommendationsRequestSeq;
  const { inputs, liveMetrics } = projectStore.getState();
  try {
    const recs = await api.post("/api/v1/thermo/recommendations", {
      gas_comp: inputs.gas_comp,
      pressure_ratio: liveMetrics.pr || 1.0,
      calc_method: inputs.calc_method,
    });
    // Ignore a stale response that a newer request has already superseded.
    if (requestId !== recommendationsRequestSeq) return;
    projectStore.setState({ recommendations: recs });
  } catch (_) {}
}

export async function fetchKijMatrix() {
  const requestId = ++kijRequestSeq;
  const { inputs } = projectStore.getState();
  try {
    const matrixData = await api.post("/api/v1/thermo/kij-matrix", {
      gas_comp: inputs.gas_comp,
      custom_kij: inputs.custom_kij,
    });
    if (requestId !== kijRequestSeq) return undefined;
    projectStore.setState({ kijMatrixData: matrixData });
    return matrixData;
  } catch (err) {
    if (requestId !== kijRequestSeq) return undefined;
    showToast("k_ij matrisi alınamadı: " + err.message, "danger");
  }
}

export function setModuleResult(moduleId, moduleResponse) {
  if (!moduleId) return;
  projectStore.setState((s) => ({
    modules: { ...(s.modules || {}), [moduleId]: moduleResponse },
  }));
}

export function setStationData(stationData) {
  projectStore.setState({ stationData: stationData || null });
}

export function loadModulePayload(modules, stationData) {
  projectStore.setState({
    modules: modules || {},
    stationData: stationData || null,
  });
}

export async function runDesignCalculation() {
  const requestId = ++designRequestSeq;
  projectStore.setState({ isCalculating: true, error: null, warnings: [] });
  const { inputs } = projectStore.getState();

  try {
    const res = await api.post("/api/v1/calculations/design", inputs);
    if (requestId !== designRequestSeq) return res;
    projectStore.setState((s) => ({
      results: res.results,
      warnings: Array.isArray(res.warnings) ? res.warnings : [],
      selectedUnits: res.selected_units || [],
      charts: res.charts,
      modules: withoutAirCoolerModule(s.modules),
      lastCalculatedSignature: computeInputsSignature(inputs),
      isResultsStale: false,
      isCalculating: false,
    }));
    showToast("Tasarım hesaplaması başarıyla tamamlandı!");
    return res;
  } catch (err) {
    if (requestId !== designRequestSeq) throw err;
    projectStore.setState({ isCalculating: false, error: err.message });
    showToast("Hesaplama hatası: " + err.message, "danger");
    throw err;
  }
}
