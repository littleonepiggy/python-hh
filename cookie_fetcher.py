"""Fetch cookies from Firefox browser profile."""

import json
import sqlite3
import os
from pathlib import Path
import glob


def get_firefox_profiles_ini() -> Path | None:
    """Locate the profiles.ini file for Firefox."""
    # Check common locations
    candidates = [
        Path.home() / "AppData" / "Roaming" / "Mozilla" / "Firefox" / "profiles.ini",
        Path.home() / "firefox_profiles.ini",
    ]
    # Also try environment variable paths
    for env in ["APPDATA"]:
        if env == "APPDATA":
            appdata = os.environ.get("APPDATA", "")
            candidates.append(Path(appdata) / "Mozilla" / "Firefox" / "profiles.ini")

    for p in candidates:
        if p.exists():
            return p
    return None


def parse_profiles_ini(ini_path: Path) -> dict[str, str]:
    """Parse Firefox profiles.ini and return {profile_name: absolute_path}."""
    profiles = {}
    current_profile = {}
    in_profile_section = False

    for line in ini_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("[") and line.endswith("]"):
            if in_profile_section and "Path" in current_profile:
                pname = current_profile.get("Name", "default")
                prof_path = current_profile["Path"]
                # Resolve to absolute path (profiles.ini stores relative to INI parent)
                resolved = (ini_path.parent / prof_path).resolve()
                if resolved.exists():
                    profiles[pname] = str(resolved)
            in_profile_section = True
            current_profile = {"Name": line[1:-1]}
        elif "=" in line and in_profile_section:
            key, val = line.split("=", 1)
            current_profile[key.strip()] = val.strip()

    # Handle last profile
    if in_profile_section and "Path" in current_profile:
        pname = current_profile.get("Name", "default")
        prof_path = current_profile["Path"]
        resolved = (ini_path.parent / prof_path).resolve()
        if resolved.exists():
            profiles[pname] = str(resolved)

    return profiles


def get_chromeless_cookie_db(profile_path: str) -> Path | None:
    """Find cookies.sqlite or the new cookieData.sqlite in Firefox profile."""
    possible_files = [f for f in os.listdir(profile_path)]
    for candidate in ["cookies.sqlite", "cookieData.sqlite"]:
        if candidate in possible_files:
            return Path(profile_path) / candidate
    # Also check for parent directory with 'Profiles' subfolder pattern
    profiles_folder = Path(profile_path) / "Profiles"
    if not profiles_folder.exists():
        # Sometimes profile path itself is the base, look deeper
        pass
    return None


def extract_cookies_profile(profile_path: str, site_url: str) -> list[dict]:
    """Extract cookies for a specific site from a Firefox profile.
    
    Returns empty list if no cookie DB found or no matching cookies (non-blocking).
    """
    import sqlite3 as _sqlite3

    profile_dir = Path(profile_path)

    # Walk the entire profile tree recursively to find any sqlite file
    for dirpath, _, filenames in os.walk(str(profile_dir)):
        for fname in filenames:
            full_path = os.path.join(dirpath, fname)
            if not (fname == "cookies.sqlite" or fname == "cookieData.sqlite"):
                continue
            db_file = Path(full_path)
            # Verify it's actually a valid sqlite DB before using it
            try:
                conn = _sqlite3.connect(str(db_file))
                tables = [row[0] for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )]
                has_cookies_table = any("cookie" in t.lower() for t in tables)
                conn.close()
                if not has_cookies_table:
                    continue
            except (_sqlite3.DatabaseError, _sqlite3.OperationalError):
                # Not a valid sqlite DB — skip to next file
                continue

            try:
                return parse_cookies(db_file, site_url)
            except Exception:
                # Bad cookie DB (corrupt/incompatible) — continue search
                continue

    return []  # No cookie DB found in this profile; caller tries next profile


def _map_columns(columns_info):
    """Map standard attribute names to actual DB columns.
    
    Firefox cookies.sqlite (modern) has these exact column names:
      base64cookie, expirationDate, lastAccessed, creationLocation, etc.
    Older profiles may use simpler names like name, value, host, path, secure, expiry.
    """
    mapping = {"name": None, "value": None, "host": None, "path": None}

    for col_name in columns_info:
        nl = col_name.lower()
        if nl == "name" or nl == "cookie_name" or nl.endswith("_name"):
            mapping["name"] = col_name
        elif nl == "value" or nl == "base64cookie":
            mapping["value"] = col_name
        elif nl == "host" or nl.startswith("hostname") or nl.endswith("_host"):
            mapping["host"] = col_name
        elif nl in ("path", "uri", "rootdomain"):
            mapping["path"] = col_name

    # If host still not found, try the first column that contains 'host'
    if not mapping["host"]:
        for col_name in columns_info:
            if "host" in col_name.lower():
                mapping["host"] = col_name
                break

    return mapping


