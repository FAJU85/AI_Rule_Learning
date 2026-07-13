"""Standalone CLI — works with ZERO MCP config.

Usage:
  ai-rule-learning sync [--dry-run] Scan sessions, generate rules, write to all detected AI agents
  ai-rule-learning status            Show current rules and detected agent configs
  ai-rule-learning rules             Print active rules
  ai-rule-learning rules pending     Print rules awaiting review
  ai-rule-learning rules approve <id> Activate a reviewed rule
  ai-rule-learning rules reject <id>  Reject a rule so it is not injected
  ai-rule-learning rules edit <id> <instruction>
  ai-rule-learning rules merge <primary-id> <duplicate-id>
  ai-rule-learning rules outcome <id> --worked|--failed
  ai-rule-learning rules health [--apply] [--dry-run]
  ai-rule-learning rules duplicates [--min-similarity <score>]
  ai-rule-learning clear [--dry-run] Remove AI Rule Learning section from all agent configs
  ai-rule-learning memory show       Show all remembered facts and preferences
  ai-rule-learning memory add <type> <content> [--dry-run] Add a memory entry manually
  ai-rule-learning memory clear      Delete all memory entries
  ai-rule-learning skills            List all saved skill procedures
  ai-rule-learning skills show <name>   Show full steps for a skill
  ai-rule-learning skills delete <name> Delete a skill
  ai-rule-learning install-cron      Install nightly auto-sync (macOS/Linux)
  ai-rule-learning uninstall-cron    Remove the nightly auto-sync job
  ai-rule-learning cron-status       Show whether auto-sync is scheduled
  ai-rule-learning metrics status    Show privacy-preserving opt-in metrics status
  ai-rule-learning metrics preview   Preview the aggregate metrics payload
  ai-rule-learning metrics enable    Opt in to anonymous aggregate usage metrics
  ai-rule-learning metrics disable   Opt out of anonymous aggregate usage metrics
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


def _consume_dry_run(args: list[str]) -> tuple[bool, list[str]]:
    """Return (dry_run, args_without_flag) for CLI commands that can write files."""
    dry_run_flags = {"--dry-run", "-n"}
    return any(arg in dry_run_flags for arg in args), [arg for arg in args if arg not in dry_run_flags]


def cmd_sync(args: list[str]) -> None:
    dry_run, args = _consume_dry_run(args)

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
    if dry_run:
        print("🔎 Dry run: no local storage, processed markers, scheduler, or agent config files will be changed.")
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
                    session_files.extend(f for f in sub.glob("*.jsonl") if ".ccr-tip" not in f.name)
            session_files.extend(f for f in sp.glob("*.jsonl") if ".ccr-tip" not in f.name)
            session_files.extend(sp.glob("conversations.json"))

    print(f"📂 Found {len(session_files)} session file(s)")

    new_files = [f for f in session_files if not is_already_processed(f)]
    print(f"🆕 {len(new_files)} new file(s) to process")

    all_conversations: list[dict] = []
    for path in new_files:
        convs = parse_any(path)
        if convs:
            all_conversations.extend(convs)
            if not dry_run:
                mark_processed(path)

    print(f"✅ Parsed {len(all_conversations)} conversation(s)")

    if not all_conversations:
        rules = load_active_rules()
        if rules:
            if dry_run:
                print(f"🔎 Dry run: would refresh {len(rules)} existing rule(s).")
            else:
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
            if dry_run:
                print(f"🔎 Dry run: would save {len(new_rules)} new rule(s) from your patterns")
            else:
                _local_save("rules.jsonl", existing + new_rules)
                print(f"🧠 Generated {len(new_rules)} new rule(s) from your patterns")
        else:
            print("ℹ️  Patterns already have rules")
    else:
        print("ℹ️  No recurring friction patterns detected yet")

    if dry_run:
        print(f"🔎 Dry run: would persist {len(all_conversations)} parsed conversation(s).")
    else:
        try:
            append_conversations(all_conversations)
        except Exception:
            pass

        try:
            activated = auto_activate_pending_rules()
            if activated:
                print(f"✅ Auto-activated {activated} rule(s) from remote dataset")
        except Exception:
            pass

    from .memory import load_memory

    rules = load_active_rules()
    if rules:
        memory_entries = load_memory()
        if dry_run:
            print(f"🔎 Dry run: would write {len(rules)} active rule(s) to detected agent configs.")
        else:
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


def _print_rules(rules: list[dict], title: str) -> None:
    if not rules:
        print(f"No {title.lower()} rules found.")
        return
    print(f"{title} ({len(rules)}):\n")
    for i, rule in enumerate(rules, 1):
        label = rule.get("priority_label", "MEDIUM")
        name = rule.get("name", rule.get("rule_id", f"Rule {i}"))
        rule_id = rule.get("rule_id", "?")
        status = rule.get("status", "active")
        instruction = rule.get("action", {}).get("instruction") or rule.get("instruction", "")
        print(f"[{label}] {name}")
        print(f"  id: {rule_id} | status: {status}")
        if instruction:
            print(f"  → {instruction}")
        print()


def cmd_rules(args: list[str]) -> None:
    dry_run, args = _consume_dry_run(args)

    from .store import edit_rule_instruction
    from .store import list_rules
    from .store import load_active_rules
    from .store import merge_rules
    from .store import record_rule_outcome
    from .store import review_rule_health
    from .store import suggest_duplicate_rules
    from .store import update_rule_status

    subcmd = args[0] if args else "active"

    if subcmd in ("active", "list", "ls"):
        rules = load_active_rules()
        if not rules:
            print("No active rules. Run: ai-rule-learning sync")
            return
        _print_rules(rules, "Active rules")
        return

    if subcmd in ("all", "pending", "approved", "rejected", "inactive", "stale", "needs_review", "merged"):
        status = None if subcmd == "all" else subcmd
        _print_rules(list_rules(status=status), "All rules" if status is None else f"{status} rules")
        return

    if subcmd in ("approve", "activate"):
        if len(args) < 2:
            print("Usage: ai-rule-learning rules approve <rule-id> [--dry-run]")
            return
        rule_id = args[1]
        if dry_run:
            print(f"🔎 Dry run: would approve and activate rule {rule_id!r}")
            return
        rule = update_rule_status(rule_id, "active")
        print(f"✅ Approved and activated rule: {rule_id}" if rule else f"❌ Rule not found: {rule_id}")
        return

    if subcmd == "reject":
        if len(args) < 2:
            print("Usage: ai-rule-learning rules reject <rule-id> [--dry-run]")
            return
        rule_id = args[1]
        note = " ".join(args[2:])
        if dry_run:
            print(f"🔎 Dry run: would reject rule {rule_id!r}")
            return
        rule = update_rule_status(rule_id, "rejected", note=note)
        print(f"✅ Rejected rule: {rule_id}" if rule else f"❌ Rule not found: {rule_id}")
        return

    if subcmd in ("deactivate", "disable"):
        if len(args) < 2:
            print("Usage: ai-rule-learning rules deactivate <rule-id> [--dry-run]")
            return
        rule_id = args[1]
        if dry_run:
            print(f"🔎 Dry run: would deactivate rule {rule_id!r}")
            return
        rule = update_rule_status(rule_id, "inactive")
        print(f"✅ Deactivated rule: {rule_id}" if rule else f"❌ Rule not found: {rule_id}")
        return

    if subcmd == "edit":
        if len(args) < 3:
            print("Usage: ai-rule-learning rules edit <rule-id> <new instruction> [--dry-run]")
            return
        rule_id = args[1]
        instruction = " ".join(args[2:])
        if dry_run:
            print(f"🔎 Dry run: would update instruction for rule {rule_id!r}")
            return
        rule = edit_rule_instruction(rule_id, instruction)
        print(f"✅ Updated rule instruction: {rule_id}" if rule else f"❌ Rule not found: {rule_id}")
        return

    if subcmd == "merge":
        if len(args) < 3:
            print("Usage: ai-rule-learning rules merge <primary-rule-id> <duplicate-rule-id> [--dry-run]")
            return
        primary_id, duplicate_id = args[1], args[2]
        if dry_run:
            print(f"🔎 Dry run: would merge duplicate rule {duplicate_id!r} into {primary_id!r}")
            return
        rule = merge_rules(primary_id, duplicate_id)
        print(
            f"✅ Merged {duplicate_id} into {primary_id}"
            if rule
            else f"❌ Could not find both rules: {primary_id}, {duplicate_id}"
        )
        return

    if subcmd == "outcome":
        if len(args) < 3 or args[2] not in ("--worked", "--failed"):
            print("Usage: ai-rule-learning rules outcome <rule-id> --worked|--failed")
            return
        rule_id = args[1]
        fired_again = args[2] == "--failed"
        if dry_run:
            print(f"🔎 Dry run: would record outcome for rule {rule_id!r}")
            return
        rule = record_rule_outcome(rule_id, fired_again=fired_again)
        print(f"✅ Recorded outcome for rule: {rule_id}" if rule else f"❌ Rule not found: {rule_id}")
        return

    if subcmd in ("duplicates", "dupes"):
        min_similarity = 0.7
        if "--min-similarity" in args:
            try:
                min_similarity = float(args[args.index("--min-similarity") + 1])
            except (IndexError, ValueError):
                print("Usage: ai-rule-learning rules duplicates [--min-similarity <score>]")
                return
        suggestions = suggest_duplicate_rules(min_similarity=min_similarity)
        if not suggestions:
            print("No likely duplicate rules found.")
            return
        print(f"Likely duplicate rules ({len(suggestions)}):")
        for item in suggestions:
            print(f"  - {item['primary_rule_id']} ↔ {item['duplicate_rule_id']} (similarity: {item['similarity']:.0%})")
            print(f"    {item['primary_name']} / {item['duplicate_name']}")
        print(
            "\nReview candidates, then run `ai-rule-learning rules merge <primary-id> <duplicate-id>` if appropriate."
        )
        return

    if subcmd == "health":
        apply_changes = "--apply" in args
        report = review_rule_health(apply=apply_changes and not dry_run)
        stale = report["stale"]
        needs_review = report["needs_review"]
        mode = "applied" if report["applied"] else "preview"
        print(f"Rule health review ({mode}):")
        print(f"  stale: {len(stale)}")
        print(f"  needs_review: {len(needs_review)}")
        for title, ruleset in (("stale", stale), ("needs_review", needs_review)):
            if ruleset:
                print(f"\n{title} candidates:")
                for rule in ruleset:
                    print(f"  - {rule.get('rule_id')}: {rule.get('name', 'Unnamed rule')}")
        if not apply_changes:
            print("\nPreview only. Re-run with `--apply` to update rule statuses.")
        elif dry_run:
            print("\n🔎 Dry run: would update matching rule statuses.")
        return

    print(f"Unknown rules subcommand: {subcmd!r}")
    print("Available: active, all, pending, approve, reject, deactivate, edit, merge, outcome, health, duplicates")


def cmd_clear(args: list[str]) -> None:
    dry_run, _args = _consume_dry_run(args)
    from .injector import remove_rules_all

    if dry_run:
        print("🔎 Dry run: would remove injected AI Rule Learning sections from detected agent configs.")
        return

    removed = remove_rules_all()
    if removed:
        print(f"✅ Removed AI Rule Learning section from: {', '.join(removed)}")
    else:
        print("ℹ️  No AI Rule Learning section found in any agent config")


def cmd_memory(args: list[str]) -> None:
    dry_run, args = _consume_dry_run(args)

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
        if dry_run:
            print(f"🔎 Dry run: would remember [{mem_type}]: {content}")
            return
        entry = add_memory(mem_type, content)
        entries = load_memory()
        written = write_memory_all(entries)
        targets = ", ".join(n for n, _ in written) if written else "none detected"
        print(f"✅ Remembered [{entry['type']}]: {entry['content']}")
        print(f"   Written to: {targets}")

    elif subcmd == "clear":
        if dry_run:
            entries = load_memory()
            print(f"🔎 Dry run: would clear {len(entries)} memory entries")
            return
        n = clear_memory()
        print(f"✅ Cleared {n} memory entries")

    else:
        print(f"Unknown memory subcommand: {subcmd!r}")
        print("Available: show, add, clear")


def cmd_skills(args: list[str]) -> None:
    dry_run, args = _consume_dry_run(args)

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
        if dry_run:
            print(f"🔎 Dry run: would delete skill {name!r}")
            return
        if delete_skill(name):
            print(f"✅ Skill deleted: {name!r}")
        else:
            print(f"❌ Skill not found: {name!r}")

    else:
        print(f"Unknown skills subcommand: {subcmd!r}")
        print("Available: list, show <name>, delete <name>")


def cmd_install_cron(args: list[str]) -> None:
    dry_run, _args = _consume_dry_run(args)
    from .scheduler import install
    from .scheduler import status

    if dry_run:
        print("🔎 Dry run: would install nightly auto-sync scheduler at 02:00.")
        return

    msg = install()
    print(f"✅ {msg}")
    print(f"\nScheduler status: {status()}")
    print("The system will now sync automatically every night at 02:00.")


def cmd_uninstall_cron(args: list[str]) -> None:
    dry_run, _args = _consume_dry_run(args)
    from .scheduler import uninstall

    if dry_run:
        print("🔎 Dry run: would remove nightly auto-sync scheduler if installed.")
        return

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


def cmd_metrics(args: list[str]) -> None:
    from .metrics import metrics_status
    from .metrics import preview_metrics_payload
    from .metrics import set_metrics_enabled

    subcmd = args[0] if args else "status"

    if subcmd == "status":
        status = metrics_status()
        state = "enabled" if status["enabled"] else "disabled"
        print(f"Privacy-preserving metrics: {state}")
        print(f"  source: {status['source']}")
        print(f"  event_count: {status['event_count']}")
        print(f"  local_file: {status['events_path']}")
        print("  content: aggregate labels only; no prompts, rules, memory, paths, usernames, or hostnames")
        return

    if subcmd == "preview":
        print(preview_metrics_payload())
        return

    if subcmd == "enable":
        set_metrics_enabled(True)
        print("✅ Anonymous aggregate metrics enabled.")
        print("   You can inspect the exact payload with: ai-rule-learning metrics preview")
        return

    if subcmd == "disable":
        set_metrics_enabled(False)
        print("✅ Anonymous aggregate metrics disabled.")
        return

    print(f"Unknown metrics subcommand: {subcmd!r}")
    print("Available: status, preview, enable, disable")


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
        "metrics": cmd_metrics,
    }

    fn = dispatch.get(cmd)
    if fn is None:
        print(__doc__)
        print(f"Unknown command: {cmd!r}")
        print(f"Available: {', '.join(dispatch)}")
        sys.exit(1)

    try:
        fn(rest)
    except Exception:
        try:
            from .metrics import record_metric_event

            record_metric_event("cli_command", success=False, metadata={"command": cmd})
        except Exception:
            pass
        raise

    try:
        from .metrics import record_metric_event

        record_metric_event("cli_command", success=True, metadata={"command": cmd})
    except Exception:
        pass


if __name__ == "__main__":
    main()
