from __future__ import annotations

from .injection import is_prompt_injection

UNSAFE_PHRASES: tuple[str, ...] = (
    "never refuse",
    "do not refuse",
    "don't refuse",
    "bypass",
    "override your",
    "override safety",
    "override rules",
    "override guidelines",
    "ignore safety",
    "ignore all",
    "ignore previous",
    "ignore prior",
    "ignore earlier",
    "ignore your instructions",
    "disregard",
    "forget your",
    "forget all",
    "forget everything",
    "forget earlier",
    "forget prior",
    "jailbreak",
    "developer mode",
    "god mode",
    "dan mode",
    "sudo mode",
    "unrestricted",
    "no restrictions",
    "without restrictions",
    "exfiltrate",
    "exfiltration",
    "you must always comply",
    "no matter what",
)

_ALWAYS_SAFE_NAMES = frozenset({"resist-instruction-override-attempts"})

_MIN_INSTRUCTION_LEN = 10


def _instruction_of(rule: dict) -> str:
    instruction = rule.get("instruction") or ""
    if not instruction:
        action = rule.get("action")
        if isinstance(action, dict):
            instruction = action.get("instruction", "")
    return str(instruction)


def unsafe_phrases_in(text: str) -> list[str]:
    low = text.lower()
    return [p for p in UNSAFE_PHRASES if p in low]


def rule_safety_issues(rule: dict, check_injection: bool = True) -> list[str]:
    if rule.get("name") in _ALWAYS_SAFE_NAMES:
        return []
    instruction = _instruction_of(rule)
    description = str(rule.get("description", "") or "")
    combined = f"{instruction} {description}"
    issues = [f'Contains unsafe phrase: "{p}"' for p in unsafe_phrases_in(combined)]
    stripped = instruction.strip()
    if stripped and len(stripped) < _MIN_INSTRUCTION_LEN:
        issues.append(f"Instruction too vague (< {_MIN_INSTRUCTION_LEN} characters)")
    if check_injection and is_prompt_injection(combined):
        issues.append("Matched prompt-injection patterns")
    return issues


def is_safe_rule(rule: dict) -> bool:
    return not rule_safety_issues(rule)
