"""Pure presentation helpers, kept out of the components so they can be tested.

Importing a Streamlit component executes page code, so anything worth asserting
on - label logic, grading thresholds, HTML fragments - lives here instead.
"""

from __future__ import annotations

from html import escape
from pathlib import Path

TEMPERATURES = {"Low": 0.1, "Medium": 0.4, "High": 0.8}

#: stage key -> label, in workflow order.
WORKFLOW_STEPS = [
    ("source", "Source"),
    ("analyze", "Analyze"),
    ("generate", "Generate"),
    ("run", "Run"),
    ("coverage", "Coverage"),
]


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
    """One-line message for the UI; the traceback stays in the debug expander."""
    if isinstance(exc, SyntaxError):
        line = getattr(exc, "lineno", None)
        detail = (exc.msg or "invalid syntax").strip()
        if line:
            return f"Python syntax error on line {line}: {detail}"
        return f"Python syntax error: {detail}"
    if isinstance(exc, FileNotFoundError):
        return "A file needed for this run is missing. Generate the tests again."
    if isinstance(exc, PermissionError):
        return "A file could not be written. Check permissions on the data/ and tests/ folders."
    return "Test generation failed. Please verify that the submitted code is valid Python."


def mode_label(generation_mode: str) -> str:
    return {
        "deterministic": "Deterministic",
        "ai": "AI assisted",
        "fallback": "Deterministic (AI fallback)",
    }.get(generation_mode, generation_mode)


def provider_status(use_ai: bool, provider: str, has_key: bool) -> tuple[str, str]:
    """Header pill text and dot class for the current provider configuration."""
    if not use_ai:
        return "Deterministic mode", "idle"
    if provider == "mock":
        return "Mock provider", "ok"
    if has_key:
        return f"{provider} ready", "ok"
    return f"{provider} key missing", "warn"


def missing_key_message(provider: str, env_var: str) -> str:
    """Actionable, secret-free guidance when a provider has no credentials."""
    return (
        f"No API key found for {provider}. Add {env_var} to .streamlit/secrets.toml "
        f"or enter it in the panel, or switch to Deterministic mode."
    )


def project_relative(path: Path | str, root: Path | str) -> str:
    """Render a path relative to the project root.

    Absolute paths in the UI are noise and leak the operating-system user name
    in screenshots and screen shares; the repo-relative form is what a reader
    actually needs.
    """
    path = Path(path)
    try:
        return Path(path).resolve().relative_to(Path(root).resolve()).as_posix()
    except (ValueError, OSError):
        return path.name


def coverage_grade(percent: float | None) -> tuple[str, str]:
    """(label, css tone) for a coverage percentage."""
    if percent is None:
        return "unknown", "muted"
    if percent >= 90:
        return "excellent", "success"
    if percent >= 75:
        return "good", "accent"
    return "needs improvement", "warning"


def workflow_stage(
    has_source: bool,
    fresh_generation: bool,
    has_execution: bool,
    has_coverage: bool,
) -> tuple[set[str], str]:
    """(completed steps, active step) for the workflow indicator.

    Pure so the progression can be asserted without a Streamlit session.
    """
    completed: set[str] = set()
    if has_source:
        completed.add("source")
    if fresh_generation:
        completed.update({"analyze", "generate"})
        if has_execution:
            completed.add("run")
            if has_coverage:
                completed.add("coverage")

    if not has_source:
        active = "source"
    elif not fresh_generation:
        active = "analyze"
    elif not has_execution:
        active = "run"
    else:
        active = "coverage"

    return completed, active


def function_rows(functions: list[dict]) -> list[dict]:
    """One row per planned function, for the detected-structure table."""
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


# --------------------------------------------------------------------------
# HTML fragments
# --------------------------------------------------------------------------

def metric_cards_html(items: list[tuple[str, object, str]]) -> str:
    """Compact metric grid. `items` is (label, value, tone)."""
    cards = "".join(
        f'<div class="tg-metric {escape(tone)}">'
        f'<div class="tg-metric-value">{escape(str(value))}</div>'
        f'<div class="tg-metric-label">{escape(label)}</div>'
        f"</div>"
        for label, value, tone in items
    )
    return f'<div class="tg-metrics">{cards}</div>'


