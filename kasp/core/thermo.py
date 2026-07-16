"""
KASP V4.5 Thermo Engine (Facade)
Bu modül eski monolitik (2400+ satırlık) çekirdek sınıfın Facade deseninde
yeniden yazılmış halidir. Arka planda işlemleri şu modüllere devreder:
  - GasMixtureBuilder (mixture.py)
  - ThermodynamicSolver (properties.py)
  - CompressorAerodynamics (aerodynamics.py)
  - TurbineSelector (selection.py)
Arayüz geriye dönük (backward) uyumludur, UI modülleri aynı fonksiyonları aynı argümanlarla çağırır.

TODO(v2.2): Bu sınıf 1086 satırdan ~200 satıra düşürülmeli. Önerilen bölünme:
  - HeatingValueCalculator → kasp/core/heating_value.py
  - PerformanceEvaluationService → kasp/core/performance_eval.py
  - DesignContextBuilder → kasp/core/design_context.py
  - ConsistencyIterator → kasp/core/consistency.py
"""

import math
import logging
import datetime

# Alt Bileşenler (V4.4 Modular Architecture)
from kasp.core.mixture import GasMixtureBuilder
from kasp.core.properties import ThermodynamicSolver
from kasp.core.aerodynamics import CompressorAerodynamics
from kasp.core.selection import TurbineSelector
from kasp.core.performance_corrections import apply_site_corrections
from kasp.core.thermo_design_orchestration import ThermoDesignOrchestrator
from kasp.core.thermo_design_support import (
    apply_fallback_tracking,
    build_design_results_payload,
    build_uncertainty_measurements,
    build_uncertainty_payload,
    compute_stage_pressure_ratio,
    select_design_method_key,
)
from kasp.core.thermo_methods import ThermoMethodSuite
from kasp.core.thermo_support import (
    convert_flow_to_kgs as convert_flow_to_kgs_helper,
    convert_pressure_to_pa as convert_pressure_to_pa_helper,
    convert_result_value as convert_result_value_helper,
    convert_temperature_to_k as convert_temperature_to_k_helper,
)

