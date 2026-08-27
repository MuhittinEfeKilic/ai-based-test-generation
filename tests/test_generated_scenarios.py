"""End-to-end shape of the generated suite: values, assertions and names.

Each fixture is a small stand-in for a different code pattern, so passing these
cannot be achieved by recognising any particular function.
"""

import importlib

import pytest

from analyzer.code_analyzer import CodeAnalyzer
from test_generator.prompt_builder import build_test_plan
from test_generator.test_generator import generate_pytest_code, generated_body


def generate(tmp_path, monkeypatch, filename: str, source: str) -> str:
    """Write a module, analyse it, and return only the generated tests."""
    module_path = tmp_path / filename
    module_path.write_text(source, encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    importlib.invalidate_caches()

    analysis = CodeAnalyzer().analyze_as_dict(str(module_path))
    plan = build_test_plan(analysis)
    return generated_body(generate_pytest_code(plan, module_path.stem))


TIERS = (
    "def fee(status):\n"
    "    if status == 'gold':\n"
    "        return 0\n"
    "    elif status == 'silver':\n"
    "        return 5\n"
    "    return 10\n"
)

GRADES = (
    "def grade(score):\n"
    "    if score >= 90:\n"
    "        return 'A'\n"
    "    if score >= 80:\n"
    "        return 'B'\n"
    "    return 'C'\n"
)

GUARDED = (
    "def charge(price):\n"
    "    if price <= 0:\n"
    "        raise ValueError('Price must be greater than zero')\n"
    "    return price * 2\n"
)


# ---- string equality branches ---------------------------------------------

def test_string_branches_use_the_literals_from_the_source(tmp_path, monkeypatch):
    code = generate(tmp_path, monkeypatch, "tiers.py", TIERS)

    assert "fee('gold')" in code
    assert "fee('silver')" in code


def test_string_branches_assert_the_real_return_values(tmp_path, monkeypatch):
    code = generate(tmp_path, monkeypatch, "tiers2.py", TIERS)

    assert "assert result == 0" in code
    assert "assert result == 5" in code
    assert "assert result == 10" in code
    assert "assert result is not None" not in code


def test_default_case_exercises_the_fall_through(tmp_path, monkeypatch):
    code = generate(tmp_path, monkeypatch, "tiers3.py", TIERS)

    assert "test_fee_default_case" in code
    # The fall-through returns 10, so the baseline must miss both branches.
    assert "fee('gold')" in code and "assert result == 10" in code


# ---- numeric comparison boundaries ----------------------------------------

def test_numeric_comparisons_produce_distinct_branch_values(tmp_path, monkeypatch):
    code = generate(tmp_path, monkeypatch, "grades.py", GRADES)

    assert "assert result == 'A'" in code
    assert "assert result == 'B'" in code
    assert "assert result == 'C'" in code


def test_redundant_boundary_scenarios_are_dropped(tmp_path, monkeypatch):
    """Two values landing on the same result are not two tests."""
    code = generate(tmp_path, monkeypatch, "grades2.py", GRADES)

    assert code.count("def test_") == 3


# ---- exception paths ------------------------------------------------------

def test_guarded_function_gets_an_exception_test(tmp_path, monkeypatch):
    code = generate(tmp_path, monkeypatch, "guard.py", GUARDED)

    assert "with pytest.raises(ValueError):" in code
    assert "charge(0)" in code


def test_exception_test_is_named_after_the_exception(tmp_path, monkeypatch):
    code = generate(tmp_path, monkeypatch, "guard2.py", GUARDED)

    assert "raises_value_error" in code


def test_exception_type_follows_the_code_not_a_fixed_assumption(tmp_path, monkeypatch):
    code = generate(
        tmp_path,
        monkeypatch,
        "keyed.py",
        "def lookup(key):\n"
        "    if key == '':\n"
        "        raise KeyError('key required')\n"
        "    return key.upper()\n",
    )

    assert "KeyError" in code
    assert "ValueError" not in code


def test_no_exception_test_when_nothing_raises(tmp_path, monkeypatch):
    code = generate(tmp_path, monkeypatch, "plain.py", "def double(x):\n    return x * 2\n")

    assert "pytest.raises" not in code


# ---- expected-value assertions --------------------------------------------

def test_expected_values_come_from_real_behaviour(tmp_path, monkeypatch):
    code = generate(
        tmp_path, monkeypatch, "adder.py", "def add(a, b):\n    return a + b\n"
    )

    assert "assert result == 200" in code  # 100 + 100


def test_noisy_floats_use_approx(tmp_path, monkeypatch):
    code = generate(
        tmp_path,
        monkeypatch,
        "floaty.py",
        "def share(total):\n    return total / 3\n",
    )

    assert "pytest.approx" in code


def test_void_functions_assert_none_rather_than_nothing(tmp_path, monkeypatch):
    code = generate(
        tmp_path,
        monkeypatch,
        "voider.py",
        "def store(value):\n    _ = value\n",
    )

    assert "assert result is None" in code


def test_unimportable_target_degrades_instead_of_guessing(tmp_path):
    """Without the module we cannot know results, so no value is claimed."""
    module_path = tmp_path / "orphan.py"
    module_path.write_text("def double(x):\n    return x * 2\n", encoding="utf-8")
    analysis = CodeAnalyzer().analyze_as_dict(str(module_path))

    code = generated_body(generate_pytest_code(build_test_plan(analysis), "not_importable_module"))

    assert "assert result is not None" in code
    assert "assert result ==" not in code


# ---- naming ---------------------------------------------------------------

def test_names_describe_the_scenario(tmp_path, monkeypatch):
    code = generate(tmp_path, monkeypatch, "tiers4.py", TIERS)

    assert "def test_fee_gold(" in code
    assert "def test_fee_silver(" in code
    assert "additional_case" not in code


def test_names_are_unique_and_valid_identifiers(tmp_path, monkeypatch):
    code = generate(
        tmp_path,
        monkeypatch,
        "twoparams.py",
        "def pick(first, second):\n"
        "    if first == 'x':\n"
        "        return 1\n"
        "    if second == 'x':\n"
        "        return 2\n"
        "    return 3\n",
    )

    names = [
        line[len("def ") : line.index("(")]
        for line in code.splitlines()
        if line.startswith("def test_")
    ]

    assert len(names) == len(set(names))
    assert all(name.isidentifier() for name in names)


def test_generated_suite_is_valid_python(tmp_path, monkeypatch):
    import ast as _ast

    code = generate(tmp_path, monkeypatch, "tiers5.py", TIERS)

    _ast.parse(code)


# ---- preview split --------------------------------------------------------

def test_preview_strips_the_import_bootstrap(tmp_path, monkeypatch):
    module_path = tmp_path / "shown.py"
    module_path.write_text("def double(x):\n    return x * 2\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    importlib.invalidate_caches()
    analysis = CodeAnalyzer().analyze_as_dict(str(module_path))

    full = generate_pytest_code(build_test_plan(analysis), "shown")
    body = generated_body(full)

    assert "sys.path.insert" in full
    assert "sys.path.insert" not in body
    assert "RUN_UI_GENERATED" not in body
    assert body.startswith("def test_")


def test_preview_returns_everything_when_there_is_no_marker():
    assert generated_body("def test_x():\n    pass\n").startswith("def test_x")
