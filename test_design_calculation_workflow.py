from kasp.ui.design_calculation_workflow import (
    DesignCalculationController,
    format_time_estimate,
)


class FakeSignal:
    def __init__(self):
        self._callbacks = []

    def connect(self, callback):
        self._callbacks.append(callback)

    def emit(self, *args):
        for callback in list(self._callbacks):
            try:
                callback(*args)
            except TypeError:
                callback()


class DummyValueWidget:
    def __init__(self):
        self.value = None
        self.visible = None
        self.enabled = None
        self.text = None

    def setValue(self, value):
        self.value = value

    def setVisible(self, value):
        self.visible = value

    def setEnabled(self, value):
        self.enabled = value

    def setText(self, value):
        self.text = value


class FakeThread:
    def __init__(self):
        self.started = FakeSignal()
        self.finished = FakeSignal()
        self._running = False

    def isRunning(self):
        return self._running

    def start(self):
        self._running = True
        self.started.emit()

    def quit(self):
        self._running = False
        self.finished.emit()


class FakeWorker:
    def __init__(self, engine, inputs, turbines):
        self.engine = engine
        self.inputs = inputs
        self.turbines = turbines
        self.finished = FakeSignal()
        self.error = FakeSignal()
        self.progress = FakeSignal()
        self.progress_detailed = FakeSignal()
        self.time_remaining = FakeSignal()
        self.cancelled = FakeSignal()
        self.run_called = False
        self.cancel_requested = False
        self.thread = None

    def moveToThread(self, thread):
        self.thread = thread

    def run(self):
        self.run_called = True

    def request_cancel(self):
        self.cancel_requested = True


class DummyDb:
    def __init__(self):
        self.saved = []

    def get_all_turbines_full_data(self):
        return [{"name": "GT-1"}]

    def save_calculation_history(self, *args):
        self.saved.append(args)


class DummyMessageBox:
    warnings = []
    infos = []
    criticals = []

    @classmethod
    def warning(cls, *args):
        cls.warnings.append(args)

    @classmethod
    def information(cls, *args):
        cls.infos.append(args)

    @classmethod
    def critical(cls, *args):
        cls.criticals.append(args)


class DummyLogger:
    def __init__(self):
        self.messages = []

    def info(self, message, *args):
        self.messages.append(("info", message % args if args else message))

    def warning(self, message, *args):
        self.messages.append(("warning", message % args if args else message))

    def error(self, message, *args):
        self.messages.append(("error", message % args if args else message))

    def debug(self, message, *args):
        self.messages.append(("debug", message % args if args else message))


class DummyWindow:
    def __init__(self):
        self.worker_thread = None
        self.worker = None
        self.progress_bar = DummyValueWidget()
        self.progress_status_label = DummyValueWidget()
        self.progress_time_label = DummyValueWidget()
        self.calculate_btn = DummyValueWidget()
        self.stop_btn = DummyValueWidget()
        self.last_design_inputs = None
        self.last_design_results_raw = None
        self.last_selected_units = None
        self.updated_results = None
        self._validation_ok = True
        self._design_inputs = {
            "project_name": "Case A",
            "method": "Politropik",
            "notes": "base snapshot",
        }

    def _show_validation_popup(self):
        return self._validation_ok

    def _get_design_inputs(self):
        return dict(self._design_inputs)

    def _update_results_ui(self, results, selected_units):
        self.updated_results = (results, selected_units)


def test_format_time_estimate_supports_seconds_and_minutes():
    assert format_time_estimate(42.9) == "~42s remaining"
    assert format_time_estimate(125.0) == "~2m 5s remaining"


def test_design_calculation_controller_run_sets_up_worker_and_running_state():
    window = DummyWindow()
    controller = DesignCalculationController(
        window,
        engine=object(),
        db=DummyDb(),
        worker_factory=lambda: FakeWorker,
        thread_factory=lambda: FakeThread,
        message_box_factory=lambda: DummyMessageBox,
    )
    controller.logger = DummyLogger()

    controller.run()

    assert isinstance(window.worker_thread, FakeThread)
    assert isinstance(window.worker, FakeWorker)
    assert window.worker.run_called is True
    assert window.calculate_btn.enabled is False
    assert window.stop_btn.enabled is True
    assert window.progress_bar.visible is True
    assert controller.active_inputs["project_name"] == "Case A"


def test_design_calculation_controller_finished_uses_start_snapshot_for_history():
    window = DummyWindow()
    db = DummyDb()
    controller = DesignCalculationController(
        window,
        engine=object(),
        db=db,
        worker_factory=lambda: FakeWorker,
        thread_factory=lambda: FakeThread,
        message_box_factory=lambda: DummyMessageBox,
    )
    controller.logger = DummyLogger()

    controller.run()
    window._design_inputs["project_name"] = "Mutated Later"
    window.worker.finished.emit({"power_unit_kw": 1234.0}, [{"turbine_name": "GT-1"}])

    assert window.last_design_inputs["project_name"] == "Case A"
    assert window.updated_results[0]["power_unit_kw"] == 1234.0
    assert db.saved[0][0] == "Case A"
    assert window.worker is None
    assert window.worker_thread is None


def test_design_calculation_controller_stop_and_progress_updates_ui():
    window = DummyWindow()
    controller = DesignCalculationController(
        window,
        engine=object(),
        db=DummyDb(),
        worker_factory=lambda: FakeWorker,
        thread_factory=lambda: FakeThread,
        message_box_factory=lambda: DummyMessageBox,
    )
    controller.logger = DummyLogger()
    controller.run()

    controller.update_progress_detailed(55, "Calculating power")
    controller.update_time_estimate(75)
    controller.stop()

    assert window.progress_bar.value == 55
    assert window.progress_status_label.text == "Calculating power"
    assert window.progress_time_label.text == "~1m 15s remaining"
    assert window.worker.cancel_requested is True
    assert window.stop_btn.enabled is False
