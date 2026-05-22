from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
)
import json

from kasp.utils.updater import (
    build_release_notes_html,
    format_bytes,
    is_newer_release,
    pick_default_asset,
)


class CompressorEditDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Kompresor Ekle/Duzenle")
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

        form_layout.addRow("Uretici:", self.manufacturer_edit)
        form_layout.addRow("Model:", self.model_edit)
        form_layout.addRow("Maks. Basincl Orani:", self.max_pr_spin)
        form_layout.addRow("Min. Akis (kg/h):", self.min_flow_spin)
        form_layout.addRow("Maks. Akis (kg/h):", self.max_flow_spin)
        form_layout.addRow("Performans Haritasi (JSON):", self.map_data_edit)

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
            "manufacturer": self.manufacturer_edit.text(),
            "model": self.model_edit.text(),
            "max_pressure_ratio": self.max_pr_spin.value(),
            "min_flow_kgs": self.min_flow_spin.value(),
            "max_flow_kgs": self.max_flow_spin.value(),
            "performance_map_data": map_data,
        }


class TurbineDetailDialog(QDialog):
    def __init__(self, turbine_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Turbin Detaylari - {turbine_data.get('model', 'Bilinmeyen')}")
        self.resize(600, 500)
        self.turbine_data = turbine_data
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        fields = [
            ("Uretici", "manufacturer"),
            ("Model", "model"),
            ("Tip", "type"),
            ("ISO Guc (kW)", "iso_power_kw"),
            ("ISO Isi Orani (kJ/kWh)", "iso_heat_rate_kj_kwh"),
            ("Surge Flow", "surge_flow"),
            ("Stonewall Flow", "stonewall_flow"),
            ("Maks. Basinc Orani", "max_pressure_ratio"),
            ("Yakit Tipi", "fuel_type"),
        ]

        for label, key in fields:
            value = self.turbine_data.get(key, "-")
            field = QLabel(str(value))
            field.setTextInteractionFlags(Qt.TextSelectableByMouse)
            form_layout.addRow(f"{label}:", field)

        layout.addLayout(form_layout)

        layout.addWidget(QLabel("Duzeltme Faktorleri (JSON):"))
        corr_text = QTextEdit()
        corr_text.setReadOnly(True)
        corr_data = self.turbine_data.get("performance_correction_data", {})
        if isinstance(corr_data, str):
            corr_text.setText(corr_data)
        else:
            corr_text.setText(json.dumps(corr_data, indent=2))
        layout.addWidget(corr_text)

        button_box = QDialogButtonBox(QDialogButtonBox.Close)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)


class TurbineEditDialog(QDialog):
    """Placeholder for future implementation."""


class ChangelogDialog(QDialog):
    """Release notes dialog backed by release metadata."""

    def __init__(self, releases=None, current_release_tag="", parent=None):
        if parent is None and releases is not None and not isinstance(releases, (list, tuple)):
            parent = releases
            releases = None
        super().__init__(parent)
        self.releases = list(releases or [])
        self.current_release_tag = current_release_tag
        self.setWindowTitle("KASP Surum Notlari")
        self.resize(700, 520)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        notes_text = QTextBrowser()
        notes_text.setOpenExternalLinks(True)
        notes_text.setHtml(
            build_release_notes_html(
                self.releases,
                self.current_release_tag,
                heading="KASP Surum Notlari",
            )
        )
        layout.addWidget(notes_text)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok)
        button_box.accepted.connect(self.accept)
        layout.addWidget(button_box)


class UpdateDialog(QDialog):
    def __init__(self, releases, current_release_tag, parent=None):
        super().__init__(parent)
        self.releases = releases
        self.current_release_tag = current_release_tag
        self.selected_release = None
        self.selected_asset = None
        self.setWindowTitle("KASP Guncelleme Merkezi")
        self.resize(720, 520)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        header = QLabel(
            f"<h3>KASP Guncellemeleri</h3>"
            f"<p>Yuklu surum: <b>{self.current_release_tag}</b></p>"
        )
        header.setTextFormat(Qt.RichText)
        layout.addWidget(header)

        form = QFormLayout()
        self.release_combo = QComboBox()
        for release in self.releases:
            self.release_combo.addItem(f"{release.tag_name} - {release.display_name}", release)
        self.release_combo.currentIndexChanged.connect(self._update_release_details)

        self.asset_combo = QComboBox()
        self.status_label = QLabel("-")
        self.published_label = QLabel("-")
        self.url_label = QLabel("-")
        self.url_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        form.addRow("Release:", self.release_combo)
        form.addRow("Dosya:", self.asset_combo)
        form.addRow("Durum:", self.status_label)
        form.addRow("Yayin Tarihi:", self.published_label)
        form.addRow("Baglanti:", self.url_label)
        layout.addLayout(form)

        layout.addWidget(QLabel("Release Notlari:"))
        self.notes_text = QTextEdit()
        self.notes_text.setReadOnly(True)
        layout.addWidget(self.notes_text)

        buttons = QHBoxLayout()
        self.download_button = QDialogButtonBox()
        self.download_button.setStandardButtons(QDialogButtonBox.Close)
        self.install_button = self.download_button.addButton(
            "Secili Surumu Indir...",
            QDialogButtonBox.AcceptRole,
        )
        self.install_button.clicked.connect(self._accept_download)
        self.download_button.rejected.connect(self.reject)
        buttons.addWidget(self.download_button)
        layout.addLayout(buttons)

        if self.releases:
            self.release_combo.setCurrentIndex(0)
            self._update_release_details()
        else:
            self.install_button.setEnabled(False)
            self.notes_text.setPlainText("Release bilgisi bulunamadi.")

    def _update_release_details(self):
        release = self.release_combo.currentData()
        if release is None:
            self.asset_combo.clear()
            self.install_button.setEnabled(False)
            self.notes_text.clear()
            return

        self.selected_release = release
        if release.tag_name == self.current_release_tag:
            status = "Kurulu surum"
        elif is_newer_release(release.tag_name, self.current_release_tag):
            status = "Yeni surum mevcut"
        else:
            status = "Daha eski surum"

        self.status_label.setText(status)
        self.published_label.setText(release.published_at or "-")
        self.url_label.setText(release.html_url or "-")
        self.notes_text.setPlainText(release.body or "Release notu bulunmuyor.")

        self.asset_combo.clear()
        for asset in release.assets:
            label = f"{asset.name} ({format_bytes(asset.size)})"
            self.asset_combo.addItem(label, asset)

        default_asset = pick_default_asset(release)
        if default_asset is not None:
            for index in range(self.asset_combo.count()):
                asset = self.asset_combo.itemData(index)
                if asset == default_asset:
                    self.asset_combo.setCurrentIndex(index)
                    break

        self.install_button.setEnabled(self.asset_combo.count() > 0)

    def _accept_download(self):
        self.selected_release = self.release_combo.currentData()
        self.selected_asset = self.asset_combo.currentData()
        if self.selected_release is None or self.selected_asset is None:
            return
        self.accept()
