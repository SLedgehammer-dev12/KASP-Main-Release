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
from kasp.core.exceptions import ThermodynamicError

# Sabitler (GasMixtureBuilder veya API 617)
from kasp.core.constants import (
    R_UNIVERSAL_J_MOL_K, STD_PRESS_PA
)

# Kütüphane Yüklemeleri (Lazy/Optional Imports)
try:
    import CoolProp.CoolProp as CP
    COOLPROP_LOADED = True
except ImportError:
    COOLPROP_LOADED = False

try:
    from thermo.eos_mix import PRMIX, SRKMIX
    from thermo import ChemicalConstantsPackage, PropertyPackage
    THERMO_LOADED = True
except ImportError:
    THERMO_LOADED = False

logger = logging.getLogger(__name__)

class ThermodynamicSolver:
    """Core Thermodynamic calculations with Thread-Safe Caching."""
    
    def __init__(self, max_cache_size=2000):
        self._property_cache = OrderedDict()
        self._max_cache_size = max_cache_size
        self._cache_hits = 0
        self._cache_misses = 0
        self._cache_lock = threading.Lock()
        
        # Cache for thermo packages to avoid expensive instantiation
        self._package_cache = {}
        
    def get_properties(self, P_pa: float, T_k: float, gas_obj, eos_method: str) -> ThermodynamicState:
        """
        Giriş basınç ve sıcaklığına bağli olarak durumu çözer. Cache mimarisi kullanir.
        gas_obj: Eğer coolprop ise string, thermo ise dict objesidir (mixture.py tarafindan uretilir)
        """
        # 1. Cache Key Oluştur (Tuple olarak daha hızlı)
        if isinstance(gas_obj, str):
            gas_hash = hash(gas_obj)
        elif isinstance(gas_obj, dict):
            # Dict -> Sortlanmış tuple listesi ile hashleme
            components_tuple = tuple(sorted(zip(gas_obj.get('IDs', []), gas_obj.get('zs', []))))
            gas_hash = hash(components_tuple)
        else:
            gas_hash = hash(str(gas_obj))
            
        cache_key = (round(P_pa, 1), round(T_k, 2), gas_hash, eos_method)

        with self._cache_lock:
            if cache_key in self._property_cache:
                self._cache_hits += 1
                state = self._property_cache.pop(cache_key)
                self._property_cache[cache_key] = state # Sona taşı (LRU)
                return state
                
        self._cache_misses += 1
        
        # 2. Ana Hesaplama Döngüsü
        try:
            if eos_method == 'coolprop':
                state = self._solve_coolprop(P_pa, T_k, gas_obj)
            elif eos_method in ['pr', 'srk']:
                state = self._solve_thermo_eos(P_pa, T_k, gas_obj, eos_method)
            else:
                raise ValueError(f"Desteklenmeyen EOS: {eos_method}")
                
        except Exception as e:
            logger.warning(f"⚠️ {eos_method.upper()} EOS hatası: {e}. Fallback (İdeal Gaz) kullanılıyor.")
            state = self._solve_fallback(P_pa, T_k, gas_obj, eos_method)
            
        # Z-Factor Uyarısı
        if state.Z < 0.5 or state.Z > 1.5:
             logger.warning(f"⚠️ Olağandışı Z faktörü: {state.Z:.4f} (P={P_pa/1e5:.1f} bar, T={T_k-273.15:.1f}°C)")
             
        # Cache'e Ekle
        with self._cache_lock:
            if len(self._property_cache) >= self._max_cache_size:
                 self._property_cache.popitem(last=False)
            self._property_cache[cache_key] = state
            
        return state

    def _solve_coolprop(self, P_pa: float, T_k: float, mixture_string: str) -> ThermodynamicState:
        """CoolProp HEOS motorunu kullanarak özellikleri çözer."""
        if not COOLPROP_LOADED:
            raise ImportError("CoolProp kütüphanesi aktif değil.")
            
        H = CP.PropsSI('Hmass', 'P', P_pa, 'T', T_k, mixture_string)
        S = CP.PropsSI('Smass', 'P', P_pa, 'T', T_k, mixture_string)
        Z = CP.PropsSI('Z', 'P', P_pa, 'T', T_k, mixture_string)
        D = CP.PropsSI('Dmass', 'P', P_pa, 'T', T_k, mixture_string)
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
        
        return ThermodynamicState(
            P=P_pa, T=T_k, H=H, S=S, Z=Z, k=k,
            MW=MW_kg_mol * 1000.0, # g/mol
            Cp=Cp, Cv=Cv, density=D, phase=phase_str,
            raw_props={'fallback': False, 'mu': CP.PropsSI('V', 'P', P_pa, 'T', T_k, mixture_string)}
        )
        
    def _solve_thermo_eos(self, P_pa: float, T_k: float, gas_data: dict, eos_method: str) -> ThermodynamicState:
        """Thermo PR/SRK modülünü kullanarak özellikleri çözer."""
        if not THERMO_LOADED:
             raise ImportError("Thermo kütüphanesi aktif değil.")
             
        # Support both old format with pre-built objects and new format with just ids/fractions
        zs = gas_data.get('zs', gas_data.get('mol_fractions', []))
        ids = gas_data.get('ids', [])
        
        pkg_key = tuple(ids)
        if pkg_key not in self._package_cache:
            constants, properties = ChemicalConstantsPackage.from_IDs(ids)
            self._package_cache[pkg_key] = (constants, properties)
            
        constants, properties = self._package_cache[pkg_key]
        
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

        return ThermodynamicState(
            P=P_pa, T=T_k, H=H, S=S, Z=Z, k=k,
            MW=MW_g_mol, Cp=Cp_real, Cv=Cv_real, density=D, phase=phase_str,
            raw_props={'fallback': False, 'mu': 1.1e-5} # Fixed viscosity for now
        )

    def _solve_fallback(self, P_pa: float, T_k: float, gas_obj, eos: str) -> ThermodynamicState:
        """Kütüphane başarısız olduğunda ideal gaz yaklaşımı."""
        # Mix MW hesabını yap/çek
        M_kg_mol = 0.02896 # HAVA varsayımı
        if isinstance(gas_obj, dict) and 'MW' in gas_obj:
             M_kg_mol = gas_obj['MW'] / 1000.0
        
        R_specific = R_UNIVERSAL_J_MOL_K / M_kg_mol
        Cp_ideal = 1000 + 0.1 * (T_k - 273.15)
        Cv_ideal = Cp_ideal - R_specific
        k_ideal = Cp_ideal / Cv_ideal if Cv_ideal > 0 else 1.4
        
        Z_ideal = max(0.5, min(1.5, 1.0 - 0.1 * (P_pa / (STD_PRESS_PA * 10))))
        rho_ideal = P_pa / (R_specific * T_k * Z_ideal) if T_k > 0 and R_specific > 0 else 1.0
        
        H_ideal = Cp_ideal * (T_k - 273.15)
        S_ideal = Cp_ideal * math.log(T_k / 273.15) if T_k > 0 else 0
        
        return ThermodynamicState(
            P=P_pa, T=T_k, H=H_ideal, S=S_ideal, Z=Z_ideal, k=max(1.2, min(1.67, k_ideal)),
            MW=M_kg_mol*1000, Cp=Cp_ideal, Cv=Cv_ideal, density=max(0.1, rho_ideal),
            phase='ideal_fallback', raw_props={'fallback': True}
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
