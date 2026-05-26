"""Builders for the design tab shell layout in the KASP main window."""

from __future__ import annotations


def get_design_tab_margins():
    from kasp.ui.responsive import compact_padding
    p = compact_padding()
    return (p, p, p, p)


def get_design_tab_spacing():
    from kasp.ui.responsive import compact_spacing
    return compact_spacing()


def build_design_tab_shell(window):
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import (
        QScrollArea, QSizePolicy, QSplitter, QTabWidget, QVBoxLayout, QWidget,
    )

    result_tab_specs = [
        ("basic_results_tab", "setup_basic_results_tab", "📈 Temel Sonuçlar"),
        ("turbine_selection_tab", "setup_turbine_selection_tab", "🚀 Türbin Seçimi"),
        ("detailed_results_tab", "setup_detailed_results_tab", "📊 Detaylı Analiz"),
        ("graphs_tab", "setup_graphs_tab", "📉 Grafikler"),
    ]

    shell_layout = QVBoxLayout(window.design_tab)
    shell_layout.setContentsMargins(0, 0, 0, 0)

    splitter = QSplitter(Qt.Horizontal)
    splitter.setChildrenCollapsible(False)

    left_content = QWidget()
    left_content.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
    left_layout = QVBoxLayout(left_content)
    margins = get_design_tab_margins()
    left_layout.setContentsMargins(*margins)
    left_layout.setSpacing(get_design_tab_spacing())

    left_scroll = QScrollArea()
    left_scroll.setWidgetResizable(True)
    left_scroll.setWidget(left_content)
    left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    left_scroll.setStyleSheet(
        "QScrollArea { border: none; background: transparent; }"
        "QScrollArea > QWidget > QWidget { background: transparent; }"
    )

    right_scroll = QScrollArea()
    right_scroll.setWidgetResizable(True)
    right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    right_scroll.setStyleSheet(
        "QScrollArea { border: none; background: transparent; }"
    )

    right_panel = QWidget()
    right_layout = QVBoxLayout(right_panel)
    right_layout.setContentsMargins(0, 0, 0, 0)

    window.results_tabs = QTabWidget()
    for attr_name, setup_method_name, title in result_tab_specs:
        tab = QWidget()
        setattr(window, attr_name, tab)
        getattr(window, setup_method_name)()
        window.results_tabs.addTab(tab, title)

    right_layout.addWidget(window.results_tabs)
    right_scroll.setWidget(right_panel)

    splitter.addWidget(left_scroll)
    splitter.addWidget(right_scroll)
    splitter.setSizes([500, 500])
    splitter.setStretchFactor(0, 1)
    splitter.setStretchFactor(1, 1)

    shell_layout.addWidget(splitter)
    window.design_splitter = splitter

    return left_layout
