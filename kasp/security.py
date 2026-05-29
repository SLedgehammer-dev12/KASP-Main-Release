"""
KASP Security Module
Handles input validation, sanitization, and security checks
"""

import re
import os
import time
import json
import hashlib
import secrets
from typing import Any, Union
import logging

logger = logging.getLogger(__name__)

DEFAULT_PASSWORD = "kasp2024"

LOCKOUT_LEVELS = [
    (3, 1),
    (5, 5),
    (8, 15),
    (10, 60),
]

_lockout_file = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "kasp_lockout.json"
)


def _load_lockout_state():
    try:
        with open(_lockout_file) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"failures": 0, "last_failure": 0, "lockout_until": 0}


def _save_lockout_state(state):
    try:
        with open(_lockout_file, "w") as f:
            json.dump(state, f)
    except OSError:
        pass


def hash_password(password: str) -> str:
    salt = secrets.token_hex(12)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 600_000)
    return f"pbkdf2:sha256:600000:{salt}:{dk.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    if not stored_hash:
        return False
    if "$" in stored_hash and "_sha256" in stored_hash:
        try:
            converted = stored_hash.replace("_sha256", ":sha256").replace("$", ":")
            _, algo, iters, salt, expected = converted.split(":")
            dk = hashlib.pbkdf2_hmac(algo, password.encode(), salt.encode(), int(iters))
            return dk.hex() == expected
        except (ValueError, AttributeError):
            return False
    try:
        _, algo, iters, salt, expected = stored_hash.split(":")
        dk = hashlib.pbkdf2_hmac(algo, password.encode(), salt.encode(), int(iters))
        return dk.hex() == expected
    except (ValueError, AttributeError):
        return False


def record_attempt(success):
    state = _load_lockout_state()
    if success:
        state["failures"] = 0
        state["lockout_until"] = 0
    else:
        state["failures"] = state.get("failures", 0) + 1
        state["last_failure"] = time.time()
    _save_lockout_state(state)


def check_lockout():
    state = _load_lockout_state()
    now = time.time()

    if state.get("lockout_until", 0) and now < state["lockout_until"]:
        remaining_sec = int(state["lockout_until"] - now)
        mins = max(1, remaining_sec // 60 + (1 if remaining_sec % 60 else 0))
        return True, f"{mins} dakika kilitli"

    failures = state.get("failures", 0)
    for level_failures, lockout_mins in LOCKOUT_LEVELS:
        if failures >= level_failures and now > state.get("last_failure", 0):
            state["lockout_until"] = now + lockout_mins * 60
            _save_lockout_state(state)
            return True, f"{lockout_mins} dakika kilitlendi"

    return False, ""


def get_lockout_remaining():
    state = _load_lockout_state()
    failures = state.get("failures", 0)
    remaining = 999
    for level_failures, _ in LOCKOUT_LEVELS:
        if failures < level_failures:
            remaining = level_failures - failures
            break
    return remaining

class InputValidator:
    """Validates and sanitizes user inputs"""
    
    @staticmethod
    def validate_numeric(value: Any, min_val: float = None, max_val: float = None) -> bool:
        """Validate numeric input with optional range checking"""
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
        """Sanitize string input to prevent SQL injection and XSS"""
        if not isinstance(input_str, str):
            return ""
        
        # Remove potential SQL injection characters
        sanitized = re.sub(r'[;\'"\\]', '', input_str)
        
        # Limit length
        sanitized = sanitized[:max_length]
        
        return sanitized.strip()
    
    @staticmethod
    def validate_file_path(path: str, allowed_extensions: list = None) -> bool:
        """Validate file path for security"""
        try:
            # Normalize the path to resolve any '..' components
            normalized = os.path.normpath(path)
            
            # Check for path traversal: if normalized path still contains '..'
            # it means someone is trying to traverse outside allowed directories
            if '..' in normalized.split(os.sep):
                logger.warning(f"Potential path traversal attempt: {path}")
                return False
            
            # Check file extension if provided
            if allowed_extensions:
                _, ext = os.path.splitext(path)
                if ext.lower() not in allowed_extensions:
                    return False
            
            return True
        except Exception as e:
            logger.error(f"Path validation error: {e}")
            return False

class PermissionManager:
    ROLES = {
        "admin": ["read", "write", "delete", "export", "config", "manage_users"],
        "engineer": ["read", "write", "export"],
        "user": ["read", "export"],
        "viewer": ["read"],
    }

    def __init__(self):
        self.user_role = "user"
        self.current_user = None

    def has_permission(self, action: str) -> bool:
        return action in self.ROLES.get(self.user_role, [])

    def set_user_role(self, role: str):
        if role in self.ROLES:
            self.user_role = role
            logger.info(f"User role set to: {role}")
        else:
            logger.warning(f"Invalid role attempted: {role}")

    def is_admin(self):
        return self.user_role == "admin"


class Session:
    """Global oturum yöneticisi."""
    _permission_manager = None
    _current_user = None

    @classmethod
    def login(cls, user):
        cls._current_user = user
        pm = get_permission_manager()
        pm.current_user = user
        pm.set_user_role(user.role)
        cls._permission_manager = pm
        logger.info(f"Session baslatildi: {user.username} ({user.role})")
        return True

    @classmethod
    def logout(cls):
        cls._current_user = None
        if cls._permission_manager:
            cls._permission_manager.current_user = None
            cls._permission_manager.set_user_role("user")
        logger.info("Session sonlandirildi.")

    @classmethod
    def current_user(cls):
        return cls._current_user

    @classmethod
    def has_permission(cls, action):
        if cls._permission_manager is None:
            pm = get_permission_manager()
            pm.set_user_role(cls._current_user.role if cls._current_user else "user")
            cls._permission_manager = pm
        return cls._permission_manager.has_permission(action)

    @classmethod
    def is_admin(cls):
        return cls._permission_manager.is_admin() if cls._permission_manager else False

    @classmethod
    def is_engineering_mode(cls):
        if not cls.is_admin():
            return False
        try:
            from kasp.config_manager import get_config_manager
            return get_config_manager().get("updates.engineering_mode", False)
        except Exception:
            return False


_permission_manager = None


def get_permission_manager() -> PermissionManager:
    global _permission_manager
    if _permission_manager is None:
        _permission_manager = PermissionManager()
    return _permission_manager
