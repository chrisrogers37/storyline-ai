"""Tests for HistoryRepository."""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

from sqlalchemy.orm import Session

from src.repositories.history_repository import HistoryRepository, HistoryCreateParams
from src.models.posting_history import PostingHistory


@pytest.fixture
def mock_db():
    """Create a mock database session with chainable query."""
    session = MagicMock(spec=Session)
    mock_query = MagicMock()
    session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.limit.return_value = mock_query
    return session


@pytest.fixture
def history_repo(mock_db):
    """Create HistoryRepository with mocked database session."""
    with patch.object(HistoryRepository, "__init__", lambda self: None):
        repo = HistoryRepository()
        repo._db = mock_db
        return repo


@pytest.mark.unit
class TestHistoryRepository:
    """Test suite for HistoryRepository."""

    def test_create_history_record(self, history_repo, mock_db):
        """Test creating a posting history record using HistoryCreateParams."""
        now = datetime.utcnow()
        params = HistoryCreateParams(
            media_item_id="some-media-id",
            queue_item_id="some-queue-id",
            queue_created_at=now,
            queue_deleted_at=now,
            scheduled_for=now,
            posted_at=now,
            status="posted",
            success=True,
            posted_by_user_id="some-user-id",
            media_metadata={"file_name": "history.jpg"},
        )

        history_repo.create(params)

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()

        added = mock_db.add.call_args[0][0]
        assert isinstance(added, PostingHistory)
        assert added.media_item_id == "some-media-id"
        assert added.status == "posted"
        assert added.success is True
        assert added.posted_by_user_id == "some-user-id"

    def test_get_by_media_id(self, history_repo, mock_db):
        """Test retrieving history by media ID."""
        mock_records = [MagicMock(media_item_id="some-media-id")]
        mock_query = mock_db.query.return_value
        mock_query.all.return_value = mock_records

        result = history_repo.get_by_media_id("some-media-id")

        assert len(result) == 1
        assert result[0].media_item_id == "some-media-id"
        mock_db.query.assert_called_with(PostingHistory)

    def test_get_all_with_filters(self, history_repo, mock_db):
        """Test listing history with status filter."""
        mock_records = [
            MagicMock(status="posted"),
            MagicMock(status="posted"),
        ]
        mock_query = mock_db.query.return_value
        mock_query.all.return_value = mock_records

        result = history_repo.get_all(status="posted", days=7, limit=10)

        assert len(result) == 2
        mock_db.query.assert_called_with(PostingHistory)

    def test_get_recent_posts(self, history_repo, mock_db):
        """Test getting posts from the last N hours."""
        mock_records = [MagicMock(), MagicMock()]
        mock_query = mock_db.query.return_value
        mock_query.all.return_value = mock_records

        result = history_repo.get_recent_posts(hours=24)

        assert len(result) == 2


@pytest.mark.unit
class TestHistoryRepositoryTenantFiltering:
    """Tests for optional chat_settings_id tenant filtering on HistoryRepository."""

    TENANT_ID = "tenant-uuid-1"

    def test_history_create_params_has_chat_settings_id(self):
        """HistoryCreateParams dataclass accepts chat_settings_id field."""
        now = datetime.utcnow()
        params = HistoryCreateParams(
            media_item_id="m-1",
            queue_item_id="q-1",
            queue_created_at=now,
            queue_deleted_at=now,
            scheduled_for=now,
            posted_at=now,
            status="posted",
            success=True,
            chat_settings_id=self.TENANT_ID,
        )
        assert params.chat_settings_id == self.TENANT_ID

    def test_history_create_params_defaults_to_none(self):
        """HistoryCreateParams chat_settings_id defaults to None."""
        now = datetime.utcnow()
        params = HistoryCreateParams(
            media_item_id="m-1",
            queue_item_id="q-1",
            queue_created_at=now,
            queue_deleted_at=now,
            scheduled_for=now,
            posted_at=now,
            status="posted",
            success=True,
        )
        assert params.chat_settings_id is None

    def test_create_passes_tenant_through_params(self, history_repo, mock_db):
        """create passes chat_settings_id from HistoryCreateParams to model."""
        now = datetime.utcnow()
        params = HistoryCreateParams(
            media_item_id="m-1",
            queue_item_id="q-1",
            queue_created_at=now,
            queue_deleted_at=now,
            scheduled_for=now,
            posted_at=now,
            status="posted",
            success=True,
            chat_settings_id=self.TENANT_ID,
        )
        history_repo.create(params)

        added = mock_db.add.call_args[0][0]
        assert added.chat_settings_id == self.TENANT_ID

    def test_get_by_id_with_tenant(self, history_repo, mock_db):
        """get_by_id passes chat_settings_id through tenant filter."""
        with patch.object(history_repo, "_apply_tenant_filter", wraps=history_repo._apply_tenant_filter) as mock_filter:
            history_repo.get_by_id("h-1", chat_settings_id=self.TENANT_ID)
            mock_filter.assert_called_once()
            assert mock_filter.call_args[0][2] == self.TENANT_ID

    def test_get_all_with_tenant(self, history_repo, mock_db):
        """get_all passes chat_settings_id through tenant filter."""
        mock_db.query.return_value.all.return_value = []
        with patch.object(history_repo, "_apply_tenant_filter", wraps=history_repo._apply_tenant_filter) as mock_filter:
            history_repo.get_all(chat_settings_id=self.TENANT_ID)
            mock_filter.assert_called_once()
            assert mock_filter.call_args[0][2] == self.TENANT_ID

    def test_get_by_media_id_with_tenant(self, history_repo, mock_db):
        """get_by_media_id passes chat_settings_id through tenant filter."""
        mock_db.query.return_value.all.return_value = []
        with patch.object(history_repo, "_apply_tenant_filter", wraps=history_repo._apply_tenant_filter) as mock_filter:
            history_repo.get_by_media_id("m-1", chat_settings_id=self.TENANT_ID)
            mock_filter.assert_called_once()
            assert mock_filter.call_args[0][2] == self.TENANT_ID

    def test_get_recent_posts_with_tenant(self, history_repo, mock_db):
        """get_recent_posts passes chat_settings_id through tenant filter."""
        mock_db.query.return_value.all.return_value = []
        with patch.object(history_repo, "_apply_tenant_filter", wraps=history_repo._apply_tenant_filter) as mock_filter:
            history_repo.get_recent_posts(hours=24, chat_settings_id=self.TENANT_ID)
            mock_filter.assert_called_once()
            assert mock_filter.call_args[0][2] == self.TENANT_ID

    def test_count_by_method_with_tenant(self, history_repo, mock_db):
        """count_by_method passes chat_settings_id through tenant filter."""
        now = datetime.utcnow()
        with patch.object(history_repo, "_apply_tenant_filter", wraps=history_repo._apply_tenant_filter) as mock_filter:
            history_repo.count_by_method("instagram_api", now, chat_settings_id=self.TENANT_ID)
            mock_filter.assert_called_once()
            assert mock_filter.call_args[0][2] == self.TENANT_ID
