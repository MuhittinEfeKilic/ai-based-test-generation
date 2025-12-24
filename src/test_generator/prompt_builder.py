from dataclasses import asdict
from typing import Dict, List


def build_test_plan(analysis: List[Dict]) -> Dict:
    """
    LLM'e ya da rule-based üreticiye gidecek 'test plan' taslağı.
    Şimdilik basit kurallar: if/for/while ve return sayısına göre senaryo öner.
    """
    plan = {"functions": []}

    for fn in analysis:
        scenarios = []

        #Temel
        scenarios.append("valid typical inputs")
        scenarios.append("edge cases (zero/empty/None if applicable)")

        #Kontrol
        if fn.get("has_if"):
            scenarios.append("branches for conditional paths (true/false)")

        if fn.get("has_for") or fn.get("has_while"):
            scenarios.append("loop behavior (0 iterations, 1 iteration, many iterations)")

        if fn.get("has_print"):
            scenarios.append("prints output (capture with capsys)")

        #Return sayısına göre
        if fn.get("returns_count", 0) >= 2:
            scenarios.append("multiple return paths should be covered")

        plan["functions"].append(
            {
                 "name": fn["name"],
                "args": fn["args"],
                "annotations": fn.get("annotations", {}),
                #flags needed by generator
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


def build_llm_prompt(test_plan: Dict) -> str:
    """
    Week 4'te LLM entegrasyonunda kullanacağız. Şimdilik prompt metnini standart bir formatta üretelim.
    """
    lines = []
    lines.append("You are an assistant that writes pytest unit tests.")
    lines.append("Generate tests for the following functions based on the plan.")
    lines.append("Return only Python code.")
    lines.append("")
    for fn in test_plan["functions"]:
        lines.append(f"Function: {fn['name']}({', '.join(fn['args'])})")
        lines.append(f"HasPrint: {str(fn.get('has_print', False)).lower()}")
        lines.append("Scenarios:")
        for s in fn["recommended_scenarios"]:
            lines.append(f"- {s}")
        lines.append("")
    return "\n".join(lines)
