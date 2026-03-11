"""
TFS Competitor Monitor - Web Scraper
Runs daily via GitHub Actions and saves results to docs/results.json
"""

import json
import re
import time
import random
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-GB,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

TRACKED_PRODUCTS = [
    "Dior Sauvage",
    "Chanel No 5",
    "YSL Black Opium",
    "Carolina Herrera Good Girl",
    "Hugo Boss Bottled",
    "Armani Acqua di Gio",
    "Paco Rabanne 1 Million",
    "Marc Jacobs Daisy",
    "Thierry Mugler Angel",
    "Versace Eros",
]

COMPETITORS = {
    "The Perfume Shop": {
        "offers_url": "https://www.theperfumeshop.com/offers",
        "search_url": "https://www.theperfumeshop.com/search?q={}",
        "base_url": "https://www.theperfumeshop.com",
        "color": "#c8a96e",
    },
    "Boots": {
        "offers_url": "https://www.boots.com/beauty/fragrance/fragrance-offers",
        "search_url": "https://www.boots.com/search?q={}+perfume&searchtext={}+perfume",
        "base_url": "https://www.boots.com",
        "color": "#004f9f",
    },
    "Superdrug": {
        "offers_url": "https://www.superdrug.com/fragrance/c/fragrance?q=%3Arelevance%3AonOffer%3Atrue",
        "search_url": "https://www.superdrug.com/search?q={}",
        "base_url": "https://www.superdrug.com",
        "color": "#e2007a",
    },
}


def fetch(url, retries=1):
    """Fetch a URL - fail fast if blocked, only 1 retry."""
    for attempt in range(retries + 1):
        try:
            time.sleep(random.uniform(1.0, 2.0))
            resp = requests.get(url, headers=HEADERS, timeout=8)
            resp.raise_for_status()
            return resp.text
        except Exception as e:
            if attempt == retries:
                print(f"  ✗ Failed: {e}")
                return None
            print(f"  ↺ Retry {attempt + 1}")
    return None


def extract_prices(html, product_name):
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    results = []
    product_words = [w.lower() for w in product_name.split() if len(w) > 2]
    price_pattern = re.compile(r"£\s*(\d+\.?\d*)")
    all_text = soup.get_text(" ", strip=True)
    for match in re.finditer(r"£\s*\d+\.?\d*", all_text):
        context_start = max(0, match.start() - 200)
        context_end = min(len(all_text), match.end() + 200)
        context = all_text[context_start:context_end].lower()
        if any(word in context for word in product_words):
            price_match = price_pattern.search(match.group())
            if price_match:
                price_val = float(price_match.group(1))
                if 10 < price_val < 500:
                    results.append(price_val)
    return sorted(set(results))


def extract_promotions(html, competitor_name):
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    promos = []
    promo_patterns = [
        r"\d+%\s*off", r"buy\s+\d+\s+get\s+\d+", r"3\s*for\s*2",
        r"2\s*for\s*1", r"free\s+\w+", r"save\s+£\d+",
        r"was\s+£[\d.]+\s+now\s+£[\d.]+", r"half\s+price",
        r"spend\s+£\d+\s+save", r"\d+\s+for\s+£\d+",
    ]
    full_text = soup.get_text(" ", strip=True)
    seen = set()
    for pattern in promo_patterns:
        for match in re.finditer(pattern, full_text, re.IGNORECASE):
            start = max(0, match.start() - 60)
            end = min(len(full_text), match.end() + 60)
            snippet = re.sub(r"\s+", " ", full_text[start:end].strip())
            if snippet not in seen and len(snippet) > 10:
                seen.add(snippet)
                promos.append({"type": match.group(0).lower(), "context": snippet[:150]})
                if len(promos) >= 8:
                    break
    return promos


def scrape_competitor(name, config):
    print(f"\n🔍 Scraping {name}...")
    result = {
        "name": name, "color": config["color"],
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "status": "ok", "promotions": [], "prices": {}, "errors": [],
    }
    print(f"  → Offers page")
    offers_html = fetch(config["offers_url"])
    if offers_html:
        result["promotions"] = extract_promotions(offers_html, name)
        print(f"  ✓ Found {len(result['promotions'])} promotions")
    else:
        result["errors"].append("Could not load offers page")
        result["status"] = "partial"

    for product in TRACKED_PRODUCTS[:5]:
        search_url = config["search_url"].format(
            product.replace(" ", "+"), product.replace(" ", "+"))
        print(f"  → Price: {product}")
        html = fetch(search_url)
        prices = extract_prices(html, product) if html else []
        result["prices"][product] = prices[0] if prices else None
        if prices:
            print(f"     £{prices[0]}")
    return result


def load_previous(data_file):
    if data_file.exists():
        try:
            with open(data_file) as f:
                return json.load(f)
        except Exception:
            pass
    return None


def detect_changes(current, previous):
    changes = []
    if not previous:
        return changes
    prev_by_name = {c["name"]: c for c in previous.get("competitors", [])}
    for comp in current.get("competitors", []):
        prev = prev_by_name.get(comp["name"])
        if not prev:
            continue
        for product, price in comp["prices"].items():
            prev_price = prev.get("prices", {}).get(product)
            if price and prev_price and price != prev_price:
                changes.append({
                    "competitor": comp["name"], "type": "price_change",
                    "product": product, "old_price": prev_price, "new_price": price,
                    "direction": "up" if price > prev_price else "down",
                    "amount": abs(price - prev_price),
                })
        prev_count = len(prev.get("promotions", []))
        curr_count = len(comp.get("promotions", []))
        if curr_count != prev_count:
            changes.append({
                "competitor": comp["name"], "type": "promotion_change",
                "old_count": prev_count, "new_count": curr_count,
            })
    return changes


def main():
    print("=" * 60)
    print("TFS Competitor Monitor — Scraper")
    print(f"Running at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 60)

    data_file = Path("docs/results.json")
    data_file.parent.mkdir(exist_ok=True)
    previous = load_previous(data_file)

    results = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tracked_products": TRACKED_PRODUCTS,
        "competitors": [],
    }

    for name, config in COMPETITORS.items():
        try:
            results["competitors"].append(scrape_competitor(name, config))
        except Exception as e:
            print(f"  ✗ Unexpected error: {e}")
            results["competitors"].append({
                "name": name, "color": config["color"], "status": "error",
                "error": str(e), "promotions": [], "prices": {},
            })

    results["changes"] = detect_changes(results, previous)

    with open(data_file, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\n✅ Done — {len(results['competitors'])} competitors, {len(results['changes'])} changes")


if __name__ == "__main__":
    main()
