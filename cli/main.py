"""CLI main entry point."""

import click
from rich.console import Console

from cli.commands.google_drive import (
    connect_google_drive,
    disconnect_google_drive,
    google_drive_status,
)
from cli.commands.health import check_health
from cli.commands.instagram import (
    add_instagram_account,
    deactivate_instagram_account,
    instagram_auth,
    instagram_status,
    list_instagram_accounts,
    reactivate_instagram_account,
)
from cli.commands.media import (
    category_mix_history,
    index,
    list_categories,
    list_media,
    update_category_mix,
    validate,
)
from cli.commands.queue import reset_queue, create_schedule, list_queue, process_queue
from cli.commands.sync import sync_media, sync_status
from cli.commands.users import list_users, promote_user
from src import __version__

console = Console()


@click.group()
@click.version_option(version=__version__)
def cli():
    """Storyline AI - Instagram Story Automation System"""
    pass


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
cli.add_command(reset_queue)
cli.add_command(list_users)
cli.add_command(promote_user)
cli.add_command(check_health)
cli.add_command(instagram_auth)
cli.add_command(instagram_status)
cli.add_command(add_instagram_account)
cli.add_command(list_instagram_accounts)
cli.add_command(deactivate_instagram_account)
cli.add_command(reactivate_instagram_account)
cli.add_command(connect_google_drive)
cli.add_command(google_drive_status)
cli.add_command(disconnect_google_drive)
cli.add_command(sync_media)
cli.add_command(sync_status)


if __name__ == "__main__":
    cli()
