"""Tests for CategoryMixRepository."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from decimal import Decimal
from datetime import datetime

from src.repositories.category_mix_repository import CategoryMixRepository
from src.models.category_mix import CategoryPostCaseMix


@pytest.mark.unit
class TestCategoryMixRepository:
    """Test suite for CategoryMixRepository."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session with chainable query."""
        session = MagicMock()
        mock_query = MagicMock()
        session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.with_entities.return_value = mock_query
        return session

    @pytest.fixture
    def mix_repo(self, mock_db):
        """Create CategoryMixRepository with mocked database."""
        with patch("src.repositories.base_repository.get_db") as mock_get_db:
            mock_get_db.return_value = iter([mock_db])
            repo = CategoryMixRepository()
            repo._db = mock_db  # Set _db (not db which is a property)
            return repo

    def test_validate_ratios_success(self, mix_repo):
        """Test that valid ratios pass validation."""
        ratios = {
            "memes": Decimal("0.7"),
            "merch": Decimal("0.3"),
        }
        # Should not raise
        mix_repo._validate_ratios(ratios)

    def test_validate_ratios_empty_raises(self, mix_repo):
        """Test that empty ratios raise ValueError."""
        with pytest.raises(ValueError, match="At least one category"):
            mix_repo._validate_ratios({})

    def test_validate_ratios_negative_raises(self, mix_repo):
        """Test that negative ratios raise ValueError."""
        ratios = {"memes": Decimal("-0.1")}
        with pytest.raises(ValueError, match="cannot be negative"):
            mix_repo._validate_ratios(ratios)

    def test_validate_ratios_over_one_raises(self, mix_repo):
        """Test that ratios over 1.0 raise ValueError."""
        ratios = {"memes": Decimal("1.5")}
        with pytest.raises(ValueError, match="cannot exceed 1.0"):
            mix_repo._validate_ratios(ratios)

    def test_validate_ratios_sum_not_one_raises(self, mix_repo):
        """Test that ratios not summing to 1.0 raise ValueError."""
        ratios = {
            "memes": Decimal("0.5"),
            "merch": Decimal("0.3"),
        }  # Sum = 0.8
        with pytest.raises(ValueError, match="must sum to 1.0"):
            mix_repo._validate_ratios(ratios)

    def test_validate_ratios_empty_category_raises(self, mix_repo):
        """Test that empty category name raises ValueError."""
        ratios = {"": Decimal("1.0")}
        with pytest.raises(ValueError, match="cannot be empty"):
            mix_repo._validate_ratios(ratios)

    def test_validate_ratios_tolerance(self, mix_repo):
        """Test that small floating point errors are tolerated."""
        # These might not sum to exactly 1.0 due to floating point
        ratios = {
            "cat1": Decimal("0.3333"),
            "cat2": Decimal("0.3333"),
            "cat3": Decimal("0.3334"),
        }
        # Should not raise (sum is close enough to 1.0)
        mix_repo._validate_ratios(ratios)

    def test_get_current_mix(self, mix_repo, mock_db):
        """Test getting current mix records."""
        mock_records = [
            Mock(category="memes", ratio=Decimal("0.7"), is_current=True),
            Mock(category="merch", ratio=Decimal("0.3"), is_current=True),
        ]
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = mock_records

        result = mix_repo.get_current_mix()

        assert len(result) == 2
        mock_db.query.assert_called_once()

    def test_get_current_mix_as_dict(self, mix_repo, mock_db):
        """Test getting current mix as dictionary."""
        mock_records = [
            Mock(category="memes", ratio=Decimal("0.7"), is_current=True),
            Mock(category="merch", ratio=Decimal("0.3"), is_current=True),
        ]
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = mock_records

        result = mix_repo.get_current_mix_as_dict()

        assert result == {"memes": Decimal("0.7"), "merch": Decimal("0.3")}

    def test_has_current_mix_true(self, mix_repo, mock_db):
        """Test has_current_mix returns True when mix exists."""
        mock_db.query.return_value.filter.return_value.scalar.return_value = 2

        result = mix_repo.has_current_mix()

        assert result is True

    def test_has_current_mix_false(self, mix_repo, mock_db):
        """Test has_current_mix returns False when no mix exists."""
        mock_db.query.return_value.filter.return_value.scalar.return_value = 0

        result = mix_repo.has_current_mix()

        assert result is False

    def test_get_categories_without_ratio(self, mix_repo, mock_db):
        """Test finding categories without defined ratios."""
        # Current mix only has "memes"
        mock_records = [Mock(category="memes", ratio=Decimal("1.0"))]
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = mock_records

        result = mix_repo.get_categories_without_ratio(["memes", "merch", "misc"])

        assert "merch" in result
        assert "misc" in result
        assert "memes" not in result

    def test_set_mix_creates_new_records(self, mix_repo, mock_db):
        """Test that set_mix creates new records."""
        # No existing records
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

        ratios = {
            "memes": Decimal("0.7"),
            "merch": Decimal("0.3"),
        }

        mix_repo.set_mix(ratios)

        # Should add 2 new records
        assert mock_db.add.call_count == 2
        mock_db.commit.assert_called_once()

    def test_set_mix_expires_old_records(self, mix_repo, mock_db):
        """Test that set_mix expires existing records."""
        # Existing records
        old_record = Mock(is_current=True, effective_to=None)
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            old_record
        ]

        ratios = {"memes": Decimal("1.0")}

        mix_repo.set_mix(ratios)

        # Old record should be expired
        assert old_record.is_current is False
        assert old_record.effective_to is not None


