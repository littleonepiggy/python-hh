"""Core vacancy scraping logic: page iteration, DOM parsing, and JSON save."""

import json
import html
import time
import random
from pathlib import Path
from urllib.parse import urlencode

from selenium.common.exceptions import StaleElementReferenceException
from ai_analyzer import analyze_vacancy
from output_formatter import print_output

PROJECT_DIR = Path(__file__).resolve().parent


def _delay(min_delay: float = 1.0, max_delay: float = 3.0) -> None:
    """Random pause between actions."""
    time.sleep(random.uniform(min_delay, max_delay))


def scrape_vacancies(driver, search_config: dict, full_config: dict | None = None) -> list[dict]:
    """Iterate over HH search pages and collect vacancy details.

    Args:
        driver: Selenium Chrome instance with hh.ru cookies already injected.
        search_config: Parsed 'search_config' from config.json.
        full_config: Entire config.json (used for llama_config).

    Returns:
        List of vacancy dicts saved to vacancies.json.
    """
    max_pages = search_config.get("max_pages", 5)
    print(f"  Max pages to scrape: {max_pages}")

    base_url = search_config.get("base_url", "https://hh.ru/search/vacancy")
    query_params = search_config.get("query_params", {})
    per_page = search_config.get("per_page", 48)
    max_per_page_cap = search_config.get("max_vacancies_per_page", 3)

    vacancies: list[dict] = []
    ai_enabled = "llama_config" in (full_config or {})

    # Load existing vacancies.json: skip already-applied links and keep
    # old entries so the file only grows (new runs append, never overwrite)
    applied_set: set[str] = set()
    existing: list[dict] = []
    try:
        existing_path = PROJECT_DIR / "vacancies.json"
        if existing_path.exists():
            with open(existing_path, "r", encoding="utf-8") as ef:
                existing = json.load(ef)
            for entry in existing:
                link = entry.get("link", "")
                analysis = entry.get("analysis", {}) or {}
                if analysis.get("applied", False):
                    applied_set.add(link)
    except Exception:
        existing = []

    existing_links = {e.get("link") for e in existing}

    start_page = search_config.get("page", 1)

    print(f"\n  Starting scrape on {base_url}...")
    print(f"  ⏭️  Start page: {start_page}")
    print(f"  ⏭️  Will skip {len(applied_set)} already-applied vacancy(es).")
    print(f"  ⏭️  Will skip {len(existing_links)} vacancy(es) already present in vacancies.json.")

    page = start_page - 1  # convert to 0-based index for internal use

    while True:
        current_page = page + 1

        # Build URL with page parameter
        params = dict(query_params)
        params["page"] = str(page + 1)
        params["per_page"] = str(per_page)
        url = f"{base_url}?{urlencode(params)}"

        print(f"\n  [Page {current_page}/{max_pages}] Fetching: {url}")

        try:
            driver.get(url)
            time.sleep(2)  # wait for client-side rendering
        except Exception as e:
            print(f"    Warning: navigation failed ({e}), skipping...")
            break

        # Extract title, company, and href from the search page (no navigation needed)
        listing_info = _extract_listing_info(driver)

        if not listing_info:
            print("    No valid vacancy entries found. Stopping.")
            break

        duplicates = set(v["link"] for v in vacancies)
        scraped_on_this_page = 0

        for title, company, href in listing_info:
            if scraped_on_this_page >= max_per_page_cap:
                print(f"\n  ⚠️  Reached per-page cap ({max_per_page_cap}). Stopping page.")
                break
            if href in duplicates:
                continue

            # Check if already processed in a previous run (by link) BEFORE navigating
            # (already in vacancies.json = already viewed/analyzed once)
            if href in existing_links:
                print(f"  📁 SKIP — already processed: {href[:80]}...")
                continue

            duplicates.add(href)

            vacancy = _fetch_vacancy_detail(driver, href, title, company, ai_enabled, full_config, applied_set, len(vacancies) + 1)
            if vacancy is not None:
                vacancies.append(vacancy)
                scraped_on_this_page += 1

            _delay()

        if current_page >= max_pages:
            print(f"\n  ⏹️  Reached max pages ({max_pages}). Done.")
            break

        page += 1

    # --- Save to JSON file: old entries + new ones, sorted best-first ---
    combined = existing + vacancies
    combined.sort(key=_score_sort_key, reverse=True)
    output_path = PROJECT_DIR / "vacancies.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(combined, f, ensure_ascii=False, indent=2)

    return vacancies


def _score_sort_key(vacancy: dict) -> float:
    """Sort key by analysis score; entries without a score sink to the end."""
    raw = (vacancy.get("analysis") or {}).get("score")
    try:
        return float(str(raw).rstrip("%"))
    except (TypeError, ValueError, AttributeError):
        return -1.0


