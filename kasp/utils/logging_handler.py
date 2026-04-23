import logging
import sys
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

class QLogHandler(logging.Handler, QObject):
    log_signal = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__()
        QObject.__init__(self, parent)
        self.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

    def emit(self, record):
        msg = self.format(record)
        self.log_signal.emit(msg)

def setup_logging(log_widget_handler):
    """Logging yapılandırması"""
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    # File handler - detaylı hata kaydı
    file_handler = logging.FileHandler('kasp_error.log', mode='w', encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(levelname)s - %(module)s - %(funcName)s - Line %(lineno)d - %(message)s'
    ))
    root_logger.addHandler(file_handler)
    
    # Widget handler - UI'da gösterim
    log_widget_handler.setLevel(logging.INFO)
    root_logger.addHandler(log_widget_handler)
    
    # Console handler - debug için
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
    root_logger.addHandler(console_handler)
    
    logging.info("KASP v4.2 DEEP başlatıldı. Logging yapılandırması tamamlandı.")
