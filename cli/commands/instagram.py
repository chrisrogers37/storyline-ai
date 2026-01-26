"""Instagram authentication CLI commands."""
import asyncio
import webbrowser
from datetime import datetime, timedelta

import click
import httpx
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.config.settings import settings
from src.repositories.token_repository import TokenRepository
from src.utils.encryption import TokenEncryption
from src.services.integrations.token_refresh import TokenRefreshService

console = Console()


@click.command(name="instagram-auth")
@click.option("--manual", is_flag=True, help="Show manual instructions without browser automation")
def instagram_auth(manual: bool):
    """
    Authenticate with Instagram API.

    This command guides you through the Meta OAuth flow to obtain
    a long-lived access token for posting Instagram Stories.

    Prerequisites:
    - Meta Developer account
    - Facebook App with Instagram Graph API enabled
    - Instagram Business or Creator account
    - Facebook Page linked to your Instagram account
    """
    console.print(Panel.fit(
        "[bold blue]Instagram API Authentication Setup[/bold blue]\n\n"
        "This wizard will help you obtain a long-lived Instagram access token.",
        title="Storyline AI"
    ))

    # Check prerequisites
    if not settings.FACEBOOK_APP_ID:
        console.print("\n[bold red]Error:[/bold red] FACEBOOK_APP_ID not configured in .env")
        console.print("Please add your Facebook App ID to .env first.")
        console.print("\nSee: documentation/guides/instagram-api-setup.md")
        return

    if not settings.FACEBOOK_APP_SECRET:
        console.print("\n[bold red]Error:[/bold red] FACEBOOK_APP_SECRET not configured in .env")
        console.print("Please add your Facebook App Secret to .env first.")
        return

    if not settings.ENCRYPTION_KEY:
        console.print("\n[bold red]Error:[/bold red] ENCRYPTION_KEY not configured in .env")
        console.print("\nGenerate one with:")
        console.print("  python -c \"from src.utils.encryption import TokenEncryption; print(TokenEncryption.generate_key())\"")
        return

    if manual:
        _show_manual_instructions()
    else:
        _run_auth_wizard()


def _show_manual_instructions():
    """Display manual authentication instructions."""
    console.print("\n[bold]Manual Authentication Instructions[/bold]\n")

    console.print("1. Go to Meta Graph API Explorer:")
    console.print("   https://developers.facebook.com/tools/explorer/\n")

    console.print("2. Select your App from the dropdown\n")

    console.print("3. Click 'Generate Access Token' and grant these permissions:")
    console.print("   - instagram_basic")
    console.print("   - instagram_content_publish")
    console.print("   - pages_show_list")
    console.print("   - pages_read_engagement\n")

    console.print("4. Copy the short-lived token and run:")
    console.print("   [cyan]storyline-cli instagram-auth[/cyan]")
    console.print("   Then paste the token when prompted.\n")

    console.print("5. The token will be exchanged for a long-lived token (60 days)")
    console.print("   and stored securely in the database.\n")


def _run_auth_wizard():
    """Run the interactive authentication wizard."""
    console.print("\n[bold]Step 1: Get a Short-Lived Token[/bold]\n")

    console.print("Option A: Use Graph API Explorer (Recommended)")
    console.print("  1. Open: https://developers.facebook.com/tools/explorer/")
    console.print("  2. Select your App")
    console.print("  3. Click 'Generate Access Token'")
    console.print("  4. Grant required permissions\n")

    # Ask if user wants to open browser
    if click.confirm("Open Graph API Explorer in browser?", default=True):
        webbrowser.open("https://developers.facebook.com/tools/explorer/")
        console.print("\n[dim]Browser opened. Complete the authentication flow there.[/dim]\n")

    console.print("\n[bold]Step 2: Enter Your Token[/bold]\n")

    short_token = click.prompt(
        "Paste your short-lived access token",
        hide_input=True,
    )

    if not short_token or len(short_token) < 50:
        console.print("[red]Invalid token format. Please try again.[/red]")
        return

    console.print("\n[dim]Exchanging for long-lived token...[/dim]")

    # Exchange for long-lived token
    long_token_result = asyncio.run(_exchange_for_long_lived_token(short_token))

    if not long_token_result:
        return

    long_token, expires_in = long_token_result

    console.print("[green]Successfully obtained long-lived token![/green]\n")

    # Get Instagram account info
    console.print("[dim]Fetching Instagram account info...[/dim]")

    account_info = asyncio.run(_get_instagram_account_id(long_token))

    if not account_info:
        console.print("[yellow]Warning: Could not fetch Instagram account ID.[/yellow]")
        console.print("You may need to set INSTAGRAM_ACCOUNT_ID manually in .env\n")

    # Store the token
    console.print("[dim]Storing token securely...[/dim]")

    _store_token(long_token, expires_in, account_info)

    # Display summary
    expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

    console.print("\n[bold green]Authentication Complete![/bold green]\n")

    table = Table(title="Token Details")
    table.add_column("Property", style="cyan")
    table.add_column("Value")

    table.add_row("Token Type", "Long-lived Access Token")
    table.add_row("Expires", expires_at.strftime("%Y-%m-%d %H:%M UTC"))
    table.add_row("Valid For", f"{expires_in // 86400} days")
    table.add_row("Storage", "Encrypted in database")

    if account_info:
        table.add_row("Instagram Account ID", account_info.get("id", "N/A"))
        table.add_row("Username", f"@{account_info.get('username', 'N/A')}")

    console.print(table)

    console.print("\n[bold]Next Steps:[/bold]")
    console.print("1. Set ENABLE_INSTAGRAM_API=true in .env")
    if account_info:
        console.print(f"2. Set INSTAGRAM_ACCOUNT_ID={account_info.get('id')} in .env")
    console.print("3. Run: storyline-cli check-health")


