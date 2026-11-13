/**
 * KASP Ergonomic Gas Mixture Builder Component
 * Dynamic active-component table with categorized <optgroup> selector,
 * quick-add common gas chips, one-click row balance ("Kalan") & remove,
 * proportional %100 normalization, smart recommendations, and kij matrix trigger.
 */

import { icon } from "../../vendor/icons.js";
import {
  projectStore,
  updateGasComponent,
  addGasComponent,
  removeGasComponent,
  balanceGasComponent,
  recalculateGasTotal,
  fetchRecommendations,
  invalidateAirCoolerCache,
  normalizeGasKey,
  escapeHtml,
} from "../store/projectStore.js";
import { uiStore, openModal } from "../store/uiStore.js";
import { t } from "../i18n/locales.js";
import { api } from "../api/client.js";

const FALLBACK_GAS_CATALOG = [
  { id: "METHANE", formula: "CH4", name_tr: "Metan", name_en: "Methane", mw: 16.043, category: "hydrocarbon" },
  { id: "ETHANE", formula: "C2H6", name_tr: "Etan", name_en: "Ethane", mw: 30.069, category: "hydrocarbon" },
  { id: "PROPANE", formula: "C3H8", name_tr: "Propan", name_en: "Propane", mw: 44.096, category: "hydrocarbon" },
  { id: "ISOBUTANE", formula: "i-C4H10", name_tr: "İzobütan", name_en: "Isobutane", mw: 58.123, category: "hydrocarbon" },
  { id: "BUTANE", formula: "n-C4H10", name_tr: "n-Bütan", name_en: "n-Butane", mw: 58.123, category: "hydrocarbon" },
  { id: "ISOPENTANE", formula: "i-C5H12", name_tr: "İzopentan", name_en: "Isopentane", mw: 72.150, category: "hydrocarbon" },
  { id: "PENTANE", formula: "n-C5H12", name_tr: "n-Pentan", name_en: "n-Pentane", mw: 72.150, category: "hydrocarbon" },
  { id: "HEXANE", formula: "C6H14", name_tr: "Hekzan", name_en: "Hexane", mw: 86.177, category: "hydrocarbon" },
  { id: "HEPTANE", formula: "C7H16", name_tr: "Heptan", name_en: "Heptane", mw: 100.204, category: "hydrocarbon" },
  { id: "OCTANE", formula: "C8H18", name_tr: "Oktan", name_en: "Octane", mw: 114.231, category: "hydrocarbon" },
  { id: "NONANE", formula: "C9H20", name_tr: "Nonan", name_en: "Nonane", mw: 128.258, category: "hydrocarbon" },
  { id: "DECANE", formula: "C10H22", name_tr: "Dekan", name_en: "Decane", mw: 142.285, category: "hydrocarbon" },
  { id: "CARBONDIOXIDE", formula: "CO2", name_tr: "Karbondioksit", name_en: "Carbon Dioxide", mw: 44.010, category: "acid_polar" },
  { id: "HYDROGENSULFIDE", formula: "H2S", name_tr: "Hidrojen Sülfür", name_en: "Hydrogen Sulfide", mw: 34.082, category: "acid_polar" },
  { id: "WATER", formula: "H2O", name_tr: "Su Buharı", name_en: "Water Vapor", mw: 18.015, category: "acid_polar" },
  { id: "NITROGEN", formula: "N2", name_tr: "Azot", name_en: "Nitrogen", mw: 28.014, category: "inert_other" },
  { id: "HYDROGEN", formula: "H2", name_tr: "Hidrojen", name_en: "Hydrogen", mw: 2.016, category: "inert_other" },
  { id: "OXYGEN", formula: "O2", name_tr: "Oksijen", name_en: "Oxygen", mw: 31.999, category: "inert_other" },
  { id: "ARGON", formula: "Ar", name_tr: "Argon", name_en: "Argon", mw: 39.948, category: "inert_other" },
  { id: "HELIUM", formula: "He", name_tr: "Helyum", name_en: "Helium", mw: 4.003, category: "inert_other" },
  { id: "NEON", formula: "Ne", name_tr: "Neon", name_en: "Neon", mw: 20.180, category: "inert_other" },
  { id: "KRYPTON", formula: "Kr", name_tr: "Kripton", name_en: "Krypton", mw: 83.798, category: "inert_other" },
  { id: "XENON", formula: "Xe", name_tr: "Ksenon", name_en: "Xenon", mw: 131.293, category: "inert_other" },
  { id: "AIR", formula: "Air", name_tr: "Kuru Hava", name_en: "Dry Air", mw: 28.966, category: "inert_other" },
];

