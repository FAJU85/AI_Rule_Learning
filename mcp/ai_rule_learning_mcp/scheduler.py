"""Cross-platform automatic sync scheduler.

Installs a nightly ai-rule-learning sync job using the best available
mechanism for the current platform:

  macOS   → LaunchAgent plist in ~/Library/LaunchAgents/
  Linux   → systemd user timer in ~/.config/systemd/user/  (preferred)
            crontab entry                                   (fallback)

The job runs `ai-rule-learning sync` nightly at 02:00 local time and
appends output to ~/.ai-rule-learning/sync.log.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

_LABEL = "com.ai-rule-learning.sync"
_LOG = Path.home() / ".ai-rule-learning" / "sync.log"
_CRON_MARKER = "# ai-rule-learning-sync"


# ── Helpers ────────────────────────────────────────────────────────────────

def _cli_path() -> str:
    """Return the absolute path to the ai-rule-learning CLI executable."""
    exe = shutil.which("ai-rule-learning")
    if exe:
        return exe
    # Fall back to same Python environment
    return str(Path(sys.executable).parent / "ai-rule-learning")


def _system() -> str:
    return platform.system()  # "Darwin" | "Linux" | "Windows"


# ── macOS LaunchAgent ──────────────────────────────────────────────────────

def _launchagent_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{_LABEL}.plist"


def _launchagent_plist(cli: str) -> str:
    log = str(_LOG)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{cli}</string>
        <string>sync</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>2</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>{log}</string>
    <key>StandardErrorPath</key>
    <string>{log}</string>
    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
"""


def _install_launchagent() -> str:
    cli = _cli_path()
    plist_path = _launchagent_path()
    plist_path.parent.mkdir(parents=True, exist_ok=True)
    plist_path.write_text(_launchagent_plist(cli), encoding="utf-8")
    try:
        subprocess.run(
            ["launchctl", "load", "-w", str(plist_path)],
            check=True, capture_output=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass  # launchctl may not be available in CI; plist is still written
    return f"LaunchAgent installed: {plist_path}\nRuns nightly at 02:00"


def _uninstall_launchagent() -> bool:
    plist_path = _launchagent_path()
    if not plist_path.exists():
        return False
    try:
        subprocess.run(
            ["launchctl", "unload", str(plist_path)],
            check=False, capture_output=True,
        )
    except FileNotFoundError:
        pass
    plist_path.unlink()
    return True


def _status_launchagent() -> str:
    p = _launchagent_path()
    if p.exists():
        return f"✅ LaunchAgent installed: {p}"
    return "⬜ LaunchAgent not installed"


# ── Linux systemd user timer ───────────────────────────────────────────────

def _systemd_dir() -> Path:
    return Path.home() / ".config" / "systemd" / "user"


def _service_path() -> Path:
    return _systemd_dir() / "ai-rule-learning.service"


def _timer_path() -> Path:
    return _systemd_dir() / "ai-rule-learning.timer"


def _systemd_service(cli: str) -> str:
    return f"""[Unit]
Description=AI Rule Learning — sync sessions and update guardrail rules

[Service]
Type=oneshot
ExecStart={cli} sync
StandardOutput=append:{_LOG}
StandardError=append:{_LOG}
"""


_SYSTEMD_TIMER = """[Unit]
Description=AI Rule Learning — nightly sync timer

[Timer]
OnCalendar=*-*-* 02:00:00
Persistent=true

[Install]
WantedBy=timers.target
"""


def _systemctl(*args: str) -> bool:
    try:
        subprocess.run(
            ["systemctl", "--user", *args],
            check=True, capture_output=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def _install_systemd() -> str:
    cli = _cli_path()
    d = _systemd_dir()
    d.mkdir(parents=True, exist_ok=True)
    _service_path().write_text(_systemd_service(cli), encoding="utf-8")
    _timer_path().write_text(_SYSTEMD_TIMER, encoding="utf-8")
    _systemctl("daemon-reload")
    _systemctl("enable", "--now", "ai-rule-learning.timer")
    return f"systemd timer installed: {_timer_path()}\nRuns nightly at 02:00"


def _uninstall_systemd() -> bool:
    if not _service_path().exists() and not _timer_path().exists():
        return False
    _systemctl("disable", "--now", "ai-rule-learning.timer")
    for p in [_service_path(), _timer_path()]:
        if p.exists():
            p.unlink()
    _systemctl("daemon-reload")
    return True


def _status_systemd() -> str:
    if _timer_path().exists():
        return f"✅ systemd timer installed: {_timer_path()}"
    return "⬜ systemd timer not installed"


# ── cron fallback ──────────────────────────────────────────────────────────

def _cron_line(cli: str) -> str:
    return f"0 2 * * * {cli} sync >> {_LOG} 2>&1  {_CRON_MARKER}"


def _read_crontab() -> str:
    try:
        result = subprocess.run(
            ["crontab", "-l"], capture_output=True, text=True
        )
        return result.stdout if result.returncode == 0 else ""
    except FileNotFoundError:
        return ""


def _write_crontab(content: str) -> bool:
    try:
        proc = subprocess.run(
            ["crontab", "-"], input=content, text=True, capture_output=True
        )
        return proc.returncode == 0
    except FileNotFoundError:
        return False


def _install_cron() -> str:
    cli = _cli_path()
    existing = _read_crontab()
    if _CRON_MARKER in existing:
        return "cron entry already installed"
    new_entry = _cron_line(cli)
    updated = (existing.rstrip() + "\n" + new_entry + "\n").lstrip()
    if _write_crontab(updated):
        return f"cron entry added:\n  {new_entry}\nRuns nightly at 02:00"
    return "cron entry written (crontab -l to verify)"


def _uninstall_cron() -> bool:
    existing = _read_crontab()
    if _CRON_MARKER not in existing:
        return False
    cleaned = "\n".join(
        ln for ln in existing.splitlines() if _CRON_MARKER not in ln
    ).strip() + "\n"
    _write_crontab(cleaned)
    return True


def _status_cron() -> str:
    if _CRON_MARKER in _read_crontab():
        return "✅ cron entry installed (runs nightly at 02:00)"
    return "⬜ cron entry not installed"


# ── Public API ─────────────────────────────────────────────────────────────

def install() -> str:
    """Install the nightly sync scheduler for the current platform."""
    _LOG.parent.mkdir(parents=True, exist_ok=True)
    system = _system()
    if system == "Darwin":
        return _install_launchagent()
    if system == "Linux":
        # Prefer systemd if available
        if shutil.which("systemctl"):
            return _install_systemd()
        return _install_cron()
    # Windows or unknown — cron fallback
    return _install_cron()


def uninstall() -> bool:
    """Remove the nightly sync scheduler. Returns True if anything was removed."""
    system = _system()
    if system == "Darwin":
        return _uninstall_launchagent()
    if system == "Linux":
        removed = _uninstall_systemd()
        if not removed:
            removed = _uninstall_cron()
        return removed
    return _uninstall_cron()


def status() -> str:
    """Return a human-readable status string for the current scheduler."""
    system = _system()
    if system == "Darwin":
        return _status_launchagent()
    if system == "Linux":
        systemd_st = _status_systemd()
        cron_st = _status_cron()
        if "✅" in systemd_st:
            return systemd_st
        if "✅" in cron_st:
            return cron_st
        return f"{systemd_st}\n{cron_st}"
    return _status_cron()


def is_installed() -> bool:
    return "✅" in status()
