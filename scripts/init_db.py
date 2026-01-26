#!/usr/bin/env python3
"""Initialize database using SQLAlchemy models."""

from src.config.database import init_db
from src.utils.logger import logger

if __name__ == "__main__":
    logger.info("Initializing database...")

    try:
        init_db()
        logger.info("✓ Database initialized successfully")
    except Exception as e:
        logger.error(f"✗ Database initialization failed: {e}")
        raise
