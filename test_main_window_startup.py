from kasp.ui.main_window_startup import (
    build_populate_ui_error_message,
    get_changelog_setting_key,
    get_ui_initialization_method_names,
    get_window_setup_config,
)


def test_window_setup_config_and_changelog_key_remain_stable():
    config = get_window_setup_config()

    assert config["minimum_size"] == (900, 550)
    assert config["default_geometry"] == (50, 50, 1700, 950)
    assert config["title"] == "KASP v4.6.2 - Termodinamik Analiz"
    assert get_changelog_setting_key() == "ui.skip_changelog_v46"


def test_ui_initialization_sequence_preserves_expected_order():
    assert get_ui_initialization_method_names() == (
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


def test_build_populate_ui_error_message_is_user_facing():
    assert (
        build_populate_ui_error_message("json bozuk")
        == "Yüklenen proje verileri arayüze yerleştirilirken hata oluştu: json bozuk"
    )
