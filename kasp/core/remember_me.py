"""KASP 'Beni hatırla' kalıcı oturum yöneticisi.

Parola diskte saklanmaz. Bunun yerine süreli, yenilenen rastgele bir oturum
jetonu üretilir:

- Veritabanında yalnızca jetonun SHA-256 özeti tutulur (`RememberTokens`).
- Ham jeton, uygulama veri dizininde yalnızca sahibinin okuyabildiği (0600)
  `kasp_remember.json` dosyasında saklanır.
- Her otomatik girişte jeton döndürülür (rotation), böylece dosyadan sızan
  eski jeton tekrar kullanılamaz.
- Parola değişimi, yönetici sıfırlaması veya kurtarma anahtarı kullanımı
  tüm jetonları iptal eder.
"""

import hashlib
import json
import logging
import os
import secrets
import stat
import time

from kasp.core.user_manager import user_from_dict
from kasp.security import get_app_data_dir

logger = logging.getLogger(__name__)

REMEMBER_DAYS = 30
STORE_FILENAME = "kasp_remember.json"
TOKEN_MIN_LEN = 32


def generate_remember_token() -> str:
    """Kriptografik olarak güvenli, URL-güvenli oturum jetonu üretir."""
    return secrets.token_urlsafe(32)


def hash_remember_token(token: str) -> str:
    """Jetonun veritabanında saklanacak SHA-256 özetini döndürür."""
    return hashlib.sha256(str(token).encode("utf-8")).hexdigest()


class RememberMeManager:
    """Oturum jetonlarını üretir, doğrular, döndürür ve iptal eder."""

    def __init__(self, user_manager, store_path: str | None = None,
                 days: int = REMEMBER_DAYS, clock=time.time):
        self.user_manager = user_manager
        self.db = user_manager.db
        self.days = max(1, int(days))
        self.clock = clock
        self.store_path = store_path or os.path.join(
            get_app_data_dir(), STORE_FILENAME
        )

    # ───────────────────────────── Genel API ─────────────────────────────

    def saved_username(self) -> str | None:
        """Diskte kayıtlı oturum varsa kullanıcı adını döndürür."""
        data = self._read_store()
        if not data:
            return None
        username = data.get("username")
        return username if isinstance(username, str) and username else None

    def is_available(self) -> bool:
        """Otomatik giriş için kullanılabilir bir jeton var mı?"""
        return self._read_store() is not None

    def issue(self, username: str) -> str | None:
        """Kullanıcı için yeni bir jeton üretir ve diske yazar."""
        user_dict = self.db.get_user_by_username(str(username or "").strip())
        if not user_dict or not user_dict.get("is_active", 1):
            return None

        token = generate_remember_token()
        token_hash = hash_remember_token(token)
        expires_at = self.clock() + self.days * 86400
        created = self.db.create_remember_token(
            user_dict["id"], token_hash, expires_at
        )
        if not created:
            return None

        if not self._write_store(user_dict["username"], token):
            self.db.delete_remember_token(token_hash)
            return None

        logger.info("Beni hatırla jetonu üretildi: %s", user_dict["username"])
        return token

    def redeem(self):
        """Kayıtlı jetonu doğrular; geçerliyse kullanıcıyı döndürür ve jetonu döndürür."""
        data = self._read_store()
        if not data:
            return None

        token = data.get("token")
        if not isinstance(token, str) or len(token) < TOKEN_MIN_LEN:
            self.forget()
            return None

        token_hash = hash_remember_token(token)
        row = self.db.get_remember_token(token_hash)
        if not row:
            self._clear_store()
            return None

        if float(row.get("expires_at") or 0) <= self.clock():
            self.db.delete_remember_token(token_hash)
            self._clear_store()
            logger.info("Beni hatırla jetonunun süresi dolmuş.")
            return None

        user_dict = self.db.get_user_by_id(row["user_id"])
        if not user_dict or not user_dict.get("is_active", 1):
            self.db.delete_remember_token(token_hash)
            self._clear_store()
            return None

        if user_dict.get("must_change_password", 0):
            # Yönetici sıfırlaması sonrası otomatik girişe izin verilmez.
            self.db.delete_user_remember_tokens(user_dict["id"])
            self._clear_store()
            logger.info("Beni hatırla reddedildi: şifre değişikliği zorunlu.")
            return None

        # Jeton rotation: eski jeton geçersiz, yenisi diske yazılır.
        self.db.delete_remember_token(token_hash)
        new_token = generate_remember_token()
        new_hash = hash_remember_token(new_token)
        expires_at = self.clock() + self.days * 86400
        if not self.db.create_remember_token(user_dict["id"], new_hash, expires_at):
            self._clear_store()
            return None
        if not self._write_store(user_dict["username"], new_token):
            self.db.delete_remember_token(new_hash)
            return None

        self.db.touch_remember_token(new_hash, self.clock())
        self.db.update_user_login(user_dict["id"])
        logger.info("Beni hatırla ile oturum açıldı: %s", user_dict["username"])
        return user_from_dict(self.db.get_user_by_id(user_dict["id"]) or user_dict)

    def forget(self) -> None:
        """Kayıtlı jetonu ve veritabanı kaydını siler."""
        data = self._read_store()
        if data and isinstance(data.get("token"), str):
            self.db.delete_remember_token(hash_remember_token(data["token"]))
        self._clear_store()

    # ─────────────────────────── Dosya işlemleri ───────────────────────────

    def _read_store(self) -> dict | None:
        try:
            with open(self.store_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return None
        if not isinstance(data, dict) or not data.get("token"):
            return None
        return data

    def _write_store(self, username: str, token: str) -> bool:
        payload = {"username": username, "token": token, "version": 1}
        tmp_path = f"{self.store_path}.{os.getpid()}.tmp"
        try:
            directory = os.path.dirname(self.store_path)
            if directory:
                os.makedirs(directory, exist_ok=True)
            fd = os.open(tmp_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(payload, f)
            os.replace(tmp_path, self.store_path)
            try:
                os.chmod(self.store_path, stat.S_IRUSR | stat.S_IWUSR)
            except OSError:
                pass
            return True
        except OSError as e:
            logger.warning("Beni hatırla dosyası yazılamadı: %s", e)
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            return False

    def _clear_store(self) -> None:
        try:
            os.unlink(self.store_path)
        except FileNotFoundError:
            pass
        except OSError as e:
            logger.warning("Beni hatırla dosyası silinemedi: %s", e)
