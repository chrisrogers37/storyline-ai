"""Tests for logger utility."""

import pytest
import logging
import tempfile
from pathlib import Path

from src.utils.logger import setup_logger, get_logger


@pytest.mark.unit
class TestLogger:
    """Test suite for logger utility."""

    def test_setup_logger_creates_logger(self):
        """Test that setup_logger creates a logger instance."""
        logger = setup_logger("test_logger")

        assert isinstance(logger, logging.Logger)
        assert logger.name == "test_logger"

    def test_setup_logger_with_custom_level(self):
        """Test setting custom log level."""
        logger = setup_logger("test_custom_level", level=logging.WARNING)

        assert logger.level == logging.WARNING

    def test_setup_logger_creates_log_directory(self):
        """Test that setup_logger creates log directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "test_logs" / "test.log"

            setup_logger("test_dir", log_file=str(log_file))

            assert log_file.parent.exists()

    def test_get_logger_returns_existing_logger(self):
        """Test that get_logger returns existing logger."""
        # Create logger
        logger1 = setup_logger("existing_logger")

        # Get same logger
        logger2 = get_logger("existing_logger")

        assert logger1 is logger2

    def test_get_logger_creates_new_logger(self):
        """Test that get_logger creates new logger if it doesn't exist."""
        logger = get_logger("new_logger")

        assert isinstance(logger, logging.Logger)
        assert logger.name == "new_logger"

    def test_logger_writes_to_file(self):
        """Test that logger writes messages to file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "test.log"

            logger = setup_logger(
                "file_logger", level=logging.INFO, log_file=str(log_file)
            )

            test_message = "Test log message"
            logger.info(test_message)

            # Read log file
            assert log_file.exists()
            with open(log_file, "r") as f:
                content = f.read()
                assert test_message in content

    def test_logger_respects_level(self):
        """Test that logger respects log level filtering."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "level_test.log"

            logger = setup_logger(
                "level_logger", level=logging.WARNING, log_file=str(log_file)
            )

            # Log at different levels
            logger.debug("Debug message")
            logger.info("Info message")
            logger.warning("Warning message")
            logger.error("Error message")

            # Read log file
            with open(log_file, "r") as f:
                content = f.read()

                # DEBUG and INFO should not be logged
                assert "Debug message" not in content
                assert "Info message" not in content

                # WARNING and ERROR should be logged
                assert "Warning message" in content
                assert "Error message" in content

    def test_logger_includes_timestamp(self):
        """Test that log messages include timestamp."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "timestamp_test.log"

            logger = setup_logger("timestamp_logger", log_file=str(log_file))

            logger.info("Timestamped message")

            # Read log file
            with open(log_file, "r") as f:
                content = f.read()

                # Check for timestamp pattern (YYYY-MM-DD HH:MM:SS)
                import re

                timestamp_pattern = r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}"
                assert re.search(timestamp_pattern, content) is not None

    def test_logger_includes_level_name(self):
        """Test that log messages include level name."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "level_name_test.log"

            logger = setup_logger("level_name_logger", log_file=str(log_file))

            logger.warning("Test warning")

            # Read log file
            with open(log_file, "r") as f:
                content = f.read()
                assert "WARNING" in content
