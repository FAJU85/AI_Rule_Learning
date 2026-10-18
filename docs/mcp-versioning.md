# MCP Versioning & Compatibility Guide

**Package**: `ai-rule-learning-mcp`  
**Reference Document**: ARL-REM-2026-006  
**Current Supported MCP Version**: `mcp>=1.0.0,<2.0.0`

---

## 1. Supported MCP Versions Matrix

| Package Version | MCP Dependency Range               | Supported Python | Status                                        |
| :-------------- | :--------------------------------- | :--------------- | :-------------------------------------------- |
| **0.2.1**       | `mcp>=1.0.0,<2.0.0`                | `>=3.10`         | **Current Stable**                            |
| **0.2.0**       | `mcp>=1.0.0` _(unbounded ceiling)_ | `>=3.10`         | Deprecated (P0 issue if resolving to mcp 2.x) |
| **0.1.1**       | `mcp>=1.0.0`                       | `>=3.10`         | Legacy release                                |

---

## 2. Root Cause of MCP 2.x Incompatibility

Between `mcp 1.x` and `mcp 2.x`, the Model Context Protocol Python SDK restructured its core server class (`mcp.server.Server`) and decorators.

Specifically:

- In `mcp 1.x`, tool registration uses decorator methods on the Server instance (e.g., `@app.list_tools()` and `@app.call_tool()`).
- In `mcp 2.x`, the high-level `Server` class removed or refactored these decorator entry points into a revised request-handler hierarchy.

When a package declared `mcp>=1.0.0` without an upper bound, `pip` on clean environments resolved the latest available SDK release (`mcp==2.3.0`), leading to:

```text
AttributeError: 'Server' object has no attribute 'list_tools'
  File "ai_rule_learning_mcp/server.py", line 67, in <module>
    @app.list_tools()
```

---

## 3. Resolution in v0.2.1

1. **Strict Dependency Ceiling**:
   `mcp/pyproject.toml` strictly bounds the SDK dependency:

   ```toml
   dependencies = [
       "mcp>=1.0.0,<2.0.0",
   ]
   ```

2. **Deterministic Installation**:
   All fresh installs with `pip install ai-rule-learning-mcp` or virtual environments resolve to tested 1.x releases (e.g., `1.30.0`).
3. **Automated Regression Guard**:
   `tests/test_default_install.py` validates that unconstrained resolution resolves to `1.x` and that server startup succeeds without runtime exceptions.

---

## 4. MCP 2.x Migration Plan

A future release (`0.3.0` or `1.0.0`) will adopt the MCP 2.x protocol structure:

- **Dual Support Layer**: Implement runtime adapter checking `mcp.__version__` to support both 1.x and 2.x handler protocols.
- **Lazy Registration**: Avoid module-load decorator execution to allow descriptive error messaging if an incompatible runtime is detected.
- **Deprecation Grace Period**: Maintain backward compatibility with existing Claude Desktop, Cursor, Windsurf, and Copilot client bridges.
