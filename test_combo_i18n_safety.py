import sys
import pytest
from PyQt5.QtWidgets import QApplication, QComboBox
from unittest.mock import Mock

from kasp.ui.i18n_qt import _translate_combo, apply_window_language
from kasp import i18n


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_combo_preserves_custom_item_data(qapp):
    """QComboBox.itemData must not be modified or used as display text."""
    class ReleaseStub:
        def __init__(self, tag):
            self.tag = tag

    combo = QComboBox()
    custom_obj = ReleaseStub("v1.0.0")
    combo.addItem("Tüm Üreticiler", custom_obj)
    combo.addItem("Hesaplama Yapılıyor", None)

    # Force language switch
    i18n.set_language("en")
    try:
        _translate_combo(combo)

        # 1. Custom itemData must remain intact and identical
        assert combo.itemData(0) is custom_obj
        # 2. None itemData must not be polluted with display text
        assert combo.itemData(1) is None
        # 3. Item text must be translated properly from its visual label, NOT from str(custom_obj)
        assert "ReleaseStub" not in combo.itemText(0)
        assert combo.itemText(0) == i18n.tr("Tüm Üreticiler")
        assert combo.itemText(1) == i18n.tr("Hesaplama Yapılıyor")
    finally:
        i18n.set_language("tr")


def test_combo_blocks_signals_during_translation(qapp):
    """Signals like currentTextChanged must be blocked during _translate_combo."""
    combo = QComboBox()
    combo.addItem("Gaz Kompozisyonu")
    combo.addItem("Tasarım Noktası")

    text_changed_mock = Mock()
    combo.currentTextChanged.connect(text_changed_mock)

    i18n.set_language("en")
    try:
        _translate_combo(combo)
        # Translation must not trigger currentTextChanged listeners
        assert text_changed_mock.call_count == 0
    finally:
        i18n.set_language("tr")


def test_combo_multiple_language_switches(qapp):
    """Multiple TR -> EN -> TR switches must preserve the canonical original text."""
    combo = QComboBox()
    combo.addItem("Hesaplama başlatılıyor...")

    # Start in TR
    i18n.set_language("tr")
    _translate_combo(combo)
    assert combo.itemText(0) == "Hesaplama başlatılıyor..."

    # Switch to EN
    i18n.set_language("en")
    _translate_combo(combo)
    assert combo.itemText(0) == "Initializing calculation..."

    # Switch back to TR
    i18n.set_language("tr")
    _translate_combo(combo)
    assert combo.itemText(0) == "Hesaplama başlatılıyor..."

    # Switch to EN again
    i18n.set_language("en")
    _translate_combo(combo)
    assert combo.itemText(0) == "Initializing calculation..."
    i18n.set_language("tr")
