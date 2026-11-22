"""Unified acceptance scorecard for docs/ACCEPTANCE.md.

Reports the CURRENT, honest state of the gates against the committed thresholds,
so progress is legible and nothing is overstated. Pure measurement — it imports
the real product (enforcement.classify, gap_detector.distill_directive) and
changes nothing. Run:
    python acceptance/scorecard.py

Not yet covered here (needs resources/decisions, reported as N/A):
  - G2 application / model generality (needs a model API key and the behavioural suite)
  - G3 token accounting (needs the live injection path)
These stay N/A rather than being faked green.
"""

from __future__ import annotations

import json
from pathlib import Path

from ai_rule_learning_mcp.enforcement import _find_check
from ai_rule_learning_mcp.enforcement import classify
from ai_rule_learning_mcp.gap_detector import distill_directive

CORPUS = Path(__file__).parent / "corpus" / "extraction.jsonl"

# One representative rule per instruction family (the 10 families of the study).
FAMILIES = {
    "F01_no_comments": "Never include comments or docstrings in code.",
    "F02_type_hints": "Annotate every function parameter and the return type.",
    "F03_snake_case": "Use snake_case for all function and variable names.",
    "F04_no_print": "Never call print(); return values instead.",
    "F05_no_else": "Never use the else keyword; use early returns.",
    "F06_short_funcs": "Keep every function at most 10 non-blank lines.",
    "F07_pathlib": "Use pathlib.Path for file paths; never use os.path.",
    "F08_fstrings": "Build strings with f-strings only; never use .format().",
    "F09_valueerror": "Reject invalid input by raising ValueError.",
    "F10_single_block": "Respond with exactly one python code block.",
}


def enforcement_coverage() -> dict[str, int]:
    implemented = pending = soft = 0
    for _family, instruction in FAMILIES.items():
        c = classify({"instruction": instruction})
        if c.channel == "soft":
            soft += 1
            continue
        chk = _find_check(c.check_id)
        if chk and chk.implemented:
            implemented += 1
        else:
            pending += 1
    return {"implemented": implemented, "pending": pending, "soft": soft, "total": len(FAMILIES)}


def extraction_metrics() -> dict[str, tuple[int, int]]:
    cases = [json.loads(line) for line in CORPUS.read_text().splitlines() if line.strip()]
    by_kind: dict[str, list[dict]] = {}
    for c in cases:
        by_kind.setdefault(c["kind"], []).append(c)

    def rules_for(text: str) -> list[str]:
        one = distill_directive(text)
        return [one] if one else []

    directives = by_kind.get("directive", [])
    recall = sum(bool(r := rules_for(c["input"])) and all(s in r[0].lower() for s in c["expect"]) for c in directives)
    noise = by_kind.get("noise", [])
    purity = sum(len(rules_for(c["input"])) == 0 for c in noise)
    multi = by_kind.get("multipart", [])
    split = sum(len(rules_for(c["input"])) >= 2 for c in multi)
    return {
        "recall": (recall, len(directives)),
        "purity": (purity, len(noise)),
        "split": (split, len(multi)),
    }


def _mark(ok: bool | None) -> str:
    return "N/A " if ok is None else ("PASS" if ok else "FAIL")


def main() -> None:
    cov = enforcement_coverage()
    ex = extraction_metrics()
    print("=" * 64)
    print("ARL ACCEPTANCE SCORECARD (current state vs docs/ACCEPTANCE.md §6)")
    print("=" * 64)

    rows = [
        ("G1.2 extraction recall", f"{ex['recall'][0]}/{ex['recall'][1]}", ex["recall"][0] >= 9),
        ("G1.4 negative-set purity", f"{ex['purity'][0]}/{ex['purity'][1]}", ex["purity"][0] == ex["purity"][1]),
        ("G1 multi-part split", f"{ex['split'][0]}/{ex['split'][1]}", ex["split"][0] == ex["split"][1]),
        (
            "G4.1 routing invariant (pending=0)",
            f"{cov['pending']} pending",
            cov["pending"] == 0,
        ),
        (
            "enforcement coverage (implemented)",
            f"{cov['implemented']}/{cov['total']}",
            cov["implemented"] == cov["total"],
        ),
        ("G2 application / model generality", "needs model key + suite", None),
        ("G3 token accounting", "needs live injection path", None),
    ]
    for label, value, ok in rows:
        print(f"  [{_mark(ok)}] {label:38} {value}")
    print("=" * 64)
    print("Gates are failable by design; N/A is reported, never faked green.")


if __name__ == "__main__":
    main()
