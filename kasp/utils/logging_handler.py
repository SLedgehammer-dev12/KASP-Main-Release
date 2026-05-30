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

def setup_logging(log_widget_handler):
    """Logging yapılandırması"""
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass
    
    # File handler - detaylı hata kaydı
    if getattr(sys, 'frozen', False):
        log_dir = os.path.expanduser("~/Library/Logs/KASP") if sys.platform == "darwin" else os.getcwd()
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, "kasp_error.log")
    else:
        log_path = "kasp_error.log"
    file_handler = logging.FileHandler(log_path, mode='w', encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(levelname)s - %(module)s - %(funcName)s - Line %(lineno)d - %(message)s'
    ))
    root_logger.addHandler(file_handler)
    
    # Widget handler - UI'da gösterim (seviye engineering mode'a göre dinamik)
    try:
        from kasp.config_manager import get_config_manager
        eng_mode = get_config_manager().get("updates.engineering_mode", False)
    except Exception:
        eng_mode = False
    log_widget_handler.setLevel(logging.DEBUG if eng_mode else logging.INFO)
    root_logger.addHandler(log_widget_handler)
    
    # Console handler - debug için
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
    root_logger.addHandler(console_handler)
    
    # Grafik kutuphanesi DEBUG spam'ini bastir
    logging.getLogger('matplotlib').setLevel(logging.WARNING)
    
    logging.info("KASP v%s baslatildi. Logging yapilandirmasi tamamlandi.", APP_VERSION)
