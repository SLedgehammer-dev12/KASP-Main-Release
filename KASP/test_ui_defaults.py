import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from kasp.core.thermo import ThermoEngine

def run_test():
    engine = ThermoEngine()
    
    # Default UI Values
    p1 = 49.65 # bar(g)
    p2 = 75.0  # bar(a) ! Note the a
    t1 = 19.0
    t2 = 60.0
    flow = 1985000 # Sm3/h
    mech_eff = 98.0
    
    gas_comp = {
      "METHANE": 85.0,"ETHANE": 4.9928,"PROPANE": 2.0019,"BUTANE": 0.5672,
      "ISOBUTANE": 0.2225,"ISOPENTANE": 0.0169,"PENTANE": 0.0104,
      "CARBONDIOXIDE": 1.1641,"NITROGEN": 4.6635,"HEXANE": 0.0285
    }
    
    # Normalizing
    total = sum(gas_comp.values())
    gas_comp = {k: v/total * 100 for k,v in gas_comp.items()}
    
    eos_method = "coolprop"
    
    gas_obj = engine._create_gas_object(gas_comp, eos_method)
    flow_kgs = engine.convert_flow_to_kgs(flow, 'Sm³/h', gas_obj, eos_method)
    
    inputs = {
        'p1_pa': engine.convert_pressure_to_pa(p1, 'bar(g)'),
        't1_k': engine.convert_temperature_to_k(t1, '°C'),
        'p2_pa': engine.convert_pressure_to_pa(p2, 'bar(a)'),
        't2_k': engine.convert_temperature_to_k(t2, '°C'),
        'flow_kgs': flow_kgs,
        'mech_eff': mech_eff,
        'driver_mode': 'turb_eff',
        'driver_val': 35.0,
        'gas_comp': gas_comp,
        'eos_method': eos_method,
        'rpm': 0.0
    }
    
    res = engine.evaluate_performance(inputs)
    print("=" * 60)
    print(f"UI Default - Performance Output")
    print(f"Flow: {flow_kgs:.2f} kg/s")
    print(f"Shaft Power: {res['shaft_power_kw']:.1f} kW")
    print(f"Gas Power: {res['gas_power_kw']:.1f} kW")
    print(f"Poly Eff: {res['poly_eff']:.2f} %")
    

if __name__ == "__main__":
    run_test()
