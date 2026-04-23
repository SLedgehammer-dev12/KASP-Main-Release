"""
KASP Performance Configuration
Optimizes database queries, caching, and resource management
"""

import sqlite3
from functools import lru_cache
from typing import Any, Dict
import logging

logger = logging.getLogger(__name__)

class DatabaseOptimizer:
    """Optimizes database operations"""
    
    @staticmethod
    def configure_connection(conn: sqlite3.Connection):
        """Configure SQLite connection for optimal performance"""
        try:
            # Enable Write-Ahead Logging for better concurrency
            conn.execute("PRAGMA journal_mode=WAL")
            
            # Increase cache size (10MB)
            conn.execute("PRAGMA cache_size=-10000")
            
            # Enable foreign keys
            conn.execute("PRAGMA foreign_keys=ON")
            
            # Optimize for performance
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA temp_store=MEMORY")
            
            logger.info("Database connection optimized")
        except Exception as e:
            logger.error(f"Database optimization error: {e}")
    
    @staticmethod
    def create_indexes(conn: sqlite3.Connection):
        """Create performance indexes on frequently queried columns"""
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_timestamp ON calculations(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_user ON calculations(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_status ON calculations(status)",
        ]
        
        try:
            cursor = conn.cursor()
            for index_sql in indexes:
                cursor.execute(index_sql)
            conn.commit()
            logger.info("Performance indexes created")
        except Exception as e:
            logger.error(f"Index creation error: {e}")

class CacheManager:
    """Manages application-level caching"""
    
    def __init__(self, max_size: int = 128):
        self.max_size = max_size
        self._cache: Dict[str, Any] = {}
    
    @lru_cache(maxsize=128)
    def get_thermodynamic_property(self, substance: str, temperature: float, pressure: float):
        """Cache thermodynamic property lookups"""
        # This should be implemented with actual thermo calculations
        pass
    
    def clear_cache(self):
        """Clear all cached data"""
        self._cache.clear()
        self.get_thermodynamic_property.cache_clear()
        logger.info("Cache cleared")
    
    def get_cache_info(self):
        """Get cache statistics"""
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "thermo_cache_info": self.get_thermodynamic_property.cache_info()
        }

# Singleton instance
_cache_manager = None

def get_cache_manager() -> CacheManager:
    """Get global cache manager instance"""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager
