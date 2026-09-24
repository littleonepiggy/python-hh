"""Track viewed vacancies to avoid duplicates across sessions."""

import json
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
VIEWED_FILE = PROJECT_DIR / "viewed.json"


def load_viewed() -> list[dict]:
    """Return list of {name, company} dicts for every vacancy seen so far."""
    if not VIEWED_FILE.exists():
        return []
    try:
        with open(VIEWED_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            # Filter to ensure each entry has name and company keys
            return [e for e in data if isinstance(e, dict) and "name" in e and "company" in e]
        return []
    except Exception:
        return []


def save_viewed(viewed: list[dict]) -> None:
    """Persist the viewed list to disk."""
    with open(VIEWED_FILE, "w", encoding="utf-8") as f:
        json.dump(viewed, f, ensure_ascii=False, indent=2)


def record_viewed(name: str, company: str) -> None:
    """Mark a vacancy as viewed."""
    viewed = load_viewed()
    # Avoid duplicates
    for entry in viewed:
        if entry.get("name") == name and entry.get("company") == company:
            return
    viewed.append({"name": name, "company": company})
    save_viewed(viewed)


def is_viewed(name: str, company: str) -> bool:
    """Check whether this vacancy has already been viewed."""
    viewed = load_viewed()
    return any(e.get("name") == name and e.get("company") == company for e in viewed)
