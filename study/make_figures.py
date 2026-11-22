import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

RAW = "study/data/raw_results.jsonl"
OUT = Path("study/figures")
OUT.mkdir(exist_ok=True)

CONDS = ["A", "C", "B0", "E", "B", "D"]
COND_LABEL = {
    "A": "A\nno rules",
    "C": "C\nplacebo",
    "B0": "B0\ndefaults",
    "E": "E\nlearned (NL)",
    "B": "B\nlearned (hint)",
    "D": "D\nplain text",
}
GROUP_COLOR = {"A": "#999999", "C": "#999999", "B0": "#56B4E9", "E": "#0072B2", "B": "#0072B2", "D": "#E69F00"}
FAMILIES = [
    "F01_no_comments", "F02_type_hints", "F03_snake_case", "F04_no_print", "F05_no_else",
    "F06_short_funcs", "F07_pathlib", "F08_fstrings", "F09_valueerror", "F10_single_block",
]

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 11,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "axes.axisbelow": True,
    "grid.color": "#e6e6e6",
    "grid.linewidth": 0.8,
    "figure.dpi": 160,
})


def load():
    return [json.loads(l) for l in Path(RAW).read_text().splitlines() if l.strip() and json.loads(l)["rep"] == 0]


def wilson(k, n, z=1.96):
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return p, (c - h) / d, (c + h) / d


def mcnemar_exact(b, c):
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


def status_map(rows):
    st = {}
    for r in rows:
        st.setdefault(r["cond"], {})[r["task_id"]] = r["status"]
    return st


