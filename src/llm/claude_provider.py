from __future__ import annotations

from .provider import LLMConfig

MAX_TOKENS = 4096


class ClaudeProvider:
    def __init__(self, config: LLMConfig):
        self.config = config

    def generate_tests(self, prompt: str) -> str:
        from anthropic import Anthropic

        client = Anthropic(api_key=self.config.api_key, timeout=float(self.config.timeout_sec))
        msg = client.messages.create(
            model=self.config.model,
            temperature=float(self.config.temperature),
            max_tokens=MAX_TOKENS,
            system="You generate pytest unit tests. Return only python code.",
            messages=[{"role": "user", "content": prompt}],
        )
        parts = []
        for block in getattr(msg, "content", []) or []:
            text = getattr(block, "text", None)
            if text:
                parts.append(text)
        return ("\n".join(parts)).strip()
