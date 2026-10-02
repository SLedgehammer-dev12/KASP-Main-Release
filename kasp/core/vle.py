"""
KASP V4.5 Process Thermodynamics — Vapor-Liquid Equilibrium (VLE) & Knockout Drum
==================================================================================
Bu modül, çok kademeli kompresörlerin ara-soğutucularında (intercoolers) meydana gelen
faz ayrışmasını (yoğuşma / VLE) ve sıvı tutucu drum (liquid knockout drum / scrubber)
davranışını simüle eder.

Termodinamik Temel:
-------------------
1. Wilson K-Değeri Korelasyonu:
   K_i = (P_c,i / P) * exp[5.373 * (1 + omega_i) * (1 - T_c,i / T)]
2. Rachford-Rice Flash Denklemi:
   f(beta) = sum_i [ z_i * (K_i - 1) / (1 + beta * (K_i - 1)) ] = 0
   Monoton azalan ve türevi f'(beta) < 0 olan bu denklem Newton-Raphson ve bisection
   hibrit algoritması ile makine hassasiyetinde çözülür.
3. Kütle ve Mol Dengesi Korunumu:
   n_feed = m_feed / MW_feed
   n_V = beta * n_feed,  n_L = (1 - beta) * n_feed
   m_V = n_V * MW_V,      m_L = n_L * MW_L
   m_V + m_L = m_feed (analitik tam korunum).
"""

from __future__ import annotations

import logging
import math
from typing import Any

from kasp.core.constants import (
    ACENTRIC_FACTORS,
    CRITICAL_PRESS_PA,
    CRITICAL_TEMPS_K,
    MOLAR_MASSES,
    normalize_component,
)

logger = logging.getLogger(__name__)


def calculate_wilson_k_values(
    p_pa: float,
    t_k: float,
    normalized_composition: dict[str, float],
) -> dict[str, float]:
    """
    Wilson bağıntısı ile karışım bileşenlerinin denge K-değerlerini (y_i / x_i) hesaplar.
    """
    if p_pa <= 0.0 or t_k <= 0.0:
        return {comp: 1.0 for comp in normalized_composition}

    k_values: dict[str, float] = {}
    for comp in normalized_composition:
        canonical = normalize_component(comp)
        t_c = CRITICAL_TEMPS_K.get(canonical, 300.0)
        p_c = CRITICAL_PRESS_PA.get(canonical, 45.0e5)
        omega = ACENTRIC_FACTORS.get(canonical, 0.1)

        try:
            # Wilson formülü
            exp_term = 5.373 * (1.0 + omega) * (1.0 - t_c / t_k)
            # Sayısal taşma engelleme
            exp_term = max(-80.0, min(80.0, exp_term))
            k_val = (p_c / p_pa) * math.exp(exp_term)
            k_values[canonical] = max(1e-15, min(1e15, k_val))
        except (OverflowError, ZeroDivisionError, ValueError):
            k_values[canonical] = 1.0

    return k_values


