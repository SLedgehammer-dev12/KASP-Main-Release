class ThermodynamicError(Exception):
    """Termodinamik hesaplama hataları için temel sınıf"""
    pass

class ConvergenceError(ThermodynamicError):
    """Yakınsama hataları"""
    def __init__(self, message, iterations=None, last_error=None):
        self.iterations = iterations
        self.last_error = last_error
        super().__init__(message)

class FluidPropertyError(ThermodynamicError):
    """Akışkan özellik hataları"""
    def __init__(self, message, composition=None, conditions=None):
        self.composition = composition
        self.conditions = conditions
        super().__init__(message)

class UnitConversionError(ValueError):
    """Birim dönüşüm hataları"""
    def __init__(self, message, value=None, from_unit=None, to_unit=None):
        self.value = value
        self.from_unit = from_unit
        self.to_unit = to_unit
        super().__init__(message)

class AdvancedThermodynamicError(ThermodynamicError):
    """Gelişmiş termodinamik hatalar"""
    def __init__(self, message, fluid_state=None, operating_conditions=None, calculation_step=None):
        self.fluid_state = fluid_state
        self.operating_conditions = operating_conditions
        self.calculation_step = calculation_step
        super().__init__(message)

    def suggest_solution(self):
        """Hataya göre otomatik çözüm önerileri"""
        if "phase" in str(self).lower():
            return "Gaz kompozisyonunu kontrol edin veya giriş sıcaklığını artırın (Faz değişimi riski)."
        elif "convergence" in str(self).lower():
            return "Maksimum iterasyon sayısını artırın veya toleransı gevşetin."
        elif "property" in str(self).lower():
            return "Basınç ve sıcaklık değerlerinin makul aralıklarda olduğunu doğrulayın."
        return "Giriş parametrelerini ve birimlerini kontrol edin."

class InputValidationError(ValueError):
    """Girdi validasyon hataları"""
    def __init__(self, message, field_name=None, invalid_value=None, expected_range=None):
        self.field_name = field_name
        self.invalid_value = invalid_value
        self.expected_range = expected_range
        super().__init__(message)

class GasCompositionError(ThermodynamicError):
    """Gaz kompozisyonu hataları"""
    def __init__(self, message, composition=None, total_percentage=None):
        self.composition = composition
        self.total_percentage = total_percentage
        super().__init__(message)

class MethodNotImplementedError(NotImplementedError):
    """Henüz implement edilmemiş metodlar için hata"""
    def __init__(self, message, method_name=None, required_version=None):
        self.method_name = method_name
        self.required_version = required_version
        super().__init__(message)
