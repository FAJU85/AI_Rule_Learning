#!/usr/bin/env python3
"""Upload historical conversations from JSON or CSV to the HuggingFace dataset.

Usage:
    python scripts/upload_historical.py --file conversations.json
    python scripts/upload_historical.py --file conversations.csv --format csv
    python scripts/upload_historical.py --file data/ --format json  # directory of JSON files
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import sys
import uuid
from pathlib import Path
from typing import Any
from typing import Dict
from typing import List

from tqdm import tqdm  # type: ignore

# Ensure project root is on sys.path when run directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import settings
from src.core.dataset_manager import DatasetManager
from src.models.conversation import Conversation
from src.models.conversation import Turn
from src.utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------


def load_json_file(path: Path) -> List[Dict[str, Any]]:
    """Load a JSON file that contains either a list of conversations or a single one."""
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, dict):
        return [data]
    return data


def load_csv_file(path: Path) -> List[Dict[str, Any]]:
    """Load a CSV where each row is a single turn.

    Expected columns: conversation_id, turn_number, user_input, agent_response
    Optional: session_id, user_id, sentiment_before, sentiment_after
    """
    conversations: Dict[str, Dict[str, Any]] = {}
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            cid = row.get("conversation_id") or str(uuid.uuid4())
            if cid not in conversations:
                conversations[cid] = {
                    "conversation_id": cid,
                    "session_id": row.get("session_id"),
                    "user_id": row.get("user_id"),
                    "turns": [],
                }
            turn = {
                "turn_number": int(row.get("turn_number", len(conversations[cid]["turns"]) + 1)),
                "user_input": row.get("user_input", ""),
                "agent_response": row.get("agent_response", ""),
            }
            if row.get("sentiment_before"):
                turn["sentiment_before"] = float(row["sentiment_before"])
            if row.get("sentiment_after"):
                turn["sentiment_after"] = float(row["sentiment_after"])
            conversations[cid]["turns"].append(turn)

    return list(conversations.values())


def raw_to_conversation(raw: Dict[str, Any]) -> Conversation:
    """Convert a raw dict into a Conversation model, generating IDs where missing."""
    if "conversation_id" not in raw or not raw["conversation_id"]:
        raw["conversation_id"] = str(uuid.uuid4())

    turns_raw = raw.pop("turns", [])
    conv = Conversation(**raw)
    for t in turns_raw:
        if "turn_number" not in t:
            t["turn_number"] = len(conv.turns) + 1
        conv.add_turn(Turn(**t))
    return conv


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: List[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Upload historical conversations to HuggingFace dataset."
    )
    parser.add_argument("--file", required=True, help="Path to file or directory")
    parser.add_argument(
        "--format",
        choices=["json", "csv"],
        default="json",
        help="Input format (default: json)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and validate without uploading",
    )
    args = parser.parse_args(argv)

    input_path = Path(args.file)
    if not input_path.exists():
        print(f"[Error] Path does not exist: {input_path}", file=sys.stderr)
        sys.exit(1)

    # Collect files
    if input_path.is_dir():
        pattern = f"**/*.{args.format}"
        files = [Path(p) for p in glob.glob(str(input_path / pattern), recursive=True)]
    else:
        files = [input_path]

    if not files:
        print("No matching files found.")
        sys.exit(0)

    print(f"Found {len(files)} file(s) to process.")

    # Parse
    raw_records: List[Dict[str, Any]] = []
    for f in files:
        try:
            if args.format == "json":
                raw_records.extend(load_json_file(f))
            else:
                raw_records.extend(load_csv_file(f))
        except Exception as exc:
            logger.warning("Skipping file due to parse error", extra={"file": str(f), "error": str(exc)})

    print(f"Parsed {len(raw_records)} conversation(s).")

    # Validate
    valid: List[Conversation] = []
    for raw in tqdm(raw_records, desc="Validating"):
        try:
            conv = raw_to_conversation(raw)
            valid.append(conv)
        except Exception as exc:
            logger.warning(
                "Skipping invalid conversation",
                extra={"error": str(exc), "raw_id": raw.get("conversation_id", "?")},
            )

    print(f"Valid: {len(valid)}, Skipped: {len(raw_records) - len(valid)}")

    if args.dry_run:
        print("[Dry run] No data uploaded.")
        return

    # Upload
    dm = DatasetManager()
    uploaded = 0
    for conv in tqdm(valid, desc="Uploading"):
        try:
            dm.save_conversation(conv)
            uploaded += 1
        except Exception as exc:
            logger.error(
                "Upload failed for conversation",
                extra={"conversation_id": conv.conversation_id, "error": str(exc)},
            )

    print(f"Upload complete. Uploaded {uploaded}/{len(valid)} conversation(s).")


if __name__ == "__main__":
    main()
