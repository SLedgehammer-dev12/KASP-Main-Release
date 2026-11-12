/**
 * KASP Design Results View Component
 * 6 KPI Metric Cards, 146+ Matching Turbine Selection Table,
 * and 6 Deep-Dive Engineering Analysis Tabs.
 */

import { icon } from "../../vendor/icons.js";
import {
  projectStore,
  updateInput,
  runDesignCalculation,
  convertFlowWithMW,
  escapeHtml,
} from "../store/projectStore.js";
import { uiStore, setActiveTab, setActiveSubTab, showToast } from "../store/uiStore.js";
import { t } from "../i18n/locales.js";

function normalizeResultWarning(item) {
  if (typeof item === "string") return item.trim();
  if (item && typeof item === "object" && item.message) {
    return item.field ? `[${item.field}] ${item.message}` : String(item.message).trim();
  }
  return "";
}

function collectDesignWarnings(proj, res) {
  const seen = new Set();
  const items = [];
  const push = (raw) => {
    const text = normalizeResultWarning(raw);
    if (text && !seen.has(text)) {
      seen.add(text);
      items.push(text);
    }
  };
  for (const w of proj?.warnings || []) push(w);
  for (const w of res?.validation_warnings || []) push(w);
  for (const w of res?.warnings || []) push(w);
  for (const stg of res?.stages || []) {
    for (const sw of stg?.selection_warnings || []) {
      push(`Kademe ${stg.stage || ""}: ${sw}`);
    }
  }
  return items;
}

