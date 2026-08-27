"""Coverage report: the headline number plus what coverage.py actually measured."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from formatting import (
    coverage_files_table_html,
    coverage_panel_html,
    panel_title_html,
)


def render(execution, html_index: Path) -> None:
    st.markdown(panel_title_html("Coverage Report", "coverage.py"), unsafe_allow_html=True)

    if execution is None:
        st.markdown(
            '<div class="tg-empty">Run the tests to measure coverage.</div>',
            unsafe_allow_html=True,
        )
        return

    st.markdown(
        coverage_panel_html(execution.percent, execution.statements, execution.missing),
        unsafe_allow_html=True,
    )

    # Statement coverage only - these runs are not configured for branch coverage.
    st.caption("Statement coverage of the analyzed module. Branch coverage is not measured.")

    if execution.files:
        st.markdown(coverage_files_table_html(execution.files), unsafe_allow_html=True)

    if execution.report:
        with st.expander("View coverage.py report"):
            st.code(execution.report, language="text")

    if html_index.exists():
        st.caption(f"HTML report: `{html_index}`")
