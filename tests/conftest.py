"""Pytest configuration and fixtures."""
import os
import pytest
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Load test environment variables before importing any application code
load_dotenv(".env.test", override=True)

from src.config.database import Base
from src.config.settings import settings


def create_test_database():
    """Create test database if it doesn't exist."""
    # Connect to default postgres database to create test database
    conn = psycopg2.connect(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        database="postgres"
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()

    # Check if test database exists
    cursor.execute(
        "SELECT 1 FROM pg_database WHERE datname = %s",
        (settings.TEST_DB_NAME,)
    )
    exists = cursor.fetchone()

    if not exists:
        cursor.execute(f"CREATE DATABASE {settings.TEST_DB_NAME}")
        print(f"\n✓ Created test database: {settings.TEST_DB_NAME}")
    else:
        print(f"\n✓ Test database already exists: {settings.TEST_DB_NAME}")

    cursor.close()
    conn.close()


def drop_test_database():
    """Drop test database."""
    # Connect to default postgres database to drop test database
    conn = psycopg2.connect(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        database="postgres"
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()

    # Terminate all connections to test database
    cursor.execute(f"""
        SELECT pg_terminate_backend(pg_stat_activity.pid)
        FROM pg_stat_activity
        WHERE pg_stat_activity.datname = '{settings.TEST_DB_NAME}'
        AND pid <> pg_backend_pid()
    """)

    # Drop database
    cursor.execute(f"DROP DATABASE IF EXISTS {settings.TEST_DB_NAME}")
    print(f"\n✓ Dropped test database: {settings.TEST_DB_NAME}")

    cursor.close()
    conn.close()


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """
    Session-scoped fixture to create test database before tests run.

    This fixture:
    1. Creates the test database if it doesn't exist
    2. Creates all tables using SQLAlchemy models
    3. Yields control to tests
    4. Drops the test database after all tests complete
    """
    # Create test database
    create_test_database()

    # Create engine and tables
    engine = create_engine(settings.test_database_url)
    Base.metadata.create_all(engine)
    print(f"✓ Created all tables in test database")

    yield engine

    # Cleanup: drop all tables and database
    Base.metadata.drop_all(engine)
    engine.dispose()
    drop_test_database()


@pytest.fixture(scope="function")
def test_db(setup_test_database):
    """
    Function-scoped fixture providing a clean database session for each test.

    Each test gets a fresh transaction that is rolled back after the test completes,
    ensuring test isolation without recreating tables.
    """
    TestSessionLocal = sessionmaker(bind=setup_test_database)
    session = TestSessionLocal()

    # Begin a nested transaction
    session.begin_nested()

    yield session

    # Rollback everything from the test
    session.rollback()
    session.close()


@pytest.fixture
def sample_media_item():
    """Sample media item for testing."""
    return {
        "file_path": "/test/media/image.jpg",
        "file_name": "image.jpg",
        "file_hash": "abc123def456",
        "file_size_bytes": 1024000,
        "mime_type": "image/jpeg",
    }
