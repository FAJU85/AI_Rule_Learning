# Full Project Audit

Date: 2026-07-13

## Executive Summary

The repository contains two related surfaces:

1. the root AI Rule Learning Python package under `src/`, and
2. the packaged MCP server/CLI under `mcp/ai_rule_learning_mcp/`.

The MCP package is the most complete and best-tested surface. The root package has useful domain
modules, tests, and CLI code, but it still depends on heavier external services and had a broken
build backend before this audit.

Two concrete infrastructure issues were fixed during the audit:

- `docker-compose.yml` referenced a missing `Dockerfile`.
- root `pyproject.toml` used an invalid build backend, `setuptools.backends.legacy`.

---

## Phase 1 — File Review and Architecture

### File Catalog

| Category              | Files                                                                                                                                         |
| --------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| Root package config   | `pyproject.toml`, `requirements.txt`, `requirements-dev.txt`, `package.json`, `package-lock.json`                                             |
| Container config      | `Dockerfile`, `.dockerignore`, `docker-compose.yml`, `.env.example`                                                                           |
| GitHub automation     | `.github/workflows/*.yml`, `.github/ISSUE_TEMPLATE/*.yml`, `.github/PULL_REQUEST_TEMPLATE.md`, `.github/CODEOWNERS`, `.github/labeler.yml`    |
| Project docs          | `README.md`, `CONTRIBUTING.md`, `FEEDBACK.md`, `ROADMAP.md`, `SECURITY.md`, `SUPPORTED_VERSIONS.md`, `CHANGELOG.md`, `PRIVACY.md`, `TERMS.md` |
| Audit/governance docs | `docs/AI_REVIEW.md`, `docs/BRANCH_PROTECTION.md`, `docs/PRODUCT_GAPS.md`, `docs/FULL_PROJECT_AUDIT.md`                                        |
| Root source           | `src/adapters`, `src/cli`, `src/core`, `src/models`, `src/services`, `src/utils`                                                              |
| MCP source            | `mcp/ai_rule_learning_mcp/*.py`, `mcp/pyproject.toml`, `mcp/README.md`, `mcp/CHANGELOG.md`                                                    |
| Space/UI source       | `space/app.py`, `space/mcp_introspect.py`, `space/README.md`, `space/requirements.txt`                                                        |
| Scripts               | `scripts/export_sessions.py`, `scripts/run_analysis.py`, `scripts/upload_historical.py`                                                       |
| Tests                 | `tests/*.py`, `mcp/tests/*.py`, `space/test_mcp_introspect.py`                                                                                |
| Data fixtures         | `data/guardrails.yaml`, `data/work_rules.jsonl`                                                                                               |

### Entry Points

| Entry point              | Purpose                                          | Status           |
| ------------------------ | ------------------------------------------------ | ---------------- |
| `python -m src.cli.main` | Root interactive/analyze/validate/list-rules CLI | Partial          |
| `ai-rule-learning-mcp`   | MCP stdio server from `mcp/pyproject.toml`       | Working          |
| `ai-rule-learning`       | MCP package CLI from `mcp/pyproject.toml`        | Working          |
| `space/app.py`           | Gradio management/analyze UI                     | Partial          |
| `docker-compose.yml`     | Redis + root CLI app container                   | Fixed config gap |

### Root Package Architecture

```text
src/cli/main.py
  ├─ adapters/openai_adapter.py or adapters/claude_adapter.py
  ├─ core/interceptor.py
  │  ├─ core/alignment_sensor.py
  │  ├─ core/gap_detector.py
  │  └─ core/rule_engine.py
  ├─ core/dataset_manager.py
  ├─ services/analysis_service.py
  └─ services/validation_service.py
```

Data flow:

1. User starts a chat or analysis command through `src/cli/main.py`.
2. The CLI chooses an AI adapter from settings.
3. The interceptor records turns and applies active rules.
4. Gap detection and analysis services identify recurring mistakes.
5. Dataset manager persists conversations and rules.
6. Rule engine loads active rules from Redis or persistent storage.

