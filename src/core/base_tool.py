"""Core Base Classes for MCP Tools.

Synthesizes architectural best practices from top GitHub repositories:
1. `prowler-cloud/prowler`:
   - Abstract `BaseTool` / `BaseScopedToolset` with automatic public async method discovery
   - Automatic `ToolAnnotations` (`readOnlyHint`, `destructiveHint`) based on naming conventions
   - Shared logger and dependency injection properties
2. `koreainvestment/open-trading-api` & `ragieai/dynamic-fastmcp`:
   - Single-purpose `BaseTool` with abstract `execute()` contract, scope tagging, and unified execution hooks
"""

from __future__ import annotations

import functools
import inspect
import logging
import time
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Callable

from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from src.core.registry import ToolRegistry

logger = logging.getLogger("mcp_server_core.tools")

READ_ONLY_PREFIXES = ("get_", "list_", "search_", "fetch_", "check_", "read_", "calculate_", "ping")
DESTRUCTIVE_PREFIXES = ("delete_", "remove_", "drop_", "destroy_", "purge_")


class ToolMetadata(BaseModel):
    """Structured metadata representing a registered MCP tool."""

    name: str = Field(description="Unique MCP tool name exposed to LLM clients")
    scope: str = Field(description="Logical domain/scope of the tool (e.g., 'system', 'math', 'users')")
    description: str = Field(description="Detailed description for LLM tool selection")
    tags: list[str] = Field(default_factory=list, description="Tags associated with the tool")
    read_only: bool = Field(default=True, description="Whether the tool only reads state")
    destructive: bool = Field(default=False, description="Whether the tool performs destructive mutations")
    source_class: str = Field(description="Python class that defines this tool")
    parameters_schema: dict[str, Any] = Field(
        default_factory=dict,
        description="JSON Schema of tool input arguments",
    )


def _wrap_tool_callable(
    fn: Callable[..., Any],
    tool_name: str,
    scope: str,
    tool_logger: logging.Logger,
) -> Callable[..., Any]:
    """Wrap a bound async method with structured logging, execution timing, and error handling
    while preserving its exact signature and type annotations for FastMCP schema generation.
    """
    sig = inspect.signature(fn)

    @functools.wraps(fn)
    async def _wrapped(*args: Any, **kwargs: Any) -> Any:
        start_time = time.perf_counter()
        tool_logger.info(f"[{scope}:{tool_name}] Executing tool with kwargs={list(kwargs.keys())}")
        try:
            result = await fn(*args, **kwargs)
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            tool_logger.info(f"[{scope}:{tool_name}] Completed in {elapsed_ms}ms")
            return result
        except Exception as exc:
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            tool_logger.error(f"[{scope}:{tool_name}] Failed after {elapsed_ms}ms: {exc}")
            raise

    _wrapped.__signature__ = sig  # type: ignore[attr-defined]
    return _wrapped


class BaseTool(ABC):
    """Pattern 1: Single-Tool Inheritance Class (Core Atomic Tool).

    Inherit from `BaseTool` when you want a dedicated class per complex tool with its own
    state, dependencies, scope, and `execute(...)` method.

    Example:
        class AddNumbersTool(BaseTool):
            name = "math_add"
            scope = "math"
            description = "Add two numbers together."

            async def execute(self, a: float, b: float) -> dict[str, Any]:
                return {"result": a + b}
    """

    name: str = ""
    scope: str = "core"
    description: str = ""
    tags: set[str] = set()
    read_only: bool | None = None
    destructive: bool | None = None

    def __init__(self) -> None:
        self._logger = logging.getLogger(f"mcp_server_core.tools.{self.scope}.{self.get_name()}")

    @property
    def logger(self) -> logging.Logger:
        """Shared structured logger for the tool instance."""
        return self._logger

    def get_name(self) -> str:
        """Return the tool name, defaulting to snake_case class name if not explicitly set."""
        if self.name:
            return self.name
        return self.__class__.__name__.lower()

    def get_description(self) -> str:
        """Return the tool description, falling back to `execute` docstring or class docstring."""
        if self.description:
            return self.description.strip()
        exec_doc = inspect.getdoc(self.execute)
        if exec_doc and exec_doc != inspect.getdoc(BaseTool.execute):
            return exec_doc.strip()
        return (inspect.getdoc(self) or f"MCP tool {self.get_name()} in scope '{self.scope}'").strip()

    def get_annotations(self) -> ToolAnnotations:
        """Build MCP ToolAnnotations for safety hints (readOnlyHint & destructiveHint)."""
        tool_name = self.get_name()
        is_read_only = (
            self.read_only
            if self.read_only is not None
            else tool_name.startswith(READ_ONLY_PREFIXES) or f"_{tool_name}".endswith(READ_ONLY_PREFIXES)
        )
        is_destructive = (
            self.destructive
            if self.destructive is not None
            else (False if is_read_only else tool_name.startswith(DESTRUCTIVE_PREFIXES))
        )
        return ToolAnnotations(
            title=f"[{self.scope.upper()}] {tool_name}",
            read_only_hint=is_read_only,
            destructive_hint=is_destructive,
        )

    @abstractmethod
    async def execute(self, *args: Any, **kwargs: Any) -> Any:
        """Execute the core tool logic. Subclasses MUST override this with typed parameters."""
        raise NotImplementedError

    def register(self, mcp: FastMCP, tool_registry: ToolRegistry | None = None) -> None:
        """Register this single tool with FastMCP and the internal ToolRegistry."""
        tool_name = self.get_name()
        tool_desc = self.get_description()
        annotations = self.get_annotations()
        tags = set(self.tags) | {self.scope}

        wrapped_fn = _wrap_tool_callable(
            fn=self.execute,
            tool_name=tool_name,
            scope=self.scope,
            tool_logger=self.logger,
        )

        registered_tool = mcp.tool(
            wrapped_fn,
            name=tool_name,
            description=tool_desc,
            tags=tags,
            annotations=annotations,
        )

        # Extract JSON schema from FastMCP's registered tool object if available
        params_schema: dict[str, Any] = getattr(registered_tool, "parameters", {}) or {}

        if tool_registry is not None:
            tool_registry.record_tool(
                ToolMetadata(
                    name=tool_name,
                    scope=self.scope,
                    description=tool_desc,
                    tags=sorted(tags),
                    read_only=bool(annotations.read_only_hint),
                    destructive=bool(annotations.destructive_hint),
                    source_class=f"{self.__class__.__module__}.{self.__class__.__name__}",
                    parameters_schema=params_schema,
                ),
                executable=wrapped_fn,
            )


