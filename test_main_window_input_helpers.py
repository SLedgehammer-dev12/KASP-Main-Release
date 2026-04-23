from kasp.ui.main_window_input_helpers import (
    build_composition_total_warning_message,
    build_input_value_error_message,
    get_unexpected_input_error_message,
    has_composition_total_warning,
)


def test_has_composition_total_warning_respects_tolerance():
    assert has_composition_total_warning(100.0) is False
    assert has_composition_total_warning(100.9) is False
    assert has_composition_total_warning(101.1) is True
    assert has_composition_total_warning(98.8) is True


def test_input_helper_messages_remain_stable():
    composition_message = build_composition_total_warning_message(98.345)
    value_error = build_input_value_error_message("akış eksik")

    assert "<b>%98.34</b>" in composition_message or "<b>%98.35</b>" in composition_message
    assert "motor otomatik olarak normalize edecektir".lower() in composition_message.lower()
    assert value_error == "Lütfen tüm zorunlu alanları kontrol edin:\nakış eksik"
    assert get_unexpected_input_error_message() == "Girdi toplama sırasında beklenmeyen bir hata oluştu."
