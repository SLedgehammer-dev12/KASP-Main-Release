"""
Unified sizing engine.

Single entry point for all relief sizing calculations. Every interface
(desktop, Streamlit, FastAPI) should call ``size_relief_case`` so that the
service phase, valve type, capacity certification and overpressure scenario
select the method and correction factors in exactly one place.

Provenance (standard edition, method, factor basis, warnings) is attached to
every result under ``Result_Meta``.
"""
from __future__ import annotations

from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field

from .constants import ATMOSPHERIC_PSIA, PRELIM_KD_GAS, PRELIM_KD_LIQUID, NONCERTIFIED_KD_LIQUID
from .gas_relief import calculate_gas_relief_area
from .liquid_relief import calculate_liquid_relief_area
from .two_phase import calculate_two_phase_area, calculate_omega_flashing
from .valve_types import calculate_pilot_gas_area, calculate_pilot_liquid_area
from .kb_coefficient import get_kb, select_kb_curve
from .piping import calculate_inlet_pressure_drop, evaluate_inlet_rule, check_outlet_rule
from .advanced_sizing import calculate_napier_steam_area, calculate_subcooled_flashing_area_usc
from .thermo_props import calculate_mixture_properties, COOLPROP_AVAILABLE

STANDARD_EDITION = "API 520 Part I 10th ed. (2020) + Errata 1 (2023)"

ServiceType = Literal["gas", "liquid", "steam", "two_phase", "two_phase_subcooled"]
ValveType = Literal["conventional", "balanced_bellows", "pilot"]


class ReliefCase(BaseModel):
    """Canonical, interface-independent relief sizing case."""

    service: ServiceType

    # Common
    p1_psia: float = Field(gt=0, description="Relieving pressure (psia)")
    p2_psia: float = Field(ge=0, description="Total back pressure (psia)")
    set_pressure_psig: Optional[float] = Field(default=None, gt=0)
    overpressure_pct: float = Field(default=10.0, ge=1.0, le=50.0)
    num_valves: int = Field(default=1, ge=1, le=100)
    valve_type: ValveType = Field(default="conventional")
    capacity_certified: bool = Field(default=True)
    kc: float = Field(default=1.0, ge=0.1, le=1.0)
    atm_psia: float = Field(default=ATMOSPHERIC_PSIA, gt=0)

    # Gas / steam
    w_lb_h: Optional[float] = Field(default=None, gt=0)
    t_rankine: Optional[float] = Field(default=None, gt=0)
    z: float = Field(default=1.0, gt=0, le=2.0)
    mw: Optional[float] = Field(default=None, gt=0)
    k: float = Field(default=1.4, gt=1.0, le=2.5)
    kd: Optional[float] = Field(default=None, ge=0.1, le=1.0)
    kb: Optional[float] = Field(default=None, ge=0.1, le=1.0)
    use_napier: bool = Field(default=False)

    # Liquid
    q_gpm: Optional[float] = Field(default=None, gt=0)
    g: Optional[float] = Field(default=None, gt=0)
    mu_cp: float = Field(default=1.0, gt=0)
    kw: Optional[float] = Field(default=None, ge=0.1, le=1.0)
    kp: Optional[float] = Field(default=None, ge=0.5, le=1.5)

    # Two-phase
    v0_ft3_lb: Optional[float] = Field(default=None, gt=0)
    v9_ft3_lb: Optional[float] = Field(default=None, gt=0)
    omega: Optional[float] = Field(default=None, gt=0)

    # Two-phase subcooled flashing (Annex C.2.3)
    ps_psia: Optional[float] = Field(default=None, gt=0)
    rho1_lb_ft3: Optional[float] = Field(default=None, gt=0)
    rho9_lb_ft3: Optional[float] = Field(default=None, gt=0)

    # Optional gas-mixture auto-properties (CoolProp). When supplied, Z/MW/k
    # are taken from the mixture unless explicitly overridden (see T3).
    composition: Optional[Dict[str, float]] = Field(default=None)
    fraction_type: Literal["mole", "mass"] = Field(default="mole")

    # Optional inlet-piping assessment (API 520 Part II 7.3). Evaluated only
    # when pipe_id_in is supplied; flows default to the case flows.
    pipe_id_in: Optional[float] = Field(default=None, gt=0)
    pipe_length_ft: float = Field(default=0.0, ge=0.0)
    fittings_90deg: int = Field(default=0, ge=0)
    fittings_45deg: int = Field(default=0, ge=0)
    gate_valves: int = Field(default=0, ge=0)
    roughness_in: float = Field(default=0.00015, ge=0.0)
    piping_density_lb_ft3: Optional[float] = Field(default=None, gt=0)
    piping_viscosity_cp: Optional[float] = Field(default=None, gt=0)
    piping_flow_gpm: Optional[float] = Field(default=None, gt=0)
    piping_flow_lb_h: Optional[float] = Field(default=None, gt=0)
    remote_sensing: bool = Field(default=False)


