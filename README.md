# AI Opportunity Matcher

Backend for the "I Hate Applications" project. Built with Flask + SQLite, running
entirely on **Hack Club's free APIs** — no paid LLM key required.

- **LLM inference:** [Hack Club AI](https://ai.hackclub.com) (free, OpenAI-compatible)
- **Live web search:** [Hack Club Search](https://search.hackclub.com) (free; optional)

## Quick start

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then add your HACKCLUB_AI_API_KEY (and optionally search/Adzuna keys)
python -m data.seed_opportunities
python app.py
```

Server runs on http://localhost:5000

Get a free Hack Club AI key at https://ai.hackclub.com/dashboard. The default model
is `qwen/qwen3-32b`; override it with `HACKCLUB_MODEL` / `HACKCLUB_SCORING_MODEL`
to any model your dashboard lists.

You can also run with **no keys at all** by setting `MOCK_MODE=true` — every
service then returns cached demo responses, useful for a stable showcase demo.

## Deploying free on Render

1. Push this repo to GitHub.
2. New → **Web Service** on [Render](https://render.com), point it at the repo.
3. Build command: `pip install -r requirements.txt`
4. Start command: `gunicorn app:app`
5. Add environment variables: `HACKCLUB_AI_API_KEY` (required),
   `HACKCLUB_SEARCH_API_KEY` (optional), `ADZUNA_APP_ID` / `ADZUNA_APP_KEY`
   (optional). Add a Render Postgres and it injects `DATABASE_URL` automatically;
   otherwise it falls back to SQLite.
6. After first deploy, run the seed once (Render Shell): `python -m data.seed_opportunities`.

Render's free tier sleeps after inactivity (~30s cold start) — fine for a demo.

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Sanity check |
| POST | `/upload-resume` | Upload PDF, get structured profile |
| POST | `/build-profile-from-form` | Manual profile entry fallback |
| POST | `/match-opportunities` | Get top 5 matching opportunities |
| POST | `/generate-application` | Generate tailored resume + cover letter |
