"""User Management Router for KASP Web API v1.

Admin-only endpoints for managing users, roles, active status, and password resets.
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

from kasp.api.auth import get_db, get_user_manager, require_permission
from kasp.core.user_manager import UserManager
from kasp.data.database import UnitDatabase

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["users"])


class UserCreateRequest(BaseModel):
    username: str
    password: str
    role: str = "user"
    full_name: str = ""
    email: str = ""


class UserUpdateRequest(BaseModel):
    role: Optional[str] = None
    full_name: Optional[str] = None
    email: Optional[str] = None
    is_active: Optional[bool] = None


class AdminResetPasswordRequest(BaseModel):
    new_password: str


@router.get("")
async def list_users(
    user_mgr: UserManager = Depends(get_user_manager),
    current_admin: dict = Depends(require_permission("manage_users")),
):
    """Kayıtlı tüm kullanıcıları listeler (Yalnızca yöneticiler)."""
    users = user_mgr.list_users()
    return [
        {
            "id": u.id,
            "username": u.username,
            "role": u.role,
            "full_name": u.full_name,
            "email": u.email,
            "is_active": u.is_active,
            "must_change_password": u.must_change_password,
            "created_at": u.created_at,
            "last_login": u.last_login,
            "security_question": u.security_question,
            "has_security_answer": u.has_security_answer,
            "has_recovery_key": u.has_recovery_key,
        }
        for u in users
    ]


@router.post("")
async def create_user(
    req: UserCreateRequest,
    user_mgr: UserManager = Depends(get_user_manager),
    current_admin: dict = Depends(require_permission("manage_users")),
):
    """Yeni kullanıcı oluşturur (Yalnızca yöneticiler)."""
    user, err = user_mgr.create_user(
        username=req.username.strip(),
        password=req.password,
        role=req.role,
        full_name=req.full_name.strip(),
        email=req.email.strip(),
    )
    if err or not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err or "Kullanıcı oluşturulamadı.")

    return {
        "message": f"'{user.username}' kullanıcısı başarıyla oluşturuldu.",
        "user": {
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "full_name": user.full_name,
            "email": user.email,
            "is_active": user.is_active,
        }
    }


@router.put("/{user_id}")
async def update_user(
    user_id: int,
    req: UserUpdateRequest,
    db: UnitDatabase = Depends(get_db),
    current_admin: dict = Depends(require_permission("manage_users")),
):
    """Kullanıcı bilgilerini ve rolünü günceller (Yalnızca yöneticiler)."""
    updates = {}
    if req.role is not None:
        if req.role not in ("admin", "engineer", "user", "viewer"):
            raise HTTPException(status_code=400, detail="Geçersiz kullanıcı rolü.")
        updates["role"] = req.role
    if req.full_name is not None:
        updates["full_name"] = req.full_name.strip()
    if req.email is not None:
        updates["email"] = req.email.strip()
    if req.is_active is not None:
        # Admin kendisini pasif yapamaz
        if current_admin["id"] == user_id and not req.is_active:
            raise HTTPException(status_code=400, detail="Kendi yönetici hesabınızı pasife alamazsınız.")
        updates["is_active"] = 1 if req.is_active else 0

    if not updates:
        raise HTTPException(status_code=400, detail="Güncellenecek alan belirtilmedi.")

    ok = db.update_user(user_id, **updates)
    if not ok:
        raise HTTPException(status_code=400, detail="Kullanıcı güncellenemedi veya bulunamadı.")

    return {"message": "Kullanıcı başarıyla güncellendi."}


@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    user_mgr: UserManager = Depends(get_user_manager),
    current_admin: dict = Depends(require_permission("manage_users")),
):
    """Kullanıcıyı siler (Yalnızca yöneticiler)."""
    if current_admin["id"] == user_id:
        raise HTTPException(status_code=400, detail="Kendi hesabınızı silemezsiniz.")

    ok, err = user_mgr.delete_user(user_id)
    if not ok:
        raise HTTPException(status_code=400, detail=err or "Kullanıcı silinemedi.")

    return {"message": "Kullanıcı başarıyla silindi."}


@router.post("/{user_id}/reset-password")
async def admin_reset_password(
    user_id: int,
    req: AdminResetPasswordRequest,
    user_mgr: UserManager = Depends(get_user_manager),
    current_admin: dict = Depends(require_permission("manage_users")),
):
    """Yönetici tarafından kullanıcının şifresini sıfırlar ve must_change_password=1 yapar."""
    ok, err = user_mgr.admin_reset_password(user_id, req.new_password)
    if not ok:
        raise HTTPException(status_code=400, detail=err or "Şifre sıfırlanamadı.")

    return {"message": "Kullanıcı şifresi sıfırlandı. İlk girişte şifre değiştirmesi istenecektir."}
