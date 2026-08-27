"""Session-state ownership for the workspace.

All reads and writes of run results go through here so the UI cannot end up
showing an analysis from one source next to coverage from another.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import streamlit as st

from formatting import workflow_stage

# Result keys, cleared together.
_RESULT_KEYS = ("analysis", "generation", "execution", "fingerprint", "source_name", "error")

_DEFAULTS: dict[str, Any] = {
    "analysis": None,
    "generation": None,
    "execution": None,
    "fingerprint": None,
    "source_name": None,
    "error": None,
    "editor_seed": 0,
    "editor_value": "",
}


def init() -> None:
    for key, value in _DEFAULTS.items():
        st.session_state.setdefault(key, value)


def get(key: str) -> Any:
    return st.session_state.get(key)


def set_error(message: str, detail: str | None = None) -> None:
    clear_results()
    st.session_state.error = {"message": message, "detail": detail}


def clear_error() -> None:
    st.session_state.error = None


def clear_results() -> None:
    for key in _RESULT_KEYS:
        st.session_state[key] = None


def store_generation(analysis, generation, fingerprint: str, source_name: str | None) -> None:
    """A fresh generation always invalidates the previous execution."""
    st.session_state.analysis = analysis
    st.session_state.generation = generation
    st.session_state.execution = None
    st.session_state.fingerprint = fingerprint
    st.session_state.source_name = source_name
    st.session_state.error = None


def store_execution(execution) -> None:
    st.session_state.execution = execution


def load_sample(code: str) -> None:
    """Replace the editor contents; the seed forces the widget to remount."""
    st.session_state.editor_value = code
    st.session_state.editor_seed += 1


def is_stale(current_fingerprint: str) -> bool:
    """True when the source or provider changed after the last generation."""
    stored = st.session_state.get("fingerprint")
    return bool(stored) and stored != current_fingerprint


@dataclass
class Stage:
    completed: set[str]
    active: str | None


def stage(has_source: bool, current_fingerprint: str) -> Stage:
    """Which workflow steps are done, and which one the user is standing on."""
    generation = st.session_state.get("generation")
    execution = st.session_state.get("execution")
    fresh = generation is not None and not is_stale(current_fingerprint)

    completed, active = workflow_stage(
        has_source=has_source,
        fresh_generation=fresh,
        has_execution=execution is not None,
        has_coverage=execution is not None and execution.percent is not None,
    )
    return Stage(completed=completed, active=active)
