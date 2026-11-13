"""Pull rental listings from Sreality.cz via the memo23/sreality-scraper Apify Actor.

Usage: python scrape.py [--max-price 20000] [--max-items 30]
Saves raw results to data/listings.json.
"""
import argparse
import json
import os
from datetime import timedelta
from pathlib import Path

from apify_client import ApifyClient
from dotenv import load_dotenv

ROOT = Path(__file__).parent
DATA = ROOT / "data"
ACTOR = "memo23/sreality-scraper"

load_dotenv(ROOT / ".env")


def search_url(city="praha", max_price=None):
    url = f"https://www.sreality.cz/hledani/pronajem/byty/{city}"
    if max_price:
        url += f"?cena-do={int(max_price)}"
    return url


def scrape(max_price=None, max_items=30, city="praha"):
    apify = ApifyClient(os.environ["APIFY_TOKEN"])
    run = apify.actor(ACTOR).call(
        run_input={
            "startUrls": [search_url(city, max_price)],
            "maxItems": max_items,
            "fetchDetails": True,  # description, seller contact, priceNote, nearby POIs
            "flatten": False,
        },
        run_timeout=timedelta(minutes=5),
        logger=None,
    )
    if run is None or run.status != "SUCCEEDED":
        raise RuntimeError(f"Apify run failed: {run and run.status}")
    items = list(apify.dataset(run.default_dataset_id).iterate_items())

    DATA.mkdir(exist_ok=True)
    (DATA / "listings.json").write_text(json.dumps(items, ensure_ascii=False, indent=2))
    return items


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--max-price", type=int, default=20000)
    p.add_argument("--max-items", type=int, default=30)
    a = p.parse_args()
    items = scrape(a.max_price, a.max_items)
    print(f"Saved {len(items)} listings to {DATA / 'listings.json'}")
    for it in items[:5]:
        area = (it.get("params") or {}).get("usableArea")
        print(f"  {it['priceCzk']:>6} Kč  {it['disposition']:<5} {area} m²  {it['address']['cityPart']}  {it['url']}")