const QUICK_ADD_CANDIDATE_IDS = [
  "METHANE",
  "ETHANE",
  "PROPANE",
  "ISOBUTANE",
  "BUTANE",
  "CARBONDIOXIDE",
  "NITROGEN",
  "HYDROGEN",
  "HYDROGENSULFIDE",
  "WATER",
  "HELIUM",
  "ARGON",
];

const CATEGORY_ORDER = [
  { key: "hydrocarbon", labelKey: "gas_cat_hydrocarbon" },
  { key: "acid_polar", labelKey: "gas_cat_acid_polar" },
  { key: "inert_other", labelKey: "gas_cat_inert_other" },
];

const GAS_I18N_FALLBACK = {
  tr: {
    gas_mix_total: "Karışım Toplamı:",
    gas_diff: "Fark",
    gas_normalize_short: "%100 Yap",
    gas_kij_btn: "kij Matrisi",
    gas_table_caption: "Aktif gaz karışımı bileşenleri ve mol yüzdeleri",
    gas_col_component: "Aktif Bileşen",
    gas_col_mol_pct: "Mol %",
    gas_col_actions: "İşlem",
    gas_add_label: "Karışıma Gaz Bileşeni Ekle",
    gas_add_btn: "Ekle",
    gas_all_added: "Tüm katalog bileşenleri eklendi",
    gas_quick_add: "Hızlı Ekle:",
    gas_cat_hydrocarbon: "Hidrokarbonlar (C1–C10)",
    gas_cat_acid_polar: "Asit & Polar Gazlar",
    gas_cat_inert_other: "İnert & Diğer Gazlar",
    gas_balance_btn: "Kalan",
    gas_remove_btn: "Kaldır",
    gas_empty_hint: "Aktif bileşen kalmadı. Yukarıdaki listeden veya hızlı ekle düğmelerinden gaz ekleyin.",
    gas_active_summary: "aktif gaz",
  },
  en: {
    gas_mix_total: "Mixture Total:",
    gas_diff: "Diff",
    gas_normalize_short: "Make 100%",
    gas_kij_btn: "kij Matrix",
    gas_table_caption: "Active gas mixture components and mole percentages",
    gas_col_component: "Active Component",
    gas_col_mol_pct: "Mole %",
    gas_col_actions: "Actions",
    gas_add_label: "Add Gas Component to Mixture",
    gas_add_btn: "Add",
    gas_all_added: "All catalog components added",
    gas_quick_add: "Quick Add:",
    gas_cat_hydrocarbon: "Hydrocarbons (C1–C10)",
    gas_cat_acid_polar: "Acid & Polar Gases",
    gas_cat_inert_other: "Inert & Other Gases",
    gas_balance_btn: "Balance",
    gas_remove_btn: "Remove",
    gas_empty_hint: "No active components left. Select and add a gas from the list or quick-add chips above.",
    gas_active_summary: "active gases",
  },
};

function trGas(key, lang = "tr") {
  const val = t(key, lang);
  if (val && val !== key) return val;
  const dict = GAS_I18N_FALLBACK[lang] || GAS_I18N_FALLBACK.tr;
  return dict[key] || key;
}

let gasCatalog = [...FALLBACK_GAS_CATALOG];
let catalogVersion = 0;
const catalogSubscribers = new Set();

export async function initGasCatalog() {
  try {
    const fetched = await api.get("/api/v1/thermo/gases");
    if (Array.isArray(fetched) && fetched.length > 0) {
      gasCatalog = fetched;
      catalogVersion += 1;
      catalogSubscribers.forEach((fn) => fn());
    }
  } catch (err) {
    console.error("Gas catalog fetch error:", err);
  }
}

