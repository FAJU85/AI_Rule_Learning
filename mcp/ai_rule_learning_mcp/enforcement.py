from __future__ import annotations

import ast
import io
import os
import shutil
import subprocess
import tempfile
import tokenize
from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import field

STRUCTURAL = "structural"
SOFT = "soft"
MIXED = "mixed"

AUTOFIX = "autofix"
GATE = "gate"
CONSTRAIN = "constrain"
NONE = "none"


def enforcement_enabled() -> bool:
    return os.environ.get("ARL_ENFORCE", "").strip().lower() in ("1", "true", "yes", "on")


def _rule_text(rule: dict) -> str:
    instruction = rule.get("instruction") or ""
    if not instruction:
        action = rule.get("action")
        if isinstance(action, dict):
            instruction = action.get("instruction", "")
    gap = rule.get("gap_type", "") or ""
    return f"{instruction} {gap}".lower()


def _detect_comments(code: str) -> list[str]:
    out: list[str] = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(code).readline):
            if tok.type == tokenize.COMMENT:
                out.append(f"comment at line {tok.start[0]}")
    except Exception:
        return out
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return out
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if ast.get_docstring(node, clean=False) is not None:
                out.append(f"docstring in {getattr(node, 'name', 'module')}")
    return out


def _fix_comments(code: str) -> str:
    lines = code.split("\n")
    comment_cut: dict[int, int] = {}
    try:
        for tok in tokenize.generate_tokens(io.StringIO(code).readline):
            if tok.type == tokenize.COMMENT:
                row = tok.start[0] - 1
                col = tok.start[1]
                comment_cut[row] = min(comment_cut.get(row, col), col)
    except Exception:
        return code

    doc_lines: set[int] = set()
    try:
        tree = ast.parse(code)
    except SyntaxError:
        tree = None
    if tree is not None:
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                body = getattr(node, "body", [])
                if (
                    body
                    and isinstance(body[0], ast.Expr)
                    and isinstance(getattr(body[0], "value", None), ast.Constant)
                    and isinstance(body[0].value.value, str)
                ):
                    start = body[0].lineno - 1
                    end = (body[0].end_lineno or body[0].lineno) - 1
                    for i in range(start, end + 1):
                        doc_lines.add(i)

    out: list[str] = []
    for i, line in enumerate(lines):
        if i in doc_lines:
            continue
        if i in comment_cut:
            trimmed = line[: comment_cut[i]].rstrip()
            if trimmed == "":
                continue
            out.append(trimmed)
        else:
            out.append(line)
    result = "\n".join(out)

    try:
        ast.parse(result)
    except SyntaxError:
        return code
    return result


def _detect_fstrings(code: str) -> list[str]:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []
    out: list[str] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "format"
            and isinstance(node.func.value, ast.Constant)
            and isinstance(node.func.value.value, str)
        ):
            out.append(f".format() on string literal at line {node.lineno}")
        if (
            isinstance(node, ast.BinOp)
            and isinstance(node.op, ast.Mod)
            and isinstance(node.left, ast.Constant)
            and isinstance(node.left.value, str)
        ):
            out.append(f"percent formatting at line {node.lineno}")
    return out


def _fix_fstrings(code: str) -> str:
    if not shutil.which("ruff"):
        return code
    tmp = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as fh:
            fh.write(code)
            tmp = fh.name
        subprocess.run(
            ["ruff", "check", "--fix", "--select", "UP031,UP032", "--isolated", tmp],
            capture_output=True,
            timeout=30,
        )
        with open(tmp, encoding="utf-8") as fh:
            fixed = fh.read()
    except Exception:
        return code
    finally:
        if tmp and os.path.exists(tmp):
            os.remove(tmp)
    try:
        ast.parse(fixed)
    except SyntaxError:
        return code
    return fixed


@dataclass
class Check:
    check_id: str
    channel: str
    mode: str
    keywords: tuple[str, ...]
    implemented: bool = False
    detect: Callable[[str], list[str]] | None = None
    fix: Callable[[str], str] | None = None
    note: str = ""


REGISTRY: tuple[Check, ...] = (
    Check(
        check_id="no_comments",
        channel=STRUCTURAL,
        mode=AUTOFIX,
        keywords=("comment", "docstring"),
        implemented=True,
        detect=_detect_comments,
        fix=_fix_comments,
    ),
    Check(
        check_id="f_strings",
        channel=STRUCTURAL,
        mode=AUTOFIX,
        keywords=("f-string", "fstring", ".format", "% formatting", "percent format"),
        implemented=True,
        detect=_detect_fstrings,
        fix=_fix_fstrings,
    ),
    Check(check_id="no_print", channel=STRUCTURAL, mode=GATE, keywords=("print(",), note="detector pending"),
    Check(
        check_id="no_else", channel=STRUCTURAL, mode=GATE, keywords=("else keyword", "no else"), note="detector pending"
    ),
    Check(
        check_id="type_hints", channel=STRUCTURAL, mode=GATE, keywords=("type hint", "annotat"), note="detector pending"
    ),
    Check(
        check_id="snake_case",
        channel=STRUCTURAL,
        mode=GATE,
        keywords=("snake_case", "snake case"),
        note="detector pending",
    ),
    Check(
        check_id="short_funcs",
        channel=STRUCTURAL,
        mode=GATE,
        keywords=("non-blank lines", "function length", "too long"),
        note="detector pending",
    ),
    Check(
        check_id="pathlib",
        channel=STRUCTURAL,
        mode=GATE,
        keywords=("pathlib", "os.path"),
        note="detector pending (ruff PTH)",
    ),
    Check(
        check_id="single_block",
        channel=STRUCTURAL,
        mode=CONSTRAIN,
        keywords=("one python code block", "single code block", "one code block"),
        note="constrained-decoding pending",
    ),
)


@dataclass
class Classification:
    channel: str
    check_id: str = ""
    mode: str = NONE
    implemented: bool = False
    note: str = ""


def classify(rule: dict) -> Classification:
    text = _rule_text(rule)
    for check in REGISTRY:
        if any(kw in text for kw in check.keywords):
            return Classification(
                channel=check.channel,
                check_id=check.check_id,
                mode=check.mode,
                implemented=check.implemented,
                note=check.note,
            )
    return Classification(channel=SOFT, mode=NONE, note="text-injection channel (~28% ceiling)")


@dataclass
class EnforcementResult:
    rule_id: str
    channel: str
    check_id: str
    mode: str
    status: str
    violations: list[str] = field(default_factory=list)
    fixed_code: str | None = None
    note: str = ""


def _find_check(check_id: str) -> Check | None:
    for check in REGISTRY:
        if check.check_id == check_id:
            return check
    return None


def enforce(rule: dict, code: str, apply_fix: bool = False) -> EnforcementResult:
    rid = str(rule.get("rule_id", ""))
    cls = classify(rule)
    if cls.channel == SOFT:
        return EnforcementResult(rid, SOFT, "", NONE, "soft", note=cls.note)
    check = _find_check(cls.check_id)
    if check is None or not check.implemented or check.detect is None:
        return EnforcementResult(
            rid, cls.channel, cls.check_id, cls.mode, "pending", note=cls.note or "detector pending"
        )

    try:
        ast.parse(code)
    except SyntaxError:
        return EnforcementResult(
            rid, cls.channel, cls.check_id, cls.mode, "parse_error", note="code is not valid python"
        )

    violations = check.detect(code)
    if not violations:
        return EnforcementResult(rid, cls.channel, cls.check_id, cls.mode, "pass")
    if apply_fix and check.mode == AUTOFIX and check.fix is not None:
        fixed = check.fix(code)
        remaining = check.detect(fixed)
        if not remaining:
            return EnforcementResult(rid, cls.channel, cls.check_id, cls.mode, "fixed", fixed_code=fixed)
        return EnforcementResult(
            rid, cls.channel, cls.check_id, cls.mode, "fail", violations=remaining, fixed_code=fixed
        )
    return EnforcementResult(rid, cls.channel, cls.check_id, cls.mode, "fail", violations=violations)


def enforce_all(rules: list[dict], code: str, apply_fix: bool = False) -> tuple[list[EnforcementResult], str]:
    current = code
    results: list[EnforcementResult] = []
    for rule in rules:
        res = enforce(rule, current, apply_fix=apply_fix)
        if res.status == "fixed" and res.fixed_code is not None:
            current = res.fixed_code
        results.append(res)
    return results, current
