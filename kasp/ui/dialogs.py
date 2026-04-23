from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLineEdit, 
                             QDialogButtonBox, QTextEdit, QLabel, QDoubleSpinBox, 
                             QComboBox, QHBoxLayout)
from PyQt5.QtCore import Qt
import json

class CompressorEditDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Kompresör Ekle/Düzenle")
        self.resize(500, 600)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.manufacturer_edit = QLineEdit()
        self.model_edit = QLineEdit()
        
        self.max_pr_spin = QDoubleSpinBox()
        self.max_pr_spin.setRange(1.0, 100.0)
        self.max_pr_spin.setValue(3.5)
        self.max_pr_spin.setSingleStep(0.1)
        
        self.min_flow_spin = QDoubleSpinBox()
        self.min_flow_spin.setRange(0, 1000000)
        self.min_flow_spin.setValue(1000)
        
        self.max_flow_spin = QDoubleSpinBox()
        self.max_flow_spin.setRange(0, 10000000)
        self.max_flow_spin.setValue(50000)
        
        self.map_data_edit = QTextEdit()
        self.map_data_edit.setPlaceholderText('{"curve1": [[flow, head, eff], ...]}')
        
        form_layout.addRow("Üretici:", self.manufacturer_edit)
        form_layout.addRow("Model:", self.model_edit)
        form_layout.addRow("Maks. Basınç Oranı:", self.max_pr_spin)
        form_layout.addRow("Min. Akış (kg/h):", self.min_flow_spin)
        form_layout.addRow("Maks. Akış (kg/h):", self.max_flow_spin)
        form_layout.addRow("Performans Haritası (JSON):", self.map_data_edit)
        
        layout.addLayout(form_layout)
        
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def get_compressor_data(self):
        try:
            map_data_str = self.map_data_edit.toPlainText()
            map_data = json.loads(map_data_str) if map_data_str.strip() else {}
        except json.JSONDecodeError:
            map_data = {}

        return {
            'manufacturer': self.manufacturer_edit.text(),
            'model': self.model_edit.text(),
            'max_pressure_ratio': self.max_pr_spin.value(),
            'min_flow_kgs': self.min_flow_spin.value(), # Note: Label says kg/h but internal might be kg/s or consistent unit
            'max_flow_kgs': self.max_flow_spin.value(),
            'performance_map_data': map_data
        }

class TurbineDetailDialog(QDialog):
    def __init__(self, turbine_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Türbin Detayları - {turbine_data.get('model', 'Bilinmeyen')}")
        self.resize(600, 500)
        self.turbine_data = turbine_data
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        
        # Read-only fields
        fields = [
            ('Üretici', 'manufacturer'),
            ('Model', 'model'),
            ('Tip', 'type'),
            ('ISO Güç (kW)', 'iso_power_kw'),
            ('ISO Isı Oranı (kJ/kWh)', 'iso_heat_rate_kj_kwh'),
            ('Surge Flow', 'surge_flow'),
            ('Stonewall Flow', 'stonewall_flow'),
            ('Maks. Basınç Oranı', 'max_pressure_ratio'),
            ('Yakıt Tipi', 'fuel_type')
        ]
        
        for label, key in fields:
            val = self.turbine_data.get(key, '-')
            lbl = QLabel(str(val))
            lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
            form_layout.addRow(f"{label}:", lbl)
            
        layout.addLayout(form_layout)
        
        # Correction Data View
        layout.addWidget(QLabel("Düzeltme Faktörleri (JSON):"))
        corr_text = QTextEdit()
        corr_text.setReadOnly(True)
        corr_data = self.turbine_data.get('performance_correction_data', {})
        if isinstance(corr_data, str):
            corr_text.setText(corr_data)
        else:
            corr_text.setText(json.dumps(corr_data, indent=2))
        layout.addWidget(corr_text)
        
        button_box = QDialogButtonBox(QDialogButtonBox.Close)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

class TurbineEditDialog(QDialog):
    """Placeholder for future implementation"""
    pass

class ChangelogDialog(QDialog):
    """Yeni sürüm güncellemelerini gösteren açılır pencere."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("KASP Güncelleme Notları")
        self.resize(600, 450)
        self.do_not_show_again = False
        self.setup_ui()

    def setup_ui(self):
        from PyQt5.QtWidgets import QCheckBox, QPushButton
        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel("<h3>KASP V4.6 Yenilikleri</h3>")
        header.setAlignment(Qt.AlignCenter)
        layout.addWidget(header)
        
        # Changelog text
        changelog_text = QTextEdit()
        changelog_text.setReadOnly(True)
        html_content = """
        <h4>Versiyon 4.6 — Responsive UI (Mevcut)</h4>
        <ul>
            <li><b>Responsive Pencere Boyutu:</b> Pencere artık ekran çözünürlüğüne göre otomatik boyutlandırılır. Düşük çözünürlüklü ekranlarda (örn. 1366×768) pencere ekranı taşmaz.</li>
            <li><b>Kaydırılabilir Sol Panel:</b> Giriş paneli bir QScrollArea içine alındı; dar ekranlarda tüm alanlara kaydırma ile erişilir.</li>
            <li><b>Doğrulama Göstergesi Yeniden Tasarlandı:</b> Büyük "Input Validation Status" bloğu kaldırıldı. Doğrulama durumu artık alt status bar'da gösterilir ve hesaplama başlatıldığında hatalı alanlar için pop-up uyarısı açılır.</li>
            <li><b>DPI Ölçeklendirme:</b> Yüksek DPI ekranlarda font boyutu otomatik ayarlanır.</li>
            <li><b>Minimum Pencere Boyutu:</b> 900×550 px olarak güncellendi.</li>
        </ul>
        <h4>Versiyon 4.5</h4>
        <ul>
            <li>Faz tespiti, ortam basıncı, ASME PTC 10 ve yoğuşma algoritması iyileştirmeleri.</li>
        </ul>
        <h4>Versiyon 4.4 İyileştirmeleri</h4>
        <ul>
            <li><b>Faz Tespiti:</b> Z &lt; 0.2 kaba algılama yerine CoolProp PhaseSI aktif edildi.</li>
            <li><b>Ortam Basıncı:</b> Yüksek rakımlı bölgeler için dinamik ortam basıncı hesabı eklendi.</li>
            <li><b>ASME PTC 10:</b> Türbin test hesaplamalarındaki Z faktörü logaritmik olarak güncellendi.</li>
            <li><b>Hata Giderimleri:</b> 'ThermoEngine' convert_result_value ve TurbineRecommendation tip hataları onarıldı.</li>
        </ul>
        """
        changelog_text.setHtml(html_content)
        layout.addWidget(changelog_text)
        
        # Checkbox for 'Do not show again'
        self.checkbox = QCheckBox("Bu sürüm için bu mesajı tekrar gösterme")
        layout.addWidget(self.checkbox)
        
        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok)
        button_box.accepted.connect(self.accept)
        layout.addWidget(button_box)

    def accept(self):
        if self.checkbox.isChecked():
            self.do_not_show_again = True
        super().accept()
