"""The evidence layer: what the generator reads off a function's own source.

These are deliberately written against small representative fixtures rather
than the portfolio demo, so nothing here can be satisfied by special-casing one
function.
"""

import ast
import time

import pytest

from test_generator.scenarios import (
    exception_slug,
    literal_expression,
    needs_approx,
    probe_call,
    slug,
)
from test_generator.value_inference import (
    Comparison,
    baseline_value,
    branch_values,
    collect_evidence,
    guard_trigger_values,
    value_satisfying,
)


def evidence_for(source: str, params: list[str]):
    return collect_evidence(source, params)


# ---- evidence extraction --------------------------------------------------

def test_equality_literals_are_collected_in_source_order():
    source = (
        "def fee(status):\n"
        "    if status == 'gold':\n"
        "        return 0\n"
        "    elif status == 'silver':\n"
        "        return 5\n"
        "    return 10\n"
    )

    assert evidence_for(source, ["status"])["status"].equality_values == ["gold", "silver"]


def test_literals_are_found_when_the_parameter_is_on_the_right():
    source = "def fee(status):\n    if 'gold' == status:\n        return 0\n    return 1\n"

    assert evidence_for(source, ["status"])["status"].equality_values == ["gold"]


def test_comparison_direction_is_mirrored():
    """`0 >= price` must be recorded as `price <= 0`."""
    source = "def charge(price):\n    if 0 >= price:\n        raise ValueError('x')\n    return price\n"

    guards = evidence_for(source, ["price"])["price"].guard_comparisons

    assert [(c.op, c.const) for c in guards] == [("<=", 0)]


def test_only_comparisons_guarding_a_raise_count_as_guards():
    source = (
        "def grade(score):\n"
        "    if score >= 90:\n"
        "        return 'A'\n"
        "    return 'B'\n"
    )
    evidence = evidence_for(source, ["score"])["score"]

    assert evidence.guard_comparisons == []
    assert [(c.op, c.const) for c in evidence.comparisons] == [(">=", 90)]


def test_none_checks_are_detected():
    source = "def label(value):\n    if value is None:\n        return 'x'\n    return value\n"

    assert evidence_for(source, ["value"])["value"].none_checked


def test_truth_tested_parameters_are_detected():
    source = "def render(text, upper):\n    if upper:\n        return text\n    return text\n"
    evidence = evidence_for(source, ["text", "upper"])

    assert evidence["upper"].truth_tested
    assert not evidence["text"].truth_tested


def test_negative_literals_are_read_correctly():
    source = "def f(x):\n    if x < -5:\n        raise ValueError('x')\n    return x\n"

    guards = evidence_for(source, ["x"])["x"].guard_comparisons

    assert [(c.op, c.const) for c in guards] == [("<", -5)]


def test_unparsable_source_yields_empty_evidence():
    evidence = evidence_for("def broken(:\n    pass\n", ["x"])

    assert evidence["x"].equality_values == []
    assert evidence["x"].guard_comparisons == []


# ---- boundary derivation --------------------------------------------------

@pytest.mark.parametrize(
    "op, const, satisfy, expected",
    [
        ("<=", 0, True, 0),      # boundary itself trips `x <= 0`
        ("<=", 0, False, 1),
        ("<", 0, True, -1),
        ("<", 0, False, 0),      # zero is valid when the guard is strict
        (">", 100, True, 101),
        (">", 100, False, 100),
        (">=", 90, True, 90),
        (">=", 90, False, 89),
        ("==", 5, True, 5),
        ("!=", 5, False, 5),
    ],
)
def test_value_satisfying_picks_boundaries(op, const, satisfy, expected):
    assert value_satisfying(Comparison(op, const), satisfy) == expected


def test_float_comparisons_keep_float_type():
    value = value_satisfying(Comparison("<=", 0.0), satisfy=False)

    assert isinstance(value, float)


def test_string_equality_produces_a_distinct_neutral_value():
    neutral = value_satisfying(Comparison("==", "premium"), satisfy=False)

    assert isinstance(neutral, str)
    assert neutral != "premium"


# ---- baseline selection ---------------------------------------------------

def test_baseline_avoids_every_raise_guard():
    source = (
        "def charge(price):\n"
        "    if price <= 0:\n"
        "        raise ValueError('x')\n"
        "    return price * 2\n"
    )
    evidence = evidence_for(source, ["price"])["price"]

    baseline = baseline_value(evidence, fallback=1)

    assert baseline > 0


def test_baseline_misses_every_equality_branch():
    """The default case should exercise the fall-through, not a named branch."""
    source = (
        "def fee(status):\n"
        "    if status == 'gold':\n"
        "        return 0\n"
        "    return 10\n"
    )
    evidence = evidence_for(source, ["status"])["status"]

    assert baseline_value(evidence, fallback="text") != "gold"


def test_truth_tested_parameter_defaults_to_false():
    source = "def render(upper):\n    if upper:\n        return 1\n    return 0\n"
    evidence = evidence_for(source, ["upper"])["upper"]

    assert baseline_value(evidence, fallback=1) is False


