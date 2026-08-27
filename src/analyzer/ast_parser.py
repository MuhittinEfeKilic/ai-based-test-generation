import ast
from dataclasses import dataclass, field
from typing import Dict, List, Union

FunctionNode = Union[ast.FunctionDef, ast.AsyncFunctionDef]


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
    is_async: bool = False
    defaults: Dict[str, str] = field(default_factory=dict)


class ASTParser:
    def parse_file(self, file_path: str) -> tuple[ast.AST, str]:
        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()
        return ast.parse(source), source

    def extract_functions(self, tree: ast.AST, source: str) -> List[FunctionInfo]:
        """Collect module-level functions only.

        Methods and nested functions are deliberately skipped: the generator
        emits ``from <module> import <name>``, which only resolves for names
        bound at module scope.
        """
        functions: List[FunctionInfo] = []

        for node in getattr(tree, "body", []):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions.append(self._describe(node, source))

        return functions

    def extract_classes(self, tree: ast.AST) -> List[str]:
        """Names of module-level classes (their methods are not test targets)."""
        return [n.name for n in getattr(tree, "body", []) if isinstance(n, ast.ClassDef)]

    def count_methods(self, tree: ast.AST) -> int:
        """How many functions are skipped because they live inside a class."""
        total = 0
        for node in getattr(tree, "body", []):
            if isinstance(node, ast.ClassDef):
                total += sum(
                    isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                    for child in node.body
                )
        return total

    def _describe(self, node: FunctionNode, source: str) -> FunctionInfo:
        args = [a.arg for a in node.args.args]
        annotations: Dict[str, str | None] = {}
        for a in node.args.args:
            if a.annotation is not None:
                annotations[a.arg] = ast.get_source_segment(source, a.annotation)
            else:
                annotations[a.arg] = None

        # Defaults bind to the *last* N positional args.
        defaults: Dict[str, str] = {}
        if node.args.defaults:
            for arg, default in zip(node.args.args[-len(node.args.defaults):], node.args.defaults):
                rendered = ast.get_source_segment(source, default)
                if rendered:
                    defaults[arg.arg] = rendered

        has_if = any(isinstance(n, ast.If) for n in ast.walk(node))
        has_for = any(isinstance(n, (ast.For, ast.AsyncFor)) for n in ast.walk(node))
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

        return FunctionInfo(
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
            is_async=isinstance(node, ast.AsyncFunctionDef),
            defaults=defaults,
        )
