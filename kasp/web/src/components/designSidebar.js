/**
 * KASP Design Sidebar Component
 * Presets bar, 6 Accordion Input Steps, Live PR/dP badges, and Calculate trigger.
 * Built with selective DOM updates and automatic engineering unit conversions.
 */

import { icon } from "../../vendor/icons.js";
import {
  projectStore,
  updateInput,
  applyPreset,
  balanceGasComponent,
  resetDesignInputs,
  runDesignCalculation,
  convertFlowWithMW,
  convertPressureUnit,
  convertTemperatureUnit,
  computeGasMixtureMW,
  recalculateLiveMetrics,
  scheduleRecommendationsRefresh,
  fetchRecommendations,
  invalidateAirCoolerCache,
  escapeHtml,
} from "../store/projectStore.js";
import { renderGasTable } from "./gasTable.js";
import { t } from "../i18n/locales.js";
import { uiStore, showToast } from "../store/uiStore.js";

const METHOD_CANONICAL_OPTIONS = [
  { key: "Metot 6", value: "Metot 6: Schultz 3-Üslü Gerçek Gaz", label: "Metot 6: Schultz 3-Üslü (API 617 / ASME PTC 10)" },
  { key: "Metot 5", value: "Metot 5: Huntington-RK45 Diferansiyel", label: "Metot 5: Huntington-RK45 Diferansiyel Entegrasyon" },
  { key: "Metot 4", value: "Metot 4: Doğrudan H-S", label: "Metot 4: Doğrudan H-S (Entalpi-Entropi)" },
  { key: "Metot 1", value: "Metot 1: Ortalama Özellikler", label: "Metot 1: Ortalama Özellikler" },
  { key: "Metot 2", value: "Metot 2: Endpoint Yaklaşımı", label: "Metot 2: Endpoint Yaklaşımı" },
  { key: "Metot 3", value: "Metot 3: Artımlı Basınç", label: "Metot 3: Artımlı Basınç" },
];

function resolveRecommendedMethodValue(recMethod) {
  const raw = String(recMethod || "");
  for (const item of METHOD_CANONICAL_OPTIONS) {
    if (raw.includes(item.key)) return item.value;
  }
  return "Metot 6: Schultz 3-Üslü Gerçek Gaz";
}

function computeValidationError(proj, lang) {
  const inp = proj?.inputs || {};
  if (!proj?.liveMetrics?.valid) {
    return {
      type: "pressure",
      message: t("validation_pout_gt_pin", lang),
      canBalanceGas: false,
    };
  }
  if (!(Number(inp.flow) > 0)) {
    return {
      type: "flow",
      message: t("validation_flow_gt_zero", lang),
      canBalanceGas: false,
    };
  }
  const gasTotal = Number(proj?.gasTotal ?? 100);
  if (Math.abs(gasTotal - 100) > 0.5) {
    return {
      type: "gas",
      message: t("validation_gas_sum", lang).replace("{pct}", gasTotal.toFixed(2)),
      canBalanceGas: true,
    };
  }
  return null;
}

