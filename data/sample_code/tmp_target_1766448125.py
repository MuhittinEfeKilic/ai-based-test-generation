from __future__ import annotations

def classify_age(age: int) -> str:
    """Multiple branches + multiple returns."""
    if age < 0:
        return "invalid"
    if age < 18:
        return "child"
    if age < 65:
        return "adult"
    return "senior"


def safe_divide(a: float, b: float) -> float:
    """Guard return + normal return."""
    if b == 0:
        return 0.0
    return a / b


def sum_even_numbers(numbers: list[int]) -> int:
    """Loop + inner condition."""
    total = 0
    for n in numbers:
        if n % 2 == 0:
            total += n
    return total


def greet_many(name: str, times: int = 3) -> None:
    """Print output (capsys)."""
    for _ in range(times):
        print(f"Hello {name}")
