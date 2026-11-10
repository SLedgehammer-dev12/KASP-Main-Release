/**
 * KASP Compressor Station Modeling & Animated Process Flow Tab Component (stationTab.js)
 * Implements full process flow verified against BOTAŞ Adapazarı PFD (0-NGTL0-CS-I-001-4000):
 * - Mainline tie-ins with Pig Receivers and Pig Launchers
 * - 48" Suction Header with dynamic Filter & Multi-Cyclone Separators (A, B, C...)
 * - Condensate Drainage System with LCVs and Condensate Tanks (Note 14)
 * - Cartridge Filter Separators (A, B, C...) with PDT transmitters
 * - Unit Building Shelter with N parallel Turbo-Compressor trains (30"x16" nozzles - Note 32)
 * - Individual Hot Gas Anti-Surge Recycle Loops with fast-acting ASV valves
 * - 48" Discharge Header & 48" Station-wide Recycle Line (Note 13)
 * - Fin-Fan Gas Air Coolers with Gas Cooler By-Pass & TCV secondary control (Note 17)
 * - Station Relief Valves (PSV) & Station Blowdown (BDV) to Emergency Vent
 * - BOTAŞ Adapazarı PFD Reference Drawing Modal Viewer
 */

import { icon } from "../../vendor/icons.js";
import { projectStore, setModuleResult, setStationData } from "../store/projectStore.js";
import { showToast } from "../store/uiStore.js";
import { api } from "../api/client.js";
import { createStation3dView } from "./station3dView.js";

