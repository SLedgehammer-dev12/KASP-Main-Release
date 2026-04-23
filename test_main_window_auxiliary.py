from kasp.ui.main_window_auxiliary import (
    build_validation_warning_lines,
    build_validation_warning_message,
    calculate_center_position,
    get_validation_field_name_map,
    get_version_label_text,
    summarize_library_inventory,
)


def test_validation_field_name_map_contains_expected_core_labels():
    field_map = get_validation_field_name_map()

    assert field_map["inlet_pressure"] == "Giriş Basıncı"
    assert field_map["flow_rate"] == "Gaz Debisi"


def test_validation_warning_helpers_render_human_readable_message():
    invalid_fields = [
        ("inlet_pressure", "0 bar geçersiz"),
        ("custom_field", "zorunlu"),
    ]

    lines = build_validation_warning_lines(invalid_fields)
    message = build_validation_warning_message(invalid_fields)

    assert lines[0] == "  • Giriş Basıncı: 0 bar geçersiz"
    assert lines[1] == "  • Custom Field: zorunlu"
    assert "Geçersiz alanlar kırmızı kenarlık ile işaretlenmiştir." in message


def test_auxiliary_summary_and_center_helpers_stay_stable():
    assert get_version_label_text() == "KASP v4.6.2"
    assert summarize_library_inventory(3, 7) == "Kütüphanede 3 türbin ve 7 kompresör bulundu."
    assert calculate_center_position(1920, 1080, 800, 600) == (560, 240)
