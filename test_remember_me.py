"""KASP 'Beni hatırla' kalıcı oturum testleri (Red → Green)."""

import json
import os
import stat
import tempfile
import time

import pytest
from PyQt5.QtWidgets import QApplication

from kasp.core.remember_me import (
    RememberMeManager,
    generate_remember_token,
    hash_remember_token,
)
from kasp.core.user_manager import UserManager
from kasp.data.database import UnitDatabase
from kasp.security import hash_password


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    database = UnitDatabase(db_name=path)
    database.create_user(
        username="admin",
        password_hash=hash_password("AdminPass123!"),
        role="admin",
        full_name="Test Admin",
    )
    yield database
    database.get_connection().close()
    try:
        os.unlink(path)
    except OSError:
        pass


@pytest.fixture
def store_path(tmp_path):
    return str(tmp_path / "kasp_remember.json")


@pytest.fixture
def manager(db, store_path):
    return RememberMeManager(UserManager(db), store_path=store_path)


def test_token_generation_is_random_and_hash_is_sha256():
    token_a = generate_remember_token()
    token_b = generate_remember_token()
    assert token_a != token_b
    assert len(token_a) >= 32
    assert hash_remember_token(token_a) == hash_remember_token(token_a)
    assert len(hash_remember_token(token_a)) == 64


def test_issue_stores_only_hash_in_db(manager, db, store_path):
    token = manager.issue("admin")

    assert token
    assert os.path.exists(store_path)

    stored = json.load(open(store_path, encoding="utf-8"))
    assert stored["username"] == "admin"
    assert stored["token"] == token

    row = db.get_cursor().execute(
        "SELECT token_hash FROM RememberTokens"
    ).fetchone()
    assert row is not None
    assert row["token_hash"] == hash_remember_token(token)
    assert row["token_hash"] != token


def test_store_file_permissions_are_owner_only(manager, store_path):
    manager.issue("admin")
    mode = stat.S_IMODE(os.stat(store_path).st_mode)
    if os.name == "posix":
        assert mode == 0o600, f"beklenen 0600, bulunan {oct(mode)}"


def test_redeem_returns_user_and_rotates_token(manager, store_path):
    first = manager.issue("admin")
    user = manager.redeem()

    assert user is not None
    assert user.username == "admin"

    rotated = json.load(open(store_path, encoding="utf-8"))["token"]
    assert rotated != first
    assert manager.redeem() is not None  # yeni jeton da geçerli


def test_expired_token_is_rejected_and_removed(manager, db, store_path):
    manager.issue("admin")
    db.get_cursor().execute(
        "UPDATE RememberTokens SET expires_at = ?", (time.time() - 5,)
    )
    db.get_connection().commit()

    assert manager.redeem() is None
    assert not os.path.exists(store_path)
    count = db.get_cursor().execute("SELECT COUNT(*) FROM RememberTokens").fetchone()[0]
    assert count == 0


def test_forget_clears_store_and_db(manager, db, store_path):
    manager.issue("admin")
    manager.forget()

    assert not os.path.exists(store_path)
    count = db.get_cursor().execute("SELECT COUNT(*) FROM RememberTokens").fetchone()[0]
    assert count == 0
    assert manager.redeem() is None


def test_must_change_password_blocks_auto_login(manager, db, store_path):
    manager.issue("admin")
    user = db.get_user_by_username("admin")
    db.update_user(user["id"], must_change_password=1)

    assert manager.redeem() is None
    assert not os.path.exists(store_path)


def test_password_change_revokes_saved_token(manager, db, store_path):
    manager.issue("admin")
    user_mgr = UserManager(db)
    ok, err = user_mgr.change_password(
        db.get_user_by_username("admin")["id"], "AdminPass123!", "NewAdminPass123!"
    )
    assert ok, err

    count = db.get_cursor().execute("SELECT COUNT(*) FROM RememberTokens").fetchone()[0]
    assert count == 0


def test_login_dialog_auto_login_without_typing(qapp, manager):
    from kasp.ui.login_dialog import LoginDialog

    manager.issue("admin")
    dialog = LoginDialog(manager.user_manager, remember_me_manager=manager)

    assert dialog.authenticated_user() is not None
    assert dialog.authenticated_user().username == "admin"

    dialog.close()


def test_login_dialog_checkbox_saves_and_clears_token(qapp, manager, store_path):
    from kasp.ui.login_dialog import LoginDialog

    dialog = LoginDialog(manager.user_manager, remember_me_manager=manager)
    dialog._username_edit.setText("admin")
    dialog._password_edit.setText("AdminPass123!")
    dialog._remember_cb.setChecked(True)
    dialog._try_login()

    assert dialog.authenticated_user() is not None
    assert os.path.exists(store_path)
    dialog.close()

    manager.forget()
    dialog2 = LoginDialog(manager.user_manager, remember_me_manager=manager)
    dialog2._username_edit.setText("admin")
    dialog2._password_edit.setText("WrongPass1!")
    dialog2._remember_cb.setChecked(False)
    dialog2._try_login()
    assert dialog2.authenticated_user() is None
    assert not os.path.exists(store_path)
    dialog2.close()