export function renderStationTab(container) {
  let stationData = null;
  let isLoading = false;
  let selectedEquip = null;
  let isPfdModalOpen = false;
  let viewMode = "3d"; // "3d" (default WebGL model), "2d", "split"
  let active3dInstance = null;
  let isParamsPanelOpen = true;
  let debounceTimer = null;

  const projState = projectStore.getState();

  function toKgs(value, unit) {
    const raw = Number(value) || 0;
    const u = unit || "kg/s";
    if (u === "kg/h") return raw / 3600.0;
    if (u === "Sm³/h" || u === "m3/h" || u === "Sm3/h" || u === "Nm³/h" || u === "Nm3/h") return (raw * 0.772) / 3600.0;
    if (u === "MMSCFD") return raw * 0.320;
    if (u === "MMSCMD") return (raw * 1e6 * 0.772) / 86400.0;
    return raw;
  }

  const initFlow = toKgs(
    projState?.inputs?.flow ?? projState?.inputs?.mass_flow ?? 120.0,
    projState?.inputs?.flow_unit || "kg/s"
  );
  const initPin = projState?.inputs?.p_in || 45.0;
  const initPout = projState?.inputs?.p_out || 75.0;

  let stationInputs = {
    mass_flow: Number(initFlow),
    p_in: Number(initPin),
    p_out: Number(initPout),
    comp_op_count: Number(projState?.inputs?.num_units || 0),
    cyclone_op_count: 0,
    filter_op_count: 0,
    cooler_bays_count: 0,
    pipe_material: "API 5L X70",
    design_factor_F: 0.50,
    pipe_standard: "BOTAŞ",
    psl_level: "PSL2",
  };

  let last3dState = null;
  function destroy3d() {
    if (active3dInstance) {
      if (typeof active3dInstance.getState === "function") {
        last3dState = active3dInstance.getState();
      }
      active3dInstance.destroy();
      active3dInstance = null;
    }
  }

  async function fetchStationData() {
    isLoading = true;
    render();
    const proj = projectStore.getState();
    try {
      const mergedInputs = {
        ...proj.inputs,
        mass_flow: stationInputs.mass_flow,
        p_in: stationInputs.p_in,
        p_out: stationInputs.p_out,
        pipe_material: stationInputs.pipe_material,
        design_factor_F: stationInputs.design_factor_F,
        pipe_standard: stationInputs.pipe_standard,
        psl_level: stationInputs.psl_level,
      };
      if (stationInputs.comp_op_count > 0) mergedInputs.comp_op_count = stationInputs.comp_op_count;
      else delete mergedInputs.comp_op_count;

      if (stationInputs.cyclone_op_count > 0) mergedInputs.cyclone_op_count = stationInputs.cyclone_op_count;
      else delete mergedInputs.cyclone_op_count;

      if (stationInputs.filter_op_count > 0) mergedInputs.filter_op_count = stationInputs.filter_op_count;
      else delete mergedInputs.filter_op_count;

      if (stationInputs.cooler_bays_count > 0) mergedInputs.cooler_bays_count = stationInputs.cooler_bays_count;
      else delete mergedInputs.cooler_bays_count;

      stationData = await api.post("/api/v1/calculations/station", {
        inputs: mergedInputs,
        design_results: proj.results,
      });
      const cachedAirCooler = projectStore.getState().modules?.air_cooler?.results;
      if (cachedAirCooler && stationData?.equipment_sizing?.air_coolers) {
        stationData.equipment_sizing.air_coolers.detailed_design = cachedAirCooler;
      }
      setStationData(stationData);
    } catch (err) {
      console.error("Station data fetch error:", err);
      showToast("İstasyon verisi alınamadı: " + err.message, "danger");
    } finally {
      isLoading = false;
      render();
    }
  }

  function triggerLiveUpdateDebounced() {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      fetchStationData();
    }, 380);
  }

  let lastResultsRef = projectStore.getState().results;
  const unsubscribeStore = projectStore.subscribe(() => {
    const s = projectStore.getState();
    if (s?.inputs && !isLoading) {
      const rawF = Number(s.inputs.flow || s.inputs.mass_flow || 0);
      const fKgs = toKgs(rawF, s.inputs.flow_unit || "kg/s");

      const pin = Number(s.inputs.p_in || 0);
      const pout = Number(s.inputs.p_out || 0);
      let changed = false;
      if (fKgs > 0 && Math.abs(fKgs - stationInputs.mass_flow) > 0.5) {
        stationInputs.mass_flow = fKgs;
        changed = true;
      }
      if (pin > 0 && Math.abs(pin - stationInputs.p_in) > 0.5) {
        stationInputs.p_in = pin;
        changed = true;
      }
      if (pout > 0 && Math.abs(pout - stationInputs.p_out) > 0.5) {
        stationInputs.p_out = pout;
        changed = true;
      }
      const nUnits = Number(s.inputs.num_units || 0);
      if (nUnits > 0 && nUnits !== stationInputs.comp_op_count) {
        stationInputs.comp_op_count = nUnits;
        changed = true;
      }
      if (s.results !== lastResultsRef) {
        lastResultsRef = s.results;
        changed = true;
      }
      if (changed) triggerLiveUpdateDebounced();
    }
  });

  function updateInspectorDrawer() {
    const inspMount = container.querySelector("#station-inspector-mount");
    if (!inspMount) return;
    if (!selectedEquip || !stationData) {
      inspMount.innerHTML = "";
      return;
    }
    const { equipment_sizing: eq, station_summary: sm } = stationData;
    inspMount.innerHTML = renderInspectorDrawer(selectedEquip, eq, sm);
    inspMount.querySelector("#btn-close-inspector")?.addEventListener("click", () => {
      selectedEquip = null;
      updateInspectorDrawer();
    });
    inspMount.querySelector("#btn-detailed-air-cooler")?.addEventListener("click", async (event) => {
      const btn = event.currentTarget;
      const detail = inspMount.querySelector("#air-cooler-detail");
      const originalText = btn.textContent;
      btn.disabled = true;
      btn.textContent = "Hesaplanıyor...";
      if (detail) detail.innerHTML = `<div style="font-size:11px;color:var(--color-text-secondary);">API 661 detaylı tasarım çalışıyor...</div>`;
      try {
        const inputs = projectStore.getState().inputs;
        const dischargeNode = (stationData.nodes || []).find(n => n.id === "N05_COMPRESSOR_DISCHARGE") || stationData.nodes?.[4] || {};
        const payload = {
          composition: inputs.gas_comp,
          mass_flow_kgs: stationInputs.mass_flow,
          p_in_bar: stationInputs.p_out,
          p_out_bar: Math.max(1.0, stationInputs.p_out - 0.4),
          t_in_c: dischargeNode.temp_c || stationData.equipment_sizing?.air_coolers?.inlet_temp_c || 80.0,
          t_out_c: stationData.equipment_sizing?.air_coolers?.outlet_temp_c || 45.0,
          air_in_c: 15.0,
          air_out_c: 35.0,
          auto_size: true,
        };
        const res = await api.post("/api/v1/modules/air_cooler/calculate", { payload });
        setModuleResult("air_cooler", res);
        if (stationData?.equipment_sizing?.air_coolers) {
          stationData.equipment_sizing.air_coolers.detailed_design = res.results || null;
          setStationData(stationData);
          mount3dView();
        }
        const r = res.results || {};
        if (detail) {
          detail.innerHTML = `
            <table class="kasp-table" style="font-size:10px;">
              <tr><td>Isıl Yük</td><td>${Number(r.heat_duty_kw || 0).toFixed(0)} kW</td></tr>
              <tr><td>Gerekli / Gerçek Alan</td><td>${Number(r.required_area_m2 || 0).toFixed(1)} / ${Number(r.actual_area_m2 || 0).toFixed(1)} m²</td></tr>
              <tr><td>Overdesign</td><td>%${Number(r.overdesign_pct || 0).toFixed(1)}</td></tr>
              <tr><td>Gaz ΔP</td><td>${Number(r.gas_pressure_drop_bar || 0).toFixed(3)} bar</td></tr>
              <tr><td>Fan Gücü</td><td>${Number(r.fan_power_kw || 0).toFixed(1)} kW</td></tr>
              <tr><td>Fan Uç Hızı</td><td>${Number(r.fan_tip_speed_ms || 0).toFixed(1)} m/s</td></tr>
              <tr><td>Geometri</td><td>${r.geometry?.tube_rows || '-'} sıra × ${r.geometry?.tubes_per_row || '-'} tüp</td></tr>
            </table>
            ${(res.warnings || []).length ? `<div style="font-size:10px;color:#f59e0b;margin-top:4px;">${res.warnings.join("<br>")}</div>` : ''}
          `;
        }
      } catch (err) {
        if (detail) detail.innerHTML = `<div style="font-size:11px;color:#ef4444;">Hata: ${err.message}</div>`;
      } finally {
        btn.disabled = false;
        btn.textContent = originalText;
      }
    });
  }

  function highlightSvgEquipment(key) {
    container.querySelectorAll(".station-equip-group").forEach((el) => {
      if (el.getAttribute("data-equip-key") === key) {
        el.classList.add("active-selected");
      } else {
        el.classList.remove("active-selected");
      }
    });
  }

  function mount3dView() {
    const mount = container.querySelector("#station-3d-mount");
    if (!mount || !stationData) {
      destroy3d();
      return;
    }
    const previousState = last3dState;
    destroy3d();
    try {
      active3dInstance = createStation3dView(mount, stationData, (equipKey) => {
        selectedEquip = equipKey;
        highlightSvgEquipment(equipKey);
        updateInspectorDrawer();
      }, { initialState: previousState || last3dState });
    } catch (err) {
      console.error("3D sahne oluşturulamadı:", err);
      active3dInstance = null;
      mount.innerHTML = `
        <div role="alert" style="height: 100%; min-height: 320px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 10px; padding: 24px; text-align: center; background: var(--color-surface); color: var(--color-text);">
          <div style="font-size: 32px;">⚠️</div>
          <div style="font-weight: 700;">3D görünüm başlatılamadı</div>
          <div style="font-size: 12px; color: var(--color-text-secondary); max-width: 420px;">
            Tarayıcınızda WebGL kullanılamıyor olabilir (donanım hızlandırma kapalı veya GPU sürücü hatası).
            2D P&amp;ID akış şeması tüm ekipman verisiyle çalışmaya devam eder.
          </div>
          <button type="button" class="btn btn-sm btn-primary" id="btn-3d-fallback-2d">📐 2D P&amp;ID Görünümüne Geç</button>
        </div>`;
      mount.querySelector("#btn-3d-fallback-2d")?.addEventListener("click", () => {
        viewMode = "2d";
        render();
      });
    }
    if (selectedEquip && active3dInstance) {
      active3dInstance.selectEquipment(selectedEquip);
      highlightSvgEquipment(selectedEquip);
    }
  }

  function render() {
    destroy3d();

    if (isLoading && !stationData) {
      container.innerHTML = `
        <div style="flex: 1; display: flex; align-items: center; justify-content: center; gap: 10px; color: var(--color-text-secondary); min-height: 400px;">
          ${icon("refreshCw", 24, "station-fan-blade")}
          <span>Kompresör İstasyonu Süreç Modeli Hesaplanıyor...</span>
        </div>
      `;
      return;
    }

    if (!stationData) {
      container.innerHTML = `
        <div style="flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 16px; min-height: 400px;">
          <p style="color: var(--color-text-secondary);">İstasyon modeli yükleniyor...</p>
          <button id="btn-refresh-station" class="btn btn-primary">
            ${icon("play", 14)}
            <span>İstasyon Modelini Başlat</span>
          </button>
        </div>
      `;
      container.querySelector("#btn-refresh-station")?.addEventListener("click", fetchStationData);
      return;
    }

    const { station_summary: sm, equipment_sizing: eq, nodes } = stationData;

    container.innerHTML = `
      <div style="flex: 1; padding: 16px 20px; overflow-y: auto; display: flex; flex-direction: column; gap: 14px;">
        
        <!-- Top Summary Cards -->
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 10px;">
          <div class="card" style="padding: 10px 14px;">
            <div style="font-size: 11px; color: var(--color-text-secondary); text-transform: uppercase; font-weight: 600;">
              İstasyon Toplam Debisi
            </div>
            <div style="font-size: 18px; font-weight: 700; color: var(--color-primary); margin-top: 4px;">
              ${sm.total_mass_flow_kgs} <span style="font-size: 12px; font-weight: 400;">kg/s</span>
            </div>
            <div style="font-size: 11px; color: var(--color-text-secondary); margin-top: 2px;">
              ${sm.volumetric_flow_mmscmd} MMSCMD • MW: ${sm.gas_mw} g/mol
            </div>
          </div>

          <div class="card" style="padding: 10px 14px;">
            <div style="font-size: 11px; color: var(--color-text-secondary); text-transform: uppercase; font-weight: 600;">
              İletim Basınç Oranı (PR)
            </div>
            <div style="font-size: 18px; font-weight: 700; color: #0ea5e9; margin-top: 4px;">
              ${sm.pressure_ratio} : 1
            </div>
            <div style="font-size: 11px; color: var(--color-text-secondary); margin-top: 2px;">
              ${sm.suction_pressure_bar} → ${sm.discharge_pressure_bar} bar(a)
            </div>
          </div>

          <div class="card" style="padding: 10px 14px;">
            <div style="font-size: 11px; color: var(--color-text-secondary); text-transform: uppercase; font-weight: 600;">
              Toplam Absorbe Güç
            </div>
            <div style="font-size: 18px; font-weight: 700; color: #f59e0b; margin-top: 4px;">
              ${sm.total_power_mw} <span style="font-size: 12px; font-weight: 400;">MW</span>
            </div>
            <div style="font-size: 11px; color: var(--color-text-secondary); margin-top: 2px;">
              ${(sm.total_power_kw * 1.34102 / 1000).toFixed(1)}k HP • ${eq.turbo_compressors.configuration}
            </div>
          </div>

          <div class="card" style="padding: 10px 14px;">
            <div style="font-size: 11px; color: var(--color-text-secondary); text-transform: uppercase; font-weight: 600;">
              Gaz Soğutucu Isıl Yükü
            </div>
            <div style="font-size: 18px; font-weight: 700; color: #10b981; margin-top: 4px;">
              ${sm.cooler_heat_duty_mw} <span style="font-size: 12px; font-weight: 400;">MWth</span>
            </div>
            <div style="font-size: 11px; color: var(--color-text-secondary); margin-top: 2px;">
              ${eq.air_coolers.bay_count} Fin-Fan Bay • Çıkış: ${eq.air_coolers.outlet_temp_c}°C
            </div>
          </div>

          <div class="card" style="padding: 10px 14px; display: flex; flex-direction: column; justify-content: space-between;">
            <div>
              <div style="font-size: 11px; color: var(--color-text-secondary); text-transform: uppercase; font-weight: 600;">
                İstasyon Dinamik Yapısı
              </div>
              <div style="font-size: 12px; font-weight: 600; color: var(--color-text); margin-top: 4px;">
                ${eq.cyclones.operating_count}+1 Siklon • ${eq.cartridge_filters.operating_count}+1 Filtre
              </div>
              <div style="font-size: 11px; color: var(--color-text-secondary);">
                ${eq.turbo_compressors.operating_count}+1 Tren • ${eq.compressor_building.area_m2} m² Bina
              </div>
            </div>
            <div style="display: flex; gap: 6px; margin-top: 6px;">
              <button id="btn-recalc-station" class="btn btn-sm btn-secondary" style="flex: 1; padding: 2px 6px; font-size: 11px;" title="Modeli Yeniden Hesapla">
                ${icon("refreshCw", 12)}
                <span>Hesapla</span>
              </button>
              <button id="btn-view-botas-pfd" class="btn btn-sm btn-primary" style="flex: 1.4; padding: 2px 6px; font-size: 11px;" title="BOTAŞ Adapazarı PFD & 3D CAD Referans Görsellerini İncele">
                ${icon("fileText", 12)}
                <span>PFD & 3D CAD</span>
              </button>
            </div>
          </div>
        </div>

        <!-- Live Station Operating Parameters & Dynamic Pipe Sizing Bar (Natural Gas Flow Calc) -->
        ${renderLiveParamsBar(stationInputs, isParamsPanelOpen)}

        <!-- View Mode Selector Bar & Quick Legend -->
        <div style="display: flex; justify-content: space-between; align-items: center; background: var(--color-surface); padding: 8px 14px; border-radius: var(--radius-md); border: 1px solid var(--color-border); flex-wrap: wrap; gap: 8px;">
          <div style="display: flex; gap: 6px; align-items: center;">
            <span style="font-size: 11px; font-weight: 700; color: var(--color-text-secondary); margin-right: 4px; text-transform: uppercase;">Görünüm:</span>
            <button id="btn-mode-3d" class="btn btn-sm ${viewMode === '3d' ? 'btn-primary' : 'btn-secondary'}" style="font-size: 12px; font-weight: 600; display: flex; align-items: center; gap: 6px;">
              <span>🧊 3D Dijital İkiz (CAD & LNG Mimari)</span>
            </button>
            <button id="btn-mode-2d" class="btn btn-sm ${viewMode === '2d' ? 'btn-primary' : 'btn-secondary'}" style="font-size: 12px; font-weight: 600; display: flex; align-items: center; gap: 6px;">
              <span>📐 2D P&ID Akış Şeması</span>
            </button>
            <button id="btn-mode-split" class="btn btn-sm ${viewMode === 'split' ? 'btn-primary' : 'btn-secondary'}" style="font-size: 12px; font-weight: 600; display: flex; align-items: center; gap: 6px;">
              <span>🔀 Yan Yana (Split 3D + 2D)</span>
            </button>
          </div>

          <div style="display: flex; gap: 10px; align-items: center; font-size: 11px; color: var(--color-text-secondary);">
            <span style="display: flex; align-items: center; gap: 4px;"><span style="display: inline-block; width: 10px; height: 3px; background: #e2d400;"></span> Proses Gaz Borulama</span>
            <span style="display: flex; align-items: center; gap: 4px;"><span style="display: inline-block; width: 10px; height: 3px; background: #00f0ff;"></span> Akış Yönü (→)</span>
            <span style="display: flex; align-items: center; gap: 4px;"><span style="display: inline-block; width: 10px; height: 3px; background: #0077be;"></span> Çelik Karkas</span>
            <span style="display: flex; align-items: center; gap: 4px;"><span style="display: inline-block; width: 10px; height: 3px; background: #8c735b;"></span> Ünite & Kontrol Binaları</span>
            <span style="display: flex; align-items: center; gap: 4px;"><span style="display: inline-block; width: 10px; height: 3px; background: #2b2e34;"></span> 7.0m Yol & Tel Çit</span>
          </div>
        </div>

        <!-- Main Visualizer Area -->
        <div id="station-main-viewer" style="position: relative;">
          ${
            viewMode === "3d"
              ? `<div id="station-3d-mount" style="width: 100%; height: clamp(440px, 74vh, 780px); border-radius: var(--radius-lg); overflow: hidden; border: 1px solid var(--color-border); background: #7aa0dc;"></div>`
              : viewMode === "2d"
              ? `<div class="station-canvas-container" style="min-height: 560px; position: relative;">
                   ${renderStationSvg(stationData)}
                 </div>`
              : `<div class="station-split-grid">
                   <div id="station-3d-mount" style="height: 100%; border-radius: var(--radius-lg); overflow: hidden; border: 1px solid var(--color-border); background: #7aa0dc;"></div>
                   <div class="station-canvas-container" style="height: 100%; overflow: auto; position: relative;">
                     ${renderStationSvg(stationData)}
                   </div>
                 </div>`
          }

          <!-- Equipment Inspector Drawer Container -->
          <div id="station-inspector-mount">
            ${selectedEquip ? renderInspectorDrawer(selectedEquip, eq, sm) : ""}
          </div>
        </div>

        <!-- 8-Nodal Telemetry Table -->
        <div class="card" style="padding: 12px;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <div style="font-size: 13px; font-weight: 700; display: flex; align-items: center; gap: 6px;">
              ${icon("activity", 14, "text-primary")}
              <span>BOTAŞ Adapazarı İstasyon Süreç Düğümleri ve Termodinamik Durum Matrisi</span>
            </div>
            <span style="font-size: 11px; color: var(--color-text-secondary);">Doküman No: 0-NGTL0-CS-I-001-4000</span>
          </div>

          <table class="kasp-table" style="font-size: 11px;">
            <thead>
              <tr>
                <th>Düğüm Kodu</th>
                <th>Açıklama / Süreç Konumu</th>
                <th style="text-align: right;">Basınç (bar a)</th>
                <th style="text-align: right;">Sıcaklık (°C)</th>
                <th style="text-align: right;">Kütlesel Debi (kg/s)</th>
                <th>Akışkan Fazı</th>
                <th>Süreç Durumu</th>
              </tr>
            </thead>
            <tbody>
              ${nodes.map(n => `
                <tr>
                  <td style="font-family: var(--font-mono); font-weight: 700; color: ${n.color};">${n.id}</td>
                  <td style="font-weight: 600;">${n.name}</td>
                  <td style="text-align: right; font-family: var(--font-mono); font-weight: 600;">${n.pressure_bar.toFixed(2)}</td>
                  <td style="text-align: right; font-family: var(--font-mono);">${n.temp_c.toFixed(1)}</td>
                  <td style="text-align: right; font-family: var(--font-mono);">${n.flow_kgs.toFixed(1)}</td>
                  <td><span class="badge badge-neutral" style="font-size: 10px;">${n.phase}</span></td>
                  <td style="color: var(--color-text-secondary); font-size: 11px;">${n.state_desc}</td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        </div>

        <!-- ASME B36.10M / API 5L Natural Gas Flow Calc Pipe Sizing Matrix Table -->
        ${renderPipeSizingTable(stationData.station_piping)}

        <!-- BOTAŞ Adapazarı PFD Lightbox Modal -->
        ${isPfdModalOpen ? renderBotasPfdModal() : ""}

      </div>
    `;

    // Mode switching handlers
    container.querySelector("#btn-mode-3d")?.addEventListener("click", () => {
      if (viewMode !== "3d") {
        viewMode = "3d";
        render();
      }
    });

    container.querySelector("#btn-mode-2d")?.addEventListener("click", () => {
      if (viewMode !== "2d") {
        viewMode = "2d";
        render();
      }
    });

    container.querySelector("#btn-mode-split")?.addEventListener("click", () => {
      if (viewMode !== "split") {
        viewMode = "split";
        render();
      }
    });

    // Mount 3D scene if applicable
    if (viewMode === "3d" || viewMode === "split") {
      mount3dView();
    }

    // Inspector Close handler
    container.querySelector("#btn-close-inspector")?.addEventListener("click", () => {
      selectedEquip = null;
      updateInspectorDrawer();
    });

    // Event Bindings
    container.querySelector("#btn-recalc-station")?.addEventListener("click", () => {
      const flowInp = container.querySelector("#station-input-mass-flow");
      if (flowInp && !isNaN(parseFloat(flowInp.value))) stationInputs.mass_flow = parseFloat(flowInp.value);
      const pinInp = container.querySelector("#station-input-pin");
      if (pinInp && !isNaN(parseFloat(pinInp.value))) stationInputs.p_in = parseFloat(pinInp.value);
      const poutInp = container.querySelector("#station-input-pout");
      if (poutInp && !isNaN(parseFloat(poutInp.value))) stationInputs.p_out = parseFloat(poutInp.value);
      fetchStationData();
    });

    // Live Parameters Panel Event Bindings
    container.querySelector("#btn-toggle-params-panel")?.addEventListener("click", () => {
      isParamsPanelOpen = !isParamsPanelOpen;
      render();
    });

    const flowSlider = container.querySelector("#slider-param-flow");
    const flowInput = container.querySelector("#input-param-flow");
    flowSlider?.addEventListener("input", (e) => {
      const val = Number(e.target.value);
      stationInputs.mass_flow = val;
      if (flowInput) flowInput.value = val;
      triggerLiveUpdateDebounced();
    });
    flowInput?.addEventListener("change", (e) => {
      const val = Number(e.target.value);
      stationInputs.mass_flow = val;
      if (flowSlider) flowSlider.value = val;
      triggerLiveUpdateDebounced();
    });

    const pinSlider = container.querySelector("#slider-param-pin");
    const pinInput = container.querySelector("#input-param-pin");
    pinSlider?.addEventListener("input", (e) => {
      const val = Number(e.target.value);
      stationInputs.p_in = val;
      if (pinInput) pinInput.value = val;
      if (stationInputs.p_out <= val) {
        stationInputs.p_out = Math.round(val * 1.5);
        const poutInput = container.querySelector("#input-param-pout");
        const poutSlider = container.querySelector("#slider-param-pout");
        if (poutInput) poutInput.value = stationInputs.p_out;
        if (poutSlider) poutSlider.value = stationInputs.p_out;
      }
      triggerLiveUpdateDebounced();
    });
    pinInput?.addEventListener("change", (e) => {
      const val = Number(e.target.value);
      stationInputs.p_in = val;
      if (pinSlider) pinSlider.value = val;
      triggerLiveUpdateDebounced();
    });

    const poutSlider = container.querySelector("#slider-param-pout");
    const poutInput = container.querySelector("#input-param-pout");
    poutSlider?.addEventListener("input", (e) => {
      const val = Number(e.target.value);
      stationInputs.p_out = val;
      if (poutInput) poutInput.value = val;
      triggerLiveUpdateDebounced();
    });
    poutInput?.addEventListener("change", (e) => {
      const val = Number(e.target.value);
      stationInputs.p_out = val;
      if (poutSlider) poutSlider.value = val;
      triggerLiveUpdateDebounced();
    });

    container.querySelector("#select-param-comps")?.addEventListener("change", (e) => {
      const v = parseInt(e.target.value, 10);
      stationInputs.comp_op_count = v;
      if (v > 0) {
        projectStore.setState(s => ({
          inputs: { ...s.inputs, num_units: v }
        }));
      }
      fetchStationData();
    });

    container.querySelector("#select-param-cyclones")?.addEventListener("change", (e) => {
      const v = parseInt(e.target.value, 10);
      stationInputs.cyclone_op_count = v;
      stationInputs.filter_op_count = v;
      fetchStationData();
    });

    container.querySelector("#select-param-coolers")?.addEventListener("change", (e) => {
      stationInputs.cooler_bays_count = parseInt(e.target.value, 10);
      fetchStationData();
    });

    container.querySelector("#select-param-material")?.addEventListener("change", (e) => {
      stationInputs.pipe_material = e.target.value;
      fetchStationData();
    });

    container.querySelector("#select-param-standard")?.addEventListener("change", (e) => {
      stationInputs.pipe_standard = e.target.value;
      fetchStationData();
    });

    container.querySelector("#select-param-psl")?.addEventListener("change", (e) => {
      stationInputs.psl_level = e.target.value;
      fetchStationData();
    });

    container.querySelector("#btn-apply-station-params")?.addEventListener("click", () => {
      fetchStationData();
    });

    container.querySelector("#btn-reset-station-params")?.addEventListener("click", () => {
      stationInputs = {
        mass_flow: 120.0,
        p_in: 45.0,
        p_out: 75.0,
        comp_op_count: 0,
        cyclone_op_count: 0,
        filter_op_count: 0,
        cooler_bays_count: 0,
        pipe_material: "API 5L X70",
        design_factor_F: 0.50,
        pipe_standard: "BOTAŞ",
        psl_level: "PSL2",
      };
      fetchStationData();
    });

    container.querySelector("#btn-view-botas-pfd")?.addEventListener("click", () => {
      isPfdModalOpen = true;
      render();
    });

    container.querySelector("#btn-close-pfd-modal")?.addEventListener("click", () => {
      isPfdModalOpen = false;
      render();
    });

    container.querySelector("#btn-footer-close-pfd-modal")?.addEventListener("click", () => {
      isPfdModalOpen = false;
      render();
    });

    container.querySelector("#botas-pfd-backdrop")?.addEventListener("click", (e) => {
      if (e.target.id === "botas-pfd-backdrop") {
        isPfdModalOpen = false;
        render();
      }
    });

    // Inspector & 3D Sync Click Handlers on SVG elements (for 2D / split view)
    container.querySelectorAll(".station-equip-group").forEach(el => {
      el.addEventListener("click", () => {
        const equipKey = el.getAttribute("data-equip-key");
        if (equipKey) {
          selectedEquip = equipKey;
          highlightSvgEquipment(equipKey);
          updateInspectorDrawer();
          if (active3dInstance) {
            active3dInstance.selectEquipment(equipKey);
          }
        }
      });
    });
  }

  // Auto-fetch on mount
  fetchStationData();
}

/**
 * Helper to render an ISA 5.1 compliant instrument bubble with live DCS readout.
 */
function renderIsaBubble(cx, cy, tapX, tapY, tagCode, loopNum, valStr, unitStr, color = "#38bdf8") {
  const isTapBelow = tapY >= cy;
  const leadStartY = isTapBelow ? cy + 13 : cy - 13;
  const pillY = isTapBelow ? cy - 27 : cy + 15;

  return `
    <g class="isa-instrument-group" style="cursor: default;">
      <title>${tagCode}-${loopNum}: ${valStr} ${unitStr}</title>
      <!-- Instrument Process Tap Lead Line -->
      <line x1="${cx}" y1="${leadStartY}" x2="${tapX}" y2="${tapY}" stroke="${color}" stroke-width="1.2" stroke-dasharray="2 2" opacity="0.85" />
      <circle cx="${tapX}" cy="${tapY}" r="2.5" fill="${color}" />

      <!-- ISA 5.1 Instrument Circle (Field / DCS Mounted) -->
      <circle cx="${cx}" cy="${cy}" r="13" fill="#0b1120" stroke="${color}" stroke-width="1.6" />
      <line x1="${cx - 13}" y1="${cy}" x2="${cx + 13}" y2="${cy}" stroke="${color}" stroke-width="1" opacity="0.5" />
      
      <!-- ISA Functional Tag & Loop Number -->
      <text x="${cx}" y="${cy - 3}" fill="${color}" font-size="7.5" font-weight="700" font-family="var(--font-mono)" text-anchor="middle">${tagCode}</text>
      <text x="${cx}" y="${cy + 8}" fill="#94a3b8" font-size="6.5" font-weight="600" font-family="var(--font-mono)" text-anchor="middle">${loopNum}</text>

      <!-- DCS Readout Pill -->
      <g transform="translate(${cx - 24}, ${pillY})">
        <rect width="48" height="12" rx="3" fill="#030712" stroke="${color}" stroke-width="0.8" opacity="0.95" />
        <text x="24" y="9" fill="#f8fafc" font-size="7" font-weight="600" font-family="var(--font-mono)" text-anchor="middle">${valStr} ${unitStr}</text>
      </g>
    </g>
  `;
}

/**
 * Renders high-fidelity P&ID SVG with dynamic units, cyclones, filters, coolers, and animated flow.
 */
function renderStationSvg(data) {
  const { equipment_sizing: eq, station_summary: sm, nodes = [] } = data;
  const numCyclones = eq.cyclones.operating_count + 1;
  const numFilters = eq.cartridge_filters.operating_count + 1;
  const numComps = eq.turbo_compressors.operating_count + 1;
  const numCoolers = eq.air_coolers.bay_count;
  const pLines = data.station_piping?.lines || {};
  const npsLabel = (key, fallback) => (pLines[key]?.nominal_size_in || fallback).replace('"', '');
  const suctionNps = npsLabel("suction_header", "48");
  const dischargeNps = npsLabel("discharge_header", `${suctionNps}"`);
  const recycleNps = npsLabel("station_recycle", "48");
  const compSuctionNps = npsLabel("comp_suction_branch", "30");
  const suctionVal = parseInt(suctionNps, 10) || 48;
  const dischargeVal = parseInt(dischargeNps, 10) || suctionVal;
  const pigReceiverBarrel = `${suctionVal + 8}"x${suctionVal}"`;
  const pigLauncherBarrel = `${dischargeVal + 8}"x${dischargeVal}"`;

  // Extract nodal values safely
  const n1Temp = nodes[0]?.temp_c ? nodes[0].temp_c.toFixed(1) : "20.0";
  const n4Pres = nodes[3]?.pressure_bar ? nodes[3].pressure_bar.toFixed(1) : "44.6";
  const n5Temp = nodes[4]?.temp_c ? nodes[4].temp_c.toFixed(1) : "43.8";
  const n7Pres = nodes[6]?.pressure_bar ? nodes[6].pressure_bar.toFixed(1) : "74.6";
  const n8Pres = nodes[7]?.pressure_bar ? nodes[7].pressure_bar.toFixed(1) : "74.6";

  return `
    <svg viewBox="0 0 1180 580" style="width: 100%; height: auto; display: block;" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <style>
          .station-equip-group {
            cursor: pointer;
            transition: filter 0.25s ease, transform 0.2s ease;
          }
          .station-equip-group:hover rect,
          .station-equip-group:hover polygon,
          .station-equip-group:hover circle:not(.station-equip-no-glow) {
            filter: drop-shadow(0 0 6px rgba(56, 189, 248, 0.75));
          }
          .station-equip-group.active-selected rect,
          .station-equip-group.active-selected polygon,
          .station-equip-group.active-selected circle:not(.station-equip-no-glow) {
            stroke: #fbbf24 !important;
            stroke-width: 3px !important;
            filter: drop-shadow(0 0 12px rgba(251, 191, 36, 0.95)) !important;
          }
          .isa-instrument-group {
            transition: transform 0.2s ease, opacity 0.2s ease;
          }
          .isa-instrument-group:hover {
            filter: drop-shadow(0 0 6px #38bdf8);
          }
        </style>

        <!-- Gradients -->
        <linearGradient id="grad-suction" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stop-color="#38bdf8" />
          <stop offset="100%" stop-color="#0284c7" />
        </linearGradient>
        <linearGradient id="grad-discharge" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stop-color="#f87171" />
          <stop offset="100%" stop-color="#dc2626" />
        </linearGradient>
        <linearGradient id="grad-cooled" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stop-color="#34d399" />
          <stop offset="100%" stop-color="#059669" />
        </linearGradient>
        <linearGradient id="grad-shelter" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stop-color="#1e293b" stop-opacity="0.15" />
          <stop offset="100%" stop-color="#0f172a" stop-opacity="0.3" />
        </linearGradient>

        <!-- Valve Marker / Symbols -->
        <marker id="arrow-blue" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="#0ea5e9" />
        </marker>
        <marker id="arrow-red" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="#ef4444" />
        </marker>
        <marker id="arrow-green" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="#10b981" />
        </marker>
        <marker id="arrow-amber" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="#f59e0b" />
        </marker>
      </defs>

      <!-- Grid Background Lines -->
      <pattern id="station-grid" width="40" height="40" patternUnits="userSpaceOnUse">
        <path d="M 40 0 L 0 0 0 40" fill="none" stroke="currentColor" stroke-opacity="0.05" stroke-width="1" />
      </pattern>
      <rect width="1180" height="580" fill="url(#station-grid)" />

      <!-- ══════════════════ 1. MAINLINE INLET & PIG RECEIVER (X: 30 - 150) ══════════════════ -->
      <g class="station-equip-group" data-equip-key="pig_receiver">
        <!-- Mainline Pipe Incoming -->
        <line x1="20" y1="210" x2="80" y2="210" stroke="#0ea5e9" stroke-width="8" stroke-linecap="round" />
        <line x1="20" y1="210" x2="80" y2="210" stroke="#bae6fd" stroke-width="3" class="station-flow-fast" />
        <text x="25" y="195" fill="#0ea5e9" font-size="10" font-weight="700">${suctionNps}" BATI KARADENİZ</text>
        <text x="25" y="232" fill="var(--color-text-secondary)" font-size="9">${sm.suction_pressure_bar} bar</text>

        <!-- Pig Receiver Vessel (Horizontal Capsule) -->
        <rect x="75" y="185" width="65" height="50" rx="14" fill="#334155" stroke="#0ea5e9" stroke-width="2" />
        <line x1="140" y1="185" x2="140" y2="235" stroke="#f59e0b" stroke-width="3" />
        <path d="M 140 195 L 147 210 L 140 225 Z" fill="#f59e0b" />
        <text x="107" y="212" fill="#ffffff" font-size="8" font-weight="700" text-anchor="middle">PIG-R</text>
        <text x="107" y="224" fill="#38bdf8" font-size="7" font-weight="600" text-anchor="middle">${pigReceiverBarrel}</text>
        <text x="107" y="248" fill="var(--color-text-secondary)" font-size="8" text-anchor="middle">Pig Alıcı Kovan</text>
      </g>

      <!-- Suction ISA 5.1 Field Instruments -->
      ${renderIsaBubble(45, 155, 45, 210, "PT", "101", sm.suction_pressure_bar.toFixed(1), "bar", "#38bdf8")}
      ${renderIsaBubble(85, 140, 85, 185, "TT", "101", n1Temp, "°C", "#38bdf8")}
      ${renderIsaBubble(135, 140, 135, 185, "FT", "101", sm.total_mass_flow_kgs.toFixed(1), "kg/s", "#38bdf8")}

      <!-- Tie-in line from Pig Receiver to Suction Header -->
      <path d="M 107 185 L 107 120 L 180 120" fill="none" stroke="#0ea5e9" stroke-width="6" stroke-linejoin="round" />
      <path d="M 107 185 L 107 120 L 180 120" fill="none" stroke="#ffffff" stroke-width="2" class="station-flow-line" />

      <!-- ══════════════════ 2. 48" SUCTION HEADER & DYNAMIC CYCLONES (X: 180 - 280) ══════════════════ -->
      <!-- Suction Header Manifold Bar -->
      <rect x="180" y="112" width="16" height="320" rx="6" fill="#0284c7" stroke="#38bdf8" stroke-width="2" />
      <text x="188" y="98" fill="#0284c7" font-size="9" font-weight="700" text-anchor="middle">${suctionNps}" SUCTION HEADER</text>

      <!-- Separation Differential Pressure & Suction Transmitters -->
      ${renderIsaBubble(240, 65, 240, 112, "PDT", "101", "0.20", "Δbar", "#0ea5e9")}
      ${renderIsaBubble(322, 65, 322, 130, "PDT", "102", "0.20", "Δbar", "#2563eb")}
      ${renderIsaBubble(367, 85, 367, 140, "PT", "201", n4Pres, "bar", "#1d4ed8")}

      <!-- Dynamic Cyclone Separators -->
      ${renderDynamicCyclonesSvg(numCyclones, eq.cyclones)}

      <!-- Intermediate Header linking Cyclones to Filters -->
      <rect x="270" y="130" width="12" height="280" rx="4" fill="#2563eb" stroke="#60a5fa" stroke-width="1.5" />

      <!-- Dynamic Cartridge Filters -->
      ${renderDynamicFiltersSvg(numFilters, eq.cartridge_filters)}

      <!-- Filtered Header into Compressor Suction -->
      <rect x="360" y="140" width="14" height="260" rx="4" fill="#1d4ed8" stroke="#93c5fd" stroke-width="1.5" />
      <text x="367" y="128" fill="#1d4ed8" font-size="8" font-weight="700" text-anchor="middle">${compSuctionNps}" COMP. SUCTION</text>

      <!-- ══════════════════ CONDENSATE TANK & DRAIN LINES (BOTAŞ PFD Note 14 & 15) ══════════════════ -->
      <g class="station-equip-group" data-equip-key="condensate_system">
        <!-- Horizontal Condensate Tank -->
        <rect x="215" y="465" width="145" height="36" rx="10" fill="#1e293b" stroke="#92400e" stroke-width="2" />
        <text x="287" y="485" fill="#fef3c7" font-size="9" font-weight="700" text-anchor="middle">KONDENSAT TANKI (Note 14)</text>
        <text x="287" y="496" fill="#fbbf24" font-size="7" text-anchor="middle">LCV Seviye Kontrol Drenajı • ${eq.condensate_system?.collection_tank_volume_m3 || 15} m³</text>
        
        <!-- Flame Arrester Vent Stack -->
        <line x1="345" y1="465" x2="345" y2="435" stroke="#92400e" stroke-width="2" />
        <polygon points="340,435 350,435 345,425" fill="#92400e" />
        <text x="345" y="420" fill="#92400e" font-size="7" font-weight="700" text-anchor="middle">VENT [F]</text>
      </g>

      <!-- ══════════════════ 3. COMPRESSOR SHELTER & TURBO-COMPRESSOR TRAINS (X: 400 - 740) ══════════════════ -->
      <g class="station-equip-group" data-equip-key="compressor_building">
        <!-- Shelter Outline -->
        <rect x="400" y="110" width="340" height="340" rx="10" fill="url(#grad-shelter)" stroke="#eab308" stroke-width="2" stroke-dasharray="6 3" />
        <!-- Crane beam -->
        <line x1="410" y1="130" x2="730" y2="130" stroke="#ca8a04" stroke-width="3" />
        <text x="570" y="126" fill="#ca8a04" font-size="10" font-weight="700" text-anchor="middle">
          ÜNİTE BİNASI (Compressor Shelter) • 15 Ton Vinç • ${eq.compressor_building.area_m2} m²
        </text>
      </g>

      <!-- Dynamic Turbo-Compressor Packages Inside Shelter -->
      ${renderDynamicCompressorTrainsSvg(numComps, eq.turbo_compressors)}

      <!-- ══════════════════ 4. 48" DISCHARGE HEADER (X: 750 - 775) ══════════════════ -->
      <!-- Common Discharge Header Manifold -->
      <rect x="750" y="130" width="16" height="300" rx="6" fill="#b91c1c" stroke="#f87171" stroke-width="2" />
      <text x="758" y="118" fill="#ef4444" font-size="9" font-weight="700" text-anchor="middle">${dischargeNps}" DISCHARGE HEADER</text>
      <text x="758" y="445" fill="#ef4444" font-size="9" text-anchor="middle">${sm.discharge_pressure_bar} bar</text>

      <!-- Discharge Header Transmitters -->
      ${renderIsaBubble(740, 75, 750, 130, "PT", "202", sm.discharge_pressure_bar.toFixed(1), "bar", "#ef4444")}
      ${renderIsaBubble(790, 75, 790, 260, "TT", "202", n5Temp, "°C", "#ef4444")}

      <!-- ══════════════════ 5. ANTI-SURGE / RECYCLE HEADER (Note 13) ══════════════════ -->
      <g class="station-equip-group" data-equip-key="station_recycle">
        <!-- Recycle pipe running top from X=758 around shelter to X=188 -->
        <path d="M 758 130 L 758 60 L 188 60 L 188 112" fill="none" stroke="#f97316" stroke-width="5" stroke-linejoin="round" />
        <path d="M 758 130 L 758 60 L 188 60 L 188 112" fill="none" stroke="#ffffff" stroke-width="1.5" class="station-flow-line" />
        
        <!-- Station Recycle Control Valve (PCV) -->
        <circle cx="470" cy="60" r="14" fill="#334155" stroke="#f97316" stroke-width="2" />
        <path d="M 462 53 L 478 67 M 478 53 L 462 67" stroke="#f97316" stroke-width="2" />
        <rect x="466" y="40" width="8" height="8" fill="#f97316" />
        <text x="470" y="32" fill="#f97316" font-size="9" font-weight="700" text-anchor="middle">${recycleNps}" ANTI-SURGE / RECYCLE HEADER</text>
      </g>

      <!-- Main Header pipe to Air Coolers -->
      <path d="M 766 260 L 810 260" fill="none" stroke="#ef4444" stroke-width="8" />
      <path d="M 766 260 L 810 260" fill="none" stroke="#fecaca" stroke-width="3" class="station-flow-fast" />

      <!-- ══════════════════ 6. FIN-FAN AIR COOLERS & GAS COOLER BY-PASS (Note 17) ══════════════════ -->
      ${renderDynamicCoolersSvg(numCoolers, eq.air_coolers)}

      <!-- GAS COOLER BY-PASS LINE WITH TCV (BOTAŞ PFD Note 17) -->
      <g class="station-equip-group" data-equip-key="cooler_bypass">
        <path d="M 790 260 L 790 350 L 965 350 L 965 260" fill="none" stroke="#f59e0b" stroke-width="3" stroke-linejoin="round" />
        <path d="M 790 260 L 790 350 L 965 350 L 965 260" fill="none" stroke="#ffffff" stroke-width="1" class="station-flow-line" />
        
        <!-- TCV Valve Symbol -->
        <circle cx="875" cy="350" r="10" fill="#334155" stroke="#f59e0b" stroke-width="1.5" />
        <path d="M 870 345 L 880 355 M 880 345 L 870 355" stroke="#f59e0b" stroke-width="1.5" />
        <rect x="872" y="337" width="6" height="6" fill="#f59e0b" />
        <text x="875" y="372" fill="#f59e0b" font-size="8" font-weight="700" text-anchor="middle">GAS COOLER BY-PASS (TCV - Note 17)</text>
      </g>
      ${renderIsaBubble(875, 412, 875, 360, "TCV", "101", "By-Pass", "%0", "#f59e0b")}

      <!-- Cooled Gas Pipe leaving coolers -->
      <path d="M 940 260 L 980 260" fill="none" stroke="#10b981" stroke-width="8" />
      <path d="M 940 260 L 980 260" fill="none" stroke="#a7f3d0" stroke-width="3" class="station-flow-fast" />

      <!-- Air Cooler Transmitters -->
      ${renderIsaBubble(965, 180, 965, 260, "TT", "301", eq.air_coolers.outlet_temp_c.toFixed(1), "°C", "#10b981")}
      ${renderIsaBubble(1010, 195, 980, 260, "PT", "301", n7Pres, "bar", "#10b981")}

      <!-- ══════════════════ 7. SAFETY RELIEF (PSV & BLOWDOWN BDV) (X: 980 - 1030) ══════════════════ -->
      <g class="station-equip-group" data-equip-key="safety_relief">
        <!-- Relief stub vertical up -->
        <path d="M 990 260 L 990 170" fill="none" stroke="#ef4444" stroke-width="4" />
        
        <!-- PSV Symbol -->
        <polygon points="980,185 1000,185 990,170" fill="#dc2626" stroke="#ffffff" stroke-width="1.5" />
        <circle cx="990" cy="162" r="7" fill="#f87171" />
        <line x1="990" y1="155" x2="990" y2="120" stroke="#dc2626" stroke-width="3" />
        <line x1="980" y1="120" x2="1000" y2="120" stroke="#dc2626" stroke-width="3" />
        <text x="990" y="110" fill="#ef4444" font-size="8" font-weight="700" text-anchor="middle">STATION RELIEF (PSV)</text>
        <text x="990" y="145" fill="var(--color-text-secondary)" font-size="8" text-anchor="middle">${eq.safety_relief_and_blowdown.psv_set_pressure_bar} bar</text>

        <!-- Blowdown BDV stub vertical down -->
        <path d="M 990 260 L 990 350" fill="none" stroke="#e11d48" stroke-width="4" />
        <circle cx="990" cy="350" r="10" fill="#334155" stroke="#e11d48" stroke-width="2" />
        <path d="M 984 345 L 996 355 M 996 345 L 984 355" stroke="#e11d48" stroke-width="2" />
        <rect x="987" y="360" width="6" height="8" fill="#e11d48" />
        <text x="990" y="380" fill="#e11d48" font-size="8" font-weight="700" text-anchor="middle">BLOWDOWN (BDV)</text>
        <text x="990" y="392" fill="var(--color-text-secondary)" font-size="7" text-anchor="middle">Emergency Vent &lt; 15 dk</text>
      </g>
      ${renderIsaBubble(1040, 125, 990, 162, "PSV", "101", eq.safety_relief_and_blowdown.psv_set_pressure_bar.toFixed(1), "bar", "#dc2626")}
      ${renderIsaBubble(1040, 350, 990, 350, "BDV", "101", "ESD", "Vent", "#e11d48")}

      <!-- ══════════════════ 8. PIG LAUNCHER & MAINLINE DISCHARGE (X: 1040 - 1160) ══════════════════ -->
      <g class="station-equip-group" data-equip-key="pig_launcher">
        <line x1="990" y1="260" x2="1050" y2="260" stroke="#10b981" stroke-width="8" />
        
        <!-- Pig Launcher Barrel -->
        <rect x="1050" y="235" width="60" height="50" rx="14" fill="#334155" stroke="#10b981" stroke-width="2" />
        <line x1="1050" y1="235" x2="1050" y2="285" stroke="#10b981" stroke-width="3" />
        <path d="M 1050 245 L 1043 260 L 1050 275 Z" fill="#10b981" />
        <text x="1080" y="260" fill="#ffffff" font-size="8" font-weight="700" text-anchor="middle">PIG-L</text>
        <text x="1080" y="272" fill="#6ee7b7" font-size="7" font-weight="600" text-anchor="middle">${pigLauncherBarrel}</text>
        <text x="1080" y="298" fill="var(--color-text-secondary)" font-size="8" text-anchor="middle">Pig Atıcı Kovan</text>

        <!-- Mainline Out -->
        <line x1="1110" y1="260" x2="1170" y2="260" stroke="#10b981" stroke-width="8" stroke-linecap="round" />
        <line x1="1110" y1="260" x2="1170" y2="260" stroke="#ecfdf5" stroke-width="3" class="station-flow-fast" />
        <text x="1165" y="245" fill="#10b981" font-size="10" font-weight="700" text-anchor="end">${dischargeNps}" ANA HAT BASMA</text>
        <text x="1165" y="280" fill="var(--color-text-secondary)" font-size="9" text-anchor="end">${eq.air_coolers.outlet_temp_c}°C • ${n8Pres} bar</text>
      </g>

      <!-- Mainline Discharge Transmitters -->
      ${renderIsaBubble(1090, 180, 1090, 260, "PT", "401", n8Pres, "bar", "#10b981")}
      ${renderIsaBubble(1140, 180, 1140, 260, "FT", "401", sm.total_mass_flow_kgs.toFixed(1), "kg/s", "#10b981")}

    </svg>
  `;
}

