"""Right panel: generation mode, AI provider, and workspace maintenance."""

from __future__ import annotations

from dataclasses import dataclass

import streamlit as st

from formatting import get_temperature, missing_key_message, panel_title_html
from llm import (
    API_KEY_SECRETS,
    DEFAULT_MODELS,
    PROVIDERS,
    PROVIDER_LABELS,
    SUPPORTS_BASE_URL,
    LLMConfig,
)

DETERMINISTIC = "Deterministic"
AI_ASSISTED = "AI Assisted"


@dataclass
class GenerationSettings:
    use_ai: bool
    provider: str
    llm_cfg: LLMConfig
    has_key: bool
    key_hint: str | None


def read_secret(name: str) -> str | None:
    """Read one entry from .streamlit/secrets.toml, tolerating no file at all."""
    try:
        return st.secrets.get(name, None)
    except Exception:
        # Streamlit raises when no secrets.toml exists; that is not an error.
        return None


def current_provider() -> str:
    return st.session_state.get("cfg_provider", PROVIDERS[0])


def current_use_ai() -> bool:
    return st.session_state.get("cfg_mode", DETERMINISTIC) == AI_ASSISTED


def provider_has_key(provider: str) -> bool:
    if provider == "mock":
        return True
    secret_name = API_KEY_SECRETS.get(provider)
    if secret_name and read_secret(secret_name):
        return True
    return bool(st.session_state.get(f"cfg_key_{provider}", "").strip())


def render() -> GenerationSettings:
    st.markdown(panel_title_html("Generation Mode"), unsafe_allow_html=True)

    mode = st.radio(
        "Generation mode",
        [DETERMINISTIC, AI_ASSISTED],
        label_visibility="collapsed",
        key="cfg_mode",
    )
    use_ai = mode == AI_ASSISTED

    if use_ai:
        st.caption(
            "Uses a language model to write additional contextual tests. "
            "Deterministic tests are still generated and remain the suite that "
            "is executed and measured."
        )
    else:
        st.caption("Fast, repeatable AST-based test generation. No network calls.")

    provider = PROVIDERS[0]
    api_key = None
    base_url = None
    model = DEFAULT_MODELS.get(provider, "mock")
    temperature = 0.1
    key_hint = None

    if use_ai:
        st.markdown(panel_title_html("AI Provider"), unsafe_allow_html=True)
        provider = st.selectbox(
            "Provider",
            options=list(PROVIDERS),
            format_func=lambda p: PROVIDER_LABELS.get(p, p),
            key="cfg_provider",
        )

        default_model = DEFAULT_MODELS.get(provider, "mock")
        model = st.text_input(
            "Model",
            value=default_model,
            key=f"cfg_model_{provider}",
            help="Override if the default model id is unavailable on your account.",
        ).strip() or default_model

        # A radio reads better than a slider here: the three levels are named,
        # not a continuum, and the slider renders its end labels twice.
        temp_label = st.radio(
            "Creativity",
            options=["Low", "Medium", "High"],
            horizontal=True,
            key="cfg_temp",
        )
        temperature = get_temperature(temp_label)

        secret_name = API_KEY_SECRETS.get(provider)
        if secret_name:
            from_secrets = read_secret(secret_name)
            if from_secrets:
                api_key = from_secrets
                st.caption(f"Key loaded from secrets (`{secret_name}`).")
            else:
                # Stored in session only; never echoed back or logged.
                api_key = st.text_input(
                    f"{PROVIDER_LABELS.get(provider, provider)} API key",
                    type="password",
                    key=f"cfg_key_{provider}",
                ).strip() or None
                if not api_key:
                    key_hint = missing_key_message(
                        PROVIDER_LABELS.get(provider, provider), secret_name
                    )
                    st.warning(key_hint)

        if provider in SUPPORTS_BASE_URL:
            base_url = st.text_input(
                "Base URL (optional)",
                key=f"cfg_base_url_{provider}",
            ).strip() or None

    llm_cfg = LLMConfig(
        provider=provider if use_ai else "mock",
        api_key=api_key,
        model=model,
        temperature=float(temperature),
        timeout_sec=30,
        base_url=base_url,
    )

    return GenerationSettings(
        use_ai=use_ai,
        provider=provider,
        llm_cfg=llm_cfg,
        has_key=provider_has_key(provider),
        key_hint=key_hint,
    )


def render_workspace_tools(on_clean) -> None:
    with st.expander("Workspace"):
        st.caption(
            "Scratch modules, uploads, generated test files and the HTML report "
            "live under `data/` and `tests/generated/`."
        )
        if st.button("Clean generated artifacts", width="stretch"):
            on_clean()
