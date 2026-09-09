import os
import sys
import pytest
from PyQt5.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("KASP_SKIP_CHANGELOG_DIALOG", "1")
os.environ.setdefault("KASP_TEST_MODE", "1")
os.environ.setdefault("MPLCONFIGDIR", "/tmp")

from kasp.ui.main_window import KaspMainWindow
from kasp.ui.theme_manager import ThemeManager
from kasp.ui.responsive import get_scale_factor, scaled_font_pt, scaled_px


@pytest.fixture(scope="module")
def app():
    qt_app = QApplication.instance()
    if qt_app is None:
        qt_app = QApplication(sys.argv)
    return qt_app


@pytest.fixture
def window(app):
    win = KaspMainWindow()
    yield win
    win.close()


def test_sticky_action_bar_structure(window):
    """Verify sticky action bar exists, is pinned outside scroll, and contains calculate/stop buttons."""
    assert hasattr(window, "sticky_action_bar")
    assert window.sticky_action_bar is not None
    assert window.sticky_action_bar.objectName() == "StickyActionBar"

    assert hasattr(window, "calculate_btn")
    assert window.calculate_btn is not None
    assert window.calculate_btn.text() == "🚀 Hesaplama Başlat"

    assert hasattr(window, "stop_btn")
    assert window.stop_btn is not None
    assert not window.stop_btn.isEnabled()

    # Progress elements exist
    assert hasattr(window, "progress_bar")
    assert hasattr(window, "progress_status_label")
    assert hasattr(window, "progress_time_label")


def test_two_column_process_grid_and_bindings(window):
    """Verify 2-column process grid widgets exist with valid initial values and units."""
    assert window.p_in_edit.text() == "49.65"
    assert window.p_in_unit_combo.currentText() == "bar(g)"

    assert window.p_out_edit.text() == "75"
    assert window.p_out_unit_combo.currentText() == "bar(a)"

    assert window.t_in_edit.text() == "19"
    assert window.t_in_unit_combo.currentText() == "°C"

    assert window.flow_edit.text() == "1985000"
    assert window.flow_unit_combo.currentText() == "Sm³/h"

    assert window.num_units_spin.value() == 1
    assert window.num_stages_spin.value() == 1


def test_live_metrics_badge(window):
    """Verify live PR and Delta-P update automatically when pressure values change."""
    assert hasattr(window, "live_metrics_badge")
    assert window.live_metrics_badge is not None

    # Initial text should contain PR and ΔP
    initial_text = window.live_metrics_badge.text()
    assert "Basınç Oranı (PR)" in initial_text
    assert "ΔP" in initial_text

    # Change p_in and p_out to known values:
    # 50 bar(a) to 100 bar(a) -> PR = 2.00, ΔP = +50.00 bar
    window.p_in_unit_combo.setCurrentText("bar(a)")
    window.p_out_unit_combo.setCurrentText("bar(a)")
    window.p_in_edit.setText("50.0")
    window.p_out_edit.setText("100.0")

    badge_text = window.live_metrics_badge.text()
    assert "2.00" in badge_text
    assert "+50.00 bar" in badge_text


def test_collapsible_project_notes(window):
    """Verify project notes group starts collapsed and can be toggled open/closed."""
    assert hasattr(window, "_toggle_project_group")
    assert hasattr(window, "project_notes_edit")
    assert hasattr(window, "project_name_edit")
    assert hasattr(window, "project_content_widget")

    # Initially collapsed
    assert window.project_content_widget.isHidden()
    assert "Göster" in window.toggle_project_notes_btn.text()

    # Toggle open
    window._toggle_project_group()
    assert not window.project_content_widget.isHidden()
    assert "Gizle" in window.toggle_project_notes_btn.text()

    # Toggle closed
    window._toggle_project_group()
    assert window.project_content_widget.isHidden()
    assert "Göster" in window.toggle_project_notes_btn.text()


