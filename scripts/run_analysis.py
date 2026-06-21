#!/usr/bin/env python3
"""Scheduled analysis runner.

Runs AnalysisService.analyze_recent() and ValidationService.validate_all_rules()
on a recurring schedule using the `schedule` library.

Usage:
    python scripts/run_analysis.py                  # run once immediately, then every hour
    python scripts/run_analysis.py --interval 30    # every 30 minutes
    python scripts/run_analysis.py --once           # run once and exit
    python scripts/run_analysis.py --lookback 48    # analyse the last 48 hours
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Ensure project root is on sys.path when run directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import schedule  # type: ignore

from config.settings import settings
from src.core.dataset_manager import DatasetManager
from src.services.analysis_service import AnalysisService
from src.services.validation_service import ValidationService
from src.utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Core job
# ---------------------------------------------------------------------------


def run_analysis_job(lookback_hours: int = 24) -> None:
    """Single analysis + validation pass."""
    logger.info("Starting scheduled analysis job", extra={"lookback_hours": lookback_hours})

    dm = DatasetManager()

    # Build adapter from default provider
    provider = settings.DEFAULT_AI_PROVIDER
    if provider == "openai":
        from src.adapters.openai_adapter import OpenAIAdapter

        adapter = OpenAIAdapter()
    else:
        from src.adapters.claude_adapter import ClaudeAdapter

        adapter = ClaudeAdapter()

    # --- Analysis ---
    analysis_svc = AnalysisService(dataset_manager=dm, adapter=adapter)
    try:
        new_rules = analysis_svc.analyze_recent(lookback_hours=lookback_hours)
        logger.info(
            "Analysis job complete",
            extra={"new_rules_generated": len(new_rules)},
        )
        if new_rules:
            for rule in new_rules:
                print(f"  [NEW RULE] {rule.rule_id}: {rule.name} (priority={rule.priority.name})")
    except Exception as exc:
        logger.error("Analysis job failed", extra={"error": str(exc)})

    # --- Validation ---
    validation_svc = ValidationService(dataset_manager=dm)
    try:
        deactivated = validation_svc.validate_all_rules()
        logger.info(
            "Validation job complete",
            extra={"deactivated_rules": len(deactivated)},
        )
        if deactivated:
            for rule_id in deactivated:
                print(f"  [DEACTIVATED] {rule_id}")
    except Exception as exc:
        logger.error("Validation job failed", extra={"error": str(exc)})


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: list | None = None) -> None:
    parser = argparse.ArgumentParser(description="Scheduled AI rule analysis runner.")
    parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help="Run interval in minutes (default: 60)",
    )
    parser.add_argument(
        "--lookback",
        type=int,
        default=24,
        help="Hours of conversation history to analyse (default: 24)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run once and exit without scheduling",
    )
    args = parser.parse_args(argv)

    # Always run immediately on startup
    run_analysis_job(lookback_hours=args.lookback)

    if args.once:
        print("--once flag set. Exiting after single run.")
        return

    # Schedule recurring runs
    schedule.every(args.interval).minutes.do(run_analysis_job, lookback_hours=args.lookback)
    print(f"Scheduler started. Running every {args.interval} minute(s). Press Ctrl+C to stop.")

    try:
        while True:
            schedule.run_pending()
            time.sleep(10)
    except KeyboardInterrupt:
        print("\nScheduler stopped.")


if __name__ == "__main__":
    main()
