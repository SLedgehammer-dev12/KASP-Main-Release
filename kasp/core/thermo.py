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

# Alt Bileşenler (V4.4 Modular Architecture)
from kasp.core.mixture import GasMixtureBuilder
from kasp.core.properties import ThermodynamicSolver
from kasp.core.aerodynamics import CompressorAerodynamics
from kasp.core.thermo_methods import ThermoMethodSuite
from kasp.core.thermo_design_orchestration import ThermoDesignOrchestrator
from kasp.core.selection import TurbineSelector
from kasp.core.thermo_design_support import (
    build_design_results_payload,
    build_uncertainty_measurements,
    build_uncertainty_payload,
    compute_stage_pressure_ratio,
    select_design_method_key,
)
from kasp.core.thermo_support import (
    build_summary_report,
    convert_flow_to_kgs,
    convert_pressure_to_pa,
    convert_result_value,
    convert_temperature_to_k,
    evaluate_performance_status,
    normalize_efficiency_reference,
    percent_deviation,
    safe_float,
)

from kasp.core.exceptions import (
    AdvancedThermodynamicError, UnitConversionError, FluidPropertyError
)
from kasp.utils.monitoring import PerformanceMonitor

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
        self.method_suite = ThermoMethodSuite(thermo_solver=self.thermo_solver, logger=self.logger)
        self.design_orchestrator = ThermoDesignOrchestrator(
            thermo_solver=self.thermo_solver,
            logger=self.logger,
        )
        
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
        sound_speed = math.sqrt(max(state.k, 0.0) * p_pa / state.density) if state.density > 0 else 0.0
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
            'a': sound_speed
        }

    @staticmethod
    def _safe_float(value, default=0.0):
        return safe_float(value, default)

    @staticmethod
    def _normalize_efficiency_reference(value, default=0.0):
        return normalize_efficiency_reference(value, default)

    @staticmethod
    def _percent_deviation(actual, expected):
        return percent_deviation(actual, expected)

    # -------------------------------------------------------------------------
    # 2. BİRİM DÖNÜŞÜM METOTLARI (UnitSystem ile Korumalı)
    # -------------------------------------------------------------------------
    def convert_pressure_to_pa(self, value, unit, ambient_pressure_pa=None):
        return convert_pressure_to_pa(value, unit, ambient_pressure_pa)

    def convert_temperature_to_k(self, value, unit):
        return convert_temperature_to_k(value, unit)

    def convert_flow_to_kgs(self, value, unit, gas_obj, eos_method):
        return convert_flow_to_kgs(
            value,
            unit,
            gas_obj,
            eos_method,
            thermo_solver=self.thermo_solver,
            logger=self.logger,
            std_press_pa=self.STD_PRESS_PA,
            standard_temp_k=self.STANDARD_TEMP_K,
            normal_temp_k=self.NORMAL_TEMP_K,
        )

    def convert_result_value(self, value: float, from_unit: str, to_unit: str, quantity_type: str) -> float:
        """UI sonuç panelleri için genel birim dönüştürücü"""
        try:
            return convert_result_value(value, from_unit, to_unit, quantity_type)
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
            stage_pr = compute_stage_pressure_ratio(pr_total, intercooler_dp, num_stages)

            max_iter      = int(inputs.get('method_max_iter', 100))
            tolerance     = float(inputs.get('method_tolerance', 0.01))
            step_count    = int(inputs.get('incremental_steps', 10))

            self.logger.info(
                f"Hesaplama başlıyor | Metot: {method} | "
                f"PR={pr_total:.2f} | Kademe={num_stages} | EOS={eos}"
            )

            method_key = select_design_method_key(method)
            stage_results = self.design_orchestrator.run_stage_loop(
                p_in_pa=p_in_pa,
                t_in_k=t_in_k,
                p_out_pa=p_out_pa,
                stage_pr=stage_pr,
                num_stages=num_stages,
                intercooler_dp=intercooler_dp,
                ic_t_k=ic_t_k,
                method_key=method_key,
                poly_eff_tgt=poly_eff_tgt,
                gas_obj=gas_obj,
                eos=eos,
                max_iter=max_iter,
                tolerance=tolerance,
                step_count=step_count,
                mass_flow_per_unit=mass_flow_per_unit,
                method_average_fn=self._method_average_properties,
                method_endpoint_fn=self._method_endpoint,
                method_incremental_fn=self._method_incremental_pressure,
                method_direct_hs_fn=self._method_direct_hs,
            )
            final_t_out_k = stage_results["final_t_out_k"]
            total_stage_gas_power_kw = stage_results["total_stage_gas_power_kw"]
            total_poly_head_kj_kg = stage_results["total_poly_head_kj_kg"]
            staged_results = stage_results["staged_results"]

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

            results = build_design_results_payload(
                p_in_pa=p_in_pa,
                t_in_k=t_in_k,
                p_out_pa=p_out_pa,
                final_t_out_k=final_t_out_k,
                total_poly_head_kj_kg=total_poly_head_kj_kg,
                poly_eff_tgt=poly_eff_tgt,
                total_stage_gas_power_kw=total_stage_gas_power_kw,
                total_shaft_kw=total_shaft_kw,
                motor_kw=motor_kw,
                unit_kw=unit_kw,
                mech_loss_kw=mech_loss_kw,
                fuel_kgh=fuel_kgh,
                mass_flow_per_unit=mass_flow_per_unit,
                inlet_acmh=inlet_acmh,
                num_units=num_units,
                total_mass_flow_kgs=total_mass_flow_kgs,
                heat_rate=heat_rate,
                lhv=lhv,
                hhv=hhv,
                inlet_properties=self._get_thermo_properties(p_in_pa, t_in_k, gas_obj, eos),
                outlet_properties=self._get_thermo_properties(p_out_pa, final_t_out_k, gas_obj, eos),
                num_stages=num_stages,
                staged_results=staged_results,
                method=method,
            )

            # 7. Belirsizlik Analizi (ASME PTC 10, opsiyonel)
            if self.uncertainty_analyzer and inputs.get('enable_uncertainty', True):
                try:
                    measurement_values = build_uncertainty_measurements(inputs)

                    def _recalculate_efficiency(varied_inputs):
                        perturbed_inputs = dict(inputs)
                        perturbed_inputs.update({
                            'p_in': varied_inputs.get('p_in', measurement_values['p_in']),
                            'p_out': varied_inputs.get('p_out', measurement_values['p_out']),
                            't_in': varied_inputs.get('t_in', measurement_values['t_in']),
                            'flow': varied_inputs.get('flow', measurement_values['flow']),
                            'use_consistency_iteration': False,
                        })
                        recalculated = self.calculate_design_performance(perturbed_inputs)
                        return recalculated.get('actual_poly_efficiency', 0.0)

                    unc = self.uncertainty_analyzer.analyze_uncertainty(
                        measurement_values,
                        {'p_in': 'pressure_transducer_high', 'p_out': 'pressure_transducer_high',
                         't_in': 'temperature_rtd_pt100',    'flow': 'flow_orifice'},
                        _recalculate_efficiency,
                        'polytropic_efficiency'
                    )
                    results['uncertainty'] = build_uncertainty_payload(
                        unc,
                        results['actual_poly_efficiency'],
                    )
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
        return self.method_suite.method_average_properties(
            p_in, t_in, p_out, poly_eff, gas_obj, eos, max_iter=max_iter, tolerance=tolerance
        )

    def _method_endpoint(self, p_in, t_in, p_out, poly_eff, gas_obj, eos, max_iter=100, tolerance=0.01):
        return self.method_suite.method_endpoint(
            p_in, t_in, p_out, poly_eff, gas_obj, eos, max_iter=max_iter, tolerance=tolerance
        )

    def _method_incremental_pressure(self, p_in, t_in, p_out, poly_eff, gas_obj, eos, step_count=10):
        return self.method_suite.method_incremental_pressure(
            p_in, t_in, p_out, poly_eff, gas_obj, eos, step_count=step_count
        )

    def _method_direct_hs(self, p_in, t_in, p_out, poly_eff, gas_obj, eos):
        return self.method_suite.method_direct_hs(p_in, t_in, p_out, poly_eff, gas_obj, eos)

    def _find_isentropic_temperature(self, p_in, t_in, p_out, S_target, gas_obj, eos, state_in):
        return self.method_suite.find_isentropic_temperature(p_in, t_in, p_out, S_target, gas_obj, eos, state_in)

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

            η_calculated = results.get('actual_poly_efficiency', 0.0) * 100.0
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

             # Design / reference values
             expected_poly_eff = self._normalize_efficiency_reference(
                 inputs.get('design_poly_eff', inputs.get('expected_poly_eff', actual_poly_eff)),
                 actual_poly_eff
             )
             expected_power = self._safe_float(
                 inputs.get('design_power_kw', inputs.get('expected_power', shaft_power_kw)),
                 shaft_power_kw
             )

             fuel_flow_kgh = self._safe_float(inputs.get('fuel_flow', inputs.get('fuel_cons_kg_h', 0.0)), 0.0)
             fuel_gas_comp = inputs.get('fuel_gas_comp', inputs.get('gas_comp', {}))
             lhv_kj_kg, _ = self._calculate_heating_values(
                 fuel_gas_comp,
                 source=inputs.get('lhv_source', 'kasp')
             )
             if lhv_kj_kg <= 0:
                 lhv_kj_kg = self._safe_float(inputs.get('lhv', 0.0), 0.0)

             fuel_kw = (fuel_flow_kgh * lhv_kj_kg) / 3600.0 if fuel_flow_kgh > 0 and lhv_kj_kg > 0 else 0.0
             actual_heat_rate = (fuel_kw * 3600.0) / shaft_power_kw if shaft_power_kw > 0 and fuel_kw > 0 else 0.0
             actual_therm_eff = shaft_power_kw / fuel_kw if fuel_kw > 0 else 0.0
             ambient_pressure_kpa = self._safe_float(
                 inputs.get(
                     'ambient_pressure_kpa',
                     inputs.get(
                         'ambient_pressure',
                         inputs.get('ambient_press', inputs.get('ambient_pressure_pa', self.STD_PRESS_PA) / 1000.0)
                     )
                 ),
                 self.STD_PRESS_PA / 1000.0
             )
             ambient_temp_c = self._safe_float(inputs.get('ambient_temp', t_in_k - 273.15), t_in_k - 273.15)
             humidity_pct = self._safe_float(inputs.get('humidity', 60.0), 60.0)
             altitude_m = self._safe_float(inputs.get('altitude', 0.0), 0.0)

             expected_heat_rate = self._safe_float(
                 inputs.get('design_heat_rate', inputs.get('expected_heat_rate', actual_heat_rate)),
                 actual_heat_rate
             )
             expected_therm_eff = self._normalize_efficiency_reference(
                 inputs.get('design_therm_eff', inputs.get('expected_therm_eff', actual_therm_eff)),
                 actual_therm_eff
             )

             dev_poly = self._percent_deviation(actual_poly_eff, expected_poly_eff)
             dev_power = self._percent_deviation(shaft_power_kw, expected_power)
             dev_heat_rate = self._percent_deviation(actual_heat_rate, expected_heat_rate)
             dev_therm_eff = self._percent_deviation(actual_therm_eff, expected_therm_eff)
             
             status_obj = self._evaluate_performance_status({
                 'deviation_poly_eff': dev_poly, 'deviation_therm_eff': dev_therm_eff,
                 'deviation_power': dev_power, 'deviation_heat_rate': dev_heat_rate
             })
             
             return {
                 'actual_poly_eff': min(max(actual_poly_eff, 0), 1),
                 'design_poly_eff': expected_poly_eff,
                 'expected_poly_eff': expected_poly_eff,
                 'deviation_poly_eff': dev_poly,
                 'actual_isentropic_eff': actual_isen_eff,
                 'poly_head_kj_kg': true_poly_head_kj_kg,
                 'actual_power': shaft_power_kw,
                 'expected_power': expected_power,
                 'deviation_power': dev_power,
                 'actual_heat_rate': actual_heat_rate,
                 'expected_heat_rate': expected_heat_rate,
                 'deviation_heat_rate': dev_heat_rate,
                 'performance_status': status_obj,
                 'actual_therm_eff': actual_therm_eff,
                 'expected_therm_eff': expected_therm_eff,
                 'deviation_therm_eff': dev_therm_eff,
                 'fuel_flow_kg_h': fuel_flow_kgh,
                 'lhv_kj_kg': lhv_kj_kg,
                 'gas_power_kw': gas_power_kw,
                 'shaft_power_kw': shaft_power_kw,
                 'test_conditions': {
                     'mass_flow': mass_flow_kgs,
                     'fuel_flow': fuel_flow_kgh,
                     'compression_ratio': p_out_pa / p_in_pa if p_in_pa > 0 else 0.0,
                     'head': true_poly_head_kj_kg,
                 },
                 'corrected_values': {
                     'correction_factors': {
                         'temperature': ambient_temp_c,
                         'pressure': ambient_pressure_kpa,
                         'humidity': humidity_pct,
                         'altitude': altitude_m,
                     }
                 }
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
            fuel_kw = 0.0
            
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

            actual_heat_rate = (fuel_kw * 3600.0) / motor_power_kw if motor_power_kw > 0 and fuel_kw > 0 else 0.0
                
            return {
                'poly_eff': poly_eff * 100.0,
                'isen_eff': isen_eff * 100.0,
                'poly_head_kj_kg': poly_head_j_kg / 1000.0,
                'gas_power_kw': gas_power_kw,
                'shaft_power_kw': shaft_power_kw,
                'motor_power_kw': motor_power_kw,
                'turb_eff': turb_eff * 100.0,
                'fuel_cons_kg_h': fuel_cons_kg_h,
                'actual_heat_rate': actual_heat_rate,
                'actual_therm_eff': turb_eff,
                'lhv_kj_kg': lhv_kj_kg
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
             return build_summary_report(
                 inputs,
                 results,
                 selected_units,
                 self.performance_monitor.get_statistics(),
                 calculation_date=datetime.datetime.now().isoformat(),
             )
        except Exception as e:
             self.logger.error(f"Rapor oluşturma hatası: {e}")
             return {}

    def _evaluate_performance_status(self, deviations):
        return evaluate_performance_status(deviations)
