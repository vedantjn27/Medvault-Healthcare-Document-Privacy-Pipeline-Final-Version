"""Typed, environment-backed application configuration."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import EmailStr, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    """Runtime settings loaded from ``backend/.env`` and environment variables."""

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "MedVault API"
    app_env: Literal["development", "testing", "staging", "production"] = "development"
    debug: bool = Field(default=False, validation_alias="APP_DEBUG")
    api_v1_prefix: str = "/api/v1"
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])

    mongodb_uri: SecretStr
    mongodb_db_name: str = "medvault"

    jwt_secret: SecretStr
    jwt_algorithm: Literal["HS256", "HS384", "HS512"] = "HS256"
    jwt_access_token_expire_minutes: int = Field(default=60, ge=5, le=1440)

    mistral_api_key: SecretStr | None = None
    mistral_model: str = "mistral-small-latest"

    vapid_public_key: SecretStr | None = None
    vapid_private_key: SecretStr | None = None
    vapid_subject: str | None = None

    smtp_host: str | None = None
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_user: str | None = None
    smtp_pass: SecretStr | None = None
    smtp_from_email: EmailStr | None = None
    smtp_use_tls: bool = True
    frontend_public_url: str = "http://127.0.0.1:5173"

    temp_job_dir: Path = Path("./.medvault_jobs")
    temp_job_ttl_seconds: int = Field(default=3600, ge=60)
    temp_cleanup_interval_seconds: int = Field(default=300, ge=30)
    max_upload_size_bytes: int = Field(default=52_428_800, ge=1_048_576)
    max_batch_files: int = Field(default=25, ge=1, le=100)
    max_concurrent_chunks: int = Field(default=4, ge=1, le=32)
    resource_profile: Literal["full", "free"] = "full"
    tesseract_cmd: Path | None = None

    @property
    def effective_spacy_model(self) -> str:
        """Select a model without changing the local full-fidelity default."""

        return "en_core_web_sm" if self.resource_profile == "free" else "en_core_web_lg"

    @property
    def effective_ocr_dpi(self) -> int:
        """Constrain raster memory only for the explicitly enabled free profile."""

        return 200 if self.resource_profile == "free" else 300

    @property
    def effective_max_concurrent_chunks(self) -> int:
        """Free Render instances process one chunk at a time to cap peak memory."""

        return 1 if self.resource_profile == "free" else self.max_concurrent_chunks

    @property
    def effective_max_upload_size_bytes(self) -> int:
        """Avoid accepting files a 512 MB service cannot safely process."""

        return min(self.max_upload_size_bytes, 10 * 1024 * 1024) if self.resource_profile == "free" else self.max_upload_size_bytes

    @property
    def effective_max_batch_files(self) -> int:
        """Keep free-tier batch work bounded without changing local limits."""

        return min(self.max_batch_files, 3) if self.resource_profile == "free" else self.max_batch_files

    @field_validator("api_v1_prefix")
    @classmethod
    def normalize_api_prefix(cls, value: str) -> str:
        normalized = f"/{value.strip('/')}"
        if normalized == "/":
            raise ValueError("API prefix cannot be empty")
        return normalized

    @field_validator("frontend_public_url")
    @classmethod
    def normalize_frontend_public_url(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        if not normalized.startswith(("http://", "https://")):
            raise ValueError("FRONTEND_PUBLIC_URL must start with http:// or https://")
        return normalized

    @field_validator("mongodb_uri")
    @classmethod
    def validate_mongodb_uri(cls, value: SecretStr) -> SecretStr:
        raw = value.get_secret_value()
        if raw.startswith("<") or not raw.startswith(("mongodb://", "mongodb+srv://")):
            raise ValueError("MONGODB_URI must be a valid MongoDB connection URI")
        return value

    @field_validator("jwt_secret")
    @classmethod
    def validate_jwt_secret(cls, value: SecretStr) -> SecretStr:
        raw = value.get_secret_value()
        if raw.startswith("<") or len(raw.encode("utf-8")) < 32:
            raise ValueError("JWT_SECRET must contain at least 32 bytes")
        return value

    @field_validator(
        "mistral_api_key",
        "vapid_public_key",
        "vapid_private_key",
        "smtp_pass",
        mode="before",
    )
    @classmethod
    def empty_optional_secrets(cls, value: object) -> object:
        return None if value == "" else value

    @field_validator("smtp_host", "smtp_user", "vapid_subject", mode="before")
    @classmethod
    def empty_optional_strings(cls, value: object) -> object:
        return None if value == "" else value

    @field_validator("tesseract_cmd", mode="before")
    @classmethod
    def empty_optional_path(cls, value: object) -> object:
        return None if value == "" else value

    @field_validator("temp_job_dir")
    @classmethod
    def resolve_temp_job_dir(cls, value: Path) -> Path:
        return value if value.is_absolute() else (BACKEND_DIR / value).resolve()


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide immutable settings instance."""

    return Settings()
