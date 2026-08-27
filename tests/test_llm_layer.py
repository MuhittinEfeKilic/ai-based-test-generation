"""Prompt contents and the LLM fallback contract."""

import pytest

from analyzer.code_analyzer import CodeAnalyzer
from llm import DEFAULT_BASE_URLS, LLMConfig, generate_with_optional_llm
from llm.llm_service import _get_provider
from test_generator.prompt_builder import MAX_SOURCE_CHARS, build_llm_prompt, build_test_plan

VALID_TESTS = "import pytest\n\ndef test_ok():\n    assert 1 == 1\n"


def plan_for(tmp_path, source: str):
    module_path = tmp_path / "mod.py"
    module_path.write_text(source, encoding="utf-8")
    return build_test_plan(CodeAnalyzer().analyze_as_dict(str(module_path)))


def test_prompt_includes_function_source(tmp_path):
    plan = plan_for(tmp_path, "def double(n: int):\n    return n * 2\n")

    prompt = build_llm_prompt(plan)

    assert "return n * 2" in prompt
    assert "Annotations: n: int" in prompt


def test_prompt_truncates_huge_bodies(tmp_path):
    body = "\n".join(f"    x = {i}" for i in range(2000))
    plan = plan_for(tmp_path, f"def big():\n{body}\n    return 1\n")

    prompt = build_llm_prompt(plan)

    assert "truncated" in prompt
    assert len(prompt) < MAX_SOURCE_CHARS * 2


def test_async_definition_is_marked_in_prompt(tmp_path):
    plan = plan_for(tmp_path, "async def load(n: int):\n    return n\n")

    assert "Definition: async def" in build_llm_prompt(plan)


def test_missing_api_key_falls_back():
    result = generate_with_optional_llm("prompt", LLMConfig(provider="openai", api_key=None))

    assert result.source == "fallback"
    assert "Missing API key" in result.error


def test_provider_exception_falls_back(monkeypatch):
    class Boom:
        def generate_tests(self, prompt):
            raise RuntimeError("network down")

    monkeypatch.setattr("llm.llm_service._get_provider", lambda cfg: Boom())
    result = generate_with_optional_llm("prompt", LLMConfig(provider="openai", api_key="k"))

    assert result.source == "fallback"
    assert result.error == "network down"


@pytest.mark.parametrize(
    "answer, expected_error",
    [
        ("Sure, here is how you test it.", "LLM output not pytest-like"),
        ("def test_broken(:\n    assert", "LLM output has syntax error"),
        ("def test_broken():\n    assert (1 ==\n", "LLM output has syntax error"),
    ],
)
def test_unusable_answers_fall_back(monkeypatch, answer, expected_error):
    class Fixed:
        def generate_tests(self, prompt):
            return answer

    monkeypatch.setattr("llm.llm_service._get_provider", lambda cfg: Fixed())
    result = generate_with_optional_llm("prompt", LLMConfig(provider="openai", api_key="k"))

    assert result.source == "fallback"
    assert result.error == expected_error


def test_fenced_answer_is_unwrapped(monkeypatch):
    class Fenced:
        def generate_tests(self, prompt):
            return f"Here you go:\n```python\n{VALID_TESTS}```"

    monkeypatch.setattr("llm.llm_service._get_provider", lambda cfg: Fenced())
    result = generate_with_optional_llm("prompt", LLMConfig(provider="openai", api_key="k"))

    assert result.source == "llm"
    assert result.code.startswith("import pytest")


def test_mock_provider_needs_no_key():
    result = generate_with_optional_llm(
        "TARGET_MODULE_IMPORT=mod\nFunction: double(n)\nHasPrint: false\nScenarios:\n- valid",
        LLMConfig(provider="mock"),
    )

    assert result.source == "llm"
    assert "def test_double" in result.code


def test_deepseek_gets_its_own_endpoint():
    provider = _get_provider(LLMConfig(provider="deepseek", api_key="k"))

    assert provider.config.base_url == DEFAULT_BASE_URLS["deepseek"]


def test_explicit_base_url_wins_over_default():
    provider = _get_provider(LLMConfig(provider="deepseek", api_key="k", base_url="http://localhost:8000"))

    assert provider.config.base_url == "http://localhost:8000"
