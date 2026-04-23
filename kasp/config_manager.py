"""
KASP Configuration Manager
Centralized configuration management with validation
"""

import json
import os
from typing import Any, Dict
import logging
import copy

logger = logging.getLogger(__name__)

class ConfigManager:
    """Manages application configuration"""
    
    DEFAULT_CONFIG = {
        "app": {
            "version": "4.6.2",
            "language": "tr",
            "theme": "light",
            "auto_save": True,
            "auto_save_interval": 300  # seconds
        },
        "database": {
            "path": "kasp_data.db",
            "backup_enabled": True,
            "backup_interval": 86400  # 24 hours
        },
        "thermodynamics": {
            "uncertainty_analysis": True,
            "precision": 6,
            "default_units": "SI"
        },
        "ui": {
            "window_width": 1200,
            "window_height": 800,
            "font_family": "Segoe UI",
            "font_size": 9,
            "show_tooltips": True,
            "confirm_on_delete": True
        },
        "logging": {
            "level": "INFO",
            "max_file_size": 10485760,  # 10MB
            "backup_count": 5
        },
        "export": {
            "default_format": "xlsx",
            "include_charts": True,
            "decimal_separator": ",",
            "thousands_separator": "."
        }
    }
    
    def __init__(self, config_file: str = "kasp_config.json"):
        self.config_file = config_file
        self.config = copy.deepcopy(self.DEFAULT_CONFIG)
        self.load_config()
    
    def load_config(self):
        """Load configuration from file"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                    self._merge_config(user_config)
                logger.info(f"Configuration loaded from {self.config_file}")
            else:
                self.save_config()
                logger.info("Default configuration created")
        except Exception as e:
            logger.error(f"Config load error: {e}. Using defaults.")
    
    def save_config(self):
        """Save configuration to file"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            logger.info("Configuration saved")
        except Exception as e:
            logger.error(f"Config save error: {e}")
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """Get configuration value using dot notation (e.g., 'app.theme')"""
        keys = key_path.split('.')
        value = self.config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value
    
    def set(self, key_path: str, value: Any):
        """Set configuration value using dot notation"""
        keys = key_path.split('.')
        config = self.config
        
        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]
        
        config[keys[-1]] = value
        self.save_config()
        logger.info(f"Configuration updated: {key_path} = {value}")
    
    def _merge_config(self, user_config: Dict):
        """Merge user config with defaults"""
        def merge_dict(base: Dict, override: Dict):
            for key, value in override.items():
                if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                    merge_dict(base[key], value)
                else:
                    base[key] = value
        
        merge_dict(self.config, user_config)

# Singleton instance
_config_manager = None

def get_config_manager() -> ConfigManager:
    """Get global configuration manager"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager
