from __future__ import annotations

import ast

from ai_rule_learning_mcp import enforcement as en


def _rule(instruction: str, gap_type: str = "", rule_id: str = "r") -> dict:
    return {"rule_id": rule_id, "instruction": instruction, "gap_type": gap_type}


def test_classify_no_comments_structural_autofix():
    c = en.classify(_rule("Never include comments or docstrings in code."))
    assert c.channel == en.STRUCTURAL
    assert c.check_id == "no_comments"
    assert c.mode == en.AUTOFIX
    assert c.implemented is True


def test_classify_fstrings_structural():
    c = en.classify(_rule("Build strings with f-strings only; never use .format()."))
    assert c.channel == en.STRUCTURAL
    assert c.check_id == "f_strings"


def test_classify_pathlib_structural_implemented():
    c = en.classify(_rule("Use pathlib.Path for file paths; never use os.path."))
    assert c.channel == en.STRUCTURAL
    assert c.check_id == "pathlib"
    assert c.implemented is True


def test_classify_soft_rule():
    c = en.classify(_rule("Keep responses concise and use a formal tone."))
    assert c.channel == en.SOFT
    assert c.mode == en.NONE


def test_enforce_no_comments_pass():
    code = "def f(x):\n    return x\n"
    res = en.enforce(_rule("Never include comments or docstrings."), code)
    assert res.status == "pass"


def test_enforce_no_comments_fail_without_fix():
    code = "def f(x):\n    # hi\n    return x\n"
    res = en.enforce(_rule("Never include comments or docstrings."), code)
    assert res.status == "fail"
    assert res.violations


def test_enforce_no_comments_autofix_strips_comment_and_docstring():
    code = 'def f(x):\n    """doc"""\n    # note\n    return x  # trailing\n'
    res = en.enforce(_rule("Never include comments or docstrings."), code, apply_fix=True)
    assert res.status == "fixed"
    assert res.fixed_code is not None
    ast.parse(res.fixed_code)
    assert "#" not in res.fixed_code
    assert '"""' not in res.fixed_code
    assert "return x" in res.fixed_code


def test_autofix_never_emits_broken_code():
    code = 'def f():\n    """only a docstring"""\n'
    res = en.enforce(_rule("Never include comments or docstrings."), code, apply_fix=True)
    assert res.status == "fail"
    assert res.fixed_code == code


def test_enforce_fstrings_detects_format():
    code = "def f(a):\n    return 'x {}'.format(a)\n"
    res = en.enforce(_rule("Use f-strings only, never .format()."), code)
    assert res.status in ("fail", "fixed")
    if res.status == "fail":
        assert res.violations


def test_enforce_pending_channel():
    code = "def f(p):\n    return p\n"
    res = en.enforce(_rule("Annotate every parameter and the return type."), code)
    assert res.status == "pending"
    assert res.channel == en.STRUCTURAL
    assert res.check_id == "type_hints"


def test_enforce_soft_channel():
    code = "def f():\n    return 1\n"
    res = en.enforce(_rule("Keep responses concise and formal."), code)
    assert res.status == "soft"
    assert res.channel == en.SOFT


def test_enforce_parse_error():
    res = en.enforce(_rule("Never include comments."), "def f(:\n")
    assert res.status == "parse_error"


def test_enforce_all_threads_fixes():
    code = "def f(x):\n    # c\n    return x\n"
    rules = [_rule("Never include comments.", rule_id="a"), _rule("Keep it formal.", rule_id="b")]
    results, out = en.enforce_all(rules, code, apply_fix=True)
    assert len(results) == 2
    assert "#" not in out
    assert any(r.status == "fixed" for r in results)
    assert any(r.status == "soft" for r in results)


def test_enforcement_enabled_env(monkeypatch):
    monkeypatch.delenv("ARL_ENFORCE", raising=False)
    assert en.enforcement_enabled() is False
    monkeypatch.setenv("ARL_ENFORCE", "1")
    assert en.enforcement_enabled() is True


_NO_PRINT = _rule("Never call print(); return values instead.")
_NO_ELSE = _rule("Never use the else keyword; use early returns.")
_SHORT = _rule("Keep every function at most 10 non-blank lines.")
_PATHLIB = _rule("Use pathlib.Path for paths, never os.path.")


def test_enforce_no_print():
    assert en.enforce(_NO_PRINT, "def f(x):\n    return x\n").status == "pass"
    res = en.enforce(_NO_PRINT, "def f(x):\n    print(x)\n    return x\n")
    assert res.status == "fail" and res.violations


def test_enforce_no_else_flags_else_and_ternary_not_elif():
    assert en.enforce(_NO_ELSE, "def f(x):\n    if x:\n        return 1\n    return 0\n").status == "pass"
    assert (
        en.enforce(
            _NO_ELSE, "def f(x):\n    if x:\n        return 1\n    elif x == 2:\n        return 2\n    return 0\n"
        ).status
        == "pass"
    )
    assert (
        en.enforce(_NO_ELSE, "def f(x):\n    if x:\n        return 1\n    else:\n        return 0\n").status == "fail"
    )
    assert en.enforce(_NO_ELSE, "def f(x):\n    return 1 if x else 0\n").status == "fail"


def test_enforce_short_funcs():
    assert en.enforce(_SHORT, "def f(x):\n    return x\n").status == "pass"
    long_body = "def f(x):\n" + "".join(f"    y{i} = x + {i}\n" for i in range(12)) + "    return x\n"
    res = en.enforce(_SHORT, long_body)
    assert res.status == "fail" and res.violations


def test_enforce_pathlib():
    assert en.enforce(_PATHLIB, "from pathlib import Path\n\ndef f(p):\n    return Path(p).name\n").status == "pass"
    res = en.enforce(_PATHLIB, "import os\n\ndef f(p):\n    return os.path.join(p, 'x')\n")
    assert res.status == "fail" and res.violations