def solve_rachford_rice(
    z: dict[str, float],
    k_values: dict[str, float],
    max_iter: int = 100,
    tolerance: float = 1e-12,
) -> float:
    """
    Rachford-Rice denklemini [0, 1] aralığında Newton-Raphson + Bisection ile çözer.
    Dönen değer: buhar mol kesri beta (0.0: tam sıvı, 1.0: tam buhar).
    """
    comps = list(z.keys())
    z_vals = [z[c] for c in comps]
    k_vals = [k_values.get(c, 1.0) for c in comps]

    # Çiğlenme (dew point) noktası kontrolü: sum(z_i / K_i) <= 1 ise hepsi buhardır.
    sum_z_over_k = sum(zi / max(1e-15, ki) for zi, ki in zip(z_vals, k_vals))
    if sum_z_over_k <= 1.0 + 1e-7:
        return 1.0

    # Kabarcıklanma (bubble point) noktası kontrolü: sum(z_i * K_i) <= 1 ise hepsi sıvıdır.
    sum_z_times_k = sum(zi * ki for zi, ki in zip(z_vals, k_vals))
    if sum_z_times_k <= 1.0 - 1e-7:
        return 0.0

    # İki fazlı bölge: f(0) > 0 ve f(1) < 0
    beta_low = 0.0
    beta_high = 1.0

    # Akıllı başlangıç tahmini
    f0 = sum_z_times_k - 1.0
    f1 = 1.0 - sum_z_over_k
    denom_init = f0 - f1
    beta = f0 / denom_init if denom_init > 0 else 0.5
    beta = max(1e-4, min(1.0 - 1e-4, beta))

    for _ in range(max_iter):
        denoms = [1.0 + beta * (ki - 1.0) for ki in k_vals]
        # Sıfıra bölme emniyeti
        denoms = [d if abs(d) > 1e-15 else (1e-15 if d >= 0 else -1e-15) for d in denoms]

        f = sum(zi * (ki - 1.0) / d for zi, ki, d in zip(z_vals, k_vals, denoms))
        df = -sum(zi * ((ki - 1.0) ** 2) / (d ** 2) for zi, ki, d in zip(z_vals, k_vals, denoms))

        if abs(f) < tolerance or (beta_high - beta_low) < tolerance:
            break

        if f > 0.0:
            beta_low = beta
        else:
            beta_high = beta

        # Newton-Raphson adımı
        if abs(df) > 1e-15:
            beta_new = beta - f / df
        else:
            beta_new = 0.5 * (beta_low + beta_high)

        # Eğer Newton aralık dışına çıkarsa bisection'a düş
        if beta_new <= beta_low or beta_new >= beta_high:
            beta = 0.5 * (beta_low + beta_high)
        else:
            beta = beta_new

    return max(0.0, min(1.0, beta))