/**
 * Renders dynamic Cyclone Separators with LCV drain lines to condensate tank.
 */
function renderDynamicCyclonesSvg(count, info) {
  const startY = 140;
  const spacing = count > 1 ? 260 / (count - 1) : 0;

  let svg = `<g class="station-equip-group" data-equip-key="cyclones">`;
  for (let i = 0; i < count; i++) {
    const y = count === 1 ? 270 : startY + i * spacing;
    const isSpare = i === count - 1;

    svg += `
      <!-- Header to Cyclone Line -->
      <path d="M 196 ${y} L 225 ${y}" fill="none" stroke="#0ea5e9" stroke-width="4" />
      <path d="M 196 ${y} L 225 ${y}" fill="none" stroke="#bae6fd" stroke-width="1.5" class="station-flow-line" />

      <!-- Cyclone Vertical Vessel Body with cone bottom -->
      <rect x="225" y="${y - 20}" width="24" height="32" rx="4" fill="#1e293b" stroke="${isSpare ? '#94a3b8' : '#0ea5e9'}" stroke-width="1.5" />
      <polygon points="225,${y + 12} 249,${y + 12} 237,${y + 26}" fill="#1e293b" stroke="${isSpare ? '#94a3b8' : '#0ea5e9'}" stroke-width="1.5" />
      
      <!-- Liquid drain LCV valve & route to Condensate Tank -->
      <line x1="237" y1="${y + 26}" x2="237" y2="${y + 40}" stroke="#92400e" stroke-width="1.5" />
      <circle cx="237" cy="${y + 40}" r="3" fill="#b45309" />
      <path d="M 237 ${y + 43} L 237 465" fill="none" stroke="#92400e" stroke-width="1" stroke-dasharray="2 2" />

      <!-- Swirl icon inside -->
      <path d="M 233 ${y - 8} Q 237 ${y - 12} 241 ${y - 8} Q 237 ${y - 4} 233 ${y}" fill="none" stroke="#38bdf8" stroke-width="1" />
      
      <text x="237" y="${y + 2}" fill="#ffffff" font-size="7" font-weight="700" text-anchor="middle">S-${i + 1}</text>
      <text x="237" y="${y + 54}" fill="var(--color-text-secondary)" font-size="7" text-anchor="middle">
        ${isSpare ? 'Yedek' : `${info.flow_per_unit_kgs} k/s`}
      </text>

      <!-- Cyclone to Intermediate Header Line -->
      <path d="M 249 ${y} L 270 ${y}" fill="none" stroke="#2563eb" stroke-width="4" />
    `;
  }
  svg += `
    <text x="237" y="115" fill="#0ea5e9" font-size="8" font-weight="700" text-anchor="middle">SİKLON SEPERATÖRLER (${count})</text>
  </g>`;
  return svg;
}

