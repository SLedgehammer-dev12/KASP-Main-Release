"""FAZ 5D: Session ve PermissionManager Testleri."""
import pytest
from kasp.security import Session, PermissionManager, get_permission_manager
from kasp.core.user_manager import User


@pytest.fixture(autouse=True)
def reset_session():
    """Her test öncesi session'ı temizle."""
    Session.logout()
    yield
    Session.logout()


def _make_user(username="testuser", role="user"):
    return User(id=1, username=username, role=role, full_name="Test", email="t@t.com")


# ─────────────────────── PermissionManager ───────────────────────

def test_permission_default_role_is_user():
    pm = PermissionManager()
    assert pm.user_role == "user"


def test_permission_admin_has_all():
    pm = PermissionManager()
    pm.set_user_role("admin")
    assert pm.has_permission("read")
    assert pm.has_permission("write")
    assert pm.has_permission("delete")
    assert pm.has_permission("export")
    assert pm.has_permission("config")
    assert pm.has_permission("manage_users")
    assert pm.is_admin()


def test_permission_engineer():
    pm = PermissionManager()
    pm.set_user_role("engineer")
    assert pm.has_permission("read")
    assert pm.has_permission("write")
    assert pm.has_permission("export")
    assert not pm.has_permission("manage_users")
    assert not pm.has_permission("config")
    assert not pm.is_admin()


def test_permission_user():
    pm = PermissionManager()
    pm.set_user_role("user")
    assert pm.has_permission("read")
    assert pm.has_permission("export")
    assert not pm.has_permission("write")
    assert not pm.has_permission("manage_users")
    assert not pm.is_admin()


def test_permission_viewer_read_only():
    pm = PermissionManager()
    pm.set_user_role("viewer")
    assert pm.has_permission("read")
    assert not pm.has_permission("export")
    assert not pm.has_permission("write")


def test_permission_invalid_action():
    pm = PermissionManager()
    pm.set_user_role("admin")
    assert not pm.has_permission("unknown_action_xyz")


def test_permission_invalid_role_defaults():
    pm = PermissionManager()
    pm.set_user_role("made_up_role")
    assert pm.user_role == "user"


# ─────────────────────── Session ───────────────────────

def test_session_login_sets_role():
    user = _make_user("admin1", "admin")
    Session.login(user)
    assert Session.is_admin()
    assert Session.has_permission("manage_users")
    assert Session.current_user().username == "admin1"


def test_session_logout_clears_state():
    user = _make_user("admin1", "admin")
    Session.login(user)
    Session.logout()
    assert Session.current_user() is None
    assert not Session.is_admin()
    assert not Session.has_permission("manage_users")


def test_session_engineer_permissions():
    user = _make_user("eng1", "engineer")
    Session.login(user)
    assert Session.has_permission("read")
    assert Session.has_permission("write")
    assert not Session.has_permission("manage_users")
    assert not Session.is_admin()


def test_session_viewer_permissions():
    user = _make_user("viewer1", "viewer")
    Session.login(user)
    assert Session.has_permission("read")
    assert not Session.has_permission("export")
    assert not Session.is_admin()


def test_session_switch_user():
    user1 = _make_user("admin1", "admin")
    Session.login(user1)
    assert Session.is_admin()

    user2 = _make_user("regular1", "user")
    Session.login(user2)
    assert not Session.is_admin()
    assert Session.current_user().username == "regular1"


def test_session_no_login_uses_default():
    Session.logout()
    pm = get_permission_manager()
    pm.set_user_role("user")
    assert Session.current_user() is None
    assert not Session.has_permission("write")


# ─────────────────────── Roles Tanımları ───────────────────────

def test_all_roles_defined():
    roles = PermissionManager.ROLES
    assert "admin" in roles
    assert "engineer" in roles
    assert "user" in roles
    assert "viewer" in roles


def test_admin_can_manage_users():
    assert "manage_users" in PermissionManager.ROLES["admin"]


def test_engineer_cannot_manage_users():
    assert "manage_users" not in PermissionManager.ROLES["engineer"]


def test_user_roles_read_and_export():
    perms = PermissionManager.ROLES["user"]
    assert "read" in perms
    assert "export" in perms
    assert "write" not in perms
    assert "delete" not in perms


# ─────────────────────── Engineering Mode ───────────────────────

def test_session_is_engineering_mode_no_user():
    Session.logout()
    assert Session.is_engineering_mode() is False


def test_session_is_engineering_mode_non_admin():
    user = _make_user("engineer1", "engineer")
    Session.login(user)
    assert Session.is_engineering_mode() is False


def test_session_is_engineering_mode_admin_no_flag():
    from kasp.config_manager import get_config_manager
    user = _make_user("admin1", "admin")
    Session.login(user)
    cfg = get_config_manager()
    original = cfg.get("updates.engineering_mode", False)
    try:
        cfg.set("updates.engineering_mode", False)
        assert Session.is_engineering_mode() is False
    finally:
        cfg.set("updates.engineering_mode", original)


def test_session_is_engineering_mode_admin_with_flag():
    from kasp.config_manager import get_config_manager
    user = _make_user("admin2", "admin")
    Session.login(user)
    cfg = get_config_manager()
    original = cfg.get("updates.engineering_mode", False)
    try:
        cfg.set("updates.engineering_mode", True)
        assert Session.is_engineering_mode() is True
    finally:
        cfg.set("updates.engineering_mode", original)


def test_admin_has_manage_users():
    assert "manage_users" in PermissionManager.ROLES["admin"]


def test_engineer_lacks_manage_users():
    assert "manage_users" not in PermissionManager.ROLES["engineer"]


def test_permission_defaults_match_plan():
    """Planlanan roller ve izinler kodla eşleşmeli."""
    roles = PermissionManager.ROLES
    assert "read" in roles["admin"] and "write" in roles["admin"] and "manage_users" in roles["admin"]
    assert "read" in roles["engineer"] and "write" in roles["engineer"]
    assert "manage_users" not in roles["engineer"]
    assert "read" in roles["viewer"] and "write" not in roles["viewer"]
