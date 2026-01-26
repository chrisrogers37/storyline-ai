"""Health check CLI command."""

import click
from rich.console import Console
from rich.table import Table

from src.services.core.health_check import HealthCheckService

console = Console()


@click.command(name="check-health")
def check_health():
    """Check system health status."""
    console.print("[bold blue]Running health checks...[/bold blue]\n")

    service = HealthCheckService()
    result = service.check_all()

    # Overall status
    if result["status"] == "healthy":
        console.print("[bold green]✓ System Status: HEALTHY[/bold green]\n")
    else:
        console.print("[bold yellow]⚠ System Status: UNHEALTHY[/bold yellow]\n")

    # Create table
    table = Table(title="Health Check Results")
    table.add_column("Component", style="cyan")
    table.add_column("Status", justify="center")
    table.add_column("Message")

    for name, check in result["checks"].items():
        status = "✓" if check["healthy"] else "✗"
        status_color = "green" if check["healthy"] else "red"

        table.add_row(
            name.title(), f"[{status_color}]{status}[/{status_color}]", check["message"]
        )

    console.print(table)
