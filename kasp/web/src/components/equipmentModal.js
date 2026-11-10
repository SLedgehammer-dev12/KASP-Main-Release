/**
 * KASP Equipment Catalog Management Modal
 * Full CRUD for 146+ Turbines and Compressors database.
 */

import { icon } from "../../vendor/icons.js";
import { closeModal, showToast } from "../store/uiStore.js";
import { authStore, hasPermission } from "../store/authStore.js";
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

function escapeAttr(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

export async function renderEquipmentModal(container) {
  let activeTab = "turbines"; // turbines, compressors
  let turbines = [];
  let compressors = [];
  let searchTerm = "";
  let isShellRendered = false;

  async function loadData() {
    try {
      [turbines, compressors] = await Promise.all([
        api.get("/api/v1/equipment/turbines"),
        api.get("/api/v1/equipment/compressors"),
      ]);
    } catch (err) {
      console.error("Equipment load error:", err);
    }
    renderTableOnly();
  }

  function getFilteredData() {
    const term = searchTerm.toLowerCase();
    const filteredTurbines = turbines.filter(t => 
      (t.manufacturer || "").toLowerCase().includes(term) ||
      (t.model || "").toLowerCase().includes(term)
    );

    const filteredCompressors = compressors.filter(c => 
      (c.manufacturer || "").toLowerCase().includes(term) ||
      (c.model || "").toLowerCase().includes(term)
    );

    return { filteredTurbines, filteredCompressors };
  }

  function renderTableOnly() {
    const tableMount = container.querySelector("#equip-table-mount");
    if (!tableMount) {
      render();
      return;
    }

    const canDelete = hasPermission("delete");
    const { filteredTurbines, filteredCompressors } = getFilteredData();

    // Update counts on buttons
    const turbBtn = container.querySelector("#tab-btn-turbines");
    if (turbBtn) turbBtn.textContent = `Gaz Türbinleri (${turbines.length})`;
    const compBtn = container.querySelector("#tab-btn-compressors");
    if (compBtn) compBtn.textContent = `Kompresörler (${compressors.length})`;

    if (activeTab === "turbines") {
      tableMount.innerHTML = `
        <table class="kasp-table">
          <thead>
            <tr>
              <th>Üretici</th>
              <th>Model</th>
              <th>Tip</th>
              <th style="text-align: right;">ISO Gücü (kW)</th>
              <th style="text-align: right;">Isı Tüketimi (kJ/kWh)</th>
              <th style="text-align: right;">Maks PR</th>
              <th style="text-align: center;">İşlem</th>
            </tr>
          </thead>
          <tbody>
            ${filteredTurbines.map(t => `
              <tr>
                <td style="font-weight: 600;">${escapeHtml(t.manufacturer)}</td>
                <td><b>${escapeHtml(t.model)}</b></td>
                <td>${escapeHtml(t.type || 'Industrial')}</td>
                <td style="text-align: right; font-family: var(--font-mono);">${(t.iso_power_kw || 0).toLocaleString()}</td>
                <td style="text-align: right; font-family: var(--font-mono);">${(t.iso_heat_rate_kj_kwh || 0).toLocaleString()}</td>
                <td style="text-align: right; font-family: var(--font-mono);">${t.max_pressure_ratio || '-'}</td>
                <td style="text-align: center;">
                  ${
                    canDelete
                      ? `<button class="btn btn-sm btn-icon btn-del-turbine" data-id="${t.id}" title="Sil">${icon("trash", 12)}</button>`
                      : "-"
                  }
                </td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      `;
    } else {
      tableMount.innerHTML = `
        <table class="kasp-table">
          <thead>
            <tr>
              <th>Üretici</th>
              <th>Model</th>
              <th style="text-align: right;">Maks PR</th>
              <th style="text-align: right;">Min Debi (kg/s)</th>
              <th style="text-align: right;">Maks Debi (kg/s)</th>
              <th style="text-align: center;">İşlem</th>
            </tr>
          </thead>
          <tbody>
            ${filteredCompressors.map(c => `
              <tr>
                <td style="font-weight: 600;">${escapeHtml(c.manufacturer)}</td>
                <td><b>${escapeHtml(c.model)}</b></td>
                <td style="text-align: right; font-family: var(--font-mono);">${c.max_pressure_ratio}</td>
                <td style="text-align: right; font-family: var(--font-mono);">${c.min_flow_kgs}</td>
                <td style="text-align: right; font-family: var(--font-mono);">${c.max_flow_kgs}</td>
                <td style="text-align: center;">
                  ${
                    canDelete
                      ? `<button class="btn btn-sm btn-icon btn-del-compressor" data-id="${c.id}" title="Sil">${icon("trash", 12)}</button>`
                      : "-"
                  }
                </td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      `;
    }

    bindTableEvents();
  }

  function bindTableEvents() {
    container.querySelectorAll(".btn-del-turbine").forEach(btn => {
      btn.addEventListener("click", async () => {
        const id = btn.getAttribute("data-id");
        if (!confirm("Bu türbini katalogdan silmek istediğinize emin misiniz?")) return;
        try {
          await api.delete(`/api/v1/equipment/turbines/${id}`);
          turbines = turbines.filter(t => t.id != id);
          renderTableOnly();
          showToast("Türbin silindi.");
        } catch (err) {
          showToast("Silme hatası: " + err.message, "danger");
        }
      });
    });

    container.querySelectorAll(".btn-del-compressor").forEach(btn => {
      btn.addEventListener("click", async () => {
        const id = btn.getAttribute("data-id");
        if (!confirm("Bu kompresörü katalogdan silmek istediğinize emin misiniz?")) return;
        try {
          await api.delete(`/api/v1/equipment/compressors/${id}`);
          compressors = compressors.filter(c => c.id != id);
          renderTableOnly();
          showToast("Kompresör silindi.");
        } catch (err) {
          showToast("Silme hatası: " + err.message, "danger");
        }
      });
    });
  }

  function render() {
    const canWrite = hasPermission("write");

    container.innerHTML = `
      <div class="modal-backdrop">
        <div class="modal-dialog modal-xl">
          <div class="modal-header">
            <div class="modal-title">
              ${icon("sliders", 18, "text-primary")}
              <span>Ekipman Veritabanı ve Katalog Yönetimi</span>
            </div>
            <button class="btn btn-sm btn-icon" id="btn-close-equip">${icon("x", 14)}</button>
          </div>

          <div class="modal-body">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px;">
              <div style="display: flex; gap: 8px;">
                <button class="btn btn-sm ${activeTab === 'turbines' ? 'btn-primary' : ''}" id="tab-btn-turbines">
                  Gaz Türbinleri (${turbines.length})
                </button>
                <button class="btn btn-sm ${activeTab === 'compressors' ? 'btn-primary' : ''}" id="tab-btn-compressors">
                  Kompresörler (${compressors.length})
                </button>
              </div>

              <div style="display: flex; align-items: center; gap: 8px;">
                <input 
                  type="text" 
                  id="equip-search" 
                  class="form-input" 
                  style="width: 200px; height: 28px;" 
                  placeholder="Katalogda ara..." 
                  value="${escapeAttr(searchTerm)}"
                />
                ${
                  canWrite
                    ? `
                      <label class="btn btn-sm btn-secondary" style="cursor: pointer; margin: 0;" title="CSV Dosyasından Toplu Türbin İçe Aktar">
                        ${icon("upload", 12)}
                        <span>CSV Yükle</span>
                        <input type="file" id="file-import-turbine-csv" accept=".csv" style="display: none;" />
                      </label>
                      <button class="btn btn-sm btn-primary" id="btn-add-equip">
                        ${icon("plus", 12)}
                        <span>Yeni Ekle</span>
                       </button>`
                    : ""
                }
              </div>
            </div>

            <div id="equip-table-mount" style="max-height: 440px; overflow-y: auto; border: 1px solid var(--color-border); border-radius: var(--radius-md);">
            </div>
          </div>
        </div>
      </div>
    `;

    container.querySelector("#btn-close-equip")?.addEventListener("click", closeModal);
    
    container.querySelector("#tab-btn-turbines")?.addEventListener("click", () => {
      if (activeTab !== "turbines") {
        activeTab = "turbines";
        container.querySelector("#tab-btn-turbines")?.classList.add("btn-primary");
        container.querySelector("#tab-btn-compressors")?.classList.remove("btn-primary");
        renderTableOnly();
      }
    });

    container.querySelector("#tab-btn-compressors")?.addEventListener("click", () => {
      if (activeTab !== "compressors") {
        activeTab = "compressors";
        container.querySelector("#tab-btn-compressors")?.classList.add("btn-primary");
        container.querySelector("#tab-btn-turbines")?.classList.remove("btn-primary");
        renderTableOnly();
      }
    });

    container.querySelector("#equip-search")?.addEventListener("input", (e) => {
      searchTerm = e.target.value;
      renderTableOnly();
    });

    // Add equipment button (simple prompt modal or form)
    container.querySelector("#btn-add-equip")?.addEventListener("click", async () => {
      const model = prompt("Türbin/Kompresör Model Adı:");
      if (!model) return;
      const mfr = prompt("Üretici Firma:") || "Genel";
      if (activeTab === "turbines") {
        const pwr = parseFloat(prompt("ISO Gücü (kW):") || "15000");
        const hr = parseFloat(prompt("Isı Tüketimi (kJ/kWh):") || "9800");
        try {
          await api.post("/api/v1/equipment/turbines", {
            manufacturer: mfr,
            model: model,
            type: "Industrial",
            iso_power_kw: pwr,
            iso_heat_rate_kj_kwh: hr,
          });
          showToast(`'${model}' kataloğa eklendi.`);
          loadData();
        } catch (err) {
          showToast("Ekleme hatası: " + err.message, "danger");
        }
      }
    });

    // CSV Import handler
    container.querySelector("#file-import-turbine-csv")?.addEventListener("change", async (e) => {
      const file = e.target.files[0];
      if (!file) return;
      const formData = new FormData();
      formData.append("file", file);
      try {
        const res = await api.post("/api/v1/equipment/turbines/import-csv", formData);
        showToast(`${res.imported_count} adet türbin başarıyla içe aktarıldı.`);
        await loadData();
      } catch (err) {
        showToast("CSV içe aktarma hatası: " + err.message, "danger");
      }
    });

    renderTableOnly();
  }

  loadData();
}
