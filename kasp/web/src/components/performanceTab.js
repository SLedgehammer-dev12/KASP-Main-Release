/**
 * KASP Performance & ASME PTC-10 Field Verification Tab Component
 */

import { icon } from "../../vendor/icons.js";
import {
  projectStore,
  escapeHtml,
  convertPressureToBarA,
  convertPressureUnit,
  convertTempToC,
  convertFlowWithMW,
  computeGasMixtureMW,
} from "../store/projectStore.js";
import { showToast } from "../store/uiStore.js";
import { api } from "../api/client.js";

function buildPtc10SummaryText(evalResults, perfInputs) {
  if (!evalResults) return "";
  const st = evalResults.overall_status?.status || evalResults.overall_status || "-";
  const dev = evalResults.deviations || {};
  const lines = [
    `KASP ASME PTC-10 Saha Doğrulama Özeti`,
    `Durum: ${st}`,
    `P_in: ${perfInputs?.p_in ?? "-"} ${perfInputs?.p_in_unit || "bar(a)"} → P_out: ${perfInputs?.p_out ?? "-"} ${perfInputs?.p_out_unit || "bar(a)"}`,
    `T_in: ${perfInputs?.t_in ?? "-"} °C → T_out: ${perfInputs?.t_out ?? "-"} °C | Debi: ${perfInputs?.flow ?? "-"} ${perfInputs?.flow_unit || "kg/s"}`,
  ];
  if (dev.polytropic_head_pct !== undefined) lines.push(`Politropik Yük Sapması: ${Number(dev.polytropic_head_pct).toFixed(2)}%`);
  if (dev.polytropic_efficiency_pct !== undefined) lines.push(`Politropik Verim Sapması: ${Number(dev.polytropic_efficiency_pct).toFixed(2)}%`);
  if (dev.shaft_power_pct !== undefined) lines.push(`Şaft Gücü Sapması: ${Number(dev.shaft_power_pct).toFixed(2)}%`);
  return lines.join("\n");
}

function linkFieldError(el, shown) {
  if (!el) return;
  const errorId = el.dataset.error;
  el.setAttribute("aria-invalid", shown ? "true" : "false");
  el.classList.toggle("is-invalid", !!shown);
  const errNode = errorId ? el.closest(".form-group")?.querySelector(`#${errorId}`) : null;
  if (errNode) {
    errNode.style.display = shown ? "block" : "none";
  }
  if (!errorId) return;
  const ids = (el.getAttribute("aria-describedby") || "")
    .split(/\s+/)
    .filter((id) => id && id !== errorId);
  if (shown) ids.push(errorId);
  if (ids.length) el.setAttribute("aria-describedby", ids.join(" "));
  else el.removeAttribute("aria-describedby");
}

