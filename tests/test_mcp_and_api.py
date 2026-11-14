"""End-to-end tests for FastAPI REST endpoints, FastMCP Native Protocol, and Scope Inheritance."""

from __future__ import annotations

from typing import Any

import pytest
from fastmcp import Client, FastMCP
from httpx import ASGITransport, AsyncClient
from pydantic import Field

from src.api.app import app
from src.core.base_tool import BaseScopedToolset, BaseTool
from src.core.registry import ToolRegistry
from src.mcp_server import mcp_server


@pytest.mark.asyncio
async def test_fastapi_mcp_info_and_tool_list() -> None:
    """Verify `/api/v1/mcp/info` returns MCP URL, scopes, and full list of registered tools."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://localhost:8000") as client:
        resp = await client.get("/api/v1/mcp/info")
        assert resp.status_code == 200
        data = resp.json()

        assert data["mcp_url"] == "http://localhost:8000/mcp"
        assert data["total_tools"] == 7
        assert set(data["scopes"].keys()) == {"math", "system", "users"}

        tool_names = [t["name"] for t in data["tools"]]
        assert "system_ping" in tool_names
        assert "system_get_runtime_info" in tool_names
        assert "math_calculate" in tool_names
        assert "users_list_users" in tool_names
        assert "users_get_user" in tool_names
        assert "users_create_user" in tool_names
        assert "users_delete_user" in tool_names


@pytest.mark.asyncio
async def test_fastapi_scope_filtering_and_rest_call() -> None:
    """Verify filtering tools by scope (`?scope=users`) and calling a tool via REST."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://localhost:8000") as client:
        # Filter by 'users' scope
        resp = await client.get("/api/v1/mcp/tools", params={"scope": "users"})
        assert resp.status_code == 200
        user_tools = resp.json()
        assert len(user_tools) == 4
        assert all(t["scope"] == "users" for t in user_tools)

        # Check annotations on users_delete_user vs users_list_users
        by_name = {t["name"]: t for t in user_tools}
        assert by_name["users_list_users"]["read_only"] is True
        assert by_name["users_list_users"]["destructive"] is False
        assert by_name["users_delete_user"]["read_only"] is False
        assert by_name["users_delete_user"]["destructive"] is True

        # Test invoking `math_calculate` via REST
        call_resp = await client.post(
            "/api/v1/mcp/tools/math_calculate/call",
            json={"arguments": {"a": 12, "b": 8, "operation": "multiply"}},
        )
        assert call_resp.status_code == 200
        call_data = call_resp.json()
        assert call_data["output"]["result"] == 96.0


@pytest.mark.asyncio
async def test_fastmcp_native_client_protocol() -> None:
    """Verify native MCP Client can list tools and call tools on `mcp_server`."""
    async with Client(mcp_server) as mcp_client:
        tools = await mcp_client.list_tools()
        names = {t.name for t in tools}
        assert {
            "system_ping",
            "system_get_runtime_info",
            "math_calculate",
            "users_list_users",
            "users_get_user",
            "users_create_user",
            "users_delete_user",
        }.issubset(names)

        # Call `system_ping` via MCP protocol
        ping_res = await mcp_client.call_tool("system_ping", {"message": "xin chao"})
        assert "xin chao" in str(ping_res)

        # Call `users_list_users` via MCP protocol
        users_res = await mcp_client.call_tool("users_list_users", {"role": "admin"})
        assert "Alice Nguyen" in str(users_res)


@pytest.mark.asyncio
async def test_custom_scope_inheritance_extensibility() -> None:
    """Verify a developer can easily create a new scope by inheriting BaseTool or BaseScopedToolset."""

    class OrderCheckTool(BaseTool):
        name = "orders_check_status"
        scope = "orders"
        description = "Check order status by order_id."

        async def execute(self, order_id: str = Field(description="Order ID")) -> dict[str, Any]:
            return {"order_id": order_id, "status": "shipped"}

    class InventoryToolset(BaseScopedToolset):
        scope = "inventory"

        async def get_stock(self, sku: str) -> dict[str, Any]:
            """Get stock count for SKU."""
            return {"sku": sku, "qty": 42}

    custom_mcp = FastMCP("custom-test")
    custom_registry = ToolRegistry()

    OrderCheckTool().register(custom_mcp, custom_registry)
    InventoryToolset().register_tools(custom_mcp, custom_registry)

    assert set(custom_registry.get_scopes_summary().keys()) == {"orders", "inventory"}

    async with Client(custom_mcp) as client:
        tools = await client.list_tools()
        assert {t.name for t in tools} == {"orders_check_status", "inventory_get_stock"}
        res = await client.call_tool("inventory_get_stock", {"sku": "SKU-999"})
        assert "42" in str(res)
