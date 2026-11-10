import pytest
from kasp.ui.design_input_binding import (
    eos_method_from_ui_text,
    solver_method_from_ui_text,
    lhv_source_from_ui_text,
)


def test_eos_method_handles_none_and_empty():
    """eos_method_from_ui_text must not raise TypeError on None or empty string."""
    method, err = eos_method_from_ui_text(None)
    assert method == "coolprop"
    assert err is None

    method_empty, err_empty = eos_method_from_ui_text("")
    assert method_empty == "coolprop"
    assert err_empty is None


def test_eos_method_case_insensitive_matching():
    """Case variants like 'gerg-2008 (iso 20765-2)' or 'coolprop (heos)' must match accurately."""
    method, err = eos_method_from_ui_text("gerg-2008 (iso 20765-2)")
    assert method == "gerg2008"
    assert err is None

    method_cp, err_cp = eos_method_from_ui_text("coolprop (heos / refprop)")
    assert method_cp == "coolprop"
    assert err_cp is None

    method_aga, err_aga = eos_method_from_ui_text("aga8-dc92 boru gazi")
    assert method_aga == "aga8"
    assert err_aga is None

    method_pr, err_pr = eos_method_from_ui_text("peng-robinson (pr)")
    assert method_pr == "pr"
    assert err_pr is None


def test_solver_method_and_lhv_source_handles_none():
    """solver_method_from_ui_text and lhv_source_from_ui_text must safely handle None without crashing."""
    assert solver_method_from_ui_text(None) == "auto"
    assert solver_method_from_ui_text("benchmark solver") == "benchmark"
    assert solver_method_from_ui_text("aj-nr jacobian") == "aj_nr"

    assert lhv_source_from_ui_text(None) == "kasp"
    assert lhv_source_from_ui_text("thermo library") == "thermo"
    assert lhv_source_from_ui_text("iso 6976 standard") == "iso6976"
