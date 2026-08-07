"""Core configuration from environment variables."""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Application configuration."""

    # Telegram
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    ADMIN_ID: int = int(os.getenv("ADMIN_ID", "0"))
    
    @property
    def ADMIN_IDS(self) -> list:
        """Get list of admin IDs from environment."""
        admin_ids_str = os.getenv("ADMIN_IDS", str(self.ADMIN_ID))
        try:
            # Поддерживаем форматы: "123,456,789" или "123 456 789"
            admin_ids = []
            for part in admin_ids_str.replace(",", " ").split():
                if part.strip().isdigit():
                    admin_ids.append(int(part.strip()))
            return admin_ids if admin_ids else [self.ADMIN_ID]
        except Exception:
            return [self.ADMIN_ID]

    # Subscription
    TRIAL_DAYS: int = int(os.getenv("TRIAL_DAYS", "3"))

    # Monitoring
    CHECK_INTERVAL: int = int(os.getenv("CHECK_INTERVAL", "30"))

    # Database
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "data/wellbot.db")

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.getenv("LOG_FILE", "logs/wellbot.log")

    # Parser
    PARSER_TIMEOUT: int = int(os.getenv("PARSER_TIMEOUT", "15"))
    PARSER_RETRY_ATTEMPTS: int = int(os.getenv("PARSER_RETRY_ATTEMPTS", "3"))
    PARSER_RETRY_DELAY: float = float(os.getenv("PARSER_RETRY_DELAY", "2.0"))

    # Rate limiting
    RATE_LIMIT_PER_SEARCH: float = float(os.getenv("RATE_LIMIT_PER_SEARCH", "2.5"))


config = Config()
