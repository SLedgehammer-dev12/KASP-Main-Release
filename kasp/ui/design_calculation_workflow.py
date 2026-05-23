"""Design-calculation workflow controller for the KASP UI."""

from __future__ import annotations

import logging


def format_time_estimate(seconds):
    """Render a compact ETA string for progress feedback."""
    if seconds < 60:
        return f"~{int(seconds)}s remaining"

    minutes = int(seconds // 60)
    remainder = int(seconds % 60)
    return f"~{minutes}m {remainder}s remaining"


class DesignCalculationController:
    """Coordinate the threaded design-calculation workflow."""

    def __init__(
        self,
        window,
        *,
        engine,
        db,
        worker_factory=None,
        thread_factory=None,
        message_box_factory=None,
    ):
        self.window = window
        self.engine = engine
        self.db = db
        self.logger = logging.getLogger(self.__class__.__name__)
        self._worker_factory = worker_factory or self._default_worker_factory
        self._thread_factory = thread_factory or self._qt_thread_factory
        self._message_box_factory = message_box_factory or self._qt_message_box
        self.active_inputs = None

    @staticmethod
    def _qt_thread_factory():
        from PyQt5.QtCore import QThread

        return QThread

    @staticmethod
    def _qt_message_box():
        from PyQt5.QtWidgets import QMessageBox

        return QMessageBox

    @staticmethod
    def _default_worker_factory():
        from kasp.utils.workers import CalculationWorker

        return CalculationWorker

    def _set_running_ui_state(self):
        self.window.progress_bar.setValue(0)
        self.window.progress_bar.setVisible(True)
        self.window.progress_status_label.setVisible(True)
        self.window.progress_status_label.setText("Initializing...")
        self.window.progress_time_label.setVisible(True)
        self.window.progress_time_label.setText("Estimating time...")
        self.window.calculate_btn.setEnabled(False)
        self.window.stop_btn.setEnabled(True)
        self.window.stop_btn.setText("⏹️ Durdur")

    def _set_idle_ui_state(self, *, progress_value=None):
        self.window.calculate_btn.setEnabled(True)
        self.window.stop_btn.setEnabled(False)
        self.window.stop_btn.setText("⏹️ Durdur")
        self.window.progress_bar.setVisible(False)
        if progress_value is not None:
            self.window.progress_bar.setValue(progress_value)
        self.window.progress_status_label.setVisible(False)
        self.window.progress_time_label.setVisible(False)

    def _handle_thread_finished(self):
        self.window.worker = None
        self.window.worker_thread = None
        self.active_inputs = None

    def run(self):
        QMessageBox = self._message_box_factory()
        current_thread = self.window.worker_thread
        if current_thread is not None and current_thread.isRunning():
            QMessageBox.warning(
                self.window,
                "Uyarı",
                "Zaten bir hesaplama çalışıyor. Lütfen bekleyin veya durdurun.",
            )
            return

        if not self.window._show_validation_popup():
            return

        inputs = self.window._get_design_inputs()
        if inputs is None:
            return

        thread_cls = self._thread_factory()
        worker_cls = self._worker_factory()
        thread = thread_cls()
        all_turbines = self.db.get_all_turbines_full_data()
        worker = worker_cls(self.engine, inputs, all_turbines)
        worker.moveToThread(thread)

        self.active_inputs = dict(inputs)
        self.window.worker_thread = thread
        self.window.worker = worker

        thread.started.connect(worker.run)
        worker.finished.connect(self.calculation_finished)
        worker.error.connect(self.calculation_error)
        worker.progress.connect(self.window.progress_bar.setValue)
        worker.progress_detailed.connect(self.update_progress_detailed)
        worker.time_remaining.connect(self.update_time_estimate)
        worker.cancelled.connect(self.calculation_cancelled)
        worker.finished.connect(thread.quit)
        worker.error.connect(thread.quit)
        worker.cancelled.connect(thread.quit)
        thread.finished.connect(self._handle_thread_finished)

        self._set_running_ui_state()
        self.logger.info(
            "Hesaplama başlatılıyor: %s (Metod: %s)",
            inputs.get("project_name", ""),
            inputs.get("method", ""),
        )
        thread.start()

    def calculation_finished(self, results_raw, selected_units):
        QMessageBox = self._message_box_factory()
        self._set_idle_ui_state(progress_value=100)

        self.window.last_design_inputs = dict(self.active_inputs or {})
        self.window.last_design_results_raw = results_raw
        self.window.last_selected_units = selected_units
        self.window._update_results_ui(results_raw, selected_units)

        if self.window.last_design_inputs:
            self.db.save_calculation_history(
                self.window.last_design_inputs.get("project_name", ""),
                "Tasarım",
                self.window.last_design_inputs,
                results_raw,
                self.window.last_design_inputs.get("notes", ""),
            )

        QMessageBox.information(self.window, "Başarılı", "✅ Tasarım hesaplaması başarıyla tamamlandı!")

    def calculation_error(self, error_message):
        QMessageBox = self._message_box_factory()
        self._set_idle_ui_state()
        QMessageBox.critical(self.window, "Hesaplama Hatası", f"❌ Hesaplama başarısız oldu:\n{error_message}")
        self.logger.error("Hesaplama hatası: %s", error_message)

    def stop(self):
        if self.window.worker is not None:
            self.window.worker.request_cancel()
            self.window.stop_btn.setEnabled(False)
            self.window.stop_btn.setText("⏳ Cancelling...")
            self.logger.warning("Calculation cancellation requested by user")

    def update_progress_detailed(self, percentage, message):
        self.window.progress_bar.setValue(percentage)
        self.window.progress_status_label.setText(message)
        self.logger.debug("Progress: %s%% - %s", percentage, message)

    def update_time_estimate(self, seconds):
        self.window.progress_time_label.setText(format_time_estimate(seconds))

    def calculation_cancelled(self):
        QMessageBox = self._message_box_factory()
        self._set_idle_ui_state()
        self.logger.info("✓ Calculation cancelled by user")
        QMessageBox.information(self.window, "Cancelled", "⏹️ Calculation was cancelled successfully.")
