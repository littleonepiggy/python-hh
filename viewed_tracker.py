"""Track viewed vacancies to avoid duplicates across sessions."""

import json
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
VIEWED_FILE = PROJECT_DIR / "viewed.json"


def load_viewed() -> dict[str, bool]:
    """Return {name|company} -> True for every vacancy seen so far."""
    if not VIEWED_FILE.exists():
        return {}
    try:
        with open(VIEWED_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            # Backwards compat: list of {"name":..., "company":...}
            return {
                f"{entry['name']}|{entry['company']}": True
                for entry in data
                if "name" in entry and "company" in entry
            }
        return data
    except Exception:
        return {}


def save_viewed(viewed: dict[str, bool]) -> None:
    """Persist the viewed set to disk."""
    with open(VIEWED_FILE, "w", encoding="utf-8") as f:
        json.dump(list(viewed.keys()), f, ensure_ascii=False, indent=2)


def record_viewed(name: str, company: str) -> None:
    """Mark a vacancy as viewed."""
    viewed = load_viewed()
    key = f"{name}|{company}"
    viewed[key] = True
    save_viewed(viewed)


def is_viewed(name: str, company: str) -> bool:
    """Check whether this vacancy has already been viewed."""
    key = f"{name}|{company}"
    viewed = load_viewed()
    return key in viewed
