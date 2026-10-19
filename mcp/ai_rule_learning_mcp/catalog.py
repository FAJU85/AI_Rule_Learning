"""Rule Catalog manager, validator, and activation engine for PyPI package.

Provides schema validation, source citation auditing, contradiction detection,
context detection, token-budgeted selection, continuous improvement tracking,
and rationale explanation ('why').
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

CITATION_PATTERNS = [
    r"DOI:\s*10\.\d{4,9}/[-._;()/:A-Za-z0-9]+",
    r"arXiv:\s*\d{4}\.\d{4,5}",
    r"CWE-\d+",
    r"OWASP",
    r"ACL:\s*[-._;()/:A-Za-z0-9]+",
    r"CodeQL",
    r"OpenAI",
    r"Anthropic",
]

_PKG_DATA_DIR = Path(__file__).parent / "data"
_DEFAULT_CATALOG_PATH = (
    _PKG_DATA_DIR / "catalog_v1.json"
    if (_PKG_DATA_DIR / "catalog_v1.json").exists()
    else Path("data/catalog_v1.json")
)
_DEFAULT_SCHEMA_PATH = (
    _PKG_DATA_DIR / "context_schema.json"
    if (_PKG_DATA_DIR / "context_schema.json").exists()
    else Path("data/context_schema.json")
)
_DEFAULT_METRICS_PATH = Path("data/rule_metrics.json")
_ACTIVE_RULES_PATH = Path.home() / ".ai-rule-learning" / "active_rules.json"


class CatalogValidationError(Exception):
    """Raised when catalog schema, citation, or contradiction validation fails."""


def estimate_tokens(text: str) -> int:
    """Accurately estimate token count for prompt formatting."""
    words = len(text.split())
    return max(1, int(words * 1.33) + 2)


def detect_context(conversation: Any) -> dict[str, str]:
    """Extract language, task_type, recent_patterns, framework, context_length,
    and user_style from a conversation object, list of turns, or raw string.
    """
    raw_text = ""
    turns_count = 1

    if isinstance(conversation, str):
        raw_text = conversation
        turns_count = max(1, len(conversation.split("\n\n")))
    elif isinstance(conversation, list):
        turns_count = len(conversation)
        parts = []
        for turn in conversation:
            if isinstance(turn, str):
                parts.append(turn)
            elif isinstance(turn, dict):
                parts.append(str(turn.get("content") or turn.get("user_input") or turn.get("ai_response") or ""))
            elif hasattr(turn, "user_input"):
                parts.append(f"{turn.user_input} {getattr(turn, 'ai_response', '')}")
            else:
                parts.append(str(turn))
        raw_text = " ".join(parts)
    elif isinstance(conversation, dict):
        turns = conversation.get("turns") or conversation.get("messages") or []
        if isinstance(turns, list):
            turns_count = len(turns)
            parts = []
            for t in turns:
                if isinstance(t, dict):
                    parts.append(str(t.get("content") or t.get("user_input") or ""))
                else:
                    parts.append(str(t))
            raw_text = " ".join(parts)
        else:
            raw_text = str(conversation.get("content") or conversation)
    else:
        raw_text = str(conversation)

    text_lower = raw_text.lower()
    total_words = len(raw_text.split())

    # 1. Detect language
    detected_lang = "agnostic"
    if re.search(r"```python|\bpython\b|\bdef\s+\w+\b|\bimport\s+[a-z0-9_]+\b|\bpytest\b", text_lower):
        detected_lang = "python"
    elif re.search(r"```typescript|```ts|\btypescript\b|\binterface\s+\w+\b|\btype\s+\w+\s*=|\bas\s+const\b", text_lower):
        detected_lang = "typescript"
    elif re.search(r"```javascript|```js|\bjavascript\b|\bconst\s+\w+\s*=\s*require\(", text_lower):
        detected_lang = "javascript"
    elif re.search(r"```go|```golang|\bgolang\b|\bgo\b|\bfunc\s+\w+\b|\bpackage\s+\w+\b", text_lower):
        detected_lang = "go"
    elif re.search(r"```rust|```rs|\brust\b|\bfn\s+\w+\b|\bimpl\s+\w+\b|\bpub\s+fn\b|\bmut\b", text_lower):
        detected_lang = "rust"
    elif re.search(r"```sql|\bsql\b|\bselect\s+.*?\s+from\b|\bcreate\s+table\b|\bwhere\s+.*?\s*=\b", text_lower):
        detected_lang = "sql"
    elif re.search(r"```bash|```sh|\bbash\b|\bshell\b|\bcurl\s+-|\bchmod\b|\bexport\s+\w+=", text_lower):
        detected_lang = "bash"

    # 2. Detect task_type
    detected_task = "code_generation"
    if re.search(r"\bsecurity\b|\bvulnerability\b|\bcwe-\d+|\bowasp\b|\bsanitiz|\binjection\b|\bcsrf\b|\bxss\b|\bexploit\b", text_lower):
        detected_task = "security_audit"
    elif re.search(r"\bdebug\b|\berror\b|\btraceback\b|\bexception\b|\bfailed\b|\bbug\b|\bcrash\b|\bwhy does this fail\b", text_lower):
        detected_task = "debugging"
    elif re.search(r"\btest\b|\bpytest\b|\bunit test\b|\bmock\b|\bfixture\b|\bcoverage\b|\bassert\b", text_lower):
        detected_task = "testing"
    elif re.search(r"\brefactor\b|\bcleanup\b|\bmodernize\b|\brestructure\b|\bsimplify\b", text_lower):
        detected_task = "refactoring"
    elif re.search(r"\barchitect\b|\barchitecture\b|\bsystem design\b|\bschema\b|\bmicroservice\b|\binfrastructure\b", text_lower):
        detected_task = "architecture"

    # 3. Detect recent_patterns
    detected_pattern = "none"
    if re.search(r"\bactually\b|\bno,? that'?s wrong\b|\byou'?re wrong\b|\bincorrect\b|\bwrong approach\b|\bfix this\b", text_lower):
        detected_pattern = "user_correction"
    elif re.search(r"\bignore previous instructions\b|\bjailbreak\b|\boverride your rules\b|\bsystem prompt\b", text_lower):
        detected_pattern = "injection_attempt"

    # 4. Detect framework
    detected_framework = "none"
    for fw in ["fastapi", "react", "nextjs", "django", "flask", "express", "pytest", "tailwind"]:
        if re.search(rf"\b{fw}\b", text_lower):
            detected_framework = fw
            break

    # 5. Detect context_length
    if total_words < 200 and turns_count <= 2:
        detected_length = "short"
    elif total_words < 1000 and turns_count <= 5:
        detected_length = "medium"
    elif total_words < 3000 and turns_count <= 12:
        detected_length = "long"
    elif total_words < 8000 and turns_count <= 25:
        detected_length = "extended"
    else:
        detected_length = "extreme"

    # 6. Detect user_style
    detected_style = "technical"
    if re.search(r"\bconcise\b|\bbrief\b|\bshort\b|\bno fluff\b|\bjust code\b", text_lower):
        detected_style = "concise"

    return {
        "language": detected_lang,
        "task_type": detected_task,
        "recent_patterns": detected_pattern,
        "framework": detected_framework,
        "context_length": detected_length,
        "user_style": detected_style,
    }


class RuleCatalog:
    """Manages static rule catalog operations, validation, and context-based activation."""

    def __init__(
        self,
        catalog_path: str | Path | None = None,
        schema_path: str | Path | None = None,
        metrics_path: str | Path | None = None,
    ) -> None:
        self.catalog_path = Path(catalog_path or _DEFAULT_CATALOG_PATH)
        self.schema_path = Path(schema_path or _DEFAULT_SCHEMA_PATH)
        self.metrics_path = Path(metrics_path or _DEFAULT_METRICS_PATH)
        self.schema: dict[str, Any] = {}
        self.rules: list[dict[str, Any]] = []
        self._rules_by_gap: dict[str, dict[str, Any]] = {}
        self._rules_by_category: dict[str, list[dict[str, Any]]] = {}
        self.metrics: dict[str, dict[str, Any]] = {}

        if self.schema_path.exists():
            self._load_schema()
        if self.catalog_path.exists():
            self._load_catalog()

    def _load_schema(self) -> None:
        try:
            with open(self.schema_path, encoding="utf-8") as f:
                self.schema = json.load(f)
        except Exception:
            self.schema = {}

    def _load_catalog(self) -> None:
        try:
            with open(self.catalog_path, encoding="utf-8") as f:
                data = json.load(f)
            self.rules = data.get("rules", [])
            self._index_rules()
        except Exception as exc:
            logger.warning("Failed to load catalog from %s: %s", self.catalog_path, exc)
            self.rules = []

    def _index_rules(self) -> None:
        self._rules_by_gap.clear()
        self._rules_by_category.clear()
        for r in self.rules:
            gt = r.get("gap_type") or r.get("id", "unknown")
            cat = r.get("category", "robustness_consistency")
            self._rules_by_gap[gt] = r
            if cat not in self._rules_by_category:
                self._rules_by_category[cat] = []
            self._rules_by_category[cat].append(r)

    @property
    def total_rules(self) -> int:
        return len(self.rules)

    @property
    def categories(self) -> list[str]:
        return sorted(list(self._rules_by_category.keys()))

    def get_rule(self, gap_type: str) -> dict[str, Any] | None:
        return self._rules_by_gap.get(gap_type)

    def get_category_rules(self, category: str) -> list[dict[str, Any]]:
        return self._rules_by_category.get(category, [])

    def activate(self, context: dict[str, Any]) -> list[dict[str, Any]]:
        """Find catalog rules matching the trigger_if conditions of context."""
        activated: list[dict[str, Any]] = []
        for r in self.rules:
            trigger_if = r.get("trigger_if", {})
            exclude_if = r.get("exclude_if", {})

            triggers_match = True
            for k, expected_v in trigger_if.items():
                actual_v = context.get(k)
                if actual_v is None:
                    triggers_match = False
                    break
                if expected_v != "any" and actual_v != "any" and actual_v != expected_v:
                    triggers_match = False
                    break

            if not triggers_match:
                continue

            excluded = False
            for k, excl_v in exclude_if.items():
                actual_v = context.get(k)
                if actual_v is not None and (excl_v == actual_v or excl_v == "any"):
                    excluded = True
                    break

            if excluded:
                continue

            activated.append(r)

        activated.sort(key=lambda x: x.get("priority", 3), reverse=True)
        return activated

    def select(
        self,
        context: dict[str, Any],
        budget_tokens: int = 500,
        max_rules: int = 10,
    ) -> list[dict[str, Any]]:
        """Select up to max_rules (<=10) within budget_tokens (<=500).
        Generates selection rationale and persists active_rules.json.
        """
        scored_candidates: list[tuple[float, dict[str, Any], str]] = []

        for r in self.rules:
            gt = r.get("gap_type") or r.get("id", "unknown")
            trigger_if = r.get("trigger_if", {})
            exclude_if = r.get("exclude_if", {})

            excluded = False
            for k, excl_v in exclude_if.items():
                actual_v = context.get(k)
                if actual_v is not None and (excl_v == actual_v or excl_v == "any"):
                    excluded = True
                    break
            if excluded:
                continue

            score = float(r.get("priority", 3) * 10)
            matched_keys: list[str] = []

            for k, expected_v in trigger_if.items():
                actual_v = context.get(k)
                if actual_v is not None:
                    if expected_v == actual_v:
                        score += 25.0
                        matched_keys.append(f"{k}='{actual_v}'")
                    elif expected_v == "any" or actual_v == "any":
                        score += 10.0
                        matched_keys.append(f"{k}=any")

            if matched_keys:
                rationale = f"Matched triggers [{', '.join(matched_keys)}]; priority={r.get('priority', 3)}"
                scored_candidates.append((score, r, rationale))

        scored_candidates.sort(key=lambda x: x[0], reverse=True)

        selected: list[dict[str, Any]] = []
        accumulated_tokens = 0

        for score, r, rationale in scored_candidates:
            if len(selected) >= max_rules:
                break
            rule_text = f"{r.get('gap_type')}: {r.get('instruction')}"
            cost = estimate_tokens(rule_text)
            if accumulated_tokens + cost <= budget_tokens:
                rule_copy = dict(r)
                rule_copy["selection_reason"] = rationale
                selected.append(rule_copy)
                accumulated_tokens += cost

        # Fallback to priority-5 rules if no rules match context
        if not selected and self.rules:
            p5_candidates = [r for r in self.rules if r.get("priority") == 5]
            if not p5_candidates:
                p5_candidates = sorted(self.rules, key=lambda x: x.get("priority", 3), reverse=True)[:5]
            for r in p5_candidates:
                if len(selected) >= max_rules:
                    break
                cost = estimate_tokens(f"{r.get('gap_type')}: {r.get('instruction')}")
                if accumulated_tokens + cost <= budget_tokens:
                    rule_copy = dict(r)
                    rule_copy["selection_reason"] = "Fallback baseline rule selected for empty/unmatched context"
                    selected.append(rule_copy)
                    accumulated_tokens += cost

        self._write_active_rules(context, selected, accumulated_tokens, budget_tokens)
        return selected

    def _write_active_rules(
        self,
        context: dict[str, Any],
        selected_rules: list[dict[str, Any]],
        accumulated_tokens: int,
        budget_tokens: int,
    ) -> None:
        global _ACTIVE_RULES_PATH
        if _ACTIVE_RULES_PATH.name == "active_rules.json" and _ACTIVE_RULES_PATH.parent.name == ".ai-rule-learning":
            _ACTIVE_RULES_PATH = Path.home() / ".ai-rule-learning" / "active_rules.json"
        try:
            _ACTIVE_RULES_PATH.parent.mkdir(parents=True, exist_ok=True)
            active_rules_list = [
                {
                    "rule_id": r.get("rule_id") or f"catalog-{r.get('gap_type')}",
                    "gap_type": r.get("gap_type"),
                    "category": r.get("category"),
                    "priority": r.get("priority"),
                    "instruction": r.get("instruction"),
                    "selection_reason": r.get("selection_reason", ""),
                }
                for r in selected_rules
            ]
            active_data = {
                "selected_at": datetime.utcnow().isoformat() + "Z",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "context": context,
                "token_budget": {
                    "allocated": budget_tokens,
                    "used": accumulated_tokens,
                    "rule_count": len(selected_rules),
                },
                "rules_count": len(selected_rules),
                "token_count": accumulated_tokens,
                "budget_tokens": budget_tokens,
                "active_rules": active_rules_list,
                "rules": active_rules_list,
            }
            with open(_ACTIVE_RULES_PATH, "w", encoding="utf-8") as f:
                json.dump(active_data, f, indent=2)
                f.write("\n")
            logger.debug("Persisted active_rules.json → %s", _ACTIVE_RULES_PATH)
        except Exception as exc:
            logger.error(
                "Failed to persist active_rules.json → %s: %s: %s",
                _ACTIVE_RULES_PATH,
                type(exc).__name__,
                exc,
            )

    def why(self, active_rules: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
        """Return explanations for why active rules were selected."""
        rules_to_explain = active_rules
        if rules_to_explain is None:
            active_path = _ACTIVE_RULES_PATH
            if active_path.name == "active_rules.json" and active_path.parent.name == ".ai-rule-learning":
                active_path = Path.home() / ".ai-rule-learning" / "active_rules.json"
            if active_path.exists():
                try:
                    data = json.loads(active_path.read_text(encoding="utf-8"))
                    rules_to_explain = data.get("rules") or data.get("active_rules", [])
                except Exception:
                    rules_to_explain = []
            else:
                rules_to_explain = []

        explanations = []
        for r in rules_to_explain or []:
            gt = r.get("gap_type") or r.get("name") or "unknown"
            reason = r.get("selection_reason") or f"Active rule in catalog: {r.get('instruction', '')}"
            explanations.append(
                {
                    "gap_type": gt,
                    "category": r.get("category", "general"),
                    "priority": r.get("priority", 3),
                    "instruction": r.get("instruction", ""),
                    "reason": reason,
                }
            )
        return explanations
