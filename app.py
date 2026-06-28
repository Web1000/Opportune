"""Flask entry point.

Serves the single-page web UI at "/" and exposes the JSON API the UI calls:
upload a resume, build a profile, match against opportunities, and generate
application materials. Each AI step lives in its own module under services/.

Email-only "login" (no password — hackathon-grade, designed to be replaced with
real auth later):
- POST /login finds-or-creates a User by email and returns their latest profile
  (if any), so the browser can auto-fill on return visits.
- /upload-resume and /build-profile-from-form accept an optional `user_id` to
  link the new profile to a user.
- GET /user/<id>/profile returns that user's latest stored profile.

Profiles are persisted. `/upload-resume` and `/build-profile-from-form` save the
structured profile to the `profile` table and return a `profile_id`. Matching
and generation accept either an inline `profile` (the live one from the UI,
which respects edits) or a `profile_id` to look up the stored copy. When both
are sent, the inline `profile` wins.
"""
import os
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from werkzeug.utils import secure_filename
from config import DATABASE_URI, UPLOAD_FOLDER, MAX_TOP_RESULTS, MOCK_MODE
from database import db
from models import Opportunity, Profile, User, TailoredResume
from services.pdf_service import extract_text_from_pdf
from services.profile_service import build_structured_profile
from services.matching_service import score_opportunity_fit
from services.application_service import generate_application, markdown_to_resume_data
from services.opportunity_search_service import search_live_opportunities
from services.latex_service import compile_resume_pdf, LatexCompileError

app = Flask(__name__)
CORS(app)                                              # allow the frontend to call the API
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URI
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

db.init_app(app)                                       # bind SQLAlchemy to this app
os.makedirs(UPLOAD_FOLDER, exist_ok=True)              # ensure the uploads folder exists


def _ensure_profile_columns():
    """Add columns introduced after the DB was first created.

    `db.create_all()` only creates missing *tables*, never adds columns to an
    existing one, so a database created before `source_filename` existed would
    be missing it. This adds the column in place (a no-op once present). Works
    on both SQLite and Postgres; ADD COLUMN there is a cheap metadata change.
    """
    from sqlalchemy import inspect, text
    cols = {c["name"] for c in inspect(db.engine).get_columns("profile")}
    if "source_filename" not in cols:
        with db.engine.begin() as conn:
            conn.execute(text("ALTER TABLE profile ADD COLUMN source_filename VARCHAR(255)"))


def _ensure_tailored_resume_columns():
    """Add columns introduced after the tailored_resume table was first created.

    `db.create_all()` creates the table fresh (with every column) when it's
    missing, but never adds columns to an existing one — so a table created
    before match_key/updated_at existed would lack them. This adds them in place
    (a no-op once present, and skipped entirely if the table doesn't exist yet).
    """
    from sqlalchemy import inspect, text
    insp = inspect(db.engine)
    if not insp.has_table("tailored_resume"):
        return
    cols = {c["name"] for c in insp.get_columns("tailored_resume")}
    with db.engine.begin() as conn:
        if "match_key" not in cols:
            conn.execute(text("ALTER TABLE tailored_resume ADD COLUMN match_key VARCHAR(512)"))
        if "updated_at" not in cols:
            conn.execute(text("ALTER TABLE tailored_resume ADD COLUMN updated_at DATETIME"))


def _initialize_db():
    """Create tables and seed the opportunity list if it's empty.

    Runs on module import so it works under both `python app.py` (local dev)
    and `gunicorn app:app` (how Render starts the server). Idempotent — safe
    to run on every startup; re-seeding is skipped if data already exists.
    """
    with app.app_context():
        db.create_all()
        _ensure_profile_columns()
        _ensure_tailored_resume_columns()
        from data.seed_opportunities import OPPORTUNITIES
        if Opportunity.query.count() == 0:
            for opp in OPPORTUNITIES:
                db.session.add(Opportunity(**opp))
            db.session.commit()


