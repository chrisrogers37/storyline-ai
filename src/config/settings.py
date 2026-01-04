"""Application settings and configuration management."""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    """Application configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Phase Control
    ENABLE_INSTAGRAM_API: bool = False

    # Database Configuration
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "storyline_ai"
    DB_USER: str = "storyline_user"
    DB_PASSWORD: str
    TEST_DB_NAME: str = "storyline_ai_test"

    # Telegram Configuration (REQUIRED)
    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_CHANNEL_ID: int
    ADMIN_TELEGRAM_CHAT_ID: int

    # Posting Schedule Configuration
    POSTS_PER_DAY: int = 3
    POSTING_HOURS_START: int = 14  # UTC
    POSTING_HOURS_END: int = 2     # UTC (next day)
    REPOST_TTL_DAYS: int = 30

    # Media Configuration
    MEDIA_DIR: str = "/home/pi/media"

    # Backup Configuration
    BACKUP_DIR: str = "/backup/storyline-ai"
    BACKUP_RETENTION_DAYS: int = 30

    # Instagram API Configuration (Phase 2 Only)
    INSTAGRAM_ACCOUNT_ID: Optional[str] = None
    INSTAGRAM_ACCESS_TOKEN: Optional[str] = None
    FACEBOOK_APP_ID: Optional[str] = None
    FACEBOOK_APP_SECRET: Optional[str] = None

    # Cloudinary Configuration (Phase 2 Only)
    CLOUDINARY_CLOUD_NAME: Optional[str] = None
    CLOUDINARY_API_KEY: Optional[str] = None
    CLOUDINARY_API_SECRET: Optional[str] = None

    # Development Settings
    DRY_RUN_MODE: bool = False
    LOG_LEVEL: str = "INFO"

    @property
    def database_url(self) -> str:
        """Get database URL for SQLAlchemy."""
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    @property
    def test_database_url(self) -> str:
        """Get test database URL."""
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.TEST_DB_NAME}"


# Global settings instance
settings = Settings()
