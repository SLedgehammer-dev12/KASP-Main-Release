"""
KASP Logging Handler
Centralized logging configuration for the application.
Merged from kasp/logging_handler.py and kasp/utils/logging_handler.py (2026-07).
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from release_metadata import APP_VERSION
from PyQt5.QtCore import QObject, pyqtSignal

ITERATION = 15
logging.addLevelName(ITERATION, "ITERATION")


def iteration(self, message, *args, **kwargs):
    if self.isEnabledFor(ITERATION):
        self._log(ITERATION, message, args, **kwargs)


logging.Logger.iteration = iteration


class LogEmitter(QObject):
    log_signal = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)


class QLogHandler(logging.Handler):
    def __init__(self, parent=None):
        super().__init__()
        self.emitter = LogEmitter(parent)
        self.log_signal = self.emitter.log_signal
        self.setFormatter(logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        ))
        self._pending = []

    def emit(self, record):
        msg = self.format(record)
        try:
            self.log_signal.emit(msg)
        except RuntimeError:
            self._pending.append(msg)

    def flush_pending(self):
        while self._pending:
            self.log_signal.emit(self._pending.pop(0))


def setup_logging(log_file='kasp_error.log', log_level=logging.INFO,
                  max_bytes=5242880, backup_count=3, log_widget_handler=None):
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)
        try:
            handler.close()
        except (AttributeError, OSError):
            pass

    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(name)s - %(funcName)s - Line %(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # File handler
    try:
        file_handler = RotatingFileHandler(
            log_file, maxBytes=max_bytes, backupCount=backup_count, encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    except Exception as e:
        print(f"WARNING: Could not create file handler: {e}", file=sys.stderr)

    # Widget handler (UI log gösterimi)
    if log_widget_handler is not None:
        try:
            from kasp.config_manager import get_config_manager
            eng_mode = get_config_manager().get("updates.engineering_mode", False)
        except Exception:
            eng_mode = False
        log_widget_handler.setLevel(logging.DEBUG if eng_mode else logging.INFO)
        root_logger.addHandler(log_widget_handler)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
    root_logger.addHandler(console_handler)

    logging.getLogger('matplotlib').setLevel(logging.WARNING)

    logger = logging.getLogger(__name__)
    logger.info(f"KASP v{APP_VERSION} - Logging yapilandirmasi tamamlandi.")
    return logger
