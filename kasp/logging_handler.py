"""
KASP Logging Handler
Centralized logging configuration for the application
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
import os

def setup_logging(log_file='kasp_error.log', log_level=logging.INFO, max_bytes=5242880, backup_count=3):
    """
    Setup logging configuration for KASP application
    
    Args:
        log_file: Path to log file
        log_level: Logging level (default: INFO)
        max_bytes: Maximum log file size before rotation (default: 5MB)
        backup_count: Number of backup files to keep (default: 3)
    
    Returns:
        Logger instance
    """
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(name)s - %(funcName)s - Line %(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Setup root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # File handler with rotation
    try:
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    except Exception as e:
        print(f"WARNING: Could not create file handler: {e}", file=sys.stderr)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Get logger for this module
    logger = logging.getLogger(__name__)
    logger.info(f"KASP V4.3 başlatıldı. Logging yapılandırması tamamlandı.")
    
    return logger
