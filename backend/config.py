"""Shared backend configuration helpers."""

import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent


def load_environment() -> None:
    """Load env files from the project root and backend directory."""
    for env_path in (
        PROJECT_ROOT / ".env",
        PROJECT_ROOT / "env",
        BACKEND_DIR / ".env",
        BACKEND_DIR / "env",
    ):
        if env_path.exists():
            load_dotenv(env_path, override=False)


def require_env(*names: str) -> dict[str, str]:
    values = {name: os.environ.get(name, "") for name in names}
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise RuntimeError(
            f"Missing required environment variable(s): {', '.join(missing)}. "
            "Add them to .env or env at the project root."
        )
    return values


load_environment()
