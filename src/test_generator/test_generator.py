from pathlib import Path
from typing import Dict, List


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
    if kind == "float_divisor":
        return ["0", "2"]
    if kind == "int":
        return ["0", "1", "2", "-1"]
    return ["1"]


def generate_pytest_code(test_plan: Dict, module_import: str) -> str:
    lines: List[str] = []

    # --- imports & path fix ---
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

    for fn in test_plan["functions"]:
        fn_name = fn["name"]
        args = fn["args"]
        safe_fn = _sanitize_name(fn_name)

        # Build sample arg literals
        arg_kinds = [_guess_kind(a) for a in args]
        arg_values = [_sample_values(k) for k in arg_kinds]

        typical_call = ", ".join(vals[0] for vals in arg_values) if args else ""
        alt_call_1 = ", ".join((vals[1] if len(vals) > 1 else vals[0]) for vals in arg_values) if args else ""
        alt_call_2 = ", ".join((vals[2] if len(vals) > 2 else vals[0]) for vals in arg_values) if args else ""

        has_print = bool(fn.get("has_print", False))
        returns_count = int(fn.get("returns_count", 0))

        # 1) print varsa: capsys
        if has_print:
            lines.append(f"def test_{safe_fn}_prints_or_runs(capsys):")
            if args:
                lines.append(f"    {fn_name}({typical_call})")
            else:
                lines.append(f"    {fn_name}()")
            lines.append("    captured = capsys.readouterr()")
            lines.append("    assert isinstance(captured.out, str)")
            lines.append("")

        # 2) return yoksa: sadece exception atmadan çalışsın (capsys yok)
        elif returns_count == 0:
            lines.append(f"def test_{safe_fn}_runs_without_exception():")
            if args:
                lines.append(f"    {fn_name}({typical_call})")
            else:
                lines.append(f"    {fn_name}()")
            lines.append("    assert True")
            lines.append("")

        # 3) return varsa: return testleri
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

    return "\n".join(lines)


def save_tests(pytest_code: str, output_path: Path) -> Path:
    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(pytest_code, encoding="utf-8")
    return output_path
