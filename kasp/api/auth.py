"""KASP Web API - Authentication, Session & RBAC Module.

Thread-safe session store, HttpOnly cookie + Bearer token support, CSRF protection,
and role-based access control (RBAC) backed by UnitDatabase & PermissionManager.
"""

import hmac
import logging
import secrets
import threading
import time
from typing import Callable, Dict, Optional, Tuple

from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from kasp.core.user_manager import UserManager
from kasp.data.database import UnitDatabase
from kasp.security import PermissionManager

logger = logging.getLogger(__name__)

# Session TTL constants
SESSION_INACTIVITY_TIMEOUT = 8 * 3600  # 8 saat inaktivite sonrası zaman aşımı
SESSION_MAX_LIFETIME = 24 * 3600       # Maksimum 24 saat oturum süresi

bearer_scheme = HTTPBearer(auto_error=False)


class WebSessionStore:
    """Bellek içi iş parçacığı güvenli (thread-safe) oturum yöneticisi."""

    def __init__(self):
        self._sessions: Dict[str, dict] = {}
        self._lock = threading.Lock()

    def create_session(self, user_dict: dict) -> Tuple[str, str]:
        """Yeni oturum oluşturur. (session_id, csrf_token) döner."""
        session_id = secrets.token_urlsafe(32)
        csrf_token = secrets.token_hex(32)
        now = time.time()

        with self._lock:
            # Temizlik
            self._cleanup_expired_locked(now)

            self._sessions[session_id] = {
                "session_id": session_id,
                "csrf_token": csrf_token,
                "user": user_dict,
                "created_at": now,
                "last_active": now,
            }

        return session_id, csrf_token

    def get_session(self, session_id: str) -> Optional[dict]:
        """Oturum verisini getirir. Süresi dolmuşsa None döner."""
        if not session_id:
            return None

        now = time.time()
        with self._lock:
            sess = self._sessions.get(session_id)
            if not sess:
                return None

            # Zaman aşımı kontrolleri
            if (now - sess["last_active"] > SESSION_INACTIVITY_TIMEOUT) or \
               (now - sess["created_at"] > SESSION_MAX_LIFETIME):
                del self._sessions[session_id]
                return None

            sess["last_active"] = now
            return sess

    def delete_session(self, session_id: str) -> bool:
        """Oturumu siler."""
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                return True
        return False

    def _cleanup_expired_locked(self, now: float):
        """Kilit altında süresi dolmuş oturumları temizler."""
        expired = [
            sid for sid, s in self._sessions.items()
            if (now - s["last_active"] > SESSION_INACTIVITY_TIMEOUT) or
               (now - s["created_at"] > SESSION_MAX_LIFETIME)
        ]
        for sid in expired:
            del self._sessions[sid]


# Global session store instance for web API
session_store = WebSessionStore()

# Thread-safe database instance singleton for API
_db_instance: Optional[UnitDatabase] = None
_db_lock = threading.Lock()


def get_db() -> UnitDatabase:
    """Thread-safe UnitDatabase bağımlılığı."""
    global _db_instance
    if _db_instance is None:
        with _db_lock:
            if _db_instance is None:
                _db_instance = UnitDatabase()
    return _db_instance


def get_user_manager(db: UnitDatabase = Depends(get_db)) -> UserManager:
    """UserManager bağımlılığı."""
    return UserManager(db)


def get_session_id_from_request(
    request: Request,
    bearer: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme)
) -> Optional[str]:
    """İstekten session_id çıkarır (Önce cookie 'kasp_session', sonra Bearer token)."""
    # 1. HttpOnly Cookie
    cookie_token = request.cookies.get("kasp_session")
    if cookie_token:
        return cookie_token

    # 2. Bearer Header
    if bearer and bearer.credentials:
        return bearer.credentials

    # 3. Custom Header X-Session-Id
    custom_header = request.headers.get("X-Session-Id")
    if custom_header:
        return custom_header

    return None


async def get_current_user_optional(
    request: Request,
    session_id: Optional[str] = Depends(get_session_id_from_request),
) -> Optional[dict]:
    """Geçerli oturum kullanıcısını döner veya None (zorunlu değil)."""
    if not session_id:
        return None
    session_data = session_store.get_session(session_id)
    if not session_data:
        return None
    return session_data.get("user")


async def get_current_user(
    request: Request,
    session_id: Optional[str] = Depends(get_session_id_from_request),
) -> dict:
    """Geçerli oturum kullanıcısını döner. Oturum yoksa 401 Unauthorized üretir."""
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Oturum açmanız gerekmektedir (kasp_session çerezi veya Bearer token eksik).",
            headers={"WWW-Authenticate": "Bearer"},
        )
    session_data = session_store.get_session(session_id)
    if not session_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Oturum süresi dolmuş veya geçersiz.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return session_data["user"]


async def require_active_user(user: dict = Depends(get_current_user)) -> dict:
    """Aktif ve şifre değiştirme zorunluluğu olmayan kullanıcı gerektirir."""
    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Kullanıcı hesabı devre dışı bırakılmıştır."
        )
    if user.get("must_change_password", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="İlk giriş: Lütfen devam etmeden önce şifrenizi değiştirin."
        )
    return user


def require_permission(action: str) -> Callable:
    """Belirli bir işlem yetkisine (RBAC) sahip kullanıcı gerektiren bağımlılık üretici."""
    def dependency(user: dict = Depends(require_active_user)) -> dict:
        role = user.get("role", "viewer")
        allowed_actions = PermissionManager.ROLES.get(role, [])
        if action not in allowed_actions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Yetkisiz işlem: '{role}' rolü '{action}' yetkisine sahip değil."
            )
        return user
    return dependency


def validate_csrf(
    request: Request,
    session_id: Optional[str] = Depends(get_session_id_from_request)
):
    """CSRF doğrulama: Durum değiştiren HTTP isteklerinde (POST/PUT/DELETE/PATCH)

    'X-CSRF-Token' başlığı ile oturumdaki csrf_token karşılaştırılır.
    """
    if request.method in ("POST", "PUT", "DELETE", "PATCH"):
        if not session_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="CSRF doğrulaması için geçerli bir oturum gereklidir."
            )
        sess = session_store.get_session(session_id)
        if not sess:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Geçersiz oturum."
            )

        expected_csrf = sess.get("csrf_token", "")
        provided_csrf = request.headers.get("X-CSRF-Token", "").strip()

        if not provided_csrf or not hmac.compare_digest(provided_csrf, expected_csrf):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Geçersiz CSRF belirteci (X-CSRF-Token mismatch)."
            )
