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
    MOLAR_MASSES, R_UNIVERSAL_J_MOL_K, STD_PRESS_PA, normalize_component, ALIAS_MAP
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


# ─────────────────────────────────────────────────────────────────────────────
# PR/SRK ikili etkileşim katsayıları (kij) — literatür derlemesi.
# Varsayılan kij=0 ekşi/asidik/H2'li ve CO2'li gazlarda Z ve entalpide %1-8
# sistematik sapma yaratır. Aşağıdaki değerler yaygın PR EOS derlemelerinden
# (Aspen/PPDS tipi) alınmıştır; kaynak: Soave 1972, Peng-Robinson 1976/1978 ve
# çok-bileşenli doğalgaz/asidik gaz kij tabloları. Değerler yaklaşıktır.
_KEY = lambda a: str(a).replace(" ", "").upper()
_PR_SRK_KIJ = {
    ("CARBONDIOXIDE", "METHANE"): 0.100,
    ("CARBONDIOXIDE", "ETHANE"): 0.130,
    ("CARBONDIOXIDE", "PROPANE"): 0.125,
    ("CARBONDIOXIDE", "BUTANE"): 0.120,
    ("CARBONDIOXIDE", "ISOBUTANE"): 0.120,
    ("CARBONDIOXIDE", "NITROGEN"): -0.017,
    ("CARBONDIOXIDE", "HYDROGENSULFIDE"): 0.100,
    ("CARBONDIOXIDE", "HYDROGEN"): 0.060,
    ("METHANE", "HYDROGENSULFIDE"): 0.080,
    ("ETHANE", "HYDROGENSULFIDE"): 0.080,
    ("PROPANE", "HYDROGENSULFIDE"): 0.070,
    ("BUTANE", "HYDROGENSULFIDE"): 0.060,
    ("ISOBUTANE", "HYDROGENSULFIDE"): 0.060,
    ("NITROGEN", "METHANE"): 0.031,
    ("NITROGEN", "ETHANE"): 0.050,
    ("NITROGEN", "PROPANE"): 0.080,
    ("NITROGEN", "BUTANE"): 0.100,
    ("NITROGEN", "ISOBUTANE"): 0.100,
    ("NITROGEN", "HYDROGENSULFIDE"): 0.170,
    ("HYDROGEN", "METHANE"): 0.030,
    ("HYDROGEN", "ETHANE"): 0.045,
    ("HYDROGEN", "PROPANE"): 0.060,
    ("HYDROGEN", "NITROGEN"): 0.100,
    ("WATER", "METHANE"): 0.450,
    ("WATER", "ETHANE"): 0.400,
    ("WATER", "CARBONDIOXIDE"): 0.120,
    ("WATER", "HYDROGENSULFIDE"): 0.100,
}
# Yüksek sapma riskli bileşenler (kij ve polarite duyarlılığı)
_HIGH_ERROR_COMPONENTS = {"CARBONDIOXIDE", "HYDROGENSULFIDE", "HYDROGEN", "WATER", "H2S", "CO2"}


# Normalizasyon sözlüğü (constants.ALIAS_MAP ile konsolide edildi)
_NORM_ALIASES = ALIAS_MAP


def _build_kij_matrix(ids) -> list[list[float]] | None:
    """PR/SRK için NxN kij matrisi üretir (simetrik). Değer yoksa 0.0.

    Tüm çiftler 0 ise `None` döndürür (thermo varsayılanı kullanılır).
    """
    n = len(ids)
    if n <= 1:
        return None
    normalized = [_NORM_ALIASES.get(_KEY(i), _KEY(i)) for i in ids]
    matrix = [[0.0] * n for _ in range(n)]
    any_nonzero = False
    for i in range(n):
        for j in range(i + 1, n):
            key = tuple(sorted((normalized[i], normalized[j])))
            kij = _PR_SRK_KIJ.get(key)
            if kij is None:
                # Alt/çapraz anahtar (ör. H2S/CO2 alias) denemesi
                kij = _PR_SRK_KIJ.get((normalized[i], normalized[j]))
            if kij is None:
                kij = _PR_SRK_KIJ.get((normalized[j], normalized[i]))
            if kij is not None:
                matrix[i][j] = matrix[j][i] = float(kij)
                any_nonzero = True
    return matrix if any_nonzero else None


def _check_missing_kij_pairs(ids, kijs) -> list[str]:
    """Yüksek-sapma riskli bileşen içeren ve kij=0 kalan çiftleri listeler."""
    n = len(ids)
    if n <= 1:
        return []
    normalized = [_NORM_ALIASES.get(_KEY(i), _KEY(i)) for i in ids]
    missing = []
    for i in range(n):
        for j in range(i + 1, n):
            ci, cj = normalized[i], normalized[j]
            if ci in _HIGH_ERROR_COMPONENTS or cj in _HIGH_ERROR_COMPONENTS:
                val = kijs[i][j] if kijs is not None else 0.0
                if val == 0.0:
                    missing.append(f"{ci}-{cj}")
    return missing


