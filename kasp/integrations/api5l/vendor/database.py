"""
Database containing standards for API 5L PSL2, BOTAŞ Specifications, ASME B31.8 & ASME B36.10.
Generated automatically from verified Excel data source with accurate column mappings.
"""

# API 5L PSL2 Steel Grades SMYS & Mechanical Properties
API_5L_SMYS_TABLE = {
    "GRADE A": {
        "grade": "GRADE A",
        "iso_grade": "L210",
        "smys_psi": 30500.0,
        "yield_tensile_max": 0.93,
        "cvn_material_j": 27.0,
        "cvn_weld_j": 27.0,
        "yield_min_mpa": 210.0,
        "yield_max_psi": 47100.0,
        "yield_max_mpa": 325.0,
        "tensile_min_psi": 48600.0,
        "tensile_min_mpa": 335.0,
        "tensile_max_psi": 83400.0,
        "tensile_max_mpa": 575.0,
        "strain_value": 0.1
    },
    "GRADE B": {
        "grade": "GRADE B",
        "iso_grade": "L245",
        "smys_psi": 35500.0,
        "yield_tensile_max": 0.8,
        "cvn_material_j": 27.0,
        "cvn_weld_j": 27.0,
        "yield_min_mpa": 245.0,
        "yield_max_psi": 65300.0,
        "yield_max_mpa": 450.0,
        "tensile_min_psi": 60200.0,
        "tensile_min_mpa": 415.0,
        "tensile_max_psi": 95000.0,
        "tensile_max_mpa": 655.0,
        "strain_value": 0.1375
    },
    "X42": {
        "grade": "X42",
        "iso_grade": "L290",
        "smys_psi": 42100.0,
        "yield_tensile_max": 0.85,
        "cvn_material_j": 27.0,
        "cvn_weld_j": 27.0,
        "yield_min_mpa": 290.0,
        "yield_max_psi": 71800.0,
        "yield_max_mpa": 495.0,
        "tensile_min_psi": 60200.0,
        "tensile_min_mpa": 415.0,
        "tensile_max_psi": 95000.0,
        "tensile_max_mpa": 655.0,
        "strain_value": 0.1375
    },
    "X46": {
        "grade": "X46",
        "iso_grade": "L320",
        "smys_psi": 46400.0,
        "yield_tensile_max": 0.85,
        "cvn_material_j": 48.0,
        "cvn_weld_j": 36.0,
        "yield_min_mpa": 320.0,
        "yield_max_psi": 76100.0,
        "yield_max_mpa": 525.0,
        "tensile_min_psi": 63100.0,
        "tensile_min_mpa": 435.0,
        "tensile_max_psi": 95000.0,
        "tensile_max_mpa": 655.0,
        "strain_value": 0.1325
    },
    "X52": {
        "grade": "X52",
        "iso_grade": "L360",
        "smys_psi": 52200.0,
        "yield_tensile_max": 0.87,
        "cvn_material_j": 48.0,
        "cvn_weld_j": 36.0,
        "yield_min_mpa": 360.0,
        "yield_max_psi": 76900.0,
        "yield_max_mpa": 530.0,
        "tensile_min_psi": 66700.0,
        "tensile_min_mpa": 460.0,
        "tensile_max_psi": 110200.0,
        "tensile_max_mpa": 760.0,
        "strain_value": 0.125
    },
    "X56": {
        "grade": "X56",
        "iso_grade": "L390",
        "smys_psi": 56600.0,
        "yield_tensile_max": 0.87,
        "cvn_material_j": 48.0,
        "cvn_weld_j": 36.0,
        "yield_min_mpa": 390.0,
        "yield_max_psi": 79000.0,
        "yield_max_mpa": 545.0,
        "tensile_min_psi": 71100.0,
        "tensile_min_mpa": 490.0,
        "tensile_max_psi": 110200.0,
        "tensile_max_mpa": 760.0,
        "strain_value": 0.1175
    },
    "X60": {
        "grade": "X60",
        "iso_grade": "L415",
        "smys_psi": 60200.0,
        "yield_tensile_max": 0.9,
        "cvn_material_j": 60.0,
        "cvn_weld_j": 45.0,
        "yield_min_mpa": 415.0,
        "yield_max_psi": 81900.0,
        "yield_max_mpa": 565.0,
        "tensile_min_psi": 75400.0,
        "tensile_min_mpa": 520.0,
        "tensile_max_psi": 110200.0,
        "tensile_max_mpa": 760.0,
        "strain_value": 0.1125
    },
    "X65": {
        "grade": "X65",
        "iso_grade": "L450",
        "smys_psi": 65300.0,
        "yield_tensile_max": 0.9,
        "cvn_material_j": 60.0,
        "cvn_weld_j": 45.0,
        "yield_min_mpa": 450.0,
        "yield_max_psi": 87000.0,
        "yield_max_mpa": 600.0,
        "tensile_min_psi": 77600.0,
        "tensile_min_mpa": 535.0,
        "tensile_max_psi": 110200.0,
        "tensile_max_mpa": 760.0,
        "strain_value": 0.11
    },
    "X70": {
        "grade": "X70",
        "iso_grade": "L485",
        "smys_psi": 70300.0,
        "yield_tensile_max": 0.93,
        "cvn_material_j": 60.0,
        "cvn_weld_j": 45.0,
        "yield_min_mpa": 485.0,
        "yield_max_psi": 92100.0,
        "yield_max_mpa": 635.0,
        "tensile_min_psi": 82700.0,
        "tensile_min_mpa": 570.0,
        "tensile_max_psi": 110200.0,
        "tensile_max_mpa": 760.0,
        "strain_value": 0.1025
    },
    "X80": {
        "grade": "X80",
        "iso_grade": "L555",
        "smys_psi": 80500.0,
        "yield_tensile_max": 0.93,
        "cvn_material_j": 90.0,
        "cvn_weld_j": 68.0,
        "yield_min_mpa": 555.0,
        "yield_max_psi": 102300.0,
        "yield_max_mpa": 705.0,
        "tensile_min_psi": 90600.0,
        "tensile_min_mpa": 625.0,
        "tensile_max_psi": 119700.0,
        "tensile_max_mpa": 825.0,
        "strain_value": 0.095
    },
    "X90": {
        "grade": "X90",
        "iso_grade": "L625",
        "smys_psi": 90600.0,
        "yield_tensile_max": 0.95,
        "cvn_material_j": 0.0,
        "cvn_weld_j": 0.0,
        "yield_min_mpa": 625.0,
        "yield_max_psi": 112400.0,
        "yield_max_mpa": 775.0,
        "tensile_min_psi": 100800.0,
        "tensile_min_mpa": 695.0,
        "tensile_max_psi": 132700.0,
        "tensile_max_mpa": 915.0,
        "strain_value": 0.085
    },
    "X100": {
        "grade": "X100",
        "iso_grade": "L690",
        "smys_psi": 100100.0,
        "yield_tensile_max": 0.97,
        "cvn_material_j": 0.0,
        "cvn_weld_j": 0.0,
        "yield_min_mpa": 690.0,
        "yield_max_psi": 121800.0,
        "yield_max_mpa": 840.0,
        "tensile_min_psi": 110200.0,
        "tensile_min_mpa": 760.0,
        "tensile_max_psi": 143600.0,
        "tensile_max_mpa": 990.0,
        "strain_value": 0.08
    },
    "X120": {
        "grade": "X120",
        "iso_grade": "L830",
        "smys_psi": 120400.0,
        "yield_tensile_max": 0.99,
        "cvn_material_j": 0.0,
        "cvn_weld_j": 0.0,
        "yield_min_mpa": 830.0,
        "yield_max_psi": 152300.0,
        "yield_max_mpa": 1050.0,
        "tensile_min_psi": 132700.0,
        "tensile_min_mpa": 915.0,
        "tensile_max_psi": 166100.0,
        "tensile_max_mpa": 1145.0,
        "strain_value": 0.0675
    },
    "SS 304 / 304L": {
        "grade": "SS 304 / 304L",
        "iso_grade": "TP304L",
        "smys_psi": 30000.0,
        "yield_tensile_max": 0.85,
        "cvn_material_j": 60.0,
        "cvn_weld_j": 45.0,
        "yield_min_mpa": 205.0,
        "yield_max_psi": 58000.0,
        "yield_max_mpa": 400.0,
        "tensile_min_psi": 70000.0,
        "tensile_min_mpa": 485.0,
        "tensile_max_psi": 95000.0,
        "tensile_max_mpa": 655.0,
        "allowable_stress_mpa": 115.0,
        "allowable_stress_psi": 16700.0,
        "strain_value": 0.35,
        "is_stainless": True
    },
    "SS 316 / 316L": {
        "grade": "SS 316 / 316L",
        "iso_grade": "TP316L",
        "smys_psi": 30000.0,
        "yield_tensile_max": 0.85,
        "cvn_material_j": 60.0,
        "cvn_weld_j": 45.0,
        "yield_min_mpa": 205.0,
        "yield_max_psi": 58000.0,
        "yield_max_mpa": 400.0,
        "tensile_min_psi": 70000.0,
        "tensile_min_mpa": 485.0,
        "tensile_max_psi": 95000.0,
        "tensile_max_mpa": 655.0,
        "allowable_stress_mpa": 115.0,
        "allowable_stress_psi": 16700.0,
        "strain_value": 0.35,
        "is_stainless": True
    },
    "SS 321": {
        "grade": "SS 321",
        "iso_grade": "TP321",
        "smys_psi": 30000.0,
        "yield_tensile_max": 0.85,
        "cvn_material_j": 60.0,
        "cvn_weld_j": 45.0,
        "yield_min_mpa": 205.0,
        "yield_max_psi": 58000.0,
        "yield_max_mpa": 400.0,
        "tensile_min_psi": 75000.0,
        "tensile_min_mpa": 515.0,
        "tensile_max_psi": 100000.0,
        "tensile_max_mpa": 690.0,
        "allowable_stress_mpa": 115.0,
        "allowable_stress_psi": 16700.0,
        "strain_value": 0.35,
        "is_stainless": True
    },
    "Duplex 2205": {
        "grade": "Duplex 2205",
        "iso_grade": "UNS S32205",
        "smys_psi": 65300.0,
        "yield_tensile_max": 0.88,
        "cvn_material_j": 80.0,
        "cvn_weld_j": 60.0,
        "yield_min_mpa": 450.0,
        "yield_max_psi": 95000.0,
        "yield_max_mpa": 655.0,
        "tensile_min_psi": 95000.0,
        "tensile_min_mpa": 655.0,
        "tensile_max_psi": 130000.0,
        "tensile_max_mpa": 900.0,
        "allowable_stress_mpa": 175.0,
        "allowable_stress_psi": 25400.0,
        "strain_value": 0.25,
        "is_stainless": True
    },
    "Super Duplex 2507": {
        "grade": "Super Duplex 2507",
        "iso_grade": "UNS S32750",
        "smys_psi": 80000.0,
        "yield_tensile_max": 0.90,
        "cvn_material_j": 80.0,
        "cvn_weld_j": 60.0,
        "yield_min_mpa": 550.0,
        "yield_max_psi": 110000.0,
        "yield_max_mpa": 760.0,
        "tensile_min_psi": 110000.0,
        "tensile_min_mpa": 760.0,
        "tensile_max_psi": 145000.0,
        "tensile_max_mpa": 1000.0,
        "allowable_stress_mpa": 210.0,
        "allowable_stress_psi": 30500.0,
        "strain_value": 0.20,
        "is_stainless": True
    }
}

