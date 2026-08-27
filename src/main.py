"""Command-line walkthrough of the full pipeline.

    python src/main.py [target.py]

Defaults to the bundled sample module. Mirrors what the Streamlit UI does:
analyze -> plan -> prompt -> generate -> save -> coverage.
"""

import argparse
import sys
from pathlib import Path
from pprint import pprint

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from analyzer.code_analyzer import CodeAnalyzer
from test_generator.prompt_builder import build_test_plan, build_llm_prompt
from test_generator.test_generator import generate_pytest_code, save_tests
from cov_tools.coverage_analyzer import CoverageAnalyzer

DEFAULT_TARGET = PROJECT_ROOT / "data" / "sample_code" / "example.py"


def module_import_for(target: Path) -> str:
    """Dotted import path for a file inside the project, e.g. data.sample_code.example."""
    relative = target.resolve().relative_to(PROJECT_ROOT)
    return ".".join(relative.with_suffix("").parts)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "target",
        nargs="?",
        default=str(DEFAULT_TARGET),
        help="Python file to generate tests for (must live inside the project).",
    )
    args = parser.parse_args()

    target = Path(args.target).resolve()
    if not target.exists():
        print(f"Target not found: {target}", file=sys.stderr)
        return 1

    # 1) Code analysis
    analyzer = CodeAnalyzer()
    analysis = analyzer.analyze_as_dict(str(target))

    print("\n================ ANALYSIS OUTPUT ================\n")
    print(f"Analyzing: {target}")
    pprint(analysis)

    if not analysis:
        print("\nNo module-level functions found; nothing to generate.")
        return 1

    # 2) Test plan
    test_plan = build_test_plan(analysis)
    print("\n================ TEST PLAN ================\n")
    pprint(test_plan)

    # 3) AI prompt (rendered here, sent to a provider only from the UI)
    module_import = module_import_for(target)
    prompt = f"TARGET_MODULE_IMPORT={module_import}\n" + build_llm_prompt(test_plan)
    print("\n================ AI PROMPT ================\n")
    print(prompt)

    # 4) Rule-based pytest generation
    pytest_code = generate_pytest_code(test_plan=test_plan, module_import=module_import)
    print("\n================ GENERATED PYTEST CODE ================\n")
    print(pytest_code)

    output_file = PROJECT_ROOT / "tests" / "generated" / "test_example_generated.py"
    saved_path = save_tests(pytest_code, output_file)
    print("\n================ FILE SAVED ================\n")
    print(f"Generated test file saved to:\n{saved_path}")

    # 5) Coverage
    print("\n================ COVERAGE ================\n")
    result = CoverageAnalyzer().run_coverage(
        project_root=PROJECT_ROOT,
        test_file=saved_path,
        source_dir=target.parent,
        target_file=target,
        html=True,
    )
    print(result.pytest_output)
    print(result.report)
    if result.html_dir:
        print(f"HTML coverage report generated at: {result.html_dir}")

    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
