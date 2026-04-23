import os
import sys
from unittest.mock import patch

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

QtWidgets = pytest.importorskip("PyQt5.QtWidgets")
QtCore = pytest.importorskip("PyQt5.QtCore")

QApplication = QtWidgets.QApplication
QScrollArea = QtWidgets.QScrollArea


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


@patch("kasp.ui.responsive.get_screen_geometry")
def test_ui_responsive_large_screen(mock_get_screen_geometry, app):
    mock_get_screen_geometry.return_value = (1920, 1080)

    from kasp.ui.main_window import KaspMainWindow

    window = KaspMainWindow()
    try:
        geom = window.geometry()
        assert geom.width() <= 1920
        assert geom.height() <= 1080
        assert window.minimumWidth() == 900
        assert window.minimumHeight() == 550
    finally:
        _cleanup_window(window, app)


@patch("kasp.ui.responsive.get_screen_geometry")
def test_ui_responsive_small_screen(mock_get_screen_geometry, app):
    mock_get_screen_geometry.return_value = (1366, 768)

    from kasp.ui.main_window import KaspMainWindow

    window = KaspMainWindow()
    try:
        geom = window.geometry()
        assert geom.width() <= int(1366 * 0.93) + 1
        assert geom.height() <= int(768 * 0.93) + 1
    finally:
        _cleanup_window(window, app)


def test_left_panel_scroll_area(app):
    from kasp.ui.main_window import KaspMainWindow

    window = KaspMainWindow()
    try:
        design_layout = window.design_tab.layout()
        left_panel_widget = design_layout.itemAt(0).widget()

        assert isinstance(left_panel_widget, QScrollArea)
        assert left_panel_widget.widgetResizable() is True
    finally:
        _cleanup_window(window, app)


def test_status_bar_has_validation_indicator(app):
    from kasp.ui.main_window import KaspMainWindow

    window = KaspMainWindow()
    try:
        status_bar = window.statusBar()
        assert status_bar is not None
        assert getattr(window, "status_validation_indicator", None) is not None
    finally:
        _cleanup_window(window, app)
