"""
KASP V4.6 — Responsive UI Module

Utilities for dynamic window sizing, DPI-aware font scaling, and
screen-resolution-based layout adjustments.
"""

import logging

logger = logging.getLogger(__name__)


def get_screen_geometry():
    """
    Return the primary screen's width and height in pixels.
    Must be called after QApplication is created.
    """
    try:
        from PyQt5.QtWidgets import QApplication, QDesktopWidget
        app = QApplication.instance()
        if app is None:
            return 1920, 1080  # safe fallback
        desk = QDesktopWidget()
        screen = desk.availableGeometry(desk.primaryScreen())
        return screen.width(), screen.height()
    except Exception as e:
        logger.warning(f"get_screen_geometry failed: {e}")
        return 1920, 1080


def get_dpi():
    """Return logical DPI of the primary screen."""
    try:
        from PyQt5.QtWidgets import QApplication
        app = QApplication.instance()
        if app:
            screen = app.primaryScreen()
            if screen:
                return screen.logicalDotsPerInch()
    except Exception as e:
        logger.warning(f"get_dpi failed: {e}")
    return 96.0  # standard DPI fallback


def get_scale_factor():
    """
    Return a UI scale factor relative to 96 DPI baseline.
    Values: 1.0 at 96 DPI, 1.25 at 120 DPI, 1.5 at 144 DPI etc.
    Clamped between 0.9 and 2.0 for safety.
    """
    dpi = get_dpi()
    factor = dpi / 96.0
    return max(0.9, min(2.0, factor))


def scaled(px: int) -> int:
    """Scale a pixel value by the current DPI scale factor."""
    return int(px * get_scale_factor())


def apply_responsive_font(app, base_pt: int = 9):
    """
    Set application-wide font to an appropriate size based on DPI.
    Must be called after QApplication is created.

    Args:
        app:     QApplication instance
        base_pt: Base font size in points at 96 DPI
    """
    try:
        from PyQt5.QtGui import QFont
        dpi = get_dpi()
        # Scale font slightly on high-DPI but keep readable on low-DPI
        if dpi >= 144:
            pt = base_pt + 2
        elif dpi >= 120:
            pt = base_pt + 1
        else:
            pt = base_pt
        font = QFont("Segoe UI", pt)
        app.setFont(font)
        logger.info(f"✓ Responsive font applied: Segoe UI {pt}pt (DPI={dpi:.0f})")
    except Exception as e:
        logger.warning(f"apply_responsive_font failed: {e}")


def compute_initial_window_size(target_w: int = 1700, target_h: int = 950,
                                 max_fraction: float = 0.93):
    """
    Compute a window size that fits on the current screen.

    Args:
        target_w:     Preferred width in pixels
        target_h:     Preferred height in pixels
        max_fraction: Maximum fraction of screen to use (0.0–1.0)

    Returns:
        (width, height) tuple
    """
    sw, sh = get_screen_geometry()
    w = min(target_w, int(sw * max_fraction))
    h = min(target_h, int(sh * max_fraction))
    # Never go below a usable minimum
    w = max(w, 900)
    h = max(h, 550)
    logger.info(
        f"✓ Responsive window size: {w}×{h} "
        f"(screen={sw}×{sh}, target={target_w}×{target_h})"
    )
    return w, h