function buildModelRecHtml(rec, inp) {
  if (!rec || (!rec.recommended_eos && !rec.recommended_method)) {
    return `
      <div style="font-size: 11px; color: var(--color-text-secondary); padding: 8px 10px; border-radius: var(--radius-sm); background: var(--color-bg); border: 1px dashed var(--color-border);">
        Canlı EOS &amp; sıkıştırma metodu önerisi yükleniyor...
      </div>
    `;
  }
  const recEos = String(rec.recommended_eos || "coolprop").toLowerCase();
  const recMethodVal = resolveRecommendedMethodValue(rec.recommended_method);
  const currentEos = String(inp.eos_model || "pr").toLowerCase();
  const recMethodPrefix = recMethodVal.split(":")[0];
  const isMethodMatch = String(inp.calc_method || "").includes(recMethodPrefix);
  const isAllMatch = currentEos === recEos && isMethodMatch;

  const eosReason = rec.eos_reason || "";
  const methodReason = rec.method_reason || "";
  const summaryTitle = rec.reason || "Akıllı Termodinamik Öneri";

  return `
    <div style="padding: 9px 10px; border-radius: var(--radius-sm); background: ${isAllMatch ? "rgba(16, 185, 129, 0.08)" : "rgba(2, 132, 199, 0.08)"}; border: 1px solid ${isAllMatch ? "rgba(16, 185, 129, 0.30)" : "rgba(2, 132, 199, 0.30)"}; font-size: 11px;">
      <div style="display: flex; justify-content: space-between; align-items: center; gap: 6px; margin-bottom: 4px;">
        <strong style="color: ${isAllMatch ? "#10b981" : "var(--color-primary)"};">
          ⚡ ${escapeHtml(recEos.toUpperCase())} • ${escapeHtml(rec.recommended_method || recMethodPrefix)}
        </strong>
        ${
          isAllMatch
            ? `<span class="badge badge-success" style="font-size: 9px;">Aktif Model Uyumlu ✓</span>`
            : `<button type="button" id="btn-apply-model-rec" class="btn btn-sm btn-primary" style="padding: 2px 8px; font-size: 10px;">Öneriyi Uygula</button>`
        }
      </div>
      <div style="font-weight: 600; color: var(--color-text); font-size: 10px; margin-bottom: 2px;">${escapeHtml(summaryTitle)}</div>
      ${eosReason ? `<div style="color: var(--color-text-secondary); font-size: 10px; line-height: 1.35;">• <b>EOS:</b> ${escapeHtml(eosReason)}</div>` : ""}
      ${methodReason ? `<div style="color: var(--color-text-secondary); font-size: 10px; line-height: 1.35;">• <b>Metot:</b> ${escapeHtml(methodReason)}</div>` : ""}
    </div>
  `;
}

function formatEquivalentHeatRate(thermEffPct) {
  const eff = Number(thermEffPct);
  if (!Number.isFinite(eff) || eff <= 0) return "";
  const hr = Math.round(360000.0 / eff);
  return `Eşdeğer Isı Tüketimi: ${hr.toLocaleString("tr-TR")} kJ/kWh`;
}