class ThermodynamicSolver:
    """Core Thermodynamic calculations with Thread-Safe Caching."""
    
    def __init__(self, max_cache_size=2000):
        self._property_cache = OrderedDict()
        self._max_cache_size = self._coerce_cache_size(max_cache_size)
        self._cache_hits = 0
        self._cache_misses = 0
        self._cache_lock = threading.RLock()
        self._as_lock = threading.RLock()
        
        # Cache for thermo packages to avoid expensive instantiation
        self._package_cache = {}
        self._run_tracking = threading.local()
        
        # Akilli fallback takipcisi
        from kasp.core.fallback import FallbackTracker
        self._fallback_tracker = FallbackTracker()
        self._active_eos_chain = None
        
        # PR/thermo isi kapasitesi integral cache (performans)
        self._h_int_cache: dict = {}

    @property
    def _active_eos_chain(self):
        if not hasattr(self._run_tracking, "active_eos_chain"):
            return None
        return self._run_tracking.active_eos_chain

    @_active_eos_chain.setter
    def _active_eos_chain(self, value):
        self._run_tracking.active_eos_chain = value

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
    def _speed_of_sound(k_value, pressure_pa, density, Z=1.0):
        if density <= 0 or pressure_pa <= 0 or k_value <= 0:
            return 0.0
        return math.sqrt(max(float(k_value) * float(pressure_pa) / float(density), 0.0))

    @staticmethod
    def _classify_phase(Z: float, density: float, raw_phase: str | None = None) -> str:
        """Z-faktör ve yoğunluğa dayalı ortak faz sınıflandırması.

        Tüm EOS motorları için tutarlı faz çıktısı üretir.
        - Z > 0.7 veya ρ < 100 kg/m³ → 'gas'
        - 0.3 < Z ≤ 0.7 → 'supercritical'
        - Z ≤ 0.3 → 'liquid'
        - raw_phase 'twophase' (CoolProp) → 'two-phase'
        """
        if raw_phase in ("ideal_fallback", "ideal", "gas", "liquid", "supercritical", "two-phase"):
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
        if speed_of_sound is None or not math.isfinite(speed_of_sound) or speed_of_sound <= 0:
            speed_of_sound = ThermodynamicSolver._speed_of_sound(k, P_pa, density, Z)
        speed_of_sound_val = (
            float(speed_of_sound or 0.0)
            if math.isfinite(float(speed_of_sound or 0.0))
            else 0.0
        )
        normalized_phase = ThermodynamicSolver._classify_phase(Z, density, phase)
        health_reasons = []
        # Standart J/(kg*K) birim sözleşmesi güvencesi
        if Cp is not None and math.isfinite(Cp) and Cp > 0:
            norm_cp = float(Cp)
        else:
            norm_cp = 1000.0
            health_reasons.append("Cp geçersiz veya <=0 olduğu için 1000.0 J/(kg·K) varsayıldı.")
        if Cv is not None and math.isfinite(Cv) and Cv > 0:
            norm_cv = float(Cv)
        else:
            norm_cv = norm_cp / (k if k > 1.0 else 1.4)
            health_reasons.append("Cv geçersiz veya <=0 olduğu için Cp/k ile türetildi.")
        raw = {
            "fallback": bool(fallback),
            "raw_phase": phase,
            "mu": mu,
            "speed_of_sound": speed_of_sound_val,
        }
        if health_reasons:
            raw["health_reasons"] = health_reasons
            raw["thermo_health"] = "WARNING"
        return ThermodynamicState(
            P=float(P_pa),
            T=float(T_k),
            H=float(H),
            S=float(S),
            Z=float(Z),
            k=float(k),
            MW=float(MW),
            Cp=norm_cp,
            Cv=norm_cv,
            density=float(density),
            phase=normalized_phase,
            speed_of_sound=float(raw.get("speed_of_sound") or 0.0),
            raw_props=raw,
        )

    def begin_run_tracking(self, solver_method="auto"):
        # Ic ice run'lar (or. belirsizlik pertürbasyonlari) icin yigin tabanli izleme (P4-25)
        stack = getattr(self._run_tracking, "context_stack", None)
        if stack is None:
            stack = []
            self._run_tracking.context_stack = stack
        current_ctx = getattr(self._run_tracking, "context", None)
        if current_ctx is not None:
            current_ctx["_saved_tracker_state"] = {
                "broken_eos": dict(self._fallback_tracker._broken_eos),
                "broken_solvers": set(self._fallback_tracker._broken_solvers),
                "nonconverged_solvers": dict(self._fallback_tracker._nonconverged_solvers),
                "eos_chain_log": list(self._fallback_tracker.eos_chain_log),
                "solver_chain_log": list(self._fallback_tracker.solver_chain_log),
            }
        stack.append(current_ctx)
        self._run_tracking.context = {
            "calls": 0,
            "fallback_calls": 0,
            "fallback_events": OrderedDict(),
            "solver_method": solver_method,
        }
        if current_ctx is None:
            self._fallback_tracker.reset()

    def end_run_tracking(self):
        context = getattr(self._run_tracking, "context", None)
        nonconverged = self._fallback_tracker.solver_nonconverged_info()
        # Onceki (dis) run baglamini geri yukle
        stack = getattr(self._run_tracking, "context_stack", None)
        if stack:
            prev_ctx = stack.pop()
            if prev_ctx is not None and "_saved_tracker_state" in prev_ctx:
                saved = prev_ctx.pop("_saved_tracker_state")
                self._fallback_tracker._broken_eos = saved["broken_eos"]
                self._fallback_tracker._broken_solvers = saved["broken_solvers"]
                self._fallback_tracker._nonconverged_solvers = saved["nonconverged_solvers"]
                self._fallback_tracker.eos_chain_log = saved["eos_chain_log"]
                self._fallback_tracker.solver_chain_log = saved["solver_chain_log"]
            self._run_tracking.context = prev_ctx
        else:
            self._run_tracking.context = None

        if not context:
            return {
                "fallback_used": False,
                "fallback_call_count": 0,
                "fallback_state_count": 0,
                "fallback_states": [],
                "solver_nonconverged": nonconverged,
            }

        return {
            "fallback_used": context["fallback_calls"] > 0,
            "fallback_call_count": context["fallback_calls"],
            "fallback_state_count": len(context["fallback_events"]),
            "fallback_states": list(context["fallback_events"].values()),
            "solver_nonconverged": nonconverged,
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
        elif eos_method == 'neqsim':
            return self._solve_neqsim(P_pa, T_k, gas_obj)
        else:
            raise ValueError(f"Desteklenmeyen EOS: {eos_method}")
        
    def get_properties(self, P_pa: float, T_k: float, gas_obj, eos_method: str, *, eos_chain=None) -> ThermodynamicState:
        """
        Giriş basınç ve sıcaklığına bağli olarak durumu çözer. Cache mimarisi kullanir.
        gas_obj: Eğer coolprop ise string, thermo ise dict objesidir (mixture.py tarafindan uretilir)
        
        eos_chain: Opsiyonel EosChain objesi. Verilirse akilli EOS fallback zinciri kullanilir.
        """
        chain = eos_chain or self._active_eos_chain
        effective_eos = eos_method
        effective_gas_obj = gas_obj
        if chain is not None:
            if chain._locked_eos is not None:
                effective_eos = chain._locked_eos
                effective_gas_obj = chain._build_gas_obj(effective_eos)
            elif chain._tracker.is_eos_broken(eos_method):
                effective_eos = None

        cache_key = (
            self._build_cache_key(P_pa, T_k, effective_gas_obj, effective_eos)
            if effective_eos is not None
            else None
        )

        if cache_key is not None:
            cached_state = self._get_cached_state(cache_key, P_pa, T_k, effective_eos)
            if cached_state is not None:
                if chain is not None and chain._locked_eos is None:
                    chain._locked_eos = effective_eos
                return cached_state

        self._record_cache_miss()

        # Aktif EosChain varsa (parametre veya global) akilli fallback kullan
        if chain is not None:
            state = chain.get_properties(P_pa, T_k, eos_method)
            if cache_key is None and chain._locked_eos is not None:
                cache_key = self._build_cache_key(
                    P_pa, T_k, chain._build_gas_obj(chain._locked_eos), chain._locked_eos
                )
        else:
            # Geriye donuk uyumlu: direkt dispatch + PR/SRK fallback + ideal gaz son care
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
                        "⚠️ %s EOS hatasi: %s. Alternatif EOS fallback deneniyor.",
                        eos_method.upper(),
                        e,
                    )
                    state = self._solve_fallback(P_pa, T_k, gas_obj, eos_method)
                    state.raw_props.setdefault('fallback_reason', str(e))
            
        # Z-Factor Uyarısı ve Teşhis Entegrasyonu
        thermo_health = state.raw_props.get('thermo_health', "HEALTHY")
        health_reasons = list(state.raw_props.get('health_reasons', []) or [])
        if state.Z < 0.5:
            if thermo_health == "HEALTHY":
                thermo_health = "WARNING"
            health_reasons.append(f"Düşük sıkıştırılabilirlik faktörü Z={state.Z:.4f} (yoğuşma riski)")
            logger.warning(f"⚠️ Olağandışı düşük Z faktörü: {state.Z:.4f} (P={P_pa/1e5:.1f} bar, T={T_k-273.15:.1f}°C)")
        elif state.Z > 1.5:
            if thermo_health == "HEALTHY":
                thermo_health = "WARNING"
            health_reasons.append(f"Beklenmedik yüksek sıkıştırılabilirlik faktörü Z={state.Z:.4f}")
            logger.warning(f"⚠️ Olağandışı yüksek Z faktörü: {state.Z:.4f} (P={P_pa/1e5:.1f} bar, T={T_k-273.15:.1f}°C)")
        
        if state.phase in ('liquid', 'two-phase', 'supercritical'):
            thermo_health = "CRITICAL"
            health_reasons.append("Akışkan sıvı, iki faz veya yoğun süperkritik bölgeye girdi (faz ayrışması riski)")

        # Fallback/ideal yaklasimla uretilen durumlar saglikta isaretlenir (P0-5)
        if state.raw_props.get('fallback', False):
            if thermo_health == "HEALTHY":
                thermo_health = "WARNING"
            layer = state.raw_props.get('fallback_layer', 'fallback')
            fb_msg = f"Sonuç fallback/ideal yaklaşım ile üretildi ({layer}); gerçek EOS kullanılmadı."
            if fb_msg not in health_reasons:
                health_reasons.append(fb_msg)

        state.raw_props['thermo_health'] = thermo_health
        state.raw_props['health_reasons'] = health_reasons

        # Fallback durumlari onbellege yazilmaz: aksi halde sonraki run'da istenen EOS
        # fallback sonucunu yanlislikla geri alabilir (P0-5).
        if not state.raw_props.get('fallback', False):
            self._store_cached_state(cache_key, state)
        self._record_run_tracking(P_pa, T_k, eos_method, state)
            
        return state

    @staticmethod
    def _parse_composition_from_gas_obj(gas_obj) -> dict[str, float]:
        """Extract canonical KASP component -> mole fraction mapping from str or dict."""
        from kasp.core.mixture import GasMixtureBuilder
        from kasp.core.constants import SUPPORTED_GASES

        comp_map = getattr(GasMixtureBuilder, "COMPONENT_MAP", SUPPORTED_GASES)
        rev_supported = {v.lower(): k for k, v in comp_map.items()}
        rev_thermo = GasMixtureBuilder.REVERSE_THERMO_ID_MAP
        rev_neqsim = {v.lower(): k for k, v in GasMixtureBuilder.NEQSIM_COMPONENT_MAP.items()}

        def _resolve_canonical(raw_name: str) -> str:
            low = str(raw_name).strip().lower()
            if low in rev_supported:
                return rev_supported[low]
            if low in rev_thermo:
                return rev_thermo[low]
            if low in rev_neqsim:
                return rev_neqsim[low]
            return normalize_component(str(raw_name))

        fractions: dict[str, float] = {}
        if isinstance(gas_obj, str):
            raw_str = gas_obj.strip()
            if "::" in raw_str:
                raw_str = raw_str.split("::", 1)[1]
            for part in raw_str.split("&"):
                part = part.strip()
                if not part:
                    continue
                if "[" in part and part.endswith("]"):
                    name, frac_str = part[:-1].split("[", 1)
                    frac = float(frac_str)
                else:
                    name = part
                    frac = 1.0
                if frac > 0:
                    canon = _resolve_canonical(name)
                    fractions[canon] = fractions.get(canon, 0.0) + frac
        elif isinstance(gas_obj, dict):
            ids = gas_obj.get("ids", gas_obj.get("IDs"))
            zs = gas_obj.get("mol_fractions", gas_obj.get("zs"))
            if ids is not None and zs is not None and len(ids) == len(zs):
                for cid, frac in zip(ids, zs):
                    f_val = float(frac)
                    if f_val > 0:
                        canon = _resolve_canonical(str(cid))
                        fractions[canon] = fractions.get(canon, 0.0) + f_val
            else:
                for k, v in gas_obj.items():
                    if k in ("MW", "ids", "IDs", "mol_fractions", "zs"):
                        continue
                    try:
                        f_val = float(v)
                    except (TypeError, ValueError):
                        continue
                    if f_val > 0:
                        canon = _resolve_canonical(str(k))
                        fractions[canon] = fractions.get(canon, 0.0) + f_val

        total = sum(fractions.values())
        if total > 0:
            fractions = {k: v / total for k, v in fractions.items()}
        return fractions

    def _coerce_thermo_gas_data(self, gas_obj) -> dict | None:
        if isinstance(gas_obj, dict):
            ids = gas_obj.get("ids", gas_obj.get("IDs"))
            zs = gas_obj.get("mol_fractions", gas_obj.get("zs"))
            if ids and zs and len(ids) == len(zs):
                return gas_obj
        try:
            from kasp.core.mixture import GasMixtureBuilder
            fractions = self._parse_composition_from_gas_obj(gas_obj)
            if fractions:
                return GasMixtureBuilder.build_thermo_data(fractions)
        except Exception as exc:
            logger.debug("Failed to coerce gas_obj to thermo data: %s", exc)
        return None

    def infer_mw_g_mol(self, gas_obj) -> float | None:
        if isinstance(gas_obj, dict):
            mw = gas_obj.get("MW")
            if mw is not None:
                try:
                    return float(mw)
                except (TypeError, ValueError) as exc:
                    logger.debug("Invalid MW value in gas_obj: %s", exc)

        try:
            fractions = self._parse_composition_from_gas_obj(gas_obj)
            if fractions:
                mw_calc = sum(
                    frac * MOLAR_MASSES[comp]
                    for comp, frac in fractions.items()
                    if comp in MOLAR_MASSES
                )
                if mw_calc > 0:
                    return mw_calc
        except Exception as exc:
            logger.debug("Failed to infer MW from gas_obj: %s", exc)

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
        with self._as_lock:
            if pkg_key not in self._package_cache:
                constants, properties = ChemicalConstantsPackage.from_IDs(ids)
                self._package_cache[pkg_key] = (constants, properties)
            return self._package_cache[pkg_key]

    def _get_coolprop_abstract_state(self, mixture_string: str):
        """CoolProp AbstractState cache — karışım başına bir kez oluşturulur."""
        with self._as_lock:
            if mixture_string not in self._package_cache:
                try:
                    from CoolProp import AbstractState
                    AS = AbstractState("HEOS", mixture_string)
                    try:
                        AS.build_phase_envelope("")
                    except Exception as e:
                        logger.debug("Phase envelope build failed for %s: %s", mixture_string, e)
                    self._package_cache[mixture_string] = AS
                except ImportError:
                    self._package_cache[mixture_string] = None
            return self._package_cache.get(mixture_string)

    def _get_coolprop_phase(self, mixture_string: str, P_pa: float, T_k: float) -> str | None:
        """AbstractState.phase() ile güvenilir faz tespiti, karışımlarda faz zarfını yönetir."""
        try:
            with self._as_lock:
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
        except Exception as exc:
            logger.debug("CoolProp phase detection failed: %s", exc)
            return None

    def _solve_coolprop(self, P_pa: float, T_k: float, mixture_string: str) -> ThermodynamicState:
        """CoolProp HEOS motorunu kullanarak özellikleri çözer."""
        if not COOLPROP_LOADED:
            raise ImportError("CoolProp kütüphanesi aktif değil.")
        if P_pa <= 0 or T_k <= 0:
            raise ValueError(f"Geçersiz basınç veya sıcaklık: P={P_pa}, T={T_k}")
            
        H = CP.PropsSI('Hmass', 'P', P_pa, 'T', T_k, mixture_string)
        S = CP.PropsSI('Smass', 'P', P_pa, 'T', T_k, mixture_string)
        Z = CP.PropsSI('Z', 'P', P_pa, 'T', T_k, mixture_string)
        D = CP.PropsSI('Dmass', 'P', P_pa, 'T', T_k, mixture_string)
        a = CP.PropsSI('A', 'P', P_pa, 'T', T_k, mixture_string)
        Cp = CP.PropsSI('Cpmass', 'P', P_pa, 'T', T_k, mixture_string)
        Cv = CP.PropsSI('Cvmass', 'P', P_pa, 'T', T_k, mixture_string)
        k = Cp / Cv if Cv > 0 else 1.4
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
        if P_pa <= 0 or T_k <= 0:
             raise ValueError(f"Geçersiz basınç veya sıcaklık: P={P_pa}, T={T_k}")
             
        if not isinstance(gas_data, dict) or ("ids" not in gas_data and "IDs" not in gas_data):
            coerced = self._coerce_thermo_gas_data(gas_data)
            if coerced is not None:
                gas_data = coerced
        ids, zs = self._extract_thermo_components(gas_data)
        constants, properties = self._get_thermo_package(ids)
        
        MW_g_mol = sum(zs[i] * constants.MWs[i] for i in range(len(zs)))
        molar_mass = MW_g_mol / 1000.0  # kg/mol
        
        EOS_CLASS = PRMIX if eos_method == 'pr' else SRKMIX
        # PR/SRK ikili etkileşim katsayıları (kij) — literatür tablosundan.
        kijs = _build_kij_matrix(ids)
        missing_risky_pairs = _check_missing_kij_pairs(ids, kijs)
        if missing_risky_pairs:
            # Yüksek-sapma riskli bileşen içeren çift(ler)de kij=0 varsa kullanıcıyı uyar
            logger.warning(
                "PR/SRK kij=0 kullanılıyor ancak yüksek-sapma riskli çift(ler) mevcut: %s. "
                "Z/entalpi belirsizliği artabilir.",
                ", ".join(sorted(missing_risky_pairs)),
            )
        eos_kwargs = dict(
            T=T_k, P=P_pa,
            Tcs=constants.Tcs, Pcs=constants.Pcs,
            omegas=constants.omegas, zs=zs
        )
        if kijs is not None:
            eos_kwargs["kijs"] = kijs
        eos = EOS_CLASS(**eos_kwargs)
        
        # Z Factor Fallback and V_m
        phase_str = 'gas'
        internal_fallback = False
        Z_g_raw = getattr(eos, 'Z_g', None)
        Z_l_raw = getattr(eos, 'Z_l', None)
        
        if Z_g_raw is not None and Z_g_raw > 0 and Z_l_raw is not None and Z_l_raw > 0:
            eos_phase = getattr(eos, 'phase', 'g')
            g_dep_g = getattr(eos, 'G_dep_g', None)
            g_dep_l = getattr(eos, 'G_dep_l', None)
            if eos_phase == 'l' or (
                g_dep_l is not None and g_dep_g is not None and g_dep_l < g_dep_g
            ):
                Z = Z_l_raw
                V_m = eos.V_l
                phase_str = 'liquid'
            else:
                Z = Z_g_raw
                V_m = eos.V_g
                phase_str = 'gas'
        elif Z_g_raw is not None and Z_g_raw > 0:
            Z = Z_g_raw
            V_m = eos.V_g  
        elif Z_l_raw is not None and Z_l_raw > 0:
            Z = Z_l_raw
            V_m = eos.V_l
            phase_str = 'liquid'
        else:
            # PR/SRK kokleri bulunamadi: ideal hacim yaklasimi (izlenebilirlik icin isaretlenir)
            Z = 1.0
            V_m = 8.314462 * T_k / P_pa
            phase_str = 'ideal'
            internal_fallback = True

        # Süperkritik faz kontrolü (backend faz yetkisi ve psödo-kritik denetim)
        eos_phase = getattr(eos, 'phase', None)
        if eos_phase in ('s', 'supercritical'):
            phase_str = 'supercritical'
        elif not internal_fallback and phase_str != 'liquid':
            try:
                tc_pseudo = sum(zs[i] * constants.Tcs[i] for i in range(len(zs)))
                pc_pseudo = sum(zs[i] * constants.Pcs[i] for i in range(len(zs)))
                if T_k > tc_pseudo and P_pa > pc_pseudo:
                    phase_str = 'supercritical'
            except Exception:
                pass
            
        D = molar_mass / V_m  # kg/m³
        
        # Heat Capacities (Ideal + Departure)
        Cp_ig_molar = sum(
            zs[i] * properties.HeatCapacityGases[i](T_k) for i in range(len(zs))
        )
        Cv_ig_molar = Cp_ig_molar - 8.314462

        def _read_dep(prefix: str) -> float:
            if phase_str == 'liquid':
                val = getattr(eos, f"{prefix}_l", None)
                if val is None:
                    val = getattr(eos, f"{prefix}_g", None)
            else:
                val = getattr(eos, f"{prefix}_g", None)
                if val is None:
                    val = getattr(eos, f"{prefix}_l", None)
            return float(val) if val is not None and math.isfinite(val) else 0.0

        cp_dep = _read_dep("Cp_dep")
        cv_dep = _read_dep("Cv_dep")
        h_dep = _read_dep("H_dep")
        s_dep = _read_dep("S_dep")
        
        Cp_real = (Cp_ig_molar + cp_dep) / molar_mass
        Cv_real = (Cv_ig_molar + cv_dep) / molar_mass
        k = Cp_real / Cv_real if Cv_real > 0 else 1.4
        
        # Enthalpy & Entropy (cached integrals for performance)
        T_ref = 298.15
        T_rounded = round(float(T_k), 5)
        H_ig_molar = 0.0
        S_ig_molar = 0.0
        log_p_ref = math.log(P_pa / 101325.0)
        with self._cache_lock:
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
        
        H = (H_ig_molar + h_dep) / molar_mass
        S = (S_ig_molar + s_dep) / molar_mass

        speed_of_sound = None
        try:
            if phase_str == 'liquid':
                speed_of_sound = getattr(eos, 'speed_of_sound_l', None)
                if (speed_of_sound is None or speed_of_sound <= 0) and hasattr(eos, 'dP_dV_l'):
                    dp_dv = getattr(eos, 'dP_dV_l', None)
                    if dp_dv is not None and dp_dv < 0 and V_m > 0 and molar_mass > 0 and Cv_real > 0:
                        speed_of_sound = math.sqrt((Cp_real / Cv_real) * (-dp_dv) * (V_m ** 2) / molar_mass)
            else:
                speed_of_sound = getattr(eos, 'speed_of_sound_g', None)
                if (speed_of_sound is None or speed_of_sound <= 0) and hasattr(eos, 'dP_dV_g'):
                    dp_dv = getattr(eos, 'dP_dV_g', None)
                    if dp_dv is not None and dp_dv < 0 and V_m > 0 and molar_mass > 0 and Cv_real > 0:
                        speed_of_sound = math.sqrt((Cp_real / Cv_real) * (-dp_dv) * (V_m ** 2) / molar_mass)
        except Exception as e:
            logger.debug("Speed of sound calculation error: %s", e)

        state = self._build_state(
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
            fallback=internal_fallback,
            speed_of_sound=speed_of_sound,
        )
        if missing_risky_pairs:
            state.raw_props.setdefault("health_reasons", []).append(
                f"missing_kij({', '.join(sorted(missing_risky_pairs))})"
            )
            if state.raw_props.get("thermo_health") not in ("CRITICAL", "WARNING"):
                state.raw_props["thermo_health"] = "WARNING"
        if internal_fallback:
            self._tag_internal_fallback(state, "eos_roots_unavailable")
        return state

    @staticmethod
    def _tag_internal_fallback(state, reason):
        state.raw_props["fallback"] = True
        state.raw_props["fallback_layer"] = "internal"
        state.raw_props["fallback_reason"] = reason
        return state

    def _solve_aga8(self, P_pa: float, T_k: float, gas_data: dict) -> ThermodynamicState:
        """AGA8-DC92 Detail (ISO 12213-2) standardını kullanarak özellikleri çözer.

        Not: pyaga8.Detail/Composition AGA8-DC92 (Starling-Savidge 1992) metodudur;
        GERG-2008 (Kunz-Wagner 2012) farklı korelasyondur — isimlendirme buna göre düzeltildi.
        Geçerlilik penceresi (yakl. T=143–473 K, P≤30 MPa, doğalgaz kompozisyonu) dışında
        çağrıldığında uyarı üretilir.
        """
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

        aga8_warnings = []
        if not (143.0 <= T_k <= 473.0):
            msg = f"AGA8-DC92 (ISO 12213-2) sıcaklık aralığı dışı: T={T_k:.1f} K (önerilen 143–473 K). Sonuç ekstrapole."
            logger.warning(msg)
            aga8_warnings.append(msg)
        if detail.pressure > 30.0:
            msg = f"AGA8-DC92 (ISO 12213-2) basınç aralığı dışı: P={detail.pressure:.1f} MPa (önerilen ≤30 MPa). Sonuç ekstrapole."
            logger.warning(msg)
            aga8_warnings.append(msg)
        
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
            
        state = self._build_state(
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
        if aga8_warnings:
            state.raw_props.setdefault("health_reasons", []).extend(aga8_warnings)
            state.raw_props["thermo_health"] = "WARNING"
        return state

    def _get_thermopack_eos(self, tp_components_tuple, eos_model='PR'):
        cache_key = (tp_components_tuple, eos_model)
        with self._as_lock:
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
        
        reverse_map = GasMixtureBuilder.REVERSE_THERMO_ID_MAP
        
        tp_ids = []
        for component_id in ids:
            canonical = reverse_map.get(str(component_id).lower(), str(component_id).upper())
            tp_id = THERMOPACK_MAPPING.get(canonical, canonical)
            tp_ids.append(tp_id)
            
        eos = self._get_thermopack_eos(tuple(tp_ids), 'PR')
        
        # Calculate specific volume and phase
        internal_fallback = False
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
                internal_fallback = True
                
        # Calculate MW and density
        MW_g_mol = sum(zs[i] * MOLAR_MASSES[reverse_map.get(str(ids[i]).lower(), str(ids[i]).upper())] for i in range(len(zs)))
        molar_mass = MW_g_mol / 1000.0 # kg/mol
        
        density = molar_mass / v # kg/m^3
        Z = P_pa * v / (8.314462 * T_k)
        
        # Enthalpy and entropy
        thermo_phase_arg = eos.VAPPH if phase_str in ('gas', 'ideal') else eos.LIQPH
        h_molar, cp_molar = eos.enthalpy(T_k, P_pa, zs, thermo_phase_arg, dhdt=True)
        H = h_molar / molar_mass
        Cp = cp_molar / molar_mass
        
        s_molar, = eos.entropy(T_k, P_pa, zs, thermo_phase_arg)
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
            
        state = self._build_state(
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
            fallback=internal_fallback,
            speed_of_sound=speed_of_sound
        )
        if internal_fallback:
            self._tag_internal_fallback(state, "thermopack_ideal_volume")
        return state

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
        
        reverse_map = GasMixtureBuilder.REVERSE_THERMO_ID_MAP
        
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
        """Kütüphane başarısız olduğunda PR/SRK denenir, sonra ideal gaz yaklaşımı."""
        orig_p_pa = float(P_pa) if P_pa is not None else 0.0
        orig_t_k = float(T_k) if T_k is not None else 0.0
        unphysical_pt = (
            orig_p_pa <= 0
            or orig_t_k <= 0
            or not math.isfinite(orig_p_pa)
            or not math.isfinite(orig_t_k)
        )

        # Önce PR ve SRK ile tekrar dene (fallback zincirinde, aynı eos hariç)
        if not unphysical_pt:
            thermo_gas_data = self._coerce_thermo_gas_data(gas_obj)
            if thermo_gas_data is not None:
                for fallback_eos in (m for m in ('pr', 'srk') if m != eos):
                    try:
                        state = self._solve_thermo_eos(P_pa, T_k, thermo_gas_data, fallback_eos)
                        state.raw_props['fallback'] = True
                        state.raw_props['fallback_layer'] = 'eos'
                        state.raw_props['fallback_from'] = eos
                        state.raw_props['fallback_to'] = fallback_eos
                        state.raw_props['fallback_type'] = f'{fallback_eos}_fallback'
                        return state
                    except Exception as e:
                        logger.debug("Fallback EOS %s failed: %s", fallback_eos, e)

        # PR/SRK da başarısız -> ideal gaz (son çare)
        P_pa = max(orig_p_pa if math.isfinite(orig_p_pa) else 1.0, 1.0)
        T_k = max(orig_t_k if math.isfinite(orig_t_k) else 1.0, 1.0)

        mw_g_mol = self.infer_mw_g_mol(gas_obj)
        M_kg_mol = (mw_g_mol / 1000.0) if mw_g_mol else 0.02896
        
        R_specific = R_UNIVERSAL_J_MOL_K / M_kg_mol
        
        # 1. Gaz kompozisyonunu ve Thermo/CoolProp yapısını çözümle
        ids, zs = [], []
        coerced = self._coerce_thermo_gas_data(gas_obj)
        if coerced is not None:
            ids = coerced.get("ids", coerced.get("IDs", []))
            zs = coerced.get("mol_fractions", coerced.get("zs", []))
        elif isinstance(gas_obj, dict):
            ids = gas_obj.get("ids", gas_obj.get("IDs", []))
            zs = gas_obj.get("mol_fractions", gas_obj.get("zs", []))

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
            except Exception as e:
                logger.debug("Thermo Cp calculation failed: %s", e)
                
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
            except Exception as e:
                logger.debug("Standard Cp calculation failed: %s", e)

        # C) Eğer her şey başarısız olursa eski doğrusal formül
        if Cp_ideal == 1000.0 or Cp_ideal <= 0:
            Cp_ideal = max(200.0, 1000 + 0.1 * (T_k - 273.15))
        
        Cv_ideal = Cp_ideal - R_specific
        k_ideal = Cp_ideal / Cv_ideal if Cv_ideal > 0 else 1.4
        
        Z_ideal = max(0.5, min(1.5, 1.0 - 0.1 * (P_pa / (STD_PRESS_PA * 10))))
        rho_ideal = P_pa / (R_specific * T_k * Z_ideal) if T_k > 0 and R_specific > 0 else 1.0
        
        H_ideal = Cp_ideal * (T_k - 298.15)
        # S referansı da H ile aynı olmalı (T_ref=298.15 K, P_ref=STD_PRESS_PA → S=0).
        # Önceki log(T/273.15) paydası PR yoluyla ~Cp·ln(298.15/273.15)≈90 J/kgK süreksizlik yaratıyordu.
        S_ideal = Cp_ideal * math.log(T_k / 298.15) - R_specific * math.log(P_pa / STD_PRESS_PA) if T_k > 0 else 0
        
        state = self._build_state(
            P_pa=P_pa,
            T_k=T_k,
            H=H_ideal,
            S=S_ideal,
            Z=Z_ideal,
            k=max(1.2, min(1.67, k_ideal)),
            MW=M_kg_mol * 1000,
            Cp=Cp_ideal,
            Cv=Cv_ideal if Cv_ideal > 0 else Cp_ideal / 1.4,
            density=max(0.1, rho_ideal),
            phase='ideal_fallback',
            fallback=True,
            speed_of_sound=self._speed_of_sound(k_ideal, P_pa, max(rho_ideal, 0.1)),
        )
        if unphysical_pt:
            state.raw_props["thermo_health"] = "CRITICAL"
            state.raw_props.setdefault("health_reasons", []).append(
                f"unphysical_pt(P_pa={orig_p_pa}, T_k={orig_t_k})"
            )
        return state
        
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
            except Exception as e:
                logger.debug("DWSIM assembly reference failed: %s", e)
                
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
        reverse_map = GasMixtureBuilder.REVERSE_THERMO_ID_MAP
        
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
        with self._as_lock:
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

    # ─────────────────────────────────────────────────────────────────────────
    # NeqSim (Java/JVM) Köprüsü — Lazy Loading
    # ─────────────────────────────────────────────────────────────────────────

    def _load_neqsim(self) -> bool:
        """NeqSim Java kütüphanesini yükler — PyInstaller bundle uyumlu."""
        if hasattr(self, "_neqsim_loaded"):
            return self._neqsim_loaded

        self._neqsim_loaded = False
        self._neqsim_jvm_started = False

        try:
            import jpype
            import jpype.imports
        except ImportError as e:
            logger.debug("jpype1 yüklü değil: %s", e)
            return False

        try:
            import sys
            import os

            # JVM zaten başlatılmış mı?
            if not jpype.isJVMStarted():
                jar_candidates = [
                    os.path.join(getattr(sys, "_MEIPASS", ""), "neqsim.jar"),
                    os.path.join(getattr(sys, "_MEIPASS", ""), "kasp", "core", "libs", "neqsim.jar"),
                    os.path.join(os.path.dirname(os.path.abspath(__file__)), "libs", "neqsim.jar"),
                    os.path.join(os.path.abspath("."), "kasp", "core", "libs", "neqsim.jar"),
                    os.path.join(os.path.abspath("."), "neqsim.jar"),
                ]

                jar_path = None
                for candidate in jar_candidates:
                    if candidate and os.path.exists(candidate):
                        jar_path = candidate
                        break

                if jar_path is None:
                    logger.debug("neqsim.jar bulunamadı, arama yolları: %s", jar_candidates)
                    return False

                # JVM argümanları - classpath kwarg sona gelmeli
                jpype.startJVM(
                    "-Xms128m",
                    "-Xmx512m",
                    "-Djava.awt.headless=true",
                    classpath=[jar_path],
                )
                self._neqsim_jvm_started = True
                logger.info("JVM NeqSim için başlatıldı: %s", jar_path)

            # NeqSim sınıflarını jpype JClass ile yükle
            self._neqsim_SystemSrkCPA = jpype.JClass("neqsim.thermo.system.SystemSrkCPA")
            self._neqsim_SystemSrkEos = jpype.JClass("neqsim.thermo.system.SystemSrkEos")
            self._neqsim_SystemPrEos = jpype.JClass("neqsim.thermo.system.SystemPrEos")
            # PhaseInterface opsiyonel, JPackage ile doğrula
            try:
                self._neqsim_PhaseInterface = jpype.JClass("neqsim.thermo.phase.PhaseInterface")
            except Exception as e:
                logger.debug("NeqSim PhaseInterface yüklenemedi: %s", e)
                self._neqsim_PhaseInterface = None

            self._neqsim_loaded = True
            logger.info("🎉 NeqSim (Java) başarıyla yüklendi!")
            return True

        except Exception as e:
            logger.warning(f"⚠️ NeqSim yükleme hatası: {e}")
            self._neqsim_loaded = False
            return False

    def _neqsim_available(self) -> bool:
        """NeqSim kullanım için hazır mı?"""
        if not hasattr(self, "_neqsim_loaded"):
            return self._load_neqsim()
        return self._neqsim_loaded

    def _solve_neqsim(self, P_pa: float, T_k: float, gas_data: dict) -> ThermodynamicState:
        """NeqSim (CPA/SRK/PR) kullanarak özellikleri çözer."""
        if not self._load_neqsim():
            raise RuntimeError("NeqSim (Java/JVM) yüklenemedi. jpype1 ve neqsim.jar gereklidir.")

        from kasp.core.mixture import GasMixtureBuilder

        # NeqSim girdisi: gas_data zaten neqsim dict ise doğrudan kullan, yoksa çevir
        if isinstance(gas_data, dict) and gas_data and all(k in GasMixtureBuilder.NEQSIM_COMPONENT_MAP.values() for k in gas_data.keys() if isinstance(k, str)):
            # gas_data zaten {"methane": 0.9, ...} formunda
            neqsim_comp = gas_data
        elif isinstance(gas_data, dict) and "ids" in gas_data:
            # thermo_data -> composition_fraction -> neqsim
            from kasp.core.constants import normalize_component as _norm
            # ids/mol_fractions -> canonical composition
            ids = gas_data.get("ids", gas_data.get("IDs", []))
            zs = gas_data.get("mol_fractions", gas_data.get("zs", []))
            comp_frac = {}
            reverse_map = GasMixtureBuilder.REVERSE_THERMO_ID_MAP
            for cid, z in zip(ids, zs):
                canonical = reverse_map.get(str(cid).lower(), str(cid).upper())
                comp_frac[canonical] = comp_frac.get(canonical, 0) + float(z)
            neqsim_comp = GasMixtureBuilder.build_neqsim_input(comp_frac)
        else:
            neqsim_comp = GasMixtureBuilder.build_neqsim_input(gas_data)

        # EOS seçimi: varsayılan SRK-CPA (polar bileşenler için), PR/SRK opsiyonel
        eos_class = self._neqsim_SystemSrkCPA

        system = eos_class(float(T_k), float(P_pa / 1e5))
        for comp_name, mol_frac in neqsim_comp.items():
            system.addComponent(comp_name, float(mol_frac))
        try:
            # NeqSim mixing rule 2 = klasik van der Waals one-fluid (kij tabanlı).
            # CPA (SystemSrkCPA) için kullanılan standart kuraldır; alternatif (örn. Huron-Vidal)
            # gerekirse bu değer konfigüre edilmelidir.
            system.setMixingRule(2)
        except Exception as e:
            logger.warning("NeqSim setMixingRule(2) başarısız; varsayılan mixing rule ile devam: %s", e)
        system.init(0)
        system.init(1)

        # Yakınsama kontrolü — yakınsamadıysa sonuç güvenilmez, açıkça uyar
        neqsim_solved = True
        try:
            if hasattr(system, "isSolved") and not system.isSolved():
                neqsim_solved = False
                logger.warning("NeqSim TP-flash yakınsamadı (isSolved=False); sonuç belirsiz.")
        except Exception as e:
            logger.debug("NeqSim convergence check skipped: %s", e)

        # Gaz fazını seç (varsa), yoksa ilk faz
        try:
            nph = system.getNumberOfPhases()
            phase = None
            for i in range(nph):
                p = system.getPhase(i)
                if p.getPhaseTypeName().lower() in ("gas", "vapour", "vapor"):
                    phase = p
                    break
            if phase is None:
                phase = system.getPhase(0)
        except Exception as e:
            logger.debug("NeqSim phase selection fallback: %s", e)
            phase = system.getPhase(0)

        molar_mass = float(phase.getMolarMass())  # kg/mol
        # NeqSim: getEnthalpy/getEntropy/getCp molar (J/mol) -> mass basis
        H_molar = float(phase.getEnthalpy())
        S_molar = float(phase.getEntropy())
        Cp_molar = float(phase.getCp())
        Cv_molar = float(phase.getCv())
        # mass basis
        H = H_molar / molar_mass if molar_mass > 0 else H_molar * 1000.0
        S = S_molar / molar_mass if molar_mass > 0 else S_molar * 1000.0
        Cp = Cp_molar / molar_mass if molar_mass > 0 else Cp_molar
        Cv = Cv_molar / molar_mass if molar_mass > 0 else Cv_molar

        density = float(phase.getDensity())
        Z = float(phase.getZ())
        MW = molar_mass * 1000.0  # g/mol
        k = Cp / Cv if Cv > 0 else 1.4
        try:
            speed_of_sound = float(phase.getSpeedOfSound())
        except Exception as e:
            logger.debug("NeqSim speedOfSound fallback: %s", e)
            speed_of_sound = self._speed_of_sound(k, P_pa, max(density, 0.1))
        try:
            mu_val = float(phase.getViscosity())
        except Exception as e:
            logger.debug("NeqSim viscosity fallback: %s", e)
            mu_val = 1.1e-5

        phase_str = 'gas'
        try:
            pt = phase.getPhaseTypeName().lower()
            if "oil" in pt or "liquid" in pt:
                phase_str = 'liquid'
            elif "gas" in pt or "vapor" in pt or "vapour" in pt:
                phase_str = 'gas'
        except Exception as e:
            logger.debug("NeqSim phase type name check failed: %s", e)

        state = self._build_state(
            P_pa=P_pa,
            T_k=T_k,
            H=H,
            S=S,
            Z=Z,
            k=k,
            MW=MW,
            Cp=Cp,
            Cv=Cv,
            density=density,
            phase=phase_str,
            fallback=False,
            speed_of_sound=speed_of_sound,
            mu=mu_val
        )
        if not neqsim_solved:
            state.raw_props["thermo_health"] = "CRITICAL"
            state.raw_props.setdefault("health_reasons", []).append("neqsim_tp_flash_not_solved")
        return state

