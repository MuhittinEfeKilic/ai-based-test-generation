"""Streamlit front-end: paste/upload code, generate tests, measure coverage.

Security note: the target file is imported and its generated tests are executed
in this process' Python environment. Only feed it code you trust.
"""

import logging
import shutil
import sys
import time
import traceback
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
from web.formatting import (
    count_tests,
    download_name,
    friendly_error,
    function_rows,
    get_temperature,
    mode_label,
)

# LLM layer
from llm import (
    API_KEY_SECRETS,
    DEFAULT_MODELS,
    PROVIDERS,
    PROVIDER_LABELS,
    SUPPORTS_BASE_URL,
    LLMConfig,
    generate_with_optional_llm,
)

# Editor with line numbers
try:
    from streamlit_ace import st_ace
    ACE_AVAILABLE = True
except Exception:
    ACE_AVAILABLE = False

log = logging.getLogger(__name__)

GENERATED_TEST_NAME = "test_generated_from_ui.py"

EXAMPLE_CODE = '''def calculate_discount(price, discount):
    if price < 0:
        raise ValueError("Price cannot be negative")

    if discount < 0 or discount > 100:
        raise ValueError("Discount must be between 0 and 100")

    return price * (1 - discount / 100)


def apply_bulk_pricing(items):
    total = 0
    for item in items:
        total += item["quantity"] * item["price"]
    if total > 100:
        return total * 0.9
    return total
'''


# --------------------------------------------------------------------------
# Filesystem helpers
# --------------------------------------------------------------------------

def prune_tmp_targets(sample_dir: Path, keep: Path | None = None) -> int:
    """Delete scratch modules from earlier runs, optionally sparing `keep`."""
    removed = 0
    if not sample_dir.exists():
        return removed
    for p in sample_dir.glob("tmp_target_*.py"):
        if keep is not None and p.resolve() == keep.resolve():
            continue
        p.unlink(missing_ok=True)
        removed += 1
    return removed


def clean_artifacts(project_root: Path) -> dict:
    data_dir = project_root / "data"
    sample_dir = data_dir / "sample_code"
    uploads_dir = data_dir / "uploads"
    coverage_dir = data_dir / "coverage_html"
    generated_tests_dir = project_root / "tests" / "generated"

    deleted = {
        "tmp_targets": 0,
        "uploads": 0,
        "coverage_html": False,
        "generated_test_files": 0,
        "errors": [],
    }

    # 1) scratch copies of the analysed module
    try:
        deleted["tmp_targets"] = prune_tmp_targets(sample_dir)
    except Exception as e:
        deleted["errors"].append(f"tmp_targets: {e}")

    # 2) uploads/
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

    # 3) coverage_html/
    try:
        if coverage_dir.exists():
            shutil.rmtree(coverage_dir, ignore_errors=True)
            deleted["coverage_html"] = True
    except Exception as e:
        deleted["errors"].append(f"coverage_html: {e}")

    # 4) generated test files (UI and CLI both write here)
    try:
        if generated_tests_dir.exists():
            for gen_file in generated_tests_dir.glob("test_*.py"):
                gen_file.unlink(missing_ok=True)
                deleted["generated_test_files"] += 1
    except Exception as e:
        deleted["errors"].append(f"generated_test_files: {e}")

    return deleted


# --------------------------------------------------------------------------
# Small presentation helpers
# --------------------------------------------------------------------------

def read_secret(name: str) -> str | None:
    """Read one entry from .streamlit/secrets.toml, tolerating no file at all."""
    try:
        return st.secrets.get(name, None)
    except Exception:
        # Streamlit raises when no secrets.toml exists; that is not an error here.
        return None


def sidebar_api_key(use_llm: bool, label: str, secret_name: str) -> str | None:
    """Prefer the key from secrets; only prompt for it when there is none."""
    secret_val = read_secret(secret_name)
    if secret_val:
        st.sidebar.success(f"{label}: loaded from secrets")
        return secret_val

    return st.sidebar.text_input(
        label,
        type="password",
        value="",
        disabled=not use_llm,
    ).strip() or None


# --------------------------------------------------------------------------
# Pipeline
# --------------------------------------------------------------------------

