from __future__ import annotations
from .provider import LLMConfig


class ClaudeProvider:
    def __init__(self, config: LLMConfig):
        self.config = config

    def generate_tests(self, prompt: str) -> str:
        from anthropic import Anthropic

        client = Anthropic(api_key=self.config.api_key)
        msg = client.messages.create(
            model=self.config.model,
            temperature=float(self.config.temperature),
            max_tokens=1200,
            messages=[{"role": "user", "content": prompt}],
        )
        parts = []
        for block in getattr(msg, "content", []) or []:
            text = getattr(block, "text", None)
            if text:
                parts.append(text)
        return ("\n".join(parts)).strip()
