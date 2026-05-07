#!/usr/bin/env python3
"""
Mødrehjælpen lokalforening scraper.

Fetches all data from https://www.moedrehjaelpen.dk/lokalforeninger
and all linked subpages, then geocodes each entry.
Saves output to data.json.

Re-run at any time to refresh data.json.
"""

import json
import re
import time

import requests
from bs4 import BeautifulSoup
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut

BASE_URL = "https://www.moedrehjaelpen.dk"
LIST_URL = f"{BASE_URL}/lokalforeninger"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "da,en;q=0.5",
}

# Address pattern: "Street N[letter], NNNN CityWord [SHORT-SUFFIX]"
# We search within individual <p> tags (natural boundaries) to avoid trailing text.
_ADDR_RE = re.compile(
    r"[A-ZÆØÅ][a-zA-ZæøåÆØÅ\s\.\-]{2,35}\s\d+[A-Za-z]?"  # street + number
    r"\s*,?\s*"
    r"\d{4}"                                                  # postal code
    r"\s+"
    r"[A-ZÆØÅ][a-zA-ZæøåÆØÅ\-]+"                           # first city word
    r"(?:\s+[A-ZÆØÅ][A-ZÆØÅ\.]{0,3}(?=[^a-zæøå]|$))?"     # optional all-caps suffix
)

# National HQ address – skip if found
_HQ_PATTERN = "Abel Cathrines"


# ── HTTP helper ───────────────────────────────────────────────────────────────

def get_soup(url: str) -> BeautifulSoup:
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")


# ── Geocoder helper ───────────────────────────────────────────────────────────

def geocode(address: str, city: str, geolocator) -> tuple[float | None, float | None]:
    """Try address first, fall back to city name."""
    queries = []
    if address:
        queries.append(f"{address}, Denmark")
    if city:
        queries.append(f"{city}, Denmark")

    for query in queries:
        for attempt in range(3):
            try:
                result = geolocator.geocode(query, country_codes="dk", timeout=10)
                if result:
                    return result.latitude, result.longitude
                break
            except GeocoderTimedOut:
                print(f"    ⚠ Timeout (attempt {attempt + 1}), retrying…")
                time.sleep(2)
    return None, None


# ── Address extraction ────────────────────────────────────────────────────────

def extract_address(soup: BeautifulSoup) -> tuple[str, str]:
    """
    Return (address, city).
    Strategy: scan <p> tags in main content for a postal-code pattern.
    Using <p> as boundary avoids capturing trailing sentence text.
    """
    for p in soup.select("main p, article p"):
        # Normalise non-breaking spaces
        text = p.get_text(" ", strip=True).replace("\xa0", " ")
        m = _ADDR_RE.search(text)
        if m:
            addr = m.group(0).strip().rstrip(" ,.")
            if _HQ_PATTERN in addr:
                continue
            # Extract city: everything after the 4-digit postal code
            city_m = re.search(r"\d{4}\s+(.+)$", addr)
            city = city_m.group(1).strip() if city_m else ""
            return addr, city
    return "", ""


def extract_gmaps_coords(soup: BeautifulSoup) -> tuple[float | None, float | None]:
    """Extract lat/lng from a Google Maps link if present."""
    for a in soup.select('a[href*="maps.google"], a[href*="google.dk/maps"], a[href*="goo.gl/maps"]'):
        m = re.search(r"@(-?\d+\.\d+),(-?\d+\.\d+)", a.get("href", ""))
        if m:
            return float(m.group(1)), float(m.group(2))
    return None, None


# ── Scraping helpers ──────────────────────────────────────────────────────────

def scrape_list() -> list[tuple[str, str]]:
    """Return [(name, absolute_url), ...] from the main listing page."""
    print(f"  Fetching list from {LIST_URL} …")
    soup = get_soup(LIST_URL)

    entries: list[tuple[str, str]] = []
    seen: set[str] = set()

    for a in soup.select("a[href]"):
        href = a["href"]
        if re.match(
            r"^(/|https?://[^/]*moedrehjaelpen\.dk)/lokalforeninger/[^/]+/?$", href
        ):
            if href.startswith("/"):
                href = BASE_URL + href
            href = href.rstrip("/") + "/"
            if href in seen:
                continue
            seen.add(href)
            name = a.get_text(strip=True)
            if name:
                entries.append((name, href))

    return entries