_initialize_db()


def _parse_bool(value):
    """Parse a truthy/falsy demo-mode flag; None when absent."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _parse_user_id(value):
    """Parse a user_id from JSON or form data; None if absent or invalid."""
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _save_profile(structured_profile: dict, raw_resume_text: str = "", user_id=None, source_filename=None) -> int:
    """Insert a profile row (optionally linked to a user) and return its new id."""
    row = Profile(
        user_id=user_id,
        raw_resume_text=raw_resume_text or "",
        structured_profile=structured_profile,
        source_filename=source_filename,
    )
    db.session.add(row)
    db.session.commit()
    return row.id


def _latest_profile_for(user_id):
    """Return the most recent Profile row for a user (or None)."""
    return (
        Profile.query.filter_by(user_id=user_id)
        .order_by(Profile.created_at.desc())
        .first()
    )


def _resolve_profile(data: dict):
    """Pull a profile dict out of a request body.

    Accepts either an inline `profile` object or a `profile_id` to look up.
    When both are present the inline profile wins (so live UI edits take effect).
    Returns (profile_dict, error_tuple) where error_tuple is (message, status_code).
    """
    profile = data.get("profile")
    if profile:
        return profile, None
    pid = data.get("profile_id")
    if pid is not None:
        row = Profile.query.get(int(pid))
        if not row:
            return None, (f"Profile {pid} not found", 404)
        return row.structured_profile, None
    return None, ("No profile or profile_id provided", 400)


# How many opportunities to score concurrently. Each score is an independent
# Claude call, and the SDK releases the GIL while waiting on the network, so a
# thread pool turns a serial chain of calls into near-parallel ones. Capped so a
# long opportunity list doesn't fire dozens of calls at once (which would risk
# rate limits); the SDK still retries any 429s with backoff.
_SCORING_CONCURRENCY = 8


def _score_to_result(profile: dict, opp: dict, mock, live: bool = False) -> dict:
    """Score one opportunity against the profile and shape the response row.

    Isolated per opportunity so (a) one scoring failure can't blank the whole
    list, and (b) callers can score many opportunities concurrently via a thread
    pool instead of one slow Claude call after another.
    """
    try:
        score = score_opportunity_fit(profile, opp, mock=mock)
    except Exception as e:
        # One opportunity failing shouldn't fail the whole request.
        score = {
            "fit_score": 0,
            "why_good_fit": [],
            "missing_information": [f"Scoring error: {str(e)}"],
            "improvement_suggestions": [],
        }
    row = {
        "opportunity": opp,
        "fit_score": score.get("fit_score", 0),
        "why_good_fit": score.get("why_good_fit", []),
        "missing_information": score.get("missing_information", []),
        "improvement_suggestions": score.get("improvement_suggestions", []),
    }
    if live:
        row["live"] = True
    return row


@app.route("/", methods=["GET"])
def index():
    """Serve the single-page web UI (static/index.html)."""
    return app.send_static_file("index.html")


@app.route("/health", methods=["GET"])
def health():
    """Simple liveness check used to confirm the server is up."""
    return jsonify({"status": "ok"})


@app.route("/config", methods=["GET"])
def get_config():
    """Expose runtime defaults the frontend needs (the demo-mode default)."""
    return jsonify({"mock_mode": MOCK_MODE})


@app.route("/login", methods=["POST"])
def login():
    """Email-only auth: sign-in (strict), sign-up (strict), or legacy find-or-create.

    Body: {
        "email": "alex@example.com",
        "name": "Alex" (optional, used on sign-up),
        "mode": "signin" | "signup" | None (optional; None = legacy find-or-create)
    }

    Behaviour by `mode`:
      - "signin": user MUST already exist. If not, returns 404 "No account..."
      - "signup": user MUST NOT already exist. If they do, returns 409 "Email already..."
      - None:     legacy behaviour — finds the user, or creates one if missing.

    Returns on success: { user_id, email, name, profile_id (or null), structured_profile (or null) }
    """
    data = request.json or {}
    email = (data.get("email") or "").strip().lower()
    name = (data.get("name") or "").strip() or None
    mode = (data.get("mode") or "").strip().lower() or None
    if not email or "@" not in email:
        return jsonify({"error": "Please enter a valid email."}), 400
    if mode and mode not in ("signin", "signup"):
        return jsonify({"error": "Invalid mode (expected 'signin' or 'signup')."}), 400

    user = User.query.filter_by(email=email).first()

    if mode == "signin":
        if not user:
            # Strict sign-in: don't create the account silently.
            return jsonify({"error": "No account with that email. Try Sign Up instead."}), 404
    elif mode == "signup":
        if user:
            # Strict sign-up: don't quietly sign them in.
            return jsonify({"error": "That email is already registered. Try Sign In instead."}), 409
        user = User(email=email, name=name or email.split("@")[0])
        db.session.add(user)
        db.session.commit()
    else:
        # Legacy / no-mode: find or create. Keeps older callers working.
        if not user:
            user = User(email=email, name=name or email.split("@")[0])
            db.session.add(user)
            db.session.commit()

    latest = _latest_profile_for(user.id)
    return jsonify({
        "user_id": user.id,
        "email": user.email,
        "name": user.name,
        "profile_id": latest.id if latest else None,
        "structured_profile": latest.structured_profile if latest else None,
    })


@app.route("/user/<int:user_id>", methods=["PATCH"])
def update_user(user_id):
    """Update a user's name and/or email. Email stays unique across accounts."""
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    data = request.json or {}
    if "name" in data:
        name = (data.get("name") or "").strip()
        if name:
            user.name = name
    if "email" in data:
        email = (data.get("email") or "").strip().lower()
        if not email or "@" not in email:
            return jsonify({"error": "Please enter a valid email."}), 400
        clash = User.query.filter_by(email=email).first()
        if clash and clash.id != user.id:
            return jsonify({"error": "That email is already in use by another account."}), 409
        user.email = email
    db.session.commit()
    return jsonify({"user_id": user.id, "email": user.email, "name": user.name})


