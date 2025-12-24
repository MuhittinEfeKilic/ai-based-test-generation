import ast
from dataclasses import dataclass
from typing import Dict, List


@dataclass
class FunctionInfo:
    name: str
    args: List[str]
    annotations: Dict[str, str | None]
    has_if: bool
    has_for: bool
    has_while: bool
    returns_count: int
    has_print: bool
    print_strings: List[str]
    has_negative_check: bool
    raises_value_error: bool
    source: str


class ASTParser:
    def parse_file(self, file_path: str) -> tuple[ast.AST, str]:
        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()
        return ast.parse(source), source

    def extract_functions(self, tree: ast.AST, source: str) -> List[FunctionInfo]:
        functions: List[FunctionInfo] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                args = [a.arg for a in node.args.args]
                annotations: Dict[str, str | None] = {}
                for a in node.args.args:
                    if a.annotation is not None:
                        annotations[a.arg] = ast.get_source_segment(source, a.annotation)
                    else:
                        annotations[a.arg] = None

                has_if = any(isinstance(n, ast.If) for n in ast.walk(node))
                has_for = any(isinstance(n, ast.For) for n in ast.walk(node))
                has_while = any(isinstance(n, ast.While) for n in ast.walk(node))
                returns_count = sum(isinstance(n, ast.Return) for n in ast.walk(node))

                # Detect print() calls
                print_calls = [
                    n
                    for n in ast.walk(node)
                    if isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Name)
                    and n.func.id == "print"
                ]
                has_print = bool(print_calls)

                print_strings: List[str] = []
                for call in print_calls:
                    for arg in call.args:
                        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                            if arg.value:
                                print_strings.append(arg.value)
                        elif isinstance(arg, ast.JoinedStr):
                            parts = []
                            for part in arg.values:
                                if isinstance(part, ast.Constant) and isinstance(part.value, str):
                                    parts.append(part.value)
                            joined = "".join(parts)
                            if joined:
                                print_strings.append(joined)

                has_negative_check = any(
                    isinstance(n, ast.Compare)
                    and any(isinstance(op, (ast.Lt, ast.LtE)) for op in n.ops)
                    and any(
                        isinstance(side, ast.Constant) and side.value == 0
                        for side in [n.left, *n.comparators]
                    )
                    for n in ast.walk(node)
                )
                raises_value_error = any(
                    isinstance(n, ast.Raise)
                    and n.exc is not None
                    and (
                        (isinstance(n.exc, ast.Call) and isinstance(n.exc.func, ast.Name) and n.exc.func.id == "ValueError")
                        or (isinstance(n.exc, ast.Name) and n.exc.id == "ValueError")
                    )
                    for n in ast.walk(node)
                )

                fn_source = ast.get_source_segment(source, node) or ""

                functions.append(
                    FunctionInfo(
                        name=node.name,
                        args=args,
                        annotations=annotations,
                        has_if=has_if,
                        has_for=has_for,
                        has_while=has_while,
                        returns_count=returns_count,
                        has_print=has_print,
                        print_strings=print_strings,
                        has_negative_check=has_negative_check,
                        raises_value_error=raises_value_error,
                        source=fn_source,
                    )
                )

        return functions
