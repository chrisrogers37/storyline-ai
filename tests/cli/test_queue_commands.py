"""Tests for queue CLI commands."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from click.testing import CliRunner

from cli.commands.queue import list_queue, reset_queue, queue_preview


@pytest.mark.unit
class TestListQueueCommand:
    """Tests for the list-queue CLI command."""

    @patch("cli.commands.queue.DashboardService")
    def test_list_queue_shows_items(self, mock_service_class):
        """Test list-queue displays in-flight items in a table."""
        from datetime import datetime

        mock_service = MagicMock()
        mock_service_class.return_value.__enter__ = Mock(return_value=mock_service)
        mock_service_class.return_value.__exit__ = Mock(return_value=False)

        mock_service.get_pending_queue_items.return_value = [
            {
                "scheduled_for": datetime(2026, 2, 15, 10, 0),
                "file_name": "queue_list.jpg",
                "category": "memes",
                "status": "processing",
            }
        ]

        runner = CliRunner()
        result = runner.invoke(list_queue, [])

        assert result.exit_code == 0
        assert "queue_list.jpg" in result.output
        assert "memes" in result.output

    @patch("cli.commands.queue.DashboardService")
    def test_list_queue_empty(self, mock_service_class):
        """Test list-queue shows message when queue is empty."""
        mock_service = MagicMock()
        mock_service_class.return_value.__enter__ = Mock(return_value=mock_service)
        mock_service_class.return_value.__exit__ = Mock(return_value=False)

        mock_service.get_pending_queue_items.return_value = []

        runner = CliRunner()
        result = runner.invoke(list_queue, [])

        assert result.exit_code == 0
        assert "Queue is empty" in result.output


@pytest.mark.unit
class TestResetQueueCommand:
    """Tests for the reset-queue CLI command."""

    @patch("cli.commands.queue.SchedulerService")
    def test_reset_queue_empty(self, mock_service_class):
        """Test reset-queue when queue is already empty."""
        mock_service = MagicMock()
        mock_service_class.return_value.__enter__ = Mock(return_value=mock_service)
        mock_service_class.return_value.__exit__ = Mock(return_value=False)
        mock_service.count_pending.return_value = 0

        runner = CliRunner()
        result = runner.invoke(reset_queue, [])

        assert result.exit_code == 0
        assert "already empty" in result.output

    @patch("cli.commands.queue.SchedulerService")
    def test_reset_queue_with_yes_flag(self, mock_service_class):
        """Test reset-queue --yes skips confirmation."""
        mock_service = MagicMock()
        mock_service_class.return_value.__enter__ = Mock(return_value=mock_service)
        mock_service_class.return_value.__exit__ = Mock(return_value=False)
        mock_service.count_pending.return_value = 3
        mock_service.clear_pending_queue.return_value = 3

        runner = CliRunner()
        result = runner.invoke(reset_queue, ["--yes"])

        assert result.exit_code == 0
        assert "Cleared 3 items" in result.output


@pytest.mark.unit
class TestQueuePreviewCommand:
    """Tests for the queue-preview CLI command."""

    @patch("cli.commands.queue.SchedulerService")
    def test_queue_preview_shows_items(self, mock_service_class):
        """Test queue-preview displays upcoming selections."""
        mock_service = MagicMock()
        mock_service_class.return_value.__enter__ = Mock(return_value=mock_service)
        mock_service_class.return_value.__exit__ = Mock(return_value=False)
        mock_service.get_queue_preview.return_value = [
            {"media_id": "id-1", "file_name": "preview1.jpg", "category": "memes"},
            {"media_id": "id-2", "file_name": "preview2.jpg", "category": "merch"},
        ]

        runner = CliRunner()
        result = runner.invoke(queue_preview, [])

        assert result.exit_code == 0
        assert "preview1.jpg" in result.output
        assert "preview2.jpg" in result.output

    @patch("cli.commands.queue.SchedulerService")
    def test_queue_preview_empty(self, mock_service_class):
        """Test queue-preview when no eligible media."""
        mock_service = MagicMock()
        mock_service_class.return_value.__enter__ = Mock(return_value=mock_service)
        mock_service_class.return_value.__exit__ = Mock(return_value=False)
        mock_service.get_queue_preview.return_value = []

        runner = CliRunner()
        result = runner.invoke(queue_preview, [])

        assert result.exit_code == 0
        assert "No eligible media" in result.output
