"""Entrypoint to launch the unified FastAPI + FastMCP server."""

import uvicorn

from src.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "src.api.app:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=False,
    )
