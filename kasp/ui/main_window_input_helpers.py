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
        from kasp.i18n import tr

        tooltip_map = {
            "p_in_unit_combo": tr("Emme basıncı birimi (bar(a), bar(g), psi(a), psi(g), kPa, MPa)"),
            "t_in_unit_combo": tr("Emme sıcaklığı birimi (°C, K, °F)"),
            "p_out_unit_combo": tr("Basma basıncı birimi (bar(a), bar(g), psi(a), psi(g), kPa, MPa)"),
            "flow_unit_combo": tr("Debi birimi (Sm³/h, Nm³/h, kg/s, MMSCFD)"),
            "perf_p_in_unit_combo": tr("Performans emme basıncı birimi"),
            "perf_t_in_unit_combo": tr("Performans emme sıcaklığı birimi"),
            "perf_p_out_unit_combo": tr("Performans basma basıncı birimi"),
            "perf_t_out_unit_combo": tr("Performans basma sıcaklığı birimi"),
            "perf_flow_unit_combo": tr("Performans debi birimi"),
        }
        for attr, tip in tooltip_map.items():
            widget = getattr(self.window, attr, None)
            if widget is not None and hasattr(widget, "setToolTip"):
                widget.setToolTip(tip)

    def update_method_options(self):
        method_combo = getattr(self.window, "method_combo", None)
        if method_combo is not None and hasattr(method_combo, "setEnabled"):
            method_combo.setEnabled(method_combo.count() > 0)
        perf_method_combo = getattr(self.window, "perf_method_combo", None)
        if perf_method_combo is not None and hasattr(perf_method_combo, "setEnabled"):
            perf_method_combo.setEnabled(perf_method_combo.count() > 0)

    def update_button_state(self):
        worker_thread = getattr(self.window, "worker_thread", None)
        is_running = False
        if worker_thread is not None and hasattr(worker_thread, "isRunning"):
            try:
                is_running = bool(worker_thread.isRunning())
            except Exception:
                is_running = False
        calc_btn = getattr(self.window, "calculate_btn", None)
        if calc_btn is not None and hasattr(calc_btn, "setEnabled"):
            calc_btn.setEnabled(not is_running)
        stop_btn = getattr(self.window, "stop_btn", None)
        if stop_btn is not None and hasattr(stop_btn, "setEnabled"):
            stop_btn.setEnabled(is_running)

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
