"""
KASP Error Handler
Centralized error handling and recovery mechanisms
"""

import sys
import traceback
import logging
from typing import Callable, Any
from functools import wraps
from PyQt5.QtWidgets import QMessageBox

logger = logging.getLogger(__name__)

class ErrorHandler:
    """Global error handler with user-friendly messages"""
    
    ERROR_MESSAGES = {
        "database": {
            "tr": "Veritabanı hatası oluştu. Lütfen programı yeniden başlatın.",
            "en": "Database error occurred. Please restart the application."
        },
        "calculation": {
            "tr": "Hesaplama hatası. Lütfen girdi değerlerini kontrol edin.",
            "en": "Calculation error. Please check input values."
        },
        "file_io": {
            "tr": "Dosya okuma/yazma hatası. Dosya erişim izinlerini kontrol edin.",
            "en": "File I/O error. Check file access permissions."
        },
        "network": {
            "tr": "Ağ bağlantısı hatası. İnternet bağlantınızı kontrol edin.",
            "en": "Network connection error. Check your internet connection."
        },
        "unknown": {
            "tr": "Beklenmeyen bir hata oluştu. Lütfen hata raporunu kaydedin.",
            "en": "An unexpected error occurred. Please save the error report."
        }
    }
    
    @staticmethod
    def show_error_dialog(title: str, message: str, details: str = None):
        """Show error dialog to user"""
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Critical)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        
        if details:
            msg_box.setDetailedText(details)
        
        msg_box.setStandardButtons(QMessageBox.Ok)
        msg_box.exec_()
    
    @staticmethod
    def get_error_message(error_type: str, language: str = "tr") -> str:
        """Get localized error message"""
        return ErrorHandler.ERROR_MESSAGES.get(error_type, ErrorHandler.ERROR_MESSAGES["unknown"]).get(language, "Error occurred")
    
    @staticmethod
    def log_exception(exc_type, exc_value, exc_traceback):
        """Log uncaught exceptions"""
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        
        logger.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
        
        # Show error dialog
        error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        ErrorHandler.show_error_dialog(
            "Critical Error",
            ErrorHandler.get_error_message("unknown"),
            error_msg
        )

def handle_errors(error_type: str = "unknown", show_dialog: bool = True):
    """Decorator for error handling"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.error(f"Error in {func.__name__}: {str(e)}", exc_info=True)
                
                if show_dialog:
                    ErrorHandler.show_error_dialog(
                        "Error",
                        ErrorHandler.get_error_message(error_type),
                        str(e)
                    )
                
                return None
        return wrapper
    return decorator

# Note: sys.excepthook is managed by exception_handler.py (GlobalExceptionHandler)
# Do not override it here to avoid conflicts
