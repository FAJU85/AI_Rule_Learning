# Runtime Inventory & Keep / Replace / Delete Map

- **Status:** PROPOSED — inventory taken 2026-10-30 against the repo copy of
  `mcp/ai_rule_learning_mcp` (reports version 0.2.7). Companion to `docs/ACCEPTANCE.md`.
- **Purpose:** answer, before any building, "are we stacking layers or replacing them?" Every
  runtime path is tagged **KEEP / REPLACE / DELETE / AUDIT** so the Tier work lands as
  replacement, not accretion. No code is changed by this document.

## Baseline (what exists now)

- Runtime package: **9,101 lines**, 23 modules.
- **21 MCP tools** exposed to every agent session (each tool's schema costs tokens in the tool
  list of every session, before any rule is ever injected).
- Rule corpus: **130 rules** in `catalog_v1.json`.
- Deterministic detectors: **2 of 9** registry checks implemented (`no_comments`, `f_strings`).

## The core value loop, and the break in it

The tool's reason to exist is one loop: **correction → rule → cheap enforcement → fewer
corrections**. As built, that loop is split across two paths that never meet:

1. **The live path (what agents call).** `record_feedback` → `generate_rules` → store; then
   `get_guardrail_rules` → `load_active_rules` + `RuleCatalog.select(budget=500, max=10)` →
   merge (local first, padded with generic catalog rules up to 10) → `format_rules_block` →
   `write_rules_all` into every detected agent config. This path is **100% Tier-3 text
   injection**. It never calls `classify` or `enforce`.
2. **The enforcement path (what nothing calls).** `enforcement.classify` / `enforce` /
   `enforce_all` are reachable **only** from `cli.py` as a manual `ai-rule-learning enforce
<file.py>` subcommand. It is **not an MCP tool** and is **not imported by `server.py`**.

**Consequence:** the deterministic-enforcement differentiator is a disconnected CLI dead-end.
The headline "AST enforcement" is, in the shipped agent flow, dead code. This is the single
most important thing to fix, and it is _not_ "add a new layer" — it is "connect the layer that
already exists to the loop and delete the CLI-only dead-end once connected."

## Keep / Replace / Delete — core loop

| Path                                              | Module                                                          | Verdict                 | Note                                                                                                                                                                                                 |
| ------------------------------------------------- | --------------------------------------------------------------- | ----------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 7 `pending` detector stubs                        | `enforcement.py` REGISTRY                                       | **REPLACE**             | Implement `no_print`, `no_else`, `type_hints`, `snake_case`, `short_funcs`, `pathlib`, `single_block` (thin `ruff`/`mypy`/AST wrappers). Converts dead stubs to live code — net dead code goes down. |
| Enforcement wiring                                | `server.py` ⇄ `enforcement.py`                                  | **ADD (essential)**     | The one justified net-new connection: route rules to enforcement (hook / PostToolUse / flow). Offsets a deletion below, so not a net layer.                                                          |
| CLI-only `enforce` entry                          | `cli.py:cmd_enforce`                                            | **DELETE after wiring** | Keep the detectors; remove the orphan subcommand once the loop calls enforcement directly.                                                                                                           |
| Inject-everything merge + 10-rule catalog padding | `server.py:get_guardrail_rules` (≈940–971)                      | **REPLACE**             | Stop padding the prompt with generic catalog defaults. Route each rule by tier; inject **only** Tier-3 rules as text. Tier-1 rules leave the prompt entirely.                                        |
| Distillation + cosmetic slot naming               | `gap_detector.py:distill_directive`, `_build_rule`, `_SLOT_MAP` | **REPLACE**             | Phase 2: decompose multi-part feedback, reject non-directives, drop the `-<hash>` slot names that carry no information.                                                                              |
| Tier-3 injection mechanism                        | `injector.py:format_rules_block`, `write_rules_all`             | **KEEP (scope down)**   | Correct mechanism for Tier-3; restrict it to Tier-3 rules only.                                                                                                                                      |
| Catalog as corpus                                 | `catalog.py`, `catalog_v1.json`                                 | **KEEP (repurpose)**    | Becomes the tier-assignment source (`acceptance/corpus/tiering.json`), not an always-injected text block.                                                                                            |
| Rule schema / safety                              | `rule_schema.py`, `safety.py`                                   | **KEEP**                | Validation stays; extend with validate-before-activate (G4.2).                                                                                                                                       |
| Store                                             | `store.py`                                                      | **KEEP**                | Learned-rule persistence; unchanged by tiering.                                                                                                                                                      |

## Satellite subsystems — AUDIT (owner decides)

These are runtime modules and MCP tools outside the core correction→enforce loop. Each adds
tool-list tokens, maintenance surface, and dead-code risk. I am **not** proposing to delete
features unilaterally; each is flagged for an explicit owner keep / defer / delete call, with a
liveness check.

| Module (lines)                                                  | MCP tool(s)                              | Why flagged                                                                          |
| --------------------------------------------------------------- | ---------------------------------------- | ------------------------------------------------------------------------------------ |
| `community.py` (518)                                            | `update_community_knowledge`             | P3 retired the `arl-community-rules` bucket; verify this is not already partly dead. |
| `scheduler.py` (321)                                            | `install_scheduler`                      | Separate concern from the learn→enforce loop.                                        |
| `skills.py` (275)                                               | `save_skill`, `get_skill`, `list_skills` | Separate feature surface.                                                            |
| `memory.py` (199)                                               | `remember`, `recall`                     | Overlaps conceptually with rules; confirm it is used.                                |
| `analyzer.py` (179), `kpi.py` (145), `metrics.py` (169)         | `analyze`, `why`, `review_rule_health`   | Reporting surface; confirm each path is exercised.                                   |
| `providers.py` (286)                                            | `list_providers`                         | Model-backend listing.                                                               |
| `clustering.py` (105), `similarity.py` (132), `dataset.py` (88) | `suggest_duplicate_rules`, `merge_rules` | Dedup/merge utilities; confirm reachable from the live flow.                         |

Minimum audit per satellite: is it called from the live path or tests? If not, it is a
deletion candidate (reduces the 21-tool surface and token cost) pending owner sign-off.

## Net-change discipline (enforced by the complexity budget)

- Phase 1 is **net-negative** on dead code: it implements stubs and deletes the CLI dead-end.
- No phase adds a runtime module without a matching deletion or an explicit owner exception.
- The only sanctioned net-new runtime connection is wiring enforcement into the loop, and it
  retires the CLI-only path in the same change.
- Per-session token cost (tool-list + injected rules) must be **measured before and after each
  phase** and must not rise. See `docs/ACCEPTANCE.md` §11.
