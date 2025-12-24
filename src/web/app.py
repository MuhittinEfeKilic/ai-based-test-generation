import sys
import time
import shutil
from pathlib import Path
import streamlit as st

#  PATHS
SRC_DIR = Path(__file__).resolve().parents[1]      # ./src
PROJECT_ROOT = SRC_DIR.parent                      # ./project_root
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from analyzer.code_analyzer import CodeAnalyzer
from test_generator.prompt_builder import build_test_plan, build_llm_prompt
from test_generator.test_generator import generate_pytest_code, save_tests
from cov_tools.coverage_analyzer import CoverageAnalyzer

# LLM layer
from llm import LLMConfig, generate_with_optional_llm

#Editor with line numbers
try:
    from streamlit_ace import st_ace
    ACE_AVAILABLE = True
except Exception:
    ACE_AVAILABLE = False


def clean_artifacts(project_root: Path) -> dict:
    data_dir = project_root / "data"
    sample_dir = data_dir / "sample_code"
    uploads_dir = data_dir / "uploads"
    coverage_dir = data_dir / "coverage_html"
    generated_tests_dir = project_root / "tests" / "generated"
    legacy_generated_dir = data_dir / "generated_tests"

    deleted = {
        "tmp_targets": 0,
        "uploads": 0,
        "coverage_html": False,
        "generated_test_file": False,
        "errors": [],
    }

    #tmp_target_#.py creation
    try:
        if sample_dir.exists():
            for p in sample_dir.glob("tmp_target_*.py"):
                p.unlink(missing_ok=True)
                deleted["tmp_targets"] += 1
    except Exception as e:
        deleted["errors"].append(f"tmp_targets: {e}")

    #2)uploads/
    try:
        if uploads_dir.exists():
            for p in uploads_dir.glob("*"):
                if p.is_file():
                    p.unlink(missing_ok=True)
                    deleted["uploads"] += 1
                elif p.is_dir():
                    shutil.rmtree(p, ignore_errors=True)
    except Exception as e:
        deleted["errors"].append(f"uploads: {e}")

    # 3)coverage_html/
    try:
        if coverage_dir.exists():
            shutil.rmtree(coverage_dir, ignore_errors=True)
            deleted["coverage_html"] = True
    except Exception as e:
        deleted["errors"].append(f"coverage_html: {e}")

    # 4)generated test file
    try:
        gen_file = generated_tests_dir / "test_generated_from_ui.py"
        legacy_file = legacy_generated_dir / "test_generated_from_ui.py"
        if gen_file.exists():
            gen_file.unlink(missing_ok=True)
            deleted["generated_test_file"] = True
        if legacy_file.exists():
            legacy_file.unlink(missing_ok=True)
            deleted["generated_test_file"] = True
    except Exception as e:
        deleted["errors"].append(f"generated_test_file: {e}")

    return deleted


def get_temperature(label: str) -> float:
    temp_map = {"Low": 0.1, "Medium": 0.4, "High": 0.8}
    return temp_map.get(label, 0.2)


def sidebar_api_key(use_llm: bool, label: str, secret_name: str) -> str | None:
    """
    If secret exists -> do not render password input (avoids extra eye icon in most cases).
    Else -> show password input (Streamlit eye is unavoidable; browser password manager may add its own).
    """
    secret_val = st.secrets.get(secret_name, None)
    if secret_val:
        st.sidebar.success(f"{label}: loaded from secrets")
        return secret_val

    return st.sidebar.text_input(
        label,
        type="password",
        value="",
        disabled=not use_llm
    ).strip() or None


st.set_page_config(page_title="AI Test Generator Prototype", layout="wide")
st.title("AI-Based Automated Test Generation System (Prototype)")
st.caption("Paste/Upload Python code → Analyze → Generate pytest → Run coverage")

data_dir = PROJECT_ROOT / "data"
sample_dir = data_dir / "sample_code"
generated_dir = PROJECT_ROOT / "tests" / "generated"
coverage_html = data_dir / "coverage_html" / "index.html"
uploads_dir = data_dir / "uploads"

