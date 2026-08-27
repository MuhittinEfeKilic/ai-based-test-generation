"""Argument-selection behaviour of the rule-based generator.

These cover the "don't generate a test that blows up on its own inputs" rules:
inferred dict keys, capsys assertions, ValueError paths, division guards.
"""

import importlib

from analyzer.code_analyzer import CodeAnalyzer
from test_generator.prompt_builder import build_test_plan
from test_generator.test_generator import generate_pytest_code


def generate(tmp_path, monkeypatch, filename: str, source: str) -> str:
    """Write a module, analyse it, and return the generated pytest source."""
    module_path = tmp_path / filename
    module_path.write_text(source, encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    importlib.invalidate_caches()

    analysis = CodeAnalyzer().analyze_as_dict(str(module_path))
    plan = build_test_plan(analysis)
    return generate_pytest_code(plan, module_path.stem)


def plain_calls(code: str) -> str:
    """The generated code with every `pytest.raises` test removed.

    Values that trip a guard are legitimate inside an exception test but must
    never appear as an ordinary call, so the two need to be told apart.
    """
    separator = "\ndef "
    blocks = code.split(separator)
    return separator.join(b for b in blocks if "pytest.raises" not in b)


def test_list_dict_infers_keys(tmp_path, monkeypatch):
    code = generate(
        tmp_path,
        monkeypatch,
        "order_utils.py",
        "def total(items: list[dict]):\n"
        "    total = 0\n"
        "    for item in items:\n"
        "        total += item['quantity'] * item['price']\n"
        "    return total\n",
    )

    assert "[{'price': 10.0, 'quantity': 1}]" in code


def test_print_path_adds_capsys_assert(tmp_path, monkeypatch):
    code = generate(
        tmp_path,
        monkeypatch,
        "printer.py",
        "def greet(name: str):\n"
        "    print('hello', name)\n"
        "    return name\n",
    )

    assert "capsys" in code
    # The probe captured the real output, so the assertion can be exact.
    assert r"assert captured.out == 'hello text\n'" in code


def test_negative_value_generates_raises(tmp_path, monkeypatch):
    code = generate(
        tmp_path,
        monkeypatch,
        "account.py",
        "def withdraw(amount: int):\n"
        "    if amount < 0:\n"
        "        raise ValueError('negative')\n"
        "    return amount\n",
    )

    assert "with pytest.raises(ValueError):" in code
    assert "withdraw(-1)" in code


def test_division_param_avoids_zero(tmp_path, monkeypatch):
    code = generate(
        tmp_path,
        monkeypatch,
        "mathy.py",
        "def safe_divide(a: float, b: float):\n"
        "    return a / (b or 1)\n",
    )

    assert "safe_divide(0.0, 0.0)" not in code


def test_unannotated_numeric_param_is_not_given_a_string(tmp_path, monkeypatch):
    """A body that compares against numbers rules out '' and None as inputs."""
    code = generate(
        tmp_path,
        monkeypatch,
        "pricing.py",
        "def calculate_discount(price, discount):\n"
        "    if price < 0:\n"
        "        raise ValueError('Price cannot be negative')\n"
        "    if discount < 0 or discount > 100:\n"
        "        raise ValueError('Discount must be between 0 and 100')\n"
        "    return price * (1 - discount / 100)\n",
    )

    assert "calculate_discount('', '')" not in code
    assert "calculate_discount(None, None)" not in code
    # Numeric parameters get numeric values, and the guard is exercised
    # through pytest.raises rather than through a plain call.
    assert "calculate_discount(100, 100)" in code
    assert "with pytest.raises(ValueError):" in code
    assert "calculate_discount(-1, 100)" in code


def test_unannotated_iterated_param_gets_the_inferred_dict_shape(tmp_path, monkeypatch):
    code = generate(
        tmp_path,
        monkeypatch,
        "bulk.py",
        "def apply_bulk_pricing(items):\n"
        "    total = 0\n"
        "    for item in items:\n"
        "        total += item['quantity'] * item['price']\n"
        "    return total\n",
    )

    assert "apply_bulk_pricing([{'price': 10.0, 'quantity': 1}])" in code
    assert "[{'x': 1}]" not in code


def test_unannotated_dict_param_is_built_from_its_keys(tmp_path, monkeypatch):
    code = generate(
        tmp_path,
        monkeypatch,
        "profile.py",
        "def describe(record):\n"
        "    return record['name']\n",
    )

    assert "describe({'name': 'value'})" in code


def test_usage_inference_does_not_override_annotations(tmp_path, monkeypatch):
    """An explicit `str` annotation wins even when the body does arithmetic."""
    code = generate(
        tmp_path,
        monkeypatch,
        "repeat.py",
        "def shout(word: str):\n"
        "    return word * 2\n",
    )

    assert "shout('text')" in code


def test_nonpositive_guard_excludes_zero_not_just_negatives(tmp_path, monkeypatch):
    """`price <= 0` rejects zero, so zero is not a safe input either."""
    code = generate(
        tmp_path,
        monkeypatch,
        "checkout.py",
        "def charge(price):\n"
        "    if price <= 0:\n"
        "        raise ValueError('Price must be greater than zero')\n"
        "    return price * 2\n",
    )

    # Zero trips `price <= 0`, so it may only appear inside pytest.raises.
    assert "charge(0)" not in plain_calls(code)
    assert "charge(0)" in code
    assert "with pytest.raises(ValueError):" in code
    assert "charge(100)" in plain_calls(code)


def test_strict_negative_guard_still_allows_zero(tmp_path, monkeypatch):
    """`amount < 0` accepts zero, so zero stays a valid case."""
    code = generate(
        tmp_path,
        monkeypatch,
        "wallet.py",
        "def withdraw(amount):\n"
        "    if amount < 0:\n"
        "        raise ValueError('negative')\n"
        "    return amount\n",
    )

    assert "withdraw(0)" in plain_calls(code)