/**
 * Renders dynamic Cartridge Filters with LCV drain lines to condensate tank.
 */
function renderDynamicFiltersSvg(count, info) {
  const startY = 150;
  const spacing = count > 1 ? 240 / (count - 1) : 0;

  let svg = `<g class="station-equip-group" data-equip-key="cartridge_filters">`;
  for (let i = 0; i < count; i++) {
    const y = count === 1 ? 270 : startY + i * spacing;
    const isSpare = i === count - 1;

    svg += `
      <!-- Inter-header to Filter Line -->
      <path d="M 282 ${y} L 305 ${y}" fill="none" stroke="#2563eb" stroke-width="4" />

      <!-- Filter Vessel (Horizontal Capsule with internal hatched cartridge) -->
      <rect x="305" y="${y - 16}" width="34" height="32" rx="8" fill="#1e293b" stroke="${isSpare ? '#94a3b8' : '#2563eb'}" stroke-width="1.5" />
      <line x1="316" y1="${y - 12}" x2="316" y2="${y + 12}" stroke="#60a5fa" stroke-width="1.5" stroke-dasharray="2 2" />
      <line x1="324" y1="${y - 12}" x2="324" y2="${y + 12}" stroke="#60a5fa" stroke-width="1.5" stroke-dasharray="2 2" />

      <!-- Bottom drain line to condensate tank -->
      <path d="M 322 ${y + 16} L 322 465" fill="none" stroke="#92400e" stroke-width="1" stroke-dasharray="2 2" />

      <text x="322" y="${y + 3}" fill="#ffffff" font-size="7" font-weight="700" text-anchor="middle">F-${i + 1}</text>
      <text x="322" y="${y + 26}" fill="var(--color-text-secondary)" font-size="7" text-anchor="middle">
        ${isSpare ? 'Yedek' : '0.3µm'}
      </text>

      <!-- Filter to Comp Suction Header Line -->
      <path d="M 339 ${y} L 360 ${y}" fill="none" stroke="#1d4ed8" stroke-width="4" />
      <path d="M 339 ${y} L 360 ${y}" fill="none" stroke="#93c5fd" stroke-width="1.5" class="station-flow-line" />
    `;
  }
  svg += `
    <text x="322" y="125" fill="#2563eb" font-size="8" font-weight="700" text-anchor="middle">KARTUŞ FİLTRELER (${count})</text>
  </g>`;
  return svg;
}

