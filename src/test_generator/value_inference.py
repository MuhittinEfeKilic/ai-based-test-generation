"""Infer interesting argument values for a function from its own source.

The deterministic generator is only as good as the values it feeds in. Rather
than guessing from parameter names, this module reads what the body actually
does with each parameter - which literals it is compared against, which
comparisons guard a `raise`, whether it is tested for None or used as a truth
value - and turns that into an ordered list of candidate values.

Everything here is pure AST analysis: no execution, no I/O, deterministic.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Any

# `param OP const` -> the operator to use when the parameter is on the right.
_MIRROR = {"<": ">", "<=": ">=", ">": "<", ">=": "<=", "==": "==", "!=": "!="}

_OP_SYMBOLS = {
    ast.Lt: "<",
    ast.LtE: "<=",
    ast.Gt: ">",
    ast.GtE: ">=",
    ast.Eq: "==",
    ast.NotEq: "!=",
}

ARITHMETIC_OPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod, ast.Pow, ast.FloorDiv)

#: Default magnitude for a numeric parameter with no constraints. A round
#: hundred keeps derived expected values readable (100 * 0.8 -> 80.0).
NUMERIC_BASE = 100


@dataclass
class Comparison:
    """A `param OP const` fact read off the AST."""

    op: str
    const: Any


@dataclass
class ParamEvidence:
    name: str
    equality_values: list = field(default_factory=list)
    comparisons: list[Comparison] = field(default_factory=list)
    guard_comparisons: list[Comparison] = field(default_factory=list)
    none_checked: bool = False
    truth_tested: bool = False
    iterated: bool = False
    subscript_keys: set = field(default_factory=set)
    arithmetic: bool = False

    @property
    def is_numeric(self) -> bool:
        if self.arithmetic:
            return True
        return any(
            isinstance(c.const, (int, float)) and not isinstance(c.const, bool)
            for c in self.comparisons
        )

    @property
    def is_stringy(self) -> bool:
        return any(isinstance(v, str) for v in self.equality_values)


def _op_symbol(op: ast.cmpop) -> str | None:
    return _OP_SYMBOLS.get(type(op))


def _literal(node: ast.AST):
    """Return (ok, value) for a node that is a plain literal constant."""
    if isinstance(node, ast.Constant):
        return True, node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        if isinstance(node.operand, ast.Constant) and isinstance(
            node.operand.value, (int, float)
        ):
            return True, -node.operand.value
    return False, None


def _comparisons_in(test: ast.AST, names: set[str]) -> list[tuple[str, Comparison]]:
    """Every `param OP literal` fact inside a condition, as (param, comparison)."""
    found: list[tuple[str, Comparison]] = []
    for node in ast.walk(test):
        if not isinstance(node, ast.Compare):
            continue
        left = node.left
        for op, right in zip(node.ops, node.comparators):
            symbol = _op_symbol(op)
            if symbol is None:
                left = right
                continue

            if isinstance(left, ast.Name) and left.id in names:
                ok, value = _literal(right)
                if ok:
                    found.append((left.id, Comparison(symbol, value)))
            elif isinstance(right, ast.Name) and right.id in names:
                ok, value = _literal(left)
                if ok:
                    found.append((right.id, Comparison(_MIRROR[symbol], value)))
            left = right
    return found


def _raises(node: ast.AST) -> bool:
    return any(isinstance(n, ast.Raise) for n in ast.walk(node))


def collect_evidence(function_source: str, param_names: list[str]) -> dict[str, ParamEvidence]:
    """Read every parameter's observable usage out of the function body."""
    evidence = {name: ParamEvidence(name=name) for name in param_names}
    if not function_source or not param_names:
        return evidence

    try:
        tree = ast.parse(function_source)
    except SyntaxError:
        return evidence

    names = set(param_names)

    for node in ast.walk(tree):
        # Comparisons that guard a raise tell us how to trigger the error path.
        if isinstance(node, ast.If):
            guarded = any(_raises(stmt) for stmt in node.body)
            for param, comparison in _comparisons_in(node.test, names):
                if guarded:
                    evidence[param].guard_comparisons.append(comparison)

            for sub in ast.walk(node.test):
                if isinstance(sub, ast.Name) and sub.id in names:
                    parent_is_compare = any(
                        sub in ast.walk(c) for c in ast.walk(node.test)
                        if isinstance(c, ast.Compare)
                    )
                    if not parent_is_compare:
                        evidence[sub.id].truth_tested = True

        if isinstance(node, ast.Compare):
            left = node.left
            for op, right in zip(node.ops, node.comparators):
                if isinstance(op, (ast.Is, ast.IsNot)):
                    for side in (left, right):
                        other = right if side is left else left
                        if isinstance(side, ast.Name) and side.id in names:
                            if isinstance(other, ast.Constant) and other.value is None:
                                evidence[side.id].none_checked = True
                left = right

            for param, comparison in _comparisons_in(node, names):
                evidence[param].comparisons.append(comparison)
                if comparison.op == "==":
                    if comparison.const not in evidence[param].equality_values:
                        evidence[param].equality_values.append(comparison.const)

        if isinstance(node, (ast.For, ast.AsyncFor)) and isinstance(node.iter, ast.Name):
            if node.iter.id in names:
                evidence[node.iter.id].iterated = True

        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
            if node.value.id in names:
                key = node.slice
                if isinstance(key, ast.Index):  # Python < 3.9 shape
                    key = key.value
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    evidence[node.value.id].subscript_keys.add(key.value)

        if isinstance(node, ast.BinOp) and isinstance(node.op, ARITHMETIC_OPS):
            for side in (node.left, node.right):
                if isinstance(side, ast.Name) and side.id in names:
                    evidence[side.id].arithmetic = True

    return evidence


