import json
import sys
from kasp.core.thermo import ThermoEngine

def main():
    engine = ThermoEngine()
    
    file_path = "dist/doğubayazıt 4. ünite.kasp"
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error loading {file_path}: {e}")
        return
        
    inputs = data.get("inputs", {})
    if not inputs:
        print("No inputs found in the file.")
        return

    # To avoid modifying the original inputs
    base_inputs = inputs.copy()
    
    methods = [
        'Metot 1: Ortalama Özellikler',
        'Metot 2: Uç Nokta İterasyonu',
        'Metot 3: Artımlı Basınç Adımları',
        'Metot 4: Doğrudan H-S Yöntemi'
    ]
    
    eos_methods = ['coolprop', 'pr', 'srk']
    
    print("=========================================================================================")
    print(" EOS Karşılaştırması - Çıkış Sıcaklıkları ve Güç")
    print("=========================================================================================")
    print(f"{'Metot / EOS':<40} | {'T_out (°C)':<12} | {'Head (kJ/kg)':<14} | {'Gas Power (kW)':<14}")
    print("-" * 89)
    
    for method in methods:
        for eos in eos_methods:
            run_inputs = base_inputs.copy()
            run_inputs['method'] = method
            run_inputs['eos_method'] = eos
            
            try:
                results = engine.calculate_design_performance(run_inputs)
                t_out = results.get('t_out', 0)
                head = results.get('head_kj_kg', 0)
                power = results.get('power_gas_total_kw', 0)
                
                print(f"{method[:20]} - {eos:<15} | {t_out:>10.2f} | {head:>12.2f} | {power:>12.2f}")
            except Exception as e:
                print(f"{method[:20]} - {eos:<15} | ERROR: {str(e)[:50]}")
        print("-" * 89)

if __name__ == "__main__":
    main()
