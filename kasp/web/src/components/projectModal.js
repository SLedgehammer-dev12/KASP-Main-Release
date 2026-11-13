/**
 * KASP Project History Management Modal
 */

import { icon } from "../../vendor/icons.js";
import { closeModal, showToast } from "../store/uiStore.js";
import { hydrateProjectSnapshot } from "../store/projectStore.js";
import { api } from "../api/client.js";

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

export async function renderProjectModal(container) {
  let projects = [];

  async function loadProjects() {
    try {
      projects = await api.get("/api/v1/projects");
    } catch (_) {
      projects = [];
    }
    render();
  }

  function render() {
    container.innerHTML = `
      <div class="modal-backdrop">
        <div class="modal-dialog modal-lg">
          <div class="modal-header">
            <div class="modal-title">
              ${icon("layers", 18, "text-primary")}
              <span>Hesaplama Geçmişi ve Kayıtlı Projeler</span>
            </div>
            <button class="btn btn-sm btn-icon" id="btn-close-proj-modal">${icon("x", 14)}</button>
          </div>

          <div class="modal-body">
            <div style="margin-bottom: 10px;">
              <input
                type="search"
                id="project-history-search"
                class="form-input"
                placeholder="Proje adı veya tarih ara..."
                aria-label="Kayıtlı projelerde ara"
                style="width: 100%; height: 32px; font-size: 12px;"
              />
            </div>
            <div style="max-height: 400px; overflow-y: auto;">
              <table class="kasp-table">
                <thead>
                  <tr>
                    <th>Tarih</th>
                    <th>Proje Adı</th>
                    <th>Tür</th>
                    <th style="text-align: right;">Giriş P (bar)</th>
                    <th style="text-align: right;">Çıkış P (bar)</th>
                    <th style="text-align: center;">İşlemler</th>
                  </tr>
                </thead>
                <tbody>
                  ${
                    projects.length > 0
                      ? projects.map(p => `
                        <tr>
                          <td style="color: var(--color-text-secondary); font-size: 11px;">${p.calculation_date || ''}</td>
                          <td><b>${escapeHtml(p.project_name || 'İsimsiz Proje')}</b></td>
                          <td><span class="badge badge-info">${p.calculation_type || 'Design'}</span></td>
                          <td style="text-align: right; font-family: var(--font-mono);">${p.inputs?.p_in || '-'}</td>
                          <td style="text-align: right; font-family: var(--font-mono);">${p.inputs?.p_out || '-'}</td>
                          <td style="text-align: center;">
                            <div style="display: inline-flex; gap: 4px;">
                              <button class="btn btn-sm btn-primary btn-load-proj" data-id="${p.id}" title="Çalışma Alanına Yükle">
                                ${icon("download", 12)}
                                <span>Yükle</span>
                              </button>
                              <button class="btn btn-sm btn-icon btn-del-proj" data-id="${p.id}" title="Sil">
                                ${icon("trash", 12)}
                              </button>
                            </div>
                          </td>
                        </tr>
                      `).join("")
                      : `<tr><td colspan="6" style="text-align: center; color: var(--color-text-secondary); padding: 24px;">Henüz kaydedilmiş hesaplama bulunmuyor.</td></tr>`
                  }
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    `;

    container.querySelector("#btn-close-proj-modal")?.addEventListener("click", closeModal);

    container.querySelector("#project-history-search")?.addEventListener("input", (e) => {
      const q = e.target.value.trim().toLowerCase();
      container.querySelectorAll("tbody tr").forEach((tr) => {
        const text = (tr.textContent || "").toLowerCase();
        tr.style.display = !q || text.includes(q) ? "" : "none";
      });
    });

    // Load handlers
    container.querySelectorAll(".btn-load-proj").forEach(btn => {
      btn.addEventListener("click", async () => {
        const id = btn.getAttribute("data-id");
        try {
          // List responses omit the heavy results payload; fetch the full record.
          const project = await api.get(`/api/v1/projects/${id}`);
          if (project && project.inputs) {
            hydrateProjectSnapshot(project);
            showToast(`'${project.project_name}' çalışma alanına yüklendi.`);
            closeModal();
          }
        } catch (err) {
          showToast("Proje yüklenemedi: " + err.message, "danger");
        }
      });
    });

    // Delete handlers
    container.querySelectorAll(".btn-del-proj").forEach(btn => {
      btn.addEventListener("click", async () => {
        const id = btn.getAttribute("data-id");
        if (!confirm("Bu hesaplama kaydını silmek istediğinize emin misiniz?")) return;
        try {
          await api.delete(`/api/v1/projects/${id}`);
          projects = projects.filter(x => x.id != id);
          render();
          showToast("Proje kaydı silindi.");
        } catch (err) {
          showToast("Silme hatası: " + err.message, "danger");
        }
      });
    });
  }

  loadProjects();
}
