"""Graph save workflow helpers for the KASP UI."""

from __future__ import annotations

import logging

from kasp.ui.design_results_workflow import GRAPH_KEY_BY_LABEL


def graph_key_from_label(label):
    """Return the internal graph key for a UI-visible label."""
    return GRAPH_KEY_BY_LABEL.get(label)


def default_graph_filename(project_name, graph_key):
    """Build the default export filename for the selected graph."""
    base_name = (project_name or "").strip().replace(" ", "_") or "Proje"
    graph_name = graph_key or "graph"
    return f"{base_name}_{graph_name}.png"


class GraphWorkflowController:
    """Handle graph-related save actions outside the main window class."""

    def __init__(self, window, *, graph_manager):
        self.window = window
        self.graph_manager = graph_manager
        self.logger = logging.getLogger(self.__class__.__name__)

    @staticmethod
    def _qt_widgets():
        from PyQt5.QtWidgets import QFileDialog, QMessageBox

        return QFileDialog, QMessageBox

    def save_current_graph(self):
        QFileDialog, QMessageBox = self._qt_widgets()

        if not self.window.last_design_results_raw:
            QMessageBox.warning(self.window, "Uyarı", "Önce bir hesaplama yapın.")
            return

        current_graph_name = self.window.graph_combo.currentText()
        graph_key = graph_key_from_label(current_graph_name)

        if not graph_key or not self.graph_manager.current_graphs.get(graph_key):
            QMessageBox.warning(self.window, "Uyarı", f"'{current_graph_name}' grafiği oluşturulmamış veya boş.")
            return

        try:
            file_path, _ = QFileDialog.getSaveFileName(
                self.window,
                f"Grafiği Kaydet - {current_graph_name}",
                default_graph_filename(self.window.project_name_edit.text(), graph_key),
                "PNG Files (*.png)",
            )

            if not file_path:
                return

            canvas = self.graph_manager.current_graphs[graph_key]
            if not hasattr(canvas, "fig"):
                QMessageBox.warning(self.window, "Hata", "Grafik objesi geçerli değil.")
                return

            canvas.fig.savefig(file_path, dpi=300, bbox_inches="tight")
            self.logger.info("Grafik kaydedildi: %s", file_path)
            QMessageBox.information(self.window, "Başarılı", f"✅ Grafik başarıyla kaydedildi:\n{file_path}")
        except Exception as exc:
            self.logger.error("Grafik kaydetme hatası: %s", exc)
            QMessageBox.critical(self.window, "Hata", f"Grafik kaydedilirken hata oluştu: {exc}")
