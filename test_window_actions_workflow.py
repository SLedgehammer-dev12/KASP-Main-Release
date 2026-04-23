from kasp.ui.window_actions_workflow import (
    WindowActionController,
    build_about_dialog_text,
    filter_logs_by_level,
)


class DummyTextArea:
    def __init__(self):
        self.entries = []

    def append(self, value):
        self.entries.append(value)

    def clear(self):
        self.entries.clear()


class DummyCombo:
    def __init__(self, value):
        self._value = value

    def currentText(self):
        return self._value

    def setCurrentText(self, value):
        self._value = value


class DummyLogger:
    def __init__(self):
        self.messages = []

    def info(self, message):
        self.messages.append(message)


class DummyEngine:
    def __init__(self):
        self.cache_cleared = False

    def clear_cache(self):
        self.cache_cleared = True


class DummyWindow:
    def __init__(self):
        self.log_text = DummyTextArea()
        self.log_level_combo = DummyCombo("INFO")
        self.all_logs = []
        self.logger = DummyLogger()
        self.last_selected_units = [{"turbine_name": "GT-1"}]
        self.turbine_table_updates = []

    def _populate_turbine_table(self, selected_units):
        self.turbine_table_updates.append(selected_units)


class DummyLibraryManager:
    def __init__(self, parent):
        self.parent = parent
        self.opened = False

    def exec_(self):
        self.opened = True


def test_filter_logs_by_level_and_about_text_helpers():
    logs = ["[INFO] one", "[ERROR] two", "[DEBUG] three"]

    assert filter_logs_by_level(logs, "TÜM LOGLAR") == logs
    assert filter_logs_by_level(logs, "ERROR") == ["[ERROR] two"]
    assert "KASP v4.6.2" in build_about_dialog_text()
    assert "ASME PTC-10" in build_about_dialog_text()


def test_window_actions_controller_handles_log_flow_and_library_refresh():
    window = DummyWindow()
    controller = WindowActionController(
        window,
        engine=DummyEngine(),
        library_manager_cls=DummyLibraryManager,
    )

    controller.append_log("[INFO] started")
    controller.append_log("[ERROR] failed")
    controller.filter_logs("ERROR")
    controller.clear_logs()
    controller.open_library_manager()

    assert window.log_text.entries == []
    assert window.all_logs == []
    assert "Sistem logları temizlendi." in window.logger.messages
    assert window.turbine_table_updates == [[{"turbine_name": "GT-1"}]]
