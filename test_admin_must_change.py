"""Başlangıç admin akışı: şifre değişimi sonrası zorunlu değişiklik tekrar tetiklenmemeli."""

import os
import tempfile

import pytest

from kasp.core.user_manager import (
    UserManager,
    ensure_initial_admin,
)
from kasp.data.database import UnitDatabase
from kasp.security import hash_password


@pytest.fixture
def db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    database = UnitDatabase(db_name=path)
    yield database
    database.get_connection().close()
    try:
        os.unlink(path)
    except OSError:
        pass


def test_fresh_install_creates_admin_with_forced_change(db):
    initial_pw = ensure_initial_admin(db)

    assert initial_pw, "ilk kurulumda tek seferlik parola üretilmeli"
    admin = db.get_user_by_username("admin")
    assert admin is not None
    assert admin["must_change_password"] == 1

    user = UserManager(db).authenticate("admin", initial_pw)
    assert user is not None
    assert user.must_change_password is True


def test_password_change_survives_restart(db):
    initial_pw = ensure_initial_admin(db)
    user_mgr = UserManager(db)
    admin = db.get_user_by_username("admin")

    ok, err = user_mgr.change_password(admin["id"], initial_pw, "Kasp!2026#Admin")
    assert ok, err
    db.update_user(admin["id"], must_change_password=0)

    # Uygulama yeniden açılıyor: başlangıç yardımcısı flag'i geri açmamalı.
    assert ensure_initial_admin(db) is None
    assert db.get_user_by_username("admin")["must_change_password"] == 0

    # İkinci yeniden açılış da aynı davranmalı.
    assert ensure_initial_admin(db) is None
    assert db.get_user_by_username("admin")["must_change_password"] == 0


def test_admin_reset_still_forces_change(db):
    ensure_initial_admin(db)
    user_mgr = UserManager(db)
    admin = db.get_user_by_username("admin")

    ok, err = user_mgr.admin_reset_password(admin["id"], "Reset!2026Pass")
    assert ok, err
    assert db.get_user_by_username("admin")["must_change_password"] == 1


def test_ensure_initial_admin_is_idempotent_for_existing_users(db):
    db.create_user("engineer", hash_password("Engineer123!"), role="engineer")

    assert ensure_initial_admin(db) is None
    assert db.get_user_by_username("admin") is None
