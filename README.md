# Opportune

AI-powered resume & opportunity matcher. Built with Flask + SQLite, running
entirely on **Hack Club's free APIs** — no paid LLM key required.

- **LLM inference:** [Hack Club AI](https://ai.hackclub.com) (free, OpenAI-compatible)
- **Live web search:** [Hack Club Search](https://search.hackclub.com) (free; optional)

## Quick start

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then add your HACKCLUB_AI_API_KEY (and optionally search/Adzuna keys)
python app.py          # tables are created and opportunities are seeded automatically on startup
```

Server runs on http://localhost:5000

Get a free Hack Club AI key at https://ai.hackclub.com/dashboard. The default model
is `qwen/qwen3-32b`; override it with `HACKCLUB_MODEL` / `HACKCLUB_SCORING_MODEL`
to any model your dashboard lists.

You can also run with **no keys at all** by setting `MOCK_MODE=true` — every
service then returns cached demo responses, useful for a stable showcase demo.

## Deploying free on Render

This repo ships a `render.yaml` blueprint, so deployment is mostly automatic.

1. Push this repo to GitHub.
2. New → **Blueprint** on [Render](https://render.com) and point it at the repo;
   it reads `render.yaml` (free web service, `gunicorn app:app`, and the
   `render-build.sh` build step that installs deps and the Tectonic LaTeX engine
   used for PDF generation).
3. When prompted, set the secret environment variables: `HACKCLUB_AI_API_KEY`
   (required), `HACKCLUB_SEARCH_API_KEY` (optional), `ADZUNA_APP_ID` /
   `ADZUNA_APP_KEY` (optional).
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
