AI-Based Automated Test Generation System

This project is an AI-assisted automated test generation prototype for Python codebases.
The system analyzes target Python source files, automatically generates pytest-compatible unit tests, executes them, and reports test coverage using coverage.py.

The main goal of the project is to demonstrate how AST-based static analysis and LLM-assisted reasoning can be combined to reduce manual test-writing effort.

Key Features
-Static code analysis using Python AST
-Automatic pytest test generation
-Support for:
    Branches and edge cases
    Exception paths
    print() output testing via capsys
-Test execution via pytest
-Code coverage analysis and HTML report generation
-Interactive Streamlit-based user interface

Requirements
-Python 3.11
-pip
All required Python libraries are listed in requirements.txt.

Setup Instructions
    -Create and activate virtual environment
        Windows:
                python -m venv .venv
                .venv\Scripts\activate
        macOS/Linux:
                python3 -m venv .venv
                source .venv/bin/activate
    -Install Dependencies
        pip install -r requirements.txt
    -Running
        Start the Streamlit UI:
            streamlit run src/app.py
After the application starts:
    -Select or upload a target Python file
    -Generate tests
    -Run tests
    -Run coverage analysis
    -All results are shown directly in the UI.
Running Tests Manually (CLI):
Run pytest:
    pytest -q data/generated_tests/test_generated_from_ui.py
Run coverage:
    python -m coverage run \
        --source=data/sample_code \
        -m pytest data/generated_tests/test_generated_from_ui.py -q

Show coverage summary:
    python -m coverage report -m
Generate HTML coverage report:
    python -m coverage html
The HTML report will be available under:
    htmlcov/index.html