"""Structural guarantees about the emitted test module.

The generated file is written into the repo but targets a scratch module, so
its import order and skip guard matter as much as its assertions.
"""

import ast
import importlib

from analyzer.code_analyzer import CodeAnalyzer
from test_generator.prompt_builder import build_test_plan
from test_generator.test_generator import generate_pytest_code


def generate(tmp_path, monkeypatch, filename: str, source: str) -> str:
    module_path = tmp_path / filename
    module_path.write_text(source, encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    importlib.invalidate_caches()

    analysis = CodeAnalyzer().analyze_as_dict(str(module_path))
    plan = build_test_plan(analysis)
    return generate_pytest_code(plan, module_path.stem)


def test_skip_guard_precedes_target_import(tmp_path, monkeypatch):
    """A disabled run must skip, not fail collection on a missing target."""
    code = generate(
        tmp_path,
        monkeypatch,
        "shapes.py",
        "def area(w: int, h: int):\n    return w * h\n",
    )

    skip_line = code.index("pytest.skip(")
    import_line = code.index("from shapes import")
    assert skip_line < import_line


def test_generated_code_is_valid_python(tmp_path, monkeypatch):
    code = generate(
        tmp_path,
        monkeypatch,
        "shapes2.py",
        "def area(w: int, h: int):\n    return w * h\n",
    )

    ast.parse(code)


def test_only_module_level_functions_are_imported(tmp_path, monkeypatch):
    """Methods and nested defs are not importable by name, so they are skipped."""
    code = generate(
        tmp_path,
        monkeypatch,
        "shop.py",
        "def public_total(x: int):\n"
        "    def helper(y: int):\n"
        "        return y\n"
        "    return helper(x)\n"
        "\n"
        "class Cart:\n"
        "    def add(self, item):\n"
        "        return item\n",
    )

    assert "from shop import public_total" in code
    assert "helper" not in code
    assert "def test_add" not in code


def test_async_function_is_awaited_via_asyncio_run(tmp_path, monkeypatch):
    code = generate(
        tmp_path,
        monkeypatch,
        "async_mod.py",
        "async def load(n: int):\n    return n * 2\n",
    )

    assert "import asyncio" in code
    assert "asyncio.run(load(" in code


def test_sync_only_module_does_not_import_asyncio(tmp_path, monkeypatch):
    code = generate(
        tmp_path,
        monkeypatch,
        "sync_mod.py",
        "def load(n: int):\n    return n * 2\n",
    )

    assert "import asyncio" not in code


def test_default_arguments_are_captured(tmp_path, monkeypatch):
    module_path = tmp_path / "greeter.py"
    module_path.write_text(
        "def greet(name: str, times: int = 3):\n"
        "    for _ in range(times):\n"
        "        print(name)\n",
        encoding="utf-8",
    )

    analysis = CodeAnalyzer().analyze_as_dict(str(module_path))

    assert analysis[0]["defaults"] == {"times": "3"}
    assert analysis[0]["is_async"] is False
