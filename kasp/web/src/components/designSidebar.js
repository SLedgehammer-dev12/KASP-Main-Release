/**
 * KASP Design Sidebar Component
 * Presets bar, 6 Accordion Input Steps, Live PR/dP badges, and Calculate trigger.
 * Built with selective DOM updates and automatic engineering unit conversions.
 */

import { icon } from "../../vendor/icons.js";
import { projectStore, updateInput, applyPreset, runDesignCalculation } from "../store/projectStore.js";
import { renderGasTable } from "./gasTable.js";
import { t } from "../i18n/locales.js";
import { uiStore } from "../store/uiStore.js";

function convertPressure(val, fromU, toU) {
  if (!val || val <= 0 || fromU === toU) return val;
  let barA = val;
  if (fromU === "bar(g)") barA = val + 1.01325;
  else if (fromU === "kPa") barA = val / 100.0;
  else if (fromU === "psi") barA = val / 14.5038;

  let res = barA;
  if (toU === "bar(g)") res = Math.max(0, barA - 1.01325);
  else if (toU === "kPa") res = barA * 100.0;
  else if (toU === "psi") res = barA * 14.5038;

  return Math.round(res * 100) / 100;
}

function convertTemperature(val, fromU, toU) {
  if (fromU === toU) return val;
  let c = val;
  if (fromU === "K") c = val - 273.15;
  else if (fromU === "°F") c = (val - 32.0) * (5.0 / 9.0);

  let res = c;
  if (toU === "K") res = c + 273.15;
  else if (toU === "°F") res = c * (9.0 / 5.0) + 32.0;

  return Math.round(res * 10) / 10;
}

function convertFlow(val, fromU, toU) {
  if (!val || val <= 0 || fromU === toU) return val;
  // Natural gas standard density approx 0.772 kg/Sm³
  let kgs = val;
  if (fromU === "kg/h") kgs = val / 3600.0;
  else if (fromU === "Sm³/h" || fromU === "m3/h") kgs = (val * 0.772) / 3600.0;
  else if (fromU === "MMSCFD") kgs = val * 0.320;

  let res = kgs;
  if (toU === "kg/h") res = kgs * 3600.0;
  else if (toU === "Sm³/h" || toU === "m3/h") res = (kgs * 3600.0) / 0.772;
  else if (toU === "MMSCFD") res = kgs / 0.320;

  return Math.round(res * 100) / 100;
}

