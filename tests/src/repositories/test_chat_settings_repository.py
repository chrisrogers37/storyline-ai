"""Tests for ChatSettingsRepository."""

import pytest
from unittest.mock import Mock, MagicMock, patch

from src.repositories.chat_settings_repository import ChatSettingsRepository
from src.models.chat_settings import ChatSettings


@pytest.mark.unit
class TestChatSettingsRepository:
    """Test suite for ChatSettingsRepository."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return MagicMock()

    @pytest.fixture
    def settings_repo(self, mock_db):
        """Create ChatSettingsRepository with mocked database."""
        with patch("src.repositories.base_repository.get_db") as mock_get_db:
            mock_get_db.return_value = iter([mock_db])
            repo = ChatSettingsRepository()
            repo._db = mock_db
            return repo

    def test_get_by_chat_id_found(self, settings_repo, mock_db):
        """Test getting settings for an existing chat."""
        mock_settings = Mock(spec=ChatSettings)
        mock_settings.telegram_chat_id = -100123
        mock_db.query.return_value.filter.return_value.first.return_value = (
            mock_settings
        )

        result = settings_repo.get_by_chat_id(-100123)

        assert result is mock_settings
        mock_db.commit.assert_called_once()  # end_read_transaction

    def test_get_by_chat_id_not_found(self, settings_repo, mock_db):
        """Test getting settings for non-existent chat returns None."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = settings_repo.get_by_chat_id(-999999)

        assert result is None

    @patch("src.repositories.chat_settings_repository.env_settings")
    def test_get_or_create_returns_existing(self, mock_env, settings_repo, mock_db):
        """Test get_or_create returns existing record without creating."""
        mock_settings = Mock(spec=ChatSettings)
        mock_db.query.return_value.filter.return_value.first.return_value = (
            mock_settings
        )

        result = settings_repo.get_or_create(-100123)

        assert result is mock_settings
        mock_db.add.assert_not_called()

    @patch("src.repositories.chat_settings_repository.env_settings")
    def test_get_or_create_bootstraps_from_env(self, mock_env, settings_repo, mock_db):
        """Test get_or_create creates new record from .env defaults."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        mock_env.DRY_RUN_MODE = True
        mock_env.ENABLE_INSTAGRAM_API = False
        mock_env.POSTS_PER_DAY = 3
        mock_env.POSTING_HOURS_START = 9
        mock_env.POSTING_HOURS_END = 22

        settings_repo.get_or_create(-100123)

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()

        added_obj = mock_db.add.call_args[0][0]
        assert isinstance(added_obj, ChatSettings)
        assert added_obj.telegram_chat_id == -100123
        assert added_obj.dry_run_mode is True
        assert added_obj.posts_per_day == 3

    def test_update_modifies_fields(self, settings_repo, mock_db):
        """Test update modifies specified fields on existing record."""
        mock_settings = Mock(spec=ChatSettings)
        mock_settings.dry_run_mode = False
        mock_settings.is_paused = False
        mock_db.query.return_value.filter.return_value.first.return_value = (
            mock_settings
        )

        settings_repo.update(-100123, dry_run_mode=True, is_paused=True)

        assert mock_settings.dry_run_mode is True
        assert mock_settings.is_paused is True
        mock_db.commit.assert_called()

    def test_set_paused_tracks_user(self, settings_repo, mock_db):
        """Test set_paused records who paused and when."""
        mock_settings = Mock(spec=ChatSettings)
        mock_db.query.return_value.filter.return_value.first.return_value = (
            mock_settings
        )

        settings_repo.set_paused(-100123, is_paused=True, user_id="user-uuid-1")

        assert mock_settings.is_paused is True
        assert mock_settings.paused_by_user_id == "user-uuid-1"
        assert mock_settings.paused_at is not None

    def test_set_unpaused_clears_tracking(self, settings_repo, mock_db):
        """Test set_paused(False) clears pause tracking fields."""
        mock_settings = Mock(spec=ChatSettings)
        mock_settings.is_paused = True
        mock_settings.paused_by_user_id = "user-uuid-1"
        mock_db.query.return_value.filter.return_value.first.return_value = (
            mock_settings
        )

        settings_repo.set_paused(-100123, is_paused=False)

        assert mock_settings.is_paused is False
        assert mock_settings.paused_by_user_id is None
        assert mock_settings.paused_at is None

    def test_get_all_active_returns_unpaused_chats(self, settings_repo, mock_db):
        """get_all_active returns only non-paused ChatSettings."""
        mock_chat1 = Mock(spec=ChatSettings, is_paused=False)
        mock_chat2 = Mock(spec=ChatSettings, is_paused=False)
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value.order_by.return_value.all.return_value = [
            mock_chat1,
            mock_chat2,
        ]

        result = settings_repo.get_all_active()

        assert len(result) == 2
        mock_db.query.assert_called_with(ChatSettings)
        mock_db.commit.assert_called_once()  # end_read_transaction

    def test_get_all_active_returns_empty_when_all_paused(self, settings_repo, mock_db):
        """get_all_active returns empty list when all chats are paused."""
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value.order_by.return_value.all.return_value = []

        result = settings_repo.get_all_active()

        assert result == []

    def test_get_all_active_returns_empty_when_no_records(self, settings_repo, mock_db):
        """get_all_active returns empty list when no chat_settings exist."""
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value.order_by.return_value.all.return_value = []

        result = settings_repo.get_all_active()

        assert result == []
