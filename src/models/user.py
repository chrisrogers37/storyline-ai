"""User model - auto-populated from Telegram interactions."""
from sqlalchemy import Column, String, BigInteger, Boolean, Integer, DateTime
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid

from src.config.database import Base


class User(Base):
    """
    User model.

    Users are automatically discovered from Telegram interactions.
    No separate registration system needed.
    """

    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Telegram identity (source of truth)
    telegram_user_id = Column(BigInteger, unique=True, nullable=False, index=True)
    telegram_username = Column(String(100))
    telegram_first_name = Column(String(255))
    telegram_last_name = Column(String(255))

    # Team
    team_name = Column(String(255))

    # Role (manually assigned via CLI)
    role = Column(String(50), default="member")  # 'admin', 'member'
    is_active = Column(Boolean, default=True)

    # Auto-tracked stats
    total_posts = Column(Integer, default=0)
    first_seen_at = Column(DateTime, default=datetime.utcnow)
    last_seen_at = Column(DateTime, default=datetime.utcnow)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<User {self.telegram_username or self.telegram_user_id} ({self.role})>"
