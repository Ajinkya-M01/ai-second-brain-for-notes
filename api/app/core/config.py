"""Core configuration loaded from environment variables using Pydantic Settings."""

import os
from pathlib import Path
from typing import Optional
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Absolute path to the api/ directory, regardless of where the process is started from.
# This file lives at api/app/core/config.py  →  .parent x3 gives api/
_API_DIR = Path(__file__).resolve().parent.parent.parent

# Absolute path to the root .env (one level above api/)
_ENV_FILE = _API_DIR.parent / ".env"

# Vercel's filesystem is read-only except /tmp (ephemeral, per-instance).
IS_VERCEL = bool(os.environ.get("VERCEL"))
_DATA_DIR = Path("/tmp/second_brain") if IS_VERCEL else _API_DIR / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_ENV: str = "development"
    PROJECT_NAME: str = "AI Second Brain API"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"

    # CORS configuration
    FRONTEND_ORIGIN: str = "http://localhost:5173"

    # Storage paths — defaults are absolute so they resolve correctly regardless of CWD.
    # Override via .env or environment variables if needed.
    DATABASE_URL: str = f"sqlite:///{_DATA_DIR / 'second_brain.db'}"
    CHROMA_PERSIST_DIR: str = str(_DATA_DIR / "chroma")
    UPLOAD_DIR: str = str(_DATA_DIR / "uploads")

    # OpenRouter AI provider settings (placeholders for Milestone 6+)
    OPENROUTER_API_KEY: Optional[str] = None
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_CHAT_MODEL: str = "nvidia/nemotron-3.5-lightning:free"
    OPENROUTER_EMBEDDING_MODEL: str = "nvidia/nemotron-3-embed-1b:free"

    # Limits and constraints
    MAX_UPLOAD_MB: int = 10
    MAX_PDF_PAGES: int = 100
    MAX_CHAT_REQUESTS_PER_MINUTE: int = 10

    @model_validator(mode="after")
    def resolve_relative_paths(self):
        if self.DATABASE_URL.startswith("sqlite:///") and not self.DATABASE_URL.startswith("sqlite:///:memory:"):
            raw_path = self.DATABASE_URL.replace("sqlite:///", "")
            path_obj = Path(raw_path)
            if not path_obj.is_absolute():
                self.DATABASE_URL = f"sqlite:///{(_API_DIR / path_obj).resolve()}"
        if not Path(self.UPLOAD_DIR).is_absolute():
            self.UPLOAD_DIR = str((_API_DIR / self.UPLOAD_DIR).resolve())
        if not Path(self.CHROMA_PERSIST_DIR).is_absolute():
            self.CHROMA_PERSIST_DIR = str((_API_DIR / self.CHROMA_PERSIST_DIR).resolve())
        return self


settings = Settings()

