"""Backend glue between the Streamlit UI and the analyzer/generator/coverage layers.

Deliberately free of Streamlit imports so every stage can be unit tested. The UI
supplies a progress callback; this module decides nothing about presentation.
"""

from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from analyzer.code_analyzer import CodeAnalyzer
from cov_tools.coverage_analyzer import CoverageAnalyzer, CoverageResult
from llm import LLMConfig, generate_with_optional_llm
from test_generator.prompt_builder import build_llm_prompt, build_test_plan
from test_generator.test_generator import generate_pytest_code, save_tests

GENERATED_TEST_NAME = "test_generated_from_ui.py"

#: Only these characters survive filename sanitisation.
_SAFE_NAME = re.compile(r"[^A-Za-z0-9_.-]")

ProgressCallback = Callable[[str], None]


class SourceError(Exception):
    """The submitted source cannot be analysed. Carries a line when known."""

    def __init__(self, message: str, line: int | None = None):
        super().__init__(message)
        self.message = message
        self.line = line


@dataclass
class AnalysisResult:
    functions: list[dict]
    classes: list[str]
    skipped_methods: int

    @property
    def metrics(self) -> dict[str, int]:
        """Counts the analyzer can actually determine - nothing inferred."""
        return {
            "functions": len(self.functions),
            "branches": sum(1 for f in self.functions if f.get("has_if")),
            "loops": sum(1 for f in self.functions if f.get("has_for") or f.get("has_while")),
            "raises": sum(1 for f in self.functions if f.get("raises_value_error")),
            "async": sum(1 for f in self.functions if f.get("is_async")),
            "prints": sum(1 for f in self.functions if f.get("has_print")),
        }


@dataclass
class GenerationResult:
    module_import: str
    target_file: Path
    saved_path: Path
    test_plan: dict
    prompt: str
    deterministic_code: str
    ai_code: str | None = None
    ai_error: str | None = None

    @property
    def mode(self) -> str:
        """deterministic | ai | fallback - what the user actually received."""
        if self.ai_code:
            return "ai"
        if self.ai_error:
            return "fallback"
        return "deterministic"


def sanitize_filename(name: str) -> str:
    """Reduce an uploaded name to a bare, safe `.py` filename.

    Uploads are written to disk, so directory components and odd characters are
    stripped rather than trusted.
    """
    base = Path(name).name
    base = _SAFE_NAME.sub("_", base).lstrip(".")
    if not base:
        base = "uploaded.py"
    if not base.endswith(".py"):
        base = f"{base}.py"
    return base


def source_fingerprint(source: str, use_ai: bool, provider: str) -> str:
    """Identity of a run's inputs, so stale results can be detected."""
    import hashlib

    payload = f"{source}\x00{use_ai}\x00{provider}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def analyze_source(target_path: Path) -> AnalysisResult:
    """Parse the target file, converting parse failures into SourceError."""
    try:
        overview = CodeAnalyzer().analyze_module(str(target_path))
    except SyntaxError as exc:
        line = getattr(exc, "lineno", None)
        detail = (exc.msg or "invalid syntax").strip()
        if line:
            raise SourceError(f"Python syntax error on line {line}: {detail}", line) from exc
        raise SourceError(f"Python syntax error: {detail}") from exc
    except (UnicodeDecodeError, ValueError) as exc:
        raise SourceError(f"The file could not be read as Python source: {exc}") from exc

    return AnalysisResult(
        functions=overview["functions"],
        classes=overview["classes"],
        skipped_methods=overview["skipped_methods"],
    )


def stage_target_module(target_path: Path, sample_dir: Path) -> tuple[Path, str]:
    """Copy the source into data/sample_code under a fresh, importable name.

    A new name per run keeps a stale module out of sys.modules; older scratch
    copies are removed so they cannot pollute later coverage runs.
    """
    sample_dir.mkdir(parents=True, exist_ok=True)
    # The random suffix matters: the clock alone collides when two runs land in
    # the same millisecond, which would reuse a module name already in sys.modules.
    stem = f"tmp_target_{int(time.time())}_{uuid.uuid4().hex[:8]}"
    tmp_target = sample_dir / f"{stem}.py"
    tmp_target.write_text(target_path.read_text(encoding="utf-8"), encoding="utf-8")
    prune_tmp_targets(sample_dir, keep=tmp_target)
    return tmp_target, f"data.sample_code.{stem}"


