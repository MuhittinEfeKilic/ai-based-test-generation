"""Generated tests and the test-execution section."""

from __future__ import annotations

import streamlit as st

from formatting import (
    count_tests,
    download_name,
    metric_cards_html,
    mode_label,
    panel_title_html,
)


def render_generated(generation, source_name: str | None) -> None:
    deterministic = generation.deterministic_code
    ai_code = generation.ai_code

    st.markdown(
        panel_title_html("Generated Tests", generation.saved_path.name),
        unsafe_allow_html=True,
    )

    if generation.ai_error:
        st.info(
            f"AI generation was unavailable, so deterministic tests were generated "
            f"instead. Reason: {generation.ai_error}"
        )

    caption = (
        f"{mode_label(generation.mode)} &middot; target module "
        f"`{generation.module_import}`"
    )
    st.caption(caption)

    if ai_code:
        det_tab, ai_tab = st.tabs(
            [
                f"Deterministic ({count_tests(deterministic)})",
                f"AI generated ({count_tests(ai_code)})",
            ]
        )
        with det_tab:
            _render_suite(
                deterministic,
                download_name(source_name),
                "Executed under coverage.py.",
                key="dl_deterministic",
                primary=True,
            )
        with ai_tab:
            _render_suite(
                ai_code,
                "test_ai_generated.py",
                "Syntax-validated and shown for review. Not executed by this app.",
                key="dl_ai",
                primary=False,
            )
    else:
        _render_suite(
            deterministic,
            download_name(source_name),
            "Executed under coverage.py.",
            key="dl_deterministic",
            primary=True,
        )


def _render_suite(code: str, filename: str, note: str, key: str, primary: bool) -> None:
    st.caption(f"`{filename}` &middot; {count_tests(code)} test functions &middot; {note}")
    st.code(code, language="python")
    st.download_button(
        "Download .py",
        data=code,
        file_name=filename,
        mime="text/x-python",
        type="primary" if primary else "secondary",
        key=key,
    )


def render_execution(execution, can_run: bool) -> bool:
    """Renders the execution section and returns True when Run was clicked."""
    st.markdown(panel_title_html("Test Execution", "pytest"), unsafe_allow_html=True)

    clicked = st.button("Run Tests", disabled=not can_run, width="stretch")
    if not can_run:
        st.caption("Generate tests first.")
        return False

    if execution is None:
        st.markdown(
            '<div class="tg-empty">Tests have not been executed yet.</div>',
            unsafe_allow_html=True,
        )
        return clicked

    counts = execution.counts
    failed = counts.get("failed", 0) + counts.get("error", 0)

    st.markdown(
        metric_cards_html(
            [
                ("Passed", counts.get("passed", 0), "success" if counts.get("passed") else ""),
                ("Failed", counts.get("failed", 0), "error" if counts.get("failed") else ""),
                ("Errors", counts.get("error", 0), "error" if counts.get("error") else ""),
                ("Total", execution.total_tests, ""),
            ]
        ),
        unsafe_allow_html=True,
    )

    if execution.ok:
        st.success("All generated tests passed.")
    else:
        st.warning(
            f"{failed} generated test(s) did not pass. The diagnostics below show "
            "which inputs the generator chose and what the code did with them."
        )

    if execution.pytest_output:
        with st.expander("View pytest output", expanded=not execution.ok):
            st.code(execution.pytest_output, language="text")

    return clicked
