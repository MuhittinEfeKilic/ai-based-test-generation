from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol


@dataclass
class LLMConfig:
    provider: str = "mock"
    api_key: str | None = None
    model: str = "gpt-4o-mini"
    temperature: float = 0.2
    timeout_sec: int = 30
    base_url: str | None = None


class LLMProvider(Protocol):
    def generate_tests(self, prompt: str) -> str:
        """Return pytest code as a string."""
        ...