def _extract_vacancy_links(driver) -> list[str]:
    """Extract all vacancy hrefs from the current search page."""
    href_list = []
    stale_retries = 0
    while not href_list and stale_retries < 3:
        try:
            links = driver.find_elements("css selector", 'a[href*="hh.ru/vacancy"]')
        except StaleElementReferenceException:
            stale_retries += 1
            time.sleep(1)
            continue
        except Exception as e:
            print(f"    Warning: could not find vacancy links ({e})")
            break

        href_list = []
        for link_el in links:
            try:
                href = link_el.get_attribute("href")
                if href and "hh.ru/vacancy" in href:
                    href_list.append(href)
            except StaleElementReferenceException:
                break  # DOM перестроился — прерываем, внешний цикл повторит
            except Exception:
                continue

    return href_list


def _fetch_vacancy_detail(driver, href: str, title: str, company: str, ai_enabled: bool, full_config: dict, applied_set: set[str], vacancy_number: int):
    """Navigate to a vacancy page and extract its content."""
    try:
        driver.get(href)
        time.sleep(2)  # detail page client-side render
    except Exception as e:
        print(f"     Warning: failed to open vacancy page ({e})")
        return None

    # Small description: text from the parent of .vacancy-title
    small_desc = _extract_small_desc(driver)

    # Full description
    full_desc = _extract_full_desc(driver)

    # Skip already-applied vacancies
    if href in applied_set:
        print(f"\n  ⏭️  SKIP — already applied: {href[:80]}...")
        return None

    current_vacancy = {"link": href, "title": title, "company": company}

    # --- AI analysis ---
    ts = time.strftime("[%Y-%m-%d %H:%M:%S]")
    print(f"\n  {ts}  #{vacancy_number}. 📎 Vacancy: {title}")
    if company:
        print(f"     🏢 Company: {company}")
    print(f"     🔗 {href}")

    if ai_enabled and full_desc:
        try:
            result = analyze_vacancy(small_desc, full_desc, full_config)
            if result:
                current_vacancy["analysis"] = result
                print_output(result, href)
                print()
            else:
                current_vacancy["analysis"] = {"error": "AI returned no result"}
        except Exception as e:
            current_vacancy["analysis"] = {"error": f"AI exception ({e})"}

    elif ai_enabled and not full_desc:
        print(f"  ⚠️ Full description is empty — skipping AI analysis")

    return current_vacancy


def _extract_small_desc(driver) -> str:
    """Extract brief description from the vacancy title area."""
    try:
        title_wrapper = driver.find_element("css selector", ".vacancy-title")
        if title_wrapper:
            parent_el = title_wrapper.find_element("xpath", "./..")
            return parent_el.text.strip().replace("\n", " | ")
    except Exception:
        pass
    return ""


def _strip_hh_footer(full_desc: str) -> str:
    """Remove the 'Ask the employer / workplace location' footer HH appends."""
    low = full_desc.lower()
    ask_idx = low.find("ask the employer")
    place_idx = low.find("where is the workplace located")
    cut_idx = min((i for i in (ask_idx, place_idx) if i >= 0), default=len(full_desc))
    return full_desc[:cut_idx].rstrip()


def _extract_full_desc(driver) -> str:
    """Extract the full job description text."""
    # data-qa is HH's own stable test attribute; CSS classes change often
    for sel in ["div[data-qa='vacancy-description']", ".g-user-content",
                ".vacancy-description", "div.vacancy-description-content"]:
        try:
            desc_el = driver.find_element("css selector", sel)
            break
        except Exception:
            desc_el = None

    if desc_el:
        time.sleep(1)
        full_desc = desc_el.text.strip().replace("\r\n", "\n").replace("\n", " ")
        return _strip_hh_footer(full_desc)

    # Fallback: JSON-LD structured data (script[@type='application/ld+json'])
    import re
    try:
        for el in driver.find_elements("css selector", "script[type='application/ld+json']"):
            data = json.loads(el.get_attribute("innerHTML"))
            if not isinstance(data, dict) or data.get("@type") != "JobPosting":
                continue
            raw = data.get("description", "")
            if not raw:
                continue
            text = html.unescape(re.sub(r"<[^>]+>", " ", raw))
            text = re.sub(r"\s+", " ", text).strip()
            return _strip_hh_footer(text)
    except Exception:
        pass

    return ""


def _extract_listing_info(driver) -> list[tuple[str, str, str]]:
    """Extract (title, company, href) from all vacancy cards on the search page."""
    results: list[tuple[str, str, str]] = []
    # Each vacancy card: title link uses data-qa="serp-item__title",
    # company link uses data-qa="vacancy-serp__vacancy-employer"
    title_links = driver.find_elements("css selector", "a[data-qa='serp-item__title']")
    for card in title_links:
        try:
            # Get title text from the inner span with data-qa="serp-item__title-text"
            title_el = card.find_element("css selector", "span[data-qa='serp-item__title-text']")
            title = title_el.text.strip()
            href = card.get_attribute("href")
            if not href:
                continue

            # Company is in the same card block
            company = ""
            try:
                company_el = card.find_element("css selector", "a[data-qa='vacancy-serp__vacancy-employer']")
                company_text_el = company_el.find_element("css selector", "span[data-qa='vacancy-serp__vacancy-employer-text']")
                company = company_text_el.text.strip()
            except Exception:
                pass
            results.append((title, company, href))
        except Exception:
            continue
    return results
