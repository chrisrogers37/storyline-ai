"""Media-related CLI commands."""

import click
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm
from pathlib import Path
from decimal import Decimal, InvalidOperation

from src.services.core.media_ingestion import MediaIngestionService
from src.repositories.media_repository import MediaRepository
from src.repositories.category_mix_repository import CategoryMixRepository

console = Console()


def prompt_for_category_ratios(
    categories: list[str], current_ratios: dict = None
) -> dict:
    """
    Prompt user to define ratios for each category.

    Args:
        categories: List of category names
        current_ratios: Optional dict of existing ratios to show as defaults

    Returns:
        Dict of {category: Decimal ratio}
    """
    if not categories:
        return {}

    current_ratios = current_ratios or {}

    cat_list = ", ".join(sorted(categories))
    console.print(
        f"\n[bold]Categories based on folder structure:[/bold] [cyan]{cat_list}[/cyan]"
    )
    console.print("[dim]Ratios must sum to 100%[/dim]\n")

    while True:
        ratios = {}

        for cat in sorted(categories):
            default = current_ratios.get(cat)
            default_hint = (
                f" [dim](current: {float(default) * 100:.0f}%)[/dim]" if default else ""
            )
            console.print(f"What % would you like [cyan]'{cat}'[/cyan]?{default_hint}")

            while True:
                value = Prompt.ask("  ")

                # Use default if empty and default exists
                if not value and default:
                    ratios[cat] = default
                    break

                try:
                    pct = float(value)
                    if pct < 0 or pct > 100:
                        console.print("[red]  Enter a value between 0 and 100[/red]")
                        continue
                    ratios[cat] = Decimal(str(pct / 100))
                    break
                except (ValueError, InvalidOperation):
                    console.print(
                        "[red]  Invalid number. Enter a percentage (e.g., 70)[/red]"
                    )

        # Validate sum
        total = sum(ratios.values())
        total_pct = float(total) * 100

        if abs(total_pct - 100) < 0.1:  # Allow small tolerance
            # Normalize to exactly 1.0
            if total != Decimal("1"):
                # Adjust the largest ratio to make sum exactly 1.0
                largest_cat = max(ratios, key=lambda k: ratios[k])
                ratios[largest_cat] += Decimal("1") - total

            console.print("\n[green]✓ Ratios sum to 100%[/green]")
            return ratios
        else:
            console.print(
                f"\n[red]✗ Ratios sum to {total_pct:.1f}%, must equal 100%[/red]"
            )
            if not Confirm.ask("Try again?", default=True):
                raise click.Abort()


def display_current_mix(mix_repo: CategoryMixRepository, media_repo: MediaRepository):
    """Display the current category mix with media counts."""
    current_mix = mix_repo.get_current_mix()

    if not current_mix:
        console.print("[yellow]No category mix configured yet[/yellow]")
        return False

    table = Table(title="Current Category Mix")
    table.add_column("Category", style="cyan")
    table.add_column("Ratio", justify="right")
    table.add_column("Media Count", justify="right", style="dim")

    for mix in current_mix:
        count = len(media_repo.get_all(category=mix.category))
        table.add_row(
            mix.category,
            f"{float(mix.ratio) * 100:.0f}%",
            str(count),
        )

    console.print(table)
    return True


@click.command(name="index-media")
@click.argument("directory", type=click.Path(exists=True))
@click.option("--recursive/--no-recursive", default=True, help="Scan subdirectories")
@click.option(
    "--extract-category/--no-extract-category",
    default=True,
    help="Extract category from subfolder names",
)
def index(directory, recursive, extract_category):
    """Index media files from a directory.

    Categories are automatically extracted from immediate subdirectory names.
    For example, media/stories/memes/image.jpg will have category "memes".

    After indexing, you'll be prompted to define posting ratios for each category.
    """
    console.print(f"[bold blue]Indexing media from:[/bold blue] {directory}")
    if extract_category:
        console.print("[dim]Category extraction enabled (from subfolder names)[/dim]")

    service = MediaIngestionService()
    media_repo = MediaRepository()
    mix_repo = CategoryMixRepository()

    try:
        result = service.scan_directory(
            directory, recursive=recursive, extract_category=extract_category
        )

        console.print("\n[bold green]✓ Indexing complete![/bold green]")
        console.print(f"  Indexed: {result['indexed']}")
        console.print(f"  Skipped: {result['skipped']}")
        console.print(f"  Errors: {result['errors']}")

        discovered_categories = result.get("categories", [])
        if discovered_categories:
            console.print(f"  Categories: {', '.join(discovered_categories)}")

        # Get all categories in the database (might include previously indexed ones)
        all_categories = media_repo.get_categories()

        if not all_categories:
            console.print("\n[yellow]No categories found in media library[/yellow]")
            return

        # Check if mix already exists
        has_mix = mix_repo.has_current_mix()
        current_ratios = mix_repo.get_current_mix_as_dict() if has_mix else {}

        # Check for new categories without ratios
        new_categories = mix_repo.get_categories_without_ratio(all_categories)

        if has_mix and not new_categories:
            # Existing mix covers all categories
            console.print("\n[bold]Current category mix:[/bold]")
            display_current_mix(mix_repo, media_repo)

            if Confirm.ask("\nKeep current ratios?", default=True):
                console.print("[green]✓ Keeping existing ratios[/green]")
                return
            # Fall through to redefine

        elif new_categories:
            console.print(
                f"\n[yellow]New categories detected: {', '.join(new_categories)}[/yellow]"
            )
            if has_mix:
                console.print("[dim]Current ratios will need to be updated[/dim]")

        # Prompt for ratios
        ratios = prompt_for_category_ratios(all_categories, current_ratios)

        # Save the new mix
        mix_repo.set_mix(ratios)

        console.print("\n[bold green]✓ Category mix saved![/bold green]")
        display_current_mix(mix_repo, media_repo)

    except Exception as e:
        console.print(f"[bold red]✗ Error:[/bold red] {str(e)}")
        raise click.Abort()