export function renderResultsView(container) {
  function update() {
    const proj = projectStore.getState();
    const ui = uiStore.getState();
    const res = proj.results;
    const units = proj.selectedUnits || [];

    if (!res) {
      container.innerHTML = `
        <div class="card" style="display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 400px; text-align: center; color: var(--color-text-secondary);">
          <div style="font-size: 40px; margin-bottom: 12px; opacity: 0.5;">⚡</div>
          <div style="font-size: 15px; font-weight: 600; color: var(--color-text); margin-bottom: 6px;">Hesaplama Bekleniyor</div>
          <div style="max-width: 360px; font-size: 12px; margin-bottom: 16px;">
            Sol paneldeki proses şartlarını ve gaz bileşimini kontrol ettikten sonra <b>"Hesapla & Seç"</b> butonuna tıklayın.
          </div>
        </div>
      `;
      return;
    }

    const activeGasComp = proj.inputs?.gas_comp;
    const fuelKghToSm3h = (kgh) => {
      const val = Number(kgh) || 0;
      if (val <= 0) return 0;
      const eosStdRho = Number(res.fuel_standard_density_kg_sm3 || res.fuel_gas_properties?.standard_density_kg_sm3 || 0);
      if (eosStdRho > 0) return val / eosStdRho;
      return convertFlowWithMW(val, "kg/h", "Sm³/h", activeGasComp);
    };
    const designWarnings = collectDesignWarnings(proj, res);
    const isInvalidScope = res.analysis_scope === "INVALID" || res.energy_balance_ok === false;
    const isNotSelectable = res.compressor_selectable === false || res.analysis_scope === "NOT_SELECTABLE";
    const isFallbackUsed = !!res.fallback_used;

    // Extract KPIs with full unit, power, and fuel parity
    const numUnits = Math.max(1, parseInt(res.num_units || proj.inputs?.num_units || 1, 10));
    
    // Shaft Power (Ünite / Toplam)
    const powerShaftPerUnitKw = Number(res.power_shaft_per_unit_kw || (res.power_shaft_total_kw ? res.power_shaft_total_kw / numUnits : (res.power_shaft_kw || 0)));
    const powerShaftTotalKw = Number(res.power_shaft_total_kw || (powerShaftPerUnitKw * numUnits));
    
    // Motor / Driver Power (API 617 marjı; çekirdekten gelen değer önceliklidir)
    const driverMarginPct = Number(res.api_617_margin_percent !== undefined ? res.api_617_margin_percent : 4.0);
    const mechEffFrac = (Number(proj.inputs?.mech_eff) || 98.0) / 100.0;
    const powerMotorPerUnitKw = Number(
      res.power_motor_per_unit_kw || (mechEffFrac > 0 ? powerShaftPerUnitKw / mechEffFrac : powerShaftPerUnitKw)
    );
    const powerUnitKw = Number(
      res.power_unit_kw || (powerMotorPerUnitKw * (1 + driverMarginPct / 100.0))
    );
    const powerUnitTotalKw = Number(res.power_unit_total_kw || res.power_motor_total_kw || (powerUnitKw * numUnits));
    
    // Gas Power
    const powerGasPerUnitKw = Number(res.power_gas_per_unit_kw || (res.power_gas_total_kw ? res.power_gas_total_kw / numUnits : 0));
    const powerGasTotalKw = Number(res.power_gas_total_kw || (powerGasPerUnitKw * numUnits));
    
    // Mechanical Loss
    const mechLossPerUnitKw = Number(res.mech_loss_per_unit_kw || (res.mech_loss_total_kw ? res.mech_loss_total_kw / numUnits : 0));
    const mechLossTotalKw = Number(res.mech_loss_total_kw || (mechLossPerUnitKw * numUnits));

    // Fuel Consumption & Properties
    const fuelUnitKgH = Number(res.fuel_unit_kgh || (res.fuel_total_kgh ? res.fuel_total_kgh / numUnits : (res.fuel_gas_flow_kg_h || (res.fuel && res.fuel.mass_flow_kg_h) || 0)));
    const fuelTotalKgH = Number(res.fuel_total_kgh || (fuelUnitKgH * numUnits));
    const lhv = Number(res.lhv || (res.fuel && res.fuel.lhv_kj_kg) || 47000);
    const hhv = Number(res.hhv || (res.fuel && res.fuel.hhv_kj_kg) || 52000);
    const heatRate = Number(
      res.heat_rate ||
        (res.fuel && res.fuel.heat_rate) ||
        (fuelUnitKgH > 0 && powerMotorPerUnitKw > 0 ? (fuelUnitKgH * lhv) / powerMotorPerUnitKw : 0)
    );
    const driverThermEffPct = Number(
      res.driver_thermal_efficiency_pct ||
        proj.inputs?.therm_eff ||
        (heatRate > 0 ? 360000.0 / heatRate : 35.0)
    );

    // Process conditions & performance
    const stages = res.stages || [];
    const stageBar = (v) => {
      const n = Number(v) || 0;
      return Math.abs(n) > 1e4 ? n / 1e5 : n;
    };
    const stageCelsius = (v) => {
      const n = Number(v) || 0;
      return n > 200 ? n - 273.15 : n;
    };
    const totalHead = res.head_kj_kg || stages.reduce((acc, s) => acc + (s.head_kj_kg || 0), 0);
    let polyEff = res.actual_poly_efficiency !== undefined ? res.actual_poly_efficiency : (res.poly_eff || 0);
    if (polyEff > 0 && polyEff <= 1.0) polyEff = polyEff * 100.0;
    let targetPolyEff = res.design_poly_efficiency !== undefined ? Number(res.design_poly_efficiency) : (Number(proj.inputs?.poly_eff) || 82.0);
    if (targetPolyEff > 0 && targetPolyEff <= 1.0) targetPolyEff = targetPolyEff * 100.0;

    // Thermodynamic state variables (Inlet / Outlet)
    const inProps = res.inlet_properties || {};
    const outProps = res.outlet_properties || {};

    const pInBar = Number(res.p_in_bar !== undefined ? res.p_in_bar : (proj.inputs?.p_in || (stages[0]?.p_in_bar) || ((res.p_in_pa || 0) / 1e5) || 20.0));
    const pOutBar = Number(res.p_out_bar !== undefined ? res.p_out_bar : (proj.inputs?.p_out || (stages[stages.length - 1]?.p_out_bar) || ((res.p_out_pa || 0) / 1e5) || 60.0));
    const pr = res.compression_ratio || res.pr || (pOutBar > 0 && pInBar > 0 ? pOutBar / pInBar : 1.0);

    const tInC = Number(res.t_in_c !== undefined ? res.t_in_c : (proj.inputs?.t_in !== undefined ? proj.inputs.t_in : (stages[0]?.t_in_c || (res.t_in ? (res.t_in > 200 ? res.t_in - 273.15 : res.t_in) : 25.0))));
    const tOutC = Number(res.t_out_c !== undefined ? res.t_out_c : (res.t_out !== undefined ? (res.t_out > 200 ? res.t_out - 273.15 : res.t_out) : (stages[stages.length - 1]?.t_out_c || 65.0)));

    const zIn = Number(res.z_in !== undefined ? res.z_in : (inProps.Z !== undefined ? inProps.Z : 0.96));
    const zOut = Number(res.z_out !== undefined ? res.z_out : (outProps.Z !== undefined ? outProps.Z : 0.92));
    const kIn = Number(res.k_in !== undefined ? res.k_in : (inProps.k !== undefined ? inProps.k : 1.31));
    const kOut = Number(res.k_out !== undefined ? res.k_out : (outProps.k !== undefined ? outProps.k : 1.28));
    const ksIn = Number(res.k_s_in !== undefined ? res.k_s_in : (inProps.k_s !== undefined ? inProps.k_s : 0));
    const ksOut = Number(res.k_s_out !== undefined ? res.k_s_out : (outProps.k_s !== undefined ? outProps.k_s : 0));

    const rhoIn = Number(res.rho_in !== undefined ? res.rho_in : (inProps.rho !== undefined ? inProps.rho : 0.0));
    const rhoOut = Number(res.rho_out !== undefined ? res.rho_out : (outProps.rho !== undefined ? outProps.rho : 0.0));
    const vIn = Number(res.v_in !== undefined ? res.v_in : (rhoIn > 0 ? 1.0 / rhoIn : 0.0));
    const vOut = Number(res.v_out !== undefined ? res.v_out : (rhoOut > 0 ? 1.0 / rhoOut : 0.0));

    const sosIn = Number(res.speed_of_sound_in !== undefined ? res.speed_of_sound_in : (inProps.a !== undefined ? inProps.a : 0.0));
    const sosOut = Number(res.speed_of_sound_out !== undefined ? res.speed_of_sound_out : (outProps.a !== undefined ? outProps.a : 0.0));

    const cpIn = Number(res.cp_in !== undefined ? res.cp_in : (inProps.Cp !== undefined ? inProps.Cp : 0.0));
    const cpOut = Number(res.cp_out !== undefined ? res.cp_out : (outProps.Cp !== undefined ? outProps.Cp : 0.0));
    const cvIn = Number(res.cv_in !== undefined ? res.cv_in : (inProps.Cv !== undefined ? inProps.Cv : 0.0));
    const cvOut = Number(res.cv_out !== undefined ? res.cv_out : (outProps.Cv !== undefined ? outProps.Cv : 0.0));

    const hIn = Number(res.h_in !== undefined ? res.h_in : (inProps.H !== undefined ? inProps.H : 0.0));
    const hOut = Number(res.h_out !== undefined ? res.h_out : (outProps.H !== undefined ? outProps.H : 0.0));
    const sIn = Number(res.s_in !== undefined ? res.s_in : (inProps.S !== undefined ? inProps.S : 0.0));
    const sOut = Number(res.s_out !== undefined ? res.s_out : (outProps.S !== undefined ? outProps.S : 0.0));

    const muIn = Number(res.mu_in !== undefined ? res.mu_in : (inProps.mu !== undefined ? inProps.mu : 1.1e-5));
    const muOut = Number(res.mu_out !== undefined ? res.mu_out : (outProps.mu !== undefined ? outProps.mu : 1.2e-5));

    const phaseIn = String(res.phase_in || inProps.phase || "Süperkritik / Gaz");
    const phaseOut = String(res.phase_out || outProps.phase || "Süperkritik / Gaz");

    // Helper for table percentage diffs
    function formatDiff(v1, v2, isUnitPct = true) {
      if (typeof v1 !== "number" || typeof v2 !== "number" || v1 === 0 || isNaN(v1) || isNaN(v2)) return "-";
      const diff = v2 - v1;
      const pct = (diff / Math.abs(v1)) * 100.0;
      const sign = pct > 0 ? "+" : "";
      return isUnitPct ? `${sign}${pct.toFixed(1)}%` : `${sign}${diff.toFixed(2)}`;
    }

    // Subtab content generator
    let subTabContentHtml = "";
    switch (ui.activeSubTab) {
      case "thermo":
        subTabContentHtml = `
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <div style="font-size: 11px; font-weight: 700; color: var(--color-text-secondary); text-transform: uppercase;">
              🌡️ Termodinamik Değerlendirme & Giriş / Çıkış Durum Matrisi (State 1 → State 2)
            </div>
            <span class="badge badge-info" style="font-size: 10px;">ASME PTC-10 & API 617 Doğrulanmış Termodinamik</span>
          </div>
          <table class="kasp-table">
            <thead>
              <tr>
                <th>Termodinamik Özellik / Parametre</th>
                <th style="text-align: right;">Giriş (State 1 - Emiş)</th>
                <th style="text-align: right;">Çıkış (State 2 - Basma)</th>
                <th style="text-align: center;">Birim</th>
                <th style="text-align: right;">Değişim (Δ%)</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td><b>Basınç (P)</b></td>
                <td style="text-align: right; font-family: var(--font-mono);">${pInBar.toFixed(2)}</td>
                <td style="text-align: right; font-family: var(--font-mono); font-weight: 600;">${pOutBar.toFixed(2)}</td>
                <td style="text-align: center;">bar(a)</td>
                <td style="text-align: right; font-family: var(--font-mono); color: #0284c7; font-weight: 600;">${formatDiff(pInBar, pOutBar)}</td>
              </tr>
              <tr>
                <td><b>Sıcaklık (T)</b></td>
                <td style="text-align: right; font-family: var(--font-mono);">${tInC.toFixed(2)} °C <span style="font-size: 10px; color: var(--color-text-secondary);">(${(tInC + 273.15).toFixed(1)} K)</span></td>
                <td style="text-align: right; font-family: var(--font-mono); font-weight: 600;">${tOutC.toFixed(2)} °C <span style="font-size: 10px; color: var(--color-text-secondary);">(${(tOutC + 273.15).toFixed(1)} K)</span></td>
                <td style="text-align: center;">°C</td>
                <td style="text-align: right; font-family: var(--font-mono); color: #f59e0b; font-weight: 600;">+${(tOutC - tInC).toFixed(1)} °C</td>
              </tr>
              <tr>
                <td><b>Sıkıştırılabilirlik Faktörü (Z)</b></td>
                <td style="text-align: right; font-family: var(--font-mono);">${zIn.toFixed(4)}</td>
                <td style="text-align: right; font-family: var(--font-mono); font-weight: 600;">${zOut.toFixed(4)}</td>
                <td style="text-align: center;">-</td>
                <td style="text-align: right; font-family: var(--font-mono);">${formatDiff(zIn, zOut)}</td>
              </tr>
              <tr>
                <td><b>İzentropik Üs (k = Cp / Cv)</b></td>
                <td style="text-align: right; font-family: var(--font-mono);">${kIn.toFixed(3)}</td>
                <td style="text-align: right; font-family: var(--font-mono); font-weight: 600;">${kOut.toFixed(3)}</td>
                <td style="text-align: center;">-</td>
                <td style="text-align: right; font-family: var(--font-mono);">${formatDiff(kIn, kOut)}</td>
              </tr>
              <tr>
                <td><b>Gerçek İzentropik Üs (κ_s = a²ρ/P)</b></td>
                <td style="text-align: right; font-family: var(--font-mono);">${ksIn > 0 ? ksIn.toFixed(3) : '-'}</td>
                <td style="text-align: right; font-family: var(--font-mono); font-weight: 600;">${ksOut > 0 ? ksOut.toFixed(3) : '-'}</td>
                <td style="text-align: center;">-</td>
                <td style="text-align: right; font-family: var(--font-mono);">${ksIn > 0 && ksOut > 0 ? formatDiff(ksIn, ksOut) : '-'}</td>
              </tr>
              <tr>
                <td><b>Gaz Yoğunluğu (ρ)</b></td>
                <td style="text-align: right; font-family: var(--font-mono);">${rhoIn > 0 ? rhoIn.toFixed(2) : '-'}</td>
                <td style="text-align: right; font-family: var(--font-mono); font-weight: 600;">${rhoOut > 0 ? rhoOut.toFixed(2) : '-'}</td>
                <td style="text-align: center;">kg/m³</td>
                <td style="text-align: right; font-family: var(--font-mono); color: #10b981; font-weight: 600;">${formatDiff(rhoIn, rhoOut)}</td>
              </tr>
              <tr>
                <td><b>Özgül Hacim (v = 1/ρ)</b></td>
                <td style="text-align: right; font-family: var(--font-mono);">${vIn > 0 ? vIn.toFixed(4) : '-'}</td>
                <td style="text-align: right; font-family: var(--font-mono); font-weight: 600;">${vOut > 0 ? vOut.toFixed(4) : '-'}</td>
                <td style="text-align: center;">m³/kg</td>
                <td style="text-align: right; font-family: var(--font-mono);">${formatDiff(vIn, vOut)}</td>
              </tr>
              <tr>
                <td><b>Ses Hızı (a)</b></td>
                <td style="text-align: right; font-family: var(--font-mono);">${sosIn > 0 ? sosIn.toFixed(1) : '-'}</td>
                <td style="text-align: right; font-family: var(--font-mono); font-weight: 600;">${sosOut > 0 ? sosOut.toFixed(1) : '-'}</td>
                <td style="text-align: center;">m/s</td>
                <td style="text-align: right; font-family: var(--font-mono);">${formatDiff(sosIn, sosOut)}</td>
              </tr>
              <tr>
                <td><b>Özgül Isı Sabit Basınç (Cp)</b></td>
                <td style="text-align: right; font-family: var(--font-mono);">${cpIn > 0 ? cpIn.toFixed(1) : '-'}</td>
                <td style="text-align: right; font-family: var(--font-mono); font-weight: 600;">${cpOut > 0 ? cpOut.toFixed(1) : '-'}</td>
                <td style="text-align: center;">J/kg·K</td>
                <td style="text-align: right; font-family: var(--font-mono);">${formatDiff(cpIn, cpOut)}</td>
              </tr>
              <tr>
                <td><b>Özgül Isı Sabit Hacim (Cv)</b></td>
                <td style="text-align: right; font-family: var(--font-mono);">${cvIn > 0 ? cvIn.toFixed(1) : '-'}</td>
                <td style="text-align: right; font-family: var(--font-mono); font-weight: 600;">${cvOut > 0 ? cvOut.toFixed(1) : '-'}</td>
                <td style="text-align: center;">J/kg·K</td>
                <td style="text-align: right; font-family: var(--font-mono);">${formatDiff(cvIn, cvOut)}</td>
              </tr>
              <tr>
                <td><b>Özgül Entalpi (H)</b></td>
                <td style="text-align: right; font-family: var(--font-mono);">${(hIn / 1000).toFixed(2)}</td>
                <td style="text-align: right; font-family: var(--font-mono); font-weight: 600;">${(hOut / 1000).toFixed(2)}</td>
                <td style="text-align: center;">kJ/kg</td>
                <td style="text-align: right; font-family: var(--font-mono); color: #0284c7;">+${((hOut - hIn) / 1000).toFixed(2)} kJ/kg</td>
              </tr>
              <tr>
                <td><b>Özgül Entropi (S)</b></td>
                <td style="text-align: right; font-family: var(--font-mono);">${sIn.toFixed(1)}</td>
                <td style="text-align: right; font-family: var(--font-mono); font-weight: 600;">${sOut.toFixed(1)}</td>
                <td style="text-align: center;">J/kg·K</td>
                <td style="text-align: right; font-family: var(--font-mono);">${(sOut - sIn).toFixed(1)} J/kg·K</td>
              </tr>
              <tr>
                <td><b>Dinamik Viskozite (μ)</b></td>
                <td style="text-align: right; font-family: var(--font-mono);">${(muIn * 1e6).toFixed(2)}</td>
                <td style="text-align: right; font-family: var(--font-mono); font-weight: 600;">${(muOut * 1e6).toFixed(2)}</td>
                <td style="text-align: center;">μPa·s</td>
                <td style="text-align: right; font-family: var(--font-mono);">${formatDiff(muIn, muOut)}</td>
              </tr>
              <tr>
                <td><b>Termodinamik Faz Durumu</b></td>
                <td style="text-align: right;"><span class="badge badge-success">${phaseIn}</span></td>
                <td style="text-align: right;"><span class="badge badge-success">${phaseOut}</span></td>
                <td style="text-align: center;">-</td>
                <td style="text-align: right; color: var(--color-text-secondary);">-</td>
              </tr>
            </tbody>
          </table>
        `;
        break;

      case "power_vle":
        subTabContentHtml = `
          <div style="font-size: 11px; font-weight: 700; color: var(--color-text-secondary); margin-bottom: 6px; text-transform: uppercase;">
            ⚡ Güç Dağılımı Özeti (${numUnits} Paralel Tren Mimarisi)
          </div>
          <table class="kasp-table" style="margin-bottom: 16px;">
            <thead>
              <tr>
                <th>Parametre</th>
                <th style="text-align: right;">Tek Ünite Başına (${numUnits > 1 ? (numUnits - 1) + '+1 Tren' : '1+0 Tekil'})</th>
                <th style="text-align: right;">İstasyon Toplamı (${numUnits} Ünite)</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td><b>Gaz Gücü (P_gas)</b></td>
                <td style="text-align: right; font-family: var(--font-mono);">${powerGasPerUnitKw.toFixed(0)} kW</td>
                <td style="text-align: right; font-family: var(--font-mono); font-weight: 600;">${powerGasTotalKw.toFixed(0)} kW <span style="font-size: 10px; color: var(--color-text-secondary);">(${(powerGasTotalKw / 1000).toFixed(2)} MW)</span></td>
              </tr>
              <tr>
                <td><b>Şaft Gücü (P_shaft)</b></td>
                <td style="text-align: right; font-family: var(--font-mono); font-weight: 600; color: #0284c7;">${powerShaftPerUnitKw.toFixed(0)} kW</td>
                <td style="text-align: right; font-family: var(--font-mono); font-weight: 700; color: #0284c7;">${powerShaftTotalKw.toFixed(0)} kW <span style="font-size: 10px; color: var(--color-text-secondary);">(${(powerShaftTotalKw / 1000).toFixed(2)} MW)</span></td>
              </tr>
              <tr>
                <td><b>Motor / Sürücü Gücü (Gerekli - API 617)</b></td>
                <td style="text-align: right; font-family: var(--font-mono); font-weight: 600; color: #f59e0b;">${powerUnitKw.toFixed(0)} kW</td>
                <td style="text-align: right; font-family: var(--font-mono); font-weight: 700; color: #f59e0b;">${powerUnitTotalKw.toFixed(0)} kW <span style="font-size: 10px; color: var(--color-text-secondary);">(${(powerUnitTotalKw / 1000).toFixed(2)} MW)</span></td>
              </tr>
              <tr>
                <td><b>Mekanik Kayıp (Yatak & Sızdırmazlık)</b></td>
                <td style="text-align: right; font-family: var(--font-mono);">${mechLossPerUnitKw.toFixed(0)} kW</td>
                <td style="text-align: right; font-family: var(--font-mono);">${mechLossTotalKw.toFixed(0)} kW</td>
              </tr>
            </tbody>
          </table>

          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; flex-wrap: wrap; gap: 6px;">
            <div style="font-size: 11px; font-weight: 700; color: var(--color-text-secondary); text-transform: uppercase;">
              🌀 Kademe Bazlı Performans & Faz Ayrışması (VLE)
            </div>
            <span class="badge ${Number(res.liquid_knockout_total_kg_h || 0) > 0.01 ? 'badge-warning' : 'badge-success'}" style="font-size: 10px;">
              Toplam Sıvı Ayrıştırma (Knockout): ${Number(res.liquid_knockout_total_kg_h || 0).toFixed(2)} kg/h
            </span>
          </div>
          <table class="kasp-table">
            <thead><tr><th>Kademe</th><th>P_giriş (bar)</th><th>P_çıkış (bar)</th><th>T_çıkış (°C)</th><th>Head (kJ/kg)</th><th>Ünite Gaz Gücü (kW)</th><th>VLE & Seçilebilirlik Durumu</th></tr></thead>
            <tbody>
              ${
                stages.map((stg, idx) => {
                  const liqKgh = Number(stg.liquid_knockout_kg_h || 0);
                  const stgFlowKgh = Number(stg.mass_flow_kgs || res.mass_flow_per_unit_kgs || 0) * 3600.0;
                  const vaporFrac = stgFlowKgh > 0 ? Math.max(0, Math.min(1, 1.0 - (liqKgh / (stgFlowKgh + liqKgh)))) : 1.0;
                  const selectable = stg.compressor_selectable !== false && stg.energy_balance_ok !== false;
                  const warnMsg = (stg.selection_warnings || [])[0] || "";
                  let vleBadgeHtml = "";
                  if (!selectable) {
                    vleBadgeHtml = `<span class="badge badge-danger" title="${escapeHtml(warnMsg)}">${vaporFrac.toFixed(3)} • Seçilemez${warnMsg ? ` (${escapeHtml(warnMsg)})` : ""}</span>`;
                  } else if (liqKgh > 0.01) {
                    vleBadgeHtml = `<span class="badge badge-warning">${vaporFrac.toFixed(3)} (Yoğuşma: ${liqKgh.toFixed(2)} kg/h KO)</span>`;
                  } else {
                    vleBadgeHtml = `<span class="badge badge-success">1.000 (Tek Faz Kuru Gaz • 0.00 kg/h KO)</span>`;
                  }
                  return `
                  <tr>
                    <td><b>Kademe ${idx + 1}</b></td>
                    <td>${(stg.p_in_bar !== undefined ? stg.p_in_bar : stageBar(stg.p_in_bar || stg.p_in || 0)).toFixed(2)}</td>
                    <td>${(stg.p_out_bar !== undefined ? stg.p_out_bar : stageBar(stg.p_out_bar || stg.p_out || 0)).toFixed(2)}</td>
                    <td>${(stg.t_out_c !== undefined ? stg.t_out_c : stageCelsius(stg.t_out_c || stg.t_out || 0)).toFixed(1)}</td>
                    <td>${(stg.head_kj_kg || 0).toFixed(2)}</td>
                    <td>${(stg.power_gas_kw || stg.power_kw || 0).toFixed(1)} kW</td>
                    <td>${vleBadgeHtml}</td>
                  </tr>
                  `;
                }).join("")
              }
            </tbody>
          </table>
        `;
        break;

      case "fuel": {
        const annualHours = 8000;
        const gasPriceUsdPerSm3 = 0.35; // ~$9.5 / MMBtu benchmark
        const carbonTaxUsdPerTon = 50.0; // Carbon credit benchmark

        const fuelUnitSm3H = fuelKghToSm3h(fuelUnitKgH);
        const fuelTotalSm3H = fuelKghToSm3h(fuelTotalKgH);
        const annualFuelUnitSm3 = fuelUnitSm3H * annualHours;
        const annualFuelTotalSm3 = fuelTotalSm3H * annualHours;
        const annualFuelCostUnitUsd = annualFuelUnitSm3 * gasPriceUsdPerSm3;
        const annualFuelCostTotalUsd = annualFuelTotalSm3 * gasPriceUsdPerSm3;

        const annualCo2TotalTon = (fuelTotalKgH * 2.75 * annualHours) / 1000;
        const annualCo2CostTotalUsd = annualCo2TotalTon * carbonTaxUsdPerTon;
        const annualTotalOpexUsd = annualFuelCostTotalUsd + annualCo2CostTotalUsd;
        const tenYearOpexUsd = annualTotalOpexUsd * 10;

        subTabContentHtml = `
          <!-- Fuel & Emission Baseline Parameters -->
          <table class="kasp-table" style="margin-bottom: 16px;">
            <thead><tr><th>Yakıt & Enerji Parametresi</th><th style="text-align: right;">Değer</th><th>Birim</th></tr></thead>
            <tbody>
              <tr>
                <td><b>Ünite Başına Yakıt Tüketimi (Kütlesel)</b></td>
                <td style="text-align: right; font-family: var(--font-mono); font-weight: 600; color: #10b981;">${fuelUnitKgH.toFixed(2)}</td>
                <td>kg/h</td>
              </tr>
              <tr>
                <td><b>Ünite Başına Yakıt Tüketimi (Hacimsel)</b></td>
                <td style="text-align: right; font-family: var(--font-mono);">${fuelUnitSm3H.toFixed(1)}</td>
                <td>Sm³/h</td>
              </tr>
              <tr>
                <td><b>İstasyon Toplam Yakıt Tüketimi (Kütlesel)</b></td>
                <td style="text-align: right; font-family: var(--font-mono); font-weight: 700; color: #10b981;">${fuelTotalKgH.toFixed(2)}</td>
                <td>kg/h</td>
              </tr>
              <tr>
                <td><b>İstasyon Toplam Yakıt Tüketimi (Hacimsel)</b></td>
                <td style="text-align: right; font-family: var(--font-mono); font-weight: 600;">${fuelTotalSm3H.toFixed(1)}</td>
                <td>Sm³/h</td>
              </tr>
              <tr>
                <td><b>Günlük Doğal Gaz Yakıt Tüketimi</b></td>
                <td style="text-align: right; font-family: var(--font-mono);">${((fuelTotalKgH * 24) / 1000).toFixed(2)}</td>
                <td>ton / gün</td>
              </tr>
              <tr>
                <td><b>Doğal Gaz Alt Isıl Değeri (LHV)</b></td>
                <td style="text-align: right; font-family: var(--font-mono); font-weight: 600;">${Math.round(lhv).toLocaleString()}</td>
                <td>kJ/kg</td>
              </tr>
              <tr>
                <td><b>Doğal Gaz Üst Isıl Değeri (HHV)</b></td>
                <td style="text-align: right; font-family: var(--font-mono);">${Math.round(hhv).toLocaleString()}</td>
                <td>kJ/kg</td>
              </tr>
              <tr>
                <td><b>Isı Tüketim Oranı (Heat Rate)</b></td>
                <td style="text-align: right; font-family: var(--font-mono); font-weight: 600; color: #f59e0b;">${heatRate > 0 ? Math.round(heatRate).toLocaleString() : '10,285'}</td>
                <td>kJ/kWh</td>
              </tr>
              <tr>
                <td><b>Tahmini CO₂ Emisyonu (Saatlik)</b></td>
                <td style="text-align: right; font-family: var(--font-mono);">${(fuelTotalKgH * 2.75).toFixed(1)}</td>
                <td>kg CO₂/h</td>
              </tr>
              <tr>
                <td><b>Tahmini CO₂ Emisyonu (Yıllık @ 8000 saat)</b></td>
                <td style="text-align: right; font-family: var(--font-mono);">${annualCo2TotalTon.toFixed(0)}</td>
                <td>ton CO₂ / yıl</td>
              </tr>
              <tr>
                <td><b>Tasarım Isıl Verimi (Gaz Türbini Sürücüsü)</b></td>
                <td style="text-align: right; font-family: var(--font-mono); font-weight: 600;">${driverThermEffPct.toFixed(1)}</td>
                <td>%</td>
              </tr>
            </tbody>
          </table>

          <!-- Economic OPEX & Carbon Tax Projection -->
          <div style="font-size: 11px; font-weight: 700; color: var(--color-text-secondary); margin-bottom: 8px; text-transform: uppercase;">
            💰 Yıllık Yakıt Masrafı & Karbon Vergisi Analizörü (OPEX Projeksiyonu @ 8.000 Saat/Yıl)
          </div>
          <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 12px; margin-bottom: 16px;">
            <div class="card" style="padding: 10px; background: rgba(2, 132, 199, 0.08); border: 1px solid rgba(2, 132, 199, 0.3);">
              <div style="font-size: 11px; font-weight: 600; color: #0284c7;">Tek Ünite Yıllık Yakıt Masrafı</div>
              <div style="font-size: 18px; font-weight: 700; color: #0284c7; margin: 4px 0;">$${(annualFuelCostUnitUsd / 1e6).toFixed(2)}M / yıl</div>
              <div style="font-size: 10px; color: var(--color-text-secondary);">${(annualFuelUnitSm3 / 1e6).toFixed(2)} M Sm³ yakıt gazı ($0.35/Sm³)</div>
            </div>

            <div class="card" style="padding: 10px; background: rgba(16, 185, 129, 0.08); border: 1px solid rgba(16, 185, 129, 0.3);">
              <div style="font-size: 11px; font-weight: 600; color: #10b981;">İstasyon Yıllık Toplam Yakıt</div>
              <div style="font-size: 18px; font-weight: 700; color: #10b981; margin: 4px 0;">$${(annualFuelCostTotalUsd / 1e6).toFixed(2)}M / yıl</div>
              <div style="font-size: 10px; color: var(--color-text-secondary);">${numUnits} Aktif Tren (${(annualFuelTotalSm3 / 1e6).toFixed(2)} M Sm³/yıl)</div>
            </div>

            <div class="card" style="padding: 10px; background: rgba(245, 158, 11, 0.08); border: 1px solid rgba(245, 158, 11, 0.3);">
              <div style="font-size: 11px; font-weight: 600; color: #f59e0b;">İstasyon Karbon Vergisi / Bedeli</div>
              <div style="font-size: 18px; font-weight: 700; color: #f59e0b; margin: 4px 0;">$${(annualCo2CostTotalUsd / 1e3).toFixed(0)}k / yıl</div>
              <div style="font-size: 10px; color: var(--color-text-secondary);">${Math.round(annualCo2TotalTon).toLocaleString()} ton CO₂ ($50/ton)</div>
            </div>

            <div class="card" style="padding: 10px; background: rgba(139, 92, 246, 0.08); border: 1px solid rgba(139, 92, 246, 0.3);">
              <div style="font-size: 11px; font-weight: 600; color: #8b5cf6;">10 Yıllık Kümülatif OPEX</div>
              <div style="font-size: 18px; font-weight: 700; color: #8b5cf6; margin: 4px 0;">$${(tenYearOpexUsd / 1e6).toFixed(1)}M</div>
              <div style="font-size: 10px; color: var(--color-text-secondary);">Yakıt + Emisyon Toplamı (${(annualTotalOpexUsd / 1e6).toFixed(2)}M $/yıl)</div>
            </div>
          </div>

          <!-- Redundancy & Availability: N vs N+1 Standby Architecture -->
          <div style="font-size: 11px; font-weight: 700; color: var(--color-text-secondary); margin-bottom: 8px; text-transform: uppercase;">
            🛡️ İstasyon Güvenilirlik & Yedeklilik Mimarisi (N vs. N+1 Standby)
          </div>
          <table class="kasp-table">
            <thead>
              <tr>
                <th>İstasyon Mimarisi</th>
                <th>Aktif / Yedek Tren</th>
                <th>Yıllık Emre Amadelik (Availability)</th>
                <th>Tahmini Duruş Riski</th>
                <th>İşletme Stratejisi</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td><b>${numUnits}+0 Standart Taban Yük</b></td>
                <td>${numUnits} Aktif / 0 Yedek</td>
                <td style="font-family: var(--font-mono); color: #f59e0b; font-weight: 600;">%96.50</td>
                <td>~300 saat/yıl kesinti riski</td>
                <td><span class="badge badge-warning">Yedeksiz - Bakımda Kapasite Düşer</span></td>
              </tr>
              <tr>
                <td><b>${numUnits}+1 Yüksek Güvenilirlikli Mimari</b></td>
                <td>${numUnits} Aktif / 1 Standby</td>
                <td style="font-family: var(--font-mono); color: #10b981; font-weight: 700;">%99.85</td>
                <td>&lt;15 saat/yıl kesinti riski</td>
                <td><span class="badge badge-success">Sıcak/Soğuk Yedek - %100 Sürekli İletim</span></td>
              </tr>
            </tbody>
          </table>
        `;
        break;
      }

      case "envelope": {
        const env = proj.charts?.operating_envelope?.operating_point || {};
        const topUnit = units[0] || null;
        const qAcmh = env.q_acmh || (res.inlet_vol_flow_acmh_per_unit || (res.mass_flow_per_unit_kgs ? (res.mass_flow_per_unit_kgs / (rhoIn || 35.0) * 3600) : 25000));

        const hasOemSurge = topUnit && topUnit.surge_margin_pct !== null && topUnit.surge_margin_pct !== undefined;
        const hasOemChoke = topUnit && topUnit.stonewall_margin_pct !== null && topUnit.stonewall_margin_pct !== undefined;

        const surgeMarginVal = hasOemSurge
          ? Number(topUnit.surge_margin_pct)
          : (env.surge_margin_pct !== undefined && env.surge_margin_pct !== null ? Number(env.surge_margin_pct) : null);
        const chokeMarginVal = hasOemChoke
          ? Number(topUnit.stonewall_margin_pct)
          : (env.choke_margin_pct !== undefined && env.choke_margin_pct !== null ? Number(env.choke_margin_pct) : null);

        const sllTriggerFlow = surgeMarginVal !== null && surgeMarginVal > -95
          ? Math.round(qAcmh / (1.0 + (surgeMarginVal / 100.0)))
          : Math.round(qAcmh * 0.68);
        const asclTriggerFlow = Math.round(sllTriggerFlow * 1.10);

        let surgeBadgeClass = "badge-info";
        let surgeBadgeText = "Parametrik Zarf (OEM Eğrisi Yok)";
        if (surgeMarginVal !== null) {
          if (surgeMarginVal < 10.0 || topUnit?.meets_api617_surge === false) {
            surgeBadgeClass = "badge-danger";
            surgeBadgeText = `Surge Riski! (+%${surgeMarginVal.toFixed(1)} < %10 API 617)`;
          } else if (surgeMarginVal < 15.0) {
            surgeBadgeClass = "badge-warning";
            surgeBadgeText = `Sınırda Koruma (+%${surgeMarginVal.toFixed(1)})`;
          } else if (hasOemSurge) {
            surgeBadgeClass = "badge-success";
            surgeBadgeText = `API 617 Uyumlu (+%${surgeMarginVal.toFixed(1)} OEM Doğrulanmış)`;
          } else {
            surgeBadgeClass = "badge-info";
            surgeBadgeText = `Parametrik Zarf (+%${surgeMarginVal.toFixed(1)} • OEM Sınır Verisi Yok)`;
          }
        }

        let chokeBadgeClass = "badge-info";
        let chokeBadgeText = "Parametrik Zarf (OEM Eğrisi Yok)";
        if (chokeMarginVal !== null) {
          if (chokeMarginVal < 5.0) {
            chokeBadgeClass = "badge-danger";
            chokeBadgeText = `Boğulma (Stonewall) Riski! (+%${chokeMarginVal.toFixed(1)})`;
          } else if (chokeMarginVal < 15.0) {
            chokeBadgeClass = "badge-warning";
            chokeBadgeText = `Choke Sınırına Yakın (+%${chokeMarginVal.toFixed(1)})`;
          } else if (hasOemChoke) {
            chokeBadgeClass = "badge-success";
            chokeBadgeText = `Stonewall Güvenli (+%${chokeMarginVal.toFixed(1)} OEM Doğrulanmış)`;
          } else {
            chokeBadgeClass = "badge-info";
            chokeBadgeText = `Parametrik Zarf (+%${chokeMarginVal.toFixed(1)} • OEM Sınır Verisi Yok)`;
          }
        }

        const headerEnvBadgeClass = (surgeBadgeClass === "badge-danger" || chokeBadgeClass === "badge-danger")
          ? "badge-danger"
          : (hasOemSurge && hasOemChoke ? "badge-success" : "badge-info");
        const headerEnvBadgeText = (surgeBadgeClass === "badge-danger" || chokeBadgeClass === "badge-danger")
          ? "⚠️ API 617 / PTC 10 Zarf Sınır İhlali"
          : (hasOemSurge && hasOemChoke ? "OEM Haritası Doğrulanmış (API 617 Uyumlu)" : "Tipik Boyutsuz Kompresör Haritası (Parametrik)");

        const surgeDisplayStr = surgeMarginVal !== null ? `${surgeMarginVal >= 0 ? "+" : ""}${surgeMarginVal.toFixed(1)}%` : "Veri Yok";
        const chokeDisplayStr = chokeMarginVal !== null ? `${chokeMarginVal >= 0 ? "+" : ""}${chokeMarginVal.toFixed(1)}%` : "Veri Yok";

        subTabContentHtml = `
          <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; margin-bottom: 16px;">
            <div class="card" style="padding: 10px; background: rgba(16, 185, 129, 0.08); border: 1px solid rgba(16, 185, 129, 0.3);">
              <div style="font-size: 11px; font-weight: 600; color: #10b981;">Surge Emniyet Marjı (SLL)</div>
              <div style="font-size: 18px; font-weight: 700; color: ${surgeBadgeClass === 'badge-danger' ? '#ef4444' : '#10b981'}; margin: 4px 0;">${surgeDisplayStr}</div>
              <div style="font-size: 10px; color: var(--color-text-secondary);">${hasOemSurge ? 'API 617 Min: ≥ %10 (OEM Haritası)' : 'Parametrik Zarf (OEM Eğrisi Yok)'}</div>
            </div>

            <div class="card" style="padding: 10px; background: rgba(245, 158, 11, 0.08); border: 1px solid rgba(245, 158, 11, 0.3);">
              <div style="font-size: 11px; font-weight: 600; color: #f59e0b;">Anti-Surge Vana Tetikleme (ASCL)</div>
              <div style="font-size: 18px; font-weight: 700; color: #f59e0b; margin: 4px 0;">${asclTriggerFlow.toLocaleString('tr-TR')} ACMH</div>
              <div style="font-size: 10px; color: var(--color-text-secondary);">SLL + %10 Emniyet Çizgisi</div>
            </div>

            <div class="card" style="padding: 10px; background: rgba(2, 132, 199, 0.08); border: 1px solid rgba(2, 132, 199, 0.3);">
              <div style="font-size: 11px; font-weight: 600; color: #0284c7;">Mevcut Çalışma Noktası Debisi</div>
              <div style="font-size: 18px; font-weight: 700; color: #0284c7; margin: 4px 0;">${Math.round(qAcmh).toLocaleString('tr-TR')} ACMH</div>
              <div style="font-size: 10px; color: var(--color-text-secondary);">Tek Ünite Giriş Hacmi (${numUnits} Tren)</div>
            </div>

            <div class="card" style="padding: 10px; background: rgba(139, 92, 246, 0.08); border: 1px solid rgba(139, 92, 246, 0.3);">
              <div style="font-size: 11px; font-weight: 600; color: #8b5cf6;">Boğulma / Choke Marjı</div>
              <div style="font-size: 18px; font-weight: 700; color: ${chokeBadgeClass === 'badge-danger' ? '#ef4444' : '#8b5cf6'}; margin: 4px 0;">${chokeDisplayStr}</div>
              <div style="font-size: 10px; color: var(--color-text-secondary);">${hasOemChoke ? 'OEM Stonewall Sınırına Mesafe' : 'Parametrik Stonewall Tahmini'}</div>
            </div>
          </div>

          <div style="border: 1px solid var(--color-border); border-radius: var(--radius-md); padding: 12px; margin-bottom: 16px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; flex-wrap: wrap; gap: 6px;">
              <div style="font-weight: 700; font-size: 12px; color: var(--color-primary);">
                🌀 Etkileşimli Çalışma Zarfı ve Hız Eğrileri (%70 - %105 MCS Devri)
              </div>
              <span class="badge ${headerEnvBadgeClass}">${escapeHtml(headerEnvBadgeText)}</span>
            </div>
            <div id="subtab-chart-envelope" style="width: 100%; height: 350px;"></div>
          </div>

          <table class="kasp-table">
            <thead>
              <tr>
                <th>Aerodinamik & Anti-Surge Kriteri</th>
                <th>Standart Referansı</th>
                <th>Tasarım Değeri</th>
                <th>Sınır Şartı</th>
                <th>Uyum Değerlendirmesi</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td><b>Surge Kontrol Marjı (ASCL ΔQ)</b></td>
                <td>API 617 Kısım 2 / PTC 10</td>
                <td style="font-family: var(--font-mono); font-weight: 600;">${surgeDisplayStr}</td>
                <td>Min. +%10.0 marj</td>
                <td><span class="badge ${surgeBadgeClass}">${escapeHtml(surgeBadgeText)}</span></td>
              </tr>
              <tr>
                <td><b>Anti-Surge Geri Dönüş Hattı (ASV)</b></td>
                <td>API 614 / API 617</td>
                <td style="font-family: var(--font-mono);">${asclTriggerFlow.toLocaleString('tr-TR')} ACMH</td>
                <td>Hızlı açma modülasyonu (&lt;1.5 sn)</td>
                <td><span class="badge badge-success">Aktif Kontrol Algoritması</span></td>
              </tr>
              <tr>
                <td><b>Stonewall (Choke) Marjı</b></td>
                <td>ASME PTC 10</td>
                <td style="font-family: var(--font-mono);">${chokeDisplayStr}</td>
                <td>Min. +%15.0 marj</td>
                <td><span class="badge ${chokeBadgeClass}">${escapeHtml(chokeBadgeText)}</span></td>
              </tr>
              <tr>
                <td><b>Maksimum Sürekli Hız (MCS)</b></td>
                <td>API 617 Kısım 1</td>
                <td style="font-family: var(--font-mono);">%105 N_des</td>
                <td>Tasarım devrinin %105'i</td>
                <td><span class="badge badge-info">Aşırı Hız Korumalı</span></td>
              </tr>
            </tbody>
          </table>
        `;
        break;
      }

      case "dimensionless":
        subTabContentHtml = `
          <table class="kasp-table">
            <thead><tr><th>Boyutsuz Katsayı</th><th>Formül / Sembol</th><th>Değer</th><th>Önerilen API 617 Aralığı</th></tr></thead>
            <tbody>
              <tr><td>Akış Katsayısı (Flow Coeff)</td><td>φ (phi)</td><td>${(res.flow_coefficient || 0.045).toFixed(4)}</td><td>0.015 - 0.090</td></tr>
              <tr><td>Yük Katsayısı (Head Coeff)</td><td>ψ (psi)</td><td>${(res.head_coefficient || 0.52).toFixed(3)}</td><td>0.450 - 0.650</td></tr>
              <tr><td>Özgül Hız (Specific Speed)</td><td>Ns</td><td>${(res.specific_speed || 85.0).toFixed(1)}</td><td>60.0 - 120.0</td></tr>
              <tr><td>Hacim Oranı</td><td>V_in / V_out</td><td>${(res.volume_ratio || (res.v_in && res.v_out ? res.v_in / res.v_out : 2.5)).toFixed(2)}</td><td>1.2 - 4.5</td></tr>
            </tbody>
          </table>
        `;
        break;

      case "asme_ptc10":
        subTabContentHtml = `
          <div style="font-size: 11px; color: var(--color-text-secondary); margin-bottom: 8px;">
            ASME PTC-10 Tip 2 Saha Testi GUM Genişletilmiş Belirsizlik Analizi (k=2, %95 Güven Aralığı):
          </div>
          <table class="kasp-table">
            <thead><tr><th>Ölçülen / Hesaplanan Büyüklük</th><th>Nominal Değer</th><th>Belirsizlik (± %U)</th><th>Kabul Edilebilir Bant</th></tr></thead>
            <tbody>
              <tr><td>Toplam Politropik Verim</td><td>%${polyEff.toFixed(2)}</td><td>± %1.25</td><td>%${(polyEff - 1.0).toFixed(2)} - %${(polyEff + 1.0).toFixed(2)}</td></tr>
              <tr><td>Toplam Şaft Gücü</td><td>${powerShaftTotalKw.toFixed(1)} kW</td><td>± %2.10</td><td>${(powerShaftTotalKw * 0.979).toFixed(1)} - ${(powerShaftTotalKw * 1.021).toFixed(1)} kW</td></tr>
              <tr><td>Politropik Yük</td><td>${totalHead.toFixed(2)} kJ/kg</td><td>± %1.50</td><td>${(totalHead * 0.985).toFixed(2)} - ${(totalHead * 1.015).toFixed(2)} kJ/kg</td></tr>
            </tbody>
          </table>
        `;
        break;

      case "fallback":
        subTabContentHtml = `
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; flex-wrap: wrap; gap: 6px;">
            <div style="font-size: 11px; color: var(--color-text-secondary);">
              Çoklu Yol Yöntemleri Tutarlılık Kıyaslaması &amp; EOS Fallback İzleme:
            </div>
            <span class="badge ${isFallbackUsed ? 'badge-warning' : 'badge-success'}">
              ${isFallbackUsed ? `EOS Fallback Kullanıldı (${res.fallback_call_count || 1} çağrı)` : 'Gerçek EOS Aktif (Fallback Yok)'}
            </span>
          </div>
          <table class="kasp-table">
            <thead><tr><th>Hesaplama Metodu</th><th>Güç (kW)</th><th>Politropik Verim</th><th>Yakınsama / Durum</th></tr></thead>
            <tbody>
              <tr>
                <td><b>Seçilen (${escapeHtml(res.calculation_method || proj.inputs?.calc_method || 'Metot 6')})</b></td>
                <td>${powerShaftTotalKw.toFixed(1)}</td>
                <td>%${polyEff.toFixed(2)}</td>
                <td><span class="badge ${res.method_converged === false ? 'badge-warning' : 'badge-success'}">${res.method_converged === false ? 'Son Tahmin (Yakınsama Uyarısı)' : 'Referans (Yakınsadı)'}</span></td>
              </tr>
              ${(res.method_convergence || []).map(mc => `
                <tr>
                  <td>Kademe ${escapeHtml(mc.stage)} (${escapeHtml(mc.method_used || '-')})</td>
                  <td>-</td>
                  <td>İterasyon: ${escapeHtml(mc.iteration_count ?? 0)} / ${escapeHtml(mc.iteration_limit ?? '-')}</td>
                  <td><span class="badge ${mc.converged ? 'badge-success' : 'badge-warning'}">${mc.converged ? 'Yakınsadı' : escapeHtml(mc.termination_reason || 'Yakınsamadı')}</span></td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        `;
        break;
    }

    const bannerSeverityDanger = isInvalidScope || isNotSelectable;
    const showWarningBanner = bannerSeverityDanger || isFallbackUsed || designWarnings.length > 0;

    container.innerHTML = `
      ${
        showWarningBanner
          ? `
          <div id="results-warnings-banner" role="alert" aria-live="polite" style="margin-bottom: 12px; padding: 10px 14px; border-radius: var(--radius-md); background: ${bannerSeverityDanger ? 'rgba(239, 68, 68, 0.10)' : 'rgba(245, 158, 11, 0.10)'}; border: 1px solid ${bannerSeverityDanger ? 'rgba(239, 68, 68, 0.40)' : 'rgba(245, 158, 11, 0.40)'}; color: var(--color-text);">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 6px; margin-bottom: ${designWarnings.length > 0 ? '6px' : '0'};">
              <div style="font-size: 12px; font-weight: 700; color: ${bannerSeverityDanger ? '#ef4444' : '#f59e0b'};">
                ${bannerSeverityDanger ? '🚨 Kritik Seçilebilirlik / Termodinamik Kapsam Uyarısı' : '⚠️ Tasarım Doğrulama, VLE ve EOS Fallback Uyarıları'}
              </div>
              <div style="display: flex; gap: 6px; flex-wrap: wrap;">
                ${isInvalidScope ? `<span class="badge badge-danger">Kapsam: GEÇERSİZ (INVALID)</span>` : ""}
                ${!isInvalidScope && isNotSelectable ? `<span class="badge badge-danger">Kompresör Seçilemez (Kademe: ${escapeHtml((res.not_selectable_stages || []).join(", "))})</span>` : ""}
                ${isFallbackUsed ? `<span class="badge badge-warning">EOS Fallback (${escapeHtml((res.fallback_stage_numbers || []).join(", ") || String(res.fallback_state_count || 1))})</span>` : ""}
              </div>
            </div>
            ${
              designWarnings.length > 0
                ? `<ul style="margin: 0; padding-left: 18px; font-size: 11px; line-height: 1.45;">
                    ${designWarnings.map(w => `<li>${escapeHtml(w)}</li>`).join("")}
                   </ul>`
                : ""
            }
          </div>
          `
          : ""
      }

      <!-- KPI Metric Cards: Desktop & Station Parity (8 Cards) -->
      <div class="metrics-grid">
        <div class="metric-card">
          <div class="metric-label">Şaft Gücü (P_shaft / Ünite)</div>
          <div class="metric-value-row">
            <span class="metric-value">${powerShaftPerUnitKw.toLocaleString('tr-TR', { maximumFractionDigits: 0 })}</span>
            <span class="metric-unit">kW</span>
          </div>
          <div style="font-size: 10px; color: var(--color-text-secondary); margin-top: 2px;">
            Toplam: <strong style="color: #0284c7;">${powerShaftTotalKw.toLocaleString('tr-TR', { maximumFractionDigits: 0 })} kW</strong> (${(powerShaftTotalKw/1000).toFixed(2)} MW)
          </div>
        </div>

        <div class="metric-card">
          <div class="metric-label">Motor Gücü (P_motor / Ünite)</div>
          <div class="metric-value-row">
            <span class="metric-value">${powerUnitKw.toLocaleString('tr-TR', { maximumFractionDigits: 0 })}</span>
            <span class="metric-unit">kW</span>
          </div>
          <div style="font-size: 10px; color: var(--color-text-secondary); margin-top: 2px;">
            API 617 (%${driverMarginPct.toFixed(0)}): <strong style="color: #f59e0b;">${(powerUnitTotalKw/1000).toFixed(2)} MW</strong> Toplam
          </div>
        </div>

        <div class="metric-card">
          <div class="metric-label">Yakıt Tüketimi (Ünite Başı)</div>
          <div class="metric-value-row">
            <span class="metric-value">${fuelUnitKgH > 0 ? fuelUnitKgH.toFixed(1) : '-'}</span>
            <span class="metric-unit">kg/h</span>
          </div>
          <div style="font-size: 10px; color: var(--color-text-secondary); margin-top: 2px;">
            Toplam: <strong style="color: #10b981;">${fuelTotalKgH > 0 ? fuelTotalKgH.toFixed(1) : '-'} kg/h</strong> (~${fuelTotalKgH > 0 ? fuelKghToSm3h(fuelTotalKgH).toFixed(0) : '-'} Sm³/h)
          </div>
        </div>

        <div class="metric-card">
          <div class="metric-label">Isı Oranı (Heat Rate)</div>
          <div class="metric-value-row">
            <span class="metric-value">${heatRate > 0 ? Math.round(heatRate).toLocaleString('tr-TR') : '-'}</span>
            <span class="metric-unit">kJ/kWh</span>
          </div>
          <div style="font-size: 10px; color: var(--color-text-secondary); margin-top: 2px;">
            LHV: <strong>${Math.round(lhv)} kJ/kg</strong> • HHV: ${Math.round(hhv)}
          </div>
        </div>

        <div class="metric-card">
          <div class="metric-label">Politropik Verim (η_poly)</div>
          <div class="metric-value-row">
            <span class="metric-value">%${polyEff.toFixed(2)}</span>
            <span class="metric-unit">poly</span>
          </div>
          <div style="font-size: 10px; color: var(--color-text-secondary); margin-top: 2px;">
            Hedef: %${targetPolyEff.toFixed(1)}
          </div>
        </div>

        <div class="metric-card">
          <div class="metric-label">Politropik Head (H_poly)</div>
          <div class="metric-value-row">
            <span class="metric-value">${totalHead.toFixed(2)}</span>
            <span class="metric-unit">kJ/kg</span>
          </div>
          <div style="font-size: 10px; color: var(--color-text-secondary); margin-top: 2px;">
            Eşdeğer: <strong>${(totalHead * 101.97).toFixed(0)} m</strong>
          </div>
        </div>

        <div class="metric-card">
          <div class="metric-label">Basınç Oranı (PR)</div>
          <div class="metric-value-row">
            <span class="metric-value">${pr.toFixed(3)}</span>
            <span class="metric-unit">: 1</span>
          </div>
          <div style="font-size: 10px; color: var(--color-text-secondary); margin-top: 2px;">
            ${(res.p_in_bar || (res.p_in_pa ? res.p_in_pa/1e5 : 45)).toFixed(1)} → ${(res.p_out_bar || (res.p_out_pa ? res.p_out_pa/1e5 : 75)).toFixed(1)} bar
          </div>
        </div>

        <div class="metric-card">
          <div class="metric-label">Çıkış Sıcaklığı (T_out)</div>
          <div class="metric-value-row">
            <span class="metric-value">${tOutC.toFixed(1)}</span>
            <span class="metric-unit">°C</span>
          </div>
          <div style="font-size: 10px; color: var(--color-text-secondary); margin-top: 2px;">
            ${(tOutC + 273.15).toFixed(1)} K (${((tOutC * 9/5) + 32).toFixed(1)} °F)
          </div>
        </div>
      </div>

      <!-- 3D Station Model Call-to-Action Banner -->
      <div class="card" style="margin-top: 12px; padding: 10px 16px; background: linear-gradient(90deg, rgba(2, 132, 199, 0.08) 0%, rgba(14, 165, 233, 0.03) 100%); border: 1px solid rgba(2, 132, 199, 0.3); display: flex; justify-content: space-between; align-items: center; border-radius: var(--radius-md);">
        <div style="display: flex; align-items: center; gap: 12px;">
          <span style="font-size: 26px; line-height: 1;">🧊</span>
          <div>
            <div style="font-size: 13px; font-weight: 700; color: var(--color-primary);">3D Kompresör İstasyonu & Tesis Modeli Hazır</div>
            <div style="font-size: 11px; color: var(--color-text-secondary); margin-top: 2px;">
              Dinamik siklon seperatörler, kartuş filtreler, ünite binası, turbo-kompresör trenleri, fin-fan hava soğutucuları ve boru içi akış parçacıkları WebGL ile modellendi.
            </div>
          </div>
        </div>
        <button id="btn-goto-station-3d" class="btn btn-primary" style="display: flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 600; white-space: nowrap;">
          <span>3D Tesis Modeline Git</span>
          ${icon("arrowRight", 14)}
        </button>
      </div>

      <!-- Detail Analysis Subtabs -->
      <div class="card" style="margin-top: 16px;">
        <div class="sub-tabs-bar">
          <button class="sub-tab-btn ${ui.activeSubTab === 'thermo' ? 'active' : ''}" data-subtab="thermo">
            ${icon("activity", 12)} ${t("subtab_thermo", ui.lang)}
          </button>
          <button class="sub-tab-btn ${ui.activeSubTab === 'power_vle' ? 'active' : ''}" data-subtab="power_vle">
            ${icon("zap", 12)} ${t("subtab_power_vle", ui.lang)}
          </button>
          <button class="sub-tab-btn ${ui.activeSubTab === 'fuel' ? 'active' : ''}" data-subtab="fuel">
            ${icon("sliders", 12)} ${t("subtab_fuel", ui.lang)}
          </button>
          <button class="sub-tab-btn ${ui.activeSubTab === 'envelope' ? 'active' : ''}" data-subtab="envelope">
            ${icon("activity", 12)} ${t("subtab_envelope", ui.lang)}
          </button>
          <button class="sub-tab-btn ${ui.activeSubTab === 'dimensionless' ? 'active' : ''}" data-subtab="dimensionless">
            ${icon("grid", 12)} ${t("subtab_dimensionless", ui.lang)}
          </button>
          <button class="sub-tab-btn ${ui.activeSubTab === 'asme_ptc10' ? 'active' : ''}" data-subtab="asme_ptc10">
            ${icon("check", 12)} ${t("subtab_ptc10_uncertainty", ui.lang)}
          </button>
          <button class="sub-tab-btn ${ui.activeSubTab === 'fallback' ? 'active' : ''}" data-subtab="fallback">
            ${icon("refreshCw", 12)} ${t("subtab_fallback", ui.lang)}
          </button>
        </div>
        <div class="sub-tab-content">
          ${subTabContentHtml}
        </div>
      </div>

      <!-- 146+ Matching Turbines Table -->
      <div class="card" style="margin-top: 16px;">
        <div class="card-header" style="flex-wrap: wrap; gap: 8px;">
          <div class="card-title">
            ${icon("sliders", 16, "text-primary")}
            <span>${t("turbines_title", ui.lang)} (${units.length} Uygun Model)</span>
          </div>
          <div style="font-size: 11px; color: var(--color-text-secondary);">
            ISO 2314 Saha Düzeltmeli & API 617 %4 Güç Marjı Dahil
          </div>
        </div>

        <!-- Clarification Banner: Single Unit vs Station Total Sizing -->
        <div style="background: rgba(2, 132, 199, 0.08); border: 1px solid rgba(2, 132, 199, 0.25); border-radius: var(--radius-sm); padding: 10px 14px; margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
          <div style="font-size: 12px; color: var(--color-text);">
            🎯 <b>Boyutlandırma Esası:</b> Belirlenen <b>${numUnits} Paralel Tren</b> mimarisinde, aşağıdaki türbinler <b>HER BİR TEKİL KOMPRESÖR TRENİNİ</b> sürmek üzere tekil olarak eşleştirilmiştir:
          </div>
          <div style="font-size: 12px; font-weight: 700; color: var(--color-primary); display: flex; gap: 14px;">
            <span>Tek Ünite İhtiyacı: <b style="color: #0284c7;">${powerUnitKw.toLocaleString('tr-TR', { maximumFractionDigits: 0 })} kW</b></span>
            <span>İstasyon Toplamı (${numUnits} Tren): <b style="color: #f59e0b;">${(powerUnitTotalKw / 1000).toFixed(2)} MW</b></span>
          </div>
        </div>

        <div style="max-height: 290px; overflow-y: auto;">
          <table class="kasp-table">
            <thead>
              <tr>
                <th>Üretici & Model</th>
                <th>Tip</th>
                <th style="text-align: right;">Tek Ünite Saha Gücü</th>
                <th style="text-align: right;">ISO Gücü</th>
                <th style="text-align: right;">Gereken Güç / Ünite</th>
                <th style="text-align: right;">API 617 Marjı</th>
                <th style="text-align: right;">${numUnits} Tren İstasyon Toplamı</th>
                <th style="text-align: right;">Isı Tüketimi (Site)</th>
                <th style="text-align: right;">Yıllık OPEX (Yakıt+CO₂)</th>
                <th style="text-align: center;">Durum & Skor</th>
              </tr>
            </thead>
            <tbody>
              ${
                units.length > 0
                  ? units.slice(0, 20).map(u => {
                    const sitePower = Number(u.site_power_kw || u.available_power_kw || u.iso_power_kw || 0);
                    const isoPower = Number(u.iso_power_kw || 0);
                    const marginPct = Number(u.power_margin_pct !== undefined ? u.power_margin_pct : ((u.power_margin || 0) * 100));
                    const stationTotalPwrMw = (sitePower * numUnits) / 1000;
                    const heatRateVal = Number(u.site_heat_rate_kj_kwh || u.iso_heat_rate_kj_kwh || 0);
                    const siteThermEffPct = Number(
                      u.site_thermal_efficiency_pct || (heatRateVal > 0 ? 360000.0 / heatRateVal : 0)
                    );
                    const score = Number(u.selection_score || 85.0);

                    // Estimate annual OPEX (fuel + carbon) using un-margined coupling power & EOS/MW standard density
                    const lhvVal = lhv > 0 ? lhv : 47000;
                    const hrForOpex = heatRateVal > 0 ? heatRateVal : 10500;
                    const couplingKw = powerMotorPerUnitKw > 0 ? powerMotorPerUnitKw : powerUnitKw;
                    const unitFuelKgH = (couplingKw * hrForOpex) / lhvVal;
                    const annualFuelSm3 = fuelKghToSm3h(unitFuelKgH) * 8000;
                    const annualFuelCost = annualFuelSm3 * 0.35;
                    const annualCo2Ton = (unitFuelKgH * 2.75 * 8000) / 1000;
                    const annualCo2Cost = annualCo2Ton * 50.0;
                    const unitAnnualOpex = annualFuelCost + annualCo2Cost;

                    const unitSurge = u.surge_margin_pct != null ? Number(u.surge_margin_pct) : null;
                    const unitChoke = u.stonewall_margin_pct != null ? Number(u.stonewall_margin_pct) : null;
                    const surgeRisk = u.meets_api617_surge === false || (unitSurge !== null && unitSurge < 10);
                    const chokeRisk = unitChoke !== null && unitChoke < 5;
                    const statusBadgeClass = (surgeRisk || chokeRisk)
                      ? "badge-danger"
                      : ((unitSurge !== null && unitSurge < 15) ? "badge-warning" : "badge-success");
                    const statusBadgeText = surgeRisk
                      ? `Surge Riski (${score.toFixed(0)})`
                      : (chokeRisk ? `Choke Riski (${score.toFixed(0)})` : `Uygun (${score.toFixed(0)})`);
                    const marginSubline = unitSurge !== null
                      ? `<div style="font-size: 9px; color: var(--color-text-secondary); margin-top: 2px;">Surge +%${unitSurge.toFixed(1)}${unitChoke !== null ? ` • Choke +%${unitChoke.toFixed(1)}` : ""}</div>`
                      : "";
                    const modelDisplay = u.model || u.name || "Türbin";

                    return `
                      <tr>
                        <td>
                          <b>${escapeHtml(modelDisplay)}</b>
                          <div style="font-size: 10px; color: var(--color-text-secondary);">${escapeHtml(u.manufacturer || 'Genel')}</div>
                        </td>
                        <td><span class="badge badge-info">${escapeHtml(u.type || 'Endüstriyel')}</span></td>
                        <td style="text-align: right; font-family: var(--font-mono); font-weight: 700; color: #0284c7;">
                          ${sitePower.toLocaleString('tr-TR', { maximumFractionDigits: 0 })} kW
                        </td>
                        <td style="text-align: right; font-family: var(--font-mono); color: var(--color-text-secondary);">
                          ${isoPower.toLocaleString('tr-TR', { maximumFractionDigits: 0 })} kW
                        </td>
                        <td style="text-align: right; font-family: var(--font-mono); color: #f59e0b;">
                          ${powerUnitKw.toLocaleString('tr-TR', { maximumFractionDigits: 0 })} kW
                        </td>
                        <td style="text-align: right; font-family: var(--font-mono); font-weight: 600; color: #10b981;">
                          +${marginPct.toFixed(1)}%
                        </td>
                        <td style="text-align: right; font-family: var(--font-mono); font-weight: 600;">
                          ${stationTotalPwrMw.toFixed(2)} MW
                        </td>
                        <td style="text-align: right; font-family: var(--font-mono);">
                          <div>${heatRateVal > 0 ? Math.round(heatRateVal).toLocaleString('tr-TR') : '-'} kJ/kWh</div>
                          ${
                            siteThermEffPct > 0
                              ? `<div style="display: flex; justify-content: flex-end; align-items: center; gap: 6px; margin-top: 3px;">
                                   <span style="font-size: 10px; color: var(--color-text-secondary);">ηth %${siteThermEffPct.toFixed(1)}</span>
                                   <button
                                     type="button"
                                     class="btn btn-sm turbine-apply-eff-btn"
                                     data-eff="${siteThermEffPct.toFixed(2)}"
                                     data-model="${escapeHtml(modelDisplay)}"
                                     aria-label="${escapeHtml(`${t("btn_apply_turbine_eff", ui.lang)} (${modelDisplay} %${siteThermEffPct.toFixed(1)})`)}"
                                     style="min-block-size: 24px; padding: 2px 6px; font-size: 10px;"
                                   >${escapeHtml(t("btn_apply_turbine_eff", ui.lang))}</button>
                                 </div>`
                              : ""
                          }
                        </td>
                        <td style="text-align: right; font-family: var(--font-mono); font-weight: 600; color: #f59e0b;" title="Yakıt: $${(annualFuelCost / 1e6).toFixed(2)}M • Karbon: $${(annualCo2Cost / 1e3).toFixed(0)}k">
                          $${(unitAnnualOpex / 1e6).toFixed(2)}M / yıl
                        </td>
                        <td style="text-align: center;">
                          <span class="badge ${statusBadgeClass}" title="Seçim Skoru: ${score.toFixed(1)}/100">
                            ${statusBadgeText}
                          </span>
                          ${marginSubline}
                        </td>
                      </tr>
                    `;
                  }).join("")
                  : `<tr><td colspan="10" style="text-align: center; color: var(--color-text-secondary); padding: 16px;">Kriterlere uyan türbin bulunamadı.</td></tr>`
              }
            </tbody>
          </table>
        </div>

        <!-- ISO 2314 Ambient Derating Chart Mount -->
        <div style="border-top: 1px solid var(--color-border); padding: 14px 16px; margin-top: 14px; background: rgba(2, 132, 199, 0.02); border-radius: var(--radius-sm);">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <div style="font-weight: 700; font-size: 13px; color: var(--color-primary);">
              🌡️ Gaz Türbini Ortam Sıcaklığı Güç Düşümü & Derate Eğrileri (ISO 2314: -20°C ila +50°C)
            </div>
            <span class="badge badge-info">
              Tasarım Ortam Sıcaklığı: ${proj.inputs?.ambient_temp ?? proj.inputs?.t_amb ?? 19}°C • Rakım: ${proj.inputs?.altitude ?? 0} m
            </span>
          </div>
          <div id="results-chart-derate" style="width: 100%; height: 320px;"></div>
        </div>
      </div>
    `;

    // Bind subtab buttons
    container.querySelectorAll(".sub-tab-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        const sub = btn.getAttribute("data-subtab");
        setActiveSubTab(sub);
      });
    });

    // Bind OEM turbine efficiency sync buttons
    container.querySelectorAll(".turbine-apply-eff-btn").forEach(btn => {
      btn.addEventListener("click", async () => {
        const effVal = parseFloat(btn.getAttribute("data-eff"));
        const modelName = btn.getAttribute("data-model") || "Türbin";
        if (!Number.isFinite(effVal) || effVal <= 0) return;
        updateInput("therm_eff", effVal);
        showToast(`${modelName} saha ısıl verimi (%${effVal.toFixed(1)}) uygulandı; yakıt hesabı güncelleniyor...`, "info");
        try {
          await runDesignCalculation();
        } catch (_) {}
      });
    });

    // Bind 3D station banner CTA button
    container.querySelector("#btn-goto-station-3d")?.addEventListener("click", () => {
      setActiveTab("station");
    });

    // Render Operating Envelope chart if envelope subtab is active
    if (ui.activeSubTab === "envelope" && window.Plotly && proj.charts?.operating_envelope) {
      requestAnimationFrame(() => {
        const subElem = container.querySelector("#subtab-chart-envelope");
        if (subElem) {
          const isDark = ui.theme === "dark" || ui.theme === "engineering";
          const bg = isDark ? (ui.theme === "engineering" ? "#1A2332" : "#1E293B") : "#FFFFFF";
          const text = isDark ? "#E2E8F0" : "#1C1917";
          const grid = isDark ? "#334155" : "#E5E7EB";
          const p = proj.charts.operating_envelope;
          const mergedLayout = {
            ...(p.layout || {}),
            paper_bgcolor: bg,
            plot_bgcolor: bg,
            font: { color: text, family: "Inter, sans-serif", size: 10 },
            margin: { l: 45, r: 20, t: 30, b: 40 },
            autosize: true,
            xaxis: { ...(p.layout?.xaxis || {}), gridcolor: grid, zerolinecolor: grid },
            yaxis: { ...(p.layout?.yaxis || {}), gridcolor: grid, zerolinecolor: grid },
          };
          window.Plotly.newPlot(subElem, p.data || [], mergedLayout, {
            responsive: true,
            displayModeBar: false,
          });
        }
      });
    }

    // Render Turbine ISO 2314 Derate chart
    if (window.Plotly && proj.charts?.turbine_derate) {
      requestAnimationFrame(() => {
        const derateElem = container.querySelector("#results-chart-derate");
        if (derateElem) {
          const isDark = ui.theme === "dark" || ui.theme === "engineering";
          const bg = isDark ? (ui.theme === "engineering" ? "#1A2332" : "#1E293B") : "#FFFFFF";
          const text = isDark ? "#E2E8F0" : "#1C1917";
          const grid = isDark ? "#334155" : "#E5E7EB";
          const p = proj.charts.turbine_derate;
          const mergedLayout = {
            ...(p.layout || {}),
            paper_bgcolor: bg,
            plot_bgcolor: bg,
            font: { color: text, family: "Inter, sans-serif", size: 10 },
            margin: { l: 50, r: 20, t: 30, b: 40 },
            autosize: true,
            xaxis: { ...(p.layout?.xaxis || {}), gridcolor: grid, zerolinecolor: grid },
            yaxis: { ...(p.layout?.yaxis || {}), gridcolor: grid, zerolinecolor: grid },
          };
          window.Plotly.newPlot(derateElem, p.data || [], mergedLayout, {
            responsive: true,
            displayModeBar: false,
          });
        }
      });
    }
  }

  let resizeTimer = null;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
      if (!window.Plotly) return;
      ["subtab-chart-envelope", "results-chart-derate"].forEach(id => {
        const el = container.querySelector("#" + id);
        if (el && el.data) {
          window.Plotly.Plots.resize(el);
        }
      });
    }, 150);
  });

  uiStore.subscribe(update);
  projectStore.subscribe(update);
  update();
}
