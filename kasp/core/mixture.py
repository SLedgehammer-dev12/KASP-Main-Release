"""Gas mixture normalization and backend-specific payload builders."""

from __future__ import annotations

import logging
from typing import Any

from kasp.core.constants import MOLAR_MASSES, SUPPORTED_GASES, normalize_component
from kasp.core.exceptions import FluidPropertyError

logger = logging.getLogger(__name__)


class GasMixtureBuilder:
    """Build gas mixture payloads for CoolProp and Thermo backends."""

    THERMO_ID_MAP = {
        "METHANE": "methane",
        "ETHANE": "ethane",
        "PROPANE": "propane",
        "ISOBUTANE": "isobutane",
        "BUTANE": "butane",
        "ISOPENTANE": "isopentane",
        "PENTANE": "pentane",
        "HEXANE": "hexane",
        "HEPTANE": "heptane",
        "OCTANE": "octane",
        "NONANE": "nonane",
        "DECANE": "decane",
        "HYDROGEN": "hydrogen",
        "HYDROGENSULFIDE": "hydrogen sulfide",
        "NITROGEN": "nitrogen",
        "CARBONDIOXIDE": "carbon dioxide",
        "WATER": "water",
        "OXYGEN": "oxygen",
        "ARGON": "argon",
        "HELIUM": "helium",
        "NEON": "neon",
        "KRYPTON": "krypton",
        "XENON": "xenon",
        "AIR": "air",
    }

    @staticmethod
    def _canonicalize_composition(composition: dict[str, float]) -> dict[str, float]:
        canonical_composition: dict[str, float] = {}
        for component, percentage in composition.items():
            canonical = normalize_component(component)
            try:
                percentage_float = float(percentage)
            except (TypeError, ValueError) as error:
                raise FluidPropertyError(f"Gecersiz bilesen orani: {component}={percentage}") from error
            canonical_composition[canonical] = canonical_composition.get(canonical, 0.0) + percentage_float
        return canonical_composition

    @staticmethod
    def _normalize_percentages(canonical_composition: dict[str, float]) -> dict[str, float]:
        total = sum(canonical_composition.values())
        if total <= 0:
            raise FluidPropertyError("Gaz kompozisyonu toplami pozitif olmalidir")
        if abs(total - 100.0) > 0.1:
            logger.warning("Gaz kompozisyonu toplami %.2f. Normalize ediliyor...", total)
            return {
                component: (percentage / total) * 100.0
                for component, percentage in canonical_composition.items()
            }
        return canonical_composition

    @staticmethod
    def validate_and_normalize(composition: dict[str, float]) -> dict[str, float]:
        if not composition:
            raise FluidPropertyError("Gaz kompozisyonu bos olamaz")

        canonical_composition = GasMixtureBuilder._normalize_percentages(
            GasMixtureBuilder._canonicalize_composition(composition)
        )

        composition_fraction: dict[str, float] = {}
        for component, percentage in canonical_composition.items():
            fraction = percentage / 100.0
            if fraction < 0:
                raise FluidPropertyError(f"Negatif bilesen orani engellendi: {component}")
            if fraction > 1.0 + 1e-9:
                raise FluidPropertyError(f"Hatali bilesen orani (>1.0): {component}")
            if component not in SUPPORTED_GASES:
                raise FluidPropertyError(
                    f"Desteklenmeyen gaz bileseni: '{component}'. "
                    f"Gecerli bilesenler: {sorted(SUPPORTED_GASES.keys())}"
                )
            composition_fraction[component] = min(fraction, 1.0)

        if GasMixtureBuilder.check_phase_stability(composition_fraction):
            logger.warning("Gaz kompozisyonu agir hidrokarbon iceriyor (faz ayrimi riski)")

        return composition_fraction

    @staticmethod
    def calculate_mixture_mw(composition_fraction: dict[str, float]) -> float:
        return sum(
            MOLAR_MASSES.get(component, 0.0) * fraction
            for component, fraction in composition_fraction.items()
        )

    @staticmethod
    def check_phase_stability(composition_fraction: dict[str, float]) -> bool:
        heavy_components = ["HEXANE", "HEPTANE", "OCTANE", "NONANE", "DECANE"]
        heavy_fraction = sum(composition_fraction.get(component, 0.0) for component in heavy_components)
        if heavy_fraction > 0.02:
            return True

        methane_frac = composition_fraction.get("METHANE", 0.0)
        ethane_frac = composition_fraction.get("ETHANE", 0.0)
        if methane_frac + ethane_frac < 0.7 and len(composition_fraction) > 2:
            return True
        return False

    @staticmethod
    def build_coolprop_string(composition_fraction: dict[str, float]) -> str:
        if len(composition_fraction) == 1:
            component, fraction = next(iter(composition_fraction.items()))
            if abs(fraction - 1.0) < 1e-6:
                safe_name = SUPPORTED_GASES.get(component.upper())
                if safe_name:
                    return safe_name
                raise FluidPropertyError(f"CoolProp desteksiz: {component}")

        components = []
        for component, fraction in composition_fraction.items():
            if fraction <= 1e-6:
                continue
            safe_name = SUPPORTED_GASES.get(component.upper())
            if safe_name:
                components.append(f"{safe_name}[{fraction:.8f}]")
            else:
                logger.warning("Bilinmeyen gaz: %s, atlaniyor", component)

        if not components:
            raise FluidPropertyError("Gecerli CoolProp gaz bileseni bulunamadi")
        return "&".join(components)

    @staticmethod
    def build_thermo_data(composition_fraction: dict[str, float]) -> dict[str, Any]:
        ids: list[str] = []
        mol_fractions: list[float] = []
        mixture_mw = GasMixtureBuilder.calculate_mixture_mw(composition_fraction)

        for component, fraction in composition_fraction.items():
            if fraction <= 1e-6:
                continue

            thermo_id = GasMixtureBuilder.THERMO_ID_MAP.get(component)
            if thermo_id is None:
                logger.warning("Thermo ID tablosunda bulunamadi: '%s', atlaniyor.", component)
                continue

            ids.append(thermo_id)
            mol_fractions.append(fraction)

        if not ids:
            raise FluidPropertyError("Gecerli Thermo gaz bileseni bulunamadi")

        return {
            "ids": ids,
            "mol_fractions": mol_fractions,
            "MW": mixture_mw,
        }
