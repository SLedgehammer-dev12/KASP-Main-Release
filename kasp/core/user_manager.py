from dataclasses import dataclass, field
import logging
import re
from kasp.security import (
    DEFAULT_PASSWORD,
    generate_recovery_key,
    hash_password,
    normalize_recovery_key,
    normalize_security_answer,
    reset_lockout_state,
    verify_password,
)

logger = logging.getLogger(__name__)

DEFAULT_SECURITY_QUESTIONS = [
    "İlk evcil hayvanınızın adı nedir?",
    "Doğduğunuz şehir neresidir?",
    "İlk çalıştığınız şirketin adı nedir?",
    "En sevdiğiniz bilim insanı veya mühendis kimdir?",
    "İlkokul öğretmeninizin soyadı nedir?",
]


def validate_password_policy(password: str) -> str | None:
    """Şifre politikasını doğrular. Hata mesajı dönerse geçersizdir, None ise geçerlidir."""
    if len(password) < 8:
        return "Şifre en az 8 karakter olmalıdır."
    if not re.search(r"[A-Z]", password):
        return "Şifre en az bir büyük harf içermelidir."
    if not re.search(r"[a-z]", password):
        return "Şifre en az bir küçük harf içermelidir."
    if not re.search(r"\d", password):
        return "Şifre en az bir rakam içermelidir."
    return None


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
    security_question: str = ""
    has_security_answer: bool = False
    has_recovery_key: bool = False


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
            security_question=user_dict.get("security_question", "") or "",
            has_security_answer=bool(user_dict.get("security_answer_hash")),
            has_recovery_key=bool(user_dict.get("recovery_key_hash")),
        )

    def create_user(self, username, password, role="user", full_name="", email=""):
        if not username or not password:
            return None, "Kullanici adi ve sifre zorunludur."
        pw_error = validate_password_policy(password)
        if pw_error:
            return None, pw_error
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
            created_at=u.get("created_at", ""), last_login=u.get("last_login", ""),
            security_question=u.get("security_question", "") or "",
            has_security_answer=bool(u.get("security_answer_hash")),
            has_recovery_key=bool(u.get("recovery_key_hash")),
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
        pw_error = validate_password_policy(new_password)
        if pw_error:
            return False, pw_error
        new_hash = hash_password(new_password)
        return self.db.update_user(user_id, password_hash=new_hash), None

    def admin_reset_password(self, user_id, new_password):
        pw_error = validate_password_policy(new_password)
        if pw_error:
            return False, pw_error
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

    def set_security_question(self, user_id: int, question: str, answer: str) -> tuple[bool, str | None]:
        """Kullanıcı için güvenlik sorusu ve hashlenmiş cevabı kaydeder."""
        question = (question or "").strip()
        if not question:
            return False, "Güvenlik sorusu boş olamaz."
        clean_ans = normalize_security_answer(answer)
        if len(clean_ans) < 2:
            return False, "Güvenlik sorusu cevabı en az 2 karakter olmalıdır."
        
        ans_hash = hash_password(clean_ans)
        ok = self.db.update_user(
            user_id,
            security_question=question,
            security_answer_hash=ans_hash
        )
        if ok:
            logger.info(f"Kullanıcı id {user_id} için güvenlik sorusu güncellendi.")
            return True, None
        return False, "Güvenlik sorusu kaydedilemedi."

    def get_security_question(self, username: str) -> tuple[str | None, str | None]:
        """Kullanıcı adından güvenlik sorusunu getirir."""
        user_dict = self.db.get_user_by_username(username.strip())
        if not user_dict:
            return None, "Kullanıcı bulunamadı."
        q = user_dict.get("security_question", "")
        has_ans = bool(user_dict.get("security_answer_hash"))
        if not q or not has_ans:
            return None, "Bu kullanıcı için tanımlı bir güvenlik sorusu bulunmuyor."
        return q, None

    def verify_security_question_and_reset(
        self, username: str, answer: str, new_password: str
    ) -> tuple[bool, str | None]:
        """Güvenlik sorusu cevabını doğrulayıp yeni şifreyi tanımlar."""
        user_dict = self.db.get_user_by_username(username.strip())
        if not user_dict:
            return False, "Kullanıcı bulunamadı."
        if not user_dict.get("is_active", 1):
            return False, "Hesap pasif durumda. Sistem yöneticinize başvurun."
        
        stored_hash = user_dict.get("security_answer_hash", "")
        if not stored_hash:
            return False, "Bu hesap için tanımlı güvenlik sorusu cevabı bulunmuyor."

        if not verify_password(normalize_security_answer(answer), stored_hash):
            return False, "Güvenlik sorusu cevabı hatalı."

        pw_error = validate_password_policy(new_password)
        if pw_error:
            return False, pw_error

        new_hash = hash_password(new_password)
        ok = self.db.update_user(user_dict["id"], password_hash=new_hash, must_change_password=0)
        if ok:
            reset_lockout_state()
            logger.info(f"Kullanıcı '{username}' güvenlik sorusu ile şifresini başarıyla sıfırladı.")
            return True, None
        return False, "Şifre güncellenemedi."

    def generate_and_save_recovery_key(self, user_id: int) -> tuple[str | None, str | None]:
        """16 haneli yeni bir acil durum kurtarma anahtarı üretir, hash'ler ve kaydeder."""
        raw_key = generate_recovery_key()
        normalized_key = normalize_recovery_key(raw_key)
        key_hash = hash_password(normalized_key)
        ok = self.db.update_user(user_id, recovery_key_hash=key_hash)
        if ok:
            logger.info(f"Kullanıcı id {user_id} için yeni kurtarma anahtarı üretildi.")
            return raw_key, None
        return None, "Kurtarma anahtarı kaydedilemedi."

    def verify_recovery_key_and_reset(
        self, username: str, recovery_key: str, new_password: str
    ) -> tuple[bool, str | None]:
        """Acil durum kurtarma anahtarı ile şifreyi sıfırlar."""
        user_dict = self.db.get_user_by_username(username.strip())
        if not user_dict:
            return False, "Kullanıcı bulunamadı."
        if not user_dict.get("is_active", 1):
            return False, "Hesap pasif durumda."

        stored_hash = user_dict.get("recovery_key_hash", "")
        if not stored_hash:
            return False, "Bu hesap için tanımlı bir kurtarma anahtarı bulunmuyor."

        if not verify_password(normalize_recovery_key(recovery_key), stored_hash):
            return False, "Geçersiz kurtarma anahtarı."

        pw_error = validate_password_policy(new_password)
        if pw_error:
            return False, pw_error

        new_hash = hash_password(new_password)
        ok = self.db.update_user(user_dict["id"], password_hash=new_hash, must_change_password=0)
        if ok:
            reset_lockout_state()
            logger.info(f"Kullanıcı '{username}' kurtarma anahtarı ile şifresini sıfırladı.")
            return True, None
        return False, "Şifre güncellenemedi."

    def cli_emergency_reset_admin(self, custom_password: str = None) -> tuple[bool, str, str]:
        """CLI acil durum aracı: Admin şifresini sıfırlar, yeni kurtarma anahtarı üretir."""
        admin_dict = self.db.get_user_by_username("admin")
        pw = custom_password or DEFAULT_PASSWORD
        pw_hash = hash_password(pw)
        
        if not admin_dict:
            self.db.create_default_admin(pw_hash)
            admin_dict = self.db.get_user_by_username("admin")

        admin_id = admin_dict["id"]
        raw_key, _ = self.generate_and_save_recovery_key(admin_id)
        self.db.update_user(admin_id, password_hash=pw_hash, is_active=1, must_change_password=1)
        reset_lockout_state()
        logger.info("CLI Acil Durum: Admin şifresi ve kurtarma anahtarı başarıyla sıfırlandı.")
        return True, pw, (raw_key or "")
