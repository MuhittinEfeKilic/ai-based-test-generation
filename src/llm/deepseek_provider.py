from __future__ import annotations
from .provider import LLMConfig


class DeepSeekProvider:
    def __init__(self, config: LLMConfig):
        self.config = config

    def generate_tests(self, prompt: str) -> str:
        # Many DeepSeek setups are OpenAI-compatible; use openai SDK with base_url
        # Requires: openai package installed and base_url set if needed.
        from openai import OpenAI

        client = OpenAI(api_key=self.config.api_key, base_url=self.config.base_url)
        resp = client.chat.completions.create(
            model=self.config.model,
            temperature=self.config.temperature,
            messages=[
                {"role": "system", "content": "You generate pytest unit tests. Return only python code."},
                {"role": "user", "content": prompt},
            ],
            timeout=self.config.timeout_sec,
        )
        return (resp.choices[0].message.content or "").strip()
