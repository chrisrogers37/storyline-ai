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
    """Create posting schedule for N days.

    Uses category ratios to allocate posts across categories.
    Run 'list-categories' to see current ratios.
    """
    console.print(f"[bold blue]Creating schedule for {days} days...[/bold blue]")

    service = SchedulerService()

    try:
        result = service.create_schedule(days=days)

        console.print(f"\n[bold green]✓ Schedule created![/bold green]")
        console.print(f"  Scheduled: {result['scheduled']}")
        console.print(f"  Skipped: {result['skipped']}")
        console.print(f"  Total slots: {result['total_slots']}")

        # Show category breakdown
        breakdown = result.get("category_breakdown", {})
        if breakdown:
            console.print(f"\n[bold]Category breakdown:[/bold]")
            for cat, count in sorted(breakdown.items()):
                pct = (count / result['scheduled'] * 100) if result['scheduled'] > 0 else 0
                console.print(f"  • {cat}: {count} ({pct:.0f}%)")

        if "error" in result:
            console.print(f"\n[yellow]⚠ Warning: {result['error']}[/yellow]")

    except Exception as e:
        console.print(f"[bold red]✗ Error:[/bold red] {str(e)}")
        raise click.Abort()


@click.command(name="process-queue")
@click.option("--force", is_flag=True, help="Process next item immediately (ignore schedule)")
def process_queue(force):
    """Process pending queue items.

    With --force: Force-posts the next scheduled item immediately and shifts
    all subsequent items forward by one slot. The last slot is discarded.
    """
    if force:
        console.print("[bold blue]Force-processing next scheduled item...[/bold blue]")
    else:
        console.print("[bold blue]Processing pending queue items...[/bold blue]")

    service = PostingService()

    try:
        if force:
            # Use new shared force_post_next() method
            result = asyncio.run(service.force_post_next(
                triggered_by="cli",
                force_sent_indicator=False,  # CLI doesn't need ⚡ in caption
            ))

            if result["success"]:
                console.print(f"\n[bold green]✓ Force-posted successfully![/bold green]")
                media = result["media_item"]
                console.print(f"  File: {media.file_name if media else 'Unknown'}")
                console.print(f"  Queue ID: {result['queue_item_id']}")

                shifted = result["shifted_count"]
                if shifted > 0:
                    console.print(f"  [cyan]Shifted {shifted} items forward[/cyan]")
                else:
                    console.print(f"  [dim]No items to shift (was last in queue)[/dim]")
            else:
                console.print(f"\n[bold red]✗ Failed:[/bold red] {result['error']}")
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
    from src.repositories.media_repository import MediaRepository

    queue_repo = QueueRepository()
    media_repo = MediaRepository()
    items = queue_repo.get_all(status="pending")

    if not items:
        console.print("[yellow]Queue is empty[/yellow]")
        return

    table = Table(title=f"Pending Queue Items ({len(items)})")
    table.add_column("Scheduled For", style="cyan")
    table.add_column("File Name")
    table.add_column("Category", style="magenta")
    table.add_column("Status")

    for item in items:
        # Get media item details
        media = media_repo.get_by_id(str(item.media_item_id))
        file_name = media.file_name[:30] if media else "Unknown"
        category = media.category if media else "-"

        table.add_row(
            item.scheduled_for.strftime("%Y-%m-%d %H:%M"),
            file_name,
            category or "-",
            item.status,
        )

    console.print(table)


@click.command(name="clear-queue")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
def clear_queue(yes):
    """Clear all pending queue items.

    Removes all items from the posting queue. Media items remain
    in the library and can be scheduled again.

    Use --yes to skip the confirmation prompt.
    """
    queue_repo = QueueRepository()
    items = queue_repo.get_all(status="pending")

    if not items:
        console.print("[yellow]Queue is already empty[/yellow]")
        return

    count = len(items)

    if not yes:
        console.print(f"[bold yellow]Warning:[/bold yellow] This will remove {count} pending queue items.")
        console.print("Media items will remain in the library and can be scheduled again.")
        if not click.confirm("Do you want to continue?"):
            console.print("[dim]Cancelled[/dim]")
            return

    try:
        deleted = queue_repo.delete_all_pending()
        console.print(f"[bold green]✓ Cleared {deleted} items from queue[/bold green]")
    except Exception as e:
        console.print(f"[bold red]✗ Error:[/bold red] {str(e)}")
        raise click.Abort()
