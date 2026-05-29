from dataclasses import dataclass, field
import logging
from kasp.security import hash_password, verify_password

logger = logging.getLogger(__name__)


@dataclass
class User:
    id: int
    username: str
    role: str = "user"
    full_name: str = ""
    email: str = ""
    is_active: bool = True
    must_change_password: bool = False
    created_at: str = ""
    last_login: str = ""


class UserManager:
    def __init__(self, db):
        self.db = db

    def authenticate(self, username: str, password: str):
        user_dict = self.db.get_user_by_username(username)
        if not user_dict:
            logger.info(f"Auth basarisiz: '{username}' kullanici adi bulunamadi.")
            return None
        if not user_dict.get("is_active", 1):
            logger.info(f"Auth basarisiz: '{username}' hesabi pasif.")
            return None
        stored_hash = user_dict.get("password_hash", "")
        if not stored_hash:
            logger.warning(f"Auth basarisiz: '{username}' hash degiskeni bos.")
            return None
        if not verify_password(password, stored_hash):
            logger.info(f"Auth basarisiz: '{username}' icin hatali sifre.")
            return None
        self.db.update_user_login(user_dict["id"])
        user_dict = self.db.get_user_by_username(username)
        if not user_dict:
            return None
        return User(
            id=user_dict["id"],
            username=user_dict["username"],
            role=user_dict.get("role", "user"),
            full_name=user_dict.get("full_name", ""),
            email=user_dict.get("email", ""),
            is_active=bool(user_dict.get("is_active", 1)),
            must_change_password=bool(user_dict.get("must_change_password", 0)),
            created_at=user_dict.get("created_at", ""),
            last_login=user_dict.get("last_login", ""),
        )

    def create_user(self, username, password, role="user", full_name="", email=""):
        if not username or not password:
            return None, "Kullanici adi ve sifre zorunludur."
        if len(password) < 4:
            return None, "Sifre en az 4 karakter olmalidir."
        if self.db.get_user_by_username(username):
            return None, f"'{username}' kullanici adi zaten kayitli."
        password_hash = hash_password(password)
        user_id = self.db.create_user(username, password_hash, role, full_name, email)
        if user_id is None:
            return None, "Kullanici olusturulamadi (benzersiz olmayan kullanici adi)."
        logger.info(f"Kullanici olusturuldu: {username} (rol: {role})")
        return User(id=user_id, username=username, role=role, full_name=full_name, email=email), None

    def list_users(self):
        users = self.db.get_all_users()
        return [User(
            id=u["id"], username=u["username"], role=u.get("role", "user"),
            full_name=u.get("full_name", ""), email=u.get("email", ""),
            is_active=bool(u.get("is_active", 1)),
            must_change_password=bool(u.get("must_change_password", 0)),
            created_at=u.get("created_at", ""), last_login=u.get("last_login", "")
        ) for u in users]

    def update_user(self, user_id, **kwargs):
        return self.db.update_user(user_id, **kwargs)

    def change_password(self, user_id, old_password, new_password):
        users = self.db.get_all_users()
        target = next((u for u in users if u["id"] == user_id), None)
        if not target:
            return False, "Kullanici bulunamadi."
        if not verify_password(old_password, target["password_hash"]):
            return False, "Mevcut sifre yanlis."
        if len(new_password) < 4:
            return False, "Yeni sifre en az 4 karakter olmalidir."
        new_hash = hash_password(new_password)
        return self.db.update_user(user_id, password_hash=new_hash), None

    def admin_reset_password(self, user_id, new_password):
        if len(new_password) < 4:
            return False, "Yeni şifre en az 4 karakter olmalidir."
        new_hash = hash_password(new_password)
        ok = self.db.update_user(user_id, password_hash=new_hash, must_change_password=1)
        return ok, (None if ok else "Şifre sıfırlanamadı.")

    def delete_user(self, user_id):
        return self.db.delete_user(user_id)

    def toggle_user_active(self, user_id):
        users = self.db.get_all_users()
        target = next((u for u in users if u["id"] == user_id), None)
        if not target:
            return False
        new_state = 0 if target.get("is_active", 1) else 1
        return self.db.update_user(user_id, is_active=new_state)
