from kasp.utils.reporting import ReportGenerator


def test_design_report_warning_lines_include_fallback_without_existing_warnings():
    lines = ReportGenerator._build_design_warning_lines(
        {
            "fallback_used": True,
            "fallback_state_count": 3,
            "fallback_stage_numbers": [1, 2],
        }
    )

    assert any("fallback" in line.lower() for line in lines)
    assert "Fallback durum sayisi: 3" in lines
    assert "Etkilenen kademeler: 1, 2" in lines


def test_design_report_warning_lines_do_not_duplicate_existing_fallback_warning():
    lines = ReportGenerator._build_design_warning_lines(
        {
            "warnings": ["EOS fallback kullanildi."],
            "fallback_used": True,
            "fallback_state_count": 1,
        }
    )

    fallback_warning_lines = [line for line in lines if "fallback" in line.lower()]
    assert fallback_warning_lines == ["EOS fallback kullanildi.", "Fallback durum sayisi: 1"]


def test_design_report_warning_lines_include_method_nonconvergence():
    lines = ReportGenerator._build_design_warning_lines(
        {
            "method_converged": False,
            "method_convergence": [
                {"stage": 1, "converged": False, "termination_reason": "max_iterations"}
            ],
        }
    )

    assert any("yakinsamadi" in line for line in lines)
    assert any("Kademeler: 1" in line for line in lines)


def test_design_warnings_html_escapes_warning_text():
    html = ReportGenerator._build_design_warnings_html(["A < B", None, "fallback kullanildi"])

    assert html.startswith("<b>Dikkat Edilmesi Gereken Noktalar:</b><br/>")
    assert "&bull; A &lt; B<br/>" in html
    assert "&bull; fallback kullanildi<br/>" in html
    assert "None" not in html


def test_design_warnings_html_returns_empty_for_no_lines():
    assert ReportGenerator._build_design_warnings_html([]) == ""


def test_percent_change_text_handles_normal_and_zero_inlet():
    assert ReportGenerator._percent_change_text(100, 110) == "+10.0"
    assert ReportGenerator._percent_change_text(0, 10) == "-"
    assert ReportGenerator._percent_change_text("bad", 10) == "-"


def test_build_detailed_thermo_data_uses_safe_percent_change():
    data = ReportGenerator._build_detailed_thermo_data(
        {
            "inlet_properties": {"Z": 1.0, "rho": 0.0, "k": 1.3, "Cp": 2200.0, "mu": 1e-5, "a": 330.0},
            "outlet_properties": {"Z": 1.1, "rho": 4.0, "k": 1.2, "Cp": 2420.0, "mu": 1.2e-5, "a": 360.0},
        }
    )

    assert data[1][-1] == "+10.0"
    assert data[2][-1] == "-"
    assert data[4][1] == "2.200"
    assert data[5][1] == "10.00"


class UnitObject:
    turbine_name = "Object Turbine"
    available_power_kw = 4200.0
    site_heat_rate = 9800.0
    efficiency_rating = "A"
    selection_score = 91.0
    recommendation_level = "Recommended"


def test_describe_report_unit_supports_alternate_dict_keys():
    details = ReportGenerator._describe_report_unit(
        {
            "turbine_name": "GT-1",
            "available_power_kw": 3000.0,
            "site_heat_rate": 10000.0,
            "efficiency_rating": "B",
            "selection_score": 87.5,
            "recommendation_level": "Good",
        }
    )

    assert details["name"] == "GT-1"
    assert details["available_power_kw"] == 3000.0
    assert details["selection_score"] == 87.5


def test_describe_report_unit_supports_object_units():
    details = ReportGenerator._describe_report_unit(UnitObject())

    assert details["name"] == "Object Turbine"
    assert details["site_heat_rate"] == 9800.0
    assert details["recommendation_level"] == "Recommended"
