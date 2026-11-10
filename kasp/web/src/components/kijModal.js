/**
 * KASP Interactive N x N kij Matrix Editor Modal (ADR-003)
 * Renders symmetric binary interaction parameter grid for the active gas mixture.
 * Displays literature values vs user overrides, supports inline editing,
 * symmetric pair linking, and reset functionality.
 */

import { icon } from "../../vendor/icons.js";
import { projectStore, setCustomKijOverride, clearCustomKijOverrides, fetchKijMatrix } from "../store/projectStore.js";
import { closeModal, showToast } from "../store/uiStore.js";
import { api } from "../api/client.js";

export async function renderKijModal(container) {
  const proj = projectStore.getState();
  const gasComp = proj.inputs.gas_comp || {};
  let currentOverrides = { ...(proj.inputs.custom_kij || {}) };

  // Fetch latest matrix data from server
  let matrixData = null;
  try {
    matrixData = await api.post("/api/v1/thermo/kij-matrix", {
      gas_comp: gasComp,
      custom_kij: currentOverrides,
    });
  } catch (err) {
    container.innerHTML = `
      <div class="modal-backdrop">
        <div class="modal-dialog">
          <div class="modal-header">
            <div class="modal-title">${icon("alertTriangle", 18, "text-danger")} Hata</div>
            <button class="btn btn-sm btn-icon" id="btn-close-kij-err">${icon("x", 14)}</button>
          </div>
          <div class="modal-body">k_ij matrisi oluşturulamadı: ${err.message}</div>
        </div>
      </div>
    `;
    container.querySelector("#btn-close-kij-err")?.addEventListener("click", closeModal);
    return;
  }

  const components = matrixData.components || [];
  const n = components.length;

  if (n < 2) {
    container.innerHTML = `
      <div class="modal-backdrop">
        <div class="modal-dialog">
          <div class="modal-header">
            <div class="modal-title">${icon("grid", 18)} kij İkili Etkileşim Matrisi</div>
            <button class="btn btn-sm btn-icon" id="btn-close-kij-empty">${icon("x", 14)}</button>
          </div>
          <div class="modal-body" style="text-align: center; padding: 32px;">
            <p style="color: var(--color-text-secondary); margin-bottom: 12px;">
              İkili etkileşim matrisi oluşturmak için gaz karışımında en az <b>2 aktif bileşen</b> bulunmalıdır.
            </p>
            <p style="font-size: 11px; color: var(--color-text-muted);">
              Şu anki aktif bileşen sayısı: ${n}
            </p>
          </div>
          <div class="modal-footer">
            <button class="btn btn-primary" id="btn-close-kij-ok">Tamam</button>
          </div>
        </div>
      </div>
    `;
    container.querySelector("#btn-close-kij-empty")?.addEventListener("click", closeModal);
    container.querySelector("#btn-close-kij-ok")?.addEventListener("click", closeModal);
    return;
  }

  // Generate Table HTML
  let tableHeaderHtml = `<tr><th>kij</th>` + components.map(c => `<th>${c}</th>`).join("") + `</tr>`;
  let tableRowsHtml = "";

  for (let i = 0; i < n; i++) {
    const ci = components[i];
    let rowCells = `<th>${ci}</th>`;
    for (let j = 0; j < n; j++) {
      const cj = components[j];
      const val = matrixData.matrix[i][j];
      const src = matrixData.sources[i][j];
      const isDiagonal = i === j;
      const isOverride = src === "user_override";

      if (isDiagonal) {
        rowCells += `<td class="kij-cell-diagonal">0.000</td>`;
      } else {
        const cellClass = isOverride ? "kij-cell-override" : "";
        const titleText = isOverride ? "Kullanıcı Tarafından Belirlenmiş Değer" : `Kaynak: ${src}`;
        rowCells += `
          <td class="${cellClass}" title="${titleText}">
            <input 
              type="number" 
              step="0.001" 
              class="kij-cell-input" 
              data-pair="${ci}:${cj}" 
              data-row="${i}" 
              data-col="${j}" 
              value="${val.toFixed(4)}"
            />
          </td>
        `;
      }
    }
    tableRowsHtml += `<tr>${rowCells}</tr>`;
  }

  container.innerHTML = `
    <div class="modal-backdrop">
      <div class="modal-dialog modal-lg">
        <div class="modal-header">
          <div class="modal-title">
            ${icon("grid", 18, "text-primary")}
            <span>İkili Etkileşim Katsayısı Matrisi (${n} x ${n} kij)</span>
          </div>
          <button class="btn btn-sm btn-icon" id="btn-modal-close-x">${icon("x", 14)}</button>
        </div>

        <div class="modal-body">
          <div style="font-size: 11px; color: var(--color-text-secondary); margin-bottom: 12px; line-height: 1.5;">
            Peng-Robinson ve SRK gibi kübik durum denklemleri için bileşen çiftleri arasındaki <b>k_ij</b> parametreleri. 
            Mavi renkli hücreler kullanıcı tanımlı (override) değerleri gösterir. Matris simetrik (k_ij = k_ji) olarak otomatik eşitlenir.
          </div>

          <div style="overflow-x: auto; max-height: 380px; border: 1px solid var(--color-border); border-radius: var(--radius-md);">
            <table class="kij-matrix-table" style="width: 100%;">
              <thead>${tableHeaderHtml}</thead>
              <tbody>${tableRowsHtml}</tbody>
            </table>
          </div>

          ${
            matrixData.risky_missing_pairs && matrixData.risky_missing_pairs.length > 0
              ? `<div style="margin-top: 12px; padding: 8px 12px; border-radius: var(--radius-md); background: var(--color-warning-bg); color: var(--color-warning-text); border: 1px solid var(--color-warning-border); font-size: 11px;">
                  ⚠️ <b>Dikkat:</b> Aşağıdaki kutupsal/asit gaz çiftleri için literatür değeri bulunamadı ve 0.0 alındı. Karışım davranışını iyileştirmek için override önerilir: 
                  ${matrixData.risky_missing_pairs.join(", ")}
                 </div>`
              : ""
          }
        </div>

        <div class="modal-footer">
          <button class="btn" id="btn-reset-overrides" title="Tüm kullanıcı override'larını silip literatür değerlerine döner">
            ${icon("refreshCw", 12)}
            <span>Varsayılanlara Sıfırla</span>
          </button>
          <div style="flex: 1;"></div>
          <button class="btn" id="btn-cancel-kij">İptal</button>
          <button class="btn btn-primary" id="btn-save-kij">
            ${icon("check", 14)}
            <span>Değişiklikleri Kaydet</span>
          </button>
        </div>
      </div>
    </div>
  `;

  // Dynamic symmetric cell update
  const inputs = container.querySelectorAll(".kij-cell-input");
  inputs.forEach(input => {
    input.addEventListener("input", (e) => {
      const row = e.target.getAttribute("data-row");
      const col = e.target.getAttribute("data-col");
      const val = parseFloat(e.target.value) || 0;
      const ci = components[row];
      const cj = components[col];

      // Update local state symmetrically
      const pairKey1 = `${ci}:${cj}`;
      const pairKey2 = `${cj}:${ci}`;
      currentOverrides[pairKey1] = val;
      currentOverrides[pairKey2] = val;

      // Update symmetric counterpart input
      const counterpart = container.querySelector(`.kij-cell-input[data-row="${col}"][data-col="${row}"]`);
      if (counterpart) {
        counterpart.value = e.target.value;
      }
      e.target.parentElement.classList.add("kij-cell-override");
      if (counterpart) counterpart.parentElement.classList.add("kij-cell-override");
    });
  });

  // Reset button
  container.querySelector("#btn-reset-overrides")?.addEventListener("click", () => {
    clearCustomKijOverrides();
    showToast("kij override değerleri sıfırlandı.");
    closeModal();
  });

  // Cancel button
  container.querySelector("#btn-cancel-kij")?.addEventListener("click", closeModal);
  container.querySelector("#btn-modal-close-x")?.addEventListener("click", closeModal);

  // Save button
  container.querySelector("#btn-save-kij")?.addEventListener("click", () => {
    for (const [pair, val] of Object.entries(currentOverrides)) {
      setCustomKijOverride(pair, val);
    }
    showToast("kij parametreleri güncellendi.");
    closeModal();
  });
}