def _same_type_step(const, delta: int):
    """const +/- 1, preserving int vs float."""
    if isinstance(const, bool):
        return not const
    if isinstance(const, int):
        return const + delta
    if isinstance(const, float):
        return const + float(delta)
    return None


def value_satisfying(comparison: Comparison, satisfy: bool):
    """A value making `param OP const` true (or false).

    Boundary values are preferred: for `x <= 0` the triggering value is 0
    itself, which is the case most likely to be mishandled.
    """
    op, const = comparison.op, comparison.const

    if isinstance(const, str):
        if op == "==":
            return const if satisfy else _neutral_string([const])
        if op == "!=":
            return _neutral_string([const]) if satisfy else const
        return None

    if not isinstance(const, (int, float)) or isinstance(const, bool):
        return None

    if op == "==":
        return const if satisfy else _same_type_step(const, 1)
    if op == "!=":
        return _same_type_step(const, 1) if satisfy else const
    if op == "<":
        return _same_type_step(const, -1) if satisfy else const
    if op == "<=":
        return const if satisfy else _same_type_step(const, 1)
    if op == ">":
        return _same_type_step(const, 1) if satisfy else const
    if op == ">=":
        return const if satisfy else _same_type_step(const, -1)
    return None


def _neutral_string(known: list) -> str:
    """A string deliberately unequal to every literal the code compares against."""
    candidate = "other"
    suffix = 1
    while candidate in known:
        candidate = f"other{suffix}"
        suffix += 1
    return candidate


def _neutral_value(evidence: ParamEvidence):
    """A value that misses every equality branch, exercising the default path."""
    literals = evidence.equality_values
    if not literals:
        return None
    if any(isinstance(v, str) for v in literals):
        return _neutral_string([v for v in literals if isinstance(v, str)])
    numeric = [v for v in literals if isinstance(v, (int, float)) and not isinstance(v, bool)]
    if numeric:
        return _same_type_step(max(numeric), 1)
    return None


