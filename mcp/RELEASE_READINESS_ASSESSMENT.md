# Release Readiness Assessment — `ai-rule-learning-mcp`

**Scope:** Public-release readiness of the `ai-rule-learning-mcp` package (assessment only — no release performed).
**Method:** Source review + fresh-venv build/install + automated audits (`pytest`, `ruff`, `mypy`, `pip-audit`, `bandit`, `twine`-equivalent build).
**Candidate version:** `0.2.0` (currently on PyPI: `0.1.0`, `0.1.1`).
**Date:** 2026-06-25

---

## Evidence summary (what was actually run)

| Check | Result |
|---|---|
| Fresh-venv build (`python -m build`) | ✅ sdist + wheel build clean |
| Fresh-venv install (`pip install dist/*.whl`) | ✅ exit 0, imports, both entry points resolve |
| Entry points (`ai-rule-learning`, `ai-rule-learning-mcp`) | ✅ CLI `--help` works; `server.main` callable |
| `pytest` | ✅ 264 passed |
| `pip-audit` | ✅ no known vulnerabilities in deps |
| `bandit` | ⚠️ 0 High, 4 Medium, 23 Low |
| `ruff check` (package) | ⚠️ 21 findings (10 I001, 6 F401, 4 E741, 1 F841) |
| `mypy` (package) | ⚠️ 2 missing-annotation errors |
| Secret scan | ✅ none (HF token via env only) |

---

## 🔵 Blue Hat — Process & Control

### Process readiness
| AC | Status | Notes |
|---|---|---|
| Packaging standards | ✅ | PEP 621 `pyproject.toml`, setuptools backend, clean `ai_rule_learning_mcp/` layout |
| Version + changelog | ⚠️ | Version `0.2.0` consistent in `pyproject` + `__init__`; **no package `CHANGELOG.md`** |
| Deps pinned w/ ranges | ✅ | `mcp>=1.0.0`, `huggingface-hub>=0.23.0` — compatible ranges |
| Clean `pip install` (fresh venv) | ✅ | verified from built wheel |
| No import/entry-point errors | ✅ | both scripts work |
| Server/CLI start without crash | ✅ | CLI `--help` OK |
| Documentation (README/usage/API) | ⚠️ | README solid, but **tools table lists 11 of 12 tools** — missing `update_community_knowledge` |
| License present | ✅ | `LICENSE` at root (⚠️ Source-Available, not OSI — see Red Hat) |
| No hardcoded secrets | ✅ | `HF_TOKEN` from env |
| `.gitignore` hygiene | ✅ | excludes `.env`, venv, caches, `dist/`/`build/` |

### Release checklist
| AC | Status | Notes |
|---|---|---|
| PyPI name owned/available | ✅ | already publishing as `ai-rule-learning-mcp` |
| Build artifacts generate | ✅ | sdist + wheel; CI runs `twine check` |
| **Test PyPI staging** | ⚠️ | `publish-mcp.yml` publishes **straight to prod PyPI**; no TestPyPI step |
| CI/CD release pipeline | ✅ | `publish-mcp.yml` — tag `mcp-v*` → **trusted publishing (OIDC)**; `release.yml` present |
| Versioning strategy | ✅ | semver; `Development Status :: 3 - Alpha` |
| Issue tracker ready | ✅ | Bug Tracker URL set |
| Contribution/community policy | ✅ | `CONTRIBUTING.md` + `CODE_OF_CONDUCT.md` present |

### Quality gates
| AC | Status | Notes |
|---|---|---|
| Tests pass | ✅ | 264 passed |
| Coverage measurable | ✅ | `pytest-cov` configured |
| Linter/formatter | ⚠️ | 21 ruff findings (package is excluded from repo CI ruff, so ungated) |
| Type check | ⚠️ | 2 mypy errors |
| No known critical bugs | ✅ | A1/A3/A4 fixed in PR #253 |
| Backward compatibility | ✅ | additive tools; `serverInfo.version` now correct vs 0.1.1 |

---

## 🔴 Red Hat — Risk & Intuition

