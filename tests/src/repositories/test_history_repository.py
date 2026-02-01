"""Tests for HistoryRepository."""

import pytest

from src.repositories.history_repository import HistoryRepository
from src.repositories.media_repository import MediaRepository
from src.repositories.user_repository import UserRepository


@pytest.mark.unit
class TestHistoryRepository:
    """Test suite for HistoryRepository."""

    @pytest.mark.skip(
        reason="TODO: Integration test - needs test_db, convert to unit test or move to integration/"
    )
    def test_create_history_record(self, test_db):
        """Test creating a posting history record."""
        media_repo = MediaRepository(test_db)
        user_repo = UserRepository(test_db)
        history_repo = HistoryRepository(test_db)

        # Create dependencies
        media = media_repo.create(
            file_path="/test/history.jpg",
            file_name="history.jpg",
            file_hash="history123",
            file_size_bytes=100000,
            mime_type="image/jpeg",
        )

        user = user_repo.create(telegram_user_id=400001)

        # Create history record
        history = history_repo.create(
            media_id=media.id,
            posted_by_user_id=user.id,
            status="posted",
            media_snapshot={"file_name": "history.jpg"},
        )

        assert history.id is not None
        assert history.media_id == media.id
        assert history.posted_by_user_id == user.id
        assert history.status == "posted"

    @pytest.mark.skip(
        reason="TODO: Integration test - needs test_db, convert to unit test or move to integration/"
    )
    def test_get_by_media_id(self, test_db):
        """Test retrieving history by media ID."""
        media_repo = MediaRepository(test_db)
        user_repo = UserRepository(test_db)
        history_repo = HistoryRepository(test_db)

        media = media_repo.create(
            file_path="/test/history2.jpg",
            file_name="history2.jpg",
            file_hash="history234",
            file_size_bytes=90000,
            mime_type="image/jpeg",
        )

        user = user_repo.create(telegram_user_id=400002)

        # Create multiple history records
        history_repo.create(
            media_id=media.id, posted_by_user_id=user.id, status="posted"
        )

        records = history_repo.get_by_media_id(media.id)

        assert len(records) >= 1
        assert records[0].media_id == media.id

    @pytest.mark.skip(
        reason="TODO: Integration test - needs test_db, convert to unit test or move to integration/"
    )
    def test_get_by_user_id(self, test_db):
        """Test retrieving history by user ID."""
        media_repo = MediaRepository(test_db)
        user_repo = UserRepository(test_db)
        history_repo = HistoryRepository(test_db)

        media = media_repo.create(
            file_path="/test/history3.jpg",
            file_name="history3.jpg",
            file_hash="history345",
            file_size_bytes=85000,
            mime_type="image/jpeg",
        )

        user = user_repo.create(telegram_user_id=400003)

        history_repo.create(
            media_id=media.id, posted_by_user_id=user.id, status="posted"
        )

        records = history_repo.get_by_user_id(user.id)

        assert len(records) >= 1
        assert records[0].posted_by_user_id == user.id

    @pytest.mark.skip(
        reason="TODO: Integration test - needs test_db, convert to unit test or move to integration/"
    )
    def test_get_stats(self, test_db):
        """Test getting posting statistics."""
        media_repo = MediaRepository(test_db)
        user_repo = UserRepository(test_db)
        history_repo = HistoryRepository(test_db)

        media = media_repo.create(
            file_path="/test/stats.jpg",
            file_name="stats.jpg",
            file_hash="stats123",
            file_size_bytes=95000,
            mime_type="image/jpeg",
        )

        user = user_repo.create(telegram_user_id=400004)

        # Create posted record
        history_repo.create(
            media_id=media.id, posted_by_user_id=user.id, status="posted"
        )

        stats = history_repo.get_stats()

        assert stats["total_posts"] >= 1
        assert stats["total_users"] >= 1

    @pytest.mark.skip(
        reason="TODO: Integration test - needs test_db, convert to unit test or move to integration/"
    )
    def test_get_recent(self, test_db):
        """Test getting recent posting history."""
        media_repo = MediaRepository(test_db)
        user_repo = UserRepository(test_db)
        history_repo = HistoryRepository(test_db)

        media = media_repo.create(
            file_path="/test/recent.jpg",
            file_name="recent.jpg",
            file_hash="recent123",
            file_size_bytes=80000,
            mime_type="image/jpeg",
        )

        user = user_repo.create(telegram_user_id=400005)

        history_repo.create(
            media_id=media.id, posted_by_user_id=user.id, status="posted"
        )

        recent = history_repo.get_recent(days=7, limit=10)

        assert len(recent) >= 1

    @pytest.mark.skip(
        reason="TODO: Integration test - needs test_db, convert to unit test or move to integration/"
    )
    def test_list_all_with_filters(self, test_db):
        """Test listing history with status filter."""
        media_repo = MediaRepository(test_db)
        user_repo = UserRepository(test_db)
        history_repo = HistoryRepository(test_db)

        media1 = media_repo.create(
            file_path="/test/filter_posted.jpg",
            file_name="filter_posted.jpg",
            file_hash="filter_p123",
            file_size_bytes=70000,
            mime_type="image/jpeg",
        )

        media2 = media_repo.create(
            file_path="/test/filter_skipped.jpg",
            file_name="filter_skipped.jpg",
            file_hash="filter_s123",
            file_size_bytes=75000,
            mime_type="image/jpeg",
        )

        user = user_repo.create(telegram_user_id=400006)

        history_repo.create(
            media_id=media1.id, posted_by_user_id=user.id, status="posted"
        )

        history_repo.create(
            media_id=media2.id, posted_by_user_id=user.id, status="skipped"
        )

        # Filter by status
        posted_records = history_repo.list_all(status="posted", limit=10)
        posted_statuses = [r.status for r in posted_records]

        assert all(status == "posted" for status in posted_statuses)