def parse_cookies(db_path: Path, site_url: str) -> list[dict]:
    """Parse cookies.sqlite and return list of cookie dicts for the given site."""
    from urllib.parse import urlparse

    parsed = urlparse(site_url)
    hostname = (parsed.hostname or "").lstrip(".")

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    tables = [row[0] for row in cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )]

    cookie_tables = [t for t in tables if "cookie" in t.lower()]

    cookies_found: list[dict] = []

    for table_name in cookie_tables:
        try:
            cols_info = [row[1] for row in cursor.execute(
                f"PRAGMA table_info('{table_name}')"
            )]
        except sqlite3.OperationalError:
            continue

        cols = _map_columns(cols_info)
        host_col = cols["host"] if cols["host"] else "host"
        name_col = cols["name"] if cols["name"] else "name"
        value_col = cols["value"] if cols["value"] else "value"
        path_col = cols["path"] if cols["path"] else "path"

        query = (f'SELECT "{host_col}", "{name_col}", "{value_col}", "{path_col}" '
                 f'FROM "{table_name}"')

        try:
            rows = cursor.execute(query).fetchall()
            for row in rows:
                host, cookie_name, cookie_value, cookie_path = row
                if not cookie_value or not cookie_name:
                    continue
                host_clean = str(host).lstrip(".")
                if _hostname_matches(host_clean, hostname):
                    cookies_found.append({
                        "name": cookie_name,
                        "value": str(cookie_value),
                        "domain": host_clean,
                        "path": (cookie_path or "/").split()[0],
                    })
        except sqlite3.OperationalError as e:
            print(f"  Warning: SQL error on table '{table_name}': {e}")

    conn.close()
    return cookies_found


def _hostname_matches(cookie_host: str, target_host: str) -> bool:
    """Check if a cookie's host matches the target domain.
    
    Browser cookie matching rules:
      - Exact match (hh.ru == hh.ru)
      - Cookie is parent domain (.hh.ru applies to any *.hh.ru)
      - Target is parent domain (www.hh.ru matches .hh.ru cookies)
    """
    cookie_host = cookie_host.lstrip(".")
    target_host = target_host.lstrip(".")

    if cookie_host == target_host:
        return True

    # Cookie has dot prefix meaning it applies to subdomains
    if cookie_host.startswith("."):
        root_domain = cookie_host[1:]  # hh.ru
        # Target must be in the subtree (subdomain or same)
        if target_host == root_domain or target_host.endswith("." + root_domain):
            return True
        return False

    # No dot prefix: cookie applies only to exact host
    # But if target IS a subdomain of this, and browser was configured with parent, accept it
    if target_host.endswith("." + cookie_host):
        return True

    return False


def get_cookies_from_firefox(config_path="config.json"):
    """Main function: load config and fetch cookies from Firefox for configured sites."""
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    profiles_ini = get_firefox_profiles_ini()
    if not profiles_ini:
        raise FileNotFoundError("Firefox profiles.ini not found. Please install Firefox first.")

    profiles = parse_profiles_ini(profiles_ini)
    print(f"  Found Firefox profiles: {list(profiles.keys())}")

    all_cookies = {}
    for source in config.get("cookie_sources", []):
        name = source["name"]
        site = source["site"]
        print(f"\nFetching cookies for '{name}' ({site}) from Firefox...")

        cookies_found = []
        # Try each profile until we find a valid cookie DB
        for prof_name, prof_path in profiles.items():
            cookies_found = extract_cookies_profile(prof_path, site)
            if cookies_found:
                print(f"  -> Extracted {len(cookies_found)} cookies from profile '{prof_name}'")
                break

        if not cookies_found:
            print(f"  -> No cookies found in any Firefox profile for this site.")
            all_cookies[name] = []
            continue

        all_cookies[name] = cookies_found

    return all_cookies, config


if __name__ == "__main__":
    import pprint
    try:
        result, conf = get_cookies_from_firefox()
        pprint.pprint(result, indent=2)
        print(f"\nTotal sources processed: {len(result)}")
    except Exception as e:
        print(f"Error: {e}")
