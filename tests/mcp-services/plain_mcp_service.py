"""Register local simulation tools directly on the standard MCP stdio transport."""

from __future__ import annotations

from typing import Any, Callable

from mcp_stdio import StdioMcpServer

Handler = Callable[[dict[str, Any]], dict[str, Any]]
_EMPTY_SCHEMA: dict[str, Any] = {"type": "object", "properties": {}, "additionalProperties": False}


def gated_handler(handler: Handler, gate: str) -> Handler:
    def call(arguments: dict[str, Any]) -> dict[str, Any]:
        if gate == "needs_approval":
            return {
                "executed": False,
                "gate": gate,
                "reason": "awaiting human approval",
            }
        result = handler(arguments)
        return {"executed": True, "gate": gate, **result}

    return call


def serve(
    name: str,
    schemas: dict[str, dict[str, Any]],
    handlers: dict[str, Handler],
    descriptions: dict[str, str],
    action_gates: dict[str, str] | None = None,
    event_schemas: dict[str, dict[str, str]] | None = None,
) -> None:
    action_gates = action_gates or {}
    tools = [
        {
            "name": tool_name,
            "description": (
                f"[gate={action_gates[tool_name]}] " if tool_name in action_gates else ""
            ) + descriptions[tool_name],
            "inputSchema": schema,
        }
        for tool_name, schema in schemas.items()
    ]

    def describe(_arguments: dict[str, Any]) -> dict[str, Any]:
        return {
            "service": name,
            "event_types": event_schemas or {},
            "read_tools": [tool for tool in schemas if tool not in action_gates],
            "act_tools": [
                {"name": tool, "gate": gate, "inputSchema": schemas[tool]}
                for tool, gate in action_gates.items()
            ],
        }

    tools.append({
        "name": "describe",
        "description": "Describe this MCP server and its registered tools.",
        "inputSchema": _EMPTY_SCHEMA,
    })
    handlers = {**handlers, "describe": describe}
    StdioMcpServer(name, tools, handlers).run()
