"""
KASP V4.4 Thermodynamic Properties Solver
Bu modül saf formüller ve kütüphaneleri (CoolProp, Thermo) kullanarak Entalpi, 
Entropi, Cp, Cv, k, Z gibi özellikleri çözümleyen ve LRU tabanlı cache
mekanizmasını işleten ThermodynamicSolver sınıfını içerir.
"""

import math
import logging
import threading
from collections import OrderedDict

# V4.4 Data Models
from kasp.core.models import ThermodynamicState

# Sabitler (GasMixtureBuilder veya API 617)
from kasp.core.constants import (
    MOLAR_MASSES, R_UNIVERSAL_J_MOL_K, STD_PRESS_PA, normalize_component
)

# Kütüphane Yüklemeleri (Lazy/Optional Imports)
try:
    import CoolProp.CoolProp as CP
    COOLPROP_LOADED = True
except ImportError:
    COOLPROP_LOADED = False

try:
    from thermo.eos_mix import PRMIX, SRKMIX
    from thermo import ChemicalConstantsPackage
    THERMO_LOADED = True
except ImportError:
    THERMO_LOADED = False

logger = logging.getLogger(__name__)

class ThermodynamicSolver:
    """Core Thermodynamic calculations with Thread-Safe Caching."""
    
    def __init__(self, max_cache_size=2000):
        self._property_cache = OrderedDict()
        self._max_cache_size = self._coerce_cache_size(max_cache_size)
        self._cache_hits = 0
        self._cache_misses = 0
        self._cache_lock = threading.Lock()
        
        # Cache for thermo packages to avoid expensive instantiation
        self._package_cache = {}
        self._run_tracking = threading.local()

    @staticmethod
    def _coerce_cache_size(value, default=2000):
        try:
            cache_size = int(value)
        except (TypeError, ValueError):
            cache_size = default
        return max(1, cache_size)

    @staticmethod
    def _build_gas_hash(gas_obj):
        if isinstance(gas_obj, str):
            return hash(gas_obj)
        if isinstance(gas_obj, dict):
            ids = gas_obj.get("ids", gas_obj.get("IDs", []))
            fractions = gas_obj.get("mol_fractions", gas_obj.get("zs", []))
            components_tuple = tuple(sorted(zip(ids, fractions)))
            return hash(components_tuple)
        return hash(str(gas_obj))

    def _build_cache_key(self, P_pa: float, T_k: float, gas_obj, eos_method: str):
        return (
            round(P_pa, 1),
            round(T_k, 2),
            self._build_gas_hash(gas_obj),
            eos_method,
        )

    def _get_cached_state(self, cache_key, P_pa: float, T_k: float, eos_method: str):
        with self._cache_lock:
            if cache_key not in self._property_cache:
                return None

            self._cache_hits += 1
            state = self._property_cache.pop(cache_key)
            self._property_cache[cache_key] = state
            self._record_run_tracking(P_pa, T_k, eos_method, state)
            return state

    def _store_cached_state(self, cache_key, state):
        with self._cache_lock:
            if len(self._property_cache) >= self._max_cache_size:
                self._property_cache.popitem(last=False)
            self._property_cache[cache_key] = state

    def _record_cache_miss(self):
        with self._cache_lock:
            self._cache_misses += 1

    @staticmethod
    def _speed_of_sound(k_value, pressure_pa, density):
        if density <= 0:
            return 0.0
        return math.sqrt(max(k_value * pressure_pa / density, 0.0))

    @staticmethod
    def _build_state(
        *,
        P_pa,
        T_k,
        H,
        S,
        Z,
        k,
        MW,
        Cp,
        Cv,
        density,
        phase,
        fallback=False,
        mu=1.1e-5,
        speed_of_sound=None,
    ):
        if speed_of_sound is None:
            speed_of_sound = ThermodynamicSolver._speed_of_sound(k, P_pa, density)
        return ThermodynamicState(
            P=P_pa,
            T=T_k,
            H=H,
            S=S,
            Z=Z,
            k=k,
            MW=MW,
            Cp=Cp,
            Cv=Cv,
            density=density,
            phase=phase,
            raw_props={
                "fallback": bool(fallback),
                "mu": mu,
                "speed_of_sound": speed_of_sound,
            },
        )

    def begin_run_tracking(self):
        self._run_tracking.context = {
            "calls": 0,
            "fallback_calls": 0,
            "fallback_events": OrderedDict(),
        }

    def end_run_tracking(self):
        context = getattr(self._run_tracking, "context", None)
        self._run_tracking.context = None

        if not context:
            return {
                "fallback_used": False,
                "fallback_call_count": 0,
                "fallback_state_count": 0,
                "fallback_states": [],
            }

        return {
            "fallback_used": context["fallback_calls"] > 0,
            "fallback_call_count": context["fallback_calls"],
            "fallback_state_count": len(context["fallback_events"]),
            "fallback_states": list(context["fallback_events"].values()),
        }

    def _record_run_tracking(self, P_pa: float, T_k: float, eos_method: str, state: ThermodynamicState):
        context = getattr(self._run_tracking, "context", None)
        if context is None:
            return

        context["calls"] += 1
        if not state.raw_props.get("fallback", False):
            return

        context["fallback_calls"] += 1
        event_key = (round(P_pa, 1), round(T_k, 2), eos_method, state.phase)
        if event_key in context["fallback_events"] or len(context["fallback_events"]) >= 12:
            return

        context["fallback_events"][event_key] = {
            "pressure_bar_a": P_pa / 1e5,
            "temperature_c": T_k - 273.15,
            "eos_method": eos_method,
            "phase": state.phase,
        }
        
    def get_properties(self, P_pa: float, T_k: float, gas_obj, eos_method: str) -> ThermodynamicState:
        """
        Giriş basınç ve sıcaklığına bağli olarak durumu çözer. Cache mimarisi kullanir.
        gas_obj: Eğer coolprop ise string, thermo ise dict objesidir (mixture.py tarafindan uretilir)
        """
        cache_key = self._build_cache_key(P_pa, T_k, gas_obj, eos_method)

        cached_state = self._get_cached_state(cache_key, P_pa, T_k, eos_method)
        if cached_state is not None:
            return cached_state
                
        self._record_cache_miss()
        
        # 2. Ana Hesaplama Döngüsü
        try:
            if eos_method == 'coolprop':
                state = self._solve_coolprop(P_pa, T_k, gas_obj)
            elif eos_method in ['pr', 'srk']:
                state = self._solve_thermo_eos(P_pa, T_k, gas_obj, eos_method)
            elif eos_method == 'aga8':
                state = self._solve_aga8(P_pa, T_k, gas_obj)
            else:
                raise ValueError(f"Desteklenmeyen EOS: {eos_method}")
                
        except Exception as e:
            logger.warning(f"⚠️ {eos_method.upper()} EOS hatası: {e}. Fallback (PR) kullanılıyor.")
            if eos_method == 'aga8':
                try:
                    state = self._solve_thermo_eos(P_pa, T_k, gas_obj, 'pr')
                    state.raw_props['fallback'] = True
                    state.raw_props['fallback_type'] = 'pr_fallback'
                except Exception as fallback_err:
                    logger.warning(f"⚠️ Fallback PR da başarısız: {fallback_err}. İdeal Gaz'a geçiliyor.")
                    state = self._solve_fallback(P_pa, T_k, gas_obj, eos_method)
            else:
                state = self._solve_fallback(P_pa, T_k, gas_obj, eos_method)
            
        # Z-Factor Uyarısı
        if state.Z < 0.5 or state.Z > 1.5:
             logger.warning(f"⚠️ Olağandışı Z faktörü: {state.Z:.4f} (P={P_pa/1e5:.1f} bar, T={T_k-273.15:.1f}°C)")
             
        self._store_cached_state(cache_key, state)
        self._record_run_tracking(P_pa, T_k, eos_method, state)
            
        return state

    def infer_mw_g_mol(self, gas_obj) -> float | None:
        if isinstance(gas_obj, dict):
            mw = gas_obj.get("MW")
            if mw is not None:
                try:
                    return float(mw)
                except (TypeError, ValueError):
                    pass

            ids = gas_obj.get("ids", gas_obj.get("IDs", []))
            zs = gas_obj.get("mol_fractions", gas_obj.get("zs", []))
            if ids and zs and len(ids) == len(zs):
                try:
                    from kasp.core.mixture import GasMixtureBuilder

                    reverse_map = {
                        thermo_id.lower(): component
                        for component, thermo_id in GasMixtureBuilder.THERMO_ID_MAP.items()
                    }
                    return sum(
                        float(fraction)
                        * MOLAR_MASSES[reverse_map.get(str(component_id).lower(), normalize_component(str(component_id)))]
                        for component_id, fraction in zip(ids, zs)
                    )
                except Exception:
                    return None

        return None

    @staticmethod
    def _extract_thermo_components(gas_data: dict):
        zs = gas_data.get('zs', gas_data.get('mol_fractions', []))
        ids = gas_data.get('ids', gas_data.get('IDs', []))
        if not ids or not zs or len(ids) != len(zs):
            raise ValueError("Thermo EOS icin ids/zs veya ids/mol_fractions eksik ya da uyumsuz.")
        return ids, zs

    def _get_thermo_package(self, ids):
        pkg_key = tuple(ids)
        if pkg_key not in self._package_cache:
            constants, properties = ChemicalConstantsPackage.from_IDs(ids)
            self._package_cache[pkg_key] = (constants, properties)
        return self._package_cache[pkg_key]

    def _solve_coolprop(self, P_pa: float, T_k: float, mixture_string: str) -> ThermodynamicState:
        """CoolProp HEOS motorunu kullanarak özellikleri çözer."""
        if not COOLPROP_LOADED:
            raise ImportError("CoolProp kütüphanesi aktif değil.")
            
        H = CP.PropsSI('Hmass', 'P', P_pa, 'T', T_k, mixture_string)
        S = CP.PropsSI('Smass', 'P', P_pa, 'T', T_k, mixture_string)
        Z = CP.PropsSI('Z', 'P', P_pa, 'T', T_k, mixture_string)
        D = CP.PropsSI('Dmass', 'P', P_pa, 'T', T_k, mixture_string)
        a = CP.PropsSI('A', 'P', P_pa, 'T', T_k, mixture_string)
        Cp = CP.PropsSI('Cpmass', 'P', P_pa, 'T', T_k, mixture_string)
        Cv = CP.PropsSI('Cvmass', 'P', P_pa, 'T', T_k, mixture_string)
        k = Cp / Cv if Cv != 0 else 1.667
        MW_kg_mol = CP.PropsSI('M', mixture_string) 
        
        # Phase bilgisi (CoolProp PhaseSI kütüphane fonksiyonu ile)
        try:
            phase_str = CP.PhaseSI('P', P_pa, 'T', T_k, mixture_string)
        except Exception:
            phase_str = 'gas'
            if Z < 0.2: phase_str = 'liquid'
        
        return self._build_state(
            P_pa=P_pa,
            T_k=T_k,
            H=H,
            S=S,
            Z=Z,
            k=k,
            MW=MW_kg_mol * 1000.0,
            Cp=Cp,
            Cv=Cv,
            density=D,
            phase=phase_str,
            fallback=False,
            mu=CP.PropsSI('V', 'P', P_pa, 'T', T_k, mixture_string),
            speed_of_sound=a,
        )
        
    def _solve_thermo_eos(self, P_pa: float, T_k: float, gas_data: dict, eos_method: str) -> ThermodynamicState:
        """Thermo PR/SRK modülünü kullanarak özellikleri çözer."""
        if not THERMO_LOADED:
             raise ImportError("Thermo kütüphanesi aktif değil.")
             
        ids, zs = self._extract_thermo_components(gas_data)
        constants, properties = self._get_thermo_package(ids)
        
        MW_g_mol = sum(zs[i] * constants.MWs[i] for i in range(len(zs)))
        molar_mass = MW_g_mol / 1000.0  # kg/mol
        
        EOS_CLASS = PRMIX if eos_method == 'pr' else SRKMIX
        eos = EOS_CLASS(
            T=T_k, P=P_pa,
            Tcs=constants.Tcs, Pcs=constants.Pcs,
            omegas=constants.omegas, zs=zs
        )
        
        # Z Factor Fallback and V_m
        phase_str = 'gas'
        Z_g_raw = getattr(eos, 'Z_g', None)
        Z_l_raw = getattr(eos, 'Z_l', None)
        
        if Z_g_raw is not None and Z_g_raw > 0:
            Z = Z_g_raw
            V_m = eos.V_g  
        elif Z_l_raw is not None and Z_l_raw > 0:
            Z = Z_l_raw
            V_m = eos.V_l
            phase_str = 'liquid'
        else:
            Z = 1.0
            V_m = 8.314462 * T_k / P_pa
            phase_str = 'ideal'
            
        D = molar_mass / V_m  # kg/m³
        
        # Heat Capacities (Ideal + Departure)
        Cp_ig_molar = sum(
            zs[i] * properties.HeatCapacityGases[i](T_k) for i in range(len(zs))
        )
        Cv_ig_molar = Cp_ig_molar - 8.314462
        
        Cp_real = (Cp_ig_molar + eos.Cp_dep_g) / molar_mass
        Cv_real = (Cv_ig_molar + eos.Cv_dep_g) / molar_mass
        k = Cp_real / Cv_real if Cv_real > 0 else 1.4
        
        # Enthalpy & Entropy
        T_ref = 298.15
        H_ig_molar = sum(
            zs[i] * properties.HeatCapacityGases[i].T_dependent_property_integral(T_ref, T_k)
            for i in range(len(zs))
        )
        S_ig_molar = sum(
            zs[i] * properties.HeatCapacityGases[i].T_dependent_property_integral_over_T(T_ref, T_k)
            for i in range(len(zs))
        ) - 8.314462 * math.log(P_pa / 101325.0)
        
        H = (H_ig_molar + eos.H_dep_g) / molar_mass
        S = (S_ig_molar + eos.S_dep_g) / molar_mass

        return self._build_state(
            P_pa=P_pa,
            T_k=T_k,
            H=H,
            S=S,
            Z=Z,
            k=k,
            MW=MW_g_mol,
            Cp=Cp_real,
            Cv=Cv_real,
            density=D,
            phase=phase_str,
            fallback=False,
        )

    def _solve_aga8(self, P_pa: float, T_k: float, gas_data: dict) -> ThermodynamicState:
        """pyaga8 (GERG-2008) standardını kullanarak özellikleri çözer."""
        import pyaga8
        
        ids, zs = self._extract_thermo_components(gas_data)
        
        # AGA8 bileşenlerini eşleme
        AGA8_FIELDS_MAP = {
            "methane": "methane",
            "ethane": "ethane",
            "propane": "propane",
            "isobutane": "isobutane",
            "butane": "n_butane",
            "isopentane": "isopentane",
            "pentane": "n_pentane",
            "hexane": "hexane",
            "heptane": "heptane",
            "octane": "octane",
            "nonane": "nonane",
            "decane": "decane",
            "hydrogen": "hydrogen",
            "hydrogen sulfide": "hydrogen_sulfide",
            "nitrogen": "nitrogen",
            "carbon dioxide": "carbon_dioxide",
            "water": "water",
            "oxygen": "oxygen",
            "argon": "argon",
            "helium": "helium",
        }
        
        comp = pyaga8.Composition()
        for c_id, fraction in zip(ids, zs):
            if fraction <= 1e-6:
                continue
            field = AGA8_FIELDS_MAP.get(c_id.lower())
            if not field:
                raise ValueError(f"AGA8 standardı '{c_id}' bileşenini desteklemez.")
            setattr(comp, field, fraction)
            
        detail = pyaga8.Detail()
        detail.set_composition(comp)
        
        # MPa ve K birimleri
        detail.pressure = P_pa / 1e6
        detail.temperature = T_k
        
        detail.calc_density()
        detail.calc_properties()
        
        # Değerlerin okunması
        Z = detail.z
        MW_g_mol = detail.mm # g/mol
        molar_mass = MW_g_mol / 1000.0 # kg/mol
        
        # Yoğunluk: d (mol/cm³) -> kg/m³
        # d * 1e6 * molar_mass
        density = detail.d * 1e6 * molar_mass
        
        # Isı kapasiteleri: cp, cv (J/mol.K) -> J/kg.K
        Cp = detail.cp / molar_mass
        Cv = detail.cv / molar_mass
        k = Cp / Cv if Cv > 0 else 1.4
        
        # Mutlak entalpi ve entropi: h (J/mol) -> J/kg, s (J/mol.K) -> J/kg.K
        H = detail.h / molar_mass
        S = detail.s / molar_mass
        
        speed_of_sound = detail.w
        
        # Faz denetimi: Z aşırı düşükse sıvılaşma/yoğuşma riski vardır
        phase_str = 'gas'
        if Z < 0.3:
            phase_str = 'liquid'
            
        return self._build_state(
            P_pa=P_pa,
            T_k=T_k,
            H=H,
            S=S,
            Z=Z,
            k=k,
            MW=MW_g_mol,
            Cp=Cp,
            Cv=Cv,
            density=density,
            phase=phase_str,
            fallback=False,
            speed_of_sound=speed_of_sound
        )

    def _solve_fallback(self, P_pa: float, T_k: float, gas_obj, eos: str) -> ThermodynamicState:
        """Kütüphane başarısız olduğunda ideal gaz yaklaşımı."""
        mw_g_mol = self.infer_mw_g_mol(gas_obj)
        M_kg_mol = (mw_g_mol / 1000.0) if mw_g_mol else 0.02896
        
        R_specific = R_UNIVERSAL_J_MOL_K / M_kg_mol
        Cp_ideal = 1000 + 0.1 * (T_k - 273.15)
        Cv_ideal = Cp_ideal - R_specific
        k_ideal = Cp_ideal / Cv_ideal if Cv_ideal > 0 else 1.4
        
        Z_ideal = max(0.5, min(1.5, 1.0 - 0.1 * (P_pa / (STD_PRESS_PA * 10))))
        rho_ideal = P_pa / (R_specific * T_k * Z_ideal) if T_k > 0 and R_specific > 0 else 1.0
        
        H_ideal = Cp_ideal * (T_k - 273.15)
        S_ideal = Cp_ideal * math.log(T_k / 273.15) if T_k > 0 else 0
        
        return self._build_state(
            P_pa=P_pa,
            T_k=T_k,
            H=H_ideal,
            S=S_ideal,
            Z=Z_ideal,
            k=max(1.2, min(1.67, k_ideal)),
            MW=M_kg_mol * 1000,
            Cp=Cp_ideal,
            Cv=Cv_ideal,
            density=max(0.1, rho_ideal),
            phase='ideal_fallback',
            fallback=True,
            speed_of_sound=self._speed_of_sound(k_ideal, P_pa, max(rho_ideal, 0.1)),
        )
        
    def get_cache_stats(self):
        with self._cache_lock:
            total = self._cache_hits + self._cache_misses
            hit_rate = self._cache_hits / total if total > 0 else 0
            return {
                'hits': self._cache_hits,
                'misses': self._cache_misses,
                'hit_rate': hit_rate,
                'size': len(self._property_cache),
                'max_size': self._max_cache_size
            }
