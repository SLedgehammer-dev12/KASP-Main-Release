/**
 * KASP Engineering Shootout Tab Component
 * 8-EOS x 6-Method benchmark suite with real-time SSE progress streaming,
 * job cancellation, and interactive comparison chart.
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

const AVAILABLE_EOS = [
  { id: "coolprop", name: "CoolProp (HEOS Ref.)" },
  { id: "pr", name: "Peng-Robinson (Kübik)" },
  { id: "srk", name: "Soave-Redlich-Kwong (Kübik)" },
  { id: "rk", name: "Redlich-Kwong" },
  { id: "vdw", name: "Van der Waals" },
  { id: "bwrs", name: "Benedict-Webb-Rubin-Starling" },
  { id: "gerg2008", name: "GERG-2008 Doğalgaz Modeli" },
];

const AVAILABLE_METHODS = [
  "Metot 1: Ortalama Özellikler",
  "Metot 2: Endpoint Yaklaşımı",
  "Metot 3: Artımlı Basınç",
  "Metot 4: Artımlı Entalpi",
  "Metot 5: Schultz 2-Üslü",
  "Metot 6: Schultz 3-Üslü Gerçek Gaz",
];

export function renderShootoutTab(container) {
  let selectedEos = ["coolprop", "pr", "srk"];
  let selectedMethods = [
    "Metot 1: Ortalama Özellikler",
    "Metot 5: Schultz 2-Üslü",
    "Metot 6: Schultz 3-Üslü Gerçek Gaz",
  ];

  let currentJobId = null;
  let isRunning = false;
  let progressPct = 0;
  let completedRuns = 0;
  let totalRuns = 0;
  let resultsList = [];
  let eventSource = null;

  function render() {
    totalRuns = selectedEos.length * selectedMethods.length;

    container.innerHTML = `
      <div style="flex: 1; padding: 20px; overflow-y: auto; display: flex; flex-direction: column; gap: 16px;">
        <div class="card">
          <div class="card-header">
            <div class="card-title">
              ${icon("cpu", 16, "text-primary")}
              <span>Mühendislik Termodinamik Shootout (Benchmark)</span>
            </div>
            <div style="font-size: 11px; color: var(--color-text-secondary);">
              Toplam Kombinasyon: <b>${totalRuns} Analiz</b>
            </div>
          </div>

          <div style="font-size: 12px; color: var(--color-text-secondary); margin-bottom: 16px;">
            Aynı gaz karışımı ve proses şartları için farklı termodinamik durum denklemleri (EOS) ile politropik yol metotlarını 
            paralel olarak test eder ve sonuçları sapma haritasında kıyaslar.
          </div>

          <!-- Configuration Matrix -->
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 16px;">
            <div>
              <div style="font-weight: 600; font-size: 12px; margin-bottom: 8px;">Kullanılacak Durum Denklemleri (EOS):</div>
              <div style="display: flex; flex-direction: column; gap: 6px;">
                ${AVAILABLE_EOS.map(eos => `
                  <label style="display: flex; align-items: center; gap: 8px; font-size: 12px; cursor: pointer;">
                    <input type="checkbox" class="eos-check" value="${eos.id}" ${selectedEos.includes(eos.id) ? "checked" : ""} ${isRunning ? "disabled" : ""} />
                    <span>${eos.name}</span>
                  </label>
                `).join("")}
              </div>
            </div>

            <div>
              <div style="font-weight: 600; font-size: 12px; margin-bottom: 8px;">Kullanılacak Politropik Yol Metotları:</div>
              <div style="display: flex; flex-direction: column; gap: 6px;">
                ${AVAILABLE_METHODS.map(m => `
                  <label style="display: flex; align-items: center; gap: 8px; font-size: 12px; cursor: pointer;">
                    <input type="checkbox" class="method-check" value="${m}" ${selectedMethods.includes(m) ? "checked" : ""} ${isRunning ? "disabled" : ""} />
                    <span>${m}</span>
                  </label>
                `).join("")}
              </div>
            </div>
          </div>

          <!-- Actions -->
          <div style="display: flex; align-items: center; gap: 12px;">
            ${
              !isRunning
                ? `<button id="btn-start-shootout" class="btn btn-primary" ${totalRuns === 0 ? "disabled" : ""}>
                    ${icon("play", 14)}
                    <span>Shootout Analizini Başlat (${totalRuns} Test)</span>
                   </button>`
                : `<button id="btn-cancel-shootout" class="btn btn-danger">
                    ${icon("x", 14)}
                    <span>Hesaplamayı Durdur</span>
                   </button>`
            }
          </div>

          <!-- Live Progress Bar -->
          ${
            isRunning || progressPct > 0
              ? `
              <div style="margin-top: 16px;">
                <div style="display: flex; justify-content: space-between; font-size: 11px; margin-bottom: 4px;">
                  <span id="shootout-progress-text">İlerleme: <b>${completedRuns} / ${totalRuns}</b></span>
                  <span id="shootout-progress-pct">%${progressPct.toFixed(1)}</span>
                </div>
                <div style="width: 100%; height: 8px; background: var(--color-surface-hover); border-radius: var(--radius-full); overflow: hidden;">
                  <div id="shootout-progress-bar" style="width: ${progressPct}%; height: 100%; background: var(--color-primary); transition: width 200ms ease;"></div>
                </div>
              </div>
            `
              : ""
          }
        </div>

        <!-- Live Results Table -->
        ${
          resultsList.length > 0 || isRunning
            ? `
            <div class="card" id="shootout-results-card">
              <div class="card-header">
                <div class="card-title">
                  ${icon("activity", 16, "text-primary")}
                  <span>Tamamlanan Kıyaslama Sonuçları <span id="shootout-results-count">(${resultsList.length})</span></span>
                </div>
              </div>

              <div style="max-height: 350px; overflow-y: auto;">
                <table class="kasp-table">
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>Durum Denklemi (EOS)</th>
                      <th>Politropik Yol Metodu</th>
                      <th style="text-align: right;">Mil Gücü (kW)</th>
                      <th style="text-align: right;">Çıkış Sıcaklığı (°C)</th>
                      <th style="text-align: right;">Verim (%)</th>
                      <th style="text-align: right;">Süre (ms)</th>
                      <th style="text-align: center;">Durum</th>
                    </tr>
                  </thead>
                  <tbody id="shootout-results-tbody">
                    ${resultsList.map(r => `
                      <tr>
                        <td>${escapeHtml(r.step || '-')}</td>
                        <td style="font-weight: 600;">${escapeHtml(r.eos?.toUpperCase())}</td>
                        <td>${escapeHtml(r.method)}</td>
                        <td style="text-align: right; font-family: var(--font-mono); font-weight: 600;">${r.power_kw ? r.power_kw.toFixed(1) : '-'}</td>
                        <td style="text-align: right; font-family: var(--font-mono);">${r.t_out_c ? r.t_out_c.toFixed(1) : '-'}</td>
                        <td style="text-align: right; font-family: var(--font-mono);">${r.eff_pct ? `%${r.eff_pct.toFixed(2)}` : '-'}</td>
                        <td style="text-align: right; font-family: var(--font-mono); color: var(--color-text-secondary);">${r.duration_ms || 0} ms</td>
                        <td style="text-align: center;">
                          <span class="badge ${r.status === 'success' ? 'badge-success' : 'badge-danger'}">${escapeHtml(r.status)}</span>
                        </td>
                      </tr>
                    `).join("")}
                  </tbody>
                </table>
              </div>
            </div>
          `
            : ""
        }
      </div>
    `;

    // Bind checkboxes
    container.querySelectorAll(".eos-check").forEach(cb => {
      cb.addEventListener("change", () => {
        if (cb.checked) {
          selectedEos.push(cb.value);
        } else {
          selectedEos = selectedEos.filter(x => x !== cb.value);
        }
        render();
      });
    });

    container.querySelectorAll(".method-check").forEach(cb => {
      cb.addEventListener("change", () => {
        if (cb.checked) {
          selectedMethods.push(cb.value);
        } else {
          selectedMethods = selectedMethods.filter(x => x !== cb.value);
        }
        render();
      });
    });

    // Start button
    container.querySelector("#btn-start-shootout")?.addEventListener("click", startShootout);
    container.querySelector("#btn-cancel-shootout")?.addEventListener("click", cancelShootout);
  }

  async function startShootout() {
    const inputs = projectStore.getState().inputs;
    resultsList = [];
    progressPct = 0;
    completedRuns = 0;
    isRunning = true;
    render();

    try {
      const initRes = await api.post("/api/v1/jobs/shootout", {
        inputs,
        eos_list: selectedEos,
        method_list: selectedMethods,
      });

      currentJobId = initRes.job_id;
      totalRuns = initRes.total_runs;

      // Connect to SSE stream
      eventSource = new EventSource(`/api/v1/jobs/${currentJobId}/stream`);

      function updateLiveProgress(r) {
        const pBar = container.querySelector("#shootout-progress-bar");
        const pText = container.querySelector("#shootout-progress-text");
        const pPct = container.querySelector("#shootout-progress-pct");
        const tbody = container.querySelector("#shootout-results-tbody");
        const countEl = container.querySelector("#shootout-results-count");

        if (pBar) pBar.style.width = `${progressPct}%`;
        if (pText) pText.innerHTML = `İlerleme: <b>${completedRuns} / ${totalRuns}</b>`;
        if (pPct) pPct.textContent = `%${progressPct.toFixed(1)}`;
        if (countEl) countEl.textContent = `(${resultsList.length})`;

        if (tbody) {
          const tr = document.createElement("tr");
          tr.innerHTML = `
            <td>${escapeHtml(r.step || '-')}</td>
            <td style="font-weight: 600;">${escapeHtml(r.eos?.toUpperCase())}</td>
            <td>${escapeHtml(r.method)}</td>
            <td style="text-align: right; font-family: var(--font-mono); font-weight: 600;">${r.power_kw ? r.power_kw.toFixed(1) : '-'}</td>
            <td style="text-align: right; font-family: var(--font-mono);">${r.t_out_c ? r.t_out_c.toFixed(1) : '-'}</td>
            <td style="text-align: right; font-family: var(--font-mono);">${r.eff_pct ? `%${r.eff_pct.toFixed(2)}` : '-'}</td>
            <td style="text-align: right; font-family: var(--font-mono); color: var(--color-text-secondary);">${r.duration_ms || 0} ms</td>
            <td style="text-align: center;">
              <span class="badge ${r.status === 'success' ? 'badge-success' : 'badge-danger'}">${escapeHtml(r.status)}</span>
            </td>
          `;
          tbody.appendChild(tr);
        } else {
          render();
        }
      }

      eventSource.onmessage = (event) => {
        try {
          const item = JSON.parse(event.data);
          if (item.type === "progress" && item.data) {
            resultsList.push(item.data);
            completedRuns = resultsList.length;
            progressPct = (completedRuns / totalRuns) * 100;
            updateLiveProgress(item.data);
          } else if (item.type === "completed" || item.type === "cancelled" || item.type === "error") {
            isRunning = false;
            eventSource.close();
            render();
            showToast(item.type === "completed" ? "Shootout analizi tamamlandı!" : "Shootout durduruldu.");
          }
        } catch (_) {}
      };

      eventSource.onerror = () => {
        isRunning = false;
        if (eventSource) eventSource.close();
        render();
      };
    } catch (err) {
      isRunning = false;
      showToast("Shootout başlatılamadı: " + err.message, "danger");
      render();
    }
  }

  async function cancelShootout() {
    if (currentJobId) {
      try {
        await api.post(`/api/v1/jobs/${currentJobId}/cancel`);
      } catch (_) {}
    }
    isRunning = false;
    if (eventSource) eventSource.close();
    showToast("Hesaplama iptal edildi.");
    render();
  }

  render();
}
