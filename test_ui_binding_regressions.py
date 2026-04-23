from kasp.ui.design_input_binding import eos_method_from_ui_text, lhv_source_from_ui_text


def test_eos_method_from_ui_text_maps_supported_labels():
    assert eos_method_from_ui_text("CoolProp")[0] == "coolprop"
    assert eos_method_from_ui_text("Peng-Robinson (thermo)")[0] == "pr"
    assert eos_method_from_ui_text("SRK (thermo)")[0] == "srk"


def test_eos_method_from_ui_text_reports_missing_library_choice():
    eos_method, error = eos_method_from_ui_text("Kütüphane Yok")

    assert eos_method is None
    assert "EOS Hatası" in error


def test_lhv_source_from_ui_text_maps_combo_labels():
    assert lhv_source_from_ui_text("KASP Veritabanı") == "kasp"
    assert lhv_source_from_ui_text("Thermo Veritabanı") == "thermo"
