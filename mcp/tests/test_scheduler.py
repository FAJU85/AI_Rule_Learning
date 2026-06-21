"""Tests for cross-platform automatic sync scheduler."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from ai_rule_learning_mcp.scheduler import (
    _CRON_MARKER,
    _cron_line,
    _install_cron,
    _install_launchagent,
    _install_systemd,
    _launchagent_path,
    _read_crontab,
    _service_path,
    _status_cron,
    _status_launchagent,
    _status_systemd,
    _timer_path,
    _uninstall_cron,
    _uninstall_launchagent,
    _uninstall_systemd,
    install,
    is_installed,
    status,
    uninstall,
)


def _patch_home(tmp: Path):
    return patch("ai_rule_learning_mcp.scheduler.Path.home", return_value=tmp)


class TestCronFallback:
    def test_cron_line_contains_marker(self):
        line = _cron_line("/usr/local/bin/ai-rule-learning")
        assert _CRON_MARKER in line
        assert "sync" in line
        assert "0 2 * * *" in line

    def test_install_cron_adds_entry(self):
        with patch("ai_rule_learning_mcp.scheduler._read_crontab", return_value=""), \
             patch("ai_rule_learning_mcp.scheduler._write_crontab", return_value=True) as mock_write, \
             patch("ai_rule_learning_mcp.scheduler._cli_path", return_value="/usr/bin/ai-rule-learning"):
            result = _install_cron()
        assert "cron" in result.lower()
        written = mock_write.call_args[0][0]
        assert _CRON_MARKER in written

    def test_install_cron_skips_if_already_present(self):
        existing = f"0 2 * * * /usr/bin/ai-rule-learning sync  {_CRON_MARKER}"
        with patch("ai_rule_learning_mcp.scheduler._read_crontab", return_value=existing):
            result = _install_cron()
        assert "already" in result

    def test_uninstall_cron_removes_entry(self):
        existing = f"# other job\n0 2 * * * x sync  {_CRON_MARKER}\n"
        with patch("ai_rule_learning_mcp.scheduler._read_crontab", return_value=existing), \
             patch("ai_rule_learning_mcp.scheduler._write_crontab", return_value=True) as mock_write:
            removed = _uninstall_cron()
        assert removed is True
        written = mock_write.call_args[0][0]
        assert _CRON_MARKER not in written
        assert "other job" in written

    def test_uninstall_cron_returns_false_if_not_present(self):
        with patch("ai_rule_learning_mcp.scheduler._read_crontab", return_value="# no marker\n"):
            assert _uninstall_cron() is False

    def test_status_cron_installed(self):
        with patch("ai_rule_learning_mcp.scheduler._read_crontab",
                   return_value=f"0 2 * * * x  {_CRON_MARKER}"):
            assert "✅" in _status_cron()

    def test_status_cron_not_installed(self):
        with patch("ai_rule_learning_mcp.scheduler._read_crontab", return_value=""):
            assert "⬜" in _status_cron()


class TestLaunchAgent:
    def test_install_creates_plist(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            plist = tmp / "Library" / "LaunchAgents" / "com.ai-rule-learning.sync.plist"
            with patch("ai_rule_learning_mcp.scheduler._launchagent_path", return_value=plist), \
                 patch("ai_rule_learning_mcp.scheduler._cli_path", return_value="/usr/bin/ai-rule-learning"), \
                 patch("subprocess.run"):
                _install_launchagent()
            assert plist.exists()
            content = plist.read_text()
            assert "com.ai-rule-learning.sync" in content
            assert "/usr/bin/ai-rule-learning" in content
            assert "<integer>2</integer>" in content  # hour = 2

    def test_uninstall_removes_plist(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            plist = tmp / "Library" / "LaunchAgents" / "com.ai-rule-learning.sync.plist"
            plist.parent.mkdir(parents=True)
            plist.write_text("<plist/>")
            with patch("ai_rule_learning_mcp.scheduler._launchagent_path", return_value=plist), \
                 patch("subprocess.run"):
                removed = _uninstall_launchagent()
            assert removed is True
            assert not plist.exists()

    def test_uninstall_returns_false_if_missing(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            plist = tmp / "Library" / "LaunchAgents" / "com.ai-rule-learning.sync.plist"
            with patch("ai_rule_learning_mcp.scheduler._launchagent_path", return_value=plist):
                assert _uninstall_launchagent() is False

    def test_status_launchagent_installed(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            plist = tmp / "Library" / "LaunchAgents" / "com.ai-rule-learning.sync.plist"
            plist.parent.mkdir(parents=True)
            plist.write_text("<plist/>")
            with patch("ai_rule_learning_mcp.scheduler._launchagent_path", return_value=plist):
                assert "✅" in _status_launchagent()

    def test_status_launchagent_not_installed(self):
        with tempfile.TemporaryDirectory() as d:
            plist = Path(d) / "missing.plist"
            with patch("ai_rule_learning_mcp.scheduler._launchagent_path", return_value=plist):
                assert "⬜" in _status_launchagent()


class TestSystemd:
    def test_install_creates_service_and_timer(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            systemd_dir = tmp / ".config" / "systemd" / "user"
            svc = systemd_dir / "ai-rule-learning.service"
            tmr = systemd_dir / "ai-rule-learning.timer"
            with patch("ai_rule_learning_mcp.scheduler._systemd_dir", return_value=systemd_dir), \
                 patch("ai_rule_learning_mcp.scheduler._service_path", return_value=svc), \
                 patch("ai_rule_learning_mcp.scheduler._timer_path", return_value=tmr), \
                 patch("ai_rule_learning_mcp.scheduler._systemctl", return_value=True), \
                 patch("ai_rule_learning_mcp.scheduler._cli_path", return_value="/usr/bin/ai-rule-learning"):
                _install_systemd()
            assert svc.exists()
            assert tmr.exists()
            assert "02:00:00" in tmr.read_text()
            assert "/usr/bin/ai-rule-learning" in svc.read_text()

    def test_uninstall_removes_files(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            svc = tmp / "ai-rule-learning.service"
            tmr = tmp / "ai-rule-learning.timer"
            svc.write_text("[Service]")
            tmr.write_text("[Timer]")
            with patch("ai_rule_learning_mcp.scheduler._service_path", return_value=svc), \
                 patch("ai_rule_learning_mcp.scheduler._timer_path", return_value=tmr), \
                 patch("ai_rule_learning_mcp.scheduler._systemctl", return_value=True):
                removed = _uninstall_systemd()
            assert removed is True
            assert not svc.exists()
            assert not tmr.exists()

    def test_status_systemd_installed(self):
        with tempfile.TemporaryDirectory() as d:
            tmr = Path(d) / "ai-rule-learning.timer"
            tmr.write_text("[Timer]")
            with patch("ai_rule_learning_mcp.scheduler._timer_path", return_value=tmr):
                assert "✅" in _status_systemd()

    def test_status_systemd_not_installed(self):
        with tempfile.TemporaryDirectory() as d:
            tmr = Path(d) / "ai-rule-learning.timer"
            with patch("ai_rule_learning_mcp.scheduler._timer_path", return_value=tmr):
                assert "⬜" in _status_systemd()


class TestPublicApi:
    def test_install_macos_uses_launchagent(self):
        with patch("ai_rule_learning_mcp.scheduler._system", return_value="Darwin"), \
             patch("ai_rule_learning_mcp.scheduler._install_launchagent", return_value="ok") as mock:
            install()
        mock.assert_called_once()

    def test_install_linux_systemd(self):
        with patch("ai_rule_learning_mcp.scheduler._system", return_value="Linux"), \
             patch("ai_rule_learning_mcp.scheduler.shutil.which", return_value="/bin/systemctl"), \
             patch("ai_rule_learning_mcp.scheduler._install_systemd", return_value="ok") as mock:
            install()
        mock.assert_called_once()

    def test_install_linux_cron_fallback(self):
        with patch("ai_rule_learning_mcp.scheduler._system", return_value="Linux"), \
             patch("ai_rule_learning_mcp.scheduler.shutil.which", return_value=None), \
             patch("ai_rule_learning_mcp.scheduler._install_cron", return_value="ok") as mock:
            install()
        mock.assert_called_once()

    def test_uninstall_macos(self):
        with patch("ai_rule_learning_mcp.scheduler._system", return_value="Darwin"), \
             patch("ai_rule_learning_mcp.scheduler._uninstall_launchagent", return_value=True) as mock:
            result = uninstall()
        assert result is True
        mock.assert_called_once()

    def test_is_installed_true(self):
        with patch("ai_rule_learning_mcp.scheduler.status", return_value="✅ installed"):
            assert is_installed() is True

    def test_is_installed_false(self):
        with patch("ai_rule_learning_mcp.scheduler.status", return_value="⬜ not installed"):
            assert is_installed() is False
