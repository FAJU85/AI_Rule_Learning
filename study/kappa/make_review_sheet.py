import csv
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, "study")
import arl_study

SEED = 20261028
FRACTION = 0.10
MIN_N = 15
RAW = "study/data/raw_results.jsonl"
TASKS = "study/data/tasks.jsonl"
OUT_DIR = Path("study/kappa")


def main():
    prompts = {t["task_id"]: t["prompt"] for t in (json.loads(l) for l in Path(TASKS).read_text().splitlines() if l.strip())}
    rows = [json.loads(line) for line in Path(RAW).read_text().splitlines() if line.strip()]
    gradeable = [r for r in rows if r["rep"] == 0 and r["status"] in ("pass", "fail")]
    gradeable.sort(key=lambda r: (r["cond"], r["task_id"]))
    rng = random.Random(SEED)
    order = list(range(len(gradeable)))
    rng.shuffle(order)
    n = max(MIN_N, round(FRACTION * len(gradeable)))
    picked = sorted(order[:n])
    sample = [gradeable[i] for i in picked]

    sheet = OUT_DIR / "review_sheet.csv"
    key = OUT_DIR / "key.csv"
    with sheet.open("w", newline="") as fs, key.open("w", newline="") as fk:
        ws = csv.writer(fs)
        wk = csv.writer(fk)
        ws.writerow(["sample_id", "family", "rule", "prompt", "response", "human_label"])
        wk.writerow(["sample_id", "checker_status"])
        for idx, r in enumerate(sample):
            sid = f"S{idx:03d}"
            rule = arl_study.FAMILIES[r["family"]][1]
            ws.writerow([sid, r["family"], rule, prompts.get(r["task_id"], ""), r["response"], ""])
            wk.writerow([sid, r["status"]])

    print(f"gradeable pass/fail responses (rep 0): {len(gradeable)}")
    print(f"sampled: {len(sample)} ({FRACTION:.0%} target, min {MIN_N}), seed {SEED}")
    print(f"wrote {sheet} (blind: no checker verdict) and {key} (hidden answer key)")
    by_cond = {}
    for r in sample:
        by_cond[r["cond"]] = by_cond.get(r["cond"], 0) + 1
    print("sample by condition:", dict(sorted(by_cond.items())))


if __name__ == "__main__":
    main()
