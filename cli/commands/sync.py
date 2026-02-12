"""Media sync CLI commands."""

import click
from rich.console import Console
from rich.table import Table

console = Console()


@click.command(name="sync-media")
@click.option(
    "--source-type",
    type=click.Choice(["local", "google_drive"]),
    default=None,
    help="Override MEDIA_SOURCE_TYPE from .env",
)
@click.option(
    "--source-root",
    default=None,
    help="Override MEDIA_SOURCE_ROOT (path for local, folder ID for google_drive)",
)
def sync_media(source_type, source_root):
    """Manually trigger a media sync against the configured provider.

    Reconciles the provider's file listing with the database:
    indexes new files, deactivates removed files, detects renames.
    """
    from src.services.core.media_sync import MediaSyncService

    console.print("[bold blue]Running media sync...[/bold blue]\n")

    service = MediaSyncService()

    try:
        result = service.sync(
            source_type=source_type,
            source_root=source_root,
            triggered_by="cli",
        )

        console.print("[bold green]Sync complete![/bold green]\n")

        table = Table(title="Sync Results")
        table.add_column("Action", style="cyan")
        table.add_column("Count", justify="right")

        table.add_row("New files indexed", str(result.new))
        table.add_row("Updated (rename/move)", str(result.updated))
        table.add_row("Deactivated (removed)", str(result.deactivated))
        table.add_row("Reactivated (reappeared)", str(result.reactivated))
        table.add_row("Unchanged", str(result.unchanged))
        table.add_row(
            "Errors",
            f"[red]{result.errors}[/red]" if result.errors > 0 else "0",
        )

        console.print(table)

        if result.error_details:
            console.print("\n[yellow]Error details:[/yellow]")
            for detail in result.error_details[:10]:
                console.print(f"  - {detail}")

    except ValueError as e:
        console.print(f"\n[red]Configuration error:[/red] {e}")
    except Exception as e:
        console.print(f"\n[red]Sync failed:[/red] {e}")


@click.command(name="sync-status")
def sync_status():
    """Show the status of the last media sync run."""
    from src.services.core.media_sync import MediaSyncService
    from src.config.settings import settings

    console.print("[bold blue]Media Sync Status[/bold blue]\n")

    # Show configuration
    config_table = Table(title="Configuration")
    config_table.add_column("Setting", style="cyan")
    config_table.add_column("Value")

    enabled = settings.MEDIA_SYNC_ENABLED
    config_table.add_row(
        "Sync Enabled",
        "[green]Yes[/green]" if enabled else "[red]No[/red]",
    )
    config_table.add_row("Source Type", settings.MEDIA_SOURCE_TYPE)
    config_table.add_row(
        "Source Root",
        settings.MEDIA_SOURCE_ROOT or f"(default: {settings.MEDIA_DIR})",
    )
    config_table.add_row("Interval", f"{settings.MEDIA_SYNC_INTERVAL_SECONDS}s")

    console.print(config_table)

    # Show last sync info
    service = MediaSyncService()
    last_sync = service.get_last_sync_info()

    if not last_sync:
        console.print("\n[yellow]No sync runs recorded yet.[/yellow]")
        if not enabled:
            console.print(
                "[dim]Enable with MEDIA_SYNC_ENABLED=true in .env, "
                "or run 'storyline-cli sync-media' manually.[/dim]"
            )
        return

    console.print()

    sync_table = Table(title="Last Sync Run")
    sync_table.add_column("Property", style="cyan")
    sync_table.add_column("Value")

    status_str = (
        "[green]Success[/green]" if last_sync["success"] else "[red]Failed[/red]"
    )
    sync_table.add_row("Status", status_str)
    sync_table.add_row("Started At", last_sync.get("started_at", "N/A"))
    sync_table.add_row("Completed At", last_sync.get("completed_at", "N/A"))

    duration = last_sync.get("duration_ms")
    if duration is not None:
        sync_table.add_row("Duration", f"{duration}ms")

    sync_table.add_row("Triggered By", last_sync.get("triggered_by", "N/A"))

    console.print(sync_table)

    # Show result summary if available
    result = last_sync.get("result")
    if result:
        console.print()
        result_table = Table(title="Sync Details")
        result_table.add_column("Action", style="cyan")
        result_table.add_column("Count", justify="right")

        result_table.add_row("New", str(result.get("new", 0)))
        result_table.add_row("Updated", str(result.get("updated", 0)))
        result_table.add_row("Deactivated", str(result.get("deactivated", 0)))
        result_table.add_row("Reactivated", str(result.get("reactivated", 0)))
        result_table.add_row("Unchanged", str(result.get("unchanged", 0)))
        errors = result.get("errors", 0)
        result_table.add_row(
            "Errors",
            f"[red]{errors}[/red]" if errors > 0 else "0",
        )

        console.print(result_table)
