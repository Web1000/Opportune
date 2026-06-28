"""Application configuration.

Loads secrets from the .env file and defines the constants used across the app.
Nothing secret is hardcoded here — keys are read from .env at runtime.

This build runs entirely on Hack Club's FREE APIs so it costs nothing to host:
  * LLM inference  -> Hack Club AI   (https://ai.hackclub.com, OpenAI-compatible)
  * Live web search-> Hack Club Search (https://search.hackclub.com)
Both are free for Hack Clubbers — no Anthropic / OpenAI billing involved.
"""
import os
from dotenv import load_dotenv

# Load .env from THIS file's own directory, overriding any pre-existing
# (possibly empty) values already exported in the environment.
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"), override=True)

# ---------------------------------------------------------------------------
# Hack Club AI (LLM inference) — free, OpenAI-compatible chat completions.
# Get a key at https://ai.hackclub.com/dashboard
# ---------------------------------------------------------------------------
HACKCLUB_AI_API_KEY = os.getenv("HACKCLUB_AI_API_KEY", "")
HACKCLUB_AI_BASE_URL = os.getenv("HACKCLUB_AI_BASE_URL", "https://ai.hackclub.com/proxy/v1")

# Hack Club Search (live web search used to ground job/scholarship results).
# Get a key at https://search.hackclub.com . Optional: if unset, live web
# search is skipped (jobs still work when Adzuna is configured).
HACKCLUB_SEARCH_API_KEY = os.getenv("HACKCLUB_SEARCH_API_KEY", "")
HACKCLUB_SEARCH_URL = os.getenv(
    "HACKCLUB_SEARCH_URL", "https://search.hackclub.com/res/v1/web/search"
)

# Adzuna job-search API credentials (developer.adzuna.com). When both are set,
# live JOB search uses Adzuna's real Canadian/US listings — with canonical apply
# URLs — instead of the Hack Club Search fallback. Empty when not configured.
ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID")
ADZUNA_APP_KEY = os.getenv("ADZUNA_APP_KEY")

# Models served by Hack Club AI. Both default to the documented qwen3-32b model,
# which is reliably available. You can point these at any model your dashboard
# lists (e.g. a Gemini / GPT / Kimi id) via env vars without code changes.
#   MAIN  -> quality-sensitive work: resume parsing, live search, drafting.
#   SCORING -> lightweight per-opportunity fit scoring (kept cheap/fast).
CLAUDE_MODEL = os.getenv("HACKCLUB_MODEL", "qwen/qwen3-32b")
SCORING_MODEL = os.getenv("HACKCLUB_SCORING_MODEL", "qwen/qwen3-32b")

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
