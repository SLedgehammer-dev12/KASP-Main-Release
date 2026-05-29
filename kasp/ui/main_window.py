import sys
import os
import json
import datetime
import logging
import threading
from release_metadata import APP_VERSION, RELEASES_API_URL, RELEASE_TAG
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, 
                             QLabel, QPushButton, QLineEdit, QTextEdit, QComboBox, 
                             QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox, 
                             QFormLayout, QGridLayout, QFileDialog, QMessageBox, 
                             QProgressBar, QProgressDialog, QSlider, QSpinBox, QDoubleSpinBox, QCheckBox, QAction,
                             QScrollArea, QSizePolicy, QRadioButton, QButtonGroup)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QIcon, QDoubleValidator

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

from kasp.core.thermo import ThermoEngine
from kasp.data.database import UnitDatabase
from kasp.utils.graphs import GraphManager
from kasp.utils.logging_handler import QLogHandler, setup_logging
from kasp.utils.workers import CalculationWorker
from kasp.utils.reporting import ReportGenerator
from kasp.utils.project_manager import ProjectManager
from kasp.utils.updater import (
    GitHubReleaseClient,
    default_download_filename,
    ReleaseCheckWorker,
    ReleaseDownloadWorker,
    unseen_releases,
)
from kasp.ui.dialogs import ChangelogDialog, UpdateDialog
from kasp.ui.library_manager import LibraryManagerWindow

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
        
        # Window properties
        from kasp.ui.responsive import scaled_px
        self.setMinimumSize(scaled_px(900), scaled_px(550))
        self.setWindowTitle(f"KASP v{APP_VERSION} - Termodinamik Analiz")
        self.setWindowFlags(
            Qt.Window | 
            Qt.WindowTitleHint | 
            Qt.WindowCloseButtonHint | 
            Qt.WindowMinimizeButtonHint | 
            Qt.WindowMaximizeButtonHint
        )
        # V4.6: Responsive geometry — fit window to available screen space
        try:
            from kasp.ui.responsive import compute_initial_window_size
            _w, _h = compute_initial_window_size(1700, 950)
            self.setGeometry(50, 50, _w, _h)
        except Exception:
            self.setGeometry(50, 50, 1700, 950)
        
        # Center window
        self.center_on_screen()
        
        # Logging setup
        self.log_handler = QLogHandler()
        setup_logging(self.log_handler)
        self.logger = logging.getLogger(self.__class__.__name__)

        # Matplotlib style
        if MATPLOTLIB_LOADED:
            plt.style.use('seaborn-v0_8-darkgrid')
        
        # Initialize core components
        self.db = UnitDatabase()
        self.engine = ThermoEngine()
        self.project_manager = ProjectManager()
        self.graph_manager = GraphManager(self.engine)
        
        # Gas component mapping
        self.COOLPROP_GAS_MAP = {
            "METHANE": "Methane (CH₄)", "ETHANE": "Ethane (C₂H₆)", "PROPANE": "Propane (C₃H₈)",
            "ISOBUTANE": "Isobutane (i-C₄H₁₀)", "BUTANE": "n-Butane (n-C₄H₁₀)", 
            "ISOPENTANE": "Isopentane (i-C₅H₁₂)", "PENTANE": "n-Pentane (n-C₅H₁₂)",
            "HEXANE": "n-Hexane (C₆H₁₄)", "HEPTANE": "n-Heptane (C₇H₁₆)", "OCTANE": "n-Octane (C₈H₁₈)",
            "NONANE": "n-Nonane (C₉H₂₀)", "DECANE": "n-Decane (C₁₀H₂₂)", 
            "HYDROGEN": "Hydrogen (H₂)", "NITROGEN": "Nitrogen (N₂)", "OXYGEN": "Oxygen (O₂)",
            "CARBONDIOXIDE": "Carbon Dioxide (CO₂)", "WATER": "Water (H₂O)", 
            "HYDROGENSULFIDE": "Hydrogen Sulfide (H₂S)", "AIR": "Air"
        }
        self.COMMON_COMPONENTS_DISPLAY = sorted(self.COOLPROP_GAS_MAP.values())
        self.DISPLAY_TO_COOLPROP_KEY = {v: k for k, v in self.COOLPROP_GAS_MAP.items()}
        
        # Central widget setup
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        
        # State variables
        self.last_design_inputs = None
        self.last_design_results_raw = None
        self.last_selected_units = None
        self.last_perf_inputs = None
        self.last_perf_results = None
        self.last_report_data = {}
        self.worker_thread = None
        self.worker = None
        self.update_check_thread = None
        self.update_check_worker = None
        self.update_download_thread = None
        self.update_download_worker = None
        self.update_progress_dialog = None
        self.last_release_catalog = []
        
        # Validation manager
        if VALIDATION_AVAILABLE:
            self.validation_manager = ValidationManager()
        else:
            self.validation_manager = None
        
        from kasp.ui.design_calculation_workflow import DesignCalculationController
        from kasp.ui.design_input_binding import DesignInputBinder
        from kasp.ui.design_results_workflow import DesignResultsPresenter
        from kasp.ui.document_workflows import DocumentWorkflowController
        from kasp.ui.gas_composition_workflow import GasCompositionController
        from kasp.ui.graph_workflow import GraphWorkflowController
        from kasp.ui.performance_workflow import PerformanceEvaluationController
        from kasp.ui.window_actions_workflow import WindowActionController

        self.design_calculation_workflow = DesignCalculationController(
            self,
            engine=self.engine,
            db=self.db,
        )
        self.design_input_binder = DesignInputBinder(self, thermo_loaded=THERMO_LOADED)
        self.document_workflow = DocumentWorkflowController(
            self,
            engine=self.engine,
            project_manager=self.project_manager,
            reportlab_loaded=REPORTLAB_LOADED,
        )
        self.gas_composition_workflow = GasCompositionController(self)
        self.performance_workflow = PerformanceEvaluationController(self, engine=self.engine)
        self.window_actions = WindowActionController(self, engine=self.engine)

        # CRITICAL FIX: Initialize all UI components
        self._initialize_ui()

        # Oturum bilgisini pencere başlığına yansıt
        try:
            from kasp.security import Session
            user = Session.current_user()
            if user:
                title = f"KASP v{APP_VERSION} — {user.username} ({user.role})"
                self.setWindowTitle(title)
            self._update_admin_menu_visibility()
        except Exception:
            pass

        # Zorunlu şifre değiştirme
        self._check_must_change_password()

        self.design_results_presenter = DesignResultsPresenter(
            self,
            engine=self.engine,
            graph_manager=self.graph_manager,
        )
        self.graph_workflow = GraphWorkflowController(self, graph_manager=self.graph_manager)
        
        self.logger.info("KASP v%s arayuzu baslatildi", APP_VERSION)
        
        # Sürüm notlarını göster (Ayarlara bağlı)
        self._check_for_updates(manual=False)

    def _show_changelog_if_needed(self):
        try:
            if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
                return
            if os.environ.get("KASP_SKIP_CHANGELOG_DIALOG") == "1":
                return
            from kasp.config_manager import get_config_manager
            config = get_config_manager()
            skip_v46 = config.get('ui.skip_changelog_v46', False)
            if not skip_v46:
                from kasp.ui.dialogs import ChangelogDialog
                dialog = ChangelogDialog(self)
                dialog.exec_()
                if dialog.do_not_show_again:
                    config.set('ui.skip_changelog_v46', True)
        except Exception as e:
            self.logger.warning(f"Changelog dialog error: {e}")

    def closeEvent(self, event):
        self._save_splitter_state()
        self._cleanup_update_check_thread()
        self._cleanup_update_download_thread()
        root_logger = logging.getLogger()
        if getattr(self, "log_handler", None) is not None:
            try:
                root_logger.removeHandler(self.log_handler)
            except Exception:
                pass
            try:
                self.log_handler.close()
            except Exception:
                pass
        super().closeEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        try:
            from kasp.ui.responsive import is_small_screen
            if is_small_screen():
                self._compact_left_panel()
        except Exception:
            pass

    def _compact_left_panel(self):
        try:
            splitter = getattr(self, "design_splitter", None)
            if splitter and splitter.count() >= 2:
                sizes = splitter.sizes()
                total = sum(sizes) or 1
                if sizes[0] / total > 0.35:
                    splitter.setSizes([int(total * 0.25), int(total * 0.75)])
        except Exception:
            pass

    def _save_splitter_state(self):
        try:
            from PyQt5.QtCore import QSettings
            settings = QSettings("KASP", "WindowState")
            for attr in ("design_splitter", "performance_splitter"):
                splitter = getattr(self, attr, None)
                if splitter:
                    settings.setValue(f"splitter/{attr}", splitter.saveState())
        except Exception:
            pass

    def restore_splitter_state(self):
        try:
            from PyQt5.QtCore import QSettings
            settings = QSettings("KASP", "WindowState")
            for attr in ("design_splitter", "performance_splitter"):
                splitter = getattr(self, attr, None)
                if splitter:
                    state = settings.value(f"splitter/{attr}")
                    if state:
                        splitter.restoreState(state)
        except Exception:
            pass

    def _show_changelog_if_needed(self):
        if getattr(self, "last_release_catalog", None):
            self._maybe_show_release_notes(self.last_release_catalog)

    def _initialize_ui(self):
        """UI bileşenlerini başlatır"""
        self._create_menu()
        self._create_tabs()
        self._apply_tab_visibility()
        self._setup_design_tab()
        self._setup_performance_tab()
        self._setup_log_tab()
        self._setup_status_bar()
        self._connect_signals()
        self._populate_unit_combos()
        self._setup_unit_tooltips()
        self._update_method_options()
        self._update_button_state()
        self._apply_saved_theme()
        self._apply_saved_language()

    def _apply_saved_theme(self):
        try:
            from kasp.config_manager import get_config_manager
            from kasp.ui.theme_manager import ThemeManager
            theme = get_config_manager().get("app.theme", "light")
            ThemeManager.apply_theme(theme)
            self._update_theme_checkmarks(theme)
        except Exception:
            pass

    def _apply_saved_language(self):
        try:
            from kasp.config_manager import get_config_manager
            lang = get_config_manager().get("app.language", "tr")
            self._update_language_checkmarks(lang)
        except Exception:
            pass

    def switch_theme(self, theme_name):
        from kasp.config_manager import get_config_manager
        from kasp.ui.theme_manager import ThemeManager
        get_config_manager().set("app.theme", theme_name)
        ThemeManager.apply_theme(theme_name)
        self._update_theme_checkmarks(theme_name)
        try:
            self.refresh_current_graph()
        except Exception:
            pass

    def switch_language(self, lang):
        from kasp.config_manager import get_config_manager
        from kasp.i18n import set_language, refresh_all_windows
        set_language(lang)
        self.setWindowTitle(f"KASP v{APP_VERSION} - " + ("Termodinamik Analiz" if lang == "tr" else "Thermodynamic Analysis"))
        refresh_all_windows()
        self._update_language_checkmarks(lang)

    def _update_theme_checkmarks(self, theme_name):
        actions = getattr(self, "_theme_actions", {})
        for key, action in actions.items():
            action.setChecked(key == theme_name)

    def _update_language_checkmarks(self, lang):
        actions = getattr(self, "_language_actions", {})
        for key, action in actions.items():
            action.setChecked(key == lang)

    def _update_menu_checkmarks(self, lang):
        self._update_language_checkmarks(lang)

    # ------------------------------------------------------------------ #
    # V4.6: Status Bar with Validation Indicator                          #
    # ------------------------------------------------------------------ #
    def _setup_status_bar(self):
        from kasp.ui.main_window_auxiliary import MainWindowAuxiliaryController

        return MainWindowAuxiliaryController(self).setup_status_bar(
            validation_available=VALIDATION_AVAILABLE,
        )

    def _update_status_bar_validation(self, *args):
        from kasp.ui.main_window_auxiliary import MainWindowAuxiliaryController

        return MainWindowAuxiliaryController(self).update_status_bar_validation(*args)

    def _show_validation_popup(self):
        from kasp.ui.main_window_auxiliary import MainWindowAuxiliaryController

        return MainWindowAuxiliaryController(self).show_validation_popup()

    def _create_menu(self):
        from kasp.ui.main_window_structure_builders import build_main_menu

        return build_main_menu(self)

    def _create_tabs(self):
        from kasp.ui.main_window_structure_builders import build_main_tabs

        return build_main_tabs(self)

    def _setup_design_tab(self):
        from kasp.ui.design_left_panel_builders import build_design_left_groups
        from kasp.ui.design_tab_shell_builders import build_design_tab_shell

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
        from kasp.ui.tab_builders import build_performance_tab

        return build_performance_tab(self, thermo_loaded=THERMO_LOADED)

    def _toggle_perf_driver_inputs(self):
        """Türbin verimi veya yakıt tüketimi girişini karşılıklı aç/kapa"""
        return self.performance_workflow.toggle_driver_inputs()
        
    def _setup_log_tab(self):
        from kasp.ui.tab_builders import build_log_tab

        return build_log_tab(self)

    def _connect_signals(self):
        from kasp.ui.main_window_signal_wiring import MainWindowSignalController

        return MainWindowSignalController(self).connect_signals()

    def _populate_unit_combos(self):
        from kasp.ui.main_window_auxiliary import MainWindowAuxiliaryController

        return MainWindowAuxiliaryController(self).populate_unit_combos()

    def _setup_unit_tooltips(self):
        pass

    def _update_method_options(self):
        pass

    def _update_button_state(self):
        pass

    def setup_basic_results_tab(self):
        from kasp.ui.design_results_tab_builders import build_basic_results_tab

        return build_basic_results_tab(self)

    def setup_turbine_selection_tab(self):
        from kasp.ui.design_results_tab_builders import build_turbine_selection_tab

        return build_turbine_selection_tab(self)

    def setup_detailed_results_tab(self):
        from kasp.ui.design_results_tab_builders import build_detailed_results_tab

        return build_detailed_results_tab(self)

    def setup_graphs_tab(self):
        from kasp.ui.design_results_tab_builders import build_graphs_tab

        return build_graphs_tab(self)

    def _update_results_ui(self, results, selected_units):
        return self.design_results_presenter.apply_results(results, selected_units)

    def _update_single_result_unit(self, key, new_unit):
        return self.design_results_presenter.update_single_result_unit(key, new_unit)

    def _populate_turbine_table(self, selected_units):
        return self.design_results_presenter.populate_turbine_table(selected_units)

    def _populate_detailed_tables(self, results):
        return self.design_results_presenter.populate_detailed_tables(results)

    def on_turbine_selection_changed(self):
        return self.design_results_presenter.apply_selected_turbine_selection(
            self.turbine_table.selectedItems(),
            self.last_selected_units,
        )

    def refresh_current_graph(self):
        return self.design_results_presenter.refresh_current_graph()

    def on_graph_button_clicked(self, idx):
        bg = getattr(self, "graph_button_group", None)
        if bg:
            btn = bg.button(idx)
            if btn:
                self.design_results_presenter.refresh_current_graph(btn.text())

    def save_current_graph(self, fmt="png"):
        return self.graph_workflow.save_current_graph(fmt)

    def _serialize_selected_units(self, selected_units):
        return self.design_results_presenter.serialize_selected_units(selected_units)

    def _build_release_client(self):
        return GitHubReleaseClient(api_url=RELEASES_API_URL, timeout=8.0)

    def _cleanup_update_check_thread(self):
        if self.update_check_thread is not None:
            self.update_check_thread.quit()
            self.update_check_thread.wait(2000)
        self.update_check_thread = None
        self.update_check_worker = None

    def _cleanup_update_download_thread(self):
        if self.update_download_thread is not None:
            self.update_download_thread.quit()
            self.update_download_thread.wait(2000)
        self.update_download_thread = None
        self.update_download_worker = None
        self.update_progress_dialog = None

    def _check_for_updates(self, manual=True):
        if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
            return

        from kasp.config_manager import get_config_manager

        config = get_config_manager()
        if not manual and not config.get("updates.check_on_startup", True):
            return

        if self.update_check_thread is not None and self.update_check_thread.isRunning():
            if manual:
                QMessageBox.information(self, "Bilgi", "Guncelleme kontrolu zaten calisiyor.")
            return

        self.statusBar().showMessage("Guncellemeler kontrol ediliyor...", 5000)
        self.update_check_thread = QThread(self)
        self.update_check_worker = ReleaseCheckWorker(self._build_release_client(), RELEASE_TAG)
        self.update_check_worker.moveToThread(self.update_check_thread)
        self.update_check_thread.started.connect(self.update_check_worker.run)
        self.update_check_worker.finished.connect(
            lambda releases, newer: self._handle_update_check_finished(releases, newer, manual)
        )
        self.update_check_worker.error.connect(
            lambda message: self._handle_update_check_error(message, manual)
        )
        self.update_check_worker.finished.connect(self.update_check_thread.quit)
        self.update_check_worker.error.connect(self.update_check_thread.quit)
        self.update_check_thread.finished.connect(self._cleanup_update_check_thread)
        self.update_check_thread.start()

    def _handle_update_check_finished(self, releases, newer_releases, manual):
        self.statusBar().showMessage("Guncelleme kontrolu tamamlandi.", 3000)
        self.last_release_catalog = list(releases or [])
        if manual:
            self._show_update_dialog(releases)
            return

        self._maybe_show_release_notes(releases)

        if not newer_releases:
            return

        latest = newer_releases[0]
        from kasp.config_manager import get_config_manager

        config = get_config_manager()
        dismissed_tag = config.get("updates.last_dismissed_tag", "")
        if dismissed_tag == latest.tag_name:
            return

        reply = QMessageBox.question(
            self,
            "Yeni Surum Bulundu",
            (
                f"Yeni bir release bulundu: {latest.tag_name}\n\n"
                f"{latest.display_name}\n\n"
                "Detaylari gorup indirmek ister misiniz?"
            ),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if reply == QMessageBox.Yes:
            self._show_update_dialog(releases)
        else:
            config.set("updates.last_dismissed_tag", latest.tag_name)

    def _maybe_show_release_notes(self, releases):
        if not releases:
            return
        if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
            return
        if os.environ.get("KASP_SKIP_CHANGELOG_DIALOG") == "1":
            return

        from kasp.config_manager import get_config_manager

        config = get_config_manager()
        last_seen_tag = config.get("updates.last_seen_release_notes_tag", "")
        visible_releases = unseen_releases(last_seen_tag, releases)
        if not visible_releases:
            return

        dialog = ChangelogDialog(visible_releases, RELEASE_TAG, self)
        dialog.exec_()
        config.set("updates.last_seen_release_notes_tag", visible_releases[0].tag_name)

    def _handle_update_check_error(self, message, manual):
        self.statusBar().showMessage("Guncelleme kontrolu basarisiz.", 5000)
        if manual:
            QMessageBox.warning(self, "Guncelleme Kontrolu", message)

    def _show_update_dialog(self, releases):
        if not releases:
            QMessageBox.information(self, "Guncelleme Merkezi", "Yayinlanmis release bulunamadi.")
            return

        dialog = UpdateDialog(releases, RELEASE_TAG, self)
        if dialog.exec_() != dialog.Accepted:
            return

        selected_release = dialog.selected_release
        selected_asset = dialog.selected_asset
        if selected_release is None or selected_asset is None:
            return

        default_name = default_download_filename(selected_release.tag_name, selected_asset)
        target_path, _ = QFileDialog.getSaveFileName(
            self,
            "Guncellemeyi Nereye Indirmek Istiyorsunuz?",
            default_name,
            "Executable Files (*.exe);;All Files (*)",
        )
        if not target_path:
            return

        self._start_update_download(selected_asset, target_path)

    def _start_update_download(self, asset, destination_path):
        if self.update_download_thread is not None and self.update_download_thread.isRunning():
            QMessageBox.information(self, "Bilgi", "Baska bir indirme zaten devam ediyor.")
            return

        self.update_progress_dialog = QProgressDialog(
            "Guncelleme indiriliyor...",
            None,
            0,
            100,
            self,
        )
        self.update_progress_dialog.setWindowTitle("Indirme")
        self.update_progress_dialog.setWindowModality(Qt.WindowModal)
        self.update_progress_dialog.setMinimumDuration(0)
        self.update_progress_dialog.setValue(0)
        self.update_progress_dialog.show()

        self.update_download_thread = QThread(self)
        self.update_download_worker = ReleaseDownloadWorker(
            self._build_release_client(),
            asset,
            destination_path,
        )
        self.update_download_worker.moveToThread(self.update_download_thread)
        self.update_download_thread.started.connect(self.update_download_worker.run)
        self.update_download_worker.progress.connect(self._handle_update_download_progress)
        self.update_download_worker.finished.connect(self._handle_update_download_finished)
        self.update_download_worker.error.connect(self._handle_update_download_error)
        self.update_download_worker.finished.connect(self.update_download_thread.quit)
        self.update_download_worker.error.connect(self.update_download_thread.quit)
        self.update_download_thread.finished.connect(self._cleanup_update_download_thread)
        self.update_download_thread.start()

    def _handle_update_download_progress(self, percent, message):
        if self.update_progress_dialog is None:
            return
        self.update_progress_dialog.setLabelText(message)
        self.update_progress_dialog.setValue(percent)

    def _handle_update_download_finished(self, path):
        if self.update_progress_dialog is not None:
            self.update_progress_dialog.setValue(100)
            self.update_progress_dialog.close()
        QMessageBox.information(
            self,
            "Indirme Tamamlandi",
            f"Guncelleme dosyasi indirildi:\n{path}",
        )

    def _handle_update_download_error(self, message):
        if self.update_progress_dialog is not None:
            self.update_progress_dialog.close()
        QMessageBox.critical(self, "Indirme Hatasi", message)

    def center_on_screen(self):
        from kasp.ui.main_window_auxiliary import MainWindowAuxiliaryController

        return MainWindowAuxiliaryController(self).center_on_screen()

    # Final public controller bridges. These are the active entry points.
    def on_gas_selection_changed(self, gas_name):
        return self.gas_composition_workflow.on_gas_selection_changed(gas_name)

    def load_standard_gas_composition(self, gas_name):
        return self.gas_composition_workflow.load_standard_gas_composition(gas_name)

    def add_component_row(self):
        return self.gas_composition_workflow.add_component_row()

    def remove_component_row(self):
        return self.gas_composition_workflow.remove_component_row()

    def _update_composition_total_label(self, *_args):
        return self.gas_composition_workflow.update_total_label(*_args)

    def normalize_composition(self):
        return self.gas_composition_workflow.normalize_composition()

    def _get_gas_composition(self):
        return self.gas_composition_workflow.get_gas_composition()

    def _get_design_inputs(self):
        try:
            inputs, total_percentage = self.design_input_binder.collect()
            if abs(total_percentage - 100.0) > 1.0:
                self.logger.warning(
                    "Kompozisyon toplamÄ± %%100'den farklÄ± (%%%0.2f). Engine normalize edecek.",
                    total_percentage,
                )
                reply = QMessageBox.warning(
                    self,
                    "âš  Gaz Kompozisyonu ToplamÄ±",
                    f"Gaz bileÅŸenlerinin toplamÄ± <b>%{total_percentage:.2f}</b> â€” bu deÄŸer %100 olmalÄ±dÄ±r.<br><br>"
                    "HesabÄ± yine de devam ettirmek istiyor musunuz? "
                    "(Motor otomatik olarak normalize edecektir.)",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )
                if reply == QMessageBox.No:
                    return None
            return inputs
        except ValueError as exc:
            QMessageBox.critical(self, "Girdi HatasÄ±", f"LÃ¼tfen tÃ¼m zorunlu alanlarÄ± kontrol edin:\n{exc}")
            return None
        except Exception as exc:
            self.logger.error(f"Girdi toplama sÄ±rasÄ±nda beklenmeyen hata: {exc}")
            QMessageBox.critical(self, "Sistem HatasÄ±", "Girdi toplama sÄ±rasÄ±nda beklenmeyen bir hata oluÅŸtu.")
            return None

    def run_calculation(self):
        return self.design_calculation_workflow.run()

    def calculation_finished(self, results_raw, selected_units):
        return self.design_calculation_workflow.calculation_finished(results_raw, selected_units)

    def calculation_error(self, error_message):
        return self.design_calculation_workflow.calculation_error(error_message)

    def stop_calculation(self):
        return self.design_calculation_workflow.stop()

    def update_progress_detailed(self, percentage, message):
        return self.design_calculation_workflow.update_progress_detailed(percentage, message)

    def update_time_estimate(self, seconds):
        return self.design_calculation_workflow.update_time_estimate(seconds)

    def calculation_cancelled(self):
        return self.design_calculation_workflow.calculation_cancelled()

    def _toggle_perf_driver_inputs(self):
        return self.performance_workflow.toggle_driver_inputs()

    def handle_design_report(self):
        return self.document_workflow.handle_design_report()

    def export_results(self):
        return self.document_workflow.export_results()

    def handle_performance_report(self):
        return self.document_workflow.handle_performance_report()

    def open_library_manager(self):
        return self.window_actions.open_library_manager()

    def clear_engine_cache(self):
        return self.window_actions.clear_engine_cache()

    def show_about_dialog(self):
        return self.window_actions.show_about_dialog()

    def show_examples(self):
        return self.window_actions.show_examples()

    def show_thermodynamics_handbook(self):
        return self.window_actions.show_thermodynamics_handbook()

    def _update_admin_menu_visibility(self):
        from kasp.security import Session
        menu_bar = self.menuBar()
        for action in menu_bar.findChildren(QAction):
            if action.text() == "👥 Kullanıcı Yönetimi":
                action.setVisible(Session.is_admin())
                break

    def _check_must_change_password(self):
        from kasp.security import Session
        user = Session.current_user()
        if user is None or not user.must_change_password:
            return
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(500, self.change_password)
        from kasp.core.user_manager import UserManager
        from kasp.data.database import UnitDatabase

    def _apply_tab_visibility(self):
        from kasp.security import Session
        tabs = getattr(self, "_main_tabs", None)
        if tabs is None:
            return

        # Log sekmesi — sadece admin
        if hasattr(self, "log_tab"):
            idx = tabs.indexOf(self.log_tab)
            if idx >= 0:
                tabs.setTabVisible(idx, Session.is_admin())

        # Engineering sekmesi — sadece admin + engineering mode
        if hasattr(self, "engineering_tab"):
            idx = tabs.indexOf(self.engineering_tab)
            if idx >= 0:
                tabs.setTabVisible(idx, Session.is_engineering_mode())
        elif Session.is_engineering_mode():
            self._add_engineering_tab(tabs)

    def _add_engineering_tab(self, tabs):
        from PyQt5.QtWidgets import QWidget
        self.engineering_tab = QWidget()
        tabs.addTab(self.engineering_tab, "🛠️ Engineering")
        self._setup_engineering_tab()

    def _setup_engineering_tab(self):
        from kasp.ui.engineering_tab_builders import build_engineering_dashboard
        self._eng_widgets = build_engineering_dashboard(
            self.engineering_tab,
            engine=self.engine,
            last_results=getattr(self, "last_design_results_raw", None)
        )
        export_btn = self._eng_widgets.get("export_btn")
        if export_btn:
            export_btn.clicked.connect(self._export_engineering_trace)
        eos_btn = self._eng_widgets.get("eos_run_btn")
        if eos_btn:
            eos_btn.clicked.connect(self._run_eos_shootout)
        method_btn = self._eng_widgets.get("method_run_btn")
        if method_btn:
            method_btn.clicked.connect(self._run_method_shootout)

    def _run_eos_shootout(self):
        if not getattr(self, "last_design_inputs", None):
            return
        from kasp.core.engineering import run_eos_shootout
        table = self._eng_widgets["eos_table"]
        table.setRowCount(0)
        prop_table = self._eng_widgets["prop_table"]
        prop_table.setRowCount(0)
        results = run_eos_shootout(self.engine, self.last_design_inputs)
        for r in results:
            row = table.rowCount()
            table.insertRow(row)
            table.setItem(row, 0, QTableWidgetItem(r.get("label", "—")))
            if r["success"]:
                table.setItem(row, 1, QTableWidgetItem(f"{r.get('t_out', 0) - 273.15:.1f}" if r.get('t_out') else "—"))
                table.setItem(row, 2, QTableWidgetItem(f"{r.get('head_kj_kg', 0):.1f}" if r.get('head_kj_kg') else "—"))
                table.setItem(row, 3, QTableWidgetItem(f"{r.get('power_kw', 0):.1f}" if r.get('power_kw') else "—"))
                table.setItem(row, 4, QTableWidgetItem(f"{r.get('poly_eff_actual', 0):.1f}%" if r.get('poly_eff_actual') else "—"))
                table.setItem(row, 5, QTableWidgetItem(f"{r.get('head_diff_pct', 0):+.2f}%" if r.get('head_diff_pct') is not None else "—"))
                table.setItem(row, 6, QTableWidgetItem(f"{r.get('elapsed_s', 0):.2f}"))
            else:
                table.setItem(row, 1, QTableWidgetItem(f"❌ {r.get('error', '')}"))

            # Ham property tablosu
            raw = r.get("raw_props", {})
            if r["success"] and raw:
                prow = prop_table.rowCount()
                prop_table.insertRow(prow)
                prop_table.setItem(prow, 0, QTableWidgetItem(r.get("label", "—")))
                prop_table.setItem(prow, 1, QTableWidgetItem(f"{raw.get('inlet_mw', 0):.2f}" if raw.get('inlet_mw') else "—"))
                prop_table.setItem(prow, 2, QTableWidgetItem(f"{raw.get('inlet_k', 0):.4f}" if raw.get('inlet_k') else "—"))
                prop_table.setItem(prow, 3, QTableWidgetItem(f"{raw.get('inlet_z', 0):.4f}" if raw.get('inlet_z') else "—"))
                prop_table.setItem(prow, 4, QTableWidgetItem(f"{raw.get('inlet_cp', 0):.1f}" if raw.get('inlet_cp') else "—"))
                prop_table.setItem(prow, 5, QTableWidgetItem(f"{raw.get('inlet_cv', 0):.1f}" if raw.get('inlet_cv') else "—"))
                prop_table.setItem(prow, 6, QTableWidgetItem(f"{raw.get('inlet_density', 0):.2f}" if raw.get('inlet_density') else "—"))
                prop_table.setItem(prow, 7, QTableWidgetItem(str(raw.get('inlet_phase', "—"))))
                prop_table.setItem(prow, 8, QTableWidgetItem(f"{raw.get('mass_flow_kgs', 0):.4f}" if raw.get('mass_flow_kgs') else "—"))

    def _run_method_shootout(self):
        if not getattr(self, "last_design_inputs", None):
            return
        from kasp.core.engineering import run_method_shootout
        table = self._eng_widgets["method_table"]
        table.setRowCount(0)
        results = run_method_shootout(self.engine, self.last_design_inputs)
        for r in results:
            row = table.rowCount()
            table.insertRow(row)
            table.setItem(row, 0, QTableWidgetItem(r.get("label", "—")))
            if r["success"]:
                table.setItem(row, 1, QTableWidgetItem(f"{r.get('t_out', 0) - 273.15:.1f}" if r.get('t_out') else "—"))
                table.setItem(row, 2, QTableWidgetItem(f"{r.get('head_kj_kg', 0):.1f}" if r.get('head_kj_kg') else "—"))
                table.setItem(row, 3, QTableWidgetItem(f"{r.get('power_kw', 0):.1f}" if r.get('power_kw') else "—"))
                table.setItem(row, 4, QTableWidgetItem(f"{r.get('poly_eff_actual', 0):.1f}%" if r.get('poly_eff_actual') else "—"))
                table.setItem(row, 5, QTableWidgetItem("✓" if r.get('convergence') else "✗"))
                table.setItem(row, 6, QTableWidgetItem(f"{r.get('elapsed_s', 0):.2f}"))
            else:
                table.setItem(row, 1, QTableWidgetItem(f"❌ {r.get('error', '')}"))

    def _populate_engineering_dashboard(self, results):
        if not hasattr(self, "_eng_widgets") or not self._eng_widgets:
            return
        from kasp.ui.engineering_tab_builders import _populate_trace_tree, _populate_performance, _populate_health, _populate_fallback
        _populate_trace_tree(self._eng_widgets["trace_tree"], results)
        _populate_performance(self._eng_widgets["perf_labels"], self.engine)
        _populate_health(self._eng_widgets["health_table"], results)
        _populate_fallback(self._eng_widgets["fallback_table"], results)

    def _export_engineering_trace(self):
        from PyQt5.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(self, "İzleme Verisini Dışa Aktar", "kasp_trace.csv", "CSV (*.csv)")
        if not path:
            return
        import csv
        tree = self._eng_widgets.get("trace_tree")
        if tree is None:
            return
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["Seviye", "Aşama/Iterasyon", "Detay"])

            def walk(item, level=""):
                w.writerow([level, item.text(0), item.text(1)])
                for i in range(item.childCount()):
                    walk(item.child(i), level + "  ")

            for i in range(tree.topLevelItemCount()):
                walk(tree.topLevelItem(i))

    def show_admin_panel(self):
        from kasp.security import Session
        if not Session.is_admin():
            return
        from kasp.core.user_manager import UserManager
        from kasp.data.database import UnitDatabase
        from kasp.ui.admin_panel import AdminPanelDialog
        db = UnitDatabase()
        user_manager = UserManager(db)
        dialog = AdminPanelDialog(user_manager, parent=self)
        dialog.exec_()

    def change_password(self):
        from kasp.security import Session
        from kasp.core.user_manager import UserManager
        from kasp.data.database import UnitDatabase
        from kasp.ui.dialogs import ChangePasswordDialog
        user = Session.current_user()
        if user is None:
            return
        forced = user.must_change_password
        while True:
            dialog = ChangePasswordDialog(self)
            if forced:
                dialog.setWindowTitle("🔑 Zorunlu Şifre Değişikliği")
            if dialog.exec_() != ChangePasswordDialog.Accepted:
                if forced:
                    QMessageBox.critical(self, "Zorunlu",
                                         "Programı kullanmak için şifrenizi değiştirmelisiniz.")
                    continue
                return
            old_pw, new_pw = dialog.get_passwords()
            db = UnitDatabase()
            user_mgr = UserManager(db)
            ok, err = user_mgr.change_password(user.id, old_pw, new_pw)
            if ok:
                if forced:
                    user_mgr.update_user(user.id, must_change_password=0)
                QMessageBox.information(self, "Başarılı", "Şifre başarıyla değiştirildi.")
                return
            else:
                QMessageBox.warning(self, "Hata", err or "Şifre değiştirilemedi.")
                if not forced:
                    return

    def logout(self):
        from kasp.security import Session
        Session.logout()
        self.close()

    def new_project(self):
        return self.document_workflow.new_project()

    def save_project(self):
        return self.document_workflow.save_project()

    def load_project(self):
        return self.document_workflow.load_project()

    def clear_logs(self):
        return self.window_actions.clear_logs()

    def append_log(self, msg):
        return self.window_actions.append_log(msg)

    def _filter_logs(self, selected_level):
        return self.window_actions.filter_logs(selected_level)

    def run_performance_evaluation(self):
        return self.performance_workflow.run_evaluation()

    def _populate_ui_from_inputs(self, inputs):
        normalized = self.design_input_binder.apply(inputs)
        self.gas_composition_workflow.update_total_label()
        return normalized
