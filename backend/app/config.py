"""Application configuration loaded from environment variables using pydantic-settings.

Required variables: MONGODB_URI, JWT_SECRET_KEY, GROQ_API_KEY, GROQ_MODEL
Optional variables: JWT_EXPIRY_MINUTES, MAX_UPLOAD_SIZE_MB, ALLOWED_ORIGINS

A ValidationError is raised at startup if any required variable is missing.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Required environment variables
    MONGODB_URI: str = Field(..., description="MongoDB Atlas connection string")
    JWT_SECRET_KEY: str = Field(..., description="Secret key for signing JWTs")
    GROQ_API_KEY: str = Field(..., description="Groq API key")
    GROQ_MODEL: str = Field(..., description="Groq model name (e.g., llama3-8b-8192)")

    # Optional environment variables with defaults
    JWT_EXPIRY_MINUTES: int = Field(
        default=60, description="JWT time-to-live in minutes"
    )
    MAX_UPLOAD_SIZE_MB: int = Field(
        default=10, description="Maximum allowed upload size in megabytes"
    )
    ALLOWED_ORIGINS: str = Field(
        default="http://localhost:3000",
        description="Comma-separated list of allowed CORS origins",
    )

    @property
    def allowed_origins_list(self) -> list[str]:
        """Parse ALLOWED_ORIGINS into a list of origin strings."""
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    @property
    def max_upload_size_bytes(self) -> int:
        """Return MAX_UPLOAD_SIZE_MB converted to bytes."""
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024


# Module-level singleton — raises ValidationError on import if required vars are missing
settings = Settings()
