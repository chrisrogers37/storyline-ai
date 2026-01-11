"""CLI main entry point."""
import click
from rich.console import Console

console = Console()


@click.group()
@click.version_option(version="1.0.0")
def cli():
    """Storyline AI - Instagram Story Automation System"""
    pass


# Import commands
from cli.commands.media import (
    index,
    list_media,
    validate,
    list_categories,
    update_category_mix,
    category_mix_history,
)
from cli.commands.queue import create_schedule, process_queue, list_queue
from cli.commands.users import list_users, promote_user
from cli.commands.health import check_health

# Add commands to CLI
cli.add_command(index)
cli.add_command(list_media)
cli.add_command(list_categories)
cli.add_command(update_category_mix)
cli.add_command(category_mix_history)
cli.add_command(validate)
cli.add_command(create_schedule)
cli.add_command(process_queue)
cli.add_command(list_queue)
cli.add_command(list_users)
cli.add_command(promote_user)
cli.add_command(check_health)


if __name__ == "__main__":
    cli()
