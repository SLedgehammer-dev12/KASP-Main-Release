/**
 * KASP Web Update & Release Download Manager Modal (updateModal.js)
 */

import { icon } from "../../vendor/icons.js";
import { closeModal, uiStore } from "../store/uiStore.js";
import {
  updateStore,
  checkWebUpdates,
  selectReleaseTag,
  startReleaseDownload,
  cancelReleaseDownload,
} from "../store/updateStore.js";
import { t } from "../i18n/locales.js";

function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function _formatSpeed(bps) {
  const v = Number(bps || 0);
  if (!v) return "";
  if (v < 1024) return `${Math.round(v)} B/s`;
  if (v < 1024 * 1024) return `${(v / 1024).toFixed(1)} KB/s`;
  return `${(v / (1024 * 1024)).toFixed(1)} MB/s`;
}

function _statusBadge(status, lang) {
  if (status === "completed") {
    return `<span class="badge badge-success">${t("update_dl_completed", lang)}</span>`;
  }
  if (status === "downloading") {
    return `<span class="badge" style="background: rgba(14,165,233,0.16); color: #0284c7;">${t("update_dl_downloading", lang)}</span>`;
  }
  if (status === "cancelling" || status === "cancelled") {
    return `<span class="badge" style="background: rgba(245,158,11,0.16); color: #d97706;">${t("update_dl_cancelled", lang)}</span>`;
  }
  if (status === "error") {
    return `<span class="badge badge-danger">${t("update_dl_error", lang)}</span>`;
  }
  return `<span class="badge">${escapeHtml(status || "")}</span>`;
}

