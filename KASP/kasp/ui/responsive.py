"""
KASP V4.7 — Responsive UI Module (Level 3)

Features:
- devicePixelRatio-aware scaling (Retina / HiDPI)
- Screen breakpoint system (XS → XL)
- Continuous font scaling via DPI ratio
- DPI-aware StyleSheet generation
- Window geometry persistence helpers
- Scroll-area wrapping for tab content
- Layout-aware stretch factors
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ── Cached screen info (populated on first call) ────────────────────────────
_SCREEN_INFO: dict | None = None


def _screen_info() -> dict:
    """Fetch screen metrics on first call, cache thereafter."""
    global _SCREEN_INFO
    if _SCREEN_INFO is not None:
        return _SCREEN_INFO
    try:
        from PyQt5.QtWidgets import QApplication, QDesktopWidget
        app = QApplication.instance()
        if app is None:
            return {"width": 1920, "height": 1080, "dpi": 96.0, "dpr": 1.0}
        desk = QDesktopWidget()
        geo = desk.availableGeometry(desk.primaryScreen())
        screen = app.primaryScreen()
        dpr = screen.devicePixelRatio() if screen else 1.0
        dpi = screen.logicalDotsPerInch() if screen else 96.0
        _SCREEN_INFO = {
            "width": geo.width(),
            "height": geo.height(),
            "dpi": dpi,
            "dpr": dpr,
        }
        logger.info(
            "✓ Screen info: %d×%d DPI=%.0f DPR=%.1f",
            _SCREEN_INFO["width"], _SCREEN_INFO["height"],
            _SCREEN_INFO["dpi"], _SCREEN_INFO["dpr"],
        )
        return _SCREEN_INFO
    except Exception as exc:
        logger.warning("get_screen_info failed: %s", exc)
        return {"width": 1920, "height": 1080, "dpi": 96.0, "dpr": 1.0}


def invalidate_screen_cache():
    """Clear cached screen info (call when screen config changes)."""
    global _SCREEN_INFO
    _SCREEN_INFO = None


# ── Breakpoints ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ScreenBreakpoint:
    """Layout breakpoint based on available screen width (logical px)."""
    category: str   # "XS" | "SM" | "MD" | "LG" | "XL"
    min_width: int

BREAKPOINTS = (
    ScreenBreakpoint("XL", 1920),
    ScreenBreakpoint("LG", 1680),
    ScreenBreakpoint("MD", 1366),
    ScreenBreakpoint("SM", 1024),
    ScreenBreakpoint("XS", 0),
)


def current_breakpoint() -> ScreenBreakpoint:
    """Return the active breakpoint for the current screen."""
    w = get_screen_geometry()[0]
    for bp in BREAKPOINTS:
        if w >= bp.min_width:
            return bp
    return BREAKPOINTS[-1]


# ── Core geometry / DPI helpers ────────────────────────────────────────────


def get_screen_geometry():
    """Return primary screen available width, height in logical pixels."""
    info = _screen_info()
    return info["width"], info["height"]


def get_dpi() -> float:
    """Return logical DPI of the primary screen."""
    return _screen_info()["dpi"]


def get_device_pixel_ratio() -> float:
    """Return device pixel ratio (1.0 = standard, 2.0 = Retina)."""
    return _screen_info()["dpr"]


def get_scale_factor() -> float:
    """DPI-based scale factor clamped to [0.85, 2.5]."""
    dpi = get_dpi()
    factor = dpi / 96.0
    return max(0.85, min(2.5, factor))


def scaled(px: int) -> int:
    """Scale a pixel value by DPI scale factor (int result)."""
    return round(px * get_scale_factor())


def scaled_float(px: float) -> float:
    """Scale a pixel value by DPI scale factor (float result)."""
    return px * get_scale_factor()


def scaled_font_size(base_pt: int = 9) -> int:
    """Return a continuously-scaled font size from base_pt at 96 DPI."""
    scale = get_scale_factor()
    # Use a damped scale to avoid fonts blowing up on 4K
    damped = 0.5 + 0.5 * scale  # damped range: 0.925–1.75
    pt = round(base_pt * damped)
    return max(7, min(18, pt))


# ── Font application ───────────────────────────────────────────────────────


def apply_responsive_font(app, base_pt: int = 9):
    """Set application-wide font scaled to screen DPI (continuous)."""
    try:
        from PyQt5.QtGui import QFont
        pt = scaled_font_size(base_pt)
        font = QFont("Segoe UI", pt)
        app.setFont(font)
        dpi = get_dpi()
        logger.info("✓ Responsive font: Segoe UI %dpt (DPI=%d)", pt, int(dpi))
    except Exception as exc:
        logger.warning("apply_responsive_font failed: %s", exc)


# ── Window geometry ────────────────────────────────────────────────────────


def compute_initial_window_size(target_w: int = 1700, target_h: int = 950,
                                 max_fraction: float = 0.93):
    """Compute a window size that fits on the current screen."""
    sw, sh = get_screen_geometry()
    # Scale target to DPI
    sf = get_scale_factor()
    tw = round(target_w * sf)
    th = round(target_h * sf)
    w = min(tw, int(sw * max_fraction))
    h = min(th, int(sh * max_fraction))
    w = max(w, 900)
    h = max(h, 550)
    logger.info(
        "✓ Responsive window: %d×%d (screen=%d×%d, target=%d×%d)",
        w, h, sw, sh, target_w, target_h,
    )
    return w, h


def compute_centered_position(w: int, h: int):
    """Return (x, y) to center a window of size w×h on the primary screen."""
    try:
        from PyQt5.QtWidgets import QDesktopWidget
        desk = QDesktopWidget()
        sg = desk.availableGeometry(desk.primaryScreen())
        x = (sg.width() - w) // 2
        y = (sg.height() - h) // 2
        return max(0, x), max(0, y)
    except Exception:
        return 50, 50


def compute_minimum_window_size() -> tuple[int, int]:
    """Return responsive minimum window size based on DPI."""
    return scaled(900), scaled(550)


# ── StyleSheet helpers ─────────────────────────────────────────────────────


def responsive_base_stylesheet() -> str:
    """Return a base DPI-aware Qt StyleSheet for the application."""
    sf = get_scale_factor()
    base_spacing = round(6 * sf)
    radius = round(4 * sf)

    return f"""
    QMainWindow {{
        background-color: palette(window);
    }}
    QGroupBox {{
        font-weight: bold;
        border: 1px solid palette(mid);
        border-radius: {radius}px;
        margin-top: {round(8 * sf)}px;
        padding-top: {round(8 * sf)}px;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: {round(10 * sf)}px;
        padding: 0 {round(3 * sf)}px;
    }}
    QPushButton {{
        padding: {round(6 * sf)}px {round(12 * sf)}px;
        border-radius: {radius}px;
        min-height: {round(20 * sf)}px;
    }}
    QPushButton#verify_perf_btn, QPushButton#run_design_btn {{
        padding: {round(10 * sf)}px {round(20 * sf)}px;
        font-weight: bold;
        font-size: {round(11 * sf)}px;
    }}
    QPushButton#generate_perf_report_btn, QPushButton#generate_report_btn {{
        padding: {round(8 * sf)}px {round(16 * sf)}px;
    }}
    QLabel[resultLabel="true"] {{
        font-size: {round(10 * sf)}px;
        padding: {round(2 * sf)}px;
    }}
    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
        padding: {round(4 * sf)}px {round(6 * sf)}px;
        border: 1px solid palette(mid);
        border-radius: {round(3 * sf)}px;
        min-height: {round(18 * sf)}px;
    }}
    QTableWidget {{
        gridline-color: palette(midlight);
        alternate-background-color: palette(alternate-base);
    }}
    QHeaderView::section {{
        padding: {round(4 * sf)}px {round(6 * sf)}px;
        border: 1px solid palette(mid);
    }}
    QTabWidget::pane {{
        border: 1px solid palette(mid);
        border-radius: {radius}px;
    }}
    QTabBar::tab {{
        padding: {round(6 * sf)}px {round(14 * sf)}px;
        border-top-left-radius: {radius}px;
        border-top-right-radius: {radius}px;
    }}
    QScrollArea {{
        border: none;
    }}
    {
        "QRadioButton, QCheckBox { spacing: " + str(base_spacing) + "px; }"
    }
    QSlider::groove:horizontal {{
        height: {round(6 * sf)}px;
        border-radius: {round(3 * sf)}px;
    }}
    QProgressBar {{
        border: 1px solid palette(mid);
        border-radius: {radius}px;
        text-align: center;
        min-height: {round(16 * sf)}px;
    }}
    QProgressBar::chunk {{
        border-radius: {radius - 1}px;
    }}
    """


# ── Scroll-area wrapping ───────────────────────────────────────────────────


def wrap_in_scroll_area(widget, parent=None):
    """Wrap *widget* in a QScrollArea so content is accessible on small screens."""
    from PyQt5.QtWidgets import QScrollArea
    scroll = QScrollArea(parent)
    scroll.setWidgetResizable(True)
    scroll.setWidget(widget)
    scroll.setFrameShape(QScrollArea.NoFrame)
    return scroll


# ── Breakpoint-aware layout helpers ────────────────────────────────────────


def breakpoint_stretch_factors() -> tuple[int, int]:
    """
    Return (input_stretch, output_stretch) for the two-panel layout.
    On narrow screens, use equal splits; on wide, give more space to results.
    """
    bp = current_breakpoint()
    if bp.category in ("XS", "SM"):
        return 1, 1
    if bp.category == "MD":
        return 1, 2
    return 1, 3  # LG, XL


def breakpoint_two_column() -> bool:
    """Return True if there's enough width for a two-column results layout."""
    bp = current_breakpoint()
    return bp.category in ("LG", "XL")


def breakpoint_graph_columns() -> int:
    """Return number of graph columns for the current breakpoint."""
    bp = current_breakpoint()
    mapping = {"XS": 1, "SM": 1, "MD": 2, "LG": 2, "XL": 3}
    return mapping.get(bp.category, 2)


def breakpoint_table_font_pt() -> int:
    """Return a table-friendly font size based on DPI and breakpoint."""
    base = scaled_font_size(9)
    bp = current_breakpoint()
    if bp.category in ("XS", "SM"):
        return max(7, base - 1)
    return base
