# Checker validation — Cohen's κ (PROTOCOL §3)

Human agreement with the deterministic checker on a seeded random **10%** of gradeable responses
(88 of 878 pass/fail responses, rep 0; seed 20261028; ≥15 minimum satisfied). This closes the §3
validation ("a human reviews a random 10% of responses and reports checker agreement (Cohen's κ)").

## Files

| File                   | Role                                                                                                             |
| ---------------------- | ---------------------------------------------------------------------------------------------------------------- |
| `make_review_sheet.py` | Regenerates the sample from `study/data/` (deterministic; seed 20261028).                                        |
| `review_sheet.csv`     | The **blind** review sheet — `sample_id, family, rule, prompt, response, human_label`. No checker verdict.       |
| `key.csv`              | The hidden answer key — `sample_id, checker_status`. **Do not open it while labelling.**                         |
| `compute_kappa.py`     | Reads the filled sheet + key, prints observed agreement, Cohen's κ, the confusion matrix, and the disagreements. |

## How to run the validation

1. Open `review_sheet.csv` in a spreadsheet (or editor). For each row, read `rule` + `prompt` +
   `response` and decide whether the response **complies with that one rule**. Put `pass` or `fail`
   in `human_label`. Judge only the stated rule, not overall code quality. Do **not** look at
   `key.csv` — that is the checker's verdict and would break the blind.
2. Save the file (keep the same columns).
3. Run `python study/kappa/compute_kappa.py`. It reports κ, agreement, the 2×2 confusion matrix,
   and every disagreement (`sample_id: human/checker`) so checker bugs can be inspected.

Per §3, checker bugs found this way are **reported, not silently fixed** after data collection.
Partial labelling works (blank rows are ignored), but the pre-registered target is the full 10%.

The sample is reproducible: `python study/kappa/make_review_sheet.py` rewrites an identical blank
`review_sheet.csv` and `key.csv` from the released data and seed (it overwrites any labels, so copy
your filled sheet aside before regenerating).