export function renderDesignSidebar(container) {
  let openSteps = { 1: true, 2: true, 3: false, 4: false, 5: false, 6: false };
  let isBuilt = false;

  // UX: geçersiz girdiler için anlık görsel geri bildirim (hesaplamayı engellemez)
  function applyValidity() {
    const inp = projectStore.getState().inputs || {};
    const live = projectStore.getState().liveMetrics || {};
    const flag = (field, bad, msg) => {
      const el = container.querySelector(`[data-field="${field}"]`);
      if (!el) return;
      el.classList.toggle("is-invalid", !!bad);
      el.setAttribute("aria-invalid", bad ? "true" : "false");
      if (bad) el.title = msg; else el.removeAttribute("title");
    };
    const prBad = live.valid === false && Number(inp.p_in) > 0 && Number(inp.p_out) > 0;
    flag("p_out", prBad, "Çıkış basıncı giriş basıncından büyük olmalıdır (PR > 1).");
    flag("p_in", Number(inp.p_in) <= 0, "Giriş basıncı pozitif olmalıdır.");
    flag("flow", Number(inp.flow) <= 0, "Debi pozitif olmalıdır.");
  }

  function render(forceRebuild = false) {
    const proj = projectStore.getState();
    const ui = uiStore.getState();
    const inp = proj.inputs;
    const live = proj.liveMetrics;

    const isValid = live.valid !== false && live.pr > 1.0;
    const prText = live.pr ? `PR = ${live.pr}` : "";
    const prClass = !isValid ? "badge-danger" : live.pr > 4.0 ? "badge-warning" : "badge-info";
    const dpText = live.delta_p_bar ? `ΔP = ${live.delta_p_bar} bar` : "";
    const dpClass = !isValid || live.delta_p_bar <= 0 ? "badge-danger" : "badge-info";

    if (isBuilt && !forceRebuild) {
      // 1. Update live metric badges without tearing DOM
      const prBadge = container.querySelector("#sidebar-pr-badge");
      if (prBadge) {
        prBadge.className = `badge ${prClass}`;
        prBadge.textContent = prText;
        prBadge.style.display = live.pr ? "inline-block" : "none";
      }
      const dpBadge = container.querySelector("#sidebar-dp-badge");
      if (dpBadge) {
        dpBadge.className = `badge ${dpClass}`;
        dpBadge.textContent = dpText;
        dpBadge.style.display = live.delta_p_bar ? "inline-block" : "none";
      }
      const unitBadge = container.querySelector("#sidebar-unit-badge");
      if (unitBadge) {
        unitBadge.textContent = `${inp.num_units || 1} Ünite`;
      }
      const unitFlowBadge = container.querySelector("#sidebar-unit-flow-badge");
      if (unitFlowBadge) {
        const uFlow = (Number(inp.flow || 0) / Math.max(1, Number(inp.num_units) || 1)).toFixed(1);
        unitFlowBadge.textContent = `${uFlow} ${inp.flow_unit || 'kg/s'} / ünite`;
      }

      // 2. Step summary labels
      const gasTotalBadge = container.querySelector("#sidebar-gas-total-badge");
      if (gasTotalBadge) {
        gasTotalBadge.className = `badge ${Math.abs(proj.gasTotal - 100) < 0.01 ? 'badge-success' : 'badge-warning'}`;
        gasTotalBadge.textContent = `%${proj.gasTotal.toFixed(1)}`;
      }

      const eosLabel = container.querySelector("#sidebar-eos-summary");
      if (eosLabel) eosLabel.textContent = inp.eos_model?.toUpperCase() || "";

      const effLabel = container.querySelector("#sidebar-eff-summary");
      if (effLabel) effLabel.textContent = `%${inp.poly_eff}`;

      // 3. Calculate button state
      const calcBtn = container.querySelector("#btn-run-calculation");
      if (calcBtn) {
        calcBtn.disabled = !!proj.isCalculating;
        const span = calcBtn.querySelector("span");
        if (span) {
          span.textContent = proj.isCalculating ? t("btn_calculating", ui.lang) : t("btn_calculate", ui.lang);
        }
      }

      applyValidity();

      // 4. Update inputs without stealing focus
      container.querySelectorAll(".inp-field").forEach(el => {
        if (document.activeElement !== el) {
          const field = el.getAttribute("data-field");
          if (field && inp[field] !== undefined && String(el.value) !== String(inp[field])) {
            el.value = inp[field];
          }
        }
      });
      return;
    }

    container.innerHTML = `
      <!-- Presets Bar -->
      <div style="padding: 10px 14px; background: var(--color-bg); border-bottom: 1px solid var(--color-border); display: flex; align-items: center; gap: 6px; overflow-x: auto;">
        <span style="font-size: 11px; font-weight: 600; color: var(--color-text-secondary); white-space: nowrap;">Önayarlar:</span>
        <button class="btn btn-sm btn-preset" data-preset="natural_gas" title="Doğalgaz Boru Hattı">⚡ Doğalgaz</button>
        <button class="btn btn-sm btn-preset" data-preset="lng_boiloff" title="LNG Boil-Off Kriyojenik">❄️ LNG</button>
        <button class="btn btn-sm btn-preset" data-preset="co2_injection" title="CO2 Enjeksiyon">🌿 CO₂</button>
        <button class="btn btn-sm btn-preset" data-preset="hydrogen_blend" title="Hidrojen Karışımı">⚡ H₂</button>
      </div>

      <div style="flex: 1; overflow-y: auto;">
        <!-- Step 1: Process Conditions -->
        <div class="step-section">
          <div class="step-header" data-step="1">
            <div style="display: flex; align-items: center; gap: 8px;">
              <span class="step-badge">1</span>
              <span>${t("step_process", ui.lang)}</span>
            </div>
            <div style="display: flex; align-items: center; gap: 4px;">
              <span id="sidebar-unit-badge" class="badge badge-secondary">${inp.num_units || 1} Ünite</span>
              <span id="sidebar-pr-badge" class="badge ${prClass}" style="${live.pr ? '' : 'display:none;'}">${prText}</span>
              <span id="sidebar-dp-badge" class="badge ${dpClass}" style="${live.delta_p_bar ? '' : 'display:none;'}">${dpText}</span>
            </div>
          </div>
          ${
            openSteps[1]
              ? `
              <div class="step-content">
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
                  <div class="form-group">
                    <label class="form-label">Giriş Basıncı (P_in)</label>
                    <div class="form-control-row">
                      <input type="number" step="0.1" class="form-input has-addon inp-field" data-field="p_in" value="${inp.p_in}" />
                      <select class="form-select input-addon-select inp-field" data-field="p_in_unit">
                        <option value="bar(a)" ${inp.p_in_unit === 'bar(a)' ? 'selected' : ''}>bar(a)</option>
                        <option value="bar(g)" ${inp.p_in_unit === 'bar(g)' ? 'selected' : ''}>bar(g)</option>
                        <option value="kPa" ${inp.p_in_unit === 'kPa' ? 'selected' : ''}>kPa</option>
                        <option value="psi" ${inp.p_in_unit === 'psi' ? 'selected' : ''}>psi</option>
                      </select>
                    </div>
                  </div>

                  <div class="form-group">
                    <label class="form-label">Çıkış Basıncı (P_out)</label>
                    <div class="form-control-row">
                      <input type="number" step="0.1" class="form-input has-addon inp-field" data-field="p_out" value="${inp.p_out}" />
                      <select class="form-select input-addon-select inp-field" data-field="p_out_unit">
                        <option value="bar(a)" ${inp.p_out_unit === 'bar(a)' ? 'selected' : ''}>bar(a)</option>
                        <option value="bar(g)" ${inp.p_out_unit === 'bar(g)' ? 'selected' : ''}>bar(g)</option>
                        <option value="kPa" ${inp.p_out_unit === 'kPa' ? 'selected' : ''}>kPa</option>
                        <option value="psi" ${inp.p_out_unit === 'psi' ? 'selected' : ''}>psi</option>
                      </select>
                    </div>
                  </div>

                  <div class="form-group">
                    <label class="form-label">Giriş Sıcaklığı (T_in)</label>
                    <div class="form-control-row">
                      <input type="number" step="0.1" class="form-input has-addon inp-field" data-field="t_in" value="${inp.t_in}" />
                      <select class="form-select input-addon-select inp-field" data-field="t_in_unit">
                        <option value="°C" ${inp.t_in_unit === '°C' ? 'selected' : ''}>°C</option>
                        <option value="K" ${inp.t_in_unit === 'K' ? 'selected' : ''}>K</option>
                        <option value="°F" ${inp.t_in_unit === '°F' ? 'selected' : ''}>°F</option>
                      </select>
                    </div>
                  </div>

                  <div class="form-group">
                    <label class="form-label">Akış Debisi (m_dot / Q)</label>
                    <div class="form-control-row">
                      <input type="number" step="0.1" class="form-input has-addon inp-field" data-field="flow" value="${inp.flow}" />
                      <select class="form-select input-addon-select inp-field" data-field="flow_unit">
                        <option value="kg/s" ${inp.flow_unit === 'kg/s' ? 'selected' : ''}>kg/s</option>
                        <option value="Sm³/h" ${inp.flow_unit === 'Sm³/h' ? 'selected' : ''}>Sm³/h</option>
                        <option value="kg/h" ${inp.flow_unit === 'kg/h' ? 'selected' : ''}>kg/h</option>
                        <option value="MMSCFD" ${inp.flow_unit === 'MMSCFD' ? 'selected' : ''}>MMSCFD</option>
                      </select>
                    </div>
                  </div>

                  <div class="form-group" style="grid-column: span 2;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                      <label class="form-label" style="margin-bottom: 0;">Ünite Sayısı (N+1 Paralel Tren)</label>
                      <span class="badge badge-info" id="sidebar-unit-flow-badge" style="font-size: 10px;">
                        ${(Number(inp.flow || 0) / Math.max(1, Number(inp.num_units) || 1)).toFixed(1)} ${inp.flow_unit || 'kg/s'} / ünite
                      </span>
                    </div>
                    <div class="form-control-row">
                      <select class="form-select inp-field" data-field="num_units" style="font-weight: 600;">
                        <option value="1" ${Number(inp.num_units || 1) === 1 ? 'selected' : ''}>1 Ünite (1 Çalışan + 0 Yedek - Tekil Ünite)</option>
                        <option value="2" ${Number(inp.num_units) === 2 ? 'selected' : ''}>2 Ünite (1 Çalışan + 1 Yedek)</option>
                        <option value="3" ${Number(inp.num_units) === 3 ? 'selected' : ''}>3 Ünite (2 Çalışan + 1 Yedek)</option>
                        <option value="4" ${Number(inp.num_units) === 4 ? 'selected' : ''}>4 Ünite (3 Çalışan + 1 Yedek)</option>
                        <option value="5" ${Number(inp.num_units) === 5 ? 'selected' : ''}>5 Ünite (4 Çalışan + 1 Yedek - BOTAŞ Tipik)</option>
                        <option value="6" ${Number(inp.num_units) === 6 ? 'selected' : ''}>6 Ünite (5 Çalışan + 1 Yedek)</option>
                        <option value="8" ${Number(inp.num_units) === 8 ? 'selected' : ''}>8 Ünite (7 Çalışan + 1 Yedek - Yüksek Kapasite)</option>
                      </select>
                    </div>
                  </div>
                </div>
              </div>
            `
              : ""
          }
        </div>

        <!-- Step 2: Gas Composition Table -->
        <div class="step-section">
          <div class="step-header" data-step="2">
            <div style="display: flex; align-items: center; gap: 8px;">
              <span class="step-badge">2</span>
              <span>${t("step_gas", ui.lang)}</span>
            </div>
            <span id="sidebar-gas-total-badge" class="badge ${Math.abs(proj.gasTotal - 100) < 0.01 ? 'badge-success' : 'badge-warning'}">%${proj.gasTotal.toFixed(1)}</span>
          </div>
          ${
            openSteps[2]
              ? `<div class="step-content" id="sidebar-gas-table-mount"></div>`
              : ""
          }
        </div>

        <!-- Step 3: Thermodynamic Model -->
        <div class="step-section">
          <div class="step-header" data-step="3">
            <div style="display: flex; align-items: center; gap: 8px;">
              <span class="step-badge">3</span>
              <span>${t("step_model", ui.lang)}</span>
            </div>
            <span id="sidebar-eos-summary" style="font-size: 11px; color: var(--color-primary); font-weight: 600;">${inp.eos_model?.toUpperCase()}</span>
          </div>
          ${
            openSteps[3]
              ? `
              <div class="step-content">
                <div class="form-group">
                  <label class="form-label">Hal Denklemi (EOS)</label>
                  <select class="form-select inp-field" data-field="eos_model">
                    <option value="coolprop" ${inp.eos_model === 'coolprop' ? 'selected' : ''}>CoolProp (HEOS Referans Model)</option>
                    <option value="pr" ${inp.eos_model === 'pr' ? 'selected' : ''}>Peng-Robinson (Kübik EoS)</option>
                    <option value="srk" ${inp.eos_model === 'srk' ? 'selected' : ''}>Soave-Redlich-Kwong (SRK)</option>
                    <option value="rk" ${inp.eos_model === 'rk' ? 'selected' : ''}>Redlich-Kwong</option>
                    <option value="bwrs" ${inp.eos_model === 'bwrs' ? 'selected' : ''}>BWRS Modeli</option>
                    <option value="gerg2008" ${inp.eos_model === 'gerg2008' ? 'selected' : ''}>GERG-2008 Modeli</option>
                  </select>
                </div>

                <div class="form-group">
                  <label class="form-label">Sıkıştırma Yolu Yöntemi</label>
                  <select class="form-select inp-field" data-field="calc_method">
                    <option value="Metot 6: Schultz 3-Üslü Gerçek Gaz" ${inp.calc_method?.includes('Metot 6') ? 'selected' : ''}>Metot 6: Schultz 3-Üslü (API 617 / ASME PTC 10)</option>
                    <option value="Metot 5: Huntington-RK45 Diferansiyel" ${inp.calc_method?.includes('Metot 5') ? 'selected' : ''}>Metot 5: Huntington-RK45 Diferansiyel Entegrasyon</option>
                    <option value="Metot 4: Doğrudan H-S" ${inp.calc_method?.includes('Metot 4') ? 'selected' : ''}>Metot 4: Doğrudan H-S (Entalpi-Entropi)</option>
                    <option value="Metot 1: Ortalama Özellikler" ${inp.calc_method?.includes('Metot 1') ? 'selected' : ''}>Metot 1: Ortalama Özellikler</option>
                    <option value="Metot 2: Endpoint Yaklaşımı" ${inp.calc_method?.includes('Metot 2') ? 'selected' : ''}>Metot 2: Endpoint Yaklaşımı</option>
                    <option value="Metot 3: Artımlı Basınç" ${inp.calc_method?.includes('Metot 3') ? 'selected' : ''}>Metot 3: Artımlı Basınç</option>
                  </select>
                </div>
              </div>
            `
              : ""
          }
        </div>

        <!-- Step 4: Stages & Intercooling -->
        <div class="step-section">
          <div class="step-header" data-step="4">
            <div style="display: flex; align-items: center; gap: 8px;">
              <span class="step-badge">4</span>
              <span>${t("step_stages", ui.lang)}</span>
            </div>
            <span style="font-size: 11px; color: var(--color-text-secondary);">${inp.num_stages} Kademe</span>
          </div>
          ${
            openSteps[4]
              ? `
              <div class="step-content">
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
                  <div class="form-group">
                    <label class="form-label">Kademe Sayısı</label>
                    <input type="number" min="1" max="6" class="form-input inp-field" data-field="num_stages" value="${inp.num_stages}" />
                  </div>
                  <div class="form-group">
                    <label class="form-label">Ünite Sayısı (N+1)</label>
                    <input type="number" min="1" max="10" class="form-input inp-field" data-field="num_units" value="${inp.num_units}" />
                  </div>
                  <div class="form-group">
                    <label class="form-label">Ara Soğutucu (°C)</label>
                    <input type="number" step="0.5" class="form-input inp-field" data-field="intercooler_t" value="${inp.intercooler_t}" />
                  </div>
                  <div class="form-group">
                    <label class="form-label">Ara Soğutucu ΔP (%)</label>
                    <input type="number" step="0.1" class="form-input inp-field" data-field="intercooler_dp_pct" value="${inp.intercooler_dp_pct}" />
                  </div>
                </div>
              </div>
            `
              : ""
          }
        </div>

        <!-- Step 5: Target Efficiencies -->
        <div class="step-section">
          <div class="step-header" data-step="5">
            <div style="display: flex; align-items: center; gap: 8px;">
              <span class="step-badge">5</span>
              <span>${t("step_efficiencies", ui.lang)}</span>
            </div>
            <span id="sidebar-eff-summary" style="font-size: 11px; color: var(--color-text-secondary);">%${inp.poly_eff}</span>
          </div>
          ${
            openSteps[5]
              ? `
              <div class="step-content">
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
                  <div class="form-group">
                    <label class="form-label">Hedef Politropik Verim (%)</label>
                    <input type="number" step="0.5" min="40" max="98" class="form-input inp-field" data-field="poly_eff" value="${inp.poly_eff}" />
                  </div>
                  <div class="form-group">
                    <label class="form-label">Mekanik Verim (%)</label>
                    <input type="number" step="0.1" min="80" max="100" class="form-input inp-field" data-field="mech_eff" value="${inp.mech_eff}" />
                  </div>
                </div>
              </div>
            `
              : ""
          }
        </div>
      </div>

      <!-- Calculate Primary Button -->
      <div style="padding: 12px 16px; background: var(--color-surface); border-top: 1px solid var(--color-border);">
        <button id="btn-run-calculation" class="btn btn-primary" style="width: 100%; height: 36px; font-size: 13px;" ${proj.isCalculating ? "disabled" : ""}>
          ${icon("zap", 16)}
          <span>${proj.isCalculating ? t("btn_calculating", ui.lang) : t("btn_calculate", ui.lang)}</span>
        </button>
      </div>
    `;

    isBuilt = true;
    applyValidity();

    // Bind accordion toggles
    container.querySelectorAll(".step-header").forEach(hdr => {
      hdr.addEventListener("click", () => {
        const stepNum = hdr.getAttribute("data-step");
        openSteps[stepNum] = !openSteps[stepNum];
        render(true);
      });
    });

    // Mount gas table into Step 2 if open
    if (openSteps[2]) {
      const gasMount = container.querySelector("#sidebar-gas-table-mount");
      if (gasMount) {
        renderGasTable(gasMount);
      }
    }

    // Bind inputs with intelligent unit conversion
    container.querySelectorAll(".inp-field").forEach(inpElem => {
      inpElem.addEventListener("change", (e) => {
        const f = e.target.getAttribute("data-field");
        let v = e.target.value;
        const currentInputs = projectStore.getState().inputs;

        if (f === "flow_unit") {
          const oldUnit = currentInputs.flow_unit || "kg/s";
          const newUnit = v;
          const oldFlow = parseFloat(currentInputs.flow) || 12.0;
          const nextFlow = convertFlow(oldFlow, oldUnit, newUnit);
          const flowEl = container.querySelector('[data-field="flow"]');
          if (flowEl) flowEl.value = nextFlow;
          projectStore.setState(s => ({
            inputs: { ...s.inputs, flow: nextFlow, flow_unit: newUnit }
          }));
          return;
        }

        if (f === "p_in_unit") {
          const oldUnit = currentInputs.p_in_unit || "bar(a)";
          const newUnit = v;
          const oldP = parseFloat(currentInputs.p_in) || 20.0;
          const nextP = convertPressure(oldP, oldUnit, newUnit);
          const pEl = container.querySelector('[data-field="p_in"]');
          if (pEl) pEl.value = nextP;
          projectStore.setState(s => ({
            inputs: { ...s.inputs, p_in: nextP, p_in_unit: newUnit }
          }));
          return;
        }

        if (f === "p_out_unit") {
          const oldUnit = currentInputs.p_out_unit || "bar(a)";
          const newUnit = v;
          const oldP = parseFloat(currentInputs.p_out) || 60.0;
          const nextP = convertPressure(oldP, oldUnit, newUnit);
          const pEl = container.querySelector('[data-field="p_out"]');
          if (pEl) pEl.value = nextP;
          projectStore.setState(s => ({
            inputs: { ...s.inputs, p_out: nextP, p_out_unit: newUnit }
          }));
          return;
        }

        if (f === "t_in_unit") {
          const oldUnit = currentInputs.t_in_unit || "°C";
          const newUnit = v;
          const oldT = parseFloat(currentInputs.t_in) || 25.0;
          const nextT = convertTemperature(oldT, oldUnit, newUnit);
          const tEl = container.querySelector('[data-field="t_in"]');
          if (tEl) tEl.value = nextT;
          projectStore.setState(s => ({
            inputs: { ...s.inputs, t_in: nextT, t_in_unit: newUnit }
          }));
          return;
        }

        if (["p_in", "p_out", "t_in", "flow", "poly_eff", "num_stages", "num_units", "intercooler_t", "intercooler_dp_pct", "mech_eff"].includes(f)) {
          v = parseFloat(v) || 0;
          if (f === "num_units") v = Math.max(1, Math.round(v));
        }
        updateInput(f, v);
      });
    });

    // Preset buttons
    container.querySelectorAll(".btn-preset").forEach(btn => {
      btn.addEventListener("click", () => {
        const pid = btn.getAttribute("data-preset");
        applyPreset(pid);
        render(true);
      });
    });

    // Calculate action
    container.querySelector("#btn-run-calculation")?.addEventListener("click", () => {
      runDesignCalculation();
    });
  }

  projectStore.subscribe(() => render(false));
  render(true);
}
