"""Google Drive CLI commands for connecting and managing media sources."""

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.config.settings import settings

console = Console()


@click.command(name="connect-google-drive")
@click.option(
    "--credentials-file",
    required=True,
    type=click.Path(exists=True, readable=True),
    help="Path to Google service account JSON key file",
)
@click.option(
    "--folder-id",
    required=True,
    help="Google Drive folder ID to use as media root",
)
def connect_google_drive(credentials_file, folder_id):
    """Connect Google Drive as a media source."""
    from src.exceptions import GoogleDriveAuthError, GoogleDriveError
    from src.services.integrations.google_drive import GoogleDriveService

    console.print(
        Panel.fit(
            "[bold blue]Connecting Google Drive[/bold blue]\n\n"
            f"Credentials: {credentials_file}\n"
            f"Folder ID: {folder_id}",
            title="Storyline AI",
        )
    )

    if not settings.ENCRYPTION_KEY:
        console.print(
            "\n[bold red]Error:[/bold red] ENCRYPTION_KEY not configured in .env"
        )
        return

    try:
        with open(credentials_file, "r") as f:
            credentials_json = f.read()
    except IOError as e:
        console.print(f"\n[red]Error reading credentials file:[/red] {e}")
        return

    console.print("\n[dim]Validating credentials and folder access...[/dim]")

    service = GoogleDriveService()

    try:
        service.connect(credentials_json=credentials_json, root_folder_id=folder_id)
    except (ValueError, GoogleDriveAuthError, GoogleDriveError) as e:
        console.print(f"\n[red]Error:[/red] {e}")
        return

    console.print("[dim]Checking folder contents...[/dim]")
    validation = service.validate_access(folder_id)

    console.print("\n[bold green]Google Drive connected![/bold green]\n")

    table = Table(title="Connection Details")
    table.add_column("Property", style="cyan")
    table.add_column("Value")
    table.add_row("Folder ID", folder_id)
    table.add_row("Media Files Found", str(validation.get("file_count", "N/A")))
    table.add_row("Categories", ", ".join(validation.get("categories", [])) or "None")
    table.add_row("Credentials", "Service Account (encrypted in DB)")
    console.print(table)


@click.command(name="google-drive-status")
def google_drive_status():
    """Check Google Drive connection status."""
    from src.services.integrations.google_drive import GoogleDriveService

    console.print("[bold blue]Google Drive Status[/bold blue]\n")

    service = GoogleDriveService()
    status = service.get_connection_status()

    table = Table()
    table.add_column("Property", style="cyan")
    table.add_column("Value")

    if status["connected"]:
        table.add_row("Status", "[green]Connected[/green]")
        table.add_row("Credential Type", status.get("credential_type", "unknown"))
        table.add_row("Service Account", status.get("service_account_email", "unknown"))
        table.add_row("Root Folder ID", status.get("root_folder_id", "unknown"))
        console.print(table)

        console.print("\n[dim]Validating access...[/dim]")
        validation = service.validate_access()

        if validation["valid"]:
            console.print("[green]Folder accessible[/green]")
            console.print(f"  Files: {validation.get('file_count', 0)}")
            console.print(
                f"  Categories: {', '.join(validation.get('categories', [])) or 'None'}"
            )
        else:
            console.print(
                f"[red]Folder not accessible:[/red] {validation.get('error')}"
            )
    else:
        table.add_row("Status", "[red]Not Connected[/red]")
        table.add_row("Error", status.get("error", "Unknown"))
        console.print(table)
        console.print(
            "\n[dim]Connect with: storyline-cli connect-google-drive "
            "--credentials-file <path> --folder-id <id>[/dim]"
        )


@click.command(name="disconnect-google-drive")
def disconnect_google_drive():
    """Remove Google Drive credentials and disconnect."""
    from src.services.integrations.google_drive import GoogleDriveService

    service = GoogleDriveService()
    status = service.get_connection_status()

    if not status["connected"]:
        console.print("[yellow]No Google Drive connection to remove.[/yellow]")
        return

    if click.confirm(
        f"Disconnect Google Drive "
        f"(account: {status.get('service_account_email', 'unknown')})?"
    ):
        if service.disconnect():
            console.print(
                "[green]Google Drive disconnected. Credentials removed.[/green]"
            )
        else:
            console.print("[red]Failed to disconnect.[/red]")
    else:
        console.print("[dim]Cancelled[/dim]")
