import sys
from pathlib import Path

# Ensure project root is in sys.path so we can import the target module
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data.sample_code.example import add, greet

import pytest

def test_add_positive_numbers():
    assert add(2, 3) == 5

def test_add_non_positive_path():
    assert add(0, 5) == 0
    assert add(-1, 3) == 0

def test_greet_prints_twice(capsys):
    greet('Efe')
    captured = capsys.readouterr()
    assert captured.out.count('Hello') == 2