# Chemical Composition Limits (API 5L PSL2 & BOTAŞ & Stainless)
CHEMICAL_COMPOSITION_RULES = {
    'GRADE A': {'C_max': 0.22, 'Mn_max': 0.90, 'P_max': 0.030, 'S_max': 0.030, 'Nb_min': 0.0, 'Nb_max': None, 'V_max': None, 'Ti_max': None, 'N_max': None, 'CE_IIW_max': None, 'CE_Pcm_max': None},
    'GRADE B': {'C_max': 0.18, 'Mn_max': 1.20, 'P_max': 0.025, 'S_max': 0.010, 'Nb_min': 0.0, 'Nb_max': 0.05, 'V_max': 0.05, 'Ti_max': 0.04, 'N_max': 0.009, 'nb_v_ti_combined_max': 0.06, 'CE_IIW_max': 0.40, 'CE_Pcm_max': 0.22},
    'X42':     {'C_max': 0.18, 'Mn_max': 1.30, 'P_max': 0.025, 'S_max': 0.010, 'Nb_min': 0.0, 'Nb_max': 0.05, 'V_max': 0.05, 'Ti_max': 0.04, 'N_max': 0.009, 'nb_v_ti_combined_max': 0.15, 'CE_IIW_max': 0.40, 'CE_Pcm_max': 0.22},
    'X46':     {'C_max': 0.18, 'Mn_max': 1.30, 'P_max': 0.025, 'S_max': 0.010, 'Nb_min': 0.0, 'Nb_max': 0.05, 'V_max': 0.05, 'Ti_max': 0.04, 'N_max': 0.009, 'nb_v_ti_combined_max': 0.15, 'CE_IIW_max': 0.40, 'CE_Pcm_max': 0.22},
    'X52':     {'C_max': 0.18, 'Mn_max': 1.40, 'P_max': 0.025, 'S_max': 0.010, 'Nb_min': 0.015, 'Nb_max': 0.05, 'V_max': 0.05, 'Ti_max': 0.04, 'N_max': 0.009, 'nb_v_ti_combined_max': 0.15, 'CE_IIW_max': 0.40, 'CE_Pcm_max': 0.22},
    'X56':     {'C_max': 0.18, 'Mn_max': 1.40, 'P_max': 0.025, 'S_max': 0.010, 'Nb_min': 0.015, 'Nb_max': 0.05, 'V_max': 0.05, 'Ti_max': 0.04, 'N_max': 0.009, 'nb_v_ti_combined_max': 0.15, 'CE_IIW_max': 0.40, 'CE_Pcm_max': 0.22},
    'X60':     {'C_max': 0.12, 'Mn_max': 1.60, 'P_max': 0.025, 'S_max': 0.010, 'Nb_min': 0.015, 'Nb_max': 0.05, 'V_max': 0.05, 'Ti_max': 0.04, 'N_max': 0.009, 'nb_v_ti_combined_max': 0.15, 'CE_IIW_max': 0.40, 'CE_Pcm_max': 0.22},
    'X65':     {'C_max': 0.12, 'Mn_max': 1.60, 'P_max': 0.025, 'S_max': 0.010, 'Nb_min': 0.015, 'Nb_max': 0.05, 'V_max': 0.05, 'Ti_max': 0.04, 'N_max': 0.009, 'nb_v_ti_combined_max': 0.15, 'CE_IIW_max': 0.40, 'CE_Pcm_max': 0.22},
    'X70':     {'C_max': 0.12, 'Mn_max': 1.70, 'P_max': 0.025, 'S_max': 0.010, 'Nb_min': 0.015, 'Nb_max': 0.05, 'V_max': 0.05, 'Ti_max': 0.04, 'N_max': 0.009, 'nb_v_ti_combined_max': 0.15, 'CE_IIW_max': 0.40, 'CE_Pcm_max': 0.22},
    'X80':     {'C_max': 0.12, 'Mn_max': 1.85, 'P_max': 0.025, 'S_max': 0.010, 'Nb_min': 0.015, 'Nb_max': 0.05, 'V_max': 0.05, 'Ti_max': 0.04, 'N_max': 0.009, 'nb_v_ti_combined_max': 0.15, 'CE_IIW_max': 0.40, 'CE_Pcm_max': 0.22},
    'X90':     {'C_max': 0.10, 'Mn_max': 2.10, 'P_max': 0.020, 'S_max': 0.010, 'Nb_min': 0.0, 'Nb_max': None, 'V_max': None, 'Ti_max': 0.06, 'N_max': 0.015, 'nb_v_ti_combined_max': 0.15, 'CE_IIW_max': None, 'CE_Pcm_max': 0.25},
    'X100':    {'C_max': 0.10, 'Mn_max': 2.10, 'P_max': 0.020, 'S_max': 0.010, 'Nb_min': 0.0, 'Nb_max': None, 'V_max': None, 'Ti_max': 0.06, 'N_max': 0.015, 'nb_v_ti_combined_max': 0.15, 'CE_IIW_max': None, 'CE_Pcm_max': 0.25},
    'X120':    {'C_max': 0.10, 'Mn_max': 2.10, 'P_max': 0.020, 'S_max': 0.010, 'Nb_min': 0.0, 'Nb_max': None, 'V_max': None, 'Ti_max': 0.06, 'N_max': 0.015, 'nb_v_ti_combined_max': 0.15, 'CE_IIW_max': None, 'CE_Pcm_max': 0.25},
    'SS 304 / 304L': {'C_max': 0.030, 'Mn_max': 2.00, 'P_max': 0.045, 'S_max': 0.030, 'Nb_min': 0.0, 'Nb_max': 0.0, 'V_max': 0.0, 'Ti_max': 0.0, 'N_max': 0.10, 'CE_IIW_max': 0.0, 'CE_Pcm_max': 0.0},
    'SS 316 / 316L': {'C_max': 0.030, 'Mn_max': 2.00, 'P_max': 0.045, 'S_max': 0.030, 'Nb_min': 0.0, 'Nb_max': 0.0, 'V_max': 0.0, 'Ti_max': 0.0, 'N_max': 0.10, 'CE_IIW_max': 0.0, 'CE_Pcm_max': 0.0},
    'SS 321':        {'C_max': 0.080, 'Mn_max': 2.00, 'P_max': 0.045, 'S_max': 0.030, 'Nb_min': 0.0, 'Nb_max': 0.0, 'V_max': 0.0, 'Ti_max': 0.70, 'N_max': 0.10, 'CE_IIW_max': 0.0, 'CE_Pcm_max': 0.0},
    'Duplex 2205':   {'C_max': 0.030, 'Mn_max': 2.00, 'P_max': 0.030, 'S_max': 0.020, 'Nb_min': 0.0, 'Nb_max': 0.0, 'V_max': 0.0, 'Ti_max': 0.0, 'N_max': 0.20, 'CE_IIW_max': 0.0, 'CE_Pcm_max': 0.0},
    'Super Duplex 2507': {'C_max': 0.030, 'Mn_max': 1.20, 'P_max': 0.035, 'S_max': 0.020, 'Nb_min': 0.0, 'Nb_max': 0.0, 'V_max': 0.0, 'Ti_max': 0.0, 'N_max': 0.32, 'CE_IIW_max': 0.0, 'CE_Pcm_max': 0.0}
}

# =====================================================================
# API 5L PSL 1 — Table 6 (47th Ed.): Pipe Body Tensile (min yield / min tensile only).
# PSL 1 has no max yield, no max tensile and no yield-to-tensile ratio limit.
# Strain values per Table 23 (guided-bend test).
# =====================================================================
API_5L_PSL1_SMYS_TABLE = {
    "A25": {
        "grade": "A25", "iso_grade": "L175",
        "yield_min_mpa": 175.0, "yield_min_psi": 25400.0,
        "tensile_min_mpa": 310.0, "tensile_min_psi": 45000.0,
        "yield_max_mpa": 0.0, "yield_max_psi": 0.0,
        "tensile_max_mpa": 0.0, "tensile_max_psi": 0.0,
        "yield_tensile_max": 0.0, "cvn_material_j": 0.0, "cvn_weld_j": 0.0,
        "strain_value": 0.0,
    },
    "A25P": {
        "grade": "A25P", "iso_grade": "L175P",
        "yield_min_mpa": 175.0, "yield_min_psi": 25400.0,
        "tensile_min_mpa": 310.0, "tensile_min_psi": 45000.0,
        "yield_max_mpa": 0.0, "yield_max_psi": 0.0,
        "tensile_max_mpa": 0.0, "tensile_max_psi": 0.0,
        "yield_tensile_max": 0.0, "cvn_material_j": 0.0, "cvn_weld_j": 0.0,
        "strain_value": 0.0,
    },
    "GRADE A": {
        "grade": "GRADE A", "iso_grade": "L210",
        "yield_min_mpa": 210.0, "yield_min_psi": 30500.0,
        "tensile_min_mpa": 335.0, "tensile_min_psi": 48600.0,
        "yield_max_mpa": 0.0, "yield_max_psi": 0.0,
        "tensile_max_mpa": 0.0, "tensile_max_psi": 0.0,
        "yield_tensile_max": 0.0, "cvn_material_j": 0.0, "cvn_weld_j": 0.0,
        "strain_value": 0.1650,
    },
    "GRADE B": {
        "grade": "GRADE B", "iso_grade": "L245",
        "yield_min_mpa": 245.0, "yield_min_psi": 35500.0,
        "tensile_min_mpa": 415.0, "tensile_min_psi": 60200.0,
        "yield_max_mpa": 0.0, "yield_max_psi": 0.0,
        "tensile_max_mpa": 0.0, "tensile_max_psi": 0.0,
        "yield_tensile_max": 0.0, "cvn_material_j": 0.0, "cvn_weld_j": 0.0,
        "strain_value": 0.1375,
    },
    "X42": {
        "grade": "X42", "iso_grade": "L290",
        "yield_min_mpa": 290.0, "yield_min_psi": 42100.0,
        "tensile_min_mpa": 415.0, "tensile_min_psi": 60200.0,
        "yield_max_mpa": 0.0, "yield_max_psi": 0.0,
        "tensile_max_mpa": 0.0, "tensile_max_psi": 0.0,
        "yield_tensile_max": 0.0, "cvn_material_j": 0.0, "cvn_weld_j": 0.0,
        "strain_value": 0.1375,
    },
    "X46": {
        "grade": "X46", "iso_grade": "L320",
        "yield_min_mpa": 320.0, "yield_min_psi": 46400.0,
        "tensile_min_mpa": 435.0, "tensile_min_psi": 63100.0,
        "yield_max_mpa": 0.0, "yield_max_psi": 0.0,
        "tensile_max_mpa": 0.0, "tensile_max_psi": 0.0,
        "yield_tensile_max": 0.0, "cvn_material_j": 0.0, "cvn_weld_j": 0.0,
        "strain_value": 0.1325,
    },
    "X52": {
        "grade": "X52", "iso_grade": "L360",
        "yield_min_mpa": 360.0, "yield_min_psi": 52200.0,
        "tensile_min_mpa": 460.0, "tensile_min_psi": 66700.0,
        "yield_max_mpa": 0.0, "yield_max_psi": 0.0,
        "tensile_max_mpa": 0.0, "tensile_max_psi": 0.0,
        "yield_tensile_max": 0.0, "cvn_material_j": 0.0, "cvn_weld_j": 0.0,
        "strain_value": 0.1250,
    },
    "X56": {
        "grade": "X56", "iso_grade": "L390",
        "yield_min_mpa": 390.0, "yield_min_psi": 56600.0,
        "tensile_min_mpa": 490.0, "tensile_min_psi": 71100.0,
        "yield_max_mpa": 0.0, "yield_max_psi": 0.0,
        "tensile_max_mpa": 0.0, "tensile_max_psi": 0.0,
        "yield_tensile_max": 0.0, "cvn_material_j": 0.0, "cvn_weld_j": 0.0,
        "strain_value": 0.1175,
    },
    "X60": {
        "grade": "X60", "iso_grade": "L415",
        "yield_min_mpa": 415.0, "yield_min_psi": 60200.0,
        "tensile_min_mpa": 520.0, "tensile_min_psi": 75400.0,
        "yield_max_mpa": 0.0, "yield_max_psi": 0.0,
        "tensile_max_mpa": 0.0, "tensile_max_psi": 0.0,
        "yield_tensile_max": 0.0, "cvn_material_j": 0.0, "cvn_weld_j": 0.0,
        "strain_value": 0.1125,
    },
    "X65": {
        "grade": "X65", "iso_grade": "L450",
        "yield_min_mpa": 450.0, "yield_min_psi": 65300.0,
        "tensile_min_mpa": 535.0, "tensile_min_psi": 77600.0,
        "yield_max_mpa": 0.0, "yield_max_psi": 0.0,
        "tensile_max_mpa": 0.0, "tensile_max_psi": 0.0,
        "yield_tensile_max": 0.0, "cvn_material_j": 0.0, "cvn_weld_j": 0.0,
        "strain_value": 0.1100,
    },
    "X70": {
        "grade": "X70", "iso_grade": "L485",
        "yield_min_mpa": 485.0, "yield_min_psi": 70300.0,
        "tensile_min_mpa": 570.0, "tensile_min_psi": 82700.0,
        "yield_max_mpa": 0.0, "yield_max_psi": 0.0,
        "tensile_max_mpa": 0.0, "tensile_max_psi": 0.0,
        "yield_tensile_max": 0.0, "cvn_material_j": 0.0, "cvn_weld_j": 0.0,
        "strain_value": 0.1025,
    },
}

# =====================================================================
# API 5L PSL 1 — Table 4 (47th Ed.): Chemical Composition (t <= 25.0 mm).
# CE is NOT required for PSL 1. Seamless vs Welded rows differ in C (and Mn for X65/X70).
# V/Nb/Ti footnotes: c) Nb+V <= 0.06 (unless agreed); d) Nb+V+Ti <= 0.15; f) unless agreed Nb+V+Ti <= 0.15.
# =====================================================================
CHEMICAL_COMPOSITION_PSL1_RULES = {
    "A25": {
        "C_max_seamless": 0.21, "C_max_welded": 0.21,
        "Mn_max_seamless": 0.60, "Mn_max_welded": 0.60,
        "P_max": 0.030, "S_max": 0.030,
        "V_max": None, "Nb_max": None, "Ti_max": None, "nb_v_ti_combined_max": None,
        "CE_IIW_max": None, "CE_Pcm_max": None,
    },
    "A25P": {
        "C_max_seamless": 0.21, "C_max_welded": 0.21,
        "Mn_max_seamless": 0.60, "Mn_max_welded": 0.60,
        "P_min": 0.045, "P_max": 0.080, "S_max": 0.030,
        "V_max": None, "Nb_max": None, "Ti_max": None, "nb_v_ti_combined_max": None,
        "CE_IIW_max": None, "CE_Pcm_max": None,
    },
    "GRADE A": {
        "C_max_seamless": 0.22, "C_max_welded": 0.22,
        "Mn_max_seamless": 0.90, "Mn_max_welded": 0.90,
        "P_max": 0.030, "S_max": 0.030,
        "V_max": None, "Nb_max": None, "Ti_max": None, "nb_v_ti_combined_max": None,
        "CE_IIW_max": None, "CE_Pcm_max": None,
    },
    "GRADE B": {
        "C_max_seamless": 0.28, "C_max_welded": 0.26,
        "Mn_max_seamless": 1.20, "Mn_max_welded": 1.20,
        "P_max": 0.030, "S_max": 0.030,
        "V_max": 0.05, "Nb_max": 0.05, "Ti_max": 0.05, "nb_v_ti_combined_max": 0.15,
        "CE_IIW_max": None, "CE_Pcm_max": None,
    },
    "X42": {
        "C_max_seamless": 0.28, "C_max_welded": 0.26,
        "Mn_max_seamless": 1.30, "Mn_max_welded": 1.30,
        "P_max": 0.030, "S_max": 0.030,
        "V_max": 0.05, "Nb_max": 0.05, "Ti_max": 0.05, "nb_v_ti_combined_max": 0.15,
        "CE_IIW_max": None, "CE_Pcm_max": None,
    },
    "X46": {
        "C_max_seamless": 0.28, "C_max_welded": 0.26,
        "Mn_max_seamless": 1.40, "Mn_max_welded": 1.40,
        "P_max": 0.030, "S_max": 0.030,
        "V_max": 0.05, "Nb_max": 0.05, "Ti_max": 0.05, "nb_v_ti_combined_max": 0.15,
        "CE_IIW_max": None, "CE_Pcm_max": None,
    },
    "X52": {
        "C_max_seamless": 0.28, "C_max_welded": 0.26,
        "Mn_max_seamless": 1.40, "Mn_max_welded": 1.40,
        "P_max": 0.030, "S_max": 0.030,
        "V_max": 0.05, "Nb_max": 0.05, "Ti_max": 0.05, "nb_v_ti_combined_max": 0.15,
        "CE_IIW_max": None, "CE_Pcm_max": None,
    },
    "X56": {
        "C_max_seamless": 0.28, "C_max_welded": 0.26,
        "Mn_max_seamless": 1.40, "Mn_max_welded": 1.40,
        "P_max": 0.030, "S_max": 0.030,
        "V_max": 0.05, "Nb_max": 0.05, "Ti_max": 0.05, "nb_v_ti_combined_max": 0.15,
        "CE_IIW_max": None, "CE_Pcm_max": None,
    },
    "X60": {
        "C_max_seamless": 0.28, "C_max_welded": 0.26,
        "Mn_max_seamless": 1.40, "Mn_max_welded": 1.40,
        "P_max": 0.030, "S_max": 0.030,
        "V_max": 0.05, "Nb_max": 0.05, "Ti_max": 0.05, "nb_v_ti_combined_max": 0.15,
        "CE_IIW_max": None, "CE_Pcm_max": None,
    },
    "X65": {
        "C_max_seamless": 0.28, "C_max_welded": 0.26,
        "Mn_max_seamless": 1.40, "Mn_max_welded": 1.45,
        "P_max": 0.030, "S_max": 0.030,
        "V_max": 0.05, "Nb_max": 0.05, "Ti_max": 0.05, "nb_v_ti_combined_max": 0.15,
        "CE_IIW_max": None, "CE_Pcm_max": None,
    },
    "X70": {
        "C_max_seamless": 0.28, "C_max_welded": 0.26,
        "Mn_max_seamless": 1.40, "Mn_max_welded": 1.65,
        "P_max": 0.030, "S_max": 0.030,
        "V_max": 0.05, "Nb_max": 0.05, "Ti_max": 0.05, "nb_v_ti_combined_max": 0.15,
        "CE_IIW_max": None, "CE_Pcm_max": None,
    },
}

