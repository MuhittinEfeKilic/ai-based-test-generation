from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

#: Selectable providers, in the order the UI lists them.
PROVIDERS = ("mock", "gemini", "openai", "claude", "deepseek")

#: Display names, since "openai".capitalize() reads badly.
PROVIDER_LABELS = {
    "mock": "Mock",
    "openai": "OpenAI",
    "gemini": "Gemini",
    "claude": "Claude",
    "deepseek": "DeepSeek",
}

#: Providers that talk to a remote API and therefore need a key.
REMOTE_PROVIDERS = frozenset({"openai", "gemini", "claude", "deepseek"})

#: Used when the user does not override the model in the sidebar.
DEFAULT_MODELS = {
    "mock": "mock",
    "openai": "gpt-4.1-mini",
    "gemini": "gemini-2.5-flash",
    "claude": "claude-sonnet-5",
    "deepseek": "deepseek-chat",
}

#: Endpoints for OpenAI-compatible providers that are not OpenAI itself.
DEFAULT_BASE_URLS = {
    "deepseek": "https://api.deepseek.com",
}

#: Name of the entry read from .streamlit/secrets.toml per provider.
API_KEY_SECRETS = {
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "claude": "ANTHROPIC_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
}

#: Providers whose endpoint can be pointed elsewhere (proxy, gateway, ...).
SUPPORTS_BASE_URL = frozenset({"openai", "deepseek"})


@dataclass
class LLMConfig:
    provider: str = "mock"
    api_key: str | None = None
    model: str = DEFAULT_MODELS["openai"]
    temperature: float = 0.2
    timeout_sec: int = 30
    base_url: str | None = None


class LLMProvider(Protocol):
    def generate_tests(self, prompt: str) -> str:
        """Return pytest code as a string."""
        ...