export function renderUpdateModal(container) {
  let unsub = null;

  function render() {
    const st = updateStore.getState();
    const lang = uiStore.getState().lang || "tr";
    const releases = st.releases || [];
    const selected =
      releases.find((r) => r.tag_name === st.selectedTag) || releases[0] || null;
    const downloads = st.downloads || [];

    const summaryBanner = st.isChecking
      ? `<div style="padding: 10px 14px; border-radius: var(--radius-sm); background: rgba(14,165,233,0.1); border: 1px solid rgba(14,165,233,0.3); font-size: 12px;">
           ⏳ ${t("update_checking", lang)}
         </div>`
      : !st.checkOk
        ? `<div style="padding: 10px 14px; border-radius: var(--radius-sm); background: rgba(239,68,68,0.1); border: 1px solid rgba(239,68,68,0.35); color: var(--color-danger); font-size: 12px;">
             ⚠️ ${escapeHtml(st.error || t("update_check_failed", lang))}
           </div>`
        : st.updateAvailable && st.latestRelease
          ? `<div style="padding: 10px 14px; border-radius: var(--radius-sm); background: rgba(16,185,129,0.12); border: 1px solid rgba(16,185,129,0.4); font-size: 12px; display:flex; align-items:center; justify-content:space-between; gap:10px; flex-wrap:wrap;">
               <div>
                 <strong>🚀 ${t("update_new_version_banner", lang)}: ${escapeHtml(st.latestRelease.tag_name)}</strong>
                 <span style="color: var(--color-text-secondary); margin-left: 8px;">(${t("update_installed", lang)}: ${escapeHtml(st.currentTag)})</span>
               </div>
               ${
                 st.latestRelease.recommended_asset_name
                   ? `<button type="button" class="btn btn-sm btn-primary btn-dl-asset" data-tag="${escapeAttr(st.latestRelease.tag_name)}" data-asset="${escapeAttr(st.latestRelease.recommended_asset_name)}">
                        ${icon("download", 13)}
                        <span>${escapeHtml(st.latestRelease.recommended_asset_name)}</span>
                      </button>`
                   : ""
               }
             </div>`
          : `<div style="padding: 10px 14px; border-radius: var(--radius-sm); background: var(--color-bg-tertiary); border: 1px solid var(--color-border); font-size: 12px;">
               ✅ ${t("update_up_to_date", lang)} (<strong>${escapeHtml(st.currentTag)}</strong>)
             </div>`;

    container.innerHTML = `
      <div class="modal-backdrop" id="update-modal-backdrop">
        <div class="modal-dialog modal-lg" style="max-width: 880px; width: 94vw; max-height: 88vh; display: flex; flex-direction: column;">
          <div class="modal-header">
            <div style="display: flex; align-items: center; gap: 10px;">
              ${icon("download", 20, "text-primary")}
              <div>
                <h3 style="margin: 0; font-size: 15px; font-weight: 700;">${t("update_manager_title", lang)}</h3>
                <div style="font-size: 11px; color: var(--color-text-secondary);">
                  ${t("update_installed", lang)}: <b>${escapeHtml(st.currentVersion)}</b> (${escapeHtml(st.currentTag)})
                </div>
              </div>
            </div>
            <div style="display: flex; align-items: center; gap: 8px;">
              <button type="button" id="btn-refresh-updates" class="btn btn-sm btn-primary" ${st.isChecking ? "disabled" : ""}>
                ${icon("refreshCw", 13)}
                <span>${t("update_check_now", lang)}</span>
              </button>
              <button type="button" id="btn-close-update-modal" class="btn btn-sm">${icon("x", 14)}</button>
            </div>
          </div>

          <div class="modal-body" style="overflow-y: auto; display: flex; flex-direction: column; gap: 14px;">
            ${summaryBanner}

            ${
              st.downloadError
                ? `<div style="padding: 8px 12px; border-radius: var(--radius-sm); background: rgba(239,68,68,0.1); color: var(--color-danger); font-size: 12px;">
                     ${escapeHtml(st.downloadError)}
                   </div>`
                : ""
            }

            <!-- Releases + Notes -->
            <div style="display: grid; grid-template-columns: 240px 1fr; gap: 12px; min-height: 220px;">
              <div style="border: 1px solid var(--color-border); border-radius: var(--radius-sm); overflow-y: auto; max-height: 280px; background: var(--color-bg-secondary);">
                ${
                  releases.length === 0
                    ? `<div style="padding: 14px; font-size: 12px; color: var(--color-text-secondary);">${t("update_no_releases", lang)}</div>`
                    : releases
                        .map((rel) => {
                          const active = selected && selected.tag_name === rel.tag_name;
                          return `
                            <button type="button" class="update-rel-item" data-tag="${escapeAttr(rel.tag_name)}"
                              style="width:100%; text-align:left; padding: 9px 11px; border:none; border-bottom: 1px solid var(--color-border); cursor:pointer; background: ${active ? "var(--color-primary-soft, rgba(14,165,233,0.14))" : "transparent"}; color: var(--color-text-primary);">
                              <div style="display:flex; justify-content:space-between; align-items:center; gap:6px;">
                                <strong style="font-size: 12px;">${escapeHtml(rel.tag_name)}</strong>
                                ${rel.is_newer ? `<span class="badge badge-success" style="font-size:10px;">Yeni</span>` : rel.tag_name === st.currentTag ? `<span class="badge" style="font-size:10px;">Kurulu</span>` : ""}
                              </div>
                              <div style="font-size: 11px; color: var(--color-text-secondary); margin-top: 2px;">${escapeHtml((rel.published_at || "").slice(0, 10) || "-")}</div>
                            </button>
                          `;
                        })
                        .join("")
                }
              </div>

              <div style="border: 1px solid var(--color-border); border-radius: var(--radius-sm); padding: 12px; display: flex; flex-direction: column; gap: 10px; background: var(--color-bg-secondary);">
                ${
                  selected
                    ? `
                      <div style="display:flex; justify-content:space-between; align-items:center; gap:8px; flex-wrap:wrap;">
                        <div>
                          <div style="font-size: 14px; font-weight: 700;">${escapeHtml(selected.name || selected.tag_name)}</div>
                          <div style="font-size: 11px; color: var(--color-text-secondary);">${escapeHtml(selected.status_label || "")} • ${escapeHtml((selected.published_at || "").slice(0, 10))}</div>
                        </div>
                        ${
                          selected.html_url
                            ? `<a href="${escapeAttr(selected.html_url)}" target="_blank" rel="noopener noreferrer" class="btn btn-sm">GitHub Release ↗</a>`
                            : ""
                        }
                      </div>

                      <div style="display: flex; flex-wrap: wrap; gap: 6px;">
                        ${
                          (selected.assets || []).length === 0
                            ? `<span style="font-size: 11px; color: var(--color-text-secondary);">${t("update_no_assets", lang)}</span>`
                            : selected.assets
                                .map((asset) => {
                                  const isRec = asset.name === selected.recommended_asset_name;
                                  return `
                                    <button type="button" class="btn btn-sm ${isRec ? "btn-primary" : ""} btn-dl-asset"
                                      data-tag="${escapeAttr(selected.tag_name)}"
                                      data-asset="${escapeAttr(asset.name)}"
                                      title="${asset.sha256_available ? "SHA-256 doğrulamalı indirme" : "SHA-256 özeti eksik"}">
                                      ${icon("download", 13)}
                                      <span>${escapeHtml(asset.name)} (${escapeHtml(asset.size_human)})</span>
                                    </button>
                                  `;
                                })
                                .join("")
                        }
                      </div>

                      <pre style="margin:0; padding:10px; border-radius:var(--radius-sm); background:var(--color-bg-primary); border:1px solid var(--color-border); font-size:11px; line-height:1.45; white-space:pre-wrap; max-height:170px; overflow-y:auto;">${escapeHtml(selected.body || t("update_no_notes", lang))}</pre>
                    `
                    : `<div style="font-size: 12px; color: var(--color-text-secondary);">${t("update_no_releases", lang)}</div>`
                }
              </div>
            </div>

            <!-- Download Manager Section -->
            <div style="border: 1px solid var(--color-border); border-radius: var(--radius-sm); padding: 12px; background: var(--color-bg-secondary);">
              <div style="font-size: 12px; font-weight: 700; margin-bottom: 8px; display:flex; align-items:center; gap:6px;">
                ${icon("layers", 14, "text-primary")}
                <span>${t("update_download_manager", lang)} (${downloads.length})</span>
              </div>

              ${
                downloads.length === 0
                  ? `<div style="font-size: 12px; color: var(--color-text-secondary);">${t("update_no_downloads", lang)}</div>`
                  : `<div style="display: flex; flex-direction: column; gap: 8px; max-height: 180px; overflow-y: auto;">
                       ${downloads
                         .map((job) => {
                           const pct = Math.max(0, Math.min(100, Number(job.percent || 0)));
                           return `
                             <div style="padding: 8px 10px; border: 1px solid var(--color-border); border-radius: var(--radius-sm); background: var(--color-bg-primary); display:flex; flex-direction:column; gap:6px;">
                               <div style="display:flex; justify-content:space-between; align-items:center; gap:8px; flex-wrap:wrap;">
                                 <div style="font-size: 12px;">
                                   <strong>${escapeHtml(job.asset_name)}</strong>
                                   <span style="color: var(--color-text-secondary); margin-left:6px;">(${escapeHtml(job.tag_name)})</span>
                                 </div>
                                 <div style="display:flex; align-items:center; gap:8px;">
                                   ${_statusBadge(job.status, lang)}
                                   ${
                                     job.status === "downloading"
                                       ? `<button type="button" class="btn btn-sm btn-cancel-dl" data-job="${escapeAttr(job.job_id)}">${t("btn_cancel", lang)}</button>`
                                       : ""
                                   }
                                   ${
                                     job.status === "completed"
                                       ? `<a href="/api/v1/updates/downloads/${encodeURIComponent(job.job_id)}/file" class="btn btn-sm btn-primary" download="${escapeAttr(job.asset_name)}">${icon("download", 12)} <span>${t("update_save_file", lang)}</span></a>`
                                       : ""
                                   }
                                 </div>
                               </div>
                               <div style="height: 6px; border-radius: 999px; background: var(--color-bg-tertiary); overflow: hidden;">
                                 <div style="height: 100%; width: ${pct}%; background: ${job.status === "error" ? "#ef4444" : job.status === "completed" ? "#10b981" : "#0ea5e9"}; transition: width 0.2s;"></div>
                               </div>
                               <div style="display:flex; justify-content:space-between; font-size: 11px; color: var(--color-text-secondary);">
                                 <span>${escapeHtml(job.downloaded_human || "0 B")} / ${escapeHtml(job.total_human || "-")} (${pct}%) ${job.status === "downloading" && job.speed_bps ? "• " + _formatSpeed(job.speed_bps) : ""}</span>
                                 <span>${job.sha256_verified ? "🔒 SHA-256 OK" : job.error ? escapeHtml(job.error) : ""}</span>
                               </div>
                               ${
                                 job.file_path
                                   ? `<div style="font-size: 10px; color: var(--color-text-secondary); word-break: break-all;">📁 ${escapeHtml(job.file_path)}</div>`
                                   : ""
                               }
                             </div>
                           `;
                         })
                         .join("")}
                     </div>`
              }
            </div>
          </div>
        </div>
      </div>
    `;

    const backdrop = container.querySelector("#update-modal-backdrop");
    if (backdrop) {
      backdrop.addEventListener("click", (e) => {
        if (e.target === backdrop) closeAndCleanup();
      });
    }
    const closeBtn = container.querySelector("#btn-close-update-modal");
    if (closeBtn) closeBtn.addEventListener("click", closeAndCleanup);

    const refreshBtn = container.querySelector("#btn-refresh-updates");
    if (refreshBtn) {
      refreshBtn.addEventListener("click", () => checkWebUpdates({ force: true, silent: false }));
    }

    container.querySelectorAll(".update-rel-item").forEach((btn) => {
      btn.addEventListener("click", () => selectReleaseTag(btn.getAttribute("data-tag")));
    });

    container.querySelectorAll(".btn-dl-asset").forEach((btn) => {
      btn.addEventListener("click", () => {
        const tag = btn.getAttribute("data-tag");
        const asset = btn.getAttribute("data-asset");
        if (tag && asset) startReleaseDownload(tag, asset);
      });
    });

    container.querySelectorAll(".btn-cancel-dl").forEach((btn) => {
      btn.addEventListener("click", () => {
        const jobId = btn.getAttribute("data-job");
        if (jobId) cancelReleaseDownload(jobId);
      });
    });
  }

  function closeAndCleanup() {
    if (unsub) {
      unsub();
      unsub = null;
    }
    closeModal();
  }

  function escapeAttr(str) {
    return escapeHtml(str);
  }

  unsub = updateStore.subscribe(() => {
    if (uiStore.getState().activeModal === "updates") {
      render();
    } else if (unsub) {
      unsub();
      unsub = null;
    }
  });

  render();
}
