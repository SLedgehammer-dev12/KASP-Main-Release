/**
 * KASP Engineering Shootout Tab Component (F04)
 * 9-EOS x 6-Method benchmark suite with real-time deduplicated SSE progress,
 * cooperative job cancellation, reference deviation mapping, engineering ranking,
 * best-row highlighting, and offline Plotly comparison chart.
 */

import { icon } from "../../vendor/icons.js";
import { projectStore, updateInput, escapeHtml } from "../store/projectStore.js";
import { uiStore, showToast } from "../store/uiStore.js";
import { api } from "../api/client.js";

const AVAILABLE_EOS = [
  { id: "coolprop", name: "CoolProp (HEOS Referans)", core: true },
  { id: "pr", name: "Peng-Robinson (Kübik)", core: true },
  { id: "srk", name: "Soave-Redlich-Kwong (SRK)", core: true },
  { id: "gerg2008", name: "GERG-2008 Doğalgaz Modeli", core: true },
  { id: "aga8", name: "AGA8-DC92 Doğalgaz Modeli", core: false },
  { id: "thermopack", name: "SINTEF ThermoPack (VLE)", core: false },
  { id: "neqsim", name: "Equinor NeqSim (CPA/SRK)", core: false },
  { id: "ccp", name: "Petrobras CCP", core: false },
  { id: "dwsim", name: "DWSIM Termodinamik", core: false },
];

const AVAILABLE_METHODS = [
  { value: "Metot 6: Schultz 3-Üslü Gerçek Gaz", short: "Metot 6 (Schultz 3-Üslü)", core: true },
  { value: "Metot 5: Huntington-RK45 Diferansiyel", short: "Metot 5 (Huntington-RK45)", core: true },
  { value: "Metot 4: Doğrudan H-S", short: "Metot 4 (Doğrudan H-S)", core: false },
  { value: "Metot 3: Artımlı Basınç", short: "Metot 3 (Artımlı Basınç)", core: false },
  { value: "Metot 2: Endpoint Yaklaşımı", short: "Metot 2 (Endpoint)", core: false },
  { value: "Metot 1: Ortalama Özellikler", short: "Metot 1 (Ortalama Öz.)", core: true },
];

function shortMethodLabel(methodStr) {
  const found = AVAILABLE_METHODS.find((m) => m.value === methodStr);
  if (found) return found.short;
  const raw = String(methodStr || "");
  return raw.length > 28 ? raw.slice(0, 28) + "…" : raw;
}

function formatSignedPct(val) {
  if (val === null || val === undefined || !Number.isFinite(Number(val))) return "—";
  const num = Number(val);
  if (Math.abs(num) < 0.0005) return "0.00%";
  return `${num > 0 ? "+" : ""}${num.toFixed(2)}%`;
}

function formatSignedTemp(val) {
  if (val === null || val === undefined || !Number.isFinite(Number(val))) return "—";
  const num = Number(val);
  if (Math.abs(num) < 0.005) return "0.00 °C";
  return `${num > 0 ? "+" : ""}${num.toFixed(2)} °C`;
}