function resolveCatalogMap() {
  const map = new Map();
  for (const item of FALLBACK_GAS_CATALOG) {
    map.set(item.id, item);
  }
  for (const item of gasCatalog) {
    if (item && item.id) {
      const prev = map.get(item.id) || {};
      map.set(item.id, { ...prev, ...item });
    }
  }
  return map;
}

function getGasDisplayName(gas, lang) {
  if (lang === "en") {
    return gas.name_en || gas.name || gas.name_tr || gas.id;
  }
  return gas.name_tr || gas.name || gas.name_en || gas.id;
}

function buildRecommendationHtml(rec) {
  if (!rec || (!rec.recommended_eos && !rec.recommended_method)) {
    return "";
  }
  const recEos = escapeHtml(String(rec.recommended_eos || "").toUpperCase());
  const recMethod = escapeHtml(String(rec.recommended_method || ""));
  const recReason = escapeHtml(String(rec.reason || ""));
  return `
    <div style="font-weight: 700; color: var(--color-primary); margin-bottom: 2px;">⚡ ${recEos} / ${recMethod}</div>
    <div style="color: var(--color-text-secondary);">${recReason}</div>
  `;
}

export function renderGasTable(container) {
  let isBuilt = false;
  let wasConnected = container.isConnected;
  let lastSignature = "";
  let debounceTimer = null;
  let pendingFocusSelector = null;
  let selectTextOnFocus = false;

  // Track user-pinned components so newly added 0% rows stay editable until explicitly removed
  const pinnedGasIds = new Set();
  const initialComp = projectStore.getState().inputs.gas_comp || {};
  for (const [rawKey, rawVal] of Object.entries(initialComp)) {
    if ((parseFloat(rawVal) || 0) > 0) {
      pinnedGasIds.add(normalizeGasKey(rawKey));
    }
  }

  let unsubProject = null;
  let unsubUi = null;

  function cleanupIfDetached() {
    if (container.isConnected) {
      wasConnected = true;
      return false;
    }
    if (wasConnected) {
      clearTimeout(debounceTimer);
      if (unsubProject) unsubProject();
      if (unsubUi) unsubUi();
      catalogSubscribers.delete(update);
      return true;
    }
    return false;
  }

  function computeActiveGasIds(comp) {
    const presentKeys = new Set();
    const orderedIds = [];
    for (const [rawKey, rawVal] of Object.entries(comp)) {
      const canonical = normalizeGasKey(rawKey);
      if (!canonical || presentKeys.has(canonical)) continue;
      presentKeys.add(canonical);
      const val = parseFloat(rawVal) || 0;
      if (val > 0 || pinnedGasIds.has(canonical)) {
        pinnedGasIds.add(canonical);
        orderedIds.push(canonical);
      }
    }
    // Prune any pinned ID that was deleted externally (e.g., preset switch or .kasp import)
    for (const id of Array.from(pinnedGasIds)) {
      if (!presentKeys.has(id)) {
        pinnedGasIds.delete(id);
      }
    }
    return orderedIds;
  }

  function formatTotalBadgeText(total, isTotalValid, lang) {
    if (isTotalValid) {
      return `%${total.toFixed(2)} ✓`;
    }
    const diff = (100 - total).toFixed(2);
    const sign = 100 - total > 0 ? "+" : "";
    return `%${total.toFixed(2)} (${trGas("gas_diff", lang)}: ${sign}${diff})`;
  }

  function handleAddComponent(targetGasId) {
    const canonical = normalizeGasKey(targetGasId);
    if (!canonical) return;
    pinnedGasIds.add(canonical);
    pendingFocusSelector = `#gas-pct-${canonical}`;
    selectTextOnFocus = true;
    addGasComponent(canonical);
  }

  function handleRemoveComponent(targetGasId, orderedIds) {
    const canonical = normalizeGasKey(targetGasId);
    if (!canonical) return;
    const idx = orderedIds.indexOf(canonical);
    let nextFocusId = null;
    if (idx >= 0 && orderedIds.length > 1) {
      nextFocusId = orderedIds[idx + 1] || orderedIds[idx - 1];
    }
    pinnedGasIds.delete(canonical);
    pendingFocusSelector = nextFocusId ? `#gas-pct-${nextFocusId}` : "#gas-add-select";
    selectTextOnFocus = false;
    removeGasComponent(canonical);
  }

  function update() {
    if (cleanupIfDetached()) return;

    const proj = projectStore.getState();
    const ui = uiStore.getState();
    const lang = ui.lang || "tr";
    const comp = proj.inputs.gas_comp || {};
    const total = proj.gasTotal;
    const isTotalValid = Math.abs(total - 100.0) < 0.01;

    const totalBadgeClass = isTotalValid
      ? "badge-success"
      : total > 0
        ? "badge-warning"
        : "badge-danger";
    const totalBadgeText = formatTotalBadgeText(total, isTotalValid, lang);

    const activeGasIds = computeActiveGasIds(comp);
    let positiveGasesCount = 0;
    for (const val of Object.values(comp)) {
      if ((parseFloat(val) || 0) > 0) positiveGasesCount++;
    }

    const signature = `${lang}|${catalogVersion}|${activeGasIds.join(",")}`;

    if (isBuilt && signature === lastSignature) {
      // Selective in-place DOM updates without interrupting active typing or stealing focus
      const totalBadge = container.querySelector("#gas-total-badge");
      if (totalBadge) {
        totalBadge.className = `badge ${totalBadgeClass}`;
        totalBadge.textContent = totalBadgeText;
      }

      const kijCount = container.querySelector("#kij-active-count");
      if (kijCount) {
        kijCount.textContent = `${trGas("gas_kij_btn", lang)} (${positiveGasesCount})`;
      }

      container.querySelectorAll(".gas-input").forEach((input) => {
        if (document.activeElement !== input) {
          const gasId = input.getAttribute("data-gas-id");
          const rawVal = comp[gasId] !== undefined ? parseFloat(comp[gasId]) : 0;
          const formatted = Number.isFinite(rawVal) && rawVal > 0 ? String(rawVal) : "0";
          if (input.value !== formatted) {
            input.value = formatted;
          }
        }
      });

      const recContainer = container.querySelector("#gas-rec-banner");
      if (recContainer) {
        const recHtml = buildRecommendationHtml(proj.recommendations);
        if (recHtml) {
          recContainer.innerHTML = recHtml;
          recContainer.style.display = "block";
        } else {
          recContainer.innerHTML = "";
          recContainer.style.display = "none";
        }
      }
      return;
    }

    lastSignature = signature;
    const catalogMap = resolveCatalogMap();
    const activeSet = new Set(activeGasIds);

    // Build categorized <optgroup> options for non-active gases
    const availableByCategory = new Map(CATEGORY_ORDER.map((c) => [c.key, []]));
    for (const gas of catalogMap.values()) {
      if (activeSet.has(gas.id)) continue;
      const catKey = availableByCategory.has(gas.category) ? gas.category : "inert_other";
      availableByCategory.get(catKey).push(gas);
    }

    let totalAvailableCount = 0;
    const optgroupsHtml = CATEGORY_ORDER.map(({ key, labelKey }) => {
      const items = availableByCategory.get(key) || [];
      if (items.length === 0) return "";
      totalAvailableCount += items.length;
      const optionsHtml = items
        .map((gas) => {
          const gName = getGasDisplayName(gas, lang);
          const mwStr = Number.isFinite(Number(gas.mw)) ? ` (${Number(gas.mw).toFixed(2)} g/mol)` : "";
          return `<option value="${escapeHtml(gas.id)}">${escapeHtml(gas.formula || gas.id)} — ${escapeHtml(gName)}${escapeHtml(mwStr)}</option>`;
        })
        .join("");
      return `<optgroup label="${escapeHtml(trGas(labelKey, lang))}">${optionsHtml}</optgroup>`;
    }).join("");

    // Quick-add chips for common gases not currently active (max 7 pills for clean single/two-row ergonomics)
    const quickChips = QUICK_ADD_CANDIDATE_IDS.filter((id) => !activeSet.has(id) && catalogMap.has(id))
      .slice(0, 7)
      .map((id) => {
        const gas = catalogMap.get(id);
        const gName = getGasDisplayName(gas, lang);
        return `
          <button type="button" class="gas-chip-btn" data-quick-gas="${escapeHtml(gas.id)}">
            <span>+ ${escapeHtml(gas.formula || gas.id)}</span>
            <span class="visually-hidden"> (${escapeHtml(gName)})</span>
          </button>
        `;
      })
      .join("");

    // Active rows HTML
    const rowsHtml =
      activeGasIds.length > 0
        ? activeGasIds
            .map((gasId) => {
              const gas = catalogMap.get(gasId) || {
                id: gasId,
                formula: gasId,
                name_tr: gasId,
                name_en: gasId,
                mw: null,
              };
              const gName = getGasDisplayName(gas, lang);
              const rawVal = comp[gasId] !== undefined ? parseFloat(comp[gasId]) : 0;
              const inputVal = Number.isFinite(rawVal) && rawVal >= 0 ? String(rawVal) : "0";
              const mwLabel = Number.isFinite(Number(gas.mw)) ? `${Number(gas.mw).toFixed(2)} g/mol` : "";
              const inputDomId = `gas-pct-${gas.id}`;

              return `
                <tr data-active-gas-row="${escapeHtml(gas.id)}">
                  <th scope="row" class="gas-comp-cell">
                    <div class="gas-comp-main">
                      <span class="gas-formula-pill">${escapeHtml(gas.formula || gas.id)}</span>
                      <div class="gas-comp-meta">
                        <span class="gas-comp-name">${escapeHtml(gName)}</span>
                        ${mwLabel ? `<span class="gas-comp-mw">${escapeHtml(mwLabel)}</span>` : ""}
                      </div>
                    </div>
                  </th>
                  <td style="text-align: right; vertical-align: middle;">
                    <label class="visually-hidden" for="${escapeHtml(inputDomId)}">${escapeHtml(gName)} (${escapeHtml(trGas("gas_col_mol_pct", lang))})</label>
                    <input
                      id="${escapeHtml(inputDomId)}"
                      name="gas_pct_${escapeHtml(gas.id)}"
                      type="number"
                      inputmode="decimal"
                      step="0.01"
                      min="0"
                      max="100"
                      class="form-input gas-input"
                      data-gas-id="${escapeHtml(gas.id)}"
                      value="${escapeHtml(inputVal)}"
                    />
                  </td>
                  <td style="text-align: right; vertical-align: middle; white-space: nowrap;">
                    <div class="gas-actions-group">
                      <button type="button" class="btn btn-sm gas-row-btn gas-balance-btn" data-balance-gas="${escapeHtml(gas.id)}">
                        <span>${escapeHtml(trGas("gas_balance_btn", lang))}</span>
                        <span class="visually-hidden"> ${escapeHtml(gName)}</span>
                      </button>
                      <button type="button" class="btn btn-sm gas-row-btn gas-remove-btn" data-remove-gas="${escapeHtml(gas.id)}">
                        <span aria-hidden="true">${icon("x", 12)}</span>
                        <span class="visually-hidden">${escapeHtml(trGas("gas_remove_btn", lang))} ${escapeHtml(gName)}</span>
                      </button>
                    </div>
                  </td>
                </tr>
              `;
            })
            .join("")
        : `
          <tr>
            <td colspan="3" style="text-align: center; padding: 14px 10px; color: var(--color-text-secondary); font-size: 11px;">
              ${escapeHtml(trGas("gas_empty_hint", lang))}
            </td>
          </tr>
        `;

    const recHtml = buildRecommendationHtml(proj.recommendations);

    container.innerHTML = `
      <div class="gas-builder-toolbar">
        <div style="display: flex; align-items: center; gap: 6px;">
          <span style="font-weight: 600; font-size: 11px; color: var(--color-text-secondary);">${escapeHtml(trGas("gas_mix_total", lang))}</span>
          <span id="gas-total-badge" role="status" aria-live="polite" class="badge ${totalBadgeClass}">${escapeHtml(totalBadgeText)}</span>
        </div>
        <div style="display: flex; align-items: center; gap: 4px;">
          <button type="button" id="btn-gas-copy" class="btn btn-sm" title="Gaz Kompozisyonunu Panoya Kopyala">
            <span aria-hidden="true">${icon("copy", 12)}</span>
          </button>
          <button type="button" id="btn-normalize-gas" class="btn btn-sm">
            <span aria-hidden="true">${icon("refreshCw", 12)}</span>
            <span>${escapeHtml(trGas("gas_normalize_short", lang))}</span>
          </button>
          <button type="button" id="btn-open-kij-matrix" class="btn btn-sm btn-primary">
            <span aria-hidden="true">${icon("grid", 12)}</span>
            <span id="kij-active-count">${escapeHtml(trGas("gas_kij_btn", lang))} (${positiveGasesCount})</span>
          </button>
        </div>
      </div>

      <div class="gas-adder-box">
        <label class="form-label" for="gas-add-select" style="margin-bottom: 0;">
          <span>${escapeHtml(trGas("gas_add_label", lang))}</span>
          <span style="font-weight: 500; font-size: 10px; color: var(--color-text-secondary);">${activeGasIds.length} ${escapeHtml(trGas("gas_active_summary", lang))}</span>
        </label>
        <div class="gas-adder-row">
          <select
            id="gas-add-select"
            name="gas_add_component"
            class="form-select gas-add-select"
            ${totalAvailableCount === 0 ? "disabled" : ""}
          >
            ${
              totalAvailableCount > 0
                ? optgroupsHtml
                : `<option value="">${escapeHtml(trGas("gas_all_added", lang))}</option>`
            }
          </select>
          <button
            type="button"
            id="btn-add-gas"
            class="btn btn-sm btn-primary gas-add-btn"
            ${totalAvailableCount === 0 ? "disabled" : ""}
          >
            <span aria-hidden="true">${icon("plus", 12)}</span>
            <span>${escapeHtml(trGas("gas_add_btn", lang))}</span>
          </button>
        </div>
        ${
          quickChips
            ? `
            <div class="gas-chips-row">
              <span class="gas-chips-label">${escapeHtml(trGas("gas_quick_add", lang))}</span>
              ${quickChips}
            </div>
          `
            : ""
        }
      </div>

      <div class="gas-table-container">
        <table class="kasp-table gas-active-table">
          <caption class="visually-hidden">${escapeHtml(trGas("gas_table_caption", lang))}</caption>
          <thead>
            <tr>
              <th scope="col" style="width: 48%;">${escapeHtml(trGas("gas_col_component", lang))}</th>
              <th scope="col" style="width: 24%; text-align: right;">${escapeHtml(trGas("gas_col_mol_pct", lang))}</th>
              <th scope="col" style="width: 28%; text-align: right;">${escapeHtml(trGas("gas_col_actions", lang))}</th>
            </tr>
          </thead>
          <tbody>
            ${rowsHtml}
          </tbody>
        </table>
      </div>

      <div id="gas-rec-banner" style="padding: 8px; border-radius: var(--radius-md); background: var(--color-primary-bg); font-size: 11px; margin-top: 6px; border: 1px solid var(--color-border); ${recHtml ? "" : "display: none;"}">
        ${recHtml}
      </div>
    `;

    isBuilt = true;

    // Bind percentage inputs with debounce so typing is smooth and responsive
    container.querySelectorAll(".gas-input").forEach((input) => {
      input.addEventListener("input", (e) => {
        const gasId = e.target.getAttribute("data-gas-id");
        const val = e.target.value;
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
          updateGasComponent(gasId, val);
        }, 120);
      });
      input.addEventListener("blur", (e) => {
        clearTimeout(debounceTimer);
        const gasId = e.target.getAttribute("data-gas-id");
        updateGasComponent(gasId, e.target.value);
        fetchRecommendations();
      });
    });

    // Bind explicit "+ Ekle" button (does NOT auto-submit on <select> change)
    const addBtn = container.querySelector("#btn-add-gas");
    const addSelect = container.querySelector("#gas-add-select");
    if (addBtn && addSelect) {
      addBtn.addEventListener("click", () => {
        if (addSelect.value) {
          handleAddComponent(addSelect.value);
        }
      });
    }

    // Bind quick-add chips
    container.querySelectorAll("[data-quick-gas]").forEach((chip) => {
      chip.addEventListener("click", () => {
        const gid = chip.getAttribute("data-quick-gas");
        if (gid) {
          handleAddComponent(gid);
        }
      });
    });

    // Bind per-row "Kalan" (Balance to 100%) buttons
    container.querySelectorAll("[data-balance-gas]").forEach((btn) => {
      btn.addEventListener("click", () => {
        clearTimeout(debounceTimer);
        const gid = btn.getAttribute("data-balance-gas");
        if (gid) {
          balanceGasComponent(gid);
        }
      });
    });

    // Bind per-row Remove buttons
    container.querySelectorAll("[data-remove-gas]").forEach((btn) => {
      btn.addEventListener("click", () => {
        clearTimeout(debounceTimer);
        const gid = btn.getAttribute("data-remove-gas");
        if (gid) {
          handleRemoveComponent(gid, activeGasIds);
        }
      });
    });

    // Bind Copy Gas Composition button
    container.querySelector("#btn-gas-copy")?.addEventListener("click", async () => {
      const gasComp = projectStore.getState().inputs?.gas_comp || {};
      const lines = Object.entries(gasComp)
        .filter(([, v]) => Number(v) > 0)
        .map(([k, v]) => `${k}: ${Number(v).toFixed(2)}%`);
      const text = lines.join("\n");
      try {
        if (navigator.clipboard?.writeText) await navigator.clipboard.writeText(text);
        showToast("Gaz kompozisyonu panoya kopyalandı.", "success");
      } catch (_) {}
    });

    // Bind %100 Normalize button
    const normBtn = container.querySelector("#btn-normalize-gas");
    if (normBtn) {
      normBtn.addEventListener("click", () => {
        clearTimeout(debounceTimer);
        const currentComp = projectStore.getState().inputs.gas_comp || {};
        const currentTotal = Object.values(currentComp).reduce((a, b) => a + (parseFloat(b) || 0), 0);
        if (currentTotal <= 0) return;
        const nextComp = {};
        let sum = 0;
        let maxKey = null;
        let maxVal = -1;
        for (const [k, v] of Object.entries(currentComp)) {
          const canonical = normalizeGasKey(k);
          const num = parseFloat(v) || 0;
          if (num > 0) {
            const normalized = Math.round((num / currentTotal) * 10000) / 100;
            nextComp[canonical] = normalized;
            sum += normalized;
            if (normalized > maxVal) {
              maxVal = normalized;
              maxKey = canonical;
            }
          }
        }
        if (maxKey && Math.abs(sum - 100.0) > 0.0001) {
          const diff = Math.round((100.0 - sum) * 100) / 100;
          nextComp[maxKey] = Math.round((nextComp[maxKey] + diff) * 100) / 100;
        }
        pinnedGasIds.clear();
        for (const k of Object.keys(nextComp)) {
          pinnedGasIds.add(k);
        }
        projectStore.setState((s) => ({
          inputs: { ...s.inputs, gas_comp: nextComp },
        }));
        // A changed composition invalidates the cached air-cooler sizing.
        invalidateAirCoolerCache();
        recalculateGasTotal();
        fetchRecommendations();
      });
    }

    // Bind kij Matrix Modal button
    const kijBtn = container.querySelector("#btn-open-kij-matrix");
    if (kijBtn) {
      kijBtn.addEventListener("click", () => {
        openModal("kij");
      });
    }

    // Manage focus predictably after adding or removing a row
    if (pendingFocusTargetExists(container, pendingFocusSelector)) {
      const targetEl = container.querySelector(pendingFocusSelector);
      const shouldSelect = selectTextOnFocus;
      pendingFocusSelector = null;
      selectTextOnFocus = false;
      targetEl.focus();
      if (shouldSelect && typeof targetEl.select === "function") {
        targetEl.select();
      }
    } else {
      pendingFocusSelector = null;
      selectTextOnFocus = false;
    }
  }

  unsubProject = projectStore.subscribe(update);
  unsubUi = uiStore.subscribe(update);
  catalogSubscribers.add(update);
  update();
}

function pendingFocusTargetExists(container, selector) {
  if (!selector) return false;
  try {
    return Boolean(container.querySelector(selector));
  } catch (_) {
    return false;
  }
}
