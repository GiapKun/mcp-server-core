"""FastMCP Server Initialization & Tool Registration."""

from __future__ import annotations

import logging

from fastmcp import FastMCP

from src.config import settings
from src.core.registry import registry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("mcp_server_core.mcp")


def create_mcp_server() -> FastMCP:
    """Create and configure the FastMCP server instance and auto-discover all scoped tools."""
    mcp = FastMCP(
        name=settings.MCP_SERVER_NAME,
        instructions=(
            "Core extensible MCP Server. Tools are organized by logical scopes "
            "(e.g., 'system', 'math', 'users')."
        ),
    )

    registry.auto_discover_and_register(
        mcp=mcp,
        tools_package="src.tools",
        enabled_scopes=settings.ENABLED_SCOPES,
    )

    return mcp


mcp_server = create_mcp_server()

# Create the ASGI Streamable HTTP app at `settings.MCP_MOUNT_PATH` (default: `/mcp`)
mcp_asgi_app = mcp_server.http_app(
    path=settings.MCP_MOUNT_PATH,
    stateless_http=settings.MCP_STATELESS_HTTP,
)
