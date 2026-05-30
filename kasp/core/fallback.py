"""Akilli Fallback Mekanizmasi — EOS, Solver ve Metot katmanlarinda zincirleme fallback.

EosChain:      Kullanici EOS'u → thermopack → pr → srk → aga8 → ideal gaz
SolverChain:   CoolProp flash → fd_nr → aj_nr → brent → k-tabanli formul
"""

from __future__ import annotations

import logging
from typing import Any

from kasp.core.mixture import GasMixtureBuilder

logger = logging.getLogger(__name__)

FALLBACK_EOS_ORDER = ["thermopack", "pr", "srk", "aga8"]
FALLBACK_SOLVER_ORDER = ["fd_nr", "aj_nr", "brent"]


class FallbackTracker:
    """Run bazinda fallback durumunu izler. begin_run_tracking ile sifirlanir."""

    def __init__(self):
        self._broken_eos: dict[str, str] = {}
        self._broken_solvers: set[str] = set()
        self.eos_chain_log: list[dict[str, str]] = []
        self.solver_chain_log: list[dict[str, str]] = []

    def reset(self):
        self._broken_eos.clear()
        self._broken_solvers.clear()
        self.eos_chain_log.clear()
        self.solver_chain_log.clear()

    def mark_eos_broken(self, eos: str, reason: str = ""):
        self._broken_eos[eos] = reason

    def is_eos_broken(self, eos: str) -> bool:
        return eos in self._broken_eos

    def eos_broken_reason(self, eos: str) -> str:
        return self._broken_eos.get(eos, "")

    def mark_solver_broken(self, solver: str):
        self._broken_solvers.add(solver)

    def is_solver_broken(self, solver: str) -> bool:
        return solver in self._broken_solvers

    def log_eos_fallback(self, from_eos: str, to_eos: str, reason: str):
        entry = {"from": from_eos, "to": to_eos, "reason": reason}
        if not self.eos_chain_log or self.eos_chain_log[-1] != entry:
            self.eos_chain_log.append(entry)

    def log_solver_fallback(self, from_solver: str, to_solver: str, reason: str):
        entry = {"from": from_solver, "to": to_solver, "reason": reason}
        self.solver_chain_log.append(entry)


class EosChainBrokenError(Exception):
    """EosChain lock-in sonrasi kilitli EOS'un calismamasi durumunda firlatilir."""
    pass


class EosChain:
    """Akilli EOS fallback zinciri.

    Zincir: preferred_eos → thermopack → pr → srk → aga8 → ideal_gaz
    - Kirik EOS'lar atlanir (1 kez basarisiz = run boyunca isaretli)
    - Ilk calisan EOS kullanilir, sonrakiler denenmez
    - Stage lock-in: ilk basarili EOS kilitlenir, stage boyunca degismez
    - gas_obj formati her EOS icin otomatik donusturulur
    """

    def __init__(
        self,
        tracker: FallbackTracker,
        thermo_solver,
        *,
        raw_composition: dict[str, float],
    ):
        self._tracker = tracker
        self._solver = thermo_solver
        self._raw_composition = dict(raw_composition)
        self._gas_obj_cache: dict[str, Any] = {}
        self._comp_fractions: dict[str, float] | None = None
        self._locked_eos: str | None = None
        self._locked_fallback = False

    def _ensure_fractions(self) -> dict[str, float]:
        if self._comp_fractions is None:
            self._comp_fractions = GasMixtureBuilder.validate_and_normalize(
                self._raw_composition
            )
        return self._comp_fractions

    def _build_gas_obj(self, eos: str):
        if eos in self._gas_obj_cache:
            return self._gas_obj_cache[eos]

        fractions = self._ensure_fractions()
        if eos == "coolprop":
            go = GasMixtureBuilder.build_coolprop_string(fractions)
        elif eos in ("thermopack", "pr", "srk", "aga8", "ccp", "dwsim"):
            go = GasMixtureBuilder.build_thermo_data(fractions)
        else:
            go = GasMixtureBuilder.build_thermo_data(fractions)

        self._gas_obj_cache[eos] = go
        return go

    def reset_lock(self):
        """Yeni stage baslangicinda EOS kilitini kaldir."""
        self._locked_eos = None
        self._locked_fallback = False

    def get_properties(self, P_pa: float, T_k: float, preferred_eos: str):
        # Stage lock-in: kilitli EOS varsa direkt onu kullan
        if self._locked_eos is not None:
            if not self._tracker.is_eos_broken(self._locked_eos):
                go = self._build_gas_obj(self._locked_eos)
                return self._solver._dispatch(P_pa, T_k, go, self._locked_eos)
            # Kilitli EOS kirildi → hata firlat, stage yeniden baslatilsin
            raise EosChainBrokenError(
                f"Kilitli EOS ({self._locked_eos}) calismiyor: "
                f"{self._tracker.eos_broken_reason(self._locked_eos)}"
            )

        chain = [preferred_eos]
        for eos in FALLBACK_EOS_ORDER:
            if eos != preferred_eos:
                chain.append(eos)

        first_error = None
        for eos in chain:
            if self._tracker.is_eos_broken(eos):
                continue

            gas_obj = self._build_gas_obj(eos)
            try:
                state = self._solver._dispatch(P_pa, T_k, gas_obj, eos)

                # Ilk basarili EOS'u kilitle — stage boyunca degismez
                self._locked_eos = eos
                if eos != preferred_eos:
                    self._locked_fallback = True

                if eos != preferred_eos:
                    reason = str(first_error or self._tracker.eos_broken_reason(preferred_eos) or "")
                    if not self._tracker.eos_chain_log or self._tracker.eos_chain_log[-1].get("to") != eos:
                        logger.warning(
                            "🔄 [EOS fallback] %s → %s: %s kullanilamiyor. Sonraki EOS deneniyor.",
                            preferred_eos,
                            eos,
                            reason or "bilinmeyen hata",
                        )
                    state.raw_props["fallback"] = True
                    state.raw_props["fallback_layer"] = "eos"
                    state.raw_props["fallback_from"] = preferred_eos
                    state.raw_props["fallback_to"] = eos
                    state.raw_props["fallback_reason"] = reason
                    self._tracker.log_eos_fallback(preferred_eos, eos, reason)

                return state

            except Exception as exc:
                first_error = exc
                self._tracker.mark_eos_broken(eos, str(exc))
                logger.debug(
                    "EOS zinciri: %s basarisiz (%s). Sonraki EOS deneniyor.",
                    eos,
                    exc,
                )

        # Tum EOS'lar basarisiz → ideal gaz (son care)
        logger.warning(
            "🔶 [EOS fallback] Tum EOS'lar basarisiz. Son care: Ideal Gaz."
        )
        gas_obj = self._build_gas_obj(preferred_eos)
        state = self._solver._solve_fallback(P_pa, T_k, gas_obj, preferred_eos)
        state.raw_props["fallback"] = True
        state.raw_props["fallback_layer"] = "eos"
        state.raw_props["fallback_from"] = preferred_eos
        state.raw_props["fallback_to"] = "ideal_gas"
        state.raw_props["fallback_reason"] = str(first_error or "")
        self._tracker.log_eos_fallback(preferred_eos, "ideal_gas", str(first_error or ""))
        return state


