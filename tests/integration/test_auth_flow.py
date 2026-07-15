import pytest
from kasp.core.user_manager import UserManager, validate_password_policy
from kasp.security import hash_password, Session


class TestAuthFlow:
    @pytest.fixture
    def mgr(self, temp_db):
        return UserManager(temp_db)

    def test_create_and_login(self, mgr):
        user, err = mgr.create_user("engineer1", "Engineer1!", "engineer", "Test")
        assert user is not None, f"Create failed: {err}"
        assert user.username == "engineer1"

        authed = mgr.authenticate("engineer1", "Engineer1!")
        assert authed is not None
        assert authed.role == "engineer"

    def test_wrong_password_fails(self, mgr):
        mgr.create_user("test1", "ValidPass1!", "user")
        assert mgr.authenticate("test1", "WrongPass1!") is None

    def test_session_lifecycle(self, mgr):
        mgr.create_user("admin2", "AdminPass1!", "admin")
        user = mgr.authenticate("admin2", "AdminPass1!")

        Session.login(user)
        assert Session.is_admin()
        assert Session.has_permission("manage_users")

        Session.logout()
        assert not Session.is_admin()
        assert not Session.has_permission("manage_users")

    def test_password_change(self, mgr):
        mgr.create_user("test2", "OldPass1!", "user")
        user = mgr.authenticate("test2", "OldPass1!")

        ok, err = mgr.change_password(user.id, "OldPass1!", "NewPass1!")
        assert ok, f"Password change failed: {err}"

        assert mgr.authenticate("test2", "OldPass1!") is None
        assert mgr.authenticate("test2", "NewPass1!") is not None

    def test_inactive_user_cannot_login(self, mgr):
        user, _ = mgr.create_user("temp1", "TempPass1!", "user")
        mgr.update_user(user.id, is_active=0)
        assert mgr.authenticate("temp1", "TempPass1!") is None

    def test_must_change_password_flag(self, mgr):
        user, _ = mgr.create_user("temp2", "TempPass1!", "user")
        mgr.update_user(user.id, must_change_password=1)
        authed = mgr.authenticate("temp2", "TempPass1!")
        assert authed is not None
        assert authed.must_change_password is True

    def test_list_all_users(self, mgr):
        mgr.create_user("u1", "Pass1111A!", "user")
        mgr.create_user("u2", "Pass2222B!", "engineer")
        users = mgr.list_users()
        assert len(users) >= 2
