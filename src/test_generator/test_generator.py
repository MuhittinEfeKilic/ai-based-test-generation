import ast
import importlib
from pathlib import Path
from typing import Dict, List, get_args, get_origin, get_type_hints


def _sanitize_name(name: str) -> str:
    return "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in name)


def _guess_kind(arg_name: str) -> str:
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


def _sample_values(kind: str) -> List[str]:
    # values returned as python literals (strings)
    if kind == "age":
        return ["-1", "0", "17", "18", "65"]
    if kind == "str":
        return ["'Efe'", "''"]
    if kind == "list_int":
        return ["[]", "[2]", "[1, 2, 3, 4, 6]"]
    if kind == "dict":
        return ["{'x': 1}"]
    if kind == "float_divisor":
        return ["0", "2"]
    if kind == "int":
        return ["0", "1", "2", "-1"]
    return ["1"]


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


def _infer_param_guards(function_source: str, param_names: List[str]) -> Dict[str, Dict[str, bool]]:
    flags: Dict[str, Dict[str, bool]] = {
        name: {"divisor": False, "zero_checked": False, "negative_checked": False}
        for name in param_names
    }
    if not function_source or not param_names:
        return flags
    try:
        tree = ast.parse(function_source)
    except SyntaxError:
        return flags
    name_set = set(param_names)
    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Div, ast.Mod)):
            right_names = {
                n.id for n in ast.walk(node.right) if isinstance(n, ast.Name) and n.id in name_set
            }
            for name in right_names:
                flags[name]["divisor"] = True
        if isinstance(node, ast.Compare):
            sides = [node.left, *node.comparators]
            for side in sides:
                if isinstance(side, ast.Name) and side.id in name_set:
                    other = node.left if side is not node.left else (node.comparators[0] if node.comparators else None)
                    if isinstance(other, ast.Constant) and other.value == 0:
                        if any(isinstance(op, (ast.Lt, ast.LtE)) for op in node.ops):
                            flags[side.id]["negative_checked"] = True
                        if any(isinstance(op, ast.Eq) for op in node.ops):
                            flags[side.id]["zero_checked"] = True
    return flags


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
    if param_annotation is str:
        return "str"
    if param_annotation is int:
        return "int"
    if param_annotation is float:
        return "float"
    return "unknown"


def build_safe_arg_value(param_name: str, param_annotation, inferred_keys: set[str]):
    kind = _normalize_annotation(param_annotation)
    if kind == "list_dict":
        return [_build_dict_from_keys(inferred_keys)]
    if kind == "dict":
        return _build_dict_from_keys(inferred_keys)
    if kind == "optional_str":
        return "SAVE10"
    if kind == "str":
        return "text"
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
        return [{"x": 1}]
    if guessed == "dict":
        return {"x": 1}
    if guessed == "float_divisor":
        return 2.0
    return 0


def _build_arg_candidates(param_name: str, param_annotation, inferred_keys: set[str]) -> List:
    kind = _normalize_annotation(param_annotation)
    if kind == "optional_str":
        return ["SAVE10", "INVALID", None]
    if kind == "int":
        return [1, 0, -1]
    if kind == "float":
        return [1.0, 0.0, -1.0]
    if kind == "list_dict":
        base = _build_dict_from_keys(inferred_keys)
        return [[base], [base, base]]
    if kind == "dict":
        return [_build_dict_from_keys(inferred_keys)]
    if kind == "str":
        return ["text", ""]
    if kind == "list":
        return [[], [1]]
    guessed = _guess_kind(param_name)
    if guessed == "str":
        return ["text", ""]
    if guessed == "list_int":
        return [[{"x": 1}], []]
    if guessed == "dict":
        return [{"x": 1}]
    return [0, "", None]


def _format_arg_value(value) -> str:
    return repr(value)


def _is_numeric_param(param_name: str, param_annotation) -> bool:
    kind = _normalize_annotation(param_annotation)
    if kind in {"int", "float"}:
        return True
    guessed = _guess_kind(param_name)
    return guessed in {"age", "int", "float_divisor"}


def _infer_negative_dict_keys(function_source: str, inferred_keys: set[str]) -> set[str]:
    if not function_source or not inferred_keys:
        return set()
    try:
        tree = ast.parse(function_source)
    except SyntaxError:
        return set()
    neg_keys: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare) and any(isinstance(op, (ast.Lt, ast.LtE)) for op in node.ops):
            sides = [node.left, *node.comparators]
            for side in sides:
                if isinstance(side, ast.Subscript):
                    key_node = side.slice
                    if isinstance(key_node, ast.Index):
                        key_node = key_node.value
                    if isinstance(key_node, ast.Constant) and isinstance(key_node.value, str):
                        if key_node.value in inferred_keys:
                            neg_keys.add(key_node.value)
    return neg_keys