def _require(value, name):
    if value is None:
        raise ValueError(f"{name} is required for this service")
    return value


def _gas_kb(case: ReliefCase) -> Optional[float]:
    if case.kb is not None:
        return case.kb
    if case.valve_type in ("conventional", "pilot"):
        return 1.0
    if case.set_pressure_psig:
        return get_kb(case.p2_psia, case.set_pressure_psig, case.valve_type,
                      case.overpressure_pct, case.atm_psia)
    return None


def _mixture_properties(case: ReliefCase, warnings) -> Dict[str, Any]:
    """Resolve Z/MW/k from an optional gas composition (T3).

    Precedence per property: an explicitly non-default user value wins,
    otherwise the CoolProp mixture value is used. Without CoolProp the
    composition is rejected loudly — never silently replaced by air.
    Returns (z, mw, k, basis_notes).
    """
    notes = []
    z, mw, k = case.z, case.mw, case.k
    if not case.composition:
        return z, mw, k, notes
    if not COOLPROP_AVAILABLE:
        raise ValueError(
            "composition requires CoolProp, which is not installed. "
            "Supply z/mw/k manually instead."
        )
    try:
        z_c, mw_c, k_c = calculate_mixture_properties(
            dict(case.composition), _require(case.t_rankine, "t_rankine"),
            case.p1_psia, case.fraction_type,
        )
    except ValueError:
        raise
    except Exception as exc:
        warnings.append(
            f"Mixture auto-properties failed ({exc}); manual z/mw/k used."
        )
        return z, mw, k, notes
    if "z" not in case.model_fields_set:
        z = z_c
        notes.append(f"Z={z_c:.4f} from mixture")
    else:
        notes.append(f"Z={case.z} manual override (mixture gave {z_c:.4f})")
    if "mw" not in case.model_fields_set or case.mw is None:
        mw = mw_c
        notes.append(f"MW={mw_c:.3f} from mixture")
    else:
        notes.append(f"MW={case.mw} manual override (mixture gave {mw_c:.3f})")
    if "k" not in case.model_fields_set:
        k = k_c
        notes.append(f"k={k_c:.4f} from mixture")
    else:
        notes.append(f"k={case.k} manual override (mixture gave {k_c:.4f})")
    return z, mw, k, notes


