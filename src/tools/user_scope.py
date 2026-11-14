"""Example Scope 3: `users` — Using `BaseScopedToolset` (Multi-Tool per Scope Pattern).

Demonstrates the `prowler-cloud/prowler` pattern where a single class represents a domain/scope,
and all public `async def` methods are auto-registered as MCP tools with `<scope>_<method>` naming
and automatic `readOnlyHint` / `destructiveHint` annotations.
"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from src.core.base_tool import BaseScopedToolset


class UserScopedToolset(BaseScopedToolset):
    """Domain toolset for `users` scope.

    Public async methods are automatically registered as:
    - `users_list_users` (readOnlyHint=True, destructiveHint=False)
    - `users_get_user` (readOnlyHint=True, destructiveHint=False)
    - `users_create_user` (readOnlyHint=False, destructiveHint=False)
    - `users_delete_user` (readOnlyHint=False, destructiveHint=True)
    """

    scope = "users"
    prefix_with_scope = True
    tags = {"iam", "directory"}

    def __init__(self) -> None:
        super().__init__()
        # Example in-memory store for demonstration
        self._mock_users: dict[str, dict[str, Any]] = {
            "usr_01": {"id": "usr_01", "name": "Alice Nguyen", "email": "alice@example.com", "role": "admin"},
            "usr_02": {"id": "usr_02", "name": "Bob Tran", "email": "bob@example.com", "role": "developer"},
            "usr_03": {"id": "usr_03", "name": "Charlie Le", "email": "charlie@example.com", "role": "viewer"},
        }

    async def list_users(
        self,
        role: str | None = Field(
            default=None,
            description="Optional role filter (e.g., 'admin', 'developer', 'viewer').",
        ),
    ) -> dict[str, Any]:
        """List all users in the workspace, optionally filtered by role."""
        users = list(self._mock_users.values())
        if role:
            users = [u for u in users if u["role"].lower() == role.lower()]
        return {
            "scope": self.scope,
            "count": len(users),
            "items": users,
        }

    async def get_user(
        self,
        user_id: str = Field(description="Unique user ID (e.g., 'usr_01')."),
    ) -> dict[str, Any]:
        """Retrieve detailed information for a specific user by ID."""
        user = self._mock_users.get(user_id)
        if not user:
            return {"found": False, "error": f"User '{user_id}' not found."}
        return {"found": True, "user": user}

    async def create_user(
        self,
        name: str = Field(description="Full display name of the new user."),
        email: str = Field(description="Email address of the new user."),
        role: str = Field(default="developer", description="Assigned role for the user."),
    ) -> dict[str, Any]:
        """Create a new user record in the `users` scope."""
        new_id = f"usr_{len(self._mock_users) + 1:02d}"
        user = {"id": new_id, "name": name, "email": email, "role": role}
        self._mock_users[new_id] = user
        return {"created": True, "user": user}

    async def delete_user(
        self,
        user_id: str = Field(description="Unique user ID to delete."),
    ) -> dict[str, Any]:
        """Delete a user by ID (automatically marked with destructiveHint=True)."""
        removed = self._mock_users.pop(user_id, None)
        if not removed:
            return {"deleted": False, "error": f"User '{user_id}' does not exist."}
        return {"deleted": True, "removed_user": removed}
