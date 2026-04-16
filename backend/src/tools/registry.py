from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


class ToolRegistryError(RuntimeError):
    pass


ToolHandler = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class RegisteredTool:
    name: str
    description: str
    read_only: bool
    handler: ToolHandler


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, RegisteredTool] = {}

    def register_tool(
        self,
        *,
        name: str,
        description: str,
        read_only: bool,
        handler: ToolHandler,
    ) -> None:
        if not name.strip():
            raise ValueError("tool name must be non-empty")
        if name in self._tools:
            raise ValueError(f"tool {name} is already registered")

        self._tools[name] = RegisteredTool(
            name=name,
            description=description,
            read_only=read_only,
            handler=handler,
        )

    def list_tools(self) -> list[str]:
        return sorted(self._tools.keys())

    def describe_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "read_only": tool.read_only,
            }
            for tool in sorted(self._tools.values(), key=lambda item: item.name)
        ]

    def execute_tool(self, name: str, params: dict[str, Any]) -> dict[str, Any]:
        tool = self._tools.get(name)
        if tool is None:
            raise ToolRegistryError(f"tool {name} is not registered")

        try:
            result = tool.handler(params)
        except ToolRegistryError:
            raise
        except Exception as exc:  # pragma: no cover - defensive fallback
            raise ToolRegistryError(f"tool {name} failed: {exc}") from exc

        if not isinstance(result, dict):
            raise ToolRegistryError(f"tool {name} returned an invalid result payload")

        status = str(result.get("status", "executed"))
        output = str(result.get("output", "Tool executed."))
        payload: dict[str, Any] = {
            "tool": name,
            "status": status,
            "output": output,
        }

        for key, value in result.items():
            if key in payload:
                continue
            payload[key] = value

        return payload