/**
 * Renders dynamic Turbo-Compressor Train Units with Individual Anti-Surge Loops.
 */
function renderDynamicCompressorTrainsSvg(count, info) {
  const startY = 160;
  const spacing = count > 1 ? 230 / (count - 1) : 0;

  let svg = `<g class="station-equip-group" data-equip-key="turbo_compressors">`;
  for (let i = 0; i < count; i++) {
    const y = count === 1 ? 270 : startY + i * spacing;
    const isSpare = i === count - 1;

    svg += `
      <!-- Train Suction Line from Header with 30"x16" nozzle -->
      <path d="M 374 ${y} L 430 ${y}" fill="none" stroke="#1d4ed8" stroke-width="5" />
      <path d="M 374 ${y} L 430 ${y}" fill="none" stroke="#93c5fd" stroke-width="1.5" class="${isSpare ? '' : 'station-flow-line'}" />

      <!-- Centrifugal Compressor Casing -->
      <rect x="430" y="${y - 18}" width="38" height="36" rx="6" fill="#1e3a8a" stroke="${isSpare ? '#94a3b8' : '#3b82f6'}" stroke-width="2" />
      <path d="M 438 ${y - 10} L 460 ${y - 14} L 460 ${y + 14} L 438 ${y + 10} Z" fill="#2563eb" opacity="0.8" />
      <text x="449" y="${y + 3}" fill="#ffffff" font-size="8" font-weight="700" text-anchor="middle">CMP-${i + 1}</text>

      <!-- Shaft Coupling -->
      <rect x="468" y="${y - 4}" width="12" height="8" fill="#64748b" />

      <!-- Gas Turbine Driver (GT) -->
      <rect x="480" y="${y - 20}" width="54" height="40" rx="4" fill="#78350f" stroke="${isSpare ? '#94a3b8' : '#f59e0b'}" stroke-width="2" />
      <!-- Turbine Exhaust Stack -->
      <rect x="520" y="${y - 30}" width="10" height="10" fill="#475569" stroke="#94a3b8" />
      <text x="507" y="${y + 3}" fill="#fef3c7" font-size="8" font-weight="700" text-anchor="middle">GT-${i + 1}</text>
      <text x="507" y="${y + 14}" fill="#fef3c7" font-size="6" text-anchor="middle">${info.power_per_unit_kw} kW</text>

      <!-- Discharge Line from Compressor -->
      <path d="M 449 ${y - 18} L 449 ${y - 28} L 710 ${y - 28} L 710 ${y} L 750 ${y}" fill="none" stroke="#dc2626" stroke-width="5" />
      <path d="M 449 ${y - 18} L 449 ${y - 28} L 710 ${y - 28} L 710 ${y} L 750 ${y}" fill="none" stroke="#fca5a5" stroke-width="1.5" class="${isSpare ? '' : 'station-flow-fast'}" />

      <!-- Discharge Check Valve (NRV) -->
      <polygon points="690,${y - 32} 700,${y - 28} 690,${y - 24}" fill="#dc2626" />

      <!-- ═════ DEDICATED ANTI-SURGE RECYCLE LOOP (HOT GAS) ═════ -->
      <!-- Taps off before check valve (X=660) and loops down/around back to suction (X=405) -->
      <path d="M 660 ${y - 28} L 660 ${y + 24} L 405 ${y + 24} L 405 ${y}" fill="none" stroke="#f59e0b" stroke-width="3" stroke-linejoin="round" />
      
      <!-- Anti-Surge Valve (ASV) -->
      <circle cx="560" cy="${y + 24}" r="8" fill="#334155" stroke="#f59e0b" stroke-width="1.5" />
      <path d="M 555 ${y + 20} L 565 ${y + 28} M 565 ${y + 20} L 555 ${y + 28}" stroke="#f59e0b" stroke-width="1.5" />
      <rect x="557" y="${y + 11}" width="6" height="5" fill="#f59e0b" />
      <text x="560" y="${y + 38}" fill="#f59e0b" font-size="7" font-weight="600" text-anchor="middle">ASV-${i + 1} (${info.anti_surge_valve_size_in}")</text>

      <!-- Train Status Label -->
      <text x="449" y="${y + 34}" fill="${isSpare ? '#94a3b8' : '#38bdf8'}" font-size="8" font-weight="600" text-anchor="middle">
        ${isSpare ? 'Yedek Tren (Standby)' : `Tren ${i + 1} (Aktif)`}
      </text>
    `;
  }
  svg += `</g>`;
  return svg;
}

/**
 * Renders dynamic Fin-Fan Air Coolers with rotating fan blade graphics.
 */
function renderDynamicCoolersSvg(count, info) {
  let svg = `<g class="station-equip-group" data-equip-key="air_coolers">`;
  const startX = 815;
  const bayWidth = 36;
  const bayGap = 8;

  for (let i = 0; i < count; i++) {
    const x = startX + i * (bayWidth + bayGap);
    svg += `
      <!-- Cooler Bay Structure -->
      <rect x="${x}" y="220" width="${bayWidth}" height="80" rx="4" fill="#0f172a" stroke="#10b981" stroke-width="1.5" />
      
      <!-- Fin Tubes Graphic -->
      <line x1="${x + 4}" y1="230" x2="${x + bayWidth - 4}" y2="230" stroke="#6ee7b7" stroke-width="2" />
      <line x1="${x + 4}" y1="238" x2="${x + bayWidth - 4}" y2="238" stroke="#6ee7b7" stroke-width="2" />
      
      <!-- Fan Shroud & Spinning Fan Blade -->
      <circle cx="${x + bayWidth / 2}" cy="265" r="14" fill="#1e293b" stroke="#10b981" stroke-width="1" />
      <g class="station-fan-blade" style="transform-origin: ${x + bayWidth / 2}px 265px;">
        <ellipse cx="${x + bayWidth / 2}" cy="265" rx="12" ry="3" fill="#34d399" opacity="0.8" />
        <ellipse cx="${x + bayWidth / 2}" cy="265" rx="3" ry="12" fill="#34d399" opacity="0.8" />
      </g>
      <circle cx="${x + bayWidth / 2}" cy="265" r="3" fill="#ffffff" />

      <text x="${x + bayWidth / 2}" y="315" fill="var(--color-text-secondary)" font-size="7" text-anchor="middle">Bay ${i + 1}</text>
    `;
  }

  svg += `
    <text x="${startX + (count * 44) / 2}" y="208" fill="#10b981" font-size="9" font-weight="700" text-anchor="middle">
      HAVA SOĞUTUCULARI (${count} Bay • ${info.total_heat_duty_mw} MWth)
    </text>
  </g>`;
  return svg;
}

/**
 * Renders the floating inspection drawer when an equipment item is clicked.
 */
