"""Input collection helpers for the KASP main window."""

from __future__ import annotations


def has_composition_total_warning(total_percentage, *, tolerance=1.0):
    return abs(total_percentage - 100.0) > tolerance


def build_composition_total_warning_message(total_percentage):
    return (
        f"Gaz bileşenlerinin toplamı <b>%{total_percentage:.2f}</b> — bu değer %100 olmalıdır.<br><br>"
        "Hesabı yine de devam ettirmek istiyor musunuz? "
        "(Motor otomatik olarak normalize edecektir.)"
    )


def build_input_value_error_message(error):
    return f"Lütfen tüm zorunlu alanları kontrol edin:\n{error}"


def get_unexpected_input_error_message():
    return "Girdi toplama sırasında beklenmeyen bir hata oluştu."


class MainWindowInputController:
    def __init__(self, window):
        self.window = window

    def setup_unit_tooltips(self):
        return None

    def update_method_options(self):
        return None

    def update_button_state(self):
        return None

    def get_design_inputs(self):
        from PyQt5.QtWidgets import QMessageBox

        try:
            inputs, total_percentage = self.window.design_input_binder.collect()

            if has_composition_total_warning(total_percentage):
                self.window.logger.warning(
                    f"Kompozisyon toplamı %100'den farklı (%{total_percentage:.2f}). Engine normalize edecek."
                )
                reply = QMessageBox.warning(
                    self.window,
                    "⚠ Gaz Kompozisyonu Toplamı",
                    build_composition_total_warning_message(total_percentage),
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )
                if reply == QMessageBox.No:
                    return None

            return inputs

        except ValueError as error:
            QMessageBox.critical(
                self.window,
                "Girdi Hatası",
                build_input_value_error_message(error),
            )
            return None
        except Exception as error:
            self.window.logger.error(
                f"Girdi toplama sırasında beklenmeyen hata: {error}"
            )
            QMessageBox.critical(
                self.window,
                "Sistem Hatası",
                get_unexpected_input_error_message(),
            )
            return None
