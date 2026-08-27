"""Metrics the UI reports must come from real run output, never guesses."""

from analyzer.code_analyzer import CodeAnalyzer
from cov_tools.coverage_analyzer import CoverageResult, parse_pytest_counts
from web.formatting import (
    count_tests,
    download_name,
    friendly_error,
    function_rows,
    get_temperature,
    mode_label,
)


def test_parses_all_passed():
    assert parse_pytest_counts("......   [100%]\n6 passed in 0.05s") == {"passed": 6}


def test_parses_mixed_summary():
    counts = parse_pytest_counts("1 failed, 5 passed, 2 skipped in 0.12s")

    assert counts == {"failed": 1, "passed": 5, "skipped": 2}


def test_parses_collection_error():
    assert parse_pytest_counts("1 error in 0.15s") == {"error": 1}


def test_parses_empty_output():
    assert parse_pytest_counts("") == {}


def test_total_tests_sums_every_outcome():
    result = CoverageResult(
        ok=False,
        report="",
        pytest_output="",
        counts={"passed": 5, "failed": 1, "skipped": 2},
    )

    assert result.total_tests == 8


def test_module_overview_reports_classes_and_skipped_methods(tmp_path):
    module_path = tmp_path / "shop.py"
    module_path.write_text(
        "def total(x):\n"
        "    return x\n"
        "\n"
        "class Cart:\n"
        "    def add(self, item):\n"
        "        return item\n"
        "\n"
        "    def remove(self, item):\n"
        "        return item\n",
        encoding="utf-8",
    )

    overview = CodeAnalyzer().analyze_module(str(module_path))

    assert [fn["name"] for fn in overview["functions"]] == ["total"]
    assert overview["classes"] == ["Cart"]
    assert overview["skipped_methods"] == 2


def test_counts_only_top_level_test_functions():
    code = "\n".join(
        [
            "import pytest",
            "def test_one():",
            "    assert True",
            "def helper():",
            "    def test_nested():",
            "        pass",
            "def test_two():",
            "    assert True",
        ]
    )

    assert count_tests(code) == 2


def test_download_name_uses_uploaded_stem():
    assert download_name("order_utils.py") == "test_order_utils.py"


def test_download_name_falls_back_for_pasted_code():
    assert download_name(None) == "test_generated.py"
    assert download_name("pasted_input.py") == "test_generated.py"


def test_syntax_error_message_surfaces_the_line():
    exc = SyntaxError("expected ':'")
    exc.lineno = 14

    assert friendly_error(exc) == "Python syntax error on line 14: expected ':'"


def test_syntax_error_without_a_line_still_reads_cleanly():
    assert friendly_error(SyntaxError("invalid syntax")) == "Python syntax error: invalid syntax"


def test_unknown_failures_get_a_generic_message():
    assert "Test generation failed" in friendly_error(RuntimeError("boom"))


def test_mode_label_distinguishes_generation_modes():
    assert mode_label("deterministic") == "Deterministic"
    assert mode_label("ai") == "AI assisted"
    assert mode_label("fallback") == "Deterministic (AI fallback)"


def test_temperature_defaults_for_unknown_label():
    assert get_temperature("Low") == 0.1
    assert get_temperature("nonsense") == 0.2


def test_function_rows_flag_behaviour():
    rows = function_rows(
        [
            {
                "name": "greet",
                "args": ["name"],
                "has_print": True,
                "has_if": False,
                "recommended_scenarios": ["a", "b"],
            }
        ]
    )

    assert rows[0]["Function"] == "greet"
    assert rows[0]["Prints"] == "yes"
    assert rows[0]["Branches"] == ""
    assert rows[0]["Scenarios"] == 2
