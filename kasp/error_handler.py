"""
KASP Error Handler
Centralized error handling and recovery mechanisms.
Merged from kasp/error_handler.py and kasp/exception_handler.py (2026-07).
"""

import sys
import traceback
import logging
from typing import Callable, Any, Type
from functools import wraps
from PyQt5.QtWidgets import QMessageBox, QApplication
from PyQt5.QtCore import QObject, pyqtSignal

from kasp.core.exceptions import (
    ThermodynamicError, ConvergenceError, FluidPropertyError,
    InputValidationError, GasCompositionError,
)

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
        return ErrorHandler.ERROR_MESSAGES.get(
            error_type, ErrorHandler.ERROR_MESSAGES["unknown"]
        ).get(language, "Error occurred")

    @staticmethod
    def log_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logger.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
        error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        ErrorHandler.show_error_dialog(
            "Critical Error",
            ErrorHandler.get_error_message("unknown"),
            error_msg
        )


def handle_errors(error_type: str = "unknown", show_dialog: bool = True):
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            try:
                return func(*args, **kwargs)
            except KeyboardInterrupt:
                raise
            except SystemExit:
                raise
            except (ThermodynamicError, ConvergenceError, FluidPropertyError,
                    InputValidationError, GasCompositionError) as e:
                logger.warning(f"{func.__name__}: {e}")
                if show_dialog:
                    ErrorHandler.show_error_dialog(
                        "Termodinamik Hata",
                        str(e),
                        getattr(e, 'details', None)
                    )
                return None
            except (ValueError, TypeError, KeyError, AttributeError) as e:
                logger.error(f"{func.__name__}: {e}", exc_info=True)
                if show_dialog:
                    ErrorHandler.show_error_dialog("Hata", str(e))
                return None
            except Exception as e:
                logger.critical(
                    f"{func.__name__}: Beklenmeyen hata", exc_info=True
                )
                if show_dialog:
                    ErrorHandler.show_error_dialog(
                        "Kritik Hata",
                        "Beklenmeyen bir hata olustu."
                    )
                return None
        return wrapper
    return decorator


class GlobalExceptionHandler(QObject):
    """Global exception handler for Qt applications"""

    exception_caught = pyqtSignal(str, str)

    def __init__(self):
        super().__init__()
        self.exception_caught.connect(self._show_exception_dialog)

    def handle_exception(self, exc_type: Type[BaseException],
                         exc_value: BaseException, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        error_msg = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        logger.critical("Uncaught exception:", exc_info=(exc_type, exc_value, exc_traceback))
        self.exception_caught.emit(str(exc_value), error_msg)

    def _show_exception_dialog(self, message: str, details: str):
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

        app = QApplication.instance()
        if app:
            app.quit()


_exception_handler = None


def install_exception_handler():
    global _exception_handler
    if _exception_handler is None:
        _exception_handler = GlobalExceptionHandler()
        sys.excepthook = _exception_handler.handle_exception
        logger.info("Global exception handler installed")
    return _exception_handler
