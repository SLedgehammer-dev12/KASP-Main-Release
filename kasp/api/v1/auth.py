"""Auth Router for KASP Web API v1.

Endpoints for login, logout, me, change-password, and password recovery.
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from kasp.api.auth import (
    get_current_user,
    get_db,
    get_session_id_from_request,
    get_user_manager,
    session_store,
)
from kasp.core.user_manager import UserManager
from kasp.data.database import UnitDatabase

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class RecoveryQuestionRequest(BaseModel):
    username: str
    answer: str
    new_password: str


class RecoveryKeyRequest(BaseModel):
    username: str
    recovery_key: str
    new_password: str


class SetSecurityQuestionRequest(BaseModel):
    question: str
    answer: str


@router.post("/login")
async def login(
    creds: LoginRequest,
    response: Response,
    db: UnitDatabase = Depends(get_db),
    user_mgr: UserManager = Depends(get_user_manager),
):
    """Kullanıcı girişi yapar. Başarılıysa session_id çerezi ve csrf_token döner."""
    username = creds.username.strip()
    
    # Kilit kontrolü
    is_locked, lock_msg, rem_time = db.check_auth_lockout(username)
    if is_locked:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=lock_msg,
        )

    user = user_mgr.authenticate(username, creds.password)
    if not user:
        just_locked, lock_msg = db.record_auth_attempt(username, success=False)
        detail = lock_msg if just_locked else "Geçersiz kullanıcı adı veya şifre."
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
        )

    # Başarılı giriş
    db.record_auth_attempt(username, success=True)

    user_dict = {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "full_name": user.full_name,
        "email": user.email,
        "is_active": user.is_active,
        "must_change_password": user.must_change_password,
        "security_question": user.security_question,
        "has_security_answer": user.has_security_answer,
        "has_recovery_key": user.has_recovery_key,
    }

    session_id, csrf_token = session_store.create_session(user_dict)

    # HttpOnly Cookie tanımla
    response.set_cookie(
        key="kasp_session",
        value=session_id,
        httponly=True,
        samesite="lax",
        secure=False,  # localhost / air-gapped HTTP için False, HTTPS'de otomatik güvenli
        max_age=24 * 3600,
        path="/",
    )

    return {
        "user": user_dict,
        "token": session_id,
        "csrf_token": csrf_token,
        "must_change_password": user.must_change_password,
    }


@router.post("/logout")
async def logout(
    response: Response,
    session_id: Optional[str] = Depends(get_session_id_from_request),
):
    """Oturumu kapatır."""
    if session_id:
        session_store.delete_session(session_id)
    response.delete_cookie(key="kasp_session", path="/")
    return {"message": "Başarıyla çıkış yapıldı."}


@router.get("/me")
async def get_me(
    user: dict = Depends(get_current_user),
    session_id: Optional[str] = Depends(get_session_id_from_request),
):
    """Mevcut oturum açmış kullanıcı profilini ve CSRF belirtecini getirir."""
    sess = session_store.get_session(session_id) if session_id else None
    csrf_token = sess.get("csrf_token") if sess else ""
    return {
        "user": user,
        "csrf_token": csrf_token,
    }


@router.post("/change-password")
async def change_password(
    req: ChangePasswordRequest,
    user: dict = Depends(get_current_user),
    user_mgr: UserManager = Depends(get_user_manager),
):
    """Oturum açmış kullanıcının şifresini değiştirir."""
    ok, err = user_mgr.change_password(user["id"], req.old_password, req.new_password)
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err or "Şifre değiştirilemedi.")
    
    # Kullanıcı durumunu güncelle
    user["must_change_password"] = False
    return {"message": "Şifreniz başarıyla güncellendi."}


@router.get("/recovery/question")
async def get_recovery_question(
    username: str,
    user_mgr: UserManager = Depends(get_user_manager),
):
    """Kullanıcının kayıtlı güvenlik sorusunu getirir."""
    q, err = user_mgr.get_security_question(username.strip())
    if err or not q:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=err or "Güvenlik sorusu bulunamadı.")
    return {"username": username.strip(), "question": q}


@router.post("/recovery/verify-question")
async def verify_recovery_question(
    req: RecoveryQuestionRequest,
    user_mgr: UserManager = Depends(get_user_manager),
):
    """Güvenlik sorusu cevabı ile şifreyi sıfırlar."""
    ok, err = user_mgr.verify_security_question_and_reset(
        req.username.strip(), req.answer, req.new_password
    )
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err or "Şifre sıfırlanamadı.")
    return {"message": "Şifreniz başarıyla sıfırlandı. Yeni şifrenizle giriş yapabilirsiniz."}


@router.post("/recovery/verify-key")
async def verify_recovery_key(
    req: RecoveryKeyRequest,
    user_mgr: UserManager = Depends(get_user_manager),
):
    """Kurtarma anahtarı ile şifreyi sıfırlar."""
    ok, msg = user_mgr.verify_recovery_key_and_reset(
        req.username.strip(), req.recovery_key, req.new_password
    )
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg or "Geçersiz kurtarma anahtarı.")
    return {"message": msg or "Şifre başarıyla güncellendi."}


@router.post("/security-question")
async def set_security_question(
    req: SetSecurityQuestionRequest,
    user: dict = Depends(get_current_user),
    user_mgr: UserManager = Depends(get_user_manager),
):
    """Mevcut kullanıcı için güvenlik sorusu ve cevabını ayarlar."""
    ok, err = user_mgr.set_security_question(user["id"], req.question, req.answer)
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err or "Güvenlik sorusu ayarlanamadı.")
    user["security_question"] = req.question
    user["has_security_answer"] = True
    return {"message": "Güvenlik sorusu başarıyla kaydedildi."}


@router.post("/recovery-key/generate")
async def generate_recovery_key_route(
    user: dict = Depends(get_current_user),
    user_mgr: UserManager = Depends(get_user_manager),
):
    """Mevcut kullanıcı için yeni bir acil durum kurtarma anahtarı üretir."""
    raw_key, err = user_mgr.generate_and_save_recovery_key(user["id"])
    if err or not raw_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err or "Anahtar üretilemedi.")
    user["has_recovery_key"] = True
    return {
        "recovery_key": raw_key,
        "message": "Kurtarma anahtarınızı güvenli bir yerde saklayın. Bu anahtar bir daha görüntülenemez."
    }
