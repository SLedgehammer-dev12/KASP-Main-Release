/**
 * KASP Project & Calculation Store
 * Central state for process design inputs, active gas mixture,
 * kij matrix overrides, calculation results, and Plotly charts.
 */

import { createStore } from "./store.js";
import { api } from "../api/client.js";
import { showToast } from "./uiStore.js";

export const DEFAULT_DESIGN_INPUTS = {
  project_name: "Yeni Kompresör Projesi",
  p_in: 20.0,
  p_in_unit: "bar(a)",
  p_out: 60.0,
  p_out_unit: "bar(a)",
  t_in: 25.0,
  t_in_unit: "°C",
  flow: 12.0,
  flow_unit: "kg/s",
  gas_comp: {
    METHANE: 88.0,
    ETHANE: 7.0,
    PROPANE: 3.0,
    NITROGEN: 1.0,
    CARBONDIOXIDE: 1.0,
  },
  eos_model: "pr",
  calc_method: "Metot 6: Schultz 3-Üslü Gerçek Gaz",
  poly_eff: 82.0,
  mech_eff: 98.0,
  therm_eff: 35.0,
  num_units: 1,
  num_stages: 2,
  intercooler_t: 35.0,
  intercooler_dp_pct: 2.0,
  custom_kij: {},
};

export const projectStore = createStore({
  inputs: { ...DEFAULT_DESIGN_INPUTS },
  results: null,
  selectedUnits: [],
  charts: null,
  isCalculating: false,
  error: null,
  recommendations: null,
  kijMatrixData: null,
  liveMetrics: { pr: 3.0, delta_p_bar: 40.0, valid: true },
  gasTotal: 100.0,
  presets: [],
  modules: {},
  stationData: null,
});

export function updateInput(field, value) {
  projectStore.setState((s) => {
    const nextInputs = { ...s.inputs, [field]: value };
    return { inputs: nextInputs };
  });
  recalculateLiveMetrics();
}

export function updateGasComponent(component, percentage) {
  projectStore.setState((s) => {
    const nextComp = { ...s.inputs.gas_comp, [component]: parseFloat(percentage) || 0 };
    return {
      inputs: { ...s.inputs, gas_comp: nextComp },
    };
  });
  recalculateGasTotal();
}

export function setCustomKijOverride(pair, value) {
  projectStore.setState((s) => {
    const nextKij = { ...s.inputs.custom_kij, [pair]: parseFloat(value) };
    return {
      inputs: { ...s.inputs, custom_kij: nextKij },
    };
  });
}

export function clearCustomKijOverrides() {
  projectStore.setState((s) => ({
    inputs: { ...s.inputs, custom_kij: {} },
  }));
}

export function recalculateGasTotal() {
  const comp = projectStore.getState().inputs.gas_comp;
  const total = Object.values(comp).reduce((a, b) => a + (parseFloat(b) || 0), 0);
  projectStore.setState({ gasTotal: Math.round(total * 100) / 100 });
}

export function recalculateLiveMetrics() {
  const { p_in, p_in_unit, p_out, p_out_unit } = projectStore.getState().inputs;
  // Convert approximately or via server
  let pInBar = parseFloat(p_in) || 0;
  let pOutBar = parseFloat(p_out) || 0;
  if (p_in_unit === "bar(g)") pInBar += 1.01325;
  if (p_out_unit === "bar(g)") pOutBar += 1.01325;
  if (p_in_unit === "kPa") pInBar /= 100;
  if (p_out_unit === "kPa") pOutBar /= 100;
  if (p_in_unit === "psi") pInBar /= 14.5038;
  if (p_out_unit === "psi") pOutBar /= 14.5038;

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
    projectStore.setState((s) => ({
      inputs: {
        ...s.inputs,
        ...preset.inputs,
      },
    }));
    recalculateGasTotal();
    recalculateLiveMetrics();
    fetchRecommendations();
    showToast(`'${preset.title}' önayarı uygulandı.`);
  }
}

export async function fetchRecommendations() {
  const { inputs, liveMetrics } = projectStore.getState();
  try {
    const recs = await api.post("/api/v1/thermo/recommendations", {
      gas_comp: inputs.gas_comp,
      pressure_ratio: liveMetrics.pr || 1.0,
      calc_method: inputs.calc_method,
    });
    projectStore.setState({ recommendations: recs });
  } catch (_) {}
}

export async function fetchKijMatrix() {
  const { inputs } = projectStore.getState();
  try {
    const matrixData = await api.post("/api/v1/thermo/kij-matrix", {
      gas_comp: inputs.gas_comp,
      custom_kij: inputs.custom_kij,
    });
    projectStore.setState({ kijMatrixData: matrixData });
    return matrixData;
  } catch (err) {
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
  projectStore.setState({ isCalculating: true, error: null });
  const { inputs } = projectStore.getState();

  try {
    const res = await api.post("/api/v1/calculations/design", inputs);
    projectStore.setState({
      results: res.results,
      selectedUnits: res.selected_units || [],
      charts: res.charts,
      isCalculating: false,
    });
    showToast("Tasarım hesaplaması başarıyla tamamlandı!");
    return res;
  } catch (err) {
    projectStore.setState({ isCalculating: false, error: err.message });
    showToast("Hesaplama hatası: " + err.message, "danger");
    throw err;
  }
}
