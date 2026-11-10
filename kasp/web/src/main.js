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
        <span>v4.1.0</span>
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

  // Modal ergonomisi: ESC ile kapat, açılışta ilk alana odak, role=dialog
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && uiStore.getState().activeModal) closeModal();
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
