import os
import sys
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("MPLBACKEND", "Agg")
os.environ.setdefault("KASP_TEST_MODE", "1")

# pytest markalari - custom test categories
def pytest_configure(config):
    config.addinivalue_line("markers", "slow: tests that take >10s (integration, CoolProp)")
    config.addinivalue_line("markers", "reference: textbook/NIST independent verification")
    config.addinivalue_line("markers", "gui: tests requiring PyQt5 display")
    config.addinivalue_line("markers", "integration: tests requiring external deps (neqsim, dwsim)")

# Bu dosyalar normal pytest koleksiyonundan haric tutulur.
# Gerekce: bunlar tek seferlik dogrulama/benchmark betikleri veya ortama bagimli
# entegrasyon testleridir (CoolProp/REFPROP kurulumu, interaktif UI gerektirirler).
# CI kapsamini genisletmek icin asagidaki listenin periyodik olarak gozden gecirilmesi onerilir.
collect_ignore = [
    "test_eos.py",
    "test_perf_vs_design.py",
    "test_power.py",
    "test_three_methods.py",
    "test_ui_defaults.py",
]

# Dynamically ignore PyQt5-dependent tests if PyQt5 is not installed
try:
    import PyQt5
    from PyQt5.QtWidgets import QApplication

    @pytest.fixture(scope="session")
    def qapp():
        qt_app = QApplication.instance()
        if qt_app is None:
            qt_app = QApplication(sys.argv)
        return qt_app

    @pytest.fixture(scope="module")
    def app(qapp):
        return qapp

except ImportError:
    pyqt5_dependent_tests = [
        "test_left_panel_ergonomics.py",
        "test_password_recovery.py",
        "test_theme_contrast.py",
        "test_ui_controller_refactor.py",
        "test_ui_responsive.py",
        "test_ui_results_refactor.py",
        "test_update_menu.py",
        "test_updater.py",
        "test_v462_regressions.py",
    ]
    for test_file in pyqt5_dependent_tests:
        if test_file not in collect_ignore:
            collect_ignore.append(test_file)


_session_exitstatus = 0


def pytest_sessionfinish(session, exitstatus):
    global _session_exitstatus
    _session_exitstatus = exitstatus


def pytest_unconfigure(config):
    """Bypass C++ library destructor segfaults (CoolProp/ccp/PyQt5) during Python exit in CI."""
    if os.environ.get("CI") or os.environ.get("KASP_TEST_MODE"):
        try:
            sys.stdout.flush()
            sys.stderr.flush()
        except Exception:
            pass
        os._exit(int(_session_exitstatus))