def run_pipeline(
    target_path: Path,
    sample_dir: Path,
    generated_dir: Path,
    use_llm: bool,
    llm_cfg: LLMConfig,
    source_name: str | None,
) -> dict:
    """Analyze -> plan -> generate -> save -> coverage. Returns what the UI shows."""
    # A fresh module name per run keeps stale imports out of sys.modules.
    unique_stem = f"tmp_target_{int(time.time())}"
    tmp_target = sample_dir / f"{unique_stem}.py"
    tmp_target.write_text(target_path.read_text(encoding="utf-8"), encoding="utf-8")
    prune_tmp_targets(sample_dir, keep=tmp_target)
    module_import = f"data.sample_code.{unique_stem}"

    overview = CodeAnalyzer().analyze_module(str(target_path))
    analysis = overview["functions"]

    result = {
        "module_import": module_import,
        "overview": overview,
        "analysis": analysis,
        "source_name": source_name,
    }

    if not analysis:
        result["empty"] = True
        return result

    test_plan = build_test_plan(analysis)
    prompt = f"TARGET_MODULE_IMPORT={module_import}\n" + build_llm_prompt(test_plan)

    generation_source = "rule-based"
    llm_error = None
    coverage_code = None

    if use_llm:
        llm_result = generate_with_optional_llm(prompt, llm_cfg)
        if llm_result.source == "llm" and llm_result.code.strip():
            pytest_code = llm_result.code
            generation_source = "ai"
            # Coverage is always measured with the deterministic tests so a
            # brittle model answer cannot distort the metric.
            coverage_code = generate_pytest_code(test_plan=test_plan, module_import=module_import)
        else:
            llm_error = llm_result.error
            pytest_code = generate_pytest_code(test_plan=test_plan, module_import=module_import)
            generation_source = "fallback"
    else:
        pytest_code = generate_pytest_code(test_plan=test_plan, module_import=module_import)

    if coverage_code is None:
        coverage_code = pytest_code

    generated_dir.mkdir(parents=True, exist_ok=True)
    saved_path = save_tests(coverage_code, generated_dir / GENERATED_TEST_NAME)

    coverage = CoverageAnalyzer().run_coverage(
        project_root=PROJECT_ROOT,
        test_file=saved_path,
        source_dir=sample_dir,
        target_file=tmp_target,
        html=True,
    )

    result.update(
        {
            "empty": False,
            "test_plan": test_plan,
            "prompt": prompt,
            "pytest_code": pytest_code,
            "coverage_code": coverage_code,
            "generation_source": generation_source,
            "llm_error": llm_error,
            "saved_path": str(saved_path),
            "coverage": coverage,
        }
    )
    return result


# --------------------------------------------------------------------------
# Page
# --------------------------------------------------------------------------

st.set_page_config(page_title="AI-Powered Python Test Generator", layout="wide")

