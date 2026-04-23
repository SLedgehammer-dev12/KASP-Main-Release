"""Auxiliary helpers for status, validation and window utilities."""

from __future__ import annotations

from kasp.i18n import APP_VERSION, tr


def get_version_label_text():
    return tr(f"KASP v{APP_VERSION}")


def get_validation_field_name_map():
    return {
        "inlet_pressure": tr("Giriş Basıncı"),
        "inlet_temperature": tr("Giriş Sıcaklığı"),
        "outlet_pressure": tr("Çıkış Basıncı"),
        "flow_rate": tr("Gaz Debisi"),
    }


def build_validation_warning_lines(invalid_fields, field_name_map=None):
    field_name_map = field_name_map or get_validation_field_name_map()
    lines = []
    for field_name, error_msg in invalid_fields:
        display = field_name_map.get(field_name, field_name.replace("_", " ").title())
        lines.append(f"  • {display}: {error_msg}")
    return lines


def build_validation_warning_message(invalid_fields, field_name_map=None):
    return (
        tr("Hesaplama başlatmadan önce lütfen aşağıdaki alanları düzeltiniz:\n\n")
        + "\n".join(build_validation_warning_lines(invalid_fields, field_name_map=field_name_map))
        + tr("\n\nGeçersiz alanlar kırmızı kenarlık ile işaretlenmiştir.")
    )


def summarize_library_inventory(turbine_count, compressor_count):
    return tr(f"Kütüphanede {turbine_count} türbin ve {compressor_count} kompresör bulundu.")


def calculate_center_position(screen_width, screen_height, window_width, window_height):
    return (
        (screen_width - window_width) // 2,
        (screen_height - window_height) // 2,
    )


class MainWindowAuxiliaryController:
    def __init__(self, window):
        self.window = window

    def setup_status_bar(self, *, validation_available):
        from PyQt5.QtWidgets import QLabel, QStatusBar

        status_bar = QStatusBar(self.window)
        self.window.setStatusBar(status_bar)

        if validation_available and self.window.validation_manager:
            from kasp.ui.validation_status import MinimalValidationIndicator

            self.window.status_validation_indicator = MinimalValidationIndicator()
            status_bar.addPermanentWidget(self.window.status_validation_indicator)

            for _field_name, input_field in self.window.validation_manager.inputs.items():
                input_field.validation_changed.connect(self.window._update_status_bar_validation)

            self.update_status_bar_validation()
        else:
            self.window.status_validation_indicator = None

        version_label = QLabel(get_version_label_text())
        version_label.setStyleSheet("color: #7f8c8d; padding: 0 8px;")
        status_bar.addPermanentWidget(version_label)

    def update_status_bar_validation(self, *_args):
        if not hasattr(self.window, "status_validation_indicator") or self.window.status_validation_indicator is None:
            return
        if self.window.validation_manager is None:
            return
        summary = self.window.validation_manager.get_validation_summary()
        self.window.status_validation_indicator.update_status(
            summary["all_valid"],
            summary["valid_count"],
            summary["total_fields"],
        )

    def show_validation_popup(self):
        from PyQt5.QtWidgets import QMessageBox

        if self.window.validation_manager is None:
            return True
        if self.window.validation_manager.all_inputs_valid():
            return True

        invalid_fields = self.window.validation_manager.get_invalid_fields()
        QMessageBox.warning(
            self.window,
            tr("⚠️ Geçersiz Girişler"),
            build_validation_warning_message(invalid_fields),
        )
        return False

    def populate_unit_combos(self):
        self.window.logger.info(tr("Birim/Kütüphane Combobox'ları güncelleniyor..."))
        all_turbines = self.window.db.get_all_turbines_full_data()
        all_compressors = self.window.db.get_all_compressors_full_data()
        self.window.logger.info(
            summarize_library_inventory(len(all_turbines), len(all_compressors))
        )

    def center_on_screen(self):
        from PyQt5.QtWidgets import QDesktopWidget

        screen = QDesktopWidget().screenGeometry()
        size = self.window.geometry()
        x, y = calculate_center_position(
            screen.width(),
            screen.height(),
            size.width(),
            size.height(),
        )
        self.window.move(x, y)