function rankClientSide(rows) {
  if (!Array.isArray(rows) || rows.length === 0) {
    return { ranked: [], summary: null };
  }
  const cloned = rows.map((r) => ({ ...r }));
  const successful = cloned.filter(
    (r) => r.status === "success" && Number.isFinite(Number(r.power_kw)) && Number(r.power_kw) > 0
  );

  let ref =
    successful.find(
      (r) =>
        r.eos === "coolprop" &&
        !r.fallback_used &&
        (String(r.method).includes("Metot 6") || String(r.method).includes("Metot 5"))
    ) ||
    successful.find((r) => r.eos === "coolprop" && !r.fallback_used) ||
    successful.find((r) => !r.fallback_used) ||
    successful[0] ||
    null;

  const refPower = ref ? Number(ref.power_kw) : 0;
  const refHead = ref ? Number(ref.head_kj_kg) : 0;
  const refTout = ref ? Number(ref.t_out_c) : 0;

  for (const r of cloned) {
    if (r.status === "success" && ref) {
      r.is_reference = r.step === ref.step;
      if (r.power_diff_pct === undefined || r.power_diff_pct === null) {
        r.power_diff_pct = refPower > 0 ? ((Number(r.power_kw) - refPower) / refPower) * 100.0 : 0.0;
      }
      if (r.head_diff_pct === undefined || r.head_diff_pct === null) {
        r.head_diff_pct = refHead > 0 ? ((Number(r.head_kj_kg) - refHead) / refHead) * 100.0 : 0.0;
      }
      if (r.t_out_diff_c === undefined || r.t_out_diff_c === null) {
        r.t_out_diff_c = Number(r.t_out_c) - refTout;
      }
    } else {
      r.is_reference = false;
    }
  }

  const methodOrder = (m) => {
    const s = String(m || "");
    if (s.includes("Metot 6")) return 0;
    if (s.includes("Metot 5")) return 1;
    if (s.includes("Metot 4")) return 2;
    if (s.includes("Metot 3")) return 3;
    if (s.includes("Metot 2")) return 4;
    return 5;
  };

  cloned.sort((a, b) => {
    if (a.status !== "success" && b.status !== "success") return (a.step || 0) - (b.step || 0);
    if (a.status !== "success") return 1;
    if (b.status !== "success") return -1;
    const tierA = a.fallback_used ? 1 : 0;
    const tierB = b.fallback_used ? 1 : 0;
    if (tierA !== tierB) return tierA - tierB;
    const devA = Math.abs(Number(a.power_diff_pct || 0)) + 0.5 * Math.abs(Number(a.head_diff_pct || 0));
    const devB = Math.abs(Number(b.power_diff_pct || 0)) + 0.5 * Math.abs(Number(b.head_diff_pct || 0));
    if (Math.abs(devA - devB) > 1e-4) return devA - devB;
    const mDiff = methodOrder(a.method) - methodOrder(b.method);
    if (mDiff !== 0) return mDiff;
    return Number(a.duration_ms || 0) - Number(b.duration_ms || 0);
  });

  cloned.forEach((r, idx) => {
    r.rank = idx + 1;
    r.is_best = idx === 0 && r.status === "success";
  });

  const best = cloned.find((r) => r.is_best) || null;
  const powers = successful.map((r) => Number(r.power_kw));
  const durations = cloned.map((r) => Number(r.duration_ms || 0)).filter((d) => d >= 0);
  const minP = powers.length ? Math.min(...powers) : 0;
  const maxP = powers.length ? Math.max(...powers) : 0;

  return {
    ranked: cloned,
    summary: {
      total_runs: cloned.length,
      success_count: successful.length,
      error_count: cloned.filter((r) => r.status === "error").length,
      fallback_count: successful.filter((r) => r.fallback_used).length,
      reference_eos: ref?.eos || null,
      reference_method: ref?.method || null,
      reference_power_kw: refPower || null,
      reference_head_kj_kg: refHead || null,
      best_eos: best?.eos || null,
      best_method: best?.method || null,
      best_power_kw: best?.power_kw || null,
      best_eff_pct: best?.eff_pct || null,
      power_spread_kw: powers.length ? maxP - minP : 0,
      power_spread_pct: powers.length && refPower > 0 ? ((maxP - minP) / refPower) * 100.0 : 0,
      avg_duration_ms: durations.length ? durations.reduce((a, b) => a + b, 0) / durations.length : 0,
    },
  };
}

