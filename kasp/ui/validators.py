"""
Input Validation Module for KASP V4

Provides real-time input validation with visual feedback for improved UX.
Includes custom QLineEdit widget and validation manager.
"""

from PyQt5.QtWidgets import QLineEdit, QToolTip
from PyQt5.QtCore import pyqtSignal, Qt, QPoint
from PyQt5.QtGui import QPalette, QColor
import logging

try:
    from kasp.core.units import UnitSystem
    from kasp.core.exceptions import UnitConversionError
except ImportError:
    # Fallback for testing
    class UnitSystem:
        @staticmethod
        def convert_pressure(value, from_unit, to_unit):
            return float(value)
        
        @staticmethod
        def convert_temperature(value, from_unit, to_unit):
            return float(value)
    
    class UnitConversionError(Exception):
        pass


class ValidatedLineEdit(QLineEdit):
    """
    Enhanced QLineEdit with real-time validation and visual feedback.
    
    Features:
    - Automatic border color change (green/red/neutral)
    - Tooltip error messages on hover
    - Validation on text change
    - Custom validation functions
    """
    
    validation_changed = pyqtSignal(bool, str)  # (is_valid, error_message)
    
    # Style templates
    STYLE_NEUTRAL = """
        QLineEdit {
            border: 1px solid #bdc3c7;
            padding: 4px;
            border-radius: 3px;
        }
    """
    
    STYLE_VALID = """
        QLineEdit {
            border: 2px solid #27ae60;
            background-color: #e8f8f3;
            padding: 4px;
            border-radius: 3px;
        }
    """
    
    STYLE_INVALID = """
        QLineEdit {
            border: 2px solid #e74c3c;
            background-color: #ffe6e6;
            padding: 4px;
            border-radius: 3px;
        }
    """
    
    STYLE_WARNING = """
        QLineEdit {
            border: 2px solid #f39c12;
            background-color: #fff3e0;
            padding: 4px;
            border-radius: 3px;
        }
    """
    
    def __init__(self, validation_func=None, parent=None):
        """
        Initialize validated line edit.
        
        Args:
            validation_func: Callable that takes (value, context) and returns (bool, str)
                           Returns (is_valid, error_message)
            parent: Parent widget
        """
        super().__init__(parent)
        self.logger = logging.getLogger(self.__class__.__name__)
        
        self.validation_func = validation_func
        self.validation_context = {}  # Extra context for validation (e.g., unit)
        self.is_valid = True
        self.error_message = ""
        self.has_been_edited = False
        
        # Connect signals
        self.textChanged.connect(self._on_text_changed)
        
        # Set initial style
        self.setStyleSheet(self.STYLE_NEUTRAL)
    
    def set_validation_context(self, context):
        """
        Set validation context (e.g., unit, related fields).
        
        Args:
            context: Dict with validation context
        """
        self.validation_context = context
        self._validate_current_text()
    
    def _on_text_changed(self, text):
        """Handle text change event."""
        self.has_been_edited = True
        self._validate_current_text()
    
    def _validate_current_text(self):
        """Validate current text and update visual state."""
        if not self.validation_func:
            return
        
        text = self.text().strip()
        
        # Don't validate empty required fields on first load
        if not text and not self.has_been_edited:
            self.is_valid = True
            self.error_message = ""
            self.setStyleSheet(self.STYLE_NEUTRAL)
            self.setToolTip("")
            self.validation_changed.emit(True, "")
            return
        
        try:
            is_valid, error_msg = self.validation_func(text, self.validation_context)
            
            self.is_valid = is_valid
            self.error_message = error_msg
            
            # Update visual style
            if is_valid:
                if error_msg:  # Warning message
                    self.setStyleSheet(self.STYLE_WARNING)
                    self.setToolTip(f"⚠️ {error_msg}")
                else:
                    self.setStyleSheet(self.STYLE_VALID)
                    self.setToolTip("")
            else:
                self.setStyleSheet(self.STYLE_INVALID)
                self.setToolTip(f"❌ {error_msg}")
            
            self.validation_changed.emit(is_valid, error_msg)
            
        except Exception as e:
            self.logger.error(f"Validation error: {e}")
            self.is_valid = False
            self.error_message = str(e)
            self.setStyleSheet(self.STYLE_INVALID)
            self.setToolTip(f"❌ Validation error: {e}")
            self.validation_changed.emit(False, str(e))
    
    def reset_validation(self):
        """Reset to neutral state."""
        self.has_been_edited = False
        self.is_valid = True
        self.error_message = ""
        self.setStyleSheet(self.STYLE_NEUTRAL)
        self.setToolTip("")


