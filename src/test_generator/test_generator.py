"""Emit deterministic pytest suites from an analyzed function plan.

The pipeline per function is: read evidence off the AST, build one scenario per
interesting input, probe each scenario by calling the function, then emit tests
that assert the values the function actually produced.

Nothing here is specific to any particular function or parameter name.
"""

import ast
import importlib
from pathlib import Path
from typing import Dict, List, get_args, get_origin, get_type_hints

from test_generator.scenarios import (
    Scenario,
    build_scenarios,
    literal_expression,
    name_scenarios,
    needs_approx,
    probe_call,
    select_scenarios,
)
from test_generator.value_inference import collect_evidence

#: Separates the import bootstrap from the generated tests. The UI shows only
#: the part after it; the saved file keeps both.
BODY_MARKER = "# --- generated tests ---"


def _sanitize_name(name: str) -> str:
    return "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in name)


def _guess_kind(arg_name: str) -> str:
    """Last-resort guess from the parameter name, used only when the body says nothing."""
    n = arg_name.lower()
    if "age" in n:
        return "age"
    if "name" in n or "text" in n or "msg" in n or "title" in n:
        return "str"
    if "times" in n or "count" in n or "n" == n or n.endswith("_n"):
        return "int"
    if "nums" in n or "numbers" in n or "items" in n or "list" in n:
        return "list_int"
    if "dict" in n or "map" in n or "data" in n:
        return "dict"
    if "denom" in n or "div" in n or "b" == n:
        return "float_divisor"
    return "int"


