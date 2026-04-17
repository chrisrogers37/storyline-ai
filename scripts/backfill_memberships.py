#!/usr/bin/env python3
"""Backfill user_chat_memberships from historical user_interactions.

Phase 1b of the multi-account dashboard migration.

Usage:
    python scripts/backfill_memberships.py                # dry run
    python scripts/backfill_memberships.py --apply        # backfill + verify
    python scripts/backfill_memberships.py --promote      # role promotion only
    python scripts/backfill_memberships.py --verify       # verification only

GATE: Phase 2 cannot deploy until --verify returns 0 gaps.
"""

import argparse
import asyncio
import sys
import time

from sqlalchemy import text

from src.config.database import get_db
from src.config.settings import settings
from src.utils.logger import logger


# ---------------------------------------------------------------------------
# Backfill
# ---------------------------------------------------------------------------

BACKFILL_SQL = text("""
    INSERT INTO user_chat_memberships (user_id, chat_settings_id, instance_role, joined_at)
    SELECT
        ui.user_id,
        cs.id,
        'member',
        MIN(ui.created_at)
    FROM user_interactions ui
    JOIN chat_settings cs ON cs.telegram_chat_id = ui.telegram_chat_id
    WHERE ui.user_id IS NOT NULL
      AND ui.telegram_chat_id < 0
      AND ui.interaction_type IN ('command', 'callback')
    GROUP BY ui.user_id, cs.id
    ON CONFLICT (user_id, chat_settings_id) DO NOTHING
""")

BACKFILL_PREVIEW_SQL = text("""
    SELECT
        u.id AS user_id,
        u.telegram_username,
        cs.telegram_chat_id,
        cs.display_name,
        MIN(ui.created_at) AS first_interaction
    FROM user_interactions ui
    JOIN chat_settings cs ON cs.telegram_chat_id = ui.telegram_chat_id
    JOIN users u ON u.id = ui.user_id
    WHERE ui.user_id IS NOT NULL
      AND ui.telegram_chat_id < 0
      AND ui.interaction_type IN ('command', 'callback')
    GROUP BY u.id, u.telegram_username, cs.telegram_chat_id, cs.display_name
    ORDER BY u.telegram_username, MIN(ui.created_at)
""")


def run_backfill(dry_run: bool = True) -> int:
    """Backfill memberships from user_interactions."""
    db = next(get_db())
    try:
        # Preview
        rows = db.execute(BACKFILL_PREVIEW_SQL).fetchall()
        if not rows:
            logger.info("No group interactions found — nothing to backfill.")
            return 0

        logger.info(f"Found {len(rows)} user-chat pairs to backfill:")
        for row in rows:
            username = row.telegram_username or "(no username)"
            name = row.display_name or str(row.telegram_chat_id)
            logger.info(f"  {username} → {name} (since {row.first_interaction})")

        if dry_run:
            logger.info("\nDry run — no changes made. Pass --apply to execute.")
            return len(rows)

        # Execute
        result = db.execute(BACKFILL_SQL)
        db.commit()
        inserted = result.rowcount
        logger.info(f"\n✓ Backfill complete: {inserted} memberships created.")
        return inserted

    finally:
        db.close()


# ---------------------------------------------------------------------------
# Role Promotion
# ---------------------------------------------------------------------------