# =====================================================================
# API 5L PSL 2 — Table 5 (47th Ed.): Chemical Composition (t <= 25.0 mm), keyed by DELIVERY CONDITION.
# Footnote handling: c) Nb+V<=0.06; d) Nb+V+Ti<=0.15; g) unless agreed Nb+V+Ti<=0.15;
#   m) C+Nb<=0.20 (M grades); n) Al_total<=0.070, N<=0.015 (M grades); CE "as agreed" where noted.
# =====================================================================
CHEMICAL_COMPOSITION_PSL2 = {
    "R": {
        "GRADE B": {"C_max": 0.24, "Si_max": 0.40, "Mn_max": 1.20, "P_max": 0.025, "S_max": 0.015,
                    "V_max": None, "Nb_max": None, "Ti_max": 0.04, "nb_v_combined_max": 0.06,
                    "CE_IIW_max": 0.43, "CE_Pcm_max": 0.25},
        "X42": {"C_max": 0.24, "Si_max": 0.40, "Mn_max": 1.20, "P_max": 0.025, "S_max": 0.015,
                "V_max": 0.06, "Nb_max": 0.05, "Ti_max": 0.04,
                "CE_IIW_max": 0.43, "CE_Pcm_max": 0.25},
    },
    "N": {
        "GRADE B": {"C_max": 0.24, "Si_max": 0.40, "Mn_max": 1.20, "P_max": 0.025, "S_max": 0.015,
                    "V_max": None, "Nb_max": None, "Ti_max": 0.04, "nb_v_combined_max": 0.06,
                    "CE_IIW_max": 0.43, "CE_Pcm_max": 0.25},
        "X42": {"C_max": 0.24, "Si_max": 0.40, "Mn_max": 1.20, "P_max": 0.025, "S_max": 0.015,
                "V_max": 0.06, "Nb_max": 0.05, "Ti_max": 0.04,
                "CE_IIW_max": 0.43, "CE_Pcm_max": 0.25},
        "X46": {"C_max": 0.24, "Si_max": 0.40, "Mn_max": 1.40, "P_max": 0.025, "S_max": 0.015,
                "V_max": 0.07, "Nb_max": 0.05, "Ti_max": 0.04, "nb_v_ti_combined_max": 0.15,
                "CE_IIW_max": 0.43, "CE_Pcm_max": 0.25},
        "X52": {"C_max": 0.24, "Si_max": 0.45, "Mn_max": 1.40, "P_max": 0.025, "S_max": 0.015,
                "V_max": 0.10, "Nb_max": 0.05, "Ti_max": 0.04, "nb_v_ti_combined_max": 0.15,
                "CE_IIW_max": 0.43, "CE_Pcm_max": 0.25},
        "X56": {"C_max": 0.24, "Si_max": 0.45, "Mn_max": 1.40, "P_max": 0.025, "S_max": 0.015,
                "V_max": 0.10, "Nb_max": 0.05, "Ti_max": 0.04, "nb_v_ti_combined_max": 0.15,
                "CE_IIW_max": 0.43, "CE_Pcm_max": 0.25},
        "X60": {"C_max": 0.24, "Si_max": 0.45, "Mn_max": 1.40, "P_max": 0.025, "S_max": 0.015,
                "V_max": 0.10, "Nb_max": 0.05, "Ti_max": 0.04, "nb_v_ti_combined_max": 0.15,
                "CE_IIW_max": None, "CE_Pcm_max": None},  # CE "as agreed"
    },
    "Q": {
        "GRADE B": {"C_max": 0.18, "Si_max": 0.45, "Mn_max": 1.40, "P_max": 0.025, "S_max": 0.015,
                    "V_max": 0.05, "Nb_max": 0.05, "Ti_max": 0.04,
                    "CE_IIW_max": 0.43, "CE_Pcm_max": 0.25},
        "X42": {"C_max": 0.18, "Si_max": 0.45, "Mn_max": 1.40, "P_max": 0.025, "S_max": 0.015,
                "V_max": 0.05, "Nb_max": 0.05, "Ti_max": 0.04,
                "CE_IIW_max": 0.43, "CE_Pcm_max": 0.25},
        "X46": {"C_max": 0.18, "Si_max": 0.45, "Mn_max": 1.40, "P_max": 0.025, "S_max": 0.015,
                "V_max": 0.05, "Nb_max": 0.05, "Ti_max": 0.04,
                "CE_IIW_max": 0.43, "CE_Pcm_max": 0.25},
        "X52": {"C_max": 0.18, "Si_max": 0.45, "Mn_max": 1.50, "P_max": 0.025, "S_max": 0.015,
                "V_max": 0.05, "Nb_max": 0.05, "Ti_max": 0.04,
                "CE_IIW_max": 0.43, "CE_Pcm_max": 0.25},
        "X56": {"C_max": 0.18, "Si_max": 0.45, "Mn_max": 1.50, "P_max": 0.025, "S_max": 0.015,
                "V_max": 0.07, "Nb_max": 0.05, "Ti_max": 0.04, "nb_v_ti_combined_max": 0.15,
                "CE_IIW_max": 0.43, "CE_Pcm_max": 0.25},
        "X60": {"C_max": 0.18, "Si_max": 0.45, "Mn_max": 1.70, "P_max": 0.025, "S_max": 0.015,
                "V_max": None, "Nb_max": None, "Ti_max": None, "nb_v_ti_combined_max": 0.15,
                "CE_IIW_max": 0.43, "CE_Pcm_max": 0.25},
        "X65": {"C_max": 0.18, "Si_max": 0.45, "Mn_max": 1.70, "P_max": 0.025, "S_max": 0.015,
                "V_max": None, "Nb_max": None, "Ti_max": None, "nb_v_ti_combined_max": 0.15,
                "CE_IIW_max": 0.43, "CE_Pcm_max": 0.25},
        "X70": {"C_max": 0.18, "Si_max": 0.45, "Mn_max": 1.80, "P_max": 0.025, "S_max": 0.015,
                "V_max": None, "Nb_max": None, "Ti_max": None, "nb_v_ti_combined_max": 0.15,
                "CE_IIW_max": 0.43, "CE_Pcm_max": 0.25},
        "X80": {"C_max": 0.18, "Si_max": 0.45, "Mn_max": 1.90, "P_max": 0.025, "S_max": 0.015,
                "V_max": None, "Nb_max": None, "Ti_max": None, "nb_v_ti_combined_max": 0.15,
                "CE_IIW_max": None, "CE_Pcm_max": None},  # CE "as agreed"
        "X90": {"C_max": 0.16, "Si_max": 0.45, "Mn_max": 1.90, "P_max": 0.020, "S_max": 0.010,
                "V_max": None, "Nb_max": None, "Ti_max": None, "nb_v_ti_combined_max": 0.15,
                "CE_IIW_max": None, "CE_Pcm_max": None},  # CE "as agreed"
        "X100": {"C_max": 0.16, "Si_max": 0.45, "Mn_max": 1.90, "P_max": 0.020, "S_max": 0.010,
                 "V_max": None, "Nb_max": None, "Ti_max": None, "nb_v_ti_combined_max": 0.15,
                 "CE_IIW_max": None, "CE_Pcm_max": None},  # CE "as agreed"
    },
    "M": {
        "GRADE B": {"C_max": 0.22, "Si_max": 0.45, "Mn_max": 1.20, "P_max": 0.025, "S_max": 0.015,
                    "V_max": 0.05, "Nb_max": 0.05, "Ti_max": 0.04,
                    "CE_IIW_max": 0.43, "CE_Pcm_max": 0.25},
        "X42": {"C_max": 0.22, "Si_max": 0.45, "Mn_max": 1.30, "P_max": 0.025, "S_max": 0.015,
                "V_max": 0.05, "Nb_max": 0.05, "Ti_max": 0.04,
                "CE_IIW_max": 0.43, "CE_Pcm_max": 0.25},
        "X46": {"C_max": 0.22, "Si_max": 0.45, "Mn_max": 1.30, "P_max": 0.025, "S_max": 0.015,
                "V_max": 0.05, "Nb_max": 0.05, "Ti_max": 0.04,
                "CE_IIW_max": 0.43, "CE_Pcm_max": 0.25},
        "X52": {"C_max": 0.22, "Si_max": 0.45, "Mn_max": 1.40, "P_max": 0.025, "S_max": 0.015,
                "V_max": None, "Nb_max": None, "Ti_max": None, "nb_v_ti_combined_max": 0.15,
                "CE_IIW_max": 0.43, "CE_Pcm_max": 0.25},
        "X56": {"C_max": 0.22, "Si_max": 0.45, "Mn_max": 1.40, "P_max": 0.025, "S_max": 0.015,
                "V_max": None, "Nb_max": None, "Ti_max": None, "nb_v_ti_combined_max": 0.15,
                "CE_IIW_max": 0.43, "CE_Pcm_max": 0.25},
        "X60": {"C_max": 0.12, "Si_max": 0.45, "Mn_max": 1.60, "P_max": 0.025, "S_max": 0.015,
                "V_max": None, "Nb_max": None, "Ti_max": 0.06, "nb_v_ti_combined_max": 0.15,
                "c_nb_max": 0.20, "Al_max": 0.070, "N_max": 0.015,
                "CE_IIW_max": 0.43, "CE_Pcm_max": 0.25},
        "X65": {"C_max": 0.12, "Si_max": 0.45, "Mn_max": 1.60, "P_max": 0.025, "S_max": 0.015,
                "V_max": None, "Nb_max": None, "Ti_max": 0.06, "nb_v_ti_combined_max": 0.15,
                "c_nb_max": 0.20, "Al_max": 0.070, "N_max": 0.015,
                "CE_IIW_max": 0.43, "CE_Pcm_max": 0.25},
        "X70": {"C_max": 0.12, "Si_max": 0.45, "Mn_max": 1.70, "P_max": 0.025, "S_max": 0.015,
                "V_max": None, "Nb_max": None, "Ti_max": 0.06, "nb_v_ti_combined_max": 0.15,
                "c_nb_max": 0.20, "Al_max": 0.070, "N_max": 0.015,
                "CE_IIW_max": 0.43, "CE_Pcm_max": 0.25},
        "X80": {"C_max": 0.12, "Si_max": 0.45, "Mn_max": 1.85, "P_max": 0.025, "S_max": 0.015,
                "V_max": None, "Nb_max": None, "Ti_max": 0.06, "nb_v_ti_combined_max": 0.15,
                "c_nb_max": 0.20, "Al_max": 0.070, "N_max": 0.015,
                "CE_IIW_max": 0.43, "CE_Pcm_max": 0.25},
        "X90": {"C_max": 0.10, "Si_max": 0.55, "Mn_max": 2.10, "P_max": 0.020, "S_max": 0.010,
                "V_max": None, "Nb_max": None, "Ti_max": 0.06, "nb_v_ti_combined_max": 0.15,
                "c_nb_max": 0.20, "Al_max": 0.070, "N_max": 0.015,
                "CE_IIW_max": None, "CE_Pcm_max": 0.25},  # CE_IIW "—" (not applicable)
        "X100": {"C_max": 0.10, "Si_max": 0.55, "Mn_max": 2.10, "P_max": 0.020, "S_max": 0.010,
                 "V_max": None, "Nb_max": None, "Ti_max": 0.06, "nb_v_ti_combined_max": 0.15,
                 "c_nb_max": 0.20, "Al_max": 0.070, "N_max": 0.015,
                 "CE_IIW_max": None, "CE_Pcm_max": 0.25},  # CE_IIW "—"
        "X120": {"C_max": 0.10, "Si_max": 0.55, "Mn_max": 2.10, "P_max": 0.020, "S_max": 0.010,
                 "V_max": None, "Nb_max": None, "Ti_max": 0.06, "nb_v_ti_combined_max": 0.15,
                 "c_nb_max": 0.20, "Al_max": 0.070, "N_max": 0.015,
                 "CE_IIW_max": None, "CE_Pcm_max": 0.25},  # CE_IIW "—"
    },
}

# Grade availability per PSL / delivery condition (API 5L 47th Ed. Table 1).
PSL1_GRADES = ["A25", "A25P", "GRADE A", "GRADE B", "X42", "X46", "X52", "X56", "X60", "X65", "X70"]

PSL2_DELIVERY_GRADES = {
    "R": ["GRADE B", "X42"],
    "N": ["GRADE B", "X42", "X46", "X52", "X56", "X60"],
    "Q": ["GRADE B", "X42", "X46", "X52", "X56", "X60", "X65", "X70", "X80", "X90", "X100"],
    "M": ["GRADE B", "X42", "X46", "X52", "X56", "X60", "X65", "X70", "X80", "X90", "X100", "X120"],
}

# API 5L 47th Ed. Table 2 (Process of manufacture): PSL 1 permits seamless and all
# welded processes modelled by this app (SMLS, ERW/HFW, SAWH, SAWL, COW). PSL 2
# excludes only CW/LW, so SAW and COW remain permitted for PSL 2 as well.
# (CW / LW are not modelled by the UI.)
PSL1_PROCESSES = ["SMLS", "ERW HFW", "SAWH", "SAWL", "COW"]
# PSL 2 delivery M is welded-only (API 5L 47th Ed. Table 3: SMLS has no M route).
PSL2_M_PROCESSES = ["ERW HFW", "SAWH", "SAWL", "COW"]
# PSL 2 deliveries N / Q / R: seamless and welded both permitted.
PSL2_OTHER_PROCESSES = ["SMLS", "ERW HFW", "SAWH", "SAWL", "COW"]