def prune_tmp_targets(sample_dir: Path, keep: Path | None = None) -> int:
    """Delete scratch modules from earlier runs, optionally sparing `keep`."""
    removed = 0
    if not sample_dir.exists():
        return removed
    for p in sample_dir.glob("tmp_target_*.py"):
        if keep is not None and p.resolve() == keep.resolve():
            continue
        p.unlink(missing_ok=True)
        removed += 1
    return removed


def generate_tests(
    analysis: AnalysisResult,
    target_path: Path,
    sample_dir: Path,
    generated_dir: Path,
    use_ai: bool,
    llm_cfg: LLMConfig,
    progress: ProgressCallback | None = None,
) -> GenerationResult:
    """Build the test plan, emit deterministic tests, optionally ask an AI too.

    The deterministic suite is always produced: it is what gets executed, so AI
    generation is strictly additive and can never leave the user with nothing.
    """
    def step(label: str) -> None:
        if progress:
            progress(label)

    step("Preparing target module")
    tmp_target, module_import = stage_target_module(target_path, sample_dir)

    step("Building test strategy")
    test_plan = build_test_plan(analysis.functions)
    prompt = f"TARGET_MODULE_IMPORT={module_import}\n" + build_llm_prompt(test_plan)

    step("Generating deterministic tests")
    deterministic_code = generate_pytest_code(test_plan=test_plan, module_import=module_import)

    ai_code = None
    ai_error = None
    if use_ai:
        step("Requesting AI tests")
        llm_result = generate_with_optional_llm(prompt, llm_cfg)
        step("Validating AI output")
        if llm_result.source == "llm" and llm_result.code.strip():
            ai_code = llm_result.code
        else:
            ai_error = llm_result.error or "The AI provider returned no usable code."

    step("Saving test file")
    generated_dir.mkdir(parents=True, exist_ok=True)
    saved_path = save_tests(deterministic_code, generated_dir / GENERATED_TEST_NAME)

    return GenerationResult(
        module_import=module_import,
        target_file=tmp_target,
        saved_path=saved_path,
        test_plan=test_plan,
        prompt=prompt,
        deterministic_code=deterministic_code,
        ai_code=ai_code,
        ai_error=ai_error,
    )


def execute_tests(
    generation: GenerationResult,
    project_root: Path,
    sample_dir: Path,
    progress: ProgressCallback | None = None,
) -> CoverageResult:
    """Run the deterministic suite under coverage.py.

    Only the deterministic suite is executed. AI output is displayed and
    downloadable but never run, so an unvalidated model answer cannot execute
    in the user's environment.
    """
    if progress:
        progress("Running tests and measuring coverage")

    return CoverageAnalyzer().run_coverage(
        project_root=project_root,
        test_file=generation.saved_path,
        source_dir=sample_dir,
        target_file=generation.target_file,
        html=True,
    )


@dataclass
class Workspace:
    """Directories the UI writes into. Nothing is written outside these."""

    project_root: Path
    uploads: Path = field(init=False)
    sample_code: Path = field(init=False)
    generated_tests: Path = field(init=False)
    coverage_html: Path = field(init=False)

    def __post_init__(self) -> None:
        self.uploads = self.project_root / "data" / "uploads"
        self.sample_code = self.project_root / "data" / "sample_code"
        self.generated_tests = self.project_root / "tests" / "generated"
        self.coverage_html = self.project_root / "data" / "coverage_html"

    def ensure(self) -> None:
        for path in (self.uploads, self.sample_code, self.generated_tests):
            path.mkdir(parents=True, exist_ok=True)

    def write_source(self, content: str, filename: str) -> Path:
        """Write user source into uploads/ under a sanitised name."""
        safe = sanitize_filename(filename)
        target = self.uploads / safe
        target.write_text(content, encoding="utf-8")
        return target