def test_collapsible_gas_composition_table(window):
    """Verify composition table can be collapsed/expanded via toggle button."""
    assert hasattr(window, "toggle_comp_table_btn")
    assert hasattr(window, "comp_table_container")
    assert hasattr(window, "_toggle_comp_table")

    # Table is initially visible
    assert not window.comp_table_container.isHidden()
    assert "Gizle" in window.toggle_comp_table_btn.text()

    # Toggle to collapse
    window._toggle_comp_table()
    assert window.comp_table_container.isHidden()
    assert "Göster" in window.toggle_comp_table_btn.text()

    # Toggle back to expand
    window._toggle_comp_table()
    assert not window.comp_table_container.isHidden()
    assert "Gizle" in window.toggle_comp_table_btn.text()


def test_solver_method_merged_into_thermo(window):
    """Verify solver_method_combo exists and is functional without a separate solver group."""
    assert hasattr(window, "solver_method_combo")
    assert window.solver_method_combo is not None
    assert window.solver_method_combo.count() > 0
    # First option should be Analytical Jacobian NR
    assert "Analitik Jakobiyen" in window.solver_method_combo.itemText(0)


def test_quick_presets_bar(window):
    """Verify quick presets button bar correctly sets process inputs and updates live metrics."""
    from PyQt5.QtWidgets import QFrame, QPushButton
    bars = window.findChildren(QFrame, "presets_bar")
    assert len(bars) >= 1
    bar = bars[0]
    preset_btns = bar.findChildren(QPushButton)
    assert len(preset_btns) >= 4

    lng_btn = [b for b in preset_btns if "LNG" in b.text()][0]
    lng_btn.click()

    assert window.p_in_edit.text() == "30.0"
    assert window.p_out_edit.text() == "80.0"
    assert window.t_in_edit.text() == "-20.0"
    assert window.flow_edit.text() == "1200000"
    assert window.gas_combo.currentText() == "Methane (CH₄)"

    # Live metrics updated
    badge_text = window.live_metrics_badge.text()
    assert "Basınç Oranı (PR)" in badge_text


def test_theme_header_readability_across_all_themes():
    """Verify all 3 themes (light, dark, engineering) define visible, readable headers and group titles."""
    for theme_key in ["light", "dark", "engineering"]:
        theme_cfg = ThemeManager.THEMES[theme_key]
        qss = ThemeManager.get_stylesheet(theme_key)

        # 1. QGroupBox::title styling must be present with bold font and explicit color
        assert "QGroupBox::title" in qss
        assert "font-weight: bold;" in qss
        assert f"color: {theme_cfg['text']};" in qss

        # 2. Sticky action bar must have distinct border and surface background
        assert "#StickyActionBar" in qss
        assert f"background-color: {theme_cfg['surface']};" in qss

        # 3. Live metrics badge styling must be defined
        assert "#live_metrics_badge" in qss

        # 4. Collapse toggle buttons and preset buttons must be defined
        assert ".collapse_toggle_btn" in qss
        assert ".preset_btn" in qss

        # 5. Header labels (QHeaderView::section)
        assert "QHeaderView::section" in qss
        assert f"color: {theme_cfg['text_secondary']};" in qss or f"color: {theme_cfg['text']};" in qss


def test_responsive_mac_scaling_guard():
    """Verify that macOS Retina displays are protected against 72 DPI downscaling."""
    from unittest.mock import patch, MagicMock

    mock_screen = MagicMock()
    mock_screen.logicalDotsPerInch.return_value = 72.0
    mock_screen.geometry.return_value.width.return_value = 1440
    mock_screen.geometry.return_value.height.return_value = 900

    mock_app = MagicMock()
    mock_app.primaryScreen.return_value = mock_screen

    with patch("PyQt5.QtWidgets.QApplication.instance", return_value=mock_app):
        with patch("sys.platform", "darwin"):
            scale = get_scale_factor()
            assert scale >= 1.0
            pt = scaled_font_pt(9)
            assert pt >= 10
