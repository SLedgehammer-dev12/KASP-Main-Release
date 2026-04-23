"""Gas-composition helpers and controller for the KASP UI."""

from __future__ import annotations

import logging


DEFAULT_NATURAL_GAS_COMPOSITION = {
    "METHANE": 85.0,
    "ETHANE": 8.0,
    "PROPANE": 4.0,
    "BUTANE": 2.0,
    "NITROGEN": 1.0,
}


def standard_composition_for_gas(gas_name):
    """Return a standard composition dict for a selected gas label."""
    normalized = (gas_name or "").casefold()

    if "methane" in normalized:
        return {"METHANE": 100.0}
    if "ethane" in normalized:
        return {"ETHANE": 100.0}
    if "propane" in normalized:
        return {"PROPANE": 100.0}
    if "nitrogen" in normalized:
        return {"NITROGEN": 100.0}
    if "carbon dioxide" in normalized:
        return {"CARBONDIOXIDE": 100.0}
    if "hydrogen" in normalized:
        return {"HYDROGEN": 100.0}
    if "water" in normalized or normalized.startswith("su"):
        return {"WATER": 100.0}
    if normalized == "air":
        return {"NITROGEN": 78.0, "OXYGEN": 21.0, "ARGON": 1.0}
    return dict(DEFAULT_NATURAL_GAS_COMPOSITION)


def normalize_percentage_values(values):
    """Normalize percentage values so their sum becomes 100.0."""
    clipped_values = [max(0.0, value) for value in values]
    total = sum(clipped_values)
    if total <= 0:
        raise ValueError("Tüm bileşen yüzdeleri sıfır veya boş. Normalize edilecek değer yok.")
    return [(value / total) * 100.0 for value in clipped_values], total


def build_total_label_state(total):
    """Return text and style for the live composition-total label."""
    diff = abs(total - 100.0)
    if diff < 0.01:
        return (
            f"Toplam: {total:.2f}%  ✔",
            "font-weight: bold; color: #27ae60; padding: 2px 4px; border-radius: 4px;",
        )
    if diff < 1.0:
        return (
            f"Toplam: {total:.2f}%  ⚠ (%100'e yakın)",
            "font-weight: bold; color: #e67e22; padding: 2px 4px; border-radius: 4px; background: #fef9e7;",
        )
    return (
        f"Toplam: {total:.2f}%  ✘ (100.00% olmalı!)",
        "font-weight: bold; color: #c0392b; padding: 2px 4px; border-radius: 4px; background: #fdf0ef;",
    )


def extract_gas_composition(entries, display_to_key):
    """Build a component->percentage dict from UI table entries."""
    gas_comp = {}
    for display_name, percentage_text in entries:
        display_name = (display_name or "").strip()
        percentage_text = (percentage_text or "").strip().replace(",", ".")
        if not display_name or not percentage_text:
            continue

        try:
            percentage = float(percentage_text)
        except ValueError:
            continue

        if percentage <= 0:
            continue

        component_key = display_to_key.get(display_name, display_name.upper())
        gas_comp[component_key] = percentage
    return gas_comp


class GasCompositionController:
    """Handle gas-composition UI workflows outside the main window class."""

    def __init__(self, window):
        self.window = window
        self.logger = logging.getLogger(self.__class__.__name__)

    @staticmethod
    def _qt_widgets():
        from PyQt5.QtCore import Qt
        from PyQt5.QtWidgets import QComboBox, QMessageBox, QTableWidgetItem

        return Qt, QComboBox, QMessageBox, QTableWidgetItem

    def _table_entries(self):
        entries = []
        for row in range(self.window.composition_table.rowCount()):
            component_combo = self.window.composition_table.cellWidget(row, 0)
            percentage_item = self.window.composition_table.item(row, 1)
            entries.append(
                (
                    component_combo.currentText() if component_combo else "",
                    percentage_item.text() if percentage_item else "",
                )
            )
        return entries

    def _populate_table(self, composition):
        Qt, QComboBox, _, QTableWidgetItem = self._qt_widgets()

        self.window.composition_table.setRowCount(len(composition))
        for row, (component_key, percentage) in enumerate(composition.items()):
            display_name = self.window.COOLPROP_GAS_MAP.get(component_key, component_key)

            combo = QComboBox()
            combo.addItems(self.window.COMMON_COMPONENTS_DISPLAY)
            if display_name in self.window.COMMON_COMPONENTS_DISPLAY:
                combo.setCurrentText(display_name)
            self.window.composition_table.setCellWidget(row, 0, combo)

            percent_item = QTableWidgetItem(str(percentage))
            percent_item.setTextAlignment(Qt.AlignCenter)
            self.window.composition_table.setItem(row, 1, percent_item)

        self.update_total_label()

    def on_gas_selection_changed(self, gas_name):
        if gas_name != "Özel Karışım":
            self.load_standard_gas_composition(gas_name)

    def load_standard_gas_composition(self, gas_name):
        self._populate_table(standard_composition_for_gas(gas_name))

    def add_component_row(self):
        _, QComboBox, _, QTableWidgetItem = self._qt_widgets()

        row_count = self.window.composition_table.rowCount()
        self.window.composition_table.insertRow(row_count)

        combo = QComboBox()
        combo.addItems(self.window.COMMON_COMPONENTS_DISPLAY)
        self.window.composition_table.setCellWidget(row_count, 0, combo)
        self.window.composition_table.setItem(row_count, 1, QTableWidgetItem("0"))
        self.update_total_label()

    def remove_component_row(self):
        current_row = self.window.composition_table.currentRow()
        if current_row >= 0:
            self.window.composition_table.removeRow(current_row)
        self.update_total_label()

    def update_total_label(self, *_args):
        try:
            total = sum(self.get_gas_composition().values())
            text, style = build_total_label_state(total)
            self.window.comp_total_label.setText(text)
            self.window.comp_total_label.setStyleSheet(style)
        except Exception as exc:
            self.window.logger.warning(f"Kompozisyon toplamı güncellenemedi: {exc}")

    def normalize_composition(self):
        _, _, QMessageBox, QTableWidgetItem = self._qt_widgets()

        try:
            numeric_values = []
            for _, percentage_text in self._table_entries():
                try:
                    numeric_values.append(float((percentage_text or "").replace(",", ".")))
                except ValueError:
                    numeric_values.append(0.0)

            normalized_values, total = normalize_percentage_values(numeric_values)
            for row, normalized_value in enumerate(normalized_values):
                self.window.composition_table.setItem(row, 1, QTableWidgetItem(f"{normalized_value:.4f}"))

            self.update_total_label()
            QMessageBox.information(
                self.window,
                "Başarılı",
                f"Gaz kompozisyonu normalize edildi.\nToplam {total:.2f}% → 100.00%",
            )
        except ValueError as exc:
            QMessageBox.warning(self.window, "Normalize Hatası", str(exc))
        except Exception as exc:
            self.window.logger.error(f"Normalize hatası: {exc}")
            QMessageBox.critical(self.window, "Hata", f"Normalize edilemedi: {exc}")

    def get_gas_composition(self):
        return extract_gas_composition(self._table_entries(), self.window.DISPLAY_TO_COOLPROP_KEY)
