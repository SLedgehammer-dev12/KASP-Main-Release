"""
KASP Test Configuration (v2.1)

Root-level conftest for legacy tests. New tests live under tests/.
"""

collect_ignore = [
    "test_ui_defaults.py",    # PyQt5 headless CI uyumsuz
    "test_ui_responsive.py",  # Ekran boyutu bagimli
    "test_theme_contrast.py", # QApplication gerektirir (CI'da headless)
]

# Previously disabled tests — now active:
# test_eos.py, test_power.py, test_three_methods.py, test_perf_vs_design.py

try:
    import PyQt5
except ImportError:
    pyqt5_tests = [
        "test_ui_controller_refactor.py",
        "test_ui_results_refactor.py",
        "test_update_menu.py",
        "test_updater.py",
        "test_v462_regressions.py",
    ]
    for t in pyqt5_tests:
        if t not in collect_ignore:
            collect_ignore.append(t)
