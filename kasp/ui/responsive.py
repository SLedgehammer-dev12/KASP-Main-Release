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
    import sys

    dpi = get_dpi()
    if sys.platform == "darwin":
        # macOS uses Cocoa points (72 pt/in) with Retina DPR (2.0).
        # Prevent 72/96 = 0.75 from penalizing Retina MacBooks with downscaling.
        return max(1.0, min(2.2, dpi / 72.0))
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
    import sys

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

    if sys.platform == "darwin":
        # On macOS Retina displays (e.g., 13" MacBook M1 Pro), Apple standard text
        # is 13pt body / 11pt subhead. Ensure comfortable readability for small base sizes.
        if base_pt < 11:
            bump = max(bump, 1)

    # Small screens → keep fonts compact (except macOS where point grid is standard)
    if cat == "small" and sys.platform != "darwin":
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
    max_w = int(sw * max_fraction)
    max_h = int(sh * max_fraction)
    w = min(target_w, max_w)
    h = min(target_h, max_h)
    w = max(w, min(900, max_w))
    h = max(h, min(550, max_h))
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
        import sys
        from PyQt5.QtGui import QFont

        # On macOS Retina displays, boost 9pt base to at least 10pt for comfortable reading
        effective_base = 10 if sys.platform == "darwin" and base_pt < 10 else base_pt
        pt = scaled_font_pt(effective_base)
        font_family = "Helvetica Neue, Arial, Segoe UI" if sys.platform == "darwin" else "SF Pro, Segoe UI, Helvetica Neue, Arial"
        font = QFont(font_family, pt)
        app.setFont(font)
        logger.info(
            f"✓ Responsive font: {font_family} {pt}pt "
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


# ---------------------------------------------------------------------------
# Legacy compatibility helpers
# ---------------------------------------------------------------------------

class _BreakpointMeta:
    def __init__(self, category: str):
        self.category = category

BREAKPOINTS = [
    _BreakpointMeta("XS"),
    _BreakpointMeta("SM"),
    _BreakpointMeta("MD"),
    _BreakpointMeta("LG"),
    _BreakpointMeta("XL"),
]


def current_breakpoint() -> _BreakpointMeta:
    cat = get_screen_category()
    mapping = {"small": "SM", "medium": "MD", "large": "LG", "ultrawide": "XL"}
    return _BreakpointMeta(mapping.get(cat, "MD"))


def breakpoint_stretch_factors() -> tuple[int, int]:
    cat = get_screen_category()
    if cat == "small":
        return 1, 1
    if cat == "medium":
        return 1, 2
    return 1, 3


def breakpoint_two_column() -> bool:
    return is_large_screen()


def breakpoint_graph_columns() -> int:
    cat = get_screen_category()
    mapping = {"small": 1, "medium": 2, "large": 2, "ultrawide": 3}
    return mapping.get(cat, 2)


def scaled_font_size(pt: int) -> int:
    return scaled_font_pt(pt)


def invalidate_screen_cache():
    pass


def compute_centered_position(w: int, h: int) -> tuple[int, int]:
    try:
        from PyQt5.QtWidgets import QDesktopWidget
        desk = QDesktopWidget()
        sg = desk.availableGeometry(desk.primaryScreen())
        x = (sg.width() - w) // 2
        y = (sg.height() - h) // 2
        return max(0, x), max(0, y)
    except Exception:
        return 50, 50

