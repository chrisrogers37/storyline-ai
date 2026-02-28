"""Tests for MediaRepository."""

import pytest
from unittest.mock import MagicMock, patch

from sqlalchemy.orm import Session

from src.repositories.media_repository import MediaRepository
from src.models.media_item import MediaItem


@pytest.fixture
def mock_db():
    """Create a mock database session with chainable query."""
    session = MagicMock(spec=Session)
    mock_query = MagicMock()
    session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.group_by.return_value = mock_query
    mock_query.having.return_value = mock_query
    mock_query.with_entities.return_value = mock_query
    mock_query.distinct.return_value = mock_query
    return session


@pytest.fixture
def media_repo(mock_db):
    """Create MediaRepository with mocked database session."""
    with patch.object(MediaRepository, "__init__", lambda self: None):
        repo = MediaRepository()
        repo._db = mock_db
        return repo


@pytest.mark.unit
class TestMediaRepository:
    """Test suite for MediaRepository."""

    def test_create_media_item(self, media_repo, mock_db):
        """Test creating a new media item."""
        media_repo.create(
            file_path="/test/image.jpg",
            file_name="image.jpg",
            file_hash="abc123",
            file_size_bytes=102400,
            mime_type="image/jpeg",
        )

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()

        added_item = mock_db.add.call_args[0][0]
        assert isinstance(added_item, MediaItem)
        assert added_item.file_path == "/test/image.jpg"
        assert added_item.file_name == "image.jpg"
        assert added_item.file_hash == "abc123"
        assert added_item.file_size == 102400
        assert added_item.mime_type == "image/jpeg"

    def test_get_by_path(self, media_repo, mock_db):
        """Test retrieving media by file path."""
        mock_item = MagicMock(file_path="/test/unique.jpg")
        mock_db.query.return_value.filter.return_value.first.return_value = mock_item

        result = media_repo.get_by_path("/test/unique.jpg")

        assert result is mock_item
        mock_db.query.assert_called_with(MediaItem)

    def test_get_by_path_not_found(self, media_repo, mock_db):
        """Test retrieving non-existent media by path returns None."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = media_repo.get_by_path("/test/nonexistent.jpg")

        assert result is None

    def test_get_by_hash(self, media_repo, mock_db):
        """Test retrieving media by file hash."""
        mock_items = [MagicMock(file_hash="hash999")]
        mock_db.query.return_value.filter.return_value.all.return_value = mock_items

        result = media_repo.get_by_hash("hash999")

        assert len(result) == 1
        assert result[0].file_hash == "hash999"

    def test_get_duplicates(self, media_repo, mock_db):
        """Test finding duplicate media items."""
        mock_dup = MagicMock()
        mock_dup.file_hash = "duplicate_hash"
        mock_dup.count = 2
        mock_dup.paths = ["/test/original.jpg", "/test/copy.jpg"]
        mock_query = mock_db.query.return_value
        mock_query.having.return_value.all.return_value = [mock_dup]

        result = media_repo.get_duplicates()

        assert len(result) == 1
        assert result[0][0] == "duplicate_hash"
        assert result[0][1] == 2
        assert len(result[0][2]) == 2

    def test_increment_times_posted(self, media_repo, mock_db):
        """Test incrementing post count."""
        mock_item = MagicMock()
        mock_item.times_posted = 0
        mock_item.last_posted_at = None
        mock_db.query.return_value.filter.return_value.first.return_value = mock_item

        media_repo.increment_times_posted("some-id")

        assert mock_item.times_posted == 1
        assert mock_item.last_posted_at is not None
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once_with(mock_item)

    def test_increment_times_posted_not_found(self, media_repo, mock_db):
        """Test incrementing post count for non-existent item."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = media_repo.increment_times_posted("nonexistent-id")

        assert result is None
        mock_db.commit.assert_not_called()

    def test_get_all_with_filters(self, media_repo, mock_db):
        """Test listing media with various filters."""
        mock_query = mock_db.query.return_value
        mock_items = [MagicMock(), MagicMock()]
        mock_query.all.return_value = mock_items

        result = media_repo.get_all(is_active=True, category="memes", limit=10)

        assert len(result) == 2
        mock_db.query.assert_called_with(MediaItem)


