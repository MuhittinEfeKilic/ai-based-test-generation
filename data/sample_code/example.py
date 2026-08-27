"""Sample target module.

Each function exercises a different branch of the generator: multiple returns,
a guard clause, a loop, printed output, a raised ValueError, and an async
definition.
"""

from __future__ import annotations

import asyncio


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


def calculate_discount(price: float, discount: float) -> float:
    """Validation errors (pytest.raises)."""
    if price < 0:
        raise ValueError("Price cannot be negative")
    if discount < 0 or discount > 100:
        raise ValueError("Discount must be between 0 and 100")
    return price * (1 - discount / 100)


async def fetch_total(items: list[dict]) -> float:
    """Async definition (asyncio.run in the generated test)."""
    await asyncio.sleep(0)
    return sum(item["quantity"] * item["price"] for item in items)
