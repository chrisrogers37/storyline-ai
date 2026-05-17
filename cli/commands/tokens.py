"""Token management CLI commands."""

import asyncio

import click
from rich.console import Console
from rich.table import Table

console = Console()


@click.command(name="revoke-tokens")
@click.option(
    "--service",
    required=True,
    type=click.Choice(["instagram", "google_drive"]),
    help="Service whose tokens to revoke",
)
@click.option(
    "--account-id",
    default=None,
    help="Instagram account UUID (scopes revocation to one account)",
)
@click.option(
    "--chat-id",
    default=None,
    type=int,
    help="Telegram chat ID (scopes revocation to one tenant's Google Drive tokens)",
)
@click.option(
    "--skip-provider",
    is_flag=True,
    help="Skip calling provider revocation APIs (DB-only revocation)",
)
def revoke_tokens(service, account_id, chat_id, skip_provider):
    """Revoke OAuth tokens for a service (for compromised credentials).

    Calls the provider's revocation API (Meta DELETE /me/permissions for
    Instagram, Google POST /revoke for Drive), then marks tokens as revoked
    in the database. Revoked tokens are excluded from all future queries.

    Re-authentication via the normal OAuth flow will clear the revocation
    and issue a fresh token.
    """
    from src.services.integrations.token_refresh import TokenRefreshService
    from src.repositories.token_repository import TokenRepository

    chat_settings_id = None
    if chat_id:
        from src.repositories.chat_settings_repository import ChatSettingsRepository

        settings_repo = ChatSettingsRepository()
        chat_settings = settings_repo.get_by_chat_id(chat_id)
        if not chat_settings:
            console.print(f"[red]No chat settings found for chat ID {chat_id}[/red]")
            return
        chat_settings_id = str(chat_settings.id)

    # Show what will be revoked
    token_repo = TokenRepository()
    from src.models.api_token import ApiToken

    query = token_repo.db.query(ApiToken).filter(
        ApiToken.service_name == service,
        ApiToken.revoked_at.is_(None),
    )
    if account_id:
        query = query.filter(ApiToken.instagram_account_id == account_id)
    if chat_settings_id:
        query = query.filter(ApiToken.chat_settings_id == chat_settings_id)
    preview = query.all()
    token_repo.end_read_transaction()

    if not preview:
        console.print(f"[yellow]No active tokens found for {service}.[/yellow]")
        return

    table = Table(title=f"Tokens to revoke ({service})")
    table.add_column("Type", style="cyan")
    table.add_column("Issued", style="dim")
    table.add_column("Expires", style="dim")
    for t in preview:
        table.add_row(
            t.token_type,
            str(t.issued_at)[:19] if t.issued_at else "—",
            str(t.expires_at)[:19] if t.expires_at else "never",
        )
    console.print(table)

    provider_note = " (provider APIs will NOT be called)" if skip_provider else ""
    if not click.confirm(
        f"\nRevoke {len(preview)} token(s) for {service}?{provider_note}"
    ):
        console.print("[dim]Cancelled[/dim]")
        return

    refresh_service = TokenRefreshService()
    result = asyncio.run(
        refresh_service.revoke_tokens(
            service_name=service,
            instagram_account_id=account_id,
            chat_settings_id=chat_settings_id,
            skip_provider=skip_provider,
        )
    )

    console.print(f"\n[green]Revoked {result['revoked']} token(s).[/green]")

    for pr in result.get("provider_results", []):
        if pr.get("success"):
            console.print(
                f"  Provider ({pr.get('service', service)}): "
                f"[green]revoked upstream[/green]"
            )
        elif pr.get("error"):
            console.print(
                f"  Provider ({pr.get('service', service)}): "
                f"[yellow]best-effort failed: {pr['error']}[/yellow]"
            )
        else:
            console.print(
                f"  Provider ({pr.get('service', service)}): "
                f"HTTP {pr.get('status_code', '?')}"
            )

    console.print(
        f"\n[dim]Re-authenticate via the normal OAuth flow to issue "
        f"fresh tokens for {service}.[/dim]"
    )
