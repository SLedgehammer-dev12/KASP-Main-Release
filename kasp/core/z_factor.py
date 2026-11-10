"""Lightweight Z-factor fallback correlations for KASP.

This module provides a last-resort, EOS-free Z-factor estimate when all
equation-of-state backends fail. It uses Kay's mixing rule, the Wichert-Aziz
correction for acid gases, and the Dranchuk-Abou-Kassem (DAK) correlation.

The DAK coefficients are the published correlation coefficients (Dranchuk &
Abou-Kassem, 1975). The implementation is intentionally dependency-free and
does not import any UI or third-party package beyond the KASP constants.

References
----------
Dranchuk, P.M. and Abou-Kassem, J.H. (1975), "Calculation of Z Factors for
Natural Gases Using Equations of State", J. Can. Pet. Technol. 14(3).
Wichert, E. and Aziz, K. (1972), "Calculate Z's for Sour Gases",
Hydrocarbon Processing 51(5), 119-122.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, Optional, Tuple

from kasp.core.constants import (
    CRITICAL_PRESS_PA,
    CRITICAL_TEMPS_K,
    MOLAR_MASSES,
    normalize_component,
)

logger = logging.getLogger(__name__)

# DAK validity window (pseudo-reduced)
PPR_MIN, PPR_MAX = 0.0, 30.0
TPR_MIN, TPR_MAX = 1.0, 3.0
DAK_TOLERANCE = 1e-4
DAK_MAX_ITERATIONS = 50
DAK_RELAXATION = 0.5


def pseudo_critical_properties(composition: Dict[str, float]) -> Tuple[float, float, float]:
    """Return (Tpc_K, Ppc_Pa, MW_g_mol) using Kay's rule + Wichert-Aziz.

    Unknown components are ignored and the remaining fractions are renormalized.
    Raises ValueError if no component has critical constants.
    """
    canonical: Dict[str, float] = {}
    for name, value in (composition or {}).items():
        try:
            fraction = float(value)
        except (TypeError, ValueError):
            continue
        if fraction <= 0.0:
            continue
        key = normalize_component(name)
        canonical[key] = canonical.get(key, 0.0) + fraction

    total = sum(canonical.values())
    if total <= 0.0:
        raise ValueError("Gaz kompozisyonu bos; Z-faktoru hesaplanamadi.")

    y = {k: v / total for k, v in canonical.items()}

    tpc = 0.0
    ppc = 0.0
    mw = 0.0
    usable = 0.0
    for key, fraction in y.items():
        tc = CRITICAL_TEMPS_K.get(key)
        pc = CRITICAL_PRESS_PA.get(key)
        mass = MOLAR_MASSES.get(key)
        if tc is None or pc is None or mass is None:
            continue
        tpc += fraction * tc
        ppc += fraction * pc
        mw += fraction * mass
        usable += fraction

    if usable <= 0.0 or tpc <= 0.0 or ppc <= 0.0:
        raise ValueError("Kritik ozellikleri bilinen bilesen bulunamadi.")

    # Renormalize to the usable fraction so ignored trace components do not
    # bias the pseudo-critical values.
    tpc /= usable
    ppc /= usable
    mw /= usable

    y_h2s = y.get("HYDROGENSULFIDE", 0.0)
    y_co2 = y.get("CARBONDIOXIDE", 0.0)
    total_acid = y_h2s + y_co2
    if total_acid > 0.01:
        epsilon_r = (
            120.0 * (total_acid ** 0.9 - total_acid ** 1.6)
            + 15.0 * (y_h2s ** 0.5 - y_h2s ** 4.0)
        )
        tpc_r = tpc * 9.0 / 5.0
        tpc_prime_r = tpc_r - epsilon_r
        ppc_prime_pa = ppc * tpc_prime_r / (tpc_r + y_h2s * (1.0 - y_h2s) * epsilon_r)
        tpc = tpc_prime_r * 5.0 / 9.0
        ppc = ppc_prime_pa

    return tpc, ppc, mw


def dak_z_factor(ppr: float, tpr: float, clamp_bounds: bool = False) -> float:
    """Dranchuk-Abou-Kassem Z-factor with damped Newton iteration."""
    if not (PPR_MIN <= ppr <= PPR_MAX and TPR_MIN <= tpr <= TPR_MAX):
        if not clamp_bounds:
            raise ValueError(
                f"DAK gecerlilik araligi disinda: Ppr={ppr:.3f} (0-30), Tpr={tpr:.3f} (1-3)."
            )
        ppr = min(PPR_MAX, max(PPR_MIN, ppr))
        tpr = min(TPR_MAX, max(TPR_MIN, tpr))

    a1, a2, a3, a4, a5 = 0.3265, -1.07, -0.5339, 0.01569, -0.05165
    a6, a7, a8, a9 = 0.5475, -0.7361, 0.1844, 0.1056
    a10, a11 = 0.6134, 0.721

    inv_tpr = 1.0 / tpr
    a1_t = a1 + a2 * inv_tpr + a3 / tpr ** 3 + a4 / tpr ** 4 + a5 / tpr ** 5
    a2_t = a6 + a7 * inv_tpr + a8 / tpr ** 2
    a9_t = a9 * (a7 * inv_tpr + a8 / tpr ** 2)
    exp_pre = a10 / tpr ** 3

    z = 1.0
    for _ in range(DAK_MAX_ITERATIONS):
        rho = 0.27 * ppr / (tpr * z)
        exp_term = math.exp(-a11 * rho * rho)
        g = (
            1.0
            + a1_t * rho
            + a2_t * rho * rho
            - a9_t * rho ** 5
            + exp_pre * (1.0 + a11 * rho * rho) * rho * rho * exp_term
        )
        f = z - g

        dg_drho = (
            a1_t
            + 2.0 * a2_t * rho
            - 5.0 * a9_t * rho ** 4
            + (2.0 * exp_pre * rho * exp_term) * (1.0 + a11 * rho * rho - a11 ** 2 * rho ** 4)
        )
        drho_dz = -rho / z if z != 0.0 else 0.0
        df_dz = 1.0 - dg_drho * drho_dz
        if abs(df_dz) < 1e-12:
            z += 0.01
            continue

        z_new = z - DAK_RELAXATION * f / df_dz
        if not math.isfinite(z_new) or z_new <= 0.0:
            raise ValueError("DAK iterasyonu fiziksel olmayan Z uretti.")
        if abs(z_new - z) < DAK_TOLERANCE:
            return z_new
        z = z_new

    raise ValueError("DAK yakinsamadi.")


def estimate_z_factor(
    composition: Dict[str, float],
    pressure_pa: float,
    temperature_k: float,
) -> Dict[str, Any]:
    """Estimate Z with Kay/Wichert-Aziz/DAK.

    Returns a dict with z_factor, ppr, tpr, valid, method, and warnings.
    Raises ValueError when the composition or inputs are invalid.
    """
    if float(temperature_k) <= 0.0 or float(pressure_pa) <= 0.0:
        raise ValueError("Mutlak sicaklik ve basinc pozitif olmalidir.")
    tpc, ppc, mw = pseudo_critical_properties(composition)
    ppr = float(pressure_pa) / ppc
    tpr = float(temperature_k) / tpc
    valid = PPR_MIN <= ppr <= PPR_MAX and TPR_MIN <= tpr <= TPR_MAX
    warnings = []
    if not valid:
        warnings.append(
            "Standing-Katz/DAK gecerlilik araligi disinda "
            f"(Ppr={ppr:.3f}, Tpr={tpr:.3f})"
        )
    z = dak_z_factor(ppr, tpr, clamp_bounds=True)
    return {
        "z_factor": float(z),
        "ppr": float(ppr),
        "tpr": float(tpr),
        "tpc_k": float(tpc),
        "ppc_pa": float(ppc),
        "mw_g_mol": float(mw),
        "valid": bool(valid),
        "method": "Dranchuk-Abou-Kassem (DAK)",
        "warnings": warnings,
    }
