import sys
import os
import json
import datetime
import logging
import threading
from release_metadata import APP_VERSION
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, 
                             QLabel, QPushButton, QLineEdit, QTextEdit, QComboBox, 
                             QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox, 
                             QFormLayout, QGridLayout, QFileDialog, QMessageBox, 
                             QProgressBar, QSlider, QSpinBox, QDoubleSpinBox, QCheckBox, QAction,
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
        self.setMinimumSize(900, 550)
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
        
        # Validation manager
        if VALIDATION_AVAILABLE:
            self.validation_manager = ValidationManager()
        else:
            self.validation_manager = None
        
        # CRITICAL FIX: Initialize all UI components
        self._initialize_ui()
        
        self.logger.info("KASP v%s arayuzu baslatildi", APP_VERSION)
        
        # Sürüm notlarını göster (Ayarlara bağlı)
        self._show_changelog_if_needed()

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

    def _initialize_ui(self):
        """UI bileşenlerini başlatır"""
        self._create_menu()
        self._create_tabs()
        self._setup_design_tab()
        self._setup_performance_tab()
        self._setup_log_tab()
        self._setup_status_bar()   # V4.6: always-visible validation indicator
        self._connect_signals()
        self._populate_unit_combos()
        self._setup_unit_tooltips()
        self._update_method_options()
        self._update_button_state()

    # ------------------------------------------------------------------ #
    # V4.6: Status Bar with Validation Indicator                          #
    # ------------------------------------------------------------------ #
    def _setup_status_bar(self):
        """Alt status bar'a doğrulama göstergesi ekler."""
        from PyQt5.QtWidgets import QStatusBar
        status_bar = QStatusBar(self)
        self.setStatusBar(status_bar)

        if VALIDATION_AVAILABLE and self.validation_manager:
            # Use the compact MinimalValidationIndicator from validation_status.py
            from kasp.ui.validation_status import MinimalValidationIndicator
            self.status_validation_indicator = MinimalValidationIndicator()
            status_bar.addPermanentWidget(self.status_validation_indicator)

            # Connect all validated inputs to update the status bar indicator
            for field_name, input_field in self.validation_manager.inputs.items():
                input_field.validation_changed.connect(self._update_status_bar_validation)

            self._update_status_bar_validation()  # initial update
        else:
            self.status_validation_indicator = None

        # Version label on the right
        from PyQt5.QtWidgets import QLabel as _QLabel
        version_label = _QLabel(f"KASP v{APP_VERSION}")
        version_label.setStyleSheet("color: #7f8c8d; padding: 0 8px;")
        status_bar.addPermanentWidget(version_label)

    def _update_status_bar_validation(self, *args):
        """Status bar doğrulama göstergesini günceller."""
        if not hasattr(self, 'status_validation_indicator') or self.status_validation_indicator is None:
            return
        if self.validation_manager is None:
            return
        summary = self.validation_manager.get_validation_summary()
        self.status_validation_indicator.update_status(
            summary['all_valid'],
            summary['valid_count'],
            summary['total_fields']
        )

    def _show_validation_popup(self):
        """Geçersiz alanlar varsa pop-up uyarı gösterir.
        
        Returns:
            bool: True if all inputs valid (proceed with calc), False to abort.
        """
        if self.validation_manager is None:
            return True  # No validation manager — proceed
        if self.validation_manager.all_inputs_valid():
            return True

        invalid_fields = self.validation_manager.get_invalid_fields()
        field_name_map = {
            'inlet_pressure': 'Giriş Basıncı',
            'inlet_temperature': 'Giriş Sıcaklığı',
            'outlet_pressure': 'Çıkış Basıncı',
            'flow_rate': 'Gaz Debisi',
        }
        lines = []
        for field_name, error_msg in invalid_fields:
            display = field_name_map.get(field_name, field_name.replace('_', ' ').title())
            lines.append(f"  • {display}: {error_msg}")

        QMessageBox.warning(
            self,
            "⚠️ Geçersiz Girişler",
            "Hesaplama başlatmadan önce lütfen aşağıdaki alanları düzeltiniz:\n\n"
            + "\n".join(lines)
            + "\n\nGeçersiz alanlar kırmızı kenarlık ile işaretlenmiştir."
        )
        return False

    def _create_menu(self):
        """Menü çubuğu oluşturur"""
        menu_bar = self.menuBar()
        
        # Dosya Menüsü
        file_menu = menu_bar.addMenu("📁 Dosya")
        
        new_action = QAction("🆕 Yeni Proje", self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self.new_project)
        file_menu.addAction(new_action)
        
        load_action = QAction("📂 Proje Aç...", self)
        load_action.setShortcut("Ctrl+O")
        load_action.triggered.connect(self.load_project)
        file_menu.addAction(load_action)
        
        save_action = QAction("💾 Projeyi Kaydet...", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_project)
        file_menu.addAction(save_action)
        
        file_menu.addSeparator()
        
        export_action = QAction("📤 Sonuçları Dışa Aktar", self)
        export_action.setShortcut("Ctrl+E")
        export_action.triggered.connect(self.export_results)
        file_menu.addAction(export_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("🚪 Çıkış", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Araçlar Menüsü
        tools_menu = menu_bar.addMenu("🛠️ Araçlar")
        
        library_action = QAction("📚 Kütüphane Yöneticisi", self)
        library_action.triggered.connect(self.open_library_manager)
        tools_menu.addAction(library_action)
        
        clear_cache_action = QAction("🧹 Önbelleği Temizle", self)
        clear_cache_action.triggered.connect(self.clear_engine_cache)
        tools_menu.addAction(clear_cache_action)
        
        # Yardım Menüsü
        help_menu = menu_bar.addMenu("❓ Yardım")
        
        examples_action = QAction("📖 Örnekler", self)
        examples_action.triggered.connect(self.show_examples)
        help_menu.addAction(examples_action)
        
        about_action = QAction("ℹ️ Hakkında", self)
        about_action.triggered.connect(self.show_about_dialog)
        help_menu.addAction(about_action)

    def _create_tabs(self):
        """Ana sekme yapısını oluşturur"""
        tabs = QTabWidget()
        tabs.setFont(QFont("Inter", 10))
        
        self.design_tab = QWidget()
        self.performance_tab = QWidget()
        self.log_tab = QWidget()
        
        tabs.addTab(self.design_tab, "📊 Tasarım / Simülasyon")
        tabs.addTab(self.performance_tab, "📈 Performans Değerlendirme")
        tabs.addTab(self.log_tab, "📋 Sistem Logları")
        
        self.main_layout.addWidget(tabs)

    def _setup_design_tab(self):
        """Tasarım sekmesi kurulumu — V4.6: Sol panel QScrollArea içinde."""
        layout = QHBoxLayout(self.design_tab)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # ── V4.6: Sol panel scroll area ────────────────────────────────────
        # Content widget that holds all left-panel groups
        left_content = QWidget()
        left_content.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        left_layout = QVBoxLayout(left_content)
        left_layout.setContentsMargins(4, 4, 4, 4)
        left_layout.setSpacing(6)

        # Scroll area wraps the content widget
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setWidget(left_content)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)  # no horizontal scroll
        left_scroll.setMinimumWidth(360)
        left_scroll.setMaximumWidth(520)
        left_scroll.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        # Style the scroll area
        left_scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
            "QScrollArea > QWidget > QWidget { background: transparent; }"
        )
        
        # Proje bilgileri
        project_group = QGroupBox("📋 Proje Bilgileri")
        project_layout = QFormLayout()
        
        self.project_name_edit = QLineEdit()
        self.project_name_edit.setPlaceholderText("Proje adını girin...")
        self.project_name_edit.setText("Yeni Kompresör Projesi")
        
        self.project_notes_edit = QTextEdit()
        self.project_notes_edit.setMaximumHeight(80)
        self.project_notes_edit.setPlaceholderText("Proje notları...")
        
        project_layout.addRow("Proje Adı *:", self.project_name_edit)
        project_layout.addRow("Notlar:", self.project_notes_edit)
        
        project_group.setLayout(project_layout)
        left_layout.addWidget(project_group)
        
        # Proses koşulları
        process_group = QGroupBox("⚙️ Proses Koşulları")
        process_layout = QGridLayout()
        
        # Giriş koşulları
        process_layout.addWidget(QLabel("Giriş Basıncı *:"), 0, 0)
        self.p_in_edit = ValidatedLineEdit(validation_func=validate_pressure)
        self.p_in_edit.setText("49.65")
        if self.validation_manager:
            self.validation_manager.register_input('inlet_pressure', self.p_in_edit)
        # self.p_in_edit.setValidator(QDoubleValidator(0, 1000, 2)) # Built-in validator handles this
        process_layout.addWidget(self.p_in_edit, 0, 1)
        
        self.p_in_unit_combo = QComboBox()
        self.p_in_unit_combo.addItems(['bar(a)', 'bar(g)', 'psia', 'psig', 'kPa', 'MPa', 'Pa'])
        self.p_in_unit_combo.setCurrentText('bar(g)')
        process_layout.addWidget(self.p_in_unit_combo, 0, 2)
        
        process_layout.addWidget(QLabel("Giriş Sıcaklığı *:"), 1, 0)
        self.t_in_edit = ValidatedLineEdit(validation_func=validate_temperature)
        self.t_in_edit.setText("19")
        if self.validation_manager:
            self.validation_manager.register_input('inlet_temperature', self.t_in_edit)
        # self.t_in_edit.setValidator(QDoubleValidator(-100, 1000, 1))
        process_layout.addWidget(self.t_in_edit, 1, 1)
        
        self.t_in_unit_combo = QComboBox()
        self.t_in_unit_combo.addItems(['°C', '°F', 'K'])
        self.t_in_unit_combo.setCurrentText('°C')
        process_layout.addWidget(self.t_in_unit_combo, 1, 2)
        
        # Çıkış koşulları
        process_layout.addWidget(QLabel("Çıkış Basıncı *:"), 2, 0)
        self.p_out_edit = ValidatedLineEdit(validation_func=validate_pressure)
        self.p_out_edit.setText("75")
        if self.validation_manager:
            self.validation_manager.register_input('outlet_pressure', self.p_out_edit)
        # self.p_out_edit.setValidator(QDoubleValidator(0, 10000, 2))
        process_layout.addWidget(self.p_out_edit, 2, 1)
        
        self.p_out_unit_combo = QComboBox()
        self.p_out_unit_combo.addItems(['bar(a)', 'bar(g)', 'psia', 'psig', 'kPa', 'MPa', 'Pa'])
        self.p_out_unit_combo.setCurrentText('bar(a)')
        process_layout.addWidget(self.p_out_unit_combo, 2, 2)
        
        process_layout.addWidget(QLabel("Gaz Debisi *:"), 3, 0)
        self.flow_edit = ValidatedLineEdit(validation_func=validate_flow)
        self.flow_edit.setText("1985000")
        if self.validation_manager:
            self.validation_manager.register_input('flow_rate', self.flow_edit)
        # self.flow_edit.setValidator(QDoubleValidator(0, 100000000, 1))
        process_layout.addWidget(self.flow_edit, 3, 1)
        
        self.flow_unit_combo = QComboBox()
        self.flow_unit_combo.addItems(['kg/h', 'kg/s', 'Sm³/h', 'Nm³/h', 'MMSCFD', 'MMSCMD'])
        self.flow_unit_combo.setCurrentText('Sm³/h')
        process_layout.addWidget(self.flow_unit_combo, 3, 2)
        
        process_layout.addWidget(QLabel("Ünite Sayısı:"), 4, 0)
        self.num_units_spin = QSpinBox()
        self.num_units_spin.setRange(1, 20)
        self.num_units_spin.setValue(1)
        process_layout.addWidget(self.num_units_spin, 4, 1)
        
        # ── Kademe & Intercooler Ayarları ──────────────────────────────────
        process_layout.addWidget(QLabel("Kademe Sayısı:"), 5, 0)
        self.num_stages_spin = QSpinBox()
        self.num_stages_spin.setRange(1, 10)
        self.num_stages_spin.setValue(1)
        self.num_stages_spin.setToolTip(
            "Kompresör kademe sayısı.\n"
            "1 = Tek kademeli (intercooler yok)\n"
            "2+ = Çok kademeli (kademeler arası eşit PR dağılımı)"
        )
        process_layout.addWidget(self.num_stages_spin, 5, 1)
        
        # Intercooler etiket
        self.ic_label = QLabel("🔄 Intercooler")
        self.ic_label.setStyleSheet("font-weight: bold; color: #2980b9; font-size: 9pt;")
        self.ic_label.setEnabled(False)
        process_layout.addWidget(self.ic_label, 6, 0, 1, 3)
        
        process_layout.addWidget(QLabel("  Basınç Kaybı (%):"), 7, 0)
        self.ic_dp_spin = QDoubleSpinBox()
        self.ic_dp_spin.setRange(0.0, 10.0)
        self.ic_dp_spin.setSingleStep(0.5)
        self.ic_dp_spin.setValue(2.0)
        self.ic_dp_spin.setDecimals(1)
        self.ic_dp_spin.setEnabled(False)
        self.ic_dp_spin.setToolTip("Intercooler'daki basınç kaybı yüzdesi (%)")
        process_layout.addWidget(self.ic_dp_spin, 7, 1)
        
        process_layout.addWidget(QLabel("  Çıkış Sıcaklığı (°C):"), 8, 0)
        self.ic_temp_edit = QLineEdit("40.0")
        self.ic_temp_edit.setValidator(QDoubleValidator(0.0, 200.0, 1))
        self.ic_temp_edit.setEnabled(False)
        self.ic_temp_edit.setToolTip("Intercooler sonrası gaz sıcaklığı (°C)")
        process_layout.addWidget(self.ic_temp_edit, 8, 1)
        
        # Kademe sayısına göre intercooler alanlarını aç/kapa
        def _toggle_intercooler(stages):
            enabled = stages > 1
            self.ic_label.setEnabled(enabled)
            self.ic_dp_spin.setEnabled(enabled)
            self.ic_temp_edit.setEnabled(enabled)
            if not enabled:
                self.ic_label.setStyleSheet("font-weight: bold; color: #95a5a6; font-size: 9pt;")
            else:
                self.ic_label.setStyleSheet("font-weight: bold; color: #2980b9; font-size: 9pt;")
        
        self.num_stages_spin.valueChanged.connect(_toggle_intercooler)
        
        process_group.setLayout(process_layout)
        left_layout.addWidget(process_group)
        
        # Gaz kompozisyonu
        gas_group = QGroupBox("⛽ Gaz Kompozisyonu")
        gas_layout = QVBoxLayout()
        
        gas_selection_layout = QHBoxLayout()
        gas_selection_layout.addWidget(QLabel("Gaz:"))
        
        self.gas_combo = QComboBox()
        self.gas_combo.addItems(['Özel Karışım'] + self.COMMON_COMPONENTS_DISPLAY)
        self.gas_combo.currentTextChanged.connect(self.on_gas_selection_changed)
        gas_selection_layout.addWidget(self.gas_combo)
        
        gas_selection_layout.addStretch()
        gas_layout.addLayout(gas_selection_layout)
        
        self.composition_table = QTableWidget()
        self.composition_table.setColumnCount(2)
        self.composition_table.setHorizontalHeaderLabels(['Bileşen', '%'])
        self.composition_table.horizontalHeader().setStretchLastSection(True)
        self.composition_table.setRowCount(5)
        self.composition_table.setMinimumHeight(220) # V4.6: En az 6 satır kaydırmasız görünür
        
        default_composition = [
            ('Methane (CH₄)', 98.00),
            ('Ethane (C₂H₆)', 1.50), 
            ('Propane (C₃H₈)', 0.00),
            ('n-Butane (n-C₄H₁₀)', 0.00),
            ('Nitrogen (N₂)', 0.50)
        ]
        
        for i, (display_name, percentage) in enumerate(default_composition):
            combo = QComboBox()
            combo.addItems(self.COMMON_COMPONENTS_DISPLAY)
            if display_name in self.COMMON_COMPONENTS_DISPLAY:
                combo.setCurrentText(display_name)
            self.composition_table.setCellWidget(i, 0, combo)
            
            percent_item = QTableWidgetItem(str(percentage))
            percent_item.setTextAlignment(Qt.AlignCenter)
            self.composition_table.setItem(i, 1, percent_item)
        
        gas_layout.addWidget(self.composition_table)
        
        comp_buttons_layout = QHBoxLayout()
        self.add_component_btn = QPushButton("➕ Bileşen Ekle")
        self.remove_component_btn = QPushButton("➖ Bileşen Sil")
        self.normalize_btn = QPushButton("📊 Normalize Et")
        
        comp_buttons_layout.addWidget(self.add_component_btn)
        comp_buttons_layout.addWidget(self.remove_component_btn)
        comp_buttons_layout.addWidget(self.normalize_btn)
        comp_buttons_layout.addStretch()
        
        gas_layout.addLayout(comp_buttons_layout)
        
        # V4.6: Canlı Toplam Etiketi — %100 dışında renk değiştirir
        self.comp_total_label = QLabel("Toplam: 100.00%  ✔")
        self.comp_total_label.setStyleSheet(
            "font-weight: bold; color: #27ae60; padding: 2px 4px; border-radius: 4px;"
        )
        gas_layout.addWidget(self.comp_total_label)
        
        gas_group.setLayout(gas_layout)
        left_layout.addWidget(gas_group)
        
        # V4.6: ValidationStatusWidget kaldırıldı — durum status bar'a taşındı.
        # Unit combolar hâlâ validation context'i günceller (border rengi için).
        if VALIDATION_AVAILABLE and self.validation_manager:
            # Connect unit combos to update validation context
            self.p_in_unit_combo.currentTextChanged.connect(
                lambda unit: self.p_in_edit.set_validation_context({'unit': unit})
            )
            self.t_in_unit_combo.currentTextChanged.connect(
                lambda unit: self.t_in_edit.set_validation_context({'unit': unit})
            )
            self.p_out_unit_combo.currentTextChanged.connect(
                lambda unit: self.p_out_edit.set_validation_context({'unit': unit})
            )
            self.flow_unit_combo.currentTextChanged.connect(
                lambda unit: self.flow_edit.set_validation_context({'unit': unit})
            )

            # Initial validation context (border colour feedback from start)
            self.p_in_edit.set_validation_context({'unit': self.p_in_unit_combo.currentText()})
            self.t_in_edit.set_validation_context({'unit': self.t_in_unit_combo.currentText()})
            self.p_out_edit.set_validation_context({'unit': self.p_out_unit_combo.currentText()})
            self.flow_edit.set_validation_context({'unit': self.flow_unit_combo.currentText()})
        
        # Hesaplama parametreleri
        calc_group = QGroupBox("🧮 Hesaplama Parametreleri")
        calc_layout = QFormLayout()
        
        self.eos_method_combo = QComboBox()
        if COOLPROP_LOADED:
            self.eos_method_combo.addItem("🎯 Yüksek Doğruluk (CoolProp)")
        if THERMO_LOADED:
            self.eos_method_combo.addItem("📊 Peng-Robinson (thermo)")
            self.eos_method_combo.addItem("📈 SRK (thermo)")
        
        if self.eos_method_combo.count() == 0:
            self.eos_method_combo.addItem("❌ Kütüphane Yok")
        else:
            self.eos_method_combo.setCurrentIndex(0)
        
        self.method_combo = QComboBox()
        self.method_combo.addItems([
            "Metot 1: Ortalama Özellikler",
            "Metot 2: Uç Nokta", 
            "Metot 3: Artımlı Basınç",
            "Metot 4: Doğrudan H-S"
        ])
        
        # Verim Girdileri
        poly_layout = QHBoxLayout()
        self.poly_eff_edit = QLineEdit("90.0")
        self.poly_eff_edit.setValidator(QDoubleValidator(50.0, 95.0, 1))
        self.poly_eff_edit.setMaximumWidth(60)
        self.poly_eff_slider = QSlider(Qt.Horizontal)
        self.poly_eff_slider.setRange(500, 950)
        self.poly_eff_slider.setValue(900)
        poly_layout.addWidget(self.poly_eff_edit)
        poly_layout.addWidget(QLabel("%"))
        poly_layout.addWidget(self.poly_eff_slider)
        
        therm_layout = QHBoxLayout()
        self.therm_eff_edit = QLineEdit("35.0")
        self.therm_eff_edit.setValidator(QDoubleValidator(20.0, 50.0, 1))
        self.therm_eff_edit.setMaximumWidth(60)
        self.therm_eff_slider = QSlider(Qt.Horizontal)
        self.therm_eff_slider.setRange(200, 500)
        self.therm_eff_slider.setValue(350)
        therm_layout.addWidget(self.therm_eff_edit)
        therm_layout.addWidget(QLabel("%"))
        therm_layout.addWidget(self.therm_eff_slider)
        
        mech_layout = QHBoxLayout()
        self.mech_eff_edit = QLineEdit("98.0")
        self.mech_eff_edit.setValidator(QDoubleValidator(80.0, 99.0, 1))
        self.mech_eff_edit.setMaximumWidth(60)
        self.mech_eff_slider = QSlider(Qt.Horizontal)
        self.mech_eff_slider.setRange(800, 990)
        self.mech_eff_slider.setValue(980)
        mech_layout.addWidget(self.mech_eff_edit)
        mech_layout.addWidget(QLabel("%"))
        mech_layout.addWidget(self.mech_eff_slider)
        
        calc_layout.addRow("EOS Metodu:", self.eos_method_combo)
        
        self.lhv_source_combo = QComboBox()
        self.lhv_source_combo.addItems([
            "KASP Sabitleri (Hızlı/Varsayılan)",
            "Thermo Veritabanı (Gelişmiş)"
        ])
        if not THERMO_LOADED:
            self.lhv_source_combo.setEnabled(False)
            self.lhv_source_combo.setItemText(1, "Thermo Veritabanı (Kütüphane Yok)")
        calc_layout.addRow("LHV/HHV Kaynağı:", self.lhv_source_combo)
        
        calc_layout.addRow("Hesaplama Metodu:", self.method_combo)
        calc_layout.addRow("Politropik Verim (%):", poly_layout)
        calc_layout.addRow("Isıl Verim (%):", therm_layout)
        calc_layout.addRow("Mekanik Verim (%):", mech_layout)
        
        # Tutarlılık Modu Ayarları
        calc_layout.addRow("", QLabel(""))  # Boşluk
        consistency_separator = QLabel("🔄 Tutarlılık Modu (Self-Consistent)")
        consistency_separator.setStyleSheet("font-weight: bold; color: #2980b9;")
        calc_layout.addRow("", consistency_separator)
        
        self.consistency_check = QCheckBox("Tutarlılık İterasyonu Kullan")
        self.consistency_check.setToolTip(
            "Girdi politropik verim ile hesaplanan verim eşitlenene kadar iterasyon yapar.\n\n"
            "KAPALI (Hızlı): Tek geçiş, hızlı hesaplama\n"
            "AÇIK (Tutarlı): İteratif, yavaş ama termodinamik olarak tutarlı"
        )
        calc_layout.addRow("", self.consistency_check)
        
        # İterasyon ayarları
        iter_settings_layout = QHBoxLayout()
        
        iter_settings_layout.addWidget(QLabel("Maks. İterasyon:"))
        self.max_consistency_iter = QSpinBox()
        self.max_consistency_iter.setRange(5, 50)
        self.max_consistency_iter.setValue(20)
        self.max_consistency_iter.setEnabled(False)
        self.max_consistency_iter.setToolTip("İzin verilen maksimum iterasyon sayısı (5-50)")
        iter_settings_layout.addWidget(self.max_consistency_iter)
        
        iter_settings_layout.addWidget(QLabel("Tolerans (%):"))
        self.consistency_tolerance = QDoubleSpinBox()
        self.consistency_tolerance.setRange(0.01, 1.0)
        self.consistency_tolerance.setSingleStep(0.01)
        self.consistency_tolerance.setValue(0.1)
        self.consistency_tolerance.setDecimals(2)
        self.consistency_tolerance.setEnabled(False)
        self.consistency_tolerance.setToolTip("Yakınsama toleransı: |η_calc - η_used| < tol")
        iter_settings_layout.addWidget(self.consistency_tolerance)
        
        iter_settings_layout.addStretch()
        calc_layout.addRow("", iter_settings_layout)
        
        # Checkbox ile ayarları enable/disable et
        self.consistency_check.toggled.connect(lambda checked: [
            self.max_consistency_iter.setEnabled(checked),
            self.consistency_tolerance.setEnabled(checked)
        ])
        
        calc_group.setLayout(calc_layout)
        left_layout.addWidget(calc_group)
        
        # Hesaplama butonları
        button_layout = QHBoxLayout()
        self.calculate_btn = QPushButton("🚀 Hesaplama Başlat")
        self.calculate_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                font-weight: bold;
                padding: 12px;
                border-radius: 6px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #2ecc71;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
            }
        """)
        
        self.stop_btn = QPushButton("⏹️ Durdur")
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                font-weight: bold;
                padding: 12px;
                border-radius: 6px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
            }
        """)
        
        button_layout.addWidget(self.calculate_btn)
        button_layout.addWidget(self.stop_btn)
        left_layout.addLayout(button_layout)
        
        # Progress bar ve durum göstergeleri (Task 4)
        progress_group = QGroupBox("📊 İlerleme")
        progress_layout = QVBoxLayout()
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        progress_layout.addWidget(self.progress_bar)
        
        self.progress_status_label = QLabel("Ready")
        self.progress_status_label.setVisible(False)
        self.progress_status_label.setStyleSheet("color: #7f8c8d; font-size: 9pt;")
        progress_layout.addWidget(self.progress_status_label)
        
        self.progress_time_label = QLabel("")
        self.progress_time_label.setVisible(False)
        self.progress_time_label.setStyleSheet("color: #3498db; font-size: 9pt;")
        progress_layout.addWidget(self.progress_time_label)
        
        progress_group.setLayout(progress_layout)
        left_layout.addWidget(progress_group)
        
        left_layout.addStretch()

        # ── Sağ panel: Sonuç gösterimi ─────────────────────────────────────
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        self.results_tabs = QTabWidget()
        
        self.basic_results_tab = QWidget()
        self.setup_basic_results_tab()
        self.results_tabs.addTab(self.basic_results_tab, "📈 Temel Sonuçlar")
        
        self.turbine_selection_tab = QWidget()
        self.setup_turbine_selection_tab()
        self.results_tabs.addTab(self.turbine_selection_tab, "🚀 Türbin Seçimi")
        
        self.detailed_results_tab = QWidget()
        self.setup_detailed_results_tab()
        self.results_tabs.addTab(self.detailed_results_tab, "📊 Detaylı Analiz")
        
        self.graphs_tab = QWidget()
        self.setup_graphs_tab()
        self.results_tabs.addTab(self.graphs_tab, "📉 Grafikler")
        
        right_layout.addWidget(self.results_tabs)
        
        # Ana layout'a panelleri ekle: sol scroll area + sağ panel
        layout.addWidget(left_scroll)
        layout.addWidget(right_panel, stretch=1)

    def _setup_performance_tab(self):
        """Performans sekmesi kurulumu"""
        layout = QHBoxLayout(self.performance_tab)
        
        # Sol Taraf: Girdiler
        input_panel = QWidget()
        input_layout = QVBoxLayout(input_panel)
        
        # 1. Saha Ölçümleri
        field_group = QGroupBox("📍 Saha Ölçümleri (ASME PTC 10)")
        field_layout = QFormLayout()
        
        self.perf_p1_edit = QLineEdit("49.65")
        self.perf_t1_edit = QLineEdit("19.0")
        self.perf_p2_edit = QLineEdit("75.0")
        self.perf_t2_edit = QLineEdit("60.0") # Örnek çıkış sıcaklığı
        
        # Debi ve Birimi yatay kutuda
        flow_layout = QHBoxLayout()
        self.perf_flow_edit = QLineEdit("1985000")
        self.perf_flow_unit_combo = QComboBox()
        self.perf_flow_unit_combo.addItems(["Sm³/h", "Nm³/h", "kg/h", "kg/s"])
        flow_layout.addWidget(self.perf_flow_edit)
        flow_layout.addWidget(self.perf_flow_unit_combo)
        
        self.perf_rpm_edit = QLineEdit("10000") # Nominal devir
        self.perf_mech_eff_edit = QLineEdit("98.0")
        
        field_layout.addRow("Giriş Basıncı (P1) [bar(g)]:", self.perf_p1_edit)
        field_layout.addRow("Giriş Sıcaklığı (T1) [°C]:", self.perf_t1_edit)
        field_layout.addRow("Çıkış Basıncı (P2) [bar(g)]:", self.perf_p2_edit)
        field_layout.addRow("Çıkış Sıcaklığı (T2) [°C]:", self.perf_t2_edit)
        field_layout.addRow("Devir [RPM] (Opsiyonel):", self.perf_rpm_edit)
        field_layout.addRow("Debi:", flow_layout)
        field_layout.addRow("Mekanik Verim [%]:", self.perf_mech_eff_edit)
        
        field_group.setLayout(field_layout)
        input_layout.addWidget(field_group)
        
        # 2. Türbin / Yakıt Seçimi (XOR)
        driver_group = QGroupBox("⚙️ Sürücü Verileri")
        driver_layout = QVBoxLayout()
        
        self.radio_turb_eff = QRadioButton("Türbin Isıl Verimini Gir (Yakıtı Hesapla)")
        self.radio_fuel_cons = QRadioButton("Yakıt Tüketimini Gir (Verimi Hesapla)")
        self.radio_turb_eff.setChecked(True)
        
        driver_layout.addWidget(self.radio_turb_eff)
        
        turb_eff_layout = QHBoxLayout()
        turb_eff_layout.addWidget(QLabel("Türbin Verimi [%]:"))
        self.perf_turb_eff_edit = QLineEdit("35.0")
        turb_eff_layout.addWidget(self.perf_turb_eff_edit)
        driver_layout.addLayout(turb_eff_layout)
        
        driver_layout.addWidget(self.radio_fuel_cons)
        
        fuel_cons_layout = QHBoxLayout()
        fuel_cons_layout.addWidget(QLabel("Yakıt Tüketimi [kg/h]:"))
        self.perf_fuel_cons_edit = QLineEdit("")
        self.perf_fuel_cons_edit.setEnabled(False)
        fuel_cons_layout.addWidget(self.perf_fuel_cons_edit)
        driver_layout.addLayout(fuel_cons_layout)
        
        # LHV/HHV Kaynak Seçimi
        self.perf_lhv_source_combo = QComboBox()
        self.perf_lhv_source_combo.addItems([
            "KASP Sabitleri (Hızlı/Varsayılan)",
            "Thermo Veritabanı (Gelişmiş)"
        ])
        if not THERMO_LOADED:
            self.perf_lhv_source_combo.setEnabled(False)
            self.perf_lhv_source_combo.setItemText(1, "Thermo Veritabanı (Kütüphane Yok)")
        driver_layout.addWidget(QLabel("LHV / HHV Kaynağı:"))
        driver_layout.addWidget(self.perf_lhv_source_combo)
        
        self.radio_turb_eff.toggled.connect(self._toggle_perf_driver_inputs)
        
        driver_group.setLayout(driver_layout)
        input_layout.addWidget(driver_group)
        
        self.verify_perf_btn = QPushButton("🚀 Performans Değerlendir")
        self.verify_perf_btn.setStyleSheet("background-color: #e67e22; color: white; font-weight: bold; padding: 10px;")
        self.verify_perf_btn.clicked.connect(self.run_performance_evaluation)
        input_layout.addWidget(self.verify_perf_btn)
        
        input_layout.addStretch()
        layout.addWidget(input_panel, stretch=1)
        
        # Sağ Taraf: Sonuçlar
        result_panel = QGroupBox("📊 Değerlendirme Sonuçları")
        result_layout = QFormLayout()
        
        self.perf_res_poly_eff = QLabel("-")
        self.perf_res_isen_eff = QLabel("-")
        self.perf_res_head = QLabel("-")
        self.perf_res_power_gas = QLabel("-")
        self.perf_res_power_shaft = QLabel("-")
        self.perf_res_fuel_or_eff = QLabel("-")
        
        # Stil
        for lbl in [self.perf_res_poly_eff, self.perf_res_isen_eff, self.perf_res_power_gas, 
                   self.perf_res_power_shaft, self.perf_res_fuel_or_eff, self.perf_res_head]:
            lbl.setStyleSheet("font-weight: bold; font-size: 15px; color: #2c3e50;")
        
        result_layout.addRow("Politropik Verim (ηp):", self.perf_res_poly_eff)
        result_layout.addRow("İzentropik Verim (ηs):", self.perf_res_isen_eff)
        result_layout.addRow("Politropik Head (Hp) [kJ/kg]:", self.perf_res_head)
        result_layout.addRow("Gaz Gücü (kW):", self.perf_res_power_gas)
        result_layout.addRow("Şaft Gücü (kW):", self.perf_res_power_shaft)
        
        self.perf_res_fuel_lbl = QLabel("Yakıt Tüketimi / Verim:")
        result_layout.addRow(self.perf_res_fuel_lbl, self.perf_res_fuel_or_eff)
        
        result_panel.setLayout(result_layout)
        layout.addWidget(result_panel, stretch=2)

    def _toggle_perf_driver_inputs(self):
        """Türbin verimi veya yakıt tüketimi girişini karşılıklı aç/kapa"""
        if self.radio_turb_eff.isChecked():
            self.perf_turb_eff_edit.setEnabled(True)
            self.perf_fuel_cons_edit.setEnabled(False)
            self.perf_turb_eff_edit.setText("35.0")
            self.perf_fuel_cons_edit.clear()
        else:
            self.perf_turb_eff_edit.setEnabled(False)
            self.perf_fuel_cons_edit.setEnabled(True)
            self.perf_turb_eff_edit.clear()
            self.perf_fuel_cons_edit.setText("500.0")
        
    def _setup_log_tab(self):
        """Log sekmesi kurulumu - Seviye filtreleme ile"""
        layout = QVBoxLayout(self.log_tab)
        
        # Filter controls
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Log Seviyesi:"))
        
        self.log_level_combo = QComboBox()
        self.log_level_combo.addItems(['TÜM LOGLAR', 'DEBUG', 'ITERATION', 'INFO', 'WARNING', 'ERROR'])
        self.log_level_combo.setCurrentText('INFO')
        self.log_level_combo.currentTextChanged.connect(self._filter_logs)
        filter_layout.addWidget(self.log_level_combo)
        
        filter_layout.addStretch()
        
        clear_btn = QPushButton("🧹 Logları Temizle")
        clear_btn.clicked.connect(self.clear_logs)
        filter_layout.addWidget(clear_btn)
        
        layout.addLayout(filter_layout)
        
        # Log display
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Courier", 9))
        layout.addWidget(self.log_text)
        
        # Store all logs for filtering
        self.all_logs = []
        
        self.log_handler.log_signal.connect(self.append_log)


    def _connect_signals(self):
        """Sinyal bağlantılarını kur"""
        # Helper function for synchronization
        def update_slider(edit, slider):
            try:
                value = float(edit.text())
                clamped_value = max(slider.minimum() / 10, min(slider.maximum() / 10, value))
                slider.setValue(int(clamped_value * 10))
                edit.setText(f"{clamped_value:.1f}")
            except ValueError:
                slider_val = slider.value() / 10.0
                edit.setText(f"{slider_val:.1f}")

        def update_edit(edit, slider_val):
            edit.setText(f"{slider_val / 10.0:.1f}")

        # Slider -> Line Edit
        self.poly_eff_slider.valueChanged.connect(lambda v: update_edit(self.poly_eff_edit, v))
        self.therm_eff_slider.valueChanged.connect(lambda v: update_edit(self.therm_eff_edit, v))
        self.mech_eff_slider.valueChanged.connect(lambda v: update_edit(self.mech_eff_edit, v))
        
        # Line Edit -> Slider
        self.poly_eff_edit.editingFinished.connect(lambda: update_slider(self.poly_eff_edit, self.poly_eff_slider))
        self.therm_eff_edit.editingFinished.connect(lambda: update_slider(self.therm_eff_edit, self.therm_eff_slider))
        self.mech_eff_edit.editingFinished.connect(lambda: update_slider(self.mech_eff_edit, self.mech_eff_slider))
        
        # Buton sinyalleri
        self.calculate_btn.clicked.connect(self.run_calculation)
        self.stop_btn.clicked.connect(self.stop_calculation)
        self.add_component_btn.clicked.connect(self.add_component_row)
        self.remove_component_btn.clicked.connect(self.remove_component_row)
        self.normalize_btn.clicked.connect(self.normalize_composition)
        self.refresh_graph_btn.clicked.connect(self.refresh_current_graph)
        self.save_graph_btn.clicked.connect(self.save_current_graph)
        
        # V4.6: Canlı gaz kompozisyon toplamı —  her hücre düzenleme veya satır değişiminde güncelle
        self.composition_table.itemChanged.connect(self._update_composition_total_label)
        self.composition_table.model().rowsInserted.connect(self._update_composition_total_label)
        self.composition_table.model().rowsRemoved.connect(self._update_composition_total_label)
        self.graph_combo.currentTextChanged.connect(self.refresh_current_graph)
        
        # Tablo sinyalleri
        self.turbine_table.itemSelectionChanged.connect(self.on_turbine_selection_changed)
        
        # Rapor butonları
        self.generate_report_btn.clicked.connect(self.handle_design_report)
        self.export_results_btn.clicked.connect(self.export_results)

    def _populate_unit_combos(self):
        """Birim combobox'larını doldur"""
        self.logger.info("Birim/Kütüphane Combobox'ları güncelleniyor...")
        all_turbines = self.db.get_all_turbines_full_data()
        all_compressors = self.db.get_all_compressors_full_data()
        self.logger.info(f"Kütüphanede {len(all_turbines)} türbin ve {len(all_compressors)} kompresör bulundu.")

    def _setup_unit_tooltips(self):
        pass

    def _update_method_options(self):
        pass

    def _update_button_state(self):
        pass

    def setup_basic_results_tab(self):
        """Temel sonuçlar sekmesi kurulumu - Satır içi birim seçiciler"""
        layout = QVBoxLayout(self.basic_results_tab)
        
        # Tutarlılık Modu Bilgi Kutusu (başlangıçta gizli)
        self.consistency_info_group = QGroupBox("🔄 Tutarlılık Modu Bilgisi")
        consistency_info_layout = QVBoxLayout()
        self.consistency_info_label = QLabel("Mod: Hızlı")
        self.consistency_info_label.setWordWrap(True)
        self.consistency_info_label.setStyleSheet("font-size: 10pt; padding: 5px;")
        consistency_info_layout.addWidget(self.consistency_info_label)
        self.consistency_info_group.setLayout(consistency_info_layout)
        self.consistency_info_group.setVisible(False)  # Başlangıçta gizli
        layout.addWidget(self.consistency_info_group)
        
        results_group = QGroupBox("🎯 Hesaplama Sonuçları")
        results_layout = QGridLayout()
        
        self.result_labels = {}
        self.result_unit_combos = {}  # Her sonuç için kendi combo'su
        
        # (Display Name, Key, Default Unit, Available Units)
        basic_results = [
            ('Çıkış Sıcaklığı', 't_out', '°C', ['°C', '°F', 'K']),
            ('Politropik Head', 'head_kj_kg', 'kJ/kg', ['kJ/kg', 'J/kg', 'Btu/lb', 'ft-lbf/lbm']),
            ('Sıkıştırma Oranı', 'compression_ratio', '', ['']),  # Birim yok
            ('Politropik Verim', 'actual_poly_efficiency', '%', ['%']),  # Kullanıcının girdiği Tasarım Verimi (T_out belirler)
            ('Motor Gücü (Ünite)', 'power_unit_kw', 'kW', ['kW', 'MW', 'hp']),
            ('Toplam Motor Gücü', 'power_unit_total_kw', 'kW', ['kW', 'MW', 'hp']),
            ('Isı Oranı', 'heat_rate', 'kJ/kWh', ['kJ/kWh', 'Btu/kWh', 'kcal/kWh']),
            ('Ünite Yakıt Tüketimi', 'fuel_unit_kgh', 'kg/h', ['kg/h', 'lb/h', 'Sm³/h', 'cal/h', 'J/h']),
            ('Toplam Yakıt Tüketimi', 'fuel_total_kgh', 'kg/h', ['kg/h', 'lb/h', 'Sm³/h', 'cal/h', 'J/h'])
        ]
        
        for i, (label, key, default_unit, available_units) in enumerate(basic_results):
            # Label
            results_layout.addWidget(QLabel(f"{label}:"), i, 0)
            
            # Value
            value_label = QLabel("-")
            value_label.setStyleSheet("font-weight: bold; color: #2c3e50; min-width: 80px;")
            value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            results_layout.addWidget(value_label, i, 1)
            self.result_labels[key] = value_label
            
            # Unit selector (inline)
            if len(available_units) > 1:  # Sadece birden fazla seçenek varsa
                unit_combo = QComboBox()
                unit_combo.addItems(available_units)
                unit_combo.setCurrentText(default_unit)
                unit_combo.setMaximumWidth(120)
                unit_combo.currentTextChanged.connect(lambda u, k=key: self._update_single_result_unit(k, u))
                results_layout.addWidget(unit_combo, i, 2)
                self.result_unit_combos[key] = unit_combo
            else:  # Birim sabit veya yok
                unit_label = QLabel(default_unit)
                results_layout.addWidget(unit_label, i, 2)
        
        results_group.setLayout(results_layout)
        layout.addWidget(results_group)
        
        summary_group = QGroupBox("📊 Performans Özeti")
        summary_layout = QVBoxLayout()
        
        self.summary_text = QTextEdit()
        self.summary_text.setMaximumHeight(150)
        self.summary_text.setReadOnly(True)
        summary_layout.addWidget(self.summary_text)
        
        summary_group.setLayout(summary_layout)
        layout.addWidget(summary_group)
        
        quick_actions_group = QGroupBox("⚡ Hızlı İşlemler")
        quick_layout = QHBoxLayout()
        
        self.export_results_btn = QPushButton("📤 Sonuçları Dışa Aktar")
        self.generate_report_btn = QPushButton("📋 Rapor Oluştur")
        self.save_project_btn = QPushButton("💾 Projeyi Kaydet")
        
        quick_layout.addWidget(self.export_results_btn)
        quick_layout.addWidget(self.generate_report_btn)
        quick_layout.addWidget(self.save_project_btn)
        
        quick_actions_group.setLayout(quick_layout)
        layout.addWidget(quick_actions_group)
        layout.addStretch()


    def setup_turbine_selection_tab(self):
        """Türbin seçimi sekmesi kurulumu"""
        layout = QVBoxLayout(self.turbine_selection_tab)
        
        self.turbine_table = QTableWidget()
        self.turbine_table.setColumnCount(8)
        self.turbine_table.setHorizontalHeaderLabels([
            'Sıra', 'Türbin', 'Güç (kW)', 'Isı Oranı', 'Verimlilik', 
            'Surge Margin', 'Seçim Puanı', 'Öneri'
        ])
        
        header = self.turbine_table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        
        layout.addWidget(QLabel("🚀 Önerilen Türbinler:"))
        layout.addWidget(self.turbine_table)
        
        detail_group = QGroupBox("👁️ Türbin Detayları")
        detail_layout = QFormLayout()
        
        self.selected_turbine_label = QLabel("Türbin seçin...")
        self.turbine_power_label = QLabel("-")
        self.turbine_efficiency_label = QLabel("-")
        self.turbine_margin_label = QLabel("-")
        self.turbine_recommendation_label = QLabel("-")
        
        detail_layout.addRow("Seçilen Türbin:", self.selected_turbine_label)
        detail_layout.addRow("Mevcut Güç:", self.turbine_power_label)
        detail_layout.addRow("Verimlilik:", self.turbine_efficiency_label)
        detail_layout.addRow("Güç Marjı:", self.turbine_margin_label)
        detail_layout.addRow("Öneri:", self.turbine_recommendation_label)
        
        detail_group.setLayout(detail_layout)
        layout.addWidget(detail_group)

    def setup_detailed_results_tab(self):
        """Detaylı sonuçlar sekmesi kurulumu"""
        layout = QVBoxLayout(self.detailed_results_tab)
        tabs = QTabWidget()
        
        thermo_tab = QWidget()
        thermo_layout = QVBoxLayout(thermo_tab)
        self.thermo_table = QTableWidget()
        self.thermo_table.setColumnCount(5)
        self.thermo_table.setHorizontalHeaderLabels(['Özellik', 'Giriş', 'Çıkış', 'Birim', 'Değişim'])
        thermo_layout.addWidget(self.thermo_table)
        tabs.addTab(thermo_tab, "🌡️ Termodinamik")
        
        power_tab = QWidget()
        power_layout = QVBoxLayout(power_tab)
        self.power_table = QTableWidget()
        self.power_table.setColumnCount(3)
        self.power_table.setHorizontalHeaderLabels(['Parametre', 'Ünite Başına', 'Toplam'])
        power_layout.addWidget(self.power_table)
        tabs.addTab(power_tab, "⚡ Güç Dağılımı")
        
        fuel_tab = QWidget()
        fuel_layout = QVBoxLayout(fuel_tab)
        self.fuel_table = QTableWidget()
        self.fuel_table.setColumnCount(2)
        self.fuel_table.setHorizontalHeaderLabels(['Parametre', 'Değer'])
        fuel_layout.addWidget(self.fuel_table)
        tabs.addTab(fuel_tab, "⛽ Yakıt Analizi")
        
        layout.addWidget(tabs)

    def setup_graphs_tab(self):
        """Grafikler sekmesi kurulumu"""
        layout = QVBoxLayout(self.graphs_tab)
        
        graph_selection_layout = QHBoxLayout()
        graph_selection_layout.addWidget(QLabel("Grafik:"))
        
        self.graph_combo = QComboBox()
        self.graph_combo.addItems([
            "T-s Diyagramı", "P-v Diyagramı", "Güç Dağılımı",
            "Türbin Performansı", "Yakınsama Grafiği"
        ])
        graph_selection_layout.addWidget(self.graph_combo)
        
        self.refresh_graph_btn = QPushButton("🔄 Grafiği Yenile")
        graph_selection_layout.addWidget(self.refresh_graph_btn)
        
        self.save_graph_btn = QPushButton("💾 Grafiği Kaydet")
        graph_selection_layout.addWidget(self.save_graph_btn)
        
        graph_selection_layout.addStretch()
        layout.addLayout(graph_selection_layout)
        
        self.graph_widget = QWidget()
        self.graph_layout = QVBoxLayout(self.graph_widget)
        layout.addWidget(self.graph_widget)
        
        self.default_graph_label = QLabel("🚀 Hesaplama yapıldıktan sonra grafikler burada görüntülenecek")
        self.default_graph_label.setAlignment(Qt.AlignCenter)
        self.default_graph_label.setStyleSheet("font-size: 16px; color: #7f8c8d; padding: 50px;")
        self.graph_layout.addWidget(self.default_graph_label)

    def on_gas_selection_changed(self, gas_name):
        """Gaz seçimi değiştiğinde"""
        if gas_name != 'Özel Karışım':
            self.load_standard_gas_composition(gas_name)

    def load_standard_gas_composition(self, gas_name):
        """Standart gaz kompozisyonunu yükle"""
        standard_compositions = {
            'Methane (CH₄)': {'METHANE': 100},
            'Ethane (C₂H₆)': {'ETHANE': 100},
            'Propane (C₃H₈)': {'PROPANE': 100},
            'Nitrogen (N₂)': {'NITROGEN': 100},
            'Carbon Dioxide (CO₂)': {'CARBONDIOXIDE': 100},
            'Hydrogen (H₂)': {'HYDROGEN': 100},
            'Su (H₂O)': {'WATER': 100},
            'Air': {'NITROGEN': 78.0, 'OXYGEN': 21.0, 'ARGON': 1.0}
        }
        
        composition = standard_compositions.get(gas_name)
        if composition is None:
            composition = {'METHANE': 85.0, 'ETHANE': 8.0, 'PROPANE': 4.0, 'BUTANE': 2.0, 'NITROGEN': 1.0}

        self.composition_table.setRowCount(len(composition))
        
        for i, (component_key, percentage) in enumerate(composition.items()):
            display_name = self.COOLPROP_GAS_MAP.get(component_key, component_key) 
            
            combo = QComboBox()
            combo.addItems(self.COMMON_COMPONENTS_DISPLAY)
            if display_name in self.COMMON_COMPONENTS_DISPLAY:
                combo.setCurrentText(display_name)
            self.composition_table.setCellWidget(i, 0, combo)
            
            self.composition_table.setItem(i, 1, QTableWidgetItem(str(percentage)))

    def add_component_row(self):
        """Bileşen satırı ekle"""
        row_count = self.composition_table.rowCount()
        self.composition_table.insertRow(row_count)
        
        combo = QComboBox()
        combo.addItems(self.COMMON_COMPONENTS_DISPLAY)
        self.composition_table.setCellWidget(row_count, 0, combo)
        
        self.composition_table.setItem(row_count, 1, QTableWidgetItem("0"))

    def remove_component_row(self):
        """Bileşen satırı sil"""
        current_row = self.composition_table.currentRow()
        if current_row >= 0:
            self.composition_table.removeRow(current_row)

    def _update_composition_total_label(self):
        """Gaz kompozisyon toplamını hesaplar ve canlı etiketi günceller."""
        try:
            total = 0.0
            for row in range(self.composition_table.rowCount()):
                item = self.composition_table.item(row, 1)
                if item:
                    try:
                        val = float(item.text().replace(',', '.'))
                        if val > 0:
                            total += val
                    except ValueError:
                        pass
            
            diff = abs(total - 100.0)
            if diff < 0.01:
                self.comp_total_label.setText(f"Toplam: {total:.2f}%  ✔")
                self.comp_total_label.setStyleSheet(
                    "font-weight: bold; color: #27ae60; padding: 2px 4px; border-radius: 4px;"
                )
            elif diff < 1.0:
                self.comp_total_label.setText(f"Toplam: {total:.2f}%  ⚠ (%100'e yakın)")
                self.comp_total_label.setStyleSheet(
                    "font-weight: bold; color: #e67e22; padding: 2px 4px; border-radius: 4px; background: #fef9e7;"
                )
            else:
                self.comp_total_label.setText(f"Toplam: {total:.2f}%  ✘ (100.00% olmalı!)")
                self.comp_total_label.setStyleSheet(
                    "font-weight: bold; color: #c0392b; padding: 2px 4px; border-radius: 4px; background: #fdf0ef;"
                )
        except Exception as e:
            self.logger.warning(f"Kompozisyon toplamı güncellenemedi: {e}")

    def normalize_composition(self):
        """Kompozisyonu normalize et — toplam %100'e göre her satırı ölçekler."""
        try:
            total = 0.0
            values = []
            for row in range(self.composition_table.rowCount()):
                item = self.composition_table.item(row, 1)
                if item:
                    try:
                        val = float(item.text().replace(',', '.'))
                        values.append((row, max(0.0, val)))
                        total += max(0.0, val)
                    except ValueError:
                        values.append((row, 0.0))
                else:
                    values.append((row, 0.0))
            
            if total <= 0:
                QMessageBox.warning(self, "Normalize Hatası",
                                    "Tüm bileşen yüzdeleri sıfır veya boş. Normalize edilecek değer yok.")
                return
            
            # Her satırı ölçekle
            for row, val in values:
                normalized_val = (val / total) * 100.0
                self.composition_table.setItem(row, 1, QTableWidgetItem(f"{normalized_val:.4f}"))
            
            self._update_composition_total_label()
            QMessageBox.information(self, "Başarılı",
                f"Gaz kompozisyonu normalize edildi.\nToplam {total:.2f}% → 100.00%")
        except Exception as e:
            self.logger.error(f"Normalize hatası: {e}")
            QMessageBox.critical(self, "Hata", f"Normalize edilemedi: {e}")

    def _get_gas_composition(self):
        """Gaz kompozisyon tablosundan bileşen adı → yüzde sözlüğü döndürür.
        
        Hem Tasarım hem de Performans sekmelerinde ortak kullanılır.
        """
        gas_comp = {}
        for row in range(self.composition_table.rowCount()):
            component_combo = self.composition_table.cellWidget(row, 0)
            percentage_item = self.composition_table.item(row, 1)
            
            if component_combo and percentage_item:
                display_name = component_combo.currentText().strip()
                percentage_str = percentage_item.text().strip().replace(',', '.')
                
                if not display_name or not percentage_str:
                    continue
                
                try:
                    percentage = float(percentage_str)
                    if percentage <= 0:
                        continue
                    comp_key = self.DISPLAY_TO_COOLPROP_KEY.get(display_name, display_name.upper())
                    gas_comp[comp_key] = percentage
                except ValueError:
                    continue
        
        return gas_comp

    def _get_design_inputs(self):
        """UI'dan tüm kullanıcı girdilerini okur"""
        inputs = {}
        errors = []
        
        try:
            inputs['project_name'] = self.project_name_edit.text()
            inputs['notes'] = self.project_notes_edit.toPlainText()
            
            inputs['p_in'] = self.p_in_edit.text()
            inputs['p_in_unit'] = self.p_in_unit_combo.currentText()
            inputs['t_in'] = self.t_in_edit.text()
            inputs['t_in_unit'] = self.t_in_unit_combo.currentText()
            inputs['p_out'] = self.p_out_edit.text()
            inputs['p_out_unit'] = self.p_out_unit_combo.currentText()
            inputs['flow'] = self.flow_edit.text()
            inputs['flow_unit'] = self.flow_unit_combo.currentText()
            inputs['num_units'] = self.num_units_spin.value()
            inputs['num_stages'] = self.num_stages_spin.value()
            inputs['intercooler_dp_pct'] = self.ic_dp_spin.value() if self.num_stages_spin.value() > 1 else 0.0
            try:
                inputs['intercooler_t'] = float(self.ic_temp_edit.text()) if self.num_stages_spin.value() > 1 else 40.0
            except ValueError:
                inputs['intercooler_t'] = 40.0
            
            selected_eos_text = self.eos_method_combo.currentText()
            if 'CoolProp' in selected_eos_text:
                inputs['eos_method'] = 'coolprop'
            elif 'Peng-Robinson' in selected_eos_text:
                inputs['eos_method'] = 'pr'
            elif 'SRK' in selected_eos_text:
                inputs['eos_method'] = 'srk'
            elif 'Kütüphane Yok' in selected_eos_text:
                errors.append("EOS Hatası: Geçerli bir EOS metodu seçiniz (Kütüphane yüklü değil).")
            else:
                inputs['eos_method'] = selected_eos_text.lower()
                if inputs['eos_method'] not in ['coolprop', 'pr', 'srk']:
                    errors.append(f"EOS Hatası: Bilinmeyen veya yanlış eşleşen EOS metodu: {selected_eos_text}")

            inputs['method'] = self.method_combo.currentText()
            
            selected_lhv = self.lhv_source_combo.currentText()
            inputs['lhv_source'] = 'thermo' if 'Thermo' in selected_lhv else 'kasp'
            
            try:
                inputs['poly_eff'] = float(self.poly_eff_edit.text())
                inputs['therm_eff'] = float(self.therm_eff_edit.text())
                inputs['mech_eff'] = float(self.mech_eff_edit.text())
            except ValueError:
                errors.append("Verimlilik değerleri (Politropik, Isıl, Mekanik) sayısal olmalıdır.")
            
            # Tutarlılık Modu Ayarları
            inputs['use_consistency_iteration'] = self.consistency_check.isChecked()
            inputs['max_consistency_iter'] = self.max_consistency_iter.value()
            inputs['consistency_tolerance'] = self.consistency_tolerance.value()

            gas_comp = self._get_gas_composition()
            total_percentage = sum(gas_comp.values())
            
            if not gas_comp:
                errors.append("Gaz kompozisyonu tanımlanmalıdır.")
            
            if abs(total_percentage - 100.0) > 1.0:
                self.logger.warning(f"Kompozisyon toplamı %100'den farklı (%{total_percentage:.2f}). Engine normalize edecek.")  # noqa: E501
                # V4.6: Kullanıcıya uyarı göster
                reply = QMessageBox.warning(
                    self, "⚠ Gaz Kompozisyonu Toplamı",
                    f"Gaz bileşenlerinin toplamı <b>%{total_percentage:.2f}</b> — bu değer %100 olmalıdır.<br><br>"
                    "Hesabı yine de devam ettirmek istiyor musunuz? "
                    "(Motor otomatik olarak normalize edecektir.)",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                if reply == QMessageBox.No:
                    return None
                
            inputs['gas_comp'] = gas_comp
            
            inputs['ambient_temp'] = float(self.t_in_edit.text())
            inputs['ambient_press'] = 1013
            inputs['altitude'] = 0
            inputs['humidity'] = 60

            if errors:
                raise ValueError("\n".join(errors))
                
            return inputs
            
        except ValueError as e:
            QMessageBox.critical(self, "Girdi Hatası", f"Lütfen tüm zorunlu alanları kontrol edin:\n{e}")
            return None
        except Exception as e:
            self.logger.error(f"Girdi toplama sırasında beklenmeyen hata: {e}")
            QMessageBox.critical(self, "Sistem Hatası", "Girdi toplama sırasında beklenmeyen bir hata oluştu.")
            return None

    def run_calculation(self):
        """Tasarım hesaplamasını başlatır"""
        if self.worker_thread is not None and self.worker_thread.isRunning():
            QMessageBox.warning(self, "Uyarı", "Zaten bir hesaplama çalışıyor. Lütfen bekleyin veya durdurun.")
            return

        # V4.6: Doğrulama pop-up — geçersiz alan varsa kullanıcıya göster ve dur
        if not self._show_validation_popup():
            return

        inputs = self._get_design_inputs()
        if inputs is None:
            return

        self.worker_thread = QThread()
        all_turbines = self.db.get_all_turbines_full_data()
        
        self.worker = CalculationWorker(self.engine, inputs, all_turbines)
        self.worker.moveToThread(self.worker_thread)
        
        
        self.worker_thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.calculation_finished)
        self.worker.error.connect(self.calculation_error)
        self.worker.progress.connect(self.progress_bar.setValue)  # Legacy
        
        # Task 4: Enhanced progress signals
        self.worker.progress_detailed.connect(self.update_progress_detailed)
        self.worker.time_remaining.connect(self.update_time_estimate)
        self.worker.cancelled.connect(self.calculation_cancelled)
        
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.error.connect(self.worker_thread.quit)
        self.worker.cancelled.connect(self.worker_thread.quit)
        
        # UI state
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.progress_status_label.setVisible(True)
        self.progress_status_label.setText("Initializing...")
        self.progress_time_label.setVisible(True)
        self.progress_time_label.setText("Estimating time...")
        
        self.calculate_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        
        self.logger.info(f"Hesaplama başlatılıyor: {inputs['project_name']} (Metod: {inputs['method']})")
        self.worker_thread.start()

    def calculation_finished(self, results_raw, selected_units):
        """Hesaplama tamamlandığında sonuçları işler"""
        self.calculate_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        
        # Task 4: Hide progress widgets
        self.progress_bar.setVisible(False)
        self.progress_bar.setValue(100)
        self.progress_status_label.setVisible(False)
        self.progress_time_label.setVisible(False)
        
        self.last_design_inputs = self._get_design_inputs()
        self.last_design_results_raw = results_raw
        self.last_selected_units = selected_units
        
        self._update_results_ui(results_raw, selected_units)
        
        self.db.save_calculation_history(
            self.last_design_inputs['project_name'], 
            'Tasarım', 
            self.last_design_inputs, 
            results_raw, 
            self.last_design_inputs['notes']
        )
        QMessageBox.information(self, "Başarılı", "✅ Tasarım hesaplaması başarıyla tamamlandı!")

    def calculation_error(self, error_message):
        """Hesaplama hatası oluştuğunda"""
        self.calculate_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        
        # Task 4: Hide progress widgets
        self.progress_bar.setVisible(False)
        self.progress_status_label.setVisible(False)
        self.progress_time_label.setVisible(False)
        QMessageBox.critical(self, "Hesaplama Hatası", f"❌ Hesaplama başarısız oldu:\n{error_message}")
        self.logger.error(f"Hesaplama hatası: {error_message}")
    
    def stop_calculation(self):
        """Hesaplamayı durdurur - Task 4: Graceful cancellation"""
        if self.worker is not None:
            self.worker.request_cancel()
            self.stop_btn.setEnabled(False)
            self.stop_btn.setText("⏳ Cancelling...")
            self.logger.warning("Calculation cancellation requested by user")
    
    # Task 4: New handler methods for enhanced progress tracking
    def update_progress_detailed(self, percentage, message):
        """Update progress bar and status message"""
        self.progress_bar.setValue(percentage)
        self.progress_status_label.setText(message)
        self.logger.debug(f"Progress: {percentage}% - {message}")
    
    def update_time_estimate(self, seconds):
        """Update estimated time remaining"""
        if seconds < 60:
            time_str = f"~{int(seconds)}s remaining"
        else:
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            time_str = f"~{minutes}m {secs}s remaining"
        
        self.progress_time_label.setText(time_str)
    
    def calculation_cancelled(self):
        """Handle calculation cancellation"""
        self.calculate_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setText("⏹️ Durdur")
        
        # Hide progress widgets
        self.progress_bar.setVisible(False)
        self.progress_status_label.setVisible(False)
        self.progress_time_label.setVisible(False)
        
        self.logger.info("✋ Calculation cancelled by user")
        QMessageBox.information(self, "Cancelled", "⏹️ Calculation was cancelled successfully.")

    def _update_results_ui(self, results, selected_units):
        """Sonuçları arayüze yansıtır - Satır içi birimlerle"""
        if not results:
            return
        
        # Önce ham sonuçları kaydet
        self.last_raw_results = results
        
        # Tutarlılık modu bilgisini göster
        if results.get('consistency_mode', False):
            self.consistency_info_group.setVisible(True)
            
            converged_icon = "✓" if results.get('consistency_converged', False) else "⚠️"
            info_text = (
                f"<b>Mod:</b> Tutarlı (Self-Consistent) {converged_icon}<br>"
                f"<b>Hedef Verim:</b> {results['poly_eff_target']:.2f}%<br>"
                f"<b>Yakınsanan Verim:</b> {results['poly_eff_converged']:.2f}%<br>"
                f"<b>Hesaplanan Verim:</b> {results['actual_poly_efficiency']*100:.2f}%<br>"
                f"<b>İterasyon:</b> {results['consistency_iterations']}<br>"
                f"<b>Final Residual:</b> {results['final_residual']:.4f}%"
            )
            if not results.get('consistency_converged', False):
                info_text += "<br><span style='color:orange;'>⚠️ Maksimum iter aşıldı!</span>"
            
            self.consistency_info_label.setText(info_text)
        else:
            self.consistency_info_group.setVisible(False)
        
        # Her sonucu kendi seçili birimi ile göster
        for key, label in self.result_labels.items():
            if key in results:
                value = results[key]
                
                # Seçili birimi al (eğer combo varsa)
                if key in self.result_unit_combos:
                    current_unit = self.result_unit_combos[key].currentText()
                    # İlk gösterimde dönüştür
                    self._update_single_result_unit(key, current_unit)
                else:
                    # Birim sabit olan sonuçlar
                    if key == 'compression_ratio':
                       label.setText(f"{value:.2f}")
                    elif key == 'actual_poly_efficiency':
                        label.setText(f"{value * 100:.2f}")
                    else:
                        label.setText(f"{value:.1f}")

            
        summary = self.engine.generate_summary_report(self.last_design_inputs, results, selected_units)
        
        # Tutarlılık moduna göre farklı özet
        if results.get('consistency_mode', False):
            converged_text = "✓ Yakınsadı" if results.get('consistency_converged') else "⚠️ Max iter aşıldı"
            summary_text = (
                f"🔄 Mod: Tutarlı (Self-Consistent)\n"
                f"Proje: {summary['project_name']}\n"
                f"Hedef Verim: {results['poly_eff_target']:.1f}% → "
                f"Yakınsanan: {results['poly_eff_converged']:.1f}% "
                f"({converged_text}, {results['consistency_iterations']} iter)\n"
                f"Sıkıştırma Oranı: {summary['basic_parameters']['compression_ratio']:.2f}\n"
                f"Toplam Güç: {summary['basic_parameters']['total_power']:.0f} kW ({summary['basic_parameters']['num_units']} Ünite)\n"
                f"Önerilen Türbin: {summary['recommended_turbines'][0]['turbine'] if summary['recommended_turbines'] else 'Yok'}"
            )
        else:
            summary_text = (
                f"⚡ Mod: Hızlı\n"
                f"Proje: {summary['project_name']}\n"
                f"Sıkıştırma Oranı: {summary['basic_parameters']['compression_ratio']:.2f}\n"
                f"Politropik Verim (Girdi): {summary['efficiency_metrics']['poly_efficiency']*100:.1f}%\n"
                f"Toplam Güç İhtiyacı: {summary['basic_parameters']['total_power']:.0f} kW ({summary['basic_parameters']['num_units']} Ünite)\n"
                f"Önerilen Türbin: {summary['recommended_turbines'][0]['turbine'] if summary['recommended_turbines'] else 'Yok'}"
            )
        self.summary_text.setText(summary_text)

        self._populate_detailed_tables(results)
        self.graph_manager.generate_all_graphs(self.last_design_inputs, results, selected_units)
        self.refresh_current_graph()
        self._populate_turbine_table(selected_units)

    def _update_single_result_unit(self, key, new_unit):
        """Tek bir sonucun birimini değiştirir"""
        if not hasattr(self, 'last_raw_results') or not self.last_raw_results:
            return
        
        results = self.last_raw_results
        if key not in results or key not in self.result_labels:
            return
        
        value = results.get(key, 0)
        
        # Birim türünü belirle ve dönüştür
        if key in ['power_unit_kw', 'power_unit_total_kw']:
            converted = self.engine.convert_result_value(value, 'kW', new_unit, 'power')
            self.result_labels[key].setText(f"{converted:.0f}")
        elif key == 'head_kj_kg':
            converted = self.engine.convert_result_value(value, 'kJ/kg', new_unit, 'head')
            self.result_labels[key].setText(f"{converted:.2f}")
        elif key == 'heat_rate':
            converted = self.engine.convert_result_value(value, 'kJ/kWh', new_unit, 'heat_rate')
            self.result_labels[key].setText(f"{converted:.0f}")
        elif key == 't_out':
            converted = self.engine.convert_result_value(value, '°C', new_unit, 'temperature')
            self.result_labels[key].setText(f"{converted:.1f}")
        elif key in ['fuel_total_kgh', 'fuel_unit_kgh']:
            # kg/h → lb/h, Sm³/h, cal/h, J/h
            if new_unit == 'lb/h':
                converted = value / 0.45359237
                self.result_labels[key].setText(f"{converted:.0f}")
            elif new_unit == 'Sm³/h':
                # Volume-based conversion requires fuel gas density at standard conditions
                # Standard conditions: 15°C (288.15 K), 1 atm (101325 Pa)
                fuel_gas_density_std = results.get('fuel_gas_density_std', None)
                if fuel_gas_density_std and fuel_gas_density_std > 0:
                    # kg/h / (kg/m³) = m³/h
                    converted = value / fuel_gas_density_std
                    self.result_labels[key].setText(f"{converted:.1f}")
                else:
                    # Fallback: use typical natural gas density (~0.75 kg/Sm³)
                    converted = value / 0.75
                    self.result_labels[key].setText(f"{converted:.1f} (est)")
            elif new_unit == 'cal/h' or new_unit == 'J/h':
                # Energy-based conversion requires LHV
                lhv_kj_kg = results.get('lhv', None)  # Fix: 'lhv' is the correct key
                if lhv_kj_kg and lhv_kj_kg > 0:
                    # kg/h * kJ/kg = kJ/h
                    energy_kj_h = value * lhv_kj_kg
                    if new_unit == 'cal/h':
                        # 1 kJ = 239.006 cal
                        converted = energy_kj_h * 239.006
                        self.result_labels[key].setText(f"{converted:.2e}")
                    else:  # J/h
                        # 1 kJ = 1000 J
                        converted = energy_kj_h * 1000
                        self.result_labels[key].setText(f"{converted:.2e}")
                else:
                    self.result_labels[key].setText("LHV Yok")
            else:  # kg/h (default)
                self.result_labels[key].setText(f"{value:.0f}")


    def _populate_turbine_table(self, selected_units):
        """Türbin seçim tablosunu doldurur"""
        self.turbine_table.setRowCount(len(selected_units))
        for row, unit in enumerate(selected_units):
            self.turbine_table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
            self.turbine_table.setItem(row, 1, QTableWidgetItem(unit.turbine_name))
            self.turbine_table.setItem(row, 2, QTableWidgetItem(f"{unit.available_power_kw:.0f}"))
            self.turbine_table.setItem(row, 3, QTableWidgetItem(f"{unit.site_heat_rate:.0f}"))
            self.turbine_table.setItem(row, 4, QTableWidgetItem(unit.efficiency_rating))
            self.turbine_table.setItem(row, 5, QTableWidgetItem(f"{unit.surge_margin_percent:.1f}%"))
            self.turbine_table.setItem(row, 6, QTableWidgetItem(f"{unit.selection_score:.1f}"))
            self.turbine_table.setItem(row, 7, QTableWidgetItem(unit.recommendation_level))


    def _populate_detailed_tables(self, results):
        """Detaylı sonuç tablolarını doldurur"""
        self.thermo_table.setRowCount(6)
        thermo_props = ['Z', 'rho', 'k', 'Cp', 'mu', 'a']
        units = ['-', 'kg/m³', '-', 'J/kg-K', 'Pa-s', 'm/s']
        display_names = ['Z Faktörü', 'Yoğunluk', 'İz. Üs (k)', 'Cp', 'Viskozite', 'Ses Hızı']
        
        in_props = results['inlet_properties']
        out_props = results['outlet_properties']
        
        for i, (prop, unit, name) in enumerate(zip(thermo_props, units, display_names)):
            val_in = in_props.get(prop, 0)
            val_out = out_props.get(prop, 0)
            change = ((val_out - val_in) / val_in) * 100 if val_in != 0 else 0
            
            self.thermo_table.setItem(i, 0, QTableWidgetItem(name))
            self.thermo_table.setItem(i, 1, QTableWidgetItem(f"{val_in:.4e}" if prop in ['mu', 'rho', 'Cp'] else f"{val_in:.3f}"))
            self.thermo_table.setItem(i, 2, QTableWidgetItem(f"{val_out:.4e}" if prop in ['mu', 'rho', 'Cp'] else f"{val_out:.3f}"))
            self.thermo_table.setItem(i, 3, QTableWidgetItem(unit))
            self.thermo_table.setItem(i, 4, QTableWidgetItem(f"{change:+.1f}%"))

        self.power_table.setRowCount(4)
        power_data = [
            ('Gaz Gücü', results['power_gas_per_unit_kw'], results['power_gas_total_kw']),
            ('Şaft Gücü', results['power_shaft_per_unit_kw'], results['power_shaft_total_kw']),
            ('Motor Gücü (Gerekli)', results['power_unit_kw'], results['power_unit_total_kw']),
            ('Mekanik Kayıp', results['mech_loss_per_unit_kw'], results['mech_loss_total_kw'])
        ]
        
        for i, (name, per_unit, total) in enumerate(power_data):
            self.power_table.setItem(i, 0, QTableWidgetItem(name))
            self.power_table.setItem(i, 1, QTableWidgetItem(f"{per_unit:.0f} kW"))
            self.power_table.setItem(i, 2, QTableWidgetItem(f"{total:.0f} kW"))

        self.fuel_table.setRowCount(3)
        self.fuel_table.setItem(0, 0, QTableWidgetItem("LHV"))
        self.fuel_table.setItem(0, 1, QTableWidgetItem(f"{results['lhv']:.0f} kJ/kg"))
        self.fuel_table.setItem(1, 0, QTableWidgetItem("HHV"))
        self.fuel_table.setItem(1, 1, QTableWidgetItem(f"{results['hhv']:.0f} kJ/kg"))
        self.fuel_table.setItem(2, 0, QTableWidgetItem("Toplam Yakıt Akışı"))
        self.fuel_table.setItem(2, 1, QTableWidgetItem(f"{results['fuel_total_kgh']:.1f} kg/h"))

    def on_turbine_selection_changed(self):
        """Türbin tablosunda seçim değiştiğinde detayları gösterir"""
        selected_rows = self.turbine_table.selectedItems()
        if not selected_rows or not self.last_selected_units:
            return
            
        row = selected_rows[0].row()
        unit = self.last_selected_units[row]
        
        self.selected_turbine_label.setText(unit['turbine'])
        self.turbine_power_label.setText(f"{unit['available_power_kw']:.0f} kW (ISO: {unit['iso_power']:.0f} kW)")
        self.turbine_efficiency_label.setText(f"Isı Oranı: {unit['site_heat_rate']:.0f} kJ/kWh ({unit['efficiency_rating']})")
        self.turbine_margin_label.setText(f"Güç: {unit['power_margin_percent']:.1f}%, Surge: {unit['surge_margin']:.1f}%")
        self.turbine_recommendation_label.setText(unit['recommendation_level'])

    def refresh_current_graph(self):
        """Seçili grafiği yeniler"""
        current_graph_name = self.graph_combo.currentText()
        
        for i in reversed(range(self.graph_layout.count())):
            item = self.graph_layout.takeAt(i)
            widget = item.widget()
            if widget and widget is not self.default_graph_label:
                widget.setParent(None)
                
        self.default_graph_label.setVisible(True)
        
        if self.last_design_results_raw and self.graph_manager.current_graphs:
            self.default_graph_label.setVisible(False)
            
            graph_map = {
                "T-s Diyagramı": 'ts_diagram',
                "P-v Diyagramı": 'pv_diagram', 
                "Güç Dağılımı": 'power_breakdown',
                "Türbin Performansı": 'performance_comparison',
                "Yakınsama Grafiği": 'convergence'
            }
            
            graph_key = graph_map.get(current_graph_name)
            canvas = self.graph_manager.current_graphs.get(graph_key)
            
            if canvas:
                self.default_graph_label.setVisible(False) 
                self.graph_layout.addWidget(canvas)
            else:
                self.default_graph_label.setText(f"Grafik verisi mevcut değil veya kütüphane ({current_graph_name}) yüklü değil.")
                self.default_graph_label.setVisible(True)

    def save_current_graph(self):
        """Mevcut grafiği dosyaya kaydeder"""
        if not self.last_design_results_raw:
            QMessageBox.warning(self, "Uyarı", "Önce bir hesaplama yapın.")
            return

        current_graph_name = self.graph_combo.currentText()
        graph_map = {
            "T-s Diyagramı": 'ts_diagram',
            "P-v Diyagramı": 'pv_diagram', 
            "Güç Dağılımı": 'power_breakdown',
            "Türbin Performansı": 'performance_comparison',
            "Yakınsama Grafiği": 'convergence'
        }
        graph_key = graph_map.get(current_graph_name)

        if not self.graph_manager.current_graphs.get(graph_key):
            QMessageBox.warning(self, "Uyarı", f"'{current_graph_name}' grafiği oluşturulmamış veya boş.")
            return

        try:
            file_path, _ = QFileDialog.getSaveFileName(
                self, f"Grafiği Kaydet - {current_graph_name}",
                f"{self.project_name_edit.text().replace(' ', '_')}_{graph_key}.png",
                "PNG Files (*.png)"
            )
            
            if file_path:
                canvas = self.graph_manager.current_graphs[graph_key]
                if hasattr(canvas, 'fig'):
                    canvas.fig.savefig(file_path, dpi=300, bbox_inches='tight')
                    self.logger.info(f"Grafik kaydedildi: {file_path}")
                    QMessageBox.information(self, "Başarılı", f"✅ Grafik başarıyla kaydedildi:\n{file_path}")
                else:
                    QMessageBox.warning(self, "Hata", "Grafik objesi geçerli değil.")
        except Exception as e:
            self.logger.error(f"Grafik kaydetme hatası: {e}")
            QMessageBox.critical(self, "Hata", f"Grafik kaydedilirken hata oluştu: {e}")

    def handle_design_report(self):
        """Tasarım raporu oluşturmayı yönetir"""
        if not self.last_design_results_raw or not self.last_design_inputs or not REPORTLAB_LOADED:
            if not REPORTLAB_LOADED:
                 QMessageBox.critical(self, "Hata", "Raporlama Kütüphanesi (ReportLab) yüklü değil.")
            else:
                 QMessageBox.warning(self, "Uyarı", "Önce başarılı bir tasarım hesaplaması yapın.")
            return
            
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Tasarım Raporunu Kaydet",
            f"{self.project_name_edit.text().replace(' ', '_')}_Tasarim_Raporu.pdf",
            "PDF Files (*.pdf)"
        )
        
        if file_path:
            try:
                report_units = {
                    'power_unit': 'kW', 'head_unit': 'kJ/kg', 'heat_rate': 'kJ/kWh',
                    'lhv': 'kJ/kg', 'hhv': 'kJ/kg', 'fuel_unit': 'kg/h'
                }
                
                reporter = ReportGenerator(file_path, self.engine)
                reporter.generate_design_report(
                    self.last_design_inputs, 
                    self.last_design_results_raw, 
                    self.last_selected_units, 
                    report_units
                )
                QMessageBox.information(self, "Başarılı", f"✅ Rapor başarıyla oluşturuldu:\n{file_path}")
                
            except Exception as e:
                self.logger.error(f"Rapor oluşturma hatası: {e}")
                QMessageBox.critical(self, "Hata", f"Rapor oluşturulurken hata oluştu: {e}")

    def export_results(self):
        """Sonuçları JSON olarak dışa aktarır"""
        if not self.last_design_results_raw:
            QMessageBox.warning(self, "Uyarı", "Önce bir hesaplama yapın.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Sonuçları Dışa Aktar",
            f"{self.project_name_edit.text().replace(' ', '_')}_Sonuclar.json",
            "JSON Files (*.json)"
        )
        
        if file_path:
            try:
                export_data = {
                    'inputs': self.last_design_inputs,
                    'results': self.last_design_results_raw,
                    'selected_units': self.last_selected_units,
                    'date': datetime.datetime.now().isoformat()
                }
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, indent=4, ensure_ascii=False, default=str)
                QMessageBox.information(self, "Başarılı", f"✅ Sonuçlar başarıyla dışa aktarıldı:\n{file_path}")
            except Exception as e:
                self.logger.error(f"Sonuç dışa aktarma hatası: {e}")
                QMessageBox.critical(self, "Hata", f"Sonuçlar dışa aktarılırken hata oluştu: {e}")

    def handle_performance_report(self):
        """Performans raporu oluşturmayı yönetir"""
        QMessageBox.information(self, "Bilgi", "Performans Değerlendirme raporu oluşturma fonksiyonu henüz tamamlanmadı.")

    def open_library_manager(self):
        """Kütüphane yöneticisini açar"""
        manager = LibraryManagerWindow(self)
        manager.exec_()
        if self.last_selected_units:
            self._populate_turbine_table(self.last_selected_units)
        self.logger.info("Kütüphane yöneticisi kapatıldı.")
        
    def clear_engine_cache(self):
        """Motor önbelleğini temizler"""
        self.engine.clear_cache()
        QMessageBox.information(self, "Başarılı", "✅ Termodinamik Özellik Önbelleği temizlendi.")

    def show_about_dialog(self):
        """Hakkında penceresini gösterir"""
        QMessageBox.about(self, f"KASP v{APP_VERSION} Hakkinda",
            f"KASP v{APP_VERSION} - Kompresor Analiz ve Secim Platformu\n\n"
            "Gelişmiş termodinamik, akışkan dinamiği ve turbomakine hesaplamaları için Python tabanlı platform.\n\n"
            "V4.6 Yenilikleri: Responsive UI, QScrollArea sol panel, DPI ölçeklendirme.\n\n"
            "Standartlar: ASME PTC-10, ASME PTC-22, API 616/617, ISO 2314"
        )
        
    def show_examples(self):
        """Örnekleri gösterir"""
        QMessageBox.information(self, "Örnekler", "Örnek projeler ilerleyen versiyonlarda eklenecektir.")

    def new_project(self):
        """Yeni proje başlatır"""
        self.project_name_edit.setText("Yeni Kompresör Projesi")
        self.project_notes_edit.clear()
        self.flow_edit.setText("1985000")
        self.p_in_edit.setText("49")
        self.p_out_edit.setText("75")
        self.summary_text.setText("-")
        self.last_design_results_raw = None
        self.last_selected_units = None
        self.logger.info("Yeni proje başlatıldı.")

    def save_project(self):
        """Projeyi kaydeder"""
        QMessageBox.information(self, "Kaydet", "Proje kaydetme fonksiyonu yakında eklenecektir.")
        
    def load_project(self):
        """Projeyi yükler"""
        QMessageBox.information(self, "Yükle", "Proje yükleme fonksiyonu yakında eklenecektir.")
        
    def clear_logs(self):
        """Logları temizler"""
        self.log_text.clear()
        self.all_logs = []
        self.logger.info("Sistem logları temizlendi.")
        
    def append_log(self, msg):
        """Log mesaj

ını arayüze ekler - Filtreleme ile"""
        # Store all logs
        self.all_logs.append(msg)
        
        # Filter and display
        selected_level = self.log_level_combo.currentText()
        if selected_level == 'TÜM LOGLAR' or selected_level in msg:
            self.log_text.append(msg)
    
    def _filter_logs(self, selected_level):
        """Log seviyesine göre filtreleme yapar"""
        self.log_text.clear()
        
        if selected_level == 'TÜM LOGLAR':
            for log in self.all_logs:
                self.log_text.append(log)
        else:
            for log in self.all_logs:
                if selected_level in log:
                    self.log_text.append(log)


    def run_performance_evaluation(self):
        """Mevcut saha verilerine dayanarak (T2 bilinen) performansı hesaplar"""
        try:
            eos_text = self.eos_method_combo.currentText()
            eos = 'coolprop' if 'CoolProp' in eos_text else ('pr' if 'Peng-Robinson' in eos_text else 'srk')
            gas_comp = self._get_gas_composition()
            
            # Toplam yüzde kontrolü (Tasarım sekmesine benzer)
            total_percentage = sum(gas_comp.values())
            if abs(total_percentage - 100.0) > 0.01:
                reply = QMessageBox.warning(self, "Uyarı", 
                    f"Gaz kompozisyonları toplamı %100 değil (Şu anki: %{total_percentage:.2f}).\nNormalizasyon yapılsın mı?",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
                if reply == QMessageBox.Yes:
                    self.normalize_composition()
                    gas_comp = self._get_gas_composition()
                else:
                    return

            gas_obj = self.engine._create_gas_object(gas_comp, eos)
            
            # Gerekli birimi al
            flow_unit = self.perf_flow_unit_combo.currentText()
            
            # Girdileri topla
            inputs = {
                'p1_pa': self.engine.convert_pressure_to_pa(float(self.perf_p1_edit.text()), 'bar(g)'),
                't1_k': self.engine.convert_temperature_to_k(float(self.perf_t1_edit.text()), '°C'),
                'p2_pa': self.engine.convert_pressure_to_pa(float(self.perf_p2_edit.text()), 'bar(g)'),
                't2_k': self.engine.convert_temperature_to_k(float(self.perf_t2_edit.text()), '°C'),
                'flow_kgs': self.engine.convert_flow_to_kgs(float(self.perf_flow_edit.text()), flow_unit, gas_obj, eos),
                'rpm': float(self.perf_rpm_edit.text()) if self.perf_rpm_edit.text() else 0.0,
                'mech_eff': float(self.perf_mech_eff_edit.text()),
                'driver_mode': 'turb_eff' if self.radio_turb_eff.isChecked() else 'fuel_cons',
                'driver_val': float(self.perf_turb_eff_edit.text() if self.radio_turb_eff.isChecked() else self.perf_fuel_cons_edit.text()),
                'gas_comp': gas_comp,
                'eos_method': eos,
                'lhv_source': 'thermo' if 'Thermo' in self.perf_lhv_source_combo.currentText() else 'kasp'
            }
            
            self.append_log("[INFO] Performans değerlendirmesi başlatıldı (ASME PTC 10).")
            results = self.engine.evaluate_performance(inputs)
            
            # UI'a yazdır
            self.perf_res_poly_eff.setText(f"%{results['poly_eff']:.2f}")
            self.perf_res_isen_eff.setText(f"%{results['isen_eff']:.2f}")
            self.perf_res_head.setText(f"{results['poly_head_kj_kg']:.1f}")
            self.perf_res_power_gas.setText(f"{results['gas_power_kw']:.0f}")
            # Yeni motor gücü / şaft gücü mantığı (motor gücünü şaft alanına yazalım, ya da yanına motor ibaresi koyalım)
            self.perf_res_power_shaft.setText(f"Motor: {results['motor_power_kw']:.0f} | Şaft: {results['shaft_power_kw']:.0f}")
            
            if self.radio_turb_eff.isChecked():
                self.perf_res_fuel_lbl.setText("Hesaplanan Yakıt [kg/h]:")
                self.perf_res_fuel_or_eff.setText(f"{results['fuel_cons_kg_h']:.1f}")
            else:
                self.perf_res_fuel_lbl.setText("Hesaplanan Türbin Verimi:")
                self.perf_res_fuel_or_eff.setText(f"%{results['turb_eff']:.1f}")
                
            self.append_log("[SUCCESS] Performans değerlendirmesi başarıyla tamamlandı.")
            
        except Exception as e:
            self.logger.error(f"Performans değerlendirme UI hatası: {e}")
            QMessageBox.critical(self, "Hata", f"Değerlendirme sırasında hata oluştu:\n{e}")


    # Phase 5: Project Save/Load Methods
    
    def new_project(self):
        """Yeni proje oluşturur - tüm alanları temizler"""
        reply = QMessageBox.question(
            self, 'Yeni Proje',
            'Mevcut projeyi temizlemek istediğinizden emin misiniz?',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Temizle
            self.project_name_edit.setText("Yeni Kompresör Projesi")
            self.project_notes_edit.clear()
            self.p_in_edit.setText("49.65")
            self.t_in_edit.setText("19")
            self.p_out_edit.setText("75")
            self.flow_edit.setText("1985000")
            self.poly_eff_edit.setText("90.0")
            self.therm_eff_edit.setText("35.0")
            self.mech_eff_edit.setText("98.0")
            self.consistency_check.setChecked(False)
            self.logger.info("Yeni proje oluşturuldu")
    
    def save_project(self):
        """Projeyi kaydet - tüm kullanıcı girdilerini JSON olarak"""
        try:
            # Dosya seç
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Projeyi Kaydet",
                "",
                "KASP Proje Dosyası (*.kasp);;Tüm Dosyalar (*)"
            )
            
            if not file_path:
                return
            
            # Mevcut inputları al
            inputs = self._get_design_inputs()
            
            # Kaydet
            success, message = self.project_manager.save_project(
                file_path,
                inputs,
                self.last_design_results_raw
            )
            
            if success:
                QMessageBox.information(
                    self,
                    "Başarılı",
                    f"✅ Proje kaydedildi:\n{message}"
                )
                self.logger.info(f"Proje kaydedildi: {file_path}")
            else:
                QMessageBox.critical(
                    self,
                    "Hata",
                    f"❌ Proje kaydedilemedi:\n{message}"
                )
                
        except Exception as e:
            self.logger.error(f"Proje kaydetme hatası: {e}", exc_info=True)
            QMessageBox.critical(self, "Hata", f"❌ Kaydetme hatası:\n{e}")
    
    def load_project(self):
        """Proje yükle - JSON dosyasından UI'yi doldur"""
        try:
            # Dosya seç
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Proje Aç",
                "",
                "KASP Proje Dosyası (*.kasp);;Tüm Dosyalar (*)"
            )
            
            if not file_path:
                return
            
            # Yükle
            success, inputs, results = self.project_manager.load_project(file_path)
            
            if not success:
                QMessageBox.critical(
                    self,
                    "Hata",
                    f"❌ Proje yüklenemedi:\n{inputs}"  # inputs = error message
                )
                return
            
            # UI'yi doldur
            self._populate_ui_from_inputs(inputs)
            
            # Sonuçlar varsa göster
            if results:
                self.last_design_results_raw = results
                self._update_results_ui(results, self.last_selected_units)
            
            QMessageBox.information(
                self,
                "Başarılı",
                f"✅ Proje yüklendi:\n{inputs.get('project_name', 'İsimsiz')}"
            )
            self.logger.info(f"Proje yüklendi: {file_path}")
        except Exception as e:
            self.logger.error(f"Proje yükleme hatası: {e}", exc_info=True)
            QMessageBox.critical(self, "Hata", f"❌ Yükleme hatası:\n{e}")
    
    def _populate_ui_from_inputs(self, inputs):
        """Yüklenen projeyi UI'ye yerleştir"""
        try:
            # Proje bilgileri
            self.project_name_edit.setText(inputs.get('project_name', ''))
            self.project_notes_edit.setPlainText(inputs.get('notes', ''))
            self.p_in_edit.setText(str(inputs.get('p_in', '')))
            self.p_in_unit_combo.setCurrentText(inputs.get('p_in_unit', 'bar(g)'))
            self.t_in_edit.setText(str(inputs.get('t_in', '')))
            self.t_in_unit_combo.setCurrentText(inputs.get('t_in_unit', '°C'))
            self.p_out_edit.setText(str(inputs.get('p_out', '')))
            self.p_out_unit_combo.setCurrentText(inputs.get('p_out_unit', 'bar(a)'))
            self.flow_edit.setText(str(inputs.get('flow', '')))
            self.flow_unit_combo.setCurrentText(inputs.get('flow_unit', 'Sm³/h'))
            self.num_units_spin.setValue(inputs.get('num_units', 1))
            
            # Hesaplama parametreleri
            eos = inputs.get('eos_method', 'coolprop')
            if eos == 'coolprop':
                self.eos_method_combo.setCurrentText("🎯 Yüksek Doğruluk (CoolProp)")
            elif eos == 'pr':
                self.eos_method_combo.setCurrentText("📊 Peng-Robinson (thermo)")
            elif eos == 'srk':
                self.eos_method_combo.setCurrentText("📈 SRK (thermo)")
            else:
                self.eos_method_combo.setCurrentIndex(0)
            
            self.method_combo.setCurrentText(inputs.get('method', 'Metot 1: Ortalama Özellikler'))
            
            lhv_src = inputs.get('lhv_source', 'kasp')
            if lhv_src == 'thermo' and THERMO_LOADED:
                self.lhv_source_combo.setCurrentIndex(1)
            else:
                self.lhv_source_combo.setCurrentIndex(0)
                
            self.poly_eff_edit.setText(str(inputs.get('poly_eff', 90.0)))
            self.therm_eff_edit.setText(str(inputs.get('therm_eff', 35.0)))
            self.mech_eff_edit.setText(str(inputs.get('mech_eff', 98.0)))
            
            # Tutarlılık modu
            self.consistency_check.setChecked(inputs.get('use_consistency_iteration', False))
            self.max_consistency_iter.setValue(inputs.get('max_consistency_iter', 20))
            self.consistency_tolerance.setValue(inputs.get('consistency_tolerance', 0.1))
            
            # Gaz kompozisyonu
            gas_comp = inputs.get('gas_comp', {})
            self.composition_table.setRowCount(0)
            if gas_comp:
                for component_key, percentage in gas_comp.items():
                    row = self.composition_table.rowCount()
                    self.composition_table.insertRow(row)
                    
                    combo = QComboBox()
                    combo.addItems(self.COMMON_COMPONENTS_DISPLAY)
                    display_name = self.COOLPROP_GAS_MAP.get(component_key, component_key)
                    if display_name in self.COMMON_COMPONENTS_DISPLAY:
                        combo.setCurrentText(display_name)
                    
                    self.composition_table.setCellWidget(row, 0, combo)
                    
                    percent_item = QTableWidgetItem(str(percentage))
                    percent_item.setTextAlignment(Qt.AlignCenter)
                    self.composition_table.setItem(row, 1, percent_item)
            
            self.logger.info("Proje verileri arayüze yerleştirildi")
            
        except Exception as e:
            self.logger.error(f"Yüklenen proje verileri arayüze yerleştirilirken hata oluştu: {e}", exc_info=True)
            QMessageBox.critical(self, "Hata", f"Yüklenen proje verileri arayüze yerleştirilirken hata oluştu: {e}")

    def center_on_screen(self):
        """Center the window on the screen"""
        from PyQt5.QtWidgets import QDesktopWidget
        screen = QDesktopWidget().screenGeometry()
        size = self.geometry()
        self.move(
            (screen.width() - size.width()) // 2,
            (screen.height() - size.height()) // 2
        )