# =====================================================================
# API 5L 46th Ed. Table 8 (PSL2) minimum absorbed energy (J), full-size specimen, average of 3, 0 °C.
# DRAFT — values to be verified against the exact Table 8 of the 46th edition.
# ---------------------------------------------------------------------
# CVN (PSL 2) — API 5L 47th Ed. Table 8: pipe body energy depends on BOTH
# outside diameter and grade. Table 8 is identical in the 46th and 47th editions.
# Weld & HAZ/HTZ energy per 9.8.3.1 (47th Ed.): HFW = 20 J; non-HFW D<1422 mm
# and grade <= X80 = 27 J; non-HFW D >= 1422 mm OR grade > X80 = 40 J.
# ---------------------------------------------------------------------
_CVN_BODY_TABLE_47 = [
    (508.0, [27, 27, 27, 40, 40, 40, 40]),
    (762.0, [27, 27, 27, 40, 40, 40, 40]),
    (914.0, [40, 40, 40, 40, 40, 54, 54]),
    (1219.0, [40, 40, 40, 40, 40, 54, 68]),
    (1422.0, [40, 54, 54, 54, 54, 68, 81]),
    (float("inf"), [40, 54, 68, 68, 81, 95, 108]),
]


# Table 22 (47th Ed.): (D_max_mm, t_min_full, t_min_3over4, t_min_2over3) for CVN test piece size.
_CVN_SPECIMEN_TABLE_22 = [
    (114.3, 12.6, 11.3, 10.9),
    (141.3, 11.9, 9.8, 9.4),
    (168.3, 11.7, 9.2, 8.5),
    (219.1, 11.4, 8.9, 8.1),
    (273.1, 11.2, 8.7, 7.9),
    (323.9, 11.1, 8.6, 7.8),
    (355.6, 11.1, 8.6, 7.7),
    (406.4, 11.0, 8.5, 7.7),
    (float("inf"), 11.0, 8.5, 7.7),
]
_CVN_SIZE_FACTOR = {"Full": 1.0, "3/4": 0.75, "2/3": 2.0 / 3.0, "1/2": 0.5}
_CVN_SIZE_LABEL = {
    "Full": "Tam boy 10 x 10 x 55 mm",
    "3/4": "3/4 boy 7.5 x 10 x 55 mm",
    "2/3": "2/3 boy 6.67 x 10 x 55 mm",
    "1/2": "1/2 boy 5 x 10 x 55 mm",
}


def get_cvn_specimen_size(d_mm: float, t_mm: float) -> dict:
    """Required CVN test piece size per Table 22 (47th Ed.): depends on BOTH D and t."""
    d = float(d_mm or 1219.0)
    t = float(t_mm or 14.3)
    for d_max, t_full, t_34, t_23 in _CVN_SPECIMEN_TABLE_22:
        if d <= d_max:
            if t >= t_full:
                size = "Full"
            elif t >= t_34:
                size = "3/4"
            elif t >= t_23:
                size = "2/3"
            else:
                size = "1/2"
            break
    else:
        size = "Full"
    return {
        "size": size,
        "label": _CVN_SIZE_LABEL[size],
        "width_ratio": _CVN_SIZE_FACTOR[size],
    }


def cvn_grade_col(grade: str) -> int:
    """Column index in Table 8 (0=X60, 1=X65, 2=X70, 3=X80, 4=X90, 5=X100, 6=X120)."""
    g = grade.upper().strip()
    if g in ("X90",):
        return 4
    if g == "X100":
        return 5
    if g == "X120":
        return 6
    if g == "X80":
        return 3
    if g == "X70":
        return 2
    if g == "X65":
        return 1
    return 0  # GRADE A / B / X42 / X46 / X52 / X56 / X60


def get_cvn_body_api5l(grade: str, d_mm: float) -> float:
    """Pipe body CVN minimum (J) per Table 8 (47th Ed.), full-size specimen at 0 °C."""
    col = cvn_grade_col(grade)
    for d_max, values in _CVN_BODY_TABLE_47:
        if d_mm <= d_max:
            return float(values[col])
    return 40.0


def get_cvn_weld_api5l(manufacturing_process: str, d_mm: float, grade: str) -> float:
    """Weld / HAZ / HTZ CVN minimum (J) per 9.8.3.1 (47th Ed.)."""
    proc = (manufacturing_process or "").upper()
    if "HFW" in proc or "ERW" in proc:
        return 20.0
    if d_mm >= 1422.0:
        return 40.0
    if cvn_grade_col(grade) >= 4:  # > L555 or X80
        return 40.0
    return 27.0


CVN_API5L = {
    "GRADE A": {"material_j": 27.0, "weld_j": 20.0},
    "GRADE B": {"material_j": 27.0, "weld_j": 20.0},
    "X42": {"material_j": 27.0, "weld_j": 20.0},
    "X46": {"material_j": 27.0, "weld_j": 20.0},
    "X52": {"material_j": 27.0, "weld_j": 20.0},
    "X56": {"material_j": 40.0, "weld_j": 27.0},
    "X60": {"material_j": 40.0, "weld_j": 27.0},
    "X65": {"material_j": 40.0, "weld_j": 27.0},
    "X70": {"material_j": 40.0, "weld_j": 27.0},
    "X80": {"material_j": 68.0, "weld_j": 54.0},
}


def get_api5l_yt_ratio(grade: str, delivery_condition: str = "M") -> float:
    """
    PSL 2 yield-to-tensile ratio (Table 7, 47th Ed.). Applies only for D > 323.9 mm
    (footnote c). Grade <= X80 -> 0.93; X90 -> 0.95 (M) / 0.97 (Q); X100 -> 0.97; X120 -> 0.99.
    """
    g = grade.upper().strip()
    if g in ("X90",):
        return 0.97 if (delivery_condition or "").upper() == "Q" else 0.95
    if g in ("X100", "X120"):
        return 0.97 if g == "X100" else 0.99
    return 0.93

# Design factor canonical key -> numeric F value.
DESIGN_FACTOR_MAP = {
    "0.80_hat": 0.80,
    "0.72_hat": 0.72,
    "0.60_hat": 0.60,
    "0.50_hat": 0.50,
    "0.50_ist1": 0.50,
    "0.50_ist2": 0.50,
    "0.50_ist_75bar": 0.50,
    "0.50_ist_82_5bar": 0.50,
    "0.40_hat": 0.40,
}

