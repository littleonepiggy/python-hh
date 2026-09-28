"""AI-powered vacancy analysis via OpenAI-compatible LLM API.

Supports two providers, selected via the 'ai_provider' key in config.json:
  - "local"    — self-hosted OpenAI-compatible server (llama_config section)
  - "opencode" — opencode Zen API (opencode_config section)
"""

import json
import os
import sqlite3
from pathlib import Path

from config_loader import build_ai_prompt


OPENCODE_GO_URL = "https://opencode.ai/zen/go/v1/chat/completions"
OPENCODE_SESSION_ID = "python-hh-vacancy-scraper"

# HTTP client lookup order
_HTTP_CLIENTS = [
    ("httpx", "httpx.post"),
    ("requests", "requests.post"),
]


def _get_http_client():
    """Find an available HTTP client library (requests or httpx)."""
    for mod_name, _ in _HTTP_CLIENTS:
        try:
            mod = __import__(mod_name)
            if mod_name == "httpx":
                return mod.post
            return getattr(mod, "post")
        except ImportError:
            continue
    return None


def _read_opencode_cli_key() -> str:
    """Read an API key stored by the opencode CLI, if present.

    The opencode CLI keeps credentials in ~/.local/share/opencode/opencode.db.
    """
    db_path = Path.home() / ".local" / "share" / "opencode" / "opencode.db"
    if not db_path.exists():
        return ""
    try:
        conn = sqlite3.connect(str(db_path))
        row = conn.execute(
            "SELECT value FROM credential WHERE active = 1 LIMIT 1"
        ).fetchone()
        conn.close()
        if row:
            data = json.loads(row[0])
            return data.get("key", "")
    except Exception:
        pass
    return ""


def _get_provider_config(config: dict) -> dict | None:
    """Resolve which provider section to use and return its config.

    Selection comes from config['ai_provider']:
      - "local" (default): use the 'llama_config' section
      - "opencode": use the 'opencode_config' section

    The opencode API key is resolved in this order:
      1. OPENCODE_API_KEY environment variable (preferred)
      2. opencode_config.api_key in config.json (fallback)
      3. credential stored by the opencode CLI

    Returns None (with a printed reason) if the provider is not usable.
    """
    provider = config.get("ai_provider", "local")

    if provider == "opencode":
        oc_cfg = dict(config.get("opencode_config", {}))
        oc_cfg.setdefault("url", OPENCODE_GO_URL)
        oc_cfg.setdefault("model", "glm-5.3-flash")
        # Env var wins over config so the machine owner always has the
        # final say; the config value is a portable fallback.
        oc_cfg["api_key"] = (
            os.environ.get("OPENCODE_API_KEY", "")
            or oc_cfg.get("api_key", "")
            or _read_opencode_cli_key()
        )
        if not oc_cfg.get("api_key"):
            print("  ⚠️  opencode provider selected but no API key found.")
            print("     Set opencode_config.api_key in config.json, or export OPENCODE_API_KEY.")
            return None
        return oc_cfg

    if provider == "local":
        return config.get("llama_config", {})

    print(f"  ⚠️  Unknown ai_provider '{provider}' in config.json (expected 'local' or 'opencode').")
    return None


def analyze_vacancy(small_desc: str, full_desc: str, config: dict):
    """Send vacancy text to LLM and parse JSON response.

    Returns the parsed dict on success, or None on failure.
    """
    provider_cfg = _get_provider_config(config)
    if not provider_cfg:
        return None

    url = provider_cfg.get("url", "http://localhost:8080/v1/chat/completions")
    model = provider_cfg.get("model", "")
    api_key = provider_cfg.get("api_key", "")
    timeout = provider_cfg.get("timeout", 120)

    system_prompt = build_ai_prompt(config)
    if not system_prompt:
        print("  ⚠️  No ai_prompt in config — AI analysis skipped")
        return None

    raw_desc = f"{small_desc}\n\n{full_desc}" if full_desc else small_desc

    post_fn = _get_http_client()
    if not post_fn:
        print("  ⚠️  No HTTP client (httpx/requests) available — AI analysis skipped")
        return None

    headers = {
        "Content-Type": "application/json",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    # opencode Go routing hint (required by the Go endpoint)
    if config.get("ai_provider") == "opencode":
        headers["x-opencode-session"] = config.get("opencode_config", {}).get(
            "session_id", OPENCODE_SESSION_ID
        )

    provider_label = config.get("ai_provider", "local")
    print(f"  🤖 Analyzing with AI ({provider_label}: {model or 'default'})...")

    try:
        request_body = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": raw_desc},
            ],
            "stream": False,
        }
        # Go-tier models are reasoning models; give them room to think + answer
        if provider_cfg.get("max_tokens"):
            request_body["max_tokens"] = provider_cfg["max_tokens"]

        resp = post_fn(
            url,
            headers=headers,
            data=json.dumps(request_body),
            timeout=timeout,
        )
        resp.raise_for_status()
        payload = resp.json()

        choices = payload.get("choices", [])
        if not choices:
            print("  ⚠️  AI returned no choices")
            return None

        content = choices[0].get("message", {}).get("content", "")

        # Strip markdown code fences if present
        content = content.strip()
        if content.startswith("```"):
            first_backtick = content.index("```")
            content = content[first_backtick + 3 :].strip()
            last_backtick = content.rfind("```")
            if last_backtick != -1:
                content = content[:last_backtick].strip()

        return json.loads(content)

    except Exception as e:
        print(f"  ⚠️  AI analysis failed ({e})")
        return None
