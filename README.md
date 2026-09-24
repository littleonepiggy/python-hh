# python-hh

HH.ru vacancy scraper with AI-powered analysis.

## Overview

Automated tool for scraping job vacancies from **hh.ru** (HeadHunter), with optional AI analysis via a local LLM (Ollama-compatible API). Fetches authenticated session cookies directly from Firefox, launches a browser with injected cookies, scrapes vacancy listings, and sends each vacancy's description to an LLM for relevance scoring and structured analysis.

## Features

- **Cookie extraction from Firefox** — reads `cookies.sqlite` / `cookieData.sqlite` directly, no external tools needed. Supports multiple Firefox profiles and both legacy and modern cookie schemas.
- **Headless Chrome scraping** — uses Selenium with configurable browser (Chrome / Chrome Canary), headless mode, and window size.
- **Multi-page pagination** — iterates through search results with configurable max pages and per-page vacancy cap.
- **AI-powered analysis** — sends vacancy descriptions to an OpenAI-compatible LLM API (default: Ollama at `localhost:8080`) for relevance scoring, pros/cons extraction, tech stack identification, salary parsing, and auto-generated cover letters.
- **Incremental scraping** — loads `vacancies.json` on startup to skip already-applied vacancies.
- **Configurable** — all behaviour controlled via `config.json`: search queries, browser settings, cookie sources, AI model, and prompt templates.

## Project Structure

| File | Purpose |
|---|---|
| `main.py` | Entry point — orchestrates cookie loading, browser launch, and scraping. |
| `config_loader.py` | Loads `config.json`, builds AI prompt, validates config. |
| `cookie_fetcher.py` | Extracts cookies from Firefox profiles (SQLite parsing). |
| `browser_manager.py` | Creates Selenium Chrome/Canary driver, injects cookies. |
| `vacancy_scraper.py` | Core scraping logic — page iteration, DOM parsing, JSON save. |
| `ai_analyzer.py` | Sends vacancy text to LLM and parses structured JSON response. |
| `output_formatter.py` | Pretty-prints AI analysis results with emojis. |
| `config.json` | Configuration (search params, browser settings, AI model, prompt). |
| `vacancies.json` | Scraped vacancy data with AI analysis results. |

## Requirements

- Python 3.10+
- Firefox (for cookie extraction)
- Chrome or Chrome Canary (for scraping)
- [Selenium](https://www.selenium.dev/)
- [requests](https://docs.python-requests.org/) or [httpx](https://www.python-httpx.org/) (for AI analysis)

### Install dependencies

```bash
pip install selenium requests
```

(or `pip install httpx` instead of `requests`.)

## Configuration

Edit `config.json`:

```json
{
  "cookie_sources": [{ "name": "hh", "site": "https://ufa.hh.ru/" }],
  "driver_browser": "chrome_canary",
  "selenium_options": { "headless": true, "window_size": [1920, 1080] },
  "search_config": {
    "base_url": "https://ufa.hh.ru/search/vacancy",
    "query_params": { "text": "PHP", "order_by": "publication_time" },
    "max_pages": 1,
    "max_vacancies_per_page": 48
  },
  "llama_config": {
    "url": "http://localhost:8080/v1/chat/completions",
    "model": "qwen3.6-35B-A3B-UD-Q4_K_M",
    "api_key": ""
  }
}
```

### Key config sections

- **`cookie_sources`** — sites to extract cookies from. Firefox must be logged in.
- **`driver_browser`** — either `chrome` or `chrome_canary`.
- **`search_config`** — HH.ru search parameters (query, filters, page count).
- **`llama_config`** — Ollama / OpenAI-compatible API endpoint for AI analysis. Set `api_key` if your server requires one.
- **`ai_prompt`** — system prompt for the LLM (supports `{telegram}` and `{phone}` placeholders from the `contact` section).

## Usage

Run the scraper:

```bash
python main.py
```

CLI options:

```bash
python main.py --max-pages 5 --page 3
```

- `--max-pages N` — override `max_pages` from config.
- `--page N` — start scraping from a specific page (1-based).

## How It Works

1. **Load cookies** from Firefox's SQLite cookie database for configured sites.
2. **Launch browser** (Chrome/Canary) with injected cookies so the session is authenticated.
3. **Navigate** to the HH.ru search URL.
4. **Iterate pages**, extracting vacancy links and scraping details.
5. **Send** each vacancy's description to the AI for structured analysis.
6. **Print** formatted results and save all data to `vacancies.json`.

## AI Analysis Output

Each vacancy gets a JSON analysis object with:

- `rel` — short relevance description
- `score` — match percentage (0–100)
- `salary` — parsed salary or "Не указана"
- `format` — remote/hybrid/office
- `stack` — array of technologies
- `pros` / `cons` — up to 4 each
- `letter` — auto-generated cover letter

## License

MIT