sample_dir.mkdir(parents=True, exist_ok=True)
uploads_dir.mkdir(parents=True, exist_ok=True)

#Sidebar
st.sidebar.header("Input")

mode = st.sidebar.radio(
    "Choose input mode",
    ["Paste code", "Upload a .py file"]
)

uploaded = None
if mode == "Upload a .py file":
    uploaded = st.sidebar.file_uploader("Upload Python file", type=["py"])

#Generation Settings (LLM optional)
st.sidebar.divider()
st.sidebar.header("Generation Settings")

use_llm = st.sidebar.checkbox("Use LLM (optional)", value=False)

#Providers requested
PROVIDERS = ["mock", "gemini", "openai", "claude", "deepseek"]

#Provider label above dropdown
st.sidebar.markdown("**LLM Provider**")
provider = st.sidebar.selectbox(
    label="LLM Provider (hidden)",
    options=PROVIDERS,
    index=0,
    disabled=not use_llm,
    label_visibility="collapsed",
)

#Creativity (Complexity)
temp_label = st.sidebar.radio(
    "Creativity",
    options=["Low", "Medium", "High"],
    index=0,
    disabled=not use_llm,
    horizontal=True
)
temperature = get_temperature(temp_label)

#Auto model selection (if no user model selection)
DEFAULT_MODELS = {
    "mock": "mock",
    "openai": "gpt-4o-mini",
    "gemini": "gemini-1.5-flash",
    "claude": "claude-3-5-sonnet-latest",
    "deepseek": "deepseek-chat",
}
model_name = DEFAULT_MODELS.get(provider, "mock")

# Provider-specific settings
api_key = None
base_url = None

if provider == "openai":
    api_key = sidebar_api_key(use_llm, "OpenAI API Key", "OPENAI_API_KEY")
    base_url = st.sidebar.text_input("OpenAI Base URL (optional)", value="", disabled=not use_llm).strip() or None

elif provider == "gemini":
    api_key = sidebar_api_key(use_llm, "Gemini API Key", "GEMINI_API_KEY")

elif provider == "claude":
    api_key = sidebar_api_key(use_llm, "Claude API Key", "ANTHROPIC_API_KEY")

elif provider == "deepseek":
    api_key = sidebar_api_key(use_llm, "DeepSeek API Key", "DEEPSEEK_API_KEY")
    base_url = st.sidebar.text_input("DeepSeek Base URL (optional)", value="", disabled=not use_llm).strip() or None

# mock => no key/base_url needed

st.sidebar.caption("If LLM fails, the system automatically falls back to rule-based generation.")

# Run/Clean
st.sidebar.divider()
run_btn = st.sidebar.button("Run Analysis → Generate Tests → Coverage", type="primary")

st.sidebar.divider()
if st.sidebar.button("🧹 Clean temp files & reports"):
    result = clean_artifacts(PROJECT_ROOT)
    if result["errors"]:
        st.sidebar.error("Clean completed with errors:")
        for err in result["errors"]:
            st.sidebar.write(f"- {err}")
    else:
        st.sidebar.success(
            f"Cleaned: tmp_targets={result['tmp_targets']}, "
            f"uploads={result['uploads']}, "
            f"coverage_html={result['coverage_html']}, "
            f"generated_test_file={result['generated_test_file']}"
        )

#Main layout
col1, col2 = st.columns(2)

pasted_code = ""
target_path = None
module_import = None

with col1:
    st.subheader("Source Code")

    if mode == "Paste code":
        if ACE_AVAILABLE:
            st.caption("Editor: ACE (syntax highlighting + line numbers).")
            pasted_code = st_ace(
                value="",
                language="python",
                theme="monokai",
                key="ace_paste_editor",
                height=460,
                font_size=14,
                tab_size=4,
                wrap=True,
                show_gutter=True,
                show_print_margin=False,
                auto_update=True,
            )
        else:
            st.caption("Tip: Install 'streamlit-ace' for syntax highlighting + line numbers.")
            pasted_code = st.text_area(
                "Paste your Python code below",
                height=420,
                placeholder="def foo(x):\n    return x + 1\n",
                key="paste_code_main_fallback"
            )

        if pasted_code and pasted_code.strip():
            target_path = uploads_dir / "pasted_input.py"
            target_path.write_text(pasted_code, encoding="utf-8")
        else:
            target_path = None

    else:  #Upload mode
        if uploaded is not None:
            target_path = uploads_dir / uploaded.name
            target_path.write_bytes(uploaded.getvalue())

        if target_path and target_path.exists():
            st.code(target_path.read_text(encoding="utf-8"), language="python")
        else:
            st.info("Upload a .py file from the sidebar.")

with col2:
    st.subheader("Outputs")

    if run_btn:
        if mode == "Paste code" and (not pasted_code or not pasted_code.strip()):
            st.error("No pasted code found. Please paste Python code in the editor on the left.")
            st.stop()

        if mode == "Upload a .py file" and (not target_path or not target_path.exists()):
            st.error("No valid file uploaded.")
            st.stop()

        try:
            unique_stem = f"tmp_target_{int(time.time())}"
            tmp_target = sample_dir / f"{unique_stem}.py"
            tmp_target.write_text(target_path.read_text(encoding="utf-8"), encoding="utf-8")
            module_import = f"data.sample_code.{unique_stem}"

            st.info(f"Target module: {module_import}")

            #1)Analysis
            analyzer = CodeAnalyzer()
            analysis = analyzer.analyze_as_dict(str(target_path))
            st.markdown("### 1) Analysis Output")
            st.json(analysis)

            #2)Test plan
            test_plan = build_test_plan(analysis)
            st.markdown("### 2) Test Plan")
            st.json(test_plan)

            #3)Prompt
            prompt = build_llm_prompt(test_plan)
            prompt = f"TARGET_MODULE_IMPORT={module_import}\n" + prompt

            st.markdown("### 3) LLM Prompt")
            st.code(prompt)

            #4)Generate pytest code
            llm_cfg = LLMConfig(
                provider=provider if use_llm else "mock",
                api_key=api_key,
                model=model_name,
                temperature=float(temperature),
                timeout_sec=30,
                base_url=base_url,
            )

            generated_source = "rule-based"
            llm_error = None
            coverage_code = None

            if use_llm:
                llm_result = generate_with_optional_llm(prompt, llm_cfg)
                if llm_result.source == "llm" and llm_result.code.strip():
                    pytest_code = llm_result.code
                    generated_source = "llm"
                    coverage_code = generate_pytest_code(test_plan=test_plan, module_import=module_import)
                else:
                    llm_error = llm_result.error
                    pytest_code = generate_pytest_code(test_plan=test_plan, module_import=module_import)
                    generated_source = "fallback(rule-based)"
            else:
                pytest_code = generate_pytest_code(test_plan=test_plan, module_import=module_import)
                generated_source = "rule-based"
            if coverage_code is None:
                coverage_code = pytest_code

            st.markdown("### 4) Generated Pytest Code")
            st.info(f"Generation Source: {generated_source}")
            if llm_error:
                st.warning(f"LLM not used: {llm_error}")
            if generated_source == "llm":
                st.info("Coverage will use safe rule-based tests to avoid brittle inputs.")

            st.code(pytest_code, language="python")

            #5)Save tests
            generated_dir.mkdir(parents=True, exist_ok=True)
            out_file = generated_dir / "test_generated_from_ui.py"
            saved_path = save_tests(coverage_code, out_file)
            st.success(f"Saved test file: {saved_path}")

            st.download_button(
                label="Download generated test file",
                data=coverage_code,
                file_name="test_generated_from_ui.py",
                mime="text/x-python",
            )

            #6)Coverage
            st.markdown("### 5) Coverage")
            cov = CoverageAnalyzer()
            cov.run_coverage(
                project_root=PROJECT_ROOT,
                test_file=saved_path,
                source_dir=sample_dir,
                html=True,
            )

            if coverage_html.exists():
                st.success("Coverage completed")
                st.info(f"HTML report path: {coverage_html}")
            else:
                st.warning("Coverage completed, but HTML report file was not found.")

        except Exception as e:
            st.error("Run failed")
            st.exception(e)
