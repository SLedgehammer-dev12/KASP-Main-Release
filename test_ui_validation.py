import os
import sys

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

QtWidgets = pytest.importorskip("PyQt5.QtWidgets")
QApplication = QtWidgets.QApplication


@pytest.fixture(scope="module")
def app():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


def test_validation_manager_marks_empty_required_field_invalid_while_widget_stays_neutral(app):
    from kasp.ui.validators import ValidationManager, ValidatedLineEdit, validate_pressure

    manager = ValidationManager()
    edit = ValidatedLineEdit(validation_func=validate_pressure)
    edit.set_validation_context({"unit": "bar(a)"})

    manager.register_input("inlet_pressure", edit)

    assert manager.all_inputs_valid() is False
    assert manager.get_invalid_fields() == [("inlet_pressure", "Pressure is required")]
    assert edit.toolTip() == ""
