"""Turn inferred argument values into named, asserted test scenarios.

Two stages:

1. Build candidate scenarios from AST evidence (pure, deterministic).
2. Probe each one by actually calling the function, so the emitted assertion
   states the value the function really produces rather than `is not None`.

The probe is what makes the assertions meaningful, and it is also the honest
part of the design: a scenario only claims to raise if it really raised, and an
expected value is only emitted when the result is a plain literal that round
trips through `repr`.
"""

from __future__ import annotations

import ast
import asyncio
import io
import math
import threading
from contextlib import redirect_stdout
from dataclasses import dataclass, field
from typing import Any

from test_generator.value_inference import (
    ParamEvidence,
    baseline_value,
    branch_values,
    guard_trigger_values,
)

#: Abandon a probe that runs longer than this; the target is user code.
PROBE_TIMEOUT_SEC = 2.0

#: Beyond this a float repr is dominated by binary rounding noise, so the
#: generated assertion uses pytest.approx instead of exact equality.
MAX_EXACT_FLOAT_DIGITS = 6

#: Keep the suite readable rather than exhaustive.
MAX_SCENARIOS_PER_FUNCTION = 8

_SENTINEL = object()


@dataclass
class ProbeResult:
    returned: bool = False
    value: Any = None
    exception: str | None = None
    stdout: str = ""
    failed: bool = False  # timed out, or could not be called at all


@dataclass
class Scenario:
    """One generated test: a call, a name, and what we expect back."""

    args: list
    label: str
    kind: str = "branch"  # default | branch | raise
    varied_param: str | None = None
    varied_value: Any = _SENTINEL
    probe: ProbeResult = field(default_factory=ProbeResult)

    @property
    def arg_key(self) -> tuple:
        return tuple(repr(a) for a in self.args)


# --------------------------------------------------------------------------
# Naming
# --------------------------------------------------------------------------

def slug(value: Any) -> str:
    """A deterministic, identifier-safe fragment describing a value."""
    if value is None:
        return "none"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        cleaned = "".join(ch if ch.isalnum() else "_" for ch in value).strip("_").lower()
        return cleaned or "empty"
    if isinstance(value, (int, float)):
        text = repr(value).replace("-", "neg_").replace(".", "_")
        return text.rstrip("_")
    if isinstance(value, (list, tuple)):
        return "empty" if not value else "list"
    if isinstance(value, dict):
        return "empty" if not value else "mapping"
    return "value"


def exception_slug(name: str) -> str:
    """ValueError -> value_error."""
    out = []
    for index, ch in enumerate(name):
        if ch.isupper() and index:
            out.append("_")
        out.append(ch.lower())
    return "".join(out)


def _sanitize(name: str) -> str:
    return "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in name)


def name_scenarios(function_name: str, scenarios: list[Scenario]) -> list[str]:
    """Descriptive, unique, deterministic test names.

    A string branch is named after the literal alone when that reads
    unambiguously; anything else keeps the parameter name for context.
    """
    base = _sanitize(function_name)

    short_labels: dict[int, str] = {}
    for index, scenario in enumerate(scenarios):
        if scenario.kind == "default":
            short_labels[index] = "default_case"
        elif isinstance(scenario.varied_value, str) and scenario.varied_value:
            short_labels[index] = slug(scenario.varied_value)
        elif scenario.varied_param is not None:
            short_labels[index] = f"{scenario.varied_param}_{slug(scenario.varied_value)}"
        else:
            short_labels[index] = scenario.label

    counts: dict[str, int] = {}
    for label in short_labels.values():
        counts[label] = counts.get(label, 0) + 1

    names: list[str] = []
    used: set[str] = set()
    for index, scenario in enumerate(scenarios):
        label = short_labels[index]
        # Ambiguous short label -> fall back to the qualified one.
        if counts[label] > 1 and scenario.varied_param:
            label = f"{scenario.varied_param}_{slug(scenario.varied_value)}"

        if scenario.kind == "raise" and scenario.probe.exception:
            label = f"{label}_raises_{exception_slug(scenario.probe.exception)}"

        candidate = _sanitize(f"test_{base}_{label}")
        suffix = 2
        while candidate in used:
            candidate = _sanitize(f"test_{base}_{label}_{suffix}")
            suffix += 1
        used.add(candidate)
        names.append(candidate)

    return names


# --------------------------------------------------------------------------
# Probing
# --------------------------------------------------------------------------

def probe_call(fn, args: list, is_async: bool = False) -> ProbeResult:
    """Call `fn(*args)` and record what happened.

    Runs on a worker thread so a runaway loop in the analyzed code cannot hang
    the generator; the abandoned thread is a daemon and the scenario degrades
    to a weaker assertion.
    """
    result = ProbeResult()
    buffer = io.StringIO()

    def run() -> None:
        try:
            with redirect_stdout(buffer):
                value = asyncio.run(fn(*args)) if is_async else fn(*args)
            result.returned = True
            result.value = value
        except Exception as exc:  # the analyzed code's own error paths
            result.exception = type(exc).__name__
        except BaseException:
            result.failed = True

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    worker.join(PROBE_TIMEOUT_SEC)

    if worker.is_alive():
        return ProbeResult(failed=True)

    try:
        result.stdout = buffer.getvalue()
    except Exception:
        result.stdout = ""
    return result


