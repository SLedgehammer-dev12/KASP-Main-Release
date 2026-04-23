"""Startup helpers for the KASP main window."""

from __future__ import annotations

from kasp.i18n import APP_VERSION, tr


def get_window_setup_config():
    return {
        "minimum_size": (900, 550),
        "default_geometry": (50, 50, 1700, 950),
        "title": tr(f"KASP v{APP_VERSION} - Termodinamik Analiz"),
    }


def get_ui_initialization_method_names():
    return (
        "_create_menu",
        "_create_tabs",
        "_setup_design_tab",
        "_setup_performance_tab",
        "_setup_log_tab",
        "_setup_status_bar",
        "_connect_signals",
        "_populate_unit_combos",
        "_setup_unit_tooltips",
        "_update_method_options",
        "_update_button_state",
    )


def get_changelog_setting_key():
    return "ui.skip_changelog_v46"


def build_populate_ui_error_message(error):
    return tr(f"Yüklenen proje verileri arayüze yerleştirilirken hata oluştu: {error}")


class MainWindowStartupController:
    def __init__(self, window):
        self.window = window

    def configure_window(self):
        from PyQt5.QtCore import Qt

        config = get_window_setup_config()
        self.window.setMinimumSize(*config["minimum_size"])
        self.window.setWindowTitle(config["title"])
        self.window.setWindowFlags(
            Qt.Window
            | Qt.WindowTitleHint
            | Qt.WindowCloseButtonHint
            | Qt.WindowMinimizeButtonHint
            | Qt.WindowMaximizeButtonHint
        )
        try:
            from kasp.ui.responsive import compute_initial_window_size

            width, height = compute_initial_window_size(1700, 950)
            self.window.setGeometry(50, 50, width, height)
        except Exception:
            self.window.setGeometry(*config["default_geometry"])

        self.window.center_on_screen()

    def initialize_ui(self):
        for method_name in get_ui_initialization_method_names():
            getattr(self.window, method_name)()

    def show_changelog_if_needed(self):
        try:
            from kasp.config_manager import get_config_manager

            config = get_config_manager()
            setting_key = get_changelog_setting_key()
            skip_v46 = config.get(setting_key, False)
            if not skip_v46:
                from kasp.ui.dialogs import ChangelogDialog

                dialog = ChangelogDialog(self.window)
                dialog.exec_()
                if dialog.do_not_show_again:
                    config.set(setting_key, True)
        except Exception as error:
            self.window.logger.warning(f"Changelog dialog error: {error}")

    def populate_ui_from_inputs(self, inputs):
        from PyQt5.QtWidgets import QMessageBox

        try:
            self.window.design_input_binder.apply(inputs)
            self.window.logger.info("Project data populated into the UI")
        except Exception as error:
            message = build_populate_ui_error_message(error)
            self.window.logger.error(message, exc_info=True)
            QMessageBox.critical(self.window, tr("Hata"), message)