# Standard Pipe Sizes, Wall Thicknesses & Tolerances (BOTAŞ & ASME B31.8)
PIPE_SIZES_TABLE = [
    {
        "inch": "½\"",
        "mm": 21.3,
        "default_material": "GRADE B",
        "botas_thk": {
            "0.72_hat": 0.0,
            "0.60_hat": 0.0,
            "0.50_hat": 0.0,
            "0.50_ist1": 3.7,
            "0.50_ist2": 3.7
        },
        "asme_thk": {
            "0.72_hat": 0.0,
            "0.60_hat": 0.0,
            "0.50_hat": 0.0,
            "0.50_ist1": 3.73,
            "0.50_ist2": 3.73
        },
        "diameter_tol_botas": {
            "end_max": 21.7,
            "end_min": 20.5,
            "body_max": 21.7,
            "body_min": 20.5
        },
        "diameter_tol_asme": {
            "end_max": 21.7,
            "end_min": 20.5,
            "body_max": 21.7,
            "body_min": 20.5
        },
        "ovality": {
            "end": "0.45",
            "body": "1.2"
        }
    },
    {
        "inch": "¾\"",
        "mm": 26.7,
        "default_material": "GRADE B",
        "botas_thk": {
            "0.72_hat": 0.0,
            "0.60_hat": 0.0,
            "0.50_hat": 0.0,
            "0.50_ist1": 3.9,
            "0.50_ist2": 3.9
        },
        "asme_thk": {
            "0.72_hat": 0.0,
            "0.60_hat": 0.0,
            "0.50_hat": 0.0,
            "0.50_ist1": 3.91,
            "0.50_ist2": 3.91
        },
        "diameter_tol_botas": {
            "end_max": 27.099999999999998,
            "end_min": 25.9,
            "body_max": 27.099999999999998,
            "body_min": 25.9
        },
        "diameter_tol_asme": {
            "end_max": 27.099999999999998,
            "end_min": 25.9,
            "body_max": 27.099999999999998,
            "body_min": 25.9
        },
        "ovality": {
            "end": "0.45",
            "body": "1.2"
        }
    },
    {
        "inch": "1\"",
        "mm": 33.4,
        "default_material": "GRADE B",
        "botas_thk": {
            "0.72_hat": 0.0,
            "0.60_hat": 0.0,
            "0.50_hat": 0.0,
            "0.50_ist1": 4.6,
            "0.50_ist2": 4.6
        },
        "asme_thk": {
            "0.72_hat": 0.0,
            "0.60_hat": 0.0,
            "0.50_hat": 0.0,
            "0.50_ist1": 4.55,
            "0.50_ist2": 4.55
        },
        "diameter_tol_botas": {
            "end_max": 33.8,
            "end_min": 32.6,
            "body_max": 33.8,
            "body_min": 32.6
        },
        "diameter_tol_asme": {
            "end_max": 33.8,
            "end_min": 32.6,
            "body_max": 33.8,
            "body_min": 32.6
        },
        "ovality": {
            "end": "0.45",
            "body": "1.2"
        }
    },
    {
        "inch": "1¼\"",
        "mm": 42.2,
        "default_material": "GRADE B",
        "botas_thk": {
            "0.72_hat": 0.0,
            "0.60_hat": 0.0,
            "0.50_hat": 0.0,
            "0.50_ist1": 4.9,
            "0.50_ist2": 4.9
        },
        "asme_thk": {
            "0.72_hat": 0.0,
            "0.60_hat": 0.0,
            "0.50_hat": 0.0,
            "0.50_ist1": 4.85,
            "0.50_ist2": 4.85
        },
        "diameter_tol_botas": {
            "end_max": 42.6,
            "end_min": 41.400000000000006,
            "body_max": 42.6,
            "body_min": 41.400000000000006
        },
        "diameter_tol_asme": {
            "end_max": 42.6,
            "end_min": 41.400000000000006,
            "body_max": 42.6,
            "body_min": 41.400000000000006
        },
        "ovality": {
            "end": "0.45",
            "body": "1.2"
        }
    },
    {
        "inch": "1½\"",
        "mm": 48.3,
        "default_material": "GRADE B",
        "botas_thk": {
            "0.72_hat": 0.0,
            "0.60_hat": 0.0,
            "0.50_hat": 0.0,
            "0.50_ist1": 5.1,
            "0.50_ist2": 5.1
        },
        "asme_thk": {
            "0.72_hat": 0.0,
            "0.60_hat": 0.0,
            "0.50_hat": 0.0,
            "0.50_ist1": 5.08,
            "0.50_ist2": 5.08
        },
        "diameter_tol_botas": {
            "end_max": 48.699999999999996,
            "end_min": 47.5,
            "body_max": 48.699999999999996,
            "body_min": 47.5
        },
        "diameter_tol_asme": {
            "end_max": 48.699999999999996,
            "end_min": 47.5,
            "body_max": 48.699999999999996,
            "body_min": 47.5
        },
        "ovality": {
            "end": "0.45",
            "body": "1.2"
        }
    },
    {
        "inch": "2\"",
        "mm": 60.3,
        "default_material": "GRADE B",
        "botas_thk": {
            "0.72_hat": 0.0,
            "0.60_hat": 0.0,
            "0.50_hat": 0.0,
            "0.50_ist1": 5.5,
            "0.50_ist2": 5.5
        },
        "asme_thk": {
            "0.72_hat": 0.0,
            "0.60_hat": 0.0,
            "0.50_hat": 0.0,
            "0.50_ist1": 5.54,
            "0.50_ist2": 5.54
        },
        "diameter_tol_botas": {
            "end_max": 61.9,
            "end_min": 59.9,
            "body_max": 60.752250000000004,
            "body_min": 59.84775
        },
        "diameter_tol_asme": {
            "end_max": 61.9,
            "end_min": 59.9,
            "body_max": 60.752250000000004,
            "body_min": 59.84775
        },
        "ovality": {
            "end": "0.45225",
            "body": "1.206"
        }
    },
    {
        "inch": "2½\"",
        "mm": 73.0,
        "default_material": "GRADE B",
        "botas_thk": {
            "0.72_hat": 0.0,
            "0.60_hat": 0.0,
            "0.50_hat": 0.0,
            "0.50_ist1": 5.2,
            "0.50_ist2": 5.2
        },
        "asme_thk": {
            "0.72_hat": 0.0,
            "0.60_hat": 0.0,
            "0.50_hat": 0.0,
            "0.50_ist1": 5.16,
            "0.50_ist2": 5.16
        },
        "diameter_tol_botas": {
            "end_max": 74.6,
            "end_min": 72.6,
            "body_max": 73.5475,
            "body_min": 72.4525
        },
        "diameter_tol_asme": {
            "end_max": 74.6,
            "end_min": 72.6,
            "body_max": 73.5475,
            "body_min": 72.4525
        },
        "ovality": {
            "end": "0.5475",
            "body": "1.46"
        }
    },
    {
        "inch": "3\"",
        "mm": 88.9,
        "default_material": "GRADE B",
        "botas_thk": {
            "0.72_hat": 0.0,
            "0.60_hat": 0.0,
            "0.50_hat": 0.0,
            "0.50_ist1": 5.5,
            "0.50_ist2": 5.5
        },
        "asme_thk": {
            "0.72_hat": 0.0,
            "0.60_hat": 0.0,
            "0.50_hat": 0.0,
            "0.50_ist1": 5.49,
            "0.50_ist2": 5.49
        },
        "diameter_tol_botas": {
            "end_max": 90.5,
            "end_min": 88.5,
            "body_max": 89.56675000000001,
            "body_min": 88.23325000000001
        },
        "diameter_tol_asme": {
            "end_max": 90.5,
            "end_min": 88.5,
            "body_max": 89.56675000000001,
            "body_min": 88.23325000000001
        },
        "ovality": {
            "end": "0.6667500000000001",
            "body": "1.7780000000000002"
        }
    },
    {
        "inch": "4\"",
        "mm": 114.3,
        "default_material": "GRADE B",
        "botas_thk": {
            "0.72_hat": 0.0,
            "0.60_hat": 0.0,
            "0.50_hat": 0.0,
            "0.50_ist1": 6.0,
            "0.50_ist2": 6.0
        },
        "asme_thk": {
            "0.72_hat": 0.0,
            "0.60_hat": 0.0,
            "0.50_hat": 0.0,
            "0.50_ist1": 6.02,
            "0.50_ist2": 6.02
        },
        "diameter_tol_botas": {
            "end_max": 115.89999999999999,
            "end_min": 113.89999999999999,
            "body_max": 115.15725,
            "body_min": 113.44275
        },
        "diameter_tol_asme": {
            "end_max": 115.89999999999999,
            "end_min": 113.89999999999999,
            "body_max": 115.15725,
            "body_min": 113.44275
        },
        "ovality": {
            "end": "0.85725",
            "body": "2.286"
        }
    },
    {
        "inch": "5\"",
        "mm": 141.3,
        "default_material": "GRADE B",
        "botas_thk": {
            "0.72_hat": 0.0,
            "0.60_hat": 0.0,
            "0.50_hat": 0.0,
            "0.50_ist1": 6.6,
            "0.50_ist2": 7.1
        },
        "asme_thk": {
            "0.72_hat": 0.0,
            "0.60_hat": 0.0,
            "0.50_hat": 0.0,
            "0.50_ist1": 6.55,
            "0.50_ist2": 7.1
        },
        "diameter_tol_botas": {
            "end_max": 142.9,
            "end_min": 140.9,
            "body_max": 142.35975000000002,
            "body_min": 140.24025000000003
        },
        "diameter_tol_asme": {
            "end_max": 142.9,
            "end_min": 140.9,
            "body_max": 142.35975000000002,
            "body_min": 140.24025000000003
        },
        "ovality": {
            "end": "1.05975",
            "body": "2.826"
        }
    },
    {
        "inch": "6\"",
        "mm": 168.3,
        "default_material": "X42",
        "botas_thk": {
            "0.72_hat": 5.2,
            "0.60_hat": 5.2,
            "0.50_hat": 5.2,
            "0.50_ist1": 6.4,
            "0.50_ist2": 6.4
        },
        "asme_thk": {
            "0.72_hat": 5.16,
            "0.60_hat": 5.16,
            "0.50_hat": 5.16,
            "0.50_ist1": 6.35,
            "0.50_ist2": 6.35
        },
        "diameter_tol_botas": {
            "end_max": 169.14149999999998,
            "end_min": 167.45850000000002,
            "body_max": 169.56225000000003,
            "body_min": 167.03775000000002
        },
        "diameter_tol_asme": {
            "end_max": 169.14149999999998,
            "end_min": 167.45850000000002,
            "body_max": 169.56225000000003,
            "body_min": 167.03775000000002
        },
        "ovality": {
            "end": "1.26225",
            "body": "3.366"
        }
    },
    {
        "inch": "8\"",
        "mm": 219.1,
        "default_material": "X42",
        "botas_thk": {
            "0.72_hat": 5.2,
            "0.60_hat": 5.2,
            "0.50_hat": 6.4,
            "0.50_ist1": 7.9,
            "0.50_ist2": 7.9
        },
        "asme_thk": {
            "0.72_hat": 5.16,
            "0.60_hat": 5.16,
            "0.50_hat": 6.35,
            "0.50_ist1": 7.92,
            "0.50_ist2": 7.92
        },
        "diameter_tol_botas": {
            "end_max": 220.19549999999998,
            "end_min": 218.0045,
            "body_max": 220.74325000000002,
            "body_min": 217.45675
        },
        "diameter_tol_asme": {
            "end_max": 220.19549999999998,
            "end_min": 218.0045,
            "body_max": 220.74325000000002,
            "body_min": 217.45675
        },
        "ovality": {
            "end": "1.6432499999999999",
            "body": "4.382"
        }
    },
    {
        "inch": "10\"",
        "mm": 273.1,
        "default_material": "X46",
        "botas_thk": {
            "0.72_hat": 5.2,
            "0.60_hat": 5.6,
            "0.50_hat": 7.1,
            "0.50_ist1": 8.7,
            "0.50_ist2": 8.7
        },
        "asme_thk": {
            "0.72_hat": 5.16,
            "0.60_hat": 5.56,
            "0.50_hat": 7.09,
            "0.50_ist1": 8.74,
            "0.50_ist2": 8.74
        },
        "diameter_tol_botas": {
            "end_max": 274.4655,
            "end_min": 271.7345,
            "body_max": 275.14825,
            "body_min": 271.05175
        },
        "diameter_tol_asme": {
            "end_max": 274.4655,
            "end_min": 271.7345,
            "body_max": 275.14825,
            "body_min": 271.05175
        },
        "ovality": {
            "end": "2.04825",
            "body": "5.462000000000001"
        }
    },
    {
        "inch": "12\"",
        "mm": 323.9,
        "default_material": "X52",
        "botas_thk": {
            "0.72_hat": 5.2,
            "0.60_hat": 6.4,
            "0.50_hat": 7.1,
            "0.50_ist1": 8.4,
            "0.50_ist2": 9.5
        },
        "asme_thk": {
            "0.72_hat": 5.16,
            "0.60_hat": 6.35,
            "0.50_hat": 7.14,
            "0.50_ist1": 8.38,
            "0.50_ist2": 9.53
        },
        "diameter_tol_botas": {
            "end_max": 325.5,
            "end_min": 322.29999999999995,
            "body_max": 326.32925,
            "body_min": 321.47075
        },
        "diameter_tol_asme": {
            "end_max": 325.5,
            "end_min": 322.29999999999995,
            "body_max": 326.32925,
            "body_min": 321.47075
        },
        "ovality": {
            "end": "2.4292499999999997",
            "body": "6.478"
        }
    },
    {
        "inch": "14\"",
        "mm": 355.6,
        "default_material": "X52",
        "botas_thk": {
            "0.72_hat": 5.2,
            "0.60_hat": 6.4,
            "0.50_hat": 7.9,
            "0.50_ist1": 9.5,
            "0.50_ist2": 10.3
        },
        "asme_thk": {
            "0.72_hat": 5.16,
            "0.60_hat": 6.35,
            "0.50_hat": 7.92,
            "0.50_ist1": 9.53,
            "0.50_ist2": 10.31
        },
        "diameter_tol_botas": {
            "end_max": 357.20000000000005,
            "end_min": 354.0,
            "body_max": 358.26700000000005,
            "body_min": 352.93300000000005
        },
        "diameter_tol_asme": {
            "end_max": 357.20000000000005,
            "end_min": 354.0,
            "body_max": 358.26700000000005,
            "body_min": 352.93300000000005
        },
        "ovality": {
            "end": "2.6670000000000003",
            "body": "7.112000000000001"
        }
    },
    {
        "inch": "16\"",
        "mm": 406.4,
        "default_material": "X60",
        "botas_thk": {
            "0.72_hat": 5.2,
            "0.60_hat": 6.4,
            "0.50_hat": 7.9,
            "0.50_ist1": 9.5,
            "0.50_ist2": 10.3
        },
        "asme_thk": {
            "0.72_hat": 5.16,
            "0.60_hat": 6.35,
            "0.50_hat": 7.92,
            "0.50_ist1": 9.53,
            "0.50_ist2": 10.31
        },
        "diameter_tol_botas": {
            "end_max": 408.0,
            "end_min": 404.79999999999995,
            "body_max": 409.448,
            "body_min": 403.352
        },
        "diameter_tol_asme": {
            "end_max": 408.0,
            "end_min": 404.79999999999995,
            "body_max": 409.448,
            "body_min": 403.352
        },
        "ovality": {
            "end": "3.0479999999999996",
            "body": "8.128"
        }
    },
    {
        "inch": "18\"",
        "mm": 457.0,
        "default_material": "X65",
        "botas_thk": {
            "0.72_hat": 5.6,
            "0.60_hat": 6.4,
            "0.50_hat": 7.9,
            "0.50_ist1": 9.5,
            "0.50_ist2": 10.3
        },
        "asme_thk": {
            "0.72_hat": 5.56,
            "0.60_hat": 6.35,
            "0.50_hat": 7.92,
            "0.50_ist1": 9.53,
            "0.50_ist2": 10.31
        },
        "diameter_tol_botas": {
            "end_max": 458.6,
            "end_min": 455.4,
            "body_max": 460.2,
            "body_min": 453.57250000000005
        },
        "diameter_tol_asme": {
            "end_max": 458.6,
            "end_min": 455.4,
            "body_max": 460.2,
            "body_min": 453.57250000000005
        },
        "ovality": {
            "end": "3.4274999999999998",
            "body": "9.14"
        }
    },
    {
        "inch": "20\"",
        "mm": 508.0,
        "default_material": "X65",
        "botas_thk": {
            "0.72_hat": 6.4,
            "0.60_hat": 7.1,
            "0.50_hat": 8.7,
            "0.50_ist1": 10.3,
            "0.50_ist2": 11.1
        },
        "asme_thk": {
            "0.72_hat": 6.35,
            "0.60_hat": 7.14,
            "0.50_hat": 8.74,
            "0.50_ist1": 10.31,
            "0.50_ist2": 11.13
        },
        "diameter_tol_botas": {
            "end_max": 509.6,
            "end_min": 506.4,
            "body_max": 511.2,
            "body_min": 504.19
        },
        "diameter_tol_asme": {
            "end_max": 509.6,
            "end_min": 506.4,
            "body_max": 511.2,
            "body_min": 504.19
        },
        "ovality": {
            "end": "3.81",
            "body": "10.16"
        }
    },
    {
        "inch": "22\"",
        "mm": 559.0,
        "default_material": "X65",
        "botas_thk": {
            "0.72_hat": 7.1,
            "0.60_hat": 7.9,
            "0.50_hat": 9.5,
            "0.50_ist1": 11.1,
            "0.50_ist2": 11.9
        },
        "asme_thk": {
            "0.72_hat": 7.14,
            "0.60_hat": 7.92,
            "0.50_hat": 9.53,
            "0.50_ist1": 11.13,
            "0.50_ist2": 11.97
        },
        "diameter_tol_botas": {
            "end_max": 560.6,
            "end_min": 557.4,
            "body_max": 562.2,
            "body_min": 554.8075
        },
        "diameter_tol_asme": {
            "end_max": 560.6,
            "end_min": 557.4,
            "body_max": 562.2,
            "body_min": 554.8075
        },
        "ovality": {
            "end": "4.1925",
            "body": "11.18"
        }
    },
    {
        "inch": "24\"",
        "mm": 610.0,
        "default_material": "X65",
        "botas_thk": {
            "0.72_hat": 7.1,
            "0.60_hat": 8.7,
            "0.50_hat": 10.3,
            "0.50_ist1": 11.9,
            "0.50_ist2": 12.7
        },
        "asme_thk": {
            "0.72_hat": 7.14,
            "0.60_hat": 8.74,
            "0.50_hat": 10.31,
            "0.50_ist1": 11.97,
            "0.50_ist2": 12.7
        },
        "diameter_tol_botas": {
            "end_max": 611.6,
            "end_min": 608.4,
            "body_max": 613.2,
            "body_min": 605.4250000000001
        },
        "diameter_tol_asme": {
            "end_max": 611.6,
            "end_min": 608.4,
            "body_max": 613.2,
            "body_min": 605.4250000000001
        },
        "ovality": {
            "end": "4.575",
            "body": "12.200000000000001"
        }
    },
    {
        "inch": "30\"",
        "mm": 762.0,
        "default_material": "X65",
        "botas_thk": {
            "0.72_hat": 9.5,
            "0.60_hat": 11.1,
            "0.50_hat": 12.7,
            "0.50_ist1": 14.3,
            "0.50_ist2": 15.9
        },
        "asme_thk": {
            "0.72_hat": 9.53,
            "0.60_hat": 11.13,
            "0.50_hat": 12.7,
            "0.50_ist1": 14.27,
            "0.50_ist2": 15.88
        },
        "diameter_tol_botas": {
            "end_max": 763.6,
            "end_min": 760.4,
            "body_max": 765.81,
            "body_min": 758.1899999999999
        },
        "diameter_tol_asme": {
            "end_max": 763.6,
            "end_min": 760.4,
            "body_max": 765.81,
            "body_min": 758.1899999999999
        },
        "ovality": {
            "end": "Anlaşmaya bağlıdır.",
            "body": "Anlaşmaya bağlıdır."
        }
    },
    {
        "inch": "32\"",
        "mm": 813.0,
        "default_material": "X65",
        "botas_thk": {
            "0.72_hat": 9.5,
            "0.60_hat": 11.9,
            "0.50_hat": 14.3,
            "0.50_ist1": 15.9,
            "0.50_ist2": 17.5
        },
        "asme_thk": {
            "0.72_hat": 9.53,
            "0.60_hat": 11.91,
            "0.50_hat": 14.27,
            "0.50_ist1": 15.88,
            "0.50_ist2": 17.48
        },
        "diameter_tol_botas": {
            "end_max": 814.6,
            "end_min": 811.4,
            "body_max": 817.0,
            "body_min": 809.0
        },
        "diameter_tol_asme": {
            "end_max": 814.6,
            "end_min": 811.4,
            "body_max": 817.0,
            "body_min": 809.0
        },
        "ovality": {
            "end": "Anlaşmaya bağlıdır.",
            "body": "Anlaşmaya bağlıdır."
        }
    },
    {
        "inch": "34\"",
        "mm": 864.0,
        "default_material": "X65",
        "botas_thk": {
            "0.72_hat": 10.3,
            "0.60_hat": 12.7,
            "0.50_hat": 15.9,
            "0.50_ist1": 15.9,
            "0.50_ist2": 17.5
        },
        "asme_thk": {
            "0.72_hat": 10.31,
            "0.60_hat": 12.7,
            "0.50_hat": 15.88,
            "0.50_ist1": 15.88,
            "0.50_ist2": 17.48
        },
        "diameter_tol_botas": {
            "end_max": 865.6,
            "end_min": 862.4,
            "body_max": 868.0,
            "body_min": 860.0
        },
        "diameter_tol_asme": {
            "end_max": 865.6,
            "end_min": 862.4,
            "body_max": 868.0,
            "body_min": 860.0
        },
        "ovality": {
            "end": "Anlaşmaya bağlıdır.",
            "body": "Anlaşmaya bağlıdır."
        }
    },
    {
        "inch": "36\"",
        "mm": 914.0,
        "default_material": "X65",
        "botas_thk": {
            "0.72_hat": 11.1,
            "0.60_hat": 12.7,
            "0.50_hat": 15.9,
            "0.50_ist1": 17.5,
            "0.50_ist2": 19.1
        },
        "asme_thk": {
            "0.72_hat": 11.13,
            "0.60_hat": 12.7,
            "0.50_hat": 15.88,
            "0.50_ist1": 17.48,
            "0.50_ist2": 19.05
        },
        "diameter_tol_botas": {
            "end_max": 915.6,
            "end_min": 912.4,
            "body_max": 918.0,
            "body_min": 910.0
        },
        "diameter_tol_asme": {
            "end_max": 915.6,
            "end_min": 912.4,
            "body_max": 918.0,
            "body_min": 910.0
        },
        "ovality": {
            "end": "Anlaşmaya bağlıdır.",
            "body": "Anlaşmaya bağlıdır."
        }
    },
    {
        "inch": "38\"",
        "mm": 965.0,
        "default_material": "X65",
        "botas_thk": {
            "0.72_hat": 11.9,
            "0.60_hat": 14.3,
            "0.50_hat": 17.5,
            "0.50_ist1": 19.1,
            "0.50_ist2": 20.6
        },
        "asme_thk": {
            "0.72_hat": 11.91,
            "0.60_hat": 14.27,
            "0.50_hat": 17.48,
            "0.50_ist1": 19.05,
            "0.50_ist2": 20.62
        },
        "diameter_tol_botas": {
            "end_max": 966.6,
            "end_min": 963.4,
            "body_max": 969.0,
            "body_min": 961.0
        },
        "diameter_tol_asme": {
            "end_max": 966.6,
            "end_min": 963.4,
            "body_max": 969.0,
            "body_min": 961.0
        },
        "ovality": {
            "end": "Anlaşmaya bağlıdır.",
            "body": "Anlaşmaya bağlıdır."
        }
    },
    {
        "inch": "40\"",
        "mm": 1016.0,
        "default_material": "X65",
        "botas_thk": {
            "0.72_hat": 11.9,
            "0.60_hat": 14.3,
            "0.50_hat": 17.5,
            "0.50_ist1": 19.1,
            "0.50_ist2": 20.6
        },
        "asme_thk": {
            "0.72_hat": 11.91,
            "0.60_hat": 14.27,
            "0.50_hat": 17.48,
            "0.50_ist1": 19.05,
            "0.50_ist2": 20.62
        },
        "diameter_tol_botas": {
            "end_max": 1017.6,
            "end_min": 1014.4,
            "body_max": 1020.0,
            "body_min": 1012.0
        },
        "diameter_tol_asme": {
            "end_max": 1017.6,
            "end_min": 1014.4,
            "body_max": 1020.0,
            "body_min": 1012.0
        },
        "ovality": {
            "end": "Anlaşmaya bağlıdır.",
            "body": "Anlaşmaya bağlıdır."
        }
    },
    {
        "inch": "42\"",
        "mm": 1067.0,
        "default_material": "X65",
        "botas_thk": {
            "0.72_hat": 12.7,
            "0.60_hat": 15.9,
            "0.50_hat": 19.1,
            "0.50_ist1": 20.6,
            "0.50_ist2": 22.2
        },
        "asme_thk": {
            "0.72_hat": 12.7,
            "0.60_hat": 15.88,
            "0.50_hat": 19.05,
            "0.50_ist1": 20.62,
            "0.50_ist2": 22.23
        },
        "diameter_tol_botas": {
            "end_max": 1068.6,
            "end_min": 1065.4,
            "body_max": 1071.0,
            "body_min": 1063.0
        },
        "diameter_tol_asme": {
            "end_max": 1068.6,
            "end_min": 1065.4,
            "body_max": 1071.0,
            "body_min": 1063.0
        },
        "ovality": {
            "end": "Anlaşmaya bağlıdır.",
            "body": "Anlaşmaya bağlıdır."
        }
    },
    {
        "inch": "44\"",
        "mm": 1118.0,
        "default_material": "X65",
        "botas_thk": {
            "0.72_hat": 14.3,
            "0.60_hat": 15.9,
            "0.50_hat": 19.1,
            "0.50_ist1": 20.6,
            "0.50_ist2": 22.2
        },
        "asme_thk": {
            "0.72_hat": 14.27,
            "0.60_hat": 15.88,
            "0.50_hat": 19.05,
            "0.50_ist1": 20.62,
            "0.50_ist2": 22.23
        },
        "diameter_tol_botas": {
            "end_max": 1119.6,
            "end_min": 1116.4,
            "body_max": 1122.0,
            "body_min": 1114.0
        },
        "diameter_tol_asme": {
            "end_max": 1119.6,
            "end_min": 1116.4,
            "body_max": 1122.0,
            "body_min": 1114.0
        },
        "ovality": {
            "end": "Anlaşmaya bağlıdır.",
            "body": "Anlaşmaya bağlıdır."
        }
    },
    {
        "inch": "46\"",
        "mm": 1168.0,
        "default_material": "X65",
        "botas_thk": {
            "0.72_hat": 14.3,
            "0.60_hat": 17.5,
            "0.50_hat": 20.6,
            "0.50_ist1": 22.2,
            "0.50_ist2": 23.8
        },
        "asme_thk": {
            "0.72_hat": 14.27,
            "0.60_hat": 17.48,
            "0.50_hat": 20.62,
            "0.50_ist1": 22.23,
            "0.50_ist2": 23.83
        },
        "diameter_tol_botas": {
            "end_max": 1169.6,
            "end_min": 1166.4,
            "body_max": 1172.0,
            "body_min": 1164.0
        },
        "diameter_tol_asme": {
            "end_max": 1169.6,
            "end_min": 1166.4,
            "body_max": 1172.0,
            "body_min": 1164.0
        },
        "ovality": {
            "end": "Anlaşmaya bağlıdır.",
            "body": "Anlaşmaya bağlıdır."
        }
    },
    {
        "inch": "48\"",
        "mm": 1219.0,
        "default_material": "X65",
        "botas_thk": {
            "0.72_hat": 14.3,
            "0.60_hat": 17.5,
            "0.50_hat": 20.6,
            "0.50_ist1": 22.2,
            "0.50_ist2": 23.8
        },
        "asme_thk": {
            "0.72_hat": 14.27,
            "0.60_hat": 17.48,
            "0.50_hat": 20.62,
            "0.50_ist1": 22.23,
            "0.50_ist2": 23.83
        },
        "diameter_tol_botas": {
            "end_max": 1220.6,
            "end_min": 1217.4,
            "body_max": 1223.0,
            "body_min": 1215.0
        },
        "diameter_tol_asme": {
            "end_max": 1220.6,
            "end_min": 1217.4,
            "body_max": 1223.0,
            "body_min": 1215.0
        },
        "ovality": {
            "end": "Anlaşmaya bağlıdır.",
            "body": "Anlaşmaya bağlıdır."
        }
    },
    {
        "inch": "52\"",
        "mm": 1321.0,
        "default_material": "X65",
        "botas_thk": {
            "0.72_hat": 15.9,
            "0.60_hat": 19.1,
            "0.50_hat": 22.2,
            "0.50_ist1": 23.8,
            "0.50_ist2": 27.0
        },
        "asme_thk": {
            "0.72_hat": 15.88,
            "0.60_hat": 19.05,
            "0.50_hat": 22.23,
            "0.50_ist1": 23.83,
            "0.50_ist2": 26.97
        },
        "diameter_tol_botas": {
            "end_max": 1322.6,
            "end_min": 1319.4,
            "body_max": 1325.0,
            "body_min": 1317.0
        },
        "diameter_tol_asme": {
            "end_max": 1322.6,
            "end_min": 1319.4,
            "body_max": 1325.0,
            "body_min": 1317.0
        },
        "ovality": {
            "end": "Anlaşmaya bağlıdır.",
            "body": "Anlaşmaya bağlıdır."
        }
    },
    {
        "inch": "56\"",
        "mm": 1422.0,
        "default_material": "X65",
        "botas_thk": {
            "0.72_hat": 17.5,
            "0.60_hat": 20.6,
            "0.50_hat": 23.8,
            "0.50_ist1": 25.4,
            "0.50_ist2": 28.6
        },
        "asme_thk": {
            "0.72_hat": 17.48,
            "0.60_hat": 20.62,
            "0.50_hat": 23.83,
            "0.50_ist1": 25.4,
            "0.50_ist2": 28.58
        },
        "diameter_tol_botas": {
            "end_max": 1423.6,
            "end_min": 1420.4,
            "body_max": 1426.0,
            "body_min": 1418.0
        },
        "diameter_tol_asme": {
            "end_max": 1423.6,
            "end_min": 1420.4,
            "body_max": 1426.0,
            "body_min": 1418.0
        },
        "ovality": {
            "end": "Anlaşmaya bağlıdır.",
            "body": "Anlaşmaya bağlıdır."
        }
    },
    {
        "inch": "60\"",
        "mm": 1524.0,
        "default_material": "X65",
        "botas_thk": {
            "0.72_hat": 19.1,
            "0.60_hat": 22.2,
            "0.50_hat": 25.4,
            "0.50_ist1": 27.0,
            "0.50_ist2": 30.2
        },
        "asme_thk": {
            "0.72_hat": 19.05,
            "0.60_hat": 22.23,
            "0.50_hat": 25.4,
            "0.50_ist1": 26.97,
            "0.50_ist2": 30.18
        },
        "diameter_tol_botas": {
            "end_max": 1525.6,
            "end_min": 1522.4,
            "body_max": 1528.0,
            "body_min": 1520.0
        },
        "diameter_tol_asme": {
            "end_max": 1525.6,
            "end_min": 1522.4,
            "body_max": 1528.0,
            "body_min": 1520.0
        },
        "ovality": {
            "end": "Anlaşmaya bağlıdır.",
            "body": "Anlaşmaya bağlıdır."
        }
    }
]

