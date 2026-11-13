/**
 * KASP Web Platform Bootstrapper (main.js)
 * High-performance, modular ES6 zero-build architecture.
 */

import { icon } from "../vendor/icons.js";
import { uiStore, setActiveTab, closeModal } from "./store/uiStore.js";
import { authStore, checkSession } from "./store/authStore.js";
import { projectStore, fetchPresets, recalculateGasTotal, recalculateLiveMetrics } from "./store/projectStore.js";
import { renderHeader } from "./components/header.js";
import { renderDesignSidebar } from "./components/designSidebar.js";
import { renderResultsView } from "./components/resultsView.js";
import { renderChartsView } from "./components/chartsView.js";
import { renderPerformanceTab } from "./components/performanceTab.js";
import { renderShootoutTab } from "./components/shootoutTab.js";
import { renderStationTab } from "./components/stationTab.js";
import { renderLogsTab } from "./components/logsTab.js";
import { renderKijModal } from "./components/kijModal.js";
import { renderEquipmentModal } from "./components/equipmentModal.js";
import { renderProjectModal } from "./components/projectModal.js";
import { renderUserModal } from "./components/userModal.js";
import { renderAuthModal } from "./components/authModal.js";
import { renderHandbookModal } from "./components/handbookModal.js";
import { renderUpdateModal } from "./components/updateModal.js";
import { updateStore, checkWebUpdates } from "./store/updateStore.js";
import { initGasCatalog } from "./components/gasTable.js";
import { t } from "./i18n/locales.js";

function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