@app.route("/user/<int:user_id>/profile", methods=["GET"])
def get_user_profile(user_id):
    """Return the latest stored profile for a given user."""
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    latest = _latest_profile_for(user_id)
    if not latest:
        return jsonify({"error": "No profile yet for this user"}), 404
    return jsonify({
        "user_id": user.id,
        "email": user.email,
        "profile_id": latest.id,
        "structured_profile": latest.structured_profile,
        "created_at": latest.created_at.isoformat() if latest.created_at else None,
    })


@app.route("/profile/<int:profile_id>", methods=["GET"])
def get_profile(profile_id):
    """Look up a stored profile by id (useful for teammates / debugging)."""
    row = Profile.query.get(profile_id)
    if not row:
        return jsonify({"error": "Profile not found"}), 404
    return jsonify({
        "profile_id": row.id,
        "structured_profile": row.structured_profile,
        "raw_text": row.raw_resume_text or "",
        "created_at": row.created_at.isoformat() if row.created_at else None,
    })


@app.route("/user/<int:user_id>/resumes", methods=["GET"])
def list_user_resumes(user_id):
    """List the résumés a user has uploaded, newest first.

    Only rows that came from an actual PDF upload are returned — form autosaves
    also create Profile rows, but they carry no source_filename / raw text, so
    they'd otherwise clutter the list with duplicates. (Saved applications live
    in their own list — see /user/<id>/applications.)
    """
    rows = (
        Profile.query.filter_by(user_id=user_id)
        .filter(Profile.source_filename.isnot(None))
        .order_by(Profile.created_at.desc())
        .all()
    )
    resumes = []
    for r in rows:
        sp = r.structured_profile or {}
        resumes.append({
            "profile_id": r.id,
            "filename": r.source_filename,
            "name": (sp.get("name") or "").strip() or r.source_filename or f"Résumé #{r.id}",
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })
    return jsonify({"resumes": resumes})


