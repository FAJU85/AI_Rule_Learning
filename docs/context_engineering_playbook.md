# Spec-Driven Context Engineering & Token Optimization Playbook

## 1. Core Operational & Compression Rules

### A. Input & Representation Engineering

1. **Semantic Compression (Code-as-Prompt):** Replace natural language descriptions with `Interfaces`, `Pydantic Models`, and empty function stubs (`raise NotImplementedError`).
2. **English Technical Directives:** Write all docstrings, variable names, and constraints in English to minimize Byte-Pair Encoding (BPE) tokenization overhead.
3. **AST Skeletons over Implementations:** When referencing external files, pass only type definitions and function signatures (`.pyi` or `.d.ts`). Omit implemented function bodies.
4. **Surgical File Reads:** Forbid the agent from reading files exceeding 150 lines in full. Enforce `ripgrep` (`rg -n`) to locate exact line numbers and read a 50-line window around the target.
5. **Mock Data Compression:** Pass test payloads in compact `CSV` or `YAML` instead of verbose `JSON` to reduce structural token overhead by 40–50%.
6. **Compressed Library Docs:** Feed `/llms.txt` or type stub files (`.d.ts` / `.pyi`) instead of raw web documentation dumps.

### B. Memory Management & KV-Cache Optimization

1. **Strict Prefix Stability (KV-Cache Hit):** Order every prompt from static at the top to dynamic at the bottom:
   `[1. System Rules] -> [2. Contracts/Types] -> [3. Active File & Task]`. Never mutate top sections mid-session to retain up to 90% prompt caching discounts.
2. **Immediate Context Pruning (Stateless Rollback):** When code fails, **do not reply in a new turn**. Copy the compiler error, delete the failed response, edit your previous prompt to append the error log, and regenerate from a clean state.
3. **Ephemeral Staging (Context Isolation):** Use a separate, disposable chat window to transpile messy natural language ideas into a clean `Spec` stub, then paste only the resulting code artifact into your primary project context.
4. **Stack Trace Pruning:** Never paste full terminal dumps. Pass only the first 2 lines showing the call site in your code and the final 2 lines showing the exact `Exception Type & Message`.

### C. Output & Infrastructure Control

1. **Unified Diffs / Search-Replace Only:** Forbid full-file reprints. Enforce `Unified Diff` or `SEARCH/REPLACE` blocks, as Output Tokens cost 3x–5x more than Input Tokens.
2. **Tool Schema Pruning (Disable Idle MCPs):** Disable all unused MCP servers. Active MCP tools inject massive JSON schemas into the system prompt on every single turn.
3. **Tiered Model Routing:**
   - Use a heavy reasoning model (Pro / Opus) with `Thinking: High` strictly for `PHASE 1: SPEC`.
   - Route atomic test generation and implementation (`RED` & `GREEN`) to a fast, low-cost model (Flash / Haiku) with `Thinking: Low/Minimal`.
4. **Early Termination (Stop Sequences):** Set a strict `max_output_tokens` ceiling and configure custom stop sequences (e.g., `# END_PHASE`) to sever generation the millisecond the code block closes.

---

## 2. Context Ignore Specification

Place `.cursorignore`, `.clineignore`, and `.rooignore` in the project root to prevent autonomous agents from ingesting high-token and transient audit artifacts:

```text
node_modules/
.venv/
venv/
env/
__pycache__/
.pytest_cache/
dist/
build/
.next/
out/
coverage/
*.lock
package-lock.json
pnpm-lock.yaml
yarn.lock
poetry.lock
uv.lock
migrations/
*.min.js
*.min.css
*.map
*.svg
*.png
*.jpg
*.sqlite
*.db
*.log
active_rules.json
data/active_rules.json
.ai-rule-learning/
```

---

## 3. Autonomous Agent Execution Loop

Agents operate under a deterministic 4-phase finite state machine:

- **Phase 1: Spec-First (Contracts Only)** — Define types, schemas, and empty function stubs (`raise NotImplementedError`). Validate via static type checker.
- **Phase 2: Atomic Red (Single Test)** — Write tests for strictly one function from Phase 1. Confirm test failure.
- **Phase 3: Atomic Green (Single Implementation)** — Implement minimal logic to pass the Phase 2 test.
- **Phase 4: Anti-Spiral & Context Pruning Gate** — If test fails after 2 targeted attempts, immediately revert broken changes via `git checkout -- <file>` and halt.

---

## 4. Layer-Wise Prompt Structure for KV-Cache Optimization

```markdown
# [1] SYSTEM & ARCHITECTURE (Fixed Prefix for KV-Cache)

- Stack: [e.g., Python 3.11 / FastAPI / Pydantic v2]
- Rules: Strict typing, pure functions, output Unified Diffs ONLY.

# [2] CONTRACTS & INTERFACES (Read-Only Context)

File: `src/schemas.py`
```

```markdown
# [3] ACTIVE FILE (Target for modification)

File: `src/service.py`

# [4] ATOMIC EXECUTION INSTRUCTION

- Phase: [SPEC | RED | GREEN]
- Target: `function_name`
```

---

## 5. NL-to-Spec Transpiler System Prompt

```markdown
# ROLE: NL-TO-SPEC TRANSPILER

Convert the user's natural language requirement into strict code specifications.
Rules:

1. Output ONLY a single code block. Zero text before or after.
2. Define data structures using Pydantic `BaseModel` or TypeScript `interface`.
3. Define function signatures with strict type hints.
4. Convert all business rules into concise English bullet points inside the function docstring.
5. Write ZERO implementation logic. End every function with `raise NotImplementedError`.
```