def scrape_lokalforening(name: str, url: str) -> dict:
    """Visit a subpage and extract all relevant fields."""
    soup = get_soup(url)

    # ── canonical name from h1 ────────────────────────────────────────────────
    h1 = soup.select_one("h1.hero-simple__headline, h1")
    if h1:
        name = h1.get_text(" ", strip=True)

    # ── activities from accordion titles ─────────────────────────────────────
    raw_activities = [
        s.get_text(strip=True)
        for s in soup.select("span.accordion__title")
        if s.get_text(strip=True)
    ]
    seen_acts: set[str] = set()
    activities: list[str] = []
    for a in raw_activities:
        if a.lower() not in seen_acts:
            seen_acts.add(a.lower())
            activities.append(a)

    # ── address & city ────────────────────────────────────────────────────────
    address, city = extract_address(soup)

    # If city still missing, derive from URL slug
    if not city:
        slug = url.rstrip("/").split("/")[-1]
        # Mapping for slugs that use ASCII-romanised Danish characters
        _SLUG_TO_CITY = {
            "koege": "Køge",
            "hoeje-taastrup": "Høje Taastrup",
            "helsingoer": "Helsingør",
            "nykoebing-f": "Nykøbing F.",
            "soenderborg": "Sønderborg",
            "noerrebro": "Nørrebro",
            "hilleroed": "Hillerød",
            "holbaek": "Holbæk",
            "naestved": "Næstved",
            "broenderslev": "Brønderslev",
            "hvidovre-roedovre": "Hvidovre-Rødovre",
        }
        city = _SLUG_TO_CITY.get(slug, slug.replace("-", " ").title())

    # ── Google Maps coordinates (opportunistic) ───────────────────────────────
    gmaps_lat, gmaps_lng = extract_gmaps_coords(soup)

    # ── contact block ─────────────────────────────────────────────────────────
    contact_div = soup.select_one(".reveal-box__content.rich-text")
    contact_text = contact_div.get_text(" ", strip=True) if contact_div else ""

    # Email
    email = ""
    if contact_div:
        for a in contact_div.select("a[href^='mailto:']"):
            email = a["href"][7:].strip()
            break
    if not email:
        for a in soup.select("a[href^='mailto:']"):
            candidate = a["href"][7:].strip()
            if "mhj-lokal" in candidate or "lokalforening" in candidate:
                email = candidate
                break
            if not email:
                email = candidate

    # Phone (8-digit Danish number)
    phone = ""
    search_text = contact_text if contact_text else soup.get_text(" ", strip=True)
    phone_m = re.search(r"\b(\d{2}[\s\-]?\d{2}[\s\-]?\d{2}[\s\-]?\d{2})\b", search_text)
    if phone_m:
        phone = re.sub(r"[\s\-]", "", phone_m.group(1))

    return {
        "name": name,
        "url": url,
        "address": address,
        "city": city,
        "phone": phone,
        "email": email,
        "lat": gmaps_lat,   # may be overwritten by Nominatim below
        "lng": gmaps_lng,
        "_has_gmaps": gmaps_lat is not None,
        "activities": activities,
    }


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    print("=== Mødrehjælpen Lokalforening Scraper ===\n")

    geolocator = Nominatim(user_agent="mhj-lokal-scraper/1.0 (educational project)")

    # ── Step 1: list ──────────────────────────────────────────────────────────
    entries = scrape_list()
    print(f"  Found {len(entries)} lokalforeninger.\n")

    # ── Step 2: scrape subpages ───────────────────────────────────────────────
    results: list[dict] = []
    for i, (name, url) in enumerate(entries, 1):
        print(f"[{i:2d}/{len(entries)}] Scraping: {name}")
        try:
            data = scrape_lokalforening(name, url)
            print(f"         address : {data['address'] or '(none)'}")
            print(f"         city    : {data['city']}")
            print(f"         phone   : {data['phone'] or '(none)'}")
            print(f"         email   : {data['email'] or '(none)'}")
            print(f"         gmaps   : {data['_has_gmaps']}")
            print(f"         acts({len(data['activities'])}): {data['activities']}")
            results.append(data)
        except Exception as exc:
            print(f"         ERROR: {exc}")
            slug = url.rstrip("/").split("/")[-1]
            results.append({
                "name": name, "url": url,
                "address": "", "city": slug.replace("-", " ").title(),
                "phone": "", "email": "",
                "lat": None, "lng": None, "_has_gmaps": False, "activities": [],
            })
        time.sleep(0.4)

    print(f"\n=== Geocoding {len(results)} entries ===\n")

    # ── Step 3: geocode (skip if we already have coords from Google Maps) ─────
    for i, entry in enumerate(results, 1):
        if entry.get("_has_gmaps"):
            print(f"[{i:2d}/{len(results)}] {entry['name']}: using Google Maps coords "
                  f"({entry['lat']:.4f}, {entry['lng']:.4f})")
            continue

        q = entry["address"] or entry["city"]
        print(f"[{i:2d}/{len(results)}] Geocoding: {q} …", end=" ", flush=True)
        lat, lng = geocode(entry["address"], entry["city"], geolocator)
        entry["lat"] = lat
        entry["lng"] = lng
        print(f"→ ({lat:.4f}, {lng:.4f})" if lat else "→ NOT FOUND")
        time.sleep(1.1)

    # ── Step 4: clean up & save ───────────────────────────────────────────────
    for entry in results:
        entry.pop("_has_gmaps", None)

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    geocoded = sum(1 for e in results if e["lat"] is not None)
    print(f"\n✓ Saved {len(results)} entries to data.json")
    print(f"✓ Geocoded: {geocoded}/{len(results)}")
    missed = [e["name"] for e in results if e["lat"] is None]
    if missed:
        print(f"  Not geocoded: {missed}")


if __name__ == "__main__":
    main()
