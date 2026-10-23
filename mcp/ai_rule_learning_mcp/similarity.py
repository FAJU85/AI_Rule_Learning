"""Lightweight lexical similarity — TF-IDF cosine over short rule text.

This is deliberately dependency-free pure Python. The corpus is a user's own
guardrail rules: at most a few hundred one-line strings. That scale does not
justify numpy, scikit-learn, or a vector database — an in-memory TF-IDF cosine
is both sufficient and auditable.

Primary use (Phase 1): rank a user's rules by relevance to the current task
context in ``get_guardrail_rules``, so the injected set is the *relevant* rules
rather than whatever wins a flat priority cap. Duplicate detection keeps its own
Jaccard scorer in ``store`` and is intentionally not routed through here.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Callable

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# A small, high-frequency stopword set. Kept short on purpose: TF-IDF already
# down-weights common terms, so this only removes the noisiest glue words that
# otherwise inflate cosine scores between unrelated rules.
_STOPWORDS = frozenset(
    {
        "a", "an", "the", "and", "or", "but", "if", "then", "else", "of", "to",
        "in", "on", "for", "with", "without", "at", "by", "from", "into", "as",
        "is", "are", "be", "been", "being", "was", "were", "do", "does", "did",
        "not", "no", "never", "always", "this", "that", "these", "those", "it",
        "its", "your", "you", "use", "using", "used", "when", "while", "should",
        "must", "can", "will", "please",
    }
)


def tokenize(text: str) -> list[str]:
    """Lowercase, split on non-alphanumerics, drop stopwords and 1-char tokens."""
    if not text:
        return []
    return [t for t in _TOKEN_RE.findall(text.lower()) if len(t) > 1 and t not in _STOPWORDS]


def _term_freq(tokens: list[str]) -> dict[str, float]:
    if not tokens:
        return {}
    counts = Counter(tokens)
    total = float(len(tokens))
    return {term: count / total for term, count in counts.items()}


def compute_idf(docs_tokens: list[list[str]]) -> dict[str, float]:
    """Smoothed inverse document frequency over a corpus of token lists."""
    n_docs = len(docs_tokens)
    if n_docs == 0:
        return {}
    doc_freq: Counter[str] = Counter()
    for tokens in docs_tokens:
        for term in set(tokens):
            doc_freq[term] += 1
    # Smoothed idf keeps weights positive even for terms present in every doc.
    return {term: math.log((1.0 + n_docs) / (1.0 + df)) + 1.0 for term, df in doc_freq.items()}


def _tfidf_vector(tokens: list[str], idf: dict[str, float]) -> dict[str, float]:
    tf = _term_freq(tokens)
    return {term: freq * idf.get(term, 0.0) for term, freq in tf.items()}


def cosine(vec_a: dict[str, float], vec_b: dict[str, float]) -> float:
    """Cosine similarity between two sparse term-weight vectors, in [0, 1]."""
    if not vec_a or not vec_b:
        return 0.0
    # Iterate the smaller vector for the dot product.
    if len(vec_a) > len(vec_b):
        vec_a, vec_b = vec_b, vec_a
    dot = sum(weight * vec_b.get(term, 0.0) for term, weight in vec_a.items())
    if dot == 0.0:
        return 0.0
    norm_a = math.sqrt(sum(w * w for w in vec_a.values()))
    norm_b = math.sqrt(sum(w * w for w in vec_b.values()))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def rank_documents(query: str, documents: list[str], top_k: int | None = None) -> list[tuple[int, float]]:
    """Rank ``documents`` by TF-IDF cosine relevance to ``query``.

    IDF is computed over the documents plus the query, so rare discriminative
    terms dominate. Returns ``(index, score)`` pairs sorted by score descending;
    the original index order breaks ties (a stable sort). ``top_k`` trims the
    result. A query with no usable tokens yields all-zero scores in input order.
    """
    doc_tokens = [tokenize(doc) for doc in documents]
    query_tokens = tokenize(query)
    idf = compute_idf(doc_tokens + [query_tokens])
    query_vec = _tfidf_vector(query_tokens, idf)

    scored = [(i, cosine(query_vec, _tfidf_vector(tokens, idf))) for i, tokens in enumerate(doc_tokens)]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored[:top_k] if top_k is not None else scored


def rank_by_relevance(
    query: str,
    items: list[dict],
    text_of: Callable[[dict], str],
    top_k: int | None = None,
) -> list[dict]:
    """Return ``items`` reordered by relevance of ``text_of(item)`` to ``query``.

    A stable sort is used, so items with equal relevance (including all-zero when
    the query shares no terms) keep their incoming order — callers that pre-sort
    by priority therefore get "relevance first, priority as tiebreak" for free.
    """
    if not query or not items:
        return list(items) if top_k is None else list(items)[:top_k]
    ranking = rank_documents(query, [text_of(item) for item in items])
    ordered = [items[i] for i, _ in ranking]
    return ordered[:top_k] if top_k is not None else ordered