# Validation Functions

def validate_pressure(value, context):
    """
    Validate pressure input.
    
    Args:
        value: String value
        context: Dict with 'unit' key
    
    Returns:
        (is_valid, error_message)
    """
    if not value:
        return False, "Pressure is required"
    
    try:
        val = float(value)
        unit = context.get('unit', 'bar(a)')
        
        # Check for negative absolute pressure
        if unit in ['bar(a)', 'psia', 'kPa', 'MPa', 'Pa']:
            if val <= 0:
                return False, "Absolute pressure must be > 0"
        
        # Check gauge pressure
        if unit in ['bar(g)', 'psig']:
            if val < -1.0:
                return False, "Gauge pressure too low"
        
        # Reasonable range check
        if val > 1000:
            return True, f"⚠️ Very high pressure ({val:.1f} {unit})"
        
        return True, ""
        
    except ValueError:
        return False, "Invalid number format"


def validate_temperature(value, context):
    """
    Validate temperature input.
    
    Args:
        value: String value
        context: Dict with 'unit' key
    
    Returns:
        (is_valid, error_message)
    """
    if not value:
        return False, "Temperature is required"
    
    try:
        val = float(value)
        unit = context.get('unit', '°C')
        
        # Convert to Kelvin for absolute zero check
        try:
            k_val = UnitSystem.convert_temperature(val, unit, 'K')
            
            if k_val < 0:
                return False, "Below absolute zero!"
            
            if k_val < 100:
                return True, "⚠️ Very low temperature"
            
            if k_val > 800:
                return True, "⚠️ Very high temperature"
            
            return True, ""
            
        except UnitConversionError as e:
            return False, f"Unit conversion error: {e}"
        
    except ValueError:
        return False, "Invalid number format"


def validate_flow(value, context):
    """
    Validate flow rate input.
    
    Args:
        value: String value
        context: Dict with 'unit' key
    
    Returns:
        (is_valid, error_message)
    """
    if not value:
        return False, "Flow rate is required"
    
    try:
        val = float(value)
        
        if val <= 0:
            return False, "Flow must be positive"
        
        if val > 100000000:
            return True, "⚠️ Very high flow rate"
        
        return True, ""
        
    except ValueError:
        return False, "Invalid number format"


class ValidationManager:
    """
    Manages validation state across multiple inputs.
    
    Tracks all validated inputs and provides summary status.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.inputs = {}  # {field_name: ValidatedLineEdit}
        self.validation_states = {}  # {field_name: (is_valid, error_msg)}
    
    def register_input(self, field_name, validated_input):
        """
        Register a validated input.
        
        Args:
            field_name: Unique field identifier
            validated_input: ValidatedLineEdit instance
        """
        self.inputs[field_name] = validated_input
        self.validation_states[field_name] = (True, "")
        
        # Connect to validation change signal
        validated_input.validation_changed.connect(
            lambda valid, msg, name=field_name: self._on_validation_changed(name, valid, msg)
        )
    
    def _on_validation_changed(self, field_name, is_valid, error_msg):
        """Handle validation change event."""
        self.validation_states[field_name] = (is_valid, error_msg)
        self.logger.debug(f"Validation changed: {field_name} = {is_valid}")
    
    def all_inputs_valid(self):
        """
        Check if all registered inputs are valid.
        
        Returns:
            bool: True if all valid
        """
        return all(state[0] for state in self.validation_states.values())
    
    def get_invalid_fields(self):
        """
        Get list of invalid field names and error messages.
        
        Returns:
            List of tuples: [(field_name, error_message), ...]
        """
        return [
            (name, state[1]) 
            for name, state in self.validation_states.items() 
            if not state[0]
        ]
    
    def get_validation_summary(self):
        """
        Get validation summary for all fields.
        
        Returns:
            Dict with field statuses
        """
        summary = {
            'all_valid': self.all_inputs_valid(),
            'total_fields': len(self.validation_states),
            'valid_count': sum(1 for state in self.validation_states.values() if state[0]),
            'invalid_count': sum(1 for state in self.validation_states.values() if not state[0]),
            'fields': self.validation_states.copy()
        }
        return summary
