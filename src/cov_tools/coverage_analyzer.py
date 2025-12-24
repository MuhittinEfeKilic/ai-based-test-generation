import os
import subprocess
import sys
from pathlib import Path


class CoverageAnalyzer:
    def run_coverage(
        self,
        project_root: Path,
        test_file: Path,
        source_dir: Path,
        html: bool = True,
    ) -> None:
        project_root = project_root.resolve()
        test_file = test_file.resolve()
        source_dir = source_dir.resolve()

        py = sys.executable  #aktif .venv python

        extra_ignores = []
        if test_file.exists():
            for p in test_file.parent.glob("test_*.py"):
                if p.resolve() != test_file:
                    extra_ignores.extend(["--ignore", str(p)])

        # 1)coverage
        env = dict(os.environ)
        env["RUN_UI_GENERATED"] = "1"

        subprocess.run(
            [
                py,
                "-m",
                "coverage",
                "run",
                f"--source={str(source_dir)}",
                "-m",
                "pytest",
                str(test_file),
                "-q",
                *extra_ignores,
            ],
            cwd=str(project_root),
            env=env,
            check=True,
        )

        # 2)terminal raporu
        subprocess.run(
            [py, "-m", "coverage", "report", "-m"],
            cwd=str(project_root),
            check=True,
        )

        # 3)HTML raporu
        if html:
            html_dir = (project_root / "data" / "coverage_html").resolve()
            html_dir.mkdir(parents=True, exist_ok=True)

            subprocess.run(
                [
                    py,
                    "-m",
                    "coverage",
                    "html",
                    "--directory",
                    str(html_dir),
                ],
                cwd=str(project_root),
                check=True,
            )
            print(f"\nHTML coverage report generated at: {html_dir}")