def fig_adherence(rows):
    st = status_map(rows)
    xs, rates, los, his, cols = [], [], [], [], []
    for c in CONDS:
        valid = [v for v in st[c].values() if v != "invalid"]
        k = sum(v == "pass" for v in valid)
        p, lo, hi = wilson(k, len(valid))
        xs.append(COND_LABEL[c]); rates.append(p * 100); los.append((p - lo) * 100); his.append((hi - p) * 100); cols.append(GROUP_COLOR[c])
    fig, ax = plt.subplots(figsize=(8, 4.6))
    bars = ax.bar(xs, rates, color=cols, width=0.68, yerr=[los, his], capsize=4, ecolor="#555555", error_kw={"lw": 1.2})
    for b, r in zip(bars, rates):
        ax.text(b.get_x() + b.get_width() / 2, r + 2.2, f"{r:.0f}%", ha="center", va="bottom", fontsize=10.5, fontweight="bold")
    ax.set_ylim(0, 108)
    ax.set_ylabel("Instruction adherence (%)")
    ax.set_title("Instruction adherence by condition (deepseek-flash, n = 150 / condition)", fontsize=12, fontweight="bold", pad=12)
    handles = [plt.Rectangle((0, 0), 1, 1, color="#999999"), plt.Rectangle((0, 0), 1, 1, color="#56B4E9"),
               plt.Rectangle((0, 0), 1, 1, color="#0072B2"), plt.Rectangle((0, 0), 1, 1, color="#E69F00")]
    ax.legend(handles, ["controls (A, C)", "shipped defaults (B0)", "ARL learned (E, B)", "plain-text memory (D)"],
              loc="upper left", frameon=False, fontsize=9.5)
    fig.tight_layout()
    fig.savefig(OUT / "fig1_adherence.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)


def fig_confirmatory(rows):
    st = status_map(rows)
    tests = [("H1  E > A", "A"), ("H2  E > C", "C"), ("H3  E > B0", "B0")]
    fig, ax = plt.subplots(figsize=(8, 3.6))
    ys = list(range(len(tests)))[::-1]
    for y, (label, base) in zip(ys, tests):
        ids = [t for t in st["E"] if t in st[base] and st["E"][t] != "invalid" and st[base][t] != "invalid"]
        pe = sum(st["E"][t] == "pass" for t in ids) / len(ids) * 100
        pb = sum(st[base][t] == "pass" for t in ids) / len(ids) * 100
        b = sum(st[base][t] == "fail" and st["E"][t] == "pass" for t in ids)
        c = sum(st[base][t] == "pass" and st["E"][t] == "fail" for t in ids)
        p = mcnemar_exact(b, c)
        ax.plot([pb, pe], [y, y], color="#bbbbbb", lw=2.5, zorder=1)
        ax.scatter([pb], [y], color="#999999", s=90, zorder=2)
        ax.scatter([pe], [y], color="#0072B2", s=90, zorder=2)
        ax.text(pb - 1.5, y, f"{pb:.0f}%", ha="right", va="center", fontsize=9.5, color="#555555")
        ax.text(pe + 1.5, y, f"{pe:.0f}%", ha="left", va="center", fontsize=9.5, fontweight="bold", color="#0072B2")
        ax.text(50, y + 0.28, f"{label}   fixed {b} / broken {c}   McNemar p = {p:.1e}   (Holm-corrected, significant)",
                ha="center", va="bottom", fontsize=9)
    ax.set_yticks(ys)
    ax.set_yticklabels([t[0] for t in tests])
    ax.set_xlim(0, 100)
    ax.set_ylim(-0.6, len(tests) - 0.2)
    ax.set_xlabel("Adherence (%) — paired tasks valid in both conditions")
    ax.set_title("Confirmatory tests: learned rules (E) vs each baseline", fontsize=12, fontweight="bold", pad=10)
    handles = [plt.Line2D([0], [0], marker="o", color="w", markerfacecolor="#999999", markersize=10, label="baseline"),
               plt.Line2D([0], [0], marker="o", color="w", markerfacecolor="#0072B2", markersize=10, label="E (ARL learned)")]
    ax.legend(handles=handles, loc="center left", bbox_to_anchor=(0.01, 0.5), frameon=False, fontsize=9.5)
    fig.tight_layout()
    fig.savefig(OUT / "fig2_confirmatory.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)


def fig_overapplication(rows):
    pa, ve, ml = {}, {}, {}
    for c in CONDS:
        rr = [r for r in rows if r["cond"] == c and r.get("side")]
        nonp = [r for r in rr if r["family"] != "F07_pathlib"]
        nonv = [r for r in rr if r["family"] != "F09_valueerror"]
        pa[c] = 100 * sum(r["side"]["imports_pathlib"] for r in nonp) / len(nonp)
        ve[c] = 100 * sum(r["side"]["raises_valueerror"] for r in nonv) / len(nonv)
        ml[c] = sum(r["side"]["n_lines"] for r in rr) / len(rr)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.5, 4.3))
    x = range(len(CONDS))
    w = 0.38
    labels = [COND_LABEL[c].replace("\n", " ") for c in CONDS]
    b1 = ax1.bar([i - w / 2 for i in x], [pa[c] for c in CONDS], width=w, color="#D55E00", label="pathlib imported (non-file tasks)")
    b2 = ax1.bar([i + w / 2 for i in x], [ve[c] for c in CONDS], width=w, color="#E69F00", label="ValueError raised (non-validation tasks)")
    ax1.set_xticks(list(x)); ax1.set_xticklabels([c for c in CONDS])
    ax1.set_ylim(0, 112); ax1.set_ylabel("Spurious application (% of off-target tasks)")
    ax1.set_title("Over-application (lower is better)", fontsize=11.5, fontweight="bold")
    ax1.legend(loc="upper left", frameon=False, fontsize=8.5)
    for bars in (b1, b2):
        for bb in bars:
            ax1.text(bb.get_x() + bb.get_width() / 2, bb.get_height() + 1.5, f"{bb.get_height():.0f}", ha="center", va="bottom", fontsize=8)
    cols = [GROUP_COLOR[c] for c in CONDS]
    bars = ax2.bar([c for c in CONDS], [ml[c] for c in CONDS], color=cols, width=0.66)
    for bb, c in zip(bars, CONDS):
        ax2.text(bb.get_x() + bb.get_width() / 2, bb.get_height() + 0.4, f"{ml[c]:.1f}", ha="center", va="bottom", fontsize=9)
    ax2.set_ylabel("Mean non-blank lines per response")
    ax2.set_title("Code length collapses under rules", fontsize=11.5, fontweight="bold")
    ax2.set_ylim(0, max(ml.values()) * 1.2)
    fig.suptitle("The cost: rule injection causes blanket over-application", fontsize=12, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(OUT / "fig3_overapplication.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)


def fig_family_heatmap(rows):
    st = {}
    for r in rows:
        if r["status"] != "invalid":
            st.setdefault((r["family"], r["cond"]), []).append(r["status"] == "pass")
    import numpy as np
    M = np.zeros((len(FAMILIES), len(CONDS)))
    for i, f in enumerate(FAMILIES):
        for j, c in enumerate(CONDS):
            v = st.get((f, c), [])
            M[i, j] = (sum(v) / len(v)) if v else float("nan")
    cmap = LinearSegmentedColormap.from_list("blues", ["#f7fbff", "#08306b"])
    fig, ax = plt.subplots(figsize=(7.6, 6.4))
    im = ax.imshow(M, cmap=cmap, vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(CONDS))); ax.set_xticklabels(CONDS)
    ax.set_yticks(range(len(FAMILIES))); ax.set_yticklabels([f.replace("_", " ") for f in FAMILIES], fontsize=9)
    for i in range(len(FAMILIES)):
        for j in range(len(CONDS)):
            if not math.isnan(M[i, j]):
                ax.text(j, i, f"{M[i, j]*100:.0f}", ha="center", va="center", fontsize=8.5,
                        color="white" if M[i, j] > 0.55 else "#1a1a1a")
    ax.set_title("Per-rule adherence (% pass) by condition", fontsize=12, fontweight="bold", pad=10)
    cb = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.03)
    cb.set_label("adherence", fontsize=9)
    fig.tight_layout()
    fig.savefig(OUT / "fig4_family_heatmap.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    rows = load()
    fig_adherence(rows)
    fig_confirmatory(rows)
    fig_overapplication(rows)
    fig_family_heatmap(rows)
    print("wrote:", ", ".join(sorted(p.name for p in OUT.glob("*.png"))))
