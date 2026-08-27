"""Analysis summary and detected code structure."""

from __future__ import annotations

import streamlit as st

from formatting import metric_cards_html, panel_title_html, structure_table_html


def render(analysis, plan_functions: list[dict], generated_tests: int | None) -> None:
    st.markdown(panel_title_html("Analysis Results"), unsafe_allow_html=True)

    if analysis is None:
        st.markdown(
            '<div class="tg-empty">Run a generation to see the analysis.</div>',
            unsafe_allow_html=True,
        )
        return

    metrics = analysis.metrics
    cards = [
        ("Functions", metrics["functions"], "accent"),
        ("With branches", metrics["branches"], ""),
        ("With loops", metrics["loops"], ""),
        ("With raises", metrics["raises"], ""),
        ("Async", metrics["async"], ""),
    ]
    if generated_tests is not None:
        cards.append(("Tests", generated_tests, "success"))

    st.markdown(metric_cards_html(cards), unsafe_allow_html=True)

    if analysis.skipped_methods:
        st.caption(
            f"{len(analysis.classes)} class(es) with {analysis.skipped_methods} method(s) "
            "were skipped: generated tests import functions by name, which only "
            "works at module level."
        )

    st.markdown(panel_title_html("Detected Code Structure"), unsafe_allow_html=True)
    # The plan carries the scenario counts; the raw analysis does not.
    st.markdown(structure_table_html(plan_functions), unsafe_allow_html=True)