async def _exchange_for_long_lived_token(short_token: str) -> tuple:
    """Exchange short-lived token for long-lived token."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://graph.facebook.com/v18.0/oauth/access_token",
                params={
                    "grant_type": "fb_exchange_token",
                    "client_id": settings.FACEBOOK_APP_ID,
                    "client_secret": settings.FACEBOOK_APP_SECRET,
                    "fb_exchange_token": short_token,
                },
                timeout=30.0,
            )

            if response.status_code != 200:
                error = response.json()
                console.print("\n[red]Error exchanging token:[/red]")
                console.print(f"  {error.get('error', {}).get('message', 'Unknown error')}")
                return None

            data = response.json()
            return (
                data.get("access_token"),
                data.get("expires_in", 5184000),  # Default 60 days
            )

    except httpx.RequestError as e:
        console.print(f"\n[red]Network error:[/red] {e}")
        return None


async def _get_instagram_account_id(token: str) -> dict:
    """Get Instagram Business Account ID from the access token."""
    try:
        async with httpx.AsyncClient() as client:
            # First, get the Facebook Pages
            pages_response = await client.get(
                "https://graph.facebook.com/v18.0/me/accounts",
                params={"access_token": token},
                timeout=30.0,
            )

            if pages_response.status_code != 200:
                return None

            pages = pages_response.json().get("data", [])

            if not pages:
                console.print("[yellow]No Facebook Pages found.[/yellow]")
                return None

            # Get Instagram account linked to the first page
            page_id = pages[0]["id"]

            ig_response = await client.get(
                f"https://graph.facebook.com/v18.0/{page_id}",
                params={
                    "fields": "instagram_business_account",
                    "access_token": token,
                },
                timeout=30.0,
            )

            if ig_response.status_code != 200:
                return None

            ig_data = ig_response.json()
            ig_account = ig_data.get("instagram_business_account")

            if not ig_account:
                console.print("[yellow]No Instagram Business Account linked to your Page.[/yellow]")
                return None

            ig_account_id = ig_account["id"]

            # Get Instagram username
            username_response = await client.get(
                f"https://graph.facebook.com/v18.0/{ig_account_id}",
                params={
                    "fields": "username",
                    "access_token": token,
                },
                timeout=30.0,
            )

            username = "unknown"
            if username_response.status_code == 200:
                username = username_response.json().get("username", "unknown")

            return {
                "id": ig_account_id,
                "username": username,
            }

    except httpx.RequestError as e:
        console.print(f"[yellow]Could not fetch account info: {e}[/yellow]")
        return None


def _store_token(token: str, expires_in: int, account_info: dict = None):
    """Store the encrypted token in the database."""
    encryption = TokenEncryption()
    token_repo = TokenRepository()

    encrypted = encryption.encrypt(token)
    issued_at = datetime.utcnow()
    expires_at = issued_at + timedelta(seconds=expires_in)

    metadata = {
        "authenticated_at": issued_at.isoformat(),
        "method": "cli_wizard",
    }

    if account_info:
        metadata["instagram_account_id"] = account_info.get("id")
        metadata["instagram_username"] = account_info.get("username")

    token_repo.create_or_update(
        service_name="instagram",
        token_type="access_token",
        token_value=encrypted,
        issued_at=issued_at,
        expires_at=expires_at,
        scopes=["instagram_basic", "instagram_content_publish", "pages_show_list"],
        metadata=metadata,
    )


@click.command(name="instagram-status")
def instagram_status():
    """Check Instagram API authentication status."""
    console.print("[bold blue]Instagram API Status[/bold blue]\n")

    service = TokenRefreshService()
    health = service.check_token_health("instagram")

    table = Table()
    table.add_column("Property", style="cyan")
    table.add_column("Value")

    # Token status
    if health["valid"]:
        table.add_row("Status", "[green]Authenticated[/green]")
    else:
        table.add_row("Status", f"[red]Not Authenticated[/red] - {health.get('error', 'Unknown')}")

    # Source
    if health["exists"]:
        table.add_row("Token Source", health.get("source", "unknown"))

    # Expiry
    if health["expires_at"]:
        expires_at = health["expires_at"]
        hours = health.get("expires_in_hours", 0)
        days = int(hours // 24) if hours else 0

        if days > 7:
            table.add_row("Expires", f"{expires_at.strftime('%Y-%m-%d')} ({days} days)")
        elif days > 0:
            table.add_row("Expires", f"[yellow]{expires_at.strftime('%Y-%m-%d')} ({days} days)[/yellow]")
        else:
            table.add_row("Expires", f"[red]{expires_at.strftime('%Y-%m-%d %H:%M')} ({int(hours)} hours)[/red]")

    # Refresh needed
    if health.get("needs_refresh"):
        table.add_row("Refresh", "[yellow]Recommended (expiring soon)[/yellow]")
    elif health.get("needs_bootstrap"):
        table.add_row("Bootstrap", "[yellow]Token in .env, not yet in DB[/yellow]")

    # Last refreshed
    if health.get("last_refreshed"):
        table.add_row("Last Refreshed", health["last_refreshed"].strftime("%Y-%m-%d %H:%M"))

    console.print(table)

    # Show config status
    console.print("\n[bold]Configuration:[/bold]")

    config_table = Table(show_header=False)
    config_table.add_column("Setting", style="dim")
    config_table.add_column("Status")

    config_table.add_row(
        "ENABLE_INSTAGRAM_API",
        "[green]true[/green]" if settings.ENABLE_INSTAGRAM_API else "[dim]false[/dim]"
    )
    config_table.add_row(
        "INSTAGRAM_ACCOUNT_ID",
        "[green]set[/green]" if settings.INSTAGRAM_ACCOUNT_ID else "[yellow]not set[/yellow]"
    )
    config_table.add_row(
        "FACEBOOK_APP_ID",
        "[green]set[/green]" if settings.FACEBOOK_APP_ID else "[red]not set[/red]"
    )
    config_table.add_row(
        "CLOUDINARY_CLOUD_NAME",
        "[green]set[/green]" if settings.CLOUDINARY_CLOUD_NAME else "[yellow]not set[/yellow]"
    )

    console.print(config_table)


@click.command(name="add-instagram-account")
@click.option("--display-name", required=True, help="User-friendly name for this account")
@click.option("--account-id", required=True, help="Instagram Business Account ID from Meta")
@click.option("--username", required=True, help="Instagram @username")
@click.option("--access-token", prompt=True, hide_input=True, help="Long-lived access token")
@click.option("--expires-days", default=60, help="Token expiry in days (default: 60)")
@click.option("--set-active", is_flag=True, help="Set this as the active account")
def add_instagram_account(display_name, account_id, username, access_token, expires_days, set_active):
    """
    Add a new Instagram account for posting.

    Supports multiple Instagram accounts within a single deployment.
    Use /settings in Telegram to switch between accounts.

    Example:
        storyline-cli add-instagram-account \\
            --display-name "Main Brand" \\
            --account-id "17841234567890" \\
            --username "brand_main" \\
            --set-active
    """
    from src.services.core.instagram_account_service import InstagramAccountService
    from src.utils.encryption import TokenEncryption

    console.print(Panel.fit(
        f"[bold blue]Adding Instagram Account[/bold blue]\n\n"
        f"Display Name: {display_name}\n"
        f"Account ID: {account_id}\n"
        f"Username: @{username.lstrip('@')}",
        title="Storyline AI"
    ))

    # Validate token
    if not access_token or len(access_token) < 50:
        console.print("[red]Error: Invalid access token format[/red]")
        return

    # Encrypt token
    encryption = TokenEncryption()
    encrypted_token = encryption.encrypt(access_token)

    # Calculate expiry
    expires_at = datetime.utcnow() + timedelta(days=expires_days)

    # Add account via service
    service = InstagramAccountService()

    try:
        account = service.add_account(
            display_name=display_name,
            instagram_account_id=account_id,
            instagram_username=username,
            access_token=encrypted_token,
            token_expires_at=expires_at,
            set_as_active=set_active,
            telegram_chat_id=settings.ADMIN_TELEGRAM_CHAT_ID if set_active else None
        )

        console.print("\n[bold green]Account added successfully![/bold green]\n")

        table = Table(title="Account Details")
        table.add_column("Property", style="cyan")
        table.add_column("Value")

        table.add_row("Account ID (Internal)", str(account.id))
        table.add_row("Display Name", account.display_name)
        table.add_row("Instagram ID", account.instagram_account_id)
        table.add_row("Username", f"@{account.instagram_username}")
        table.add_row("Token Expires", expires_at.strftime("%Y-%m-%d"))
        table.add_row("Active", "[green]Yes[/green]" if set_active else "No")

        console.print(table)

        if not set_active:
            console.print("\n[dim]Use /settings in Telegram to set this as the active account.[/dim]")

    except ValueError as e:
        console.print(f"\n[red]Error:[/red] {e}")


@click.command(name="list-instagram-accounts")
@click.option("--all", "include_inactive", is_flag=True, help="Include deactivated accounts")
def list_instagram_accounts(include_inactive):
    """
    List all Instagram accounts.

    Shows all configured Instagram accounts with their status and
    whether they're currently active for posting.
    """
    from src.services.core.instagram_account_service import InstagramAccountService
    from src.repositories.token_repository import TokenRepository

    service = InstagramAccountService()
    token_repo = TokenRepository()

    accounts = service.list_accounts(include_inactive=include_inactive)
    active_account = service.get_active_account(settings.ADMIN_TELEGRAM_CHAT_ID)

    if not accounts:
        console.print("[yellow]No Instagram accounts configured.[/yellow]")
        console.print("\nAdd an account with:")
        console.print("  storyline-cli add-instagram-account --help")
        return

    table = Table(title="Instagram Accounts")
    table.add_column("Active", justify="center")
    table.add_column("Display Name", style="cyan")
    table.add_column("Username")
    table.add_column("Instagram ID")
    table.add_column("Token Status")
    table.add_column("Status")

    for account in accounts:
        is_active = active_account and str(active_account.id) == str(account.id)

        # Check token status
        token = token_repo.get_token_for_account(str(account.id))
        if token:
            if token.is_expired:
                token_status = "[red]Expired[/red]"
            elif token.hours_until_expiry() and token.hours_until_expiry() < 168:
                token_status = f"[yellow]{int(token.hours_until_expiry() / 24)}d left[/yellow]"
            else:
                hours = token.hours_until_expiry()
                token_status = f"[green]{int(hours / 24) if hours else '∞'}d left[/green]"
        else:
            token_status = "[red]No token[/red]"

        table.add_row(
            "✓" if is_active else "",
            account.display_name,
            f"@{account.instagram_username}" if account.instagram_username else "-",
            account.instagram_account_id,
            token_status,
            "[green]Active[/green]" if account.is_active else "[dim]Disabled[/dim]"
        )

    console.print(table)

    if active_account:
        console.print(f"\n[dim]Active account: {active_account.display_name}[/dim]")
    else:
        console.print("\n[yellow]No account selected as active. Use /settings in Telegram to select one.[/yellow]")


@click.command(name="deactivate-instagram-account")
@click.argument("username_or_id")
def deactivate_instagram_account(username_or_id):
    """
    Deactivate an Instagram account (soft delete).

    The account and tokens are preserved but won't appear in the selection list.

    Argument can be the @username or the internal account UUID.
    """
    from src.services.core.instagram_account_service import InstagramAccountService

    service = InstagramAccountService()

    # Try to find account by username first, then by ID
    account = service.get_account_by_username(username_or_id)
    if not account:
        account = service.get_account_by_id(username_or_id)

    if not account:
        console.print(f"[red]Error: Account '{username_or_id}' not found[/red]")
        return

    if not account.is_active:
        console.print(f"[yellow]Account '{account.display_name}' is already deactivated[/yellow]")
        return

    if click.confirm(f"Deactivate account '{account.display_name}' (@{account.instagram_username})?"):
        service.deactivate_account(str(account.id))
        console.print(f"[green]Account '{account.display_name}' has been deactivated[/green]")
    else:
        console.print("[dim]Cancelled[/dim]")


@click.command(name="reactivate-instagram-account")
@click.argument("username_or_id")
def reactivate_instagram_account(username_or_id):
    """
    Reactivate a previously deactivated Instagram account.

    Argument can be the @username or the internal account UUID.
    """
    from src.services.core.instagram_account_service import InstagramAccountService

    service = InstagramAccountService()

    # Try to find account by username first, then by ID
    account = service.get_account_by_username(username_or_id)
    if not account:
        account = service.get_account_by_id(username_or_id)

    if not account:
        console.print(f"[red]Error: Account '{username_or_id}' not found[/red]")
        return

    if account.is_active:
        console.print(f"[yellow]Account '{account.display_name}' is already active[/yellow]")
        return

    service.reactivate_account(str(account.id))
    console.print(f"[green]Account '{account.display_name}' has been reactivated[/green]")
