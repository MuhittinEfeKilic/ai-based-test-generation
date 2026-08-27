from __future__ import annotations

from .provider import LLMConfig

SYSTEM_PROMPT = "You generate pytest unit tests. Return only python code."


class OpenAIProvider:
    """Chat-completions provider for any OpenAI-compatible endpoint.

    DeepSeek speaks the same protocol, so it reuses this class with a
    different ``base_url`` rather than a duplicated implementation.
    """

    def __init__(self, config: LLMConfig):
        self.config = config

    def generate_tests(self, prompt: str) -> str:
        from openai import OpenAI

        client = OpenAI(api_key=self.config.api_key, base_url=self.config.base_url)
        resp = client.chat.completions.create(
            model=self.config.model,
            temperature=self.config.temperature,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            timeout=self.config.timeout_sec,
        )
        return (resp.choices[0].message.content or "").strip()
