from kasp.core.thermo import ThermoEngine
import sys

def run_test():
    engine = ThermoEngine()
    
    inputs = {
        'gas_comp': {'METHANE': 1.0},
        'eos_method': 'coolprop',
        'ambient_pressure_pa': 101325.0,
        'p_in': 20.0,
        'p_in_unit': 'bar',
        't_in': 30.0,
        't_in_unit': '°C',
        'p_out': 60.0,
        'p_out_unit': 'bar',
        'flow': 50000.0,
        'flow_unit': 'kg/h',
        'poly_eff': 85.0,
        'mech_eff': 98.0
    }

    try:
        results = engine.calculate_design_performance(inputs)
        print(f"mass_flow_per_unit_kgs: {results.get('mass_flow_per_unit_kgs')}")
        print(f"head_kj_kg: {results.get('head_kj_kg')}")
        print(f"power_gas_per_unit_kw: {results.get('power_gas_per_unit_kw')}")
        print(f"power_shaft_per_unit_kw: {results.get('power_shaft_per_unit_kw')}")
        print(f"power_motor_per_unit_kw: {results.get('power_motor_per_unit_kw')}")
        print(f"power_unit_kw: {results.get('power_unit_kw')}")

    except Exception as e:
        print(f"Calculation failed: {e}")

if __name__ == '__main__':
    run_test()
