/**
 * KASP Performance & ASME PTC-10 Field Verification Tab Component
 */

import { icon } from "../../vendor/icons.js";
import { projectStore } from "../store/projectStore.js";
import { showToast } from "../store/uiStore.js";
import { api } from "../api/client.js";

function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

export function renderPerformanceTab(container) {
  let isEvaluating = false;
  let evalResults = null;
  let perfInputs = null;

  function render() {
    const proj = projectStore.getState();
    const hasDesign = !!proj.results;

    const pInVal = perfInputs?.p_in !== undefined ? perfInputs.p_in : (proj.inputs?.p_in || 19.5);
    const pOutVal = perfInputs?.p_out !== undefined ? perfInputs.p_out : (proj.inputs?.p_out || 58.2);
    const tInVal = perfInputs?.t_in !== undefined ? perfInputs.t_in : (proj.inputs?.t_in || 26.0);
    const tOutVal = perfInputs?.t_out !== undefined ? perfInputs.t_out : (proj.results?.t_out_c !== undefined ? Number(proj.results.t_out_c).toFixed(1) : 138.5);
    const flowVal = perfInputs?.flow !== undefined ? perfInputs.flow : (proj.inputs?.flow || 11.8);

    container.innerHTML = `
      <div style="flex: 1; padding: 20px; overflow-y: auto; display: flex; flex-direction: column; gap: 16px;">
        <div class="card">
          <div class="card-header">
            <div class="card-title">
              ${icon("check", 16, "text-primary")}
              <span>ASME PTC-10 Saha Testi Doğrulama ve Sapma Analizi</span>
            </div>
            ${
              hasDesign
                ? `<span class="badge badge-success">Tasarım Noktası Aktif</span>`
                : `<span class="badge badge-warning">Tasarım Noktası Yok (Varsayılan Kıyaslama)</span>`
            }
          </div>

          <div style="font-size: 12px; color: var(--color-text-secondary); margin-bottom: 16px; line-height: 1.5;">
            Kompresör test sahasından veya SCADA sisteminden alınan gerçek işletme verilerini girin. 
            Sistem ASME PTC-10 ve ISO 5389 kriterlerine göre 6 temel metrikte sapmaları (% deviasyon) ve kabul durumunu analiz eder.
          </div>

          <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; margin-bottom: 16px;">
            <div class="form-group">
              <label class="form-label">Giriş Basıncı (P_in)</label>
              <div class="form-control-row">
                <input type="number" step="0.1" id="perf-p-in" class="form-input" value="${pInVal}" />
                <span style="margin-left: 6px; font-size: 11px;">bar(a)</span>
              </div>
            </div>

            <div class="form-group">
              <label class="form-label">Çıkış Basıncı (P_out)</label>
              <div class="form-control-row">
                <input type="number" step="0.1" id="perf-p-out" class="form-input" value="${pOutVal}" />
                <span style="margin-left: 6px; font-size: 11px;">bar(a)</span>
              </div>
            </div>

            <div class="form-group">
              <label class="form-label">Giriş Sıcaklığı (T_in)</label>
              <div class="form-control-row">
                <input type="number" step="0.1" id="perf-t-in" class="form-input" value="${tInVal}" />
                <span style="margin-left: 6px; font-size: 11px;">°C</span>
              </div>
            </div>

            <div class="form-group">
              <label class="form-label">Çıkış Sıcaklığı (T_out)</label>
              <div class="form-control-row">
                <input type="number" step="0.1" id="perf-t-out" class="form-input" value="${tOutVal}" />
                <span style="margin-left: 6px; font-size: 11px;">°C</span>
              </div>
            </div>

            <div class="form-group">
              <label class="form-label">Kütlesel Debi (m_dot)</label>
              <div class="form-control-row">
                <input type="number" step="0.1" id="perf-flow" class="form-input" value="${flowVal}" />
                <span style="margin-left: 6px; font-size: 11px;">kg/s</span>
              </div>
            </div>
          </div>

          <button id="btn-run-ptc10" class="btn btn-primary" ${isEvaluating ? "disabled" : ""}>
            ${icon("play", 14)}
            <span>${isEvaluating ? "Değerlendiriliyor..." : "Saha Verisini Doğrula (ASME PTC-10)"}</span>
          </button>
        </div>

        <!-- Evaluation Results Table -->
        ${
          evalResults
            ? `
            <div class="card">
              <div class="card-header" style="display: flex; justify-content: space-between; align-items: center;">
                <div class="card-title">
                  ${icon("activity", 16, "text-primary")}
                  <span>6-Metrik ASME PTC-10 Tolerans ve Sapma Matrisi</span>
                </div>
                <button id="btn-perf-pdf-export" class="btn btn-sm" title="ASME PTC-10 PDF Raporu İndir">
                  ${icon("fileText", 14)}
                  <span>Performans PDF İndir</span>
                </button>
              </div>
              <table class="kasp-table">
                <thead>
                  <tr>
                    <th>Performans Parametresi</th>
                    <th style="text-align: right;">Saha Test Değeri</th>
                    <th style="text-align: right;">Tasarım Referansı</th>
                    <th style="text-align: right;">Sapma (%)</th>
                    <th style="text-align: center;">Tolerans Limiti</th>
                    <th style="text-align: center;">ASME PTC-10 Kararı</th>
                  </tr>
                </thead>
                <tbody>
                  ${(evalResults.comparison || []).map(row => {
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
                        <td style="font-weight: 600;">${escapeHtml(rowName)}</td>
                        <td style="text-align: right; font-family: var(--font-mono);">${typeof testVal === 'number' ? testVal.toFixed(2) : escapeHtml(testVal ?? '-')} ${escapeHtml(row.unit || '')}</td>
                        <td style="text-align: right; font-family: var(--font-mono);">${typeof designVal === 'number' ? designVal.toFixed(2) : escapeHtml(designVal ?? '-')} ${escapeHtml(row.unit || '')}</td>
                        <td style="text-align: right; font-family: var(--font-mono); font-weight: 600;">${typeof devPct === 'number' && devPct > 0 ? '+' : ''}${typeof devPct === 'number' ? devPct.toFixed(2) : '-'}%</td>
                        <td style="text-align: center; font-size: 11px; color: var(--color-text-secondary);">±%${tolCrit ?? 5.0}</td>
                        <td style="text-align: center;"><span class="badge ${statusClass}">${statusLabel}</span></td>
                      </tr>
                    `;
                  }).join("")}
                </tbody>
              </table>
            </div>
          `
            : ""
        }
      </div>
    `;

    // Bind evaluate button
    container.querySelector("#btn-run-ptc10")?.addEventListener("click", async () => {
      const pIn = parseFloat(container.querySelector("#perf-p-in")?.value);
      const pOut = parseFloat(container.querySelector("#perf-p-out")?.value);
      const tIn = parseFloat(container.querySelector("#perf-t-in")?.value);
      const tOut = parseFloat(container.querySelector("#perf-t-out")?.value);
      const flow = parseFloat(container.querySelector("#perf-flow")?.value);

      if (isNaN(pIn) || pIn <= 0) {
        showToast("Geçersiz giriş basıncı: Mutlak basınç pozitif olmalıdır.", "warning");
        return;
      }
      if (isNaN(pOut) || pOut <= pIn) {
        showToast("Çıkış basıncı giriş basıncından büyük olmalıdır (PR > 1.0).", "warning");
        return;
      }
      if (isNaN(flow) || flow <= 0) {
        showToast("Kütlesel debi pozitif bir değer olmalıdır.", "warning");
        return;
      }

      perfInputs = { p_in: pIn, p_out: pOut, t_in: tIn, t_out: tOut, flow };
      isEvaluating = true;
      render();

      const fieldData = {
        p_in: pIn,
        p_in_unit: "bar(a)",
        p_out: pOut,
        p_out_unit: "bar(a)",
        t_in: tIn,
        t_in_unit: "°C",
        t_out: tOut,
        t_out_unit: "°C",
        flow: flow,
        flow_unit: "kg/s",
        gas_comp: projectStore.getState().inputs.gas_comp,
      };

      try {
        evalResults = await api.post("/api/v1/calculations/performance", {
          field_data: fieldData,
          design_point: projectStore.getState().results,
        });
        showToast("ASME PTC-10 değerlendirmesi tamamlandı.");
      } catch (err) {
        showToast("Performans değerlendirme hatası: " + err.message, "danger");
      } finally {
        isEvaluating = false;
        render();
      }
    });

    // Bind PDF export button
    container.querySelector("#btn-perf-pdf-export")?.addEventListener("click", async () => {
      if (!evalResults) return;
      const proj = projectStore.getState();
      const filename = `asme_ptc10_${(proj.inputs.project_name || "kasp").replace(/\s+/g, "_")}.pdf`;
      try {
        await api.downloadFile("/api/v1/reports/performance-pdf", {
          inputs: proj.inputs,
          results: evalResults,
          filename,
        }, filename);
      } catch (err) {
        showToast("PDF indirme hatası: " + err.message, "danger");
      }
    });
  }

  projectStore.subscribe(render);
  render();
}
