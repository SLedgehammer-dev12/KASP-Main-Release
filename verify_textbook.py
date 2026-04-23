import math

def calculate_textbook_compressor_power():
    # Textbook formula for compressor gas power:
    # P (kW) = [ n / (n-1) ] * (Z_avg * R * T1) * [ (P2/P1)^((n-1)/n) - 1 ] * (mass_flow / poly_eff)
    
    # Inputs from our verify_eos.py test
    mass_flow_kgh = 50000.0
    mass_flow_kgs = mass_flow_kgh / 3600.0
    
    P1 = 20.0
    P2 = 60.0
    PR = P2 / P1
    
    T1_C = 30.0
    T1_K = T1_C + 273.15
    
    poly_eff = 0.85
    
    # Natural gas properties (Methane 90%, Ethane 5%, Propane 5%)
    # MW ~ 0.9*16 + 0.05*30 + 0.05*44 = 14.4 + 1.5 + 2.2 = 18.1 g/mol = 0.0181 kg/mol
    MW = 18.1 / 1000.0
    R_universal = 8.314462  # J/mol.K
    R_specific = R_universal / MW / 1000.0 # kJ/kg.K  (8.314/18.1*1000/1000) = 0.459
    
    # Typical k value (gamma) for natural gas is around 1.3
    k = 1.3
    n_over_n_minus_1 = (k / (k-1)) * poly_eff
    n_minus_1_over_n = 1.0 / n_over_n_minus_1
    
    # Compressibility (Z)
    Z1 = 0.95
    Z2 = 0.88
    Z_avg = (Z1 + Z2) / 2.0
    
    # Polytropic Head (kJ/kg)
    H_p = Z_avg * R_specific * T1_K * n_over_n_minus_1 * (math.pow(PR, n_minus_1_over_n) - 1)
    
    # Gas Power (kW) = mass_flow * H_p / poly_eff
    gas_power = mass_flow_kgs * H_p / poly_eff
    
    print(f"--- TEXTBOOK CALCULATION ---")
    print(f"Mass Flow: {mass_flow_kgs:.2f} kg/s")
    print(f"R_specific: {R_specific:.4f} kJ/kg.K")
    print(f"Z_avg: {Z_avg:.2f}")
    print(f"Polytropic Head: {H_p:.2f} kJ/kg")
    print(f"Gas Power: {gas_power:.2f} kW")
    
if __name__ == '__main__':
    calculate_textbook_compressor_power()
