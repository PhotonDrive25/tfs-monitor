"""
TFS Competitor Monitor - Web Scraper v2
Now captures bottle sizes alongside prices.
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
        "color": "#c8a96e",
    },
    "Boots": {
        "offers_url": "https://www.boots.com/beauty/fragrance/fragrance-offers",
        "search_url": "https://www.boots.com/search?q={}+perfume&searchtext={}+perfume",
        "color": "#004f9f",
    },
    "Superdrug": {
        "offers_url": "https://www.superdrug.com/fragrance/c/fragrance?q=%3Arelevance%3AonOffer%3Atrue",
        "search_url": "https://www.superdrug.com/search?q={}",
        "color": "#e2007a",
    },
}

# Size pattern — matches: 50ml, 100 ml, 75ML, 1.7oz, 200ml etc.
SIZE_PATTERN = re.compile(r"(\d+\.?\d*)\s*(ml|ML|Ml|oz|OZ)", re.IGNORECASE)
PRICE_PATTERN = re.compile(r"£\s*(\d+\.?\d*)")


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


def extract_size_from_context(context):
    """Pull the most relevant bottle size from surrounding text."""
    size_match = SIZE_PATTERN.search(context)
    if size_match:
        amount = size_match.group(1)
        unit = size_match.group(2).lower()
        # Normalise: remove .0 from whole numbers
        if amount.endswith(".0"):
            amount = amount[:-2]
        return f"{amount}{unit}"
    return None


def extract_prices(html, product_name):
    """
    Returns a list of dicts: [{"price": 85.0, "size": "100ml"}, ...]
    sorted by price ascending.
    """
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    results = []
    seen_prices = set()
    product_words = [w.lower() for w in product_name.split() if len(w) > 2]
    all_text = soup.get_text(" ", strip=True)

    for match in re.finditer(r"£\s*\d+\.?\d*", all_text):
        context_start = max(0, match.start() - 250)
        context_end = min(len(all_text), match.end() + 250)
        context = all_text[context_start:context_end]
        context_lower = context.lower()

        # Must mention the product
        if not any(word in context_lower for word in product_words):
            continue

        price_match = PRICE_PATTERN.search(match.group())
        if not price_match:
            continue

        price_val = float(price_match.group(1))
        if not (10 < price_val < 500):
            continue

        # Avoid duplicates
        if price_val in seen_prices:
            continue
        seen_prices.add(price_val)

        # Try to find the bottle size in the same context window
        size = extract_size_from_context(context)

        results.append({"price": price_val, "size": size})

    # Sort cheapest first
    results.sort(key=lambda x: x["price"])
    return results


def extract_promotions(html):
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
        "name": name,
        "color": config["color"],
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "status": "ok",
        "promotions": [],
        # prices is now: { "Dior Sauvage": [{"price": 85.0, "size": "100ml"}, ...] }
        "prices": {},
        "errors": [],
    }

    # Scrape offers page
    offers_html = fetch(config["offers_url"])
    if offers_html:
        result["promotions"] = extract_promotions(offers_html)
        print(f"  ✓ {len(result['promotions'])} promotions")
    else:
        result["errors"].append("Could not load offers page")
        result["status"] = "partial"

    # Scrape prices
    for product in TRACKED_PRODUCTS[:5]:
        search_url = config["search_url"].format(product.replace(" ", "+"))
        print(f"  → {product}")
        html = fetch(search_url)
        variants = extract_prices(html, product) if html else []
        result["prices"][product] = variants  # list of {price, size}
        if variants:
            summary = ", ".join(
                f"£{v['price']} ({v['size'] or '?'})" for v in variants[:3]
            )
            print(f"     {summary}")

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

        for product, variants in comp["prices"].items():
            prev_variants = prev.get("prices", {}).get(product, [])

            # Compare cheapest available price for change detection
            curr_cheapest = variants[0]["price"] if variants else None
            # Handle old format (plain float) and new format (list of dicts)
            if prev_variants and isinstance(prev_variants, list) and len(prev_variants) > 0:
                prev_cheapest = prev_variants[0]["price"] if isinstance(prev_variants[0], dict) else prev_variants[0]
            elif prev_variants and isinstance(prev_variants, (int, float)):
                prev_cheapest = prev_variants
            else:
                prev_cheapest = None

            if curr_cheapest and prev_cheapest and curr_cheapest != prev_cheapest:
                changes.append({
                    "competitor": comp["name"],
                    "type": "price_change",
                    "product": product,
                    "old_price": prev_cheapest,
                    "new_price": curr_cheapest,
                    "direction": "up" if curr_cheapest > prev_cheapest else "down",
                    "amount": abs(curr_cheapest - prev_cheapest),
                })

        prev_count = len(prev.get("promotions", []))
        curr_count = len(comp.get("promotions", []))
        if curr_count != prev_count:
            changes.append({
                "competitor": comp["name"],
                "type": "promotion_change",
                "old_count": prev_count,
                "new_count": curr_count,
            })

    return changes


def main():
    print("=" * 60)
    print("TFS Competitor Monitor — Scraper v2 (with bottle sizes)")
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
