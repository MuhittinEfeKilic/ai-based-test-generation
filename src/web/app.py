"""TestGen - AI-Powered Python Test Generator.

Streamlit entry point. This module only orchestrates: every panel lives in
`components/`, the backend glue in `pipeline.py`, session handling in
`state.py`, and the visual system in `styles.py`.

Security note: the analyzed module is imported and the deterministic suite is
executed in this process' Python environment. AI-generated code is validated
and displayed but never executed. Only analyze code you trust.
"""

from __future__ import annotations

import logging
import os
import shutil
import sys
import traceback
from pathlib import Path

import streamlit as st

SRC_DIR = Path(__file__).resolve().parents[1]      # ./src
PROJECT_ROOT = SRC_DIR.parent
WEB_DIR = Path(__file__).resolve().parent
for _path in (str(SRC_DIR), str(WEB_DIR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import state
import styles
from components import (
    analysis_panel,
    configuration,
    coverage_panel,
    header,
    source_editor,
    test_results,
)
from formatting import count_tests, friendly_error, steps_html
from pipeline import (
    SourceError,
    Workspace,
    analyze_source,
    execute_tests,
    generate_tests,
    prune_tmp_targets,
    source_fingerprint,
)

log = logging.getLogger("testgen.web")

st.set_page_config(
    page_title="TestGen - AI-Powered Python Test Generator",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="collapsed",
)

styles.inject()
state.init()

workspace = Workspace(PROJECT_ROOT)
workspace.ensure()

REPO_URL = os.environ.get("TESTGEN_REPO_URL")


def clean_artifacts() -> None:
    """Remove everything the app generates. Scoped to the workspace directories."""
    removed = prune_tmp_targets(workspace.sample_code)

    for path in workspace.uploads.glob("*"):
        if path.is_file():
            path.unlink(missing_ok=True)

    for path in workspace.generated_tests.glob("test_*.py"):
        path.unlink(missing_ok=True)

    if workspace.coverage_html.exists():
        shutil.rmtree(workspace.coverage_html, ignore_errors=True)

    state.clear_results()
    st.toast(f"Cleaned workspace ({removed} scratch module(s) removed).")


# --------------------------------------------------------------------------
# Header - reads the previous render's configuration so it can sit on top.
# --------------------------------------------------------------------------
_provider = configuration.current_provider()
header.render(
    use_ai=configuration.current_use_ai(),
    provider=_provider,
    has_key=configuration.provider_has_key(_provider),
    repo_url=REPO_URL,
)

steps_slot = st.empty()

left, right = st.columns([1.15, 0.85], gap="large")

with left:
    source = source_editor.render()
    generate_clicked = source_editor.render_cta(source.has_code)

with right:
    settings = configuration.render()
    configuration.render_workspace_tools(clean_artifacts)

fingerprint = source_fingerprint(source.code, settings.use_ai, settings.provider)

# --------------------------------------------------------------------------
# Generate
# --------------------------------------------------------------------------
if generate_clicked:
    state.clear_error()
    status = st.status("Generating tests...", expanded=True)

    def progress(label: str) -> None:
        status.write(label)

    try:
        progress("Analyzing source")
        target_path = workspace.write_source(source.code, source.filename)
        analysis = analyze_source(target_path)

        if not analysis.functions:
            status.update(label="No testable functions found", state="error")
            detail = (
                f"This file defines {len(analysis.classes)} class(es) with "
                f"{analysis.skipped_methods} method(s); generated tests import "
                "functions by name, which only works at module level."
                if analysis.classes
                else "Add at least one module-level `def` to generate tests."
            )
            state.set_error(f"No module-level functions were found. {detail}")
        else:
            generation = generate_tests(
                analysis=analysis,
                target_path=target_path,
                sample_dir=workspace.sample_code,
                generated_dir=workspace.generated_tests,
                use_ai=settings.use_ai,
                llm_cfg=settings.llm_cfg,
                progress=progress,
            )
            state.store_generation(analysis, generation, fingerprint, source.filename)
            status.update(label="Tests generated", state="complete")

    except SourceError as exc:
        log.warning("Source rejected: %s", exc.message)
        status.update(label="Could not analyze source", state="error")
        state.set_error(exc.message)
    except Exception as exc:  # friendly here, full detail only in the log/expander
        log.exception("Generation failed")
        status.update(label="Generation failed", state="error")
        state.set_error(friendly_error(exc), traceback.format_exc())

# --------------------------------------------------------------------------
# Results
# --------------------------------------------------------------------------
error = state.get("error")
analysis = state.get("analysis")
generation = state.get("generation")
execution = state.get("execution")

current = state.stage(source.has_code, fingerprint)
steps_slot.markdown(steps_html(current.completed, current.active), unsafe_allow_html=True)

with right:
    if error:
        st.error(error["message"])
        if error.get("detail"):
            with st.expander("Technical details"):
                st.code(error["detail"], language="text")

    if generation is not None and state.is_stale(fingerprint):
        st.warning(
            "The source or provider changed after this run. Re-run "
            "**Analyze & Generate Tests** to refresh these results."
        )

    analysis_panel.render(
        analysis,
        generation.test_plan["functions"] if generation else [],
        count_tests(generation.deterministic_code) if generation else None,
    )

if generation is not None:
    st.divider()
    test_results.render_generated(generation, state.get("source_name"))

    st.divider()
    exec_col, cov_col = st.columns([0.85, 1.15], gap="large")

    with exec_col:
        run_clicked = test_results.render_execution(execution, can_run=True)

    with cov_col:
        coverage_panel.render(execution, workspace.coverage_html / "index.html")

    if run_clicked:
        status = st.status("Running tests...", expanded=True)
        try:
            result = execute_tests(
                generation=generation,
                project_root=PROJECT_ROOT,
                sample_dir=workspace.sample_code,
                progress=status.write,
            )
            state.store_execution(result)
            status.update(label="Test run complete", state="complete")
            st.rerun()
        except Exception:
            log.exception("Test execution failed")
            status.update(label="Test run failed", state="error")
            st.error(
                "The test run could not be completed. Check that pytest and "
                "coverage are installed in this environment."
            )
            with st.expander("Technical details"):
                st.code(traceback.format_exc(), language="text")
