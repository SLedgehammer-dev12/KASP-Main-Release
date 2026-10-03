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
    'CH4':              'METHANE',
    'H2S':              'HYDROGENSULFIDE',
    'HYDROGEN SULFIDE': 'HYDROGENSULFIDE',
    'H2O':              'WATER',
    'IBUTANE':          'ISOBUTANE',   # eski V4.2 anahtarı
    'IC4H10':           'ISOBUTANE',
    'IPENTANE':         'ISOPENTANE',  # eski V4.2 anahtarı
    'N2':               'NITROGEN',
    'O2':               'OXYGEN',
    'H2':               'HYDROGEN',
    'AR':               'ARGON',
    'HE':               'HELIUM',
    'C2H6':             'ETHANE',
    'C3H8':             'PROPANE',
    'NC4H10':           'BUTANE',
    'C4H10':            'BUTANE',
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
    # H2S LHV = 517.93 kJ/mol / 34.082 g/mol ≈ 15196 kJ/kg (ISO 6976/GPA 2172).
    # Önceki 16450 değeri HHV'ye karşılık geliyordu; ekşi gazda yakıt debisini ~%8 yanlış hesaplıyordu.
    'HYDROGENSULFIDE':15196,
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
API_617_DRIVER_MARGIN_PCT = 4.0     # API 617 minimum driver margin (%)

# ─────────────────────────────────────────────────────────────────────────────
# Kritik Sıcaklıklar (K), Kritik Basınçlar (Pa) ve Asantrik Faktörler (ω)
# ─────────────────────────────────────────────────────────────────────────────
CRITICAL_TEMPS_K = {
    'METHANE':        190.56,
    'ETHANE':         305.32,
    'PROPANE':        369.83,
    'ISOBUTANE':      407.85,
    'BUTANE':         425.12,
    'ISOPENTANE':     460.35,
    'PENTANE':        469.70,
    'HEXANE':         507.60,
    'HEPTANE':        540.20,
    'OCTANE':         568.70,
    'NONANE':         594.60,
    'DECANE':         617.70,
    'HYDROGEN':        33.19,
    'HYDROGENSULFIDE':373.20,
    'NITROGEN':       126.19,
    'CARBONDIOXIDE':  304.13,
    'WATER':          647.10,
    'OXYGEN':         154.58,
    'ARGON':          150.86,
    'HELIUM':           5.19,
    'NEON':            44.40,
    'KRYPTON':        209.40,
    'XENON':          289.70,
    'AIR':            132.53,
}

CRITICAL_PRESS_PA = {
    'METHANE':        45.99e5,
    'ETHANE':         48.72e5,
    'PROPANE':        42.48e5,
    'ISOBUTANE':      36.40e5,
    'BUTANE':         37.96e5,
    'ISOPENTANE':     33.81e5,
    'PENTANE':        33.70e5,
    'HEXANE':         30.25e5,
    'HEPTANE':        27.40e5,
    'OCTANE':         24.90e5,
    'NONANE':         22.90e5,
    'DECANE':         21.10e5,
    'HYDROGEN':       13.13e5,
    'HYDROGENSULFIDE':89.40e5,
    'NITROGEN':       33.96e5,
    'CARBONDIOXIDE':  73.77e5,
    'WATER':         220.64e5,
    'OXYGEN':         50.43e5,
    'ARGON':          48.98e5,
    'HELIUM':          2.27e5,
    'NEON':           27.60e5,
    'KRYPTON':        55.00e5,
    'XENON':          58.40e5,
    'AIR':            37.86e5,
}

ACENTRIC_FACTORS = {
    'METHANE':        0.011,
    'ETHANE':         0.099,
    'PROPANE':        0.152,
    'ISOBUTANE':      0.186,
    'BUTANE':         0.200,
    'ISOPENTANE':     0.229,
    'PENTANE':        0.251,
    'HEXANE':         0.301,
    'HEPTANE':        0.349,
    'OCTANE':         0.398,
    'NONANE':         0.443,
    'DECANE':         0.492,
    'HYDROGEN':      -0.216,
    'HYDROGENSULFIDE':0.094,
    'NITROGEN':       0.037,
    'CARBONDIOXIDE':  0.224,
    'WATER':          0.344,
    'OXYGEN':         0.022,
    'ARGON':          0.001,
    'HELIUM':        -0.390,
    'NEON':          -0.029,
    'KRYPTON':        0.005,
    'XENON':          0.004,
    'AIR':            0.033,
}

