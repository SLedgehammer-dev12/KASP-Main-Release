/**
 * KASP Gas Mixture Table Component
 * 19-gas composition manager with live %100 total badge, normalization,
 * smart recommendations, and kij matrix modal trigger.
 */

import { icon } from "../../vendor/icons.js";
import { projectStore, updateGasComponent, recalculateGasTotal, fetchRecommendations } from "../store/projectStore.js";
import { openModal } from "../store/uiStore.js";
import { api } from "../api/client.js";

let gasCatalog = [];

export async function initGasCatalog() {
  try {
    gasCatalog = await api.get("/api/v1/thermo/gases");
  } catch (err) {
    console.error("Gas catalog fetch error:", err);
  }
}

export function renderGasTable(container) {
  let isBuilt = false;
  let debounceTimer = null;

  function update() {
    const proj = projectStore.getState();
    const comp = proj.inputs.gas_comp || {};
    const total = proj.gasTotal;
    const isTotalValid = Math.abs(total - 100.0) < 0.01;

    const totalBadgeClass = isTotalValid ? "badge-success" : (total > 0 ? "badge-warning" : "badge-danger");
    const totalBadgeText = isTotalValid ? `%${total.toFixed(2)} ✓` : `%${total.toFixed(2)} (Fark: ${(100 - total).toFixed(2)})`;

    let activeGasesCount = 0;
    for (const val of Object.values(comp)) {
      if ((parseFloat(val) || 0) > 0) activeGasesCount++;
    }

    if (isBuilt) {
      // 1. Update live total badge
      const totalBadge = container.querySelector("#gas-total-badge");
      if (totalBadge) {
        totalBadge.className = `badge ${totalBadgeClass}`;
        totalBadge.textContent = totalBadgeText;
      }

      // 2. Update kij button counter
      const kijCount = container.querySelector("#kij-active-count");
      if (kijCount) {
        kijCount.textContent = `kij Matrisi (${activeGasesCount})`;
      }

      // 3. Update inputs without stealing focus or interrupting active keystrokes
      container.querySelectorAll(".gas-input").forEach((input) => {
        if (document.activeElement !== input) {
          const gasId = input.getAttribute("data-gas-id");
          const val = comp[gasId] !== undefined ? comp[gasId] : 0;
          const formatted = val > 0 ? String(val) : "";
          if (input.value !== formatted) {
            input.value = formatted;
          }
        }
      });

      // 4. Update recommendation banner
      let recContainer = container.querySelector("#gas-rec-banner");
      if (proj.recommendations) {
        const recHtml = `
          <div style="font-weight: 700; color: var(--color-primary); margin-bottom: 2px;">⚡ ${proj.recommendations.recommended_eos?.toUpperCase()} / ${proj.recommendations.recommended_method}</div>
          <div style="color: var(--color-text-secondary);">${proj.recommendations.reason || ""}</div>
        `;
        if (recContainer) {
          recContainer.innerHTML = recHtml;
          recContainer.style.display = "block";
        }
      } else if (recContainer) {
        recContainer.style.display = "none";
      }
      return;
    }

    // Initial DOM generation
    const rowsHtml = (gasCatalog.length ? gasCatalog : Object.keys(comp).map(id => ({ id, formula: id, name_tr: id }))).map(gas => {
      const val = comp[gas.id] !== undefined ? comp[gas.id] : 0;
      return `
        <tr>
          <td style="font-weight: 600;">${gas.formula || gas.id}</td>
          <td style="color: var(--color-text-secondary);">${gas.name_tr || gas.name || gas.id}</td>
          <td style="text-align: right;">
            <input 
              type="number" 
              step="0.01" 
              min="0" 
              max="100" 
              class="form-input gas-input" 
              data-gas-id="${gas.id}" 
              value="${val > 0 ? val : ''}" 
              placeholder="0.00"
            />
          </td>
        </tr>
      `;
    }).join("");

    container.innerHTML = `
      <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
        <div style="display: flex; align-items: center; gap: 8px;">
          <span style="font-weight: 600; font-size: 11px; color: var(--color-text-secondary);">Karışım Toplamı:</span>
          <span id="gas-total-badge" class="badge ${totalBadgeClass}">${totalBadgeText}</span>
        </div>
        <div style="display: flex; align-items: center; gap: 4px;">
          <button id="btn-normalize-gas" class="btn btn-sm" title="Tüm bileşenleri %100'e orantısal tamamlar">
            ${icon("refreshCw", 12)}
            <span>%100 Yap</span>
          </button>
          <button id="btn-open-kij-matrix" class="btn btn-sm btn-primary" title="N x N İkili Etkileşim Parametre Matrisini Görüntüle ve Düzenle">
            ${icon("grid", 12)}
            <span id="kij-active-count">kij Matrisi (${activeGasesCount})</span>
          </button>
        </div>
      </div>

      <div class="gas-table-container">
        <table class="kasp-table">
          <thead>
            <tr>
              <th style="width: 25%;">Formül</th>
              <th style="width: 50%;">Bileşen Adı</th>
              <th style="width: 25%; text-align: right;">Mol %</th>
            </tr>
          </thead>
          <tbody>
            ${rowsHtml}
          </tbody>
        </table>
      </div>

      <div id="gas-rec-banner" style="padding: 8px; border-radius: var(--radius-md); background: var(--color-primary-bg); font-size: 11px; margin-top: 8px; border: 1px solid var(--color-border); ${proj.recommendations ? '' : 'display: none;'}">
        ${proj.recommendations ? `
          <div style="font-weight: 700; color: var(--color-primary); margin-bottom: 2px;">⚡ ${proj.recommendations.recommended_eos?.toUpperCase()} / ${proj.recommendations.recommended_method}</div>
          <div style="color: var(--color-text-secondary);">${proj.recommendations.reason || ""}</div>
        ` : ''}
      </div>
    `;

    isBuilt = true;

    // Bind inputs with debouncing to prevent UI thrashing during typing
    container.querySelectorAll(".gas-input").forEach(input => {
      input.addEventListener("input", (e) => {
        const gasId = e.target.getAttribute("data-gas-id");
        const val = e.target.value;
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
          updateGasComponent(gasId, val);
        }, 150);
      });
      input.addEventListener("blur", () => {
        clearTimeout(debounceTimer);
        fetchRecommendations();
      });
    });

    const normBtn = container.querySelector("#btn-normalize-gas");
    if (normBtn) {
      normBtn.addEventListener("click", () => {
        const currentComp = projectStore.getState().inputs.gas_comp;
        const currentTotal = Object.values(currentComp).reduce((a, b) => a + (parseFloat(b) || 0), 0);
        if (currentTotal <= 0) return;
        const nextComp = {};
        let sum = 0;
        let maxKey = null;
        let maxVal = -1;
        for (const [k, v] of Object.entries(currentComp)) {
          const num = parseFloat(v) || 0;
          if (num > 0) {
            const normalized = Math.round((num / currentTotal) * 10000) / 100;
            nextComp[k] = normalized;
            sum += normalized;
            if (normalized > maxVal) {
              maxVal = normalized;
              maxKey = k;
            }
          }
        }
        // Rounding discrepancy adjustment to guarantee exact 100.00%
        if (maxKey && Math.abs(sum - 100.0) > 0.0001) {
          const diff = Math.round((100.0 - sum) * 100) / 100;
          nextComp[maxKey] = Math.round((nextComp[maxKey] + diff) * 100) / 100;
        }
        projectStore.setState(s => ({
          inputs: { ...s.inputs, gas_comp: nextComp }
        }));
        recalculateGasTotal();
        fetchRecommendations();
      });
    }

    const kijBtn = container.querySelector("#btn-open-kij-matrix");
    if (kijBtn) {
      kijBtn.addEventListener("click", () => {
        openModal("kij");
      });
    }
  }

  projectStore.subscribe(update);
  update();
}
