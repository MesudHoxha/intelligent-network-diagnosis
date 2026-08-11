from __future__ import annotations

from pathlib import Path

import uvicorn

from src.phase7.api import create_app


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000


def main() -> None:
    """Run the frozen API locally without exposing a configurable bind host."""

    uvicorn.run(
        create_app(repository_root=Path.cwd()),
        host=DEFAULT_HOST,
        port=DEFAULT_PORT,
        reload=False,
    )


if __name__ == "__main__":
    main()
