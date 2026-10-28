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


def test_classify_pathlib_structural_but_pending():
    c = en.classify(_rule("Use pathlib.Path for file paths; never use os.path."))
    assert c.channel == en.STRUCTURAL
    assert c.check_id == "pathlib"
    assert c.implemented is False


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
    res = en.enforce(_rule("Use pathlib.Path, never os.path."), code)
    assert res.status == "pending"
    assert res.channel == en.STRUCTURAL


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
