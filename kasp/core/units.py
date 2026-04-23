from .exceptions import UnitConversionError

class UnitSystem:
    """Merkezi birim yönetim sistemi"""
    
    STD_PRESS_PA = 101325.0
    NORMAL_TEMP_K = 273.15
    STANDARD_TEMP_K = 288.15
    GRAVITATIONAL_ACCELERATION = 9.80665
    R_UNIVERSAL_J_MOL_K = 8.314462
    KJ_PER_BTU = 1.055056
    KG_PER_LB = 0.45359237
    KJ_PER_KCAL = 4.184
    METER_TO_FOOT = 3.28084
    
    UNITS = {
        'pressure': ['bar', 'Pa', 'kPa', 'MPa', 'psi', 'atm', 'kg/cm²'],
        'temperature': ['°C', 'K', '°F', '°R'],
        'flow': ['kg/h', 'kg/s', 'm³/h', 'Sm³/h', 'Nm³/h', 'MMSCFD', 'MMSCMD', 'ACMH'],
        'power': ['kW', 'MW', 'hp', 'Btu/h'],
        'length': ['mm', 'm', 'inch', 'ft'],
        'energy': ['kJ', 'J', 'kcal', 'Btu', 'kWh']
    }
    
    @classmethod
    def convert_pressure(cls, value, from_unit, to_unit='Pa', ambient_pressure_pa=None):
        """Basınç birimi dönüşümü - Gauge ve Absolute desteği"""
        ambient = ambient_pressure_pa if ambient_pressure_pa is not None else cls.STD_PRESS_PA
        if from_unit == to_unit:
            return value
            
        # Gauge birimleri için absolute'e çevir
        is_gauge = False
        if from_unit in ['bar(g)', 'psig']:
            is_gauge = True
            if from_unit == 'bar(g)':
                from_unit = 'bar'
            elif from_unit == 'psig':
                from_unit = 'psi'
        
        # bar(a) -> bar çevirisi (absolute zaten)
        if from_unit.endswith('(a)'):
            from_unit = from_unit.replace('(a)', '')
        if from_unit == 'psia':
            from_unit = 'psi'
            
        # Önce Pa'ya çevir (absolute basınç)
        pa_value = 0
        if from_unit == 'Pa': 
            pa_value = value
        elif from_unit == 'kPa': 
            pa_value = value * 1000
        elif from_unit == 'MPa': 
            pa_value = value * 1e6
        elif from_unit == 'bar': 
            pa_value = value * 1e5
        elif from_unit == 'psi': 
            pa_value = value * 6894.76
        elif from_unit == 'atm': 
            pa_value = value * 101325
        elif from_unit == 'kg/cm²': 
            pa_value = value * 98066.5
        else: 
            raise UnitConversionError(f"Bilinmeyen basınç birimi: {from_unit}")
        
        # Eğer gauge ise, atmosferik basıncı ekle
        if is_gauge:
            pa_value += ambient
        
        # Pa'dan hedef birime çevir
        if to_unit == 'Pa': 
            return pa_value
        elif to_unit == 'kPa': 
            return pa_value / 1000
        elif to_unit == 'MPa': 
            return pa_value / 1e6
        elif to_unit == 'bar' or to_unit == 'bar(a)': 
            return pa_value / 1e5
        elif to_unit == 'psi' or to_unit == 'psia': 
            return pa_value / 6894.76
        elif to_unit == 'atm': 
            return pa_value / 101325
        elif to_unit == 'kg/cm²': 
            return pa_value / 98066.5
        elif to_unit == 'bar(g)':
            return (pa_value - ambient) / 1e5
        elif to_unit == 'psig':
            return (pa_value - ambient) / 6894.76
        else: 
            raise UnitConversionError(f"Bilinmeyen hedef basınç birimi: {to_unit}")


    @classmethod
    def convert_temperature(cls, value, from_unit, to_unit='K'):
        """Sıcaklık birimi dönüşümü"""
        if from_unit == to_unit:
            return value
            
        # Önce Kelvin'e çevir
        k_value = 0
        if from_unit == 'K': k_value = value
        elif from_unit == '°C': k_value = value + 273.15
        elif from_unit == '°F': k_value = (value + 459.67) * 5/9
        elif from_unit == '°R': k_value = value * 5/9
        else: raise UnitConversionError(f"Bilinmeyen sıcaklık birimi: {from_unit}")
        
        # Kelvin'den hedef birime çevir
        if to_unit == 'K': return k_value
        elif to_unit == '°C': return k_value - 273.15
        elif to_unit == '°F': return k_value * 9/5 - 459.67
        elif to_unit == '°R': return k_value * 9/5
        else: raise UnitConversionError(f"Bilinmeyen hedef sıcaklık birimi: {to_unit}")

    @classmethod
    def validate_pressure_value(cls, value, unit):
        """Basınç değerini valide et"""
        try:
            val = float(value)
            # Absolute pressure units cannot be negative
            if val < 0 and unit not in ['psi', 'bar']:
                raise UnitConversionError(
                    f"Negatif basınç değeri ({val} {unit}) geçersiz", val, unit
                )
            return True
        except ValueError:
            raise UnitConversionError(f"Geçersiz basınç değeri: {value}", value, unit)

    @classmethod
    def validate_temperature_value(cls, value, unit):
        """Sıcaklık değerini valide et"""
        try:
            val = float(value)
            # Mutlak sıfır kontrolü
            k_val = cls.convert_temperature(val, unit, 'K')
            if k_val < 0:
                raise UnitConversionError(f"Mutlak sıfırın altında sıcaklık: {val} {unit}")
            return True
        except ValueError:
            raise UnitConversionError(f"Geçersiz sıcaklık değeri: {value}")
