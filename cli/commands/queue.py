"""Queue-related CLI commands."""
import click
import asyncio
from rich.console import Console
from rich.table import Table

from src.services.core.scheduler import SchedulerService
from src.services.core.posting import PostingService
from src.repositories.queue_repository import QueueRepository

console = Console()


@click.command(name="create-schedule")
@click.option("--days", default=7, help="Number of days to schedule")
def create_schedule(days):
    """Create posting schedule for N days."""
    console.print(f"[bold blue]Creating schedule for {days} days...[/bold blue]")

    service = SchedulerService()

    try:
        result = service.create_schedule(days=days)

        console.print(f"\n[bold green]✓ Schedule created![/bold green]")
        console.print(f"  Scheduled: {result['scheduled']}")
        console.print(f"  Skipped: {result['skipped']}")
        console.print(f"  Total slots: {result['total_slots']}")

        if "error" in result:
            console.print(f"\n[yellow]⚠ Warning: {result['error']}[/yellow]")

    except Exception as e:
        console.print(f"[bold red]✗ Error:[/bold red] {str(e)}")
        raise click.Abort()


@click.command(name="process-queue")
@click.option("--force", is_flag=True, help="Process next item immediately (ignore schedule)")
def process_queue(force):
    """Process pending queue items."""
    if force:
        console.print("[bold blue]Force-processing next scheduled item...[/bold blue]")
    else:
        console.print("[bold blue]Processing pending queue items...[/bold blue]")

    service = PostingService()

    try:
        if force:
            result = asyncio.run(service.process_next_immediate())
        else:
            result = asyncio.run(service.process_pending_posts())

        console.print(f"\n[bold green]✓ Processing complete![/bold green]")
        console.print(f"  Processed: {result['processed']}")
        console.print(f"  Telegram: {result['telegram']}")
        console.print(f"  Failed: {result['failed']}")

    except Exception as e:
        console.print(f"[bold red]✗ Error:[/bold red] {str(e)}")
        raise click.Abort()


@click.command(name="list-queue")
def list_queue():
    """List pending queue items."""
    repo = QueueRepository()
    items = repo.get_all(status="pending")

    if not items:
        console.print("[yellow]Queue is empty[/yellow]")
        return

    table = Table(title=f"Pending Queue Items ({len(items)})")
    table.add_column("Scheduled For", style="cyan")
    table.add_column("Status")
    table.add_column("Retry Count", justify="right")

    for item in items:
        table.add_row(
            item.scheduled_for.strftime("%Y-%m-%d %H:%M"),
            item.status,
            str(item.retry_count)
        )

    console.print(table)
