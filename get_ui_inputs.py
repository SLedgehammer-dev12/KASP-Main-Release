import sys
import json
from PyQt5.QtWidgets import QApplication
from kasp.ui.main_window import KaspMainWindow

app = QApplication(sys.argv)
window = KaspMainWindow()

# UI üzerindeki inputs sözlüğünü çekelim
inputs = window._get_design_inputs()

print("UI'dan çekilen Inputs:")
print(json.dumps(inputs, indent=4, ensure_ascii=False))

print("\nMotor Çalıştırılıyor (UI Girdisi ile)...")
from kasp.core.thermo import ThermoEngine
engine = ThermoEngine()
res = engine.calculate_design_performance(inputs)

print(f"  Head (kJ/kg)      : {res.get('head_kj_kg', 0):.2f}")
print(f"  T_out (°C)        : {res.get('t_out', 0):.2f}")
print(f"  Gas Power (kW)    : {res.get('power_gas_per_unit_kw', 0):.2f}")
print(f"  Shaft Power (kW)  : {res.get('power_shaft_per_unit_kw', 0):.2f}")
print(f"  Unit Power (kW)   : {res.get('power_unit_kw', 0):.2f}")