def steps_html(completed: set[str], active: str | None) -> str:
    """Subtle Source -> Analyze -> Generate -> Run -> Coverage indicator."""
    parts = []
    for index, (key, label) in enumerate(WORKFLOW_STEPS):
        state = "active" if key == active else ("done" if key in completed else "")
        parts.append(
            f'<span class="tg-step {state}"><span class="tg-dot"></span>{escape(label)}</span>'
        )
        if index < len(WORKFLOW_STEPS) - 1:
            parts.append('<span class="tg-sep">/</span>')
    return f'<div class="tg-steps">{"".join(parts)}</div>'


def panel_title_html(title: str, note: str = "") -> str:
    note_html = f'<span class="tg-panel-note">{escape(note)}</span>' if note else ""
    return f'<div class="tg-panel-title"><h3>{escape(title)}</h3>{note_html}</div>'


def coverage_panel_html(
    percent: float | None,
    statements: int | None,
    missing: int | None,
) -> str:
    """The headline coverage figure with a plain progress bar."""
    label, tone = coverage_grade(percent)
    color = {
        "success": "var(--success)",
        "accent": "var(--accent)",
        "warning": "var(--warning)",
        "muted": "var(--text-faint)",
    }[tone]

    value = f"{percent:.0f}%" if percent is not None else "n/a"
    width = max(0.0, min(percent or 0.0, 100.0))

    if statements is not None and missing is not None:
        covered = statements - missing
        sub = f"{covered} of {statements} statements covered &middot; {missing} missed"
    else:
        sub = "Statement coverage"

    return (
        '<div class="tg-coverage">'
        '<div class="tg-coverage-head">'
        f'<span class="tg-coverage-value" style="color:{color}">{value}</span>'
        '<span class="tg-coverage-label">statement coverage</span>'
        f'<span class="tg-badge">{escape(label)}</span>'
        "</div>"
        f'<div class="tg-bar"><div class="tg-bar-fill" style="width:{width:.1f}%;background:{color}"></div></div>'
        f'<div class="tg-coverage-sub">{sub}</div>'
        "</div>"
    )


def structure_table_html(functions: list[dict]) -> str:
    """Detected code structure, without dumping raw AST at the user."""
    if not functions:
        return '<div class="tg-empty">No module-level functions detected.</div>'

    head = (
        "<tr><th>Function</th><th>Arguments</th><th>Returns</th>"
        "<th>Traits</th><th>Scenarios</th></tr>"
    )

    rows = []
    for fn in functions:
        args = ", ".join(fn["args"]) or "&ndash;"
        returns = fn.get("returns_count", 0)
        returns_text = "none" if not returns else f"{returns} path{'s' if returns > 1 else ''}"

        traits = []
        if fn.get("is_async"):
            traits.append('<span class="tg-tag async">async</span>')
        if fn.get("has_if"):
            traits.append('<span class="tg-tag">branch</span>')
        if fn.get("has_for") or fn.get("has_while"):
            traits.append('<span class="tg-tag">loop</span>')
        if fn.get("has_print"):
            traits.append('<span class="tg-tag">print</span>')
        if fn.get("raises_value_error"):
            traits.append('<span class="tg-tag raises">raises</span>')
        traits_html = "".join(traits) or "&ndash;"

        rows.append(
            f'<tr><td class="name">{escape(fn["name"])}</td>'
            f'<td class="args">{escape(args) if args != "&ndash;" else args}</td>' 
            f"<td>{returns_text}</td>"
            f"<td>{traits_html}</td>"
            f'<td>{len(fn.get("recommended_scenarios", []))}</td></tr>'
        )

    return (
        '<div class="tg-table-wrap"><table class="tg-table">'
        f"<thead>{head}</thead><tbody>{''.join(rows)}</tbody>"
        "</table></div>"
    )


def coverage_files_table_html(files: list, display_names: dict | None = None) -> str:
    """Per-file coverage.

    `display_names` maps the scratch module's filename back to the name the
    user supplied, so the table shows `pasted_input.py` rather than an internal
    `tmp_target_...` name.
    """
    if not files:
        return ""
    names = display_names or {}
    head = "<tr><th>File</th><th>Statements</th><th>Missed</th><th>Coverage</th></tr>"
    rows = "".join(
        f'<tr><td class="name">'
        f"{escape(names.get(Path(f.path).name, Path(f.path).name))}</td>"
        f"<td>{f.statements}</td><td>{f.missing}</td>"
        f"<td>{f.percent:.0f}%</td></tr>"
        for f in files
    )
    return (
        '<div class="tg-table-wrap"><table class="tg-table">'
        f"<thead>{head}</thead><tbody>{rows}</tbody></table></div>"
    )