@pytest.mark.unit
class TestCategoryMixRepositoryTenantFiltering:
    """Tests for optional chat_settings_id tenant filtering on CategoryMixRepository."""

    TENANT_ID = "tenant-uuid-1"

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session with chainable query."""
        session = MagicMock()
        mock_query = MagicMock()
        session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.with_entities.return_value = mock_query
        return session

    @pytest.fixture
    def mix_repo(self, mock_db):
        """Create CategoryMixRepository with mocked database."""
        with patch("src.repositories.base_repository.get_db") as mock_get_db:
            mock_get_db.return_value = iter([mock_db])
            repo = CategoryMixRepository()
            repo._db = mock_db
            return repo

    def test_get_current_mix_with_tenant(self, mix_repo, mock_db):
        """get_current_mix passes chat_settings_id through tenant filter."""
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        with patch.object(
            mix_repo, "_apply_tenant_filter", wraps=mix_repo._apply_tenant_filter
        ) as mock_filter:
            mix_repo.get_current_mix(chat_settings_id=self.TENANT_ID)
            mock_filter.assert_called_once()
            assert mock_filter.call_args[0][2] == self.TENANT_ID

    def test_get_current_mix_as_dict_passes_tenant(self, mix_repo, mock_db):
        """get_current_mix_as_dict passes chat_settings_id to get_current_mix."""
        with patch.object(mix_repo, "get_current_mix", return_value=[]) as mock_get:
            mix_repo.get_current_mix_as_dict(chat_settings_id=self.TENANT_ID)
            mock_get.assert_called_once_with(chat_settings_id=self.TENANT_ID)

    def test_get_history_with_tenant(self, mix_repo, mock_db):
        """get_history passes chat_settings_id through tenant filter."""
        mock_db.query.return_value.order_by.return_value.all.return_value = []
        with patch.object(
            mix_repo, "_apply_tenant_filter", wraps=mix_repo._apply_tenant_filter
        ) as mock_filter:
            mix_repo.get_history(chat_settings_id=self.TENANT_ID)
            mock_filter.assert_called_once()
            assert mock_filter.call_args[0][2] == self.TENANT_ID

    def test_set_mix_passes_tenant_to_expire_query(self, mix_repo, mock_db):
        """set_mix passes chat_settings_id when expiring old records."""
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        with patch.object(mix_repo, "get_current_mix", return_value=[]) as mock_get:
            mix_repo.set_mix({"memes": Decimal("1.0")}, chat_settings_id=self.TENANT_ID)
            mock_get.assert_called_once_with(chat_settings_id=self.TENANT_ID)

    def test_set_mix_passes_tenant_to_new_records(self, mix_repo, mock_db):
        """set_mix sets chat_settings_id on newly created records."""
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        mix_repo.set_mix(
            {"memes": Decimal("0.7"), "merch": Decimal("0.3")},
            chat_settings_id=self.TENANT_ID,
        )

        # Both added records should have the tenant ID
        for call in mock_db.add.call_args_list:
            added = call[0][0]
            assert added.chat_settings_id == self.TENANT_ID

    def test_has_current_mix_with_tenant(self, mix_repo, mock_db):
        """has_current_mix passes chat_settings_id through tenant filter."""
        # Set up chain so scalar() returns an int after tenant filter
        mock_query = mock_db.query.return_value.filter.return_value
        mock_query.filter.return_value.scalar.return_value = 0
        mock_query.scalar.return_value = 0
        with patch.object(
            mix_repo, "_apply_tenant_filter", wraps=mix_repo._apply_tenant_filter
        ) as mock_filter:
            mix_repo.has_current_mix(chat_settings_id=self.TENANT_ID)
            mock_filter.assert_called_once()
            assert mock_filter.call_args[0][2] == self.TENANT_ID

    def test_get_categories_without_ratio_passes_tenant(self, mix_repo, mock_db):
        """get_categories_without_ratio passes chat_settings_id to get_current_mix_as_dict."""
        with patch.object(
            mix_repo, "get_current_mix_as_dict", return_value={}
        ) as mock_get:
            mix_repo.get_categories_without_ratio(
                ["memes"], chat_settings_id=self.TENANT_ID
            )
            mock_get.assert_called_once_with(chat_settings_id=self.TENANT_ID)


@pytest.mark.unit
class TestCategoryPostCaseMixModel:
    """Test suite for CategoryPostCaseMix model."""

    def test_model_repr(self):
        """Test model string representation."""
        mix = CategoryPostCaseMix(
            category="memes",
            ratio=Decimal("0.7"),
            is_current=True,
        )

        repr_str = repr(mix)

        assert "memes" in repr_str
        assert "70" in repr_str
        assert "current" in repr_str

    def test_model_repr_expired(self):
        """Test model string representation for expired record."""
        mix = CategoryPostCaseMix(
            category="merch",
            ratio=Decimal("0.3"),
            is_current=False,
            effective_to=datetime(2024, 1, 15),
        )

        repr_str = repr(mix)

        assert "merch" in repr_str
        assert "expired" in repr_str