# Populate explicit aliases for 75 bar and 82.5 bar station thickness keys
for _p in PIPE_SIZES_TABLE:
    if "0.50_ist1" in _p.get("botas_thk", {}):
        _p["botas_thk"]["0.50_ist_75bar"] = _p["botas_thk"]["0.50_ist1"]
        _p["botas_thk"]["0.50_ist_82_5bar"] = _p["botas_thk"]["0.50_ist2"]
    if "0.50_ist1" in _p.get("asme_thk", {}):
        _p["asme_thk"]["0.50_ist_75bar"] = _p["asme_thk"]["0.50_ist1"]
        _p["asme_thk"]["0.50_ist_82_5bar"] = _p["asme_thk"]["0.50_ist2"]

# ASME B36.10 Schedule Thicknesses Matrix
ASME_B36_10_TABLE = {
    "0.125": [
        1.24,
        1.45,
        1.73,
        2.41
    ],
    "0.25": [
        1.65,
        1.85,
        2.24,
        3.02
    ],
    "0.375": [
        1.65,
        1.85,
        2.31,
        3.2
    ],
    "0.5": [
        1.65,
        2.11,
        2.41,
        2.77,
        3.73,
        4.78,
        7.47
    ],
    "0.75": [
        1.65,
        2.11,
        2.41,
        2.87,
        3.91,
        5.56,
        7.82
    ],
    "1": [
        1.65,
        2.77,
        2.9,
        3.38,
        4.55,
        6.35,
        9.09
    ],
    "1.25": [
        1.65,
        2.77,
        2.97,
        3.56,
        4.85,
        6.35,
        9.7
    ],
    "1.5": [
        1.65,
        2.77,
        3.18,
        3.68,
        5.08,
        7.14,
        10.15
    ],
    "2": [
        1.65,
        2.11,
        2.77,
        3.18,
        3.91,
        4.37,
        4.78,
        5.54,
        6.35,
        7.14,
        8.74,
        11.07
    ],
    "2.5": [
        2.11,
        2.77,
        3.05,
        3.18,
        3.58,
        3.96,
        4.37,
        4.78,
        5.16,
        5.49,
        6.35,
        7.01,
        9.53,
        14.02
    ],
    "3": [
        2.11,
        2.77,
        3.05,
        3.18,
        3.58,
        3.96,
        4.37,
        4.78,
        5.49,
        6.35,
        7.14,
        7.62,
        11.13,
        15.24
    ],
    "3.5": [
        2.11,
        2.77,
        3.05,
        3.18,
        3.58,
        3.96,
        4.37,
        4.78,
        5.74,
        6.35,
        7.14,
        8.08
    ],
    "4": [
        1.13,
        2.11,
        2.77,
        3.05,
        3.18,
        3.58,
        3.96,
        4.37,
        4.78,
        5.16,
        5.56,
        6.02,
        6.35,
        7.14,
        7.92,
        8.56,
        13.49,
        17.12
    ],
    "5": [
        2.11,
        2.77,
        3.18,
        3.4,
        3.96,
        4.78,
        5.56,
        6.55,
        7.14,
        7.92,
        8.74,
        9.53,
        12.7,
        15.88,
        19.05
    ],
    "6": [
        2.11,
        2.77,
        3.18,
        3.4,
        3.58,
        3.96,
        4.37,
        4.78,
        5.16,
        5.56,
        6.35,
        7.11,
        7.92,
        8.74,
        9.53,
        10.97,
        12.7,
        14.27,
        15.88,
        18.26,
        19.05,
        21.95,
        22.23
    ],
    "8": [
        2.77,
        3.18,
        3.76,
        3.96,
        4.78,
        5.16,
        5.56,
        6.35,
        7.04,
        7.92,
        8.18,
        8.74,
        9.53,
        10.31,
        11.13,
        12.7,
        14.27,
        15.09,
        15.88,
        18.26,
        19.05,
        20.62,
        22.23,
        23.01,
        25.4
    ],
    "10": [
        3.4,
        3.96,
        4.19,
        4.78,
        5.16,
        5.56,
        6.35,
        7.09,
        7.8,
        8.74,
        9.27,
        11.13,
        12.7,
        14.27,
        15.09,
        15.88,
        18.26,
        20.62,
        21.44,
        22.23,
        23.83,
        25.4,
        28.58,
        31.75
    ],
    "12": [
        3.96,
        4.37,
        4.57,
        4.78,
        5.16,
        5.56,
        6.35,
        7.14,
        7.92,
        8.38,
        8.74,
        9.53,
        10.31,
        11.13,
        12.7,
        14.27,
        15.88,
        17.48,
        19.05,
        20.62,
        21.44,
        22.23,
        23.83,
        25.4,
        26.97,
        28.58,
        31.75,
        33.32
    ],
    "14": [
        3.96,
        4.78,
        5.16,
        5.33,
        5.56,
        6.35,
        7.14,
        7.92,
        8.74,
        9.53,
        10.31,
        11.13,
        11.91,
        12.7,
        14.27,
        15.09,
        15.88,
        17.48,
        19.05,
        20.62,
        22.23,
        23.83,
        25.4,
        26.97,
        27.79,
        28.58,
        31.75,
        35.71,
        50.8,
        53.98,
        55.88,
        63.5
    ],
    "16": [
        4.19,
        4.78,
        5.16,
        5.56,
        6.35,
        7.14,
        7.92,
        8.74,
        9.53,
        10.31,
        11.13,
        11.91,
        12.7,
        14.27,
        15.88,
        16.66,
        17.48,
        19.05,
        20.62,
        21.44,
        22.23,
        23.83,
        25.4,
        26.19,
        26.97,
        28.58,
        30.18,
        30.96,
        31.73,
        36.53,
        40.49
    ],
    "18": [
        4.19,
        4.78,
        5.56,
        6.35,
        7.14,
        7.92,
        8.74,
        9.53,
        10.31,
        11.13,
        11.91,
        12.7,
        14.27,
        15.88,
        17.48,
        19.05,
        20.62,
        22.23,
        23.83,
        25.4,
        26.97,
        28.58,
        29.36,
        30.18,
        31.75,
        34.93,
        39.67,
        45.24
    ],
    "20": [
        4.78,
        5.56,
        6.35,
        7.14,
        7.92,
        8.74,
        9.53,
        10.31,
        11.13,
        11.91,
        12.7,
        14.27,
        15.09,
        15.88,
        17.48,
        19.05,
        20.62,
        22.23,
        23.83,
        25.4,
        26.19,
        26.97,
        28.58,
        30.18,
        31.75,
        32.54,
        33.32,
        34.93,
        38.1,
        44.45,
        50.01
    ],
    "22": [
        4.78,
        5.56,
        6.35,
        7.14,
        7.92,
        8.74,
        9.53,
        10.31,
        11.13,
        11.91,
        12.7,
        14.27,
        15.88,
        17.48,
        19.05,
        20.62,
        22.23,
        23.83,
        25.4,
        26.97,
        28.58,
        30.18,
        31.75,
        33.92,
        34.93,
        36.53,
        38.1,
        41.28,
        47.63,
        53.98
    ],
    "24": [
        5.54,
        6.35,
        7.14,
        7.92,
        8.74,
        9.53,
        10.31,
        11.13,
        11.91,
        12.7,
        14.27,
        15.88,
        17.48,
        19.05,
        20.62,
        22.23,
        23.83,
        24.61,
        25.4,
        26.97,
        28.58,
        30.18,
        30.96,
        31.75,
        33.32,
        34.93,
        36.53,
        38.1,
        38.89,
        39.67,
        46.02,
        52.37,
        59.54
    ],
    "26": [
        6.35,
        7.14,
        7.92,
        8.74,
        9.53,
        10.31,
        11.13,
        11.91,
        12.7,
        14.27,
        15.88,
        17.48,
        19.05,
        20.62,
        22.23,
        23.83,
        25.4
    ],
    "28": [
        6.35,
        7.14,
        7.92,
        8.74,
        9.53,
        10.31,
        11.13,
        11.91,
        12.7,
        14.27,
        15.88,
        17.48,
        19.05,
        20.62,
        22.23,
        23.83,
        25.4
    ],
    "30": [
        6.35,
        7.14,
        7.92,
        8.74,
        9.53,
        10.31,
        11.13,
        11.91,
        12.7,
        14.27,
        15.88,
        17.48,
        19.05,
        20.62,
        22.23,
        23.83,
        25.4,
        26.97,
        28.58,
        30.18,
        31.75
    ],
    "32": [
        6.35,
        7.14,
        7.92,
        8.74,
        9.53,
        10.31,
        11.13,
        11.91,
        12.7,
        14.27,
        15.88,
        17.48,
        19.05,
        20.62,
        22.23,
        23.83,
        25.4,
        26.97,
        28.58,
        30.18,
        31.75
    ],
    "34": [
        6.35,
        7.14,
        7.92,
        8.74,
        9.53,
        10.31,
        11.13,
        11.91,
        12.7,
        14.27,
        15.88,
        17.48,
        19.05,
        20.62,
        22.23,
        23.83,
        25.4,
        26.97,
        28.58,
        30.18,
        31.75
    ],
    "36": [
        6.35,
        7.14,
        7.92,
        8.74,
        9.53,
        10.31,
        11.13,
        11.91,
        12.7,
        14.27,
        15.88,
        17.48,
        19.05,
        20.62,
        22.23,
        23.83,
        25.4,
        26.97,
        28.58,
        30.18,
        31.75
    ],
    "38": [
        7.92,
        8.74,
        9.53,
        10.31,
        11.13,
        11.91,
        12.7,
        14.27,
        15.88,
        17.48,
        19.05,
        20.62,
        22.23,
        23.83,
        25.4,
        26.97,
        28.58,
        30.18,
        31.75
    ],
    "40": [
        7.92,
        8.74,
        9.53,
        10.31,
        11.13,
        11.91,
        12.7,
        14.27,
        15.88,
        17.48,
        19.05,
        20.62,
        22.23,
        23.83,
        25.4,
        26.97,
        28.58,
        30.18,
        31.75
    ],
    "42": [
        8.74,
        9.53,
        10.31,
        11.13,
        11.91,
        12.7,
        14.27,
        15.88,
        17.48,
        19.05,
        20.62,
        22.23,
        23.83,
        25.4,
        26.97,
        28.58,
        30.18,
        31.75
    ],
    "44": [
        8.74,
        9.53,
        10.31,
        11.13,
        11.91,
        12.7,
        14.27,
        15.88,
        17.48,
        19.05,
        20.62,
        22.23,
        23.83,
        25.4,
        26.97,
        28.58,
        30.18,
        31.75
    ],
    "46": [
        8.74,
        9.53,
        10.31,
        11.13,
        11.91,
        12.7,
        14.27,
        15.88,
        17.48,
        19.05,
        20.62,
        22.23,
        23.83,
        25.4,
        26.97,
        28.58,
        30.18,
        31.75
    ],
    "48": [
        8.74,
        9.53,
        10.31,
        11.13,
        11.91,
        12.7,
        14.27,
        15.88,
        17.48,
        19.05,
        20.62,
        22.23,
        23.83,
        25.4,
        26.97,
        28.58,
        30.18,
        31.75
    ],
    "52": [
        9.53,
        10.31,
        11.13,
        11.91,
        12.7,
        14.27,
        15.88,
        17.48,
        19.05,
        20.62,
        22.23,
        23.83,
        25.4,
        26.97,
        28.58,
        30.18,
        31.75
    ],
    "56": [
        9.53,
        10.31,
        11.13,
        11.91,
        12.7,
        14.27,
        15.88,
        17.48,
        19.05,
        20.62,
        22.23,
        23.83,
        25.4,
        26.97,
        28.58,
        30.18,
        31.75
    ],
    "60": [
        9.53,
        10.31,
        11.13,
        11.91,
        12.7,
        14.27,
        15.88,
        17.48,
        19.05,
        20.62,
        22.23,
        23.83,
        25.4,
        26.97,
        28.58,
        30.18,
        31.75
    ],
    "64": [
        9.53,
        10.31,
        11.13,
        11.91,
        12.7,
        14.27,
        15.88,
        17.48,
        19.05,
        20.62,
        22.23,
        23.83,
        25.4,
        26.97,
        28.58,
        30.18,
        31.75
    ],
    "68": [
        11.91,
        12.7,
        14.27,
        15.88,
        17.48,
        19.05,
        20.62,
        22.23,
        23.83,
        25.4,
        26.97,
        28.58,
        30.18,
        31.75
    ],
    "72": [
        12.7,
        14.27,
        15.88,
        17.48,
        19.05,
        20.62,
        22.23,
        23.83,
        25.4,
        26.97,
        28.58,
        30.18,
        31.75
    ],
    "76": [
        12.7,
        14.27,
        15.88,
        17.48,
        19.05,
        20.62,
        22.23,
        23.83,
        25.4,
        26.97,
        28.58,
        30.18,
        31.75
    ],
    "80": [
        12.7,
        14.27,
        15.88,
        17.48,
        19.05,
        20.62,
        22.23,
        23.83,
        25.4,
        26.97,
        28.58,
        30.18,
        31.75
    ]
}

