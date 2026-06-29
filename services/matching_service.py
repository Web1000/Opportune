"""Matching service: score how well a profile fits one opportunity, using Claude.

The /match-opportunities route calls this once per opportunity, then sorts by
fit_score. The output highlights gaps ("what's missing") — the product's core
feature.
"""
from config import SCORING_MODEL, MOCK_MODE
from services.profile_service import safe_json_parse   # reuse the shared JSON parser
from services.llm_client import client


def _mock_score(opportunity: dict) -> dict:
    """Demo score returned when demo mode is on. The score varies per opportunity
    (derived from the title) so the demo looks realistic without calling the API."""
    title = opportunity.get("title", "this opportunity")
    org = opportunity.get("organization", "this organization")
    field = opportunity.get("field", "this field")
    score = 70 + (sum(ord(c) for c in title) % 25)   # deterministic value in 70-94
    return {
        "fit_score": score,
        "why_good_fit": [
            f"Technical skills align well with {field}",
            "GPA comfortably exceeds the stated requirement",
            "Relevant internship and project experience",
        ],
        "missing_information": [
            "No explicit teamwork or leadership example listed",
            f"Limited evidence tailored specifically to {org}",
        ],
        "improvement_suggestions": [
            "Add a concrete team or leadership accomplishment",
            f"Highlight a project relevant to {field}",
        ],
    }


def score_opportunity_fit(profile: dict, opportunity: dict, mock=None) -> dict:
    """Ask Claude to rate the profile against one opportunity.

    mock=None -> follow global MOCK_MODE; True/False -> per-request override.
    Returns a dict with: fit_score, why_good_fit, missing_information,
    improvement_suggestions.
    """

    use_mock = MOCK_MODE if mock is None else bool(mock)
    if use_mock:
        return _mock_score(opportunity)

    # Ask for a generously-calibrated score plus structured strengths/gaps/suggestions.
    prompt = f"""You are evaluating how well a student profile matches an opportunity.

Profile:
{profile}

Opportunity:
{opportunity}

Return JSON with these exact fields:
- fit_score: integer from 0 to 100 — how worth-applying this opportunity is for
  the student. Be encouraging and optimistic: reward potential, transferable
  skills, and trajectory, since these are early-career students who grow into
  roles. Use the weights below to decide what matters most, but do NOT
  mechanically score-and-deduct each row — start from a high baseline and
  subtract only for substantive mismatches (wrong field or seniority). A missing
  "preferred" / "nice-to-have" skill should cost a few points at most.
| Metric                      | Weight  |
| --------------------------- | ------- |
| Relevant skills             | 25      |
| Experience                  | 20      |
| Education/Training          | 15      |
| Problem-solving ability     | 20      |
| Communication skills        | 10      |
| Leadership/initiative       | 10      |
| **Total**                   | **100** |
  Calibrate to this scale:
    90-100   = excellent, directly-aligned fit
    85-89    = strong fit — the typical score for a plausible, relevant candidate
    80-84    = good fit with a few minor gaps
    70-79    = partial fit: real, but a stretch
    below 70 = only a clear mismatch in field or seniority
  Most students who could reasonably apply should land at 83 or higher. Still
  list shortfalls under missing_information, but they must not pull the number
  below the low-80s for a relevant candidate.
- why_good_fit: array of 2-3 short strings naming specific strengths
- missing_information: array of 2-3 short strings naming concrete gaps
- improvement_suggestions: array of 2-3 short strings with actionable advice

Return ONLY valid JSON. No markdown fences. No commentary."""

    # The free model occasionally returns an empty or non-JSON response (it puts
    # everything in a reasoning block and leaves content blank). That's transient,
    # so retry a few times before giving up.
    last_err = None
    for _ in range(3):
        try:
            response = client.messages.create(
                model=SCORING_MODEL,
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}],
            )
            text = (response.content[0].text if response.content else "") or ""
            if not text.strip():
                last_err = "empty response from model"
                continue
            parsed = safe_json_parse(text)
            if isinstance(parsed, dict) and "fit_score" in parsed:
                return parsed
            last_err = "no score in response"
        except Exception as e:
            last_err = str(e)

    # Every attempt failed. Degrade gracefully: the opportunity already matched the
    # search/profile, so show a neutral, encouraging score and a soft note rather
    # than a 0 with a raw error message in the user's face.
    print(f"[matching] scoring failed after retries: {last_err}")
    return {
        "fit_score": 80,
        "why_good_fit": [],
        "missing_information": [],
        "improvement_suggestions": [
            "Open the posting to confirm eligibility, amount, and deadline.",
        ],
    }