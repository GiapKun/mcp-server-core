"""Auto-Discovery Tool Registry for FastMCP + FastAPI.

Automatically imports all modules inside `src.tools`, finds concrete subclasses of
`BaseTool` and `BaseScopedToolset`, filters by enabled scopes, and registers them
with the FastMCP server.
"""

from __future__ import annotations

import importlib
import inspect
import logging
import pkgutil
from typing import TYPE_CHECKING, Any, Callable

from src.core.base_tool import BaseScopedToolset, BaseTool, ToolMetadata

if TYPE_CHECKING:
    from fastmcp import FastMCP

logger = logging.getLogger("mcp_server_core.registry")


def _iter_all_subclasses(base_cls: type) -> list[type]:
    """Recursively collect all subclasses of `base_cls`."""
    found: list[type] = []
    for sub in base_cls.__subclasses__():
        found.append(sub)
        found.extend(_iter_all_subclasses(sub))
    return found


class ToolRegistry:
    """Central registry tracking all discovered MCP tools, their scopes, and schemas."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolMetadata] = {}
        self._executables: dict[str, Callable[..., Any]] = {}
        self._loaded_packages: set[str] = set()

    def record_tool(self, metadata: ToolMetadata, executable: Callable[..., Any]) -> None:
        """Record a tool's metadata and callable in the registry."""
        self._tools[metadata.name] = metadata
        self._executables[metadata.name] = executable

    def list_tools(self, scope: str | None = None) -> list[ToolMetadata]:
        """Return all registered tools, optionally filtered by `scope`."""
        tools = list(self._tools.values())
        if scope:
            tools = [t for t in tools if t.scope.lower() == scope.lower()]
        return sorted(tools, key=lambda t: (t.scope, t.name))

    def get_tool(self, name: str) -> ToolMetadata | None:
        """Retrieve metadata for a specific tool by name."""
        return self._tools.get(name)

    def get_scopes_summary(self) -> dict[str, list[str]]:
        """Return a mapping of `scope -> [tool_name, ...]`."""
        summary: dict[str, list[str]] = {}
        for tool in self.list_tools():
            summary.setdefault(tool.scope, []).append(tool.name)
        return summary

    async def execute_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        """Execute a registered tool directly by name (used by REST debug/test endpoint)."""
        if name not in self._executables:
            raise KeyError(f"Tool '{name}' is not registered.")
        fn = self._executables[name]
        return await fn(**arguments)

    def auto_discover_and_register(
        self,
        mcp: FastMCP,
        tools_package: str = "src.tools",
        enabled_scopes: list[str] | None = None,
    ) -> int:
        """Dynamically import all modules in `tools_package` and register all concrete
        `BaseTool` and `BaseScopedToolset` classes matching `enabled_scopes`.
        """
        allow_all = not enabled_scopes or "*" in enabled_scopes
        allowed = {s.lower() for s in (enabled_scopes or [])}

        # 1. Import the package and all submodules
        pkg = importlib.import_module(tools_package)
        if hasattr(pkg, "__path__"):
            for _, module_name, _ in pkgutil.walk_packages(pkg.__path__, prefix=f"{tools_package}."):
                importlib.import_module(module_name)
                logger.debug(f"Imported tool module: {module_name}")

        total_registered = 0

        # 2. Discover concrete BaseTool subclasses
        for cls in _iter_all_subclasses(BaseTool):
            if inspect.isabstract(cls) or not cls.__module__.startswith(tools_package):
                continue
            instance: BaseTool = cls()
            if not allow_all and instance.scope.lower() not in allowed:
                logger.info(f"Skipping BaseTool '{cls.__name__}' (scope '{instance.scope}' disabled)")
                continue
            instance.register(mcp, tool_registry=self)
            total_registered += 1

        # 3. Discover concrete BaseScopedToolset subclasses
        for cls in _iter_all_subclasses(BaseScopedToolset):
            if inspect.isabstract(cls) or not cls.__module__.startswith(tools_package):
                continue
            toolset: BaseScopedToolset = cls()
            if not allow_all and toolset.scope.lower() not in allowed:
                logger.info(
                    f"Skipping BaseScopedToolset '{cls.__name__}' (scope '{toolset.scope}' disabled)"
                )
                continue
            total_registered += toolset.register_tools(mcp, tool_registry=self)

        self._loaded_packages.add(tools_package)
        logger.info(
            f"Auto-discovery complete: registered {total_registered} MCP tools across scopes {list(self.get_scopes_summary().keys())}"
        )
        return total_registered


# Global singleton registry
registry = ToolRegistry()
