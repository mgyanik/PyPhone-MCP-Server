"""注册表契约：工具数量、别名、annotations 透传、参数校验。"""

import pytest

from src.registry import MCPFacade, ToolRegistry, load_tools, registry

EXPECTED_TOOLS = {
    "read_file_or_outline",
    "patch_file",
    "list_directory",
    "search_codebase",
    "move_or_delete_file",
    "inspect_file_meta",
    "find_process",
    "take_github",
}


def setup_module(module):
    load_tools()


def test_tool_count_and_names():
    names = {t.name for t in registry.list_tools()}
    assert names == EXPECTED_TOOLS


def test_aliases_resolve():
    assert registry.get_tool("read_file").name == "read_file_or_outline"
    assert registry.get_tool("edit__file").name == "patch_file"
    assert registry.get_tool("search_text").name == "search_codebase"
    assert registry.get_tool("list_dir").name == "list_directory"
    assert registry.get_tool("get_file_info").name == "inspect_file_meta"
    assert registry.get_tool("manage_file").name == "move_or_delete_file"


def test_annotations_passed_through():
    tool = registry.get_tool("find_process")
    assert tool.annotations.get("readOnlyHint") is True
    assert tool.to_mcp_format()["annotations"]["readOnlyHint"] is True


def test_descriptions_not_empty():
    for tool in registry.list_tools():
        assert len(tool.description.strip()) >= 20


def test_unknown_parameter_rejected():
    with pytest.raises(ValueError):
        registry.call_tool("inspect_file_meta", {"path": ".", "no_such_param": 1})


def test_duplicate_registration_rejected():
    reg = ToolRegistry()
    reg.register(lambda: None, name="dup")

    def another():
        return None

    with pytest.raises(ValueError):
        reg.register(another, name="dup")


def test_facade_decorator_registers():
    reg = ToolRegistry()
    facade = MCPFacade(reg)

    @facade.tool(name="demo")
    def demo():
        return {"ok": True}

    assert reg.get_tool("demo") is not None