# KASP Agentic Rules: Graphify & Superpowers

All agents working on the KASP codebase in Antigravity and OpenCode must follow these principles:

## 1. Impact Mapping via Graphify
- Before modifying or refactoring any core module (`kasp/core/`, `kasp/data/`, `kasp/ui/`), run Graphify impact analysis:
  ```bash
  python3 .agents/skills/graphify/scripts/graphify.py impact <filename_or_symbol>
  ```
- Review the linked test suites identified by Graphify. These test suites constitute the verification contract for your change.

## 2. Engineering Discipline via Superpowers
- **Plan First**: Never write production code without identifying edge cases and defining constraints.
- **Strict TDD**:
  1. Write failing test in `test_*.py` (Red).
  2. Implement minimal targeted solution in `kasp/` (Green).
  3. Refactor cleanly.
- **4-Phase Debugging**: When diagnosing a failure, systematically Replicate -> Isolate -> Hypothesize & Validate -> Fix.
- **Verification Gate**: Before declaring work complete, execute all linked tests:
  ```bash
  python3 .agents/skills/superpowers/scripts/superpowers_tdd.py run <test_files>
  ```
