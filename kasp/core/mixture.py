"""
KASP V4.4 Gas Mixture Builder
Gaz bileşenlerinin CoolProp (HEOS) ve Thermo kütüphaneleriyle uyumlu bir biçimde
normalizasyonunu (Mol Fraction), validasyonunu ve faz güvenlik (Phase Stability)
testlerini yürüten modül.
"""

import logging
from typing import Dict, Any

from kasp.core.exceptions import FluidPropertyError
from kasp.core.constants import (
    SUPPORTED_GASES, normalize_component
)

logger = logging.getLogger(__name__)

class GasMixtureBuilder:
    """Gaz kompozisyonu inşa ve validasyon aracı."""
    
    # Thermo (PR/SRK) kütüphanesi için bileşen isim tablosu (Sabit)
    THERMO_ID_MAP = {
        'METHANE':         'methane',
        'ETHANE':          'ethane',
        'PROPANE':         'propane',
        'ISOBUTANE':       'isobutane',
        'BUTANE':          'butane',
        'ISOPENTANE':      'isopentane',
        'PENTANE':         'pentane',
        'HEXANE':          'hexane',
        'HEPTANE':         'heptane',
        'OCTANE':          'octane',
        'NONANE':          'nonane',
        'DECANE':          'decane',
        'HYDROGEN':        'hydrogen',
        'HYDROGENSULFIDE': 'hydrogen sulfide',
        'NITROGEN':        'nitrogen',
        'CARBONDIOXIDE':   'carbon dioxide',
        'WATER':           'water',
        'OXYGEN':          'oxygen',
        'ARGON':           'argon',
        'HELIUM':          'helium',
        'NEON':            'neon',
        'KRYPTON':         'krypton',
        'XENON':           'xenon',
        'AIR':             'air',
    }

    @staticmethod
    def validate_and_normalize(composition: Dict[str, float]) -> Dict[str, float]:
        """
        Gelen dict'in (Örn: {'CH4': 90, 'CO2': 10}) anahtarlarını normalize eder.
        Toplamı %100'e (1.0 kesrine) oranlar ve bilinmeyen gazları reddeder.
        """
        if not composition:
            raise FluidPropertyError("Gaz kompozisyonu boş olamaz")

        # 1. Alias'ları (takma adları) canonical isimlere çevir
        composition_canonical = {}
        for comp, pct in composition.items():
            canonical = normalize_component(comp)
            if canonical in composition_canonical:
                composition_canonical[canonical] += pct
            else:
                composition_canonical[canonical] = pct

        # 2. %100 Toplam Kontrolü
        total = sum(composition_canonical.values())
        if abs(total - 100.0) > 0.1:
            logger.warning(
                f"Gaz kompozisyonu toplamı %{total:.2f}. Normalize ediliyor..."
            )
            composition_canonical = {
                k: (v / total) * 100.0 for k, v in composition_canonical.items()
            }

        # 3. Ondalık (Fraction) Dönüşümü ve Validasyon
        composition_fraction: Dict[str, float] = {}
        for comp, percentage in composition_canonical.items():
            fraction = percentage / 100.0
            if fraction < 0:
                raise FluidPropertyError(f"Negatif bileşen oranı engellendi: {comp}")
            if fraction > 1.0 + 1e-9:
                raise FluidPropertyError(f"Hatalı bileşen oranı (>1.0): {comp}")
                
            # Dictionary Validasyonu (Tek Kaynak Kontrolü)
            if comp not in SUPPORTED_GASES:
                raise FluidPropertyError(
                    f"Desteklenmeyen gaz bileşeni: '{comp}'. "
                    f"Geçerli bileşenler: {sorted(SUPPORTED_GASES.keys())}"
                )
                
            composition_fraction[comp] = min(fraction, 1.0)
            
        # 4. Faz Kontrolü (Ağır Hidrokarbon yoğunluğu uyarısı)
        if GasMixtureBuilder.check_phase_stability(composition_fraction):
            logger.warning(
                "Gaz kompozisyonu ağır hidrokarbon içeriyor (Faz ayrımı / Sıvılaşma riski)"
            )

        return composition_fraction

    @staticmethod
    def check_phase_stability(composition_fraction: Dict[str, float]) -> bool:
        """Basit sıvı faz/çiy noktası tahmini"""
        heavy_components = ['HEXANE', 'HEPTANE', 'OCTANE', 'NONANE', 'DECANE']
        heavy_fraction = sum(composition_fraction.get(comp, 0) for comp in heavy_components)
        
        if heavy_fraction > 0.02:
            return True  # 2%'den fazla ağır bileşen (çiy noktası riski)
            
        methane_frac = composition_fraction.get('METHANE', 0)
        ethane_frac = composition_fraction.get('ETHANE', 0)
        if methane_frac + ethane_frac < 0.7 and len(composition_fraction) > 2:
            return True  # C1+C2 toplamı %70'ten azsa riskli
            
        return False

    @staticmethod
    def build_coolprop_string(composition_fraction: Dict[str, float]) -> str:
        """CoolProp kütüphanesi için Mixture Stringi (Örn: 'Methane[0.9]&Ethane[0.1]') oluşturur."""
        if len(composition_fraction) == 1:
            comp, frac = next(iter(composition_fraction.items()))
            if abs(frac - 1.0) < 1e-6:
                safe_name = SUPPORTED_GASES.get(comp.upper())
                if safe_name: return safe_name
                raise FluidPropertyError(f"CoolProp desteksiz: {comp}")
        
        components = []
        for comp, frac in composition_fraction.items():
            if frac > 1e-6:
                safe_name = SUPPORTED_GASES.get(comp.upper())
                if safe_name:
                    components.append(f"{safe_name}[{frac:.8f}]")
                else:
                    logger.warning(f"Bilinmeyen gaz: {comp}, atlanıyor")
                    
        if not components:
            raise FluidPropertyError("Geçerli CoolProp gaz bileşeni bulunamadı")
            
        return '&'.join(components)

    @staticmethod
    def build_thermo_data(composition_fraction: Dict[str, float]) -> Dict[str, Any]:
        """Thermo PR/SRK modülü için ID'leri ve Mol Kesişmelerini hazırlar."""
        mol_fractions = []
        ids = []
        
        for comp, frac in composition_fraction.items():
            if frac > 1e-6:
                thermo_id = GasMixtureBuilder.THERMO_ID_MAP.get(comp)
                if thermo_id is None:
                    logger.warning(f"Thermo ID tablosunda bulunamadı: '{comp}', atlandı.")
                    continue
                ids.append(thermo_id)
                mol_fractions.append(frac)
                
        if not ids:
             raise FluidPropertyError("Geçerli Thermo gaz bileşeni bulunamadı")
             
        return {
            'ids': ids,
            'mol_fractions': mol_fractions
        }
