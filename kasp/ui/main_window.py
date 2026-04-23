import sys
import os
import logging
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QPushButton, QLineEdit, QTextEdit, QComboBox, 
                             QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox, 
                             QFormLayout, QGridLayout, QMessageBox, 
                             QProgressBar, QSlider, QSpinBox, QDoubleSpinBox, QCheckBox,
                             QRadioButton, QButtonGroup)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QIcon

try:
    import matplotlib.pyplot as plt
    MATPLOTLIB_LOADED = True
except ImportError:
    MATPLOTLIB_LOADED = False

try:
    from reportlab.pdfgen import canvas
    REPORTLAB_LOADED = True
except ImportError:
    REPORTLAB_LOADED = False

try:
    import CoolProp.CoolProp as CP
    COOLPROP_LOADED = True
except ImportError:
    COOLPROP_LOADED = False

try:
    import thermo
    THERMO_LOADED = True
except ImportError:
    THERMO_LOADED = False

from kasp.utils.logging_handler import QLogHandler, setup_logging
from kasp.ui.design_left_panel_builders import build_design_left_groups
from kasp.ui.design_results_workflow import DesignResultsPresenter
from kasp.ui.design_results_tab_builders import (
    build_basic_results_tab,
    build_detailed_results_tab,
    build_graphs_tab,
    build_turbine_selection_tab,
)
from kasp.ui.main_window_bootstrap import (
    bootstrap_main_window_foundation,
    bootstrap_main_window_workflows,
)
from kasp.ui.main_window_auxiliary import MainWindowAuxiliaryController
from kasp.ui.main_window_input_helpers import MainWindowInputController
from kasp.ui.main_window_signal_wiring import MainWindowSignalController
from kasp.ui.main_window_startup import MainWindowStartupController
from kasp.ui.main_window_structure_builders import build_main_menu, build_main_tabs
from kasp.ui.design_tab_shell_builders import build_design_tab_shell
from kasp.ui.tab_builders import build_log_tab, build_performance_tab
from kasp.i18n import APP_VERSION, apply_window_language, get_language

# Task 2: Validation system (additive - preserves all existing functionality)
try:
    from kasp.ui.validators import (
        ValidatedLineEdit,
        ValidationManager, 
        validate_pressure,
        validate_temperature,
        validate_flow
    )
    from kasp.ui.validation_status import ValidationStatusWidget
    VALIDATION_AVAILABLE = True
except ImportError:
    # Fallback if validation modules not available
    VALIDATION_AVAILABLE = False
    
    class ValidatedLineEdit(QLineEdit):
        """Fallback class that behaves like QLineEdit but accepts validation_func"""
        def __init__(self, validation_func=None, parent=None):
            super().__init__(parent)
            self.validation_changed = pyqtSignal(bool, str) # Dummy signal
            
        def set_validation_context(self, context):
            pass
            
    # Dummy validation functions
    def validate_pressure(*args): return True, ""
    def validate_temperature(*args): return True, ""
    def validate_flow(*args): return True, ""
    
    class ValidationManager:
        def register_input(self, *args): pass
        def all_inputs_valid(self): return True
        def get_invalid_fields(self): return []
        
    class ValidationStatusWidget(QWidget):
        def update_validation_status(self, *args): pass
        def add_custom_status(self, *args, **kwargs): pass

class KaspMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Logging setup
        self.log_handler = QLogHandler(self)
        setup_logging(self.log_handler)
        self.logger = logging.getLogger(self.__class__.__name__)

        # Matplotlib style
        if MATPLOTLIB_LOADED:
            plt.style.use('seaborn-v0_8-darkgrid')
        
        bootstrap_main_window_foundation(self)
        
        # Central widget setup
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        
        # Validation manager
        if VALIDATION_AVAILABLE:
            self.validation_manager = ValidationManager()
        else:
            self.validation_manager = None
        self.window_auxiliary = MainWindowAuxiliaryController(self)
        self.window_input = MainWindowInputController(self)
        self.window_startup = MainWindowStartupController(self)
        self.window_startup.configure_window()
        self.language = get_language()
        
        # CRITICAL FIX: Initialize all UI components
        self._initialize_ui()
        apply_window_language(self)
        bootstrap_main_window_workflows(
            self,
            reportlab_loaded=REPORTLAB_LOADED,
            thermo_loaded=THERMO_LOADED,
        )
        
        self.logger.info("KASP v%s UI initialized (language=%s)", APP_VERSION, self.language)
        
        # SÃ¼rÃ¼m notlarÄ±nÄ± gÃ¶ster (Ayarlara baÄŸlÄ±)
        self._show_changelog_if_needed()

    def _show_changelog_if_needed(self):
        self.window_startup.show_changelog_if_needed()

    def _initialize_ui(self):
        """UI bileÅŸenlerini baÅŸlatÄ±r"""
        self.window_startup.initialize_ui()

    # ------------------------------------------------------------------ #
    # V4.6: Status Bar with Validation Indicator                          #
    # ------------------------------------------------------------------ #
    def _setup_status_bar(self):
        """Alt status bar'a doÄŸrulama gÃ¶stergesi ekler."""
        self.window_auxiliary.setup_status_bar(validation_available=VALIDATION_AVAILABLE)

    def _update_status_bar_validation(self, *args):
        """Status bar doÄŸrulama gÃ¶stergesini gÃ¼nceller."""
        self.window_auxiliary.update_status_bar_validation(*args)

    def _show_validation_popup(self):
        """GeÃ§ersiz alanlar varsa pop-up uyarÄ± gÃ¶sterir.
        
        Returns:
            bool: True if all inputs valid (proceed with calc), False to abort.
        """
        return self.window_auxiliary.show_validation_popup()

    def _create_menu(self):
        """MenÃ¼ Ã§ubuÄŸu oluÅŸturur"""
        build_main_menu(self)

    def _create_tabs(self):
        """Ana sekme yapÄ±sÄ±nÄ± oluÅŸturur"""
        build_main_tabs(self)

    def _setup_design_tab(self):
        """TasarÄ±m sekmesi kurulumu â€” V4.6: Sol panel QScrollArea iÃ§inde."""
        left_layout = build_design_tab_shell(self)
        build_design_left_groups(
            self,
            left_layout,
            line_edit_cls=ValidatedLineEdit,
            validation_manager=self.validation_manager,
            validate_pressure=validate_pressure,
            validate_temperature=validate_temperature,
            validate_flow=validate_flow,
            validation_available=VALIDATION_AVAILABLE,
            coolprop_loaded=COOLPROP_LOADED,
            thermo_loaded=THERMO_LOADED,
        )

    def _setup_performance_tab(self):
        """Performans sekmesi kurulumu"""
        build_performance_tab(self, thermo_loaded=THERMO_LOADED)

    def _toggle_perf_driver_inputs(self):
        """TÃ¼rbin verimi veya yakÄ±t tÃ¼ketimi giriÅŸini karÅŸÄ±lÄ±klÄ± aÃ§/kapa"""
        self.performance_workflow.toggle_driver_inputs()

    def _setup_log_tab(self):
        """Log sekmesi kurulumu - Seviye filtreleme ile"""
        build_log_tab(self)


    def _connect_signals(self):
        """Sinyal baÄŸlantÄ±larÄ±nÄ± kur"""
        MainWindowSignalController(self).connect_signals()

    def _populate_unit_combos(self):
        """Birim combobox'larÄ±nÄ± doldur"""
        self.window_auxiliary.populate_unit_combos()

    def _setup_unit_tooltips(self):
        self.window_input.setup_unit_tooltips()

    def _update_method_options(self):
        self.window_input.update_method_options()

    def _update_button_state(self):
        self.window_input.update_button_state()

    def setup_basic_results_tab(self):
        """Temel sonuÃ§lar sekmesi kurulumu - SatÄ±r iÃ§i birim seÃ§iciler"""
        build_basic_results_tab(self)


    def setup_turbine_selection_tab(self):
        """TÃ¼rbin seÃ§imi sekmesi kurulumu"""
        build_turbine_selection_tab(self)

    def setup_detailed_results_tab(self):
        """DetaylÄ± sonuÃ§lar sekmesi kurulumu"""
        build_detailed_results_tab(self)

    def setup_graphs_tab(self):
        """Grafikler sekmesi kurulumu"""
        build_graphs_tab(self)

    def on_gas_selection_changed(self, gas_name):
        """Gaz seÃ§imi deÄŸiÅŸtiÄŸinde"""
        self.gas_composition_workflow.on_gas_selection_changed(gas_name)

    def load_standard_gas_composition(self, gas_name):
        """Standart gaz kompozisyonunu yÃ¼kle"""
        self.gas_composition_workflow.load_standard_gas_composition(gas_name)

    def add_component_row(self):
        """BileÅŸen satÄ±rÄ± ekle"""
        self.gas_composition_workflow.add_component_row()

    def remove_component_row(self):
        """BileÅŸen satÄ±rÄ± sil"""
        self.gas_composition_workflow.remove_component_row()

    def _update_composition_total_label(self, *_args):
        """Gaz kompozisyon toplamÄ±nÄ± hesaplar ve canlÄ± etiketi gÃ¼nceller."""
        self.gas_composition_workflow.update_total_label(*_args)

    def normalize_composition(self):
        """Kompozisyonu normalize et â€” toplam %100'e gÃ¶re her satÄ±rÄ± Ã¶lÃ§ekler."""
        self.gas_composition_workflow.normalize_composition()

    def _get_gas_composition(self):
        """Gaz kompozisyon tablosundan bileÅŸen adÄ± â†’ yÃ¼zde sÃ¶zlÃ¼ÄŸÃ¼ dÃ¶ndÃ¼rÃ¼r.
        
        Hem TasarÄ±m hem de Performans sekmelerinde ortak kullanÄ±lÄ±r.
        """
        return self.gas_composition_workflow.get_gas_composition()

    def _get_design_inputs(self):
        """UI'dan tÃ¼m kullanÄ±cÄ± girdilerini okur"""
        return self.window_input.get_design_inputs()

    def run_calculation(self):
        """TasarÄ±m hesaplamasÄ±nÄ± baÅŸlatÄ±r"""
        self.design_calculation_workflow.run()

    def calculation_finished(self, results_raw, selected_units):
        """Hesaplama tamamlandÄ±ÄŸÄ±nda sonuÃ§larÄ± iÅŸler"""
        self.design_calculation_workflow.calculation_finished(results_raw, selected_units)

    def calculation_error(self, error_message):
        """Hesaplama hatasÄ± oluÅŸtuÄŸunda"""
        self.design_calculation_workflow.calculation_error(error_message)
    
    def stop_calculation(self):
        """HesaplamayÄ± durdurur - Task 4: Graceful cancellation"""
        self.design_calculation_workflow.stop()
    
    # Task 4: New handler methods for enhanced progress tracking
    def update_progress_detailed(self, percentage, message):
        """Update progress bar and status message"""
        self.design_calculation_workflow.update_progress_detailed(percentage, message)
    
    def update_time_estimate(self, seconds):
        """Update estimated time remaining"""
        self.design_calculation_workflow.update_time_estimate(seconds)
    
    def calculation_cancelled(self):
        """Handle calculation cancellation"""
        self.design_calculation_workflow.calculation_cancelled()

    def _update_results_ui(self, results, selected_units):
        """Sonuclari arayuze yansitir - Satir ici birimlerle"""
        self.design_results_presenter.apply_results(results, selected_units)

    def _update_single_result_unit(self, key, new_unit):
        """Tek bir sonucun birimini degistirir"""
        self.design_results_presenter.update_single_result_unit(key, new_unit)

    def _populate_turbine_table(self, selected_units):
        """Turbin secim tablosunu doldurur"""
        self.design_results_presenter.populate_turbine_table(selected_units)

    @staticmethod
    def _get_selected_unit_value(unit, *keys, default=None):
        return DesignResultsPresenter.get_selected_unit_value(unit, *keys, default=default)

    def _serialize_selected_units(self, selected_units):
        return self.design_results_presenter.serialize_selected_units(selected_units)

    def _populate_detailed_tables(self, results):
        """Detayli sonuc tablolarini doldurur"""
        self.design_results_presenter.populate_detailed_tables(results)

    def on_turbine_selection_changed(self):
        """Turbin tablosunda secim degistiginde detaylari gosterir"""
        self.design_results_presenter.apply_selected_turbine_selection(
            self.turbine_table.selectedItems(),
            self.last_selected_units,
        )

    def refresh_current_graph(self):
        """Secili grafigi yeniler"""
        self.design_results_presenter.refresh_current_graph()

    def save_current_graph(self):
        """Mevcut grafiÄŸi dosyaya kaydeder"""
        self.graph_workflow.save_current_graph()

    def handle_design_report(self):
        """TasarÄ±m raporu oluÅŸturmayÄ± yÃ¶netir"""
        self.document_workflow.handle_design_report()

    def export_results(self):
        """SonuÃ§larÄ± JSON olarak dÄ±ÅŸa aktarÄ±r"""
        self.document_workflow.export_results()

    def handle_performance_report(self):
        """Performans raporu oluÅŸturmayÄ± yÃ¶netir"""
        self.document_workflow.handle_performance_report()

    def open_library_manager(self):
        """KÃ¼tÃ¼phane yÃ¶neticisini aÃ§ar"""
        self.window_actions.open_library_manager()
        
    def clear_engine_cache(self):
        """Motor Ã¶nbelleÄŸini temizler"""
        self.window_actions.clear_engine_cache()

    def show_about_dialog(self):
        """HakkÄ±nda penceresini gÃ¶sterir"""
        self.window_actions.show_about_dialog()
        
    def show_examples(self):
        """Ã–rnekleri gÃ¶sterir"""
        self.window_actions.show_examples()

    def clear_logs(self):
        """LoglarÄ± temizler"""
        self.window_actions.clear_logs()
        
    def append_log(self, msg):
        """Log mesaj

Ä±nÄ± arayÃ¼ze ekler - Filtreleme ile"""
        self.window_actions.append_log(msg)
    
    def _filter_logs(self, selected_level):
        """Log seviyesine gÃ¶re filtreleme yapar"""
        self.window_actions.filter_logs(selected_level)


    def run_performance_evaluation(self):
        """Mevcut saha verilerine dayanarak (T2 bilinen) performansÄ± hesaplar"""
        self.performance_workflow.run_evaluation()


    # Phase 5: Project Save/Load Methods
    
    def new_project(self):
        """Yeni proje oluÅŸturur - tÃ¼m alanlarÄ± temizler"""
        self.document_workflow.new_project()
    
    def save_project(self):
        """Projeyi kaydet - tÃ¼m kullanÄ±cÄ± girdilerini JSON olarak"""
        self.document_workflow.save_project()
    
    def load_project(self):
        """Proje yÃ¼kle - JSON dosyasÄ±ndan UI'yi doldur"""
        self.document_workflow.load_project()
    
    def _populate_ui_from_inputs(self, inputs):
        """YÃ¼klenen projeyi UI'ye yerleÅŸtir"""
        self.window_startup.populate_ui_from_inputs(inputs)

    def center_on_screen(self):
        """Center the window on the screen"""
        self.window_auxiliary.center_on_screen()
