"""Group semantically-similar short texts into clusters (Phase 3).

Community aggregation collects correction *signals* contributed across sessions.
Grouping them by the coarse `gap_type` taxonomy alone treats "add type hints",
"include type hints" and "missing type hints" as three separate signals. This
module clusters near-duplicate signals so an emergent pattern surfaces once, with
a single canonical label.

Single-linkage agglomerative clustering over TF-IDF cosine, pure Python. The
input is a handful to a few hundred short strings, so the O(n^2) pairwise pass is
fine and needs no numpy, scikit-learn, or a vector database — the same
discipline as `similarity`.
"""

from __future__ import annotations

from .similarity import cosine, tfidf_vectors


def cluster_texts(texts: list[str], threshold: float = 0.5) -> list[list[int]]:
    """Cluster ``texts`` by TF-IDF cosine, single-linkage at ``threshold``.

    Returns a list of clusters, each a list of indices into ``texts``, ordered by
    the smallest member index so output is deterministic. Texts that match nothing
    else form singleton clusters.
    """
    n = len(texts)
    if n == 0:
        return []
    if n == 1:
        return [[0]]

    vectors = tfidf_vectors(texts)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]  # path compression
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    for i in range(n):
        for j in range(i + 1, n):
            if cosine(vectors[i], vectors[j]) >= threshold:
                union(i, j)

    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    return [sorted(members) for _, members in sorted(groups.items())]


def canonical_text(texts: list[str], cluster: list[int]) -> str:
    """Pick a representative for a cluster: the medoid (highest summed similarity
    to the other members), breaking ties by the shortest, then lexically first.
    """
    if not cluster:
        return ""
    if len(cluster) == 1:
        return texts[cluster[0]]

    vectors = tfidf_vectors([texts[i] for i in cluster])
    best_idx = 0
    best_key = (-1.0, 0, "")
    for local, global_idx in enumerate(cluster):
        total = sum(cosine(vectors[local], vectors[other]) for other in range(len(cluster)) if other != local)
        text = texts[global_idx]
        key = (total, -len(text), text)  # higher similarity, then shorter, then lexical
        if key > best_key:
            best_key = key
            best_idx = global_idx
    return texts[best_idx]


def cluster_signals(signals: list[str], threshold: float = 0.5) -> list[dict]:
    """Cluster signal strings into emergent groups.

    Returns one dict per cluster — ``{"canonical", "members", "size"}`` — sorted
    by size descending so the strongest emergent patterns come first.
    """
    clusters = cluster_texts(signals, threshold=threshold)
    out = [
        {
            "canonical": canonical_text(signals, cluster),
            "members": [signals[i] for i in cluster],
            "size": len(cluster),
        }
        for cluster in clusters
    ]
    out.sort(key=lambda c: c["size"], reverse=True)
    return out


def dedupe_similar(texts: list[str], threshold: float = 0.5) -> list[str]:
    """Collapse near-duplicate strings to one canonical representative each,
    preserving first-appearance order of the surviving representatives.
    """
    clusters = cluster_texts(texts, threshold=threshold)
    rep_by_min_index = {min(cluster): canonical_text(texts, cluster) for cluster in clusters}
    return [rep_by_min_index[i] for i in sorted(rep_by_min_index)]
