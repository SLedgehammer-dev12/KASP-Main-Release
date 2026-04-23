from types import SimpleNamespace

import pytest

from kasp.core.thermo_design_orchestration import ThermoDesignOrchestrator


class DummyLogger:
    def __init__(self):
        self.messages = []

    def info(self, message):
        self.messages.append(("info", message))


class DummySolver:
    def get_properties(self, pressure, temperature, gas_obj, eos):
        return SimpleNamespace(
            P=pressure,
            T=temperature,
            H=temperature * 1000.0,
            MW=20.0,
            density=2.0,
            k=1.3,
            Z=0.95,
        )


def average_method(p_in, t_in, p_out, poly_eff, gas_obj, eos, max_iter, tolerance):
    return t_in + 10.0, 100.0, 0.95, {"method": "avg"}


def endpoint_method(p_in, t_in, p_out, poly_eff, gas_obj, eos, max_iter, tolerance):
    return t_in + 20.0, 120.0, 0.94, {"method": "endpoint"}


def incremental_method(p_in, t_in, p_out, poly_eff, gas_obj, eos, step_count):
    return t_in + 30.0, 140.0, 0.93, {"method": "incremental", "steps": step_count}


def direct_hs_method(p_in, t_in, p_out, poly_eff, gas_obj, eos):
    return t_in + 40.0, 160.0, 0.92, {"method": "direct_hs"}


def test_design_orchestrator_runs_average_method_and_accumulates_stage_outputs():
    orchestrator = ThermoDesignOrchestrator(thermo_solver=DummySolver(), logger=DummyLogger())

    result = orchestrator.run_stage_loop(
        p_in_pa=100000.0,
        t_in_k=300.0,
        p_out_pa=400000.0,
        stage_pr=2.0,
        num_stages=2,
        intercooler_dp=0.01,
        ic_t_k=310.0,
        method_key="average",
        poly_eff_tgt=0.8,
        gas_obj={"gas": "x"},
        eos="coolprop",
        max_iter=50,
        tolerance=0.01,
        step_count=8,
        mass_flow_per_unit=10.0,
        method_average_fn=average_method,
        method_endpoint_fn=endpoint_method,
        method_incremental_fn=incremental_method,
        method_direct_hs_fn=direct_hs_method,
    )

    assert result["final_t_out_k"] == 320.0
    assert result["total_stage_gas_power_kw"] == pytest.approx(2500.0)
    assert result["total_poly_head_kj_kg"] == pytest.approx(200.0)
    assert len(result["staged_results"]) == 2
    assert result["staged_results"][0]["method_history"]["method"] == "avg"


def test_design_orchestrator_selects_incremental_and_direct_hs_callbacks():
    orchestrator = ThermoDesignOrchestrator(thermo_solver=DummySolver(), logger=DummyLogger())

    incremental_result = orchestrator.run_stage_loop(
        p_in_pa=100000.0,
        t_in_k=300.0,
        p_out_pa=200000.0,
        stage_pr=2.0,
        num_stages=1,
        intercooler_dp=0.0,
        ic_t_k=300.0,
        method_key="incremental",
        poly_eff_tgt=0.8,
        gas_obj={"gas": "x"},
        eos="coolprop",
        max_iter=50,
        tolerance=0.01,
        step_count=6,
        mass_flow_per_unit=10.0,
        method_average_fn=average_method,
        method_endpoint_fn=endpoint_method,
        method_incremental_fn=incremental_method,
        method_direct_hs_fn=direct_hs_method,
    )
    direct_result = orchestrator.run_stage_loop(
        p_in_pa=100000.0,
        t_in_k=300.0,
        p_out_pa=200000.0,
        stage_pr=2.0,
        num_stages=1,
        intercooler_dp=0.0,
        ic_t_k=300.0,
        method_key="direct_hs",
        poly_eff_tgt=0.8,
        gas_obj={"gas": "x"},
        eos="coolprop",
        max_iter=50,
        tolerance=0.01,
        step_count=6,
        mass_flow_per_unit=10.0,
        method_average_fn=average_method,
        method_endpoint_fn=endpoint_method,
        method_incremental_fn=incremental_method,
        method_direct_hs_fn=direct_hs_method,
    )

    assert incremental_result["staged_results"][0]["method_history"]["method"] == "incremental"
    assert incremental_result["staged_results"][0]["method_history"]["steps"] == 6
    assert direct_result["staged_results"][0]["method_history"]["method"] == "direct_hs"