def test_declared_type_outranks_body_arithmetic():
    """`word * 2` is arithmetic, but `word: str` still means a string."""
    source = "def shout(word):\n    return word * 2\n"
    evidence = evidence_for(source, ["word"])["word"]

    assert baseline_value(evidence, fallback="text", numeric_ok=False) == "text"


def test_float_annotation_produces_a_float_baseline():
    source = "def scale(value):\n    return value * 2\n"
    evidence = evidence_for(source, ["value"])["value"]

    assert isinstance(baseline_value(evidence, fallback=1.0, prefer_float=True), float)


# ---- branch and trigger values -------------------------------------------

def test_branch_values_include_every_equality_literal():
    source = (
        "def fee(status):\n"
        "    if status == 'gold':\n"
        "        return 0\n"
        "    if status == 'silver':\n"
        "        return 5\n"
        "    return 10\n"
    )
    values = branch_values(evidence_for(source, ["status"])["status"])

    assert "gold" in values
    assert "silver" in values


def test_branch_values_include_both_sides_of_a_comparison():
    source = "def grade(score):\n    if score >= 90:\n        return 'A'\n    return 'B'\n"

    values = branch_values(evidence_for(source, ["score"])["score"])

    assert 90 in values and 89 in values


def test_branch_values_offer_none_and_booleans_when_relevant():
    source = (
        "def label(value, flag):\n"
        "    if value is None:\n"
        "        return 'x'\n"
        "    if flag:\n"
        "        return 'y'\n"
        "    return 'z'\n"
    )
    evidence = evidence_for(source, ["value", "flag"])

    assert None in branch_values(evidence["value"])
    assert True in branch_values(evidence["flag"])
    assert False in branch_values(evidence["flag"])


def test_guard_triggers_target_the_error_path():
    source = (
        "def charge(price):\n"
        "    if price <= 0:\n"
        "        raise ValueError('x')\n"
        "    return price\n"
    )

    assert guard_trigger_values(evidence_for(source, ["price"])["price"]) == [0]


def test_functions_without_guards_have_no_triggers():
    source = "def double(x):\n    return x * 2\n"

    assert guard_trigger_values(evidence_for(source, ["x"])["x"]) == []


# ---- probing --------------------------------------------------------------

def test_probe_records_a_returned_value():
    result = probe_call(lambda a, b: a + b, [2, 3])

    assert result.returned
    assert result.value == 5
    assert result.exception is None


def test_probe_records_the_exception_type_without_raising():
    def boom(x):
        raise KeyError("nope")

    result = probe_call(boom, [1])

    assert not result.returned
    assert result.exception == "KeyError"


def test_probe_captures_stdout():
    def talk(name):
        print("hi", name)

    result = probe_call(talk, ["ada"])

    assert result.stdout == "hi ada\n"
    assert result.returned


def test_probe_gives_up_on_a_runaway_function(monkeypatch):
    monkeypatch.setattr("test_generator.scenarios.PROBE_TIMEOUT_SEC", 0.2)

    def slow():
        # Sleeps rather than spins: the abandoned daemon thread must not keep
        # burning CPU for the rest of the session.
        time.sleep(5)

    result = probe_call(slow, [])

    assert result.failed
    assert not result.returned


def test_probe_handles_async_functions():
    async def fetch(n):
        return n * 2

    result = probe_call(fetch, [21], is_async=True)

    assert result.returned and result.value == 42


# ---- assertion safety -----------------------------------------------------

@pytest.mark.parametrize("value", [1, 2.5, "text", True, None, [1, 2], {"a": 1}, (1, 2)])
def test_literal_expression_round_trips_plain_values(value):
    text = literal_expression(value)

    assert text is not None
    assert ast.literal_eval(text) == value


@pytest.mark.parametrize("value", [float("nan"), float("inf"), object()])
def test_literal_expression_refuses_values_it_cannot_state(value):
    assert literal_expression(value) is None


def test_literal_expression_refuses_huge_values():
    assert literal_expression(list(range(500))) is None


def test_approx_is_used_only_for_noisy_floats():
    assert needs_approx(0.30000000000000004)
    assert not needs_approx(80.0)
    assert not needs_approx(95.5)
    assert not needs_approx(100)


# ---- naming ---------------------------------------------------------------

@pytest.mark.parametrize(
    "value, expected",
    [
        ("SAVE5", "save5"), ("premium", "premium"), (None, "none"),
        (True, "true"), (False, "false"), (0, "0"), (-1, "neg_1"), ("", "empty"),
    ],
)
def test_slug_is_deterministic_and_identifier_safe(value, expected):
    assert slug(value) == expected
    assert f"test_{slug(value)}".isidentifier()


def test_exception_slug_snake_cases_the_class_name():
    assert exception_slug("ValueError") == "value_error"
    assert exception_slug("KeyError") == "key_error"