def _infer_print_param_targets(function_source: str, param_names: List[str]) -> set[str]:
    if not function_source or not param_names:
        return set()
    try:
        tree = ast.parse(function_source)
    except SyntaxError:
        return set()
    names = set(param_names)
    targets: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            if not any(
                isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "print"
                for n in ast.walk(node)
            ):
                continue
            test = node.test
            if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not) and isinstance(test.operand, ast.Name):
                if test.operand.id in names:
                    targets.add(test.operand.id)
            elif isinstance(test, ast.Compare) and isinstance(test.left, ast.Name):
                if test.left.id in names and test.comparators:
                    comp = test.comparators[0]
                    if isinstance(comp, ast.Constant) and comp.value is None:
                        targets.add(test.left.id)
                    if isinstance(comp, ast.Constant) and comp.value == 0:
                        targets.add(test.left.id)
    return targets


def _build_print_call_args(
    args: List[str],
    arg_candidates: List[List],
    annotations: Dict[str, str | None],
    inferred_keys: set[str],
    function_source: str,
    print_strings: List[str],
):
    overrides = {}
    targets = _infer_print_param_targets(function_source, args)
    for idx, a in enumerate(args):
        kind = _normalize_annotation(annotations.get(a))
        if a in targets:
            if kind in {"list", "list_dict"}:
                overrides[a] = []
            elif kind == "dict":
                overrides[a] = {}
            elif kind == "optional_str":
                overrides[a] = None
            elif kind == "str":
                overrides[a] = ""
            elif kind in {"int", "float"}:
                overrides[a] = 0
        if kind == "optional_str" and print_strings:
            overrides[a] = "INVALID"
    values = []
    for idx, a in enumerate(args):
        if a in overrides:
            values.append(_format_arg_value(overrides[a]))
        else:
            values.append(_format_arg_value(arg_candidates[idx][0]))
    return ", ".join(values)


