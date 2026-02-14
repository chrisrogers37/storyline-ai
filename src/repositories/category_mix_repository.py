"""Category post case mix repository - CRUD with Type 2 SCD logic."""

from typing import Optional, List, Dict
from datetime import datetime
from decimal import Decimal
from sqlalchemy import func

from src.repositories.base_repository import BaseRepository
from src.models.category_mix import CategoryPostCaseMix


class CategoryMixRepository(BaseRepository):
    """Repository for CategoryPostCaseMix with Type 2 SCD operations."""

    def __init__(self):
        super().__init__()

    def get_current_mix(
        self, chat_settings_id: Optional[str] = None
    ) -> List[CategoryPostCaseMix]:
        """Get all current (active) category ratios."""
        query = self.db.query(CategoryPostCaseMix).filter(
            CategoryPostCaseMix.is_current
        )
        query = self._apply_tenant_filter(
            query, CategoryPostCaseMix, chat_settings_id
        )
        return query.order_by(CategoryPostCaseMix.category).all()

    def get_current_mix_as_dict(
        self, chat_settings_id: Optional[str] = None
    ) -> Dict[str, Decimal]:
        """Get current mix as {category: ratio} dictionary."""
        current = self.get_current_mix(chat_settings_id=chat_settings_id)
        return {mix.category: mix.ratio for mix in current}

    def get_history(
        self, category: Optional[str] = None, chat_settings_id: Optional[str] = None
    ) -> List[CategoryPostCaseMix]:
        """Get full history, optionally filtered by category."""
        query = self.db.query(CategoryPostCaseMix)
        query = self._apply_tenant_filter(
            query, CategoryPostCaseMix, chat_settings_id
        )

        if category:
            query = query.filter(CategoryPostCaseMix.category == category)

        return query.order_by(
            CategoryPostCaseMix.category,
            CategoryPostCaseMix.effective_from.desc(),
        ).all()

    def set_mix(
        self,
        ratios: Dict[str, Decimal],
        user_id: Optional[str] = None,
        chat_settings_id: Optional[str] = None,
    ) -> List[CategoryPostCaseMix]:
        """
        Set new category mix ratios (Type 2 SCD update).

        This expires all current ratios and creates new ones.
        Validates that ratios sum to 1.0 (100%).

        Args:
            ratios: Dict of {category: ratio} where ratios sum to 1.0
            user_id: User making the change
            chat_settings_id: Optional tenant scope

        Returns:
            List of newly created CategoryPostCaseMix records

        Raises:
            ValueError: If ratios don't sum to 1.0 or are invalid
        """
        # Validate ratios
        self._validate_ratios(ratios)

        now = datetime.utcnow()

        # Expire only this tenant's current records
        current_records = self.get_current_mix(chat_settings_id=chat_settings_id)
        for record in current_records:
            record.effective_to = now
            record.is_current = False

        # Create new records with tenant FK
        new_records = []
        for category, ratio in ratios.items():
            new_record = CategoryPostCaseMix(
                category=category,
                ratio=ratio,
                effective_from=now,
                effective_to=None,
                is_current=True,
                created_by_user_id=user_id,
                chat_settings_id=chat_settings_id,
            )
            self.db.add(new_record)
            new_records.append(new_record)

        self.db.commit()

        # Refresh to get IDs
        for record in new_records:
            self.db.refresh(record)

        return new_records

    def has_current_mix(self, chat_settings_id: Optional[str] = None) -> bool:
        """Check if any current mix ratios exist."""
        query = self.db.query(func.count(CategoryPostCaseMix.id)).filter(
            CategoryPostCaseMix.is_current
        )
        query = self._apply_tenant_filter(
            query, CategoryPostCaseMix, chat_settings_id
        )
        count = query.scalar()
        return count > 0

    def get_categories_without_ratio(
        self, categories: List[str], chat_settings_id: Optional[str] = None
    ) -> List[str]:
        """Find categories that don't have a current ratio defined."""
        current_mix = self.get_current_mix_as_dict(chat_settings_id=chat_settings_id)
        return [cat for cat in categories if cat not in current_mix]

    def _validate_ratios(self, ratios: Dict[str, Decimal]) -> None:
        """
        Validate that ratios are valid.

        Raises:
            ValueError: If validation fails
        """
        if not ratios:
            raise ValueError("At least one category ratio must be provided")

        # Check each ratio is valid
        for category, ratio in ratios.items():
            if not category or not category.strip():
                raise ValueError("Category name cannot be empty")

            ratio_decimal = Decimal(str(ratio))

            if ratio_decimal < 0:
                raise ValueError(f"Ratio for '{category}' cannot be negative: {ratio}")

            if ratio_decimal > 1:
                raise ValueError(f"Ratio for '{category}' cannot exceed 1.0: {ratio}")

        # Check sum equals 1.0 (with small tolerance for floating point)
        total = sum(Decimal(str(r)) for r in ratios.values())
        tolerance = Decimal("0.0001")

        if abs(total - Decimal("1.0")) > tolerance:
            raise ValueError(f"Ratios must sum to 1.0 (100%). Current sum: {total:.4f}")
