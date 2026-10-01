#!/usr/bin/env python3
"""Compatibility entrypoint for local simulation stdio MCP services."""

from __future__ import annotations

from typing import Any

from plain_mcp_service import Handler, serve


def run_service(
    jsonrpc_name: str,
    tool_schemas: dict[str, dict[str, Any]],
    handlers: dict[str, Handler],
    descriptions: dict[str, str],
    action_gates: dict[str, str] | None = None,
    event_schemas: dict[str, dict[str, str]] | None = None,
) -> None:
    serve(jsonrpc_name, tool_schemas, handlers, descriptions, action_gates, event_schemas)