function renderInspectorDrawer(key, eq, sm) {
  let title = "Ekipman Teftişi";
  let content = "";

  if (key === "pig_receiver") {
    title = "Pig Alıcı (Suction Pig Receiver - PIG-R)";
    content = `
      <div style="font-size: 11px; line-height: 1.5; color: var(--color-text);">
        <p><b>İşlev:</b> 48" Batı Karadeniz ana iletim hattından gelen temizleme ve denetim pig araçlarını istasyon emişine girmeden yakalar.</p>
        <table class="kasp-table" style="font-size: 10px; margin: 8px 0;">
          <tr><td>Kovan Ölçüsü</td><td>PIG-R-56"x48" (ANSI Class 600)</td></tr>
          <tr><td>İşletme Basıncı</td><td>${sm.suction_pressure_bar} bar(a)</td></tr>
          <tr><td>Hızlı Açılır Kapak</td><td>Band-lock / Clamp tipi emniyet kilitli</td></tr>
          <tr><td>Kicker / Dengeleme</td><td>NPS 8" By-pass & Tahliye bağlantısı</td></tr>
        </table>
      </div>
    `;
  } else if (key === "cyclones") {
    title = `Filtre & Çoklu Siklon Seperatörler (${eq.cyclones.configuration})`;
    content = `
      <div style="font-size: 11px; line-height: 1.5; color: var(--color-text);">
        <p><b>İşlev:</b> Santrifüj girdap kuvvetiyle serbest sıvı ve >10µm katı partikülleri %99.5 verimle ayırarak alt LCV vanalarıyla kondensat tankına iletir.</p>
        <table class="kasp-table" style="font-size: 10px; margin: 8px 0;">
          <tr><td>Çalışma Modeli</td><td>${eq.cyclones.operating_count} Aktif + 1 Otomatik Yedek</td></tr>
          <tr><td>Ünite Başına Debi</td><td>${eq.cyclones.flow_per_unit_kgs} kg/s</td></tr>
          <tr><td>Basınç Düşüşü (ΔP)</td><td>${eq.cyclones.pressure_drop_bar} bar</td></tr>
          <tr><td>Drenaj Sistemi</td><td>LCV Seviye Kontrol Vanası ➔ Kondensat Tankı (Note 10)</td></tr>
        </table>
      </div>
    `;
  } else if (key === "cartridge_filters") {
    title = `Kartuş Filtre Seperatörleri (${eq.cartridge_filters.configuration})`;
    content = `
      <div style="font-size: 11px; line-height: 1.5; color: var(--color-text);">
        <p><b>İşlev:</b> Siklon sonrası kalan 0.3 mikrona kadar ince aerosol ve tozu tutarak çark erozyonunu önler.</p>
        <table class="kasp-table" style="font-size: 10px; margin: 8px 0;">
          <tr><td>Filtreleme Hassasiyeti</td><td>${eq.cartridge_filters.filter_efficiency_micron}</td></tr>
          <tr><td>Ünite Başına Debi</td><td>${eq.cartridge_filters.flow_per_unit_kgs} kg/s</td></tr>
          <tr><td>Temiz Filtre ΔP</td><td>${eq.cartridge_filters.clean_dp_bar} bar</td></tr>
          <tr><td>Fark Basınç İletimi</td><td>PDT Diferansiyel Basınç Transmiteri</td></tr>
        </table>
      </div>
    `;
  } else if (key === "turbo_compressors") {
    title = `Turbo-Kompresör Paketleri (${eq.turbo_compressors.configuration})`;
    content = `
      <div style="font-size: 11px; line-height: 1.5; color: var(--color-text);">
        <p><b>İşlev:</b> API 617 santrifüj kompresör ve endüstriyel gaz türbini tahrikli ana basınçlandırma trenleri.</p>
        <table class="kasp-table" style="font-size: 10px; margin: 8px 0;">
          <tr><td>Tren Başına Şaft Gücü</td><td>${eq.turbo_compressors.power_per_unit_kw.toLocaleString()} kW (${eq.turbo_compressors.power_per_unit_hp.toLocaleString()} HP)</td></tr>
          <tr><td>Tren Başına Gaz Debisi</td><td>${eq.turbo_compressors.flow_per_unit_kgs} kg/s</td></tr>
          <tr><td>Tren Başına Yakıt Tüketimi</td><td>${(eq.turbo_compressors.power_per_unit_kw * 0.195).toFixed(1)} kg/h (~${((eq.turbo_compressors.power_per_unit_kw * 0.195)/0.772).toFixed(0)} Sm³/h)</td></tr>
          <tr><td>Tahmini Isı Oranı (Heat Rate)</td><td>~10,285 kJ/kWh (%35 Termal Verim)</td></tr>
          <tr><td>Emiş Nozulu</td><td>${eq.turbo_compressors.suction_nozzle_size_in}</td></tr>
          <tr><td>Basma Nozulu</td><td>${eq.turbo_compressors.discharge_nozzle_size_in}</td></tr>
          <tr><td>Anti-Surge Valfi</td><td>ASV ${eq.turbo_compressors.anti_surge_valve_size_in}" (Stroking: &lt; ${eq.turbo_compressors.anti_surge_stroke_time_s}s)</td></tr>
          ${eq.turbo_compressors.anti_surge_valve_sizing ? `<tr><td>ASV IEC 60534 Boyut</td><td>${eq.turbo_compressors.anti_surge_valve_sizing.valve_inch} • Cv ${Number(eq.turbo_compressors.anti_surge_valve_sizing.required_cv).toFixed(1)} • Açıklık %${Number(eq.turbo_compressors.anti_surge_valve_sizing.opening_percent).toFixed(1)}</td></tr>` : ''}
          <tr><td>Surge Sınır Debisi</td><td>${eq.turbo_compressors.surge_limit_flow_kgs} kg/s</td></tr>
        </table>
      </div>
    `;
  } else if (key === "anti_surge") {
    title = `Anti-Surge Geri Dönüş Döngüsü ve Hızlı ASV Valfi`;
    content = `
      <div style="font-size: 11px; line-height: 1.5; color: var(--color-text);">
        <p><b>İşlev:</b> Kompresörün surge bölgesine düşmesini engellemek için hızlı tepki süreli (&lt; ${eq.turbo_compressors.anti_surge_stroke_time_s}s) pnömatik valf ile basma gazını emişe yönlendirir.</p>
        <table class="kasp-table" style="font-size: 10px; margin: 8px 0;">
          <tr><td>Vana Çapı</td><td>ASV ${eq.turbo_compressors.anti_surge_valve_size_in}" Hızlı Açılan Küresel/Kafesli Vana</td></tr>
          <tr><td>Stroking Süresi</td><td>&lt; ${eq.turbo_compressors.anti_surge_stroke_time_s} saniye (Tam Açılma)</td></tr>
          <tr><td>Surge Kontrol Sınırı</td><td>${eq.turbo_compressors.surge_limit_flow_kgs} kg/s</td></tr>
          <tr><td>Akustik İyileştirme</td><td>Gürültü ve titreşim önleyici kademeli difüzör trim</td></tr>
          ${eq.turbo_compressors.anti_surge_valve_sizing ? `<tr><td>IEC 60534 Kapasite</td><td>${eq.turbo_compressors.anti_surge_valve_sizing.valve_inch} • Cv ${Number(eq.turbo_compressors.anti_surge_valve_sizing.required_cv).toFixed(1)} • Gürültü ${Number(eq.turbo_compressors.anti_surge_valve_sizing.noise_db || 0).toFixed(1)} dB</td></tr>` : ''}
        </table>
      </div>
    `;
  } else if (key === "compressor_building") {
    title = "Kompresör Ünite Binası (Shelter)";
    content = `
      <div style="font-size: 11px; line-height: 1.5; color: var(--color-text);">
        <p><b>İşlev:</b> Ağır hizmet tipi akustik yalıtımlı ünite binası tüm turbo-kompresör trenlerini barındırır.</p>
        <table class="kasp-table" style="font-size: 10px; margin: 8px 0;">
          <tr><td>Boyutlar (G x U x Y)</td><td>${eq.compressor_building.width_m} x ${eq.compressor_building.length_m} x ${eq.compressor_building.height_m} m</td></tr>
          <tr><td>Toplam Taban Alanı</td><td>${eq.compressor_building.area_m2} m²</td></tr>
          <tr><td>Tavan Vinci</td><td>${eq.compressor_building.crane_capacity_tons} Ton Gezer Vinç</td></tr>
          <tr><td>Akustik İzolasyon</td><td>${eq.compressor_building.acoustic_attenuation_dba}</td></tr>
          <tr><td>Emniyet Sistemleri</td><td>Gaz Algılama (%20 LEL), CO2 / Inergen Söndürme</td></tr>
        </table>
      </div>
    `;
  } else if (key === "station_recycle") {
    const recycleSize = eq.station_recycle.pipe_size || '48"';
    title = `${recycleSize} Anti-Surge / Recycle Header (Note 13)`;
    content = `
      <div style="font-size: 11px; line-height: 1.5; color: var(--color-text);">
        <p><b>İşlev:</b> Kompresör anti-surge (ASV) çıkışlarını toplayıp emiş kolektörüne döndürür; aynı zamanda istasyon recycle/purge hattı olarak çalışır.</p>
        <table class="kasp-table" style="font-size: 10px; margin: 8px 0;">
          <tr><td>Boru Çapı</td><td>${recycleSize} Anti-Surge / Suction Tie-in</td></tr>
          <tr><td>Maks. Sirkülasyon</td><td>${eq.station_recycle.max_recirculation_capacity_kgs} kg/s</td></tr>
          <tr><td>Kontrol Vanası</td><td>PCV Kademeli Basınç Düşürücü Düşük Gürültülü Trim</td></tr>
          ${eq.station_recycle.pcv_sizing ? `<tr><td>PCV IEC 60534 Boyut</td><td>${eq.station_recycle.pcv_sizing.valve_inch} • Cv ${Number(eq.station_recycle.pcv_sizing.required_cv).toFixed(1)} • Açıklık %${Number(eq.station_recycle.pcv_sizing.opening_percent).toFixed(1)}</td></tr>` : ''}
        </table>
      </div>
    `;
  } else if (key === "cooler_bypass") {
    title = "Gas Cooler By-Pass Hattı (TCV - Note 17)";
    content = `
      <div style="font-size: 11px; line-height: 1.5; color: var(--color-text);">
        <p><b>İşlev:</b> Soğuk kış aylarında veya düşük debide VFD fanlar minimum devirde dahi gazı aşırı soğutursa, TCV vanası açılarak sıcak basma gazını soğuk çıkışla karıştırır.</p>
        <table class="kasp-table" style="font-size: 10px; margin: 8px 0;">
          <tr><td>Vana Tipi</td><td>TCV Sıcaklık Kontrollü Oransal Vana</td></tr>
          <tr><td>Baypas Boru Çapı</td><td>${eq.air_coolers.bypass_line?.pipe_size || '-'} (ASME B36.10M)</td></tr>
          <tr><td>Birincil Kontrol</td><td>Hava Soğutucu Fanlarında VFD Frekans Kontrolü</td></tr>
          <tr><td>İkincil Kontrol</td><td>TCV Sıcak Gaz Karıştırma Baypası</td></tr>
          ${eq.air_coolers.cooler_bypass_valve_sizing ? `<tr><td>TCV IEC 60534 Boyut</td><td>${eq.air_coolers.cooler_bypass_valve_sizing.valve_inch} • Cv ${Number(eq.air_coolers.cooler_bypass_valve_sizing.required_cv).toFixed(1)} • Açıklık %${Number(eq.air_coolers.cooler_bypass_valve_sizing.opening_percent).toFixed(1)}</td></tr>` : ''}
        </table>
      </div>
    `;
  } else if (key === "condensate_system") {
    title = "Kondensat Toplama ve Depolama Sistemi (Note 14 & 15)";
    content = `
      <div style="font-size: 11px; line-height: 1.5; color: var(--color-text);">
        <p><b>İşlev:</b> Siklon seperatörler ve kartuş filtrelerden ayrıştırılan sıvı hidrokarbon ve suyu depolar.</p>
        <table class="kasp-table" style="font-size: 10px; margin: 8px 0;">
          <tr><td>Tank Hacmi</td><td>${eq.condensate_system?.collection_tank_volume_m3 || 15} m³</td></tr>
          <tr><td>Vent Emniyeti</td><td>Flame Arrester Emniyetli Atmosferik Vent Bacası</td></tr>
          <tr><td>Boşaltım</td><td>Lokal tanker veya saha drenaj sistemi (Note 15)</td></tr>
        </table>
      </div>
    `;
  } else if (key === "air_coolers") {
    title = `Hava Soğutucuları (${eq.air_coolers.bay_count} Fin-Fan Bay)`;
    content = `
      <div style="font-size: 11px; line-height: 1.5; color: var(--color-text);">
        <p><b>İşlev:</b> Sıkıştırma sonrası ısınan gazı boru hattı kaplama limitlerine (${eq.air_coolers.outlet_temp_c}°C) soğutur.</p>
        <table class="kasp-table" style="font-size: 10px; margin: 8px 0;">
          <tr><td>Toplam Isıl Yük</td><td>${eq.air_coolers.total_heat_duty_mw} MWth</td></tr>
          <tr><td>Giriş / Çıkış Sıcaklığı</td><td>${eq.air_coolers.inlet_temp_c}°C → ${eq.air_coolers.outlet_temp_c}°C</td></tr>
          <tr><td>Fan Modülü Sayısı</td><td>${eq.air_coolers.total_fans} Adet Induced-Draft VFD Fan</td></tr>
          <tr><td>Basınç Kaybı (ΔP)</td><td>${eq.air_coolers.pressure_drop_bar} bar</td></tr>
          ${eq.air_coolers.cooler_bypass_valve_sizing ? `<tr><td>TCV Boyut</td><td>${eq.air_coolers.cooler_bypass_valve_sizing.valve_inch} • Cv ${Number(eq.air_coolers.cooler_bypass_valve_sizing.required_cv).toFixed(1)}</td></tr>` : ''}
        </table>
        <button id="btn-detailed-air-cooler" class="btn btn-sm btn-primary" style="margin-top: 6px;">📐 API 661 Detaylı Tasarım</button>
        <div id="air-cooler-detail" style="margin-top: 8px;"></div>
      </div>
    `;
  } else if (key === "safety_relief") {
    title = "Emniyet Tahliye ve Acil Boşaltma (PSV & BDV)";
    content = `
      <div style="font-size: 11px; line-height: 1.5; color: var(--color-text);">
        <p><b>İşlev:</b> Aşırı basınçta (PSV) ve acil durdurma (ESD) senaryolarında istasyonu < 15 dakikada güvenle tahliye eder.</p>
        <table class="kasp-table" style="font-size: 10px; margin: 8px 0;">
          <tr><td>PSV Ayar Basıncı</td><td>${eq.safety_relief_and_blowdown.psv_set_pressure_bar} bar (1 Duty + 1 Standby)</td></tr>
          ${eq.safety_relief_and_blowdown.psv_sizing ? `
          <tr><td>API 520 Ön Boyutlandırma</td><td>${Number(eq.safety_relief_and_blowdown.psv_sizing.required_area_sqin).toFixed(3)} in² • Orifis ${eq.safety_relief_and_blowdown.psv_sizing.selected_orifice || '-'} (${Number(eq.safety_relief_and_blowdown.psv_sizing.selected_orifice_area_sqin || 0).toFixed(3)} in²)</td></tr>
          <tr><td>Orifis Yükü</td><td>%${Number(eq.safety_relief_and_blowdown.psv_sizing.orifice_loading_pct || 0).toFixed(1)} • ${eq.safety_relief_and_blowdown.psv_sizing.flow_type || 'Gas'}</td></tr>
          ` : ''}
          <tr><td>Tahliye Kapasitesi</td><td>%${eq.safety_relief_and_blowdown.relief_capacity_pct} İstasyon Maks. Debisi</td></tr>
          <tr><td>BDV Acil Boşaltma</td><td>${eq.safety_relief_and_blowdown.depressurization_time_min} Dakika (API 521 Standart)</td></tr>
          <tr><td>Baca Tipi</td><td>Emergency Vent at Safe Height / Flame Arrester</td></tr>
        </table>
      </div>
    `;
  } else if (key === "pig_launcher") {
    title = "Pig Atıcı (Discharge Pig Launcher - PIG-L)";
    content = `
      <div style="font-size: 11px; line-height: 1.5; color: var(--color-text);">
        <p><b>İşlev:</b> Basınçlandırılmış ve soğutulmuş gaz iletim hattına akıllı pig araçlarını fırlatır.</p>
        <table class="kasp-table" style="font-size: 10px; margin: 8px 0;">
          <tr><td>Kovan Ölçüsü</td><td>PIG-L-56"x48" (ANSI Class 900)</td></tr>
          <tr><td>İşletme Basıncı</td><td>${sm.discharge_pressure_bar} bar(a)</td></tr>
          <tr><td>Sinyal Verici</td><td>Manyetik Pinger & Geçiş Dedektörü</td></tr>
        </table>
      </div>
    `;
  } else if (key === "control_building") {
    title = "Merkezi Kontrol ve Yardımcı Tesisler Binası (Control Building)";
    content = `
      <div style="font-size: 11px; line-height: 1.5; color: var(--color-text);">
        <p><b>İşlev:</b> İstasyonun tüm DCS, SCADA, acil durdurma (ESD), yangın/gaz algılama ve elektrik dağıtım merkezidir.</p>
        <table class="kasp-table" style="font-size: 10px; margin: 8px 0;">
          <tr><td>Kontrol Sistemi</td><td>Yedekli DCS & SCADA Sunucuları</td></tr>
          <tr><td>Emniyet Seviyesi</td><td>IEC 61508 / 61511 SIL-3 Emniyet PLC</td></tr>
          <tr><td>Kesintisiz Güç (UPS)</td><td>2 x %100 Statik UPS & Akü Grubu (4 Saat Otonomi)</td></tr>
          <tr><td>Yangın & Gaz (F&G)</td><td>%20 LEL IR Dedektörler, UV/IR Alev Algılama</td></tr>
          <tr><td>İklimlendirme</td><td>Ex-Proof Pozitif Basınçlı Havalandırma (HVAC)</td></tr>
        </table>
      </div>
    `;
  } else if (key === "generator_building") {
    title = "Acil Durum Jeneratör ve O.G. Şalt Binası";
    content = `
      <div style="font-size: 11px; line-height: 1.5; color: var(--color-text);">
        <p><b>İşlev:</b> Şebeke enerjisi kesildiğinde kritik enstrümantasyon, yağlama pompaları ve emniyet sistemlerinin enerjisini sağlar.</p>
        <table class="kasp-table" style="font-size: 10px; margin: 8px 0;">
          <tr><td>Jeneratör Tipi</td><td>Dizel Motor Tahrikli Standby Acil Durum Genset</td></tr>
          <tr><td>Gerilim Seviyesi</td><td>6.6 kV Orta Gerilim / 400 V Alçak Gerilim Baraları</td></tr>
          <tr><td>Transfer Süresi (ATS)</td><td>&lt; 15 Saniye Otomatik Şebeke Transferi</td></tr>
        </table>
      </div>
    `;
  } else if (key === "air_compressor_building") {
    title = "Basınçlı Hava ve Enstrüman Servis Binası";
    content = `
      <div style="font-size: 11px; line-height: 1.5; color: var(--color-text);">
        <p><b>İşlev:</b> Pnömatik vanalar, ESD aktüatörleri ve enstrümanlar için kuru ve temiz basınçlı hava üretir.</p>
        <table class="kasp-table" style="font-size: 10px; margin: 8px 0;">
          <tr><td>Çalışma Basıncı</td><td>7.5 - 10.0 bar(g) Basınçlı Enstrüman Havası</td></tr>
          <tr><td>Hava Kalitesi</td><td>ISO 8573-1 Sınıf 1.2.1 (-40°C Çiy Noktası)</td></tr>
          <tr><td>Kurutucu</td><td>Çift Kuleli Isısız Desikant Hava Kurutucu</td></tr>
        </table>
      </div>
    `;
  } else if (key === "admin_building") {
    title = "İdari Yönetim ve Bakım Atölyesi Binası";
    content = `
      <div style="font-size: 11px; line-height: 1.5; color: var(--color-text);">
        <p><b>İşlev:</b> Saha mühendislik ofisleri, mekanik/elektrik bakım atölyeleri ve yedek parça ambarıdır.</p>
        <table class="kasp-table" style="font-size: 10px; margin: 8px 0;">
          <tr><td>Birimler</td><td>Mühendislik Odaları, Mekanik Atölye, Kalibrasyon Lab.</td></tr>
          <tr><td>Atölye Vinci</td><td>3 Tonluk Gezer Köprülü Vinç</td></tr>
        </table>
      </div>
    `;
  } else if (key === "guard_shelter") {
    title = "Tesis Ana Güvenlik & Giriş Nizamiyesi";
    content = `
      <div style="font-size: 11px; line-height: 1.5; color: var(--color-text);">
        <p><b>İşlev:</b> Saha giriş-çıkış emniyeti, CCTV çevre güvenliği ve personel geçiş kontrolüdür.</p>
        <table class="kasp-table" style="font-size: 10px; margin: 8px 0;">
          <tr><td>Güvenlik Standardı</td><td>BOTAŞ Kritik Tesis Çevre Güvenlik Standardı</td></tr>
          <tr><td>Giriş Kontrolü</td><td>Otomatik Bariyer + CCTV Plaka Tanıma Sistemi</td></tr>
        </table>
      </div>
    `;
  }

  return `
    <div class="station-inspector-card">
      <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--color-border); padding-bottom: 8px; margin-bottom: 10px;">
        <div style="font-size: 12px; font-weight: 700; color: var(--color-primary);">${title}</div>
        <button id="btn-close-inspector" class="btn btn-sm btn-icon" style="padding: 2px;">${icon("x", 12)}</button>
      </div>
      ${content}
    </div>
  `;
}

