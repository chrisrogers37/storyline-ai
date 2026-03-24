"""Queue-related CLI commands."""

import click
from rich.console import Console
from rich.table import Table

from src.services.core.scheduler import SchedulerService
from src.services.core.dashboard_service import DashboardService

console = Console()


@click.command(name="list-queue")
def list_queue():
    """List in-flight queue items (sent to Telegram, awaiting action)."""
    with DashboardService() as service:
        items = service.get_pending_queue_items()

    if not items:
        console.print("[yellow]Queue is empty[/yellow]")
        return

    table = Table(title=f"In-Flight Queue Items ({len(items)})")
    table.add_column("Sent At", style="cyan")
    table.add_column("File Name")
    table.add_column("Category", style="magenta")
    table.add_column("Status")

    for item in items:
        file_name = item["file_name"][:30] if item["file_name"] else "Unknown"

        table.add_row(
            item["scheduled_for"].strftime("%Y-%m-%d %H:%M"),
            file_name,
            item["category"] or "-",
            item["status"],
        )

    console.print(table)


@click.command(name="reset-queue")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
def reset_queue(yes):
    """Clear all in-flight queue items.

    Removes items waiting for team action (Posted/Skip/Reject).
    Media items remain in the library for future selection.

    Use --yes to skip the confirmation prompt.
    """
    with SchedulerService() as scheduler:
        count = scheduler.count_pending()

        if count == 0:
            console.print("[yellow]Queue is already empty[/yellow]")
            return

        if not yes:
            console.print(
                f"[bold yellow]Warning:[/bold yellow] This will remove {count} in-flight queue items."
            )
            console.print(
                "Media items will remain in the library for future selection."
            )
            if not click.confirm("Do you want to continue?"):
                console.print("[dim]Cancelled[/dim]")
                return

        try:
            deleted = scheduler.clear_pending_queue()
            console.print(
                f"[bold green]✓ Cleared {deleted} items from queue[/bold green]"
            )
        except Exception as e:
            console.print(f"[bold red]✗ Error:[/bold red] {str(e)}")
            raise click.Abort()


@click.command(name="queue-preview")
@click.option("--count", "-n", default=5, help="Number of items to preview")
def queue_preview(count):
    """Preview the next N media items the scheduler would select.

    Shows what the JIT scheduler would pick without actually posting.
    """
    with SchedulerService() as scheduler:
        previews = scheduler.get_queue_preview(
            telegram_chat_id=None,  # Uses admin chat fallback
            count=count,
        )

    if not previews:
        console.print("[yellow]No eligible media available[/yellow]")
        return

    table = Table(title=f"Next {len(previews)} Selections (Preview)")
    table.add_column("#", style="dim")
    table.add_column("File Name")
    table.add_column("Category", style="magenta")

    for i, item in enumerate(previews, 1):
        file_name = item["file_name"][:40] if item["file_name"] else "Unknown"
        table.add_row(str(i), file_name, item["category"] or "-")

    console.print(table)
