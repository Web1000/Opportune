"""Database models (ORM tables) for the AI Opportunity Matcher.

Each class maps to one SQLite table. Currently only Opportunity is populated
(by the seed script); the User/Profile/MatchResult/GeneratedApplication tables
are defined for future persistence but the live endpoints return data directly.
"""
from datetime import datetime
from database import db


class User(db.Model):
    """A student user. Optional — the app works without creating users."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(120), unique=True)


class Profile(db.Model):
    """A parsed resume profile."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    raw_resume_text = db.Column(db.Text)        # full text extracted from the PDF
    structured_profile = db.Column(db.JSON)     # the structured fields as JSON
    source_filename = db.Column(db.String(255)) # original PDF filename (uploads only; null for form saves)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Opportunity(db.Model):
    """A scholarship or internship the user can be matched against (seeded data)."""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    organization = db.Column(db.String(200))
    type = db.Column(db.String(50))            # "Internship" | "Scholarship"
    field = db.Column(db.String(100))
    location = db.Column(db.String(100))
    gpa_requirement = db.Column(db.String(50))
    required_skills = db.Column(db.Text)
    description = db.Column(db.Text)
    deadline = db.Column(db.String(50))


class MatchResult(db.Model):
    """A scored match between a user and an opportunity (reserved for future use)."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    opportunity_id = db.Column(db.Integer, db.ForeignKey("opportunity.id"))
    fit_score = db.Column(db.Integer)
    explanation = db.Column(db.Text)
    missing_info = db.Column(db.Text)


class GeneratedApplication(db.Model):
    """A generated resume + cover letter for one opportunity (reserved for future use)."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    opportunity_id = db.Column(db.Integer, db.ForeignKey("opportunity.id"))
    tailored_resume = db.Column(db.Text)
    cover_letter = db.Column(db.Text)
    suggestions = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class TailoredResume(db.Model):
    """A saved application (tailored résumé + cover letter) for one opportunity.

    One row per (user, match): `match_key` identifies the opportunity, so saving
    the résumé or the cover letter again UPSERTS this row instead of piling up
    duplicates. Surfaced in the "My applications" tab, organized by match.

    Kept in its OWN table (not Profile) on purpose: the app loads a user's latest
    Profile as their master profile, so storing a job-specific application as a
    Profile would silently overwrite that. This table sidesteps it.
    """
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    match_key = db.Column(db.String(512))          # stable per-opportunity key (url / id / "role|org")
    opportunity_name = db.Column(db.String(255))   # e.g. "Software Engineering Intern — Shopify"
    resume_data = db.Column(db.JSON)               # structured résumé (drives the PDF)
    tailored_resume = db.Column(db.Text)           # edited résumé markdown shown in the preview
    cover_letter = db.Column(db.Text)              # edited cover letter
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
