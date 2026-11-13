/**
 * KASP Header Component
 */

import { icon } from "../../vendor/icons.js";
import { uiStore, setTheme, setLanguage, openModal, showToast } from "../store/uiStore.js";
import { authStore, logoutUser } from "../store/authStore.js";
import {
  projectStore,
  updateInput,
  hydrateProjectSnapshot,
  markProjectSaved,
} from "../store/projectStore.js";
import { t } from "../i18n/locales.js";
import { api } from "../api/client.js";
import { updateStore } from "../store/updateStore.js";

function escapeAttr(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

export function renderHeader(container) {
  function update() {
    const ui = uiStore.getState();
    const auth = authStore.getState();
    const proj = projectStore.getState();
    const upd = updateStore.getState();
    const activeDl = (upd.downloads || []).find((d) => d.status === "downloading");

    container.innerHTML = `
      <div class="kasp-header-left">
        <div class="kasp-brand">
          ${icon("activity", 20, "text-primary")}
          <span>${t("app_title", ui.lang)}</span>
          <span class="kasp-brand-badge">v4.1 Pro</span>
        </div>
        <input 
          type="text" 
          id="project-title-input" 
          class="kasp-project-title-input" 
          value="${escapeAttr(proj.inputs.project_name || 'Yeni Proje')}" 
          title="Proje Adı"
        />
        <span
          id="unsaved-indicator"
          class="badge"
          title="${t("unsaved_changes", ui.lang)}"
          style="display: ${proj.hasUnsavedChanges ? "inline-flex" : "none"}; align-items: center; gap: 4px; padding: 2px 8px; border-radius: 999px; font-size: 11px; font-weight: 600; background: var(--warning-bg, rgba(245, 158, 11, 0.16)); color: var(--warning, #f59e0b); border: 1px solid rgba(245, 158, 11, 0.4); white-space: nowrap;"
        >
          ● ${t("unsaved_changes", ui.lang)}
        </span>
      </div>

      <div class="kasp-header-actions">
        <!-- Project Actions -->
        <button id="btn-save-project" class="btn btn-sm ${proj.hasUnsavedChanges ? 'btn-warning' : ''}" title="Projeyi Veritabanına Kaydet (Ctrl/Cmd+S)">
          ${icon("database", 14)}
          <span>${t("btn_save", ui.lang)}</span>
        </button>

        <button id="btn-export-kasp" class="btn btn-sm" title=".kasp Dosyası İndir">
          ${icon("download", 14)}
          <span>${t("btn_export_kasp", ui.lang)}</span>
        </button>

        <button id="btn-export-json" class="btn btn-sm" title="Sonuçları JSON Olarak Dışa Aktar (_Sonuclar.json)">
          ${icon("download", 14)}
          <span>Sonuç JSON</span>
        </button>

        <label class="btn btn-sm" title=".kasp Dosyası Yükle" style="cursor: pointer; margin: 0;">
          ${icon("upload", 14)}
          <span>${t("btn_import_kasp", ui.lang)}</span>
          <input type="file" id="file-import-kasp" accept=".kasp,.json" style="display: none;" />
        </label>

        <button id="btn-pdf-export" class="btn btn-sm" title="PDF Tasarım Raporu Oluştur">
          ${icon("fileText", 14)}
          <span>${t("btn_pdf_report", ui.lang)}</span>
        </button>

        <button id="btn-module-excel" class="btn btn-sm" title="Tasarım + Modül + İstasyon Sonuçlarını Excel Olarak İndir">
          ${icon("grid", 14)}
          <span>Modül Excel</span>
        </button>

        <div style="width: 1px; height: 18px; background: var(--color-border); margin: 0 4px;"></div>

        <!-- Management Modals -->
        <button id="btn-handbook" class="btn btn-sm btn-icon" title="Termodinamik El Kitabı (Thermodynamics Handbook)">
          ${icon("book", 14)}
        </button>

        <button id="btn-equipment-catalog" class="btn btn-sm btn-icon" title="${t("btn_equipment_catalog", ui.lang)}">
          ${icon("sliders", 14)}
        </button>

        <button id="btn-project-history" class="btn btn-sm btn-icon" title="${t("btn_project_history", ui.lang)}">
          ${icon("layers", 14)}
        </button>

        ${
          auth.role === "admin"
            ? `<button id="btn-user-mgmt" class="btn btn-sm btn-icon" title="${t("btn_user_management", ui.lang)}">
                ${icon("users", 14)}
               </button>`
            : ""
        }

        <div style="width: 1px; height: 18px; background: var(--color-border); margin: 0 4px;"></div>

        <!-- Theme Switcher -->
        <select id="theme-selector" class="form-select" style="width: auto; height: 26px; font-size: 11px; padding: 0 6px;">
          <option value="light" ${ui.theme === "light" ? "selected" : ""}>☀️ Açık</option>
          <option value="dark" ${ui.theme === "dark" ? "selected" : ""}>🌙 Koyu</option>
          <option value="engineering" ${ui.theme === "engineering" ? "selected" : ""}>⚡ Mühendislik</option>
        </select>

        <!-- Language Switcher -->
        <button id="btn-toggle-lang" class="btn btn-sm" style="padding: 0 6px; font-size: 11px; font-weight: 700;">
          ${ui.lang.toUpperCase()}
        </button>

        <!-- Keyboard Shortcuts Help -->
        <button type="button" id="btn-shortcuts-help" class="btn btn-sm" title="Klavye Kısayolları (?)" aria-label="Klavye Kısayolları" style="padding: 0 7px; font-size: 11px; font-weight: 700;">
          ?
        </button>

        <!-- Update & Download Manager -->
        <button type="button" id="btn-update-manager" class="btn btn-sm ${upd.updateAvailable ? "btn-warning" : ""}" title="${t("update_manager_title", ui.lang)}" style="gap: 5px;">
          ${icon("download", 13)}
          <span>${
            activeDl
              ? `${activeDl.percent || 0}%`
              : upd.updateAvailable
                ? t("btn_updates_new", ui.lang)
                : t("btn_updates", ui.lang)
          }</span>
        </button>

        <div style="width: 1px; height: 18px; background: var(--color-border); margin: 0 4px;"></div>

        <!-- Auth Button -->
        ${
          auth.isAuthenticated
            ? `<button id="btn-logout" class="btn btn-sm" title="Oturumu Kapat (${auth.user.username})">
                ${icon("user", 14)}
                <span>${auth.user.username}</span>
                ${icon("x", 12)}
               </button>`
            : `<button id="btn-login" class="btn btn-sm btn-primary">
                ${icon("lock", 14)}
                <span>${t("btn_login", ui.lang)}</span>
               </button>`
        }
      </div>
    `;

    // Bind event handlers
    const titleInput = container.querySelector("#project-title-input");
    if (titleInput) {
      titleInput.addEventListener("change", (e) => updateInput("project_name", e.target.value));
    }

    const themeSelect = container.querySelector("#theme-selector");
    if (themeSelect) {
      themeSelect.addEventListener("change", (e) => setTheme(e.target.value));
    }

    const langBtn = container.querySelector("#btn-toggle-lang");
    if (langBtn) {
      langBtn.addEventListener("click", () => setLanguage(ui.lang === "tr" ? "en" : "tr"));
    }

    const loginBtn = container.querySelector("#btn-login");
    if (loginBtn) {
      loginBtn.addEventListener("click", () => openModal("login"));
    }

    const logoutBtn = container.querySelector("#btn-logout");
    if (logoutBtn) {
      logoutBtn.addEventListener("click", () => logoutUser());
    }

    const equipBtn = container.querySelector("#btn-equipment-catalog");
    if (equipBtn) {
      equipBtn.addEventListener("click", () => openModal("equipment"));
    }

    const handbookBtn = container.querySelector("#btn-handbook");
    if (handbookBtn) {
      handbookBtn.addEventListener("click", () => openModal("handbook"));
    }

    const historyBtn = container.querySelector("#btn-project-history");
    if (historyBtn) {
      historyBtn.addEventListener("click", () => openModal("projects"));
    }

    const userMgmtBtn = container.querySelector("#btn-user-mgmt");
    if (userMgmtBtn) {
      userMgmtBtn.addEventListener("click", () => openModal("users"));
    }

    const saveBtn = container.querySelector("#btn-save-project");
    if (saveBtn) {
      saveBtn.addEventListener("click", async () => {
        const { inputs, results, selectedUnits, charts, warnings, modules, stationData } = projectStore.getState();
        try {
          await api.post("/api/v1/projects", {
            project_name: inputs.project_name,
            calculation_type: "Design",
            inputs,
            results,
            selected_units: selectedUnits,
            charts,
            warnings,
            modules,
            station_data: stationData,
            notes: "Web arayüzünden kaydedildi.",
          });
          markProjectSaved();
          showToast("Proje başarıyla geçmişe kaydedildi.", "success");
        } catch (err) {
          showToast("Kayıt hatası: " + err.message, "danger");
        }
      });
    }

    const exportBtn = container.querySelector("#btn-export-kasp");
    if (exportBtn) {
      exportBtn.addEventListener("click", async () => {
        const { inputs, results, selectedUnits, charts, warnings, modules, stationData } = projectStore.getState();
        const filename = `${(inputs.project_name || "kasp_project").replace(/\s+/g, "_")}.kasp`;
        try {
          await api.downloadFile(
            "/api/v1/projects/export-kasp",
            {
              project_name: inputs.project_name,
              inputs,
              results,
              selected_units: selectedUnits,
              charts,
              warnings,
              modules,
              station_data: stationData,
            },
            filename
          );
          markProjectSaved();
          showToast(".kasp proje dosyası başarıyla indirildi.", "success");
        } catch (err) {
          showToast("Proje indirme hatası: " + err.message, "danger");
        }
      });
    }

    const exportJsonBtn = container.querySelector("#btn-export-json");
    if (exportJsonBtn) {
      exportJsonBtn.addEventListener("click", async () => {
        const { inputs, results, selectedUnits, modules, stationData } = projectStore.getState();
        if (!results) {
          showToast("Lütfen önce bir tasarım hesaplaması yapın.", "warning");
          return;
        }
        const safeName = (inputs.project_name || "kasp_project").replace(/\s+/g, "_");
        try {
          await api.downloadFile(
            "/api/v1/projects/export-results-json",
            { project_name: inputs.project_name, inputs, results, selected_units: selectedUnits, modules, station_data: stationData },
            `${safeName}_Sonuclar.json`
          );
          showToast("Sonuç JSON dosyası başarıyla indirildi.", "success");
        } catch (err) {
          showToast("JSON indirme hatası: " + err.message, "danger");
        }
      });
    }

    const pdfBtn = container.querySelector("#btn-pdf-export");
    if (pdfBtn) {
      pdfBtn.addEventListener("click", async () => {
        const { inputs, results, selectedUnits, modules, stationData } = projectStore.getState();
        if (!results) {
          showToast("Lütfen önce bir tasarım hesaplaması yapın.", "warning");
          return;
        }
        const safeName = (inputs.project_name || "kasp_tasarim_raporu").replace(/\s+/g, "_");
        try {
          showToast("PDF raporu hazırlanıyor...", "info");
          await api.downloadFile(
            "/api/v1/reports/pdf",
            { inputs, results, selected_units: selectedUnits, modules, station_data: stationData },
            `${safeName}.pdf`
          );
          showToast("PDF raporu başarıyla indirildi.", "success");
        } catch (err) {
          showToast("PDF raporu oluşturulamadı: " + err.message, "danger");
        }
      });
    }

    const moduleExcelBtn = container.querySelector("#btn-module-excel");
    if (moduleExcelBtn) {
      moduleExcelBtn.addEventListener("click", async () => {
        const { inputs, results, selectedUnits, warnings, modules, stationData } = projectStore.getState();
        if (!results && !stationData && !Object.keys(modules || {}).length) {
          showToast("Lütfen önce bir tasarım veya modül hesaplaması yapın.", "warning");
          return;
        }
        const safeName = (inputs.project_name || "kasp_project").replace(/\s+/g, "_");
        try {
          showToast("Excel raporu hazırlanıyor...", "info");
          await api.downloadFile(
            "/api/v1/reports/modules-excel",
            {
              inputs,
              results,
              selected_units: selectedUnits,
              warnings,
              modules,
              station_data: stationData,
            },
            `${safeName}_Modul_Raporu.xlsx`
          );
          showToast("Excel raporu başarıyla indirildi.", "success");
        } catch (err) {
          showToast("Excel raporu indirilemedi: " + err.message, "danger");
        }
      });
    }

    const importInput = container.querySelector("#file-import-kasp");
    if (importInput) {
      importInput.addEventListener("change", async (e) => {
        const file = e.target.files[0];
        if (!file) return;
        const formData = new FormData();
        formData.append("file", file);
        try {
          const res = await api.post("/api/v1/projects/import-kasp", formData);
          if (res && res.inputs) {
            hydrateProjectSnapshot(res);
            showToast("Proje başarıyla yüklendi.", "success");
          }
        } catch (err) {
          showToast("Yükleme hatası: " + err.message, "danger");
        } finally {
          e.target.value = "";
        }
      });
    }

    container.querySelector("#btn-shortcuts-help")?.addEventListener("click", () => {
      window.dispatchEvent(new CustomEvent("kasp:open-shortcuts-help"));
    });

    container.querySelector("#btn-update-manager")?.addEventListener("click", () => {
      openModal("updates");
    });
  }

  uiStore.subscribe(update);
  authStore.subscribe(update);
  projectStore.subscribe(update);
  updateStore.subscribe(update);
  update();
}