def generate_pytest_code(test_plan: Dict, module_import: str) -> str:
    lines: List[str] = []

    # --- imports & path fix ---
    lines.append("import os")
    lines.append("import sys")
    lines.append("from pathlib import Path")
    lines.append("")
    lines.append("PROJECT_ROOT = Path(__file__).resolve().parents[2]")
    lines.append("if str(PROJECT_ROOT) not in sys.path:")
    lines.append("    sys.path.insert(0, str(PROJECT_ROOT))")
    lines.append("")
    lines.append(
        f"from {module_import} import " + ", ".join(fn["name"] for fn in test_plan["functions"])
    )
    lines.append("")
    lines.append("import pytest")
    lines.append("")
    lines.append("if os.getenv('RUN_UI_GENERATED') != '1':")
    lines.append("    pytest.skip('ui generated tests are disabled', allow_module_level=True)")
    lines.append("")

    module_obj = None
    try:
        module_obj = importlib.import_module(module_import)
    except Exception:
        module_obj = None

    for fn in test_plan["functions"]:
        fn_name = fn["name"]
        args = fn["args"]
        safe_fn = _sanitize_name(fn_name)

        #Sample arg literals
        annotations = fn.get("annotations", {})
        fn_source = fn.get("source", "")
        inferred_keys = infer_dict_keys_from_ast(fn_source)
        negative_dict_keys = _infer_negative_dict_keys(fn_source, inferred_keys)
        type_hints = {}
        if module_obj is not None:
            try:
                fn_obj = getattr(module_obj, fn_name)
                type_hints = get_type_hints(fn_obj, include_extras=True)
            except Exception:
                type_hints = {}

        has_negative_check = bool(fn.get("has_negative_check", False))
        raises_value_error = bool(fn.get("raises_value_error", False))

        arg_candidates = []
        param_flags = _infer_param_guards(fn.get("source", ""), args)
        for a in args:
            hint = type_hints.get(a, annotations.get(a))
            candidates = _build_arg_candidates(a, hint, inferred_keys)
            flags = param_flags.get(a, {})
            if flags.get("divisor") and not flags.get("zero_checked"):
                candidates = [c for c in candidates if not (isinstance(c, (int, float)) and c == 0)]
            if has_negative_check or raises_value_error or flags.get("negative_checked"):
                candidates = [c for c in candidates if not (isinstance(c, (int, float)) and c < 0)]
            if not candidates:
                candidates = [build_safe_arg_value(a, hint, inferred_keys)]
            arg_candidates.append(candidates)

        typical_call = ", ".join(_format_arg_value(vals[0]) for vals in arg_candidates) if args else ""
        alt_call_1 = ", ".join(_format_arg_value((vals[1] if len(vals) > 1 else vals[0])) for vals in arg_candidates) if args else ""
        alt_call_2 = ", ".join(_format_arg_value((vals[2] if len(vals) > 2 else vals[0])) for vals in arg_candidates) if args else ""

        has_print = bool(fn.get("has_print", False))
        returns_count = int(fn.get("returns_count", 0))
        print_strings = fn.get("print_strings", [])

        if has_print:
            lines.append(f"def test_{safe_fn}_prints_or_runs(capsys):")
            if args:
                print_call = _build_print_call_args(
                    args,
                    arg_candidates,
                    annotations,
                    inferred_keys,
                    fn_source,
                    print_strings,
                )
                lines.append(f"    {fn_name}({print_call})")
            else:
                lines.append(f"    {fn_name}()")
            lines.append("    captured = capsys.readouterr()")
            if print_strings:
                lines.append(f"    assert {print_strings[0]!r} in captured.out")
            else:
                lines.append("    assert captured.out != ''")
            lines.append("")

        if returns_count == 0:
            lines.append(f"def test_{safe_fn}_runs_without_exception():")
            if args:
                lines.append(f"    {fn_name}({typical_call})")
            else:
                lines.append(f"    {fn_name}()")
            lines.append("    assert True")
            lines.append("")

        else:
            lines.append(f"def test_{safe_fn}_typical_returns_value():")
            call = f"{fn_name}({typical_call})" if args else f"{fn_name}()"
            lines.append(f"    result = {call}")
            lines.append("    assert result is not None")
            lines.append("")

            lines.append(f"def test_{safe_fn}_edge_case_returns_value():")
            call2 = f"{fn_name}({alt_call_1})" if args else f"{fn_name}()"
            lines.append(f"    result = {call2}")
            lines.append("    assert result is not None")
            lines.append("")

            if fn.get("has_for") or fn.get("has_while") or fn.get("has_if") or returns_count >= 2:
                lines.append(f"def test_{safe_fn}_additional_case_returns_value():")
                call3 = f"{fn_name}({alt_call_2})" if args else f"{fn_name}()"
                lines.append(f"    result = {call3}")
                lines.append("    assert result is not None")
                lines.append("")

        if raises_value_error or (negative_dict_keys and raises_value_error):
            neg_arg_index = None
            numeric_negative_checked = False
            for idx, a in enumerate(args):
                flags = param_flags.get(a, {})
                hint = type_hints.get(a, annotations.get(a))
                if flags.get("negative_checked"):
                    neg_arg_index = idx
                    numeric_negative_checked = True
                    break
                if _is_numeric_param(a, hint):
                    neg_arg_index = idx
                    break
            dict_neg_index = None
            if negative_dict_keys and raises_value_error:
                for idx, a in enumerate(args):
                    hint = type_hints.get(a, annotations.get(a))
                    kind = _normalize_annotation(hint)
                    if kind in {"list_dict", "dict"}:
                        dict_neg_index = idx
                        break
            if dict_neg_index is not None and not numeric_negative_checked:
                hint = type_hints.get(args[dict_neg_index], annotations.get(args[dict_neg_index]))
                kind = _normalize_annotation(hint)
                base = _build_dict_from_keys(inferred_keys)
                for key in negative_dict_keys:
                    if key in base:
                        base[key] = -1
                neg_value = [base] if kind == "list_dict" else base
                neg_args = []
                for jdx, vals in enumerate(arg_candidates):
                    if jdx == dict_neg_index:
                        neg_args.append(_format_arg_value(neg_value))
                    else:
                        neg_args.append(_format_arg_value(vals[0]))
                neg_call = ", ".join(neg_args)
                lines.append(f"def test_{safe_fn}_negative_raises_value_error():")
                lines.append("    with pytest.raises(ValueError):")
                lines.append(f"        {fn_name}({neg_call})")
                lines.append("")
            elif neg_arg_index is not None:
                neg_args = []
                for idx, vals in enumerate(arg_candidates):
                    if idx == neg_arg_index:
                        hint = type_hints.get(args[idx], annotations.get(args[idx]))
                        kind = _normalize_annotation(hint)
                        neg_value = -1.0 if kind == "float" else -1
                        neg_args.append(_format_arg_value(neg_value))
                    else:
                        neg_args.append(_format_arg_value(vals[0]))
                neg_call = ", ".join(neg_args)
                lines.append(f"def test_{safe_fn}_negative_raises_value_error():")
                lines.append("    with pytest.raises(ValueError):")
                lines.append(f"        {fn_name}({neg_call})")
                lines.append("")

    return "\n".join(lines)


def save_tests(pytest_code: str, output_path: Path) -> Path:
    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(pytest_code, encoding="utf-8")
    return output_path
