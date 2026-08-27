from __future__ import annotations

import ast
import re
from dataclasses import dataclass, replace

from .provider import DEFAULT_BASE_URLS, REMOTE_PROVIDERS, LLMConfig
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

    if cfg.provider == "deepseek":
        # DeepSeek is OpenAI-compatible; it only needs its own endpoint.
        from .openai_provider import OpenAIProvider
        base_url = cfg.base_url or DEFAULT_BASE_URLS["deepseek"]
        return OpenAIProvider(replace(cfg, base_url=base_url))

    if cfg.provider == "gemini":
        from .gemini_provider import GeminiProvider
        return GeminiProvider(cfg)

    if cfg.provider == "claude":
        from .claude_provider import ClaudeProvider
        return ClaudeProvider(cfg)

    return MockLLMProvider()


def generate_with_optional_llm(prompt: str, cfg: LLMConfig) -> LLMResult:
    """Ask the configured provider for tests, falling back on any problem.

    Every failure mode - missing key, network error, non-code answer, code that
    does not parse - returns ``source="fallback"`` with an ``error`` message so
    the caller can degrade to the rule-based generator instead of crashing.
    """
    if cfg.provider in REMOTE_PROVIDERS and not cfg.api_key:
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
