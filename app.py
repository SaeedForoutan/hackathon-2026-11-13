"""Flat Hunter: Streamlit UI for the live demo.

Run: streamlit run app.py
"""
import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import streamlit as st

from agent import DEFAULT_MODEL, DEFAULT_PROFILE, MODEL_CHOICES, draft_message, rank
from filter import apply_filters, load_listings, normalize
from scrape import scrape

DATA = Path(__file__).parent / "data"
SEEN = DATA / "seen.json"          # listing id -> first time we saw it
LAST_RUN = DATA / "last_run.json"  # backup of the last good run, for offline demo
AUTO_DRAFT_TOP = 3

st.set_page_config(page_title="Flat Hunter", page_icon="🏠", layout="wide")


# ---------- "new since last run" ----------

def load_seen():
    try:
        return json.loads(SEEN.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_seen(seen):
    DATA.mkdir(exist_ok=True)
    SEEN.write_text(json.dumps(seen, indent=1))


# ---------- pipeline ----------

def run_pipeline(profile, model, max_price, min_area, max_km, max_items, use_saved, only_new):
    with st.status("Hunting for flats…", expanded=True) as status:
        if use_saved:
            st.write("📂 Using saved listings (no Apify call)")
            listings = load_listings()
        else:
            st.write(f"🕷️ Pulling today's Sreality listings with Apify (up to {max_items})…")
            t = time.time()
            listings = [normalize(it) for it in scrape(max_price=max_price, max_items=max_items)]
            st.write(f"   got {len(listings)} listings in {time.time() - t:.0f}s")

        kept = apply_filters(listings, max_price=max_price, min_area=min_area,
                             target=profile["target"], max_km=max_km)
        st.write(f"🔎 {len(kept)} of {len(listings)} match budget, size and distance")

        seen = load_seen()
        for x in kept:
            x["is_new"] = x["id"] not in seen
        n_new = sum(x["is_new"] for x in kept)
        st.write(f"🆕 {n_new} are new since the last run")
        st.session_state["empty_reason"] = (
            "Nothing new since your last run. Untick **Only show new** to see everything again."
            if kept else "No listings match. Try a higher budget or a larger distance.")
        if only_new:
            kept = [x for x in kept if x["is_new"]]

        if not kept:
            status.update(label="No matching listings", state="complete")
            return []

        bar = st.progress(0.0, text="🧠 Reading the Czech ads…")
        ranked = rank(kept, profile, model=model,
                      on_progress=lambda d, n: bar.progress(d / n, text=f"🧠 Reading the Czech ads… {d}/{n}"))

        top = [x for x in ranked if x["analysis"]][:AUTO_DRAFT_TOP]
        st.write(f"✉️ Drafting Czech messages for the top {len(top)}…")
        with ThreadPoolExecutor(3) as ex:
            for x, m in zip(top, ex.map(lambda x: _safe_draft(x, profile, model), top)):
                x["message"] = m

        now = datetime.now().isoformat(timespec="seconds")
        for x in kept:
            seen.setdefault(x["id"], now)
        save_seen(seen)
        LAST_RUN.write_text(json.dumps({"profile": profile, "model": model, "at": now, "results": ranked}, ensure_ascii=False))
        status.update(label=f"Done: {len(ranked)} flats ranked", state="complete", expanded=False)
    return ranked


def _safe_draft(x, profile, model):
    try:
        return draft_message(x, profile, model).model_dump()
    except Exception as e:
        return {"error": str(e)[:200]}


# ---------- UI ----------

def score_color(s):
    return "green" if s >= 65 else "orange" if s >= 45 else "red"


def fmt_czk(n):
    return f"{n:,} Kč".replace(",", " ") if n else "?"


def render_message(x, profile, model, key):
    m = x.get("message")
    if m is None:
        if st.button("✉️ Draft message in Czech", key=f"draft-{key}"):
            with st.spinner("Writing in Czech…"):
                x["message"] = m = _safe_draft(x, profile, model)
        else:
            return
    if "error" in m:
        st.error(f"Could not draft message: {m['error']}")
        return
    st.markdown("**Message to the landlord** (copy button top-right)")
    st.code(m["czech"], language=None, wrap_lines=True)
    with st.expander("What it says in English"):
        st.write(m["english"])
    if x.get("seller_email"):
        mailto = f"mailto:{x['seller_email']}?subject={quote('Pronájem: ' + (x['title'] or ''))}&body={quote(m['czech'])}"
        st.link_button("Open in email", mailto)


def render_card(i, x, profile, model):
    an = x["analysis"]
    with st.container(border=True):
        left, right = st.columns([1, 2.3], gap="medium")
        with left:
            if x["photos"]:
                st.image(x["photos"][0], width="stretch")
            st.link_button("Open on Sreality ↗", x["url"], width="stretch")
            contact = " · ".join(v for v in (x.get("seller_name"), x.get("seller_phone"), x.get("seller_email")) if v)
            if contact:
                st.caption(f"📇 {contact}")
        with right:
            badges = []
            if an:
                badges.append(f":{score_color(an['score'])}-badge[Fit {an['score']}/100]")
            if x.get("is_new"):
                badges.append(":blue-badge[NEW]")
            st.markdown(" ".join(badges))
            st.subheader(f"#{i} · {x['disposition']} · {x['area'] or '?'} m² · {fmt_czk(x['price'])}/month")
            dist = f" · 📍 {x['distance_km']} km from {profile['target']}" if x.get("distance_km") is not None else ""
            st.caption(f"{x['address']}{dist}")

            if not an:
                st.warning(f"Could not analyse this listing: {x.get('error')}")
                return
            st.write(an["summary"])
            c1, c2 = st.columns(2)
            c1.metric("Real monthly cost", fmt_czk(an["total_monthly_czk"]))
            c2.metric("Cost to move in", fmt_czk(an["move_in_cost_czk"]))
            p, c = st.columns(2)
            p.markdown("**👍 Pros**\n" + "\n".join(f"- {s}" for s in an["pros"]))
            c.markdown("**👎 Cons**\n" + "\n".join(f"- {s}" for s in an["cons"]))
            if an["red_flags"]:
                st.error("**🚩 Red flags**\n" + "\n".join(f"- {s}" for s in an["red_flags"]))
            render_message(x, profile, model, key=x["id"])


with st.sidebar:
    st.header("👤 Who's looking?")
    name = st.text_input("Name", DEFAULT_PROFILE["name"])
    about = st.text_area("About you", DEFAULT_PROFILE["about"], height=90)
    target = st.text_input("School / work (for commute)", DEFAULT_PROFILE["target"])
    notes = st.text_area("What matters to you", DEFAULT_PROFILE["notes"], height=90)

    st.header("🔎 Search")
    max_price = st.number_input("Max rent (Kč/month)", 5000, 100000, 20000, step=1000)
    min_area = st.number_input("Min size (m²)", 0, 200, 25, step=5)
    max_km = st.slider("Max distance (km)", 1.0, 20.0, 10.0, step=0.5)
    max_items = st.slider("Listings to pull from Sreality", 5, 60, 20, step=5)

    st.header("🧠 AI model")
    model = st.selectbox("Model (on Featherless)", list(MODEL_CHOICES), format_func=MODEL_CHOICES.get,
                         index=list(MODEL_CHOICES).index(DEFAULT_MODEL) if DEFAULT_MODEL in MODEL_CHOICES else 0,
                         help="Reads the Czech ads and writes the landlord message. "
                              "If it fails, the app falls back to DeepSeek V3.2.")
    only_new = st.checkbox("Only show new since last run", value=False)
    use_saved = st.checkbox("Offline: re-use last scraped listings", value=False,
                            help="Skips Apify; still runs the AI on data/listings.json")

    go = st.button("🏠 Find flats", type="primary", width="stretch")

    st.divider()
    if LAST_RUN.exists() and st.button("⏪ Show last saved run (no network)", width="stretch"):
        saved = json.loads(LAST_RUN.read_text())
        st.session_state.update(results=saved["results"], profile=saved["profile"], run_at=saved["at"],
                                run_model=saved.get("model"))
    if st.button("Forget seen listings", width="stretch"):
        SEEN.unlink(missing_ok=True)
        st.toast("Seen history cleared: every listing counts as new again")

st.title("🏠 Flat Hunter")
st.caption("Today's Prague rentals from Sreality, read for you in plain English, "
           "with a polite Czech message to the landlord ready to send.")

if go:
    profile = {"name": name, "about": about, "target": target, "notes": notes}
    try:
        results = run_pipeline(profile, model, max_price, min_area, max_km, max_items, use_saved, only_new)
        st.session_state.update(results=results, profile=profile, run_model=model,
                                run_at=datetime.now().isoformat(timespec="seconds"))
    except Exception as e:
        st.error(f"Something failed: {e}. Try **Show last saved run** in the sidebar.")

results = st.session_state.get("results")
if results is None:
    st.info("Fill in your needs on the left and press **Find flats**.")
elif not results:
    st.warning(st.session_state.get("empty_reason", "No listings match."))
else:
    profile = st.session_state["profile"]
    n_new = sum(bool(x.get("is_new")) for x in results)
    run_model = st.session_state.get("run_model")
    by = f" · by {MODEL_CHOICES.get(run_model, run_model).split(' (')[0]}" if run_model else ""
    st.markdown(f"**{len(results)} flats ranked for {profile['name']}** · {n_new} new{by} · run at {st.session_state['run_at']}")
    for i, x in enumerate(results, 1):
        render_card(i, x, profile, model)

st.divider()
st.caption("Built by **Saeed Foroutan** · AI Tinkerers Prague hackathon, 13 Nov 2026 · "
           "Data: Apify · AI: Featherless")
