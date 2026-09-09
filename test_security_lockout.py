"""Comprehensive test suite for KASP Security brute-force lockout and expiration."""

import json
import os
import sys
import time
import pytest
from PyQt5.QtWidgets import QApplication

from kasp.security import (
    LOCKOUT_LEVELS,
    FAILURE_RESET_WINDOW,
    check_lockout,
    get_lockout_remaining,
    record_attempt,
    _load_lockout_state,
    _save_lockout_state,
    _lockout_file,
)
from kasp.ui.login_dialog import LoginDialog


@pytest.fixture(autouse=True)
def clean_lockout_file():
    """Ensure clean lockout state before and after each test."""
    _save_lockout_state({"failures": 0, "last_failure": 0, "lockout_until": 0})
    yield
    _save_lockout_state({"failures": 0, "last_failure": 0, "lockout_until": 0})
    if os.path.exists(_lockout_file + ".tmp"):
        try:
            os.remove(_lockout_file + ".tmp")
        except OSError:
            pass


def test_lockout_initial_state():
    """Fresh state has no lockout and 3 attempts remaining."""
    locked, msg = check_lockout()
    assert not locked
    assert msg == ""
    assert get_lockout_remaining() == 3


def test_failed_attempts_progression():
    """First and second failures do not lock out, 3rd locks out for 1 minute."""
    locked1, msg1 = record_attempt(False)
    assert not locked1
    assert msg1 == ""
    assert get_lockout_remaining() == 2

    locked2, msg2 = record_attempt(False)
    assert not locked2
    assert msg2 == ""
    assert get_lockout_remaining() == 1

    locked3, msg3 = record_attempt(False)
    assert locked3
    assert "1 dakika kilitlendi" in msg3
    # Next tier is 5 attempts, so 5 - 3 = 2 remaining after unlock
    assert get_lockout_remaining() == 2


def test_lockout_check_during_lockout(monkeypatch):
    """While locked, check_lockout reports remaining time down to seconds."""
    base_time = 10000.0
    monkeypatch.setattr(time, "time", lambda: base_time)

    # Trigger 1 min lockout at t=10000.0 (expires at 10060.0)
    record_attempt(False)
    record_attempt(False)
    record_attempt(False)

    # At 30s into lockout (30s remaining)
    monkeypatch.setattr(time, "time", lambda: base_time + 30.0)
    locked, msg = check_lockout()
    assert locked
    assert "30 saniye kilitli" in msg

    # At 5s into lockout (55s remaining)
    monkeypatch.setattr(time, "time", lambda: base_time + 5.0)
    locked, msg = check_lockout()
    assert locked
    assert "55 saniye kilitli" in msg


def test_lockout_expiration_and_infinite_loop_prevention(monkeypatch):
    """When lockout expires, check_lockout MUST clear lockout and return False,
    and MUST NEVER re-lock in an infinite loop."""
    base_time = 20000.0
    monkeypatch.setattr(time, "time", lambda: base_time)

    record_attempt(False)
    record_attempt(False)
    record_attempt(False)

    state = _load_lockout_state()
    lockout_until = state["lockout_until"]
    assert lockout_until == base_time + 60.0

    # Fast forward past expiration (65 seconds later)
    expired_time = base_time + 65.0
    monkeypatch.setattr(time, "time", lambda: expired_time)

    # First check after expiration: MUST BE UNLOCKED
    locked, msg = check_lockout()
    assert not locked
    assert msg == ""

    # Verify state file has cleared lockout_until
    state_after = _load_lockout_state()
    assert state_after["lockout_until"] == 0

    # Second, third, and fourth checks: MUST STILL BE UNLOCKED (No infinite lockout!)
    for _ in range(5):
        locked_repeat, msg_repeat = check_lockout()
        assert not locked_repeat
        assert msg_repeat == ""


def test_subsequent_attempts_after_unlock(monkeypatch):
    """After unlock, 4th failure doesn't lock, 5th failure triggers 5 min lockout."""
    base_time = 30000.0
    monkeypatch.setattr(time, "time", lambda: base_time)

    # 3 failures -> locked until 30060.0
    record_attempt(False)
    record_attempt(False)
    record_attempt(False)

    # Unlock at t = 30061.0
    monkeypatch.setattr(time, "time", lambda: base_time + 61.0)
    assert not check_lockout()[0]

    # Attempt 4 fails: should NOT lock out (tier 2 is 5 attempts)
    locked4, msg4 = record_attempt(False)
    assert not locked4
    assert get_lockout_remaining() == 1

    # Attempt 5 fails: MUST lock out for 5 minutes!
    locked5, msg5 = record_attempt(False)
    assert locked5
    assert "5 dakika kilitlendi" in msg5

    state = _load_lockout_state()
    assert state["lockout_until"] == (base_time + 61.0) + (5 * 60.0)


