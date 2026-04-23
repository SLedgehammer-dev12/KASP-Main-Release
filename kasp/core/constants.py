"""
KASP V4.3 — Merkezi Sabitler Modülü
=====================================
Tüm uygulama sabitleri buradan yönetilir.
Değişiklik: V4.3'te MOLAR_MASSES, LHV_DATA, WATER_PRODUCED ve
SAFE_NAMES tek kaynak olarak buraya taşındı.
"""

# ─────────────────────────────────────────────────────────────────────────────
# Desteklenen Gaz Bileşenleri
# İç Anahtar (KASP canonical) → CoolProp Adı
# ─────────────────────────────────────────────────────────────────────────────
SUPPORTED_GASES = {
    # Alkanlar
    'METHANE':        'Methane',
    'ETHANE':         'Ethane',
    'PROPANE':        'Propane',
    'ISOBUTANE':      'IsoButane',
    'BUTANE':         'n-Butane',
    'ISOPENTANE':     'Isopentane',
    'PENTANE':        'n-Pentane',
    'HEXANE':         'n-Hexane',
    'HEPTANE':        'n-Heptane',
    'OCTANE':         'n-Octane',
    'NONANE':         'n-Nonane',
    'DECANE':         'n-Decane',
    # Diğer yanıcılar
    'HYDROGEN':       'Hydrogen',
    'HYDROGENSULFIDE':'HydrogenSulfide',
    # İnert / diğer
    'NITROGEN':       'Nitrogen',
    'CARBONDIOXIDE':  'CarbonDioxide',
    'WATER':          'Water',
    'OXYGEN':         'Oxygen',
    'ARGON':          'Argon',
    'HELIUM':         'Helium',
    'NEON':           'Neon',
    'KRYPTON':        'Krypton',
    'XENON':          'Xenon',
    'AIR':            'Air',
}

# Eski/alternatif anahtarlar → KASP canonical anahtarına eşleme
# UI veya dosya yüklemede farklı isimler geldiğinde normalize et
ALIAS_MAP = {
    'CO2':              'CARBONDIOXIDE',
    'CARBON DIOXIDE':   'CARBONDIOXIDE',
    'H2S':              'HYDROGENSULFIDE',
    'HYDROGEN SULFIDE': 'HYDROGENSULFIDE',
    'H2O':              'WATER',
    'IBUTANE':          'ISOBUTANE',   # eski V4.2 anahtarı
    'IPENTANE':         'ISOPENTANE',  # eski V4.2 anahtarı
    'N2':               'NITROGEN',
    'O2':               'OXYGEN',
    'H2':               'HYDROGEN',
    'AR':               'ARGON',
    'HE':               'HELIUM',
}

def normalize_component(name: str) -> str:
    """
    Bileşen adını KASP canonical formuna çevirir.
    Tanımlanamayan adları olduğu gibi büyük harf olarak döndürür.
    """
    upper = name.strip().upper()
    # Önce alias kontrolü
    canonical = ALIAS_MAP.get(upper, upper)
    return canonical


# ─────────────────────────────────────────────────────────────────────────────
# Molar Kütleler — g/mol
# ─────────────────────────────────────────────────────────────────────────────
MOLAR_MASSES = {
    'METHANE':       16.043,
    'ETHANE':        30.069,
    'PROPANE':       44.096,
    'ISOBUTANE':     58.123,
    'BUTANE':        58.123,
    'ISOPENTANE':    72.150,
    'PENTANE':       72.150,
    'HEXANE':        86.177,
    'HEPTANE':       100.204,
    'OCTANE':        114.231,
    'NONANE':        128.258,
    'DECANE':        142.285,
    'HYDROGEN':       2.016,
    'HYDROGENSULFIDE':34.082,
    'NITROGEN':       28.014,
    'CARBONDIOXIDE':  44.010,
    'WATER':          18.015,
    'OXYGEN':         31.999,
    'ARGON':          39.948,
    'HELIUM':          4.003,
    'NEON':           20.180,
    'KRYPTON':        83.798,
    'XENON':         131.293,
    'AIR':            28.966,
}

# ─────────────────────────────────────────────────────────────────────────────
# Alt Isıl Değer — kJ/kg (LHV, 25°C referans)
# ─────────────────────────────────────────────────────────────────────────────
LHV_DATA = {
    'METHANE':        50016,
    'ETHANE':         47486,
    'PROPANE':        46357,
    'ISOBUTANE':      45570,
    'BUTANE':         45718,
    'ISOPENTANE':     45220,
    'PENTANE':        45357,
    'HEXANE':         44750,
    'HEPTANE':        44670,
    'OCTANE':         44600,
    'NONANE':         44540,
    'DECANE':         44500,
    'HYDROGEN':      119960,
    'HYDROGENSULFIDE':16450,
    # İnertler yanmaz → 0
    'NITROGEN':           0,
    'CARBONDIOXIDE':      0,
    'WATER':              0,
    'ARGON':              0,
    'HELIUM':             0,
    'OXYGEN':             0,
    'NEON':               0,
    'KRYPTON':            0,
    'XENON':              0,
    'AIR':                0,
}

# ─────────────────────────────────────────────────────────────────────────────
# Yanma Sırasında Üretilen Su Molar Sayısı (mol H₂O / mol yakıt)
# ─────────────────────────────────────────────────────────────────────────────
WATER_PRODUCED = {
    'METHANE':       2,
    'ETHANE':        3,
    'PROPANE':       4,
    'ISOBUTANE':     5,
    'BUTANE':        5,
    'ISOPENTANE':    6,
    'PENTANE':       6,
    'HEXANE':        7,
    'HEPTANE':       8,
    'OCTANE':        9,
    'NONANE':        10,
    'DECANE':        11,
    'HYDROGEN':      1,
    'HYDROGENSULFIDE':1,
}

# ─────────────────────────────────────────────────────────────────────────────
# Birim Seçenekleri (UI için)
# ─────────────────────────────────────────────────────────────────────────────
UNIT_OPTIONS = {
    'pressure':    ['bar(a)', 'psia', 'kPa(a)', 'MPa(a)', 'kg/cm²(a)'],
    'temperature': ['°C', '°F', 'K', 'R'],
    'flow':        ['kg/s', 'kg/h', 'MMSCFD', 'MMSCMD', 'Sm³/h', 'Nm³/h', 'kmol/h'],
    'power':       ['kW', 'MW', 'hp', 'Btu/h'],
}

# ─────────────────────────────────────────────────────────────────────────────
# Varsayılan Gaz Kompozisyonu (%)
# ─────────────────────────────────────────────────────────────────────────────
DEFAULT_COMPOSITION = {
    'METHANE':   98.0,
    'ETHANE':     1.5,
    'NITROGEN':   0.5,
}

# ─────────────────────────────────────────────────────────────────────────────
# Fiziksel Sabitler
# ─────────────────────────────────────────────────────────────────────────────
R_UNIVERSAL_J_MOL_K   = 8.314462    # J/(mol·K)
STD_PRESS_PA          = 101325.0    # Pa  (1 atm)
NORMAL_TEMP_K         = 273.15      # K   (0 °C)
STANDARD_TEMP_K       = 288.15      # K   (15 °C)
GRAVITATIONAL_ACC     = 9.80665     # m/s²
