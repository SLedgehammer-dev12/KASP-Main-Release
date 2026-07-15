"""
KASP Performance Configuration
Veritabanı optimizasyonları doğrudan UnitDatabase._configure_performance()
içinde uygulanmaktadır. Bu modül geriye dönük uyumluluk için tutulmaktadır.
"""
import sqlite3
import logging

logger = logging.getLogger(__name__)


class DatabaseOptimizer:
    """Veritabanı optimizasyonları — kullanım dışı, UnitDatabase'e taşındı."""

    @staticmethod
    def configure_connection(conn: sqlite3.Connection):
        logger.warning(
            "DatabaseOptimizer.configure_connection() kullanım dışı. "
            "UnitDatabase._configure_performance() kullanın."
        )
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA cache_size=-10000")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA temp_store=MEMORY")
        except sqlite3.Error as exc:
            logger.error(f"Database optimization error: {exc}")

    @staticmethod
    def create_indexes(conn: sqlite3.Connection):
        logger.warning(
            "DatabaseOptimizer.create_indexes() kullanım dışı. "
            "UnitDatabase._configure_performance() kullanın."
        )
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_history_date ON CalculationHistory(calculation_date)",
            "CREATE INDEX IF NOT EXISTS idx_turbines_type ON Turbines(type)",
            "CREATE INDEX IF NOT EXISTS idx_users_username ON Users(username)",
        ]
        try:
            cursor = conn.cursor()
            for index_sql in indexes:
                cursor.execute(index_sql)
            conn.commit()
            logger.info("Performance indexes created")
        except sqlite3.Error as exc:
            logger.error(f"Index creation error: {exc}")


class CacheManager:
    """Kullanım dışı — ThermodynamicSolver kendi LRU cache'ini yönetir."""

    def __init__(self, max_size: int = 128):
        raise NotImplementedError(
            "CacheManager kullanım dışı. ThermodynamicSolver.get_properties() "
            "kendi @lru_cache dekoratörünü kullanmaktadır."
        )


_cache_manager = None


def get_cache_manager() -> CacheManager:
    raise NotImplementedError("CacheManager kullanım dışı.")