st.markdown(
    """
    <style>
      .block-container { padding-top: 2.2rem; }
      section[data-testid="stSidebar"] hr { margin: 0.9rem 0; }
      div[data-testid="stMetricValue"] { font-size: 1.6rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("AI-Powered Python Test Generator")
st.caption("Generate pytest tests and coverage reports from Python code in seconds.")
st.caption("Add Python code → Analyze → Generate tests → Review coverage → Download")

data_dir = PROJECT_ROOT / "data"
sample_dir = data_dir / "sample_code"
generated_dir = PROJECT_ROOT / "tests" / "generated"
coverage_html = data_dir / "coverage_html" / "index.html"
uploads_dir = data_dir / "uploads"

sample_dir.mkdir(parents=True, exist_ok=True)
uploads_dir.mkdir(parents=True, exist_ok=True)

st.session_state.setdefault("editor_seed", 0)
st.session_state.setdefault("editor_value", "")
st.session_state.setdefault("last_run", None)
st.session_state.setdefault("last_error", None)

# ---- Sidebar: Input -------------------------------------------------------
st.sidebar.header("Input")

mode = st.sidebar.radio("Source", ["Paste code", "Upload .py"], label_visibility="collapsed")

uploaded = None
if mode == "Upload .py":
    uploaded = st.sidebar.file_uploader("Upload a Python file", type=["py"])

# ---- Sidebar: Test Generation --------------------------------------------
st.sidebar.divider()
st.sidebar.header("Test Generation")

use_llm = st.sidebar.checkbox("Use AI generation", value=False)
st.sidebar.caption(
    "Optional. If AI generation is unavailable, the system falls back to "
    "rule-based test generation."
)

provider = st.sidebar.selectbox(
    "AI provider",
    options=list(PROVIDERS),
    index=0,
    format_func=lambda p: PROVIDER_LABELS.get(p, p),
    disabled=not use_llm,
)

temp_label = st.sidebar.radio(
    "Creativity",
    options=["Low", "Medium", "High"],
    index=0,
    disabled=not use_llm,
    horizontal=True,
)
temperature = get_temperature(temp_label)

default_model = DEFAULT_MODELS.get(provider, "mock")
model_name = st.sidebar.text_input(
    "Model",
    value=default_model,
    disabled=not use_llm,
    help="Override if the default model id is unavailable on your account.",
).strip() or default_model

api_key = None
base_url = None
provider_label = PROVIDER_LABELS.get(provider, provider)

secret_name = API_KEY_SECRETS.get(provider)
if secret_name:
    api_key = sidebar_api_key(use_llm, f"{provider_label} API key", secret_name)

if provider in SUPPORTS_BASE_URL:
    base_url = st.sidebar.text_input(
        f"{provider_label} base URL (optional)",
        value="",
        disabled=not use_llm,
    ).strip() or None

# ---- Sidebar: actions -----------------------------------------------------
st.sidebar.divider()
run_btn = st.sidebar.button("Analyze & Generate Tests", type="primary", width="stretch")

with st.sidebar.expander("Advanced"):
    debug_mode = st.checkbox("Show technical details on error", value=False)
    if st.button("Clean temp files & reports", width="stretch"):
        cleaned = clean_artifacts(PROJECT_ROOT)
        if cleaned["errors"]:
            st.error("Clean completed with errors:")
            for err in cleaned["errors"]:
                st.write(f"- {err}")
        else:
            st.success(
                f"Cleaned: {cleaned['tmp_targets']} scratch modules, "
                f"{cleaned['uploads']} uploads, "
                f"{cleaned['generated_test_files']} test files"
            )

# ---- Main layout ----------------------------------------------------------
col1, col2 = st.columns([1, 1], gap="large")

pasted_code = ""
target_path = None
source_name = None

with col1:
    st.subheader("Python source")

    if mode == "Paste code":
        left, right = st.columns([1, 3])
        with left:
            if st.button("Load example", width="stretch"):
                st.session_state.editor_value = EXAMPLE_CODE
                st.session_state.editor_seed += 1
        with right:
            st.caption("Loads a sample with branches, a loop and validation errors.")

        if ACE_AVAILABLE:
            pasted_code = st_ace(
                value=st.session_state.editor_value,
                language="python",
                theme="tomorrow_night",
                key=f"ace_paste_editor_{st.session_state.editor_seed}",
                height=440,
                font_size=14,
                tab_size=4,
                wrap=True,
                show_gutter=True,
                show_print_margin=False,
                auto_update=True,
            )
        else:
            st.caption("Tip: install 'streamlit-ace' for syntax highlighting and line numbers.")
            pasted_code = st.text_area(
                "Python code",
                value=st.session_state.editor_value,
                height=440,
                placeholder="def foo(x):\n    return x + 1\n",
                key=f"paste_code_fallback_{st.session_state.editor_seed}",
                label_visibility="collapsed",
            )

        if pasted_code and pasted_code.strip():
            target_path = uploads_dir / "pasted_input.py"
            target_path.write_text(pasted_code, encoding="utf-8")

    else:  # Upload mode
        if uploaded is not None:
            target_path = uploads_dir / uploaded.name
            target_path.write_bytes(uploaded.getvalue())
            source_name = uploaded.name

        if target_path and target_path.exists():
            st.code(target_path.read_text(encoding="utf-8"), language="python")
        else:
            st.info("Upload a .py file from the sidebar to get started.")

# ---- Run ------------------------------------------------------------------
if run_btn:
    st.session_state.last_error = None
    if not target_path or not target_path.exists():
        st.session_state.last_run = None
        st.session_state.last_error = {
            "message": "No Python code found. Paste code, load the example, or upload a file.",
            "detail": None,
        }
    else:
        llm_cfg = LLMConfig(
            provider=provider if use_llm else "mock",
            api_key=api_key,
            model=model_name,
            temperature=float(temperature),
            timeout_sec=30,
            base_url=base_url,
        )
        with st.spinner("Analyzing code, generating tests and measuring coverage..."):
            try:
                st.session_state.last_run = run_pipeline(
                    target_path=target_path,
                    sample_dir=sample_dir,
                    generated_dir=generated_dir,
                    use_llm=use_llm,
                    llm_cfg=llm_cfg,
                    source_name=source_name,
                )
            except Exception as exc:  # friendly message here, full detail in the log
                log.exception("Test generation failed")
                st.session_state.last_run = None
                st.session_state.last_error = {
                    "message": friendly_error(exc),
                    "detail": traceback.format_exc(),
                }

# ---- Results --------------------------------------------------------------
with col2:
    st.subheader("Results")

    run = st.session_state.last_run
    error = st.session_state.last_error

    if error:
        st.error(error["message"])
        if debug_mode and error["detail"]:
            st.code(error["detail"], language="text")

    elif run is None:
        st.info("Add Python code or load the example to generate automated pytest tests.")
        st.caption(
            "Generated tests are written to tests/generated/ and executed under "
            "coverage.py. The target module is imported locally, so only run code you trust."
        )

    elif run["empty"]:
        classes = run["overview"]["classes"]
        skipped = run["overview"]["skipped_methods"]
        st.warning("No testable functions found.")
        if classes:
            st.caption(
                f"Found {len(classes)} class(es) with {skipped} method(s). "
                "Only module-level functions can be imported by name, so methods are skipped."
            )
        else:
            st.caption("Add at least one module-level `def` to generate tests.")

    else:
        cov = run["coverage"]
        counts = cov.counts
        label = mode_label(run["generation_source"], PROVIDER_LABELS.get(provider, provider))

        # When the AI wrote the displayed suite, the executed suite is the
        # rule-based one - label the metrics so the two counts cannot be misread
        # as contradicting each other.
        executed_is_shown = run["coverage_code"] == run["pytest_code"]
        passed_label = "Passed" if executed_is_shown else "Passed (rule-based)"

        m1, m2, m3, m4 = st.columns(4)
        m1.metric(
            "Tests",
            count_tests(run["pytest_code"]),
            help="Test functions in the suite shown under 'Generated tests'.",
        )
        m2.metric(
            passed_label,
            f"{counts.get('passed', 0)}/{cov.total_tests}",
            help="Results of the suite that was executed under coverage.py.",
        )
        m3.metric("Coverage", f"{cov.percent:.0f}%" if cov.percent is not None else "n/a")
        m4.metric("Mode", label)

        if run["llm_error"]:
            st.warning(f"AI generation unavailable, used rule-based tests: {run['llm_error']}")
        elif cov.ok:
            st.success("Tests generated and executed successfully.")
        else:
            st.warning("Some generated tests failed. See the Coverage tab for details.")

        tab_analysis, tab_tests, tab_coverage = st.tabs(
            ["Analysis", "Generated tests", "Coverage"]
        )

        with tab_analysis:
            overview = run["overview"]
            plan_functions = run["test_plan"]["functions"]
            a1, a2, a3 = st.columns(3)
            a1.metric("Functions", len(overview["functions"]))
            a2.metric("Classes", len(overview["classes"]))
            a3.metric(
                "Test targets",
                sum(len(fn.get("recommended_scenarios", [])) for fn in plan_functions),
            )

            if overview["skipped_methods"]:
                st.caption(
                    f"{overview['skipped_methods']} class method(s) skipped - only "
                    "module-level functions are importable by name."
                )

            st.dataframe(function_rows(plan_functions), width="stretch", hide_index=True)

            with st.expander("Test plan (JSON)"):
                st.json(run["test_plan"])
            with st.expander("Raw analysis (JSON)"):
                st.json(run["analysis"])
            with st.expander("AI prompt"):
                st.code(run["prompt"], language="text")

        with tab_tests:
            st.caption(f"Target module: `{run['module_import']}`")
            st.code(run["pytest_code"], language="python")

            st.download_button(
                "Download generated tests",
                data=run["pytest_code"],
                file_name=download_name(run["source_name"]),
                mime="text/x-python",
                type="primary",
            )

            if run["coverage_code"] != run["pytest_code"]:
                st.caption(
                    "Coverage was measured with the deterministic rule-based suite "
                    "so a brittle AI answer cannot distort the metric."
                )
                st.download_button(
                    "Download rule-based tests (used for coverage)",
                    data=run["coverage_code"],
                    file_name="test_rule_based.py",
                    mime="text/x-python",
                )

            st.caption(f"Saved to: `{run['saved_path']}`")

        with tab_coverage:
            if cov.percent is not None:
                st.metric("Line coverage", f"{cov.percent:.0f}%")
                st.progress(min(cov.percent / 100, 1.0))

            c1, c2, c3 = st.columns(3)
            c1.metric("Passed", counts.get("passed", 0))
            c2.metric("Failed", counts.get("failed", 0) + counts.get("error", 0))
            c3.metric("Total", cov.total_tests)

            if cov.report:
                st.code(cov.report, language="text")
            if not cov.ok and cov.pytest_output:
                with st.expander("Test run output", expanded=True):
                    st.code(cov.pytest_output, language="text")

            if coverage_html.exists():
                st.caption(f"HTML report: `{coverage_html}`")