class BaseScopedToolset(ABC):
    """Pattern 2: Multi-Tool Domain/Scope Class (Inspired by `prowler-cloud/prowler`).

    Inherit from `BaseScopedToolset` when you want to group multiple related tools
    under a single scope (e.g., `scope = "users"`). Every public `async def` method on the
    subclass is automatically registered as an MCP tool!

    Example:
        class UserScopedToolset(BaseScopedToolset):
            scope = "users"
            prefix_with_scope = True  # `list_users` -> `users_list_users`

            async def list_users(self, limit: int = 10) -> dict[str, Any]:
                '''List active users.'''
                ...
    """

    scope: str = "default"
    prefix_with_scope: bool = True
    tags: set[str] = set()
    read_only_tools: frozenset[str] = frozenset()
    destructive_tools: frozenset[str] = frozenset()

    def __init__(self) -> None:
        self._logger = logging.getLogger(f"mcp_server_core.toolset.{self.scope}")

    @property
    def logger(self) -> logging.Logger:
        """Shared structured logger for the scoped toolset."""
        return self._logger

    def _build_tool_name(self, method_name: str) -> str:
        if self.prefix_with_scope and not method_name.startswith(f"{self.scope}_"):
            return f"{self.scope}_{method_name}"
        return method_name

    def _annotations_for(self, method_name: str, full_tool_name: str) -> ToolAnnotations:
        """Infer MCP safety annotations from method name or explicit frozensets."""
        if method_name.startswith(READ_ONLY_PREFIXES) or method_name in self.read_only_tools:
            return ToolAnnotations(
                title=f"[{self.scope.upper()}] {full_tool_name}",
                read_only_hint=True,
                destructive_hint=False,
            )
        is_destructive = (
            method_name.startswith(DESTRUCTIVE_PREFIXES) or method_name in self.destructive_tools
        )
        return ToolAnnotations(
            title=f"[{self.scope.upper()}] {full_tool_name}",
            read_only_hint=False,
            destructive_hint=is_destructive,
        )

    def register_tools(self, mcp: FastMCP, tool_registry: ToolRegistry | None = None) -> int:
        """Automatically inspect and register all public async methods as MCP tools."""
        registered_count = 0
        reserved_names = {"register_tools", "logger"}

        for method_name, method in inspect.getmembers(self, predicate=inspect.ismethod):
            if method_name.startswith("_") or method_name in reserved_names:
                continue
            if not inspect.iscoroutinefunction(method):
                continue

            full_tool_name = self._build_tool_name(method_name)
            description = (inspect.getdoc(method) or f"Tool {full_tool_name} in scope '{self.scope}'").strip()
            annotations = self._annotations_for(method_name, full_tool_name)
            tags = set(self.tags) | {self.scope}

            wrapped_fn = _wrap_tool_callable(
                fn=method,
                tool_name=full_tool_name,
                scope=self.scope,
                tool_logger=self.logger,
            )

            registered_tool = mcp.tool(
                wrapped_fn,
                name=full_tool_name,
                description=description,
                tags=tags,
                annotations=annotations,
            )

            params_schema: dict[str, Any] = getattr(registered_tool, "parameters", {}) or {}

            if tool_registry is not None:
                tool_registry.record_tool(
                    ToolMetadata(
                        name=full_tool_name,
                        scope=self.scope,
                        description=description,
                        tags=sorted(tags),
                        read_only=bool(annotations.read_only_hint),
                        destructive=bool(annotations.destructive_hint),
                        source_class=f"{self.__class__.__module__}.{self.__class__.__name__}.{method_name}",
                        parameters_schema=params_schema,
                    ),
                    executable=wrapped_fn,
                )

            registered_count += 1
            self.logger.debug(f"Auto-registered scoped tool: {full_tool_name}")

        self.logger.info(
            f"Auto-registered {registered_count} tools from {self.__class__.__name__} (scope='{self.scope}')"
        )
        return registered_count