def literal_expression(value: Any) -> str | None:
    """`repr(value)` when it is a plain literal that round trips, else None.

    This is the gate on emitting `assert result == ...`: anything whose repr is
    not a faithful literal (objects, NaN, recursive structures) falls back to a
    weaker assertion instead of a wrong one.
    """
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    try:
        text = repr(value)
        if len(text) > 200:
            return None
        restored = ast.literal_eval(text)
    except Exception:
        return None
    if type(restored) is not type(value):
        return None
    try:
        if restored != value:
            return None
    except Exception:
        return None
    return text


def needs_approx(value: Any) -> bool:
    """True for floats whose decimal expansion is binary-rounding noise."""
    if not isinstance(value, float) or isinstance(value, bool):
        return False
    text = repr(value)
    if "e" in text or "E" in text:
        return True
    _, _, fraction = text.partition(".")
    return len(fraction) > MAX_EXACT_FLOAT_DIGITS


# --------------------------------------------------------------------------
# Scenario construction
# --------------------------------------------------------------------------

def build_scenarios(
    params: list[str],
    evidence: dict[str, ParamEvidence],
    fallbacks: dict[str, Any],
    defaults: dict[str, Any],
    numeric_ok: dict[str, bool] | None = None,
    prefer_float: dict[str, bool] | None = None,
) -> list[Scenario]:
    """Candidate scenarios, before probing.

    One baseline plus one scenario per interesting value per parameter, each
    varying a single parameter so a failure points at one thing.
    """
    baseline = []
    for name in params:
        if name in defaults:
            baseline.append(defaults[name])
        else:
            baseline.append(
                baseline_value(
                    evidence[name],
                    fallbacks.get(name),
                    numeric_ok=(numeric_ok or {}).get(name, True),
                    prefer_float=(prefer_float or {}).get(name, False),
                )
            )

    scenarios = [Scenario(args=list(baseline), label="default_case", kind="default")]
    seen = {scenarios[0].arg_key}

    def add(index: int, value: Any, kind: str) -> None:
        args = list(baseline)
        args[index] = value
        scenario = Scenario(
            args=args,
            label=f"{params[index]}_{slug(value)}",
            kind=kind,
            varied_param=params[index],
            varied_value=value,
        )
        if scenario.arg_key in seen:
            return
        seen.add(scenario.arg_key)
        scenarios.append(scenario)

    for index, name in enumerate(params):
        for value in branch_values(evidence[name]):
            add(index, value, "branch")

    for index, name in enumerate(params):
        for value in guard_trigger_values(evidence[name]):
            add(index, value, "raise")

    return scenarios


def select_scenarios(
    scenarios: list[Scenario],
    expected_exceptions: set[str] | None = None,
) -> list[Scenario]:
    """Keep what the probe showed to be meaningful, drop the rest.

    `expected_exceptions` are the types the function raises explicitly. A call
    that raises one of them is a genuine error-path test even if it started out
    as a branch scenario; a call that raises anything else was simply a bad
    input choice and is discarded rather than enshrined as a test.
    """
    expected = expected_exceptions or set()
    usable = [s for s in scenarios if not s.probe.failed]
    if not usable:
        return []

    kept: list[Scenario] = []
    seen_outcomes: list = []

    for scenario in usable:
        raised = scenario.probe.exception
        if raised:
            # Keep it as an error-path test only when the function is known to
            # raise that type; otherwise the input was simply wrong.
            if raised in expected or (not expected and scenario.kind == "raise"):
                scenario.kind = "raise"
                kept.append(scenario)
            continue

        # An explicit equality/None/bool branch is kept on principle: it was
        # aimed at a named branch, even if the observed result coincides.
        is_equality_branch = isinstance(scenario.varied_value, (str, bool)) or (
            scenario.varied_value is None
        )
        outcome = _outcome(scenario)
        if not is_equality_branch and scenario.probe.returned:
            if any(_same_outcome(outcome, other) for other in seen_outcomes):
                continue

        seen_outcomes.append(outcome)
        kept.append(scenario)

    return kept[:MAX_SCENARIOS_PER_FUNCTION]


def _outcome(scenario: Scenario):
    """What a scenario demonstrated: its return value and its output."""
    return (scenario.probe.returned, scenario.probe.value, scenario.probe.stdout)


def _same_outcome(left, right) -> bool:
    if not (left[0] and right[0]):
        return False
    return _equal(left[1], right[1]) and left[2] == right[2]


def _equal(left: Any, right: Any) -> bool:
    try:
        return bool(left == right)
    except Exception:
        return False