/**
 * Renders the full-screen BOTAŞ Adapazarı PFD & 3D CAD Reference Gallery lightbox modal.
 */
function renderBotasPfdModal() {
  return `
    <div class="kasp-modal-backdrop" id="botas-pfd-backdrop" style="z-index: 1000; background: rgba(0, 0, 0, 0.85);">
      <div class="kasp-modal" style="width: 95vw; height: 92vh; max-width: 98vw; max-height: 96vh; display: flex; flex-direction: column; background: var(--color-surface);">
        
        <!-- Modal Header -->
        <div class="kasp-modal-header" style="display: flex; justify-content: space-between; align-items: center; padding: 12px 20px; border-bottom: 1px solid var(--color-border);">
          <div style="display: flex; align-items: center; gap: 10px;">
            ${icon("fileText", 20, "text-primary")}
            <div>
              <h3 style="margin: 0; font-size: 14px; font-weight: 700;">BOTAŞ Adapazarı Kompresör İstasyonu — Orijinal PFD & 3D CAD Referans Galerisi</h3>
              <div style="font-size: 11px; color: var(--color-text-secondary);">
                Doküman No: <b>0-NGTL0-CS-I-001-4000</b> • BOTAŞ / Kontrolmatik Mühendislik • 3D Navisworks / Plant 3D & PFD
              </div>
            </div>
          </div>
          <button id="btn-close-pfd-modal" class="btn btn-sm btn-icon">${icon("x", 16)}</button>
        </div>

        <!-- Drawing & 3D CAD Gallery View (Scrollable) -->
        <div style="flex: 1; overflow: auto; padding: 16px; background: #0b0f19; display: flex; flex-direction: column; gap: 18px; align-items: center;">
          <div style="width: 100%; max-width: 1400px;">
            <div style="color: #38bdf8; font-size: 13px; font-weight: 700; margin-bottom: 8px;">1. 3D CAD Referans Görünümleri (MFS, CFS, Gas Cooler, COMPRESSOR-01..05, 7.0m Yol & Kontrol Binaları)</div>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(420px, 1fr)); gap: 12px;">
              <img src="/static/vendor/cad_ref_2.jpg" alt="3D CAD Vaziyet Planı" style="width: 100%; border-radius: 6px; border: 1px solid rgba(255,255,255,0.15);" />
              <img src="/static/vendor/cad_ref_3.jpg" alt="3D CAD Genel İzometrik" style="width: 100%; border-radius: 6px; border: 1px solid rgba(255,255,255,0.15);" />
              <img src="/static/vendor/cad_ref_1.jpg" alt="3D CAD Proses Sahası" style="width: 100%; border-radius: 6px; border: 1px solid rgba(255,255,255,0.15);" />
              <img src="/static/vendor/cad_ref_4.jpg" alt="3D CAD COMPRESSOR-04 İç Kesit" style="width: 100%; border-radius: 6px; border: 1px solid rgba(255,255,255,0.15);" />
              <img src="/static/vendor/cad_ref_5.jpg" alt="3D CAD Kolektör ve Ünite Binaları" style="width: 100%; border-radius: 6px; border: 1px solid rgba(255,255,255,0.15);" />
            </div>
          </div>

          <div style="width: 100%; max-width: 1400px;">
            <div style="color: #34d399; font-size: 13px; font-weight: 700; margin-bottom: 8px;">2. Proses Akış Diyagramı (PFD — 0-NGTL0-CS-I-001-4000)</div>
            <img src="/static/vendor/pfd_reference.png" alt="BOTAŞ Adapazarı PFD Referansı" style="max-width: 100%; height: auto; border-radius: 6px; box-shadow: 0 4px 20px rgba(0,0,0,0.5);" />
          </div>
        </div>

        <!-- Modal Footer -->
        <div class="kasp-modal-footer" style="padding: 10px 20px; border-top: 1px solid var(--color-border); display: flex; justify-content: space-between; align-items: center; background: var(--color-surface); font-size: 11px; color: var(--color-text-secondary);">
          <div style="display: flex; gap: 12px; align-items: center; flex-wrap: wrap;">
            <span style="font-weight: 600; color: var(--color-primary);">Doğrulanan Sistemler:</span>
            <span>48" Ana Hat & Pig Kovanları</span>
            <span>•</span>
            <span>MFS Çoklu Siklon</span>
            <span>•</span>
            <span>CFS Kartuş Filtre</span>
            <span>•</span>
            <span>COMPRESSOR-01..05 (Mavi Çelik Karkas & X-Ray Kesit)</span>
            <span>•</span>
            <span>Gas Cooler & TCV By-Pass</span>
            <span>•</span>
            <span>7.0m Yol, Tel Çit & Kontrol Binası</span>
          </div>
          <button id="btn-footer-close-pfd-modal" class="btn btn-sm btn-secondary">Kapat</button>
        </div>

      </div>
    </div>
  `;
}

/**
 * Renders the live interactive parameter control bar for real-time natural gas pipe sizing.
 */
function renderLiveParamsBar(inputs, isExpanded) {
  const mmscmdEst = (inputs.mass_flow * 0.1147).toFixed(1);
  return `
    <div class="card" style="padding: 12px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-md);">
      
      <!-- Collapsible Top Summary Bar -->
      <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
        <div style="display: flex; align-items: center; gap: 8px;">
          ${icon("sliders", 16, "text-primary")}
          <div style="font-size: 12px; font-weight: 700; color: var(--color-text);">
            Canlı İşletme Parametreleri & Dinamik ASME B36.10M / API 5L Boru Boyutlandırma
          </div>
          <span class="badge badge-success" style="font-size: 10px;">Natural Gas Flow Calc Motoru Aktif</span>
        </div>

        <div style="display: flex; align-items: center; gap: 12px; font-size: 11px;">
          <div style="color: var(--color-text-secondary);">
            Debi: <strong style="color: #38bdf8; font-family: var(--font-mono);">${inputs.mass_flow.toFixed(1)} kg/s</strong> <span style="opacity: 0.7;">(~${mmscmdEst} MMSCMD)</span>
          </div>
          <div style="color: var(--color-text-secondary);">
            Emiş: <strong style="color: #34d399; font-family: var(--font-mono);">${inputs.p_in.toFixed(1)} bar(a)</strong>
          </div>
          <div style="color: var(--color-text-secondary);">
            Basma: <strong style="color: #f59e0b; font-family: var(--font-mono);">${inputs.p_out.toFixed(1)} bar(a)</strong>
          </div>
          <div style="color: var(--color-text-secondary);">
            Çelik: <strong style="color: #a78bfa;">${inputs.pipe_material}</strong>
          </div>
          <button id="btn-toggle-params-panel" class="btn btn-sm btn-secondary" style="font-size: 11px; padding: 2px 8px;">
            ${isExpanded ? "Paneli Daralt ▲" : "Parametreleri Düzenle ▼"}
          </button>
        </div>
      </div>

      <!-- Expanded Interactive Controls Grid -->
      ${isExpanded ? `
        <div style="margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--color-border); display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px;">
          
          <!-- Mass Flow Controller -->
          <div style="background: var(--color-surface-hover); padding: 8px 10px; border-radius: var(--radius-sm); border: 1px solid var(--color-border);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
              <label style="font-size: 11px; font-weight: 600; color: var(--color-text);">Kütlesel Debi (kg/s)</label>
              <input type="number" id="input-param-flow" min="10" max="400" step="1" value="${inputs.mass_flow}" style="width: 65px; font-size: 11px; padding: 2px 4px; text-align: right; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 4px; color: var(--color-text); font-family: var(--font-mono);" />
            </div>
            <input type="range" id="slider-param-flow" min="20" max="300" step="5" value="${inputs.mass_flow}" style="width: 100%; cursor: pointer;" />
            <div style="display: flex; justify-content: space-between; font-size: 9px; color: var(--color-text-secondary); margin-top: 2px;">
              <span>20 kg/s (2.3 MMSCMD)</span>
              <span>150 kg/s</span>
              <span>300 kg/s (34.5 MMSCMD)</span>
            </div>
          </div>

          <!-- Suction Pressure Controller -->
          <div style="background: var(--color-surface-hover); padding: 8px 10px; border-radius: var(--radius-sm); border: 1px solid var(--color-border);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
              <label style="font-size: 11px; font-weight: 600; color: var(--color-text);">Emiş Basıncı P_in (bar a)</label>
              <input type="number" id="input-param-pin" min="20" max="65" step="0.5" value="${inputs.p_in}" style="width: 65px; font-size: 11px; padding: 2px 4px; text-align: right; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 4px; color: var(--color-text); font-family: var(--font-mono);" />
            </div>
            <input type="range" id="slider-param-pin" min="25" max="60" step="1" value="${inputs.p_in}" style="width: 100%; cursor: pointer;" />
            <div style="display: flex; justify-content: space-between; font-size: 9px; color: var(--color-text-secondary); margin-top: 2px;">
              <span>25 bar</span>
              <span>45 bar (Standart)</span>
              <span>60 bar</span>
            </div>
          </div>

          <!-- Discharge Pressure Controller -->
          <div style="background: var(--color-surface-hover); padding: 8px 10px; border-radius: var(--radius-sm); border: 1px solid var(--color-border);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
              <label style="font-size: 11px; font-weight: 600; color: var(--color-text);">Basma Basıncı P_out (bar a)</label>
              <input type="number" id="input-param-pout" min="50" max="95" step="0.5" value="${inputs.p_out}" style="width: 65px; font-size: 11px; padding: 2px 4px; text-align: right; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 4px; color: var(--color-text); font-family: var(--font-mono);" />
            </div>
            <input type="range" id="slider-param-pout" min="50" max="90" step="1" value="${inputs.p_out}" style="width: 100%; cursor: pointer;" />
            <div style="display: flex; justify-content: space-between; font-size: 9px; color: var(--color-text-secondary); margin-top: 2px;">
              <span>50 bar</span>
              <span>75 bar (Standart)</span>
              <span>90 bar</span>
            </div>
          </div>

          <!-- Equipment Counts & Pipe Steel Selection -->
          <div style="background: var(--color-surface-hover); padding: 8px 10px; border-radius: var(--radius-sm); border: 1px solid var(--color-border); display: flex; flex-direction: column; gap: 6px;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <label style="font-size: 11px; font-weight: 600; color: var(--color-text);">Kompresör Trenleri:</label>
              <select id="select-param-comps" style="font-size: 11px; padding: 2px 4px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 4px; color: var(--color-text);">
                <option value="0" ${inputs.comp_op_count === 0 ? "selected" : ""}>Otomatik (Debiye Göre)</option>
                <option value="1" ${inputs.comp_op_count === 1 ? "selected" : ""}>1+1 Tren</option>
                <option value="2" ${inputs.comp_op_count === 2 ? "selected" : ""}>2+1 Tren</option>
                <option value="3" ${inputs.comp_op_count === 3 ? "selected" : ""}>3+1 Tren</option>
                <option value="4" ${inputs.comp_op_count === 4 ? "selected" : ""}>4+1 Tren (BOTAŞ)</option>
                <option value="5" ${inputs.comp_op_count === 5 ? "selected" : ""}>5+1 Tren</option>
                <option value="6" ${inputs.comp_op_count === 6 ? "selected" : ""}>6+1 Tren</option>
              </select>
            </div>

            <div style="display: flex; justify-content: space-between; align-items: center;">
              <label style="font-size: 11px; font-weight: 600; color: var(--color-text);">Siklon / Filtre Sayısı:</label>
              <select id="select-param-cyclones" style="font-size: 11px; padding: 2px 4px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 4px; color: var(--color-text);">
                <option value="0" ${inputs.cyclone_op_count === 0 ? "selected" : ""}>Otomatik (Debiye Göre)</option>
                <option value="2" ${inputs.cyclone_op_count === 2 ? "selected" : ""}>2+1 Ünite</option>
                <option value="3" ${inputs.cyclone_op_count === 3 ? "selected" : ""}>3+1 Ünite (BOTAŞ)</option>
                <option value="4" ${inputs.cyclone_op_count === 4 ? "selected" : ""}>4+1 Ünite</option>
                <option value="5" ${inputs.cyclone_op_count === 5 ? "selected" : ""}>5+1 Ünite</option>
              </select>
            </div>

            <div style="display: flex; justify-content: space-between; align-items: center;">
              <label style="font-size: 11px; font-weight: 600; color: var(--color-text);">Hava Soğutucu Bay:</label>
              <select id="select-param-coolers" style="font-size: 11px; padding: 2px 4px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 4px; color: var(--color-text);">
                <option value="0" ${inputs.cooler_bays_count === 0 ? "selected" : ""}>Otomatik (Isıl Yüke Göre)</option>
                <option value="2" ${inputs.cooler_bays_count === 2 ? "selected" : ""}>2 Bay (4 Fan)</option>
                <option value="4" ${inputs.cooler_bays_count === 4 ? "selected" : ""}>4 Bay (8 Fan)</option>
                <option value="6" ${inputs.cooler_bays_count === 6 ? "selected" : ""}>6 Bay (12 Fan - BOTAŞ)</option>
                <option value="8" ${inputs.cooler_bays_count === 8 ? "selected" : ""}>8 Bay (16 Fan)</option>
                <option value="10" ${inputs.cooler_bays_count === 10 ? "selected" : ""}>10 Bay (20 Fan)</option>
              </select>
            </div>

            <div style="display: flex; justify-content: space-between; align-items: center;">
              <label style="font-size: 11px; font-weight: 600; color: var(--color-text);">Boru Çelik Sınıfı:</label>
              <select id="select-param-material" style="font-size: 11px; padding: 2px 4px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 4px; color: var(--color-text);">
                <option value="API 5L X70" ${inputs.pipe_material === "API 5L X70" ? "selected" : ""}>API 5L X70 (485 MPa)</option>
                <option value="API 5L X65" ${inputs.pipe_material === "API 5L X65" ? "selected" : ""}>API 5L X65 (450 MPa)</option>
                <option value="API 5L X52" ${inputs.pipe_material === "API 5L X52" ? "selected" : ""}>API 5L X52 (360 MPa)</option>
                <option value="API 5L Gr. B" ${inputs.pipe_material === "API 5L Gr. B" ? "selected" : ""}>API 5L Gr. B (245 MPa)</option>
              </select>
            </div>

            <div style="display: flex; justify-content: space-between; align-items: center;">
              <label style="font-size: 11px; font-weight: 600; color: var(--color-text);">Boru Standardı:</label>
              <select id="select-param-standard" style="font-size: 11px; padding: 2px 4px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 4px; color: var(--color-text);">
                <option value="BOTAŞ" ${inputs.pipe_standard === "BOTAŞ" ? "selected" : ""}>BOTAŞ 5120_R7</option>
                <option value="ASME B31.8 / ASME B31.4" ${inputs.pipe_standard === "ASME B31.8 / ASME B31.4" ? "selected" : ""}>API 5L / ASME B31.8</option>
                <option value="ASME B31.3" ${inputs.pipe_standard === "ASME B31.3" ? "selected" : ""}>ASME B31.3</option>
              </select>
            </div>

            <div style="display: flex; justify-content: space-between; align-items: center;">
              <label style="font-size: 11px; font-weight: 600; color: var(--color-text);">PSL Seviyesi:</label>
              <select id="select-param-psl" style="font-size: 11px; padding: 2px 4px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 4px; color: var(--color-text);">
                <option value="PSL2" ${inputs.psl_level === "PSL2" ? "selected" : ""}>PSL2</option>
                <option value="PSL1" ${inputs.psl_level === "PSL1" ? "selected" : ""}>PSL1</option>
              </select>
            </div>
          </div>

        </div>

        <div style="display: flex; justify-content: flex-end; gap: 8px; margin-top: 10px;">
          <button id="btn-reset-station-params" class="btn btn-sm btn-secondary" style="font-size: 11px;">
            ${icon("refreshCw", 12)}
            <span>Varsayılan Parametreler</span>
          </button>
          <button id="btn-apply-station-params" class="btn btn-sm btn-primary" style="font-size: 11px;">
            ${icon("play", 12)}
            <span>Boru Hatlarını Boyutlandır & Güncelle</span>
          </button>
        </div>
      ` : ""}

    </div>
  `;
}

