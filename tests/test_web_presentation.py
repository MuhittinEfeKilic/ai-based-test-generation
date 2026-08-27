"""Grading, workflow progression and the HTML fragments the panels render."""

import pytest

from cov_tools.coverage_analyzer import FileCoverage, parse_coverage_json
from web.formatting import (
    coverage_files_table_html,
    coverage_grade,
    coverage_panel_html,
    metric_cards_html,
    missing_key_message,
    project_relative,
    provider_status,
    steps_html,
    structure_table_html,
    workflow_stage,
)

FN = {
    "name": "calculate_discount",
    "args": ["price", "discount"],
    "has_if": True,
    "raises_value_error": True,
    "returns_count": 1,
    "recommended_scenarios": ["a", "b", "c"],
}


# ---- grading --------------------------------------------------------------

@pytest.mark.parametrize(
    "percent, label",
    [
        (100.0, "excellent"),
        (90.0, "excellent"),
        (89.9, "good"),
        (75.0, "good"),
        (74.9, "needs improvement"),
        (0.0, "needs improvement"),
    ],
)
def test_coverage_grade_thresholds(percent, label):
    assert coverage_grade(percent)[0] == label


def test_unknown_coverage_is_not_graded():
    assert coverage_grade(None) == ("unknown", "muted")


def test_coverage_panel_reports_real_statement_counts():
    html = coverage_panel_html(81.25, 32, 6)

    assert "81%" in html
    assert "26 of 32 statements covered" in html
    assert "6 missed" in html
    assert "width:81.2%" in html


def test_coverage_panel_without_totals_makes_no_claims():
    html = coverage_panel_html(None, None, None)

    assert "n/a" in html
    assert "statements covered" not in html


def test_coverage_bar_never_exceeds_the_track():
    assert "width:100.0%" in coverage_panel_html(140.0, 10, 0)


# ---- provider status ------------------------------------------------------

def test_deterministic_mode_reports_no_provider():
    assert provider_status(False, "openai", True) == ("Deterministic mode", "idle")


def test_missing_key_is_flagged_but_never_echoed():
    text, dot = provider_status(True, "openai", False)

    assert dot == "warn"
    assert "key missing" in text


def test_mock_provider_needs_no_credentials():
    assert provider_status(True, "mock", False)[1] == "ok"


def test_missing_key_message_names_the_variable_not_the_secret():
    message = missing_key_message("OpenAI", "OPENAI_API_KEY")

    assert "OPENAI_API_KEY" in message
    assert "Deterministic" in message


# ---- workflow progression -------------------------------------------------

def test_workflow_starts_at_source():
    completed, active = workflow_stage(False, False, False, False)

    assert completed == set()
    assert active == "source"


def test_workflow_waits_on_analyze_until_generation_is_fresh():
    completed, active = workflow_stage(True, False, False, False)

    assert completed == {"source"}
    assert active == "analyze"


def test_workflow_points_at_run_after_generation():
    completed, active = workflow_stage(True, True, False, False)

    assert completed == {"source", "analyze", "generate"}
    assert active == "run"


def test_workflow_completes_with_coverage():
    completed, active = workflow_stage(True, True, True, True)

    assert completed == {"source", "analyze", "generate", "run", "coverage"}
    assert active == "coverage"


def test_stale_generation_rewinds_the_indicator():
    """A changed source makes the generation stale, so Run must not look done."""
    completed, active = workflow_stage(True, False, True, True)

    assert "run" not in completed
    assert active == "analyze"


# ---- HTML safety and shape ------------------------------------------------

def test_structure_table_lists_detected_traits():
    html = structure_table_html([FN])

    assert "calculate_discount" in html
    assert "price, discount" in html
    assert 'class="tg-tag">branch</span>' in html
    assert 'class="tg-tag raises">raises</span>' in html


def test_structure_table_escapes_function_names():
    html = structure_table_html([{**FN, "name": "<script>alert(1)</script>"}])

    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_structure_table_has_an_empty_state():
    assert "No module-level functions" in structure_table_html([])


def test_metric_cards_escape_values():
    html = metric_cards_html([("Functions", "<b>3</b>", "accent")])

    assert "<b>" not in html
    assert "&lt;b&gt;3&lt;/b&gt;" in html


def test_steps_html_marks_active_and_done():
    html = steps_html({"source", "analyze"}, "generate")

    assert 'class="tg-step done"' in html
    assert 'class="tg-step active"' in html


def test_coverage_files_table_is_omitted_when_empty():
    assert coverage_files_table_html([]) == ""


def test_coverage_files_table_shows_only_basenames():
    html = coverage_files_table_html(
        [FileCoverage(path="data/sample_code/tmp_target_1.py", statements=13, missing=2, percent=84.6)]
    )

    assert "tmp_target_1.py" in html
    assert "data/sample_code" not in html
    assert "85%" in html


# ---- coverage json parsing -----------------------------------------------

def test_parse_coverage_json_extracts_totals_and_files():
    payload = """
    {"files": {"a.py": {"summary": {"num_statements": 10, "missing_lines": 2,
     "percent_covered": 80.0}}},
     "totals": {"num_statements": 10, "missing_lines": 2, "percent_covered": 80.0}}
    """

    parsed = parse_coverage_json(payload)

    assert parsed["percent"] == 80.0
    assert parsed["statements"] == 10
    assert parsed["missing"] == 2
    assert parsed["files"][0].path == "a.py"


def test_parse_coverage_json_survives_garbage():
    assert parse_coverage_json("not json") == {}
    assert parse_coverage_json("") == {}


# ---- paths shown in the UI ------------------------------------------------

def test_paths_are_shown_relative_to_the_project(tmp_path):
    root = tmp_path / "project"
    target = root / "data" / "coverage_html" / "index.html"
    target.parent.mkdir(parents=True)
    target.write_text("x", encoding="utf-8")

    assert project_relative(target, root) == "data/coverage_html/index.html"


def test_paths_outside_the_project_fall_back_to_the_bare_name(tmp_path):
    """Never leak an absolute path - and therefore never the OS user name."""
    outside = tmp_path / "elsewhere" / "report.html"
    outside.parent.mkdir(parents=True)
    outside.write_text("x", encoding="utf-8")

    rendered = project_relative(outside, tmp_path / "project")

    assert rendered == "report.html"
    assert "\\" not in rendered and "/" not in rendered


def test_coverage_table_shows_the_user_facing_source_name():
    """The scratch module name is an implementation detail, not a label."""
    html = coverage_files_table_html(
        [FileCoverage(path="data/sample_code/tmp_target_1_ab.py", statements=12, missing=0, percent=100.0)],
        {"tmp_target_1_ab.py": "pasted_input.py"},
    )

    assert "pasted_input.py" in html
    assert "tmp_target" not in html


def test_coverage_table_falls_back_to_the_real_name():
    html = coverage_files_table_html(
        [FileCoverage(path="a/b/other.py", statements=1, missing=0, percent=100.0)], {}
    )

    assert "other.py" in html
