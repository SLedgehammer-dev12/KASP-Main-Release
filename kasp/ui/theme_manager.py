"""
KASP Theme Manager
Provides modern, professional themes and UI customization
"""

from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QPalette, QColor
from PyQt5.QtCore import Qt

class ThemeManager:
    """Manages application themes and styling"""
    
    # Modern color schemes
    # Modern color schemes with theme-aware warning variables and contrast safeguards
    THEMES = {
        "light": {
            "primary": "#0F62FE",
            "secondary": "#6F42C1",
            "success": "#198754",
            "warning": "#FD7E14",
            "danger": "#DC3545",
            "background": "#F8F9FA",
            "surface": "#FFFFFF",
            "text": "#1C1917",
            "text_secondary": "#6B7280",
            "border": "#E5E7EB",
            "success_bg": "#DCFCE7",
            "success_text": "#15803D",
            "success_border": "#BBF7D0",
            "danger_bg": "#FEE2E2",
            "danger_text": "#B91C1C",
            "danger_border": "#FECACA",
            "warning_bg": "#FEF3C7",
            "warning_text": "#B45309",
            "warning_border": "#FDE68A"
        },
        "dark": {
            "primary": "#3B82F6",
            "secondary": "#A855F7",
            "success": "#10B981",
            "warning": "#F59E0B",
            "danger": "#EF4444",
            "background": "#0F172A",
            "surface": "#1E293B",
            "text": "#F8FAFC",
            "text_secondary": "#94A3B8",
            "border": "#334155",
            "success_bg": "#064E3B",
            "success_text": "#34D399",
            "success_border": "#059669",
            "danger_bg": "#7F1D1D",
            "danger_text": "#FCA5A5",
            "danger_border": "#B91C1C",
            "warning_bg": "#78350F",
            "warning_text": "#FBBF24",
            "warning_border": "#D97706"
        },
        "engineering": {
            "primary": "#00B4D8",
            "secondary": "#FF6F00",
            "success": "#2ECC71",
            "warning": "#F39C12",
            "danger": "#E74C3C",
            "background": "#0E1726",
            "surface": "#1A2332",
            "text": "#E2E8F0",
            "text_secondary": "#94A3B8",
            "border": "#2E3A4E",
            "success_bg": "#1B3B2B",
            "success_text": "#2ECC71",
            "success_border": "#27AE60",
            "danger_bg": "#3B1C1C",
            "danger_text": "#E74C3C",
            "danger_border": "#C0392B",
            "warning_bg": "#3B2C1C",
            "warning_text": "#F39C12",
            "warning_border": "#D35400"
        }
    }
    
    @staticmethod
    def apply_theme(theme_name: str = "light"):
        """Apply theme to application"""
        if theme_name not in ThemeManager.THEMES:
            theme_name = "light"

        theme = ThemeManager.THEMES[theme_name]

        try:
            from kasp.ui.responsive import scaled_px, scaled_font_pt
            _px = lambda v: scaled_px(v)
            _pt = lambda v: scaled_font_pt(v)
        except Exception:
            _px = lambda v: v
            _pt = lambda v: v

        stylesheet = f"""
            /* Main Window & Dialogs */
            QMainWindow, QDialog, QAbstractScrollArea {{
                background-color: {theme['background']};
                color: {theme['text']};
            }}
            
            /* Text Labels (Transparent background protects against leakage) */
            QLabel {{
                background-color: transparent;
                color: {theme['text']};
            }}
            
            QLabel:disabled {{
                color: {theme['text_secondary']};
            }}
            
            /* Specific Warning Banner styling */
            QLabel#fallback_info_label {{
                background-color: {theme['warning_bg']};
                color: {theme['warning_text']};
                border: 1px solid {theme['warning_border']};
                border-radius: 4px;
            }}
            
            /* Checkboxes & Radio Buttons */
            QCheckBox, QRadioButton {{
                background-color: transparent;
                color: {theme['text']};
            }}
            
            QCheckBox:disabled, QRadioButton:disabled {{
                color: {theme['text_secondary']};
            }}
            
            /* Group Boxes with theme border and primary-colored titles */
            QGroupBox {{
                background-color: transparent;
                color: {theme['text']};
                font-weight: bold;
                border: 1px solid {theme['border']};
                border-radius: 8px;
                margin-top: {_px(14)}px;
                padding-top: {_px(14)}px;
            }}
            
            QGroupBox:disabled {{
                color: {theme['text_secondary']};
            }}
            
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 6px;
                left: 10px;
                color: {theme['primary']};
            }}
            
            /* Buttons */
            QPushButton {{
                background-color: {theme['primary']};
                color: white;
                border: 1px solid rgba(0, 0, 0, 0.1);
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: bold;
            }}
            
            QPushButton:hover {{
                background-color: {theme['secondary']};
                border: 1px solid rgba(255, 255, 255, 0.15);
            }}
            
            QPushButton:pressed {{
                background-color: {theme['text_secondary']};
            }}
            
            QPushButton:disabled {{
                background-color: {theme['border']};
                color: {theme['text_secondary']};
            }}
            
            /* Input Fields */
            QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
                background-color: {theme['surface']};
                border: 1px solid {theme['border']};
                border-radius: 6px;
                padding: {_px(6)}px;
                color: {theme['text']};
            }}
            
            QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, 
            QDoubleSpinBox:focus, QComboBox:focus {{
                border: 2px solid {theme['primary']};
                background-color: {theme['background']};
            }}
            
            QLineEdit:disabled, QTextEdit:disabled, QSpinBox:disabled, 
            QDoubleSpinBox:disabled, QComboBox:disabled {{
                background-color: {theme['surface']};
                color: {theme['text_secondary']};
                border: 1px solid {theme['border']};
            }}
            
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: {_px(24)}px;
                border-left-width: 1px;
                border-left-color: {theme['border']};
                border-left-style: solid;
                border-top-right-radius: 6px;
                border-bottom-right-radius: 6px;
            }}
            
            QComboBox::down-arrow {{
                image: none;
                border: none;
            }}
            
            QComboBox QAbstractItemView {{
                background-color: {theme['surface']};
                border: 1px solid {theme['border']};
                border-radius: 6px;
                selection-background-color: {theme['primary']};
                selection-color: white;
                color: {theme['text']};
                padding: {_px(4)}px;
            }}
            
            /* Validation States via Dynamic Properties */
            QLineEdit[validationState="neutral"], QComboBox[validationState="neutral"] {{
                border: 1px solid {theme['border']};
                background-color: {theme['surface']};
                color: {theme['text']};
            }}
            QLineEdit[validationState="valid"], QComboBox[validationState="valid"] {{
                border: 2px solid {theme['success_border']};
                background-color: {theme['success_bg']};
                color: {theme['success_text']};
            }}
            QLineEdit[validationState="invalid"], QComboBox[validationState="invalid"] {{
                border: 2px solid {theme['danger_border']};
                background-color: {theme['danger_bg']};
                color: {theme['danger_text']};
            }}
            QLineEdit[validationState="warning"], QComboBox[validationState="warning"] {{
                border: 2px solid {theme['warning_border']};
                background-color: {theme['warning_bg']};
                color: {theme['warning_text']};
            }}

            /* Custom Object Styles */
            QFrame#HelpGuidancePanel {{
                background-color: {theme['surface']};
                border: 1px solid {theme['border']};
                border-left: 5px solid {theme['primary']};
                border-radius: 4px;
            }}
            
            QLabel#help_guidance_text {{
                color: {theme['text']};
            }}
            
            ValidationStatusWidget {{
                background-color: {theme['surface']};
                border: 1px solid {theme['border']};
                border-radius: 5px;
            }}
            
            QLabel[statusType="valid"] {{
                color: {theme['success_text']};
                font-weight: bold;
            }}
            QLabel[statusType="invalid"] {{
                color: {theme['danger_text']};
                font-weight: bold;
            }}
            QLabel[statusType="warning"] {{
                color: {theme['warning_text']};
                font-weight: bold;
            }}
            
            MinimalValidationIndicator {{
                border-radius: 3px;
                padding: 2px;
            }}
            MinimalValidationIndicator[statusType="valid"] {{
                background-color: {theme['success_bg']};
                color: {theme['success_text']};
            }}
            MinimalValidationIndicator[statusType="invalid"] {{
                background-color: {theme['danger_bg']};
                color: {theme['danger_text']};
            }}
            
            QLabel#comp_total_label[compTotalState="valid"] {{
                color: {theme['success_text']};
                font-weight: bold;
            }}
            QLabel#comp_total_label[compTotalState="invalid"] {{
                color: {theme['danger_text']};
                font-weight: bold;
            }}
            QLabel#comp_total_label[compTotalState="warning"] {{
                color: {theme['warning_text']};
                font-weight: bold;
            }}
            
            QLabel#ic_label {{
                font-weight: bold;
                color: {theme['primary']};
                font-size: {_pt(9)}pt;
            }}
            QLabel#ic_label:disabled {{
                color: {theme['text_secondary']};
            }}
            
            QLabel#consistency_separator {{
                font-weight: bold;
                color: {theme['primary']};
            }}
            
            QPushButton#calculate_btn {{
                background-color: {theme['success']};
                color: white;
                font-weight: bold;
                padding: {_px(12)}px;
                border-radius: 6px;
                font-size: {_pt(14)}px;
            }}
            QPushButton#calculate_btn:hover {{
                background-color: {theme['success_text']};
            }}
            QPushButton#calculate_btn:disabled {{
                background-color: {theme['border']};
                color: {theme['text_secondary']};
            }}
            
            QPushButton#stop_btn {{
                background-color: {theme['danger']};
                color: white;
                font-weight: bold;
                padding: {_px(12)}px;
                border-radius: 6px;
                font-size: {_pt(14)}px;
            }}
            QPushButton#stop_btn:hover {{
                background-color: {theme['danger_text']};
            }}
            QPushButton#stop_btn:disabled {{
                background-color: {theme['border']};
                color: {theme['text_secondary']};
            }}
            
            QLabel#progress_status_label {{
                color: {theme['text_secondary']};
                font-size: {_pt(9)}pt;
            }}
            
            QLabel#progress_time_label {{
                color: {theme['primary']};
                font-size: {_pt(9)}pt;
            }}
            
            QLabel#version_label {{
                color: {theme['text_secondary']};
                padding: 0 {_px(8)}px;
            }}
            
            QPushButton#verify_perf_btn {{
                background-color: {theme['secondary']};
                color: white;
                font-weight: bold;
                padding: {_px(10)}px;
            }}
            QPushButton#verify_perf_btn:hover {{
                background-color: {theme['primary']};
            }}
            
            QPushButton#generate_perf_report_btn {{
                background-color: {theme['primary']};
                color: white;
                font-weight: bold;
                padding: {_px(10)}px;
            }}
            QPushButton#generate_perf_report_btn:hover {{
                background-color: {theme['secondary']};
            }}
            
            QLabel[resultLabel="true"] {{
                font-weight: bold;
                font-size: {_pt(15)}px;
            }}
            
            QLabel#consistency_info_label {{
                font-size: {_pt(10)}pt;
                padding: {_px(5)}px;
            }}
            
            QLabel#fallback_info_label {{
                font-size: {_pt(10)}pt;
                padding: {_px(6)}px;
            }}
            
            QLabel#value_label {{
                font-weight: bold;
                min-width: {_px(80)}px;
            }}
            
            QLabel#default_graph_label {{
                font-size: {_pt(16)}px;
                color: {theme['text_secondary']};
                padding: {_px(50)}px;
            }}
            
            /* Tables */
            QTableWidget {{
                background-color: {theme['surface']};
                alternate-background-color: {theme['background']};
                gridline-color: {theme['border']};
                border: 1px solid {theme['border']};
                border-radius: 8px;
            }}
            
            QTableWidget::item {{
                padding: 8px;
            }}
            
            QTableWidget::item:selected {{
                background-color: {theme['primary']};
                color: white;
            }}
            
            QHeaderView::section {{
                background-color: {theme['surface']};
                color: {theme['text']};
                padding: 8px;
                border: none;
                border-bottom: 3px solid {theme['primary']};
                font-weight: bold;
            }}
            
            /* Tabs */
            QTabWidget::pane {{
                border: 1px solid {theme['border']};
                border-radius: 8px;
                background-color: {theme['surface']};
            }}
            
            QTabBar::tab {{
                background-color: {theme['background']};
                color: {theme['text_secondary']};
                padding: {_px(10)}px {_px(20)}px;
                border: 1px solid {theme['border']};
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 2px;
            }}
            
            QTabBar::tab:selected {{
                background-color: {theme['surface']};
                color: {theme['primary']};
                font-weight: bold;
                border-bottom: 3px solid {theme['primary']};
            }}
            
            /* Menu Bar */
            QMenuBar {{
                background-color: {theme['surface']};
                border-bottom: 1px solid {theme['border']};
            }}
            
            QMenuBar::item {{
                padding: 8px 12px;
                background-color: transparent;
            }}
            
            QMenuBar::item:selected {{
                background-color: {theme['primary']};
                color: white;
            }}
            
            QMenu {{
                background-color: {theme['surface']};
                border: 1px solid {theme['border']};
            }}
            
            QMenu::item:selected {{
                background-color: {theme['primary']};
                color: white;
            }}
            
            /* Status Bar */
            QStatusBar {{
                background-color: {theme['surface']};
                border-top: 1px solid {theme['border']};
                color: {theme['text_secondary']};
            }}
            
            /* Progress Bar */
            QProgressBar {{
                border: 1px solid {theme['border']};
                border-radius: 4px;
                text-align: center;
                background-color: {theme['surface']};
            }}
            
            QProgressBar::chunk {{
                background-color: {theme['primary']};
                border-radius: 3px;
            }}
            
            /* Scroll Bars */
            QScrollBar:vertical {{
                background-color: {theme['surface']};
                width: {_px(8)}px;
                border-radius: 4px;
            }}
            
            QScrollBar::handle:vertical {{
                background-color: {theme['text_secondary']};
                border-radius: 4px;
                min-height: {_px(20)}px;
            }}
            
            QScrollBar::handle:vertical:hover {{
                background-color: {theme['primary']};
            }}
            
            QScrollBar:horizontal {{
                background-color: {theme['surface']};
                height: {_px(8)}px;
                border-radius: 4px;
            }}
            
            QScrollBar::handle:horizontal {{
                background-color: {theme['text_secondary']};
                border-radius: 4px;
                min-width: {_px(20)}px;
            }}
            
            QScrollBar::handle:horizontal:hover {{
                background-color: {theme['primary']};
            }}
            
            QScrollBar::add-line, QScrollBar::sub-line,
            QScrollBar::add-page, QScrollBar::sub-page {{
                background: none;
                border: none;
            }}
            
            /* Tool Tips */
            QToolTip {{
                background-color: {theme['text']};
                color: {theme['background']};
                border: 1px solid {theme['border']};
                padding: {_px(5)}px;
                border-radius: 4px;
            }}
        """
        
        QApplication.instance().setStyleSheet(stylesheet)
    
    @staticmethod
    def get_icon_color(theme_name: str = "light") -> str:
        """Get appropriate icon color for theme"""
        theme = ThemeManager.THEMES.get(theme_name, ThemeManager.THEMES["light"])
        return theme["text"]
