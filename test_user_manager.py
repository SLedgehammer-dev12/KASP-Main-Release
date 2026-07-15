"""FAZ 5: Kullanıcı Yönetimi Testleri."""
import pytest
import os
import tempfile
from kasp.data.database import UnitDatabase
from kasp.core.user_manager import UserManager, User
from kasp.security import hash_password, verify_password


@pytest.fixture
def test_db():
    """Her test için geçici bir veritabanı oluştur."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db = UnitDatabase(db_name=path)
    yield db
    db.get_connection().close()
    os.unlink(path)


@pytest.fixture
def user_mgr(test_db):
    """UserManager fixture — default admin oluşturur."""
    test_db.create_default_admin(hash_password("Admin1234!"))
    return UserManager(test_db)


# ─────────────────────── Veritabanı Users Tablosu ───────────────────────

def test_users_table_exists(test_db):
    """Users tablosu oluşturulmuş olmalı."""
    cursor = test_db.get_cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='Users'")
    assert cursor.fetchone() is not None


def test_default_admin_created(test_db):
    """create_default_admin bir admin kullanıcısı oluşturmalı."""
    test_db.create_default_admin(hash_password("Test1234!"))
    user = test_db.get_user_by_username("admin")
    assert user is not None
    assert user["role"] == "admin"
    assert user["is_active"] == 1


def test_default_admin_idempotent(test_db):
    """İkinci kez create_default_admin çağrıldığında duplicate olmamalı."""
    test_db.create_default_admin(hash_password("ValidPw1!"))
    test_db.create_default_admin(hash_password("ValidPw2!"))
    users = test_db.get_all_users()
    admin_count = sum(1 for u in users if u["username"] == "admin")
    assert admin_count == 1


# ─────────────────────── UserManager CRUD ───────────────────────

def test_authenticate_valid_user(user_mgr):
    """Geçerli kullanıcı ile authenticate başarılı olmalı."""
    user = user_mgr.authenticate("admin", "Admin1234!")
    assert user is not None
    assert user.username == "admin"
    assert user.role == "admin"


def test_authenticate_wrong_password(user_mgr):
    """Hatalı şifre ile authenticate None dönmeli."""
    user = user_mgr.authenticate("admin", "wrongpass")
    assert user is None


def test_authenticate_nonexistent_user(user_mgr):
    """Var olmayan kullanıcı ile authenticate None dönmeli."""
    user = user_mgr.authenticate("ghost_user", "anything")
    assert user is None


def test_authenticate_inactive_user(user_mgr):
    """Pasif kullanıcı authenticate olamamalı."""
    user_mgr.create_user("tester", "Test1234!", role="user")
    users = user_mgr.list_users()
    tester = next(u for u in users if u.username == "tester")
    user_mgr.update_user(tester.id, is_active=0)
    user = user_mgr.authenticate("tester", "Test1234!")
    assert user is None


def test_create_user(user_mgr):
    """Yeni kullanıcı oluşturulabilmeli."""
    user, err = user_mgr.create_user("engineer1", "ValidEng1!", role="engineer", full_name="Test Eng")
    assert user is not None
    assert err is None
    assert user.username == "engineer1"
    assert user.role == "engineer"
    assert user.full_name == "Test Eng"


def test_create_duplicate_user(user_mgr):
    """Aynı kullanıcı adı ikinci kez oluşturulamamalı."""
    user_mgr.create_user("dup_user", "ValidPw1!")
    user2, err = user_mgr.create_user("dup_user", "AnotherPw1!")
    assert user2 is None
    assert err is not None
    assert "zaten" in err.lower() or "kayitli" in err.lower()


def test_create_user_empty_username(user_mgr):
    """Boş kullanıcı adı reddedilmeli."""
    user, err = user_mgr.create_user("", "ValidPw1!")
    assert user is None
    assert err is not None


def test_create_user_short_password(user_mgr):
    """4 karakterden kısa şifre reddedilmeli."""
    user, err = user_mgr.create_user("newguy", "ab")
    assert user is None
    assert err is not None


def test_list_users(user_mgr):
    """list_users en az 1 kullanıcı dönmeli."""
    users = user_mgr.list_users()
    assert len(users) >= 1
    admin = next(u for u in users if u.username == "admin")
    assert admin.role == "admin"


def test_update_user(user_mgr):
    """Kullanıcı güncellenebilmeli."""
    user, _ = user_mgr.create_user("editme", "ValidPw1!", role="user")
    ok = user_mgr.update_user(user.id, full_name="Edited Name", role="engineer")
    assert ok
    users = user_mgr.list_users()
    updated = next(u for u in users if u.username == "editme")
    assert updated.full_name == "Edited Name"
    assert updated.role == "engineer"


def test_delete_user(user_mgr):
    """Kullanıcı silinebilmeli."""
    user, _ = user_mgr.create_user("delete_me", "ValidPw1!")
    assert user_mgr.delete_user(user.id)
    assert user_mgr.authenticate("delete_me", "ValidPw1!") is None


def test_toggle_user_active(user_mgr):
    """Kullanıcı aktif/pasif toggle edilebilmeli."""
    user, _ = user_mgr.create_user("toggle_me", "ValidPw1!")
    assert user.is_active
    user_mgr.toggle_user_active(user.id)
    users = user_mgr.list_users()
    toggled = next(u for u in users if u.username == "toggle_me")
    assert not toggled.is_active
    user_mgr.toggle_user_active(user.id)
    users = user_mgr.list_users()
    toggled = next(u for u in users if u.username == "toggle_me")
    assert toggled.is_active


# ─────────────────────── Password Change ───────────────────────

def test_change_password_valid(user_mgr):
    """Geçerli eski şifre ile şifre değiştirilebilmeli."""
    user, _ = user_mgr.create_user("pw_user", "Old1234!")
    ok, err = user_mgr.change_password(user.id, "Old1234!", "New5678!")
    assert ok
    assert err is None
    assert user_mgr.authenticate("pw_user", "New5678!") is not None
    assert user_mgr.authenticate("pw_user", "Old1234!") is None


def test_change_password_wrong_old(user_mgr):
    """Hatalı eski şifre ile değişiklik reddedilmeli."""
    user, _ = user_mgr.create_user("pw_user2", "Correct1!")
    ok, err = user_mgr.change_password(user.id, "WrongPw1!", "NewValid1!")
    assert not ok


def test_change_password_short_new(user_mgr):
    """Kısa yeni şifre reddedilmeli."""
    user, _ = user_mgr.create_user("pw_user3", "Correct1!")
    ok, err = user_mgr.change_password(user.id, "Correct1!", "ab")
    assert not ok


def test_admin_reset_password(user_mgr):
    """Admin herhangi bir kullanıcının şifresini sıfırlayabilmeli."""
    user, _ = user_mgr.create_user("target", "Original1!")
    ok, err = user_mgr.admin_reset_password(user.id, "Reset12345!")
    assert ok
    assert user_mgr.authenticate("target", "Reset12345!") is not None
    assert user_mgr.authenticate("target", "Original1!") is None


def test_admin_reset_password_short(user_mgr):
    """Admin reset — kısa şifre reddedilmeli."""
    user, _ = user_mgr.create_user("target2", "Original1!")
    ok, err = user_mgr.admin_reset_password(user.id, "ab")
    assert not ok


# ─────────────────────── Login Tracking ───────────────────────

def test_authenticate_updates_last_login(user_mgr):
    """Başarılı login last_login alanını güncellemeli."""
    user_mgr.create_user("login_tester", "ValidPw1!")
    user = user_mgr.authenticate("login_tester", "ValidPw1!")
    assert user.last_login is not None
    assert len(user.last_login) > 0


# ─────────────────────── must_change_password ───────────────────────

def test_create_user_must_change_password_default(user_mgr):
    """Yeni kullanıcının must_change_password varsayılanı False olmalı."""
    user, _ = user_mgr.create_user("fresh_user", "Password123!")
    assert user.must_change_password is False


def test_admin_reset_sets_must_change_password(user_mgr):
    """Admin şifre sıfırlayınca must_change_password True olmalı."""
    user, _ = user_mgr.create_user("resettable", "Oldpw1234!")
    ok, err = user_mgr.admin_reset_password(user.id, "Newpw5678!")
    assert ok

    users = user_mgr.list_users()
    updated = next(u for u in users if u.username == "resettable")
    assert updated.must_change_password is True

    auth = user_mgr.authenticate("resettable", "Newpw5678!")
    assert auth is not None
    assert auth.must_change_password is True


def test_admin_reset_old_password_no_longer_works(user_mgr):
    """Admin sıfırlaması sonrası eski şifre çalışmamalı."""
    user, _ = user_mgr.create_user("pw_reset", "Oldpw1234!")
    user_mgr.admin_reset_password(user.id, "Newpw9999!")
    assert user_mgr.authenticate("pw_reset", "Oldpw1234!") is None
    assert user_mgr.authenticate("pw_reset", "Newpw9999!") is not None


def test_normal_password_change_does_not_set_flag(user_mgr):
    """Kendi şifresini değiştiren kullanıcıda must_change_password değişmemeli."""
    user, _ = user_mgr.create_user("self_change", "Original1!")
    ok, _ = user_mgr.change_password(user.id, "Original1!", "Updated12!")
    assert ok
    users = user_mgr.list_users()
    updated = next(u for u in users if u.username == "self_change")
    assert updated.must_change_password is False


def test_admin_can_clear_must_change_password(user_mgr):
    """Admin must_change_password flag'ini temizleyebilmeli."""
    user, _ = user_mgr.create_user("flagged", "Pw12345!")
    user_mgr.admin_reset_password(user.id, "Newpw9999!")
    users = user_mgr.list_users()
    u = next(u for u in users if u.username == "flagged")
    assert u.must_change_password is True

    user_mgr.update_user(u.id, must_change_password=0)
    users = user_mgr.list_users()
    u2 = next(u for u in users if u.username == "flagged")
    assert u2.must_change_password is False
