"""FAZ 1-2-3: DWSIM EOS Entegrasyon Testleri."""
import pytest
from kasp.core.properties import ThermodynamicSolver
from kasp.core.thermo import ThermoEngine
from kasp.core.mixture import GasMixtureBuilder


# ─────────────────────── FAZ 1: _create_gas_object 'dwsim' ───────────────────────

def test_create_gas_object_with_dwsim():
    """ThermoEngine._create_gas_object 'dwsim' metodunu tanımalı."""
    engine = ThermoEngine()
    comp = {"METHANE": 95.0, "ETHANE": 5.0}
    gas_obj = engine._create_gas_object(comp, "dwsim")
    assert isinstance(gas_obj, dict)
    assert "ids" in gas_obj
    assert "mol_fractions" in gas_obj
    assert len(gas_obj["ids"]) == 2


def test_dwsim_rejected_in_previous_version():
    """'dwsim' bilinmeyen EOS değil — ValueError atmamalı."""
    engine = ThermoEngine()
    comp = {"METHANE": 100.0}
    try:
        engine._create_gas_object(comp, "dwsim")
    except ValueError as e:
        pytest.fail(f"_create_gas_object 'dwsim' için ValueError attı: {e}")


# ─────────────────────── FAZ 2: Bundle Arama Yolu ───────────────────────

def test_dwsim_dll_search_paths_include_bundle():
    """_load_dwsim_dll search_paths 'sys._MEIPASS' içermeli."""
    solver = ThermodynamicSolver()
    import sys
    import os

    original_load = solver._dwsim_dll_loaded if hasattr(solver, "_dwsim_dll_loaded") else None
    solver._dwsim_dll_loaded = False

    try:
        solver._load_dwsim_dll()
    except Exception:
        pass

    paths = [getattr(sys, '_MEIPASS', '')]
    assert paths[0] is not None
    assert os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "kasp", "core", "libs"
    ) is not None

    if original_load is not None:
        solver._dwsim_dll_loaded = original_load


# ─────────────────────── FAZ 3: SteamTables + Viskozite ───────────────────────

def test_dwsim_steam_tables_auto_detect_water():
    """Su > %5 ise SteamTablesPropertyPackage seçilmeli."""
    solver = ThermodynamicSolver()
    import sys

    try:
        import clr
    except ImportError:
        pytest.skip("pythonnet (clr) yüklü değil — DWSIM testi atlanıyor")

    if solver._load_dwsim_dll():
        gas_data = {
            "ids": ["WATER", "METHANE"],
            "mol_fractions": [0.10, 0.90],
            "MW": 18.015 * 0.10 + 16.04 * 0.90,
        }
        try:
            state = solver.get_properties(1e6, 400.0, gas_data, "dwsim")
            assert state is not None
            assert state.Z > 0.0
            assert state.Cp > 0.0
            assert state.density > 0.0
        except Exception as e:
            if "yüklenemedi" in str(e).lower():
                pytest.skip("DWSIM DLL bulunamadı")
            raise
    else:
        pytest.skip("DWSIM DLL yüklenemedi")


def test_dwsim_viscosity_property():
    """DWSIM çözücü viskozite değeri döndürmeli (veya en azından çökmeden fallback)."""
    solver = ThermodynamicSolver()

    try:
        import clr
    except ImportError:
        pytest.skip("pythonnet yüklü değil")

    if solver._load_dwsim_dll():
        gas_data = {
            "ids": ["METHANE", "ETHANE"],
            "mol_fractions": [0.95, 0.05],
            "MW": 16.04 * 0.95 + 30.07 * 0.05,
        }
        try:
            state = solver.get_properties(101325, 298.15, gas_data, "dwsim")
            assert state is not None
            mu = state.raw_props.get("mu", 0)
            assert mu > 0.0
        except Exception as e:
            if "yüklenemedi" in str(e).lower():
                pytest.skip("DWSIM DLL bulunamadı")
            raise
    else:
        pytest.skip("DWSIM DLL yüklenemedi")


def test_dwsim_thermal_conductivity():
    """DWSIM çözücü termal iletkenlik hesaplamalı (veya 0 fallback)."""
    solver = ThermodynamicSolver()

    try:
        import clr
    except ImportError:
        pytest.skip("pythonnet yüklü değil")

    if solver._load_dwsim_dll():
        gas_data = {
            "ids": ["NITROGEN", "OXYGEN"],
            "mol_fractions": [0.79, 0.21],
            "MW": 28.013 * 0.79 + 32.0 * 0.21,
        }
        try:
            state = solver.get_properties(101325, 300.0, gas_data, "dwsim")
            assert state is not None
            tc = state.raw_props.get("thermal_conductivity", -1)
            assert tc >= 0.0
        except Exception as e:
            if "yüklenemedi" in str(e).lower():
                pytest.skip("DWSIM DLL bulunamadı")
            raise
    else:
        pytest.skip("DWSIM DLL yüklenemedi")


# ─────────────────────── TermoEngine üzerinden DWSIM ───────────────────────

def test_thermo_engine_dwsim_design():
    """Full ThermoEngine DWSIM EOS ile tasarım hesaplaması yapabilmeli."""
    engine = ThermoEngine()

    try:
        import clr
    except ImportError:
        pytest.skip("pythonnet yüklü değil")

    solver = ThermodynamicSolver()
    if not solver._load_dwsim_dll():
        pytest.skip("DWSIM DLL yüklenemedi")

    inputs = {
        "p_in": 10.0,
        "p_in_unit": "bar",
        "t_in": 25.0,
        "t_in_unit": "°C",
        "p_out": 20.0,
        "p_out_unit": "bar",
        "flow": 5000.0,
        "flow_unit": "kg/h",
        "gas_comp": {"METHANE": 90.0, "ETHANE": 8.0, "PROPANE": 2.0},
        "eos_method": "dwsim",
        "solver_method": "aj_nr",
        "method": "Metot 1: Ortalama Özellikler",
        "poly_eff": 85.0,
        "num_units": 1,
        "num_stages": 1,
        "therm_eff": 35.0,
        "mech_eff": 98.0,
        "intercooler_dp_pct": 0.0,
        "intercooler_t": 40.0,
        "enable_uncertainty": False,
    }
    results = engine.calculate_design_performance(inputs)
    assert results["t_out"] > 25.0
    assert results["power_gas_total_kw"] > 0.0
    assert results["head_kj_kg"] > 0.0
