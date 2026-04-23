"""
KASP Security Module
Handles input validation, sanitization, and security checks
"""

import re
import os
from typing import Any, Union
import logging

logger = logging.getLogger(__name__)

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
    """Manages user permissions and access control"""
    
    def __init__(self):
        self.user_role = "user"  # Default role
        self.permissions = {
            "admin": ["read", "write", "delete", "export", "config"],
            "engineer": ["read", "write", "export"],
            "user": ["read", "export"],
            "viewer": ["read"]
        }
    
    def has_permission(self, action: str) -> bool:
        """Check if current user has permission for action"""
        return action in self.permissions.get(self.user_role, [])
    
    def set_user_role(self, role: str):
        """Set user role"""
        if role in self.permissions:
            self.user_role = role
            logger.info(f"User role set to: {role}")
        else:
            logger.warning(f"Invalid role attempted: {role}")

# Singleton instance
_permission_manager = None

def get_permission_manager() -> PermissionManager:
    """Get global permission manager instance"""
    global _permission_manager
    if _permission_manager is None:
        _permission_manager = PermissionManager()
    return _permission_manager