def _piping_assessment(case: ReliefCase, w_lb_h=None, q_gpm=None) -> Dict[str, Any]:
    """Optional inlet/outlet piping check (T4).

    Evaluated only when pipe_id_in is supplied. Returns a dict with
    ``warnings`` (list) and ``summary`` (dict) for Result_Meta.
    """
    out: Dict[str, Any] = {"warnings": [], "summary": {}}
    if case.pipe_id_in is None:
        return out
    flow_gpm = case.piping_flow_gpm if case.piping_flow_gpm is not None else q_gpm
    flow_lb_h = case.piping_flow_lb_h if case.piping_flow_lb_h is not None else w_lb_h
    density = case.piping_density_lb_ft3
    viscosity = case.piping_viscosity_cp
    if density is None or viscosity is None:
        out["warnings"].append(
            "Piping assessment skipped: piping_density_lb_ft3 and "
            "piping_viscosity_cp are both required when pipe_id_in is given."
        )
        return out
    try:
        drop = calculate_inlet_pressure_drop(
            flow_gpm=flow_gpm,
            fluid_density_lb_ft3=density,
            viscosity_cp=viscosity,
            pipe_id_in=case.pipe_id_in,
            pipe_length_ft=case.pipe_length_ft,
            fittings_90deg=case.fittings_90deg,
            fittings_45deg=case.fittings_45deg,
            gate_valves=case.gate_valves,
            roughness_in=case.roughness_in,
            flow_rate_lb_h=flow_lb_h,
        )
    except (ValueError, ZeroDivisionError) as exc:
        out["warnings"].append(f"Piping assessment failed: {exc}")
        return out
    out["summary"] = {
        "delta_p_psi": round(drop["delta_p_psi"], 4),
        "velocity_fps": round(drop["velocity_fps"], 2),
    }
    if case.set_pressure_psig:
        rule = evaluate_inlet_rule(
            drop["delta_p_psi"], case.set_pressure_psig,
            case.valve_type, remote_sensing=case.remote_sensing,
        )
        out["summary"]["inlet_rule"] = rule["status"]
        out["summary"]["delta_p_pct_of_set"] = round(rule["delta_p_pct"], 3)
        if not rule["passes"]:
            out["warnings"].append(f"Inlet piping: {rule['message']}")
        bp_gauge = max(case.p2_psia - case.atm_psia, 0.0)
        set_psig = case.set_pressure_psig
        passes, bp_pct = check_outlet_rule(bp_gauge, set_psig, valve_type=case.valve_type)
        out["summary"]["outlet_rule_pass"] = passes
        out["summary"]["backpressure_pct_of_set"] = round(bp_pct, 2)
        if not passes:
            limit_pct = 50.0 if case.valve_type == "pilot" else (30.0 if case.valve_type == "balanced_bellows" else 10.0)
            out["warnings"].append(
                f"Built-up backpressure {bp_pct:.1f}% exceeds {limit_pct:.0f}% of set "
                f"pressure (API 520 Part II outlet rule for {case.valve_type}) — engineering review required."
            )
    else:
        out["warnings"].append(
            "Piping drop computed but no set pressure supplied; "
            "3% inlet / 10% outlet rules could not be evaluated."
        )
    return out


def _merge_piping(case: ReliefCase, meta: Dict[str, Any], warnings,
                 w_lb_h=None, q_gpm=None) -> None:
    """Run the optional piping assessment and fold it into meta/warnings."""
    piping = _piping_assessment(case, w_lb_h=w_lb_h, q_gpm=q_gpm)
    warnings.extend(piping["warnings"])
    if piping["summary"]:
        meta["Piping_Assessment"] = piping["summary"]


