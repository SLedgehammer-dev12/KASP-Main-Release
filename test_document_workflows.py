import datetime

from kasp.ui.document_workflows import (
    build_results_export_payload,
    default_design_report_filename,
    default_performance_report_filename,
    default_results_export_filename,
)


def test_document_workflow_default_filenames_use_current_suffixes():
    assert default_design_report_filename("Ana Proje") == "Ana_Proje_Tasarim_Raporu.pdf"
    assert default_results_export_filename("Ana Proje") == "Ana_Proje_Sonuclar.json"
    assert default_performance_report_filename("GT 01") == "GT_01_Performans_Raporu.pdf"


def test_document_workflow_default_filenames_use_fallback_for_empty_names():
    assert default_design_report_filename("") == "Proje_Tasarim_Raporu.pdf"
    assert default_results_export_filename(None) == "Proje_Sonuclar.json"
    assert default_performance_report_filename("   ") == "Performans_Performans_Raporu.pdf"


def test_build_results_export_payload_uses_passed_timestamp():
    exported_at = datetime.datetime(2026, 4, 19, 10, 30, 0)

    payload = build_results_export_payload(
        {"project_name": "Demo"},
        {"power": 123},
        [{"model": "GT"}],
        exported_at=exported_at,
    )

    assert payload["inputs"] == {"project_name": "Demo"}
    assert payload["results"] == {"power": 123}
    assert payload["selected_units"] == [{"model": "GT"}]
    assert payload["date"] == exported_at.isoformat()
