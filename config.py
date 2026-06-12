"""Loads and validates configuration from environment / .env file."""

import os
from dotenv import load_dotenv

load_dotenv()


def _require(key: str) -> str:
    val = os.getenv(key)
    if not val:
        raise EnvironmentError(
            f"Required environment variable '{key}' is not set.\n"
            f"Copy .env.example to .env and fill in your keys."
        )
    return val


class Config:
    DGIS_API_KEY: str = _require("DGIS_API_KEY")
    GOOGLE_OAUTH_JSON: str = os.getenv("GOOGLE_OAUTH_JSON", "oauth_credentials.json")
    SHEET_ID: str = os.getenv("SHEET_ID", "")
    SHEET_NAME: str = os.getenv("SHEET_NAME", "Parking Almaty")
    MAX_PAGES: int = int(os.getenv("MAX_PAGES", "5"))
    REQUESTS_PER_SECOND: float = float(os.getenv("REQUESTS_PER_SECOND", "2"))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")


cfg = Config()