def size_relief_case(case: ReliefCase) -> Dict[str, Any]:
    """
    Route a ReliefCase to the correct sizing method and return the result
    dict enriched with provenance under ``Result_Meta``.
    """
    warnings = []
    meta: Dict[str, Any] = {
        "Standard": STANDARD_EDITION,
        "Service": case.service,
        "Valve_Type": case.valve_type,
    }

    if case.service == "steam" or (case.service == "gas" and case.use_napier):
        w_steam = _require(case.w_lb_h, "w_lb_h")
        result = calculate_napier_steam_area(
            w_lb_h=w_steam,
            p1_psia=case.p1_psia,
            p2_psia=case.p2_psia,
            t_rankine=case.t_rankine,
            kd=case.kd if case.kd is not None else PRELIM_KD_GAS,
            kb=_gas_kb(case) or 1.0,
            kc=case.kc,
            num_valves=case.num_valves,
        )
        meta.update({
            "Method": "Napier steam (API 520 Part I 5.7, Eq 25)",
            "Kd_Basis": "0.975 preliminary (steam)",
            "Kb_Basis": "Figure 31" if case.valve_type == "balanced_bellows" else "Kb = 1.0",
            "Ksh_Basis": "psvpy-derived superheat table (known deviation vs "
                         "API 520 Table: see test suite notes); Ksh = 1.0 when "
                         "temperature is not supplied (saturated assumed)",
        })
        if case.t_rankine is None:
            warnings.append("No steam temperature supplied; KSH = 1.0 (saturated) assumed.")
        if case.p2_psia > 0.5 * case.p1_psia:
            warnings.append("Back pressure above ~50% of relieving pressure; verify critical flow with the manufacturer.")
        _merge_piping(case, meta, warnings, w_lb_h=w_steam)
        return _wrap(result, meta, warnings)

    if case.service == "gas":
        w = _require(case.w_lb_h, "w_lb_h")
        t = _require(case.t_rankine, "t_rankine")
        z, mw, k, prop_notes = _mixture_properties(case, warnings)
        mw = _require(mw, "mw (or composition)")
        if prop_notes:
            meta["Z_MW_k_Basis"] = "; ".join(prop_notes)

        if case.valve_type == "pilot":
            result = calculate_pilot_gas_area(
                w_lb_h=w, p1_psia=case.p1_psia, p2_psia=case.p2_psia,
                t_rankine=t, z=z, mw=mw, k=k,
                kc=case.kc, kb=case.kb,
                set_pressure_psig=case.set_pressure_psig,
                num_valves=case.num_valves,
                overpressure_pct=case.overpressure_pct,
            )
            meta.update({
                "Method": "Pilot-operated gas (API 520 Part I 5.6 + 7)",
                "Kd_Basis": "0.99 pilot-operated (API 520 Table 13)",
                "Kb_Basis": "Kb = 1.0 (pilot capacity independent of backpressure; "
                            "subcritical F2 form takes no Kb term, as in Eq 16)",
            })
            if prop_notes:
                meta["Z_MW_k_Basis"] = "; ".join(prop_notes)
            _merge_piping(case, meta, warnings, w_lb_h=w)
            return _wrap(result, meta, warnings)

        kb = _gas_kb(case)
        if kb is None:
            warnings.append("No set pressure supplied; Kb = 1.0 assumed. Backpressure correction may be unconservative.")
            kb = 1.0
        elif case.valve_type == "balanced_bellows":
            _, basis = select_kb_curve(case.overpressure_pct)
            meta["Kb_Basis"] = f"Figure 31 {basis} overpressure curve"
        else:
            meta["Kb_Basis"] = "Kb = 1.0 (conventional, subcritical equation accounts for backpressure)"

        result = calculate_gas_relief_area(
            w_lb_h=w, p1_psia=case.p1_psia, p2_psia=case.p2_psia,
            t_rankine=t, z=z, mw=mw, k=k,
            kd=case.kd if case.kd is not None else PRELIM_KD_GAS,
            kb=kb, kc=case.kc, num_valves=case.num_valves,
        )
        meta.update({
            "Method": "Gas/vapor (API 520 Part I 5.6, Eq 6/16)",
            "Kd_Basis": f"{case.kd if case.kd is not None else PRELIM_KD_GAS} ({'certified' if case.kd else 'preliminary 0.975'})",
        })
        if kb < 1.0 and case.p2_psia > case.atm_psia:
            warnings.append(
                "Balanced bellows backpressure correction applied. Final capacity shall be verified "
                "with the manufacturer's certified Kd and actual orifice area."
            )
        if case.valve_type in ("balanced_bellows", "pilot"):
            meta["Backpressure_Note"] = (
                "Kb/Kw evaluated on total backpressure. Constant (superimposed) "
                "backpressure additionally reduces the opening differential — "
                "verify any set-pressure correction per API 520 Part I 5.3."
            )
        _merge_piping(case, meta, warnings, w_lb_h=w)
        return _wrap(result, meta, warnings)

    if case.service == "liquid":
        q = _require(case.q_gpm, "q_gpm")
        g = _require(case.g, "g")

        if case.valve_type == "pilot":
            result = calculate_pilot_liquid_area(
                q_gpm=q, p1_psia=case.p1_psia, p2_psia=case.p2_psia,
                g=g, mu_cp=case.mu_cp, kw=case.kw or 1.0, num_valves=case.num_valves,
            )
            if result.get("Orifice_Iteration_Converged") is False:
                warnings.append("Viscous liquid orifice selection did not converge within maximum iterations — engineering review required.")
            meta.update({
                "Method": "Pilot-operated liquid (API 520 Part I 5.8 + 7)",
                "Kd_Basis": "0.80 pilot-operated liquid",
                "Kv_Basis": "Kv = 1.0 (viscosity <= 100 cP per 5.8.1.3)",
                "Backpressure_Note": (
                    "Kw evaluated on total backpressure. Constant (superimposed) "
                    "backpressure additionally reduces the opening differential — "
                    "verify any set-pressure correction per API 520 Part I 5.3."
                ),
            })
            _merge_piping(case, meta, warnings, q_gpm=q)
            return _wrap(result, meta, warnings)

        if case.capacity_certified:
            kd = case.kd if case.kd is not None else PRELIM_KD_LIQUID
            meta.update({
                "Method": "Liquid, capacity certified (API 520 Part I 5.8, Eq 32)",
                "Kd_Basis": f"{kd} (certified/preliminary)",
                "Kp_Basis": "Not used for certified liquid valves",
                "Kv_Basis": "Kv = 1.0 when mu <= 100 cP; Figure 38/Eq 34 otherwise",
            })
        else:
            kd = NONCERTIFIED_KD_LIQUID
            meta.update({
                "Method": "Liquid, capacity NOT certified (API 520 Part I 5.9, Eq 42)",
                "Kd_Basis": f"{NONCERTIFIED_KD_LIQUID} (required by 5.9)",
                "Kp_Basis": "Figure 39 (Kp = 1.0 at 25% overpressure)",
                "Kv_Basis": "Kv = 1.0 when mu <= 100 cP",
            })
            warnings.append(
                "Noncertified liquid sizing per 5.9 typically oversizes at 10% overpressure; "
                "overpressures below 10% shall be avoided."
            )

        result = calculate_liquid_relief_area(
            q_gpm=q, p1_psia=case.p1_psia, p2_psia=case.p2_psia,
            g=g, mu_cp=case.mu_cp, kd=kd, kw=case.kw, kc=case.kc,
            num_valves=case.num_valves, kp=case.kp,
            overpressure_pct=case.overpressure_pct,
            valve_type=case.valve_type,
            set_pressure_psig=case.set_pressure_psig,
            atm_psia=case.atm_psia,
            capacity_certified=case.capacity_certified,
        )
        if result.get("Kw", 1.0) < 1.0:
            warnings.append("Balanced bellows Kw correction applied (Figure 32).")
        if result.get("Re_Below_80"):
            warnings.append("Reynolds number below 80; Eq 34 validity limit (Re >= 80) exceeded — engineering review required.")
        if result.get("Orifice_Iteration_Converged") is False:
            warnings.append("Viscous liquid orifice selection did not converge within 10 iterations (oscillating between sizes) — engineering review required.")
        if case.valve_type == "balanced_bellows":
            meta["Backpressure_Note"] = (
                "Kw evaluated on total backpressure. Constant (superimposed) "
                "backpressure additionally reduces the opening differential — "
                "verify any set-pressure correction per API 520 Part I 5.3."
            )
        _merge_piping(case, meta, warnings, q_gpm=q)
        return _wrap(result, meta, warnings)

    if case.service == "two_phase":
        w = _require(case.w_lb_h, "w_lb_h")
        v0 = _require(case.v0_ft3_lb, "v0_ft3_lb")
        if case.omega is None:
            v9 = _require(case.v9_ft3_lb, "v9_ft3_lb")
            omega = calculate_omega_flashing(v0, v9)
        else:
            omega = case.omega

        kb = case.kb
        if kb is None:
            if case.valve_type == "balanced_bellows" and case.set_pressure_psig:
                kb = get_kb(case.p2_psia, case.set_pressure_psig,
                            "balanced_bellows", case.overpressure_pct, case.atm_psia)
            else:
                kb = 1.0

        result = calculate_two_phase_area(
            w_lb_h=w, p0_psia=case.p1_psia, p_back_psia=case.p2_psia,
            v0_ft3_lb=v0, omega=omega, kd=case.kd if case.kd is not None else 0.85,
            kb=kb, kc=case.kc, num_valves=case.num_valves,
        )
        meta.update({
            "Method": "Two-phase Omega method (API 520 Part I Annex C)",
            "Kd_Basis": f"{case.kd if case.kd is not None else 0.85} (effective, no certified two-phase capacities exist)",
            "Kb_Basis": "Figure 31" if kb != 1.0 else "Kb = 1.0",
            "v9_Basis": "User flash value" if case.v9_ft3_lb is not None else "omega supplied directly",
        })
        warnings.append(
            "No PRDs have certified capacities for two-phase flow; final selection requires "
            "manufacturer/vendor confirmation."
        )
        _merge_piping(case, meta, warnings, w_lb_h=w)
        return _wrap(result, meta, warnings)

    if case.service == "two_phase_subcooled":
        q = _require(case.q_gpm, "q_gpm")
        result = calculate_subcooled_flashing_area_usc(
            q_gpm=q, p1_psia=case.p1_psia, p2_psia=case.p2_psia,
            ps_psia=_require(case.ps_psia, "ps_psia"),
            rho1_lb_ft3=_require(case.rho1_lb_ft3, "rho1_lb_ft3"),
            rho9_lb_ft3=_require(case.rho9_lb_ft3, "rho9_lb_ft3"),
            kd=case.kd if case.kd is not None else 0.65,
            kb=case.kb if case.kb is not None else 1.0,
            kc=case.kc, num_valves=case.num_valves,
        )
        meta.update({
            "Method": "Two-phase subcooled flashing (API 520 Part I Annex C.2.3)",
            "Kd_Basis": f"{case.kd if case.kd is not None else 0.65} (subcooled liquid, C.2.3)",
            "Kb_Basis": "Kb = 1.0 unless overridden",
            "Kv_Basis": "Kv = 1.0 (screening; apply viscosity correction by direct call if needed)",
        })
        warnings.append(
            "Subcooled-flashing screening per Annex C.2.3; final selection requires "
            "manufacturer/vendor confirmation."
        )
        if not result.get("Critical_Flow", True):
            warnings.append(
                "Subcritical subcooled-flashing regime; verify downstream conditions "
                "with the vendor."
            )
        _merge_piping(case, meta, warnings, q_gpm=q)
        return _wrap(result, meta, warnings)

    raise ValueError(f"Unsupported service: {case.service}")


def _wrap(result: Dict[str, Any], meta: Dict[str, Any], warnings) -> Dict[str, Any]:
    result = dict(result)
    result["Result_Meta"] = {**meta, "Warnings": list(warnings)}
    result["Verification_Status"] = "preliminary-verified" if not warnings else "review-required"
    return result


__all__ = ["ReliefCase", "size_relief_case", "STANDARD_EDITION"]
