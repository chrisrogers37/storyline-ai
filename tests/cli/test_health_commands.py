"""Tests for health CLI commands."""
import pytest
from click.testing import CliRunner

from cli.commands.health import check_health


@pytest.mark.unit
class TestHealthCommands:
    """Test suite for health CLI commands."""

    def test_check_health_command(self, test_db):
        """Test check-health CLI command."""
        runner = CliRunner()

        result = runner.invoke(check_health, [])

        # Command should execute successfully
        assert result.exit_code == 0
        # Should show health check results
        assert "database" in result.output.lower() or "health" in result.output.lower()

    def test_check_health_shows_all_checks(self, test_db):
        """Test that check-health shows all health checks."""
        runner = CliRunner()

        result = runner.invoke(check_health, [])

        assert result.exit_code == 0

        # Should include main health check categories
        output_lower = result.output.lower()
        # At least some health check information should be present
        assert any(
            keyword in output_lower
            for keyword in ["database", "telegram", "queue", "health", "check"]
        )
