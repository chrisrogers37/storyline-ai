"""Tests for queue CLI commands."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from click.testing import CliRunner

from cli.commands.queue import create_schedule, list_queue, process_queue


@pytest.mark.unit
class TestCreateScheduleCommand:
    """Tests for the create-schedule CLI command."""

    @patch("cli.commands.queue.SchedulerService")
    def test_create_schedule_success(self, mock_service_class):
        """Test create-schedule successfully creates a schedule."""
        mock_service = mock_service_class.return_value
        mock_service.create_schedule.return_value = {
            "scheduled": 6,
            "skipped": 0,
            "total_slots": 6,
            "category_breakdown": {"memes": 4, "merch": 2},
        }

        runner = CliRunner()
        result = runner.invoke(create_schedule, ["--days", "1"])

        assert result.exit_code == 0
        assert "Schedule created" in result.output
        assert "Scheduled: 6" in result.output
        mock_service.create_schedule.assert_called_once_with(days=1)

    @patch("cli.commands.queue.SchedulerService")
    def test_create_schedule_no_media(self, mock_service_class):
        """Test create-schedule when service raises exception due to no media."""
        mock_service = mock_service_class.return_value
        mock_service.create_schedule.side_effect = ValueError(
            "No eligible media items available"
        )

        runner = CliRunner()
        result = runner.invoke(create_schedule, ["--days", "1"])

        assert result.exit_code != 0
        assert "No eligible media" in result.output or "Error" in result.output

    @patch("cli.commands.queue.SchedulerService")
    def test_create_schedule_default_days(self, mock_service_class):
        """Test create-schedule uses default of 7 days."""
        mock_service = mock_service_class.return_value
        mock_service.create_schedule.return_value = {
            "scheduled": 21,
            "skipped": 0,
            "total_slots": 21,
        }

        runner = CliRunner()
        result = runner.invoke(create_schedule, [])

        assert result.exit_code == 0
        mock_service.create_schedule.assert_called_once_with(days=7)


@pytest.mark.unit
class TestListQueueCommand:
    """Tests for the list-queue CLI command."""

    @patch("src.repositories.media_repository.MediaRepository")
    @patch("cli.commands.queue.QueueRepository")
    def test_list_queue_shows_items(self, mock_queue_class, mock_media_class):
        """Test list-queue displays pending items in a table."""
        from datetime import datetime

        mock_queue_repo = mock_queue_class.return_value
        mock_media_repo = mock_media_class.return_value

        mock_queue_item = Mock()
        mock_queue_item.media_item_id = "media-uuid-1"
        mock_queue_item.scheduled_for = datetime(2026, 2, 15, 10, 0)
        mock_queue_item.status = "pending"

        mock_queue_repo.get_all.return_value = [mock_queue_item]

        mock_media = Mock()
        mock_media.file_name = "queue_list.jpg"
        mock_media.category = "memes"
        mock_media_repo.get_by_id.return_value = mock_media

        runner = CliRunner()
        result = runner.invoke(list_queue, [])

        assert result.exit_code == 0
        assert "queue_list.jpg" in result.output
        assert "memes" in result.output
        assert "pending" in result.output
        mock_queue_repo.get_all.assert_called_once_with(status="pending")

    @patch("src.repositories.media_repository.MediaRepository")
    @patch("cli.commands.queue.QueueRepository")
    def test_list_queue_empty(self, mock_queue_class, mock_media_class):
        """Test list-queue shows message when queue is empty."""
        mock_queue_repo = mock_queue_class.return_value
        mock_queue_repo.get_all.return_value = []

        runner = CliRunner()
        result = runner.invoke(list_queue, [])

        assert result.exit_code == 0
        assert "Queue is empty" in result.output


@pytest.mark.unit
class TestProcessQueueCommand:
    """Tests for the process-queue CLI command."""

    @patch("cli.commands.queue.PostingService")
    def test_process_queue_success(self, mock_service_class):
        """Test process-queue processes pending items."""
        mock_service = mock_service_class.return_value
        mock_service.process_pending_posts = AsyncMock(
            return_value={
                "processed": 3,
                "telegram": 3,
                "failed": 0,
            }
        )

        runner = CliRunner()
        result = runner.invoke(process_queue, [])

        assert result.exit_code == 0
        assert "Processing complete" in result.output
        assert "Processed: 3" in result.output

    @patch("cli.commands.queue.PostingService")
    def test_process_queue_force(self, mock_service_class):
        """Test process-queue --force posts next item immediately."""
        mock_service = mock_service_class.return_value

        mock_media = Mock()
        mock_media.file_name = "force_post.jpg"

        mock_service.force_post_next = AsyncMock(
            return_value={
                "success": True,
                "media_item": mock_media,
                "queue_item_id": "queue-uuid-1",
                "shifted_count": 2,
            }
        )

        runner = CliRunner()
        result = runner.invoke(process_queue, ["--force"])

        assert result.exit_code == 0
        assert "Force-posted successfully" in result.output
        assert "force_post.jpg" in result.output
        assert "Shifted 2 items forward" in result.output
