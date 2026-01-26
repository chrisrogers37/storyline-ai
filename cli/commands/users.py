"""User management CLI commands."""

import click
from rich.console import Console
from rich.table import Table

from src.repositories.user_repository import UserRepository

console = Console()


@click.command(name="list-users")
def list_users():
    """List all users."""
    repo = UserRepository()
    users = repo.get_all()

    if not users:
        console.print("[yellow]No users found[/yellow]")
        return

    table = Table(title=f"Users ({len(users)})")
    table.add_column("Username", style="cyan")
    table.add_column("Role")
    table.add_column("Total Posts", justify="right")
    table.add_column("Active", justify="center")

    for user in users:
        active = "✓" if user.is_active else "✗"
        username = (
            f"@{user.telegram_username}"
            if user.telegram_username
            else f"ID:{user.telegram_user_id}"
        )

        table.add_row(username, user.role, str(user.total_posts), active)

    console.print(table)


@click.command(name="promote-user")
@click.argument("telegram_user_id", type=int)
@click.option("--role", type=click.Choice(["admin", "member"]), default="admin")
def promote_user(telegram_user_id, role):
    """Promote user to admin or demote to member."""
    repo = UserRepository()
    user = repo.get_by_telegram_id(telegram_user_id)

    if not user:
        console.print(f"[bold red]✗ User not found: {telegram_user_id}[/bold red]")
        raise click.Abort()

    repo.update_role(str(user.id), role)

    username = (
        f"@{user.telegram_username}"
        if user.telegram_username
        else f"ID:{user.telegram_user_id}"
    )
    console.print(f"[bold green]✓ Updated {username} to role: {role}[/bold green]")
