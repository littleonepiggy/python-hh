"""Chrome browser creation and cookie management."""

import sys
import shutil
import subprocess
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service


def find_chrome_bin(browser_name: str) -> str | None:
    """Look up the right Chrome/Chromium executable based on config setting."""
    is_canary = browser_name == "chrome_canary"

    candidates: list[str] = []
    if sys.platform == "win32":
        # Windows
        if is_canary:
            candidates = [
                r"C:/Program Files/Google/Chrome SxS/Application/chrome.exe",
                r"C:/Users/user/AppData/Local/Google/Chrome SxS/Application/chrome.exe",
                r"C:/Program Files (x86)/Google/Chrome SxS/Application/chrome.exe",
                r"C:/Program Files/Chromium/Application/chrome.exe",
            ]
        else:
            candidates = [
                r"C:/Program Files/Google/Chrome/Application/chrome.exe",
                r"C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
                r"C:/Users/user/AppData/Local/Google/Chrome/Application/chrome.exe",
            ]
    else:
        # Linux / macOS
        if is_canary:
            candidates = [
                "/opt/google/chrome-unstable/chrome",
                "/usr/bin/google-chrome-unstable",
                "/usr/bin/google-chrome-beta",
                "/snap/chromium/current/usr/lib/chromium-browser/chrome",
                "/usr/bin/chromium-browser",
                "/usr/bin/chromium",
            ]
        else:
            candidates = [
                "/opt/google/chrome/chrome",
                "/usr/bin/google-chrome-stable",
                "/usr/bin/google-chrome",
                "/snap/chromium/current/usr/lib/chromium-browser/chrome",
                "/usr/bin/chromium-browser",
                "/usr/bin/chromium",
            ]

    for candidate in candidates:
        if Path(candidate).exists():
            return candidate

    # Fallback: search via where (Windows) / shutil.which (Linux, macOS)
    try:
        if sys.platform == "win32":
            out = subprocess.check_output(["where", "chrome.exe"], text=True, stderr=subprocess.DEVNULL)
            for line in out.strip().splitlines():
                if Path(line.strip()).exists():
                    return line.strip()
        else:
            for exe in (["google-chrome-unstable", "google-chrome-beta", "chromium", "chromium-browser", "google-chrome"]
                        if is_canary else
                        ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser"]):
                resolved = shutil.which(exe)
                if resolved:
                    return resolved
    except Exception:
        pass

    return None


def create_driver(browser_name: str, full_config: dict | None = None) -> webdriver.Chrome:
    """Create a Selenium WebDriver for the requested Chrome build."""
    chrome_exe = find_chrome_bin(browser_name)
    if not chrome_exe:
        label = "Chrome Canary/Unstable or Chromium" if browser_name == "chrome_canary" else "Google Chrome or Chromium"
        print(f"Error: {label} not found on this machine.")
        print("Install it via: sudo snap install chromium  (or apt install chromium-browser)")
        sys.exit(1)

    print(f"  Using {browser_name.replace('_', ' ').title()}: {chrome_exe}")

    service = Service()

    chrome_options = Options()

    # Apply selenium_options from config
    selenium_opts = full_config.get("selenium_options", {}) if full_config else {}
    is_headless = selenium_opts.get("headless", False)
    win_size = selenium_opts.get("window_size", [1920, 1080])

    if is_headless:
        chrome_options.add_argument("--headless=new")
        print("  🕵️  Running in headless mode (user-profile dir skipped)")
    else:
        user_data_dir = _get_user_data_dir(browser_name)
        if user_data_dir.exists():
            chrome_options.add_argument(f"--user-data-dir={user_data_dir}")

    chrome_options.binary_location = chrome_exe
    chrome_options.add_argument(f"--window-size={win_size[0]},{win_size[1]}")
    if not is_headless:
        chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--proxy-bypass-list=<local>")
    chrome_options.add_argument("--disable-proxy-server")
    chrome_options.add_argument("--no-first-run --no-proxy-server")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver


def _get_user_data_dir(browser_name: str) -> Path:
    """Return the user-data-dir path for the given browser (per-OS)."""
    home = Path.home()
    if sys.platform == "win32":
        if browser_name == "chrome_canary":
            return home / "AppData" / "Local" / "Google" / "Chrome SxS" / "User Data"
        return home / "AppData" / "Local" / "Google" / "Chrome" / "User Data"
    if sys.platform == "darwin":
        suffix = "Canary" if browser_name == "chrome_canary" else ""
        return home / "Library" / "Application Support" / "Google" / ("Chrome" + suffix)
    # Linux
    if browser_name == "chrome_canary":
        return home / "snap" / "chromium" / "common" / "chromium"
    return home / ".config" / "chromium" / "User Data"


def paste_cookies(driver, cookies: list[dict]) -> None:
    """Paste a list of cookie dicts into the browser."""
    for cookie in cookies:
        try:
            cookie_dict = {
                "name": cookie["name"],
                "value": cookie["value"],
            }
            if "domain" in cookie and cookie["domain"]:
                cookie_dict["domain"] = cookie["domain"]
            if "path" in cookie:
                cookie_dict["path"] = cookie["path"]
            if cookie.get("secure") is not None:
                cookie_dict["secure"] = bool(cookie["secure"])

            driver.add_cookie(cookie_dict)
            print(f"    OK {cookie['name'][:40]}... ({len(cookie['value'])} chars)")
        except Exception as e:
            print(f"    FAIL could not add '{cookie['name']}': {e}")
