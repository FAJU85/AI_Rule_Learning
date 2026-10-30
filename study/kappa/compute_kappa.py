import csv
import sys
from pathlib import Path

OUT_DIR = Path("study/kappa")


def norm(v):
    v = (v or "").strip().lower()
    if v in ("pass", "p", "1", "true", "yes", "y"):
        return "pass"
    if v in ("fail", "f", "0", "false", "no", "n"):
        return "fail"
    return ""


def main():
    sheet = {}
    for row in csv.DictReader((OUT_DIR / "review_sheet.csv").open()):
        lab = norm(row.get("human_label"))
        if lab:
            sheet[row["sample_id"]] = lab
    key = {row["sample_id"]: norm(row["checker_status"]) for row in csv.DictReader((OUT_DIR / "key.csv").open())}

    ids = [s for s in sheet if s in key]
    if not ids:
        print("No labelled rows yet. Fill the human_label column (pass/fail) in review_sheet.csv.")
        return

    cats = ("pass", "fail")
    n = len(ids)
    agree = sum(sheet[s] == key[s] for s in ids)
    po = agree / n
    cm = {(h, c): 0 for h in cats for c in cats}
    for s in ids:
        cm[(sheet[s], key[s])] += 1
    pe = sum((sum(cm[(h, c)] for c in cats) / n) * (sum(cm[(h2, c2)] for h2 in cats) / n)
             for c2, c in ((c, c) for c in cats) for h in [c2])
    ph = {h: sum(cm[(h, c)] for c in cats) / n for h in cats}
    pc = {c: sum(cm[(h, c)] for h in cats) / n for c in cats}
    pe = sum(ph[x] * pc[x] for x in cats)
    kappa = (po - pe) / (1 - pe) if pe != 1 else 1.0

    print(f"labelled & matched: {n} of {len(sheet)} filled")
    print(f"observed agreement (po): {po:.3f}  ({agree}/{n})")
    print(f"expected agreement (pe): {pe:.3f}")
    print(f"Cohen's kappa: {kappa:.3f}")
    print("confusion (human x checker):")
    print(f"              checker=pass  checker=fail")
    for h in cats:
        print(f"  human={h:4s}      {cm[(h,'pass')]:>6d}        {cm[(h,'fail')]:>6d}")
    disagree = [s for s in ids if sheet[s] != key[s]]
    if disagree:
        print("disagreements (sample_id: human vs checker):", ", ".join(f"{s}:{sheet[s]}/{key[s]}" for s in sorted(disagree)))


if __name__ == "__main__":
    main()
