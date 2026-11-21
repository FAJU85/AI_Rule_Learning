#!/bin/bash
set -euo pipefail

# Restore this repository's local quality gates in Claude Code cloud sessions.
# Fresh containers start without the repo's node_modules or a faithful Python
# env, which leaves husky's commit-msg (commitlint) and pre-commit (lint-staged)
# hooks inactive and can pull drifted dependencies. Without this, bad commits
# slip past local checks and only CI catches them. Runs only in cloud sessions;
# local contributors manage their own environment.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-.}"

# Node deps: reinstalls husky git hooks + commitlint + lint-staged + markdown
# and format tooling. Gated on the manifests so it only runs when they change.
node_hashes=node_modules/.session-start.sha256
if ! sha256sum --check --status "$node_hashes" 2>/dev/null; then
  rm -f "$node_hashes"
  npm install
  sha256sum .claude/hooks/session-start.sh package.json package-lock.json > "$node_hashes" || rm -f "$node_hashes"
fi

# Python deps: installs the pinned runtime + dev deps and the MCP package
# editable (its pin keeps mcp>=1,<2), so ruff/mypy/pytest run against the real,
# faithfully-pinned product instead of a drifted container. The hash file lives
# in the interpreter's site-packages so it disappears with the packages.
pyhashes="$(python3 -I -c 'import sysconfig; print(sysconfig.get_path("purelib"))')/.arl-session-start.sha256"
if ! sha256sum --check --status "$pyhashes" 2>/dev/null; then
  rm -f "$pyhashes"
  # --ignore-installed PyJWT: the cloud base image ships a debian PyJWT with no
  # RECORD file that pip cannot uninstall; install our pinned copy over it.
  python3 -m pip install -q --ignore-installed PyJWT -r requirements.txt -r requirements-dev.txt
  python3 -m pip install -q -e mcp
  sha256sum .claude/hooks/session-start.sh requirements.txt requirements-dev.txt mcp/pyproject.toml > "$pyhashes" || rm -f "$pyhashes"
fi
