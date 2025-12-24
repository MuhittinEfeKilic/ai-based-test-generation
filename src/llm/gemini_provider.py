from __future__ import annotations
from .provider import LLMConfig


class GeminiProvider:
    def __init__(self, config: LLMConfig):
        self.config = config

    def generate_tests(self, prompt: str) -> str:
        import google.generativeai as genai

        genai.configure(api_key=self.config.api_key)
        model = genai.GenerativeModel(self.config.model)
        resp = model.generate_content(
            prompt,
            generation_config={"temperature": float(self.config.temperature)},
        )
        return (getattr(resp, "text", "") or "").strip()
