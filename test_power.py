import CoolProp.CoolProp as CP

P1 = 20e5
T1 = 303.15
P2 = 60e5

# Isentropic T2
S1 = CP.PropsSI('Smass', 'P', P1, 'T', T1, 'Methane')
H1 = CP.PropsSI('Hmass', 'P', P1, 'T', T1, 'Methane')
H2_s = CP.PropsSI('Hmass', 'P', P2, 'S', S1, 'Methane')

head_isen = (H2_s - H1) / 1000.0
print(f"Isentropic Head: {head_isen} kJ/kg")

# Polytropic approx
poly_eff = 0.85
head_poly = head_isen / poly_eff
print(f"Polytropic Head (approx): {head_poly} kJ/kg")

mass_flow_kgs = 50000 / 3600.0
print(f"Mass flow: {mass_flow_kgs} kg/s")

power_kw = mass_flow_kgs * head_poly
print(f"Gas Power: {power_kw} kW")

shaft_power = power_kw / poly_eff
print(f"Shaft Power: {shaft_power} kW")
