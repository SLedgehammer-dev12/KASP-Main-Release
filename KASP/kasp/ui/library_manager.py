from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget, 
                             QTableWidget, QTableWidgetItem, QPushButton, QHeaderView, 
                             QComboBox, QLabel, QMessageBox, QGroupBox, QFormLayout)
from PyQt5.QtCore import Qt
import logging
from release_metadata import APP_VERSION
from kasp.data.database import UnitDatabase
from .dialogs import CompressorEditDialog, TurbineDetailDialog

class LibraryManagerWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Ekipman Kutuphanesi Yonetimi - KASP v{APP_VERSION}")
        self.setModal(True)
        self.resize(1200, 800)
        self.db = parent.db if parent and hasattr(parent, 'db') else UnitDatabase()
        self.logger = logging.getLogger(self.__class__.__name__)
        self.setup_ui()
        self.refresh_turbines()
        self.refresh_compressors()
        self.update_statistics()

    def setup_ui(self):
        """UI bileşenlerini oluştur"""
        layout = QVBoxLayout(self)
        
        # Tabs
        self.tabs = QTabWidget()
        
        # --- Turbines Tab ---
        self.turbines_tab = QWidget()
        turbines_layout = QVBoxLayout(self.turbines_tab)
        
        # Filter
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Üretici Filtresi:"))
        self.manufacturer_filter = QComboBox()
        self.manufacturer_filter.addItem("Tüm Üreticiler")
        self.manufacturer_filter.currentTextChanged.connect(self.filter_turbines)
        filter_layout.addWidget(self.manufacturer_filter)
        filter_layout.addStretch()
        turbines_layout.addLayout(filter_layout)
        
        # Table
        self.turbine_table = QTableWidget()
        self.turbine_table.setColumnCount(6)
        self.turbine_table.setHorizontalHeaderLabels(['ID', 'Üretici', 'Model', 'Güç (kW)', 'Isı Oranı', 'Tip'])
        self.turbine_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.turbine_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.turbine_table.doubleClicked.connect(self.show_turbine_details)
        turbines_layout.addWidget(self.turbine_table)
        
        # Actions
        t_btn_layout = QHBoxLayout()
        self.refresh_turbines_btn = QPushButton("🔄 Yenile")
        self.refresh_turbines_btn.clicked.connect(self.refresh_turbines)
        self.view_turbine_btn = QPushButton("👁️ Detay Göster")
        self.view_turbine_btn.clicked.connect(self.show_turbine_details)
        
        t_btn_layout.addWidget(self.refresh_turbines_btn)
        t_btn_layout.addWidget(self.view_turbine_btn)
        t_btn_layout.addStretch()
        turbines_layout.addLayout(t_btn_layout)
        
        self.tabs.addTab(self.turbines_tab, "🚀 Gaz Türbinleri")
        
        # --- Compressors Tab ---
        self.compressors_tab = QWidget()
        comp_layout = QVBoxLayout(self.compressors_tab)
        
        self.compressor_table = QTableWidget()
        self.compressor_table.setColumnCount(6)
        self.compressor_table.setHorizontalHeaderLabels(['ID', 'Üretici', 'Model', 'Max PR', 'Min Akış', 'Max Akış'])
        self.compressor_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.compressor_table.setSelectionBehavior(QTableWidget.SelectRows)
        comp_layout.addWidget(self.compressor_table)
        
        c_btn_layout = QHBoxLayout()
        self.add_comp_btn = QPushButton("➕ Ekle")
        self.add_comp_btn.clicked.connect(self.add_compressor)
        self.del_comp_btn = QPushButton("🗑️ Sil")
        self.del_comp_btn.clicked.connect(self.delete_compressor)
        self.refresh_comp_btn = QPushButton("🔄 Yenile")
        self.refresh_comp_btn.clicked.connect(self.refresh_compressors)
        
        c_btn_layout.addWidget(self.add_comp_btn)
        c_btn_layout.addWidget(self.del_comp_btn)
        c_btn_layout.addWidget(self.refresh_comp_btn)
        c_btn_layout.addStretch()
        comp_layout.addLayout(c_btn_layout)
        
        self.tabs.addTab(self.compressors_tab, "💨 Kompresörler")
        
        layout.addWidget(self.tabs)
        
        # --- Statistics ---
        stats_group = QGroupBox("📊 İstatistikler")
        stats_layout = QHBoxLayout()
        self.stats_label = QLabel("Yükleniyor...")
        stats_layout.addWidget(self.stats_label)
        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)

    def refresh_turbines(self):
        """Türbin listesini yenile"""
        try:
            turbines = self.db.get_all_turbines_full_data()
            self.all_turbines = turbines
            
            # Üretici filtrelerini güncelle (mevcut seçimi korumaya çalış)
            current_filter = self.manufacturer_filter.currentText()
            manufacturers = sorted(set(t['manufacturer'] for t in turbines))
            
            self.manufacturer_filter.blockSignals(True)
            self.manufacturer_filter.clear()
            self.manufacturer_filter.addItem("Tüm Üreticiler")
            self.manufacturer_filter.addItems(manufacturers)
            
            index = self.manufacturer_filter.findText(current_filter)
            if index >= 0:
                self.manufacturer_filter.setCurrentIndex(index)
            self.manufacturer_filter.blockSignals(False)
            
            self.filter_turbines() # Tabloyu güncelle
            self.update_statistics()
            self.logger.info(f"{len(turbines)} türbin listelendi")
            
        except Exception as e:
            self.logger.error(f"Türbin listesi yenilenirken hata: {e}")
            QMessageBox.critical(self, "Hata", f"Türbin listesi yenilenirken hata oluştu:\n{e}")

    def filter_turbines(self):
        """Türbinleri filtrele ve göster"""
        if not hasattr(self, 'all_turbines'):
            return
            
        filter_text = self.manufacturer_filter.currentText()
        if filter_text == "Tüm Üreticiler":
            filtered = self.all_turbines
        else:
            filtered = [t for t in self.all_turbines if t['manufacturer'] == filter_text]
            
        self.display_turbines(filtered)

    def display_turbines(self, turbines):
        """Türbinleri tabloya doldur"""
        self.turbine_table.setRowCount(len(turbines))
        for row, t in enumerate(turbines):
            self.turbine_table.setItem(row, 0, QTableWidgetItem(str(t.get('id', '-'))))
            self.turbine_table.setItem(row, 1, QTableWidgetItem(t.get('manufacturer', '-')))
            self.turbine_table.setItem(row, 2, QTableWidgetItem(t.get('model', '-')))
            self.turbine_table.setItem(row, 3, QTableWidgetItem(f"{t.get('iso_power_kw', 0):.0f}"))
            self.turbine_table.setItem(row, 4, QTableWidgetItem(f"{t.get('iso_heat_rate_kj_kwh', 0):.0f}"))
            self.turbine_table.setItem(row, 5, QTableWidgetItem(t.get('type', '-')))

    def show_turbine_details(self):
        """Seçili türbin detaylarını göster"""
        row = self.turbine_table.currentRow()
        if row < 0:
            return
            
        # Filtrelenmiş listeden doğru türbini bulmak için ID kullanabiliriz veya UI sırasına güvenebiliriz
        # Ancak en doğrusu ID ile bulmak.
        try:
            t_id = int(self.turbine_table.item(row, 0).text())
            turbine = next((t for t in self.all_turbines if t.get('id') == t_id), None)
            
            if turbine:
                dialog = TurbineDetailDialog(turbine, self)
                dialog.exec_()
        except ValueError:
            pass

    def refresh_compressors(self):
        """Kompresör listesini yenile"""
        try:
            compressors = self.db.get_all_compressors_full_data()
            self.all_compressors = compressors
            self.display_compressors(compressors)
            self.update_statistics()
        except Exception as e:
            self.logger.error(f"Kompresör listesi hatası: {e}")

    def display_compressors(self, compressors):
        """Kompresörleri tabloya doldur"""
        self.compressor_table.setRowCount(len(compressors))
        for row, c in enumerate(compressors):
            self.compressor_table.setItem(row, 0, QTableWidgetItem(str(c.get('id', '-'))))
            self.compressor_table.setItem(row, 1, QTableWidgetItem(c.get('manufacturer', '-')))
            self.compressor_table.setItem(row, 2, QTableWidgetItem(c.get('model', '-')))
            self.compressor_table.setItem(row, 3, QTableWidgetItem(f"{c.get('max_pressure_ratio', 0):.2f}"))
            self.compressor_table.setItem(row, 4, QTableWidgetItem(f"{c.get('min_flow_kgs', 0):.1f}"))
            self.compressor_table.setItem(row, 5, QTableWidgetItem(f"{c.get('max_flow_kgs', 0):.1f}"))

    def add_compressor(self):
        """Yeni kompresör ekle"""
        dialog = CompressorEditDialog(self)
        if dialog.exec() == QDialog.Accepted:
            compressor_data = dialog.get_compressor_data()
            if compressor_data and self.db.add_compressor(compressor_data):
                self.refresh_compressors()
                QMessageBox.information(self, "Başarılı", "✅ Kompresör başarıyla eklendi")
            else:
                QMessageBox.warning(self, "Hata", "❌ Kompresör eklenemedi (model zaten mevcut olabilir)")

    def delete_compressor(self):
        """Seçili kompresörü sil"""
        current_row = self.compressor_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Uyarı", "⚠️ Lütfen silmek için bir kompresör seçin")
            return
            
        try:
            c_id = int(self.compressor_table.item(current_row, 0).text())
            model = self.compressor_table.item(current_row, 2).text()
            
            reply = QMessageBox.question(
                self, "Onay", 
                f"'{model}' kompresörünü silmek istediğinizden emin misiniz?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                if self.db.delete_compressor(c_id):
                    self.refresh_compressors()
                    QMessageBox.information(self, "Başarılı", "✅ Kompresör başarıyla silindi")
                else:
                    QMessageBox.warning(self, "Hata", "❌ Kompresör silinemedi")
        except ValueError:
            pass

    def update_statistics(self):
        """İstatistikleri güncelle"""
        t_count = len(getattr(self, 'all_turbines', []))
        c_count = len(getattr(self, 'all_compressors', []))
        self.stats_label.setText(f"Toplam Türbin: {t_count} | Toplam Kompresör: {c_count}")