### MCP Package Architecture

```text
mcp/ai_rule_learning_mcp/server.py
  ├─ providers.py      # parse local session exports
  ├─ gap_detector.py   # detect patterns and generate rules
  ├─ store.py          # local JSONL persistence and safety filtering
  ├─ injector.py       # write memory/rules/skills to agent configs
  ├─ memory.py         # local memory facts/preferences
  ├─ skills.py         # local skill markdown files
  ├─ scheduler.py      # LaunchAgent/systemd/cron automation
  └─ analyzer.py       # health, failure mode, injection, effectiveness reports
```

MCP data flow:

1. User or MCP client calls a tool such as `sync_sessions` or `record_feedback`.
2. Providers parse local session files into normalized conversation records.
3. Gap detector generates rules from repeated patterns.
4. Store persists JSONL files under `~/.ai-rule-learning/`.
5. Injector writes idempotent markdown blocks to supported agent config files.
6. Scheduler can optionally run sync nightly.

### Build Pipeline and Tool Registration

| Area              | Registration                                                            |
| ----------------- | ----------------------------------------------------------------------- |
| Root Python build | `pyproject.toml` with `setuptools.build_meta`                           |
| MCP Python build  | `mcp/pyproject.toml` with console scripts                               |
| Node tooling      | `package.json` scripts for Markdown lint/format and commit hooks        |
| CI                | `.github/workflows/ci.yml` runs Python, Markdown, and commitlint checks |
| PR labels         | `.github/workflows/labeler.yml` + `.github/labeler.yml`                 |
| AI review         | `.github/workflows/ai-review.yml` + `.coderabbit.yaml`                  |
| Welcome messages  | `.github/workflows/welcome.yml`                                         |
| Docker            | `docker-compose.yml` uses `Dockerfile` for root CLI app + Redis         |

### Component Status

| Component            | Status         | Notes                                                                       |
| -------------------- | -------------- | --------------------------------------------------------------------------- |
| MCP server           | Working        | MCP tests pass locally.                                                     |
| MCP CLI              | Working        | Covered by MCP tests and docs.                                              |
| MCP injector         | Working        | Idempotent target writes are tested.                                        |
| MCP scheduler        | Working        | Scheduler behavior is unit-tested; OS services need real host verification. |
| Root CLI             | Partial        | Tests pass, but real chat requires API credentials and external services.   |
| Root dataset manager | Partial        | Depends on external storage credentials for full behavior.                  |
| Gradio Space UI      | Partial        | Needs UX redesign and stronger product fit.                                 |
| Docker compose       | Fixed          | `Dockerfile` and `.env.example` added.                                      |
| Root packaging       | Fixed          | Invalid backend replaced with `setuptools.build_meta`.                      |
| CI automation        | Working config | Needs GitHub-hosted run to validate external action behavior.               |

---

## Phase 2 — Roadmap and Prioritized Backlog

### Blocker

| Item                                              | Dependency | Effort | Status |
| ------------------------------------------------- | ---------- | ------ | ------ |
| Add missing `Dockerfile` for `docker-compose.yml` | Docker     | Small  | Fixed  |
| Fix root package build backend                    | setuptools | Small  | Fixed  |

### High Priority

| Item                                        | Dependency             | Effort | Notes                                                         |
| ------------------------------------------- | ---------------------- | ------ | ------------------------------------------------------------- |
| Add rule review lifecycle states            | MCP store/CLI/injector | Medium | Pending/approved/rejected/active/stale/needs_review.          |
| Extend dry-run mode beyond CLI              | MCP server/dashboard   | Medium | CLI dry-run added; MCP tools and future UI still need parity. |
| Improve local management dashboard          | UI framework decision  | Large  | Should replace confusing external management workflows.       |
| Make external storage optional and explicit | MCP/root settings      | Medium | Avoid silent behavior and hidden dependencies.                |

