from setuptools import setup, find_packages

setup(
    name="storyline-ai",
    version="1.0.0",
    description="Instagram Story Automation System with Telegram Integration",
    author="Your Name",
    packages=find_packages(),
    install_requires=[
        "python-dotenv>=1.0.0",
        "pydantic>=2.5.0",
        "pydantic-settings>=2.1.0",
        "sqlalchemy>=2.0.23",
        "psycopg2-binary>=2.9.9",
        "python-telegram-bot>=20.7",
        "httpx>=0.25.2",
        "Pillow>=10.1.0",
        "click>=8.1.7",
        "rich>=13.7.0",
        "python-dateutil>=2.8.2",
    ],
    entry_points={
        "console_scripts": [
            "storyline-cli=cli.main:cli",
        ],
    },
    python_requires=">=3.10",
)
