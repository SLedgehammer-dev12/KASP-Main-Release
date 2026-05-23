"""
KASP V4.7 — Responsive UI Module

Utilities for dynamic window sizing, DPI-aware font scaling,
screen-resolution-based layout adjustments, and breakpoint-driven
compact/comfortable mode switching.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Breakpoint thresholds (pixels)
# ---------------------------------------------------------------------------
BP_SMALL_MAX = 1366
BP_MEDIUM_MAX = 1920
BP_LARGE_MAX = 2560


# ---------------------------------------------------------------------------
# Screen geometry
# ---------------------------------------------------------------------------

def get_screen_geometry():
    """Return the primary screen's available width and height in pixels."""
    try:
        from PyQt5.QtWidgets import QApplication, QDesktopWidget

        app = QApplication.instance()
        if app is None:
            return 1920, 1080
        desk = QDesktopWidget()
        screen = desk.availableGeometry(desk.primaryScreen())
        return screen.width(), screen.height()
    except Exception as exc:
        logger.warning(f"get_screen_geometry failed: {exc}")
        return 1920, 1080


# ---------------------------------------------------------------------------
# DPI helpers
# ---------------------------------------------------------------------------

def get_dpi():
    """Return logical DPI of the primary screen."""
    try:
        from PyQt5.QtWidgets import QApplication

        app = QApplication.instance()
        if app:
            screen = app.primaryScreen()
            if screen:
                return screen.logicalDotsPerInch()
    except Exception as exc:
        logger.warning(f"get_dpi failed: {exc}")
    return 96.0


def get_scale_factor():
    """Return UI scale factor relative to 96 DPI baseline.  Clamped [0.85, 2.2]."""
    dpi = get_dpi()
    factor = dpi / 96.0
    return max(0.85, min(2.2, factor))


# ---------------------------------------------------------------------------
# Screen category / breakpoints
# ---------------------------------------------------------------------------

def get_screen_category() -> str:
    """
    Return a human-readable screen-size category.

    Returns one of: 'small' (≤1366), 'medium' (≤1920),
    'large' (≤2560), 'ultrawide' (>2560).
    """
    sw, _sh = get_screen_geometry()
    if sw <= BP_SMALL_MAX:
        return "small"
    if sw <= BP_MEDIUM_MAX:
        return "medium"
    if sw <= BP_LARGE_MAX:
        return "large"
    return "ultrawide"


def is_small_screen() -> bool:
    return get_screen_category() == "small"


def is_medium_screen() -> bool:
    return get_screen_category() == "medium"


def is_large_screen() -> bool:
    return get_screen_category() in ("large", "ultrawide")


# ---------------------------------------------------------------------------
# User-configured UI scale (optional multiplier)
# ---------------------------------------------------------------------------

def get_ui_scale() -> float:
    """
    Return the user-chosen UI-scale preference.

    Reads ``app.ui_scale`` from the config manager.  Valid values are
    ``0.85`` (compact), ``1.0`` (normal) and ``1.25`` (large).
    Falls back to 1.0 when the config is not available.
    """
    try:
        from kasp.config_manager import get_config_manager

        value = get_config_manager().get("app.ui_scale", 1.0)
    except Exception:
        value = 1.0
    try:
        value = float(value)
    except (TypeError, ValueError):
        value = 1.0
    return max(0.7, min(1.5, value))


# ---------------------------------------------------------------------------
# Unified scaling helpers (DPI × user-scale)
# ---------------------------------------------------------------------------

def _combined_scale() -> float:
    """DPI scale factor × user UI-scale preference."""
    return get_scale_factor() * get_ui_scale()


def scaled_px(px: int) -> int:
    """Scale a **pixel** value by the combined (DPI × user) scale factor."""
    return max(1, int(px * _combined_scale()))


def scaled_spacing(base: int) -> int:
    """Scale a spacing / margin value (pixels).  Alias for ``scaled_px``."""
    return scaled_px(base)


def scaled_font_pt(base_pt: int) -> int:
    """
    Return a DPI-aware font point-size.

    High-DPI screens get an extra 1–2 pt boost on top of the base value.
    The result also accounts for the screen category so that fonts stay
    readable on small laptop displays.
    """
    dpi = get_dpi()
    cat = get_screen_category()

    # High-DPI bump
    if dpi >= 192:
        bump = 3
    elif dpi >= 144:
        bump = 2
    elif dpi >= 120:
        bump = 1
    else:
        bump = 0

    # Small screens → keep fonts compact
    if cat == "small":
        bump = max(0, bump - 1)

    return max(7, base_pt + bump)


# ---------------------------------------------------------------------------
# Convenience pixel shortcuts  (legacy + new)
# ---------------------------------------------------------------------------

def scaled(px: int) -> int:
    """Legacy alias — delegates to ``scaled_px``."""
    return scaled_px(px)


# ---------------------------------------------------------------------------
# Window geometry
# ---------------------------------------------------------------------------

def compute_initial_window_size(
    target_w: int = 1700,
    target_h: int = 950,
    max_fraction: float = 0.93,
):
    """
    Compute a window size that fits on the current screen.

    Returns a ``(width, height)`` tuple.
    """
    sw, sh = get_screen_geometry()
    w = min(target_w, int(sw * max_fraction))
    h = min(target_h, int(sh * max_fraction))
    w = max(w, scaled_px(900))
    h = max(h, scaled_px(550))
    logger.info(
        f"✓ Responsive window size: {w}×{h} "
        f"(screen={sw}×{sh}, target={target_w}×{target_h})"
    )
    return w, h


def dialog_size(pct_w: float, pct_h: float):
    """
    Return a dialog ``(width, height)`` expressed as a **fraction**
    of the available screen geometry.

    Example: ``dialog_size(0.4, 0.35)`` → ~768 × 378 on a 1920×1080 screen.
    """
    sw, sh = get_screen_geometry()
    w = max(320, int(sw * pct_w))
    h = max(240, int(sh * pct_h))
    return w, h


# ---------------------------------------------------------------------------
# Application-wide responsive font
# ---------------------------------------------------------------------------

def apply_responsive_font(app, base_pt: int = 9):
    """
    Set application-wide font to a DPI-aware size.

    Must be called **after** ``QApplication`` is created.
    """
    try:
        from PyQt5.QtGui import QFont

        pt = scaled_font_pt(base_pt)
        font = QFont("Segoe UI", pt)
        app.setFont(font)
        logger.info(
            f"✓ Responsive font: Segoe UI {pt}pt "
            f"(base={base_pt}, DPI={get_dpi():.0f}, "
            f"cat={get_screen_category()})"
        )
    except Exception as exc:
        logger.warning(f"apply_responsive_font failed: {exc}")


# ---------------------------------------------------------------------------
# Compact-mode helper
# ---------------------------------------------------------------------------

def compact_padding() -> int:
    """Return the recommended content padding for the current screen size."""
    if is_small_screen():
        return scaled_px(2)
    return scaled_px(4)


def compact_spacing() -> int:
    """Return the recommended layout spacing for the current screen size."""
    if is_small_screen():
        return scaled_px(3)
    return scaled_px(6)


def compact_font_delta() -> int:
    """Small negative delta to shrink fonts on tiny screens."""
    return -1 if is_small_screen() else 0
