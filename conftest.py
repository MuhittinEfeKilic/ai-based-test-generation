"""Make the project importable from tests without per-file sys.path juggling.

`src/` is added so tests can `from analyzer... import ...`, and the repo root is
added so generated tests can import `data.sample_code.<module>`.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"

for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
