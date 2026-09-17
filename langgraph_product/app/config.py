"""Application configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR.parent / ".env")
load_dotenv(ROOT_DIR / ".env")


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return int(raw)


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return raw.lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_env: str = os.getenv("APP_ENV", "local")
    app_secret_key: str = os.getenv("APP_SECRET_KEY", "local-dev")

    database_url: str = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{ROOT_DIR / 'agent_platform.db'}",
    )
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    model_provider: str = os.getenv("MODEL_PROVIDER", "openai_compatible")
    model_id: str = os.getenv("MODEL_ID", "")
    base_url: str = os.getenv("BASE_URL", "")
    api_key: str = os.getenv("API_KEY", "")
    temperature: float = float(os.getenv("TEMPERATURE", "0"))

    embedding_model: str = os.getenv("EMBEDDING_MODEL", "")
    embedding_base_url: str = os.getenv("EMBEDDING_BASE_URL", "")
    embedding_api_key: str = os.getenv("EMBEDDING_API_KEY", "")

    trace_enabled: bool = _bool_env("TRACE_ENABLED", True)
    project_workspace_root: str = os.getenv(
        "PROJECT_WORKSPACE_ROOT",
        str(ROOT_DIR / "generated_projects"),
    )
    max_generated_file_bytes: int = _int_env("MAX_GENERATED_FILE_BYTES", 200_000)
    max_tool_timeout_seconds: int = _int_env("MAX_TOOL_TIMEOUT_SECONDS", 120)

    default_daily_token_limit: int = _int_env("DEFAULT_DAILY_TOKEN_LIMIT", 100_000)
    default_monthly_token_limit: int = _int_env("DEFAULT_MONTHLY_TOKEN_LIMIT", 2_000_000)
    builder_blueprint_token_limit: int = _int_env("BUILDER_BLUEPRINT_TOKEN_LIMIT", 80_000)
    builder_full_project_token_limit: int = _int_env(
        "BUILDER_FULL_PROJECT_TOKEN_LIMIT",
        300_000,
    )


settings = Settings()
