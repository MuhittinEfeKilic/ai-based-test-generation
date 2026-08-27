"""Application toolbar: brand on the left, run context on the right."""

from __future__ import annotations

from html import escape

import streamlit as st

from formatting import provider_status


def render(use_ai: bool, provider: str, has_key: bool, repo_url: str | None = None) -> None:
    status_text, dot = provider_status(use_ai, provider, has_key)

    right = [
        f'<span class="tg-pill"><span class="tg-dot {dot}"></span>{escape(status_text)}</span>'
    ]
    if repo_url:
        right.append(
            f'<span class="tg-pill"><a href="{escape(repo_url)}" target="_blank" '
            'rel="noopener noreferrer">Repository</a></span>'
        )

    st.markdown(
        '<div class="tg-header">'
        '<div class="tg-brand">'
        '<span class="tg-mark">TG</span>'
        '<span class="tg-name">TestGen</span>'
        '<span class="tg-tagline">AI-Powered Python Testing</span>'
        "</div>"
        f'<div class="tg-header-right">{"".join(right)}</div>'
        "</div>",
        unsafe_allow_html=True,
    )
