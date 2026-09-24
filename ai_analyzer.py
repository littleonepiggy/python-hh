"""AI-powered vacancy analysis via OpenAI-compatible LLM API."""

import json
from config_loader import build_ai_prompt


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


def analyze_vacancy(small_desc: str, full_desc: str, config: dict):
    """Send vacancy text to LLM and parse JSON response.

    Returns the parsed dict on success, or None on failure.
    """
    llama_cfg = config.get("llama_config", {})
    url = llama_cfg.get("url", "http://localhost:8080/v1/chat/completions")
    model = llama_cfg.get("model", "qwen3.6-35B-A3B-UD-Q4_K_M")
    api_key = llama_cfg.get("api_key", "")

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

    try:
        resp = post_fn(
            url,
            headers=headers,
            data=json.dumps({
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": raw_desc},
                ],
                "stream": False,
            }),
            timeout=120,
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
