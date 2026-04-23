from kasp.ui.main_window_structure_builders import get_main_menu_specs, get_main_tab_titles


def test_main_tab_titles_remain_in_expected_order():
    assert get_main_tab_titles() == [
        "📊 Tasarım / Simülasyon",
        "📈 Performans Değerlendirme",
        "📋 Sistem Logları",
    ]


def test_main_menu_specs_keep_expected_actions_and_shortcuts():
    specs = get_main_menu_specs()

    assert list(specs.keys()) == ["📁 Dosya", "🛠️ Araçlar", "❓ Yardım"]
    assert specs["📁 Dosya"][0] == ("🆕 Yeni Proje", "Ctrl+N", "new_project")
    assert specs["📁 Dosya"][-1] == ("🚪 Çıkış", "Ctrl+Q", "close")
    assert specs["🛠️ Araçlar"][1] == ("🧹 Önbelleği Temizle", None, "clear_engine_cache")
    assert specs["❓ Yardım"][0][2] == "show_examples"
