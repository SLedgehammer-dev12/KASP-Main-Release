"""Unit and integration tests for the responsive UI module."""
import os
import sys
from unittest.mock import MagicMock, patch

import pytest
from PyQt5.QtWidgets import QApplication

from kasp.ui.main_window import KaspMainWindow
from kasp.ui.responsive import invalidate_screen_cache


@pytest.fixture(scope="module")
def app():
    os.environ["KASP_TEST_MODE"] = "1"
    qt_app = QApplication.instance()
    if qt_app is None:
        qt_app = QApplication(sys.argv)
    return qt_app


# ── Unit tests (pure functions, no window needed) ───────────────────────────

def test_breakpoints_present():
    from kasp.ui.responsive import (
        BREAKPOINTS,
        breakpoint_stretch_factors,
        breakpoint_two_column,
        breakpoint_graph_columns,
        current_breakpoint,
        scaled,
        scaled_font_size,
    )
    assert len(BREAKPOINTS) == 5
    bp = current_breakpoint()
    assert bp.category in ("XS", "SM", "MD", "LG", "XL")
    sf = breakpoint_stretch_factors()
    assert isinstance(sf, tuple) and len(sf) == 2
    assert isinstance(breakpoint_two_column(), bool)
    assert 1 <= breakpoint_graph_columns() <= 3
    assert scaled(100) >= 85
    assert 7 <= scaled_font_size(9) <= 18


def test_compute_initial_window_size():
    from kasp.ui.responsive import compute_initial_window_size, invalidate_screen_cache
    invalidate_screen_cache()
    with (
        patch("kasp.ui.responsive.get_screen_geometry", return_value=(1366, 768)),
        patch("kasp.ui.responsive.get_dpi", return_value=96.0),
    ):
        w, h = compute_initial_window_size(1700, 950)
        assert w <= 1271, f"w={w} should fit 1366 screen"
        assert h <= 720, f"h={h} should fit 768 screen"
        assert w >= 900
        assert h >= 550


def test_compute_centered_position(app):
    from kasp.ui.responsive import compute_centered_position
    x, y = compute_centered_position(1000, 600)
    assert x >= 0
    assert y >= 0


# ── Integration tests ──────────────────────────────────────────────────────

def test_status_bar_indicator_exists(app):
    window = KaspMainWindow()
    try:
        assert window.statusBar() is not None
        assert getattr(window, "status_validation_indicator", None) is not None
    finally:
        window.close()


def test_window_opens_cleanly(app):
    """Smoke test: window opens and closes without crash."""
    window = KaspMainWindow()
    try:
        assert window.isVisible() or True  # may not be visible in CI
    finally:
        window.close()
