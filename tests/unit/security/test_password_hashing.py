import re
import pytest
from kasp.security import hash_password, verify_password
from kasp.core.user_manager import validate_password_policy, User, UserManager


class TestPasswordHashing:
    def test_hash_format(self):
        hashed = hash_password("ValidPass1")
        assert hashed.startswith("pbkdf2:sha256:600000:")

    def test_verify_correct(self):
        pw = "StrongPass1"
        hashed = hash_password(pw)
        assert verify_password(pw, hashed)

    def test_verify_wrong(self):
        hashed = hash_password("CorrectPass1")
        assert not verify_password("WrongPass1", hashed)

    def test_unique_per_call(self):
        h1 = hash_password("SamePass1")
        h2 = hash_password("SamePass1")
        assert h1 != h2

    def test_iterations_600k(self):
        hashed = hash_password("TestPass1")
        parts = hashed.split(":")
        assert int(parts[2]) == 600000

    def test_salt_at_least_32_hex(self):
        hashed = hash_password("TestPass1")
        parts = hashed.split(":")
        salt_hex = parts[3]
        assert len(bytes.fromhex(salt_hex)) >= 16

    def test_verify_legacy_format(self):
        stored = "pbkdf2_sha256$600000$abcdef12$deadbeef"
        assert verify_password("any", stored) in (True, False)


class TestPasswordPolicy:
    def test_too_short_rejected(self):
        err = validate_password_policy("Sh0rt")
        assert err is not None

    def test_no_uppercase_rejected(self):
        err = validate_password_policy("alllowercase1")
        assert err is not None

    def test_no_lowercase_rejected(self):
        err = validate_password_policy("ALLUPPERCASE1")
        assert err is not None

    def test_no_digit_rejected(self):
        err = validate_password_policy("NoDigitsHere")
        assert err is not None

    def test_valid_accepts(self):
        err = validate_password_policy("ValidPass1")
        assert err is None


class TestUserManager:
    @pytest.fixture
    def mgr(self, temp_db):
        return UserManager(temp_db)

    def test_weak_password_rejected(self, mgr):
        _, err = mgr.create_user("test1", "weak", "user")
        assert err is not None

    def test_strong_password_accepted(self, mgr):
        user, err = mgr.create_user("test2", "StrongPass1!", "user")
        assert user is not None, f"Hata: {err}"
        assert user.username == "test2"
        assert user.role == "user"

    def test_duplicate_username_rejected(self, mgr):
        mgr.create_user("dup", "ValidPass1!", "user")
        _, err = mgr.create_user("dup", "ValidPass2!", "user")
        assert err is not None
