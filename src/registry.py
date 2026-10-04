"""MCP 工具注册表与装饰器实现。"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Callable


def _infer_json_schema(annotation: Any) -> dict[str, Any]:
    import typing
    import types
    if isinstance(annotation, str):
        if "list[" in annotation or annotation == "list":
            return {"type": "array", "items": {"type": "string"}}
        if "dict[" in annotation or annotation == "dict":
            return {"type": "object"}
        if "bool" in annotation:
            return {"type": "boolean"}
        if "int" in annotation or "float" in annotation:
            return {"type": "number"}
        return {"type": "string"}

    origin = typing.get_origin(annotation)
    if origin is typing.Union or (hasattr(types, "UnionType") and origin is types.UnionType):
        # 联合类型：取非 None 的分支
        args = [a for a in typing.get_args(annotation) if a is not type(None)]
        if args:
            return _infer_json_schema(args[0])
        return {"type": "string"}
    if origin is list or annotation is list:
        schema = {"type": "array"}
        args = typing.get_args(annotation)
        if args:
            schema["items"] = _infer_json_schema(args[0])
        else:
            schema["items"] = {"type": "string"}
        return schema
    if origin is dict or annotation is dict:
        return {"type": "object"}
    if annotation is bool:
        return {"type": "boolean"}
    if annotation in (int, float):
        return {"type": "number"}
    if annotation is str:
        return {"type": "string"}
    return {"type": "string"}
@dataclass
class ToolDefinition:
    name: str
    func: Callable[..., Any]
    description: str
    annotations: dict[str, Any] = field(default_factory=dict)
    parameters: dict[str, Any] = field(default_factory=dict)

    def to_mcp_format(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.parameters,
        }


class ToolRegistry:
    """全局 MCP 工具注册中心。"""

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}
        self._aliases: dict[str, str] = {}

    def register_alias(self, alias_name: str, target_tool_name: str) -> None:
        """注册工具别名，保证客户端无论调用主名或兼容别名均可正常解析。"""
        self._aliases[alias_name] = target_tool_name

    def register(
        self,
        func: Callable[..., Any],
        name: str | None = None,
        description: str | None = None,
        annotations: dict[str, Any] | None = None,
    ) -> Callable[..., Any]:
        tool_name = name or func.__name__
        desc = description or inspect.getdoc(func) or ""
        ann = annotations or getattr(func, "__mcp_annotations__", {})

        # 生成简单的 JSON Schema 参数描述
        sig = inspect.signature(func)
        try:
            import typing
            type_hints = typing.get_type_hints(func)
        except Exception:
            type_hints = {}

        properties = {}
        required = []
        for param_name, param in sig.parameters.items():
            if param_name in ("self", "cls"):
                continue
            param_ann = type_hints.get(param_name, param.annotation)
            param_schema = _infer_json_schema(param_ann)

            properties[param_name] = param_schema
            if param.default == inspect.Parameter.empty:
                required.append(param_name)

        schema = {
            "type": "object",
            "properties": properties,
            "required": required,
        }

        definition = ToolDefinition(
            name=tool_name,
            func=func,
            description=desc.strip(),
            annotations=ann,
            parameters=schema,
        )

        self._tools[tool_name] = definition
        func.__mcp_tool__ = True
        func.__mcp_annotations__ = ann
        func.__mcp_name__ = tool_name
        return func

    def get_tool(self, name: str) -> ToolDefinition | None:
        if name in self._tools:
            return self._tools[name]
        target = self._aliases.get(name)
        if target:
            return self._tools.get(target)
        return None

    def list_tools(self) -> list[ToolDefinition]:
        return list(self._tools.values())

    def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        tool_def = self.get_tool(name)
        if not tool_def:
            raise ValueError(f"未找到工具: {name}")
            
        # 兼容处理：过滤掉客户端注入的多余参数（例如特殊平台框架强加的 "_" dummy参数）
        sig = inspect.signature(tool_def.func)
        has_kwargs = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
        
        if not has_kwargs:
            valid_keys = set(sig.parameters.keys())
            arguments = {k: v for k, v in arguments.items() if k in valid_keys}
            
        return tool_def.func(**arguments)


class MCPFacade:
    """支持 @mcp.tool(annotations=...) 语法。"""

    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry

    def tool(
        self,
        name: str | None = None,
        description: str | None = None,
        annotations: dict[str, Any] | None = None,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            return self.registry.register(
                func, name=name, description=description, annotations=annotations
            )

        return decorator


registry = ToolRegistry()
mcp = MCPFacade(registry)


def load_tools() -> None:
    """Pre-load all tools so they register themselves."""
    import src.tools.fetch_url  # noqa: F401
    import src.tools.find_process  # noqa: F401
    import src.tools.list_dir  # noqa: F401
    import src.tools.manage_file  # noqa: F401
    import src.tools.read_file  # noqa: F401
    import src.tools.search_text  # noqa: F401
    import src.tools.get_file_info  # noqa: F401
    import src.tools.edit_file  # noqa: F401
    import src.tools.take_github  # noqa: F401
    import src.tools.request_tool  # noqa: F401
    registry.register_alias("edit__file", "patch_file")
    registry.register_alias("read_file", "read_file_or_outline")
    registry.register_alias("read_file_lines", "read_file_or_outline")
    registry.register_alias("search_text", "search_codebase")
    registry.register_alias("list_dir", "list_directory")
    registry.register_alias("MCP__list_dir", "list_directory")
    registry.register_alias("get_file_info", "inspect_file_meta")
    registry.register_alias("manage_file", "move_or_delete_file")