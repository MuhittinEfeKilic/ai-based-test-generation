"""Pure presentation helpers, kept out of app.py so they can be unit tested.

Importing app.py executes the Streamlit page, so anything worth asserting on
lives here instead.
"""

from pathlib import Path

TEMPERATURES = {"Low": 0.1, "Medium": 0.4, "High": 0.8}


def get_temperature(label: str) -> float:
    return TEMPERATURES.get(label, 0.2)


def count_tests(code: str) -> int:
    """Number of test functions in generated source."""
    return sum(1 for line in code.splitlines() if line.startswith("def test_"))


def download_name(source_name: str | None) -> str:
    """test_<source stem>.py when the source file is known, else a generic name."""
    if not source_name:
        return "test_generated.py"
    stem = Path(source_name).stem
    if not stem or stem == "pasted_input":
        return "test_generated.py"
    return f"test_{stem}.py"


def friendly_error(exc: Exception) -> str:
    """One-line message for the UI; the traceback stays in the log."""
    if isinstance(exc, SyntaxError):
        return "The submitted code is not valid Python. Fix the syntax error and try again."
    return "Test generation failed. Please verify that the submitted code is valid Python."


def mode_label(generation_source: str, provider_label: str) -> str:
    return {
        "rule-based": "Rule-based",
        "ai": f"AI ({provider_label})",
        "fallback": "Rule-based (AI fallback)",
    }.get(generation_source, generation_source)


def function_rows(functions: list[dict]) -> list[dict]:
    """One table row per planned function, for the Analysis tab."""
    return [
        {
            "Function": fn["name"],
            "Args": ", ".join(fn["args"]) or "-",
            "Async": "yes" if fn.get("is_async") else "",
            "Branches": "yes" if fn.get("has_if") else "",
            "Loops": "yes" if fn.get("has_for") or fn.get("has_while") else "",
            "Prints": "yes" if fn.get("has_print") else "",
            "Raises": "yes" if fn.get("raises_value_error") else "",
            "Scenarios": len(fn.get("recommended_scenarios", [])),
        }
        for fn in functions
    ]
