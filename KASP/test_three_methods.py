"""
KASP V4.4 — 4 Hesaplama Metodu + Consistency Modu Doğrulama Testi
"""
import sys
sys.path.insert(0, '.')

from kasp.core.thermo import ThermoEngine

eng = ThermoEngine()

BASE = {
    'p_in':  20.0,  'p_in_unit':  'bar',
    't_in':  30.0,  't_in_unit':  '°C',
    'p_out': 60.0,  'p_out_unit': 'bar',
    'flow':  50000, 'flow_unit':  'kg/h',
    'gas_comp':   {'METHANE': 90, 'ETHANE': 5, 'PROPANE': 5},
    'eos_method': 'coolprop',
    'poly_eff':   85.0,
    'num_units': 1, 'num_stages': 1,
    'therm_eff': 35.0, 'mech_eff': 98.0,
    'intercooler_dp_pct': 0.0,
    'intercooler_t': 40.0,
    'enable_uncertainty': False,
}

METHODS = [
    'Metot 1: Ortalama Ozellikler',
    'Metot 2: Uc Nokta',
    'Metot 3: Artimli Basinc',
    'Metot 4: Dogrudan H-S',
]

print("=" * 72)
print("  KASP V4.4 — 4 Hesaplama Metodu Karsilastirma Testi")
print("=" * 72)
print(f"  Giris:  {BASE['p_in']} bar | {BASE['t_in']} C")
print(f"  Cikis:  {BASE['p_out']} bar")
print(f"  Debi:   {BASE['flow']} kg/h")
print(f"  EOS:    {BASE['eos_method']}")
print(f"  eta_p:  {BASE['poly_eff']}% (hedef)")
print("=" * 72)

results = {}
for meth in METHODS:
    inp = dict(BASE)
    inp['method'] = meth
    try:
        r = eng.calculate_design_performance(inp)
        results[meth] = r
        print(f"\n[{meth}]")
        print(f"  T_cikis          = {r['t_out']:.2f} C")
        print(f"  Politropik Head  = {r['head_kj_kg']:.2f} kJ/kg")
        print(f"  Gaz Gucu         = {r['power_gas_per_unit_kw']:.1f} kW")
        print(f"  Saft Gucu        = {r['power_shaft_per_unit_kw']:.1f} kW")
        print(f"  actual_poly_eff  = {r['actual_poly_efficiency']*100:.2f}%")
        hist = r['stages'][0].get('method_history', {})
        meth_used = hist.get('method_used', 'N/A')
        iters = len(hist.get('iteration', []))
        print(f"  Metod dahili     = {meth_used} ({iters} iter)")
        
        # Metot 4 ek bilgileri
        if 'Metot 4' in meth:
            t_isen = hist.get('t_isentropic', 0)
            dh_isen = hist.get('delta_h_isentropic_kj', 0)
            dh_act = hist.get('delta_h_actual_kj', 0)
            eta_is = hist.get('eta_isentropic_derived', 0)
            sigma = hist.get('sigma_backcomputed', 0)
            print(f"  T_isentropic     = {t_isen:.2f} K ({t_isen-273.15:.2f} C)")
            print(f"  DH_isen          = {dh_isen:.2f} kJ/kg")
            print(f"  DH_actual        = {dh_act:.2f} kJ/kg")
            print(f"  eta_isen_derived = {eta_is:.4f}")
            print(f"  sigma (n-1)/n    = {sigma:.6f}")
    except Exception as e:
        print(f"  HATA: {e}")
        import traceback
        traceback.print_exc()

# Karsilastirma tablosu
if len(results) >= 2:
    print("\n" + "=" * 72)
    print("  KARSILASTIRMA TABLOSU")
    print("=" * 72)
    print(f"  {'Metot':<35} {'T_out(C)':>10} {'Head(kJ/kg)':>12} {'Gaz Gucu(kW)':>14}")
    print(f"  {'-'*35} {'-'*10} {'-'*12} {'-'*14}")
    for meth, r in results.items():
        t = r['t_out']
        h = r['head_kj_kg']
        p = r['power_gas_per_unit_kw']
        print(f"  {meth:<35} {t:>10.2f} {h:>12.2f} {p:>14.1f}")

# Consistency modu testi
print("\n" + "=" * 72)
print("  Consistency Modu Testi (SUR)")
print("=" * 72)
inp2 = dict(BASE)
inp2['use_consistency_iteration'] = True
inp2['max_consistency_iter'] = 10
inp2['consistency_tolerance'] = 0.1
try:
    rc = eng.calculate_design_performance_with_mode(inp2)
    print(f"  Yakinsadi mi?     = {rc.get('consistency_converged', '?')}")
    print(f"  Iterasyon sayisi  = {rc.get('consistency_iterations', '?')}")
    print(f"  Hedef eta_p       = {rc.get('poly_eff_target', '?'):.2f}%")
    print(f"  Yakinsayan eta_p  = {rc.get('poly_eff_converged', '?'):.2f}%")
    print(f"  Son residual      = {rc.get('final_residual', '?'):.4f}%")
    print(f"  T_cikis           = {rc.get('t_out', 0):.2f} C")
    print(f"  Saft Gucu         = {rc.get('power_shaft_per_unit_kw', 0):.1f} kW")
except Exception as e:
    print(f"  HATA: {e}")

# PR > 4 integral metot testi
print("\n" + "=" * 72)
print("  Yuksek Basinc Orani (PR=9) — API 617 Integral Metot Testi")
print("=" * 72)
inp3 = dict(BASE)
inp3['p_out'] = 180.0  # PR = 9
inp3['method'] = 'Metot 1: Ortalama Ozellikler'
try:
    rhi = eng.calculate_design_performance(inp3)
    hist = rhi['stages'][0].get('method_history', {})
    meth_used = hist.get('method_used', 'N/A')
    ki = hist.get('k_integral', 'N/A')
    print(f"  PR = {rhi['compression_ratio']:.1f}")
    print(f"  Dahili metod     = {meth_used}")
    if ki != 'N/A':
        print(f"  k_integral       = {ki:.4f}")
    print(f"  T_cikis          = {rhi['t_out']:.2f} C")
    print(f"  Head             = {rhi['head_kj_kg']:.2f} kJ/kg")
    print(f"  Saft Gucu        = {rhi['power_shaft_per_unit_kw']:.1f} kW")
except Exception as e:
    print(f"  HATA: {e}")

# PR > 4 — Metot 4 H-S ile karsilastirma
print("\n" + "=" * 72)
print("  Yuksek PR (PR=9) — Metot 4 (H-S) Karsilastirma")
print("=" * 72)
inp4 = dict(BASE)
inp4['p_out'] = 180.0
inp4['method'] = 'Metot 4: Dogrudan H-S'
try:
    rhs = eng.calculate_design_performance(inp4)
    print(f"  PR = {rhs['compression_ratio']:.1f}")
    print(f"  T_cikis          = {rhs['t_out']:.2f} C")
    print(f"  Head             = {rhs['head_kj_kg']:.2f} kJ/kg")
    print(f"  Saft Gucu        = {rhs['power_shaft_per_unit_kw']:.1f} kW")
    hist4 = rhs['stages'][0].get('method_history', {})
    print(f"  T_isen           = {hist4.get('t_isentropic', 0):.2f} K")
    print(f"  DH_isen          = {hist4.get('delta_h_isentropic_kj', 0):.2f} kJ/kg")
    print(f"  eta_isen         = {hist4.get('eta_isentropic_derived', 0):.4f}")
except Exception as e:
    print(f"  HATA: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 72)
print("  TESTLER TAMAMLANDI")
print("=" * 72)
