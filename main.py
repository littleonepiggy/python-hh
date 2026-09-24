"""Entry point — orchestrates cookie loading, browser launch, and scraping."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config_loader import load_config, validate_config
from browser_manager import create_driver, paste_cookies
from vacancy_scraper import scrape_vacancies
from cookie_fetcher import get_cookies_from_firefox


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-pages", type=int, default=None,
                        help="Override max_pages from config.json")
    parser.add_argument("--page", type=int, default=None,
                        help="Start scraping from a specific page (1-based)")
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()
    config = load_config()

    # CLI overrides
    if "search_config" in config:
        cfg_max = config["search_config"].get("max_pages", 5)
        if args.max_pages is not None:
            config["search_config"]["max_pages"] = args.max_pages
            print(f"Override: max_pages set to {args.max_pages} via CLI")
        else:
            print(f"Using search_config.max_pages from config.json: {cfg_max}")

    # Page handling
    if args.page is not None:
        config["search_config"]["page"] = args.page
        print(f"Override: starting from page {args.page} via CLI")
    elif config["search_config"].get("page") is None:
        config["search_config"]["page"] = 1

    validate_config(config)

    browser_name = config.get("driver_browser", "chrome")
    title = browser_name.replace("_", " ").title()

    print("=" * 60)
    print(f"Firefox Cookie Loader - {title} Edition")
    print("=" * 60)

    # --- Cookie loading ---
    cookie_sources = config["cookie_sources"]
    target_source = cookie_sources[0]
    source_name = target_source["name"]
    source_site = target_source["site"]

    print("\n[1/4] Fetching cookies from Firefox...")
    all_cookies, _ = get_cookies_from_firefox()

    if not any(all_cookies.values()):
        print("No cookies found. Please log into the target sites in Firefox first.")
        sys.exit(1)

    total = sum(len(c) for c in all_cookies.values())
    print(f"\n  Total cookies collected: {total}")
    for name, cookies in all_cookies.items():
        print(f"    - {name}: {len(cookies)} cookies")

    cookies_to_paste = all_cookies[source_name]
    print(f"\n[2/4] Using cookie source: '{source_name}' ({len(cookies_to_paste)} cookies)")

    # --- Browser launch ---
    print(f"\n[3/4] Launching {title}...")
    driver = create_driver(browser_name, config)

    # --- Cookie injection ---
    source_domain = source_site.replace("https://", "").replace("http://", "")
    print(f"[4/4] Loading {source_site} and pasting cookies...")
    try:
        driver.get(source_site)
        print(f"  Navigated to {source_site}")
    except Exception as e:
        print(f"  Warning: initial navigation failed ({e}), continuing...")

    paste_cookies(driver, cookies_to_paste)

    print("  Reloading page with cookies applied...")
    try:
        driver.refresh()
    except Exception as e:
        print(f"  Warning: refresh failed ({e})")

    # Verify
    current_cookies = driver.get_cookies()
    print(f"\n  Browser now has {len(current_cookies)} cookies")
    try:
        print(f"  Current page:    {driver.current_url}")
        print(f"  Page title:      {driver.title[:60]}")
    except Exception:
        pass

    # --- Scrape ---
    search_config = config.get("search_config", None)
    if not search_config:
        print("\n  No 'search_config' found. Skipping vacancy scraping.")
    else:
        try:
            print(f"\n{'=' * 60}")
            print("  🕸️  Starting vacancy scraping...")
            vacancies = scrape_vacancies(driver, search_config, config)
            print(f"\n  ✅ Scraping complete. Total: {len(vacancies)} vacancy(es).")
        except KeyboardInterrupt:
            print("\n  ⏹️  Interrupted by user.")
        finally:
            driver.quit()
            print("  🔒 Browser closed.")


if __name__ == "__main__":
    main()
