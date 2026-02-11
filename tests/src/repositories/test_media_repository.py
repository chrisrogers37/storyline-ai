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
