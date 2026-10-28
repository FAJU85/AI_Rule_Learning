from __future__ import annotations

from ai_rule_learning_mcp.gap_detector import distill_directive as d


def test_dotted_token_not_truncated():
    out = d("You used os.path again. I always want pathlib.Path for file paths.")
    assert out == "Use pathlib.Path for file paths."
    assert "os." not in out


def test_fstrings_dotted_token_preserved():
    out = d("You used .format() for a string. I only want f-strings, never .format().")
    assert out.startswith("Use f-strings")
    assert "You used" not in out


def test_directive_sentence_selected_over_complaint():
    out = d("You added comments and docstrings again. I never want comments or docstrings in my code.")
    assert out.startswith("Avoid")
    assert "added" not in out.lower()


def test_imperative_second_sentence_kept():
    out = d("You used print() again. Return the value instead of printing it.")
    assert out.startswith("Return the value")


def test_i_want_becomes_use():
    assert d("I always want pathlib.Path for file paths.") == "Use pathlib.Path for file paths."


def test_i_never_want_becomes_avoid():
    assert d("I never want comments in my code.").startswith("Avoid comments")


def test_existing_forgot_pattern_unchanged():
    assert d("you forgot to handle the empty-list case") == "Always handle the empty-list case."


def test_existing_prefer_pattern_unchanged():
    assert d("I prefer pytest fixtures over unittest") == "Prefer pytest fixtures over unittest."


def test_noise_still_rejected():
    assert d("thanks") == ""
    assert d("hmm ok") == ""
