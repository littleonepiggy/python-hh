"""Load and validate configuration from config.json."""

import json
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent


def load_config(config_path: str = "config.json") -> dict:
    """Load and return config.json."""
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_ai_prompt(config: dict) -> str:
    """Load prompt template from config and substitute contact placeholders."""
    raw = config.get("ai_prompt", "")
    if not raw:
        return ""
    contact = config.get("contact", {})
    telegram = contact.get("telegram", "")
    phone = contact.get("phone", "")
    return raw.format(telegram=telegram, phone=phone)


def validate_config(config: dict) -> None:
    """Validate that required config sections exist. Exit if missing."""
    if not config.get("cookie_sources"):
        print("Error: 'cookie_sources' not defined in config.json.")
        exit(1)
    if not config.get("search_config"):
        print("Warning: 'search_config' not defined in config.json. Scraping will be skipped.")
