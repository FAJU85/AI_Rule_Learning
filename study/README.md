# Effectiveness study — pre-registration bundle

This directory is the frozen pre-registration bundle for the DeepSeek instruction-adherence
study of `ai-rule-learning-mcp` 0.2.7.

## Contents

| File                | Role                                                                                                                                                                                                    |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `PROTOCOL.md`       | The pre-registered protocol (design, hypotheses, analysis, limitations, COI).                                                                                                                           |
| `arl_study.py`      | The frozen study harness (selftest, build-tasks, learn, run, analyze). Hashed in `PROTOCOL.md` §1.                                                                                                      |
| `COLAB_ONE_CELL.py` | The one-cell Colab runner actually executed. It embeds `arl_study.py` as its `SRC` literal and writes it out with `SRC.lstrip("\n")`, so `arl_study.py` here is byte-identical to what the cell runs.   |
| `data/`             | Released raw run data: `raw_results.jsonl` (900 calls), `tasks.jsonl`, `learn_log*.json`.                                                                                                               |
| `analyze_prereg.py` | Post-registration analyzer implementing §4 (H1–H3 McNemar + Holm, equivalence TOSTs, robustness, over-application) on the released data. See `PROTOCOL.md` §9.2. Run: `python study/analyze_prereg.py`. |
| `RESULTS.md`        | Computed results of the registered `MODE="main"` run (deepseek-flash).                                                                                                                                  |
| `PAPER_DRAFT.md`    | Draft Results / Over-application / Threats sections.                                                                                                                                                    |

`arl_study.py` was extracted from `COLAB_ONE_CELL.py`'s `SRC` literal, not edited by hand, so the two
cannot drift. Regenerate/verify:

```python
import ast, hashlib
src = next(ast.literal_eval(n.value) for n in ast.walk(ast.parse(open("COLAB_ONE_CELL.py").read()))
           if isinstance(n, ast.Assign) and any(getattr(t, "id", None) == "SRC" for t in n.targets))
assert hashlib.sha256(src.lstrip("\n").encode()).hexdigest() == \
    "ef282a95f5d65eef31e4118437bc19be0d1a6cce32f3fda9271dcabc4fd42948"
```

## Registration → run order (do not skip)

1. This commit freezes `PROTOCOL.md` + `arl_study.py` together with their sha256 hashes in §1.
2. **Register** the frozen bundle (OSF upload preferred for the COI; or a git tag on this commit).
   The registration timestamp is the tag/upload time — not a hand-edited date.
3. Only then run `MODE="main"` in `COLAB_ONE_CELL.py` (Colab secret `DEEPSEEK_API_KEY` required).
4. Paste the `analyze` output back for interpretation; release all raw responses (`arl_main_results.zip`).

The offline checker selftest was reproduced at freeze: `27/27 checker cases ok; tasks=150`.
A new tool version or any change to §1 after registration is a new study / a logged deviation (§9).
