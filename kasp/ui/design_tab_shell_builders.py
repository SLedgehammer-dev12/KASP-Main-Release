"""Builders for the design tab shell layout in the KASP main window."""

from __future__ import annotations


def get_design_tab_margins():
    return (4, 4, 4, 4)


def get_design_tab_spacing():
    return 6


def get_design_left_scroll_width_range():
    return (360, 520)


def build_design_tab_shell(window):
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import QHBoxLayout, QScrollArea, QSizePolicy, QTabWidget, QVBoxLayout, QWidget

    result_tab_specs = [
        ("basic_results_tab", "setup_basic_results_tab", "📈 Temel Sonuçlar"),
        ("turbine_selection_tab", "setup_turbine_selection_tab", "🚀 Türbin Seçimi"),
        ("detailed_results_tab", "setup_detailed_results_tab", "📊 Detaylı Analiz"),
        ("graphs_tab", "setup_graphs_tab", "📉 Grafikler"),
    ]

    layout = QHBoxLayout(window.design_tab)
    margins = get_design_tab_margins()
    layout.setContentsMargins(*margins)
    layout.setSpacing(get_design_tab_spacing())

    left_content = QWidget()
    left_content.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
    left_layout = QVBoxLayout(left_content)
    left_layout.setContentsMargins(*margins)
    left_layout.setSpacing(get_design_tab_spacing())

    left_scroll = QScrollArea()
    left_scroll.setWidgetResizable(True)
    left_scroll.setWidget(left_content)
    left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    min_width, max_width = get_design_left_scroll_width_range()
    left_scroll.setMinimumWidth(min_width)
    left_scroll.setMaximumWidth(max_width)
    left_scroll.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
    left_scroll.setStyleSheet(
        "QScrollArea { border: none; background: transparent; }"
        "QScrollArea > QWidget > QWidget { background: transparent; }"
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

    layout.addWidget(left_scroll)
    layout.addWidget(right_panel, stretch=1)

    return left_layout
