import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

# pytest -q ends with lines like "1 failed, 5 passed in 0.12s".
_COUNT_RE = re.compile(r"(\d+)\s+(passed|failed|error|errors|skipped)\b")


@dataclass
class CoverageResult:
    ok: bool
    report: str
    pytest_output: str
    html_dir: Path | None = None
    percent: float | None = None
    counts: dict[str, int] = field(default_factory=dict)

    @property
    def total_tests(self) -> int:
        return sum(
            self.counts.get(key, 0) for key in ("passed", "failed", "error", "skipped")
        )


def parse_pytest_counts(output: str) -> dict[str, int]:
    """Pull passed/failed/error/skipped counts out of a pytest -q summary."""
    counts: dict[str, int] = {}
    for value, label in _COUNT_RE.findall(output):
        key = "error" if label == "errors" else label
        counts[key] = counts.get(key, 0) + int(value)
    return counts


class CoverageAnalyzer:
    """Run the generated tests under coverage.py in a child process."""

    def run_coverage(
        self,
        project_root: Path,
        test_file: Path,
        source_dir: Path,
        target_file: Path | None = None,
        html: bool = True,
    ) -> CoverageResult:
        """Measure coverage of `target_file`, or of `source_dir` when it is None.

        Scoping to a single file keeps unrelated modules that happen to sit in
        the same folder out of the totals.
        """
        project_root = project_root.resolve()
        test_file = test_file.resolve()
        source_dir = source_dir.resolve()

        if target_file is not None:
            scope = f"--include={target_file.resolve()}"
        else:
            scope = f"--source={source_dir}"

        py = sys.executable  # the active .venv interpreter

        # Only the file we just generated should run; siblings are left alone.
        extra_ignores = []
        if test_file.exists():
            for p in test_file.parent.glob("test_*.py"):
                if p.resolve() != test_file:
                    extra_ignores.extend(["--ignore", str(p)])

        env = dict(os.environ)
        env["RUN_UI_GENERATED"] = "1"

        # 1) run the tests under coverage
        run_proc = subprocess.run(
            [
                py,
                "-m",
                "coverage",
                "run",
                scope,
                "-m",
                "pytest",
                str(test_file),
                # Override project addopts: a second -q would suppress the
                # summary line the counts are parsed from.
                "-o",
                "addopts=",
                "-q",
                *extra_ignores,
            ],
            cwd=str(project_root),
            env=env,
            capture_output=True,
            text=True,
        )
        pytest_output = (run_proc.stdout or "") + (run_proc.stderr or "")

        # 2) terminal report
        report_proc = subprocess.run(
            [py, "-m", "coverage", "report", "-m"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
        )
        report = (report_proc.stdout or "") + (report_proc.stderr or "")

        percent = self._total_percent(py, project_root)

        # 3) HTML report
        html_dir = None
        if html:
            html_dir = (project_root / "data" / "coverage_html").resolve()
            html_dir.mkdir(parents=True, exist_ok=True)

            subprocess.run(
                [py, "-m", "coverage", "html", "--directory", str(html_dir)],
                cwd=str(project_root),
                capture_output=True,
                text=True,
            )

        return CoverageResult(
            ok=run_proc.returncode == 0,
            report=report,
            pytest_output=pytest_output,
            html_dir=html_dir,
            percent=percent,
            counts=parse_pytest_counts(pytest_output),
        )

    def _total_percent(self, py: str, project_root: Path) -> float | None:
        """Ask coverage.py for the single total number, or None if unavailable."""
        proc = subprocess.run(
            [py, "-m", "coverage", "report", "--format=total"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
        )
        try:
            return float(proc.stdout.strip())
        except (TypeError, ValueError):
            return None
