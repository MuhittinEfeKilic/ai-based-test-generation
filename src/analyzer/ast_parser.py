import ast
from dataclasses import dataclass
from typing import List


@dataclass
class FunctionInfo:
    name: str
    args: List[str]
    has_if: bool
    has_for: bool
    has_while: bool
    returns_count: int
    has_print: bool


class ASTParser:
    def parse_file(self, file_path: str) -> ast.AST:
        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()
        return ast.parse(source)

    def extract_functions(self, tree: ast.AST) -> List[FunctionInfo]:
        functions: List[FunctionInfo] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                args = [a.arg for a in node.args.args]

                has_if = any(isinstance(n, ast.If) for n in ast.walk(node))
                has_for = any(isinstance(n, ast.For) for n in ast.walk(node))
                has_while = any(isinstance(n, ast.While) for n in ast.walk(node))
                returns_count = sum(isinstance(n, ast.Return) for n in ast.walk(node))

                # Detect print(...) calls
                has_print = any(
                    isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Name)
                    and n.func.id == "print"
                    for n in ast.walk(node)
                )

                functions.append(
                    FunctionInfo(
                        name=node.name,
                        args=args,
                        has_if=has_if,
                        has_for=has_for,
                        has_while=has_while,
                        returns_count=returns_count,
                        has_print=has_print,
                    )
                )

        return functions
