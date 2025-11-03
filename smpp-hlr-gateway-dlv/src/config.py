"""
Configuration management using environment variables with Pydantic.
"""
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
from typing import Literal


class Settings(BaseSettings):
    """Application settings from environment variables."""

    # SMPP Server
    smpp_host: str = Field(default="0.0.0.0", description="SMPP server bind host")
    smpp_port: int = Field(default=2776, ge=1024, le=65535, description="SMPP server port")
    smpp_system_id: str = Field(default="testuser", description="Expected system_id for authentication")
    smpp_password: str = Field(default="testpass", description="Expected password for authentication")

    # TMT Velocity HLR API
    hlr_api_key: str = Field(default="MyApiKey", description="TMT API Key")
    hlr_api_secret: str = Field(default="MyApiSecret", description="TMT API Secret")
    hlr_base_url: str = Field(
        default="https://api.tmtvelocity.com/live/json",
        description="TMT Velocity base URL"
    )
    hlr_timeout_seconds: float = Field(default=5.0, gt=0, description="HLR request timeout")
    hlr_timeout_policy: Literal["reject"] = Field(
        default="reject",
        description="Policy when HLR timeout occurs"
    )
    hlr_cache_ttl_seconds: int = Field(
        default=86400,
        ge=0,
        description="HLR result cache TTL (0 to disable)"
    )

    # Redis Cache
    redis_url: str = Field(
        default="redis://redis:6379/0",
        description="Redis connection URL"
    )
    redis_max_connections: int = Field(default=30, ge=1, description="Redis connection pool size")

    # PostgreSQL Database
    db_enabled: bool = Field(default=True, description="Enable PostgreSQL storage")
    db_host: str = Field(default="localhost", description="PostgreSQL host")
    db_port: int = Field(default=5432, ge=1, le=65535, description="PostgreSQL port")
    db_name: str = Field(default="smpp_hlr", description="Database name")
    db_user: str = Field(default="smpp_user", description="Database user")
    db_password: str = Field(default="password", description="Database password")
    db_pool_min: int = Field(default=5, ge=1, description="Minimum pool size")
    db_pool_max: int = Field(default=20, ge=1, description="Maximum pool size")

    # Cache Warmup
    cache_warmup_enabled: bool = Field(default=True, description="Enable cache warmup on startup")
    cache_warmup_days: int = Field(default=7, ge=1, description="Days to load from DB")
    cache_warmup_limit: int = Field(default=100000, ge=1, description="Max records to warmup")

    # Logging
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: Literal["json", "console"] = Field(default="json", description="Log format")

    # Metrics
    metrics_enabled: bool = Field(default=True, description="Enable Prometheus metrics")
    metrics_port: int = Field(default=9091, ge=1024, le=65535, description="Metrics HTTP port")
    metrics_path: str = Field(default="/metrics", description="Metrics endpoint path")

    # Delivery Reports
    dlr_delay_seconds: float = Field(
        default=0,
        ge=0,
        description="Delay before sending DELIVRD DLR"
    )

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"log_level must be one of {valid_levels}")
        return v_upper

    class Config:
        env_file = "../.env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()