export function renderDesignSidebar(container) {
  let openSteps = { 1: true, 2: true, 3: true, 4: false, 5: false, 6: false };
  let isBuilt = false;

  function bindModelRecApply() {
    const applyBtn = container.querySelector("#btn-apply-model-rec");
    if (!applyBtn) return;
    applyBtn.addEventListener("click", () => {
      const rec = projectStore.getState().recommendations;
      if (!rec) return;
      const recEos = String(rec.recommended_eos || "coolprop").toLowerCase();
      const recMethodVal = resolveRecommendedMethodValue(rec.recommended_method);
      updateInput("eos_model", recEos);
      updateInput("calc_method", recMethodVal);
      showToast(`Önerilen model uygulandı: ${recEos.toUpperCase()} / ${recMethodVal.split(":")[0]}`);
      render(false);
    });
  }

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

      const mwBadge = container.querySelector("#sidebar-mw-badge");
      if (mwBadge) {
        mwBadge.textContent = `MW ${computeGasMixtureMW(inp.gas_comp).toFixed(2)} g/mol`;
      }

      const eosLabel = container.querySelector("#sidebar-eos-summary");
      if (eosLabel) eosLabel.textContent = inp.eos_model?.toUpperCase() || "";

      const recBox = container.querySelector("#sidebar-model-rec-box");
      if (recBox) {
        recBox.innerHTML = buildModelRecHtml(proj.recommendations, inp);
        bindModelRecApply();
      }

      const stagesLabel = container.querySelector("#sidebar-stages-summary");
      if (stagesLabel) stagesLabel.textContent = `${inp.num_stages} Kademe`;

      const effLabel = container.querySelector("#sidebar-eff-summary");
      if (effLabel) {
        effLabel.textContent = `ηp %${inp.poly_eff} • ηth %${inp.therm_eff ?? 35}`;
      }

      const hrHint = container.querySelector("#sidebar-therm-hr-hint");
      if (hrHint) {
        hrHint.textContent = formatEquivalentHeatRate(inp.therm_eff ?? 35);
      }

      const siteLabel = container.querySelector("#sidebar-site-summary");
      if (siteLabel) {
        siteLabel.textContent = `${inp.ambient_temp ?? 19}°C • ${inp.altitude ?? 0} m`;
      }

      // 3. Calculate button, validation alert & stale state
      const valErr = computeValidationError(proj, ui.lang);
      const calcBtn = container.querySelector("#btn-run-calculation");
      if (calcBtn) {
        calcBtn.disabled = !!proj.isCalculating || !!valErr;
        calcBtn.classList.toggle("is-stale", !!proj.isResultsStale);
        const span = calcBtn.querySelector(".calc-btn-label");
        if (span) {
          span.textContent = proj.isCalculating ? t("btn_calculating", ui.lang) : t("btn_calculate", ui.lang);
        }
      }
      const valBox = container.querySelector("#sidebar-validation-alert");
      const valMsg = container.querySelector("#sidebar-validation-msg");
      const balBtn = container.querySelector("#btn-footer-balance-gas");
      if (valBox) {
        valBox.style.display = valErr ? "flex" : "none";
      }
      if (valMsg) {
        valMsg.textContent = valErr ? valErr.message : "";
      }
      if (balBtn) {
        balBtn.style.display = valErr?.canBalanceGas ? "inline-flex" : "none";
      }
      const stalePill = container.querySelector("#sidebar-stale-pill");
      if (stalePill) {
        stalePill.style.display = proj.isResultsStale ? "flex" : "none";
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

    const allStepsOpen = [1, 2, 3, 4, 5, 6].every((n) => !!openSteps[n]);
    const valErr = computeValidationError(proj, ui.lang);

    container.innerHTML = `
      <!-- Presets & Accordion Quick-Control Bar -->
      <div style="padding: 8px 12px; background: var(--color-bg); border-bottom: 1px solid var(--color-border); display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 6px;">
        <div style="display: flex; flex-wrap: wrap; align-items: center; gap: 4px; min-width: 0;">
          <span style="font-size: 11px; font-weight: 600; color: var(--color-text-secondary); white-space: nowrap;">Önayarlar:</span>
          <button class="btn btn-sm btn-preset" data-preset="natural_gas" title="Doğalgaz Boru Hattı">⚡ Doğalgaz</button>
          <button class="btn btn-sm btn-preset" data-preset="lng_boiloff" title="LNG Boil-Off Kriyojenik">❄️ LNG</button>
          <button class="btn btn-sm btn-preset" data-preset="co2_injection" title="CO2 Enjeksiyon">🌿 CO₂</button>
          <button class="btn btn-sm btn-preset" data-preset="hydrogen_blend" title="Hidrojen Karışımı">⚡ H₂</button>
        </div>
        <div style="display: flex; align-items: center; gap: 4px; flex-shrink: 0;">
          <button
            type="button"
            id="btn-reset-inputs"
            class="btn btn-sm"
            title="${escapeHtml(t("btn_reset_defaults", ui.lang))}"
            style="white-space: nowrap; font-size: 10px; padding: 2px 7px;"
          >${escapeHtml(t("btn_reset_defaults", ui.lang))}</button>
          <button
            type="button"
            id="btn-toggle-all-steps"
            class="btn btn-sm"
            aria-pressed="${allStepsOpen ? "true" : "false"}"
            title="${escapeHtml(allStepsOpen ? t("steps_collapse_all", ui.lang) : t("steps_expand_all", ui.lang))}"
            style="white-space: nowrap; font-size: 10px; padding: 2px 7px;"
          >${escapeHtml(allStepsOpen ? t("steps_collapse_all", ui.lang) : t("steps_expand_all", ui.lang))}</button>
        </div>
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
                        <option value="Nm³/h" ${inp.flow_unit === 'Nm³/h' ? 'selected' : ''}>Nm³/h</option>
                        <option value="kg/h" ${inp.flow_unit === 'kg/h' ? 'selected' : ''}>kg/h</option>
                        <option value="MMSCFD" ${inp.flow_unit === 'MMSCFD' ? 'selected' : ''}>MMSCFD</option>
                        <option value="MMSCMD" ${inp.flow_unit === 'MMSCMD' ? 'selected' : ''}>MMSCMD</option>
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
            <div style="display: flex; align-items: center; gap: 4px;">
              <span id="sidebar-mw-badge" class="badge badge-info" style="font-size: 10px;">MW ${computeGasMixtureMW(inp.gas_comp).toFixed(2)} g/mol</span>
              <span id="sidebar-gas-total-badge" class="badge ${Math.abs(proj.gasTotal - 100) < 0.01 ? 'badge-success' : 'badge-warning'}">%${proj.gasTotal.toFixed(1)}</span>
            </div>
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
            <span id="sidebar-eos-summary" style="font-size: 11px; color: var(--color-primary); font-weight: 600;">${escapeHtml(inp.eos_model?.toUpperCase() || "")}</span>
          </div>
          ${
            openSteps[3]
              ? `
              <div class="step-content">
                <div id="sidebar-model-rec-box" aria-live="polite" style="margin-bottom: 10px;">
                  ${buildModelRecHtml(proj.recommendations, inp)}
                </div>

                <div class="form-group">
                  <label class="form-label">Hal Denklemi (EOS)</label>
                  <select class="form-select inp-field" data-field="eos_model">
                    <option value="coolprop" ${inp.eos_model === 'coolprop' ? 'selected' : ''}>CoolProp (HEOS Referans Model)</option>
                    <option value="pr" ${(inp.eos_model === 'pr' || inp.eos_model === 'vdw') ? 'selected' : ''}>Peng-Robinson (Kübik EoS)</option>
                    <option value="srk" ${(inp.eos_model === 'srk' || inp.eos_model === 'rk') ? 'selected' : ''}>Soave-Redlich-Kwong (SRK)</option>
                    <option value="gerg2008" ${(inp.eos_model === 'gerg2008' || inp.eos_model === 'bwrs') ? 'selected' : ''}>GERG-2008 Doğalgaz Modeli</option>
                    <option value="aga8" ${inp.eos_model === 'aga8' ? 'selected' : ''}>AGA8-DC92 Doğalgaz Modeli</option>
                    <option value="thermopack" ${inp.eos_model === 'thermopack' ? 'selected' : ''}>SINTEF ThermoPack (VLE / Asit Gazı)</option>
                    <option value="neqsim" ${inp.eos_model === 'neqsim' ? 'selected' : ''}>Equinor NeqSim (SRK-CPA Polar)</option>
                    <option value="ccp" ${inp.eos_model === 'ccp' ? 'selected' : ''}>Petrobras CCP (Santrifüj Paketi)</option>
                    <option value="dwsim" ${inp.eos_model === 'dwsim' ? 'selected' : ''}>DWSIM Termodinamik Motoru</option>
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
            <span id="sidebar-stages-summary" style="font-size: 11px; color: var(--color-text-secondary);">${inp.num_stages} Kademe</span>
          </div>
          ${
            openSteps[4]
              ? `
              <div class="step-content">
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
                  <div class="form-group">
                    <label class="form-label" for="inp-num-stages">Kademe Sayısı</label>
                    <input id="inp-num-stages" type="number" min="1" max="6" class="form-input inp-field" data-field="num_stages" value="${inp.num_stages}" />
                  </div>
                  <div class="form-group">
                    <label class="form-label" for="inp-step4-num-units">Ünite Sayısı (N+1)</label>
                    <input id="inp-step4-num-units" type="number" min="1" max="10" class="form-input inp-field" data-field="num_units" value="${inp.num_units}" />
                  </div>
                  <div class="form-group">
                    <label class="form-label" for="inp-intercooler-t">Ara Soğutucu (°C)</label>
                    <input id="inp-intercooler-t" type="number" step="0.5" class="form-input inp-field" data-field="intercooler_t" value="${inp.intercooler_t}" />
                  </div>
                  <div class="form-group">
                    <label class="form-label" for="inp-intercooler-dp">Ara Soğutucu ΔP (%)</label>
                    <input id="inp-intercooler-dp" type="number" step="0.1" class="form-input inp-field" data-field="intercooler_dp_pct" value="${inp.intercooler_dp_pct}" />
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
            <span id="sidebar-eff-summary" style="font-size: 11px; color: var(--color-text-secondary);">ηp %${inp.poly_eff} • ηth %${inp.therm_eff ?? 35}</span>
          </div>
          ${
            openSteps[5]
              ? `
              <div class="step-content">
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
                  <div class="form-group">
                    <label class="form-label" for="inp-poly-eff">Hedef Politropik Verim (%)</label>
                    <input id="inp-poly-eff" type="number" inputmode="decimal" step="0.5" min="40" max="98" class="form-input inp-field" data-field="poly_eff" value="${inp.poly_eff}" />
                  </div>
                  <div class="form-group">
                    <label class="form-label" for="inp-mech-eff">Mekanik Verim (%)</label>
                    <input id="inp-mech-eff" type="number" inputmode="decimal" step="0.1" min="80" max="100" class="form-input inp-field" data-field="mech_eff" value="${inp.mech_eff}" />
                  </div>
                  <div class="form-group" style="grid-column: span 2;">
                    <label class="form-label" for="inp-therm-eff">${escapeHtml(t("label_therm_eff", ui.lang))}</label>
                    <input
                      id="inp-therm-eff"
                      type="number"
                      inputmode="decimal"
                      step="0.5"
                      min="15"
                      max="65"
                      class="form-input inp-field"
                      data-field="therm_eff"
                      aria-describedby="sidebar-therm-hr-hint"
                      value="${inp.therm_eff ?? 35}"
                    />
                    <div id="sidebar-therm-hr-hint" style="font-size: 10px; color: var(--color-text-secondary); margin-top: 4px;">
                      ${escapeHtml(formatEquivalentHeatRate(inp.therm_eff ?? 35))}
                    </div>
                  </div>
                </div>
              </div>
            `
              : ""
          }
        </div>

        <!-- Step 6: Site & Ambient Conditions (ISO 2314 Derating) -->
        <div class="step-section">
          <div class="step-header" data-step="6">
            <div style="display: flex; align-items: center; gap: 8px;">
              <span class="step-badge">6</span>
              <span>${t("step_site", ui.lang)}</span>
            </div>
            <span id="sidebar-site-summary" style="font-size: 11px; color: var(--color-text-secondary);">${inp.ambient_temp ?? 19}°C • ${inp.altitude ?? 0} m</span>
          </div>
          ${
            openSteps[6]
              ? `
              <div class="step-content">
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
                  <div class="form-group">
                    <label class="form-label" for="inp-ambient-temp">${escapeHtml(t("label_ambient_temp", ui.lang))}</label>
                    <input
                      id="inp-ambient-temp"
                      type="number"
                      inputmode="decimal"
                      step="1"
                      min="-40"
                      max="55"
                      class="form-input inp-field"
                      data-field="ambient_temp"
                      value="${inp.ambient_temp ?? 19}"
                    />
                  </div>
                  <div class="form-group">
                    <label class="form-label" for="inp-altitude">${escapeHtml(t("label_altitude", ui.lang))}</label>
                    <input
                      id="inp-altitude"
                      type="number"
                      inputmode="numeric"
                      step="50"
                      min="0"
                      max="4000"
                      class="form-input inp-field"
                      data-field="altitude"
                      value="${inp.altitude ?? 0}"
                    />
                  </div>
                  <div class="form-group" style="grid-column: span 2;">
                    <label class="form-label" for="inp-humidity">${escapeHtml(t("label_humidity", ui.lang))}</label>
                    <input
                      id="inp-humidity"
                      type="number"
                      inputmode="numeric"
                      step="5"
                      min="0"
                      max="100"
                      class="form-input inp-field"
                      data-field="humidity"
                      value="${inp.humidity ?? 60}"
                    />
                  </div>
                </div>
              </div>
            `
              : ""
          }
        </div>
      </div>

      <!-- Sticky Calculate Primary Action Bar -->
      <div style="position: sticky; bottom: 0; z-index: 5; padding: 10px 14px; background: var(--color-surface); border-top: 1px solid var(--color-border); box-shadow: 0 -4px 12px rgba(0,0,0,0.06);">
        <div id="sidebar-validation-alert" role="alert" style="display: ${valErr ? "flex" : "none"}; align-items: center; justify-content: space-between; gap: 6px; margin-bottom: 6px; padding: 5px 8px; border-radius: var(--radius-sm); background: rgba(239, 68, 68, 0.12); border: 1px solid rgba(239, 68, 68, 0.35); color: #dc2626; font-size: 10.5px; font-weight: 600;">
          <span id="sidebar-validation-msg">${valErr ? escapeHtml(valErr.message) : ""}</span>
          <button type="button" id="btn-footer-balance-gas" class="btn btn-sm" style="display: ${valErr?.canBalanceGas ? "inline-flex" : "none"}; padding: 2px 6px; font-size: 10px; flex-shrink: 0;">${escapeHtml(t("btn_balance_100", ui.lang))}</button>
        </div>
        <div id="sidebar-stale-pill" style="display: ${proj.isResultsStale ? "flex" : "none"}; align-items: center; justify-content: space-between; gap: 6px; margin-bottom: 6px; padding: 4px 8px; border-radius: var(--radius-sm); background: rgba(245, 158, 11, 0.12); border: 1px solid rgba(245, 158, 11, 0.35); color: #d97706; font-size: 10.5px; font-weight: 600;">
          <span>⚠️ Girdiler değişti — yeniden hesaplayın</span>
        </div>
        <button id="btn-run-calculation" class="btn btn-primary ${proj.isResultsStale ? "is-stale" : ""}" style="width: 100%; height: 36px; font-size: 13px; display: flex; align-items: center; justify-content: center; gap: 8px;" ${proj.isCalculating || valErr ? "disabled" : ""}>
          ${icon("zap", 16)}
          <span class="calc-btn-label">${proj.isCalculating ? t("btn_calculating", ui.lang) : t("btn_calculate", ui.lang)}</span>
          <kbd style="font-size: 9.5px; padding: 1px 5px; border-radius: 4px; background: rgba(255,255,255,0.18); border: 1px solid rgba(255,255,255,0.28); font-family: var(--font-mono);">⌘/Ctrl+Enter</kbd>
        </button>
      </div>
    `;

    isBuilt = true;
    applyValidity();

    const resetBtn = container.querySelector("#btn-reset-inputs");
    if (resetBtn) {
      resetBtn.addEventListener("click", () => {
        resetDesignInputs();
        showToast("Tasarım girdileri varsayılan değerlere sıfırlandı.");
      });
    }

    const footerBalanceBtn = container.querySelector("#btn-footer-balance-gas");
    if (footerBalanceBtn) {
      footerBalanceBtn.addEventListener("click", () => {
        const comp = projectStore.getState().inputs?.gas_comp || {};
        const target = Object.keys(comp).find((k) => k === "CH4" || k === "METHANE") || Object.keys(comp)[0];
        if (target) {
          balanceGasComponent(target);
        }
      });
    }

    // Expand / Collapse All Accordion Steps
    const toggleAllBtn = container.querySelector("#btn-toggle-all-steps");
    if (toggleAllBtn) {
      toggleAllBtn.addEventListener("click", () => {
        const nextOpen = ![1, 2, 3, 4, 5, 6].every((n) => !!openSteps[n]);
        for (let s = 1; s <= 6; s++) openSteps[s] = nextOpen;
        render(true);
      });
    }

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

    // Bind live model recommendation apply button if Step 3 is open
    if (openSteps[3]) {
      bindModelRecApply();
    }

    // Bind inputs with intelligent unit conversion (real MW & EOS-aware)
    container.querySelectorAll(".inp-field").forEach(inpElem => {
      inpElem.addEventListener("change", (e) => {
        const f = e.target.getAttribute("data-field");
        let v = e.target.value;
        const currentInputs = projectStore.getState().inputs;

        if (f === "flow_unit") {
          const oldUnit = currentInputs.flow_unit || "kg/s";
          const newUnit = v;
          const oldFlow = parseFloat(currentInputs.flow) || 12.0;
          const converted = convertFlowWithMW(oldFlow, oldUnit, newUnit, currentInputs.gas_comp);
          const nextFlow = Math.round(converted * 100) / 100;
          const flowEl = container.querySelector('[data-field="flow"]');
          if (flowEl) flowEl.value = nextFlow;
          invalidateAirCoolerCache();
          projectStore.setState(s => ({
            inputs: { ...s.inputs, flow: nextFlow, flow_unit: newUnit }
          }));
          return;
        }

        if (f === "p_in_unit") {
          const oldUnit = currentInputs.p_in_unit || "bar(a)";
          const newUnit = v;
          const oldP = parseFloat(currentInputs.p_in) || 20.0;
          const nextP = convertPressureUnit(oldP, oldUnit, newUnit);
          const pEl = container.querySelector('[data-field="p_in"]');
          if (pEl) pEl.value = nextP;
          invalidateAirCoolerCache();
          projectStore.setState(s => ({
            inputs: { ...s.inputs, p_in: nextP, p_in_unit: newUnit }
          }));
          recalculateLiveMetrics();
          scheduleRecommendationsRefresh();
          return;
        }

        if (f === "p_out_unit") {
          const oldUnit = currentInputs.p_out_unit || "bar(a)";
          const newUnit = v;
          const oldP = parseFloat(currentInputs.p_out) || 60.0;
          const nextP = convertPressureUnit(oldP, oldUnit, newUnit);
          const pEl = container.querySelector('[data-field="p_out"]');
          if (pEl) pEl.value = nextP;
          invalidateAirCoolerCache();
          projectStore.setState(s => ({
            inputs: { ...s.inputs, p_out: nextP, p_out_unit: newUnit }
          }));
          recalculateLiveMetrics();
          scheduleRecommendationsRefresh();
          return;
        }

        if (f === "t_in_unit") {
          const oldUnit = currentInputs.t_in_unit || "°C";
          const newUnit = v;
          const oldT = parseFloat(currentInputs.t_in) || 25.0;
          const nextT = convertTemperatureUnit(oldT, oldUnit, newUnit);
          const tEl = container.querySelector('[data-field="t_in"]');
          if (tEl) tEl.value = nextT;
          invalidateAirCoolerCache();
          projectStore.setState(s => ({
            inputs: { ...s.inputs, t_in: nextT, t_in_unit: newUnit }
          }));
          return;
        }

        if (
          [
            "p_in",
            "p_out",
            "t_in",
            "flow",
            "poly_eff",
            "num_stages",
            "num_units",
            "intercooler_t",
            "intercooler_dp_pct",
            "mech_eff",
            "therm_eff",
            "ambient_temp",
            "altitude",
            "humidity",
          ].includes(f)
        ) {
          const parsed = parseFloat(v);
          v = Number.isFinite(parsed) ? parsed : 0;
          if (f === "num_units" || f === "num_stages") v = Math.max(1, Math.round(v));
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
  if (!projectStore.getState().recommendations) {
    fetchRecommendations();
  }
}
