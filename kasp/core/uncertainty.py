"""
ASME PTC 10 Uncertainty Analysis Module

Provides comprehensive uncertainty analysis for compressor performance testing
following ASME PTC 10 (Performance Test Code) Appendix B requirements.

Key Features:
- Standard instrument accuracy database
- RSS (Root-Sum-Square) uncertainty propagation
- Sensitivity coefficient calculation
- Combined and expanded uncertainty
- 95% confidence intervals
"""

import numpy as np
import logging
from typing import Dict, Tuple, Callable, Optional, Any


class InstrumentDatabase:
    """
    Standard instrument accuracies per ASME PTC 10 and industry best practices.
    
    Provides typical uncertainty values for common measurement instruments
    used in compressor performance testing.
    """
    
    # Instrument accuracy specifications
    INSTRUMENTS = {
        # Pressure measurements
        'pressure_transducer_high': {
            'accuracy': 0.0025,  # ±0.25% of full scale
            'unit': '%FS',
            'description': 'High-accuracy pressure transducer'
        },
        'pressure_transducer_standard': {
            'accuracy': 0.005,  # ±0.5% of full scale
            'unit': '%FS',
            'description': 'Standard pressure transducer'
        },
        'pressure_gauge_analog': {
            'accuracy': 0.01,  # ±1.0% of full scale
            'unit': '%FS',
            'description': 'Analog pressure gauge'
        },
        
        # Temperature measurements
        'temperature_rtd_pt100': {
            'accuracy': 0.15,  # ±0.15°C
            'unit': '°C',
            'description': 'RTD Pt100 (Class A)'
        },
        'temperature_rtd_pt100_class_b': {
            'accuracy': 0.30,  # ±0.30°C
            'unit': '°C',
            'description': 'RTD Pt100 (Class B)'
        },
        'temperature_thermocouple_k': {
            'accuracy': 0.75,  # ±0.75°C
            'unit': '°C',
            'description': 'Type K Thermocouple'
        },
        'temperature_thermocouple_t': {
            'accuracy': 0.50,  # ±0.50°C
            'unit': '°C',
            'description': 'Type T Thermocouple'
        },
        
        # Flow measurements
        'flow_orifice': {
            'accuracy': 0.01,  # ±1.0% of reading
            'unit': '%',
            'description': 'Orifice flow meter'
        },
        'flow_turbine': {
            'accuracy': 0.005,  # ±0.5% of reading
            'unit': '%',
            'description': 'Turbine flow meter'
        },
        'flow_venturi': {
            'accuracy': 0.0075,  # ±0.75% of reading
            'unit': '%',
            'description': 'Venturi flow meter'
        },
        'flow_coriolis': {
            'accuracy': 0.001,  # ±0.1% of reading
            'unit': '%',
            'description': 'Coriolis mass flow meter'
        },
        
        # Power/Speed measurements
        'power_meter': {
            'accuracy': 0.002,  # ±0.2% of reading
            'unit': '%',
            'description': 'Digital power meter'
        },
        'speed_tachometer': {
            'accuracy': 0.0001,  # ±0.01% of reading
            'unit': '%',
            'description': 'Optical tachometer'
        },
    }
    
    @classmethod
    def get_instrument_accuracy(cls, instrument_type: str) -> float:
        """
        Get accuracy value for specified instrument type.
        
        Args:
            instrument_type: Instrument identifier (e.g., 'pressure_transducer_high')
        
        Returns:
            Accuracy value (as decimal, e.g., 0.0025 for 0.25%)
        
        Raises:
            KeyError: If instrument type not found in database
        """
        if instrument_type not in cls.INSTRUMENTS:
            raise KeyError(f"Instrument type '{instrument_type}' not found in database")
        
        return cls.INSTRUMENTS[instrument_type]['accuracy']
    
    @classmethod
    def get_instrument_info(cls, instrument_type: str) -> Dict[str, Any]:
        """
        Get complete information for specified instrument.
        
        Args:
            instrument_type: Instrument identifier
        
        Returns:
            Dict with accuracy, unit, and description
        """
        if instrument_type not in cls.INSTRUMENTS:
            raise KeyError(f"Instrument type '{instrument_type}' not found in database")
        
        return cls.INSTRUMENTS[instrument_type].copy()
    
    @classmethod
    def list_instruments(cls, category: Optional[str] = None) -> Dict[str, Dict]:
        """
        List all available instruments, optionally filtered by category.
        
        Args:
            category: Optional category filter ('pressure', 'temperature', 'flow', 'power')
        
        Returns:
            Dict of instrument specifications
        """
        if category is None:
            return cls.INSTRUMENTS.copy()
        
        category_lower = category.lower()
        filtered = {
            k: v for k, v in cls.INSTRUMENTS.items()
            if k.startswith(category_lower)
        }
        
        return filtered


