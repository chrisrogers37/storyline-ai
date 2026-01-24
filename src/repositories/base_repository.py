"""Base repository class with proper session management."""
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.utils.logger import logger


class BaseRepository:
    """
    Base class for all repositories.

    Handles database session lifecycle to prevent connection pool exhaustion.
    Sessions are created on demand and must be closed when done.

    IMPORTANT: Always call commit() after write operations and
    end_read_transaction() after read-only operations to prevent
    "idle in transaction" connections.
    """

    def __init__(self):
        self._db_generator = get_db()
        self._db: Session = next(self._db_generator)

    @property
    def db(self) -> Session:
        """Get the database session, ensuring it's in a clean state."""
        # Rollback any failed transaction to reset session state
        try:
            if not self._db.is_active:
                self._db.rollback()
        except Exception:
            pass
        return self._db

    def commit(self):
        """Commit the current transaction."""
        try:
            self._db.commit()
        except Exception as e:
            logger.warning(f"Error during commit: {e}")
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
        """
        try:
            self._db.commit()
        except Exception:
            # If commit fails on a read-only transaction, rollback
            try:
                self._db.rollback()
            except Exception:
                pass

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
                pass
        except Exception as e:
            logger.warning(f"Error closing database session: {e}")
        finally:
            # Also explicitly close just in case
            try:
                self._db.close()
            except Exception:
                pass

    def __del__(self):
        """Cleanup when repository is garbage collected."""
        try:
            self.close()
        except Exception:
            # Suppress errors during garbage collection
            pass

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures session is closed."""
        self.close()
        return False  # Don't suppress exceptions
