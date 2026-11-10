/**
 * KASP System Logs Tab Component
 * Real-time SSE log streamer connected to MemoryRingLogHandler.
 */

import { icon } from "../../vendor/icons.js";
import { api } from "../api/client.js";
import { showToast } from "../store/uiStore.js";

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

export function renderLogsTab(container) {
  let logs = [];
  let filterLevel = "ALL";
  let autoScroll = true;
  let eventSource = null;

  async function init() {
    try {
      logs = await api.get("/api/v1/logs?limit=300");
    } catch (_) {
      logs = [];
    }
    render();
    startStream();
  }

  function startStream() {
    if (eventSource) eventSource.close();
    eventSource = new EventSource("/api/v1/logs/stream");

    eventSource.onmessage = (event) => {
      try {
        const logEntry = JSON.parse(event.data);
        logs.push(logEntry);
        if (logs.length > 500) logs.shift();
        appendLogToDom(logEntry);
      } catch (_) {}
    };
  }

  function appendLogToDom(entry) {
    if (filterLevel !== "ALL" && entry.level !== filterLevel) return;
    const listElem = container.querySelector("#logs-list");
    if (!listElem) return;

    const row = document.createElement("div");
    row.style.cssText = "padding: 3px 6px; border-bottom: 1px solid var(--color-border); font-family: var(--font-mono); font-size: 11px; white-space: pre-wrap;";
    let color = "var(--color-text)";
    if (entry.level === "WARNING") color = "var(--color-warning)";
    if (entry.level === "ERROR" || entry.level === "CRITICAL") color = "var(--color-danger)";
    if (entry.level === "ITERATION") color = "var(--color-primary)";

    const safeTime = escapeHtml(entry.asctime || '');
    const safeLevel = escapeHtml(entry.level || 'INFO');
    const safeName = escapeHtml(entry.name || 'kasp');
    const safeMsg = escapeHtml(entry.message || '');

    row.innerHTML = `<span style="color: var(--color-text-secondary);">${safeTime}</span> <span style="font-weight: 700; color: ${color};">[${safeLevel}]</span> <span style="color: var(--color-text-muted);">${safeName}:</span> ${safeMsg}`;
    listElem.appendChild(row);

    if (autoScroll) {
      listElem.scrollTop = listElem.scrollHeight;
    }
  }

  function render() {
    const filteredLogs = filterLevel === "ALL" ? logs : logs.filter(l => l.level === filterLevel);

    container.innerHTML = `
      <div style="flex: 1; padding: 20px; overflow: hidden; display: flex; flex-direction: column; gap: 12px; height: 100%;">
        <div class="card" style="padding: 10px 16px; display: flex; align-items: center; justify-content: space-between; flex-shrink: 0;">
          <div style="display: flex; align-items: center; gap: 8px;">
            ${icon("terminal", 16, "text-primary")}
            <span style="font-weight: 600; font-size: 13px;">Sistem ve Termodinamik Motor Logları</span>
            <span class="badge badge-info">${filteredLogs.length} Kayıt</span>
          </div>

          <div style="display: flex; align-items: center; gap: 10px;">
            <select id="log-level-filter" class="form-select" style="width: auto; height: 26px; font-size: 11px; padding: 0 6px;">
              <option value="ALL" ${filterLevel === "ALL" ? "selected" : ""}>Tüm Seviyeler</option>
              <option value="INFO" ${filterLevel === "INFO" ? "selected" : ""}>INFO</option>
              <option value="WARNING" ${filterLevel === "WARNING" ? "selected" : ""}>WARNING</option>
              <option value="ERROR" ${filterLevel === "ERROR" ? "selected" : ""}>ERROR</option>
              <option value="ITERATION" ${filterLevel === "ITERATION" ? "selected" : ""}>ITERATION</option>
            </select>

            <label style="display: flex; align-items: center; gap: 4px; font-size: 11px; cursor: pointer; user-select: none;">
              <input type="checkbox" id="cb-autoscroll" ${autoScroll ? "checked" : ""} />
              <span>Oto-Kaydır</span>
            </label>

            <button id="btn-clear-logs" class="btn btn-sm btn-danger" title="Logları Temizle">
              ${icon("trash", 12)}
              <span>Temizle</span>
            </button>
          </div>
        </div>

        <div id="logs-list" style="flex: 1; overflow-y: auto; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-lg); padding: 8px;">
          ${filteredLogs.map(entry => {
            let color = "var(--color-text)";
            if (entry.level === "WARNING") color = "var(--color-warning)";
            if (entry.level === "ERROR" || entry.level === "CRITICAL") color = "var(--color-danger)";
            if (entry.level === "ITERATION") color = "var(--color-primary)";
            const safeTime = escapeHtml(entry.asctime || '');
            const safeLevel = escapeHtml(entry.level || 'INFO');
            const safeName = escapeHtml(entry.name || 'kasp');
            const safeMsg = escapeHtml(entry.message || '');
            return `
              <div style="padding: 3px 6px; border-bottom: 1px solid var(--color-border); font-family: var(--font-mono); font-size: 11px; white-space: pre-wrap;">
                <span style="color: var(--color-text-secondary);">${safeTime}</span> 
                <span style="font-weight: 700; color: ${color};">[${safeLevel}]</span> 
                <span style="color: var(--color-text-muted);">${safeName}:</span> 
                ${safeMsg}
              </div>
            `;
          }).join("")}
        </div>
      </div>
    `;

    const filterSelect = container.querySelector("#log-level-filter");
    if (filterSelect) {
      filterSelect.addEventListener("change", (e) => {
        filterLevel = e.target.value;
        render();
      });
    }

    const autoCb = container.querySelector("#cb-autoscroll");
    if (autoCb) {
      autoCb.addEventListener("change", (e) => {
        autoScroll = e.target.checked;
      });
    }

    const clearBtn = container.querySelector("#btn-clear-logs");
    if (clearBtn) {
      clearBtn.addEventListener("click", async () => {
        try {
          await api.delete("/api/v1/logs");
          logs = [];
          render();
          showToast("Log kayıtları temizlendi.");
        } catch (_) {}
      });
    }

    const listElem = container.querySelector("#logs-list");
    if (listElem && autoScroll) {
      listElem.scrollTop = listElem.scrollHeight;
    }
  }

  init();
}
