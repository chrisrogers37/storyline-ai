"""Tests for queue CLI commands."""

import pytest
from click.testing import CliRunner
from datetime import datetime

from cli.commands.queue import create_schedule, list_queue, process_queue
from src.repositories.media_repository import MediaRepository
from src.repositories.user_repository import UserRepository
from src.repositories.queue_repository import QueueRepository


@pytest.mark.unit
class TestQueueCommands:
    """Test suite for queue CLI commands."""

    def test_create_schedule_command(self, test_db):
        """Test create-schedule CLI command."""
        media_repo = MediaRepository(test_db)
        user_repo = UserRepository(test_db)

        # Create test data
        media_repo.create(
            file_path="/test/schedule_cmd.jpg",
            file_name="schedule_cmd.jpg",
            file_hash="schedule_cmd_hash",
            file_size_bytes=100000,
            mime_type="image/jpeg",
        )

        user_repo.create(telegram_user_id=2000001)

        runner = CliRunner()
        result = runner.invoke(create_schedule, ["--days", "1", "--posts-per-day", "2"])

        # Command should execute successfully
        assert result.exit_code == 0
        assert "schedule" in result.output.lower() or "queued" in result.output.lower()

    def test_create_schedule_no_media(self, test_db):
        """Test create-schedule with no available media."""
        runner = CliRunner()

        result = runner.invoke(create_schedule, ["--days", "1"])

        # Should handle gracefully (may warn about no media)
        # Exit code may be 0 or non-zero depending on implementation
        assert "no media" in result.output.lower() or result.exit_code == 0

    def test_list_queue_command(self, test_db):
        """Test list-queue CLI command."""
        media_repo = MediaRepository(test_db)
        user_repo = UserRepository(test_db)
        queue_repo = QueueRepository(test_db)

        # Create test queue item
        media = media_repo.create(
            file_path="/test/queue_list.jpg",
            file_name="queue_list.jpg",
            file_hash="queue_list_hash",
            file_size_bytes=95000,
            mime_type="image/jpeg",
        )

        user = user_repo.create(telegram_user_id=2000002)

        queue_repo.create(
            media_id=media.id,
            scheduled_user_id=user.id,
            scheduled_time=datetime.utcnow(),
        )

        runner = CliRunner()
        result = runner.invoke(list_queue, [])

        # Command should execute successfully
        assert result.exit_code == 0

    def test_list_queue_with_status_filter(self, test_db):
        """Test list-queue with status filter."""
        media_repo = MediaRepository(test_db)
        user_repo = UserRepository(test_db)
        queue_repo = QueueRepository(test_db)

        media = media_repo.create(
            file_path="/test/status_filter.jpg",
            file_name="status_filter.jpg",
            file_hash="status_filter_hash",
            file_size_bytes=90000,
            mime_type="image/jpeg",
        )

        user = user_repo.create(telegram_user_id=2000003)

        queue_repo.create(
            media_id=media.id,
            scheduled_user_id=user.id,
            scheduled_time=datetime.utcnow(),
        )

        runner = CliRunner()
        result = runner.invoke(list_queue, ["--status", "pending"])

        assert result.exit_code == 0

    def test_process_queue_command(self, test_db):
        """Test process-queue CLI command."""
        media_repo = MediaRepository(test_db)
        user_repo = UserRepository(test_db)
        queue_repo = QueueRepository(test_db)

        # Create pending queue item
        media = media_repo.create(
            file_path="/test/process.jpg",
            file_name="process.jpg",
            file_hash="process_hash",
            file_size_bytes=85000,
            mime_type="image/jpeg",
        )

        user = user_repo.create(telegram_user_id=2000004)

        queue_repo.create(
            media_id=media.id,
            scheduled_user_id=user.id,
            scheduled_time=datetime.utcnow(),
        )

        runner = CliRunner()
        result = runner.invoke(process_queue, [])

        # Command should execute successfully
        assert result.exit_code == 0
