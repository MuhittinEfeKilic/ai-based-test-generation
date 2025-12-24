from pprint import pprint
from pathlib import Path

from analyzer.code_analyzer import CodeAnalyzer
from test_generator.prompt_builder import build_test_plan, build_llm_prompt
from test_generator.test_generator import generate_pytest_code, save_tests
from cov_tools.coverage_analyzer import CoverageAnalyzer  # <-- updated import


def main():
    project_root = Path(__file__).resolve().parents[1]
    sample_file = project_root / "data" / "sample_code" / "example.py"

    #Week 3: Code Analysis / Test Plan
    analyzer = CodeAnalyzer()
    analysis = analyzer.analyze_as_dict(str(sample_file))

    print("\n================ ANALYSIS OUTPUT ================\n")
    print(f"Analyzing: {sample_file}")
    pprint(analysis)
    test_plan = build_test_plan(analysis)

    print("\n================ TEST PLAN ================\n")
    pprint(test_plan)

    # Week 4: LLM Prompt
    prompt = build_llm_prompt(test_plan)
    print("\n================ LLM PROMPT (Week 4) ================\n")
    print(prompt)

    # Week 4: Pytest Code Generation
    module_import = "data.sample_code.example"
    pytest_code = generate_pytest_code(test_plan=test_plan, module_import=module_import)

    print("\n================ GENERATED PYTEST CODE ================\n")
    print(pytest_code)

    # Save generated tests
    output_file = project_root / "data" / "generated_tests" / "test_example_generated.py"

    print("\n--- DEBUG: about to save tests ---")
    print("Will save to:", output_file)

    saved_path = save_tests(pytest_code, output_file)

    print("\n================ FILE SAVED ================\n")
    print(f"Generated test file saved to:\n{saved_path}")

    print("\n--- DEBUG PATHS ---")
    print("Output file should be:", saved_path)
    print("Parent exists?:", saved_path.parent.exists())
    print("File exists?  :", saved_path.exists())

    # Week 5: Coverage Measurement
    print("\n================ COVERAGE (Week 5) ================\n")

    cov = CoverageAnalyzer()
    cov.run_coverage(
        project_root=project_root,
        test_file=saved_path,
        source_dir=project_root / "data" / "sample_code",
        html=True,
    )


if __name__ == "__main__":
    main()
