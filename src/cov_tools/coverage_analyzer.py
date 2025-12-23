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

        py = sys.executable  # aktif .venv python

        # 1) coverage run
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
            ],
            cwd=str(project_root),
            check=True,
        )

        # 2) terminal report
        subprocess.run(
            [py, "-m", "coverage", "report", "-m"],
            cwd=str(project_root),
            check=True,
        )

        # 3) HTML report (Windows-safe)
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
                    str(html_dir),   # <-- NO "-d=..."
                ],
                cwd=str(project_root),
                check=True,
            )
            print(f"\nHTML coverage report generated at: {html_dir}")
