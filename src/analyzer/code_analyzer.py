from dataclasses import asdict
from typing import List, Dict

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