@pytest.mark.unit
class TestMediaRepositorySyncMethods:
    """Tests for sync-related repository methods added in Phase 03."""

    def test_get_active_by_source_type(self, media_repo, mock_db):
        """Returns only active items for given source type."""
        mock_items = [MagicMock(source_type="local", is_active=True)]
        mock_db.query.return_value.filter.return_value.all.return_value = mock_items

        result = media_repo.get_active_by_source_type("local")

        assert len(result) == 1
        mock_db.query.assert_called_with(MediaItem)

    def test_get_inactive_by_source_identifier(self, media_repo, mock_db):
        """Returns inactive item by source_type + identifier."""
        mock_item = MagicMock(
            source_type="local",
            source_identifier="/media/old.jpg",
            is_active=False,
        )
        mock_db.query.return_value.filter.return_value.first.return_value = mock_item

        result = media_repo.get_inactive_by_source_identifier("local", "/media/old.jpg")

        assert result is mock_item

    def test_get_inactive_by_source_identifier_not_found(self, media_repo, mock_db):
        """Returns None when no inactive match found."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = media_repo.get_inactive_by_source_identifier("local", "/nonexistent")

        assert result is None

    def test_reactivate_sets_is_active_true(self, media_repo, mock_db):
        """Reactivates item and sets updated_at."""
        mock_item = MagicMock()
        mock_item.is_active = False
        mock_db.query.return_value.filter.return_value.first.return_value = mock_item

        media_repo.reactivate("some-id")

        assert mock_item.is_active is True
        assert mock_item.updated_at is not None
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once_with(mock_item)

    def test_update_source_info_updates_fields(self, media_repo, mock_db):
        """Updates file_path, file_name, and source_identifier."""
        mock_item = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_item

        media_repo.update_source_info(
            media_id="item-1",
            file_path="/new/path.jpg",
            file_name="new_name.jpg",
            source_identifier="/new/path.jpg",
        )

        assert mock_item.file_path == "/new/path.jpg"
        assert mock_item.file_name == "new_name.jpg"
        assert mock_item.source_identifier == "/new/path.jpg"
        assert mock_item.updated_at is not None
        mock_db.commit.assert_called_once()

    def test_update_source_info_partial_update(self, media_repo, mock_db):
        """Only updates fields that are not None."""
        mock_item = MagicMock()
        mock_item.file_path = "/original/path.jpg"
        mock_item.source_identifier = "/original/id"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_item

        media_repo.update_source_info(
            media_id="item-1",
            file_name="only_name_changed.jpg",
        )

        assert mock_item.file_name == "only_name_changed.jpg"
        # file_path and source_identifier should not be changed
        assert mock_item.file_path == "/original/path.jpg"
        assert mock_item.source_identifier == "/original/id"
        mock_db.commit.assert_called_once()


@pytest.mark.unit
class TestMediaRepositoryBackfillMethods:
    """Tests for backfill-related repository methods added in Phase 05."""

    def test_get_by_instagram_media_id(self, media_repo, mock_db):
        """Returns item by Instagram media ID."""
        mock_item = MagicMock(instagram_media_id="17841405793087218")
        mock_db.query.return_value.filter.return_value.first.return_value = mock_item

        result = media_repo.get_by_instagram_media_id("17841405793087218")

        assert result is mock_item
        mock_db.query.assert_called_with(MediaItem)

    def test_get_by_instagram_media_id_not_found(self, media_repo, mock_db):
        """Returns None when no item with given Instagram media ID."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = media_repo.get_by_instagram_media_id("nonexistent")

        assert result is None

    def test_get_backfilled_instagram_media_ids(self, media_repo, mock_db):
        """Returns set of all backfilled Instagram media IDs."""
        mock_db.query.return_value.filter.return_value.all.return_value = [
            ("id_1",),
            ("id_2",),
            ("id_3",),
        ]

        result = media_repo.get_backfilled_instagram_media_ids()

        assert result == {"id_1", "id_2", "id_3"}

    def test_get_backfilled_instagram_media_ids_empty(self, media_repo, mock_db):
        """Returns empty set when no backfilled items."""
        mock_db.query.return_value.filter.return_value.all.return_value = []

        result = media_repo.get_backfilled_instagram_media_ids()

        assert result == set()


