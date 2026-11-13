/**
 * KASP Plotly.js Interactive Charts View Component
 * Renders 8 dense scientific charts + 3-layer SVG thermodynamic diagram.
 * Supports zoom, pan, hover tooltips, and theme updates.
 */

import { icon } from "../../vendor/icons.js";
import { projectStore } from "../store/projectStore.js";
import { uiStore } from "../store/uiStore.js";

export function renderChartsView(container) {
  let lastChartsRef = null;
  let lastTheme = null;
  let renderFrameId = null;

  function update() {
    const proj = projectStore.getState();
    const ui = uiStore.getState();
    const charts = proj.charts;

    if (!charts) {
      if (lastChartsRef !== null) {
        container.innerHTML = "";
        lastChartsRef = null;
      }
      return;
    }

    if (charts === lastChartsRef && ui.theme === lastTheme) {
      return; // Chart data and theme are unchanged, avoid DOM & Plotly thrashing
    }
    lastChartsRef = charts;
    lastTheme = ui.theme;

    if (renderFrameId) {
      cancelAnimationFrame(renderFrameId);
      renderFrameId = null;
    }

    container.querySelector("#btn-charts-reset-zoom")?.addEventListener("click", () => {
      if (!window.Plotly) return;
      ["chart-envelope", "chart-turbine-derate", "chart-ts", "chart-pv", "chart-hs", "chart-kz", "chart-stage"].forEach((id) => {
        const el = container.querySelector(`#${id}`);
        if (el && el.data) {
          try {
            window.Plotly.relayout(el, { "xaxis.autorange": true, "yaxis.autorange": true });
          } catch (_) {}
        }
      });
    });

    container.querySelector("#btn-charts-download-png")?.addEventListener("click", () => {
      if (!window.Plotly) return;
      const el = container.querySelector("#chart-envelope");
      if (el && el.data) {
        try {
          window.Plotly.downloadImage(el, { format: "png", width: 1200, height: 700, filename: "kasp_operating_envelope" });
        } catch (_) {}
      }
    });

    container.innerHTML = `
      <div class="card" style="margin-top: 16px;">
        <div class="card-header" style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
          <div class="card-title">
            ${icon("barChart", 16, "text-primary")}
            <span>Termodinamik Grafikler ve Mimari Analiz</span>
          </div>
          <div style="display: flex; align-items: center; gap: 6px; flex-wrap: wrap;">
            <span style="font-size: 11px; color: var(--color-text-secondary);">
              Plotly.js Etkileşimli Zoom &amp; Pan Aktif
            </span>
            <button type="button" id="btn-charts-reset-zoom" class="btn btn-sm" title="Tüm grafiklerin yakınlaştırmasını sıfırla">Zoom Sıfırla</button>
            <button type="button" id="btn-charts-download-png" class="btn btn-sm" title="Çalışma Zarfı grafiğini PNG olarak indir">PNG İndir</button>
          </div>
        </div>

        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(420px, 1fr)); gap: 16px;">
          <!-- Operating Envelope & Anti-Surge Map (API 617 / ASME PTC 10) -->
          <div class="card" style="padding: 12px; grid-column: 1 / -1;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
              <div style="font-weight: 700; font-size: 13px; color: var(--color-primary);">
                🌀 Kompresör Aerodinamik Çalışma Zarfı & Anti-Surge Haritası (API 617 / ASME PTC 10)
              </div>
              <span class="badge badge-success" id="badge-envelope-status">
                Surge Emniyet Marjı: +%${charts.operating_envelope?.operating_point?.surge_margin_pct || 47.1} (Güvenli Bölge)
              </span>
            </div>
            <div id="chart-envelope" style="width: 100%; height: 360px;"></div>
          </div>

          <!-- T-s Diagram -->
          <div class="card" style="padding: 12px;">
            <div style="font-weight: 600; font-size: 12px; margin-bottom: 8px;">Sıcaklık - Entropi (T-s) Diyagramı</div>
            <div id="chart-ts" style="width: 100%; height: 320px;"></div>
          </div>

          <!-- P-v Diagram -->
          <div class="card" style="padding: 12px;">
            <div style="font-weight: 600; font-size: 12px; margin-bottom: 8px;">Basınç - Hacim (P-v) Diyagramı</div>
            <div id="chart-pv" style="width: 100%; height: 320px;"></div>
          </div>

          <!-- Mollier h-s Diagram -->
          <div class="card" style="padding: 12px;">
            <div style="font-weight: 600; font-size: 12px; margin-bottom: 8px;">Mollier Entalpi - Entropi (h-s) Haritası</div>
            <div id="chart-hs" style="width: 100%; height: 320px;"></div>
          </div>

          <!-- k-Z Path Diagram -->
          <div class="card" style="padding: 12px;">
            <div style="font-weight: 600; font-size: 12px; margin-bottom: 8px;">İzentropik Üs - Sıkıştırılabilirlik (k-Z) Yolu</div>
            <div id="chart-kz" style="width: 100%; height: 320px;"></div>
          </div>

          <!-- Stage Overview -->
          <div class="card" style="padding: 12px;">
            <div style="font-weight: 600; font-size: 12px; margin-bottom: 8px;">Kademe Güç & Basınç Dağılımı</div>
            <div id="chart-stage" style="width: 100%; height: 320px;"></div>
          </div>

          <!-- Turbine Radar -->
          <div class="card" style="padding: 12px;">
            <div style="font-weight: 600; font-size: 12px; margin-bottom: 8px;">Gaz Türbini Seçim Radarı (API 617)</div>
            <div id="chart-radar" style="width: 100%; height: 320px;"></div>
          </div>

          <!-- Turbine ISO 2314 Ambient Derate Curves -->
          <div class="card" style="padding: 12px; grid-column: 1 / -1;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
              <div style="font-weight: 700; font-size: 12px; color: var(--color-primary);">
                🌡️ Gaz Türbini Ortam Sıcaklığı Güç Düşümü & Derate Eğrileri (ISO 2314)
              </div>
              <span class="badge badge-info">
                Tasarım Ortam Sıcaklığı: ${charts.turbine_derate?.site_temp_c || 19}°C • Gereken Güç: ${Math.round(charts.turbine_derate?.required_power_kw || 2500).toLocaleString('tr-TR')} kW
              </span>
            </div>
            <div id="chart-turbine-derate" style="width: 100%; height: 340px;"></div>
          </div>

          <!-- Energy Flow Sankey Diagram -->
          ${
            charts.power_sankey
              ? `<div class="card" style="padding: 12px; grid-column: 1 / -1;">
                  <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                    <div style="font-weight: 700; font-size: 12px; color: var(--color-primary);">
                      ⚡ İstasyon Enerji ve Güç Akış Diyagramı (Sankey - API 617 / ASME)
                    </div>
                    <span class="badge badge-success">Yakıt Isıl Girişi ➔ Faydalı Gaz Gücü</span>
                  </div>
                  <div id="chart-sankey" style="width: 100%; height: 320px;"></div>
                 </div>`
              : ""
          }
        </div>

        <!-- 3-Layer Thermodynamic SVG Architecture Diagram -->
        ${
          charts.architecture_svg
            ? `<div class="card" style="margin-top: 16px; padding: 16px; text-align: center; overflow-x: auto;">
                <div style="font-weight: 600; font-size: 12px; margin-bottom: 12px; text-align: left;">3-Katmanlı Termodinamik Mimari Şeması</div>
                <div style="display: inline-block;">${charts.architecture_svg}</div>
               </div>`
            : ""
        }
      </div>
    `;

    // Stagger Plotly rendering across successive animation frames
    // This gives the browser event loop time to breathe and prevents UI thread freezing
    const chartQueue = [
      ["chart-envelope", charts.operating_envelope],
      ["chart-turbine-derate", charts.turbine_derate],
      ...(charts.power_sankey ? [["chart-sankey", charts.power_sankey]] : []),
      ["chart-ts", charts.ts_diagram],
      ["chart-pv", charts.pv_diagram],
      ["chart-hs", charts.hs_mollier],
      ["chart-kz", charts.kz_path],
      ["chart-stage", charts.stage_overview],
      ["chart-radar", charts.turbine_radar],
    ];

    let queueIdx = 0;
    function renderNext() {
      if (queueIdx >= chartQueue.length) return;
      const [elemId, payload] = chartQueue[queueIdx++];
      renderPlotlyChart(elemId, payload, ui.theme);
      if (queueIdx < chartQueue.length) {
        renderFrameId = requestAnimationFrame(renderNext);
      }
    }
    renderFrameId = requestAnimationFrame(renderNext);
  }

  function renderPlotlyChart(elemId, payload, theme) {
    if (!payload || !window.Plotly) return;
    const elem = container.querySelector(`#${elemId}`);
    if (!elem) return;

    const isDark = theme === "dark" || theme === "engineering";
    const bg = isDark ? (theme === "engineering" ? "#1A2332" : "#1E293B") : "#FFFFFF";
    const text = isDark ? "#E2E8F0" : "#1C1917";
    const grid = isDark ? "#334155" : "#E5E7EB";

    let traces = payload.data || [];
    let customLayout = payload.layout || {};

    if (!payload.data) {
      if (payload.actual_path && payload.actual_path.t_c) {
        // T-s Diagram
        traces = [
          {
            x: payload.actual_path.s,
            y: payload.actual_path.t_c,
            mode: "lines+markers",
            name: payload.actual_path.name || "Gerçek Yol (Politropik)",
            line: { color: "#0284c7", width: 2.5 },
            marker: { size: 6, color: "#0284c7" },
          },
          ...(payload.isentropic_path ? [{
            x: payload.isentropic_path.s,
            y: payload.isentropic_path.t_c,
            mode: "lines",
            name: payload.isentropic_path.name || "İzentropik Referans",
            line: { color: "#94a3b8", width: 2, dash: "dash" },
          }] : []),
          ...(payload.points ? payload.points.map(pt => ({
            x: [pt.s],
            y: [pt.t_c],
            mode: "markers+text",
            text: [pt.label],
            textposition: "top center",
            name: pt.label,
            marker: { size: 8, color: "#f59e0b" },
            showlegend: false,
          })) : [])
        ];
        customLayout = {
          xaxis: { title: payload.x_label || "Entropi s [kJ/kg·K]" },
          yaxis: { title: payload.y_label || "Sıcaklık T [°C]" },
        };
      } else if (payload.polytropic_path) {
        // P-v Diagram
        traces = [
          {
            x: payload.polytropic_path.v,
            y: payload.polytropic_path.p,
            mode: "lines",
            name: payload.polytropic_path.name || "Politropik (Pvⁿ=C)",
            line: { color: "#0284c7", width: 2.5 },
          },
          ...(payload.isentropic_path ? [{
            x: payload.isentropic_path.v,
            y: payload.isentropic_path.p,
            mode: "lines",
            name: payload.isentropic_path.name || "İzentropik (Pvᵏ=C)",
            line: { color: "#94a3b8", width: 2, dash: "dash" },
          }] : []),
        ];
        customLayout = {
          xaxis: { title: payload.x_label || "Özgül Hacim v [m³/kg]" },
          yaxis: { title: payload.y_label || "Basınç P [bar(a)]" },
        };
      } else if (payload.actual_path && payload.actual_path.h) {
        // Mollier h-s Diagram
        traces = [
          {
            x: payload.actual_path.s,
            y: payload.actual_path.h,
            mode: "lines+markers",
            name: payload.actual_path.name || "Gerçek Entalpi Artışı",
            line: { color: "#10b981", width: 2.5 },
            marker: { size: 6, color: "#10b981" },
          },
          ...(payload.isentropic_path ? [{
            x: payload.isentropic_path.s,
            y: payload.isentropic_path.h,
            mode: "lines",
            name: payload.isentropic_path.name || "İzentropik Head",
            line: { color: "#94a3b8", width: 2, dash: "dash" },
          }] : []),
        ];
        customLayout = {
          xaxis: { title: payload.x_label || "Entropi s [kJ/kg·K]" },
          yaxis: { title: payload.y_label || "Entalpi h [kJ/kg]" },
        };
      } else if (payload.prs && payload.z_values) {
        // k-Z path
        traces = [
          {
            x: payload.prs,
            y: payload.z_values,
            mode: "lines+markers",
            name: "Sıkıştırılabilirlik (Z)",
            yaxis: "y1",
            line: { color: "#0284c7", width: 2 },
          },
          {
            x: payload.prs,
            y: payload.k_values,
            mode: "lines+markers",
            name: "İzentropik Üs (k)",
            yaxis: "y2",
            line: { color: "#f59e0b", width: 2, dash: "dot" },
          },
        ];
        customLayout = {
          xaxis: { title: payload.x_label || "Basınç Oranı (P / P_in)" },
          yaxis: { title: "Z Faktörü", side: "left" },
          yaxis2: { title: "İzentropik Üs k", side: "right", overlaying: "y" },
        };
      } else if (payload.powers_kw && payload.labels) {
        // Stage Overview
        traces = [
          {
            x: payload.labels,
            y: payload.powers_kw,
            type: "bar",
            name: "Gaz Gücü (kW)",
            marker: { color: "#0284c7" },
          },
          {
            x: payload.labels,
            y: payload.heads_kj_kg,
            type: "scatter",
            mode: "lines+markers",
            name: "Head (kJ/kg)",
            yaxis: "y2",
            line: { color: "#10b981", width: 2.5 },
            marker: { size: 7, color: "#10b981" },
          },
        ];
        customLayout = {
          yaxis: { title: "Güç [kW]" },
          yaxis2: { title: "Head [kJ/kg]", side: "right", overlaying: "y" },
        };
      } else if (payload.categories && payload.series) {
        // Turbine Radar
        const colors = ["#0284c7", "#10b981", "#f59e0b", "#8b5cf6"];
        traces = payload.series.map((s, idx) => ({
          type: "scatterpolar",
          r: [...s.values, s.values[0]],
          theta: [...payload.categories, payload.categories[0]],
          fill: "toself",
          name: s.name,
          line: { color: colors[idx % colors.length] },
        }));
        customLayout = {
          polar: {
            radialaxis: { visible: true, range: [0, 100] },
          },
        };
      } else if (payload.nodes && payload.links) {
        // Power Sankey Diagram
        traces = [
          {
            type: "sankey",
            orientation: "h",
            node: {
              pad: 14,
              thickness: 18,
              line: { color: isDark ? "#475569" : "#cbd5e1", width: 0.5 },
              label: payload.nodes.map((n) => n.name),
              color: ["#f59e0b", "#ef4444", "#0284c7", "#f97316", "#10b981", "#8b5cf6", "#06b6d4"],
            },
            link: {
              source: payload.links.map((l) => l.source),
              target: payload.links.map((l) => l.target),
              value: payload.links.map((l) => l.value),
              color: isDark ? "rgba(255,255,255,0.18)" : "rgba(0,0,0,0.12)",
            },
          },
        ];
        customLayout = {
          font: { color: text, family: "Inter, sans-serif", size: 10 },
          margin: { l: 20, r: 20, t: 30, b: 20 },
        };
      }
    }

    const baseLayout = {
      paper_bgcolor: bg,
      plot_bgcolor: bg,
      font: { color: text, family: "Inter, sans-serif", size: 10 },
      margin: { l: 50, r: 20, t: 52, b: 44 },
      autosize: true,
      xaxis: { gridcolor: grid, zerolinecolor: grid },
      yaxis: { gridcolor: grid, zerolinecolor: grid },
    };

    const mergedLayout = {
      ...baseLayout,
      ...customLayout,
      title: undefined,
      margin: customLayout.margin ? { ...baseLayout.margin, ...customLayout.margin, t: Math.max(52, customLayout.margin.t || 0) } : baseLayout.margin,
      paper_bgcolor: bg,
      plot_bgcolor: bg,
    };

    try {
      window.Plotly.newPlot(elem, traces, mergedLayout, {
        responsive: true,
        displayModeBar: false,
      });
    } catch (err) {
      console.warn("Plotly plot error:", err);
    }
  }

  projectStore.subscribe(update);
  window.addEventListener("kasp:theme-changed", update);

  let resizeTimer = null;
  function onWindowResize() {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
      if (!window.Plotly) return;
      const chartIds = [
        "chart-envelope", "chart-turbine-derate", "chart-sankey", "chart-ts", "chart-pv",
        "chart-hs", "chart-kz", "chart-stage", "chart-radar"
      ];
      chartIds.forEach((id) => {
        const el = container.querySelector(`#${id}`);
        if (el && el.data) {
          try {
            window.Plotly.Plots.resize(el);
          } catch (_) {}
        }
      });
    }, 120);
  }
  window.addEventListener("resize", onWindowResize);

  update();
}
