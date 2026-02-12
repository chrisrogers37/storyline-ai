"""Instagram backfill CLI commands."""

import asyncio
from datetime import datetime
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


@click.command(name="backfill-instagram")
@click.option(
    "--limit",
    type=int,
    default=None,
    help="Maximum number of items to backfill (default: all)",
)
@click.option(
    "--media-type",
    type=click.Choice(["feed", "stories", "both"]),
    default="feed",
    help="Type of media to backfill (default: feed)",
)
@click.option(
    "--since",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    default=None,
    help="Only backfill media newer than this date (YYYY-MM-DD)",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Preview what would be backfilled without downloading",
)
@click.option(
    "--account-id",
    type=str,
    default=None,
    help="Instagram account UUID to backfill from (default: active account)",
)
def backfill_instagram(
    limit: Optional[int],
    media_type: str,
    since: Optional[datetime],
    dry_run: bool,
    account_id: Optional[str],
):
    """Backfill media from Instagram into the local media library.

    Downloads previously posted media (feed posts, stories) from the
    Instagram Graph API and indexes them in the database. This enables
    post recycling -- old content can be re-surfaced through scheduling.

    NOTE: Stories are only available via the API for the last 24 hours.
    Feed posts are available as far back as the account's history.

    Examples:

        storyline-cli backfill-instagram

        storyline-cli backfill-instagram --limit 50

        storyline-cli backfill-instagram --dry-run

        storyline-cli backfill-instagram --since 2025-01-01

        storyline-cli backfill-instagram --account-id abc123...
    """
    from src.services.integrations.instagram_backfill import (
        InstagramBackfillService,
    )

    mode = "[yellow]DRY RUN[/yellow]" if dry_run else "[green]LIVE[/green]"
    console.print(
        Panel.fit(
            f"[bold blue]Instagram Media Backfill[/bold blue] ({mode})\n\n"
            f"Media type: {media_type}\n"
            f"Limit: {limit or 'all'}\n"
            f"Since: {since.strftime('%Y-%m-%d') if since else 'all time'}\n"
            f"Account: {account_id or 'active account'}",
            title="Storyline AI",
        )
    )

    if media_type in ("stories", "both"):
        console.print(
            "\n[yellow]Note:[/yellow] Stories are only available via the "
            "Instagram API for the last 24 hours. Historical stories "
            "cannot be retrieved.\n"
        )

    service = InstagramBackfillService()

    try:
        result = asyncio.run(
            service.backfill(
                limit=limit,
                media_type=media_type,
                since=since,
                dry_run=dry_run,
                account_id=account_id,
                triggered_by="cli",
            )
        )

        status = (
            "[yellow]DRY RUN[/yellow]"
            if dry_run
            else "[bold green]Complete[/bold green]"
        )
        console.print(f"\nBackfill {status}\n")

        table = Table(title="Backfill Results")
        table.add_column("Metric", style="cyan")
        table.add_column("Count", justify="right")

        action = "Would download" if dry_run else "Downloaded"
        table.add_row(action, str(result.downloaded))
        table.add_row("Skipped (duplicate)", str(result.skipped_duplicate))
        table.add_row("Skipped (unsupported)", str(result.skipped_unsupported))
        table.add_row(
            "Failed",
            f"[red]{result.failed}[/red]" if result.failed > 0 else "0",
        )
        table.add_row("Total API items", str(result.total_api_items))

        console.print(table)

        if result.error_details:
            console.print("\n[yellow]Error details:[/yellow]")
            for detail in result.error_details[:10]:
                console.print(f"  - {detail}")

    except Exception as e:
        console.print(f"\n[red]Backfill failed:[/red] {e}")


@click.command(name="backfill-status")
def backfill_status():
    """Show Instagram backfill history and statistics."""
    from src.services.integrations.instagram_backfill import (
        InstagramBackfillService,
    )

    console.print("[bold blue]Instagram Backfill Status[/bold blue]\n")

    service = InstagramBackfillService()
    status = service.get_backfill_status()

    overview_table = Table(title="Overview")
    overview_table.add_column("Metric", style="cyan")
    overview_table.add_column("Value")
    overview_table.add_row(
        "Total Backfilled Items", str(status["total_backfilled"])
    )
    console.print(overview_table)

    last_run = status.get("last_run")
    if not last_run:
        console.print("\n[yellow]No backfill runs recorded yet.[/yellow]")
        console.print(
            "[dim]Run 'storyline-cli backfill-instagram --dry-run' "
            "to preview.[/dim]"
        )
        return

    console.print()

    run_table = Table(title="Last Backfill Run")
    run_table.add_column("Property", style="cyan")
    run_table.add_column("Value")

    run_table.add_row(
        "Status",
        "[green]Success[/green]" if last_run["success"] else "[red]Failed[/red]",
    )
    run_table.add_row("Started At", last_run.get("started_at", "N/A"))
    run_table.add_row("Completed At", last_run.get("completed_at", "N/A"))
    run_table.add_row("Triggered By", last_run.get("triggered_by", "N/A"))

    console.print(run_table)

    result = last_run.get("result")
    if result:
        console.print()
        detail_table = Table(title="Last Run Details")
        detail_table.add_column("Metric", style="cyan")
        detail_table.add_column("Count", justify="right")

        detail_table.add_row("Downloaded", str(result.get("downloaded", 0)))
        detail_table.add_row(
            "Skipped (duplicate)", str(result.get("skipped_duplicate", 0))
        )
        detail_table.add_row(
            "Skipped (unsupported)", str(result.get("skipped_unsupported", 0))
        )
        failed = result.get("failed", 0)
        detail_table.add_row(
            "Failed",
            f"[red]{failed}[/red]" if failed > 0 else "0",
        )
        detail_table.add_row(
            "Total API Items", str(result.get("total_api_items", 0))
        )
        detail_table.add_row(
            "Dry Run",
            "Yes" if result.get("dry_run") else "No",
        )

        console.print(detail_table)
