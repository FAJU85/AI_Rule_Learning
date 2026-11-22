"""Score the real extraction path (gap_detector.distill_directive) against the
held-out extraction corpus, reporting the G1 metrics from docs/ACCEPTANCE.md:
directive recall, negative-set purity (G1.4), and multi-part split rate.

This is a measurement tool, not a CI gate — it prints the numbers so the
extraction rebuild can be driven test-first and reported honestly. Run:
    python acceptance/run_extraction.py
"""

from __future__ import annotations

import json
from pathlib import Path

from ai_rule_learning_mcp.gap_detector import distill_directive

CORPUS = Path(__file__).parent / "corpus" / "extraction.jsonl"


def _rules_for(text: str) -> list[str]:
    one = distill_directive(text)
    return [one] if one else []


def main() -> None:
    cases = [json.loads(line) for line in CORPUS.read_text().splitlines() if line.strip()]
    by_kind: dict[str, list[dict]] = {}
    for c in cases:
        by_kind.setdefault(c["kind"], []).append(c)

    print(f"corpus: {len(cases)} cases from {CORPUS.name}\n")

    directives = by_kind.get("directive", [])
    hit = 0
    for c in directives:
        rules = _rules_for(c["input"])
        ok = bool(rules) and all(sub in rules[0].lower() for sub in c["expect"])
        hit += ok
        if not ok:
            print(f"  [directive miss] {c['id']}: {rules!r}")
    print(f"G1 directive recall: {hit}/{len(directives)}")

    noise = by_kind.get("noise", [])
    rejected = 0
    for c in noise:
        rules = _rules_for(c["input"])
        ok = len(rules) == 0
        rejected += ok
        if not ok:
            print(f"  [noise accepted] {c['id']}: {rules!r}")
    print(f"G1.4 negative-set purity: {rejected}/{len(noise)}")

    multi = by_kind.get("multipart", [])
    split_ok = 0
    for c in multi:
        rules = _rules_for(c["input"])
        ok = len(rules) >= 2
        split_ok += ok
        if not ok:
            print(f"  [multipart not split] {c['id']}: {len(rules)} rule(s): {rules!r}")
    print(f"G1 multi-part split rate: {split_ok}/{len(multi)}")


if __name__ == "__main__":
    main()
