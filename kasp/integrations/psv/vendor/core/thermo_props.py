import logging
from .constants import (
    COOLPROP_FALLBACK_Z, COOLPROP_FALLBACK_MW, COOLPROP_FALLBACK_K,
    COOLPROP_REF_TEMP_K, COOLPROP_REF_PRESSURE_PA,
)

logger = logging.getLogger(__name__)

try:
    import CoolProp.CoolProp as CP
    COOLPROP_AVAILABLE = True
except ImportError:
    COOLPROP_AVAILABLE = False
    logger.warning("CoolProp not available. Mixture property auto-calculation disabled.")

COOLPROP_FALLBACK_DEFAULTS = {
    'Z': COOLPROP_FALLBACK_Z,
    'MW': COOLPROP_FALLBACK_MW,
    'k': COOLPROP_FALLBACK_K
}

_MW_CACHE = {}

def calculate_mixture_properties(composition_dict, t_rankine, p_psia, fraction_type="mole"):
    """
    composition_dict: dict of fluid fractions (0 to 1) e.g. {'Methane': 0.8, 'Ethane': 0.2}
    t_rankine: Temperature in Rankine
    p_psia: Pressure in psia
    fraction_type: "mole" or "mass"
    Returns: Z (Compressibility), MW (Molecular Weight g/mol), k (Specific Heat Ratio)
    """
    if not composition_dict:
        raise ValueError("No composition provided.")

    if not COOLPROP_AVAILABLE:
        logger.warning("CoolProp unavailable, returning default fallback values.")
        return (
            COOLPROP_FALLBACK_DEFAULTS['Z'],
            COOLPROP_FALLBACK_DEFAULTS['MW'],
            COOLPROP_FALLBACK_DEFAULTS['k']
        )

    t_k = t_rankine * 5.0 / 9.0
    p_pa = p_psia * 6894.757

    clean_comp = {}
    for f, v in composition_dict.items():
        name = "Water" if f == "Water (Steam)" else f
        clean_comp[name] = clean_comp.get(name, 0.0) + v
    composition_dict = clean_comp

    total_input = sum(composition_dict.values())
    if abs(total_input - 1.0) > 1e-3:
        raise ValueError(f"Sum of fractions must be 1.0 (or 100%). Current sum: {total_input*100:.2f}%")

    composition_normalized = {k: v/total_input for k, v in composition_dict.items()}

    if fraction_type.lower() == "mass":
        mole_fractions = {}
        total_moles = 0.0
        for fluid, mass_frac in composition_normalized.items():
            try:
                if fluid not in _MW_CACHE:
                    _MW_CACHE[fluid] = CP.PropsSI('molar_mass', 'T', COOLPROP_REF_TEMP_K, 'P', COOLPROP_REF_PRESSURE_PA, fluid)
                mw_pure = _MW_CACHE[fluid]
                moles = mass_frac / mw_pure
                mole_fractions[fluid] = moles
                total_moles += moles
            except Exception as e:
                raise ValueError(f"Could not get properties for {fluid}: {str(e)}")

        composition_normalized = {k: v/total_moles for k, v in mole_fractions.items()}

    if len(composition_normalized) == 1:
        fluid = list(composition_normalized.keys())[0]
        fluid_str = fluid
    else:
        fluid_str = "HEOS::" + "&".join([f"{f}[{v}]" for f, v in composition_normalized.items()])

    try:
        z = CP.PropsSI('Z', 'T', t_k, 'P', p_pa, fluid_str)
        mw = CP.PropsSI('molar_mass', 'T', t_k, 'P', p_pa, fluid_str) * 1000.0
        cp = CP.PropsSI('Cpmass', 'T', t_k, 'P', p_pa, fluid_str)
        cv = CP.PropsSI('Cvmass', 'T', t_k, 'P', p_pa, fluid_str)
        k = cp / cv
        return z, mw, k
    except Exception as e:
        error_msg = str(e).lower()
        if "binary pair" in error_msg or "interaction" in error_msg or "not match" in error_msg:
            return calculate_ideal_mixture_properties(composition_normalized, t_k, p_pa)
        logger.warning(f"CoolProp calculation failed: {e}, falling back to defaults.")
        return (
            COOLPROP_FALLBACK_DEFAULTS['Z'],
            COOLPROP_FALLBACK_DEFAULTS['MW'],
            COOLPROP_FALLBACK_DEFAULTS['k']
        )

def calculate_ideal_mixture_properties(mole_fractions, t_k, p_pa):
    """Fallback calculation using linear combination (Kay's rule) for missing interaction params."""
    z_mix = 0.0
    mw_mix = 0.0
    cp_mix = 0.0
    cv_mix = 0.0

    for fluid, y in mole_fractions.items():
        clean_fluid = "Water" if fluid == "Water (Steam)" else fluid
        try:
            mw_i = CP.PropsSI('molar_mass', 'T', t_k, 'P', p_pa, clean_fluid) * 1000.0
            phase = CP.PhaseSI('T', t_k, 'P', p_pa, clean_fluid)
            if 'liquid' in phase.lower():
                # Component is liquid at mixture P, use low-P vapor properties for gas mixture
                cp_i = CP.PropsSI('Cpmolar', 'T', t_k, 'P', 101325, clean_fluid)
                cv_i = CP.PropsSI('Cvmolar', 'T', t_k, 'P', 101325, clean_fluid)
                z_i = 1.0
            else:
                z_i = CP.PropsSI('Z', 'T', t_k, 'P', p_pa, clean_fluid)
                cp_i = CP.PropsSI('Cpmolar', 'T', t_k, 'P', p_pa, clean_fluid)
                cv_i = CP.PropsSI('Cvmolar', 'T', t_k, 'P', p_pa, clean_fluid)

            z_mix += y * z_i
            mw_mix += y * mw_i
            cp_mix += y * cp_i
            cv_mix += y * cv_i
        except Exception as pure_err:
            raise ValueError(f"Could not calculate pure properties for {fluid} at this state: {pure_err}")

    k_mix = cp_mix / cv_mix if cv_mix > 0 else COOLPROP_FALLBACK_DEFAULTS['k']
    return z_mix, mw_mix, k_mix


def get_coolprop_fluids():
    """Return a sorted list of all available CoolProp pure fluids."""
    if not COOLPROP_AVAILABLE:
        return []
    fluids_str = CP.get_global_param_string("FluidsList")
    fluids = sorted(fluids_str.split(","))
    if "Water" in fluids:
        fluids[fluids.index("Water")] = "Water (Steam)"
    return fluids