export function renderShootoutTab(container) {
  let selectedEos = ["coolprop", "pr", "srk", "gerg2008"];
  let selectedMethods = [
    "Metot 6: Schultz 3-Üslü Gerçek Gaz",
    "Metot 5: Huntington-RK45 Diferansiyel",
    "Metot 1: Ortalama Özellikler",
  ];

  let currentJobId = null;
  let isRunning = false;
  let progressPct = 0;
  let completedRuns = 0;
  let totalRuns = 0;
  let rawResults = [];
  let rankedResults = [];
  let summaryData = null;
  let validationErrorMsg = "";
  let eventSource = null;
  let seenSteps = new Set();

  function buildRowHtml(r) {
    const isBest = Boolean(r.is_best);
    const isRef = Boolean(r.is_reference);
    const isSuccess = r.status === "success";
    const effEos = String(r.effective_eos || r.eos || "").toLowerCase();
    const reqEos = String(r.eos || "").toLowerCase();
    const hasFallback = Boolean(r.fallback_used || (effEos && reqEos && effEos !== reqEos));

    const pDiff = Number(r.power_diff_pct);
    const pDiffBadgeClass = !Number.isFinite(pDiff)
      ? ""
      : Math.abs(pDiff) <= 1.0
        ? "badge-success"
        : Math.abs(pDiff) <= 3.0
          ? "badge-info"
          : "badge-warning";

    return `
      <tr class="${isBest ? "shootout-best-row" : ""}" data-step="${escapeHtml(r.step)}">
        <td style="font-family: var(--font-mono); font-weight: 700; white-space: nowrap;">
          ${
            isBest
              ? `<span class="badge badge-success" style="font-size: 10px;">#${escapeHtml(r.rank)} En İyi</span>`
              : `#${escapeHtml(r.rank || r.step || "-")}`
          }
        </td>
        <th scope="row" style="white-space: nowrap;">
          <div style="display: flex; align-items: center; gap: 6px;">
            <span style="font-weight: 700;">${escapeHtml(reqEos.toUpperCase())}</span>
            ${
              hasFallback
                ? `<span class="badge badge-warning" style="font-size: 9px;" title="Etkin çözücü: ${escapeHtml(effEos.toUpperCase())}">Fallback → ${escapeHtml(effEos.toUpperCase())}</span>`
                : ""
            }
          </div>
        </th>
        <td>
          <div style="display: flex; align-items: center; gap: 6px; flex-wrap: wrap;">
            <span>${escapeHtml(shortMethodLabel(r.method))}</span>
            ${isRef ? `<span class="badge badge-info" style="font-size: 9px;">Referans</span>` : ""}
          </div>
        </td>
        <td style="text-align: right; font-family: var(--font-mono); font-weight: 600;">
          ${isSuccess && Number.isFinite(Number(r.power_kw)) ? Number(r.power_kw).toLocaleString("tr-TR", { minimumFractionDigits: 1, maximumFractionDigits: 1 }) : "—"}
        </td>
        <td style="text-align: right; font-family: var(--font-mono);">
          ${
            isSuccess && r.power_diff_pct !== null && r.power_diff_pct !== undefined
              ? `<span class="badge ${pDiffBadgeClass}" style="font-family: var(--font-mono); font-size: 10px;">${escapeHtml(formatSignedPct(r.power_diff_pct))}</span>`
              : "—"
          }
        </td>
        <td style="text-align: right; font-family: var(--font-mono);">
          ${
            isSuccess && Number.isFinite(Number(r.head_kj_kg))
              ? `${Number(r.head_kj_kg).toFixed(2)} <span style="font-size: 10px; color: var(--color-text-secondary);">(${escapeHtml(formatSignedPct(r.head_diff_pct))})</span>`
              : "—"
          }
        </td>
        <td style="text-align: right; font-family: var(--font-mono);">
          ${
            isSuccess && Number.isFinite(Number(r.t_out_c))
              ? `${Number(r.t_out_c).toFixed(1)} <span style="font-size: 10px; color: var(--color-text-secondary);">(${escapeHtml(formatSignedTemp(r.t_out_diff_c))})</span>`
              : "—"
          }
        </td>
        <td style="text-align: right; font-family: var(--font-mono); font-weight: 600;">
          ${isSuccess && Number.isFinite(Number(r.eff_pct)) ? `%${Number(r.eff_pct).toFixed(2)}` : "—"}
        </td>
        <td style="text-align: right; font-family: var(--font-mono); color: var(--color-text-secondary); white-space: nowrap;">
          ${Number(r.duration_ms || 0).toFixed(1)} ms
        </td>
        <td style="text-align: center; white-space: nowrap;">
          ${
            isSuccess
              ? `<div style="display: inline-flex; align-items: center; gap: 6px;">
                   <span class="badge ${hasFallback ? "badge-warning" : "badge-success"}">${hasFallback ? "Yedek EOS" : "Doğrulandı"}</span>
                   <button type="button" class="btn btn-sm shootout-apply-btn" data-eos="${escapeHtml(effEos || reqEos)}" data-method="${escapeHtml(r.method)}" aria-label="${escapeHtml(reqEos.toUpperCase())} ve ${escapeHtml(shortMethodLabel(r.method))} kombinasyonunu tasarıma uygula" style="height: 22px; padding: 0 7px; font-size: 10px;">
                     Uygula
                   </button>
                 </div>`
              : `<span class="badge badge-danger" title="${escapeHtml(r.error || "Hesaplama hatası")}">Hata</span>`
          }
        </td>
      </tr>
    `;
  }

  function renderPlotlyComparisonChart() {
    const chartEl = container.querySelector("#shootout-plotly-chart");
    if (!chartEl || typeof window.Plotly === "undefined") return;

    const validRows = rankedResults.filter(
      (r) => r.status === "success" && Number.isFinite(Number(r.power_kw))
    );
    if (validRows.length === 0) {
      chartEl.innerHTML = "";
      return;
    }

    const isDark = uiStore.getState().theme === "dark";
    const textColor = isDark ? "#E2E8F0" : "#1E293B";
    const gridColor = isDark ? "rgba(148, 163, 184, 0.16)" : "rgba(100, 116, 139, 0.16)";
    const bgColor = "rgba(0,0,0,0)";

    const methodsInRun = Array.from(new Set(validRows.map((r) => r.method)));
    const eosInRun = Array.from(new Set(validRows.map((r) => String(r.eos || "").toUpperCase())));
    const palette = ["#0284C7", "#10B981", "#F59E0B", "#8B5CF6", "#EC4899", "#14B8A6"];

    const traces = methodsInRun.map((mName, mIdx) => {
      const yVals = eosInRun.map((eosCode) => {
        const match = validRows.find(
          (r) => String(r.eos || "").toUpperCase() === eosCode && r.method === mName
        );
        return match ? Number(match.power_kw) : null;
      });
      const customHover = eosInRun.map((eosCode) => {
        const match = validRows.find(
          (r) => String(r.eos || "").toUpperCase() === eosCode && r.method === mName
        );
        if (!match) return "";
        return `Sıra #${match.rank} | ΔGüç: ${formatSignedPct(match.power_diff_pct)} | T_çıkış: ${Number(match.t_out_c).toFixed(1)} °C | Verim: %${Number(match.eff_pct).toFixed(2)}`;
      });

      return {
        type: "bar",
        name: shortMethodLabel(mName),
        x: eosInRun,
        y: yVals,
        customdata: customHover,
        hovertemplate: "<b>%{x}</b> — " + escapeHtml(shortMethodLabel(mName)) + "<br>Mil Gücü: <b>%{y:,.1f} kW</b><br>%{customdata}<extra></extra>",
        marker: {
          color: palette[mIdx % palette.length],
          borderRadius: 4,
        },
      };
    });

    const powers = validRows.map((r) => Number(r.power_kw));
    const minP = Math.min(...powers);
    const maxP = Math.max(...powers);
    const pad = Math.max(10, (maxP - minP) * 0.35 || maxP * 0.03);

    const layout = {
      barmode: "group",
      paper_bgcolor: bgColor,
      plot_bgcolor: bgColor,
      margin: { t: 24, r: 20, b: 48, l: 68 },
      height: 290,
      font: { family: "Inter, system-ui, sans-serif", size: 11, color: textColor },
      xaxis: {
        title: { text: "Durum Denklemi (EOS)" },
        gridcolor: gridColor,
      },
      yaxis: {
        title: { text: "Toplam Mil Gücü (kW)" },
        gridcolor: gridColor,
        range: [Math.max(0, minP - pad), maxP + pad],
      },
      legend: {
        orientation: "h",
        y: 1.14,
        x: 0,
        font: { size: 10 },
      },
    };

    window.Plotly.react(chartEl, traces, layout, {
      responsive: true,
      displaylogo: false,
      modeBarButtonsToRemove: ["lasso2d", "select2d"],
    });
  }

  function bindTableApplyButtons() {
    container.querySelectorAll(".shootout-apply-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        const eos = btn.getAttribute("data-eos");
        const method = btn.getAttribute("data-method");
        if (eos) updateInput("eos_model", eos);
        if (method) updateInput("calc_method", method);
        showToast(`Tasarım modeline uygulandı: ${(eos || "").toUpperCase()} • ${shortMethodLabel(method)}`);
      });
    });
  }

  function render() {
    const inp = projectStore.getState().inputs || {};
    const plannedRuns = selectedEos.length * selectedMethods.length;
    const displayTotal = isRunning ? totalRuns : plannedRuns;

    const s = summaryData;
    const bestLabel = s && s.best_eos ? `${String(s.best_eos).toUpperCase()} • ${shortMethodLabel(s.best_method)}` : "—";
    const refLabel = s && s.reference_eos ? `${String(s.reference_eos).toUpperCase()} • ${shortMethodLabel(s.reference_method)}` : "—";

    container.innerHTML = `
      <div style="flex: 1; padding: 20px; overflow-y: auto; display: flex; flex-direction: column; gap: 16px;">
        <div class="card">
          <div class="card-header" style="flex-wrap: wrap; gap: 8px;">
            <h2 class="card-title" style="margin: 0;">
              ${icon("cpu", 16, "text-primary")}
              <span>Mühendislik Termodinamik Shootout (9-EOS × 6-Metot Kıyaslama)</span>
            </h2>
            <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
              <span class="badge badge-info" style="font-family: var(--font-mono);">
                P_giriş: ${escapeHtml(inp.p_in)} ${escapeHtml(inp.p_in_unit)} → P_çıkış: ${escapeHtml(inp.p_out)} ${escapeHtml(inp.p_out_unit)}
              </span>
              <span class="badge badge-info" style="font-family: var(--font-mono);">
                Debi: ${escapeHtml(inp.flow)} ${escapeHtml(inp.flow_unit)} • ${escapeHtml(inp.num_stages || 1)} Kademe
              </span>
              <span style="font-size: 11px; color: var(--color-text-secondary);">
                Seçili Kombinasyon: <b id="shootout-planned-count">${displayTotal} Analiz</b>
              </span>
            </div>
          </div>

          <p style="font-size: 12px; color: var(--color-text-secondary); margin: 0 0 12px 0;">
            Aktif gaz karışımı ve proses şartları için durum denklemlerini (EOS) ve politropik sıkıştırma yolu metotlarını paralel çalıştırır,
            ASME PTC-10 / API 617 referans bazına göre sapmaları hesaplar ve en tutarlı kombinasyonu <b>#1 En İyi</b> olarak sıralar.
          </p>

          <!-- Quick Matrix Presets -->
          <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 14px;">
            <span style="font-size: 11px; font-weight: 600; color: var(--color-text-secondary);">Hızlı Matris:</span>
            <button type="button" id="btn-preset-core" class="btn btn-sm" ${isRunning ? "disabled" : ""}>
              Çekirdek Referans (4 EOS × 3 Metot = 12)
            </button>
            <button type="button" id="btn-preset-all" class="btn btn-sm" ${isRunning ? "disabled" : ""}>
              Tam Matris (9 EOS × 6 Metot = 54)
            </button>
            <button type="button" id="btn-preset-clear" class="btn btn-sm" ${isRunning ? "disabled" : ""}>
              Seçimi Temizle
            </button>
          </div>

          <!-- Configuration Matrix -->
          <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; margin-bottom: 16px;">
            <fieldset style="border: 1px solid var(--color-border); border-radius: var(--radius-md); padding: 10px 12px; margin: 0;">
              <legend style="font-weight: 600; font-size: 12px; padding: 0 6px; color: var(--color-text);">
                Kullanılacak Durum Denklemleri (EOS)
              </legend>
              <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 6px; margin-top: 4px;">
                ${AVAILABLE_EOS.map((eos) => {
                  const cbId = `shootout-eos-${eos.id}`;
                  return `
                    <div style="display: flex; align-items: center; gap: 8px; font-size: 12px;">
                      <input
                        type="checkbox"
                        id="${cbId}"
                        class="eos-check"
                        value="${escapeHtml(eos.id)}"
                        ${selectedEos.includes(eos.id) ? "checked" : ""}
                        ${isRunning ? "disabled" : ""}
                      />
                      <label for="${cbId}" style="cursor: pointer; user-select: none;">${escapeHtml(eos.name)}</label>
                    </div>
                  `;
                }).join("")}
              </div>
            </fieldset>

            <fieldset style="border: 1px solid var(--color-border); border-radius: var(--radius-md); padding: 10px 12px; margin: 0;">
              <legend style="font-weight: 600; font-size: 12px; padding: 0 6px; color: var(--color-text);">
                Kullanılacak Politropik Yol Metotları
              </legend>
              <div style="display: flex; flex-direction: column; gap: 6px; margin-top: 4px;">
                ${AVAILABLE_METHODS.map((m, idx) => {
                  const cbId = `shootout-method-${idx + 1}`;
                  return `
                    <div style="display: flex; align-items: center; gap: 8px; font-size: 12px;">
                      <input
                        type="checkbox"
                        id="${cbId}"
                        class="method-check"
                        value="${escapeHtml(m.value)}"
                        ${selectedMethods.includes(m.value) ? "checked" : ""}
                        ${isRunning ? "disabled" : ""}
                      />
                      <label for="${cbId}" style="cursor: pointer; user-select: none;">${escapeHtml(m.value)}</label>
                    </div>
                  `;
                }).join("")}
              </div>
            </fieldset>
          </div>

          ${
            validationErrorMsg
              ? `<div role="alert" style="margin-bottom: 12px; padding: 10px 12px; border-radius: var(--radius-md); background: var(--color-danger-bg); border: 1px solid var(--color-danger-border); color: var(--color-danger-text); font-size: 12px;">
                   <b>Doğrulama Hatası:</b> ${escapeHtml(validationErrorMsg)}
                 </div>`
              : ""
          }

          <!-- Actions -->
          <div style="display: flex; align-items: center; gap: 12px; flex-wrap: wrap;">
            ${
              !isRunning
                ? `<button type="button" id="btn-start-shootout" class="btn btn-primary" ${plannedRuns === 0 ? "disabled" : ""}>
                    ${icon("play", 14)}
                    <span>Shootout Analizini Başlat (${plannedRuns} Test)</span>
                   </button>`
                : `<button type="button" id="btn-cancel-shootout" class="btn btn-danger">
                    ${icon("x", 14)}
                    <span>Hesaplamayı Durdur</span>
                   </button>`
            }
          </div>

          <!-- Native Accessible Progress Bar -->
          ${
            isRunning || completedRuns > 0
              ? `
              <div style="margin-top: 16px;">
                <div style="display: flex; justify-content: space-between; align-items: center; font-size: 11px; margin-bottom: 6px;">
                  <label id="shootout-progress-label" for="shootout-progress-bar" style="font-weight: 600; color: var(--color-text);">
                    İlerleme: <span id="shootout-progress-text">${completedRuns} / ${totalRuns || plannedRuns}</span> kombinasyon tamamlandı
                  </label>
                  <span id="shootout-progress-pct" style="font-family: var(--font-mono); font-weight: 700; color: var(--color-primary);">%${progressPct.toFixed(1)}</span>
                </div>
                <progress id="shootout-progress-bar" class="kasp-progress" max="100" value="${progressPct.toFixed(1)}"></progress>
              </div>
            `
              : ""
          }
        </div>

        <!-- Summary KPI Strip -->
        ${
          s && s.success_count > 0
            ? `
            <div class="metrics-grid" id="shootout-kpi-grid">
              <div class="metric-card" style="border-left: 3px solid #10b981;">
                <div class="metric-label">🏆 #1 En İyi Kombinasyon</div>
                <div style="font-size: 13px; font-weight: 700; color: var(--color-text); line-height: 1.3;">${escapeHtml(bestLabel)}</div>
                <div style="font-size: 11px; color: var(--color-text-secondary); font-family: var(--font-mono);">
                  Güç: ${Number(s.best_power_kw || 0).toLocaleString("tr-TR", { maximumFractionDigits: 1 })} kW • Verim: %${Number(s.best_eff_pct || 0).toFixed(2)}
                </div>
              </div>

              <div class="metric-card" style="border-left: 3px solid var(--color-primary);">
                <div class="metric-label">Referans Baz Model</div>
                <div style="font-size: 13px; font-weight: 700; color: var(--color-text); line-height: 1.3;">${escapeHtml(refLabel)}</div>
                <div style="font-size: 11px; color: var(--color-text-secondary); font-family: var(--font-mono);">
                  Ref Head: ${Number(s.reference_head_kj_kg || 0).toFixed(2)} kJ/kg
                </div>
              </div>

              <div class="metric-card">
                <div class="metric-label">Model Güç Yayılımı (Max − Min)</div>
                <div class="metric-value-row">
                  <span class="metric-value">${Number(s.power_spread_pct || 0).toFixed(2)}</span>
                  <span class="metric-unit">% (${Number(s.power_spread_kw || 0).toFixed(1)} kW)</span>
                </div>
              </div>

              <div class="metric-card">
                <div class="metric-label">Tamamlanan &amp; Ort. Çözüm Süresi</div>
                <div class="metric-value-row">
                  <span class="metric-value">${escapeHtml(s.success_count)}/${escapeHtml(s.total_runs)}</span>
                  <span class="metric-unit">başarılı • ${Number(s.avg_duration_ms || 0).toFixed(1)} ms</span>
                </div>
              </div>
            </div>
          `
            : ""
        }

        <!-- Ranked Results Table -->
        ${
          rankedResults.length > 0 || isRunning
            ? `
            <div class="card" id="shootout-results-card">
              <div class="card-header" style="flex-wrap: wrap; gap: 8px;">
                <h3 class="card-title" id="shootout-ranking-heading" style="margin: 0;">
                  ${icon("activity", 16, "text-primary")}
                  <span>Sıralamalı EOS × Metot Kıyaslama Tablosu <span id="shootout-results-count">(${rankedResults.length})</span></span>
                </h3>
                <span style="font-size: 11px; color: var(--color-text-secondary);">
                  Yeşil vurgulanan satır referans doğruluk ve yakınsama kriterine göre <b>#1 En İyi</b> modeldir.
                </span>
              </div>

              <div tabindex="0" role="region" aria-labelledby="shootout-ranking-heading" class="shootout-table-wrapper">
                <table class="kasp-table" id="shootout-ranking-table">
                  <caption class="visually-hidden">EOS ve Politropik Metot Kıyaslama Sıralama Tablosu</caption>
                  <thead>
                    <tr>
                      <th scope="col">Sıra</th>
                      <th scope="col">EOS Modeli</th>
                      <th scope="col">Politropik Yol Metodu</th>
                      <th scope="col" style="text-align: right;">Mil Gücü (kW)</th>
                      <th scope="col" style="text-align: right;">ΔGüç (%)</th>
                      <th scope="col" style="text-align: right;">Poli. Head (kJ/kg)</th>
                      <th scope="col" style="text-align: right;">T_çıkış (°C)</th>
                      <th scope="col" style="text-align: right;">Verim (%)</th>
                      <th scope="col" style="text-align: right;">Süre</th>
                      <th scope="col" style="text-align: center;">Durum / İşlem</th>
                    </tr>
                  </thead>
                  <tbody id="shootout-results-tbody">
                    ${rankedResults.map(buildRowHtml).join("")}
                  </tbody>
                </table>
              </div>
            </div>
          `
            : ""
        }

        <!-- Interactive Plotly Comparison Chart -->
        ${
          rankedResults.some((r) => r.status === "success") && !isRunning
            ? `
            <div class="card" id="shootout-chart-card">
              <div class="card-header">
                <h3 class="card-title" style="margin: 0;">
                  ${icon("bar-chart-2", 16, "text-primary")}
                  <span>EOS × Politropik Metot Mil Gücü Sapma Haritası</span>
                </h3>
              </div>
              <figure style="margin: 0;">
                <div id="shootout-plotly-chart" style="width: 100%; min-height: 290px;"></div>
                <figcaption style="font-size: 11px; color: var(--color-text-secondary); margin-top: 6px;">
                  Her EOS grubu içinde politropik yol metotlarının toplam mil gücü (kW) dağılımı ve referansa göre yüzdesel farkları.
                </figcaption>
              </figure>
            </div>
          `
            : ""
        }
      </div>
    `;

    // Bind preset buttons
    container.querySelector("#btn-preset-core")?.addEventListener("click", () => {
      selectedEos = AVAILABLE_EOS.filter((e) => e.core).map((e) => e.id);
      selectedMethods = AVAILABLE_METHODS.filter((m) => m.core).map((m) => m.value);
      render();
    });

    container.querySelector("#btn-preset-all")?.addEventListener("click", () => {
      selectedEos = AVAILABLE_EOS.map((e) => e.id);
      selectedMethods = AVAILABLE_METHODS.map((m) => m.value);
      render();
    });

    container.querySelector("#btn-preset-clear")?.addEventListener("click", () => {
      selectedEos = [];
      selectedMethods = [];
      render();
    });

    // Bind checkboxes
    container.querySelectorAll(".eos-check").forEach((cb) => {
      cb.addEventListener("change", () => {
        if (cb.checked) {
          if (!selectedEos.includes(cb.value)) selectedEos.push(cb.value);
        } else {
          selectedEos = selectedEos.filter((x) => x !== cb.value);
        }
        render();
      });
    });

    container.querySelectorAll(".method-check").forEach((cb) => {
      cb.addEventListener("change", () => {
        if (cb.checked) {
          if (!selectedMethods.includes(cb.value)) selectedMethods.push(cb.value);
        } else {
          selectedMethods = selectedMethods.filter((x) => x !== cb.value);
        }
        render();
      });
    });

    // Bind start/cancel and row apply buttons
    container.querySelector("#btn-start-shootout")?.addEventListener("click", startShootout);
    container.querySelector("#btn-cancel-shootout")?.addEventListener("click", cancelShootout);
    bindTableApplyButtons();

    if (rankedResults.some((r) => r.status === "success") && !isRunning) {
      renderPlotlyComparisonChart();
    }
  }

  function updateStreamingDom() {
    const pBar = container.querySelector("#shootout-progress-bar");
    const pText = container.querySelector("#shootout-progress-text");
    const pPct = container.querySelector("#shootout-progress-pct");
    const tbody = container.querySelector("#shootout-results-tbody");
    const countEl = container.querySelector("#shootout-results-count");

    if (pBar) pBar.value = Number(progressPct.toFixed(1));
    if (pText) pText.textContent = `${completedRuns} / ${totalRuns}`;
    if (pPct) pPct.textContent = `%${progressPct.toFixed(1)}`;
    if (countEl) countEl.textContent = `(${rankedResults.length})`;

    if (tbody) {
      tbody.innerHTML = rankedResults.map(buildRowHtml).join("");
      bindTableApplyButtons();
    } else {
      render();
    }
  }

  async function syncFinalJobStatus(jobId) {
    if (!jobId) return;
    try {
      const st = await api.get(`/api/v1/jobs/${jobId}/status`);
      if (Array.isArray(st.ranked_results) && st.ranked_results.length > 0) {
        rankedResults = st.ranked_results;
        summaryData = st.summary || rankClientSide(st.ranked_results).summary;
      } else if (Array.isArray(st.results) && st.results.length > 0) {
        const computed = rankClientSide(st.results);
        rankedResults = computed.ranked;
        summaryData = st.summary || computed.summary;
      }
      completedRuns = st.completed || rankedResults.length;
      if (st.total > 0) {
        totalRuns = st.total;
        progressPct = Math.min(100, (completedRuns / totalRuns) * 100);
      }
    } catch (_) {}
  }

  async function startShootout() {
    const inputs = projectStore.getState().inputs;
    validationErrorMsg = "";
    rawResults = [];
    rankedResults = [];
    summaryData = null;
    seenSteps = new Set();
    progressPct = 0;
    completedRuns = 0;
    totalRuns = selectedEos.length * selectedMethods.length;
    isRunning = true;
    render();

    try {
      const initRes = await api.post("/api/v1/jobs/shootout", {
        inputs,
        eos_list: selectedEos,
        method_list: selectedMethods,
      });

      currentJobId = initRes.job_id;
      totalRuns = initRes.total_runs || totalRuns;

      if (eventSource) {
        eventSource.close();
      }
      eventSource = new EventSource(`/api/v1/jobs/${currentJobId}/stream`);

      eventSource.onmessage = async (event) => {
        try {
          const item = JSON.parse(event.data);
          if (item.type === "progress" && item.data) {
            const stepNum = item.data.step;
            if (stepNum !== undefined && seenSteps.has(stepNum)) {
              return;
            }
            if (stepNum !== undefined) {
              seenSteps.add(stepNum);
            }
            rawResults.push(item.data);
            completedRuns = rawResults.length;
            progressPct = totalRuns > 0 ? Math.min(100, (completedRuns / totalRuns) * 100) : 0;
            const liveRanked = rankClientSide(rawResults);
            rankedResults = liveRanked.ranked;
            summaryData = liveRanked.summary;
            updateStreamingDom();
          } else if (item.type === "completed" || item.type === "cancelled" || item.type === "error") {
            isRunning = false;
            if (eventSource) {
              eventSource.close();
              eventSource = null;
            }
            if (item.type === "completed") {
              if (Array.isArray(item.ranked_results) && item.ranked_results.length > 0) {
                rankedResults = item.ranked_results;
                summaryData = item.summary || rankClientSide(item.ranked_results).summary;
                completedRuns = rankedResults.length;
                progressPct = 100;
              } else {
                await syncFinalJobStatus(currentJobId);
              }
              showToast("Shootout kıyaslama ve sıralama analizi tamamlandı!", "success");
            } else if (item.type === "error") {
              validationErrorMsg = item.message || "Shootout sırasında beklenmeyen hata oluştu.";
              showToast("Shootout hata ile sonlandı.", "danger");
            } else {
              showToast("Shootout durduruldu.");
            }
            render();
          }
        } catch (_) {}
      };

      eventSource.onerror = async () => {
        if (eventSource) {
          eventSource.close();
          eventSource = null;
        }
        await syncFinalJobStatus(currentJobId);
        isRunning = false;
        render();
      };
    } catch (err) {
      isRunning = false;
      validationErrorMsg = err?.message || "Shootout başlatılamadı.";
      showToast("Shootout başlatılamadı: " + validationErrorMsg, "danger");
      render();
    }
  }

  async function cancelShootout() {
    if (currentJobId) {
      try {
        await api.post(`/api/v1/jobs/${currentJobId}/cancel`);
      } catch (_) {}
    }
    isRunning = false;
    if (eventSource) {
      eventSource.close();
      eventSource = null;
    }
    showToast("Hesaplama iptal edildi.");
    render();
  }

  // Keep active process badges synced when user updates inputs in Design tab
  projectStore.subscribe(() => {
    if (!isRunning && uiStore.getState().activeTab === "shootout") {
      render();
    }
  });

  // Re-style Plotly chart when theme changes
  uiStore.subscribe(() => {
    if (!isRunning && uiStore.getState().activeTab === "shootout" && rankedResults.length > 0) {
      renderPlotlyComparisonChart();
    }
  });

  render();
}
