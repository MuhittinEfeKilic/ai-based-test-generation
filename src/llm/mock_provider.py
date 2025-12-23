from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class FnSig:
    name: str
    args: List[str]
    has_print: bool = False


class MockLLMProvider:
    def _extract_module_import(self, prompt: str) -> Optional[str]:
        m = re.search(r"^TARGET_MODULE_IMPORT=(.+)$", prompt, flags=re.MULTILINE)
        return m.group(1).strip() if m else None

    def _extract_signatures(self, prompt: str) -> List[FnSig]:
        sigs: List[FnSig] = []
        sig_by_name = {}
        seen = set()
        last_name = None

        for line in prompt.splitlines():
            m = re.match(r"^Function:\s*([a-zA-Z_]\w*)\s*\((.*?)\)\s*$", line)
            if m:
                fname, argblob = m.group(1), m.group(2)
                if fname in seen:
                    last_name = fname
                    continue
                seen.add(fname)
                last_name = fname

                argblob = argblob.strip()
                if not argblob:
                    args = []
                else:
                    args = [a.strip() for a in argblob.split(",") if a.strip()]

                sig = FnSig(name=fname, args=args, has_print=False)
                sigs.append(sig)
                sig_by_name[fname] = sig
                continue

            m = re.match(r"^HasPrint:\s*(true|false)\s*$", line, flags=re.IGNORECASE)
            if m and last_name and last_name in sig_by_name:
                sig_by_name[last_name].has_print = (m.group(1).lower() == "true")

        return sigs

    def _looks_like_print_function(self, sig: FnSig) -> bool:
        if sig.has_print:
            return True
        return any(k in sig.name.lower() for k in ["print", "greet", "log", "echo", "show"])

    def _value_for_arg(self, arg: str) -> str:
        a = arg.lower()

        if a in {"n", "count", "times", "time", "k", "num"} or "times" in a:
            return "2"

        if a in {"b", "denom", "denominator", "divisor"} or "div" in a:
            return "2"

        if "list" in a or "arr" in a or "nums" in a or "numbers" in a or "items" in a:
            return "[1, 2, 3, 4]"

        if "name" in a or "text" in a or "msg" in a or "str" in a:
            return "'Alice'"

        if "age" in a:
            return "20"

        return "1"

    def _build_call(self, sig: FnSig) -> str:
        if not sig.args:
            return f"{sig.name}()"
        values = [self._value_for_arg(a) for a in sig.args]
        return f"{sig.name}({', '.join(values)})"

    def generate_tests(self, prompt: str) -> str:
        module_import = self._extract_module_import(prompt)
        sigs = self._extract_signatures(prompt)

        lines: List[str] = []
        lines.append("import pytest")

        if module_import and sigs:
            imports = ", ".join(s.name for s in sigs)
            lines.append(f"from {module_import} import {imports}")
        lines.append("")

        if not sigs:
            lines.append("def test_generated_by_mock_llm_smoke():")
            lines.append("    assert True")
            lines.append("")
            return "\n".join(lines)

        for sig in sigs:
            call_expr = self._build_call(sig)

            if self._looks_like_print_function(sig):
                lines.append(f"def test_{sig.name}_prints_something(capsys):")
                lines.append(f"    {call_expr}")
                lines.append("    captured = capsys.readouterr()")
                lines.append("    assert captured.out is not None")
                lines.append("    assert len(captured.out) >= 0")
                lines.append("")
            else:
                lines.append(f"def test_{sig.name}_returns_or_runs():")
                lines.append(f"    result = {call_expr}")
                lines.append("    assert result is not None or result is None")
                lines.append("")

        return "\n".join(lines)
