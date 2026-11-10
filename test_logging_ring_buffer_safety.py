import pytest
import logging
from kasp.utils.logging_handler import MemoryRingLogHandler


def test_get_logs_zero_limit_returns_empty_list():
    """get_logs(limit=0) must return an empty list, NOT the full log buffer."""
    handler = MemoryRingLogHandler(capacity=50)
    logger = logging.getLogger("test_zero_limit_logger")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    for i in range(10):
        logger.info(f"Log message {i}")

    # Must return empty list, not all 10 logs
    logs_zero = handler.get_logs(limit=0)
    assert logs_zero == [], f"Expected empty list for limit=0, got {len(logs_zero)} items"


def test_get_logs_negative_limit_returns_empty_list():
    """get_logs with negative limit must return empty list."""
    handler = MemoryRingLogHandler(capacity=50)
    logger = logging.getLogger("test_neg_limit_logger")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    for i in range(5):
        logger.info(f"Log message {i}")

    assert handler.get_logs(limit=-1) == []
    assert handler.get_logs(limit=-100) == []


def test_get_logs_normal_limit_and_level_filter():
    """get_logs with positive limit and level filtering works accurately."""
    handler = MemoryRingLogHandler(capacity=50)
    logger = logging.getLogger("test_filter_logger")
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    logger.debug("Debug msg")
    logger.info("Info msg 1")
    logger.info("Info msg 2")
    logger.warning("Warn msg")

    info_logs = handler.get_logs(limit=1, level="INFO")
    assert len(info_logs) == 1
    assert info_logs[0]["message"] == "Info msg 2"