@app.route("/profile/<int:profile_id>", methods=["DELETE"])
def delete_profile(profile_id):
    """Delete a stored profile (used by the 'My resumes' delete button)."""
    row = Profile.query.get(profile_id)
    if not row:
        return jsonify({"error": "Profile not found"}), 404
    db.session.delete(row)
    db.session.commit()
    return jsonify({"deleted": profile_id})


def _application_summary(row):
    """List-view shape for one application card in 'My applications'."""
    stamp = row.updated_at or row.created_at
    return {
        "id": row.id,
        "match_key": row.match_key or "",
        "name": row.opportunity_name or f"Application #{row.id}",
        "has_resume": bool((row.tailored_resume or "").strip()),
        "has_cover": bool((row.cover_letter or "").strip()),
        "updated_at": stamp.isoformat() if stamp else None,
    }


@app.route("/save-application", methods=["POST"])
def save_application():
    """Create or update a saved application (résumé + cover letter) for one match.

    Upserts by (user_id, match_key) so saving the résumé or the cover letter
    again updates the SAME row instead of piling up duplicates. Only the fields
    present in the body are written, so "Save résumé" and "Save cover letter"
    can each persist just their own part.

    Body: { user_id, match_key, opportunity_name?, resume_data?, tailored_resume?, cover_letter? }
    Requires a signed-in user — guests have nowhere to persist applications.
    """
    data = request.json or {}
    user_id = _parse_user_id(data.get("user_id"))
    if not user_id:
        return jsonify({"error": "Sign in to save applications to your account."}), 401
    match_key = (data.get("match_key") or "").strip()[:512]
    if not match_key:
        return jsonify({"error": "Missing match_key"}), 400

    row = TailoredResume.query.filter_by(user_id=user_id, match_key=match_key).first()
    if row is None:
        row = TailoredResume(user_id=user_id, match_key=match_key)
        db.session.add(row)

    name = (data.get("opportunity_name") or "").strip()
    if name:
        row.opportunity_name = name[:255]
    # Only write the parts that were sent, so each save button touches just its own.
    if "tailored_resume" in data:
        row.tailored_resume = data.get("tailored_resume") or ""
    if "resume_data" in data:
        row.resume_data = data.get("resume_data") or {}
    if "cover_letter" in data:
        row.cover_letter = data.get("cover_letter") or ""

    db.session.commit()
    return jsonify(_application_summary(row))


@app.route("/user/<int:user_id>/applications", methods=["GET"])
def list_user_applications(user_id):
    """List a user's saved applications — one per match, most-recently-updated first."""
    rows = (
        TailoredResume.query.filter_by(user_id=user_id)
        .order_by(TailoredResume.updated_at.desc(), TailoredResume.created_at.desc())
        .all()
    )
    return jsonify({"applications": [_application_summary(r) for r in rows]})


@app.route("/application/<int:app_id>", methods=["GET"])
def get_application(app_id):
    """Return one saved application in full — used by the match detail view."""
    row = TailoredResume.query.get(app_id)
    if not row:
        return jsonify({"error": "Application not found"}), 404
    stamp = row.updated_at or row.created_at
    return jsonify({
        "id": row.id,
        "match_key": row.match_key or "",
        "opportunity_name": row.opportunity_name or "",
        "resume_data": row.resume_data or {},
        "tailored_resume": row.tailored_resume or "",
        "cover_letter": row.cover_letter or "",
        "updated_at": stamp.isoformat() if stamp else None,
    })


@app.route("/application/<int:app_id>", methods=["DELETE"])
def delete_application(app_id):
    """Delete a saved application (the 'My applications' delete button)."""
    row = TailoredResume.query.get(app_id)
    if not row:
        return jsonify({"error": "Application not found"}), 404
    db.session.delete(row)
    db.session.commit()
    return jsonify({"deleted": app_id})