def test_escalation_to_higher_tiers(monkeypatch):
    """8 failures -> 15 min; 10 failures -> 60 min."""
    cur_time = 40000.0

    def advance(sec):
        nonlocal cur_time
        cur_time += sec
        monkeypatch.setattr(time, "time", lambda: cur_time)

    advance(0)
    # Failures 1-3 -> 1 min
    record_attempt(False)
    record_attempt(False)
    locked3, _ = record_attempt(False)
    assert locked3

    # Fast forward 61s (unlock)
    advance(61)
    assert not check_lockout()[0]

    # Failure 4 -> no lock
    locked4, _ = record_attempt(False)
    assert not locked4

    # Failure 5 -> 5 min lock
    locked5, msg5 = record_attempt(False)
    assert locked5
    assert "5 dakika kilitlendi" in msg5

    # Fast forward 301s (unlock)
    advance(301)
    assert not check_lockout()[0]

    # Failure 6, 7 -> no lock
    assert not record_attempt(False)[0]
    assert not record_attempt(False)[0]

    # Failure 8 -> 15 min lock
    locked8, msg8 = record_attempt(False)
    assert locked8
    assert "15 dakika kilitlendi" in msg8

    # Fast forward 901s (unlock)
    advance(901)
    assert not check_lockout()[0]

    # Failure 9 -> no lock
    assert not record_attempt(False)[0]

    # Failure 10 -> 60 min lock
    locked10, msg10 = record_attempt(False)
    assert locked10
    assert "60 dakika kilitlendi" in msg10


def test_successful_login_clears_lockout_state():
    """Successful login resets failures and lockout_until."""
    record_attempt(False)
    record_attempt(False)
    record_attempt(True)

    state = _load_lockout_state()
    assert state["failures"] == 0
    assert state["lockout_until"] == 0
    assert state["last_failure"] == 0
    assert get_lockout_remaining() == 3


def test_inactivity_resets_failed_attempts(monkeypatch):
    """If inactive for > 15 minutes without active lock, failures reset to 0."""
    t0 = 50000.0
    monkeypatch.setattr(time, "time", lambda: t0)

    # 2 failures
    record_attempt(False)
    record_attempt(False)
    assert get_lockout_remaining() == 1

    # User returns 16 minutes later
    monkeypatch.setattr(time, "time", lambda: t0 + 960.0)
    # Next failure should be treated as 1st failure (failures reset to 0 + 1 = 1)
    locked, _ = record_attempt(False)
    assert not locked
    assert get_lockout_remaining() == 2


def test_login_dialog_ui_reenables_after_expiration(monkeypatch):
    """Full GUI test: LoginDialog disables inputs during lockout and
    RE-ENABLES them immediately once lockout time expires."""
    app = QApplication.instance() or QApplication([])

    class MockUserManager:
        def authenticate(self, u, p):
            return None

    cur_time = 60000.0
    monkeypatch.setattr(time, "time", lambda: cur_time)

    dialog = LoginDialog(MockUserManager())
    assert dialog._password_edit.isEnabled()
    assert dialog._login_btn.isEnabled()
    assert dialog._status_label.text() == ""

    # Enter wrong credentials 3 times
    dialog._username_edit.setText("admin")
    dialog._password_edit.setText("wrong_pass")
    dialog._try_login()
    assert dialog._password_edit.isEnabled()
    dialog._try_login()
    assert dialog._password_edit.isEnabled()
    dialog._try_login()

    # After 3rd wrong login: MUST BE DISABLED
    assert not dialog._password_edit.isEnabled()
    assert not dialog._login_btn.isEnabled()
    assert not dialog._username_edit.isEnabled()
    assert "⏳" in dialog._status_label.text()

    # Fast forward past 60s lockout
    cur_time += 65.0
    monkeypatch.setattr(time, "time", lambda: cur_time)

    # Simulate the timer tick
    dialog._on_lockout_tick()

    # Inputs MUST BE RE-ENABLED
    assert dialog._password_edit.isEnabled(), "Password field must be enabled after lockout expires"
    assert dialog._login_btn.isEnabled(), "Login button must be enabled after lockout expires"
    assert dialog._username_edit.isEnabled(), "Username field must be enabled after lockout expires"
    assert "Kilit açıldı" in dialog._status_label.text()
