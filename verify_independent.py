import CoolProp.CoolProp as CP
import math

def independent_verification():
    print("--- INDEPENDENT COOLPROP VERIFICATION ---")
    
    # Mix definition
    gas = "HEOS::Methane[0.9]&Ethane[0.05]&Propane[0.05]"
    
    # State 1 (Inlet)
    p1 = 2000000.0  # 20 bar
    t1 = 303.15     # 30 C
    
    h1 = CP.PropsSI('Hmass', 'P', p1, 'T', t1, gas)
    s1 = CP.PropsSI('Smass', 'P', p1, 'T', t1, gas)
    d1 = CP.PropsSI('Dmass', 'P', p1, 'T', t1, gas)
    z1 = CP.PropsSI('Z', 'P', p1, 'T', t1, gas)
    
    # Isentropic State (Outlet)
    p2 = 6000000.0  # 60 bar
    h2_is = CP.PropsSI('Hmass', 'P', p2, 'Smass', s1, gas)
    t2_is = CP.PropsSI('T', 'P', p2, 'Smass', s1, gas)
    s2_is = CP.PropsSI('Smass', 'P', p2, 'T', t2_is, gas)
    z2_is = CP.PropsSI('Z', 'P', p2, 'T', t2_is, gas)
    
    mass_flow = 50000.0 / 3600.0  # 13.88 kg/s
    
    # Isentropic Work
    head_is = (h2_is - h1) / 1000.0  # kJ/kg
    power_is = mass_flow * head_is  # kW
    
    print(f"Isentropic Head: {head_is:.2f} kJ/kg")
    print(f"Isentropic Gas Power: {power_is:.2f} kW")
    
    # Polytropic Work (Target eff = 85%)
    # We iteratively find actual T2 that satisfies PolyEff = 85%
    poly_eff_target = 0.85
    R_spec = 8.314462 / (18.1 / 1000.0) # approx
    
    t2_guess = t2_is + 20
    for _ in range(50):
        h2_act = CP.PropsSI('Hmass', 'P', p2, 'T', t2_guess, gas)
        z2_act = CP.PropsSI('Z', 'P', p2, 'T', t2_guess, gas)
        
        # approximate Z_avg log
        try:
            z_avg = (z2_act - z1) / math.log(z2_act / z1)
        except:
             z_avg = (z2_act + z1) / 2.0
             
        n_over_n_minus_1 = math.log(p2/p1) / math.log(t2_guess/t1)
        sigma = 1.0 / n_over_n_minus_1
        
        # Real PTC 10 head
        R_real = CP.PropsSI('gas_constant', 'P', p1, 'T', t1, gas) / CP.PropsSI('molar_mass', 'P', p1, 'T', t1, gas)
        head_poly = (z_avg * R_real * t1 * (1.0 / sigma) * (math.pow(p2/p1, sigma) - 1.0)) / 1000.0
        
        calc_eff = head_poly / ((h2_act - h1)/1000.0)
        t2_guess += 10.0 * (calc_eff - poly_eff_target)
        
    actual_power = mass_flow * head_poly / poly_eff_target
    
    print(f"Polytropic Head (PTC 10): {head_poly:.2f} kJ/kg")
    print(f"Actual Gas Power (85% eff): {actual_power:.2f} kW")
    print(f"Final T2: {t2_guess - 273.15:.2f} C")

if __name__ == '__main__':
    independent_verification()
