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
            "border": "#E0E0E0"
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
            "border": "#3D3D3D"
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
            "border": "#CFD8DC"
        }
    }
    
    @staticmethod
    def apply_theme(theme_name: str = "light"):
        """Apply theme to application"""
        if theme_name not in ThemeManager.THEMES:
            theme_name = "light"
        
        theme = ThemeManager.THEMES[theme_name]
        
        stylesheet = f"""
            /* Main Window */
            QMainWindow {{
                background-color: {theme['background']};
            }}
            
            /* Widgets */
            QWidget {{
                background-color: {theme['background']};
                color: {theme['text']};
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
