"""Standalone CLI — works with ZERO MCP config.

Usage:
  ai-rule-learning sync     Scan sessions, generate rules, write to all detected AI agents
  ai-rule-learning status   Show current rules and detected agent configs
  ai-rule-learning rules    Print active rules
  ai-rule-learning clear    Remove AI Rule Learning section from all agent configs
"""

from __future__ import annotations

import sys
from pathlib import Path


def _default_session_paths() -> list[Path]:
    candidates = [
        Path.home() / ".claude" / "projects",
        Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json",
    ]
    return [p for p in candidates if p.exists()]


def cmd_sync(args: list[str]) -> None:
    from .gap_detector import analyze_conversations
    from .injector import detected_targets, write_rules_all
    from .providers import parse_any
    from .store import (
        _local_load,
        _local_save,
        append_conversations,
        auto_activate_pending_rules,
        is_already_processed,
        load_active_rules,
        mark_processed,
    )

    raw_paths = [Path(p) for p in args] if args else _default_session_paths()
    if not raw_paths:
        print("⚠️  No session paths found. Pass a path: ai-rule-learning sync ~/.claude/projects")
        sys.exit(1)

    session_files: list[Path] = []
    for sp in raw_paths:
        if sp.is_file():
            session_files.append(sp)
        elif sp.is_dir():
            for sub in sp.iterdir():
                if sub.is_dir():
                    session_files.extend(
                        f for f in sub.glob("*.jsonl") if ".ccr-tip" not in f.name
                    )
            session_files.extend(
                f for f in sp.glob("*.jsonl") if ".ccr-tip" not in f.name
            )
            session_files.extend(sp.glob("conversations.json"))

    print(f"📂 Found {len(session_files)} session file(s)")

    new_files = [f for f in session_files if not is_already_processed(f)]
    print(f"🆕 {len(new_files)} new file(s) to process")

    all_conversations: list[dict] = []
    for path in new_files:
        convs = parse_any(path)
        if convs:
            all_conversations.extend(convs)
            mark_processed(path)

    print(f"✅ Parsed {len(all_conversations)} conversation(s)")

    if not all_conversations:
        rules = load_active_rules()
        if rules:
            written = write_rules_all(rules)
            targets = ", ".join(n for n, _ in written)
            print(f"📝 {len(rules)} existing rule(s) refreshed → {targets}")
        else:
            print("ℹ️  No conversations to process and no existing rules. Try again after more sessions.")
        return

    detected = analyze_conversations(all_conversations)
    if detected:
        existing = _local_load("rules.jsonl")
        existing_ids = {r.get("rule_id") for r in existing}
        new_rules = [r for r in detected if r.get("rule_id") not in existing_ids]
        if new_rules:
            _local_save("rules.jsonl", existing + new_rules)
            print(f"🧠 Generated {len(new_rules)} new rule(s) from your patterns")
        else:
            print("ℹ️  Patterns already have rules")
    else:
        print("ℹ️  No recurring friction patterns detected yet")

    try:
        append_conversations(all_conversations)
    except Exception:
        pass

    try:
        activated = auto_activate_pending_rules()
        if activated:
            print(f"✅ Auto-activated {activated} rule(s) from HF dataset")
    except Exception:
        pass

    rules = load_active_rules()
    if rules:
        written = write_rules_all(rules)
        if written:
            targets = ", ".join(n for n, _ in written)
            print(f"\n📝 {len(rules)} rule(s) written to: {targets}")
        print("🎉 These rules will now apply automatically to every future session!\n")
        print("Active rules:")
        for rule in rules:
            label = rule.get("priority_label", "MEDIUM")
            name = rule.get("name", rule.get("rule_id", "rule"))
            print(f"  [{label}] {name}")
    else:
        print("ℹ️  No active rules generated yet")


def cmd_status(_args: list[str]) -> None:
    from .injector import _ALL_TARGETS, read_injected_rules
    from .store import LOCAL_DIR, _local_load, load_active_rules

    rules = load_active_rules()
    injected = read_injected_rules()

    print(f"📁 Local storage: {LOCAL_DIR}")
    print(f"   Rules stored:  {len(_local_load('rules.jsonl'))}")
    print(f"   Active rules:  {len(rules)}")
    print()

    print("🤖 Detected AI agent configs:")
    for target in _ALL_TARGETS:
        p = target.config_path()
        if target.is_detected():
            status = f"✅ {p}" + (" (rules injected)" if p.exists() else " (will be created on sync)")
        else:
            status = f"⬜ {target.name} not detected"
        print(f"   {status}")

    print()
    print(f"   Injected rules: {len(injected)}")
    if injected:
        print()
        print("Current guardrails:")
        for line in injected:
            print(f"  {line}")


def cmd_rules(_args: list[str]) -> None:
    from .store import load_active_rules

    rules = load_active_rules()
    if not rules:
        print("No active rules. Run: ai-rule-learning sync")
        return
    print(f"Active rules ({len(rules)}):\n")
    for i, rule in enumerate(rules, 1):
        label = rule.get("priority_label", "MEDIUM")
        name = rule.get("name", rule.get("rule_id", f"Rule {i}"))
        instruction = rule.get("action", {}).get("instruction") or rule.get("instruction", "")
        print(f"[{label}] {name}")
        if instruction:
            print(f"  → {instruction}")
        print()


def cmd_clear(_args: list[str]) -> None:
    from .injector import remove_rules_all

    removed = remove_rules_all()
    if removed:
        print(f"✅ Removed AI Rule Learning section from: {', '.join(removed)}")
    else:
        print("ℹ️  No AI Rule Learning section found in any agent config")


def main() -> None:
    argv = sys.argv[1:]
    cmd = argv[0] if argv else "status"
    rest = argv[1:]

    dispatch = {
        "sync": cmd_sync,
        "status": cmd_status,
        "rules": cmd_rules,
        "clear": cmd_clear,
    }

    fn = dispatch.get(cmd)
    if fn is None:
        print(__doc__)
        print(f"Unknown command: {cmd!r}")
        print(f"Available: {', '.join(dispatch)}")
        sys.exit(1)

    fn(rest)


if __name__ == "__main__":
    main()
