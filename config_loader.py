"""Load and validate configuration from config.json."""

import json
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent

# Optional gitignored file holding the full AI prompt. If it exists it
# overrides config.json's "ai_prompt" placeholder.
AI_PROMPT_FILE = PROJECT_DIR / "ai_prompt.txt"

# Optional gitignored file holding personal contact info:
#   {"telegram": "@handle", "phone": "79990000000"}
CONTACTS_FILE = PROJECT_DIR / "contacts.json"


def load_config(config_path: str = "config.json") -> dict:
    """Load config.json and merge in optional local overrides.

    Personal data (contacts) lives in the gitignored contacts.json when
    present, so tracked config.json can stay free of personal info.
    """
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    if CONTACTS_FILE.exists():
        try:
            contacts = json.loads(CONTACTS_FILE.read_text(encoding="utf-8"))
            if contacts:
                config["contact"] = contacts
        except (json.JSONDecodeError, OSError) as e:
            print(f"  ⚠️  Could not read {CONTACTS_FILE.name}: {e} — using config contact.")

    return config


def build_ai_prompt(config: dict) -> str:
    """Load prompt template from file or config and substitute contacts."""
    raw = config.get("ai_prompt", "")
    if AI_PROMPT_FILE.exists():
        raw = AI_PROMPT_FILE.read_text(encoding="utf-8")
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
