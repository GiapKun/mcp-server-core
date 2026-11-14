"""Example Scope 2: `math` — Using `BaseTool` with rich Pydantic validation."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from src.core.base_tool import BaseTool


class MathCalculateTool(BaseTool):
    """Perform basic arithmetic operations under the `math` scope."""

    name = "math_calculate"
    scope = "math"
    description = (
        "Perform arithmetic calculation (add, subtract, multiply, divide) on two numbers "
        "and return structured output."
    )
    tags = {"arithmetic", "calculator"}
    read_only = True

    async def execute(
        self,
        a: float = Field(description="First numeric operand."),
        b: float = Field(description="Second numeric operand."),
        operation: Literal["add", "subtract", "multiply", "divide"] = Field(
            default="add",
            description="Arithmetic operation to perform: 'add', 'subtract', 'multiply', or 'divide'.",
        ),
    ) -> dict[str, Any]:
        if operation == "add":
            result = a + b
        elif operation == "subtract":
            result = a - b
        elif operation == "multiply":
            result = a * b
        elif operation == "divide":
            if b == 0:
                raise ValueError("Division by zero is not allowed.")
            result = a / b
        else:
            raise ValueError(f"Unsupported operation: {operation}")

        return {
            "scope": self.scope,
            "operation": operation,
            "a": a,
            "b": b,
            "result": result,
        }
