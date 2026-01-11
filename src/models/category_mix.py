"""Category post case mix model - Type 2 SCD for tracking posting ratio history."""
from sqlalchemy import Column, String, Boolean, DateTime, Numeric, ForeignKey, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid

from src.config.database import Base


class CategoryPostCaseMix(Base):
    """
    Category posting ratio configuration with Type 2 SCD.

    Tracks the desired posting ratio for each category over time.
    When ratios change, old records are expired (effective_to set)
    and new records are created, preserving full history.

    All current (is_current=TRUE) ratios must sum to 1.0.
    """

    __tablename__ = "category_post_case_mix"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Category name (matches media_items.category)
    category = Column(String(100), nullable=False, index=True)

    # Ratio as decimal (0.70 = 70%), precision 5 scale 4 allows 0.0000 to 9.9999
    ratio = Column(Numeric(5, 4), nullable=False)

    # Type 2 SCD fields
    effective_from = Column(DateTime, nullable=False, default=datetime.utcnow)
    effective_to = Column(DateTime, nullable=True)  # NULL = currently active
    is_current = Column(Boolean, default=True, index=True)

    # Audit fields
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))

    # Constraints
    __table_args__ = (
        CheckConstraint("ratio >= 0 AND ratio <= 1", name="check_ratio_range"),
    )

    def __repr__(self):
        status = "current" if self.is_current else f"expired {self.effective_to}"
        return f"<CategoryPostCaseMix {self.category}={float(self.ratio)*100:.1f}% ({status})>"
