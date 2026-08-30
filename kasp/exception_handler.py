"""
KASP Global Exception Handler
Catches all unhandled exceptions and logs them properly
"""

import sys
import traceback
import logging
import os
from typing import Type
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import QObject, pyqtSignal, QProcess

logger = logging.getLogger(__name__)

class GlobalExceptionHandler(QObject):
    """Global exception handler for Qt applications"""
    
    exception_caught = pyqtSignal(str, str)
    
    def __init__(self):
        super().__init__()
        self.exception_caught.connect(self._show_exception_dialog)
        self._dialog_active = False
    
    def handle_exception(self, exc_type: Type[BaseException], exc_value: BaseException, exc_traceback):
        """Handle uncaught exceptions"""
        # Ignore KeyboardInterrupt
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        
        # Prevent re-entrant dialogs
        if self._dialog_active:
            logger.critical("Re-entrant exception, forcing exit", exc_info=(exc_type, exc_value, exc_traceback))
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            app = QApplication.instance()
            if app:
                app.quit()
            return
        
        # Format exception
        error_msg = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        
        # Log the error
        logger.critical("Uncaught exception:", exc_info=(exc_type, exc_value, exc_traceback))
        
        # Emit signal to show dialog (thread-safe)
        self.exception_caught.emit(str(exc_value), error_msg)
    
    def _show_exception_dialog(self, message: str, details: str):
        """Show exception dialog to user with recovery options"""
        self._dialog_active = True
        try:
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Critical)
            msg_box.setWindowTitle("KASP - Beklenmeyen Hata")
            msg_box.setText(
                "Beklenmeyen bir hata oluştu!\n\n"
                "Lütfen bu hatayı raporlayın."
            )
            msg_box.setInformativeText(message)
            msg_box.setDetailedText(details)
            
            # Recovery options
            save_exit_btn = msg_box.addButton("Kaydet ve Çık", QMessageBox.AcceptRole)
            restart_btn = msg_box.addButton("Yeniden Başlat", QMessageBox.ActionRole)
            continue_btn = msg_box.addButton("Devam Et (Riskli)", QMessageBox.RejectRole)
            msg_box.setDefaultButton(save_exit_btn)
            
            msg_box.exec_()
            
            clicked = msg_box.clickedButton()
            app = QApplication.instance()
            
            if clicked == save_exit_btn:
                if app:
                    app.quit()
            elif clicked == restart_btn:
                if app:
                    app.quit()
                    # Restart the application
                    QProcess.startDetached(sys.executable, sys.argv)
            elif clicked == continue_btn:
                # User chose to continue - dismiss dialog, don't quit
                logger.warning("User chose to continue after unhandled exception")
            else:
                # Dialog closed without choice - safe default: quit
                if app:
                    app.quit()
        finally:
            self._dialog_active = False

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
