"""PyQt5 widget localization helpers for the KASP desktop UI."""

from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QAction,
    QAbstractButton,
    QComboBox,
    QDialog,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMenu,
    QPlainTextEdit,
    QTabWidget,
    QTextEdit,
    QWidget,
    QApplication,
)

from kasp.i18n import tr

_ORIGINAL_TEXT_ROLE = Qt.UserRole + 99


def _translate_combo(combo: QComboBox) -> None:
    blocked = combo.blockSignals(True)
    try:
        for index in range(combo.count()):
            current = combo.itemText(index)
            original = combo.itemData(index, _ORIGINAL_TEXT_ROLE)
            if original is None:
                combo.setItemData(index, current, _ORIGINAL_TEXT_ROLE)
                original = current
            combo.setItemText(index, tr(str(original)))
    finally:
        combo.blockSignals(blocked)


def _translate_widget(widget: QWidget) -> None:
    if isinstance(widget, QTabWidget):
        for index in range(widget.count()):
            current = widget.tabText(index)
            original = widget.property("tr_tab_" + str(index))
            if original is None:
                widget.setProperty("tr_tab_" + str(index), current)
                original = current
            widget.setTabText(index, tr(str(original)))

    if isinstance(widget, QGroupBox):
        current = widget.title()
        original = widget.property("tr_text")
        if original is None:
            widget.setProperty("tr_text", current)
            original = current
        widget.setTitle(tr(str(original)))
    elif isinstance(widget, (QLabel, QAbstractButton)):
        current = widget.text()
        original = widget.property("tr_text")
        if original is None:
            widget.setProperty("tr_text", current)
            original = current
        widget.setText(tr(str(original)))

    if isinstance(widget, (QLineEdit, QTextEdit, QPlainTextEdit)):
        current = widget.placeholderText()
        if current:
            original = widget.property("tr_placeholder")
            if original is None:
                widget.setProperty("tr_placeholder", current)
                original = current
            widget.setPlaceholderText(tr(str(original)))

    if widget.windowTitle():
        current = widget.windowTitle()
        original = widget.property("tr_title")
        if original is None:
            widget.setProperty("tr_title", current)
            original = current
        widget.setWindowTitle(tr(str(original)))

    if widget.toolTip():
        current = widget.toolTip()
        original = widget.property("tr_tooltip")
        if original is None:
            widget.setProperty("tr_tooltip", current)
            original = current
        widget.setToolTip(tr(str(original)))

    if isinstance(widget, QComboBox):
        _translate_combo(widget)


def apply_window_language(widget: QWidget) -> None:
    _translate_widget(widget)
    for child in widget.findChildren(QWidget):
        _translate_widget(child)

    for menu in widget.findChildren(QMenu):
        menu.setTitle(tr(menu.title()))

    for action in widget.findChildren(QAction):
        action.setText(tr(action.text()))

    if isinstance(widget, QDialog):
        widget.setWindowTitle(tr(widget.windowTitle()))


def refresh_all_windows(window: QWidget | None = None) -> None:
    seen = set()
    if window is not None:
        apply_window_language(window)
        seen.add(id(window))
    app = QApplication.instance()
    if not app:
        return
    for widget in app.topLevelWidgets():
        if id(widget) not in seen:
            apply_window_language(widget)