/**
 * Renders the comprehensive 15-line ASME B36.10M / API 5L Natural Gas Flow Calc Pipe Sizing Matrix Table.
 */
function renderPipeSizingTable(piping) {
  if (!piping || Object.keys(piping).length === 0) {
    return `
      <div class="card" style="padding: 14px; text-align: center; color: var(--color-text-secondary); font-size: 12px;">
        ${icon("activity", 18, "text-primary")}
        <div style="margin-top: 6px;">Boru boyutlandırma hesapları yükleniyor...</div>
      </div>
    `;
  }

  const linesMap = piping.lines || piping;
  const lines = Object.values(linesMap);

  return `
    <div class="card" style="padding: 12px;">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; flex-wrap: wrap; gap: 6px;">
        <div style="display: flex; align-items: center; gap: 6px;">
          ${icon("activity", 15, "text-primary")}
          <span style="font-size: 13px; font-weight: 700;">ASME B36.10M / API 5L Dinamik Boru Boyutlandırma & Hidrolik Doğrulama Matrisi</span>
          <span class="badge badge-primary" style="font-size: 10px;">15 Proses Hattı</span>
        </div>
        <div style="font-size: 11px; color: var(--color-text-secondary); display: flex; gap: 10px; align-items: center;">
          <span>Barlow: <b>t = P·D / (2·SMYS·F)</b></span>
          <span>•</span>
          <span>Erozyon: <b>API RP 14E (v &lt; 122/√ρ)</b></span>
          <span>•</span>
          <span>Sürtünme: <b>Churchill (1977)</b></span>
        </div>
      </div>

      <div style="overflow-x: auto;">
        <table class="kasp-table" style="font-size: 11px; width: 100%; white-space: nowrap;">
          <thead>
            <tr>
              <th style="width: 55px;">Hat No</th>
              <th>Proses Hattı Tanımı</th>
              <th style="text-align: right;">Debi (kg/s)</th>
              <th style="text-align: right;">Basınç (bar a)</th>
              <th style="text-align: center;">Anma Çapı (NPS)</th>
              <th style="text-align: center;">Dış Çap (OD mm)</th>
              <th style="text-align: center;">Çizelge & Kalınlık (mm)</th>
              <th style="text-align: right;">Min. Barlow (t_req)</th>
              <th style="text-align: right;">Standart t_min</th>
              <th style="text-align: center;">Standart</th>
              <th style="text-align: right;">Gaz Hızı (v m/s)</th>
              <th style="text-align: center;">Erozyon Oranı (EVR)</th>
              <th style="text-align: right;">ΔP (bar/100m)</th>
              <th style="text-align: right;">Ağırlık (kg/m)</th>
              <th style="text-align: center;">Durum</th>
            </tr>
          </thead>
          <tbody>
            ${lines.map(line => {
              const tag = line.tag || line.line_id || "-";
              const name = line.name || "-";
              const flow = line.flow_kgs !== undefined ? line.flow_kgs : (line.flow_kg_s || 0);
              const pressure = line.pressure_bar !== undefined ? line.pressure_bar : (line.p_bar || 0);
              const nps = line.nominal_size_in || (line.selected_pipe ? line.selected_pipe.nps : "-");
              const od = line.od_mm || (line.selected_pipe ? line.selected_pipe.od_mm : 0);
              const sch = line.schedule || (line.selected_pipe ? line.selected_pipe.schedule : "-");
              const thick = line.wall_thickness_mm !== undefined ? line.wall_thickness_mm : (line.selected_pipe ? line.selected_pipe.thickness_mm : 0);
              const treq = line.min_required_thickness_mm !== undefined ? line.min_required_thickness_mm : (line.selected_pipe ? line.selected_pipe.t_req_mm : 0);
              const v = line.actual_velocity_ms !== undefined ? line.actual_velocity_ms : (line.selected_pipe ? line.selected_pipe.velocity_m_s : 0);
              const evr = line.erosion_ratio_pct !== undefined ? line.erosion_ratio_pct : (line.selected_pipe ? line.selected_pipe.evr_percent : 0);
              const dp = line.pressure_drop_bar_per_100m !== undefined ? line.pressure_drop_bar_per_100m : (line.selected_pipe ? line.selected_pipe.dp_bar_per_100m : 0);
              const weight = line.pipe_weight_kg_m !== undefined ? line.pipe_weight_kg_m : (line.selected_pipe ? line.selected_pipe.weight_kg_m : 0);
              const status = line.velocity_status || (line.selected_pipe ? line.selected_pipe.status : "OK");
              const std = line.standard_recommendation || {};
              const stdMin = std.minimum_standard_thickness_mm;
              const stdOk = std.is_sufficient !== false && !std.error;

              const vColor = v > 18 ? "#ef4444" : v > 15 ? "#f59e0b" : "#10b981";
              const evrColor = evr > 80 ? "#ef4444" : evr > 60 ? "#f59e0b" : "#10b981";
              const isStatusOk = status.includes("Optimum") || status === "OK";

              return `
                <tr>
                  <td style="font-family: var(--font-mono); font-weight: 700; color: #38bdf8;">${tag}</td>
                  <td style="font-weight: 600;">${name}</td>
                  <td style="text-align: right; font-family: var(--font-mono);">${flow.toFixed(1)}</td>
                  <td style="text-align: right; font-family: var(--font-mono);">${pressure.toFixed(1)}</td>
                  <td style="text-align: center; font-family: var(--font-mono); font-weight: 700; color: #facc15;">
                    ${nps}
                  </td>
                  <td style="text-align: center; font-family: var(--font-mono);">${od ? od.toFixed(1) : "-"}</td>
                  <td style="text-align: center; font-family: var(--font-mono);">
                    <span class="badge badge-neutral" style="font-size: 10px;">Sch ${sch}</span>
                    <strong style="margin-left: 4px;">${thick ? thick.toFixed(2) + " mm" : "-"}</strong>
                  </td>
                  <td style="text-align: right; font-family: var(--font-mono); color: var(--color-text-secondary);">
                    ${treq ? treq.toFixed(2) + " mm" : "-"}
                  </td>
                  <td style="text-align: right; font-family: var(--font-mono); color: var(--color-text-secondary);" title="${std.tolerance_rule || ''}">
                    ${stdMin ? Number(stdMin).toFixed(2) + " mm" : "-"}
                  </td>
                  <td style="text-align: center; font-size: 10px;">
                    <span class="badge ${stdOk ? 'badge-success' : 'badge-warning'}" title="${std.tolerance_rule || ''}">
                      ${std.standard || "BOTAŞ"} ${std.psl_level || "PSL2"}
                    </span>
                  </td>
                  <td style="text-align: right; font-family: var(--font-mono); font-weight: 700; color: ${vColor};">
                    ${v.toFixed(2)} m/s
                  </td>
                  <td style="text-align: center; font-family: var(--font-mono);">
                    <div style="display: flex; align-items: center; justify-content: center; gap: 4px;">
                      <div style="width: 44px; height: 6px; background: rgba(255,255,255,0.1); border-radius: 3px; overflow: hidden;">
                        <div style="width: ${Math.min(100, evr)}%; height: 100%; background: ${evrColor};"></div>
                      </div>
                      <span style="font-size: 10px; color: ${evrColor}; font-weight: 600;">%${evr.toFixed(1)}</span>
                    </div>
                  </td>
                  <td style="text-align: right; font-family: var(--font-mono); font-size: 10px;">
                    ${dp !== undefined ? dp.toFixed(3) : "-"}
                  </td>
                  <td style="text-align: right; font-family: var(--font-mono); font-size: 10px; color: var(--color-text-secondary);">
                    ${weight ? weight.toFixed(1) : "-"}
                  </td>
                  <td style="text-align: center;">
                    <span class="badge ${isStatusOk ? 'badge-success' : 'badge-warning'}" style="font-size: 10px;">
                      ${isStatusOk ? "OK" : status}
                    </span>
                  </td>
                </tr>
              `;
            }).join("")}
          </tbody>
        </table>
      </div>

      <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 8px; font-size: 10px; color: var(--color-text-secondary); flex-wrap: wrap; gap: 6px;">
        <div>
          <span>Boru Malzemesi: <b>${piping.pipe_material || "API 5L X70"} (SMYS = 485 MPa)</b></span>
          <span style="margin: 0 6px;">•</span>
          <span>İstasyon Emniyet Tasarım Faktörü: <b>F = ${piping.design_factor_F ? piping.design_factor_F.toFixed(2) : "0.50"} (ASME B31.8 Sınıf 1 Bölüm 2 Kompresör Sahası)</b></span>
          <span style="margin: 0 6px;">•</span>
          <span>Boru Standardı: <b>${piping.pipe_standard || "BOTAŞ"} ${piping.psl_level || "PSL2"}</b></span>
        </div>
        <div>
          <span>Hız Kriteri: &lt; 15 m/s (Optimum), &lt; 18 m/s (Tavan), v_erozyon = 122 / √ρ</span>
        </div>
      </div>
    </div>
  `;
}
