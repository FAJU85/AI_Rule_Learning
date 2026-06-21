"""Entry-point CLI for the AI Rule Learning System.

Usage:
    python -m src.cli.main [command] [options]

Commands:
    chat        Start an interactive conversation session.
    analyze     Run analysis on recent conversations.
    validate    Validate and prune underperforming rules.
    list-rules  List all active rules.
"""

from __future__ import annotations

import argparse
import sys

from config.settings import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Command implementations
# ---------------------------------------------------------------------------


def cmd_chat(args: argparse.Namespace) -> None:
    """Start an interactive chat session with rule injection."""
    provider = args.provider or settings.DEFAULT_AI_PROVIDER

    adapter = _build_adapter(provider)
    from src.core.dataset_manager import DatasetManager
    from src.core.interceptor import ConversationInterceptor
    from src.core.rule_engine import RuleEngine

    dm = DatasetManager()
    rule_engine = RuleEngine(dataset_manager=dm)
    interceptor = ConversationInterceptor(adapter=adapter, rule_engine=rule_engine, dataset_manager=dm)

    conversation = interceptor.start_session(
        user_id=args.user_id,
        project_context=args.context,
    )
    print(f"Session started: {conversation.conversation_id}")
    print("Type 'exit' or 'quit' to end the session.\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            user_input = "exit"

        if user_input.lower() in {"exit", "quit", ""}:
            break

        try:
            response = interceptor.process_turn(
                conversation_id=conversation.conversation_id,
                user_input=user_input,
                base_system_prompt=args.system_prompt or "",
            )
            print(f"AI: {response}\n")
        except Exception as exc:
            logger.error("Turn processing error", extra={"error": str(exc)})
            print(f"[Error] {exc}\n")

    interceptor.end_session(conversation.conversation_id)
    print("Session ended.")


def cmd_analyze(args: argparse.Namespace) -> None:
    """Run the analysis pipeline on recent conversations."""
    from src.core.dataset_manager import DatasetManager
    from src.services.analysis_service import AnalysisService

    dm = DatasetManager()
    adapter = _build_adapter(settings.DEFAULT_AI_PROVIDER)
    service = AnalysisService(dataset_manager=dm, adapter=adapter)

    new_rules = service.analyze_recent(lookback_hours=args.hours)
    print(f"Analysis complete. New rules generated: {len(new_rules)}")
    for rule in new_rules:
        print(f"  [{rule.priority.name}] {rule.rule_id}: {rule.name}")


def cmd_validate(args: argparse.Namespace) -> None:
    """Validate and prune underperforming rules."""
    from src.core.dataset_manager import DatasetManager
    from src.services.validation_service import ValidationService

    dm = DatasetManager()
    service = ValidationService(dataset_manager=dm)
    deactivated = service.validate_all_rules()
    print(f"Validation complete. Deactivated rules: {len(deactivated)}")
    for rule_id in deactivated:
        print(f"  Deactivated: {rule_id}")


def cmd_list_rules(args: argparse.Namespace) -> None:
    """Print all active rules."""
    from src.core.dataset_manager import DatasetManager

    dm = DatasetManager()
    rules = dm.load_rules(active_only=not args.all)
    if not rules:
        print("No rules found.")
        return
    print(f"{'ID':<38} {'Priority':<10} {'Name':<40} {'Score':<8}")
    print("-" * 100)
    for rule in rules:
        active_flag = "" if rule.is_active else " [inactive]"
        print(
            f"{rule.rule_id:<38} {rule.priority.name:<10} {rule.name:<40} {rule.effectiveness_score:<8.2f}{active_flag}"
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_adapter(provider: str):
    if provider == "openai":
        from src.adapters.openai_adapter import OpenAIAdapter

        return OpenAIAdapter()
    if provider in {"claude", "anthropic"}:
        from src.adapters.claude_adapter import ClaudeAdapter

        return ClaudeAdapter()
    raise ValueError(f"Unknown AI provider: {provider!r}")


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ai-rule-learning",
        description="AI Rule Learning System CLI",
    )
    sub = parser.add_subparsers(dest="command")

    # chat
    p_chat = sub.add_parser("chat", help="Start an interactive chat session")
    p_chat.add_argument("--provider", default=None, help="AI provider (openai|claude)")
    p_chat.add_argument("--user-id", default=None, help="User identifier")
    p_chat.add_argument("--context", default=None, help="Project context string")
    p_chat.add_argument("--system-prompt", default=None, help="Base system prompt")

    # analyze
    p_analyze = sub.add_parser("analyze", help="Run gap analysis on recent conversations")
    p_analyze.add_argument("--hours", type=int, default=24, help="Lookback window in hours")

    # validate
    sub.add_parser("validate", help="Validate and prune underperforming rules")

    # list-rules
    p_list = sub.add_parser("list-rules", help="List rules")
    p_list.add_argument("--all", action="store_true", help="Include inactive rules")

    return parser


def main(argv=None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    commands = {
        "chat": cmd_chat,
        "analyze": cmd_analyze,
        "validate": cmd_validate,
        "list-rules": cmd_list_rules,
    }

    try:
        commands[args.command](args)
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(0)
    except Exception as exc:
        logger.error("CLI error", extra={"command": args.command, "error": str(exc)})
        print(f"[Fatal] {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
