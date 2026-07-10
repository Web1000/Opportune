"""Application configuration.

Loads secrets from the .env file and defines the constants used across the app.
Nothing secret is hardcoded here — keys are read from .env at runtime.

This build runs on free API tiers so it costs nothing to host:
  * LLM inference  -> Groq (https://console.groq.com, OpenAI-compatible); any
                      OpenAI-compatible endpoint works via LLM_BASE_URL / LLM_MODEL.
  * Live web search-> Tavily (https://app.tavily.com), with Hack Club Search
                      (https://search.hackclub.com) as a fallback.
"""
import os
from dotenv import load_dotenv

# Load .env from THIS file's own directory, overriding any pre-existing
# (possibly empty) values already exported in the environment.
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"), override=True)

# ---------------------------------------------------------------------------
# LLM inference — any OpenAI-compatible chat-completions endpoint.
# Defaults to Groq (free tier, very fast, reliable JSON). To use another
# provider, just set LLM_BASE_URL / LLM_MODEL. The older HACKCLUB_AI_* names
# are still honored as a fallback so existing deployments keep working.
#   Groq:   https://api.groq.com/openai/v1   (key: https://console.groq.com)
# ---------------------------------------------------------------------------
LLM_API_KEY = (
    os.getenv("LLM_API_KEY")
    or os.getenv("GROQ_API_KEY")
    or os.getenv("HACKCLUB_AI_API_KEY", "")
)
LLM_BASE_URL = (
    os.getenv("LLM_BASE_URL")
    or os.getenv("HACKCLUB_AI_BASE_URL")
    or "https://api.groq.com/openai/v1"
)

# Hack Club Search (live web search used to ground job/scholarship results).
# Get a key at https://search.hackclub.com . Optional: if unset, live web
# search is skipped (jobs still work when Adzuna is configured).
HACKCLUB_SEARCH_API_KEY = os.getenv("HACKCLUB_SEARCH_API_KEY", "")
HACKCLUB_SEARCH_URL = os.getenv(
    "HACKCLUB_SEARCH_URL", "https://search.hackclub.com/res/v1/web/search"
)

# Tavily search (tavily.com) — preferred live-search backend when configured, as
# it is reliable and supports server-side domain filtering. When TAVILY_API_KEY
# is set, web_search() uses Tavily and falls back to Hack Club Search only if the
# Tavily request fails. Get a free key (1k searches/mo) at https://app.tavily.com .
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
TAVILY_SEARCH_URL = os.getenv("TAVILY_SEARCH_URL", "https://api.tavily.com/search")

# Adzuna job-search API credentials (developer.adzuna.com). When both are set,
# live JOB search uses Adzuna's real Canadian/US listings — with canonical apply
# URLs — instead of the Hack Club Search fallback. Empty when not configured.
ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID")
ADZUNA_APP_KEY = os.getenv("ADZUNA_APP_KEY")

# Which model handles which job. Defaults are Groq models chosen so the app
# stays fast: a capable 70B for drafting, and a small "instant" model for the
# per-opportunity scoring that runs many times per search. Override via env
# without code changes to point at any model your provider lists.
#   MAIN  -> quality-sensitive work: resume parsing, live search, drafting.
#   SCORING -> lightweight per-opportunity fit scoring (kept cheap/fast).
LLM_MODEL = os.getenv("LLM_MODEL") or os.getenv("HACKCLUB_MODEL") or "llama-3.3-70b-versatile"
LLM_SCORING_MODEL = (
    os.getenv("LLM_SCORING_MODEL")
    or os.getenv("HACKCLUB_SCORING_MODEL")
    or "llama-3.1-8b-instant"
)

# Folder where uploaded resume PDFs are temporarily saved.
UPLOAD_FOLDER = "uploads"

# Database URL. In the cloud (Render etc.) the platform provides DATABASE_URL,
# typically pointing at a managed Postgres. Locally we fall back to SQLite, which
# Flask-SQLAlchemy 3.x places in instance/app.db (a single file database).
# Render's Postgres URLs use the legacy "postgres://" scheme; SQLAlchemy 2.x only
# accepts "postgresql://", so we rewrite the prefix when needed.
_db_url = os.getenv("DATABASE_URL", "sqlite:///app.db")
if _db_url.startswith("postgres://"):
    _db_url = _db_url.replace("postgres://", "postgresql://", 1)
DATABASE_URI = _db_url

# Cap the number of matches returned by /match-opportunities.
MAX_TOP_RESULTS = 5

# Project root, used to locate bundled binaries and templates.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Path to the Tectonic LaTeX engine used to compile the tailored resume PDF.
import platform as _platform
_bin_name = "tectonic.exe" if _platform.system() == "Windows" else "tectonic"
_bundled_tectonic = os.path.join(BASE_DIR, "bin", _bin_name)
TECTONIC_BIN = os.getenv("TECTONIC_BIN") or (
    _bundled_tectonic if os.path.exists(_bundled_tectonic) else "tectonic"
)

# Demo mode flag. When truthy, the service functions return cached demo
# responses instead of calling the API — this protects a live demo from API
# outages, rate limits, and (here) keeps it working with no keys configured.
MOCK_MODE = os.getenv("MOCK_MODE", "").strip().lower() in ("1", "true", "yes", "on")
