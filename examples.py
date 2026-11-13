"""Run the full Flat Hunter pipeline for 10 example renters and save everything to a CSV.

One Apify scrape per distinct budget (merged, shared by all examples), then for each example:
hard filters -> LLM ranking + English explanation -> Czech landlord message for the top few.

Usage: python examples.py [--max-items 30] [--offline] [--per-example 10] [--drafts 3]
Writes data/examples_listings.json (raw scrape) and data/examples_results.csv (one row per example x listing).
Does not touch data/listings.json, data/seen.json or data/last_run.json (the demo's files).
"""
import argparse
import csv
import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from agent import DEFAULT_MODEL, draft_message, rank
from filter import apply_filters, normalize

DATA = Path(__file__).parent / "data"
RAW = DATA / "examples_listings.json"
OUT = DATA / "examples_results.csv"

EXAMPLES = [
    {"id": 1, "name": "Saeed", "about": "27, international master's student at ČVUT, part-time job, non-smoker, no pets",
     "target": "ČVUT Dejvice", "notes": "needs address registration (přechodný pobyt) for visa; near metro; move in within a month",
     "max_price": 20000, "min_area": 25, "max_km": 10},
    {"id": 2, "name": "Priya", "about": "23, Indian exchange student at VŠE for one semester, quiet, non-smoker",
     "target": "VŠE Žižkov", "notes": "tight budget; furnished only; short lease (5 months) if possible",
     "max_price": 15000, "min_area": 15, "max_km": 6},
    {"id": 3, "name": "Lucas", "about": "25, Brazilian PhD student at Charles University with a stipend",
     "target": "Univerzita Karlova", "notes": "wants a quiet place to study; ok with a studio; no agency fee if possible",
     "max_price": 18000, "min_area": 20, "max_km": 5},
    {"id": 4, "name": "Amina and Omar", "about": "married couple from Egypt, both working in IT, non-smokers",
     "target": "Karlín", "notes": "need 2 rooms (2+kk or 2+1); want a balcony; long-term lease",
     "max_price": 30000, "min_area": 45, "max_km": 8},
    {"id": 5, "name": "Yuki", "about": "29, Japanese software engineer relocating to Prague, has a small cat",
     "target": "Anděl", "notes": "must allow pets (cat); good tram connection; available now",
     "max_price": 25000, "min_area": 30, "max_km": 7},
    {"id": 6, "name": "Daniel", "about": "21, Ukrainian bachelor student at ČVUT, works weekends in a café",
     "target": "ČVUT Karlovo náměstí", "notes": "cheapest possible; fine with a small room; utilities must be clear",
     "max_price": 13000, "min_area": 10, "max_km": 8},
    {"id": 7, "name": "Sofia", "about": "26, Italian intern at a startup near Wenceslas Square, 6-month internship",
     "target": "Václavské náměstí", "notes": "walking distance to work preferred; furnished; safe area at night",
     "max_price": 22000, "min_area": 20, "max_km": 3},
    {"id": 8, "name": "Mehmet", "about": "31, Turkish postdoc at the Czech Academy of Sciences in Libeň, non-smoker",
     "target": "Palmovka", "notes": "needs a desk space for home office; near metro B; address registration",
     "max_price": 20000, "min_area": 30, "max_km": 6},
    {"id": 9, "name": "Emma", "about": "24, American master's student, moving with a friend who will share the flat",
     "target": "Univerzita Karlova", "notes": "two people sharing; 2 rooms preferred; split rent; furnished",
     "max_price": 28000, "min_area": 40, "max_km": 6},
    {"id": 10, "name": "Kwame", "about": "28, Ghanaian data analyst who just got a job offer at an office in Pankrác",
     "target": "Pankrác", "notes": "worried about 'no foreigners' ads; wants clear contract in English if possible; near metro C",
     "max_price": 24000, "min_area": 25, "max_km": 7},
]

COLUMNS = [
    "example_id", "person", "about", "target", "notes", "max_price", "min_area", "max_km", "model",
    "listings_scraped", "listings_matching", "rank", "is_top_drafted",
    "listing_id", "url", "title", "price_czk", "disposition", "area_m2", "address", "distance_km",
    "furnished", "ready_date", "floor", "agency", "seller_name", "seller_phone", "seller_email",
    "score", "summary", "pros", "cons", "red_flags", "total_monthly_czk", "move_in_cost_czk",
    "message_czech", "message_english", "error", "run_at",
]


