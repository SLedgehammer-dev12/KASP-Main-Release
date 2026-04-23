import pytest

from kasp.ui.main_window_signal_wiring import coerce_slider_text_value, format_slider_text


def test_coerce_slider_text_value_clamps_and_falls_back():
    assert coerce_slider_text_value("92.4", 500, 950) == pytest.approx(92.4)
    assert coerce_slider_text_value("120", 500, 950) == pytest.approx(95.0)
    assert coerce_slider_text_value("bad", 500, 950) == pytest.approx(50.0)


def test_format_slider_text_uses_single_decimal_output():
    assert format_slider_text(873) == "87.3"
