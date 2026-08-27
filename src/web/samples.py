"""Sample programs offered in the editor.

Each one exercises a different part of the analyzer, so the sample buttons
double as a quick tour of what the generator can detect.
"""

from __future__ import annotations

from dataclasses import dataclass

CALCULATOR = '''def calculate_discount(price, discount):
    if price < 0:
        raise ValueError("Price cannot be negative")

    if discount < 0 or discount > 100:
        raise ValueError("Discount must be between 0 and 100")

    return price * (1 - discount / 100)


def apply_bulk_pricing(items):
    total = 0
    for item in items:
        total += item["quantity"] * item["price"]
    if total > 100:
        return total * 0.9
    return total
'''

USER_VALIDATION = '''def classify_age(age: int) -> str:
    if age < 0:
        raise ValueError("Age cannot be negative")
    if age < 13:
        return "child"
    if age < 20:
        return "teenager"
    if age < 65:
        return "adult"
    return "senior"


def validate_username(username: str) -> bool:
    if not username:
        print("Username is required")
        return False
    if len(username) < 3:
        print("Username is too short")
        return False
    return True
'''


@dataclass(frozen=True)
class Sample:
    key: str
    label: str
    description: str
    code: str


SAMPLES = (
    Sample(
        key="calculator",
        label="Calculator",
        description="Branching, a loop and two validation errors.",
        code=CALCULATOR,
    ),
    Sample(
        key="validation",
        label="User validation",
        description="Multiple return paths and printed output.",
        code=USER_VALIDATION,
    ),
)
