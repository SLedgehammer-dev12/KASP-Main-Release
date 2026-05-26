collect_ignore = [
    "test_eos.py",
    "test_perf_vs_design.py",
    "test_power.py",
    "test_three_methods.py",
    "test_ui_defaults.py",
    "test_ui_responsive.py",
]

# Dynamically ignore PyQt5-dependent tests if PyQt5 is not installed
try:
    import PyQt5
except ImportError:
    pyqt5_dependent_tests = [
        "test_theme_contrast.py",
        "test_ui_controller_refactor.py",
        "test_ui_results_refactor.py",
        "test_update_menu.py",
        "test_updater.py",
        "test_v462_regressions.py",
    ]
    for test_file in pyqt5_dependent_tests:
        if test_file not in collect_ignore:
            collect_ignore.append(test_file)
