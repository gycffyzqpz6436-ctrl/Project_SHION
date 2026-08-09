from __future__ import annotations

from app.tools.interface import ShionTool, ToolResult


class DisabledTool:
    enabled = False

    def __init__(self, name: str) -> None:
        self.name = name

    def invoke(self, request: dict) -> ToolResult:
        return ToolResult(False, error=f"tool unavailable: {self.name}")


class ToolRegistry:
    """Default-deny boundary between model decisions and privileged capabilities."""

    def __init__(self) -> None:
        self._tools: dict[str, ShionTool] = {}

    def register(self, tool: ShionTool) -> None:
        self._tools[tool.name] = tool

    def invoke(self, name: str, request: dict) -> ToolResult:
        tool = self._tools.get(name)
        if tool is None or not tool.enabled:
            return ToolResult(False, error=f"tool unavailable: {name}")
        return tool.invoke(request)

    def status(self) -> dict[str, bool]:
        return {name: tool.enabled for name, tool in self._tools.items()}


def default_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()
    for name in ("vision", "image_generation", "web", "voice", "local"):
        registry.register(DisabledTool(name))
    return registry
