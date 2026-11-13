"""Normalize raw Sreality listings and apply hard filters (price, size, distance).

Usage: python filter.py [--max-price 20000] [--min-area 25] [--target "ČVUT Dejvice"] [--max-km 6]
"""
import argparse
import json
import math
from functools import lru_cache
from pathlib import Path

import requests

DATA = Path(__file__).parent / "data"

# Common targets for students in Prague, so the demo doesn't depend on a geocoder.
KNOWN_PLACES = {
    "čvut dejvice": (50.1029, 14.3925),
    "cvut dejvice": (50.1029, 14.3925),
    "čvut karlovo náměstí": (50.0760, 14.4185),
    "univerzita karlova": (50.0880, 14.4040),
    "vše žižkov": (50.0843, 14.4413),
    "vse zizkov": (50.0843, 14.4413),
    "václavské náměstí": (50.0810, 14.4280),
    "apify": (50.0884, 14.4352),  # Apify office, Prague (hackathon venue)
}


@lru_cache(maxsize=64)
def geocode(place):
    """Return (lat, lon) for a place name; known places first, then OpenStreetMap Nominatim."""
    key = place.strip().lower()
    if key in KNOWN_PLACES:
        return KNOWN_PLACES[key]
    r = requests.get(
        "https://nominatim.openstreetmap.org/search",
        params={"q": f"{place}, Praha", "format": "json", "limit": 1, "countrycodes": "cz"},
        headers={"User-Agent": "flat-hunter-hackathon/0.1"},
        timeout=10,
    )
    r.raise_for_status()
    hits = r.json()
    if not hits:
        raise ValueError(f"Could not find place: {place}")
    return float(hits[0]["lat"]), float(hits[0]["lon"])


def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(a))


def normalize(it):
    """Flatten one memo23 listing into the fields the rest of the app uses."""
    p = it.get("params") or {}
    a = it.get("address") or {}
    pois = sorted(it.get("nearbyPois") or [], key=lambda x: x.get("distance", 1e9))
    return {
        "id": str(it["id"]),
        "url": it["url"],
        "title": it.get("name"),
        "price": it.get("priceCzk"),
        "disposition": it.get("disposition"),
        # Top-level `surface` is unreliable in this Actor's output; usableArea is correct.
        "area": p.get("usableArea") or p.get("floorArea"),
        "address": ", ".join(x for x in (a.get("street"), a.get("cityPart"), a.get("district")) if x),
        "lat": it.get("latitude"),
        "lon": it.get("longitude"),
        "description": it.get("description") or "",
        "price_note": p.get("priceNote") or "",
        "furnished": p.get("furnished"),
        "ready_date": p.get("readyDate"),
        "floor": p.get("floorNumber"),
        "seller_name": it.get("sellerName"),
        "seller_phone": it.get("sellerPhone"),
        "seller_email": it.get("sellerEmail"),
        "agency": it.get("agency"),
        "photos": (it.get("photos") or [])[:4],
        "nearby": [f"{x['name']} ({x['distance']} m)" for x in pois[:10]],
    }


def apply_filters(listings, max_price=None, min_area=None, max_area=None,
                  target=None, max_km=None, dispositions=None):
    """Hard filters in plain code. Adds `distance_km` when a target is given; sorts by it."""
    target_ll = geocode(target) if target else None
    out = []
    for x in listings:
        if max_price and (x["price"] is None or x["price"] > max_price):
            continue
        if min_area and (x["area"] is None or x["area"] < min_area):
            continue
        if max_area and x["area"] is not None and x["area"] > max_area:
            continue
        if dispositions and x["disposition"] not in dispositions:
            continue
        x = dict(x, distance_km=None)
        if target_ll and x["lat"] is not None:
            x["distance_km"] = round(haversine_km(*target_ll, x["lat"], x["lon"]), 1)
            if max_km and x["distance_km"] > max_km:
                continue
        out.append(x)
    out.sort(key=lambda x: (x["distance_km"] is None, x["distance_km"] or 0, x["price"] or 0))
    return out


def load_listings(path=DATA / "listings.json"):
    return [normalize(it) for it in json.loads(Path(path).read_text())]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-price", type=int, default=20000)
    ap.add_argument("--min-area", type=int)
    ap.add_argument("--target", default="ČVUT Dejvice")
    ap.add_argument("--max-km", type=float)
    a = ap.parse_args()
    all_ = load_listings()
    kept = apply_filters(all_, a.max_price, a.min_area, target=a.target, max_km=a.max_km)
    print(f"{len(kept)}/{len(all_)} listings pass filters (target: {a.target})")
    for x in kept:
        print(f"  {x['distance_km']:>5} km  {x['price']:>6} Kč  {x['disposition']:<5} {x['area']} m²  {x['address']}")
