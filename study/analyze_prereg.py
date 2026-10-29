import json
import math
import random
import sys
from pathlib import Path

CONDS = ["A", "B0", "B", "C", "D", "E"]
CONFOUNDED = {"F07_pathlib", "F09_valueerror"}
MARGIN = 10.0
BOOT_ITERS = 20000
SEED = 20261028


def load(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    centre = p + z * z / (2 * n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (centre - half) / d, (centre + half) / d


def mcnemar_exact(b, c):
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


def status_map(rows, exclude=frozenset()):
    out = {}
    for r in rows:
        if r["rep"] != 0 or r["family"] in exclude:
            continue
        out.setdefault(r["cond"], {})[r["task_id"]] = r["status"]
    return out


def paired_ids(st, x, y):
    return [t for t in st[x] if t in st[y] and st[x][t] != "invalid" and st[y][t] != "invalid"]


def mcnemar(st, x, y):
    ids = paired_ids(st, x, y)
    b = sum(st[x][t] == "fail" and st[y][t] == "pass" for t in ids)
    c = sum(st[x][t] == "pass" and st[y][t] == "fail" for t in ids)
    return b, c, len(ids), mcnemar_exact(b, c)


def holm(pvals):
    order = sorted(range(len(pvals)), key=lambda i: pvals[i])
    adj = {}
    run = 0.0
    for rank, i in enumerate(order):
        run = max(run, min(1.0, pvals[i] * (len(pvals) - rank)))
        adj[i] = run
    return adj


def bootstrap_ci(st, x, y, iters=BOOT_ITERS, seed=SEED):
    ids = paired_ids(st, x, y)
    diffs_unit = [(1 if st[y][t] == "pass" else 0) - (1 if st[x][t] == "pass" else 0) for t in ids]
    base = 100.0 * sum(diffs_unit) / len(diffs_unit)
    rng = random.Random(seed)
    n = len(diffs_unit)
    samples = []
    for _ in range(iters):
        s = sum(diffs_unit[rng.randrange(n)] for _ in range(n))
        samples.append(100.0 * s / n)
    samples.sort()
    return base, samples[int(0.05 * iters)], samples[int(0.95 * iters) - 1], n


def report(rows):
    st = status_map(rows)
    print("=== per-condition (rep 0) ===")
    for c in CONDS:
        d = st[c]
        inv = sum(v == "invalid" for v in d.values())
        valid = [v for v in d.values() if v != "invalid"]
        k = sum(v == "pass" for v in valid)
        lo, hi = wilson(k, len(valid))
        print(f"  {c:3s} {k}/{len(valid)} = {k / len(valid):.3f} [{lo:.3f},{hi:.3f}]  invalid={inv}")

    print("\n=== confirmatory family (H1 E>A, H2 E>C, H3 E>B0), Holm over 3 ===")
    fam = [("H1 E>A", "A", "E"), ("H2 E>C", "C", "E"), ("H3 E>B0", "B0", "E")]
    stats = [mcnemar(st, x, y) for _, x, y in fam]
    adj = holm([s[3] for s in stats])
    for i, (name, x, y) in enumerate(fam):
        b, c, n, p = stats[i]
        ids = paired_ids(st, x, y)
        py = sum(st[y][t] == "pass" for t in ids) / n
        px = sum(st[x][t] == "pass" for t in ids) / n
        flag = "SIG" if adj[i] < 0.05 else "n.s."
        print(f"  {name}: {y}={py:.3f} vs {x}={px:.3f}  fix={b} break={c} n={n}  McNemar p={p:.3g}  Holm p={adj[i]:.3g}  {flag}")

    print("\n=== equivalence (paired diff y-x, 90% bootstrap CI, margin +/-10) ===")
    for lab, x, y in [("E vs D", "D", "E"), ("E vs B", "B", "E"), ("B vs D", "D", "B")]:
        base, lo, hi, n = bootstrap_ci(st, x, y)
        verdict = "EQUIVALENT" if lo >= -MARGIN and hi <= MARGIN else "INCONCLUSIVE"
        print(f"  {lab}: diff({y}-{x})={base:+.2f}  90% CI [{lo:+.2f},{hi:+.2f}]  n={n}  -> {verdict}")

    st2 = status_map(rows, exclude=CONFOUNDED)
    print("\n=== robustness: excluding confounded families (F07, F09) ===")
    for c in CONDS:
        valid = [v for v in st2[c].values() if v != "invalid"]
        k = sum(v == "pass" for v in valid)
        print(f"  {c:3s} {k}/{len(valid)} = {k / len(valid):.3f}")
    for name, x, y in [("E>A", "A", "E"), ("E>B0", "B0", "E"), ("E>C", "C", "E")]:
        b, c, n, p = mcnemar(st2, x, y)
        print(f"  {name} (no F07/F09): fix={b} break={c} n={n} McNemar p={p:.3g}")

    print("\n=== over-application (valid responses, rep 0) ===")
    for c in CONDS:
        rr = [r for r in rows if r["rep"] == 0 and r["cond"] == c and r.get("side")]
        nonp = [r for r in rr if r["family"] != "F07_pathlib"]
        nonv = [r for r in rr if r["family"] != "F09_valueerror"]
        pa = sum(r["side"]["imports_pathlib"] for r in nonp)
        ve = sum(r["side"]["raises_valueerror"] for r in nonv)
        ml = sum(r["side"]["n_lines"] for r in rr) / len(rr)
        print(f"  {c:3s} pathlib(non-F07) {pa}/{len(nonp)}  ValueError(non-F09) {ve}/{len(nonv)}  mean_lines {ml:.1f}")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "study/data/raw_results.jsonl"
    report(load(path))
