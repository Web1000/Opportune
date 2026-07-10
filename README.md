# Opportune

AI-powered resume & opportunity matcher. Built with Flask + SQLite, running on
free API tiers — no paid LLM key required.

- **LLM inference:** [Groq](https://console.groq.com) (free, fast, OpenAI-compatible);
  any OpenAI-compatible endpoint works via `LLM_BASE_URL` / `LLM_MODEL`
- **Live web search:** [Tavily](https://app.tavily.com), with
  [Hack Club Search](https://search.hackclub.com) as a fallback (both optional)

## Quick start

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then add your GROQ_API_KEY (and optionally search/Adzuna keys)
python app.py          # tables are created and opportunities are seeded automatically on startup
```

Server runs on http://localhost:5000

Get a free Groq key at https://console.groq.com. The default models are
`llama-3.3-70b-versatile` (drafting) and `llama-3.1-8b-instant` (scoring); override
them with `LLM_MODEL` / `LLM_SCORING_MODEL`, or point at another provider entirely
with `LLM_BASE_URL`.

You can also run with **no keys at all** by setting `MOCK_MODE=true` — every
service then returns cached demo responses, useful for a stable showcase demo.

## Deploying free on Render

This repo ships a `render.yaml` blueprint, so deployment is mostly automatic.

1. Push this repo to GitHub.
2. New → **Blueprint** on [Render](https://render.com) and point it at the repo;
   it reads `render.yaml` (free web service, `gunicorn app:app`, and the
   `render-build.sh` build step that installs deps and the Tectonic LaTeX engine
   used for PDF generation).
3. When prompted, set the secret environment variables: `GROQ_API_KEY`
   (required), `TAVILY_API_KEY` / `HACKCLUB_SEARCH_API_KEY` (optional, for live
   search), `ADZUNA_APP_ID` / `ADZUNA_APP_KEY` (optional).
4. Deploy. Tables are created and opportunities are seeded automatically on
   startup. Add a Render Postgres if you want data to persist; otherwise it
   falls back to (ephemeral) SQLite.

Render's free tier sleeps after inactivity (~50s cold start) — fine for a demo.

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Sanity check |
| POST | `/upload-resume` | Upload PDF, get structured profile |
| POST | `/build-profile-from-form` | Manual profile entry fallback |
| POST | `/match-opportunities` | Get top 5 matching opportunities |
| POST | `/generate-application` | Generate tailored resume + cover letter |