def get_listings(max_items, offline):
    if offline:
        raw = json.loads(RAW.read_text())
    else:
        from scrape import ACTOR, search_url  # imports apify client only when needed
        import os
        from datetime import timedelta
        from apify_client import ApifyClient

        apify = ApifyClient(os.environ["APIFY_TOKEN"])

        def one(max_price):
            run = apify.actor(ACTOR).call(
                run_input={"startUrls": [search_url("praha", max_price)], "maxItems": max_items,
                           "fetchDetails": True, "flatten": False},
                run_timeout=timedelta(minutes=8), logger=None)
            if run is None or run.status != "SUCCEEDED":
                raise RuntimeError(f"Apify run failed for {max_price} Kč: {run and run.status}")
            return list(apify.dataset(run.default_dataset_id).iterate_items())

        # One Sreality search per distinct budget, like each person would run in the app: a single broad
        # search only returns the expensive end, so cheap budgets would find nothing.
        budgets = sorted({e["max_price"] for e in EXAMPLES})
        with ThreadPoolExecutor(3) as pool:
            batches = list(pool.map(one, budgets))
        raw = list({str(it["id"]): it for batch in batches for it in batch}.values())
        print(f"{len(budgets)} searches: " + ", ".join(f"≤{b}: {len(r)}" for b, r in zip(budgets, batches)))
        DATA.mkdir(exist_ok=True)
        RAW.write_text(json.dumps(raw, ensure_ascii=False, indent=2))
    return [normalize(it) for it in raw]


def safe_draft(x, profile, model):
    try:
        return draft_message(x, profile, model).model_dump()
    except Exception as e:
        return {"error": str(e)[:200]}


def run_example(ex, listings, model, per_example, drafts):
    profile = {k: ex[k] for k in ("name", "about", "target", "notes")}
    kept = apply_filters(listings, max_price=ex["max_price"], min_area=ex["min_area"],
                         target=ex["target"], max_km=ex["max_km"])
    n_match = len(kept)
    ranked = rank(kept[:per_example], profile, model=model) if kept else []
    top = [x for x in ranked if x["analysis"]][:drafts]
    with ThreadPoolExecutor(3) as pool:
        for x, m in zip(top, pool.map(lambda x: safe_draft(x, profile, model), top)):
            x["message"] = m

    now = datetime.now().isoformat(timespec="seconds")
    base = {"example_id": ex["id"], "person": ex["name"], "about": ex["about"], "target": ex["target"],
            "notes": ex["notes"], "max_price": ex["max_price"], "min_area": ex["min_area"],
            "max_km": ex["max_km"], "model": model, "listings_scraped": len(listings),
            "listings_matching": n_match, "run_at": now}
    if not ranked:  # keep a row so the CSV shows this example found nothing
        return [dict(base, rank=0, error="no listings match the filters")]

    rows = []
    for i, x in enumerate(ranked, 1):
        an, m = x.get("analysis") or {}, x.get("message") or {}
        rows.append(dict(
            base, rank=i, is_top_drafted="message" in x,
            listing_id=x["id"], url=x["url"], title=x["title"], price_czk=x["price"],
            disposition=x["disposition"], area_m2=x["area"], address=x["address"],
            distance_km=x["distance_km"], furnished=x["furnished"], ready_date=x["ready_date"],
            floor=x["floor"], agency=x["agency"], seller_name=x["seller_name"],
            seller_phone=x["seller_phone"], seller_email=x["seller_email"],
            score=an.get("score"), summary=an.get("summary"),
            pros=" | ".join(an.get("pros", [])), cons=" | ".join(an.get("cons", [])),
            red_flags=" | ".join(an.get("red_flags", [])),
            total_monthly_czk=an.get("total_monthly_czk"), move_in_cost_czk=an.get("move_in_cost_czk"),
            message_czech=m.get("czech"), message_english=m.get("english"),
            error=x.get("error") or m.get("error"),
        ))
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-items", type=int, default=30, help="listings per budget search")
    ap.add_argument("--offline", action="store_true", help="re-use data/examples_listings.json, skip Apify")
    ap.add_argument("--per-example", type=int, default=10, help="max listings analysed per example (nearest first)")
    ap.add_argument("--drafts", type=int, default=3, help="Czech messages drafted per example")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    a = ap.parse_args()

    t = time.time()
    listings = get_listings(a.max_items, a.offline)
    print(f"{len(listings)} listings ({'saved' if a.offline else 'scraped'}) in {time.time() - t:.0f}s")

    all_rows = []
    for ex in EXAMPLES:
        t = time.time()
        rows = run_example(ex, listings, a.model, a.per_example, a.drafts)
        all_rows += rows
        best = rows[0]
        print(f"#{ex['id']:>2} {ex['name']:<15} {best['listings_matching']:>2} match, "
              f"{sum(r.get('score') is not None for r in rows)} ranked, "
              f"{sum(bool(r.get('message_czech')) for r in rows)} drafts, "
              f"{sum(bool(r.get('error')) and r['rank'] > 0 for r in rows)} errors, "
              f"top score {best.get('score')} ({time.time() - t:.0f}s)")

    with OUT.open("w", newline="", encoding="utf-8-sig") as f:  # BOM so Excel shows Czech characters
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(all_rows)
    print(f"Saved {len(all_rows)} rows to {OUT}")