### Medium Priority

| Item                                   | Dependency       | Effort | Notes                                                             |
| -------------------------------------- | ---------------- | ------ | ----------------------------------------------------------------- |
| Add opt-in adoption metrics design     | Privacy docs     | Medium | Must avoid raw prompts, code, secrets, paths, and memory content. |
| Add richer example fixtures            | Tests/docs       | Small  | Improves contributor onboarding.                                  |
| Add actionlint validation              | CI               | Small  | Validates GitHub workflow syntax locally/CI.                      |
| Add dependency/security scanning tools | CI secrets/tools | Medium | `pip-audit` and `gitleaks` are not installed locally.             |

### Low Priority

| Item                              | Dependency                  | Effort | Notes                                                   |
| --------------------------------- | --------------------------- | ------ | ------------------------------------------------------- |
| Replace deprecated datetime usage | Python modules/tests        | Medium | Tests emit many Python 3.14 deprecation warnings.       |
| Tighten type checking             | mypy config                 | Medium | Current local mypy run is blocked by environment stubs. |
| Improve changelog consistency     | Maintainer release workflow | Small  | Some docs are ahead of tagged releases.                 |

---

## Phase 3 — Troubleshooting and Fixes

### Error 1 — Missing Dockerfile

Root cause: `docker-compose.yml` had `dockerfile: Dockerfile`, but the repository did not contain a
`Dockerfile`.

Reproduction:

```bash
rg --files -g 'Dockerfile*'
sed -n '1,80p' docker-compose.yml
```

Fix applied:

- Added `Dockerfile` for the root Python app.
- Added `.dockerignore` to keep builds smaller and avoid copying local secrets/cache.
- Added `.env.example` to document required environment variables.

Verification:

- File now exists and matches the compose reference.
- Formatting and repository tests were run after the change.

### Error 2 — Invalid Root Build Backend

Root cause: root `pyproject.toml` used `setuptools.backends.legacy`, which pip could not import.

Reproduction:

```bash
python -m pip install -e . --no-deps --no-build-isolation
python -m pytest -c /dev/null mcp/tests/test_cli_dry_run.py -q
```

Observed failure:

```text
BackendUnavailable: Cannot import 'setuptools.backends.legacy'
```

Fix applied:

- Changed root `pyproject.toml` build backend to `setuptools.build_meta`.

Verification:

- Root packaging configuration now references a valid setuptools backend.
- `python -m pip install -e . --no-deps --no-build-isolation
python -m pytest -c /dev/null mcp/tests/test_cli_dry_run.py -q` now succeeds in this environment.

### Known Environment Limitation

`mypy src` fails in this container because installed NumPy stubs use syntax that conflicts with the
current Python 3.14 environment:

```text
Type statement is only supported in Python 3.12 and greater
```

The repository targets Python 3.11 in config and CI, so this is tracked as an environment/tooling
limitation rather than a source-code regression.

---

## Phase 4 — Development Completed

Implemented during this audit:

- full audit notes for future reference,
- missing Docker build file,
- Docker ignore file,
- environment example file,
- root package build backend fix,
- MCP CLI dry-run support for write/destructive commands.

---

## Validation Summary

Commands run during the audit:

```bash
ruff format --check .
npm run format:check
npm run lint
ruff check .
mypy src
python -m pytest -o addopts='' tests -q
python -m pytest -c /dev/null mcp/tests -q
python -m pip install -e . --no-deps --no-build-isolation
python -m pytest -c /dev/null mcp/tests/test_cli_dry_run.py -q
```

Results:

- Formatting passed.
- Markdown linting passed.
- Ruff linting passed.
- Root tests passed.
- MCP tests passed.
- MCP CLI dry-run tests passed.
- mypy was blocked by the local Python 3.14 / NumPy stub mismatch described above.
