import sys

import pytest
from PyQt5.QtWidgets import QApplication

from kasp.ui.main_window import KaspMainWindow


@pytest.fixture(scope="module")
def app():
    qt_app = QApplication.instance()
    if qt_app is None:
        qt_app = QApplication(sys.argv)
    return qt_app


def test_update_menu_action_exists(app):
    window = KaspMainWindow()
    try:
        action_texts = []
        for top_level_action in window.menuBar().actions():
            menu = top_level_action.menu()
            if menu is None:
                continue
            action_texts.extend(action.text() for action in menu.actions())
    finally:
        window.close()

    assert any("Guncellemeleri Kontrol Et" in text for text in action_texts)