# ASME B36.19M Stainless Steel Pipe Dimensions (Schedules 5S, 10S, 40S, 80S)
ASME_B36_19_TABLE = {
    "1/8": [1.24, 1.45, 1.73, 2.41],
    "1/4": [1.24, 1.65, 2.24, 3.02],
    "3/8": [1.24, 1.65, 2.31, 3.20],
    "1/2": [1.65, 2.11, 2.77, 3.73],
    "3/4": [1.65, 2.11, 2.87, 3.91],
    "1": [1.65, 2.77, 3.38, 4.55],
    "1 1/4": [1.65, 2.77, 3.56, 4.85],
    "1 1/2": [1.65, 2.77, 3.68, 5.08],
    "2": [1.65, 2.77, 3.91, 5.54],
    "2 1/2": [2.11, 3.05, 5.16, 7.01],
    "3": [2.11, 3.05, 5.49, 7.62],
    "3 1/2": [2.11, 3.05, 5.74, 8.08],
    "4": [2.11, 3.05, 6.02, 8.56],
    "5": [2.77, 3.40, 6.55, 9.53],
    "6": [2.77, 3.40, 7.11, 10.97],
    "8": [2.77, 3.76, 8.18, 12.70],
    "10": [3.40, 4.19, 9.27, 12.70],
    "12": [3.96, 4.57, 9.53, 12.70],
    "14": [3.96, 4.78, 9.53, 12.70],
    "16": [4.19, 4.78, 9.53, 12.70],
    "18": [4.19, 4.78, 9.53, 12.70],
    "20": [4.78, 5.54, 9.53, 12.70],
    "22": [4.78, 5.54, 9.53, 12.70],
    "24": [5.54, 6.35, 9.53, 12.70],
    "30": [6.35, 7.92, 9.53, 12.70],
    "36": [6.35, 7.92, 9.53, 12.70]
}

def is_stainless_grade(grade: str) -> bool:
    """Returns True if the material grade is stainless steel or duplex."""
    g = grade.upper().strip()
    return "SS" in g or "304" in g or "316" in g or "321" in g or "DUPLEX" in g

# Helper functions
def get_smys_info(grade: str, psl_level: str = "PSL2"):
    g = grade.upper().strip()
    is_psl1 = psl_level and "PSL1" in str(psl_level).upper()
    table = API_5L_PSL1_SMYS_TABLE if is_psl1 else API_5L_SMYS_TABLE
    if g in table:
        info = dict(table[g])
    else:
        default_grade = 'GRADE B' if is_psl1 else 'X65'
        info = dict(table[default_grade])
        info['is_unrecognized_fallback'] = True
        info['requested_grade'] = grade
    info.setdefault('smys_psi', info.get('yield_min_psi', 0.0))
    return info


def get_chemical_rules(
    grade: str,
    standard_type: str = "BOTAŞ",
    psl_level: str = "PSL2",
    delivery_condition: str = "M",
    manufacturing_process: str = "SAWH",
    t_mm: float = None,
):
    """
    Returns chemical-composition limits for the selected standard/PSL/delivery.

    - PSL 1        -> Table 4 (CE is not required; seamless/welded rows differ in C/Mn).
    - PSL 2 + API  -> Table 5 row selected by DELIVERY CONDITION (R/N/Q/M) (47th Ed.).
    - BOTAŞ        -> unchanged BOTAŞ limits.
    - t > 25.0 mm (API) -> 'as agreed' per API 5L 9.2.3.
    - PSL 2 SMLS t > 20.0 mm -> CE limits 'as agreed' (Table 5, footnote a).
    """
    grade = grade.upper().strip()
    is_api = "API" in str(standard_type).upper()
    is_psl1 = psl_level and "PSL1" in str(psl_level).upper()

    if is_api and t_mm is not None and float(t_mm) > 25.0:
        return {
            "as_agreed": True,
            "note": ("API 5L 9.2.3: t > 25.0 mm olduğundan kimyasal bileşim "
                     "anlaşmaya bağlıdır (Tablo 4/5 gerekirse tadil edilerek uygulanır)."),
        }

    if is_psl1:
        base = CHEMICAL_COMPOSITION_PSL1_RULES.get(grade)
        if not base:
            base = CHEMICAL_COMPOSITION_PSL1_RULES['GRADE B']
        proc = (manufacturing_process or "").upper()
        is_smls = "SMLS" in proc or "SEAMLESS" in proc or "DIKISSIZ" in proc
        key_c = "C_max_seamless" if is_smls else "C_max_welded"
        key_mn = "Mn_max_seamless" if is_smls else "Mn_max_welded"
        return {
            "C_max": base.get(key_c, base.get("C_max_welded")),
            "Mn_max": base.get(key_mn, base.get("Mn_max_welded")),
            "P_min": base.get("P_min", 0.0),
            "P_max": base.get("P_max", 0.030),
            "S_max": base.get("S_max", 0.030),
            "Nb_min": 0.0,
            "Nb_max": base.get("Nb_max"),
            "V_max": base.get("V_max"),
            "Ti_max": base.get("Ti_max"),
            "nb_v_ti_combined_max": base.get("nb_v_ti_combined_max"),
            "N_max": None,
            "CE_IIW_max": None,
            "CE_Pcm_max": None,
            "as_agreed": False,
        }

    if is_api:
        delivery = (delivery_condition or "M").upper()
        if delivery not in CHEMICAL_COMPOSITION_PSL2:
            delivery = "M"
        rules = CHEMICAL_COMPOSITION_PSL2.get(delivery, {}).get(grade)
        if not rules:
            rules = CHEMICAL_COMPOSITION_PSL2.get("M", {}).get(grade)
        if not rules:
            rules = CHEMICAL_COMPOSITION_PSL2.get("M", {}).get("GRADE B")
        rules = dict(rules)
        rules["Nb_min"] = 0.0
        rules.setdefault("N_max", rules.get("N_max"))  # present only for M grades (footnote n)
        proc = (manufacturing_process or "").upper()
        is_smls = "SMLS" in proc or "SEAMLESS" in proc or "DIKISSIZ" in proc
        if is_smls and t_mm is not None and float(t_mm) > 20.0:
            # Table 5, footnote a: for seamless pipe with t > 20.0 mm, CE limits as agreed.
            rules["CE_IIW_max"] = None
            rules["CE_Pcm_max"] = None
        rules["as_agreed"] = False
        return rules

    base = dict(CHEMICAL_COMPOSITION_RULES.get(grade, CHEMICAL_COMPOSITION_RULES['X65']))
    base["as_agreed"] = False
    return base