@app.route("/upload-resume", methods=["POST"])
def upload_resume():
    """Accept a PDF, extract text, build a structured profile, and persist it.

    If `user_id` is provided as a form field, the new profile is linked to that user.
    Returns: { profile_id, user_id, raw_text, structured_profile }.
    """
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "Empty filename"}), 400
    filename = secure_filename(file.filename)         # sanitize the filename before saving
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(file_path)
    mock = _parse_bool(request.form.get("mock"))      # optional per-request demo flag
    user_id = _parse_user_id(request.form.get("user_id"))
    try:
        resume_text = extract_text_from_pdf(file_path)            # PDF -> text
        profile_json = build_structured_profile(resume_text, mock=mock)  # text -> JSON
    except Exception as e:
        return jsonify({"error": f"Failed to process resume: {str(e)}"}), 500
    # build_structured_profile never raises — on an API/parse failure it returns
    # an (otherwise-empty) profile carrying an `error` note. Surface that as a
    # real error instead of silently persisting a blank profile and reporting
    # "saved" to a user whose form then fills in nothing.
    if profile_json.get("error"):
        return jsonify({"error": f"Couldn't read that résumé: {profile_json['error']}"}), 502
    profile_id = _save_profile(
        profile_json, raw_resume_text=resume_text, user_id=user_id, source_filename=filename,
    )
    return jsonify({
        "profile_id": profile_id,
        "user_id": user_id,
        "raw_text": resume_text,
        "structured_profile": profile_json,
    })


@app.route("/build-profile-from-form", methods=["POST"])
def build_profile_from_form():
    """Persist a manually-entered profile and return its profile_id.

    The body is the profile dict itself; a top-level `user_id` (if present) is
    popped out before saving so it isn't stored inside the profile.
    """
    data = dict(request.json or {})
    if not data:
        return jsonify({"error": "No profile data"}), 400
    user_id = _parse_user_id(data.pop("user_id", None))
    profile_id = _save_profile(data, user_id=user_id)
    return jsonify({"profile_id": profile_id, "user_id": user_id, "structured_profile": data})


@app.route("/match-opportunities", methods=["POST"])
def match_opportunities():
    """Score the profile against every opportunity and return the top matches.

    Accepts either an inline `profile` object or a `profile_id` to look up.
    """
    data = request.json or {}
    mock = _parse_bool(data.get("mock"))              # optional per-request demo flag
    profile, err = _resolve_profile(data)
    if err:
        return jsonify({"error": err[0]}), err[1]

    opportunities = Opportunity.query.all()           # load all seeded opportunities
    # Materialize plain dicts in this thread first: the worker threads below must
    # not touch SQLAlchemy ORM objects (the session isn't thread-safe), only dicts.
    opp_dicts = [
        {
            "id": opp.id,
            "title": opp.title,
            "organization": opp.organization,
            "type": opp.type,
            "field": opp.field,
            "location": opp.location,
            "gpa_requirement": opp.gpa_requirement,
            "required_skills": opp.required_skills,
            "description": opp.description,
            "deadline": opp.deadline,
        }
        for opp in opportunities
    ]
    # Score every opportunity concurrently rather than one Claude call at a time.
    with ThreadPoolExecutor(max_workers=_SCORING_CONCURRENCY) as pool:
        results = list(pool.map(lambda od: _score_to_result(profile, od, mock), opp_dicts))

    results.sort(key=lambda x: x["fit_score"], reverse=True)   # best matches first
    return jsonify(results[:MAX_TOP_RESULTS])                  # return only the top N


