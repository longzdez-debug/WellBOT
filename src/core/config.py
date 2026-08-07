"""Core configuration from environment variables."""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Application configuration."""

    # Telegram
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    ADMIN_ID: int = int(os.getenv("ADMIN_ID", "0"))

    # Subscription
    TRIAL_DAYS: int = int(os.getenv("TRIAL_DAYS", "3"))

    # Monitoring
    CHECK_INTERVAL: int = int(os.getenv("CHECK_INTERVAL", "30"))

    # Database
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "data/kufar_bot.db")

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.getenv("LOG_FILE", "logs/bot.log")

    # Parser
    PARSER_TIMEOUT: int = int(os.getenv("PARSER_TIMEOUT", "15"))
    PARSER_RETRY_ATTEMPTS: int = int(os.getenv("PARSER_RETRY_ATTEMPTS", "3"))
    PARSER_RETRY_DELAY: float = float(os.getenv("PARSER_RETRY_DELAY", "2.0"))

    # Rate limiting
    RATE_LIMIT_PER_SEARCH: float = float(os.getenv("RATE_LIMIT_PER_SEARCH", "2.5"))


config = Config()
