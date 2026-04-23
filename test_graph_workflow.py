from kasp.ui.graph_workflow import (
    GraphWorkflowController,
    default_graph_filename,
    graph_key_from_label,
)


class DummyTextField:
    def __init__(self, value):
        self._value = value

    def text(self):
        return self._value


class DummyCombo:
    def __init__(self, value):
        self._value = value

    def currentText(self):
        return self._value


class FakeFigure:
    def __init__(self):
        self.saved = []

    def savefig(self, path, **kwargs):
        self.saved.append((path, kwargs))


class FakeCanvas:
    def __init__(self):
        self.fig = FakeFigure()


class FakeFileDialog:
    last_call = None

    @classmethod
    def getSaveFileName(cls, *args):
        cls.last_call = args
        return ("D:/tmp/export.png", "PNG Files (*.png)")


class FakeMessageBox:
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

    def error(self, message, *args):
        self.messages.append(("error", message % args if args else message))


class DummyWindow:
    def __init__(self):
        self.last_design_results_raw = {"status": "ok"}
        self.project_name_edit = DummyTextField("Ana Proje")
        self.graph_combo = DummyCombo("T-s Diyagramı")


class DummyGraphManager:
    def __init__(self):
        self.current_graphs = {"ts_diagram": FakeCanvas()}


def test_graph_workflow_helpers_map_labels_and_build_filenames():
    assert graph_key_from_label("T-s Diyagramı") == "ts_diagram"
    assert graph_key_from_label("Bilinmeyen") is None
    assert default_graph_filename("Ana Proje", "ts_diagram") == "Ana_Proje_ts_diagram.png"
    assert default_graph_filename("", None) == "Proje_graph.png"


def test_graph_workflow_controller_saves_current_canvas():
    window = DummyWindow()
    manager = DummyGraphManager()
    controller = GraphWorkflowController(window, graph_manager=manager)
    controller.logger = DummyLogger()
    controller._qt_widgets = staticmethod(lambda: (FakeFileDialog, FakeMessageBox))

    controller.save_current_graph()

    saved = manager.current_graphs["ts_diagram"].fig.saved
    assert saved[0][0] == "D:/tmp/export.png"
    assert saved[0][1]["dpi"] == 300
    assert saved[0][1]["bbox_inches"] == "tight"
    assert FakeFileDialog.last_call[2] == "Ana_Proje_ts_diagram.png"
    assert FakeMessageBox.infos
