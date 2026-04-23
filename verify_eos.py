import sys
import json
from kasp.core.thermo import ThermoEngine

def run_tests():
    engine = ThermoEngine()
    
    base_inputs = {
        'gas_comp': {
            'METHANE': 0.98,
            'ETHANE': 0.015,
            'NITROGEN': 0.005
        },
        'ambient_pressure_pa': 101325.0,
        'p_in': 50.66325,  # 49.65 barg -> 50.66325 bar(a)
        'p_in_unit': 'bar',
        't_in': 19.0,
        't_in_unit': '°C',
        'p_out': 75.0,       # 75.0 bar(a)
        'p_out_unit': 'bar',
        'flow': 1985000.0,
        'flow_unit': 'Sm³/h',
        'poly_eff': 90.0,
        'mech_eff': 98.0,
        'num_units': 1,
        'num_stages': 1
    }

    eos_methods = ['coolprop', 'pr', 'srk']
    
    results_summary = {}

    for mode in ['Quick', 'Consistent']:
        print(f"\n{'='*50}")
        print(f"--- TESTING DIFFERENT EOS METHODS ({mode} Mode) ---")
        print(f"{'='*50}")
        
        for eos in eos_methods:
            print(f"\n>> Testing EOS: {eos.upper()} | Mode: {mode}")
            inputs = base_inputs.copy()
            inputs['eos_method'] = eos
            
            if mode == 'Consistent':
                inputs['use_consistency_iteration'] = True
                
            try:
                results = engine.calculate_design_performance(inputs)
                
                p_gas = results.get('power_gas_per_unit_kw', 0)
                p_shaft = results.get('power_shaft_per_unit_kw', 0)
                p_unit = results.get('power_unit_kw', 0)
                t_out = results.get('t_out', 0)
                head = results.get('head_kj_kg', 0)
                
                print(f"  Head (kJ/kg)      : {head:.2f}")
                print(f"  T_out (°C)        : {t_out:.2f}")
                print(f"  Gas Power (kW)    : {p_gas:.2f}")
                print(f"  Shaft Power (kW)  : {p_shaft:.2f}")
                print(f"  Unit Power (kW)   : {p_unit:.2f}")
                
                if mode == 'Consistent':
                    print(f"  Converged         : {results.get('consistency_converged')}")
                    print(f"  Iterations        : {results.get('consistency_iterations')}")
                    print(f"  Poly Eff Target   : {results.get('poly_eff_target', 0):.2f}%")
                    print(f"  Poly Eff Calc     : {results.get('poly_eff_converged', 0):.2f}%")
                
                results_summary[f"{eos}_{mode}"] = {
                    'head': head,
                    't_out': t_out,
                    'power': p_unit
                }
            except Exception as e:
                print(f"  FAILED: {e}")
                import traceback
                traceback.print_exc()

if __name__ == '__main__':
    run_tests()
