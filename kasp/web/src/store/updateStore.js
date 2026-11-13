/**
 * KASP Web Update & Release Download Manager Store (updateStore.js)
 */

import { createStore } from "./store.js";
import { api } from "../api/client.js";
import { showToast, uiStore } from "./uiStore.js";
import { t } from "../i18n/locales.js";

export const updateStore = createStore({
  isChecking: false,
  hasChecked: false,
  checkOk: true,
  error: null,
  currentVersion: "4.1.1-web",
  currentTag: "web-v4.1.1",
  platform: "",
  checkedAt: null,
  updateAvailable: false,
  newerCount: 0,
  latestRelease: null,
  releases: [],
  selectedTag: null,
  downloads: [],
  downloadError: null,
});

let _pollTimer = null;

function _hasActiveDownloads(downloads) {
  return (downloads || []).some(
    (d) => d.status === "downloading" || d.status === "cancelling"
  );
}

function _ensurePolling() {
  if (_pollTimer) return;
  _pollTimer = setInterval(async () => {
    await refreshDownloads();
    if (!_hasActiveDownloads(updateStore.getState().downloads)) {
      clearInterval(_pollTimer);
      _pollTimer = null;
    }
  }, 600);
}

export async function refreshDownloads() {
  try {
    const res = await api.get("/api/v1/updates/downloads");
    const downloads = Array.isArray(res?.downloads) ? res.downloads : [];
    updateStore.setState({ downloads });
  } catch (_) {
    // Non-fatal polling error
  }
}

export async function checkWebUpdates({ force = false, silent = false } = {}) {
  if (updateStore.getState().isChecking) return;
  updateStore.setState({ isChecking: true, error: null });

  try {
    const data = await api.get(`/api/v1/updates/check?force=${force ? "true" : "false"}`);
    const releases = Array.isArray(data?.releases) ? data.releases : [];
    const currentSelected = updateStore.getState().selectedTag;
    const selectedTag =
      releases.find((r) => r.tag_name === currentSelected)?.tag_name ||
      data?.latest_release?.tag_name ||
      releases[0]?.tag_name ||
      null;

    updateStore.setState({
      isChecking: false,
      hasChecked: true,
      checkOk: data?.check_ok !== false,
      error: data?.error || null,
      currentVersion: data?.current_version || "4.1.1-web",
      currentTag: data?.current_tag || "web-v4.1.1",
      platform: data?.platform || "",
      checkedAt: data?.checked_at || null,
      updateAvailable: !!data?.update_available,
      newerCount: Number(data?.newer_count || 0),
      latestRelease: data?.latest_release || null,
      releases,
      selectedTag,
    });

    await refreshDownloads();
    if (_hasActiveDownloads(updateStore.getState().downloads)) {
      _ensurePolling();
    }

    const lang = uiStore.getState().lang || "tr";
    if (data?.check_ok === false) {
      if (!silent) {
        showToast(data.error || t("update_check_failed", lang), "danger");
      }
    } else if (data?.update_available) {
      const latestTag = data.latest_release?.tag_name || "";
      showToast(`${t("update_available_toast", lang)} (${latestTag})`, "success");
    } else if (!silent) {
      showToast(t("update_up_to_date", lang), "success");
    }
  } catch (err) {
    updateStore.setState({
      isChecking: false,
      hasChecked: true,
      checkOk: false,
      error: err?.message || "Güncelleme kontrolü başarısız",
    });
    if (!silent) {
      showToast(err?.message || "Güncelleme kontrolü başarısız", "danger");
    }
  }
}

export function selectReleaseTag(tagName) {
  updateStore.setState({ selectedTag: tagName });
}

export async function startReleaseDownload(tagName, assetName) {
  updateStore.setState({ downloadError: null });
  try {
    const job = await api.post("/api/v1/updates/download", {
      tag_name: tagName,
      asset_name: assetName,
    });
    const prev = updateStore.getState().downloads || [];
    updateStore.setState({
      downloads: [job, ...prev.filter((d) => d.job_id !== job.job_id)],
    });
    _ensurePolling();
    const lang = uiStore.getState().lang || "tr";
    showToast(`${t("update_download_started", lang)}: ${assetName}`, "success");
    return job;
  } catch (err) {
    const msg = err?.message || "İndirme başlatılamadı";
    updateStore.setState({ downloadError: msg });
    showToast(msg, "danger");
    return null;
  }
}

export async function cancelReleaseDownload(jobId) {
  try {
    await api.post(`/api/v1/updates/downloads/${encodeURIComponent(jobId)}/cancel`, {});
    await refreshDownloads();
  } catch (err) {
    showToast(err?.message || "İndirme iptal edilemedi", "danger");
  }
}
