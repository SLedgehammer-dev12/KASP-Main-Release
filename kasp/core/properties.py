"""
KASP V4.4 Thermodynamic Properties Solver
Bu modül saf formüller ve kütüphaneleri (CoolProp, Thermo) kullanarak Entalpi, 
Entropi, Cp, Cv, k, Z gibi özellikleri çözümleyen ve LRU tabanlı cache
mekanizmasını işleten ThermodynamicSolver sınıfını içerir.
"""

import math
import logging
import sys
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

try:
    import ccp
    from ccp import Q_
    CCP_LOADED = True
except ImportError:
    CCP_LOADED = False

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
        
        # Akilli fallback takipcisi
        from kasp.core.fallback import FallbackTracker
        self._fallback_tracker = FallbackTracker()
        self._active_eos_chain = None
        
        # PR/thermo isi kapasitesi integral cache (performans)
        self._h_int_cache: dict = {}

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
    def _classify_phase(Z: float, density: float, raw_phase: str | None = None) -> str:
        """Z-faktör ve yoğunluğa dayalı ortak faz sınıflandırması.

        Tüm EOS motorları için tutarlı faz çıktısı üretir.
        - Z > 0.7 veya ρ < 100 kg/m³ → 'gas'
        - 0.3 < Z ≤ 0.7 → 'supercritical'
        - Z ≤ 0.3 → 'liquid'
        - raw_phase 'twophase' (CoolProp) → 'two-phase'
        """
        if raw_phase in ("ideal_fallback", "ideal"):
            return raw_phase
        if raw_phase == "twophase":
            return "two-phase"

        if density < 100.0 or Z > 0.7:
            return "gas"
        elif Z > 0.3:
            return "supercritical"
        else:
            return "liquid"

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
        normalized_phase = ThermodynamicSolver._classify_phase(Z, density, phase)
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
            phase=normalized_phase,
            raw_props={
                "fallback": bool(fallback),
                "raw_phase": phase,
                "mu": mu,
                "speed_of_sound": speed_of_sound,
            },
        )

    def begin_run_tracking(self, solver_method="auto"):
        self._run_tracking.context = {
            "calls": 0,
            "fallback_calls": 0,
            "fallback_events": OrderedDict(),
            "solver_method": solver_method,
        }
        self._fallback_tracker.reset()

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
        
    def _dispatch(self, P_pa: float, T_k: float, gas_obj, eos_method: str) -> ThermodynamicState:
        """EOS'a ozgu cozucuyu cagirir. Fallback yapmaz, saf dispatch."""
        if eos_method == 'coolprop':
            return self._solve_coolprop(P_pa, T_k, gas_obj)
        elif eos_method in ['pr', 'srk']:
            return self._solve_thermo_eos(P_pa, T_k, gas_obj, eos_method)
        elif eos_method == 'aga8':
            return self._solve_aga8(P_pa, T_k, gas_obj)
        elif eos_method == 'thermopack':
            return self._solve_thermopack(P_pa, T_k, gas_obj)
        elif eos_method == 'ccp':
            return self._solve_ccp(P_pa, T_k, gas_obj)
        elif eos_method == 'dwsim':
            return self._solve_dwsim(P_pa, T_k, gas_obj)
        else:
            raise ValueError(f"Desteklenmeyen EOS: {eos_method}")
        
    def get_properties(self, P_pa: float, T_k: float, gas_obj, eos_method: str, *, eos_chain=None) -> ThermodynamicState:
        """
        Giriş basınç ve sıcaklığına bağli olarak durumu çözer. Cache mimarisi kullanir.
        gas_obj: Eğer coolprop ise string, thermo ise dict objesidir (mixture.py tarafindan uretilir)
        
        eos_chain: Opsiyonel EosChain objesi. Verilirse akilli EOS fallback zinciri kullanilir.
        """
        cache_key = self._build_cache_key(P_pa, T_k, gas_obj, eos_method)

        cached_state = self._get_cached_state(cache_key, P_pa, T_k, eos_method)
        if cached_state is not None:
            return cached_state
                
        self._record_cache_miss()
        
        # Aktif EosChain varsa (parametre veya global) akilli fallback kullan
        chain = eos_chain or self._active_eos_chain
        if chain is not None:
            state = chain.get_properties(P_pa, T_k, eos_method)
        else:
            # Geriye donuk uyumlu: direkt dispatch + PR fallback + ideal gaz son care
            try:
                state = self._dispatch(P_pa, T_k, gas_obj, eos_method)
            except Exception as e:
                if self._active_eos_chain is not None:
                    logger.debug(
                        "⚠️ %s EOS hatasi EosChain tarafindan yonetiliyor: %s",
                        eos_method.upper(),
                        e,
                    )
                    state = self._solve_fallback(P_pa, T_k, gas_obj, eos_method)
                else:
                    logger.info(
                        "⚠️ %s EOS hatasi: %s. PR fallback deneniyor.",
                        eos_method.upper(),
                        e,
                    )
                    try:
                        state = self._solve_thermo_eos(P_pa, T_k, gas_obj, 'pr')
                        state.raw_props['fallback'] = True
                        state.raw_props['fallback_layer'] = 'eos'
                        state.raw_props['fallback_from'] = eos_method
                        state.raw_props['fallback_to'] = 'pr'
                        state.raw_props['fallback_type'] = 'pr_fallback'
                        state.raw_props['fallback_reason'] = str(e)
                    except Exception as fallback_err:
                        logger.warning(
                            "⚠️ PR fallback da başarısız: %s. Ideal gaz'a geçiliyor.",
                            fallback_err,
                        )
                        state = self._solve_fallback(P_pa, T_k, gas_obj, eos_method)
            
        # Z-Factor Uyarısı ve Teşhis Entegrasyonu
        thermo_health = "HEALTHY"
        health_reasons = []
        if state.Z < 0.5:
            thermo_health = "WARNING"
            health_reasons.append(f"Düşük sıkıştırılabilirlik faktörü Z={state.Z:.4f} (yoğuşma riski)")
            logger.warning(f"⚠️ Olağandışı düşük Z faktörü: {state.Z:.4f} (P={P_pa/1e5:.1f} bar, T={T_k-273.15:.1f}°C)")
        elif state.Z > 1.5:
            thermo_health = "WARNING"
            health_reasons.append(f"Beklenmedik yüksek sıkıştırılabilirlik faktörü Z={state.Z:.4f}")
            logger.warning(f"⚠️ Olağandışı yüksek Z faktörü: {state.Z:.4f} (P={P_pa/1e5:.1f} bar, T={T_k-273.15:.1f}°C)")
        
        if state.phase in ('liquid', 'two-phase', 'supercritical'):
            thermo_health = "CRITICAL"
            health_reasons.append("Akışkan sıvı, iki faz veya yoğun süperkritik bölgeye girdi (faz ayrışması riski)")
            
        state.raw_props['thermo_health'] = thermo_health
        state.raw_props['health_reasons'] = health_reasons
             
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

    def _get_coolprop_abstract_state(self, mixture_string: str):
        """CoolProp AbstractState cache — karışım başına bir kez oluşturulur."""
        if mixture_string not in self._package_cache:
            try:
                from CoolProp import AbstractState
                AS = AbstractState("HEOS", mixture_string)
                try:
                    AS.build_phase_envelope("")
                except Exception:
                    pass
                self._package_cache[mixture_string] = AS
            except ImportError:
                self._package_cache[mixture_string] = None
        return self._package_cache.get(mixture_string)

    def _get_coolprop_phase(self, mixture_string: str, P_pa: float, T_k: float) -> str | None:
        """AbstractState.phase() ile güvenilir faz tespiti, karışımlarda faz zarfını yönetir."""
        try:
            AS = self._get_coolprop_abstract_state(mixture_string)
            if AS is None:
                return None
            AS.update(CP.PT_INPUTS, P_pa, T_k)
            iphase = AS.phase()
            from CoolProp import iphase_gas, iphase_liquid, iphase_supercritical
            from CoolProp import iphase_supercritical_gas, iphase_supercritical_liquid
            from CoolProp import iphase_twophase, iphase_not_imposed
            phase_map = {
                iphase_gas: "gas",
                iphase_liquid: "liquid",
                iphase_supercritical: "supercritical",
                iphase_supercritical_gas: "gas",
                iphase_supercritical_liquid: "supercritical",
                iphase_twophase: "twophase",
            }
            return phase_map.get(iphase)
        except Exception:
            return None

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
        
        # Faz tespiti: AbstractState ile (karışım faz zarfını otomatik yönetir)
        # AbstractState başarısız olursa PhaseSI, o da başarısız olursa Z+ρ sınıflandırıcıya bırak
        phase_str = self._get_coolprop_phase(mixture_string, P_pa, T_k)
        if phase_str is None:
            try:
                phase_str = CP.PhaseSI('P', P_pa, 'T', T_k, mixture_string)
            except Exception:
                phase_str = None
        
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
            phase=phase_str or "gas",
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
        
        # Enthalpy & Entropy (cached integrals for performance)
        T_ref = 298.15
        T_rounded = round(T_k, 1)
        H_ig_molar = 0.0
        S_ig_molar = 0.0
        log_p_ref = math.log(P_pa / 101325.0)
        for i in range(len(zs)):
            h_key = (ids[i], T_ref, T_rounded)
            s_key = (ids[i], T_ref, T_rounded, 'S')
            if h_key not in self._h_int_cache:
                self._h_int_cache[h_key] = properties.HeatCapacityGases[i].T_dependent_property_integral(T_ref, T_k)
            if s_key not in self._h_int_cache:
                self._h_int_cache[s_key] = properties.HeatCapacityGases[i].T_dependent_property_integral_over_T(T_ref, T_k)
            H_ig_molar += zs[i] * self._h_int_cache[h_key]
            S_ig_molar += zs[i] * self._h_int_cache[s_key]
        S_ig_molar -= 8.314462 * log_p_ref
        
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

    def _get_thermopack_eos(self, tp_components_tuple, eos_model='PR'):
        cache_key = (tp_components_tuple, eos_model)
        if cache_key not in self._package_cache:
            from thermopack.cubic import cubic
            components_str = ','.join(tp_components_tuple)
            eos = cubic(components_str, eos_model)
            self._package_cache[cache_key] = eos
        return self._package_cache[cache_key]

    def _solve_thermopack(self, P_pa: float, T_k: float, gas_data: dict) -> ThermodynamicState:
        """thermopack (SINTEF) motorunu kullanarak özellikleri çözer."""
        from kasp.core.mixture import GasMixtureBuilder
        
        ids, zs = self._extract_thermo_components(gas_data)
        
        THERMOPACK_MAPPING = {
            'METHANE': 'C1',
            'ETHANE': 'C2',
            'PROPANE': 'C3',
            'BUTANE': 'NC4',
            'ISOBUTANE': 'IC4',
            'PENTANE': 'NC5',
            'ISOPENTANE': 'IC5',
            'HEXANE': 'NC6',
            'HEPTANE': 'NC7',
            'OCTANE': 'NC8',
            'NONANE': 'NC9',
            'DECANE': 'NC10',
            'NITROGEN': 'N2',
            'CARBONDIOXIDE': 'CO2',
            'HYDROGENSULFIDE': 'H2S',
            'HYDROGEN': 'H2',
            'OXYGEN': 'O2',
            'WATER': 'H2O',
            'HELIUM': 'HE',
            'ARGON': 'AR',
        }
        
        reverse_map = {
            thermo_id.lower(): component
            for component, thermo_id in GasMixtureBuilder.THERMO_ID_MAP.items()
        }
        
        tp_ids = []
        for component_id in ids:
            canonical = reverse_map.get(str(component_id).lower(), str(component_id).upper())
            tp_id = THERMOPACK_MAPPING.get(canonical, canonical)
            tp_ids.append(tp_id)
            
        eos = self._get_thermopack_eos(tuple(tp_ids), 'PR')
        
        # Calculate specific volume and phase
        try:
            v, = eos.specific_volume(T_k, P_pa, zs, eos.VAPPH)
            phase_str = 'gas'
        except Exception:
            try:
                v, = eos.specific_volume(T_k, P_pa, zs, eos.LIQPH)
                phase_str = 'liquid'
            except Exception:
                v = 8.314462 * T_k / P_pa
                phase_str = 'ideal'
                
        # Calculate MW and density
        MW_g_mol = sum(zs[i] * MOLAR_MASSES[reverse_map.get(str(ids[i]).lower(), str(ids[i]).upper())] for i in range(len(zs)))
        molar_mass = MW_g_mol / 1000.0 # kg/mol
        
        density = molar_mass / v # kg/m^3
        Z = P_pa * v / (8.314462 * T_k)
        
        # Enthalpy and entropy
        h_molar, cp_molar = eos.enthalpy(T_k, P_pa, zs, eos.VAPPH if phase_str == 'gas' else eos.LIQPH, dhdt=True)
        H = h_molar / molar_mass
        Cp = cp_molar / molar_mass
        
        s_molar, = eos.entropy(T_k, P_pa, zs, eos.VAPPH if phase_str == 'gas' else eos.LIQPH)
        S = s_molar / molar_mass
        
        # Internal energy for Cv
        u_molar, cv_molar = eos.internal_energy_tv(T_k, v, zs, dedt=True)
        Cv = cv_molar / molar_mass
        
        k = Cp / Cv if Cv > 0 else 1.4
        
        # Speed of sound
        try:
            speed_of_sound = eos.speed_of_sound_tv(T_k, v, zs)
        except Exception:
            speed_of_sound = self._speed_of_sound(k, P_pa, density)
            
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

    def _solve_ccp(self, P_pa: float, T_k: float, gas_data: dict) -> ThermodynamicState:
        """ccp (Petrobras) motorunu kullanarak özellikleri çözer."""
        if not CCP_LOADED:
            raise ImportError("ccp kütüphanesi aktif değil.")
        
        from kasp.core.mixture import GasMixtureBuilder
        
        ids, zs = self._extract_thermo_components(gas_data)
        
        CCP_MAPPING = {
            'METHANE': 'Methane',
            'ETHANE': 'Ethane',
            'PROPANE': 'Propane',
            'BUTANE': 'n-Butane',
            'ISOBUTANE': 'IsoButane',
            'PENTANE': 'n-Pentane',
            'ISOPENTANE': 'Isopentane',
            'HEXANE': 'n-Hexane',
            'HEPTANE': 'n-Heptane',
            'OCTANE': 'n-Octane',
            'NONANE': 'n-Nonane',
            'DECANE': 'n-Decane',
            'NITROGEN': 'Nitrogen',
            'CARBONDIOXIDE': 'CarbonDioxide',
            'HYDROGENSULFIDE': 'HydrogenSulfide',
            'HYDROGEN': 'Hydrogen',
            'OXYGEN': 'Oxygen',
            'WATER': 'Water',
            'HELIUM': 'Helium',
            'ARGON': 'Argon',
            'AIR': 'Air',
        }
        
        reverse_map = {
            thermo_id.lower(): component
            for component, thermo_id in GasMixtureBuilder.THERMO_ID_MAP.items()
        }
        
        fluid = {}
        for c_id, fraction in zip(ids, zs):
            if fraction <= 1e-6:
                continue
            canonical = reverse_map.get(str(c_id).lower(), str(c_id).upper())
            ccp_name = CCP_MAPPING.get(canonical, canonical)
            fluid[ccp_name] = fraction
            
        # Normalize fluid sum to 1.0
        total = sum(fluid.values())
        if total > 0:
            fluid = {k: v/total for k, v in fluid.items()}
            
        state_ccp = ccp.State(
            fluid=fluid,
            p=Q_(P_pa, 'Pa'),
            T=Q_(T_k, 'K'),
            EOS='PR'
        )
        
        H = state_ccp.h().to('J/kg').magnitude
        S = state_ccp.s().to('J/kg/K').magnitude
        Z = state_ccp.z().magnitude
        
        cp_val = state_ccp.cp().to('J/kg/K').magnitude
        cv_val = state_ccp.cv().to('J/kg/K').magnitude
        k = cp_val / cv_val if cv_val > 0 else 1.4
        
        density = state_ccp.rho().to('kg/m**3').magnitude
        
        MW_g_mol = sum(zs[i] * MOLAR_MASSES[reverse_map.get(str(ids[i]).lower(), str(ids[i]).upper())] for i in range(len(zs)))
        
        phase_str = 'gas'
        if Z < 0.3:
            phase_str = 'liquid'
            
        speed_of_sound = self._speed_of_sound(k, P_pa, density)
        
        return self._build_state(
            P_pa=P_pa,
            T_k=T_k,
            H=H,
            S=S,
            Z=Z,
            k=k,
            MW=MW_g_mol,
            Cp=cp_val,
            Cv=cv_val,
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
        
        # 1. Gaz kompozisyonunu ve Thermo/CoolProp yapısını çözümle
        ids, zs = [], []
        if isinstance(gas_obj, dict):
            ids = gas_obj.get("ids", gas_obj.get("IDs", []))
            zs = gas_obj.get("mol_fractions", gas_obj.get("zs", []))
        elif isinstance(gas_obj, str):
            try:
                from kasp.core.mixture import GasMixtureBuilder
                from kasp.core.constants import SUPPORTED_GASES
                rev_supported = {v.lower(): k for k, v in SUPPORTED_GASES.items()}
                for part in gas_obj.split('&'):
                    if '[' in part and part.endswith(']'):
                        name, frac_str = part[:-1].split('[')
                        canonical = rev_supported.get(name.lower(), name.upper())
                        thermo_id = GasMixtureBuilder.THERMO_ID_MAP.get(canonical)
                        if thermo_id:
                            ids.append(thermo_id)
                            zs.append(float(frac_str))
            except Exception:
                pass

        # 2. Dinamik Ideal Cp Hesaplama
        Cp_ideal = 1000.0 # Güvenli taban
        
        # A) Thermo kütüphanesi kuruluysa ve bileşenler çözülebildiyse tam polynomial Cp
        if THERMO_LOADED and ids and zs and len(ids) == len(zs):
            try:
                constants, properties = self._get_thermo_package(ids)
                # J/mol-K molar ideal Cp
                Cp_ig_molar = sum(
                    zs[i] * properties.HeatCapacityGases[i](T_k) for i in range(len(zs))
                )
                Cp_ideal = Cp_ig_molar / M_kg_mol
            except Exception:
                pass
                
        # B) Thermo kurulu değilse veya başarısız olursa, 298.15K standart Cp değerleri üzerinden ağırlıklı ortalama + sıcaklık düzeltmesi
        if Cp_ideal == 1000.0 and ids and zs and len(ids) == len(zs):
            try:
                STANDARD_CP_MOLAR = {
                    'methane': 35.7, 'ethane': 52.6, 'propane': 73.6,
                    'isobutane': 96.8, 'n_butane': 97.4, 'butane': 97.4,
                    'isopentane': 120.0, 'n_pentane': 120.0, 'pentane': 120.0,
                    'hexane': 143.0, 'n_hexane': 143.0,
                    'heptane': 166.0, 'n_heptane': 166.0,
                    'octane': 189.0, 'n_octane': 189.0,
                    'nonane': 212.0, 'decane': 235.0,
                    'hydrogen': 28.8, 'hydrogen sulfide': 34.2, 'hydrogen_sulfide': 34.2,
                    'nitrogen': 29.12, 'carbon dioxide': 37.13, 'carbon_dioxide': 37.13,
                    'water': 33.58, 'oxygen': 29.37, 'argon': 20.786,
                    'helium': 20.786, 'neon': 20.786, 'krypton': 20.786,
                    'xenon': 20.786, 'air': 29.07
                }
                cp_molar_mix = sum(
                    zs[i] * STANDARD_CP_MOLAR.get(str(ids[i]).lower(), 29.0)
                    for i in range(len(zs))
                )
                # 298.15K'den uzaklaştıkça ideal Cp artış faktörü
                temp_factor = 1.0 + 0.001 * (T_k - 298.15)
                Cp_ideal = (cp_molar_mix * temp_factor) / M_kg_mol
            except Exception:
                pass

        # C) Eğer her şey başarısız olursa eski doğrusal formül
        if Cp_ideal == 1000.0:
            Cp_ideal = 1000 + 0.1 * (T_k - 273.15)
        
        Cv_ideal = Cp_ideal - R_specific
        k_ideal = Cp_ideal / Cv_ideal if Cv_ideal > 0 else 1.4
        
        Z_ideal = max(0.5, min(1.5, 1.0 - 0.1 * (P_pa / (STD_PRESS_PA * 10))))
        rho_ideal = P_pa / (R_specific * T_k * Z_ideal) if T_k > 0 and R_specific > 0 else 1.0
        
        H_ideal = Cp_ideal * (T_k - 298.15)
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

    def _load_dwsim_dll(self):
        """DWSIM Standalone dll'sini bulur ve pythonnet clr ile yükler."""
        if hasattr(self, "_dwsim_dll_loaded"):
            return self._dwsim_dll_loaded

        self._dwsim_dll_loaded = False
        try:
            import clr
            import os
            
            search_paths = [
                getattr(sys, '_MEIPASS', ''),
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "libs"),
                os.path.abspath("."),
                os.path.abspath("./kasp/libs"),
                "/Applications/DWSIM.app/Contents/MonoBundle",
                "C:\\Program Files\\DWSIM",
                "C:\\Program Files (x86)\\DWSIM",
            ]
            
            dll_name = "DWSIM.Thermodynamics.StandaloneLibrary.dll"
            loaded = False
            
            try:
                clr.AddReference("DWSIM.Thermodynamics.StandaloneLibrary")
                loaded = True
            except Exception:
                pass
                
            if not loaded:
                for path in search_paths:
                    full_path = os.path.join(path, dll_name)
                    if os.path.exists(full_path):
                        clr.AddReference(full_path)
                        loaded = True
                        break
                        
            if loaded:
                from DWSIM.Thermodynamics import PropertyPackages, CalculatorInterface
                self._dwsim_PropertyPackages = PropertyPackages
                self._dwsim_Calculator = CalculatorInterface.Calculator()
                self._dwsim_Calculator.Initialize()
                self._dwsim_dll_loaded = True
                logger.info("🎉 DWSIM Standalone Thermodynamics Library başarıyla yüklendi!")
        except Exception as e:
            logger.warning(f"⚠️ DWSIM DLL yükleme hatası: {e}")
            self._dwsim_dll_loaded = False
            
        return self._dwsim_dll_loaded

    def _solve_dwsim(self, P_pa: float, T_k: float, gas_data: dict) -> ThermodynamicState:
        """DWSIM Standalone Thermodynamics Library kullanarak özellikleri çözer."""
        if not self._load_dwsim_dll():
            raise RuntimeError("DWSIM Standalone kütüphanesi yüklenemedi.")
            
        from System import Array, Double, String
        
        ids, zs = self._extract_thermo_components(gas_data)
        
        from kasp.core.mixture import GasMixtureBuilder
        reverse_map = {
            thermo_id.lower(): component
            for component, thermo_id in GasMixtureBuilder.THERMO_ID_MAP.items()
        }
        
        DWSIM_MAPPING = {
            'METHANE': 'Methane',
            'ETHANE': 'Ethane',
            'PROPANE': 'Propane',
            'BUTANE': 'n-Butane',
            'ISOBUTANE': 'Isobutane',
            'PENTANE': 'n-Pentane',
            'ISOPENTANE': 'Isopentane',
            'HEXANE': 'n-Hexane',
            'HEPTANE': 'n-Heptane',
            'OCTANE': 'n-Octane',
            'NONANE': 'n-Nonane',
            'DECANE': 'n-Decane',
            'NITROGEN': 'Nitrogen',
            'CARBONDIOXIDE': 'Carbon Dioxide',
            'HYDROGENSULFIDE': 'Hydrogen Sulfide',
            'HYDROGEN': 'Hydrogen',
            'OXYGEN': 'Oxygen',
            'WATER': 'Water',
            'HELIUM': 'Helium',
            'ARGON': 'Argon',
            'AIR': 'Air',
        }
        
        dwsim_names = []
        dwsim_fracs = []
        
        for c_id, fraction in zip(ids, zs):
            if fraction <= 1e-6:
                continue
            canonical = reverse_map.get(str(c_id).lower(), str(c_id).upper())
            dw_name = DWSIM_MAPPING.get(canonical, canonical)
            dwsim_names.append(dw_name)
            dwsim_fracs.append(fraction)
            
        total_frac = sum(dwsim_fracs)
        if total_frac > 0:
            dwsim_fracs = [f / total_frac for f in dwsim_fracs]
            
        carray = Array[String](dwsim_names)
        comparray = Array[Double](dwsim_fracs)
        
        cache_key = tuple(dwsim_names)
        if cache_key not in self._package_cache:
            water_fraction = 0.0
            if 'Water' in dwsim_names:
                idx = dwsim_names.index('Water')
                water_fraction = dwsim_fracs[idx]
            if water_fraction > 0.05:
                pp = self._dwsim_PropertyPackages.SteamTablesPropertyPackage(True)
            else:
                pp = self._dwsim_PropertyPackages.PRPropertyPackage(True)
            self._package_cache[cache_key] = pp
        else:
            pp = self._package_cache[cache_key]
            
        ms = self._dwsim_Calculator.CreateMaterialStream(carray, comparray)
        ms.SetPropertyPackage(pp)
        
        ms.SetTemperature(float(T_k))
        ms.SetPressure(float(P_pa))
        ms.SetFlashSpec("PT")
        ms.Calculate()
        
        present_phases = list(ms.GetPresentPhases())
        phase_label = "Vapor" if "Vapor" in present_phases else "Overall"
        
        try:
            density = float(ms.GetSinglePhaseProp("density", phase_label, "Mass"))
        except Exception:
            density = float(ms.GetSinglePhaseProp("density", "Overall", "Mass"))
            
        try:
            H = float(ms.GetSinglePhaseProp("enthalpy", phase_label, "Mass")) * 1000.0
        except Exception:
            H = float(ms.GetSinglePhaseProp("enthalpy", "Overall", "Mass")) * 1000.0
            
        try:
            S = float(ms.GetSinglePhaseProp("entropy", phase_label, "Mass")) * 1000.0
        except Exception:
            S = float(ms.GetSinglePhaseProp("entropy", "Overall", "Mass")) * 1000.0
            
        try:
            Z = float(ms.GetSinglePhaseProp("compressibilityFactor", phase_label, "Mass"))
        except Exception:
            Z = float(ms.GetSinglePhaseProp("compressibilityFactor", "Overall", "Mass"))
            
        try:
            cp_val = float(ms.GetSinglePhaseProp("heatCapacityCp", phase_label, "Mass")) * 1000.0
        except Exception:
            cp_val = float(ms.GetSinglePhaseProp("heatCapacityCp", "Overall", "Mass")) * 1000.0
            
        try:
            cv_val = float(ms.GetSinglePhaseProp("heatCapacityCv", phase_label, "Mass")) * 1000.0
        except Exception:
            cv_val = float(ms.GetSinglePhaseProp("heatCapacityCv", "Overall", "Mass")) * 1000.0
            
        k = cp_val / cv_val if cv_val > 0 else 1.4
        
        try:
            speed_of_sound = float(ms.GetSinglePhaseProp("speedOfSound", phase_label, "Mass"))
        except Exception:
            speed_of_sound = self._speed_of_sound(k, P_pa, density)

        try:
            mu_val = float(ms.GetSinglePhaseProp("viscosity", phase_label, "Mass"))
        except Exception:
            try:
                mu_val = float(ms.GetSinglePhaseProp("viscosity", "Overall", "Mass"))
            except Exception:
                mu_val = 1.1e-5

        try:
            tc_val = float(ms.GetSinglePhaseProp("thermalConductivity", phase_label, "Mass"))
        except Exception:
            try:
                tc_val = float(ms.GetSinglePhaseProp("thermalConductivity", "Overall", "Mass"))
            except Exception:
                tc_val = 0.0

        MW_g_mol = sum(zs[i] * MOLAR_MASSES[reverse_map.get(str(ids[i]).lower(), str(ids[i]).upper())] for i in range(len(zs)))
        phase_str = 'gas' if phase_label == 'Vapor' else 'liquid'

        return self._build_state(
            P_pa=P_pa,
            T_k=T_k,
            H=H,
            S=S,
            Z=Z,
            k=k,
            MW=MW_g_mol,
            Cp=cp_val,
            Cv=cv_val,
            density=density,
            phase=phase_str,
            fallback=False,
            speed_of_sound=speed_of_sound,
            mu=mu_val
        )