def get_cvn(
    grade: str,
    standard_type: str = "BOTAŞ",
    psl_level: str = "PSL2",
    d_mm: float = None,
    manufacturing_process: str = "SAWH",
):
    """
    Returns {'material_j': .., 'weld_j': .., 'required': bool} CVN minimums.
    PSL 1 -> not required (CVN is a PSL 2 requirement only).
    """
    grade = grade.upper().strip()
    is_api = "API" in str(standard_type).upper()
    is_psl1 = psl_level and "PSL1" in str(psl_level).upper()

    if is_psl1:
        return {"material_j": None, "weld_j": None, "required": False}
    if is_api:
        if d_mm is None:
            d_mm = 1219.0
        return {
            "material_j": get_cvn_body_api5l(grade, d_mm),
            "weld_j": get_cvn_weld_api5l(manufacturing_process, d_mm, grade),
            "required": True,
        }
    info = API_5L_SMYS_TABLE.get(grade, API_5L_SMYS_TABLE['X65'])
    return {
        "material_j": info.get('cvn_material_j', 0.0),
        "weld_j": info.get('cvn_weld_j', 0.0),
        "required": True,
    }


# ---------------------------------------------------------------------
# Carbon equivalent calculators (API 5L 47th Ed. Eq. 2 / Eq. 3)
# CE_IIW  = C + Mn/6 + (Cr+Mo+V)/5 + (Ni+Cu)/15        -> applies when C > 0.12 %
# CE_Pcm  = C + Si/30 + (Mn+Cu+Cr)/20 + Ni/60 + Mo/15 + V/10 + 5B   -> applies when C <= 0.12 %
# ---------------------------------------------------------------------
def _num(analysis, key, default=0.0):
    try:
        v = analysis.get(key)
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def compute_ce_iww(analysis: dict) -> float:
    return (_num(analysis, "C")
            + _num(analysis, "Mn") / 6.0
            + (_num(analysis, "Cr") + _num(analysis, "Mo") + _num(analysis, "V")) / 5.0
            + (_num(analysis, "Ni") + _num(analysis, "Cu")) / 15.0)


def compute_ce_pcm(analysis: dict) -> float:
    return (_num(analysis, "C")
            + _num(analysis, "Si") / 30.0
            + (_num(analysis, "Mn") + _num(analysis, "Cu") + _num(analysis, "Cr")) / 20.0
            + _num(analysis, "Ni") / 60.0
            + _num(analysis, "Mo") / 15.0
            + _num(analysis, "V") / 10.0
            + 5.0 * _num(analysis, "B"))


# ---------------------------------------------------------------------
# Carbon-reduction manganese compensation
#   API 5L Table 4 (PSL1) / Table 5 (PSL2) footnote b, and
#   BOTAŞ 5120 R7 Tablo-1 note c:
#   For each 0.01 % reduction of C below its specified maximum, the Mn
#   maximum may be raised by 0.05 %, capped per grade range.
# ---------------------------------------------------------------------
_MN_COMP_CAP_PSL1 = {
    "GRADE B": 1.65, "X42": 1.65, "X46": 1.65, "X52": 1.65,
    "X56": 1.75, "X60": 1.75, "X65": 1.75,
    "X70": 2.00,
}
_MN_COMP_CAP_PSL2 = {
    "GRADE B": 1.65, "X42": 1.65, "X46": 1.65, "X52": 1.65,
    "X56": 1.75, "X60": 1.75, "X65": 1.75,
    "X70": 2.00, "X80": 2.00,
    "X90": 2.20, "X100": 2.20, "X120": 2.20,
}
# BOTAŞ 5120 R7 note c: X70 and above -> 2.00 % (şartname API'den ayrıdır).
# Tablo-1'de olmayan X90/X100/X120 ise API 5L Table 5 note b'ye göre 2.20 %.
_MN_COMP_CAP_BOTAS = {
    "GRADE B": 1.65, "X42": 1.65, "X46": 1.65, "X52": 1.65,
    "X56": 1.75, "X60": 1.75, "X65": 1.75,
    "X70": 2.00, "X80": 2.00, "X90": 2.20, "X100": 2.20, "X120": 2.20,
}


def get_mn_max_compensated(
    grade: str,
    c_max: float,
    c_actual: float,
    mn_max_base: float,
    standard_type: str = "BOTAŞ",
    psl_level: str = "PSL2",
):
    """
    Returns the effective Mn maximum after the C-reduction allowance.
    Falls back to ``mn_max_base`` when the needed data is missing.
    """
    if c_max is None or c_actual is None or mn_max_base is None:
        return mn_max_base
    g = (grade or "").upper().strip()
    is_api = "API" in str(standard_type).upper()
    if is_api:
        is_psl1 = psl_level and "PSL1" in str(psl_level).upper()
        caps = _MN_COMP_CAP_PSL1 if is_psl1 else _MN_COMP_CAP_PSL2
    else:
        caps = _MN_COMP_CAP_BOTAS
    cap = caps.get(g)
    if cap is None:
        return mn_max_base
    reduction = float(c_max) - float(c_actual)
    if reduction <= 0:
        return mn_max_base
    # Only whole 0.01 % steps count.
    steps = int((reduction + 1e-9) / 0.01)
    return min(float(mn_max_base) + 0.05 * steps, cap)


# ---------------------------------------------------------------------
# Grade / delivery / process availability helpers (47th Ed. Table 1 / 2 / 3)
# ---------------------------------------------------------------------
def get_psl1_grades() -> list:
    return list(PSL1_GRADES)


def get_psl2_grades_for_delivery(delivery: str) -> list:
    return list(PSL2_DELIVERY_GRADES.get((delivery or "M").upper(), PSL2_DELIVERY_GRADES["M"]))


def get_deliveries_for_grade(grade: str) -> list:
    g = grade.upper().strip()
    return [d for d, grades in PSL2_DELIVERY_GRADES.items() if g in grades]


def get_psl1_processes() -> list:
    return list(PSL1_PROCESSES)


def get_psl2_processes_for_delivery(delivery: str) -> list:
    if (delivery or "").upper() == "M":
        return list(PSL2_M_PROCESSES)
    return list(PSL2_OTHER_PROCESSES)

def normalize_design_factor(factor_str) -> str:
    """Normalize a design factor label (tolerates comma/dot decimal separators and Turkish words)."""
    if not factor_str:
        return "0.72_hat"
    s = str(factor_str).replace(",", ".").lower()
    # Turkish capital 'İ' lowercases to 'i\u0307' (i + combining dot above); strip the dot.
    s = s.replace("\u0307", "")
    has_ist = ("ist" in s) or ("istasyon" in s)
    has_ist2 = ("ist. 2" in s) or ("ist2" in s) or ("istasyon 2" in s) or ("82.5" in s) or ("82_5" in s) or ("82.5 bar" in s)
    if "0.8" in s:
        return "0.80_hat"
    if "0.6" in s:
        return "0.60_hat"
    if "0.5" in s or has_ist:
        if has_ist2:
            return "0.50_ist2"
        if has_ist:
            return "0.50_ist1"
        return "0.50_hat"
    if "0.4" in s:
        return "0.40_hat"
    return "0.72_hat"

def parse_design_factor(factor_str):
    """Returns (canonical_key, numeric_F) for a design factor string."""
    key = normalize_design_factor(factor_str)
    return key, DESIGN_FACTOR_MAP.get(key, 0.72)

def default_design_pressure_for_factor(f_factor: float) -> float:
    """Excel 'Design P F' mapping: 75 bar -> F=0.8, 82.5 -> F=0.72, 100 -> F=0.6/0.5/0.4."""
    if f_factor >= 0.80:
        return 75.0
    if f_factor >= 0.72:
        return 82.5
    return 100.0

def compute_api5l_tolerances(d_mm: float, t_mm: float, manufacturing_process: str = "SAWH") -> dict:
    """
    API 5L 47th Ed. Table 10 — Tolerances for Diameter and Out-of-roundness
    (SMLS vs Welded distinguished; caps applied: body welded max ±3.2 mm and
     ±0.005D max ±4.0 mm; end welded ±0.005D max ±1.6 mm / ±1.6 mm).

    Returns {'end_max','end_min','body_max','body_min','ovality_end','ovality_body'}.
    Out-of-roundness is limited to D/t <= 75 (otherwise "by agreement").
    """
    d = float(d_mm)
    t = float(t_mm) if t_mm else 14.3
    d_over_t = d / t if t > 0 else 999.0
    proc = (manufacturing_process or "").upper()
    is_smls = "SMLS" in proc or "SEAMLESS" in proc or "DIKISSIZ" in proc

    # --- Diameter tolerance ---
    if d < 60.3:
        body_max, body_min = d + 0.4, d - 0.8
        end_max, end_min = d + 0.4, d - 0.8
    elif d <= 168.3:
        body_max, body_min = d * 1.0075, d * 0.9925
        end_max, end_min = d + 1.6, d - 0.4
    elif d <= 610.0:
        if is_smls:
            body_max, body_min = d * 1.0075, d * 0.9925
        else:
            body_max, body_min = min(d * 1.0075, d + 3.2), max(d * 0.9925, d - 3.2)
        e = min(0.005 * d, 1.6)
        end_max, end_min = d + e, d - e
    elif d <= 1422.0:
        if is_smls:
            body_max, body_min = d * 1.01, d * 0.99
            end_max, end_min = d + 2.0, d - 2.0
        else:
            body_max, body_min = d + min(0.005 * d, 4.0), d - min(0.005 * d, 4.0)
            end_max, end_min = d + 1.6, d - 1.6
    else:  # D > 1422 mm — as agreed
        body_max = body_min = end_max = end_min = "Anlaşmaya bağlıdır."

    # --- Out-of-roundness (ovality), D/t <= 75 ---
    if d_over_t > 75.0:
        ovality_end = ovality_body = "Anlaşmaya bağlıdır."
    else:
        if d < 60.3:
            ovality_body, ovality_end = 1.2, 0.9
        elif d <= 610.0:
            ovality_body, ovality_end = 0.020 * d, 0.015 * d
        else:
            ovality_body = min(0.015 * d, 15.0)
            ovality_end = min(0.010 * d, 13.0)

    return {
        'end_max': round(end_max, 2) if isinstance(end_max, float) else end_max,
        'end_min': round(end_min, 2) if isinstance(end_min, float) else end_min,
        'body_max': round(body_max, 2) if isinstance(body_max, float) else body_max,
        'body_min': round(body_min, 2) if isinstance(body_min, float) else body_min,
        'ovality_end': round(ovality_end, 2) if isinstance(ovality_end, float) else ovality_end,
        'ovality_body': round(ovality_body, 2) if isinstance(ovality_body, float) else ovality_body,
    }

FRACTIONS_NORMALIZATION = {
    "1/2": "½", "½": "½", "0.5": "½",
    "3/4": "¾", "¾": "¾", "0.75": "¾",
    "1 1/4": "1¼", "1-1/4": "1¼", "1 1/4\"": "1¼", "1¼": "1¼", "1.25": "1¼",
    "1 1/2": "1½", "1-1/2": "1½", "1 1/2\"": "1½", "1½": "1½", "1.5": "1½",
    "2 1/2": "2½", "2-1/2": "2½", "2 1/2\"": "2½", "2½": "2½", "2.5": "2½",
    "3 1/2": "3½", "3-1/2": "3½", "3 1/2\"": "3½", "3½": "3½", "3.5": "3½"
}

def normalize_inch_str(s: str) -> str:
    cleaned = str(s).replace('\\', '').replace('"', '').replace("'", '').strip()
    return FRACTIONS_NORMALIZATION.get(cleaned, cleaned)

def get_pipe_size_by_inch(inch: str):
    inch_norm = normalize_inch_str(inch)
    for p in PIPE_SIZES_TABLE:
        p_norm = normalize_inch_str(p['inch'])
        if p_norm == inch_norm or p['inch'] == inch:
            return p
    # Try numeric conversion
    try:
        inch_float = float(inch_norm)
        for p in PIPE_SIZES_TABLE:
            try:
                p_float = float(normalize_inch_str(p['inch']))
                if abs(p_float - inch_float) < 0.05:
                    return p
            except (ValueError, TypeError):
                pass
    except (ValueError, TypeError):
        pass
    return None

def get_pipe_size_by_mm(mm: float, max_diff: float = 15.0):
    best_match = None
    min_diff = 999999
    for p in PIPE_SIZES_TABLE:
        diff = abs(p['mm'] - mm)
        if diff < min_diff:
            min_diff = diff
            best_match = p
    if min_diff > max_diff:
        return None
    return best_match

def get_botas_all_factors_for_diameter(diameter_inch: str):
    pipe_size = get_pipe_size_by_inch(diameter_inch)
    if not pipe_size:
        return []
    
    factors = [
        ('0,72 (Hat)', '0.72_hat', 75.0),
        ('0,6 (Hat)', '0.60_hat', 75.0),
        ('0,5 (Hat)', '0.50_hat', 75.0),
        ('0,5 (İstasyon - 75 Bar)', '0.50_ist1', 75.0),
        ('0,5 (İstasyon - 82,5 Bar)', '0.50_ist2', 82.5),
    ]
    
    d_mm = pipe_size['mm']
    if d_mm >= 406.4:
        default_proc = 'SAWH'
    elif d_mm >= 114.3:
        default_proc = 'ERW HFW'
    else:
        default_proc = 'SMLS'

    pipes = []
    seen_factors = set()
    for factor_label, factor_key, pressure_bar in factors:
        thk = pipe_size['botas_thk'].get(factor_key, 0.0)
        if thk > 0:
            # Check if this exact thk and factor was already added
            if (factor_label, thk) not in seen_factors:
                seen_factors.add((factor_label, thk))
                pipes.append({
                    'id': f"pipe_botas_{len(pipes)+1}_{int(d_mm)}_{int(thk*100)}",
                    'diameter_inch': pipe_size['inch'],
                    'diameter_mm': pipe_size['mm'],
                    'design_factor_str': factor_label,
                    'wall_thickness_mm': thk,
                    'manufacturing_process': default_proc,
                    'material_grade': pipe_size['default_material'],
                    'standard_type': 'BOTAŞ',
                    'design_pressure_bar': pressure_bar
                })
    return pipes
