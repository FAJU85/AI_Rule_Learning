"""Community dataset contribution — personal tier opt-in.

Only anonymised gap patterns (type, count, severity) are sent to the
community pool. Raw conversation text NEVER leaves the user's machine.

Community dataset: vooom/AI_Rule_Learning_Community (public, opt-in only)
"""

from __future__ import annotations

import json
import os
from datetime import datetime

COMMUNITY_DATASET = "vooom/AI_Rule_Learning_Community"
HF_TOKEN = os.environ.get("HF_TOKEN", "")


def _gap_pattern(gap: dict) -> dict:
    return {
        "type": gap.get("type", "unknown"),
        "severity": gap.get("severity", 1),
        "turn": gap.get("turn", 0),
    }


def contribute_gaps(gaps_by_type: dict[str, list[dict]], source_hash: str) -> bool:
    """Submit anonymised gap pattern counts to the community dataset.

    Only gap type/severity/turn metadata is sent — no conversation text.
    source_hash is SHA-256 of session_id and is used for deduplication only.
    """
    if not HF_TOKEN:
        return False

    patterns = {
        gtype: [_gap_pattern(g) for g in gaps]
        for gtype, gaps in gaps_by_type.items()
        if gaps
    }
    if not patterns:
        return False

    record = {
        "source_hash": source_hash,
        "contributed_at": datetime.utcnow().isoformat(),
        "gap_patterns": patterns,
        "total_gaps": sum(len(v) for v in patterns.values()),
    }

    try:
        from huggingface_hub import HfApi, hf_hub_download
        from huggingface_hub.errors import EntryNotFoundError

        api = HfApi(token=HF_TOKEN)

        existing: list[dict] = []
        try:
            path = hf_hub_download(
                repo_id=COMMUNITY_DATASET,
                filename="contributions.jsonl",
                repo_type="dataset",
                token=HF_TOKEN,
                force_download=True,
            )
            with open(path, encoding="utf-8") as f:
                existing = [json.loads(l) for l in f if l.strip()]
        except (EntryNotFoundError, Exception):
            pass

        if record["source_hash"] in {r.get("source_hash") for r in existing}:
            return False

        updated = existing + [record]
        content = "\n".join(json.dumps(r, ensure_ascii=False) for r in updated) + "\n"
        api.upload_file(
            path_or_fileobj=content.encode(),
            path_in_repo="contributions.jsonl",
            repo_id=COMMUNITY_DATASET,
            repo_type="dataset",
            commit_message="mcp: anonymised gap contribution",
        )
        return True
    except Exception:
        return False