# Eski yardımcılar ve Sabitler
from kasp.core.exceptions import AdvancedThermodynamicError, InputValidationError
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
        elif eos_method in ['pr', 'srk', 'aga8', 'thermopack', 'ccp', 'dwsim']:
            return GasMixtureBuilder.build_thermo_data(comp_frac)
        else:
            raise ValueError(f"Bilinmeyen EOS metodu: {eos_method}")

    def _get_thermo_properties(self, p_pa, t_k, gas_obj, eos_method):
        """Legacy dictionary bekleyen eski kod kısımları için köprü (Bridge)."""
        state = self.thermo_solver.get_properties(p_pa, t_k, gas_obj, eos_method)
        speed_of_sound = state.raw_props.get('speed_of_sound')
        if speed_of_sound is None:
            try:
                speed_of_sound = math.sqrt(max(state.k * p_pa / state.density, 0.0))
            except Exception:
                speed_of_sound = None
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
            'a': speed_of_sound if speed_of_sound is not None else 0.0,
            'phase': state.phase,
        }

    # -------------------------------------------------------------------------
    # 2. BİRİM DÖNÜŞÜM METOTLARI
    # -------------------------------------------------------------------------
    def convert_pressure_to_pa(self, value, unit, ambient_pressure_pa=None):
        return convert_pressure_to_pa_helper(value, unit, ambient_pressure_pa)

    def convert_temperature_to_k(self, value, unit):
        return convert_temperature_to_k_helper(value, unit)

    def convert_flow_to_kgs(self, value, unit, gas_obj, eos_method):
        return convert_flow_to_kgs_helper(
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

    def convert_result_value(
        self,
        value: float,
        from_unit: str,
        to_unit: str,
        quantity_type: str,
        gas_obj=None,
        eos_method=None,
        lhv_kj_kg=None,
    ) -> float:
        return convert_result_value_helper(
            value,
            from_unit,
            to_unit,
            quantity_type,
            gas_obj,
            eos_method,
            lhv_kj_kg,
            thermo_solver=self.thermo_solver,
            logger=self.logger,
            std_press_pa=self.STD_PRESS_PA,
            standard_temp_k=self.STANDARD_TEMP_K,
            normal_temp_k=self.NORMAL_TEMP_K,
        )

    def _calculate_heating_values(self, composition, source='kasp', gas_obj=None, eos_method=None):
        from kasp.core.heating_value import calculate as calc_heating
        return calc_heating(
            composition,
            source,
            thermo_solver=self.thermo_solver,
            gas_obj=gas_obj,
            eos_method=eos_method,
        )

    # -------------------------------------------------------------------------
    # 4. ANA TASARIM HESAPLAMA ÇEKİRDEĞİ (Design Performance)
    # -------------------------------------------------------------------------

    @staticmethod
    def _validate_design_inputs(inputs):
        required = {
            'p_in': 'Giris basinci',
            'p_out': 'Cikis basinci',
            't_in': 'Giris sicakligi',
            'flow': 'Debi',
            'gas_comp': 'Gaz bilesimi',
            'poly_eff': 'Politropik verim',
        }
        missing = [v for k, v in required.items() if k not in inputs]
        if missing:
            raise InputValidationError(f"Eksik alanlar: {', '.join(missing)}")
        if not isinstance(inputs.get('gas_comp', {}), dict) or not inputs['gas_comp']:
            raise InputValidationError("Gaz bilesimi bos veya gecersiz.")
        if inputs.get('p_out', 0) <= inputs.get('p_in', 0):
            raise InputValidationError("Cikis basinci giris basincindan buyuk olmali.")
        poly_eff = inputs.get('poly_eff', 0)
        if not (0 < poly_eff <= 100):
            raise InputValidationError(f"Politropik verim 0-100 arasinda olmali: {poly_eff}")

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
        self._validate_design_inputs(inputs)

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
        from kasp.core.aerodynamics import reset_fallback_comparisons, set_current_stage, get_fallback_comparisons
        reset_fallback_comparisons()
        set_current_stage("Performans")
        solver_method = inputs.get("solver_method", "auto")
        self.thermo_solver.begin_run_tracking(solver_method)
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
            lhv_kj_kg, hhv_kj_kg = self._calculate_heating_values(
                inputs['gas_comp'], 
                source=inputs.get('lhv_source', 'kasp'),
                gas_obj=gas_obj,
                eos_method=eos
            )
            if lhv_kj_kg <= 0:
                lhv_kj_kg = EngineSettings.FALLBACK_LHV_KJ_KG
                
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

            actual_heat_rate = (
                fuel_cons_kg_h * lhv_kj_kg / max(shaft_power_kw, 1e-9)
                if fuel_cons_kg_h > 0
                else 0.0
            )
            corrected = apply_site_corrections(
                shaft_power_kw,
                actual_heat_rate,
                inputs.get("site_correction_inputs", {}),
            )

            results = {
                'poly_eff': poly_eff * 100.0,
                'isen_eff': isen_eff * 100.0,
                'poly_head_kj_kg': poly_head_j_kg / 1000.0,
                'gas_power_kw': gas_power_kw,
                'shaft_power_kw': shaft_power_kw,
                'motor_power_kw': motor_power_kw,
                'turb_eff': turb_eff * 100.0,
                'fuel_cons_kg_h': fuel_cons_kg_h,
                'actual_heat_rate': actual_heat_rate,
                'corrected_power_kw': corrected["corrected_power_kw"],
                'corrected_heat_rate': corrected["corrected_heat_rate_kj_kwh"],
                'correction_factors': corrected["correction_factors"],
            }
            results["fallback_comparison"] = get_fallback_comparisons()
            return results
        except Exception as e:
            self.logger.error(f"Performans değerlendirme hatası: {e}")
            raise
        finally:
            self.thermo_solver.end_run_tracking()

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
    def select_units(self, required_power_kw, site_conditions, all_turbines_data, limit=5,
                     surge_min=None, stonewall_min=None):
        """TurbineSelector modülüne delegasyon yapar."""
        return TurbineSelector.select_units(
            required_power_kw, site_conditions, all_turbines_data, limit,
            surge_min=surge_min, stonewall_min=stonewall_min,
        )

    def select_all_by_power(self, required_power_kw, site_conditions, all_turbines_data):
        """Güç gereksinimini karşılayan tüm türbinleri güce göre sıralar."""
        return TurbineSelector.select_all_by_power(
            required_power_kw, site_conditions, all_turbines_data,
        )

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

    def _method_average_properties(self, p_in, t_in, p_out, poly_eff, gas_obj, eos, max_iter=100, tolerance=0.01):
        return self.method_suite.method_average_properties(
            p_in,
            t_in,
            p_out,
            poly_eff,
            gas_obj,
            eos,
            max_iter=max_iter,
            tolerance=tolerance,
        )

    def _method_endpoint(self, p_in, t_in, p_out, poly_eff, gas_obj, eos, max_iter=100, tolerance=0.01):
        return self.method_suite.method_endpoint(
            p_in,
            t_in,
            p_out,
            poly_eff,
            gas_obj,
            eos,
            max_iter=max_iter,
            tolerance=tolerance,
        )

    def _method_incremental_pressure(self, p_in, t_in, p_out, poly_eff, gas_obj, eos, step_count=10):
        return self.method_suite.method_incremental_pressure(
            p_in,
            t_in,
            p_out,
            poly_eff,
            gas_obj,
            eos,
            step_count=step_count,
        )

    def _method_direct_hs(self, p_in, t_in, p_out, poly_eff, gas_obj, eos):
        return self.method_suite.method_direct_hs(
            p_in,
            t_in,
            p_out,
            poly_eff,
            gas_obj,
            eos,
        )

    def _find_isentropic_temperature(self, p_in, t_in, p_out, S_target, gas_obj, eos, state_in):
        return self.method_suite.find_isentropic_temperature(
            p_in,
            t_in,
            p_out,
            S_target,
            gas_obj,
            eos,
            state_in,
        )

    def _prepare_design_context(self, inputs):
        ambient_pressure_pa = inputs.get("ambient_pressure_pa", self.STD_PRESS_PA)
        p_in_pa = self.convert_pressure_to_pa(float(inputs["p_in"]), inputs["p_in_unit"], ambient_pressure_pa)
        t_in_k = self.convert_temperature_to_k(float(inputs["t_in"]), inputs["t_in_unit"])
        p_out_pa = self.convert_pressure_to_pa(float(inputs["p_out"]), inputs["p_out_unit"], ambient_pressure_pa)

        if p_out_pa <= p_in_pa:
            raise ValueError(f"Cikis basinci ({p_out_pa/1e5:.2f} bar) giristen kucuk/esit olamaz.")

        eos = inputs["eos_method"]
        gas_obj = self._create_gas_object(inputs["gas_comp"], eos)
        total_mass_flow_kgs = self.convert_flow_to_kgs(
            float(inputs["flow"]),
            inputs["flow_unit"],
            gas_obj,
            eos,
        )

        # Akilli EOS fallback zinciri olustur
        from kasp.core.fallback import EosChain
        eos_chain = EosChain(
            self.thermo_solver._fallback_tracker,
            self.thermo_solver,
            raw_composition=inputs.get("gas_comp", {}),
        )

        num_units = max(1, int(inputs.get("num_units", 1)))
        mass_flow_per_unit = total_mass_flow_kgs / num_units
        method = inputs.get("method", "Metot 1: Ortalama Ozellikler")
        method_key = select_design_method_key(method)
        num_stages = max(1, int(inputs.get("num_stages", 1)))
        poly_eff_tgt = max(0.01, min(0.99, float(inputs.get("poly_eff", 85.0)) / 100.0))

        intercooler_dp = float(inputs.get("intercooler_dp_pct", 0.0)) / 100.0
        ic_t_raw = float(inputs.get("intercooler_t", 40.0))
        ic_t_k = ic_t_raw + 273.15 if ic_t_raw < 200 else ic_t_raw
        pressure_ratio_total = p_out_pa / p_in_pa

        requested_max_iter = int(inputs.get("method_max_iter", 100))
        max_iter = self._limit_design_method_iterations(inputs, eos, requested_max_iter)

        return {
            "p_in_pa": p_in_pa,
            "t_in_k": t_in_k,
            "p_out_pa": p_out_pa,
            "eos": eos,
            "gas_obj": gas_obj,
            "eos_chain": eos_chain,
            "total_mass_flow_kgs": total_mass_flow_kgs,
            "num_units": num_units,
            "mass_flow_per_unit": mass_flow_per_unit,
            "method": method,
            "method_key": method_key,
            "num_stages": num_stages,
            "poly_eff_tgt": poly_eff_tgt,
            "intercooler_dp": intercooler_dp,
            "ic_t_k": ic_t_k,
            "pressure_ratio_total": pressure_ratio_total,
            "stage_pr": compute_stage_pressure_ratio(
                pressure_ratio_total,
                intercooler_dp,
                num_stages,
            ),
            "max_iter": max_iter,
            "tolerance": float(inputs.get("method_tolerance", 0.01)),
            "step_count": max(2, int(inputs.get("incremental_steps", 10))),
        }

    def _limit_design_method_iterations(self, inputs, eos, requested_max_iter):
        if eos != "coolprop":
            return requested_max_iter

        if inputs.get("bypass_complex_cap", False):
            return requested_max_iter

        gas_comp = inputs.get("gas_comp") or {}
        active_components = sum(1 for value in gas_comp.values() if float(value or 0.0) > 1e-9)
        if active_components < 8:
            return requested_max_iter

        try:
            from kasp.config_manager import get_config_manager
            config = get_config_manager()
            max_complex_iter = int(config.get("coolprop.max_complex_iter", 3))
        except Exception:
            max_complex_iter = 3

        capped_iter = min(requested_max_iter, max_complex_iter)
        if capped_iter < requested_max_iter:
            self.logger.warning(
                "Kompleks CoolProp karisimi icin metot iterasyonu %s -> %s ile sinirlandi.",
                requested_max_iter,
                capped_iter,
            )
        return capped_iter

    def _add_fuel_standard_density(self, results, fuel_composition, eos):
        try:
            fuel_gas_obj = self._create_gas_object(fuel_composition, eos)
            fuel_state_std = self.thermo_solver.get_properties(
                self.STD_PRESS_PA,
                self.STANDARD_TEMP_K,
                fuel_gas_obj,
                eos,
            )
            results["fuel_gas_density_std"] = fuel_state_std.density
        except Exception as error:
            self.logger.debug(f"Fuel standard density hesaplanamadi: {error}")
            results["fuel_gas_density_std"] = None

    def _add_uncertainty_result(self, results, inputs, p_in_pa, p_out_pa, t_in_k, mass_flow_per_unit):
        if not self.uncertainty_analyzer or not inputs.get("enable_uncertainty", True):
            results["uncertainty"] = None
            return

        def recalc_poly_eff(perturbed_measurements):
            """Pertürbe edilmiş ölçümlerle tasarım hesaplamasını yeniden çalıştırır."""
            modified_inputs = dict(inputs)
            modified_inputs.update({
                "p_in": float(perturbed_measurements["p_in"]),
                "p_in_unit": "bara",
                "p_out": float(perturbed_measurements["p_out"]),
                "p_out_unit": "bara",
                "t_in": float(perturbed_measurements["t_in"]),
                "t_in_unit": "K",
                "flow": float(perturbed_measurements["flow"]),
                "flow_unit": "kg/s",
                "enable_uncertainty": False,
            })
            try:
                recalc_result = self.calculate_design_performance(modified_inputs)
                return recalc_result.get("actual_poly_efficiency", 0.0)
            except Exception:
                return results["actual_poly_efficiency"]

        try:
            uncertainty_result = self.uncertainty_analyzer.analyze_uncertainty(
                build_uncertainty_measurements(
                    {
                        "p_in": p_in_pa / 1e5,
                        "p_out": p_out_pa / 1e5,
                        "t_in": t_in_k,
                        "flow": mass_flow_per_unit,
                    }
                ),
                {
                    "p_in": "pressure_transducer_high",
                    "p_out": "pressure_transducer_high",
                    "t_in": "temperature_rtd_pt100",
                    "flow": "flow_orifice",
                },
                recalc_poly_eff,
                "polytropic_efficiency",
            )
            results["uncertainty"] = build_uncertainty_payload(
                uncertainty_result,
                results["actual_poly_efficiency"],
            )
        except Exception as error:
            self.logger.warning(f"Belirsizlik modulu basarisiz: {error}")
            results["uncertainty"] = None

    def _calculate_design_energy_context(self, inputs, context, stage_loop):
        final_t_out_k = stage_loop["final_t_out_k"]
        total_stage_gas_power_kw = stage_loop["total_stage_gas_power_kw"]
        total_poly_head_kj_kg = stage_loop["total_poly_head_kj_kg"]
        staged_results = stage_loop["staged_results"]

        state_inlet = self.thermo_solver.get_properties(
            context["p_in_pa"],
            context["t_in_k"],
            context["gas_obj"],
            context["eos"],
        )
        inlet_acmh = (
            (context["mass_flow_per_unit"] / state_inlet.density) * 3600.0
            if state_inlet.density > 0
            else 0.0
        )

        mech_loss_kw = CompressorAerodynamics.calculate_mechanical_loss(
            inlet_acmh / 3600.0,
            total_stage_gas_power_kw,
        )
        total_shaft_kw = total_stage_gas_power_kw + mech_loss_kw

        mech_eff_raw = float(inputs.get("mech_eff", 98.0))
        mech_eff = mech_eff_raw / 100.0 if mech_eff_raw > 1.0 else mech_eff_raw
        if mech_eff <= 0:
            raise ValueError("Mekanik verim sifir veya negatif olamaz.")

        motor_kw = total_shaft_kw / mech_eff
        unit_kw = motor_kw * 1.04

        fuel_composition = inputs.get("fuel_gas_comp", inputs["gas_comp"])
        fuel_gas_obj = self._create_gas_object(fuel_composition, context.get("eos", "pr"))
        lhv, hhv = self._calculate_heating_values(
            fuel_composition,
            source=inputs.get("lhv_source", "kasp"),
            gas_obj=fuel_gas_obj,
            eos_method=context.get("eos", "pr")
        )
        therm_raw = inputs.get("therm_eff", 0.35)
        therm_eff = therm_raw / 100.0 if therm_raw > 1.0 else therm_raw

        fuel_kw = motor_kw / therm_eff if therm_eff > 0 else 0.0
        heat_rate = (fuel_kw * 3600.0) / motor_kw if motor_kw > 0 else 0.0
        fuel_kgh = (fuel_kw * 3600.0) / lhv if lhv > 0 else 0.0

        return {
            "final_t_out_k": final_t_out_k,
            "total_stage_gas_power_kw": total_stage_gas_power_kw,
            "total_poly_head_kj_kg": total_poly_head_kj_kg,
            "staged_results": staged_results,
            "inlet_acmh": inlet_acmh,
            "mech_loss_kw": mech_loss_kw,
            "total_shaft_kw": total_shaft_kw,
            "motor_kw": motor_kw,
            "unit_kw": unit_kw,
            "fuel_composition": fuel_composition,
            "fuel_kgh": fuel_kgh,
            "heat_rate": heat_rate,
            "lhv": lhv,
            "hhv": hhv,
            "inlet_properties": self._get_thermo_properties(
                context["p_in_pa"],
                context["t_in_k"],
                context["gas_obj"],
                context["eos"],
            ),
            "outlet_properties": self._get_thermo_properties(
                context["p_out_pa"],
                final_t_out_k,
                context["gas_obj"],
                context["eos"],
            ),
        }

    def calculate_design_performance(self, inputs):
        start_time = datetime.datetime.now()
        from kasp.core.aerodynamics import reset_fallback_comparisons, get_fallback_comparisons
        reset_fallback_comparisons()
        try:
            fallback_tracking = None
            solver_method = inputs.get("solver_method", "auto")
            self.thermo_solver.begin_run_tracking(solver_method)
            try:
                context = self._prepare_design_context(inputs)

                self.logger.info(
                    f"Hesaplama basliyor | Metot: {context['method']} | "
                    f"PR={context['pressure_ratio_total']:.2f} | "
                    f"Kademe={context['num_stages']} | EOS={context['eos']}"
                )

                stage_loop = self.design_orchestrator.run_stage_loop(
                    p_in_pa=context["p_in_pa"],
                    t_in_k=context["t_in_k"],
                    p_out_pa=context["p_out_pa"],
                    stage_pr=context["stage_pr"],
                    num_stages=context["num_stages"],
                    intercooler_dp=context["intercooler_dp"],
                    ic_t_k=context["ic_t_k"],
                    method_key=context["method_key"],
                    poly_eff_tgt=context["poly_eff_tgt"],
                    gas_obj=context["gas_obj"],
                    eos=context["eos"],
                    max_iter=context["max_iter"],
                    tolerance=context["tolerance"],
                    step_count=context["step_count"],
                    mass_flow_per_unit=context["mass_flow_per_unit"],
                    eos_chain=context.get("eos_chain"),
                    method_average_fn=self.method_suite.method_average_properties,
                    method_endpoint_fn=self.method_suite.method_endpoint,
                    method_incremental_fn=self.method_suite.method_incremental_pressure,
                    method_direct_hs_fn=self.method_suite.method_direct_hs,
                )

                # run_stage_loop temizledigi _active_eos_chain'i post-processing icin tekrar aktiflestir
                eos_chain = context.get("eos_chain")
                if eos_chain is not None:
                    self.thermo_solver._active_eos_chain = eos_chain

                try:
                    energy = self._calculate_design_energy_context(inputs, context, stage_loop)
                    staged_results = energy["staged_results"]

                    results = build_design_results_payload(
                        p_in_pa=context["p_in_pa"],
                        t_in_k=context["t_in_k"],
                        p_out_pa=context["p_out_pa"],
                        final_t_out_k=energy["final_t_out_k"],
                        total_poly_head_kj_kg=energy["total_poly_head_kj_kg"],
                        poly_eff_tgt=context["poly_eff_tgt"],
                        total_stage_gas_power_kw=energy["total_stage_gas_power_kw"],
                        total_shaft_kw=energy["total_shaft_kw"],
                        motor_kw=energy["motor_kw"],
                        unit_kw=energy["unit_kw"],
                        mech_loss_kw=energy["mech_loss_kw"],
                        fuel_kgh=energy["fuel_kgh"],
                        mass_flow_per_unit=context["mass_flow_per_unit"],
                        inlet_acmh=energy["inlet_acmh"],
                        num_units=context["num_units"],
                        total_mass_flow_kgs=context["total_mass_flow_kgs"],
                        heat_rate=energy["heat_rate"],
                        lhv=energy["lhv"],
                        hhv=energy["hhv"],
                        inlet_properties=energy["inlet_properties"],
                        outlet_properties=energy["outlet_properties"],
                        num_stages=context["num_stages"],
                        staged_results=staged_results,
                        method=context["method"],
                    )

                    self._add_fuel_standard_density(results, energy["fuel_composition"], context["eos"])
                    self._add_uncertainty_result(
                        results,
                        inputs,
                        context["p_in_pa"],
                        context["p_out_pa"],
                        context["t_in_k"],
                        context["mass_flow_per_unit"],
                    )
                finally:
                    if eos_chain is not None:
                        self.thermo_solver._active_eos_chain = None
            finally:
                fallback_tracking = self.thermo_solver.end_run_tracking()

            apply_fallback_tracking(
                results,
                fallback_tracking,
                staged_results,
                energy["inlet_properties"],
                energy["outlet_properties"],
            )

            self.performance_monitor.log_performance(
                "design_performance",
                (datetime.datetime.now() - start_time).total_seconds(),
            )
            results["fallback_comparison"] = get_fallback_comparisons()
            if eos_chain is not None and getattr(eos_chain, "_locked_eos", None):
                results["_effective_eos"] = eos_chain._locked_eos
            return results

        except Exception as error:
            self.logger.error(f"Design performance error: {error}", exc_info=True)
            raise AdvancedThermodynamicError(f"Hesaplama hatasi (V4.5): {error}")

    def _calculate_with_consistency(self, inputs):
        start_time = datetime.datetime.now()

        eta_target = float(inputs.get("poly_eff", 85.0))
        eta_min = max(50.0, float(inputs.get("consistency_eta_min", 60.0)))
        eta_max = min(99.0, float(inputs.get("consistency_eta_max", 95.0)))
        eta_current = min(max(eta_target, eta_min), eta_max)
        relaxation = max(0.1, min(0.7, float(inputs.get("consistency_relaxation", 0.35))))
        tolerance = float(inputs.get("consistency_tolerance", 0.1))
        max_iter = int(inputs.get("max_consistency_iter", EngineSettings.MAX_CONSISTENCY_ITERATIONS))

        self.logger.info(
            f"Tutarlilik modu | Hedef eta={eta_target:.2f}% | "
            f"Aralik=({eta_min:.1f}, {eta_max:.1f}) | Tol={tolerance}% | Maks. iter={max_iter}"
        )

        history = []
        converged = False
        residual = 0.0
        results = {}
        bounded = False

        for iteration in range(max_iter):
            inputs_temp = dict(inputs)
            inputs_temp["poly_eff"] = eta_current

            try:
                results = self.calculate_design_performance(inputs_temp)
            except Exception as error:
                self.logger.error(f"Tutarlilik iter {iteration + 1} hatasi: {error}")
                break

            eta_calculated = results["actual_poly_efficiency"] * 100.0
            residual = abs(eta_calculated - eta_current)

            history.append(
                {
                    "iteration": iteration + 1,
                    "eta_used": eta_current,
                    "eta_calculated": eta_calculated,
                    "residual": residual,
                    "t_out": results.get("t_out", 0),
                    "power_kw": results.get("power_unit_kw", 0),
                }
            )

            self.logger.debug(
                f"  Iter {iteration + 1}: eta_used={eta_current:.3f}% -> "
                f"eta_calc={eta_calculated:.3f}% | residual={residual:.4f}%"
            )

            if residual < tolerance:
                converged = True
                break

            eta_new = relaxation * eta_calculated + (1.0 - relaxation) * eta_current
            eta_bounded = min(eta_max, max(eta_min, eta_new))

            if abs(eta_bounded - eta_new) > 1e-9 and abs(eta_bounded - eta_current) < 1e-9:
                bounded = True
                warning_text = (
                    f"Tutarlilik iterasyonu fiziksel verim sinirina dayandi ({eta_bounded:.1f}%). "
                    "Son gecerli cozum korundu."
                )
                self.logger.warning(warning_text)
                results.setdefault("warnings", []).append(warning_text)
                break

            eta_current = eta_bounded

        if not converged and not bounded:
            self.logger.warning(
                f"Tutarlilik maks. iter ({max_iter}) asildi. Son residual={residual:.4f}% (tol={tolerance}%)"
            )

        results["consistency_mode"] = True
        results["poly_eff_target"] = eta_target
        results["poly_eff_converged"] = eta_current
        results["consistency_iterations"] = len(history)
        results["consistency_history"] = history
        results["consistency_converged"] = converged
        results["final_residual"] = residual

        elapsed = (datetime.datetime.now() - start_time).total_seconds()
        self.logger.info(f"Tutarlilik hesabi tamamlandi: {elapsed:.1f}s, {len(history)} iter")
        return results
