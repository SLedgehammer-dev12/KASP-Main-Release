"""
KASP Logging Handler
Centralized logging configuration for the application
"""

import logging
import sys
from kasp.utils.logging_handler import setup_logging as _setup_logging

# ITERATION level tanimi (utils modulu da tanimli, tekrar etmemek icin try/except)
try:
    ITERATION = 15
    logging.addLevelName(ITERATION, "ITERATION")
    def iteration(self, message, *args, **kwargs):
        if self.isEnabledFor(ITERATION):
            self._log(ITERATION, message, args, **kwargs)
    logging.Logger.iteration = iteration
except Exception:
    pass


def setup_logging(log_file='kasp_error.log', log_level=logging.INFO, max_bytes=5242880, backup_count=3):
    """
    Logging yapilandirmasi (kasp.utils.logging_handler.setup_logging'e yonlendirme).

    Geriye donuk uyumluluk icin parametreleri kabul eder ama utils versiyonu
    config_manager'dan okur; bu fonksiyon parametreleri log_level ve log_file
    haricini dikkate almaz.
    """
    # log_file parametresi utils versiyonu config_manager'dan alir,
    # ama biz yine de dosya handler'i ekleyebiliriz.
    # Basitlik icin utils setup_logging'i cagir; log_widget_handler=None.
    logger = _setup_logging(log_widget_handler=None)

    # log_level ve log_file degistirilmek istenirse root logger level guncelle
    root_logger = logging.getLogger()
    if log_level != logging.INFO:
        root_logger.setLevel(log_level)
        for h in root_logger.handlers:
            h.setLevel(log_level)

    if logger is None:
        logger = root_logger

    logger.info("KASP v%s - Logging yapilandirmasi (wrapper) tamamlandi.", 
                getattr(sys.modules.get('release_metadata'), 'APP_VERSION', '?'))
    return logger
