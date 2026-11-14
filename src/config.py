"""Application and MCP Server configuration using Pydantic Settings."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralized settings for FastAPI + FastMCP server."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = Field(default="Enterprise FastAPI + FastMCP Server")
    APP_VERSION: str = Field(default="0.1.0")
    HOST: str = Field(default="0.0.0.0")
    PORT: int = Field(default=8000)
    PUBLIC_BASE_URL: str = Field(default="http://localhost:8000")

    # MCP Server settings
    MCP_SERVER_NAME: str = Field(default="core-mcp-server")
    MCP_MOUNT_PATH: str = Field(default="/mcp")
    MCP_STATELESS_HTTP: bool = Field(default=True)

    # Optional list of enabled scopes; ["*"] means all scopes are enabled
    ENABLED_SCOPES: list[str] = Field(default=["*"])


settings = Settings()
