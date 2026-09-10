"""KASP Şifre Kurtarma, Güvenlik Sorusu ve CLI Acil Durum Testleri."""

import os
import pytest
import sqlite3
import tempfile
from PyQt5.QtWidgets import QApplication

from kasp.security import (
    DEFAULT_PASSWORD,
    check_lockout,
    generate_recovery_key,
    hash_password,
    normalize_recovery_key,
    normalize_security_answer,
    record_attempt,
    reset_lockout_state,
    verify_password,
)
from kasp.core.user_manager import UserManager, validate_password_policy
from kasp.data.database import UnitDatabase


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db = UnitDatabase(db_name=path)
    yield db
    db.get_connection().close()
    try:
        os.unlink(path)
    except OSError:
        pass


@pytest.fixture
def user_mgr(temp_db):
    mgr = UserManager(temp_db)
    # Varsayılan admin oluştur
    temp_db.create_default_admin(hash_password(DEFAULT_PASSWORD))
    return mgr


def test_security_helpers():
    # normalize_security_answer
    assert normalize_security_answer("  AnKaRa  ") == "ankara"
    assert normalize_security_answer("") == ""

    # generate_recovery_key
    key = generate_recovery_key()
    assert key.startswith("KASP-")
    parts = key.split("-")
    assert len(parts) == 4
    for p in parts[1:]:
        assert len(p) == 4

    # normalize_recovery_key
    assert normalize_recovery_key(key.lower()) == key
    assert normalize_recovery_key(key.replace("-", "")) == key
    assert normalize_recovery_key("  " + key + "  ") == key


def test_set_and_get_security_question(user_mgr):
    user, err = user_mgr.create_user("engineer1", "Pass1234", role="user")
    assert user is not None

    # Boş soru reddedilmeli
    ok, err = user_mgr.set_security_question(user.id, "", "cevap")
    assert not ok
    assert "boş olamaz" in err

    # Kısa cevap reddedilmeli (<2 karakter)
    ok, err = user_mgr.set_security_question(user.id, "Doğum yeriniz?", "a")
    assert not ok
    assert "en az 2 karakter" in err

    # Geçerli soru ve cevap
    ok, err = user_mgr.set_security_question(user.id, "Doğduğunuz şehir neresidir?", "İstanbul")
    assert ok
    assert err is None

    # Soruyu sorgula
    q, err = user_mgr.get_security_question("engineer1")
    assert q == "Doğduğunuz şehir neresidir?"
    assert err is None

    # Olmayan kullanıcı için sorgu
    q_none, err = user_mgr.get_security_question("nonexistent")
    assert q_none is None
    assert "Kullanıcı bulunamadı" in err


def test_verify_security_question_and_reset(user_mgr):
    user, _ = user_mgr.create_user("tech_user", "Oldpass123", role="user")
    user_mgr.set_security_question(user.id, "İlk arabanız?", "Toros")

    # Yanlış cevapla sıfırlama başarısız olmalı
    ok, err = user_mgr.verify_security_question_and_reset("tech_user", "Renault", "Newpass999")
    assert not ok
    assert "hatalı" in err

    # Zayıf yeni şifre reddedilmeli
    ok, err = user_mgr.verify_security_question_and_reset("tech_user", "toros", "short")
    assert not ok
    assert "en az 8 karakter" in err

    # Büyük/küçük harf ve boşluk toleransı ile doğru cevap
    ok, err = user_mgr.verify_security_question_and_reset("tech_user", "  tOrOs  ", "SecurePass888")
    assert ok
    assert err is None

    # Yeni şifre ile kimlik doğrulama başarılı olmalı
    auth_user = user_mgr.authenticate("tech_user", "SecurePass888")
    assert auth_user is not None
    assert auth_user.username == "tech_user"
    assert not auth_user.must_change_password


def test_recovery_key_generation_and_reset(user_mgr):
    user, _ = user_mgr.create_user("operator", "Initial123", role="user")
    key, err = user_mgr.generate_and_save_recovery_key(user.id)
    assert key is not None
    assert key.startswith("KASP-")

    # Yanlış anahtar ile sıfırlama
    ok, err = user_mgr.verify_recovery_key_and_reset("operator", "KASP-0000-0000-0000", "NewPass321")
    assert not ok
    assert "Geçersiz" in err

    # Doğru anahtar ile sıfırlama (tire olmadan / küçük harf ile de geçerli)
    raw_clean = key.lower().replace("-", "")
    ok, err = user_mgr.verify_recovery_key_and_reset("operator", raw_clean, "SuperSecure777")
    assert ok
    assert err is None

    # Yeni şifre doğrulanmalı
    auth = user_mgr.authenticate("operator", "SuperSecure777")
    assert auth is not None


def test_cli_emergency_reset_admin(user_mgr):
    # Admin şifresini bilerek değiştirip kilitliyoruz
    admin_dict = user_mgr.db.get_user_by_username("admin")
    user_mgr.admin_reset_password(admin_dict["id"], "ChangedPassword999")
    for _ in range(3):
        record_attempt(success=False)
    locked, _ = check_lockout()
    assert locked

    # CLI Acil Sıfırlama çağrısı
    ok, pw, key = user_mgr.cli_emergency_reset_admin()
    assert ok
    assert pw == DEFAULT_PASSWORD
    assert key.startswith("KASP-")

    # Kilit kalkmış olmalı
    locked_after, _ = check_lockout()
    assert not locked_after

    # Admin yeni geçici şifre ile giriş yapabilmeli ve must_change_password=True olmalı
    admin_user = user_mgr.authenticate("admin", DEFAULT_PASSWORD)
    assert admin_user is not None
    assert admin_user.must_change_password is True


def test_password_recovery_dialog(qapp, user_mgr, monkeypatch):
    from PyQt5.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: QMessageBox.Ok)
    from kasp.ui.password_recovery_dialog import PasswordRecoveryDialog

    user, _ = user_mgr.create_user("rec_user", "PassWord123", role="user")
    user_mgr.set_security_question(user.id, "En sevdiğiniz renk?", "Mavi")

    dialog = PasswordRecoveryDialog(user_mgr, default_username="rec_user")
    assert dialog._question_label.text().startswith("❓")

    # Yanıt ve yeni şifre gir
    dialog._answer_edit.setText("mavi")
    dialog._new_pw_edit.setText("ResetPass456")
    dialog._confirm_pw_edit.setText("ResetPass456")

    # Sıfırlamayı tetikle
    dialog._do_reset()
    assert dialog.recovered_username == "rec_user"

    # Veritabanında kontrol et
    auth = user_mgr.authenticate("rec_user", "ResetPass456")
    assert auth is not None
    dialog.close()


def test_security_settings_dialog(qapp, user_mgr, monkeypatch):
    from PyQt5.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: QMessageBox.Ok)
    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)
    from kasp.ui.dialogs import SecuritySettingsDialog

    user, _ = user_mgr.create_user("settings_user", "PassWord123", role="user")
    dialog = SecuritySettingsDialog(user_mgr, user)
    dialog._ans_edit.setText("Ankara")
    dialog._save_security_question()

    q, err = user_mgr.get_security_question("settings_user")
    assert q is not None

    dialog._generate_new_key()
    assert dialog._key_display.text().startswith("KASP-")
    dialog.close()


def test_login_dialog_recovery_button(qapp, user_mgr):
    from kasp.ui.login_dialog import LoginDialog

    login_dlg = LoginDialog(user_mgr)
    assert hasattr(login_dlg, "_forgot_btn")
    assert login_dlg._forgot_btn.text() == "❓ Şifremi Unuttum"
    login_dlg.close()
