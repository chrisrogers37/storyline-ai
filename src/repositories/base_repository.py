"""Base repository class with proper session management."""

from typing import Optional

from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.utils.logger import logger
from src.utils.resilience import db_circuit_breaker


class BaseRepository:
    """
    Base class for all repositories.

    Handles database session lifecycle to prevent connection pool exhaustion.
    Sessions are created on demand and must be closed when done.

    Integrates with a circuit breaker so that when the database is
    unreachable, subsequent operations fail fast instead of hanging
    for 30 seconds on the pool timeout.

    IMPORTANT: Always call commit() after write operations and
    end_read_transaction() after read-only operations to prevent
    "idle in transaction" connections.
    """

    def __init__(self):
        self._db_generator = get_db()
        self._db: Session = next(self._db_generator)

    @property
    def db(self) -> Session:
        """Get the database session, ensuring it's in a clean state.

        Checks the circuit breaker before returning the session. If the
        circuit is open (DB has been failing), raises OperationalError
        immediately instead of waiting for a pool timeout.
        """
        if not db_circuit_breaker.allow_request():
            raise OperationalError(
                "Database circuit breaker is open — failing fast",
                params=None,
                orig=None,
            )

        # Rollback any failed transaction to reset session state
        try:
            if not self._db.is_active:
                self._db.rollback()
        except Exception as e:
            # Rollback failed — connection is likely severed (e.g. Neon idle timeout).
            # Create a fresh session instead of returning a broken one.
            logger.warning(
                f"Session recovery rollback failed, creating new session: {e}"
            )
            db_circuit_breaker.record_failure()
            try:
                self._db.close()
            except Exception as close_err:
                logger.warning(f"Failed to close broken session: {close_err}")
            self._db_generator = get_db()
            self._db = next(self._db_generator)
        return self._db

    def commit(self):
        """Commit the current transaction."""
        try:
            self._db.commit()
            db_circuit_breaker.record_success()
        except Exception as e:
            logger.warning(f"Error during commit: {e}")
            db_circuit_breaker.record_failure()
            self._db.rollback()
            raise

    def rollback(self):
        """Rollback the current transaction."""
        try:
            self._db.rollback()
        except Exception as e:
            logger.warning(f"Error during rollback: {e}")

    def end_read_transaction(self):
        """
        End a read-only transaction by committing (releases locks).

        Call this after read-only operations to prevent "idle in transaction"
        connections. In SQLAlchemy, even SELECT queries start a transaction
        that must be ended.

        If both commit and rollback fail (e.g. dead SSL connection), replaces
        the session entirely so the next operation starts clean.
        """
        try:
            self._db.commit()
        except Exception as commit_err:
            # If commit fails on a read-only transaction, rollback
            logger.debug(f"Read transaction commit failed, rolling back: {commit_err}")
            try:
                self._db.rollback()
            except Exception as rollback_err:
                # Both commit and rollback failed — connection is dead.
                # Replace the session entirely.
                logger.warning(
                    f"Session unrecoverable (commit: {commit_err}, "
                    f"rollback: {rollback_err}), creating fresh session"
                )
                try:
                    self._db.close()
                except Exception as close_err:
                    logger.warning(f"Failed to close dead session: {close_err}")
                self._db_generator = get_db()
                self._db = next(self._db_generator)

    def close(self):
        """
        Close the database session and return connection to pool.

        Call this when you're done with the repository to prevent
        connection pool exhaustion.
        """
        try:
            # Exhaust the generator to trigger the finally block
            # which closes the session
            try:
                next(self._db_generator)
            except StopIteration:
                pass  # Expected: generator already exhausted from __init__
        except Exception as e:
            logger.warning(f"Error closing database session: {e}")
        finally:
            # Also explicitly close just in case
            try:
                self._db.close()
            except Exception as e:
                # Suppressed: session.close() during cleanup is best-effort.
                # The session may already be closed or the pool invalidated.
                logger.debug(f"Suppressed error during session close: {e}")

    def __del__(self):
        """Cleanup when repository is garbage collected."""
        try:
            self.close()
        except Exception:
            # Suppressed intentionally: during garbage collection / interpreter shutdown,
            # logging infrastructure may already be torn down. Attempting to log here
            # could itself raise errors. The close() method already has its own logging.
            pass

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures session is closed."""
        self.close()
        return False  # Don't suppress exceptions

    def use_session(self, session: Session):
        """Temporarily use a shared session for coordinated multi-repo transactions.

        This allows multiple repositories to operate on the same database
        session so their writes can be committed or rolled back atomically.

        The caller is responsible for committing or rolling back the shared session.

        Args:
            session: An existing SQLAlchemy Session to use instead of this repo's own.
        """
        self._db = session

    def _apply_tenant_filter(
        self, query, model_class, chat_settings_id: Optional[str] = None
    ):
        """Apply tenant filter if chat_settings_id is provided. No-op when None."""
        if chat_settings_id:
            query = query.filter(model_class.chat_settings_id == chat_settings_id)
        return query

    def _tenant_query(self, model_class, chat_settings_id=None):
        """Start a query with automatic tenant filtering applied."""
        query = self.db.query(model_class)
        return self._apply_tenant_filter(query, model_class, chat_settings_id)

    @staticmethod
    def check_connection():
        """
        Verify database connectivity by executing a simple query.

        Used by HealthCheckService to test the database connection
        without violating the service/repository layer boundary.

        Raises:
            Exception: If database is unreachable or query fails
        """
        from sqlalchemy import text

        db = next(get_db())
        try:
            db.execute(text("SELECT 1"))
        finally:
            db.close()
