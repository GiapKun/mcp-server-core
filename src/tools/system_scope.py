"""Example Scope 1: `system` — Using `BaseTool` (Single-Tool Inheritance Pattern)."""

from __future__ import annotations

import platform
from datetime import datetime, timezone
from typing import Any

from pydantic import Field

from src.config import settings
from src.core.base_tool import BaseTool


class SystemPingTool(BaseTool):
    """Example tool inheriting from `BaseTool` under the `system` scope."""

    name = "system_ping"
    scope = "system"
    description = "Ping the MCP server and verify connectivity with an optional echo message."
    tags = {"diagnostics", "health"}
    read_only = True

    async def execute(
        self,
        message: str = Field(
            default="hello",
            description="Optional message to echo back from the MCP server.",
        ),
    ) -> dict[str, Any]:
        return {
            "status": "ok",
            "scope": self.scope,
            "echo": message,
            "server_name": settings.MCP_SERVER_NAME,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        }


class SystemRuntimeInfoTool(BaseTool):
    """Retrieve environment and Python runtime diagnostics for the `system` scope."""

    name = "system_get_runtime_info"
    scope = "system"
    description = "Get system platform, Python runtime version, and active MCP scopes."
    tags = {"diagnostics", "runtime"}
    read_only = True

    async def execute(self) -> dict[str, Any]:
        return {
            "app_name": settings.APP_NAME,
            "app_version": settings.APP_VERSION,
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "enabled_scopes": settings.ENABLED_SCOPES,
        }
