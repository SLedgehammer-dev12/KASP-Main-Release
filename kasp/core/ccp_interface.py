"""
CCP (Petrobras) Integration Module
===================================

Provides alternative calculation backend using petrobras/ccp library.

This module adapts the petrobras/ccp library to work with KASP V4's
internal data structures and provides:
- Alternative calculation engine (validation)
- REFPROP support (when available)
- Industry-standard calculations (Petrobras)

Author: KASP V4 Development Team
License: Same as KASP V4
"""

import logging
from typing import Dict, Optional, Any

# Try to import ccp
try:
    import ccp
    from ccp import Q_  # pint quantity for units
    CCP_AVAILABLE = True
except ImportError:
    CCP_AVAILABLE = False
    Q_ = None


class CCPImportError(Exception):
    """Raised when CCP library is not available"""
    pass


class CCPAdapter:
    """
    Adapter for petrobras/ccp library
    
    Converts KASP V4 inputs to CCP format and vice versa.
    Provides transparent integration with existing KASP workflow.
    
    Example:
        >>> adapter = CCPAdapter()
        >>> results = adapter.calculate_performance(kasp_inputs)
        >>> print(results['t_out'], results['power_kw'])
    """
    
    # Component name mapping: KASP -> CCP
    COMPONENT_MAPPING = {
        'METHANE': 'Methane',
        'ETHANE': 'Ethane',
        'PROPANE': 'Propane',
        'BUTANE': 'n-Butane',
        'ISOBUTANE': 'IsoButane',
        'PENTANE': 'n-Pentane',
        'ISOPENTANE': 'Isopentane',
        'HEXANE': 'n-Hexane',
        'HEPTANE': 'n-Heptane',
        'OCTANE': 'n-Octane',
        'NONANE': 'n-Nonane',
        'DECANE': 'n-Decane',
        'NITROGEN': 'Nitrogen',
        'CARBONDIOXIDE': 'CarbonDioxide',
        'HYDROGENSULFIDE': 'HydrogenSulfide',
        'HYDROGEN': 'Hydrogen',
        'OXYGEN': 'Oxygen',
        'WATER': 'Water',
        'HELIUM': 'Helium',
        'ARGON': 'Argon',
        'AIR': 'Air',
    }
    
    def __init__(self, use_refprop: bool = False):
        """
        Initialize CCP adapter
        
        Args:
            use_refprop: Use REFPROP instead of CoolProp (requires license)
        
        Raises:
            CCPImportError: If CCP library is not installed
        """
        if not CCP_AVAILABLE:
            raise CCPImportError(
                "petrobras/ccp library not installed.\n"
                "Install with: pip install ccp"
            )
        
        self.logger = logging.getLogger(__name__)
        self.use_refprop = use_refprop
        
        # Check REFPROP availability if requested
        if use_refprop:
            try:
                # Try to use REFPROP
                test_state = ccp.State(
                    fluid={'Methane': 1.0},
                    p=Q_(1, 'bar'),
                    T=Q_(300, 'K'),
                    EOS='REFPROP'
                )
                self.logger.info("✓ REFPROP available and working")
            except Exception as e:
                self.logger.warning(f"REFPROP not available: {e}")
                self.logger.info("Falling back to CoolProp")
                self.use_refprop = False
        
        self.logger.info(
            f"CCP Adapter initialized (EOS: {'REFPROP' if self.use_refprop else 'CoolProp'})"
        )
    
    def calculate_performance(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate compressor performance using CCP
        
        Args:
            inputs: KASP V4 standard input dictionary with keys:
                - gas_comp: Gas composition dict (% basis)
                - p_in, p_in_unit: Inlet pressure
                - t_in, t_in_unit: Inlet temperature
                - p_out, p_out_unit: Outlet pressure
                - flow, flow_unit: Mass flow rate
                - poly_eff: Polytropic efficiency (%)
                - speed: Rotational speed (optional)
                - impeller_diameter: D (m, optional)
                - blade_height: b (m, optional)
        
        Returns:
            Dictionary with keys:
                - t_out: Outlet temperature (K)
                - p_out: Outlet pressure (Pa)
                - head_kj_kg: Polytropic head (kJ/kg)
                - power_kw: Shaft power (kW)
                - efficiency: Actual efficiency
                - z_avg: Average compressibility factor
                - calculation_backend: 'CCP/Petrobras' or 'CCP/REFPROP'
        """
        try:
            # Convert gas composition
            fluid = self._convert_gas_composition(inputs['gas_comp'])
            
            # Create suction state
            suc = ccp.State(
                fluid=fluid,
                p=Q_(inputs['p_in'], inputs['p_in_unit']),
                T=Q_(inputs['t_in'], inputs['t_in_unit']),
                EOS='REFPROP' if self.use_refprop else 'PR'  # CCP default
            )
            
            # Estimate discharge state for initial point
            # (CCP needs discharge for Point creation)
            p_out_q = Q_(inputs['p_out'], inputs['p_out_unit'])
            
            # Initial temperature estimate using isentropic relation
            pressure_ratio = p_out_q.magnitude / suc.p.magnitude
            k_guess = 1.3  # Typical for natural gas
            t_out_guess = suc.T.magnitude * (pressure_ratio ** ((k_guess - 1) / k_guess))
            
            disch_initial = ccp.State(
                fluid=fluid,
                p=p_out_q,
                T=Q_(t_out_guess, 'K'),
                EOS='REFPROP' if self.use_refprop else 'PR'
            )
            
            # Convert flow rate
            flow_q = self._convert_flow_rate(inputs['flow'], inputs['flow_unit'])
            
            # Get geometric parameters (if available)
            b = inputs.get('blade_height', 0.0285)  # Default: 28.5 mm
            D = inputs.get('impeller_diameter', 0.365)  # Default: 365 mm
            speed = inputs.get('speed', 7500)  # Default: 7500 RPM
            
            # Create performance point
            point = ccp.Point(
                suc=suc,
                disch=disch_initial,
                speed=Q_(speed, 'RPM'),
                flow_m=flow_q,
                b=b,
                D=D
            )
            
            # Extract results
            results = {
                't_out': point.disch.T.to('K').magnitude,
                'p_out': point.disch.p.to('Pa').magnitude,
                'head_kj_kg': point.head.to('J/kg').magnitude / 1000.0,
                'power_kw': point.power.to('W').magnitude / 1000.0,
                'efficiency': point.eff.magnitude,
                'z_avg': self._compute_z_avg_log(suc.z().magnitude, point.disch.z().magnitude),
                'calculation_backend': 'CCP/REFPROP' if self.use_refprop else 'CCP/Petrobras',
                'ccp_version': ccp.__version__ if hasattr(ccp, '__version__') else 'unknown'
            }
            
            self.logger.debug(
                f"CCP calculation complete: T_out={results['t_out']:.1f}K, "
                f"Power={results['power_kw']:.1f}kW"
            )
            
            return results
            
        except Exception as e:
            self.logger.error(f"CCP calculation failed: {e}", exc_info=True)
            raise RuntimeError(f"CCP calculation error: {e}")
            
    def _compute_z_avg_log(self, z1: float, z2: float) -> float:
        import math
        if abs(z2 - z1) < 1e-6:
            return (z1 + z2) / 2.0
        try:
            return (z2 - z1) / math.log(z2 / z1)
        except (ValueError, ZeroDivisionError):
            return (z1 + z2) / 2.0
    
    def _convert_gas_composition(self, kasp_comp: Dict[str, float]) -> Dict[str, float]:
        """
        Convert KASP composition to CCP format
        
        Args:
            kasp_comp: {component: percentage} (0-100 scale)
        
        Returns:
            {component: mole_fraction} (0-1 scale)
        """
        ccp_comp = {}
        
        for comp, percentage in kasp_comp.items():
            comp_upper = comp.upper()
            ccp_name = self.COMPONENT_MAPPING.get(comp_upper, comp)
            
            # Convert percentage to mole fraction
            ccp_comp[ccp_name] = percentage / 100.0
        
        # Validate total
        total = sum(ccp_comp.values())
        if abs(total - 1.0) > 0.01:
            self.logger.warning(
                f"Composition sum = {total:.4f}, normalizing to 1.0"
            )
            ccp_comp = {k: v/total for k, v in ccp_comp.items()}
        
        return ccp_comp
    
    def _convert_flow_rate(self, value: float, unit: str) -> Any:
        """
        Convert flow rate to pint quantity
        
        Args:
            value: Flow rate value
            unit: Unit string (kg/s, kg/h, etc.)
        
        Returns:
            pint Quantity
        """
        # Map KASP units to pint units
        unit_mapping = {
            'kg/s': 'kg/s',
            'kg/h': 'kg/hr',
            'lb/h': 'lb/hr',
        }
        
        pint_unit = unit_mapping.get(unit, unit)
        return Q_(value, pint_unit)
    
    def compare_with_kasp(self, kasp_results: Dict, ccp_results: Dict) -> Dict:
        """
        Compare KASP and CCP results
        
        Args:
            kasp_results: Results from KASP Native calculation
            ccp_results: Results from CCP calculation
        
        Returns:
            Dictionary with comparison metrics
        """
        def percent_diff(kasp_val, ccp_val):
            """Calculate percentage difference"""
            if kasp_val == 0:
                return 0.0
            return ((ccp_val - kasp_val) / kasp_val) * 100.0
        
        comparison = {
            't_out_diff_percent': percent_diff(
                kasp_results.get('t_out', 0) + 273.15,  # Convert °C to K
                ccp_results['t_out']
            ),
            'head_diff_percent': percent_diff(
                kasp_results.get('head_kj_kg', 0),
                ccp_results['head_kj_kg']
            ),
            'power_diff_percent': percent_diff(
                kasp_results.get('power_unit_kw', 0),
                ccp_results['power_kw']
            ),
            'efficiency_diff_percent': percent_diff(
                kasp_results.get('actual_poly_efficiency', 0),
                ccp_results['efficiency']
            ),
        }
        
        # Overall agreement metric
        max_diff = max(abs(v) for v in comparison.values())
        comparison['max_deviation_percent'] = max_diff
        comparison['agreement_status'] = (
            'Excellent' if max_diff < 1.0 else
            'Good' if max_diff < 3.0 else
            'Acceptable' if max_diff < 5.0 else
            'Poor'
        )
        
        return comparison


def is_ccp_available() -> bool:
    """Check if CCP library is available"""
    return CCP_AVAILABLE


def get_ccp_info() -> Dict[str, Any]:
    """Get CCP library information"""
    if not CCP_AVAILABLE:
        return {
            'available': False,
            'message': 'CCP library not installed'
        }
    
    return {
        'available': True,
        'version': getattr(ccp, '__version__', 'unknown'),
        'refprop_available': _check_refprop_available()
    }


def _check_refprop_available() -> bool:
    """Check if REFPROP is available"""
    try:
        test_state = ccp.State(
            fluid={'Methane': 1.0},
            p=Q_(1, 'bar'),
            T=Q_(300, 'K'),
            EOS='REFPROP'
        )
        return True
    except:
        return False
