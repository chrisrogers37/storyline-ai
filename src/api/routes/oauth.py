"""Instagram OAuth redirect flow endpoints."""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse

from src.services.core.oauth_service import OAuthService
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


def _success_html_page(username: str) -> HTMLResponse:
    """Return a simple HTML success page."""
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
            <p>Instagram account <strong>@{username}</strong> has been
            connected to Storyline AI.</p>
            <p>You can close this window and return to Telegram.</p>
        </div>
        </body></html>
        """,
        status_code=200,
    )


def _error_html_page(title: str, message: str) -> HTMLResponse:
    """Return a simple HTML error page."""
    return HTMLResponse(
        content=f"""
        <!DOCTYPE html>
        <html>
        <head><title>Storyline AI - {title}</title>
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
            <h1>{title}</h1>
            <p>{message}</p>
        </div>
        </body></html>
        """,
        status_code=200,
    )
