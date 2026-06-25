"""Tests for the gradio-free MCP introspection used by the dashboard."""

import mcp_introspect as mi


def test_collect_returns_expected_shape():
    data = mi.collect_mcp_internals()
    for key in ("server", "tools", "resources", "prompts", "runtime", "errors"):
        assert key in data, key
    assert isinstance(data["tools"], list)


def test_server_identity_and_version():
    data = mi.collect_mcp_internals()
    # Skip gracefully if the MCP package isn't importable in this environment.
    if not data["server"]:
        assert data["errors"]
        return
    assert data["server"]["name"] == "ai-rule-learning"
    # A3 fix: version must be the package version, never the SDK's.
    assert data["server"]["version"] == data["server"]["package_version"]


def test_tools_enumerated_with_schema():
    data = mi.collect_mcp_internals()
    if not data["tools"]:
        return
    t = data["tools"][0]
    for key in ("name", "description", "input_schema", "status"):
        assert key in t
    # every tool carries a (possibly empty) JSON-serialisable input schema
    assert isinstance(t["input_schema"], dict)


def test_tool_rows_filtering():
    data = mi.collect_mcp_internals()
    all_rows = mi.tool_rows(data)
    if not all_rows:
        return
    # filter by a substring of a known tool name
    name = data["tools"][0]["name"]
    filtered = mi.tool_rows(data, query=name)
    assert filtered and all(name in r[0] or name.lower() in r[1].lower() for r in filtered)
    # a nonsense query yields nothing
    assert mi.tool_rows(data, query="zzz_no_such_tool_zzz") == []


def test_server_markdown_renders():
    data = mi.collect_mcp_internals()
    md = mi.server_markdown(data)
    assert isinstance(md, str) and md.strip()


def test_empty_note():
    assert mi.empty_note("resources", 0)
    assert mi.empty_note("resources", 3) == ""


def test_runtime_present():
    data = mi.collect_mcp_internals()
    rt = data["runtime"]
    assert "transports" in rt and "python" in rt
