"""
KASP V4.5 Thermo Engine (Facade)
Bu modül eski monolitik (2400+ satırlık) çekirdek sınıfın Facade deseninde
yeniden yazılmış halidir. Arka planda işlemleri şu modüllere devreder:
  - GasMixtureBuilder (mixture.py)
  - ThermodynamicSolver (properties.py)
  - CompressorAerodynamics (aerodynamics.py)
  - TurbineSelector (selection.py)
Arayüz geriye dönük (backward) uyumludur, UI modülleri aynı fonksiyonları aynı argümanlarla çağırır.
"""

import math
import logging
import datetime
import numpy as np

# Alt Bileşenler (V4.4 Modular Architecture)
from kasp.core.mixture import GasMixtureBuilder
from kasp.core.properties import ThermodynamicSolver
from kasp.core.aerodynamics import CompressorAerodynamics
from kasp.core.selection import TurbineSelector

# Eski yardımcılar ve Sabitler
from kasp.core.units import UnitSystem
from kasp.core.exceptions import (
    AdvancedThermodynamicError, UnitConversionError, FluidPropertyError
)
from kasp.utils.monitoring import PerformanceMonitor
from kasp.core.settings import EngineSettings

from kasp.core.constants import (
    SUPPORTED_GASES, LHV_DATA, MOLAR_MASSES, WATER_PRODUCED,
    R_UNIVERSAL_J_MOL_K, STD_PRESS_PA, NORMAL_TEMP_K, STANDARD_TEMP_K
)

# Uncertainty Analysis (Optional)
try:
    from kasp.core.uncertainty import UncertaintyAnalyzer
    UNCERTAINTY_AVAILABLE = True
except ImportError:
    UNCERTAINTY_AVAILABLE = False
    UncertaintyAnalyzer = None

