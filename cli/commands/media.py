"""Media-related CLI commands."""

import click
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm
from pathlib import Path
from decimal import Decimal, InvalidOperation

from src.services.core.media_ingestion import MediaIngestionService

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


def display_current_mix(service: MediaIngestionService):
    """Display the current category mix with media counts."""
    current_mix = service.get_current_mix()

    if not current_mix:
        console.print("[yellow]No category mix configured yet[/yellow]")
        return False

    table = Table(title="Current Category Mix")
    table.add_column("Category", style="cyan")
    table.add_column("Ratio", justify="right")
    table.add_column("Media Count", justify="right", style="dim")

    category_counts = service.get_category_counts()
    for mix in current_mix:
        count = category_counts.get(mix.category, 0)
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

    with MediaIngestionService() as service:
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
            all_categories = service.get_categories()

            if not all_categories:
                console.print("\n[yellow]No categories found in media library[/yellow]")
                return

            # Check if mix already exists
            has_mix = service.has_current_mix()
            current_ratios = service.get_current_mix_as_dict() if has_mix else {}

            # Check for new categories without ratios
            new_categories = service.get_categories_without_ratio(all_categories)

            if has_mix and not new_categories:
                # Existing mix covers all categories
                console.print("\n[bold]Current category mix:[/bold]")
                display_current_mix(service)

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
            service.set_category_mix(ratios)

            console.print("\n[bold green]✓ Category mix saved![/bold green]")
            display_current_mix(service)

        except Exception as e:
            console.print(f"[bold red]✗ Error:[/bold red] {str(e)}")
            raise click.Abort()


@click.command(name="update-category-mix")
def update_category_mix():
    """Update the posting ratio mix for categories.

    Opens a workflow to redefine what percentage of posts
    should come from each category.
    """
    with MediaIngestionService() as service:
        categories = service.get_categories()

        if not categories:
            console.print(
                "[yellow]No categories found. Run index-media first.[/yellow]"
            )
            return

        console.print("[bold blue]Update Category Mix[/bold blue]")
        console.print(f"Categories in library: {', '.join(sorted(categories))}\n")

        # Show current mix
        has_mix = display_current_mix(service)

        if has_mix:
            if not Confirm.ask("\nRedefine ratios?", default=True):
                return

        current_ratios = service.get_current_mix_as_dict()
        ratios = prompt_for_category_ratios(categories, current_ratios)

        # Save
        service.set_category_mix(ratios)

        console.print("\n[bold green]✓ Category mix updated![/bold green]")
        display_current_mix(service)


