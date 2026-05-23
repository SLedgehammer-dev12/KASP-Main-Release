"""
KASP Global Exception Handler
Catches all unhandled exceptions and logs them properly
"""

import sys
import traceback
import logging
from typing import Type
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import QObject, pyqtSignal

logger = logging.getLogger(__name__)

class GlobalExceptionHandler(QObject):
    """Global exception handler for Qt applications"""
    
    exception_caught = pyqtSignal(str, str)
    
    def __init__(self):
        super().__init__()
        self.exception_caught.connect(self._show_exception_dialog)
    
    def handle_exception(self, exc_type: Type[BaseException], exc_value: BaseException, exc_traceback):
        """Handle uncaught exceptions"""
        # Ignore KeyboardInterrupt
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        
        # Format exception
        error_msg = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        
        # Log the error
        logger.critical("Uncaught exception:", exc_info=(exc_type, exc_value, exc_traceback))
        
        # Emit signal to show dialog (thread-safe)
        self.exception_caught.emit(str(exc_value), error_msg)
    
    def _show_exception_dialog(self, message: str, details: str):
        """Show exception dialog to user"""
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Critical)
        msg_box.setWindowTitle("KASP - Beklenmeyen Hata")
        msg_box.setText(
            "Beklenmeyen bir hata oluştu!\n\n"
            "Lütfen bu hatayı raporlayın ve uygulamayı yeniden başlatın."
        )
        msg_box.setInformativeText(message)
        msg_box.setDetailedText(details)
        msg_box.setStandardButtons(QMessageBox.Close)
        msg_box.exec_()
        
        # Exit application after showing error
        app = QApplication.instance()
        if app:
            app.quit()

# Global instance
_exception_handler = None

def install_exception_handler():
    """Install global exception handler"""
    global _exception_handler
    if _exception_handler is None:
        _exception_handler = GlobalExceptionHandler()
        sys.excepthook = _exception_handler.handle_exception
        logger.info("Global exception handler installed")
    return _exception_handler