class UncertaintyAnalyzer:
    """
    ASME PTC 10 Appendix B compliant uncertainty analysis.
    
    Implements Root-Sum-Square (RSS) method for propagating measurement
    uncertainties through thermodynamic calculations.
    
    Features:
    - Combined uncertainty calculation
    - Sensitivity coefficient calculation (numerical differentiation)
    - Expanded uncertainty with coverage factor (k=2 for 95% confidence)
    - Detailed uncertainty breakdown by parameter
    """
    
    def __init__(self, instrument_db: Optional[InstrumentDatabase] = None):
        """
        Initialize uncertainty analyzer.
        
        Args:
            instrument_db: InstrumentDatabase instance (creates new if None)
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.db = instrument_db or InstrumentDatabase()
        self.coverage_factor_95 = 2.0  # k=2 for 95% confidence (normal distribution)
    
    def calculate_combined_uncertainty(
        self,
        measurement_uncertainties: Dict[str, float],
        sensitivities: Dict[str, float]
    ) -> Tuple[float, Dict[str, float]]:
        """
        Calculate combined uncertainty using RSS method.
        
        ASME PTC 10 Equation: σ_combined = sqrt(Σ(S_i × σ_i)²)
        
        where:
            S_i = sensitivity coefficient (∂f/∂x_i)
            σ_i = uncertainty of parameter i
        
        Args:
            measurement_uncertainties: Dict of {parameter: uncertainty_value}
            sensitivities: Dict of {parameter: sensitivity_coefficient}
        
        Returns:
            Tuple of (combined_uncertainty, contributions_dict)
            - combined_uncertainty: Total combined uncertainty
            - contributions_dict: Individual contributions by parameter
        """
        if not measurement_uncertainties:
            self.logger.warning("No measurement uncertainties provided")
            return 0.0, {}
        
        contributions = {}
        sum_of_squares = 0.0
        
        for param, uncertainty in measurement_uncertainties.items():
            if param not in sensitivities:
                self.logger.warning(f"No sensitivity coefficient for parameter '{param}', skipping")
                continue
            
            sensitivity = sensitivities[param]
            contribution = sensitivity * uncertainty
            contributions[param] = abs(contribution)
            sum_of_squares += contribution ** 2
        
        combined_uncertainty = np.sqrt(sum_of_squares)
        
        self.logger.debug(
            f"Combined uncertainty: {combined_uncertainty:.6f} "
            f"from {len(contributions)} parameters"
        )
        
        return combined_uncertainty, contributions
    
    def calculate_expanded_uncertainty(
        self,
        combined_uncertainty: float,
        coverage_factor: Optional[float] = None
    ) -> float:
        """
        Calculate expanded uncertainty for specified confidence level.
        
        Expanded uncertainty: U = k × σ_combined
        
        Args:
            combined_uncertainty: Combined uncertainty value
            coverage_factor: Coverage factor (default: 2.0 for 95% confidence)
        
        Returns:
            Expanded uncertainty
        """
        k = coverage_factor if coverage_factor is not None else self.coverage_factor_95
        return k * combined_uncertainty
    
    def calculate_sensitivity_coefficient(
        self,
        calculation_function: Callable,
        parameter_name: str,
        base_inputs: Dict[str, Any],
        delta_fraction: float = 0.01
    ) -> float:
        """
        Calculate sensitivity coefficient using numerical differentiation.
        
        Sensitivity: S = ∂f/∂x ≈ (f(x + Δx) - f(x)) / Δx
        
        Uses central difference for better accuracy:
        S ≈ (f(x + Δx) - f(x - Δx)) / (2Δx)
        
        Args:
            calculation_function: Function that takes inputs dict and returns result
            parameter_name: Name of parameter to vary
            base_inputs: Base input parameters
            delta_fraction: Fractional change for differentiation (default: 1%)
        
        Returns:
            Sensitivity coefficient (∂result/∂parameter)
        """
        if parameter_name not in base_inputs:
            raise KeyError(f"Parameter '{parameter_name}' not found in base_inputs")
        
        base_value = base_inputs[parameter_name]
        delta = abs(base_value * delta_fraction)
        
        if delta == 0:
            delta = 1e-6  # Fallback for zero values
        
        # Calculate f(x + Δx)
        inputs_plus = base_inputs.copy()
        inputs_plus[parameter_name] = base_value + delta
        
        try:
            result_plus = calculation_function(inputs_plus)
        except Exception as e:
            self.logger.error(f"Error calculating f(x+Δx): {e}")
            raise
        
        # Calculate f(x - Δx)
        inputs_minus = base_inputs.copy()
        inputs_minus[parameter_name] = base_value - delta
        
        try:
            result_minus = calculation_function(inputs_minus)
        except Exception as e:
            self.logger.error(f"Error calculating f(x-Δx): {e}")
            raise
        
        # Central difference
        sensitivity = (result_plus - result_minus) / (2 * delta)
        
        self.logger.debug(
            f"Sensitivity of result to '{parameter_name}': "
            f"{sensitivity:.6e} (Δ={delta:.6e})"
        )
        
        return sensitivity
    
    def analyze_uncertainty(
        self,
        measurement_values: Dict[str, float],
        instrument_config: Dict[str, str],
        calculation_function: Callable,
        result_key: str = 'polytropic_efficiency'
    ) -> Dict[str, Any]:
        """
        Perform complete uncertainty analysis for a calculation.
        
        Args:
            measurement_values: Dict of {parameter: measured_value}
            instrument_config: Dict of {parameter: instrument_type}
            calculation_function: Function to analyze
            result_key: Key for extracting result from calculation output
        
        Returns:
            Dict with complete uncertainty analysis:
            - 'combined_uncertainty': Combined uncertainty
            - 'expanded_uncertainty': Expanded uncertainty (95%)
            - 'sensitivities': Sensitivity coefficients
            - 'contributions': Individual contributions
            - 'breakdown_percent': Percentage breakdown
        """
        # Get instrument uncertainties
        measurement_uncertainties = {}
        for param, instrument_type in instrument_config.items():
            if param not in measurement_values:
                continue
            
            try:
                accuracy = self.db.get_instrument_accuracy(instrument_type)
                measured_value = measurement_values[param]
                
                # Calculate absolute uncertainty
                instrument_info = self.db.get_instrument_info(instrument_type)
                if instrument_info['unit'] == '%FS' or instrument_info['unit'] == '%':
                    uncertainty = measured_value * accuracy
                else:  # Absolute units (e.g., °C)
                    uncertainty = accuracy
                
                measurement_uncertainties[param] = uncertainty
                
            except KeyError as e:
                self.logger.warning(f"Instrument type not found: {e}")
                continue
        
        # Calculate sensitivity coefficients
        sensitivities = {}
        for param in measurement_uncertainties.keys():
            try:
                def wrapped_function(inputs):
                    result = calculation_function(inputs)
                    if isinstance(result, dict):
                        return result.get(result_key, 0.0)
                    return result
                
                sensitivity = self.calculate_sensitivity_coefficient(
                    wrapped_function,
                    param,
                    measurement_values
                )
                sensitivities[param] = sensitivity
                
            except Exception as e:
                self.logger.error(f"Error calculating sensitivity for '{param}': {e}")
                continue
        
        # Calculate combined uncertainty
        combined_unc, contributions = self.calculate_combined_uncertainty(
            measurement_uncertainties,
            sensitivities
        )
        
        # Calculate expanded uncertainty
        expanded_unc = self.calculate_expanded_uncertainty(combined_unc)
        
        # Calculate percentage breakdown
        total_contribution = sum(abs(c) for c in contributions.values())
        breakdown_percent = {}
        if total_contribution > 0:
            for param, contrib in contributions.items():
                breakdown_percent[param] = (abs(contrib) / total_contribution) * 100
        
        analysis = {
            'combined_uncertainty': combined_unc,
            'expanded_uncertainty': expanded_unc,
            'coverage_factor': self.coverage_factor_95,
            'confidence_level': 0.95,
            'sensitivities': sensitivities,
            'contributions': contributions,
            'breakdown_percent': breakdown_percent,
            'measurement_uncertainties': measurement_uncertainties
        }
        
        self.logger.info(
            f"Uncertainty analysis complete: "
            f"σ_combined={combined_unc:.4e}, U_95%={expanded_unc:.4e}"
        )
        
        return analysis