export function renderPerformanceTab(container) {
  let isEvaluating = false;
  let evalResults = null;
  let perfInputs = null;
  let lastSubmittedFieldData = null;
  let userEdited = false;
  let selectedStageIdx = 0;

  function buildDefaultsFromStore(stageIdxOverride = selectedStageIdx) {
    const proj = projectStore.getState();
    const inp = proj.inputs || {};
    const res = proj.results || null;
    const stages = Array.isArray(res?.stages) ? res.stages : [];
    const hasMultiStages = stages.length > 1;
    const validStage = hasMultiStages && stageIdxOverride >= 0 && stageIdxOverride < stages.length
      ? stages[stageIdxOverride]
      : null;

    const pInBarA = validStage
      ? Number(validStage.p_in_bar || 19.5)
      : (convertPressureToBarA(inp.p_in ?? 19.5, inp.p_in_unit || "bar(a)") || 19.5);
    const pOutBarA = validStage
      ? Number(validStage.p_out_bar || 58.2)
      : (convertPressureToBarA(inp.p_out ?? 58.2, inp.p_out_unit || "bar(a)") || 58.2);
    const tInC = validStage
      ? Number(validStage.t_in_c ?? 26.0)
      : convertTempToC(inp.t_in ?? 26.0, inp.t_in_unit || "°C");
    const tOutC = validStage
      ? Number(validStage.t_out_c ?? 85.0)
      : (res?.t_out_c !== undefined ? Number(res.t_out_c) : 138.5);
    const flowRaw = Number(inp.flow ?? 11.8);
    const flowUnitRaw = String(inp.flow_unit || "kg/s");
    const isActualFlow = flowUnitRaw === "m³/h" || flowUnitRaw === "m3/h" || flowUnitRaw.toUpperCase() === "ACMH";
    let flowKgs;
    if (isActualFlow) {
      // ACMH (actual m³/h) → kg/s using an ideal-gas inlet density estimate at P_in/T_in.
      const mwKg = computeGasMixtureMW(inp.gas_comp) / 1000.0;
      const rhoIn = ((pInBarA * 1e5) * mwKg) / (8.314462618 * Math.max(tInC + 273.15, 1.0));
      flowKgs = (Number.isFinite(flowRaw) && flowRaw > 0 && rhoIn > 0) ? (flowRaw * rhoIn) / 3600.0 : 11.8;
    } else {
      flowKgs = convertFlowWithMW(flowRaw, flowUnitRaw, "kg/s", inp.gas_comp) || 11.8;
    }

    return {
      p_in: Math.round(pInBarA * 100) / 100,
      p_in_unit: "bar(a)",
      p_out: Math.round(pOutBarA * 100) / 100,
      p_out_unit: "bar(a)",
      t_in: Math.round(tInC * 10) / 10,
      t_out: Math.round(tOutC * 10) / 10,
      flow: Math.round(flowKgs * 100) / 100,
      flow_unit: "kg/s",
      fuel_flow_kgh: "",
      stage_index: hasMultiStages && stageIdxOverride >= 0 ? stageIdxOverride : "",
    };
  }

  function collectPerfWarnings(res) {
    if (!res) return [];
    const list = [];
    for (const w of res.warnings || []) {
      const txt = typeof w === "string" ? w.trim() : (w?.message || "").trim();
      if (txt && !list.includes(txt)) list.push(txt);
    }
    return list;
  }

  function capturePerfInputsFromDom() {
    const pIn = container.querySelector("#perf-p-in");
    if (!pIn || !perfInputs) return;
    const num = (sel, fallback) => {
      const v = parseFloat(container.querySelector(sel)?.value);
      return Number.isFinite(v) ? v : fallback;
    };
    const str = (sel, fallback) => container.querySelector(sel)?.value || fallback;
    perfInputs = {
      ...perfInputs,
      p_in: num("#perf-p-in", perfInputs.p_in),
      p_in_unit: str("#perf-p-in-unit", perfInputs.p_in_unit),
      p_out: num("#perf-p-out", perfInputs.p_out),
      p_out_unit: str("#perf-p-out-unit", perfInputs.p_out_unit),
      t_in: num("#perf-t-in", perfInputs.t_in),
      t_out: num("#perf-t-out", perfInputs.t_out),
      flow: num("#perf-flow", perfInputs.flow),
      flow_unit: str("#perf-flow-unit", perfInputs.flow_unit),
      fuel_flow_kgh: container.querySelector("#perf-fuel-kgh")?.value ?? "",
    };
  }

  function render() {
    const proj = projectStore.getState();
    const inp = proj.inputs || {};
    const hasDesign = !!proj.results;

    // Preserve in-progress field edits across store-driven re-renders.
    if (perfInputs && userEdited) capturePerfInputsFromDom();
    if (!perfInputs || !userEdited) {
      perfInputs = buildDefaultsFromStore();
    }

    const mwVal = computeGasMixtureMW(inp.gas_comp).toFixed(2);
    const activeEos = String(inp.eos_model || "coolprop").toUpperCase();
    const thermEff = Number(inp.therm_eff || 35.0);
    const perfWarnings = collectPerfWarnings(evalResults);
    const perfStatus = evalResults?.performance_status || null;
    const overallStatusStr = String(perfStatus?.status || "UYGUN").toUpperCase();
    const overallBadgeClass = overallStatusStr.includes("KRİT") || overallStatusStr.includes("KRIT")
      ? "badge-danger"
      : (overallStatusStr.includes("DİKK") || overallStatusStr.includes("DIKK") ? "badge-warning" : "badge-success");

    container.innerHTML = `
      <div style="flex: 1; padding: 20px; overflow-y: auto; display: flex; flex-direction: column; gap: 16px;">
        <div class="card">
          <div class="card-header" style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
            <div class="card-title">
              ${icon("check", 16, "text-primary")}
              <span>ASME PTC-10 Saha Testi Doğrulama ve Sapma Analizi</span>
            </div>
            <div style="display: flex; align-items: center; gap: 6px; flex-wrap: wrap;">
              <span class="badge badge-info" title="Aktif Gaz ve EOS Modeli">EOS: ${escapeHtml(activeEos)} • MW ${mwVal} g/mol</span>
              ${
                hasDesign
                  ? `<span class="badge badge-success">Tasarım Noktası Aktif</span>`
                  : `<span class="badge badge-warning">Tasarım Noktası Yok (Öz-Referans Modu)</span>`
              }
              ${
                Array.isArray(proj.results?.stages) && proj.results.stages.length > 1
                  ? `<select id="perf-stage-ref" class="form-select" style="width: auto; height: 28px; font-size: 11px; padding: 0 8px;" aria-label="ASME PTC-10 Test Bölümü">
                      ${proj.results.stages.map((s, idx) => `<option value="${idx}" ${Number(selectedStageIdx) === idx ? "selected" : ""}>ASME PTC-10 Bölüm ${idx + 1} (Kademe ${s.stage || idx + 1})</option>`).join("")}
                      <option value="-1" ${Number(selectedStageIdx) === -1 ? "selected" : ""}>Tüm Tren (Toplam Giriş/Çıkış)</option>
                     </select>`
                  : ""
              }
              <button type="button" id="btn-sync-from-design" class="btn btn-sm" title="Tasarım sekmesindeki güncel basınç, sıcaklık ve debiyi saha formuna aktar">
                Tasarım Noktasından Doldur
              </button>
              <button type="button" id="btn-reset-ptc10-form" class="btn btn-sm" title="Saha formunu varsayılanlara sıfırla">
                Sıfırla
              </button>
            </div>
          </div>

          <div style="font-size: 12px; color: var(--color-text-secondary); margin-bottom: 16px; line-height: 1.5;">
            Kompresör test sahasından veya SCADA sisteminden alınan gerçek işletme verilerini girin.
            Sistem aktif <b>${escapeHtml(activeEos)}</b> hal denklemi, gerçek karışım molekül ağırlığı (<b>${mwVal} g/mol</b>) ve ISO 5389 saha düzeltmeleriyle ASME PTC-10 kabul durumunu analiz eder.
          </div>

          <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 12px; margin-bottom: 16px;">
            <div class="form-group">
              <label class="form-label" for="perf-p-in">Giriş Basıncı (P_in)</label>
              <div class="form-control-row">
                <input type="number" step="0.1" id="perf-p-in" class="form-input has-addon" value="${perfInputs.p_in}" aria-invalid="false" data-error="perf-pin-err" />
                <select id="perf-p-in-unit" class="form-select input-addon-select" aria-invalid="false">
                  <option value="bar(a)" ${perfInputs.p_in_unit === "bar(a)" ? "selected" : ""}>bar(a)</option>
                  <option value="bar(g)" ${perfInputs.p_in_unit === "bar(g)" ? "selected" : ""}>bar(g)</option>
                  <option value="kPa" ${perfInputs.p_in_unit === "kPa" ? "selected" : ""}>kPa</option>
                  <option value="psi" ${perfInputs.p_in_unit === "psi" ? "selected" : ""}>psi</option>
                </select>
              </div>
              <div id="perf-pin-err" style="display: none; font-size: 11px; color: #ef4444; margin-top: 4px;">Mutlak giriş basıncı pozitif olmalıdır.</div>
            </div>

            <div class="form-group">
              <label class="form-label" for="perf-p-out">Çıkış Basıncı (P_out)</label>
              <div class="form-control-row">
                <input type="number" step="0.1" id="perf-p-out" class="form-input has-addon" value="${perfInputs.p_out}" aria-invalid="false" data-error="perf-pout-err" />
                <select id="perf-p-out-unit" class="form-select input-addon-select" aria-invalid="false">
                  <option value="bar(a)" ${perfInputs.p_out_unit === "bar(a)" ? "selected" : ""}>bar(a)</option>
                  <option value="bar(g)" ${perfInputs.p_out_unit === "bar(g)" ? "selected" : ""}>bar(g)</option>
                  <option value="kPa" ${perfInputs.p_out_unit === "kPa" ? "selected" : ""}>kPa</option>
                  <option value="psi" ${perfInputs.p_out_unit === "psi" ? "selected" : ""}>psi</option>
                </select>
              </div>
              <div id="perf-pout-err" style="display: none; font-size: 11px; color: #ef4444; margin-top: 4px;">Çıkış mutlak basıncı giriş basıncından büyük olmalıdır (PR &gt; 1).</div>
            </div>

            <div class="form-group">
              <label class="form-label" for="perf-t-in">Giriş Sıcaklığı (T_in)</label>
              <div class="form-control-row">
                <input type="number" step="0.1" id="perf-t-in" class="form-input" value="${perfInputs.t_in}" aria-invalid="false" />
                <span style="margin-left: 6px; font-size: 11px;">°C</span>
              </div>
            </div>

            <div class="form-group">
              <label class="form-label" for="perf-t-out">Çıkış Sıcaklığı (T_out)</label>
              <div class="form-control-row">
                <input type="number" step="0.1" id="perf-t-out" class="form-input" value="${perfInputs.t_out}" aria-invalid="false" data-error="perf-tout-err" />
                <span style="margin-left: 6px; font-size: 11px;">°C</span>
              </div>
              <div id="perf-tout-err" style="display: none; font-size: 11px; color: #ef4444; margin-top: 4px;">Geçerli bir çıkış sıcaklığı girilmelidir.</div>
            </div>

            <div class="form-group">
              <label class="form-label" for="perf-flow">Saha Gaz Debisi</label>
              <div class="form-control-row">
                <input type="number" step="0.1" id="perf-flow" class="form-input has-addon" value="${perfInputs.flow}" aria-invalid="false" data-error="perf-flow-err" />
                <select id="perf-flow-unit" class="form-select input-addon-select" aria-invalid="false">
                  <option value="kg/s" ${perfInputs.flow_unit === "kg/s" ? "selected" : ""}>kg/s</option>
                  <option value="kg/h" ${perfInputs.flow_unit === "kg/h" ? "selected" : ""}>kg/h</option>
                  <option value="Sm³/h" ${perfInputs.flow_unit === "Sm³/h" ? "selected" : ""}>Sm³/h</option>
                  <option value="Nm³/h" ${perfInputs.flow_unit === "Nm³/h" ? "selected" : ""}>Nm³/h</option>
                  <option value="MMSCFD" ${perfInputs.flow_unit === "MMSCFD" ? "selected" : ""}>MMSCFD</option>
                  <option value="MMSCMD" ${perfInputs.flow_unit === "MMSCMD" ? "selected" : ""}>MMSCMD</option>
                  <option value="m³/h" ${perfInputs.flow_unit === "m³/h" ? "selected" : ""}>m³/h (ACMH)</option>
                </select>
              </div>
              <div id="perf-flow-err" style="display: none; font-size: 11px; color: #ef4444; margin-top: 4px;">Gaz debisi sıfırdan büyük olmalıdır.</div>
            </div>

            <div class="form-group">
              <label class="form-label" for="perf-fuel-kgh">Ölçülü Yakıt (Opsiyonel)</label>
              <div class="form-control-row">
                <input type="number" step="1" min="0" id="perf-fuel-kgh" class="form-input" placeholder="Boş = η_th %${thermEff.toFixed(0)}" value="${perfInputs.fuel_flow_kgh ?? ""}" aria-invalid="false" />
                <span style="margin-left: 6px; font-size: 11px;">kg/h</span>
              </div>
            </div>
          </div>

          <button id="btn-run-ptc10" class="btn btn-primary" ${isEvaluating ? "disabled" : ""}>
            ${icon("play", 14)}
            <span>${isEvaluating ? "Değerlendiriliyor..." : "Saha Verisini Doğrula (ASME PTC-10)"}</span>
          </button>
        </div>

        ${
          perfWarnings.length > 0
            ? `
            <div id="perf-warnings-banner" role="alert" aria-live="polite" style="padding: 12px 14px; border-radius: var(--radius-md); background: rgba(245, 158, 11, 0.10); border: 1px solid rgba(245, 158, 11, 0.40); color: var(--color-text);">
              <div style="font-size: 12px; font-weight: 700; color: #d97706; margin-bottom: 4px;">
                ⚠️ ASME PTC-10 Hesaplama Uyarıları (${perfWarnings.length})
              </div>
              <ul style="margin: 0; padding-left: 18px; font-size: 11px; line-height: 1.45;">
                ${perfWarnings.map((w) => `<li>${escapeHtml(w)}</li>`).join("")}
              </ul>
            </div>
          `
            : ""
        }

        ${
          evalResults
            ? `
            <!-- ASME PTC-10 Thermodynamic KPI Summary -->
            <div class="metrics-grid">
              <div class="metric-card">
                <div class="metric-label">Politropik Verim (η_p)</div>
                <div class="metric-value-row">
                  <span class="metric-value" style="color: ${Math.abs(Number(evalResults.deviation_poly_eff || 0)) > 5 ? "#ef4444" : "#10b981"};">%${Number(evalResults.poly_eff || 0).toFixed(1)}</span>
                  <span class="metric-unit">poly</span>
                </div>
                <div style="font-size: 10px; color: var(--color-text-secondary); margin-top: 2px;">
                  Tasarım: <strong>%${Number(evalResults.design_poly_eff || 0).toFixed(1)}</strong> (${Number(evalResults.deviation_poly_eff || 0) > 0 ? "+" : ""}${Number(evalResults.deviation_poly_eff || 0).toFixed(2)}%) • η_s: %${Number(evalResults.isen_eff || 0).toFixed(1)}
                </div>
              </div>

              <div class="metric-card">
                <div class="metric-label">Politropik Yük (Head)</div>
                <div class="metric-value-row">
                  <span class="metric-value" style="color: #0284c7;">${Number(evalResults.poly_head_kj_kg || 0).toFixed(1)}</span>
                  <span class="metric-unit">kJ/kg</span>
                </div>
                <div style="font-size: 10px; color: var(--color-text-secondary); margin-top: 2px;">
                  Kütlesel Debi: <strong>${Number(evalResults.flow_kgs || 0).toFixed(2)} kg/s</strong> • EOS: ${escapeHtml(String(evalResults.eos_model || activeEos).toUpperCase())}
                </div>
              </div>

              <div class="metric-card">
                <div class="metric-label">Saha Mil Gücü / ISO 5389</div>
                <div class="metric-value-row">
                  <span class="metric-value" style="color: #f59e0b;">${Number(evalResults.shaft_power_kw || 0).toLocaleString("tr-TR", { maximumFractionDigits: 0 })}</span>
                  <span class="metric-unit">kW</span>
                </div>
                <div style="font-size: 10px; color: var(--color-text-secondary); margin-top: 2px;">
                  ISO Düzeltilmiş: <strong>${Number(evalResults.corrected_power_kw || 0).toLocaleString("tr-TR", { maximumFractionDigits: 0 })} kW</strong> (${Number(evalResults.deviation_power || 0) > 0 ? "+" : ""}${Number(evalResults.deviation_power || 0).toFixed(2)}%)
                </div>
              </div>

              <div class="metric-card">
                <div class="metric-label">Yakıt &amp; Isı Tüketimi</div>
                <div class="metric-value-row">
                  <span class="metric-value" style="color: #8b5cf6;">${Number(evalResults.fuel_cons_kg_h || 0).toLocaleString("tr-TR", { maximumFractionDigits: 1 })}</span>
                  <span class="metric-unit">kg/h</span>
                </div>
                <div style="font-size: 10px; color: var(--color-text-secondary); margin-top: 2px;">
                  Isı Oranı: <strong>${Math.round(Number(evalResults.actual_heat_rate || 0)).toLocaleString("tr-TR")} kJ/kWh</strong> • η_th: %${Number(evalResults.turb_eff || 0).toFixed(1)}
                </div>
              </div>
            </div>

            <!-- Evaluation Results Table -->
            <div class="card">
              <div class="card-header" style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
                <div class="card-title" id="ptc10-matrix-heading">
                  ${icon("activity", 16, "text-primary")}
                  <span>6-Metrik ASME PTC-10 Tolerans ve Sapma Matrisi</span>
                  <span class="badge ${overallBadgeClass}" style="margin-left: 6px;">Genel Karar: ${escapeHtml(overallStatusStr)}</span>
                </div>
                <div style="display: flex; align-items: center; gap: 6px;">
                  <button type="button" id="btn-copy-ptc10-summary" class="btn btn-sm" title="ASME PTC-10 özetini panoya kopyala">
                    ${icon("copy", 14)}
                    <span>Özeti Kopyala</span>
                  </button>
                  <button id="btn-perf-pdf-export" class="btn btn-sm" title="ASME PTC-10 PDF Raporu İndir">
                    ${icon("fileText", 14)}
                    <span>Performans PDF İndir</span>
                  </button>
                </div>
              </div>

              ${
                perfStatus?.description
                  ? `<div style="font-size: 11px; color: var(--color-text-secondary); margin-bottom: 12px; padding: 8px 10px; border-radius: var(--radius-sm); background: var(--color-bg); border: 1px solid var(--color-border);">
                      <b>${escapeHtml(perfStatus.status || "Durum")}:</b> ${escapeHtml(perfStatus.description)} — <i>${escapeHtml(perfStatus.recommendation || "")}</i>
                    </div>`
                  : ""
              }

              <div tabindex="0" role="region" aria-labelledby="ptc10-matrix-heading" style="overflow-x: auto; max-inline-size: 100%;">
                <table class="kasp-table">
                  <thead>
                    <tr>
                      <th scope="col">Performans Parametresi</th>
                      <th scope="col" style="text-align: right;">Saha Test Değeri</th>
                      <th scope="col" style="text-align: right;">Tasarım Referansı</th>
                      <th scope="col" style="text-align: right;">Sapma (%)</th>
                      <th scope="col" style="text-align: center;">Tolerans Limiti</th>
                      <th scope="col" style="text-align: center;">ASME PTC-10 Kararı</th>
                    </tr>
                  </thead>
                  <tbody>
                    ${(evalResults.comparison || []).map((row) => {
                      const rowName = row.name || row.parameter || "-";
                      const testVal = row.test_val !== undefined ? row.test_val : row.test_value;
                      const designVal = row.design_val !== undefined ? row.design_val : row.design_value;
                      const devPct = row.dev_pct !== undefined ? row.dev_pct : row.deviation_pct;
                      const tolCrit = row.tol_crit !== undefined ? row.tol_crit : (row.tolerance_pct !== undefined ? row.tolerance_pct : 5.0);
                      const rawStatus = String(row.status || "").toUpperCase();
                      const statusClass = (rawStatus === "OK" || rawStatus === "VALID")
                        ? "badge-success"
                        : (rawStatus === "WARNING" ? "badge-warning" : "badge-danger");
                      const statusLabel = (rawStatus === "OK" || rawStatus === "VALID") ? "OK"
                        : (rawStatus === "WARNING" ? "WARNING" : "CRITICAL");
                      return `
                        <tr>
                          <th scope="row" style="font-weight: 600; text-align: left;">${escapeHtml(rowName)}</th>
                          <td style="text-align: right; font-family: var(--font-mono);">${typeof testVal === "number" ? testVal.toFixed(2) : escapeHtml(testVal ?? "-")} ${escapeHtml(row.unit || "")}</td>
                          <td style="text-align: right; font-family: var(--font-mono);">${typeof designVal === "number" ? designVal.toFixed(2) : escapeHtml(designVal ?? "-")} ${escapeHtml(row.unit || "")}</td>
                          <td style="text-align: right; font-family: var(--font-mono); font-weight: 600;">${typeof devPct === "number" && devPct > 0 ? "+" : ""}${typeof devPct === "number" ? devPct.toFixed(2) : "-"}%</td>
                          <td style="text-align: center; font-size: 11px; color: var(--color-text-secondary);">±%${tolCrit ?? 5.0}</td>
                          <td style="text-align: center;"><span class="badge ${statusClass}">${statusLabel}</span></td>
                        </tr>
                      `;
                    }).join("")}
                  </tbody>
                </table>
              </div>
            </div>
          `
            : ""
        }
      </div>
    `;

    const pInEl = container.querySelector("#perf-p-in");
    const pInUnitEl = container.querySelector("#perf-p-in-unit");
    const pOutEl = container.querySelector("#perf-p-out");
    const pOutUnitEl = container.querySelector("#perf-p-out-unit");
    const tInEl = container.querySelector("#perf-t-in");
    const tOutEl = container.querySelector("#perf-t-out");
    const flowEl = container.querySelector("#perf-flow");
    const flowUnitEl = container.querySelector("#perf-flow-unit");
    const fuelEl = container.querySelector("#perf-fuel-kgh");

    // Clear field error states as user edits
    [pInEl, pOutEl, tOutEl, flowEl].forEach((el) => {
      el?.addEventListener("input", () => {
        userEdited = true;
        linkFieldError(el, false);
      });
    });
    [tInEl, fuelEl].forEach((el) => {
      el?.addEventListener("input", () => {
        userEdited = true;
      });
    });

    pInUnitEl?.addEventListener("change", (e) => {
      userEdited = true;
      const newU = e.target.value;
      const curVal = parseFloat(pInEl?.value);
      if (Number.isFinite(curVal)) {
        const converted = Math.round(convertPressureUnit(curVal, perfInputs.p_in_unit, newU) * 100) / 100;
        perfInputs.p_in = converted;
        if (pInEl) pInEl.value = converted;
      }
      perfInputs.p_in_unit = newU;
    });

    pOutUnitEl?.addEventListener("change", (e) => {
      userEdited = true;
      const newU = e.target.value;
      const curVal = parseFloat(pOutEl?.value);
      if (Number.isFinite(curVal)) {
        const converted = Math.round(convertPressureUnit(curVal, perfInputs.p_out_unit, newU) * 100) / 100;
        perfInputs.p_out = converted;
        if (pOutEl) pOutEl.value = converted;
      }
      perfInputs.p_out_unit = newU;
    });

    flowUnitEl?.addEventListener("change", (e) => {
      userEdited = true;
      const newU = e.target.value;
      const curVal = parseFloat(flowEl?.value);
      if (Number.isFinite(curVal) && curVal > 0 && perfInputs.flow_unit !== "m³/h" && newU !== "m³/h") {
        const gasComp = projectStore.getState().inputs?.gas_comp;
        const converted = Math.round(convertFlowWithMW(curVal, perfInputs.flow_unit, newU, gasComp) * 100) / 100;
        perfInputs.flow = converted;
        if (flowEl) flowEl.value = converted;
      }
      perfInputs.flow_unit = newU;
    });

    container.querySelector("#perf-stage-ref")?.addEventListener("change", (e) => {
      selectedStageIdx = parseInt(e.target.value, 10);
      userEdited = false;
      perfInputs = buildDefaultsFromStore(selectedStageIdx);
      render();
    });

    container.querySelector("#btn-sync-from-design")?.addEventListener("click", () => {
      userEdited = false;
      perfInputs = buildDefaultsFromStore(selectedStageIdx);
      render();
      showToast("Tasarım noktası değerleri saha formuna aktarıldı.");
    });

    // Bind evaluate button
    container.querySelector("#btn-run-ptc10")?.addEventListener("click", async () => {
      const pIn = parseFloat(pInEl?.value);
      const pInUnit = pInUnitEl?.value || "bar(a)";
      const pOut = parseFloat(pOutEl?.value);
      const pOutUnit = pOutUnitEl?.value || "bar(a)";
      const tIn = parseFloat(tInEl?.value);
      const tOut = parseFloat(tOutEl?.value);
      const flow = parseFloat(flowEl?.value);
      const flowUnit = flowUnitEl?.value || "kg/s";
      const fuelRaw = fuelEl?.value?.trim() || "";
      const fuelFlowKgh = fuelRaw !== "" ? parseFloat(fuelRaw) : null;

      const pInAbs = convertPressureToBarA(pIn, pInUnit);
      const pOutAbs = convertPressureToBarA(pOut, pOutUnit);

      let firstInvalid = null;
      const markCheck = (el, bad) => {
        linkFieldError(el, bad);
        if (bad && !firstInvalid) firstInvalid = el;
      };

      markCheck(pInEl, !Number.isFinite(pIn) || pInAbs <= 0);
      markCheck(pOutEl, !Number.isFinite(pOut) || pOutAbs <= pInAbs);
      markCheck(tOutEl, !Number.isFinite(tOut));
      markCheck(flowEl, !Number.isFinite(flow) || flow <= 0);

      if (firstInvalid) {
        firstInvalid.focus();
        showToast("Lütfen vurgulanan saha ölçüm alanlarını düzeltin.", "warning");
        return;
      }

      userEdited = true;
      perfInputs = {
        p_in: pIn,
        p_in_unit: pInUnit,
        p_out: pOut,
        p_out_unit: pOutUnit,
        t_in: Number.isFinite(tIn) ? tIn : 25.0,
        t_out: tOut,
        flow,
        flow_unit: flowUnit,
        fuel_flow_kgh: fuelFlowKgh !== null && Number.isFinite(fuelFlowKgh) && fuelFlowKgh > 0 ? fuelFlowKgh : "",
      };
      isEvaluating = true;
      render();

      const curInputs = projectStore.getState().inputs || {};
      const fieldData = {
        project_name: curInputs.project_name || "ASME PTC-10 Saha Testi",
        unit_name: curInputs.project_name || "Kompresör Ünitesi",
        p_in: perfInputs.p_in,
        p_in_unit: perfInputs.p_in_unit,
        p_out: perfInputs.p_out,
        p_out_unit: perfInputs.p_out_unit,
        t_in: perfInputs.t_in,
        t_in_unit: "°C",
        t_out: perfInputs.t_out,
        t_out_unit: "°C",
        flow: perfInputs.flow,
        flow_unit: perfInputs.flow_unit,
        gas_comp: curInputs.gas_comp,
        eos_model: curInputs.eos_model || "coolprop",
        mech_eff: Number(curInputs.mech_eff || 98.0),
        therm_eff: Number(curInputs.therm_eff || 35.0),
        ambient_temp: Number(curInputs.t_amb ?? curInputs.ambient_temp ?? 15.0),
        ambient_pressure: Number(curInputs.ambient_pressure ?? 101.325),
        humidity: Number(curInputs.humidity ?? 60.0),
        altitude: Number(curInputs.altitude ?? 0.0),
      };
      if (Array.isArray(projectStore.getState().results?.stages) && projectStore.getState().results.stages.length > 1 && selectedStageIdx >= 0) {
        fieldData.stage_index = selectedStageIdx;
      }
      if (perfInputs.fuel_flow_kgh !== "") {
        fieldData.fuel_flow_kgh = Number(perfInputs.fuel_flow_kgh);
        fieldData.fuel_flow = Number(perfInputs.fuel_flow_kgh);
        fieldData.fuel_flow_unit = "kg/h";
      }

      try {
        evalResults = await api.post("/api/v1/calculations/performance", {
          field_data: fieldData,
          design_point: projectStore.getState().results,
        });
        lastSubmittedFieldData = {
          ...fieldData,
          fuel_flow: fieldData.fuel_flow ?? Math.round(Number(evalResults?.fuel_cons_kg_h || 0) * 10) / 10,
          fuel_flow_unit: "kg/h",
        };
        showToast("ASME PTC-10 değerlendirmesi tamamlandı.");
      } catch (err) {
        showToast("Performans değerlendirme hatası: " + err.message, "danger");
      } finally {
        isEvaluating = false;
        render();
      }
    });

    container.querySelector("#btn-reset-ptc10-form")?.addEventListener("click", () => {
      userEdited = false;
      perfInputs = buildDefaultsFromStore();
      evalResults = null;
      render();
      showToast("ASME PTC-10 saha formu sıfırlandı.", "info");
    });

    container.querySelector("#btn-copy-ptc10-summary")?.addEventListener("click", async () => {
      if (!evalResults) return;
      const summary = buildPtc10SummaryText(evalResults, perfInputs);
      try {
        if (navigator.clipboard?.writeText) await navigator.clipboard.writeText(summary);
        showToast("ASME PTC-10 özeti panoya kopyalandı.", "success");
      } catch (_) {}
    });

    // Bind PDF export button (sends actual field test inputs, NOT design inputs)
    container.querySelector("#btn-perf-pdf-export")?.addEventListener("click", async () => {
      if (!evalResults) return;
      const proj = projectStore.getState();
      const filename = `asme_ptc10_${(proj.inputs.project_name || "kasp").replace(/\s+/g, "_")}.pdf`;
      const pdfInputs = lastSubmittedFieldData || {
        ...proj.inputs,
        ...perfInputs,
        t_in_unit: "°C",
        t_out_unit: "°C",
      };
      try {
        await api.downloadFile(
          "/api/v1/reports/performance-pdf",
          {
            inputs: pdfInputs,
            results: evalResults,
            filename,
          },
          filename
        );
        showToast("ASME PTC-10 Performans PDF raporu indirildi.", "success");
      } catch (err) {
        showToast("PDF indirme hatası: " + err.message, "danger");
      }
    });
  }

  projectStore.subscribe(render);
  render();
}
