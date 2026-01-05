"""Media-related CLI commands."""
import click
from rich.console import Console
from rich.table import Table
from pathlib import Path

from src.services.core.media_ingestion import MediaIngestionService
from src.repositories.media_repository import MediaRepository

console = Console()


@click.command(name="index-media")
@click.argument("directory", type=click.Path(exists=True))
@click.option("--recursive/--no-recursive", default=True, help="Scan subdirectories")
def index(directory, recursive):
    """Index media files from a directory."""
    console.print(f"[bold blue]Indexing media from:[/bold blue] {directory}")

    service = MediaIngestionService()

    try:
        result = service.scan_directory(directory, recursive=recursive)

        console.print(f"\n[bold green]✓ Indexing complete![/bold green]")
        console.print(f"  Indexed: {result['indexed']}")
        console.print(f"  Skipped: {result['skipped']}")
        console.print(f"  Errors: {result['errors']}")

    except Exception as e:
        console.print(f"[bold red]✗ Error:[/bold red] {str(e)}")
        raise click.Abort()


@click.command(name="list-media")
@click.option("--limit", default=20, help="Number of items to show")
@click.option("--active-only", is_flag=True, help="Show only active media")
def list_media(limit, active_only):
    """List indexed media items."""
    repo = MediaRepository()
    items = repo.get_all(is_active=True if active_only else None, limit=limit)

    if not items:
        console.print("[yellow]No media items found[/yellow]")
        return

    table = Table(title=f"Media Items (showing {len(items)})")
    table.add_column("File Name", style="cyan")
    table.add_column("Times Posted", justify="right")
    table.add_column("Last Posted", justify="right")
    table.add_column("Active", justify="center")

    for item in items:
        last_posted = item.last_posted_at.strftime("%Y-%m-%d") if item.last_posted_at else "Never"
        active = "✓" if item.is_active else "✗"

        table.add_row(item.file_name[:40], str(item.times_posted), last_posted, active)

    console.print(table)


@click.command(name="validate-image")
@click.argument("image_path", type=click.Path(exists=True))
def validate(image_path):
    """Validate an image meets Instagram requirements."""
    from src.utils.image_processing import ImageProcessor

    processor = ImageProcessor()
    result = processor.validate_image(Path(image_path))

    if result.is_valid:
        console.print(f"[bold green]✓ Image is valid![/bold green]")
    else:
        console.print(f"[bold red]✗ Image has errors:[/bold red]")
        for error in result.errors:
            console.print(f"  - {error}")

    if result.warnings:
        console.print(f"\n[yellow]⚠ Warnings:[/yellow]")
        for warning in result.warnings:
            console.print(f"  - {warning}")

    console.print(f"\n[bold]Image Details:[/bold]")
    console.print(f"  Resolution: {result.width}x{result.height}")
    console.print(f"  Aspect Ratio: {result.aspect_ratio:.2f}")
    console.print(f"  File Size: {result.file_size_mb:.2f} MB")
    console.print(f"  Format: {result.format}")