def baseline_value(
    evidence: ParamEvidence,
    fallback,
    numeric_ok: bool = True,
    prefer_float: bool = False,
):
    """The value used when a scenario is not deliberately varying this parameter.

    Chosen to avoid every raise guard and every equality branch, so the baseline
    exercises the function's default path. `numeric_ok` is False when the
    annotation states a definitely non-numeric type: a declared type always
    outranks what the body happens to do with the value (`word * 2` is
    arithmetic, but `word: str` still means a string).
    """
    if evidence.guard_comparisons:
        value = _valid_against_guards(evidence, fallback, numeric_ok, prefer_float)
        if value is not None:
            return value

    neutral = _neutral_value(evidence)
    if neutral is not None:
        return neutral

    # A parameter used only as a truth value defaults to False, so the baseline
    # falls through to the else-branch and True becomes the interesting case.
    if evidence.truth_tested and not evidence.is_numeric and not evidence.equality_values:
        return False

    if numeric_ok and evidence.is_numeric:
        return _numeric_default(evidence, prefer_float)

    return fallback


def _numeric_default(evidence: ParamEvidence, prefer_float: bool = False):
    """NUMERIC_BASE, as float when the code or the annotation implies one."""
    if prefer_float or any(isinstance(c.const, float) for c in evidence.comparisons):
        return float(NUMERIC_BASE)
    return NUMERIC_BASE


def _valid_against_guards(
    evidence: ParamEvidence,
    fallback,
    numeric_ok: bool = True,
    prefer_float: bool = False,
):
    """A value that makes every raise guard false."""
    neutral = _neutral_value(evidence)
    if numeric_ok and evidence.is_numeric:
        candidate = _numeric_default(evidence, prefer_float)
    elif neutral is not None:
        # The parameter is compared against literals, so start from a value of
        # the same shape rather than a name-based guess.
        candidate = neutral
    else:
        candidate = fallback

    for comparison in evidence.guard_comparisons:
        if _holds(candidate, comparison):
            candidate = value_satisfying(comparison, satisfy=False)

    if candidate is None:
        return None

    # One more pass: stepping away from one guard may have violated another.
    for comparison in evidence.guard_comparisons:
        if _holds(candidate, comparison):
            return None
    return candidate


def _holds(value, comparison: Comparison) -> bool:
    """Whether `value OP const` is true, ignoring incomparable types."""
    if value is None:
        return False
    op, const = comparison.op, comparison.const
    try:
        if op == "==":
            return value == const
        if op == "!=":
            return value != const
        if op == "<":
            return value < const
        if op == "<=":
            return value <= const
        if op == ">":
            return value > const
        if op == ">=":
            return value >= const
    except TypeError:
        return False
    return False


def guard_trigger_values(evidence: ParamEvidence) -> list:
    """Values likely to trip this parameter's raise guards, boundary first."""
    values = []
    for comparison in evidence.guard_comparisons:
        value = value_satisfying(comparison, satisfy=True)
        if value is not None and value not in values:
            values.append(value)
    return values


def branch_values(evidence: ParamEvidence) -> list:
    """Values that steer the function into a specific non-error branch."""
    values: list = []

    for literal in evidence.equality_values:
        if literal not in values:
            values.append(literal)

    if evidence.none_checked and None not in values:
        values.append(None)

    if evidence.truth_tested:
        for flag in (True, False):
            if flag not in values:
                values.append(flag)

    # Boundary values on the *valid* side of each raise guard.
    for comparison in evidence.guard_comparisons:
        value = value_satisfying(comparison, satisfy=False)
        if value is not None and value not in values:
            values.append(value)

    # Ordinary comparisons steer non-error branches too: `score >= 90` wants
    # both 90 (taken) and 89 (not taken).
    for comparison in evidence.comparisons:
        if comparison in evidence.guard_comparisons or comparison.op in {"==", "!="}:
            continue
        for satisfy in (True, False):
            value = value_satisfying(comparison, satisfy)
            if value is not None and value not in values:
                values.append(value)

    return values
