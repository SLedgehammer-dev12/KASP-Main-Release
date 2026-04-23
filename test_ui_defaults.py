import os
import sys

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

QtWidgets = pytest.importorskip("PyQt5.QtWidgets")
QApplication = QtWidgets.QApplication


@pytest.fixture(scope="module")
def app():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


def _cleanup_window(window, app):
    window.close()
    window.deleteLater()
    app.processEvents()


def test_default_design_values(app):
    from kasp.ui.main_window import KaspMainWindow

    window = KaspMainWindow()
    try:
        assert window.project_name_edit.text() == "Yeni KompresÃ¶r Projesi"
        assert window.p_in_edit.text() == "49.65"
        assert window.t_in_edit.text() == "19"
        assert window.p_out_edit.text() == "75"
        assert window.flow_edit.text() == "1985000"
        assert window.num_units_spin.value() == 1
        assert window.num_stages_spin.value() == 1
        assert window.consistency_check.isChecked() is False
    finally:
        _cleanup_window(window, app)


def test_single_stage_defaults_disable_intercooler(app):
    from kasp.ui.main_window import KaspMainWindow

    window = KaspMainWindow()
    try:
        assert window.num_stages_spin.value() == 1
        assert window.ic_label.isEnabled() is False
        assert window.ic_dp_spin.isEnabled() is False
        assert window.ic_temp_edit.isEnabled() is False
        assert window.ic_dp_spin.value() == pytest.approx(2.0)
        assert window.ic_temp_edit.text() == "40.0"
    finally:
        _cleanup_window(window, app)
