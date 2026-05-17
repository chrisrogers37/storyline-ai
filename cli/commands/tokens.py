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


@click.command(name="rotate-keys")
def rotate_keys():
    """Re-encrypt all stored tokens with the current primary encryption key.

    Reads all encrypted token values from api_tokens, decrypts each with
    MultiFernet (tries all keys in ENCRYPTION_KEYS), and re-encrypts with
    the primary (first) key.

    Rotation workflow:
      1. Generate a new key: python -c "from src.utils.encryption import TokenEncryption; print(TokenEncryption.generate_key())"
      2. Prepend it to ENCRYPTION_KEYS in .env: ENCRYPTION_KEYS=NEW_KEY,OLD_KEY
      3. Deploy (new tokens use the new key; old tokens still decrypt)
      4. Run: storydump-cli rotate-keys
      5. Remove OLD_KEY from ENCRYPTION_KEYS
    """
    from src.repositories.token_repository import TokenRepository
    from src.models.api_token import ApiToken
    from src.utils.encryption import TokenEncryption

    encryption = TokenEncryption()
    token_repo = TokenRepository()

    # Fetch all tokens (including revoked — they still have encrypted values)
    tokens = token_repo.db.query(ApiToken).all()

    if not tokens:
        console.print("[yellow]No tokens found in database.[/yellow]")
        token_repo.close()
        return

    console.print(f"Found {len(tokens)} token(s) to rotate.")

    rotated = 0
    failed = 0

    try:
        for token in tokens:
            try:
                token.token_value = encryption.rotate(token.token_value)
                rotated += 1
            except ValueError as e:
                console.print(
                    f"[red]Failed to rotate {token.service_name}/{token.token_type} "
                    f"(id={token.id}): {e}[/red]"
                )
                failed += 1

        if rotated > 0:
            token_repo.db.commit()
    except Exception:
        console.print(
            "\n[red]WARNING: rotation incomplete. Keep all keys in "
            "ENCRYPTION_KEYS until rotation succeeds.[/red]"
        )
        token_repo.db.rollback()
        token_repo.close()
        raise

    token_repo.close()

    console.print(f"\n[green]Rotated: {rotated}[/green]")
    if failed:
        console.print(f"[red]Failed: {failed}[/red]")
        console.print(
            "\n[red]WARNING: rotation incomplete. Keep all keys in "
            "ENCRYPTION_KEYS until rotation succeeds.[/red]"
        )

    if failed == 0 and rotated > 0:
        console.print(
            "\n[dim]All tokens now use the primary key. "
            "Old keys can be removed from ENCRYPTION_KEYS.[/dim]"
        )