### Risk identification
| AC | Status | Notes |
|---|---|---|
| No eval/exec of untrusted input | ✅ | `eval` refs are detection strings, not calls |
| Subprocess safety | ✅ | all `subprocess.run([...])` list-form, **no `shell=True`** (cron/launchctl). bandit B607 partial-path is minor |
| Dependency audit | ✅ | `pip-audit` clean |
| **Supply-chain (community data)** | 🔴 | `hf_hub_download(...)` for the community dataset is **not revision-pinned** (bandit B615 ×4). Combined with the injector writing rules into user agent configs, a poisoned dataset is the sharpest risk |
| Rule-safety gate | 🟠 | `_is_safe_rule` exists but is a **denylist** (`_UNSAFE_PHRASES`) — weaker than allowlist validation |
| Error handling | 🟠 | tool handlers return structured `❌` text, but **no top-level try/except** in `call_tool` → an unexpected handler exception surfaces via the MCP framework (may include exception text) |
| Data privacy | ✅ | `scrub_pii` redacts email/home/IP/phone/token before storage **and** upload; truncated to 4000 chars |
| Contribution default | ✅ | `ARL_CONTRIBUTE` defaults **false** (opt-in); HF upload gated on `HF_DATASET`+`HF_TOKEN` |
| Backend availability / fallback | ✅ | HF calls wrapped in try/except; local-storage fallback when HF unconfigured |

### Gut-check
- **Real problem?** Yes — persistent, self-improving guardrails/memory across AI sessions is a genuine pain point.
- **5-min UX?** Strong — CLI is zero-config (`ai-rule-learning sync`).
- **"Why would it do that?" surprises?** Yes, two powerful default behaviors: it **writes into user AI-agent config files** (Claude/Cursor/Windsurf/Copilot) and **installs a cron/systemd/launchd job**. Both need explicit, upfront consent framing.
- **Name accuracy?** ✅ accurate and descriptive.
- **Competitors?** Memory space is crowded (mem0, Letta/MemGPT, memory MCP servers); the *guardrail-rule-learning + auto-injection* angle is the differentiator.
- **Community readiness?** MCP ecosystem is early but growing — acceptable timing for an Alpha.

---

## Gap Analysis & Recommendations

### Missing items (by severity)
**Blocking (fix before publish):**
- **B1 — Lint/type not clean:** 21 ruff + 2 mypy findings in the shipped package.
- **B2 — Docs incomplete/under-disclosed:** README missing `update_community_knowledge`; no clear disclosure that the tool writes to agent config files, installs a scheduler, and (opt-in) uploads scrubbed conversation snippets.
- **B3 — Supply-chain hardening:** community downloads unpinned (B615); rule-safety is denylist-only.

**Warning (strongly recommended):**
- No package `CHANGELOG.md`.
- No top-level error containment in `call_tool`.
- No TestPyPI staging step in the publish workflow.

**Nice-to-have (v0.2.x):**
- License classifier / SPDX clarity (Source-Available is unusual on PyPI; set expectations in README).
- Tighten `_is_safe_rule` toward allowlist/schema validation.

### Risk mitigations
| Risk | Mitigation |
|---|---|
| Poisoned community dataset → injected rules | Pin `revision=` on `hf_hub_download`; validate community rules through `_is_safe_rule` (confirm on the pull path) before activation/injection |
| Surprising side effects | README "What it writes / installs / uploads" section; keep `contribute` opt-in |
| Exception leakage | wrap `call_tool` dispatch in try/except → structured error |

---

## Verdict — **CONDITIONAL-GO** at **v0.2.0** (Alpha)

The package builds, installs cleanly in a fresh environment, passes 264 tests, has clean dependency audit, working entry points, opt-in privacy defaults, and a **fully built OIDC trusted-publishing pipeline**. It is close. The conditions below are about polish + trust, not fundamental defects.

**Release blockers with acceptance criteria:**
1. **B1 — Clean gates:** `ruff check ai_rule_learning_mcp/` and `mypy ai_rule_learning_mcp/` exit 0 (or documented excludes).
2. **B2 — Docs/disclosure:** all 12 tools in README; a section disclosing config-file writes, scheduler install, and opt-in community upload.
3. **B3 — Supply-chain:** `hf_hub_download` calls revision-pinned (bandit B615 resolved); community-sourced rules confirmed to pass `_is_safe_rule` before injection.

**On meeting B1–B3 → GO.** Recommended version **`0.2.0`** (not `1.0.0` — API is still `Development Status :: Alpha`). Release path: push tag **`mcp-v0.2.0`** (triggers `publish-mcp.yml`), then swap the Space `requirements.txt` git reference back to the pinned PyPI release.

---

*Out of scope (per card): actual PyPI release, new feature development.*