@pytest.mark.unit
class TestGetNextEligibleForPosting:
    """Tests for MediaRepository.get_next_eligible_for_posting().

    This method contains complex multi-table queries with subqueries.
    Full testing requires integration tests with a real database.
    """

    @pytest.mark.skip(
        reason="Integration test - needs real DB to verify multi-table query"
    )
    def test_returns_never_posted_first(self):
        """Integration test: verify never-posted items are prioritized."""
        pass

    @pytest.mark.skip(
        reason="Integration test - needs real DB to verify multi-table query"
    )
    def test_excludes_locked_items(self):
        """Integration test: verify locked items are excluded."""
        pass

    @pytest.mark.skip(
        reason="Integration test - needs real DB to verify multi-table query"
    )
    def test_excludes_queued_items(self):
        """Integration test: verify already-queued items are excluded."""
        pass

    @pytest.mark.skip(
        reason="Integration test - needs real DB to verify multi-table query"
    )
    def test_filters_by_category(self):
        """Integration test: verify category filtering works."""
        pass


@pytest.mark.unit
class TestMediaRepositoryTenantFiltering:
    """Tests for optional chat_settings_id tenant filtering on MediaRepository."""

    TENANT_ID = "tenant-uuid-1"

    def test_get_by_id_with_tenant(self, media_repo, mock_db):
        """get_by_id passes chat_settings_id through tenant filter."""
        with patch.object(
            media_repo, "_apply_tenant_filter", wraps=media_repo._apply_tenant_filter
        ) as mock_filter:
            media_repo.get_by_id("some-id", chat_settings_id=self.TENANT_ID)
            mock_filter.assert_called_once_with(
                mock_db.query.return_value.filter.return_value,
                MediaItem,
                self.TENANT_ID,
            )

    def test_get_by_id_without_tenant(self, media_repo, mock_db):
        """get_by_id works without chat_settings_id (backward compat)."""
        with patch.object(
            media_repo, "_apply_tenant_filter", wraps=media_repo._apply_tenant_filter
        ) as mock_filter:
            media_repo.get_by_id("some-id")
            mock_filter.assert_called_once_with(
                mock_db.query.return_value.filter.return_value,
                MediaItem,
                None,
            )

    def test_get_by_path_with_tenant(self, media_repo, mock_db):
        """get_by_path passes chat_settings_id through tenant filter."""
        with patch.object(
            media_repo, "_apply_tenant_filter", wraps=media_repo._apply_tenant_filter
        ) as mock_filter:
            media_repo.get_by_path("/test/path.jpg", chat_settings_id=self.TENANT_ID)
            mock_filter.assert_called_once()
            assert mock_filter.call_args[0][2] == self.TENANT_ID

    def test_get_by_hash_with_tenant(self, media_repo, mock_db):
        """get_by_hash passes chat_settings_id through tenant filter."""
        with patch.object(
            media_repo, "_apply_tenant_filter", wraps=media_repo._apply_tenant_filter
        ) as mock_filter:
            media_repo.get_by_hash("hash123", chat_settings_id=self.TENANT_ID)
            mock_filter.assert_called_once()
            assert mock_filter.call_args[0][2] == self.TENANT_ID

    def test_get_by_instagram_media_id_with_tenant(self, media_repo, mock_db):
        """get_by_instagram_media_id passes chat_settings_id through."""
        with patch.object(
            media_repo, "_apply_tenant_filter", wraps=media_repo._apply_tenant_filter
        ) as mock_filter:
            media_repo.get_by_instagram_media_id(
                "ig-123", chat_settings_id=self.TENANT_ID
            )
            mock_filter.assert_called_once()
            assert mock_filter.call_args[0][2] == self.TENANT_ID

    def test_get_backfilled_instagram_media_ids_with_tenant(self, media_repo, mock_db):
        """get_backfilled_instagram_media_ids passes chat_settings_id through."""
        mock_db.query.return_value.filter.return_value.all.return_value = []
        with patch.object(
            media_repo, "_apply_tenant_filter", wraps=media_repo._apply_tenant_filter
        ) as mock_filter:
            media_repo.get_backfilled_instagram_media_ids(
                chat_settings_id=self.TENANT_ID
            )
            mock_filter.assert_called_once()
            assert mock_filter.call_args[0][2] == self.TENANT_ID

    def test_get_by_source_identifier_with_tenant(self, media_repo, mock_db):
        """get_by_source_identifier passes chat_settings_id through."""
        with patch.object(
            media_repo, "_apply_tenant_filter", wraps=media_repo._apply_tenant_filter
        ) as mock_filter:
            media_repo.get_by_source_identifier(
                "local", "/path", chat_settings_id=self.TENANT_ID
            )
            mock_filter.assert_called_once()
            assert mock_filter.call_args[0][2] == self.TENANT_ID

    def test_get_active_by_source_type_with_tenant(self, media_repo, mock_db):
        """get_active_by_source_type passes chat_settings_id through."""
        with patch.object(
            media_repo, "_apply_tenant_filter", wraps=media_repo._apply_tenant_filter
        ) as mock_filter:
            media_repo.get_active_by_source_type(
                "local", chat_settings_id=self.TENANT_ID
            )
            mock_filter.assert_called_once()
            assert mock_filter.call_args[0][2] == self.TENANT_ID

    def test_get_inactive_by_source_identifier_with_tenant(self, media_repo, mock_db):
        """get_inactive_by_source_identifier passes chat_settings_id through."""
        with patch.object(
            media_repo, "_apply_tenant_filter", wraps=media_repo._apply_tenant_filter
        ) as mock_filter:
            media_repo.get_inactive_by_source_identifier(
                "local", "/path", chat_settings_id=self.TENANT_ID
            )
            mock_filter.assert_called_once()
            assert mock_filter.call_args[0][2] == self.TENANT_ID

    def test_get_all_with_tenant(self, media_repo, mock_db):
        """get_all passes chat_settings_id through tenant filter."""
        mock_db.query.return_value.all.return_value = []
        with patch.object(
            media_repo, "_apply_tenant_filter", wraps=media_repo._apply_tenant_filter
        ) as mock_filter:
            media_repo.get_all(is_active=True, chat_settings_id=self.TENANT_ID)
            mock_filter.assert_called_once()
            assert mock_filter.call_args[0][2] == self.TENANT_ID

    def test_get_categories_with_tenant(self, media_repo, mock_db):
        """get_categories passes chat_settings_id through tenant filter."""
        mock_db.query.return_value.filter.return_value.distinct.return_value.all.return_value = []
        with patch.object(
            media_repo, "_apply_tenant_filter", wraps=media_repo._apply_tenant_filter
        ) as mock_filter:
            media_repo.get_categories(chat_settings_id=self.TENANT_ID)
            mock_filter.assert_called_once()
            assert mock_filter.call_args[0][2] == self.TENANT_ID

    def test_get_duplicates_with_tenant(self, media_repo, mock_db):
        """get_duplicates passes chat_settings_id through tenant filter."""
        mock_db.query.return_value.having.return_value.all.return_value = []
        with patch.object(
            media_repo, "_apply_tenant_filter", wraps=media_repo._apply_tenant_filter
        ) as mock_filter:
            media_repo.get_duplicates(chat_settings_id=self.TENANT_ID)
            mock_filter.assert_called_once()
            assert mock_filter.call_args[0][2] == self.TENANT_ID

    def test_create_with_tenant(self, media_repo, mock_db):
        """create sets chat_settings_id on the new MediaItem."""
        media_repo.create(
            file_path="/test/image.jpg",
            file_name="image.jpg",
            file_hash="abc123",
            file_size_bytes=102400,
            chat_settings_id=self.TENANT_ID,
        )

        added_item = mock_db.add.call_args[0][0]
        assert added_item.chat_settings_id == self.TENANT_ID

    def test_create_without_tenant(self, media_repo, mock_db):
        """create without chat_settings_id sets None (backward compat)."""
        media_repo.create(
            file_path="/test/image.jpg",
            file_name="image.jpg",
            file_hash="abc123",
            file_size_bytes=102400,
        )

        added_item = mock_db.add.call_args[0][0]
        assert added_item.chat_settings_id is None

    def test_get_next_eligible_with_tenant(self, media_repo, mock_db):
        """get_next_eligible_for_posting passes chat_settings_id to main query."""
        with patch.object(
            media_repo, "_apply_tenant_filter", wraps=media_repo._apply_tenant_filter
        ) as mock_filter:
            media_repo.get_next_eligible_for_posting(chat_settings_id=self.TENANT_ID)
            mock_filter.assert_called_once()
            assert mock_filter.call_args[0][2] == self.TENANT_ID
