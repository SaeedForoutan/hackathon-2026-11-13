# Flat Hunter

An AI agent that helps international students find a flat in Prague.

Built by **Saeed Foroutan** at "AI Agents for the Rest of Us" (AI Tinkerers Prague, Apify office), 13 November 2026.

## The problem

Finding a room in Prague as an international student means checking Sreality.cz every day, reading ads in Czech,
spotting hidden fees and agency commissions, and writing to landlords in a language you don't speak.

## What it does

1. Pulls today's rental listings from Sreality.cz with an [Apify](https://apify.com) Actor (`memo23/sreality-scraper`).
2. Filters them by budget, size and distance to your school or work.
3. Reads each Czech ad with an open model on [Featherless](https://featherless.ai) (Kimi-K3) and explains it in
   plain English: fit score, pros, cons, red flags, real monthly cost and cost to move in.
4. Drafts a polite message to the landlord in Czech, with an English translation, ready to copy or email.
5. Marks listings that are new since your last run.

## Run it

```bash
git clone git@github.com:SaeedForoutan/hackathon-2026-11-13.git
cd hackathon-2026-11-13
uv venv && uv pip install -r requirements.txt
cp .env.example .env   # then add APIFY_TOKEN and FEATHERLESS_API_KEY
.venv/bin/streamlit run app.py
```

The pieces also run on their own: `python scrape.py`, `python filter.py`, `python agent.py`.

## Files

- `scrape.py`: calls the Apify Actor and saves raw listings to `data/listings.json`
- `filter.py`: hard filters and straight-line distance to a target place
- `agent.py`: LLM ranking and explanations in English, Czech message drafting
- `app.py`: Streamlit UI, "new since last run" tracking, offline replay of the last run

## License

MIT, see [LICENSE](LICENSE).
