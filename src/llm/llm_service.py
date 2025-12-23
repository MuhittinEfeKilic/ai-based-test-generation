from __future__ import annotations

import ast
import re
from dataclasses import dataclass

from .provider import LLMConfig
from .mock_provider import MockLLMProvider


@dataclass
class LLMResult:
    source: str              # "llm" | "fallback"
    code: str
    error: str | None = None


def _extract_python_code(text: str) -> str:
    fence = re.search(r"```(?:python)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if fence:
        return fence.group(1).strip()
    return text.strip()


def _is_plausible_pytest(code: str) -> bool:
    return ("def test_" in code) and ("assert" in code or "pytest" in code)


def _syntax_ok(code: str) -> bool:
    try:
        ast.parse(code)
        return True
    except SyntaxError:
        return False


def _get_provider(cfg: LLMConfig):
    if cfg.provider == "openai":
        from .openai_provider import OpenAIProvider
        return OpenAIProvider(cfg)

    if cfg.provider == "gemini":
        from .gemini_provider import GeminiProvider
        return GeminiProvider(cfg)

    if cfg.provider == "claude":
        from .claude_provider import ClaudeProvider
        return ClaudeProvider(cfg)

    if cfg.provider == "deepseek":
        from .deepseek_provider import DeepSeekProvider
        return DeepSeekProvider(cfg)

    return MockLLMProvider()


def generate_with_optional_llm(prompt: str, cfg: LLMConfig) -> LLMResult:
    # Missing key for providers that require it => fallback
    if cfg.provider in {"openai", "gemini", "claude", "deepseek"} and not cfg.api_key:
        return LLMResult(source="fallback", code="", error=f"Missing API key for provider: {cfg.provider}")

    try:
        provider = _get_provider(cfg)
        raw = provider.generate_tests(prompt)
        code = _extract_python_code(raw)

        if not _is_plausible_pytest(code):
            return LLMResult(source="fallback", code="", error="LLM output not pytest-like")

        if not _syntax_ok(code):
            return LLMResult(source="fallback", code="", error="LLM output has syntax error")

        return LLMResult(source="llm", code=code)

    except Exception as e:
        return LLMResult(source="fallback", code="", error=str(e))
