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
            "primary": "#2196F3",
            "secondary": "#FFC107",
            "success": "#4CAF50",
            "warning": "#FF9800",
            "danger": "#F44336",
            "background": "#FFFFFF",
            "surface": "#F5F5F5",
            "text": "#212121",
            "text_secondary": "#757575",
            "border": "#E0E0E0",
            "success_bg": "#e8f5e9",
            "success_text": "#2e7d32",
            "success_border": "#a5d6a7",
            "danger_bg": "#ffe6e6",
            "danger_text": "#c62828",
            "danger_border": "#ef9a9a",
            "warning_bg": "#fff3e0",
            "warning_text": "#b25300",
            "warning_border": "#ffe0b2"
        },
        "dark": {
            "primary": "#2196F3",
            "secondary": "#FFC107",
            "success": "#66BB6A",
            "warning": "#FFA726",
            "danger": "#EF5350",
            "background": "#1E1E1E",
            "surface": "#2D2D2D",
            "text": "#FFFFFF",
            "text_secondary": "#B0B0B0",
            "border": "#3D3D3D",
            "success_bg": "#1b5e20",
            "success_text": "#a5d6a7",
            "success_border": "#2e7d32",
            "danger_bg": "#2d1010",
            "danger_text": "#ff8a80",
            "danger_border": "#881b1b",
            "warning_bg": "#2d1f10",
            "warning_text": "#fbbf24",
            "warning_border": "#78350f"
        },
        "engineering": {
            "primary": "#00796B",
            "secondary": "#FF6F00",
            "success": "#388E3C",
            "warning": "#F57C00",
            "danger": "#D32F2F",
            "background": "#FAFAFA",
            "surface": "#FFFFFF",
            "text": "#263238",
            "text_secondary": "#607D8B",
            "border": "#CFD8DC",
            "success_bg": "#e8f5e9",
            "success_text": "#2e7d32",
            "success_border": "#a5d6a7",
            "danger_bg": "#ffe6e6",
            "danger_text": "#c62828",
            "danger_border": "#ef9a9a",
            "warning_bg": "#fff3e0",
            "warning_text": "#b25300",
            "warning_border": "#ffe0b2"
        }
    }
    
    @staticmethod
    def apply_theme(theme_name: str = "light"):
        """Apply theme to application"""
        if theme_name not in ThemeManager.THEMES:
            theme_name = "light"
        
        theme = ThemeManager.THEMES[theme_name]
        
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
            
            /* Group Boxes with theme border and primary-colored titles */
            QGroupBox {{
                background-color: transparent;
                color: {theme['text']};
                font-weight: bold;
                border: 1px solid {theme['border']};
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 12px;
            }}
            
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 5px;
                left: 10px;
                color: {theme['primary']};
            }}
            
            /* Buttons */
            QPushButton {{
                background-color: {theme['primary']};
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }}
            
            QPushButton:hover {{
                background-color: {theme['secondary']};
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
                border-radius: 4px;
                padding: 6px;
                color: {theme['text']};
            }}
            
            QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, 
            QDoubleSpinBox:focus, QComboBox:focus {{
                border: 2px solid {theme['primary']};
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
                font-size: 9pt;
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
                padding: 12px;
                border-radius: 6px;
                font-size: 14px;
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
                padding: 12px;
                border-radius: 6px;
                font-size: 14px;
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
                font-size: 9pt;
            }}
            
            QLabel#progress_time_label {{
                color: {theme['primary']};
                font-size: 9pt;
            }}
            
            QLabel#version_label {{
                color: {theme['text_secondary']};
                padding: 0 8px;
            }}
            
            QPushButton#verify_perf_btn {{
                background-color: {theme['secondary']};
                color: white;
                font-weight: bold;
                padding: 10px;
            }}
            QPushButton#verify_perf_btn:hover {{
                background-color: {theme['primary']};
            }}
            
            QPushButton#generate_perf_report_btn {{
                background-color: {theme['primary']};
                color: white;
                font-weight: bold;
                padding: 10px;
            }}
            QPushButton#generate_perf_report_btn:hover {{
                background-color: {theme['secondary']};
            }}
            
            QLabel[resultLabel="true"] {{
                font-weight: bold;
                font-size: 15px;
            }}
            
            QLabel#consistency_info_label {{
                font-size: 10pt;
                padding: 5px;
            }}
            
            QLabel#fallback_info_label {{
                font-size: 10pt;
                padding: 6px;
            }}
            
            QLabel#value_label {{
                font-weight: bold;
                min-width: 80px;
            }}
            
            QLabel#default_graph_label {{
                font-size: 16px;
                color: {theme['text_secondary']};
                padding: 50px;
            }}
            
            /* Tables */
            QTableWidget {{
                background-color: {theme['surface']};
                alternate-background-color: {theme['background']};
                gridline-color: {theme['border']};
                border: 1px solid {theme['border']};
                border-radius: 4px;
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
                border-bottom: 2px solid {theme['primary']};
                font-weight: bold;
            }}
            
            /* Tabs */
            QTabWidget::pane {{
                border: 1px solid {theme['border']};
                border-radius: 4px;
                background-color: {theme['surface']};
            }}
            
            QTabBar::tab {{
                background-color: {theme['background']};
                color: {theme['text_secondary']};
                padding: 10px 20px;
                border: 1px solid {theme['border']};
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
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
                width: 12px;
                border-radius: 6px;
            }}
            
            QScrollBar::handle:vertical {{
                background-color: {theme['text_secondary']};
                border-radius: 6px;
                min-height: 20px;
            }}
            
            QScrollBar::handle:vertical:hover {{
                background-color: {theme['primary']};
            }}
            
            /* Tool Tips */
            QToolTip {{
                background-color: {theme['text']};
                color: {theme['background']};
                border: 1px solid {theme['border']};
                padding: 5px;
                border-radius: 4px;
            }}
        """
        
        QApplication.instance().setStyleSheet(stylesheet)
    
    @staticmethod
    def get_icon_color(theme_name: str = "light") -> str:
        """Get appropriate icon color for theme"""
        theme = ThemeManager.THEMES.get(theme_name, ThemeManager.THEMES["light"])
        return theme["text"]
