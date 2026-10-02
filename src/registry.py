"""MCP 工具注册表与装饰器实现。"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Callable


def _infer_json_type(annotation: Any) -> str:
    import typing
    import types
    if isinstance(annotation, str):
        if "list[" in annotation or annotation == "list":
            return "array"
        if "dict[" in annotation or annotation == "dict":
            return "object"
        if "bool" in annotation:
            return "boolean"
        if "int" in annotation or "float" in annotation:
            return "number"
        return "string"

    origin = typing.get_origin(annotation)
    if origin is typing.Union or (hasattr(types, "UnionType") and origin is types.UnionType):
        # 联合类型：取非 None 的分支
        args = [a for a in typing.get_args(annotation) if a is not type(None)]
        if args:
            return _infer_json_type(args[0])
        return "string"
    if origin is list or annotation is list:
        return "array"
    if origin is dict or annotation is dict:
        return "object"
    if annotation is bool:
        return "boolean"
    if annotation in (int, float):
        return "number"
    if annotation is str:
        return "string"
    return "string"

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
            "annotations": self.annotations,
            "inputSchema": self.parameters,
        }


class ToolRegistry:
    """全局 MCP 工具注册中心。"""

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

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
            param_type = _infer_json_type(param_ann)

            properties[param_name] = {"type": param_type}
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
        return self._tools.get(name)

    def list_tools(self) -> list[ToolDefinition]:
        return list(self._tools.values())

    def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        tool_def = self.get_tool(name)
        if not tool_def:
            raise ValueError(f"未找到工具: {name}")
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
    """导入并注册所有工具（批量工具、任务工具、移植的 shell 工具）。"""
    # 导入工具模块以触发装饰器注册
    import src.tools.get_file  # noqa: F401
    import src.tools.list_dir  # noqa: F401
    import src.tools.search_text  # noqa: F401
    import src.tools.start_task  # noqa: F401
    import src.tools.get_task_status  # noqa: F401
    import src.tools.list_tasks  # noqa: F401
    import src.tools.cancel_task  # noqa: F401
