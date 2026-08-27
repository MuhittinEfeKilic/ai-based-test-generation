from typing import Dict, List

# Guard against pathological inputs blowing up the prompt: a single function
# body is truncated past this many characters.
MAX_SOURCE_CHARS = 2000


def build_test_plan(analysis: List[Dict]) -> Dict:
    """Turn raw analyzer output into a test plan.

    The plan is the single contract shared by both generators: the rule-based
    one reads the flags, the LLM one reads the scenarios and source.
    """
    plan = {"functions": []}

    for fn in analysis:
        scenarios = []

        # Always worth covering
        scenarios.append("valid typical inputs")
        scenarios.append("edge cases (zero/empty/None if applicable)")

        # Control flow
        if fn.get("has_if"):
            scenarios.append("branches for conditional paths (true/false)")

        if fn.get("has_for") or fn.get("has_while"):
            scenarios.append("loop behavior (0 iterations, 1 iteration, many iterations)")

        if fn.get("has_print"):
            scenarios.append("prints output (capture with capsys)")

        if fn.get("raises_value_error"):
            scenarios.append("invalid input raises ValueError")

        # Distinct exit points
        if fn.get("returns_count", 0) >= 2:
            scenarios.append("multiple return paths should be covered")

        plan["functions"].append(
            {
                "name": fn["name"],
                "args": fn["args"],
                "annotations": fn.get("annotations", {}),
                "defaults": fn.get("defaults", {}),
                "is_async": fn.get("is_async", False),
                # flags needed by generator
                "has_if": fn.get("has_if", False),
                "has_for": fn.get("has_for", False),
                "has_while": fn.get("has_while", False),
                "returns_count": fn.get("returns_count", 0),
                "has_print": fn.get("has_print", False),
                "print_strings": fn.get("print_strings", []),
                "has_negative_check": fn.get("has_negative_check", False),
                "raises_value_error": fn.get("raises_value_error", False),
                "source": fn.get("source", ""),
                "recommended_scenarios": scenarios,
            }
        )

    return plan


def _truncate(source: str) -> str:
    if len(source) <= MAX_SOURCE_CHARS:
        return source
    return source[:MAX_SOURCE_CHARS] + "\n# ... truncated ..."


def build_llm_prompt(test_plan: Dict) -> str:
    """Render the plan as an LLM prompt.

    The function bodies are included verbatim: without them the model can only
    guess at behaviour from the signature, which produces assertions that
    compile but do not actually pin anything down.
    """
    lines = []
    lines.append("You are an assistant that writes pytest unit tests.")
    lines.append("Generate tests for the following functions based on the plan and source.")
    lines.append("Rules:")
    lines.append("- Return only Python code, no prose.")
    lines.append("- Import the functions from the module given by TARGET_MODULE_IMPORT.")
    lines.append("- Assert on concrete expected values, not just `is not None`.")
    lines.append("- Use the capsys fixture for functions that print.")
    lines.append("- Use pytest.raises for documented error paths.")
    lines.append("")

    for fn in test_plan["functions"]:
        prefix = "async def" if fn.get("is_async") else "def"
        lines.append(f"Function: {fn['name']}({', '.join(fn['args'])})")
        lines.append(f"Definition: {prefix}")
        lines.append(f"HasPrint: {str(fn.get('has_print', False)).lower()}")

        annotations = {k: v for k, v in (fn.get("annotations") or {}).items() if v}
        if annotations:
            rendered = ", ".join(f"{k}: {v}" for k, v in annotations.items())
            lines.append(f"Annotations: {rendered}")

        if fn.get("defaults"):
            rendered = ", ".join(f"{k}={v}" for k, v in fn["defaults"].items())
            lines.append(f"Defaults: {rendered}")

        lines.append("Scenarios:")
        for s in fn["recommended_scenarios"]:
            lines.append(f"- {s}")

        source = fn.get("source", "")
        if source:
            lines.append("Source:")
            lines.append("```python")
            lines.append(_truncate(source))
            lines.append("```")

        lines.append("")

    return "\n".join(lines)
