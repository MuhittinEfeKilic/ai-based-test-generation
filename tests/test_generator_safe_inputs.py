import importlib
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from analyzer.code_analyzer import CodeAnalyzer
from test_generator.prompt_builder import build_test_plan
from test_generator.test_generator import generate_pytest_code


def test_list_dict_infers_keys(tmp_path, monkeypatch):
    module_path = tmp_path / "order_utils.py"
    module_path.write_text(
        "def total(items: list[dict]):\n"
        "    total = 0\n"
        "    for item in items:\n"
        "        total += item['quantity'] * item['price']\n"
        "    return total\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    importlib.invalidate_caches()

    analyzer = CodeAnalyzer()
    analysis = analyzer.analyze_as_dict(str(module_path))
    plan = build_test_plan(analysis)
    code = generate_pytest_code(plan, "order_utils")

    assert "[{'price': 10.0, 'quantity': 1}]" in code


def test_print_path_adds_capsys_assert(tmp_path, monkeypatch):
    module_path = tmp_path / "printer.py"
    module_path.write_text(
        "def greet(name: str):\n"
        "    print('hello', name)\n"
        "    return name\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    importlib.invalidate_caches()

    analyzer = CodeAnalyzer()
    analysis = analyzer.analyze_as_dict(str(module_path))
    plan = build_test_plan(analysis)
    code = generate_pytest_code(plan, "printer")

    assert "capsys" in code
    assert "assert 'hello' in captured.out" in code


def test_negative_value_generates_raises(tmp_path, monkeypatch):
    module_path = tmp_path / "account.py"
    module_path.write_text(
        "def withdraw(amount: int):\n"
        "    if amount < 0:\n"
        "        raise ValueError('negative')\n"
        "    return amount\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    importlib.invalidate_caches()

    analyzer = CodeAnalyzer()
    analysis = analyzer.analyze_as_dict(str(module_path))
    plan = build_test_plan(analysis)
    code = generate_pytest_code(plan, "account")

    assert "with pytest.raises(ValueError):" in code
    assert "withdraw(-1)" in code


def test_division_param_avoids_zero(tmp_path, monkeypatch):
    module_path = tmp_path / "mathy.py"
    module_path.write_text(
        "def safe_divide(a: float, b: float):\n"
        "    return a / (b or 1)\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    importlib.invalidate_caches()

    analyzer = CodeAnalyzer()
    analysis = analyzer.analyze_as_dict(str(module_path))
    plan = build_test_plan(analysis)
    code = generate_pytest_code(plan, "mathy")

    assert "safe_divide(0.0, 0.0)" not in code
