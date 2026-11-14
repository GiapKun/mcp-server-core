"""Main FastAPI Application integrating FastMCP ASGI App and Lifespan.

Follows the production pattern from `redhat-data-and-ai/template-mcp-server` and
official `jlowin/fastmcp` ASGI mounting docs:
- Combine FastAPI lifespan with `mcp_asgi_app.lifespan(app)` so FastMCP's session manager
  initializes properly.
- Register FastAPI REST routes (`/health`, `/api/v1/mcp/info`, `/api/v1/mcp/tools`, etc.).
- Mount `mcp_asgi_app` at `/` so `/mcp` serves the native MCP Streamable HTTP protocol directly.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import router as mcp_discovery_router
from src.config import settings
from src.mcp_server import mcp_asgi_app


@asynccontextmanager
async def combined_lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Wire FastAPI lifespan with FastMCP's HTTP session manager lifespan."""
    async with mcp_asgi_app.lifespan(app):
        yield


def create_app() -> FastAPI:
    """Create the unified FastAPI + FastMCP ASGI application."""
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "Unified **FastAPI + FastMCP** server architecture with scope-based tool inheritance "
            "(`BaseTool` and `BaseScopedToolset`) and automatic tool discovery."
        ),
        lifespan=combined_lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["System"])
    async def health_check() -> dict[str, str]:
        """Health check endpoint."""
        return {
            "status": "healthy",
            "service": settings.MCP_SERVER_NAME,
            "version": settings.APP_VERSION,
            "mcp_endpoint": f"{settings.PUBLIC_BASE_URL.rstrip('/')}{settings.MCP_MOUNT_PATH}",
        }

    # Include REST API routes for inspecting MCP URL, scopes, and tools
    app.include_router(mcp_discovery_router)

    # Mount the FastMCP Streamable HTTP ASGI application (exposes `/mcp`)
    app.mount("/", mcp_asgi_app)

    return app


app = create_app()
