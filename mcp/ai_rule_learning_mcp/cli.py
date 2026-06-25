"""Standalone CLI — works with ZERO MCP config.

Usage:
  ai-rule-learning sync              Scan sessions, generate rules, write to all detected AI agents
  ai-rule-learning status            Show current rules and detected agent configs
  ai-rule-learning rules             Print active rules
  ai-rule-learning clear             Remove AI Rule Learning section from all agent configs
  ai-rule-learning memory show       Show all remembered facts and preferences
  ai-rule-learning memory add <type> <content>   Add a memory entry manually
  ai-rule-learning memory clear      Delete all memory entries
  ai-rule-learning skills            List all saved skill procedures
  ai-rule-learning skills show <name>   Show full steps for a skill
  ai-rule-learning skills delete <name> Delete a skill
  ai-rule-learning install-cron      Install nightly auto-sync (macOS/Linux)
  ai-rule-learning uninstall-cron    Remove the nightly auto-sync job
  ai-rule-learning cron-status       Show whether auto-sync is scheduled
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
    from .injector import write_rules_all
    from .providers import parse_any
    from .store import _local_load
    from .store import _local_save
    from .store import append_conversations
    from .store import auto_activate_pending_rules
    from .store import is_already_processed
    from .store import load_active_rules
    from .store import mark_processed

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

    from .memory import load_memory

    rules = load_active_rules()
    if rules:
        memory_entries = load_memory()
        written = write_rules_all(rules, memory_entries=memory_entries or None)
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
    from .injector import _ALL_TARGETS
    from .injector import read_injected_rules
    from .store import LOCAL_DIR
    from .store import _local_load
    from .store import load_active_rules

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


def cmd_memory(args: list[str]) -> None:
    from .injector import write_memory_all
    from .memory import add_memory
    from .memory import clear_memory
    from .memory import format_memory_for_display
    from .memory import load_memory

    subcmd = args[0] if args else "show"

    if subcmd == "show" or subcmd == "list":
        entries = load_memory()
        print(format_memory_for_display(entries))

    elif subcmd == "add":
        if len(args) < 3:
            print("Usage: ai-rule-learning memory add <type> <content>")
            print("Types: preference, project, never, user_info, context")
            return
        mem_type = args[1]
        content = " ".join(args[2:])
        entry = add_memory(mem_type, content)
        entries = load_memory()
        written = write_memory_all(entries)
        targets = ", ".join(n for n, _ in written) if written else "none detected"
        print(f"✅ Remembered [{entry['type']}]: {entry['content']}")
        print(f"   Written to: {targets}")

    elif subcmd == "clear":
        n = clear_memory()
        print(f"✅ Cleared {n} memory entries")

    else:
        print(f"Unknown memory subcommand: {subcmd!r}")
        print("Available: show, add, clear")


def cmd_skills(args: list[str]) -> None:
    from .skills import delete_skill
    from .skills import format_skill_detail
    from .skills import format_skills_for_display
    from .skills import get_skill
    from .skills import list_skills

    subcmd = args[0] if args else "list"

    if subcmd in ("list", "ls") or not args:
        skills = list_skills()
        print(format_skills_for_display(skills))

    elif subcmd == "show" or subcmd == "get":
        if len(args) < 2:
            print("Usage: ai-rule-learning skills show <name>")
            return
        name = " ".join(args[1:])
        skill = get_skill(name)
        if skill is None:
            print(f"❌ Skill not found: {name!r}")
            print("Run `ai-rule-learning skills` to list available skills.")
        else:
            print(format_skill_detail(skill))

    elif subcmd == "delete" or subcmd == "rm":
        if len(args) < 2:
            print("Usage: ai-rule-learning skills delete <name>")
            return
        name = " ".join(args[1:])
        if delete_skill(name):
            print(f"✅ Skill deleted: {name!r}")
        else:
            print(f"❌ Skill not found: {name!r}")

    else:
        print(f"Unknown skills subcommand: {subcmd!r}")
        print("Available: list, show <name>, delete <name>")


def cmd_install_cron(_args: list[str]) -> None:
    from .scheduler import install
    from .scheduler import status

    msg = install()
    print(f"✅ {msg}")
    print(f"\nScheduler status: {status()}")
    print("The system will now sync automatically every night at 02:00.")


def cmd_uninstall_cron(_args: list[str]) -> None:
    from .scheduler import uninstall

    removed = uninstall()
    if removed:
        print("✅ Nightly auto-sync removed.")
    else:
        print("ℹ️  No auto-sync job found.")


def cmd_cron_status(_args: list[str]) -> None:
    from .scheduler import is_installed
    from .scheduler import status

    st = status()
    print(st)
    if not is_installed():
        print("\nRun `ai-rule-learning install-cron` to enable nightly auto-sync.")


def main() -> None:
    argv = sys.argv[1:]
    cmd = argv[0] if argv else "status"
    rest = argv[1:]

    dispatch = {
        "sync": cmd_sync,
        "status": cmd_status,
        "rules": cmd_rules,
        "clear": cmd_clear,
        "memory": cmd_memory,
        "skills": cmd_skills,
        "install-cron": cmd_install_cron,
        "uninstall-cron": cmd_uninstall_cron,
        "cron-status": cmd_cron_status,
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
