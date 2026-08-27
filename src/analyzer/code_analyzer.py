from dataclasses import asdict
from typing import Dict, List

from analyzer.ast_parser import ASTParser, FunctionInfo


class CodeAnalyzer:
    def __init__(self) -> None:
        self._parser = ASTParser()

    def analyze(self, file_path: str) -> List[FunctionInfo]:
        tree, source = self._parser.parse_file(file_path)
        return self._parser.extract_functions(tree, source)

    def analyze_as_dict(self, file_path: str) -> List[Dict]:
        infos = self.analyze(file_path)
        return [asdict(i) for i in infos]

    def analyze_module(self, file_path: str) -> Dict:
        """Everything the UI needs about a file in a single parse.

        `skipped_methods` is reported so the summary can explain why a file full
        of classes produces no tests.
        """
        tree, source = self._parser.parse_file(file_path)
        functions = self._parser.extract_functions(tree, source)
        return {
            "functions": [asdict(i) for i in functions],
            "classes": self._parser.extract_classes(tree),
            "skipped_methods": self._parser.count_methods(tree),
        }
