<h1 align="center">🏠 Flat Hunter</h1>

<p align="center">
  <b>An AI agent that helps international students find a flat in Prague.</b><br>
  It reads Czech rental ads for you, flags the catches, and writes to the landlord in Czech.
</p>

<p align="center">
  <a href="https://flat-hunter-wfx0.onrender.com/">
    <img alt="Open the live app" src="https://img.shields.io/badge/Live_demo-Open_the_app-2ea44f?style=for-the-badge&logo=streamlit&logoColor=white">
  </a>
</p>

<p align="center">
  <a href="https://flat-hunter-wfx0.onrender.com/"><b>flat-hunter-wfx0.onrender.com</b></a>
</p>

<p align="center">
  <img alt="Data: Apify" src="https://img.shields.io/badge/data-Apify-97d700?style=flat-square">
  <img alt="AI: Featherless" src="https://img.shields.io/badge/AI-Featherless-7c3aed?style=flat-square">
  <img alt="UI: Streamlit" src="https://img.shields.io/badge/UI-Streamlit-ff4b4b?style=flat-square&logo=streamlit&logoColor=white">
  <img alt="Python 3" src="https://img.shields.io/badge/python-3-3776ab?style=flat-square&logo=python&logoColor=white">
  <a href="LICENSE"><img alt="MIT license" src="https://img.shields.io/badge/license-MIT-blue?style=flat-square"></a>
</p>

<p align="center">
  Built by <b>Saeed Foroutan</b> at "AI Agents for the Rest of Us"<br>
  AI Tinkerers Prague · Apify office · 13 November 2026
</p>

---

## Try it

Open **[the live app](https://flat-hunter-wfx0.onrender.com/)**, fill in your budget, school or workplace and what matters
to you, then press **Find flats**. A full run takes about a minute. If the page is slow to open at first, the server is
waking up; give it a moment.

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

## Run it locally

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
