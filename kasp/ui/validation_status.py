"""
Validation Status Widget for KASP V4

Provides a dashboard showing validation status across all inputs.
"""

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QFrame, QScrollArea, QPushButton)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont
import logging


class ValidationStatusWidget(QWidget):
    """
    Dashboard widget showing validation status for all inputs.
    
    Displays:
    - Overall validation status
    - Individual field statuses with icons
    - Error/warning messages
    - Quick action buttons
    """
    
    fix_all_clicked = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.field_labels = {}  # {field_name: QLabel}
        self._init_ui()
    
    def _init_ui(self):
        """Initialize UI components."""
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)
        
        # Header
        header_layout = QHBoxLayout()
        header_label = QLabel("⚙️ Input Validation Status")
        header_font = QFont()
        header_font.setBold(True)
        header_font.setPointSize(10)
        header_label.setFont(header_font)
        header_layout.addWidget(header_label)
        header_layout.addStretch()
        
        # Overall status indicator
        self.overall_status_label = QLabel("✓ All Valid")
        self.overall_status_label.setProperty("statusType", "valid")
        header_layout.addWidget(self.overall_status_label)
        
        main_layout.addLayout(header_layout)
        
        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        main_layout.addWidget(separator)
        
        # Scroll area for fields
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(200)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        
        fields_widget = QWidget()
        self.fields_layout = QVBoxLayout()
        self.fields_layout.setContentsMargins(0, 0, 0, 0)
        self.fields_layout.setSpacing(3)
        fields_widget.setLayout(self.fields_layout)
        scroll.setWidget(fields_widget)
        
        main_layout.addWidget(scroll)
        
        # Action buttons (initially hidden)
        self.action_layout = QHBoxLayout()
        self.fix_all_btn = QPushButton("🔧 Fix All Issues")
        self.fix_all_btn.setVisible(False)
        self.fix_all_btn.clicked.connect(self.fix_all_clicked.emit)
        self.action_layout.addStretch()
        self.action_layout.addWidget(self.fix_all_btn)
        main_layout.addLayout(self.action_layout)
        
        # Set background and border styling is handled via centralized QSS
        self.setLayout(main_layout)
    
    def update_validation_status(self, validation_manager):
        """
        Update dashboard based on ValidationManager state.
        
        Args:
            validation_manager: ValidationManager instance
        """
        summary = validation_manager.get_validation_summary()
        
        # Update overall status
        if summary['all_valid']:
            self.overall_status_label.setText(f"✓ All Valid ({summary['valid_count']}/{summary['total_fields']})")
            self.overall_status_label.setProperty("statusType", "valid")
            self.fix_all_btn.setVisible(False)
        else:
            self.overall_status_label.setText(
                f"⚠️ {summary['invalid_count']} Issue(s) ({summary['valid_count']}/{summary['total_fields']} valid)"
            )
            self.overall_status_label.setProperty("statusType", "invalid")
            self.fix_all_btn.setVisible(True)
        self.overall_status_label.style().unpolish(self.overall_status_label)
        self.overall_status_label.style().polish(self.overall_status_label)
        
        # Update field statuses
        for field_name, (is_valid, error_msg) in summary['fields'].items():
            if field_name not in self.field_labels:
                # Create new label for this field
                label = QLabel()
                label.setWordWrap(True)
                label.setTextFormat(Qt.RichText)
                self.field_labels[field_name] = label
                self.fields_layout.addWidget(label)
            
            label = self.field_labels[field_name]
            
            # Format field name (convert snake_case to Title Case)
            display_name = field_name.replace('_', ' ').title()
            
            if is_valid:
                if error_msg:  # Warning
                    label.setText(f"⚠️ <b>{display_name}:</b> {error_msg}")
                    label.setProperty("statusType", "warning")
                else:  # Valid
                    label.setText(f"✓ <b>{display_name}:</b> Valid")
                    label.setProperty("statusType", "valid")
            else:  # Invalid
                label.setText(f"❌ <b>{display_name}:</b> {error_msg}")
                label.setProperty("statusType", "invalid")
            label.style().unpolish(label)
            label.style().polish(label)
    
    def add_custom_status(self, field_name, is_valid, message, icon=""):
        """
        Add custom status indicator (e.g., for composition total).
        
        Args:
            field_name: Field identifier
            is_valid: Boolean validation state
            message: Status message
            icon: Optional icon (emoji)
        """
        if field_name not in self.field_labels:
            label = QLabel()
            label.setWordWrap(True)
            label.setTextFormat(Qt.RichText)
            self.field_labels[field_name] = label
            self.fields_layout.addWidget(label)
        
        label = self.field_labels[field_name]
        display_name = field_name.replace('_', ' ').title()
        
        if is_valid:
            label.setText(f"{icon or '✓'} <b>{display_name}:</b> {message}")
            label.setProperty("statusType", "valid")
        else:
            label.setText(f"{icon or '❌'} <b>{display_name}:</b> {message}")
            label.setProperty("statusType", "invalid")
        label.style().unpolish(label)
        label.style().polish(label)
    
    def clear_status(self):
        """Clear all status indicators."""
        for label in self.field_labels.values():
            label.setParent(None)
            label.deleteLater()
        self.field_labels.clear()
        self.overall_status_label.setText("Ready")
        self.overall_status_label.setProperty("statusType", "neutral")
        self.overall_status_label.style().unpolish(self.overall_status_label)
        self.overall_status_label.style().polish(self.overall_status_label)


class MinimalValidationIndicator(QWidget):
    """
    Compact validation indicator for space-constrained UIs.
    Shows only count and color-coded status.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
    
    def _init_ui(self):
        """Initialize minimal UI."""
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 2, 5, 2)
        
        self.icon_label = QLabel("✓")
        self.text_label = QLabel("All inputs valid")
        
        layout.addWidget(self.icon_label)
        layout.addWidget(self.text_label)
        
        self.setLayout(layout)
        self.setProperty("statusType", "valid")
    
    def update_status(self, all_valid, valid_count, total_count):
        """
        Update indicator status.
        
        Args:
            all_valid: Boolean - all inputs valid
            valid_count: Number of valid inputs
            total_count: Total number of inputs
        """
        if all_valid:
            self.icon_label.setText("✓")
            self.text_label.setText(f"All {total_count} inputs valid")
            self.setProperty("statusType", "valid")
        else:
            invalid_count = total_count - valid_count
            self.icon_label.setText("⚠️")
            self.text_label.setText(f"{invalid_count} input(s) need attention")
            self.setProperty("statusType", "invalid")
        self.style().unpolish(self)
        self.style().polish(self)
