"""Application settings and configuration management."""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    """Application configuration."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    # Meta Graph API
    META_GRAPH_API_VERSION: str = "v21.0"

    # Database Configuration
    DATABASE_URL: Optional[str] = None  # Full URL (overrides DB_* components if set)
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "storydump"
    DB_USER: str = "storydump_user"
    DB_PASSWORD: Optional[str] = ""
    DB_SSLMODE: Optional[str] = None  # e.g., "require" for Neon
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    TEST_DB_NAME: str = "storydump_test"

    # Telegram Configuration (REQUIRED)
    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_CHANNEL_ID: int
    ADMIN_TELEGRAM_CHAT_ID: int

    # Media Configuration
    MEDIA_DIR: str = "/tmp/media"

    # Backup Configuration
    BACKUP_DIR: str = "/backup/storydump"
    BACKUP_RETENTION_DAYS: int = 30

    # Instagram API Configuration (Phase 2 Only)
    INSTAGRAM_ACCOUNT_ID: Optional[str] = None
    INSTAGRAM_ACCESS_TOKEN: Optional[str] = None
    FACEBOOK_APP_ID: Optional[str] = None  # Facebook Login OAuth (legacy)
    FACEBOOK_APP_SECRET: Optional[str] = None  # Facebook Login OAuth (legacy)
    INSTAGRAM_APP_ID: Optional[str] = None  # Instagram Login OAuth (preferred)
    INSTAGRAM_APP_SECRET: Optional[str] = None  # Instagram Login OAuth (preferred)
    OAUTH_REDIRECT_BASE_URL: Optional[str] = None  # e.g., "https://api.storydump.app"
    INSTAGRAM_DEEPLINK_URL: str = "https://www.instagram.com/"

    # Google Drive OAuth (Phase 05 Multi-Tenant)
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None

    # Cloudinary Configuration (Phase 2 Only)
    CLOUD_STORAGE_PROVIDER: str = "cloudinary"  # Currently only cloudinary supported
    CLOUDINARY_CLOUD_NAME: Optional[str] = None
    CLOUDINARY_API_KEY: Optional[str] = None
    CLOUDINARY_API_SECRET: Optional[str] = None
    CLOUD_UPLOAD_RETENTION_HOURS: int = 24  # Delete cloud uploads after this time

    # Instagram API Rate Limiting (Phase 2)
    INSTAGRAM_POSTS_PER_HOUR: int = 25  # Meta's limit for Stories

    # Security (Phase 2 - required for token encryption)
    ENCRYPTION_KEY: Optional[str] = None  # Fernet key for encrypting tokens in DB

    # Media Sync (loop cadence is system-wide; per-chat enable lives in chat_settings)
    MEDIA_SYNC_INTERVAL_SECONDS: int = 300  # 5 minutes

    # Logging
    LOG_LEVEL: str = "INFO"

    # Instagram username for deep links (still env — wired into widget URLs)
    INSTAGRAM_USERNAME: Optional[str] = None

    # AI Caption Generation
    ANTHROPIC_API_KEY: Optional[str] = None
    CAPTION_MODEL: str = "claude-haiku-4-5-20251001"

    @property
    def meta_graph_base(self) -> str:
        """Base URL for Meta Graph API calls."""
        return f"https://graph.facebook.com/{self.META_GRAPH_API_VERSION}"

    @property
    def database_url(self) -> str:
        """Get database URL for SQLAlchemy.

        If DATABASE_URL is set, use it directly (standard for PaaS platforms).
        Otherwise, assemble from individual DB_* components.
        Appends ?sslmode= if DB_SSLMODE is set (required for Neon).
        """
        if self.DATABASE_URL:
            return self.DATABASE_URL

        if self.DB_PASSWORD:
            url = f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        else:
            url = f"postgresql://{self.DB_USER}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

        if self.DB_SSLMODE:
            url += f"?sslmode={self.DB_SSLMODE}"
        return url

    @property
    def test_database_url(self) -> str:
        """Get test database URL."""
        if self.DB_PASSWORD:
            url = f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.TEST_DB_NAME}"
        else:
            url = f"postgresql://{self.DB_USER}@{self.DB_HOST}:{self.DB_PORT}/{self.TEST_DB_NAME}"

        if self.DB_SSLMODE:
            url += f"?sslmode={self.DB_SSLMODE}"
        return url


# Global settings instance
settings = Settings()
