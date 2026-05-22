"""
KASP Security Module
Handles input validation, sanitization, security checks, and authentication.
"""

import hashlib
import hmac
import re
import os
import secrets
import time
from typing import Any, Union
import logging

logger = logging.getLogger(__name__)

PBKDF2_ITERATIONS = 200_000
MAX_BRUTE_FORCE_ATTEMPTS = 5
LOCKOUT_LEVELS = [
    (5, 30),
    (10, 300),
    (15, 3600),
]

DEFAULT_PASSWORD = "123456"

_locked_state = {"attempts": 0, "locked_until": 0.0}


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS
    )
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored_value: str) -> bool:
    if not stored_value or not password:
        return False
    try:
        algorithm, iterations, salt_hex, digest_hex = stored_value.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        expected = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            int(iterations),
        ).hex()
        return hmac.compare_digest(expected, digest_hex)
    except Exception:
        return False


def check_lockout():
    now = time.time()
    if _locked_state["locked_until"] > now:
        remaining = int(_locked_state["locked_until"] - now)
        mins = remaining // 60
        secs = remaining % 60
        if mins > 0:
            return True, f"{mins} dk {secs} sn bekleyin..."
        return True, f"{secs} sn bekleyin..."
    return False, ""


def get_lockout_remaining():
    now = time.time()
    if _locked_state["locked_until"] > now:
        return int(_locked_state["locked_until"] - now)

    attempts = _locked_state["attempts"]
    for limit, _ in LOCKOUT_LEVELS:
        if attempts < limit:
            return limit - attempts
    return 1


def _calculate_lockout_seconds():
    attempts = _locked_state["attempts"]
    for limit, lockout_secs in LOCKOUT_LEVELS:
        if attempts >= limit:
            return lockout_secs
    return 0


def record_attempt(success=False):
    global _locked_state
    if success:
        _locked_state["attempts"] = 0
        _locked_state["locked_until"] = 0.0
        return

    _locked_state["attempts"] += 1
    lockout_secs = _calculate_lockout_seconds()
    if lockout_secs > 0:
        _locked_state["locked_until"] = time.time() + lockout_secs


def hash_default_password():
    return hash_password(DEFAULT_PASSWORD)


class InputValidator:
    """Validates and sanitizes user inputs"""

    @staticmethod
    def validate_numeric(value: Any, min_val: float = None, max_val: float = None) -> bool:
        try:
            num = float(value)
            if min_val is not None and num < min_val:
                return False
            if max_val is not None and num > max_val:
                return False
            return True
        except (ValueError, TypeError):
            return False

    @staticmethod
    def sanitize_string(input_str: str, max_length: int = 255) -> str:
        if not isinstance(input_str, str):
            return ""
        sanitized = re.sub(r'[;\'"\\]', '', input_str)
        sanitized = sanitized[:max_length]
        return sanitized.strip()

    @staticmethod
    def validate_file_path(path: str, allowed_extensions: list = None) -> bool:
        try:
            normalized = os.path.normpath(path)
            if '..' in normalized.split(os.sep):
                logger.warning(f"Potential path traversal attempt: {path}")
                return False
            if allowed_extensions:
                _, ext = os.path.splitext(path)
                if ext.lower() not in allowed_extensions:
                    return False
            return True
        except Exception as e:
            logger.error(f"Path validation error: {e}")
            return False


class PermissionManager:
    """Manages user permissions and access control"""

    def __init__(self):
        self.user_role = "user"
        self.permissions = {
            "admin": ["read", "write", "delete", "export", "config"],
            "engineer": ["read", "write", "export"],
            "user": ["read", "export"],
            "viewer": ["read"]
        }

    def has_permission(self, action: str) -> bool:
        return action in self.permissions.get(self.user_role, [])

    def set_user_role(self, role: str):
        if role in self.permissions:
            self.user_role = role
            logger.info(f"User role set to: {role}")
        else:
            logger.warning(f"Invalid role attempted: {role}")


_permission_manager = None


def get_permission_manager() -> PermissionManager:
    global _permission_manager
    if _permission_manager is None:
        _permission_manager = PermissionManager()
    return _permission_manager