async function initApp() {
  const appRoot = document.getElementById("app");
  if (!appRoot) return;

  // Initialize theme
  const initialTheme = uiStore.getState().theme || "light";
  document.documentElement.setAttribute("data-theme", initialTheme);

  // App Layout Skeleton
  appRoot.innerHTML = `
    <!-- Top Header -->
    <header id="header-mount" class="kasp-header"></header>

    <!-- Navigation Tab Bar -->
    <nav class="kasp-nav-bar">
      <div class="kasp-tabs" id="nav-tabs-mount" role="tablist" aria-label="Ana sekmeler">
        <button class="kasp-tab-btn active" data-tab="design">
          ${icon("sliders", 14)}
          <span>Tasarım (Design)</span>
        </button>
        <button class="kasp-tab-btn" data-tab="performance">
          ${icon("check", 14)}
          <span>Performans (ASME PTC-10)</span>
        </button>
        <button class="kasp-tab-btn" data-tab="shootout">
          ${icon("cpu", 14)}
          <span>Mühendislik Shootout</span>
        </button>
        <button class="kasp-tab-btn" data-tab="station" id="nav-btn-station">
          <span style="font-size: 15px; margin-right: 2px;">🧊</span>
          <span>3D İstasyon & P&ID</span>
          <span class="badge" style="background: #0284c7; color: #fff; font-size: 10px; padding: 1px 6px; border-radius: 8px; font-weight: 700; margin-left: 4px;">3D WebGL</span>
        </button>
        <button class="kasp-tab-btn" data-tab="logs">
          ${icon("terminal", 14)}
          <span>Sistem Logları</span>
        </button>
      </div>
    </nav>

    <!-- Main Content Workspace -->
    <main class="kasp-main-workspace">
      <!-- 1. Design Tab -->
      <div class="kasp-tab-content active" id="tab-content-design">
        <div class="kasp-design-layout">
          <aside class="kasp-design-sidebar" id="design-sidebar-mount"></aside>
          <section class="kasp-design-main" id="design-main-mount">
            <div id="results-view-mount"></div>
            <div id="charts-view-mount"></div>
          </section>
        </div>
      </div>

      <!-- 2. Performance Tab -->
      <div class="kasp-tab-content" id="tab-content-performance">
        <div id="performance-tab-mount" style="flex: 1; height: 100%; overflow: hidden; display: flex;"></div>
      </div>

      <!-- 3. Shootout Tab -->
      <div class="kasp-tab-content" id="tab-content-shootout">
        <div id="shootout-tab-mount" style="flex: 1; height: 100%; overflow: hidden; display: flex;"></div>
      </div>

      <!-- 4. Station P&ID Tab -->
      <div class="kasp-tab-content" id="tab-content-station">
        <div id="station-tab-mount" style="flex: 1; height: 100%; overflow: hidden; display: flex;"></div>
      </div>

      <!-- 5. System Logs Tab -->
      <div class="kasp-tab-content" id="tab-content-logs">
        <div id="logs-tab-mount" style="flex: 1; height: 100%; overflow: hidden; display: flex;"></div>
      </div>
    </main>

    <!-- Bottom Status Bar -->
    <footer class="kasp-status-bar" id="status-bar-mount">
      <div class="kasp-status-group">
        <div class="kasp-status-indicator">
          <span class="status-dot"></span>
          <span>Termodinamik Motor: <b>CoolProp HEOS & Kübik Aktif</b></span>
        </div>
        <div class="kasp-status-indicator">
          <span class="status-dot"></span>
          <span>ASME PTC-10 & API 617 Doğrulandı</span>
        </div>
      </div>
      <div class="kasp-status-group">
        <span id="status-theme-label">Tema: Açık</span>
        <span>•</span>
        <span id="status-user-label">Misafir</span>
        <span>•</span>
        <span id="status-web-version" style="cursor:pointer;" title="Sürüm & İndirme Yöneticisi">v4.1.0-web</span>
      </div>
    </footer>

    <!-- Modals Mount Container -->
    <div id="modals-mount"></div>

    <!-- Toast Notifications Mount Container -->
    <div class="toast-container" id="toasts-mount" role="status" aria-live="polite"></div>
  `;

  // Mount Header
  renderHeader(document.getElementById("header-mount"));

  // Tab switching logic
  const tabBtns = document.querySelectorAll(".kasp-tab-btn");
  tabBtns.forEach(btn => {
    btn.setAttribute("role", "tab");
    btn.addEventListener("click", () => {
      const targetTab = btn.getAttribute("data-tab");
      setActiveTab(targetTab);
    });
  });

  uiStore.subscribe((ui) => {
    // Update tab bar buttons
    tabBtns.forEach(btn => {
      btn.setAttribute("aria-selected", String(btn.getAttribute("data-tab") === ui.activeTab));
      if (btn.getAttribute("data-tab") === ui.activeTab) {
        btn.classList.add("active");
      } else {
        btn.classList.remove("active");
      }
    });

    // Update tab contents
    document.querySelectorAll(".kasp-tab-content").forEach(content => {
      if (content.id === `tab-content-${ui.activeTab}`) {
        content.classList.add("active");
      } else {
        content.classList.remove("active");
      }
    });

    // Notify WebGL 3D renderer on tab switch
    if (ui.activeTab === "station") {
      setTimeout(() => {
        window.dispatchEvent(new Event("resize"));
      }, 60);
    }

    // Update status labels
    const themeLabel = document.getElementById("status-theme-label");
    if (themeLabel) {
      themeLabel.textContent = `Tema: ${ui.theme === "engineering" ? "Mühendislik" : (ui.theme === "dark" ? "Koyu" : "Açık")}`;
    }

    // Render Modals
    const modalsMount = document.getElementById("modals-mount");
    if (modalsMount) {
      if (!ui.activeModal) {
        modalsMount.innerHTML = "";
      } else if (ui.activeModal === "kij") {
        renderKijModal(modalsMount);
      } else if (ui.activeModal === "equipment") {
        renderEquipmentModal(modalsMount);
      } else if (ui.activeModal === "projects") {
        renderProjectModal(modalsMount);
      } else if (ui.activeModal === "handbook") {
        renderHandbookModal(modalsMount);
      } else if (ui.activeModal === "users") {
        renderUserModal(modalsMount);
      } else if (ui.activeModal === "updates") {
        renderUpdateModal(modalsMount);
      } else if (ui.activeModal === "login" || ui.activeModal === "changePassword") {
        renderAuthModal(modalsMount);
      }
    }

    // Render Toasts
    const toastsMount = document.getElementById("toasts-mount");
    if (toastsMount) {
      toastsMount.innerHTML = ui.toasts.map(t => `
        <div class="toast toast-${t.type || 'success'}">
          ${icon(t.type === 'danger' ? 'alertTriangle' : 'check', 16, t.type === 'danger' ? 'text-danger' : 'text-success')}
          <span>${escapeHtml(t.message)}</span>
        </div>
      `).join("");
    }
  });

  // Hesaplama durumu: sonuç alanında meşgul göstergesi
  projectStore.subscribe((st) => {
    const main = document.getElementById("design-main-mount");
    if (!main) return;
    main.classList.toggle("is-busy", !!st.isCalculating);
    main.setAttribute("aria-busy", st.isCalculating ? "true" : "false");
  });

  function toggleShortcutsHelp(forceOpen = null) {
    const existing = document.getElementById("shortcuts-help-overlay");
    if (existing) {
      if (forceOpen === true) return;
      existing.remove();
      return;
    }
    if (forceOpen === false) return;
    const overlay = document.createElement("div");
    overlay.id = "shortcuts-help-overlay";
    overlay.setAttribute("role", "dialog");
    overlay.setAttribute("aria-modal", "true");
    overlay.style.cssText = "position:fixed;inset:0;z-index:10000;background:rgba(15,23,42,0.65);backdrop-filter:blur(4px);display:flex;align-items:center;justify-content:center;padding:16px;";
    overlay.innerHTML = `
      <div class="card" style="max-width:460px;width:100%;padding:18px 20px;box-shadow:0 20px 48px rgba(0,0,0,0.4);">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
          <h3 style="margin:0;font-size:15px;font-weight:700;">⌨️ KASP Klavye Kısayolları</h3>
          <button type="button" id="btn-close-shortcuts-help" class="btn btn-sm">✕</button>
        </div>
        <div style="display:grid;grid-template-columns:auto 1fr;gap:8px 14px;font-size:12px;align-items:center;">
          <kbd>Ctrl/Cmd + Enter</kbd><span>Aktif tasarım / istasyon hesabını başlat</span>
          <kbd>Ctrl/Cmd + S</kbd><span>Projeyi veritabanına kaydet</span>
          <kbd>?</kbd><span>Bu kısayol rehberini aç / kapat</span>
          <kbd>1 – 8 / R</kbd><span>3D kamera önayarları / ISO sıfırla</span>
          <kbd>F / Esc</kbd><span>3D tam ekranı aç / kapat</span>
          <kbd>+ / − / 0</kbd><span>2D P&amp;ID yakınlaştır / uzaklaştır / sıfırla</span>
        </div>
      </div>
    `;
    overlay.addEventListener("click", (ev) => {
      if (ev.target === overlay || ev.target.id === "btn-close-shortcuts-help") overlay.remove();
    });
    document.body.appendChild(overlay);
  }
  window.addEventListener("kasp:open-shortcuts-help", () => toggleShortcutsHelp());

  // Modal & workflow keyboard shortcuts: ESC closes modal, Ctrl/Cmd+Enter runs calculation, Ctrl/Cmd+S saves project
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      if (document.getElementById("shortcuts-help-overlay")) {
        toggleShortcutsHelp(false);
        return;
      }
      if (uiStore.getState().activeModal) {
        closeModal();
        return;
      }
    }
    const tag = (e.target && e.target.tagName) ? e.target.tagName.toLowerCase() : "";
    const isTyping = tag === "input" || tag === "textarea" || tag === "select" || e.target?.isContentEditable;
    if (e.key === "?" && !isTyping && !e.ctrlKey && !e.metaKey) {
      e.preventDefault();
      toggleShortcutsHelp();
      return;
    }
    if ((e.ctrlKey || e.metaKey) && !uiStore.getState().activeModal) {
      if (e.key === "Enter") {
        const activeTab = uiStore.getState().activeTab || "design";
        const targetBtn =
          activeTab === "station"
            ? document.getElementById("btn-size-station-pipes")
            : document.getElementById("btn-run-calculation");
        if (targetBtn && !targetBtn.disabled) {
          e.preventDefault();
          targetBtn.click();
        }
      } else if (e.key.toLowerCase() === "s") {
        const saveBtn = document.getElementById("btn-save-project");
        if (saveBtn) {
          e.preventDefault();
          saveBtn.click();
        }
      }
    }
  });

  window.addEventListener("beforeunload", (e) => {
    if (projectStore.getState().hasUnsavedChanges) {
      e.preventDefault();
      e.returnValue = "";
    }
  });
  new MutationObserver(() => {
    const mm = document.getElementById("modals-mount");
    const dlg = mm && mm.querySelector(".modal-dialog");
    if (dlg && !dlg.hasAttribute("role")) {
      dlg.setAttribute("role", "dialog");
      dlg.setAttribute("aria-modal", "true");
      const first = dlg.querySelector("input:not([type=file]), select, textarea");
      if (first) first.focus({ preventScroll: true });
    }
  }).observe(document.getElementById("modals-mount"), { childList: true });

  authStore.subscribe((auth) => {
    const userLabel = document.getElementById("status-user-label");
    if (userLabel) {
      userLabel.textContent = auth.isAuthenticated ? `${auth.user?.username} (${auth.role})` : "Misafir";
    }
  });

  // Mount components
  renderDesignSidebar(document.getElementById("design-sidebar-mount"));
  renderResultsView(document.getElementById("results-view-mount"));
  renderChartsView(document.getElementById("charts-view-mount"));
  renderPerformanceTab(document.getElementById("performance-tab-mount"));
  renderShootoutTab(document.getElementById("shootout-tab-mount"));
  renderStationTab(document.getElementById("station-tab-mount"));
  renderLogsTab(document.getElementById("logs-tab-mount"));

  // Initial data loading
  await Promise.all([
    initGasCatalog(),
    fetchPresets(),
    checkSession(),
  ]);

  // Automatic non-blocking startup update check for Web Edition
  checkWebUpdates({ force: false, silent: true });

  document.getElementById("status-web-version")?.addEventListener("click", () => {
    uiStore.setState({ activeModal: "updates" });
  });
  updateStore.subscribe((upd) => {
    const verEl = document.getElementById("status-web-version");
    if (verEl && upd.currentVersion) {
      verEl.textContent = `v${upd.currentVersion}`;
    }
  });

  recalculateGasTotal();
  recalculateLiveMetrics();

  // URL Hash Navigation (e.g. #station, #3d, #performance)
  const hash = window.location.hash.toLowerCase();
  if (hash.includes("station") || hash.includes("3d")) {
    setActiveTab("station");
  } else if (hash.includes("performance")) {
    setActiveTab("performance");
  } else if (hash.includes("shootout")) {
    setActiveTab("shootout");
  }
}

// Bootstrap when DOM is ready
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initApp);
} else {
  initApp();
}
