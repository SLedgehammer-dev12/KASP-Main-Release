import logging
import os
import sys
from release_metadata import APP_VERSION
from PyQt5.QtCore import QObject, pyqtSignal

# Custom log level for iteration details
ITERATION = 15  # Between DEBUG (10) and INFO (20)
logging.addLevelName(ITERATION, "ITERATION")

def iteration(self, message, *args, **kwargs):
    """Helper method for ITERATION level logging"""
    if self.isEnabledFor(ITERATION):
        self._log(ITERATION, message, args, **kwargs)

# Add iteration method to Logger class
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
        self.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

    def emit(self, record):
        msg = self.format(record)
        self.log_signal.emit(msg)

from logging.handlers import RotatingFileHandler

def setup_logging(log_widget_handler=None):
    """Logging yapılandırması"""
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    try:
        from kasp.config_manager import get_config_manager
        cfg = get_config_manager()
        eng_mode = cfg.get("updates.engineering_mode", False)
        max_bytes = int(cfg.get("logging.max_file_size", 5242880) or 5242880)
        backup_count = int(cfg.get("logging.backup_count", 3) or 3)
        cfg_level_name = str(cfg.get("logging.level", "INFO") or "INFO").upper()
        cfg_level = getattr(logging, cfg_level_name, logging.INFO)
    except Exception:
        eng_mode = False
        max_bytes = 5242880
        backup_count = 3
        cfg_level = logging.INFO

    # Remove old QLogHandler instances so UI signals aren't duplicated on re-init,
    # but preserve existing RotatingFileHandler and StreamHandler instances.
    has_rotating_file = False
    has_stream = False
    for handler in list(root_logger.handlers):
        if isinstance(handler, QLogHandler) and handler is not log_widget_handler:
            root_logger.removeHandler(handler)
        elif isinstance(handler, RotatingFileHandler):
            has_rotating_file = True
        elif isinstance(handler, logging.FileHandler):
            # Replace plain FileHandler with RotatingFileHandler
            root_logger.removeHandler(handler)
            try:
                handler.close()
            except Exception:
                pass
        elif isinstance(handler, logging.StreamHandler):
            has_stream = True

    if not has_rotating_file:
        if getattr(sys, 'frozen', False):
            log_dir = os.path.expanduser("~/Library/Logs/KASP") if sys.platform == "darwin" else os.getcwd()
            os.makedirs(log_dir, exist_ok=True)
            log_path = os.path.join(log_dir, "kasp_error.log")
        else:
            log_path = "kasp_error.log"
        try:
            file_handler = RotatingFileHandler(
                log_path,
                mode='a',
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding='utf-8',
            )
            file_handler.setLevel(min(logging.DEBUG, cfg_level))
            file_handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(levelname)s - %(module)s - %(funcName)s - Line %(lineno)d - %(message)s'
            ))
            root_logger.addHandler(file_handler)
        except Exception:
            pass

    if log_widget_handler is not None:
        log_widget_handler.setLevel(logging.DEBUG if eng_mode else logging.INFO)
        if log_widget_handler not in root_logger.handlers:
            root_logger.addHandler(log_widget_handler)

    if not has_stream:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
        root_logger.addHandler(console_handler)

    # Grafik kutuphanesi DEBUG spam'ini bastir
    logging.getLogger('matplotlib').setLevel(logging.WARNING)

    logging.info("KASP v%s baslatildi. Logging yapilandirmasi tamamlandi.", APP_VERSION)
    return root_logger
