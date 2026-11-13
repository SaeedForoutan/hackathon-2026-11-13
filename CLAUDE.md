# Project: Flat Hunter agent (hackathon build)

## Context
- Event: "AI Agents for the Rest of Us", interdisciplinary hackathon by AI Tinkerers Prague, Apify office, Fri 13 Nov 2026.
- Building time: 11:30 to 18:00. Team presentations start at 18:00. The demo must run LIVE.
- Sponsors whose tools we should use well: **Apify** (web data) and **Featherless** (open-model inference).
- Judging rubric:
  1. Is there a real problem and a specific person who has it?
  2. Does it work live, and did we make good use of the tools?
  3. Would "the rest of us" actually use it, or is it just a wrapper?

## The idea
**Person:** an international student looking for a room or flat in Prague (use a real, named person for the pitch, ideally someone on the team).
**Mundane task:** checking Sreality.cz every day, reading Czech ads, filtering out bad ones, and writing to landlords in Czech.
**What the agent does:**
1. Pulls today's listings from Sreality with an Apify Actor.
2. Filters them by the person's needs (budget, size, location).
3. Ranks the remaining ones and explains each in plain English (pros, cons, red flags).
4. Drafts a polite message to the landlord **in Czech**, ready to send.
5. Shows only listings that are new since the last run.

## Tools

### Apify (data)
Ready-made Sreality scrapers exist in Apify Store. Test both quickly with a small run (maxItems 5) and keep the one that works best:
- `swerve/sreality-scraper` — structured input: `location`, `dealType`, `propertyType`, `maxItems`, `minPrice`, `maxPrice`, `minArea`, `maxArea`, `fetchDetails`, `excludeAgents`, ... (about $0.005 per result)
- `memo23/sreality-scraper` — input is `startUrls` (paste a Sreality search URL); returns price, Kč/m², disposition, address, GPS, photos, agency; `fetchDetails` adds full description and seller contact (about $0.001 per result)

Before calling an Actor, check its input schema. Python client: `pip install apify-client`.

```python
from apify_client import ApifyClient
apify = ApifyClient(os.environ["APIFY_TOKEN"])
run = apify.actor("swerve/sreality-scraper").call(run_input={...})
items = list(apify.dataset(run["defaultDatasetId"]).iterate_items())
```

### Featherless (model)
OpenAI-compatible API. Use the normal `openai` library:

```python
from openai import OpenAI
llm = OpenAI(api_key=os.environ["FEATHERLESS_API_KEY"],
             base_url="https://api.featherless.ai/v1")
```

- List models: `GET https://api.featherless.ai/v1/models`.
- Pick a strong instruct model (for example a Llama 3.3 70B or Qwen instruct model). **Test Czech writing quality early**, because the landlord message must read naturally.
- Ask the model for JSON output for the ranking step, and validate it.

## Suggested architecture (keep it simple)
- `scrape.py` — call the Apify Actor, save raw results to `data/listings.json`.
- `filter.py` — hard filters in plain code (price, size). Distance to the person's school/work from listing GPS (haversine) as the first version of "commute".
- `agent.py` — LLM steps: rank + explain in English, draft Czech message.
- `app.py` — small UI for the live demo (Streamlit is fastest). Inputs: budget, area, size, target address, a few personal notes ("no smokers", "near metro"). Output: ranked cards with English summary, link, and the Czech message with a copy button.
- `.env` — `APIFY_TOKEN`, `FEATHERLESS_API_KEY`. Never commit it.

## Plan for the day
- 11:30–12:30 — set up project, keys, one successful small Apify run.
- 12:30–14:30 — filtering + LLM ranking and explanations; Czech message drafting.
- 14:30–16:30 — Streamlit UI; "new since last run" tracking.
- 16:30–17:30 — polish, test end to end with the real person's needs.
- 17:30–18:00 — rehearse the demo. **Save one good run's results as a backup** in case the network or an API fails live.

## Notes
- Keep the scope small. A working live demo matters more than extra features.
- PostHog is not a sponsor of this event, so it is optional.
