#!/usr/bin/env python3
"""
Superpowers TDD Runner & Quality Verification Gate for KASP.
Enforces the Red-Green-Refactor cycle and validates test outcomes before merge.
"""

import os
import subprocess
import sys
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[4]

def run_pytest(test_files: list[str], verbose: bool = True) -> int:
    cmd = [sys.executable, "-m", "pytest"]
    if verbose:
        cmd.extend(["-v", "--tb=short"])
    cmd.extend(test_files)
    
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"  # Safe for GUI test runs in headless mode
    
    print(f"🚀 [Superpowers TDD] Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=WORKSPACE_ROOT, env=env)
    return result.returncode

def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 superpowers_tdd.py run <test_file_or_pattern>...")
        print("  python3 superpowers_tdd.py quick-check")
        print("  python3 superpowers_tdd.py full-suite")
        sys.exit(1)

    action = sys.argv[1].lower()
    if action == "run":
        targets = sys.argv[2:]
        if not targets:
            print("Error: Specify at least one test file or pattern.")
            sys.exit(1)
        code = run_pytest(targets)
        if code == 0:
            print("\n✅ [Superpowers TDD] GREEN: All specified tests passed cleanly.")
        else:
            print(f"\n❌ [Superpowers TDD] RED: Tests failed with exit code {code}.")
        sys.exit(code)

    elif action == "quick-check":
        # Fast smoke test
        quick_tests = ["test_thermo_limits.py", "test_p2_security.py", "test_p4_reference.py"]
        code = run_pytest(quick_tests)
        sys.exit(code)

    elif action == "full-suite":
        code = run_pytest(["test_*.py"])
        sys.exit(code)

    else:
        print(f"Unknown command: {action}")
        sys.exit(1)

if __name__ == "__main__":
    main()