def perform_vle_flash(
    p_pa: float,
    t_k: float,
    composition: dict[str, float],
    mass_flow_kgs: float = 1.0,
) -> dict[str, Any]:
    """
    Belirtilen basınç (P, Pa), sıcaklık (T, K), kompozisyon ve kütle debisi (kg/s) için
    izotermal VLE flash hesabı yapar.

    Returns:
        dict:
            - vapor_fraction: float (0..1)
            - liquid_fraction: float (0..1)
            - liquid_knockout_kg_h: float (ayrıştırılan sıvı debisi, kg/h)
            - liquid_mass_flow_kgs: float (sıvı kütlesel debisi, kg/s)
            - vapor_mass_flow_kgs: float (buhar kütlesel debisi, kg/s)
            - vapor_composition: dict[str, float] (% olarak buhar bileşimi, toplam 100.0)
            - liquid_composition: dict[str, float] (% olarak sıvı bileşimi, toplam 100.0)
            - is_two_phase: bool (yoğuşma olup olmadığı)
            - feed_mw: float (g/mol)
            - vapor_mw: float (g/mol)
            - liquid_mw: float (g/mol)
    """
    if not composition:
        return {
            "vapor_fraction": 1.0,
            "liquid_fraction": 0.0,
            "liquid_knockout_kg_h": 0.0,
            "liquid_mass_flow_kgs": 0.0,
            "vapor_mass_flow_kgs": mass_flow_kgs,
            "vapor_composition": {},
            "liquid_composition": {},
            "is_two_phase": False,
            "feed_mw": 28.0,
            "vapor_mw": 28.0,
            "liquid_mw": 28.0,
        }

    # 1. Kompozisyonu normalize et (mol kesri z_i)
    raw_total = sum(float(v) for v in composition.values() if float(v or 0.0) > 0.0)
    if raw_total <= 0.0:
        return {
            "vapor_fraction": 1.0,
            "liquid_fraction": 0.0,
            "liquid_knockout_kg_h": 0.0,
            "liquid_mass_flow_kgs": 0.0,
            "vapor_mass_flow_kgs": mass_flow_kgs,
            "vapor_composition": composition,
            "liquid_composition": {},
            "is_two_phase": False,
            "feed_mw": 28.0,
            "vapor_mw": 28.0,
            "liquid_mw": 28.0,
        }

    z: dict[str, float] = {}
    for comp, val in composition.items():
        v = float(val or 0.0)
        if v > 1e-12:
            canonical = normalize_component(comp)
            z[canonical] = z.get(canonical, 0.0) + (v / raw_total)

    # 2. Wilson K değerleri
    k_values = calculate_wilson_k_values(p_pa, t_k, z)

    # 3. Rachford-Rice buhar kesri beta
    beta = solve_rachford_rice(z, k_values)

    # Feed molar kütlesi
    feed_mw = sum(z[c] * MOLAR_MASSES.get(c, 28.0) for c in z)
    if feed_mw <= 0.0:
        feed_mw = 28.0

    # Tam buhar durumu
    if beta >= 1.0 - 1e-7:
        comp_pct = {c: z[c] * 100.0 for c in z}
        return {
            "vapor_fraction": 1.0,
            "liquid_fraction": 0.0,
            "liquid_knockout_kg_h": 0.0,
            "liquid_mass_flow_kgs": 0.0,
            "vapor_mass_flow_kgs": mass_flow_kgs,
            "vapor_composition": comp_pct,
            "liquid_composition": {},
            "is_two_phase": False,
            "feed_mw": feed_mw,
            "vapor_mw": feed_mw,
            "liquid_mw": feed_mw,
        }

    # Tam sıvı durumu
    if beta <= 1e-7:
        comp_pct = {c: z[c] * 100.0 for c in z}
        return {
            "vapor_fraction": 0.0,
            "liquid_fraction": 1.0,
            "liquid_knockout_kg_h": mass_flow_kgs * 3600.0,
            "liquid_mass_flow_kgs": mass_flow_kgs,
            "vapor_mass_flow_kgs": 0.0,
            "vapor_composition": {},
            "liquid_composition": comp_pct,
            "is_two_phase": True,
            "feed_mw": feed_mw,
            "vapor_mw": feed_mw,
            "liquid_mw": feed_mw,
        }

    # 4. İki fazlı ayrışma dengesi
    y_raw = {c: z[c] * k_values[c] / (1.0 + beta * (k_values[c] - 1.0)) for c in z}
    x_raw = {c: z[c] / (1.0 + beta * (k_values[c] - 1.0)) for c in z}

    tot_y = sum(y_raw.values())
    tot_x = sum(x_raw.values())

    y = {c: max(0.0, y_raw[c] / tot_y) if tot_y > 0 else z[c] for c in z}
    x = {c: max(0.0, x_raw[c] / tot_x) if tot_x > 0 else z[c] for c in z}

    vapor_mw = sum(y[c] * MOLAR_MASSES.get(c, 28.0) for c in y)
    liquid_mw = sum(x[c] * MOLAR_MASSES.get(c, 28.0) for c in x)
    vapor_mw = max(1.0, vapor_mw)
    liquid_mw = max(1.0, liquid_mw)

    # Kütle ve mol dengesi
    # n_feed (mol/s) = mass_flow_kgs * 1000 / feed_mw
    n_feed = (mass_flow_kgs * 1000.0) / feed_mw
    n_vapor = beta * n_feed
    n_liquid = (1.0 - beta) * n_feed

    vapor_mass_flow_kgs = (n_vapor * vapor_mw) / 1000.0
    liquid_mass_flow_kgs = (n_liquid * liquid_mw) / 1000.0

    # Analitik tamamlama (yuvarlama sapmalarını mass_flow_kgs toplamına kilitler)
    if (vapor_mass_flow_kgs + liquid_mass_flow_kgs) > 0:
        ratio = mass_flow_kgs / (vapor_mass_flow_kgs + liquid_mass_flow_kgs)
        vapor_mass_flow_kgs *= ratio
        liquid_mass_flow_kgs *= ratio

    liquid_knockout_kg_h = liquid_mass_flow_kgs * 3600.0

    vapor_comp_pct = {c: round(y[c] * 100.0, 6) for c in y if y[c] > 1e-9}
    liquid_comp_pct = {c: round(x[c] * 100.0, 6) for c in x if x[c] > 1e-9}

    return {
        "vapor_fraction": beta,
        "liquid_fraction": 1.0 - beta,
        "liquid_knockout_kg_h": liquid_knockout_kg_h,
        "liquid_mass_flow_kgs": liquid_mass_flow_kgs,
        "vapor_mass_flow_kgs": vapor_mass_flow_kgs,
        "vapor_composition": vapor_comp_pct,
        "liquid_composition": liquid_comp_pct,
        "is_two_phase": True,
        "feed_mw": feed_mw,
        "vapor_mw": vapor_mw,
        "liquid_mw": liquid_mw,
    }
