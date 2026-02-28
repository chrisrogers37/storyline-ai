"""Tests for BaseRepository."""

import pytest
from unittest.mock import MagicMock, patch

from src.repositories.base_repository import BaseRepository


@pytest.mark.unit
class TestBaseRepository:
    """Test suite for BaseRepository."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return MagicMock()

    @pytest.fixture
    def repo(self, mock_db):
        """Create BaseRepository with mocked database."""
        with patch("src.repositories.base_repository.get_db") as mock_get_db:
            mock_get_db.return_value = iter([mock_db])
            repo = BaseRepository()
            repo._db = mock_db
            return repo

    def test_init_creates_session(self):
        """Test that __init__ creates a database session from get_db()."""
        mock_session = MagicMock()
        with patch("src.repositories.base_repository.get_db") as mock_get_db:
            mock_get_db.return_value = iter([mock_session])
            repo = BaseRepository()

        assert repo._db is mock_session

    def test_db_property_returns_session(self, repo, mock_db):
        """Test that db property returns the session."""
        mock_db.is_active = True
        result = repo.db
        assert result is mock_db

    def test_db_property_rollback_on_inactive(self, repo, mock_db):
        """Test that db property rolls back when session is not active."""
        mock_db.is_active = False
        _ = repo.db
        mock_db.rollback.assert_called_once()

    def test_db_property_creates_new_session_when_rollback_fails(self, repo, mock_db):
        """Test that db property creates a fresh session if rollback fails (severed connection)."""
        mock_db.is_active = False
        mock_db.rollback.side_effect = Exception("connection is closed")

        new_session = MagicMock()
        with patch("src.repositories.base_repository.get_db") as mock_get_db:
            mock_get_db.return_value = iter([new_session])
            result = repo.db

        assert result is new_session
        mock_db.close.assert_called_once()

    def test_commit_calls_session_commit(self, repo, mock_db):
        """Test that commit() delegates to session.commit()."""
        repo.commit()
        mock_db.commit.assert_called_once()

    def test_commit_rollback_on_error(self, repo, mock_db):
        """Test that commit() rolls back and re-raises on error."""
        mock_db.commit.side_effect = Exception("Commit failed")

        with pytest.raises(Exception, match="Commit failed"):
            repo.commit()

        mock_db.rollback.assert_called_once()

    def test_rollback_calls_session_rollback(self, repo, mock_db):
        """Test that rollback() delegates to session.rollback()."""
        repo.rollback()
        mock_db.rollback.assert_called_once()

    def test_rollback_suppresses_error(self, repo, mock_db):
        """Test that rollback() does not raise if session.rollback fails."""
        mock_db.rollback.side_effect = Exception("Rollback failed")
        # Should NOT raise
        repo.rollback()

    def test_end_read_transaction_commits(self, repo, mock_db):
        """Test that end_read_transaction() commits to release locks."""
        repo.end_read_transaction()
        mock_db.commit.assert_called_once()

    def test_end_read_transaction_rollback_on_error(self, repo, mock_db):
        """Test that end_read_transaction() falls back to rollback."""
        mock_db.commit.side_effect = Exception("Read commit failed")
        # Should NOT raise
        repo.end_read_transaction()
        mock_db.rollback.assert_called_once()

    def test_close_calls_session_close(self, repo, mock_db):
        """Test that close() calls session.close()."""
        repo.close()
        mock_db.close.assert_called_once()

    def test_context_manager_enter_returns_self(self, repo):
        """Test that __enter__ returns the repository instance."""
        result = repo.__enter__()
        assert result is repo

    def test_context_manager_exit_calls_close(self, repo, mock_db):
        """Test that __exit__ calls close()."""
        repo.__exit__(None, None, None)
        mock_db.close.assert_called_once()

    def test_context_manager_does_not_suppress_exceptions(self, repo):
        """Test that __exit__ returns False (does not suppress exceptions)."""
        result = repo.__exit__(ValueError, ValueError("test"), None)
        assert result is False

    def test_apply_tenant_filter_with_id(self, repo):
        """Test _apply_tenant_filter adds filter when chat_settings_id provided."""
        mock_query = MagicMock()
        mock_model = MagicMock()

        result = repo._apply_tenant_filter(mock_query, mock_model, "tenant-1")

        mock_query.filter.assert_called_once()
        assert result is mock_query.filter.return_value

    def test_apply_tenant_filter_without_id(self, repo):
        """Test _apply_tenant_filter is no-op when chat_settings_id is None."""
        mock_query = MagicMock()
        mock_model = MagicMock()

        result = repo._apply_tenant_filter(mock_query, mock_model, None)

        mock_query.filter.assert_not_called()
        assert result is mock_query

    def test_tenant_query_calls_db_query_and_apply_filter(self, repo, mock_db):
        """Test _tenant_query combines db.query() with _apply_tenant_filter()."""
        mock_db.is_active = True
        mock_model = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query

        with patch.object(
            repo, "_apply_tenant_filter", return_value=mock_query
        ) as mock_filter:
            result = repo._tenant_query(mock_model, chat_settings_id="tenant-1")

        mock_db.query.assert_called_once_with(mock_model)
        mock_filter.assert_called_once_with(mock_query, mock_model, "tenant-1")
        assert result is mock_query

    def test_tenant_query_without_chat_settings_id(self, repo, mock_db):
        """Test _tenant_query passes None to _apply_tenant_filter when no tenant."""
        mock_db.is_active = True
        mock_model = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query

        with patch.object(
            repo, "_apply_tenant_filter", return_value=mock_query
        ) as mock_filter:
            result = repo._tenant_query(mock_model)

        mock_db.query.assert_called_once_with(mock_model)
        mock_filter.assert_called_once_with(mock_query, mock_model, None)
        assert result is mock_query

    def test_tenant_query_returns_chainable_query(self, repo, mock_db):
        """Test _tenant_query returns a query object that supports chaining."""
        mock_db.is_active = True
        mock_model = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query

        with patch.object(repo, "_apply_tenant_filter", return_value=mock_query):
            result = repo._tenant_query(mock_model, "tenant-1")

        # Verify chaining works (filter, order_by, etc.)
        result.filter.assert_not_called()  # Not called yet, but should be callable
        chained = result.filter(mock_model.id == "test")
        assert chained is mock_query.filter.return_value

    def test_check_connection_executes_query(self):
        """Test that check_connection() executes a SELECT 1 query."""
        mock_session = MagicMock()
        with patch("src.repositories.base_repository.get_db") as mock_get_db:
            mock_get_db.return_value = iter([mock_session])
            BaseRepository.check_connection()

        mock_session.execute.assert_called_once()
        mock_session.close.assert_called_once()
