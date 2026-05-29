"""FAZ 6-7-8: Engineering Mode, Güvenlik ve Log Testleri."""
import pytest
from kasp.security import Session, PermissionManager, get_permission_manager
from kasp.core.user_manager import UserManager, User


@pytest.fixture(autouse=True)
def reset_session():
    Session.logout()
    yield
    Session.logout()


def _make_user(username="testuser", role="user"):
    return User(id=1, username=username, role=role, full_name="Test")


# ─────────────────────── Config: engineering_mode ───────────────────────

def test_config_engineering_mode_default():
    from kasp.config_manager import get_config_manager
    cfg = get_config_manager()
    val = cfg.get("updates.engineering_mode", None)
    assert val is not None
    assert val in (True, False)


def test_config_engineering_mode_set_get():
    from kasp.config_manager import get_config_manager
    cfg = get_config_manager()
    original = cfg.get("updates.engineering_mode", False)
    try:
        cfg.set("updates.engineering_mode", True)
        assert cfg.get("updates.engineering_mode", False) is True
        cfg.set("updates.engineering_mode", False)
        assert cfg.get("updates.engineering_mode", True) is False
    finally:
        cfg.set("updates.engineering_mode", original)


# ─────────────────────── Session: is_engineering_mode ───────────────────────

def test_engineering_mode_false_by_default():
    Session.logout()
    assert Session.is_engineering_mode() is False


def test_engineering_mode_admin_with_flag():
    from kasp.config_manager import get_config_manager
    user = _make_user("admin1", "admin")
    Session.login(user)
    cfg = get_config_manager()
    original = cfg.get("updates.engineering_mode", False)
    try:
        cfg.set("updates.engineering_mode", True)
        assert Session.is_engineering_mode() is True
    finally:
        cfg.set("updates.engineering_mode", original)


def test_engineering_mode_non_admin_always_false():
    from kasp.config_manager import get_config_manager
    user = _make_user("engineer1", "engineer")
    Session.login(user)
    cfg = get_config_manager()
    original = cfg.get("updates.engineering_mode", False)
    try:
        cfg.set("updates.engineering_mode", True)
        assert Session.is_engineering_mode() is False
    finally:
        cfg.set("updates.engineering_mode", original)


def test_engineering_mode_no_user_false():
    Session.logout()
    assert Session.is_engineering_mode() is False


# ─────────────────────── must_change_password ───────────────────────

def test_user_dataclass_has_must_change_password():
    user = User(id=1, username="test", role="user", must_change_password=True)
    assert user.must_change_password is True
    user2 = User(id=2, username="test2")
    assert user2.must_change_password is False


def test_admin_reset_sets_must_change_password():
    import os
    import tempfile
    from kasp.data.database import UnitDatabase
    from kasp.security import hash_password

    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db = UnitDatabase(db_name=path)
    try:
        db.create_default_admin(hash_password("adminpw"))
        mgr = UserManager(db)
        mgr.create_user("target", "original", role="user")
        users = mgr.list_users()
        target = next(u for u in users if u.username == "target")

        ok, err = mgr.admin_reset_password(target.id, "newpass123")
        assert ok
        assert err is None

        users = mgr.list_users()
        updated = next(u for u in users if u.username == "target")
        assert updated.must_change_password is True

        auth_user = mgr.authenticate("target", "newpass123")
        assert auth_user is not None
        assert auth_user.must_change_password is True
    finally:
        db.get_connection().close()
        os.unlink(path)


def test_create_user_default_must_change_false():
    import os
    import tempfile
    from kasp.data.database import UnitDatabase
    from kasp.security import hash_password
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db = UnitDatabase(db_name=path)
    try:
        db.create_default_admin(hash_password("adminpw"))
        mgr = UserManager(db)
        user, err = mgr.create_user("newguy", "pw1234", role="user")
        assert user is not None
        assert user.must_change_password is False
    finally:
        db.get_connection().close()
        os.unlink(path)


# ─────────────────────── Log Filtre: filter_logs_by_level ───────────────────────

LEVEL_MARKERS = ["DEBUG", "ITERATION", "INFO", "WARNING", "ERROR", "CRITICAL"]


def _filter_logs_by_level(logs, selected_level):
    """Log filtresi — PyQt5 import etmeden saf implementasyon."""
    if selected_level in {"TÜM LOGLAR", "ALL LOGS"}:
        return list(logs)
    level_idx = LEVEL_MARKERS.index(selected_level) if selected_level in LEVEL_MARKERS else -1
    if level_idx < 0:
        return [log for log in logs if selected_level in log]
    result = []
    for log in logs:
        for marker in LEVEL_MARKERS[level_idx:]:
            if marker in log:
                result.append(log)
                break
    return result


def test_filter_logs_all_shows_all():
    logs = ["DEBUG - test", "INFO - test", "WARNING - test", "ERROR - test"]
    result = _filter_logs_by_level(logs, "TÜM LOGLAR")
    assert len(result) == 4


def test_filter_logs_warning_shows_warning_and_above():
    logs = [
        "DEBUG - low", "ITERATION - step 1", "INFO - normal",
        "WARNING - check", "ERROR - fail", "CRITICAL - crash",
    ]
    result = _filter_logs_by_level(logs, "WARNING")
    assert "DEBUG - low" not in result
    assert "ITERATION - step 1" not in result
    assert "INFO - normal" not in result
    assert "WARNING - check" in result
    assert "ERROR - fail" in result
    assert "CRITICAL - crash" in result


def test_filter_logs_info_shows_info_and_above():
    logs = ["DEBUG - x", "ITERATION - y", "INFO - z", "WARNING - w"]
    result = _filter_logs_by_level(logs, "INFO")
    assert "DEBUG - x" not in result
    assert "ITERATION - y" not in result
    assert "INFO - z" in result
    assert "WARNING - w" in result


def test_filter_logs_debug_shows_all():
    logs = ["DEBUG - x", "INFO - y", "ERROR - z"]
    result = _filter_logs_by_level(logs, "DEBUG")
    assert len(result) == 3


def test_filter_logs_error_shows_error_only():
    logs = ["DEBUG - x", "INFO - y", "WARNING - w", "ERROR - e"]
    result = _filter_logs_by_level(logs, "ERROR")
    assert "DEBUG - x" not in result
    assert "INFO - y" not in result
    assert "WARNING - w" not in result
    assert "ERROR - e" in result


# ─────────────────────── Cache Performance Graph ───────────────────────

def test_graph_key_by_label_has_cache_performance():
    from kasp.ui.design_results_workflow import GRAPH_KEY_BY_LABEL
    assert "Cache Performansı" in GRAPH_KEY_BY_LABEL
    assert "Cache Performance" in GRAPH_KEY_BY_LABEL
    assert GRAPH_KEY_BY_LABEL["Cache Performansı"] == "cache_performance"
    assert GRAPH_KEY_BY_LABEL["Cache Performance"] == "cache_performance"


def test_graph_option_labels_include_cache():
    from kasp.ui.design_results_tab_builders import get_graph_option_labels
    labels = get_graph_option_labels()
    has_cache = "Cache Performansı" in labels or "Cache Performance" in labels
    assert has_cache
