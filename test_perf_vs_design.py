import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from kasp.core.thermo import ThermoEngine

def run_test():
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dist', 'doğubayazıt 4. ünite.kasp'), 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    s = data['results']['stages'][0]
    p1_pa = s['p_in']
    t1_k = s['t_in']
    p2_pa = s['p_out']
    t2_k = s['t_out']
    
    calc_poly_eff = s['poly_eff_design'] * 100
    calc_shaft_kw = data['results']['power_shaft_total_kw']
    calc_head_kj_kg = s['head_kj_kg']
    calc_fuel_kgh = data['results']['fuel_total_kgh']
    
    flow_nm3h = float(data['inputs']['flow'])
    mech_eff = data['inputs']['mech_eff']
    therm_eff = 35.0
    gas_comp = data['inputs']['gas_comp']
    eos_method = "coolprop"
    
    print("="*60)
    print(" KASP V4.6.1 - PERFORMANS TESTI: DOGUBAYAZIT 4. UNITE ")
    print("="*60)
    print(f"[TASARIM BEKLENEN] T2: {t2_k-273.15:.2f} C | Poly Eff: {calc_poly_eff:.2f}% | Shaft: {calc_shaft_kw:.0f} kW | Fuel: {calc_fuel_kgh:.0f} kg/h")

    engine = ThermoEngine()
    
    gas_obj = engine._create_gas_object(gas_comp, eos_method)
    flow_kgs = engine.convert_flow_to_kgs(flow_nm3h, 'Nm³/h', gas_obj, eos_method)
    
    # --- 1. DOGRU TASARIM (YENI MOTORLA) ---
    design_inputs = {
        'p_in': p1_pa / 100000.0, # bar
        'p_in_unit': 'bar(a)',
        't_in': t1_k - 273.15,
        't_in_unit': '°C',
        'p_out': p2_pa / 100000.0,
        'p_out_unit': 'bar(a)',
        'flow': flow_nm3h,
        'flow_unit': 'Nm³/h',
        'num_units': 1,
        'gas_comp': gas_comp,
        'eos_method': eos_method,
        'method': 'Metot 4: Doğrudan H-S',
        'poly_eff': 90.0,
        'therm_eff': 35.0,
        'mech_eff': 98.0,
        'use_consistency_iteration': False
    }
    
    # Force ambient to 0 because we pass absolute bar
    design_inputs['ambient_pressure_pa'] = 0.0

    print("="*60)
    print(" 1. TASARIM SIMULASYONU ÇALIŞTIRILIYOR (V4.6.1 FIXED ENGINE) ")
    print("="*60)
    design_res = engine.calculate_design_performance(design_inputs)
    
    true_t2_k = design_res['t_out'] + 273.15
    true_shaft_kw = design_res['power_shaft_total_kw']
    true_fuel_kgh = design_res['fuel_total_kgh']
    true_head_kj_kg = design_res['stages'][0]['head_kj_kg']
    diag_poly_eff = design_res['stages'][0]['poly_eff_diagnostic'] * 100.0
    true_delta_h = design_res['stages'][0]['delta_h_kj_kg']
    true_phys_shaft = (true_delta_h * flow_kgs) / (98.0 / 100.0)
    
    print(f"[YENI TASARIM] T2: {true_t2_k-273.15:.2f} C | Poly Eff (Input): 90.00% | Poly Eff (Diagnostic): {diag_poly_eff:.2f}%")
    print(f"[YENI TASARIM] Head: {true_head_kj_kg:.2f} kJ/kg | Delta H (Real): {true_delta_h:.2f} kJ/kg")
    print(f"[YENI TASARIM] Shaft API: {true_shaft_kw:.0f} kW | Shaft Physics (dH*m): {true_phys_shaft:.0f} kW | Fuel: {true_fuel_kgh:.0f} kg/h")

    # --- 2. PERFORMANS TESTI (TERSINE HESAPLAMA) ---
    print("-" * 60)
    print(" 2. PERFORMANS MOTORU ÇALIŞTIRILIYOR (ASME PTC 10)...")
    
    gas_obj = engine._create_gas_object(gas_comp, eos_method)
    flow_kgs = engine.convert_flow_to_kgs(flow_nm3h, 'Nm³/h', gas_obj, eos_method)
    
    perf_inputs = {
        'p1_pa': p1_pa,
        't1_k': t1_k,
        'p2_pa': p2_pa,
        't2_k': true_t2_k,  # Feed the newly calculated correct T2!
        'flow_kgs': flow_kgs,
        'mech_eff': 98.0,
        'driver_mode': 'turb_eff',
        'driver_val': 35.0,
        'gas_comp': gas_comp,
        'eos_method': eos_method,
        'rpm': 0.0
    }

    res = engine.evaluate_performance(perf_inputs)
    
    print("-" * 60)
    print(" PERFORMANS Modülü Sonuçları:")
    print(f"[PERFORMANS SONUÇ] Poly Eff: {res['poly_eff']:.2f}%")
    print(f"[PERFORMANS SONUÇ] Head:     {res['poly_head_kj_kg']:.2f} kJ/kg")
    print(f"[PERFORMANS SONUÇ] Shaft P:  {res['shaft_power_kw']:.0f} kW")
    print(f"[PERFORMANS SONUÇ] Fuel:     {res['fuel_cons_kg_h']:.0f} kg/h")
    
    print("="*60)
    print(" MATCHING VERIFICATION (PERFORMANCE VS DESIGN) ")
    print(f"D Poly Eff  : {res['poly_eff'] - 90.0:+.4f} %  (Should be 0)")
    print(f"D Head      : {res['poly_head_kj_kg'] - true_head_kj_kg:+.4f} kJ/kg (Should be 0)")
    print(f"D Shaft Pow : {res['shaft_power_kw'] - true_shaft_kw:+.1f} kW (Should be 0)")
    print(f"D Fuel Cons : {res['fuel_cons_kg_h'] - true_fuel_kgh:+.1f} kg/h (Should be 0)")
    print("="*60)
    
    print("-" * 60)
    print(" PERFORMANS Modulu Sonuclari:")
    print(f"[PERFORMANS SONUC] Poly Eff: {res['poly_eff']:.2f}%")
    print(f"[PERFORMANS SONUC] Isen Eff: {res['isen_eff']:.2f}%")
    print(f"[PERFORMANS SONUC] Head:     {res['poly_head_kj_kg']:.2f} kJ/kg")
    print(f"[PERFORMANS SONUC] Shaft P:  {res['shaft_power_kw']:.0f} kW")
    print(f"[PERFORMANS SONUC] Fuel:     {res['fuel_cons_kg_h']:.0f} kg/h")
    
    print("="*60)
    print(" KARŞILAŞTIRMA / FARK ")
    print(f"D Poly Eff  : {res['poly_eff'] - calc_poly_eff:+.4f} %")
    print(f"D Head      : {res['poly_head_kj_kg'] - calc_head_kj_kg:+.4f} kJ/kg")
    print(f"D Shaft Pow : {res['shaft_power_kw'] - calc_shaft_kw:+.1f} kW")
    print(f"D Fuel Cons : {res['fuel_cons_kg_h'] - calc_fuel_kgh:+.1f} kg/h")
    print("="*60)

if __name__ == "__main__":
    run_test()