class ThermoEngine:
    """KASP V4.5 — Gelişmiş Termodinamik Motor (Facade Sınıfı)"""

    # Geriye dönük uyumluluk için sınıf değişkenleri
    STD_PRESS_PA = STD_PRESS_PA
    NORMAL_TEMP_K = NORMAL_TEMP_K
    STANDARD_TEMP_K = STANDARD_TEMP_K
    R_UNIVERSAL_J_MOL_K = R_UNIVERSAL_J_MOL_K
    COOLPROP_SAFE_NAMES = list(SUPPORTED_GASES.keys())
    _THERMO_ID_MAP = GasMixtureBuilder.THERMO_ID_MAP
    LHV_DATA = LHV_DATA
    MOLAR_MASSES = MOLAR_MASSES

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.performance_monitor = PerformanceMonitor()
        
        # 1. Alt Modüllerin (Sub-systems) İlklendirilmesi
        self.thermo_solver = ThermodynamicSolver(max_cache_size=3000)
        
        if UNCERTAINTY_AVAILABLE:
            self.uncertainty_analyzer = UncertaintyAnalyzer()
            self.logger.info("✓ Uncertainty analysis enabled (ASME PTC 10).")
        else:
            self.uncertainty_analyzer = None

        self.logger.info("KASP V4.5 Termodinamik Motoru (Modular Facade) başlatıldı.")

    # -------------------------------------------------------------------------
    # 1. DELEGASYON METOTLARI (Mixture & Properties)
    # -------------------------------------------------------------------------
    def _validate_gas_composition(self, composition):
        """UI testleriyle geriye dönük uyumluluk için GasMixtureBuilder'ı çağırır."""
        return GasMixtureBuilder.validate_and_normalize(composition)
    def _create_gas_object(self, composition, eos_method):
        """Gaz objesi oluşturmayı GasMixtureBuilder'a devreder."""
        comp_frac = GasMixtureBuilder.validate_and_normalize(composition)
        if eos_method == 'coolprop':
            return GasMixtureBuilder.build_coolprop_string(comp_frac)
        elif eos_method in ['pr', 'srk']:
            return GasMixtureBuilder.build_thermo_data(comp_frac)
        else:
            raise ValueError(f"Bilinmeyen EOS metodu: {eos_method}")

    def _get_thermo_properties(self, p_pa, t_k, gas_obj, eos_method):
        """Legacy dictionary bekleyen eski kod kısımları için köprü (Bridge)."""
        state = self.thermo_solver.get_properties(p_pa, t_k, gas_obj, eos_method)
        return {
            'H': state.H,
            'S': state.S,
            'Z': state.Z,
            'k': state.k,
            'rho': state.density,
            'Cp': state.Cp,
            'Cv': state.Cv,
            'M_kg_mol': state.MW / 1000.0,
            'fallback_used': state.raw_props.get('fallback', False),
            'mu': state.raw_props.get('mu', 1.1e-5),
            'a': 300.0 # Placeholder
        }

    # -------------------------------------------------------------------------
    # 2. BİRİM DÖNÜŞÜM METOTLARI (UnitSystem ile Korumalı)
    # -------------------------------------------------------------------------
    def convert_pressure_to_pa(self, value, unit, ambient_pressure_pa=None):
        try:
            UnitSystem.validate_pressure_value(value, unit)
            return UnitSystem.convert_pressure(value, unit, 'Pa', ambient_pressure_pa)
        except UnitConversionError as e:
            raise UnitConversionError(f"Basınç dönüşüm hatası: {e}", value, unit)

    def convert_temperature_to_k(self, value, unit):
        try:
            UnitSystem.validate_temperature_value(value, unit)
            return UnitSystem.convert_temperature(value, unit, 'K')
        except UnitConversionError as e:
            raise UnitConversionError(f"Sıcaklık dönüşüm hatası: {e}", value, unit)

    def convert_flow_to_kgs(self, value, unit, gas_obj, eos_method):
        """Hacimsel veya molar debiyi ağırlıksal debiye çevirir."""
        if unit == "kg/s": return float(value)
        if unit == "kg/h": return float(value) / 3600.0

        try:
            val_f = float(value)
            if unit in ["Sm³/h", "MMSCMD"]:
                state_std = self.thermo_solver.get_properties(self.STD_PRESS_PA, self.STANDARD_TEMP_K, gas_obj, eos_method)
                if unit == "Sm³/h": return (val_f * state_std.density) / 3600.0
                if unit == "MMSCMD": return (val_f * 1e6 / 86400) * state_std.density

            elif unit == "Nm³/h":
                state_norm = self.thermo_solver.get_properties(self.STD_PRESS_PA, self.NORMAL_TEMP_K, gas_obj, eos_method)
                return (val_f * state_norm.density) / 3600.0

            elif unit == "MMSCFD":
                t_std_k = self.convert_temperature_to_k(60, "°F")
                p_std_pa = self.convert_pressure_to_pa(14.73, "psia")
                state_scfd = self.thermo_solver.get_properties(p_std_pa, t_std_k, gas_obj, eos_method)
                vol_m3_sec = val_f * 1e6 * 0.0283168 / 86400
                return vol_m3_sec * state_scfd.density

            elif unit in ["kgmol/h", "kmol/h"]:
                if eos_method == 'coolprop' and isinstance(gas_obj, str):
                    mw = self.thermo_solver.get_properties(101325, 298.15, gas_obj, eos_method).MW
                elif isinstance(gas_obj, dict) and 'MW' in gas_obj:
                    mw = gas_obj['MW']
                else:
                    mw = 16.04 # Methane fallback
                return (val_f * mw) / 3600.0

        except Exception as e:
            self.logger.error(f"Debi dönüşüm hatası: {e}")
            raise UnitConversionError(f"Debi dönüşümü başarısız: {e}", value, unit)

        raise UnitConversionError(f"Bilinmeyen akış birimi: {unit}", value, unit)

    def convert_result_value(self, value: float, from_unit: str, to_unit: str, quantity_type: str) -> float:
        """UI sonuç panelleri için genel birim dönüştürücü"""
        if from_unit == to_unit:
            return value
            
        try:
            if quantity_type == 'temperature':
                return UnitSystem.convert_temperature(value, from_unit, to_unit)
            elif quantity_type == 'pressure':
                return UnitSystem.convert_pressure(value, from_unit, to_unit)
            elif quantity_type == 'power':
                kw_val = value
                if from_unit == 'MW': kw_val = value * 1000
                elif from_unit == 'hp': kw_val = value * 0.7457
                
                if to_unit == 'kW': return kw_val
                elif to_unit == 'MW': return kw_val / 1000
                elif to_unit == 'hp': return kw_val / 0.7457
            elif quantity_type == 'head':
                if from_unit == 'kJ/kg' and to_unit == 'ft-lbf/lbm':
                    return value * 334.55256555
                elif from_unit == 'ft-lbf/lbm' and to_unit == 'kJ/kg':
                    return value / 334.55256555
            elif quantity_type == 'heat_rate':
                base_val = value
                if from_unit == 'Btu/kWh': base_val = value / 0.947817
                elif from_unit == 'kcal/kWh': base_val = value / 0.239006
                elif from_unit == 'Btu/hp-hr': base_val = value / 0.706787
                
                if to_unit == 'kJ/kWh': return base_val
                elif to_unit == 'Btu/kWh': return base_val * 0.947817
                elif to_unit == 'kcal/kWh': return base_val * 0.239006
                elif to_unit == 'Btu/hp-hr': return base_val * 0.706787
            return value
        except Exception as e:
            self.logger.error(f"Sonuç dönüştürmede birim hatası {quantity_type}: {e}")
            return value

    # -------------------------------------------------------------------------
    # 3. YANMA VE YAKIT HESAPLAMALARI
    # -------------------------------------------------------------------------
    def _calculate_heating_values(self, composition, source='kasp'):
        comp_frac = GasMixtureBuilder.validate_and_normalize(composition)
        
        total_lhv_energy_kj_per_mole = 0 
        total_molar_mass_mix = 0
        total_water_moles_produced = 0
        
        for comp, fraction in comp_frac.items():
            comp_upper = comp.upper()
            mw = MOLAR_MASSES.get(comp_upper, 0)
            
            if source == 'thermo':
                try:
                    import thermo
                    from thermo.chemical import Chemical
                    chem_name = comp_upper.lower().capitalize()
                    
                    if chem_name == "Carbondioxide": chem_name = "Carbon dioxide"
                    elif chem_name == "Hydrogensulfide": chem_name = "Hydrogen sulfide"
                    elif chem_name == "Isopentane": chem_name = "Isopentane"
                    elif chem_name == "Isobutane": chem_name = "Isobutane"
                    
                    chem = Chemical(chem_name)
                    if chem.Hc:
                        hhv_kj_kg = abs(chem.Hc) / 1000.0
                        
                        # WATER_PRODUCED is moles of water per mole of fuel. Convert to mass of water per kg of fuel.
                        water_moles_per_mole_fuel = WATER_PRODUCED.get(comp_upper, 0)
                        mw_fuel_kg = mw / 1000.0
                        mass_h2o_per_kg_fuel = (water_moles_per_mole_fuel * 0.018015) / mw_fuel_kg if mw_fuel_kg > 0 else 0
                        
                        lhv_kj_kg = hhv_kj_kg - (mass_h2o_per_kg_fuel * 2441.7)
                        lhv = lhv_kj_kg
                    else:
                        lhv = LHV_DATA.get(comp_upper, 0)
                except Exception as e:
                    self.logger.warning(f"Thermo Hc alinmadi ({comp}): {e}, KASP sabitlerine dönülüyor.")
                    lhv = LHV_DATA.get(comp_upper, 0)
            else:
                lhv = LHV_DATA.get(comp_upper, 0)
            
            total_lhv_energy_kj_per_mole += lhv * (mw/1000.0) * fraction
            total_molar_mass_mix += fraction * mw
            total_water_moles_produced += fraction * WATER_PRODUCED.get(comp_upper, 0)
            
        if total_molar_mass_mix == 0: return 0, 0
        
        avg_molar_mass_kg = total_molar_mass_mix / 1000.0
        lhv_mass_basis = total_lhv_energy_kj_per_mole / avg_molar_mass_kg
        
        mass_h2o_produced = (total_water_moles_produced * MOLAR_MASSES.get('WATER', 18.02)) / total_molar_mass_mix
        hhv_mass_basis = lhv_mass_basis + mass_h2o_produced * 2441.7
        
        return lhv_mass_basis, hhv_mass_basis

    # -------------------------------------------------------------------------
    # 4. ANA TASARIM HESAPLAMA ÇEKİRDEĞİ (Design Performance)
    # -------------------------------------------------------------------------
    def calculate_design_performance(self, inputs):
        """
        V4.4 Hesaplama Motoru — UI'dan seçilen metoda göre çalışır:
          • Metot 1: Ortalama Özellikler  (PR > 4 ise API 617 Appendix C integrasyon)
          • Metot 2: Uç Nokta İterasyonu
          • Metot 3: Artımlı Basınç Adımları

        Kullanım:
            inputs['method'] = 'Metot 1: Ortalama Özellikler'  (varsayılan)
                             | 'Metot 2: Uç Nokta'
                             | 'Metot 3: Artımlı Basınç'
        """
        start_time = datetime.datetime.now()
        try:
            # 1. Birim Dönüşümleri & Validasyon
            amb_p    = inputs.get('ambient_pressure_pa', self.STD_PRESS_PA)
            p_in_pa  = self.convert_pressure_to_pa(float(inputs['p_in']),  inputs['p_in_unit'],  amb_p)
            t_in_k   = self.convert_temperature_to_k(float(inputs['t_in']), inputs['t_in_unit'])
            p_out_pa = self.convert_pressure_to_pa(float(inputs['p_out']), inputs['p_out_unit'], amb_p)

            if p_out_pa <= p_in_pa:
                raise ValueError(f"Çıkış basıncı ({p_out_pa/1e5:.2f} bar) girişten küçük/eşit olamaz.")

            gas_obj             = self._create_gas_object(inputs['gas_comp'], inputs['eos_method'])
            total_mass_flow_kgs = self.convert_flow_to_kgs(float(inputs['flow']), inputs['flow_unit'], gas_obj, inputs['eos_method'])

            num_units        = max(1, inputs.get('num_units', 1))
            mass_flow_per_unit = total_mass_flow_kgs / num_units

            # 2. Hesaplama Metodu & Kademe Parametreleri
            method = inputs.get('method', 'Metot 1: Ortalama Özellikler')
            eos    = inputs['eos_method']

            num_stages   = max(1, int(inputs.get('num_stages', 1)))
            poly_eff_tgt = max(0.01, min(0.99, float(inputs.get('poly_eff', 85.0)) / 100.0))

            intercooler_dp = float(inputs.get('intercooler_dp_pct', 0.0)) / 100.0
            ic_t_raw       = float(inputs.get('intercooler_t', 40.0))
            ic_t_k         = ic_t_raw + 273.15 if ic_t_raw < 200 else ic_t_raw

            pr_total = p_out_pa / p_in_pa
            stage_pr = (
                (pr_total / ((1.0 - intercooler_dp) ** (num_stages - 1))) ** (1.0 / num_stages)
                if num_stages > 1 else pr_total
            )

            max_iter      = int(inputs.get('method_max_iter', 100))
            tolerance     = float(inputs.get('method_tolerance', 0.01))
            step_count    = int(inputs.get('incremental_steps', 10))

            self.logger.info(
                f"Hesaplama başlıyor | Metot: {method} | "
                f"PR={pr_total:.2f} | Kademe={num_stages} | EOS={eos}"
            )

            # 3. Kademeli Hesaplama Döngüsü
            curr_p_in = p_in_pa
            curr_t_in = t_in_k
            total_stage_gas_power_kw = 0.0
            total_poly_head_kj_kg    = 0.0
            staged_results           = []
            final_t_out_k            = t_in_k

            for stage in range(1, num_stages + 1):
                curr_p_out = curr_p_in * stage_pr
                if stage == num_stages:
                    curr_p_out = p_out_pa  # Son kademe, hedef basıncı tam tuttur

                self.logger.info(
                    f">> KADEME {stage}: {curr_p_in/1e5:.2f} bar → {curr_p_out/1e5:.2f} bar"
                )

                # Metot Seçimi
                if 'Metot 2' in method or 'Endpoint' in method or 'Uç Nokta' in method:
                    t_out_k, poly_head, z_avg, history = self._method_endpoint(
                        curr_p_in, curr_t_in, curr_p_out, poly_eff_tgt, gas_obj, eos, max_iter, tolerance
                    )
                elif 'Metot 3' in method or 'Artımlı' in method or 'Incremental' in method:
                    t_out_k, poly_head, z_avg, history = self._method_incremental_pressure(
                        curr_p_in, curr_t_in, curr_p_out, poly_eff_tgt, gas_obj, eos, step_count
                    )
                elif 'Metot 4' in method or 'H-S' in method or 'Doğrudan' in method:
                    t_out_k, poly_head, z_avg, history = self._method_direct_hs(
                        curr_p_in, curr_t_in, curr_p_out, poly_eff_tgt, gas_obj, eos
                    )
                else:
                    # Varsayılan: Metot 1 — Ortalama Özellikler (API 617 Appendix C)
                    t_out_k, poly_head, z_avg, history = self._method_average_properties(
                        curr_p_in, curr_t_in, curr_p_out, poly_eff_tgt, gas_obj, eos, max_iter, tolerance
                    )

                # Stage sonuç özellikleri
                state_in  = self.thermo_solver.get_properties(curr_p_in,  curr_t_in, gas_obj, eos)
                state_out = self.thermo_solver.get_properties(curr_p_out, t_out_k,   gas_obj, eos)

                # ► Tasarım gücü: kullanıcının η_p varsayımı tutarlı şekilde kullanılır
                #   P_gaz = m_dot × H_politropik / η_p
                #   (η_p = 85% ile T_out bulunduysa, güç hesabı da aynı η ile tutarlı olmalı)
                stage_gas_power_kw = mass_flow_per_unit * (poly_head / poly_eff_tgt)

                # ► Tanı verisi: CoolProp gerçek ΔH'dan geri hesaplanan verim
                #   actual_poly_eff = H_politropik / ΔH_gerçek
                #   Bu değer η_p'den farklıysa gerçek gaz k değişiminin etkisi görülüyor
                stage_delta_h_kj = (state_out.H - state_in.H) / 1000.0  # kJ/kg (CoolProp)
                R_sp = R_UNIVERSAL_J_MOL_K / (state_in.MW / 1000.0)
                actual_poly_eff = CompressorAerodynamics.calculate_polytropic_efficiency(
                    state_in, state_out, R_sp
                )  # Tanı amaçlı — güç hesabında kullanılmıyor

                total_stage_gas_power_kw += stage_gas_power_kw
                total_poly_head_kj_kg    += poly_head

                staged_results.append({
                    'stage':               stage,
                    'p_in':                curr_p_in,
                    't_in':                curr_t_in,
                    'p_out':               curr_p_out,
                    't_out':               t_out_k,
                    'head_kj_kg':          poly_head,
                    'poly_eff_design':     poly_eff_tgt,       # ← kullanıcı girişi (tasarım verimi)
                    'poly_eff_diagnostic': actual_poly_eff,    # ← geri hesaplanan (tanı)
                    'poly_eff':            poly_eff_tgt,       # ← geriye uyumluluk
                    'power_gas_kw':        stage_gas_power_kw,
                    'delta_h_kj_kg':       stage_delta_h_kj,   # ← CoolProp gerçek ΔH
                    'z_avg':               z_avg,
                    'method_history':      history,
                })

                final_t_out_k = t_out_k

                # Intercooler (kademeler arası)
                if stage < num_stages:
                    curr_p_in = curr_p_out * (1.0 - intercooler_dp)
                    curr_t_in = ic_t_k

            # 4. Toplam Performans Hesapları
            state1     = self.thermo_solver.get_properties(p_in_pa, t_in_k, gas_obj, eos)
            inlet_acmh = (mass_flow_per_unit / state1.density) * 3600.0

            mech_loss_kw      = CompressorAerodynamics.calculate_mechanical_loss(inlet_acmh / 3600.0, total_stage_gas_power_kw)
            total_shaft_kw    = total_stage_gas_power_kw + mech_loss_kw

            mech_eff_raw = float(inputs.get('mech_eff', 98.0))
            mech_eff     = mech_eff_raw / 100.0 if mech_eff_raw > 1.0 else mech_eff_raw
            motor_kw     = total_shaft_kw / mech_eff
            unit_kw      = motor_kw * 1.04  # API 617 %4 elektrik marjı

            # 5. Yakıt & Isıl Verim
            lhv, hhv   = self._calculate_heating_values(
                inputs.get('fuel_gas_comp', inputs['gas_comp']), 
                source=inputs.get('lhv_source', 'kasp')
            )
            therm_raw  = inputs.get('therm_eff', 0.35)
            therm_eff  = therm_raw / 100.0 if therm_raw > 1.0 else therm_raw

            fuel_kw         = motor_kw / therm_eff if therm_eff > 0 else 0.0
            heat_rate       = (fuel_kw * 3600.0) / motor_kw if motor_kw > 0 else 0.0
            fuel_kgh        = (fuel_kw * 3600.0) / lhv if lhv > 0 else 0.0

            # 6. Sonuç Paketi
            last_stage = staged_results[-1]
            results = {
                't_out':                       final_t_out_k - 273.15,
                'head_kj_kg':                  total_poly_head_kj_kg,
                'compression_ratio':           p_out_pa / p_in_pa,
                # ► Tasarım verimi: kullanıcı girişi — güç hesabında kullanılan
                'actual_poly_efficiency':      poly_eff_tgt,
                'power_gas_per_unit_kw':       total_stage_gas_power_kw,
                'power_shaft_per_unit_kw':     total_shaft_kw,
                'power_motor_per_unit_kw':     motor_kw,
                'power_unit_kw':               unit_kw,
                'api_617_margin_percent':      4.0,
                'mech_loss_per_unit_kw':       mech_loss_kw,
                'fuel_unit_kgh':               fuel_kgh,
                'mass_flow_per_unit_kgs':      mass_flow_per_unit,
                'inlet_vol_flow_acmh_per_unit': inlet_acmh,
                'power_gas_total_kw':          total_stage_gas_power_kw * num_units,
                'power_shaft_total_kw':        total_shaft_kw   * num_units,
                'power_unit_total_kw':         unit_kw          * num_units,
                'mech_loss_total_kw':          mech_loss_kw     * num_units,
                'fuel_total_kgh':              fuel_kgh         * num_units,
                'mass_flow_total_kgs':         total_mass_flow_kgs,
                'heat_rate':                   heat_rate,
                'lhv':                         lhv,
                'hhv':                         hhv,
                'inlet_properties':  self._get_thermo_properties(p_in_pa,  t_in_k,       gas_obj, eos),
                'outlet_properties': self._get_thermo_properties(p_out_pa, final_t_out_k, gas_obj, eos),
                'num_units':         num_units,
                'num_stages':        num_stages,
                'stages':            staged_results,
                'calculation_method': method,
                'warnings':          [],
                'engine_version':    '1.2.0 (V4.5 — 4-Method Engine)',
            }

            # 7. Belirsizlik Analizi (ASME PTC 10, opsiyonel)
            if self.uncertainty_analyzer and inputs.get('enable_uncertainty', True):
                try:
                    unc = self.uncertainty_analyzer.analyze_uncertainty(
                        {'p_in': p_in_pa / 1e5, 'p_out': p_out_pa / 1e5,
                         't_in': t_in_k, 'flow': mass_flow_per_unit},
                        {'p_in': 'pressure_transducer_high', 'p_out': 'pressure_transducer_high',
                         't_in': 'temperature_rtd_pt100',    'flow': 'flow_orifice'},
                        lambda x: results['actual_poly_efficiency'],
                        'polytropic_efficiency'
                    )
                    results['uncertainty'] = {
                        'polytropic_efficiency': {
                            'value':                results['actual_poly_efficiency'],
                            'combined_uncertainty': unc['combined_uncertainty'],
                            'expanded_uncertainty': unc['expanded_uncertainty'],
                            'confidence_level':     '95%',
                            'breakdown':            unc['breakdown_percent'],
                        },
                        'asme_ptc10_compliant': True,
                    }
                except Exception as e:
                    self.logger.warning(f"Belirsizlik modülü başarısız: {e}")
                    results['uncertainty'] = None
            else:
                results['uncertainty'] = None

            self.performance_monitor.log_performance(
                'design_performance',
                (datetime.datetime.now() - start_time).total_seconds()
            )
            return results

        except Exception as e:
            self.logger.error(f"Design performance error: {e}", exc_info=True)
            raise AdvancedThermodynamicError(f"Hesaplama hatası (V4.4): {e}")

    # ─── Hesaplama Metodları (Private) ───────────────────────────────────────

    def _method_average_properties(self, p_in, t_in, p_out, poly_eff, gas_obj, eos, max_iter=100, tolerance=0.01):
        """
        Metot 1: Ortalama Özellikler

        Giriş ve çıkış özgül ısı oranlarının (k) ortalaması ile sıkıştırma
        yolunu iteratif olarak çözer. PR > EngineSettings.PR_INTEGRATION_THRESHOLD
        (varsayılan 4.0) ise API 617 Appendix C sayısal integrasyonu uygulanır.

        Kullanıcının girdiği poly_eff değeri, her iterasyonda n = (k-1)/(k×η_p)
        formülünde sıkıştırma üssünü belirlemek için kullanılır.
        Bu üsle hesaplanan T_out, State2 için tekrar k hesabını tetikler.
        Döngü, T_out < tolerance değişene kadar devam eder.

        Returns:
            (t_out_k, poly_head_kj_kg, z_avg, history)
        """
        pr = p_out / p_in
        use_integral = pr > EngineSettings.PR_INTEGRATION_THRESHOLD

        if use_integral:
            self.logger.info(
                f"📊 API 617 Appendix C — İntegral metodu: PR={pr:.2f} > {EngineSettings.PR_INTEGRATION_THRESHOLD}"
            )

        try:
            state_in = self.thermo_solver.get_properties(p_in, t_in, gas_obj, eos)
            k1, Z1  = state_in.k, state_in.Z
        except Exception as e:
            raise RuntimeError(f"Giriş özellikleri hesaplanamadı (Metot 1): {e}")

        n_init   = (k1 - 1) / (k1 * poly_eff)
        t2_guess = t_in * (p_out / p_in) ** n_init
        if t2_guess <= 0 or t2_guess > t_in * 10:
            t2_guess = t_in * 1.5

        history = {
            'pressure':    [p_in],
            'temperature': [t_in],
            'z_factor':    [Z1],
            'k_value':     [k1],
            'iteration':   [0],
            'method_used': 'integral' if use_integral else 'averaging',
        }
        integral_analysis = None
        _use_integral = use_integral  # Hata durumunda fallback için yerel kopya

        for iteration in range(max_iter):
            t2_old = t2_guess

            try:
                state_out = self.thermo_solver.get_properties(p_out, t2_old, gas_obj, eos)
                k2, Z2    = state_out.k, state_out.Z
            except Exception as e:
                raise RuntimeError(f"Çıkış özellikleri hesaplanamadı (Metot 1, iter {iteration}): {e}")

            if _use_integral:
                try:
                    n_minus_1_over_n, k_integral, integral_analysis = \
                        CompressorAerodynamics.calculate_polytropic_exponent_integral(
                            p_in, t_in, p_out, poly_eff,
                            self.thermo_solver, gas_obj, eos, steps=20
                        )
                    k_avg = k_integral
                    history['k_integral']        = k_integral
                    history['integral_analysis'] = integral_analysis
                except Exception as e:
                    self.logger.warning(f"⚠ İntegral metot başarısız, ortalamaya dönülüyor: {e}")
                    k_avg = (k1 + k2) / 2.0
                    n_minus_1_over_n = (k_avg - 1) / (k_avg * poly_eff)
                    _use_integral = False
                    history['method_used'] = 'averaging_fallback'
            else:
                k_avg            = (k1 + k2) / 2.0
                n_minus_1_over_n = (k_avg - 1) / (k_avg * poly_eff)

            Z_avg = CompressorAerodynamics._calculate_z_average_logarithmic(Z1, Z2)

            if abs(n_minus_1_over_n) < 1e-10:
                self.logger.warning("Metot 1: n_minus_1_over_n sıfıra çok yakın, döngü sonlandırıldı.")
                break

            t2_new = t_in * (p_out / p_in) ** n_minus_1_over_n
            # Salınımı önlemek için damping (0.5)
            t2_guess = t2_old + 0.5 * (t2_new - t2_old)

            history['pressure'].append(p_out)
            history['temperature'].append(t2_guess)
            history['z_factor'].append(Z_avg)
            history['k_value'].append(k_avg)
            history['iteration'].append(iteration + 1)

            if abs(t2_guess - t2_old) < tolerance:
                # Yakınsandı — ortalama koşullarda Z'yi yenile, head hesapla
                try:
                    state_avg = self.thermo_solver.get_properties((p_in + p_out) / 2, (t_in + t2_guess) / 2, gas_obj, eos)
                    Z_avg = state_avg.Z
                    MW    = state_avg.MW
                except Exception:
                    MW = state_in.MW

                R_sp = R_UNIVERSAL_J_MOL_K / (MW / 1000.0)
                poly_head = (Z_avg * R_sp * t_in * (1.0 / n_minus_1_over_n)
                             * (math.pow(p_out / p_in, n_minus_1_over_n) - 1.0)) / 1000.0

                self.logger.debug(f"✓ Metot 1 yakınsadı: {iteration + 1} iter, T_out={t2_guess:.1f} K")
                return t2_guess, poly_head, Z_avg, history

        # Yakınsamasız son değer
        self.logger.warning(f"⚠ Metot 1: Maks. iterasyon ({max_iter}) aşıldı, son tahmin kullanılıyor.")
        try:
            state_avg = self.thermo_solver.get_properties((p_in + p_out) / 2, (t_in + t2_guess) / 2, gas_obj, eos)
            Z_avg_f = state_avg.Z
            k_f     = state_avg.k
            MW      = state_avg.MW
        except Exception:
            Z_avg_f = Z1; k_f = k1; MW = state_in.MW

        R_sp  = R_UNIVERSAL_J_MOL_K / (MW / 1000.0)
        n_f   = (k_f - 1) / (k_f * poly_eff)
        poly_head = (Z_avg_f * R_sp * t_in * (1.0 / n_f)
                     * (math.pow(p_out / p_in, n_f) - 1.0)) / 1000.0 if abs(n_f) > 1e-10 else 0.0
        return t2_guess, poly_head, Z_avg_f, history

    def _method_endpoint(self, p_in, t_in, p_out, poly_eff, gas_obj, eos, max_iter=100, tolerance=0.01):
        """
        Metot 2: Uç Nokta İterasyonu

        Sadece hesaplanan çıkış noktasının k2 değerini kullanarak n hesaplar.
        Daha basit, ancak büyük basınç oranlarında Metot 1'den az doğru olabilir.

        Kullanıcının gordiği poly_eff, her adımda çıkış k2 ile:
            n = (k2 - 1) / (k2 × η_p)  →  T_out = T_in × (P_out/P_in)^n
        şeklinde kullanılır.

        Returns:
            (t_out_k, poly_head_kj_kg, z_avg, history)
        """
        try:
            state_in = self.thermo_solver.get_properties(p_in, t_in, gas_obj, eos)
            k1, Z1   = state_in.k, state_in.Z
        except Exception as e:
            raise RuntimeError(f"Giriş özellikleri hesaplanamadı (Metot 2): {e}")

        n_init   = (k1 - 1) / (k1 * poly_eff)
        t2_guess = t_in * (p_out / p_in) ** n_init
        if t2_guess <= 0:
            t2_guess = t_in * 1.1

        history = {
            'pressure':    [p_in],
            'temperature': [t_in],
            'z_factor':    [Z1],
            'k_value':     [k1],
            'iteration':   [0],
            'method_used': 'endpoint',
        }

        for iteration in range(max_iter):
            t2_old = t2_guess

            try:
                state_out = self.thermo_solver.get_properties(p_out, t2_old, gas_obj, eos)
                k2, Z2    = state_out.k, state_out.Z
            except Exception as e:
                raise RuntimeError(f"Çıkış özellikleri hesaplanamadı (Metot 2, iter {iteration}): {e}")

            n_minus_1_over_n = (k2 - 1) / (k2 * poly_eff)
            if abs(n_minus_1_over_n) < 1e-10:
                break

            t2_new   = t_in * (p_out / p_in) ** n_minus_1_over_n
            # Damping
            t2_guess = t2_old + 0.8 * (t2_new - t2_old)
            if t2_guess <= t_in:
                t2_guess = t_in * 1.01

            history['pressure'].append(p_out)
            history['temperature'].append(t2_guess)
            history['z_factor'].append(Z2)
            history['k_value'].append(k2)
            history['iteration'].append(iteration + 1)

            if abs(t2_guess - t2_old) < tolerance:
                state_out_final = self.thermo_solver.get_properties(p_out, t2_guess, gas_obj, eos)
                Z2_f  = state_out_final.Z
                Z_avg = CompressorAerodynamics._calculate_z_average_logarithmic(Z1, Z2_f)
                R_sp  = R_UNIVERSAL_J_MOL_K / (state_in.MW / 1000.0)
                poly_head = (Z_avg * R_sp * t_in * (1.0 / n_minus_1_over_n)
                             * (math.pow(p_out / p_in, n_minus_1_over_n) - 1.0)) / 1000.0

                self.logger.debug(f"✓ Metot 2 yakınsadı: {iteration + 1} iter, T_out={t2_guess:.1f} K")
                return t2_guess, poly_head, Z_avg, history

        # Yakınsamasız son değer
        self.logger.warning(f"⚠ Metot 2: Yakınsama sağlanamadı ({max_iter} iter).")
        Z_avg_f = CompressorAerodynamics._calculate_z_average_logarithmic(Z1, Z2)
        R_sp    = R_UNIVERSAL_J_MOL_K / (state_in.MW / 1000.0)
        n_f     = (k2 - 1) / (k2 * poly_eff)
        poly_head = (Z_avg_f * R_sp * t_in * (1.0 / n_f)
                     * (math.pow(p_out / p_in, n_f) - 1.0)) / 1000.0 if abs(n_f) > 1e-10 else 0.0
        return t2_guess, poly_head, Z_avg_f, history

    def _method_incremental_pressure(self, p_in, t_in, p_out, poly_eff, gas_obj, eos, step_count=10):
        """
        Metot 3: Artımlı Basınç Adımları

        Toplam sıkıştırmayı geometrik olarak eşit basınç adımlarına böler.
        Her adımda o noktanın k değeri ile yerel n hesaplanır; head ve sıcaklık
        birikimli toplanır. Yüksek doğruluk, ancak daha yavaş.

        Kullanıcının girdiği poly_eff, her adımda:
            n_adım = (k_adım - 1) / (k_adım × η_p)
        formülünde kullanılır; head kümülatif olarak birikmektedir.

        Returns:
            (t_out_k, poly_head_kj_kg, z_avg, history)
        """
        if step_count < 2:
            step_count = 10

        try:
            state_in = self.thermo_solver.get_properties(p_in, t_in, gas_obj, eos)
            Z0       = state_in.Z
            MW       = state_in.MW
        except Exception as e:
            raise RuntimeError(f"Giriş özellikleri hesaplanamadı (Metot 3): {e}")

        R_sp = R_UNIVERSAL_J_MOL_K / (MW / 1000.0)

        history = {
            'pressure':         [p_in],
            'temperature':      [t_in],
            'z_factor':         [Z0],
            'head_incremental': [0.0],
            'step':             [0],
            'method_used':      'incremental_pressure',
        }

        pressures    = np.geomspace(p_in, p_out, step_count + 1)
        p_current    = p_in
        t_current    = t_in
        total_head   = 0.0
        z_list       = [Z0]

        for i in range(step_count):
            p_start = pressures[i]
            p_end   = pressures[i + 1]

            try:
                state_step = self.thermo_solver.get_properties(p_start, t_current, gas_obj, eos)
                k_step = state_step.k
                z_step = state_step.Z
            except Exception as e:
                raise RuntimeError(f"Artımlı hesaplama hatası — Adım {i}: {e}")

            n_step = (k_step - 1) / (k_step * poly_eff)
            if abs(n_step) < 1e-10:
                raise RuntimeError(f"n_step sıfıra çok yakın (adım {i}).")

            head_step   = (z_step * R_sp * t_current * (1.0 / n_step)
                           * (math.pow(p_end / p_start, n_step) - 1.0)) / 1000.0
            total_head += head_step
            t_current   = t_current * (p_end / p_start) ** n_step

            z_list.append(z_step)
            history['pressure'].append(p_end)
            history['temperature'].append(t_current)
            history['z_factor'].append(z_step)
            history['head_incremental'].append(total_head)
            history['step'].append(i + 1)

        z_avg = float(np.mean(z_list))
        self.logger.debug(f"✓ Metot 3 tamamlandı: {step_count} adım, T_out={t_current:.1f} K, Head={total_head:.2f} kJ/kg")
        return t_current, total_head, z_avg, history

    def _method_direct_hs(self, p_in, t_in, p_out, poly_eff, gas_obj, eos):
        """
        Metot 4: Doğrudan Entalpi-Entropi (H-S) Yöntemi

        Politropik üs (n) ve özgül ısı oranı (k) hesaplamasını ATLAR.
        Bunun yerine EOS'un doğrudan ürettiği H ve S değerleriyle çalışır:

          1. İzentropik çıkış sıcaklığını bul  →  S(P₂, T₂ₛ) = S₁
          2. İzentropik entalpi farkını hesapla →  ΔH_isen = H₂ₛ - H₁
          3. Politropik→İzentropik verim dönüşümü (Schultz yaklaşımı)
          4. Gerçek ΔH hesapla                →  ΔH_gerçek = ΔH_isen / η_isen
          5. Gerçek T₂'yi bul                 →  H(P₂, T₂) = H₁ + ΔH_gerçek
          6. Politropik head'i geri hesapla    →  σ = ln(T₂/T₁)/ln(P₂/P₁)

        Bu yöntem, mevcut 3 metodun bağımsız çapraz doğrulaması olarak kullanılır.

        Returns:
            (t_out_k, poly_head_kj_kg, z_avg, history)
        """
        try:
            state_in = self.thermo_solver.get_properties(p_in, t_in, gas_obj, eos)
            H1, S1, k1, Z1 = state_in.H, state_in.S, state_in.k, state_in.Z
            MW = state_in.MW
        except Exception as e:
            raise RuntimeError(f"Giriş özellikleri hesaplanamadı (Metot 4): {e}")

        R_sp = R_UNIVERSAL_J_MOL_K / (MW / 1000.0)

        # ── Adım 1: İzentropik Çıkış Sıcaklığı ──────────────────────────────
        # S(P_out, T_isen) = S_in  →  T_isen bulunacak
        t_isen = self._find_isentropic_temperature(p_in, t_in, p_out, S1, gas_obj, eos, state_in)

        try:
            state_isen = self.thermo_solver.get_properties(p_out, t_isen, gas_obj, eos)
            H2_isen = state_isen.H
        except Exception as e:
            raise RuntimeError(f"İzentropik çıkış özellikleri hesaplanamadı (Metot 4): {e}")

        # ── Adım 2: İzentropik Entalpi Farkı ─────────────────────────────────
        delta_h_isen = H2_isen - H1  # J/kg

        if delta_h_isen <= 0:
            # CoolProp yüksek sıcaklıklarda fallback'a düşebilir ve tutarsız H verebilir.
            # Bu durumda k tabanlı basit izentropik iş hesabı kullan.
            self.logger.warning(
                f"⚠ Metot 4: ΔH_isen negatif ({delta_h_isen:.1f} J/kg). "
                f"k-tabanlı izentropik fallback kullanılıyor."
            )
            pr = p_out / p_in
            n_isen_fb = (k1 - 1) / k1
            Z_avg_fb = Z1  # Giriş Z'si ile yaklaşım
            delta_h_isen = (Z_avg_fb * R_sp * t_in * (1.0 / n_isen_fb)
                            * (math.pow(pr, n_isen_fb) - 1.0))  # J/kg
            # t_isen'i de güncelle
            t_isen = t_in * math.pow(pr, n_isen_fb)
            self.logger.info(
                f"  Fallback: ΔH_isen={delta_h_isen/1000:.1f} kJ/kg, T_isen={t_isen:.1f} K"
            )

        # ── Adım 3-5: İteratif Schultz Dönüşümü + T₂ Çözümü ─────────────────
        # Dış döngü: k_avg'ı güncelleyerek η_isen ve T₂'yi iyileştir
        pr = p_out / p_in
        k_avg = k1  # İlk tahmin
        t2_guess = t_isen * (1.0 + (1.0 - poly_eff) * 0.3)  # İlk T₂ tahmini
        iterations_hs = []
        outer_iterations = 3  # k_avg rafine döngüsü

        for outer in range(outer_iterations):
            # ── Adım 3: Schultz η_isen hesabı (güncel k_avg ile) ──────────
            exponent_isen = (k_avg - 1) / k_avg
            exponent_poly = (k_avg - 1) / (k_avg * poly_eff)

            pr_isen_term = math.pow(pr, exponent_isen) - 1.0
            pr_poly_term = math.pow(pr, exponent_poly) - 1.0

            if abs(pr_poly_term) < 1e-10:
                eta_isen = poly_eff
            else:
                eta_isen = pr_isen_term / pr_poly_term

            eta_isen = max(0.01, min(1.0, eta_isen))

            # ── Adım 4: Gerçek entalpi farkı ──────────────────────────────
            delta_h_actual = delta_h_isen / eta_isen  # J/kg
            H_target = H1 + delta_h_actual

            # ── Adım 5: T₂ Newton-Raphson ─────────────────────────────────
            max_iter = 30
            tol_h = 100.0  # J/kg

            for iteration in range(max_iter):
                try:
                    state_guess = self.thermo_solver.get_properties(p_out, t2_guess, gas_obj, eos)
                    H_guess = state_guess.H
                except Exception as e:
                    self.logger.warning(f"Metot 4 iter {outer}.{iteration}: özellik hatası @ T={t2_guess:.1f} K: {e}")
                    t2_guess = t2_guess * 0.99
                    continue

                dH = H_guess - H_target
                iterations_hs.append({
                    'iter': f"{outer}.{iteration}", 'T': t2_guess, 'H': H_guess,
                    'H_target': H_target, 'dH': dH, 'k_avg': k_avg, 'eta_isen': eta_isen
                })

                if abs(dH) < tol_h:
                    self.logger.debug(
                        f"✓ Metot 4 iç döngü yakınsadı: outer={outer}, iter={iteration + 1}, "
                        f"T_out={t2_guess:.1f} K, ΔH_err={dH:.1f} J/kg, k_avg={k_avg:.4f}"
                    )
                    break

                # Sayısal türev dH/dT (~Cp)
                dt = 0.5
                try:
                    state_plus = self.thermo_solver.get_properties(p_out, t2_guess + dt, gas_obj, eos)
                    dH_dT = (state_plus.H - H_guess) / dt
                except Exception:
                    dH_dT = state_in.Cp if state_in.Cp > 0 else 2000.0

                if abs(dH_dT) < 1e-5:
                    dH_dT = 2000.0

                # Newton adımı (damped)
                delta_t = -dH / dH_dT
                delta_t = max(-50.0, min(50.0, delta_t))  # Adım sınırı
                t2_guess = t2_guess + 0.8 * delta_t
                t2_guess = max(t_in * 1.001, min(t_in * 5.0, t2_guess))  # Fiziksel sınırlar

            else:
                self.logger.warning(
                    f"⚠ Metot 4: inner loop maks. iterasyon ({max_iter}) aşıldı. "
                    f"Son T={t2_guess:.1f} K"
                )

            # ── Dış döngü: k_avg güncelleme ───────────────────────────────
            # T₂ bulundu → k₂ hesapla → k_avg = (k₁ + k₂) / 2 → tekrar η_isen
            try:
                state_t2 = self.thermo_solver.get_properties(p_out, t2_guess, gas_obj, eos)
                k2 = state_t2.k
                k_avg_new = (k1 + k2) / 2.0
                self.logger.debug(
                    f"  Dış döngü {outer}: k₁={k1:.4f}, k₂={k2:.4f}, "
                    f"k_avg: {k_avg:.4f} → {k_avg_new:.4f}"
                )
                if abs(k_avg_new - k_avg) < 0.001:
                    # k_avg yakınsadı, dış döngüden çık
                    k_avg = k_avg_new
                    break
                k_avg = k_avg_new
            except Exception:
                # k₂ hesaplanamadıysa mevcut k_avg ile devam et
                break

        # ── Adım 6: Politropik Head Geri Hesaplama ────────────────────────────
        # σ = ln(T₂/T₁) / ln(P₂/P₁)
        try:
            state_out = self.thermo_solver.get_properties(p_out, t2_guess, gas_obj, eos)
            Z2 = state_out.Z
        except Exception:
            Z2 = Z1

        Z_avg = CompressorAerodynamics._calculate_z_average_logarithmic(Z1, Z2)

        ln_TR = math.log(t2_guess / t_in) if t2_guess > t_in else 1e-10
        ln_PR = math.log(p_out / p_in)

        if abs(ln_PR) < 1e-10:
            poly_head = 0.0
        else:
            sigma = ln_TR / ln_PR  # (n-1)/n geri hesaplanan

            if abs(sigma) < 1e-10:
                # İzotermal limit
                poly_head = (Z_avg * R_sp * t_in * ln_PR) / 1000.0
            else:
                poly_head = (Z_avg * R_sp * t_in * (1.0 / sigma)
                             * (math.pow(p_out / p_in, sigma) - 1.0)) / 1000.0

        # ── History (Tanı Verisi) ─────────────────────────────────────────────
        history = {
            'method_used': 'direct_hs',
            'pressure': [p_in, p_out],
            'temperature': [t_in, t2_guess],
            'z_factor': [Z1, Z2],
            'iteration': list(range(len(iterations_hs) + 1)),
            't_isentropic': t_isen,
            'delta_h_isentropic_kj': delta_h_isen / 1000.0,
            'delta_h_actual_kj': delta_h_actual / 1000.0,
            'eta_isentropic_derived': eta_isen,
            'sigma_backcomputed': ln_TR / ln_PR if abs(ln_PR) > 1e-10 else 0,
            'iterations_detail': iterations_hs,
        }

        self.logger.info(
            f"✓ Metot 4 (H-S) tamamlandı: T_out={t2_guess:.1f} K ({t2_guess-273.15:.1f}°C), "
            f"H_poly={poly_head:.2f} kJ/kg, η_isen={eta_isen:.4f}, "
            f"ΔH_isen={delta_h_isen/1000:.1f} kJ/kg, ΔH_actual={delta_h_actual/1000:.1f} kJ/kg"
        )

        return t2_guess, poly_head, Z_avg, history

    def _find_isentropic_temperature(self, p_in, t_in, p_out, S_target, gas_obj, eos, state_in):
        """
        İzentropik çıkış sıcaklığını bulur: S(P_out, T_isen) = S_target

        CoolProp'ta doğrudan Entropy-Pressure flash yapılır.
        PR/SRK'da Newton-Raphson iterasyonu ile çözülür.
        """
        # ── CoolProp: Direct Flash ────────────────────────────────────────────
        if eos == 'coolprop':
            try:
                import CoolProp.CoolProp as CP
                t_isen = CP.PropsSI('T', 'P', p_out, 'Smass', S_target, gas_obj)
                if t_isen > 0 and t_isen < t_in * 10:
                    self.logger.debug(f"CoolProp izentropik flash: T_isen={t_isen:.1f} K")
                    return t_isen
            except Exception as e:
                self.logger.debug(f"CoolProp izentropik flash başarısız: {e}")

        # ── Newton-Raphson Fallback (PR/SRK ve CoolProp hatası) ───────────────
        k = state_in.k if state_in.k > 1.0 else 1.3
        n_isen = (k - 1) / k
        t_guess = t_in * math.pow(p_out / p_in, n_isen)

        for i in range(25):
            try:
                state_try = self.thermo_solver.get_properties(p_out, t_guess, gas_obj, eos)
                S_try = state_try.S
            except Exception:
                t_guess *= 1.01
                continue

            dS = S_try - S_target
            if abs(dS) < 5.0:  # J/(kg·K) tolerans
                self.logger.debug(f"İzentropik Newton yakınsadı: {i+1} iter, T={t_guess:.1f} K")
                return t_guess

            # dS/dT ≈ Cp/T
            dS_dT = state_try.Cp / t_guess if state_try.Cp > 0 else 2.0
            if abs(dS_dT) < 1e-10:
                dS_dT = 2.0

            delta = -dS / dS_dT
            delta = max(-30.0, min(30.0, delta))
            t_guess += 0.7 * delta
            t_guess = max(t_in * 0.9, min(t_in * 5.0, t_guess))

        self.logger.warning(f"⚠ İzentropik T tam yakınsayamadı, son T={t_guess:.1f} K")
        return t_guess

    # ─── Self-Consistent & Wrapper Metodlar ──────────────────────────────────


    def _calculate_with_consistency(self, inputs):
        """
        Self-Consistent Calculation — SUR (Successive Under-Relaxation)

        Seçilen hesaplama metodunu, hesaplanan verimin kullanıcının girdiği
        hedef verime yakınsayana kadar iteratif olarak çalıştırır.

        Kullanıcının girdiği poly_eff burada η_target olarak alınır.
        Her iterasyonda hesaplanan gerçek verim (actual_poly_efficiency) ile
        η_target arasındaki hata α = 0.5 ile güncelleme adımına girdi olur:
            η_new = α × η_hesaplanan + (1-α) × η_mevcut

        Reference: Numerical Recipes, Ch. 9.7 (Fixed-Point Iteration)
        """
        start_time = datetime.datetime.now()

        η_target  = float(inputs.get('poly_eff', 85.0))
        η_current = η_target
        α         = 0.5       # Relaxation faktörü
        tolerance = float(inputs.get('consistency_tolerance', 0.1))  # %
        max_iter  = int(inputs.get('max_consistency_iter', 20))

        self.logger.info(
            f"🔄 Tutarlılık modu | Hedef η={η_target:.2f}% | "
            f"Tol={tolerance}% | Maks. iter={max_iter}"
        )

        history   = []
        converged = False
        residual  = 0.0
        results   = {}

        for k in range(max_iter):
            inputs_temp           = dict(inputs)  # Sığ kopya
            inputs_temp['poly_eff'] = η_current

            try:
                results = self.calculate_design_performance(inputs_temp)
            except Exception as e:
                self.logger.error(f"Tutarlılık iter {k + 1} hatası: {e}")
                break

            η_calculated = results['actual_poly_efficiency'] * 100.0
            residual     = abs(η_calculated - η_current)

            history.append({
                'iteration':     k + 1,
                'eta_used':      η_current,
                'eta_calculated': η_calculated,
                'residual':      residual,
                't_out':         results.get('t_out', 0),
                'power_kw':      results.get('power_unit_kw', 0),
            })

            self.logger.debug(
                f"  Iter {k + 1}: η_used={η_current:.3f}% → "
                f"η_calc={η_calculated:.3f}% | Residual={residual:.4f}%"
            )

            if residual < tolerance:
                converged = True
                self.logger.info(
                    f"✓ Tutarlılık yakınsadı — iter={k + 1}, "
                    f"η={η_current:.3f}%, Residual={residual:.4f}%"
                )
                break

            η_new     = α * η_calculated + (1 - α) * η_current
            η_current = max(1.0, min(99.0, η_new))

        if not converged:
            self.logger.warning(
                f"⚠ Tutarlılık maks. iter ({max_iter}) aşıldı. "
                f"Son residual={residual:.4f}% (tol={tolerance}%)"
            )

        results['consistency_mode']       = True
        results['poly_eff_target']        = η_target
        results['poly_eff_converged']     = η_current
        results['consistency_iterations'] = len(history)
        results['consistency_history']    = history
        results['consistency_converged']  = converged
        results['final_residual']         = residual

        elapsed = (datetime.datetime.now() - start_time).total_seconds()
        self.logger.info(f"Tutarlılık hesabı tamamlandı: {elapsed:.1f}s, {len(history)} iter")
        return results

    def calculate_design_performance_with_mode(self, inputs):
        """
        Wrapper — Mod seçimine göre hesaplama yapar.

        Mode 1 (Hızlı):    calculate_design_performance()       ← inputs['method'] ile seçilen metot
        Mode 2 (Tutarlı):  _calculate_with_consistency()        ← η hedefine iteratif yakınsama

        inputs anahtar değerleri:
            'use_consistency_iteration' : bool  — True → Tutarlılık modu
            'method'                    : str   — Hesaplama metodu (1/2/3)
            'max_consistency_iter'      : int   — Maks. tutarlılık iterasyonu (varsayılan 20)
            'consistency_tolerance'     : float — Yakınsama toleransı % (varsayılan 0.1)
        """
        if inputs.get('use_consistency_iteration', False):
            self.logger.info("🔄 Tutarlılık modu aktif — İteratif hesaplama başlıyor...")
            return self._calculate_with_consistency(inputs)
        else:
            return self.calculate_design_performance(inputs)

    # -------------------------------------------------------------------------
    # 5. TEST VE POLİTROPİK VERİM HESAPLAMA EKRANLARI
    # -------------------------------------------------------------------------
    def calculate_performance_test(self, inputs):
        """Gerçek sahada ölçülen giriş ve çıkış T-P değerlerine göre kompresör performansını inceler."""
        start_time = datetime.datetime.now()
        try:
             # Basic mapping and conversion
             amb_p = inputs.get('ambient_pressure_pa', self.STD_PRESS_PA)
             p_in_pa = self.convert_pressure_to_pa(float(inputs['p_in']), inputs['p_in_unit'], amb_p)
             t_in_k = self.convert_temperature_to_k(float(inputs['t_in']), inputs['t_in_unit'])
             p_out_pa = self.convert_pressure_to_pa(float(inputs['p_out']), inputs['p_out_unit'], amb_p)
             t_out_k = self.convert_temperature_to_k(float(inputs['t_out']), inputs['t_out_unit'])
             
             gas_obj = self._create_gas_object(inputs['gas_comp'], inputs['eos_method'])
             state_in = self.thermo_solver.get_properties(p_in_pa, t_in_k, gas_obj, inputs['eos_method'])
             state_out = self.thermo_solver.get_properties(p_out_pa, t_out_k, gas_obj, inputs['eos_method'])
             
             t_out_isen = CompressorAerodynamics.calculate_isentropic_outlet_temp(
                 state_in, p_out_pa, self.thermo_solver, gas_obj, inputs['eos_method']
             )
             state_isen = self.thermo_solver.get_properties(p_out_pa, t_out_isen, gas_obj, inputs['eos_method'])
             
             actual_head_kj_kg = (state_out.H - state_in.H) / 1000.0
             isen_head_kj_kg = (state_isen.H - state_in.H) / 1000.0
             
             R_sp = R_UNIVERSAL_J_MOL_K / (state_in.MW / 1000.0)
             actual_poly_eff = CompressorAerodynamics.calculate_polytropic_efficiency(state_in, state_out, R_sp)
             actual_isen_eff = isen_head_kj_kg / actual_head_kj_kg if actual_head_kj_kg > 0 else 0
             true_poly_head_kj_kg = actual_head_kj_kg * actual_poly_eff
             
             mass_flow_kgs = self.convert_flow_to_kgs(float(inputs['flow']), inputs['flow_unit'], gas_obj, inputs['eos_method'])
             gas_power_kw = mass_flow_kgs * actual_head_kj_kg
             inlet_acmh = (mass_flow_kgs / state_in.density) * 3600.0
             mech_loss_kw = CompressorAerodynamics.calculate_mechanical_loss(inlet_acmh/3600.0, gas_power_kw)
             shaft_power_kw = gas_power_kw + mech_loss_kw
             
             # Status check
             expected_poly_eff = float(inputs.get('design_poly_eff', 0.85))
             dev_poly = ((actual_poly_eff - expected_poly_eff) / expected_poly_eff * 100.0) if expected_poly_eff > 0 else 0.0
             
             # Fallbacks for other deviations
             dev_power = 0; dev_heat_rate = 0; actual_heat_rate = 0; corrected_power = shaft_power_kw
             
             status_obj = self._evaluate_performance_status({
                 'deviation_poly_eff': dev_poly, 'deviation_therm_eff': 0, 
                 'deviation_power': dev_power, 'deviation_heat_rate': dev_heat_rate
             })
             
             return {
                 'actual_poly_eff': min(max(actual_poly_eff, 0), 1),
                 'expected_poly_eff': expected_poly_eff,
                 'deviation_poly_eff': dev_poly,
                 'actual_isentropic_eff': actual_isen_eff,
                 'actual_power': shaft_power_kw,
                 'expected_power': corrected_power,
                 'deviation_power': dev_power,
                 'actual_heat_rate': actual_heat_rate,
                 'expected_heat_rate': actual_heat_rate,
                 'deviation_heat_rate': dev_heat_rate,
                 'performance_status': status_obj,
                 'actual_therm_eff': 0, 'expected_therm_eff':0, 'deviation_therm_eff':0
             }
        except Exception as e:
             self.logger.error(f"Performans testi hatası: {e}")
             raise

    def evaluate_performance(self, inputs):
        """
        ASME PTC 10 / API 617 standartlarına göre mevcut saha şartları verildiğinde kompresör performansını hesaplar.
        """
        try:
            p1 = inputs['p1_pa']
            t1 = inputs['t1_k']
            p2 = inputs['p2_pa']
            t2 = inputs['t2_k']
            flow_kgs = inputs['flow_kgs']
            mech_eff = inputs['mech_eff'] / 100.0
            driver_mode = inputs['driver_mode']
            driver_val = inputs['driver_val']
            
            gas_obj = self._create_gas_object(inputs['gas_comp'], inputs['eos_method'])
            eos = inputs['eos_method']
            
            # 1. Durum Belirleme (Entalpi - Entropi)
            state_in = self.thermo_solver.get_properties(p1, t1, gas_obj, eos)
            state_out_actual = self.thermo_solver.get_properties(p2, t2, gas_obj, eos)
            
            h1 = state_in.H
            s1 = state_in.S
            h2_actual = state_out_actual.H
            
            actual_dh = h2_actual - h1
            if actual_dh <= 0:
                raise ValueError("Hesaplanan entalpi değişimi negatif veya sıfır. Çıkış sıcaklığını (T2) kontrol edin.")
                
            # 2. İzentropik Çıkış Durumu
            t2_s = CompressorAerodynamics.calculate_isentropic_temp_fallback(state_in, p2, self.thermo_solver, gas_obj, eos)
            state_out_isen = self.thermo_solver.get_properties(p2, t2_s, gas_obj, eos)
            h2_isen = state_out_isen.H
            
            isen_dh = h2_isen - h1
            
            # Verim ve Head hesapları (ASME PTC 10 / API 617 Doğrudan oranlama)
            isen_eff = isen_dh / actual_dh
            
            R_sp = R_UNIVERSAL_J_MOL_K / (state_in.MW / 1000.0)
            poly_eff = CompressorAerodynamics.calculate_polytropic_efficiency(state_in, state_out_actual, R_sp)
            poly_head_j_kg = poly_eff * actual_dh
            
            # 3. Güç Hesapları
            gas_power_w = actual_dh * flow_kgs
            gas_power_kw = gas_power_w / 1000.0
            
            inlet_acmh = (flow_kgs / state_in.density) * 3600.0
            mech_loss_kw = CompressorAerodynamics.calculate_mechanical_loss(inlet_acmh / 3600.0, gas_power_kw)
            
            shaft_power_kw = gas_power_kw + mech_loss_kw
            motor_power_kw = shaft_power_kw / mech_eff
            
            # 4. Sürücü (Türbin/Yakıt) Hesapları
            lhv_kj_kg, _ = self._calculate_heating_values(
                inputs['gas_comp'], 
                source=inputs.get('lhv_source', 'kasp')
            )
            if lhv_kj_kg <= 0:
                lhv_kj_kg = 50000.0 # Varsayılan yakıt ısıl değeri kJ/kg (Metan'a yakın)
                
            turb_eff = 0.0
            fuel_cons_kg_h = 0.0
            
            if driver_mode == 'turb_eff':
                turb_eff = driver_val / 100.0
                if turb_eff > 0:
                    fuel_kw = motor_power_kw / turb_eff
                    fuel_cons_kg_h = (fuel_kw * 3600.0) / lhv_kj_kg
            else:
                fuel_cons_kg_h = driver_val
                if fuel_cons_kg_h > 0:
                    fuel_kw = (fuel_cons_kg_h * lhv_kj_kg) / 3600.0
                    turb_eff = motor_power_kw / fuel_kw if fuel_kw > 0 else 0.0
                
            return {
                'poly_eff': poly_eff * 100.0,
                'isen_eff': isen_eff * 100.0,
                'poly_head_kj_kg': poly_head_j_kg / 1000.0,
                'gas_power_kw': gas_power_kw,
                'shaft_power_kw': shaft_power_kw,
                'motor_power_kw': motor_power_kw,
                'turb_eff': turb_eff * 100.0,
                'fuel_cons_kg_h': fuel_cons_kg_h
            }
        except Exception as e:
            self.logger.error(f"Performans değerlendirme hatası: {e}")
            raise

    def calculate_polytropic_efficiency(self, p1_pa, t1_k, p2_pa, t2_k, gas_comp, eos_method):
        """Basit poli verim hesaplayıcı (UI'da bazı alt panellerde doğrudan çağırılır)"""
        try:
            gas_obj = self._create_gas_object(gas_comp, eos_method)
            state_in = self.thermo_solver.get_properties(p1_pa, t1_k, gas_obj, eos_method)
            state_out = self.thermo_solver.get_properties(p2_pa, t2_k, gas_obj, eos_method)
            R_sp = R_UNIVERSAL_J_MOL_K / (state_in.MW / 1000.0)
            return CompressorAerodynamics.calculate_polytropic_efficiency(state_in, state_out, R_sp)
        except Exception as e:
            self.logger.warning(f"Bağımsız politropik verim hesabı hatası: {e}")
            return 0.0

    # -------------------------------------------------------------------------
    # 6. TÜRBİN SEÇİMİ VE ANALİZ METOTLARI
    # -------------------------------------------------------------------------
    def select_units(self, required_power_kw, site_conditions, all_turbines_data, limit=5):
        """TurbineSelector modülüne delegasyon yapar."""
        recommendations = TurbineSelector.select_units(
            required_power_kw, site_conditions, all_turbines_data, limit
        )
        
        return recommendations

    def analyze_operating_envelope(self, compressor_data, operating_conditions):
        try:
            surge_flow = compressor_data.get('surge_flow', 0)
            stonewall_flow = compressor_data.get('stonewall_flow', 0)
            op_flow = operating_conditions.get('flow', 0)
            
            surge_dist = ((op_flow - surge_flow) / surge_flow * 100) if surge_flow > 0 else 0
            sw_dist = ((stonewall_flow - op_flow) / op_flow * 100) if stonewall_flow > 0 else 0
            
            region = 'SAFE'
            if surge_dist < 10 or sw_dist < 5: region = 'CRITICAL'
            elif surge_dist < 15 or sw_dist < 8: region = 'WARNING'
            
            recs = []
            if surge_dist < 10: recs.append("🚨 SURGE RİSKİ - Debiyi artırın")
            if sw_dist < 5: recs.append("🚨 STONEWALL RİSKİ - Debiyi düşürün")
            if not recs: recs.append("✅ Güvenli çalışma bölgesi")
            
            return {
                'surge_distance_percent': surge_dist,
                'stonewall_distance_percent': sw_dist,
                'safe_operating_margin': min(surge_dist, sw_dist),
                'operating_region': region,
                'recommendations': recs
            }
        except Exception as e:
            return {'error': str(e)}

    def generate_summary_report(self, inputs, results, selected_units):
        try:
             return {
                 'project_name': inputs.get('project_name', 'Bilinmiyor'),
                 'calculation_date': datetime.datetime.now().isoformat(),
                 'basic_parameters': {
                     'num_units': inputs.get('num_units', 1),
                     'compression_ratio': results.get('compression_ratio', 1.0),
                     'power_per_unit': results.get('power_unit_kw', 0),
                     'total_power': results.get('power_unit_total_kw', 0),
                     'outlet_temperature': results.get('t_out', 0)
                 },
                 'efficiency_metrics': {
                     'poly_efficiency': float(inputs.get('poly_eff', 85)) / 100.0,
                     'actual_poly_efficiency': results.get('actual_poly_efficiency', 0),
                     'thermal_efficiency': float(inputs.get('therm_eff', 35)) / 100.0,
                     'heat_rate': results.get('heat_rate', 0)
                 },
                 'recommended_turbines': [
                     {
                         'rank': i + 1,
                         'turbine': u.turbine_name,
                         'power': u.available_power_kw,
                         'efficiency': u.efficiency_rating,
                         'score': u.selection_score
                     } for i, u in enumerate(selected_units[:3])
                 ] if selected_units else [],
                 'system_performance': self.performance_monitor.get_statistics()
             }
        except Exception as e:
             self.logger.error(f"Rapor oluşturma hatası: {e}")
             return {}

    def _evaluate_performance_status(self, deviations):
        max_dev = max(abs(deviations['deviation_poly_eff']), abs(deviations['deviation_therm_eff']),
                      abs(deviations['deviation_heat_rate']), abs(deviations['deviation_power']))
                      
        if max_dev <= 2.0:
            return {'status': 'EXCELLENT', 'color': 'green', 'description': 'İdeal', 'recommendation': 'Müdahale gerekmez.'}
        elif max_dev <= 5.0:
            return {'status': 'GOOD', 'color': 'blue', 'description': 'İyi', 'recommendation': 'Gözlemleyin.'}
        elif max_dev <= 10.0:
            return {'status': 'ACCEPTABLE', 'color': 'orange', 'description': 'Kabul edilebilir', 'recommendation': 'Bakım planlayın.'}
        else:
            return {'status': 'POOR', 'color': 'red', 'description': 'Düşük', 'recommendation': 'Acil bakım.'}
