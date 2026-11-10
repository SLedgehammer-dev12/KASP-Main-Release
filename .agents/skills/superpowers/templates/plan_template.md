# [Superpowers] Execution Plan: <Feature / Bugfix Name>

## 1. Problem Statement & Context
- **Description**: Concise summary of what needs to be solved or built.
- **Root Cause (if bug)**: Identified through Phase 1-3 debugging.
- **Affected Components (via Graphify)**:
  - Source files: `kasp/...`
  - Downstream consumers: `kasp/...`
  - Linked test suites: `test_...py`

---

## 2. Constraints & Quality Gates
- [ ] No regression in CoolProp / PR / SRK / AGA8 calculation accuracy.
- [ ] Any user-facing strings must use `kasp/i18n.py` (`tr()`).
- [ ] Database schema changes must be backwards-compatible in SQLite.
- [ ] UI contrast ratios must maintain WCAG AA readability.
- [ ] All linked tests must pass (`python3 .agents/skills/superpowers/scripts/superpowers_tdd.py run <tests>`).

---

## 3. Atomic Task Breakdown (TDD Loop)

### Task 1: Write Failing Test (RED)
- **Target File**: `test_<name>.py`
- **Action**: Add test case asserting expected new behavior or reproducing bug.
- **Verification**: Run test and confirm it fails as expected (`pytest test_<name>.py -k test_target`).

### Task 2: Implement Minimal Code Change (GREEN)
- **Target File**: `kasp/<module>.py`
- **Action**: Write the minimal code required to satisfy the test.
- **Verification**: Run test and confirm it turns green.

### Task 3: Refactor & Clean Up (REFACTOR)
- **Action**: Remove dead code, eliminate duplication, ensure type hints and docstrings.
- **Verification**: Run full suite of linked tests to ensure no regressions.

---

## 4. Verification & Review Sign-Off
- [ ] Red-Green-Refactor verified
- [ ] Graphify impact checked (no unhandled side-effects)
- [ ] QA test runner passes with 0 failures
