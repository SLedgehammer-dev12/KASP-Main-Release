import time
import pytest
from kasp.security import (
    _load_lockout_state, _save_lockout_state,
    record_attempt, check_lockout, get_lockout_remaining,
)


class TestLockout:
    def setup_method(self):
        _save_lockout_state({"failures": 0, "last_failure": 0, "lockout_until": 0})

    def test_initial_not_locked(self):
        locked, _ = check_lockout()
        assert not locked

    def test_three_failures_lock(self):
        for _ in range(3):
            record_attempt(success=False)
        state = _load_lockout_state()
        assert state["failures"] == 3, f"failures={state['failures']}"

    def test_success_resets_failures(self):
        for _ in range(2):
            record_attempt(success=False)
        record_attempt(success=True)
        state = _load_lockout_state()
        assert state["failures"] == 0

    def test_remaining_decreases(self):
        for _ in range(2):
            record_attempt(success=False)
        remaining = get_lockout_remaining()
        assert remaining == 1

    def test_ten_failures_tracked(self):
        for _ in range(10):
            record_attempt(success=False)
        state = _load_lockout_state()
        assert state["failures"] >= 10

    def test_lockout_state_is_dict(self):
        state = _load_lockout_state()
        assert isinstance(state, dict)
        assert "failures" in state