class SolverChain:
    """Akilli cozucu fallback zinciri.

    Zincir: fd_nr → aj_nr → brent → k-tabanli formul
    - "auto" modda sirali dene
    - Kullanici secimi varsa sadece o denenir
    - Kirik cozuculer atlanir
    """

    def __init__(self, tracker: FallbackTracker):
        self._tracker = tracker

    def find_isentropic_temp(
        self,
        state_in,
        p_out: float,
        thermo_solver,
        gas_obj,
        eos: str,
        *,
        solver_method: str = "auto",
    ):
        from kasp.core.aerodynamics import CompressorAerodynamics

        if solver_method != "auto":
            return self._run_single(
                state_in, p_out, thermo_solver, gas_obj, eos, solver_method
            )

        first_error = None
        for method in FALLBACK_SOLVER_ORDER:
            if self._tracker.is_solver_broken(method):
                continue

            try:
                T = self._run_single(
                    state_in, p_out, thermo_solver, gas_obj, eos, method
                )
                if method != FALLBACK_SOLVER_ORDER[0]:
                    logger.warning(
                        "🔄 [Solver fallback] %s → %s: izentropik cozucu basarisiz. Sonraki deneniyor.",
                        FALLBACK_SOLVER_ORDER[0],
                        method,
                    )
                return T
            except Exception as exc:
                first_error = exc
                self._tracker.mark_solver_broken(method)
                logger.debug(
                    "Solver zinciri: %s basarisiz (%s). Sonraki deneniyor.",
                    method,
                    exc,
                )

        logger.warning(
            "🔶 [Solver fallback] Tum cozuculer basarisiz. Son care: k-tabanli formul."
        )
        self._tracker.log_solver_fallback("all", "k_formula", str(first_error or ""))
        return self._k_based_fallback(state_in, p_out)

    def _run_single(
        self, state_in, p_out: float, thermo_solver, gas_obj, eos: str, method: str
    ) -> float:
        from kasp.core.aerodynamics import CompressorAerodynamics

        if method == "fd_nr":
            T, _, _ = CompressorAerodynamics.calculate_isentropic_temp_fd_nr(
                state_in, p_out, thermo_solver, gas_obj, eos
            )
        elif method == "aj_nr":
            T, _, _ = CompressorAerodynamics.calculate_isentropic_temp_aj_nr(
                state_in, p_out, thermo_solver, gas_obj, eos
            )
        elif method == "brent":
            T, _, _ = CompressorAerodynamics.calculate_isentropic_temp_brent(
                state_in, p_out, thermo_solver, gas_obj, eos
            )
        else:
            raise ValueError(f"Bilinmeyen cozucu: {method}")

        return T

    def _k_based_fallback(self, state_in, p_out: float) -> float:
        k = state_in.k if state_in.k > 1.0 else 1.3
        pr = p_out / state_in.P
        n_isen = (k - 1.0) / k
        return state_in.T * (pr**n_isen)
