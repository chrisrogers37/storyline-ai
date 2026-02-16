"""OAuth redirect flow endpoints for Instagram and Google Drive."""

import html

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse

from src.services.core.oauth_service import OAuthService
from src.services.integrations.google_drive_oauth import GoogleDriveOAuthService
from src.utils.logger import logger

router = APIRouter(tags=["oauth"])


@router.get("/instagram/start")
async def instagram_oauth_start(
    chat_id: int = Query(..., description="Telegram chat ID initiating the flow"),
):
    """
    Generate Instagram OAuth authorization URL.

    Called when user clicks "Connect Instagram" in Telegram.
    Returns a redirect to Meta's authorization page.
    """
    oauth_service = OAuthService()
    try:
        auth_url = oauth_service.generate_authorization_url(chat_id)
        return RedirectResponse(url=auth_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        oauth_service.close()


@router.get("/instagram/callback")
async def instagram_oauth_callback(
    code: str = Query(None, description="Authorization code from Meta"),
    state: str = Query(..., description="Signed state token"),
    error: str = Query(None, description="Error code if user denied"),
    error_reason: str = Query(None, description="Error reason"),
    error_description: str = Query(None, description="Human-readable error"),
):
    """
    Handle Instagram OAuth callback.

    Meta redirects here after user authorizes (or denies).
    Exchanges the code for a long-lived token, stores it,
    and notifies the user in Telegram.
    """
    oauth_service = OAuthService()
    try:
        # Handle user denial
        if error:
            logger.warning(
                f"OAuth denied: {error} - {error_reason} - {error_description}"
            )
            # Validate state to get chat_id for notification
            try:
                chat_id = oauth_service.validate_state_token(state)
                await oauth_service.notify_telegram(
                    chat_id,
                    f"Instagram connection cancelled.\n"
                    f"Reason: {error_description or error_reason or error}",
                    success=False,
                )
            except ValueError:
                pass  # Can't notify if state is invalid
            return _error_html_page(
                "Connection Cancelled",
                "You cancelled the Instagram connection. "
                "You can try again from Telegram.",
            )

        if not code:
            raise HTTPException(status_code=400, detail="Missing authorization code")

        # Validate state token (CSRF protection + extract chat_id)
        try:
            chat_id = oauth_service.validate_state_token(state)
        except ValueError as e:
            logger.error(f"Invalid OAuth state: {e}")
            return _error_html_page(
                "Link Expired",
                "This authorization link has expired or is invalid. "
                "Please request a new one from Telegram.",
            )

        # Exchange code for tokens and store
        result = await oauth_service.exchange_and_store(code, chat_id)

        # Notify Telegram
        await oauth_service.notify_telegram(
            chat_id,
            f"Instagram connected! Account: @{result['username']}\n"
            f"Token valid for {result['expires_in_days']} days.",
            success=True,
        )

        return _success_html_page(result["username"])

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OAuth callback error: {e}", exc_info=True)
        return _error_html_page(
            "Connection Failed",
            "Something went wrong connecting your Instagram account. "
            "Please try again from Telegram.",
        )
    finally:
        oauth_service.close()


@router.get("/google-drive/start")
async def google_drive_oauth_start(
    chat_id: int = Query(..., description="Telegram chat ID initiating the flow"),
):
    """
    Generate Google Drive OAuth authorization URL.

    Called when user clicks "Connect Google Drive" in Telegram.
    Returns a redirect to Google's consent screen.
    """
    gdrive_service = GoogleDriveOAuthService()
    try:
        auth_url = gdrive_service.generate_authorization_url(chat_id)
        return RedirectResponse(url=auth_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        gdrive_service.close()


@router.get("/google-drive/callback")
async def google_drive_oauth_callback(
    code: str = Query(None, description="Authorization code from Google"),
    state: str = Query(..., description="Signed state token"),
    error: str = Query(None, description="Error code if user denied"),
):
    """
    Handle Google Drive OAuth callback.

    Google redirects here after user authorizes (or denies).
    Exchanges the code for tokens, stores per-tenant,
    and notifies the user in Telegram.
    """
    gdrive_service = GoogleDriveOAuthService()
    try:
        # Handle user denial
        if error:
            logger.warning(f"Google Drive OAuth denied: {error}")
            try:
                chat_id = gdrive_service.validate_state_token(state)
                await gdrive_service.notify_telegram(
                    chat_id,
                    "Google Drive connection cancelled.",
                    success=False,
                )
            except ValueError:
                pass  # Can't notify if state is invalid
            return _error_html_page(
                "Connection Cancelled",
                "You cancelled the Google Drive connection. "
                "You can try again from Telegram.",
            )

        if not code:
            raise HTTPException(status_code=400, detail="Missing authorization code")

        # Validate state token (CSRF protection + extract chat_id)
        try:
            chat_id = gdrive_service.validate_state_token(state)
        except ValueError as e:
            logger.error(f"Invalid Google Drive OAuth state: {e}")
            return _error_html_page(
                "Link Expired",
                "This authorization link has expired or is invalid. "
                "Please request a new one from Telegram.",
            )

        # Exchange code for tokens and store
        result = await gdrive_service.exchange_and_store(code, chat_id)

        # Notify Telegram
        await gdrive_service.notify_telegram(
            chat_id,
            f"Google Drive connected! Account: {result['email']}\n"
            f"Access token valid for {result['expires_in_hours']} hours "
            f"(auto-refreshes).",
            success=True,
        )

        return _gdrive_success_html_page(result["email"])

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Google Drive OAuth callback error: {e}", exc_info=True)
        return _error_html_page(
            "Connection Failed",
            "Something went wrong connecting your Google Drive. "
            "Please try again from Telegram.",
        )
    finally:
        gdrive_service.close()


def _gdrive_success_html_page(email: str) -> HTMLResponse:
    """Return a simple HTML success page for Google Drive."""
    safe_email = html.escape(email)
    return HTMLResponse(
        content=f"""
        <!DOCTYPE html>
        <html>
        <head><title>Storyline AI - Google Drive Connected!</title>
        <style>
            body {{ font-family: -apple-system, sans-serif; text-align: center;
                   padding: 60px 20px; background: #f5f5f5; }}
            .card {{ background: white; border-radius: 12px; padding: 40px;
                    max-width: 400px; margin: 0 auto;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
            h1 {{ color: #22c55e; }}
            p {{ color: #666; }}
        </style></head>
        <body>
        <div class="card">
            <h1>Google Drive Connected!</h1>
            <p>Your Google Drive (<strong>{safe_email}</strong>) has been
            connected to Storyline AI.</p>
            <p>You can close this window and return to Telegram.</p>
        </div>
        </body></html>
        """,
        status_code=200,
    )


def _success_html_page(username: str) -> HTMLResponse:
    """Return a simple HTML success page."""
    safe_username = html.escape(username)
    return HTMLResponse(
        content=f"""
        <!DOCTYPE html>
        <html>
        <head><title>Storyline AI - Connected!</title>
        <style>
            body {{ font-family: -apple-system, sans-serif; text-align: center;
                   padding: 60px 20px; background: #f5f5f5; }}
            .card {{ background: white; border-radius: 12px; padding: 40px;
                    max-width: 400px; margin: 0 auto;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
            h1 {{ color: #22c55e; }}
            p {{ color: #666; }}
        </style></head>
        <body>
        <div class="card">
            <h1>Connected!</h1>
            <p>Instagram account <strong>@{safe_username}</strong> has been
            connected to Storyline AI.</p>
            <p>You can close this window and return to Telegram.</p>
        </div>
        </body></html>
        """,
        status_code=200,
    )


def _error_html_page(title: str, message: str) -> HTMLResponse:
    """Return a simple HTML error page."""
    safe_title = html.escape(title)
    safe_message = html.escape(message)
    return HTMLResponse(
        content=f"""
        <!DOCTYPE html>
        <html>
        <head><title>Storyline AI - {safe_title}</title>
        <style>
            body {{ font-family: -apple-system, sans-serif; text-align: center;
                   padding: 60px 20px; background: #f5f5f5; }}
            .card {{ background: white; border-radius: 12px; padding: 40px;
                    max-width: 400px; margin: 0 auto;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
            h1 {{ color: #ef4444; }}
            p {{ color: #666; }}
        </style></head>
        <body>
        <div class="card">
            <h1>{safe_title}</h1>
            <p>{safe_message}</p>
        </div>
        </body></html>
        """,
        status_code=200,
    )
