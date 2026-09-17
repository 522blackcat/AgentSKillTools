from app.tools.registry import execute_tool, list_tools


def test_generated_tool_registry_has_stub_executor() -> None:
    tools = list_tools()
    assert tools
    result = execute_tool(tools[0]["name"], {"tenant_id": "tenant-tools", "query": "sample"})
    assert result["status"] == "stubbed"
    assert "review_required" in result