@app.route("/search-live-opportunities", methods=["POST"])
def search_live_opportunities_endpoint():
    """Pull live opportunities from indeed.com / scholarshipscanada.com and score them.

    Returns {"results": [...scored matches...], "notice": {...} | null}. When the
    user searched a specific company and nothing was found at it, we fall back to
    a company-free search ("similar positions") and set a company_not_found notice
    so the frontend can tell the user. Each result mirrors the /match-opportunities
    shape so the same card component renders it."""
    data = request.json or {}
    profile = data.get("profile")
    sources = data.get("sources") or ["indeed", "scholarshipscanada"]
    filters = data.get("filters") or {}
    mock = _parse_bool(data.get("mock"))
    if not profile:
        return jsonify({"error": "No profile provided"}), 400

    company = (filters.get("company") or "").strip()
    errors = []
    live_opps = search_live_opportunities(profile, sources, mock=mock, filters=filters, errors=errors)

    notice = None
    # Searched a specific company but found nothing AT it: fall back to similar
    # positions (the same search minus the company) and flag it for the user.
    # Skipped when the search itself errored — we then can't tell "no jobs there"
    # apart from "search broke", and surface the error below instead.
    if company and not live_opps and not errors:
        fallback_filters = {k: v for k, v in filters.items() if k != "company"}
        live_opps = search_live_opportunities(profile, sources, mock=mock, filters=fallback_filters, errors=errors)
        notice = {"type": "company_not_found", "company": company}

    # If every source failed and nothing came back, surface the real reason
    # instead of letting the frontend show a misleading "no matches" message.
    if not live_opps and errors:
        return jsonify({"error": f"Live search is unavailable right now ({errors[0]}). "
                                 "Check your connection, or turn on Demo mode to try sample results."}), 502

    # Score the live opportunities concurrently (one Claude call each) instead of
    # sequentially — this scoring pass is the bulk of the live-search wait.
    with ThreadPoolExecutor(max_workers=_SCORING_CONCURRENCY) as pool:
        results = list(pool.map(lambda o: _score_to_result(profile, o, mock, live=True), live_opps))

    results.sort(key=lambda x: x["fit_score"], reverse=True)
    return jsonify({"results": results, "notice": notice})


@app.route("/generate-application", methods=["POST"])
def generate_application_endpoint():
    """Generate a tailored resume + cover letter for one chosen opportunity.

    Accepts either an inline `profile` or a `profile_id`, plus an `opportunity`.
    """
    data = request.json or {}
    opportunity = data.get("opportunity")
    mock = _parse_bool(data.get("mock"))              # optional per-request demo flag
    profile, err = _resolve_profile(data)
    if err:
        return jsonify({"error": err[0]}), err[1]
    if not opportunity:
        return jsonify({"error": "Missing opportunity"}), 400
    try:
        application = generate_application(profile, opportunity, mock=mock)
    except Exception as e:
        return jsonify({"error": f"Generation failed: {str(e)}"}), 500
    return jsonify(application)


@app.route("/render-resume-pdf", methods=["POST"])
def render_resume_pdf_endpoint():
    """Compile a résumé into a PDF using the fixed LaTeX layout.

    Prefers the edited résumé markdown (`tailored_resume`) when present, parsing
    it back into the structured shape the layout needs so the PDF reflects the
    user's on-screen edits — contacts are enriched from `resume_data` so links
    and icons survive. Falls back to `resume_data` directly otherwise.
    """
    data = request.json or {}
    resume_data = data.get("resume_data")
    tailored_resume = data.get("tailored_resume")
    if tailored_resume and tailored_resume.strip():
        resume_data = markdown_to_resume_data(tailored_resume, base=resume_data or {})
    if not resume_data:
        return jsonify({"error": "Missing resume_data"}), 400
    try:
        pdf_bytes = compile_resume_pdf(resume_data)
    except LatexCompileError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": f"PDF generation failed: {str(e)}"}), 500
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": 'inline; filename="resume.pdf"'},
    )


if __name__ == "__main__":
    # _initialize_db() already ran on import; just start the dev server.
    # Port is configurable via the PORT env var (defaults to 5000); we use 5001
    # locally because macOS AirPlay occupies port 5000.
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, port=port)