def infer_dict_keys_from_ast(function_source: str) -> set[str]:
    if not function_source:
        return set()
    try:
        tree = ast.parse(function_source)
    except SyntaxError:
        return set()
    keys: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript):
            key_node = node.slice
            if isinstance(key_node, ast.Index):
                key_node = key_node.value
            if isinstance(key_node, ast.Constant) and isinstance(key_node.value, str):
                keys.add(key_node.value)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr == "get" and node.args:
                first = node.args[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    keys.add(first.value)
    return keys


def _default_value_for_key(key: str):
    k = key.lower()
    if k in {"quantity", "qty", "count", "num", "n", "age"}:
        return 1
    if k in {"price", "cost", "amount", "total"}:
        return 10.0
    if k in {"name", "title", "label"}:
        return "value"
    if k in {"id"}:
        return 1
    return 1


def _build_dict_from_keys(keys: set[str]) -> Dict:
    if not keys:
        return {"x": 1}
    return {k: _default_value_for_key(k) for k in sorted(keys)}


def _normalize_annotation(param_annotation):
    if param_annotation is None:
        return "unknown"
    if isinstance(param_annotation, str):
        s = param_annotation.replace(" ", "")
        s_lower = s.lower()
        if "list" in s_lower and "dict" in s_lower:
            return "list_dict"
        if s_lower.startswith("dict") or "dict[" in s_lower:
            return "dict"
        if "optional[str]" in s_lower or "str|none" in s_lower or "none|str" in s_lower:
            return "optional_str"
        if s_lower in {"str", "builtins.str"}:
            return "str"
        if s_lower in {"int", "builtins.int"}:
            return "int"
        if s_lower in {"float", "builtins.float"}:
            return "float"
        if s_lower in {"bool", "builtins.bool"}:
            return "bool"
        if s_lower.startswith("list"):
            return "list"
        return "unknown"
    origin = get_origin(param_annotation)
    args = get_args(param_annotation)
    if origin in {list, List}:
        if args and (get_origin(args[0]) in {dict, Dict} or args[0] in {dict, Dict}):
            return "list_dict"
        return "list"
    if origin in {dict, Dict} or param_annotation in {dict, Dict}:
        return "dict"
    if origin is not None and args:
        if type(None) in args and str in args:
            return "optional_str"
    if param_annotation is bool:
        return "bool"
    if param_annotation is str:
        return "str"
    if param_annotation is int:
        return "int"
    if param_annotation is float:
        return "float"
    return "unknown"


def build_safe_arg_value(param_name: str, param_annotation, inferred_keys: set[str]):
    """A value that is merely type-plausible, used when the body gives no evidence."""
    kind = _normalize_annotation(param_annotation)
    if kind == "list_dict":
        return [_build_dict_from_keys(inferred_keys)]
    if kind == "dict":
        return _build_dict_from_keys(inferred_keys)
    if kind == "optional_str":
        return "text"
    if kind == "str":
        return "text"
    if kind == "bool":
        return True
    if kind == "int":
        return 1
    if kind == "float":
        return 1.0
    if kind == "list":
        return []

    guessed = _guess_kind(param_name)
    if guessed == "str":
        return "text"
    if guessed == "list_int":
        return [1, 2, 3]
    if guessed == "dict":
        return _build_dict_from_keys(inferred_keys)
    if guessed == "float_divisor":
        return 2.0
    if guessed == "age":
        return 30
    return 1


def _usage_fallback(evidence, param_name, hint, inferred_keys):
    """Shape the fallback with what the body does, before falling back to names."""
    if evidence.iterated:
        if evidence.subscript_keys or infer_keys_present(inferred_keys):
            return [_build_dict_from_keys(evidence.subscript_keys or inferred_keys)]
        return [1, 2, 3]
    if evidence.subscript_keys:
        return _build_dict_from_keys(evidence.subscript_keys)
    return build_safe_arg_value(param_name, hint, inferred_keys)


def infer_keys_present(keys: set[str]) -> bool:
    return bool(keys)


def _parsed_defaults(raw_defaults: Dict[str, str]) -> Dict[str, object]:
    """Declared defaults, kept only when they are plain literals."""
    parsed: Dict[str, object] = {}
    for name, text in (raw_defaults or {}).items():
        try:
            parsed[name] = ast.literal_eval(text)
        except (ValueError, SyntaxError):
            continue
    return parsed


def _raised_exception_names(function_source: str) -> List[str]:
    """Exception class names raised directly by the function, in source order."""
    if not function_source:
        return []
    try:
        tree = ast.parse(function_source)
    except SyntaxError:
        return []
    names: List[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Raise) or node.exc is None:
            continue
        exc = node.exc
        if isinstance(exc, ast.Call):
            exc = exc.func
        if isinstance(exc, ast.Name) and exc.id not in names:
            names.append(exc.id)
    return names


def _call_expr(fn_name: str, args: List, is_async: bool) -> str:
    rendered = ", ".join(repr(a) for a in args)
    call = f"{fn_name}({rendered})"
    return f"asyncio.run({call})" if is_async else call


def _stdout_assertion(text: str) -> List[str]:
    """Assert on captured output, exactly when that stays readable."""
    if not text:
        return ["    assert captured.out == ''"]
    if len(text) <= 200:
        return [f"    assert captured.out == {text!r}"]
    first_line = text.splitlines()[0]
    return [f"    assert {first_line!r} in captured.out"]


def _emit_scenario(
    lines: List[str],
    name: str,
    fn_name: str,
    scenario: Scenario,
    is_async: bool,
    has_print: bool,
    fallback_exception: str | None,
) -> None:
    call = _call_expr(fn_name, scenario.args, is_async)
    probe = scenario.probe

    if scenario.kind == "raise":
        exception = probe.exception or fallback_exception or "Exception"
        lines.append(f"def {name}():")
        lines.append(f"    with pytest.raises({exception}):")
        lines.append(f"        {call}")
        lines.append("")
        return

    fixture = "capsys" if has_print else ""
    lines.append(f"def {name}({fixture}):")

    asserted = False
    if probe.returned and probe.value is not None:
        literal = literal_expression(probe.value)
        lines.append(f"    result = {call}")
        if literal is None:
            lines.append("    assert result is not None")
        elif needs_approx(probe.value):
            lines.append(f"    assert result == pytest.approx({literal})")
        else:
            lines.append(f"    assert result == {literal}")
        asserted = True
    elif probe.returned:
        lines.append(f"    result = {call}")
        lines.append("    assert result is None")
        asserted = True
    else:
        # No usable probe: still exercise the call, assert only what we know.
        lines.append(f"    result = {call}")
        lines.append("    assert result is not None")
        asserted = True

    if has_print:
        lines.append("    captured = capsys.readouterr()")
        lines.extend(_stdout_assertion(probe.stdout if probe.returned else ""))

    if not asserted:
        lines.append("    assert True")
    lines.append("")


def generate_pytest_code(test_plan: Dict, module_import: str) -> str:
    """Emit a deterministic pytest module for every function in the plan.

    Note: the target module is imported and its functions are called so that
    expected values can be derived from real behaviour. Only run this on code
    you trust. When the import fails, generation degrades to weaker assertions
    rather than guessing at results.
    """
    functions = test_plan["functions"]
    needs_asyncio = any(fn.get("is_async") for fn in functions)

    lines: List[str] = []
    lines.append("import os")
    lines.append("import sys")
    if needs_asyncio:
        lines.append("import asyncio")
    lines.append("from pathlib import Path")
    lines.append("")
    lines.append("import pytest")
    lines.append("")
    lines.append("PROJECT_ROOT = Path(__file__).resolve().parents[2]")
    lines.append("if str(PROJECT_ROOT) not in sys.path:")
    lines.append("    sys.path.insert(0, str(PROJECT_ROOT))")
    lines.append("")
    # The skip must precede the target import: the generated file lives in the
    # repo but its target is a scratch module, so importing first would turn a
    # deliberately disabled test run into a collection error.
    lines.append("if os.getenv('RUN_UI_GENERATED') != '1':")
    lines.append("    pytest.skip('ui generated tests are disabled', allow_module_level=True)")
    lines.append("")
    lines.append(
        f"from {module_import} import " + ", ".join(fn["name"] for fn in functions)
    )
    lines.append("")
    lines.append(BODY_MARKER)
    lines.append("")

    try:
        module_obj = importlib.import_module(module_import)
    except Exception:
        module_obj = None

    for fn in functions:
        fn_name = fn["name"]
        params = fn["args"]
        fn_source = fn.get("source", "")
        annotations = fn.get("annotations", {})
        is_async = bool(fn.get("is_async", False))
        has_print = bool(fn.get("has_print", False))

        fn_obj = None
        type_hints: Dict = {}
        if module_obj is not None:
            try:
                fn_obj = getattr(module_obj, fn_name)
                type_hints = get_type_hints(fn_obj, include_extras=True)
            except Exception:
                fn_obj = getattr(module_obj, fn_name, None)
                type_hints = {}

        inferred_keys = infer_dict_keys_from_ast(fn_source)
        evidence = collect_evidence(fn_source, params)

        hints = {n: type_hints.get(n, annotations.get(n)) for n in params}
        kinds = {n: _normalize_annotation(hints[n]) for n in params}
        # A declared non-numeric type outranks numeric evidence from the body.
        numeric_ok = {n: kinds[n] in {"unknown", "int", "float"} for n in params}
        prefer_float = {n: kinds[n] == "float" for n in params}

        fallbacks = {
            name: _usage_fallback(evidence[name], name, hints[name], inferred_keys)
            for name in params
        }
        defaults = _parsed_defaults(fn.get("defaults", {}))

        scenarios = build_scenarios(
            params, evidence, fallbacks, defaults, numeric_ok, prefer_float
        )

        raised_names = _raised_exception_names(fn_source)

        if fn_obj is not None:
            for scenario in scenarios:
                scenario.probe = probe_call(fn_obj, scenario.args, is_async)
            selected = select_scenarios(scenarios, set(raised_names))
        else:
            # Without the module we cannot confirm behaviour; keep the
            # non-error scenarios and assert only that they run.
            selected = [s for s in scenarios if s.kind != "raise"][:3]
            if raised_names:
                selected.extend(s for s in scenarios if s.kind == "raise")

        if not selected:
            continue

        fallback_exception = next(iter(raised_names), None)
        names = name_scenarios(fn_name, selected)
        for name, scenario in zip(names, selected):
            _emit_scenario(
                lines,
                name,
                fn_name,
                scenario,
                is_async,
                has_print,
                fallback_exception,
            )

    return "\n".join(lines)


def generated_body(code: str) -> str:
    """The generated tests without the import bootstrap, for UI preview."""
    marker = code.find(BODY_MARKER)
    if marker == -1:
        return code
    return code[marker + len(BODY_MARKER):].strip("\n")


def save_tests(pytest_code: str, output_path: Path) -> Path:
    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(pytest_code, encoding="utf-8")
    return output_path
