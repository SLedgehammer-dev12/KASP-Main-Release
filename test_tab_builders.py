from kasp.ui.design_results_tab_builders import (
    get_basic_result_definitions,
    get_design_result_tab_titles,
    get_graph_option_labels,
    get_turbine_table_headers,
)
from kasp.ui.tab_builders import (
    get_log_level_options,
    get_performance_flow_units,
    get_performance_lhv_source_items,
)


def test_get_log_level_options_returns_expected_filter_order():
    assert get_log_level_options() == ["TÜM LOGLAR", "DEBUG", "ITERATION", "INFO", "WARNING", "ERROR"]


def test_get_performance_flow_units_preserves_supported_units():
    assert get_performance_flow_units() == ["Sm³/h", "Nm³/h", "kg/h", "kg/s"]


def test_get_performance_lhv_source_items_reflects_thermo_availability():
    assert get_performance_lhv_source_items(True)[1] == "Thermo Veritabanı (Gelişmiş)"
    assert get_performance_lhv_source_items(False)[1] == "Thermo Veritabanı (Kütüphane Yok)"


def test_design_result_tab_helpers_define_expected_titles_and_graph_options():
    assert get_design_result_tab_titles() == [
        "📈 Temel Sonuçlar",
        "🚀 Türbin Seçimi",
        "📊 Detaylı Analiz",
        "📉 Grafikler",
    ]
    assert get_graph_option_labels() == [
        "T-s Diyagramı",
        "P-v Diyagramı",
        "Güç Dağılımı",
        "Türbin Performansı",
        "Yakınsama Grafiği",
    ]
    assert get_turbine_table_headers()[0] == "Sıra"


def test_basic_result_definitions_keep_expected_keys_and_units():
    definitions = get_basic_result_definitions()

    assert definitions[0][1] == "t_out"
    assert definitions[0][2] == "°C"
    assert definitions[-1][1] == "fuel_total_kgh"
    assert "hp" in definitions[4][3]