async def promote_roles() -> int:
    """Call getChatAdministrators for each group and promote memberships."""
    import httpx

    db = next(get_db())
    try:
        # Get all distinct group chat_ids that have memberships
        chat_rows = db.execute(
            text("""
            SELECT DISTINCT cs.telegram_chat_id, cs.id AS chat_settings_id
            FROM user_chat_memberships ucm
            JOIN chat_settings cs ON cs.id = ucm.chat_settings_id
            WHERE ucm.is_active = TRUE
              AND cs.telegram_chat_id < 0
        """)
        ).fetchall()

        if not chat_rows:
            logger.info("No active group memberships found — nothing to promote.")
            return 0

        logger.info(f"Checking admin status for {len(chat_rows)} groups...")
        promoted = 0
        bot_url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}"

        async with httpx.AsyncClient(timeout=10) as client:
            for chat_row in chat_rows:
                chat_id = chat_row.telegram_chat_id
                cs_id = str(chat_row.chat_settings_id)

                try:
                    resp = await client.get(
                        f"{bot_url}/getChatAdministrators",
                        params={"chat_id": chat_id},
                    )
                    data = resp.json()

                    if not data.get("ok"):
                        logger.warning(
                            f"  getChatAdministrators failed for {chat_id}: "
                            f"{data.get('description', 'unknown error')}"
                        )
                        await asyncio.sleep(0.05)
                        continue

                    for admin in data.get("result", []):
                        tg_user_id = admin["user"]["id"]
                        status = admin["status"]  # "creator" or "administrator"

                        if admin["user"].get("is_bot", False):
                            continue

                        role = "owner" if status == "creator" else "admin"

                        updated = db.execute(
                            text("""
                                UPDATE user_chat_memberships
                                SET instance_role = :role
                                FROM users u
                                WHERE user_chat_memberships.user_id = u.id
                                  AND u.telegram_user_id = :tg_user_id
                                  AND user_chat_memberships.chat_settings_id = :cs_id
                                  AND user_chat_memberships.instance_role = 'member'
                            """),
                            {"role": role, "tg_user_id": tg_user_id, "cs_id": cs_id},
                        )
                        if updated.rowcount > 0:
                            username = admin["user"].get("username", tg_user_id)
                            logger.info(f"  Promoted @{username} → {role} in {chat_id}")
                            promoted += 1

                    db.commit()

                except Exception as e:
                    logger.warning(f"  Error for chat {chat_id}: {e}")
                    db.rollback()

                # Rate limit: 50ms between API calls
                await asyncio.sleep(0.05)

        logger.info(f"\n✓ Role promotion complete: {promoted} users promoted.")
        return promoted

    finally:
        db.close()


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

# Catches fully-missed users; partial per-group gaps require manual inspection.
VERIFY_SQL = text("""
    SELECT u.id, u.telegram_username, COUNT(DISTINCT ui.telegram_chat_id) AS groups
    FROM users u
    JOIN user_interactions ui ON ui.user_id = u.id
    WHERE ui.telegram_chat_id < 0
      AND ui.interaction_type IN ('command', 'callback')
    GROUP BY u.id, u.telegram_username
    HAVING COUNT(DISTINCT ui.telegram_chat_id) > 0
    AND u.id NOT IN (SELECT user_id FROM user_chat_memberships)
""")


def run_verification() -> int:
    """Check for users with group interactions but no memberships."""
    db = next(get_db())
    try:
        gaps = db.execute(VERIFY_SQL).fetchall()

        if not gaps:
            logger.info(
                "✓ Verification passed: all users with group interactions have memberships."
            )
            return 0

        logger.error(f"✗ Verification FAILED: {len(gaps)} users missing memberships:")
        for row in gaps:
            username = row.telegram_username or "(no username)"
            logger.error(f"  {username} (id={row.id}) — {row.groups} group(s)")

        logger.error("\nPhase 2 CANNOT deploy until this is resolved.")
        return len(gaps)

    finally:
        db.close()


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


def print_stats():
    """Print current membership statistics."""
    db = next(get_db())
    try:
        total = db.execute(text("SELECT COUNT(*) FROM user_chat_memberships")).scalar()
        active = db.execute(
            text("SELECT COUNT(*) FROM user_chat_memberships WHERE is_active = TRUE")
        ).scalar()
        by_role = db.execute(
            text(
                "SELECT instance_role, COUNT(*) FROM user_chat_memberships "
                "GROUP BY instance_role ORDER BY instance_role"
            )
        ).fetchall()

        logger.info(f"Memberships: {total} total ({active} active)")
        for role, count in by_role:
            logger.info(f"  {role}: {count}")

    finally:
        db.close()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Backfill user_chat_memberships from historical interactions."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Execute the backfill (default is dry run)",
    )
    parser.add_argument(
        "--promote",
        action="store_true",
        help="Run role promotion via Telegram getChatAdministrators",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Run verification query only",
    )
    args = parser.parse_args()

    if args.apply and args.promote:
        parser.error("Cannot combine --apply and --promote. Run them sequentially.")

    start = time.time()

    if args.verify:
        gaps = run_verification()
        print_stats()
        sys.exit(1 if gaps > 0 else 0)

    if args.promote:
        asyncio.run(promote_roles())
        print_stats()
        sys.exit(0)

    # Default: backfill (dry run unless --apply)
    run_backfill(dry_run=not args.apply)

    if args.apply:
        logger.info("\nRunning verification...")
        gaps = run_verification()
        print_stats()

        elapsed = time.time() - start
        logger.info(f"\nCompleted in {elapsed:.1f}s")
        sys.exit(1 if gaps > 0 else 0)


if __name__ == "__main__":
    main()
