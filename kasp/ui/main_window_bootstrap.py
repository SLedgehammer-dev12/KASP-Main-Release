"""Bootstrap helpers for initializing the KASP main window."""

from __future__ import annotations


def build_gas_component_maps():
    coolprop_gas_map = {
        "METHANE": "Methane (CH₄)",
        "ETHANE": "Ethane (C₂H₆)",
        "PROPANE": "Propane (C₃H₈)",
        "ISOBUTANE": "Isobutane (i-C₄H₁₀)",
        "BUTANE": "n-Butane (n-C₄H₁₀)",
        "ISOPENTANE": "Isopentane (i-C₅H₁₂)",
        "PENTANE": "n-Pentane (n-C₅H₁₂)",
        "HEXANE": "n-Hexane (C₆H₁₄)",
        "HEPTANE": "n-Heptane (C₇H₁₆)",
        "OCTANE": "n-Octane (C₈H₁₈)",
        "NONANE": "n-Nonane (C₉H₂₀)",
        "DECANE": "n-Decane (C₁₀H₂₂)",
        "HYDROGEN": "Hydrogen (H₂)",
        "NITROGEN": "Nitrogen (N₂)",
        "OXYGEN": "Oxygen (O₂)",
        "CARBONDIOXIDE": "Carbon Dioxide (CO₂)",
        "WATER": "Water (H₂O)",
        "HYDROGENSULFIDE": "Hydrogen Sulfide (H₂S)",
        "AIR": "Air",
    }
    common_components_display = sorted(coolprop_gas_map.values())
    display_to_coolprop_key = {value: key for key, value in coolprop_gas_map.items()}
    return coolprop_gas_map, common_components_display, display_to_coolprop_key


def initialize_window_state(window):
    window.last_design_inputs = None
    window.last_design_results_raw = None
    window.last_selected_units = None
    window.last_perf_inputs = None
    window.last_perf_results = None
    window.last_report_data = {}
    window.worker_thread = None
    window.worker = None


def bootstrap_main_window_foundation(window):
    from kasp.data.database import UnitDatabase
    from kasp.core.thermo import ThermoEngine
    from kasp.utils.graphs import GraphManager
    from kasp.utils.project_manager import ProjectManager

    window.db = UnitDatabase()
    window.engine = ThermoEngine()
    window.project_manager = ProjectManager()
    window.graph_manager = GraphManager(window.engine)
    (
        window.COOLPROP_GAS_MAP,
        window.COMMON_COMPONENTS_DISPLAY,
        window.DISPLAY_TO_COOLPROP_KEY,
    ) = build_gas_component_maps()
    initialize_window_state(window)


def bootstrap_main_window_workflows(window, *, reportlab_loaded, thermo_loaded):
    from kasp.ui.design_calculation_workflow import DesignCalculationController
    from kasp.ui.design_input_binding import DesignInputBinder
    from kasp.ui.design_results_workflow import DesignResultsPresenter
    from kasp.ui.document_workflows import DocumentWorkflowController
    from kasp.ui.gas_composition_workflow import GasCompositionController
    from kasp.ui.graph_workflow import GraphWorkflowController
    from kasp.ui.performance_workflow import PerformanceEvaluationController
    from kasp.ui.window_actions_workflow import WindowActionController

    window.design_calculation_workflow = DesignCalculationController(
        window,
        engine=window.engine,
        db=window.db,
    )
    window.gas_composition_workflow = GasCompositionController(window)
    window.design_input_binder = DesignInputBinder(window, thermo_loaded=thermo_loaded)
    window.design_results_presenter = DesignResultsPresenter(
        window,
        engine=window.engine,
        graph_manager=window.graph_manager,
    )
    window.graph_workflow = GraphWorkflowController(window, graph_manager=window.graph_manager)
    window.window_actions = WindowActionController(window, engine=window.engine)
    window.document_workflow = DocumentWorkflowController(
        window,
        engine=window.engine,
        project_manager=window.project_manager,
        reportlab_loaded=reportlab_loaded,
    )
    window.performance_workflow = PerformanceEvaluationController(window, engine=window.engine)
