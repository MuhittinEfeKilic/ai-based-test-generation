"""The UI's backend glue: staging, analysis errors, generation, invalidation."""

import pytest

from llm import LLMConfig
from web.pipeline import (
    AnalysisResult,
    SourceError,
    Workspace,
    analyze_source,
    generate_tests,
    prune_tmp_targets,
    sanitize_filename,
    source_fingerprint,
    stage_target_module,
)

CALC = (
    "def calculate_discount(price, discount):\n"
    "    if price < 0:\n"
    "        raise ValueError('negative')\n"
    "    return price * (1 - discount / 100)\n"
)


# ---- filename safety ------------------------------------------------------

@pytest.mark.parametrize(
    "raw, expected",
    [
        ("utils.py", "utils.py"),
        ("../../etc/passwd", "passwd.py"),
        ("a/b/c/mod.py", "mod.py"),
        ("weird name!.py", "weird_name_.py"),
        ("", "uploaded.py"),
        ("....", "uploaded.py"),
        ("noext", "noext.py"),
    ],
)
def test_uploaded_names_are_reduced_to_a_safe_basename(raw, expected):
    assert sanitize_filename(raw) == expected


def test_workspace_writes_only_inside_uploads(tmp_path):
    workspace = Workspace(tmp_path)
    workspace.ensure()

    written = workspace.write_source("x = 1\n", "../../escape.py")

    assert written.parent == workspace.uploads
    assert written.name == "escape.py"


# ---- analysis errors ------------------------------------------------------

def test_syntax_error_becomes_a_source_error_with_a_line(tmp_path):
    bad = tmp_path / "bad.py"
    bad.write_text("def broken(:\n    return 1\n", encoding="utf-8")

    with pytest.raises(SourceError) as excinfo:
        analyze_source(bad)

    assert excinfo.value.line == 1
    assert "line 1" in excinfo.value.message


def test_analysis_reports_only_measurable_metrics(tmp_path):
    module = tmp_path / "mixed.py"
    module.write_text(
        "async def fetch(n):\n"
        "    return n\n"
        "\n"
        "def loopy(items):\n"
        "    for i in items:\n"
        "        print(i)\n"
        "\n"
        "def guard(x):\n"
        "    if x < 0:\n"
        "        raise ValueError('no')\n"
        "    return x\n",
        encoding="utf-8",
    )

    metrics = analyze_source(module).metrics

    assert metrics == {
        "functions": 3,
        "branches": 1,
        "loops": 1,
        "raises": 1,
        "async": 1,
        "prints": 1,
    }


def test_class_only_source_analyses_to_zero_functions(tmp_path):
    module = tmp_path / "shop.py"
    module.write_text(
        "class Cart:\n    def add(self, item):\n        return item\n", encoding="utf-8"
    )

    result = analyze_source(module)

    assert result.functions == []
    assert result.classes == ["Cart"]
    assert result.skipped_methods == 1


# ---- staging --------------------------------------------------------------

def test_staging_creates_a_fresh_module_and_removes_the_previous_one(tmp_path):
    source = tmp_path / "src.py"
    source.write_text(CALC, encoding="utf-8")
    sample_dir = tmp_path / "sample_code"

    first, first_import = stage_target_module(source, sample_dir)
    second, second_import = stage_target_module(source, sample_dir)

    assert first_import != second_import
    assert not first.exists()
    assert second.exists()
    assert second_import.startswith("data.sample_code.tmp_target_")


def test_prune_spares_the_kept_module(tmp_path):
    sample_dir = tmp_path / "sample_code"
    sample_dir.mkdir()
    keep = sample_dir / "tmp_target_1.py"
    keep.write_text("x = 1\n", encoding="utf-8")
    (sample_dir / "tmp_target_2.py").write_text("x = 2\n", encoding="utf-8")
    (sample_dir / "example.py").write_text("x = 3\n", encoding="utf-8")

    removed = prune_tmp_targets(sample_dir, keep=keep)

    assert removed == 1
    assert keep.exists()
    assert (sample_dir / "example.py").exists()


# ---- generation -----------------------------------------------------------

def _generate(tmp_path, use_ai, llm_cfg=None, progress=None):
    source = tmp_path / "src.py"
    source.write_text(CALC, encoding="utf-8")
    analysis = analyze_source(source)
    return generate_tests(
        analysis=analysis,
        target_path=source,
        sample_dir=tmp_path / "sample_code",
        generated_dir=tmp_path / "generated",
        use_ai=use_ai,
        llm_cfg=llm_cfg or LLMConfig(provider="mock"),
        progress=progress,
    )


def test_deterministic_generation_writes_the_executable_suite(tmp_path):
    result = _generate(tmp_path, use_ai=False)

    assert result.mode == "deterministic"
    assert result.ai_code is None
    assert "def test_calculate_discount" in result.deterministic_code
    assert result.saved_path.read_text(encoding="utf-8") == result.deterministic_code


def test_ai_mode_keeps_the_deterministic_suite_alongside(tmp_path):
    result = _generate(tmp_path, use_ai=True, llm_cfg=LLMConfig(provider="mock"))

    assert result.mode == "ai"
    assert result.ai_code
    assert "def test_calculate_discount" in result.deterministic_code
    # The saved file - the one that gets executed - is always deterministic.
    assert result.saved_path.read_text(encoding="utf-8") == result.deterministic_code


def test_missing_credentials_fall_back_without_losing_tests(tmp_path):
    result = _generate(
        tmp_path, use_ai=True, llm_cfg=LLMConfig(provider="openai", api_key=None)
    )

    assert result.mode == "fallback"
    assert result.ai_code is None
    assert "Missing API key" in result.ai_error
    assert "def test_calculate_discount" in result.deterministic_code


def test_progress_reports_only_real_stages(tmp_path):
    seen = []
    _generate(tmp_path, use_ai=False, progress=seen.append)

    assert seen == [
        "Preparing target module",
        "Building test strategy",
        "Generating deterministic tests",
        "Saving test file",
    ]


def test_ai_progress_adds_the_provider_stages(tmp_path):
    seen = []
    _generate(tmp_path, use_ai=True, progress=seen.append)

    assert "Requesting AI tests" in seen
    assert "Validating AI output" in seen


# ---- staleness ------------------------------------------------------------

def test_fingerprint_changes_with_source_or_provider():
    base = source_fingerprint("x = 1", False, "mock")

    assert source_fingerprint("x = 1", False, "mock") == base
    assert source_fingerprint("x = 2", False, "mock") != base
    assert source_fingerprint("x = 1", True, "mock") != base
    assert source_fingerprint("x = 1", False, "openai") != base


def test_metrics_of_an_empty_analysis_are_all_zero():
    metrics = AnalysisResult(functions=[], classes=[], skipped_methods=0).metrics

    assert set(metrics.values()) == {0}
