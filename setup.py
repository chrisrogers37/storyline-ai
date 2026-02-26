from setuptools import setup, find_packages

from src import __version__

setup(
    name="storyline-ai",
    version=__version__,
    description="Instagram Story Automation System with Telegram Integration",
    author="Your Name",
    packages=find_packages(),
    install_requires=[
        "alembic>=1.18.0",
        "click>=8.1.7",
        "cloudinary>=1.36.0",
        "cryptography>=41.0.0",
        "fastapi>=0.109.0",
        "google-api-python-client>=2.100.0",
        "google-auth>=2.23.0",
        "google-auth-oauthlib>=1.1.0",
        "httpx>=0.25.2",
        "Pillow>=10.1.0",
        "psycopg2-binary>=2.9.9",
        "pydantic>=2.5.0",
        "pydantic-settings>=2.1.0",
        "python-dateutil>=2.8.2",
        "python-dotenv>=1.0.0",
        "python-telegram-bot>=20.7",
        "rich>=13.7.0",
        "sqlalchemy>=2.0.23",
        "uvicorn>=0.27.0",
    ],
    entry_points={
        "console_scripts": [
            "storyline-cli=cli.main:cli",
        ],
    },
    python_requires=">=3.10",
)