@click.command(name="list-media")
@click.option("--limit", default=20, help="Number of items to show")
@click.option("--active-only", is_flag=True, help="Show only active media")
@click.option("--category", "-c", help="Filter by category (e.g., 'memes' or 'merch')")
def list_media(limit, active_only, category):
    """List indexed media items."""
    with MediaIngestionService() as service:
        items = service.list_media(
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
    with MediaIngestionService() as service:
        categories = service.get_categories()

        if not categories:
            console.print("[yellow]No categories found[/yellow]")
            return

        current_mix = service.get_current_mix_as_dict()

        table = Table(title="Media Categories")
        table.add_column("Category", style="cyan")
        table.add_column("Media Count", justify="right")
        table.add_column("Post Ratio", justify="right", style="magenta")

        category_counts = service.get_category_counts()
        for cat in sorted(categories):
            count = category_counts.get(cat, 0)
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
    with MediaIngestionService() as service:
        history = service.get_mix_history(category=category)

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


@click.command(name="dedup-media")
@click.option("--dry-run", is_flag=True, default=True, help="Preview only (default)")
@click.option(
    "--apply", is_flag=True, default=False, help="Actually deactivate duplicates"
)
def dedup_media(dry_run, apply):
    """Find and deactivate duplicate media items (same file content, different filenames)."""
    from src.repositories.media_repository import MediaRepository

    repo = MediaRepository()
    try:
        groups = repo.get_duplicate_hash_groups()
    finally:
        repo.close()

    if not groups:
        console.print("[green]No duplicate files found.[/green]")
        return

    total_extras = 0
    ids_to_deactivate = []

    table = Table(title=f"Duplicate File Groups ({len(groups)} groups)")
    table.add_column("Hash", style="dim", max_width=10)
    table.add_column("Keep", style="green")
    table.add_column("Deactivate", style="red")
    table.add_column("Times Posted", justify="right")

    for group in groups:
        items = group["items"]
        # Keep the item with highest times_posted (then first by name as tiebreak)
        keeper = items[0]  # Already sorted by times_posted DESC
        extras = items[1:]
        total_extras += len(extras)

        extra_names = ", ".join(i["file_name"][:30] for i in extras)
        ids_to_deactivate.extend(i["id"] for i in extras)

        table.add_row(
            group["hash"][:10],
            keeper["file_name"][:35],
            extra_names[:60],
            str(keeper["times_posted"]),
        )

    console.print(table)
    console.print(
        f"\n[bold]{len(groups)} groups, {total_extras} duplicate items to deactivate[/bold]"
    )

    if apply:
        if not Confirm.ask(
            f"Deactivate {total_extras} duplicate items? This is reversible (is_active=false)."
        ):
            console.print("[yellow]Aborted.[/yellow]")
            return

        repo = MediaRepository()
        try:
            count = repo.deactivate_by_ids(ids_to_deactivate)
        finally:
            repo.close()
        console.print(f"[green]Deactivated {count} duplicate items.[/green]")
    else:
        console.print("\n[dim]Dry run — use --apply to deactivate duplicates.[/dim]")


@click.command(name="pool-health")
def pool_health():
    """Show media pool health: active, locked, eligible, and duplicate counts."""
    from src.repositories.media_repository import MediaRepository
    from src.repositories.lock_repository import LockRepository
    from src.repositories.queue_repository import QueueRepository

    media_repo = MediaRepository()
    lock_repo = LockRepository()
    queue_repo = QueueRepository()

    try:
        # Overall counts
        posting_status = media_repo.count_by_posting_status()
        total_active = (
            posting_status["never_posted"]
            + posting_status["posted_once"]
            + posting_status["posted_multiple"]
        )
        total_inactive = media_repo.count_inactive()
        eligible = media_repo.count_eligible()

        # Lock breakdown
        locks_by_reason = lock_repo.count_by_reason()
        total_locks = sum(locks_by_reason.values())

        # Queue
        queued = queue_repo.count_pending()

        # Duplicates
        dupe_groups = media_repo.get_duplicate_hash_groups()
        dupe_extras = sum(len(g["items"]) - 1 for g in dupe_groups)

        # Per-category
        category_counts = media_repo.count_by_category()
        eligible_by_cat = media_repo.count_eligible_by_category()
    finally:
        media_repo.close()
        lock_repo.close()
        queue_repo.close()

    # Summary table
    summary = Table(title="Media Pool Health", show_header=False)
    summary.add_column("Metric", style="bold")
    summary.add_column("Value", justify="right")

    summary.add_row("Active items", str(total_active))
    summary.add_row("Inactive items", str(total_inactive))
    summary.add_row("  Never posted", str(posting_status["never_posted"]))
    summary.add_row("  Posted once", str(posting_status["posted_once"]))
    summary.add_row("  Posted 2+", str(posting_status["posted_multiple"]))
    summary.add_row("", "")
    summary.add_row("Currently locked", str(total_locks))
    for reason, count in sorted(locks_by_reason.items(), key=lambda x: -x[1]):
        summary.add_row(f"  {reason}", str(count))
    summary.add_row("In queue", str(queued))
    summary.add_row("", "")
    summary.add_row("[green]Eligible right now[/green]", f"[green]{eligible}[/green]")
    summary.add_row("", "")
    summary.add_row("Duplicate file groups", str(len(dupe_groups)))
    summary.add_row("Extra duplicate items", str(dupe_extras))

    console.print(summary)

    # Per-category table
    cat_table = Table(title="Per-Category Breakdown")
    cat_table.add_column("Category", style="cyan")
    cat_table.add_column("Active", justify="right")
    cat_table.add_column("Eligible", justify="right", style="green")
    cat_table.add_column("Locked/Queued", justify="right", style="yellow")

    for cat in sorted(category_counts.keys()):
        active = category_counts[cat]
        elig = eligible_by_cat.get(cat, 0)
        locked = active - elig
        cat_table.add_row(cat, str(active), str(elig), str(locked))

    console.print(cat_table)