@click.command(name="update-category-mix")
def update_category_mix():
    """Update the posting ratio mix for categories.

    Opens a workflow to redefine what percentage of posts
    should come from each category.
    """
    media_repo = MediaRepository()
    mix_repo = CategoryMixRepository()

    categories = media_repo.get_categories()

    if not categories:
        console.print("[yellow]No categories found. Run index-media first.[/yellow]")
        return

    console.print("[bold blue]Update Category Mix[/bold blue]")
    console.print(f"Categories in library: {', '.join(sorted(categories))}\n")

    # Show current mix
    has_mix = display_current_mix(mix_repo, media_repo)

    if has_mix:
        if not Confirm.ask("\nRedefine ratios?", default=True):
            return

    current_ratios = mix_repo.get_current_mix_as_dict()
    ratios = prompt_for_category_ratios(categories, current_ratios)

    # Save
    mix_repo.set_mix(ratios)

    console.print("\n[bold green]✓ Category mix updated![/bold green]")
    display_current_mix(mix_repo, media_repo)


@click.command(name="list-media")
@click.option("--limit", default=20, help="Number of items to show")
@click.option("--active-only", is_flag=True, help="Show only active media")
@click.option("--category", "-c", help="Filter by category (e.g., 'memes' or 'merch')")
def list_media(limit, active_only, category):
    """List indexed media items."""
    repo = MediaRepository()
    items = repo.get_all(
        is_active=True if active_only else None,
        category=category,
        limit=limit,
    )

    if not items:
        msg = "[yellow]No media items found"
        if category:
            msg += f" in category '{category}'"
        msg += "[/yellow]"
        console.print(msg)
        return

    title = f"Media Items (showing {len(items)})"
    if category:
        title += f" - Category: {category}"

    table = Table(title=title)
    table.add_column("File Name", style="cyan")
    table.add_column("Category", style="magenta")
    table.add_column("Times Posted", justify="right")
    table.add_column("Last Posted", justify="right")
    table.add_column("Active", justify="center")

    for item in items:
        last_posted = (
            item.last_posted_at.strftime("%Y-%m-%d") if item.last_posted_at else "Never"
        )
        active = "✓" if item.is_active else "✗"
        cat = item.category or "-"

        table.add_row(
            item.file_name[:40], cat, str(item.times_posted), last_posted, active
        )

    console.print(table)


@click.command(name="list-categories")
def list_categories():
    """List all media categories with their posting ratios."""
    media_repo = MediaRepository()
    mix_repo = CategoryMixRepository()

    categories = media_repo.get_categories()

    if not categories:
        console.print("[yellow]No categories found[/yellow]")
        return

    current_mix = mix_repo.get_current_mix_as_dict()

    table = Table(title="Media Categories")
    table.add_column("Category", style="cyan")
    table.add_column("Media Count", justify="right")
    table.add_column("Post Ratio", justify="right", style="magenta")

    for cat in sorted(categories):
        count = len(media_repo.get_all(category=cat))
        ratio = current_mix.get(cat)
        ratio_str = f"{float(ratio) * 100:.0f}%" if ratio else "[dim]not set[/dim]"
        table.add_row(cat, str(count), ratio_str)

    console.print(table)

    if not current_mix:
        console.print(
            "\n[yellow]Tip: Run 'update-category-mix' to set posting ratios[/yellow]"
        )


@click.command(name="category-mix-history")
@click.option("--category", "-c", help="Filter by specific category")
def category_mix_history(category):
    """Show history of category mix changes (Type 2 SCD)."""
    mix_repo = CategoryMixRepository()

    history = mix_repo.get_history(category=category)

    if not history:
        console.print("[yellow]No category mix history found[/yellow]")
        return

    table = Table(title="Category Mix History")
    table.add_column("Category", style="cyan")
    table.add_column("Ratio", justify="right")
    table.add_column("Effective From", justify="right")
    table.add_column("Effective To", justify="right")
    table.add_column("Status", justify="center")

    for record in history:
        eff_from = record.effective_from.strftime("%Y-%m-%d %H:%M")
        eff_to = (
            record.effective_to.strftime("%Y-%m-%d %H:%M")
            if record.effective_to
            else "-"
        )
        status = "[green]current[/green]" if record.is_current else "[dim]expired[/dim]"

        table.add_row(
            record.category,
            f"{float(record.ratio) * 100:.0f}%",
            eff_from,
            eff_to,
            status,
        )

    console.print(table)


@click.command(name="validate-image")
@click.argument("image_path", type=click.Path(exists=True))
def validate(image_path):
    """Validate an image meets Instagram requirements."""
    from src.utils.image_processing import ImageProcessor

    processor = ImageProcessor()
    result = processor.validate_image(Path(image_path))

    if result.is_valid:
        console.print("[bold green]✓ Image is valid![/bold green]")
    else:
        console.print("[bold red]✗ Image has errors:[/bold red]")
        for error in result.errors:
            console.print(f"  - {error}")

    if result.warnings:
        console.print("\n[yellow]⚠ Warnings:[/yellow]")
        for warning in result.warnings:
            console.print(f"  - {warning}")

    console.print("\n[bold]Image Details:[/bold]")
    console.print(f"  Resolution: {result.width}x{result.height}")
    console.print(f"  Aspect Ratio: {result.aspect_ratio:.2f}")
    console.print(f"  File Size: {result.file_size_mb:.2f} MB")
    console.print(f"  Format: {result.format}")
