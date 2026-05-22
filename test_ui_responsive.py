import sys
from unittest.mock import patch

import pytest
from PyQt5.QtWidgets import QApplication

from kasp.ui.main_window import KaspMainWindow


@pytest.fixture(scope="module")
def app():
    qt_app = QApplication.instance()
    if qt_app is None:
        qt_app = QApplication(sys.argv)
    return qt_app


@patch("kasp.ui.responsive.get_screen_geometry", return_value=(1920, 1080))
def test_ui_responsive_large_screen(_, app):
    window = KaspMainWindow()
    try:
        geom = window.geometry()
        assert geom.width() <= 1700
        assert geom.height() <= 950
        assert window.minimumWidth() == 900
        assert window.minimumHeight() == 550
    finally:
        window.close()


@patch("kasp.ui.responsive.get_screen_geometry", return_value=(1366, 768))
def test_ui_responsive_small_screen(_, app):
    window = KaspMainWindow()
    try:
        geom = window.geometry()
        assert geom.width() <= int(1366 * 0.93) + 1
        assert geom.height() <= int(768 * 0.93) + 1
    finally:
        window.close()


def test_status_bar_indicator_exists(app):
    window = KaspMainWindow()
    try:
        assert window.statusBar() is not None
        assert getattr(window, "status_validation_indicator", None) is not None
    finally:
        window.close()
