"""FastAPI REST Endpoints for inspecting MCP Server URL, Scopes, and Registered Tools."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from src.config import settings
from src.core.base_tool import ToolMetadata
from src.core.registry import registry

router = APIRouter(prefix="/api/v1/mcp", tags=["MCP Discovery & Management"])


class MCPServerOverviewResponse(BaseModel):
    """Output response containing the MCP URL, server metadata, scopes, and full tool list."""

    server_name: str = Field(description="Name of the FastMCP server")
    version: str = Field(description="Application version")
    mcp_url: str = Field(description="Full Streamable HTTP URL for MCP clients to connect to")
    transport: str = Field(default="streamable-http", description="Active MCP transport protocol")
    total_tools: int = Field(description="Total number of registered MCP tools")
    scopes: dict[str, list[str]] = Field(description="Mapping of scope name to tool names")
    tools: list[ToolMetadata] = Field(description="Detailed list of all registered MCP tools")
    client_config_example: dict[str, Any] = Field(
        description="Ready-to-paste MCP client configuration snippet (Claude Desktop / Cursor / Antigravity)"
    )


class ToolExecuteRequest(BaseModel):
    """Payload for testing an MCP tool directly via FastAPI REST."""

    arguments: dict[str, Any] = Field(
        default_factory=dict,
        description="Key-value arguments passed to the tool's execute method.",
    )


def _resolve_mcp_url(request: Request) -> str:
    """Build the full MCP endpoint URL based on incoming request or configured base URL."""
    base = str(request.base_url).rstrip("/")
    if "testserver" in base:
        base = settings.PUBLIC_BASE_URL.rstrip("/")
    mount_path = settings.MCP_MOUNT_PATH if settings.MCP_MOUNT_PATH.startswith("/") else f"/{settings.MCP_MOUNT_PATH}"
    return f"{base}{mount_path}"


@router.get(
    "/info",
    response_model=MCPServerOverviewResponse,
    summary="Get MCP Server URL & Registered MCP Tools List",
)
async def get_mcp_info(
    request: Request,
    scope: str | None = Query(
        default=None,
        description="Optional scope filter (e.g. 'system', 'math', 'users')",
    ),
) -> MCPServerOverviewResponse:
    """Return the complete MCP connection URL, available scopes, and registered MCP tools."""
    mcp_url = _resolve_mcp_url(request)
    tools = registry.list_tools(scope=scope)
    return MCPServerOverviewResponse(
        server_name=settings.MCP_SERVER_NAME,
        version=settings.APP_VERSION,
        mcp_url=mcp_url,
        transport="streamable-http",
        total_tools=len(tools),
        scopes=registry.get_scopes_summary(),
        tools=tools,
        client_config_example={
            "mcpServers": {
                settings.MCP_SERVER_NAME: {
                    "url": mcp_url,
                    "transport": "streamable-http",
                }
            }
        },
    )


@router.get(
    "/tools",
    response_model=list[ToolMetadata],
    summary="List Registered MCP Tools (with optional scope filter)",
)
async def list_mcp_tools(
    scope: str | None = Query(
        default=None,
        description="Filter tools by scope (e.g., 'system', 'math', 'users')",
    ),
) -> list[ToolMetadata]:
    """Return the list of registered MCP tools and their JSON schemas."""
    return registry.list_tools(scope=scope)


@router.get(
    "/scopes",
    response_model=dict[str, list[str]],
    summary="List All Scopes and Their Tools",
)
async def list_mcp_scopes() -> dict[str, list[str]]:
    """Return all registered scopes and the tool names belonging to each scope."""
    return registry.get_scopes_summary()


@router.post(
    "/tools/{tool_name}/call",
    summary="Test-Invoke an MCP Tool via REST API",
)
async def call_mcp_tool_via_rest(
    tool_name: str,
    payload: ToolExecuteRequest,
) -> dict[str, Any]:
    """Convenience REST endpoint to test a tool's execution without an MCP client."""
    tool_meta = registry.get_tool(tool_name)
    if not tool_meta:
        raise HTTPException(
            status_code=404,
            detail=f"MCP tool '{tool_name}' not found. Available tools: {[t.name for t in registry.list_tools()]}",
        )
    try:
        output = await registry.execute_tool(tool_name, payload.arguments)
        return {
            "status": "success",
            "tool": tool_name,
            "scope": tool_meta.scope,
            "output": output,
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
