"""Left panel: where the user's Python source comes from."""

from __future__ import annotations

from dataclasses import dataclass

import streamlit as st

import state
from formatting import panel_title_html
from pipeline import sanitize_filename
from samples import SAMPLES

try:
    from streamlit_ace import st_ace
    ACE_AVAILABLE = True
except Exception:  # pragma: no cover - depends on optional dependency
    ACE_AVAILABLE = False

PLACEHOLDER = "def add(a, b):\n    return a + b\n"


@dataclass
class SourceInput:
    code: str
    filename: str

    @property
    def has_code(self) -> bool:
        return bool(self.code and self.code.strip())


def render() -> SourceInput:
    st.markdown(panel_title_html("Source Code", "python"), unsafe_allow_html=True)

    mode = st.radio(
        "Input mode",
        ["Editor", "Upload file"],
        horizontal=True,
        label_visibility="collapsed",
        key="cfg_input_mode",
    )

    if mode == "Upload file":
        return _render_upload()
    return _render_editor()


def _render_upload() -> SourceInput:
    uploaded = st.file_uploader("Upload a .py file", type=["py"], label_visibility="collapsed")
    if uploaded is None:
        st.markdown(
            '<div class="tg-empty">Upload a .py file to analyze.</div>',
            unsafe_allow_html=True,
        )
        return SourceInput(code="", filename="uploaded.py")

    safe_name = sanitize_filename(uploaded.name)
    try:
        code = uploaded.getvalue().decode("utf-8")
    except UnicodeDecodeError:
        st.error("That file is not UTF-8 encoded text. Save it as UTF-8 and upload again.")
        return SourceInput(code="", filename=safe_name)

    st.caption(f"`{safe_name}` &middot; {len(code.splitlines())} lines")
    st.code(code, language="python")
    return SourceInput(code=code, filename=safe_name)


def _render_editor() -> SourceInput:
    # Buttons rather than a dropdown: loading a sample is a one-shot action,
    # and a select would keep re-firing its value on every rerun.
    columns = st.columns(len(SAMPLES) + 1)
    for column, sample in zip(columns, SAMPLES):
        with column:
            if st.button(sample.label, width="stretch", help=sample.description):
                state.load_sample(sample.code)
                state.clear_results()
                st.rerun()

    with columns[-1]:
        if st.button("Clear", width="stretch"):
            state.load_sample("")
            state.clear_results()
            st.rerun()

    seed = state.get("editor_seed")
    if ACE_AVAILABLE:
        code = st_ace(
            value=state.get("editor_value"),
            language="python",
            theme="tomorrow_night",
            key=f"editor_{seed}",
            height=420,
            font_size=13,
            tab_size=4,
            wrap=False,
            show_gutter=True,
            show_print_margin=False,
            auto_update=True,
        )
    else:
        st.caption("Install `streamlit-ace` for syntax highlighting and line numbers.")
        code = st.text_area(
            "Python source",
            value=state.get("editor_value"),
            height=420,
            placeholder=PLACEHOLDER,
            key=f"editor_text_{seed}",
            label_visibility="collapsed",
        )

    code = code or ""
    if code.strip():
        st.caption(f"`pasted_input.py` &middot; {len(code.splitlines())} lines")

    return SourceInput(code=code, filename="pasted_input.py")


def render_cta(has_code: bool) -> bool:
    """The primary action. Disabled rather than hidden when there is no source."""
    clicked = st.button(
        "Analyze & Generate Tests",
        type="primary",
        width="stretch",
        disabled=not has_code,
    )
    if not has_code:
        st.caption("Add Python code or load a sample to enable generation.")
    return clicked

