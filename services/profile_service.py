"""Profile service: turn raw resume text into a structured JSON profile via Claude.

Also defines safe_json_parse — the shared helper that every service uses to
robustly parse Claude's JSON output.
"""
import json
import re
from config import CLAUDE_MODEL, MOCK_MODE
from services.llm_client import client



def safe_json_parse(text: str) -> dict:
    """Parse a JSON object out of Claude's reply, tolerating common quirks.

    Claude sometimes wraps JSON in ```json fences or adds a sentence around it,
    which would break json.loads(). We strip the fences, grab the first {...}
    block, then parse it.
    """
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)    # remove a leading ```json fence
    text = re.sub(r"\s*```$", "", text)              # remove a trailing ``` fence
    match = re.search(r"\{.*\}", text, re.DOTALL)    # find the JSON object itself
    if match:
        text = match.group(0)
    return json.loads(text)


# Profile returned when demo mode is on, so the app works without calling the API.
_MOCK_PROFILE = {
    "name": "Demo Student",
    "email": "demo.student@uwaterloo.ca",
    "phone": "(519) 555-0199",
    "location": "Waterloo, ON",
    "links": {"linkedin": "linkedin.com/in/demostudent", "github": "github.com/demostudent"},
    "education": [{"school": "University of Waterloo", "degree": "BASc, Computer Science", "gpa": "3.8", "year": "Expected 2027", "location": "Waterloo, ON"}],
    "skills": {"languages": ["Python", "Java", "SQL"], "tools": ["React", "Flask", "Git"], "web": ["HTML/CSS", "REST APIs"]},
    "interests": ["fintech", "machine learning", "web development"],
    "experiences": [
        {"category": "Work", "title": "Software Developer Intern", "organization": "FinTech Startup", "location": "Toronto, ON", "duration": "Summer 2025", "description": "Built internal dashboards with React and Flask; wrote SQL queries and automated reports."},
        {"category": "Leadership", "title": "Teaching Assistant", "organization": "University of Waterloo", "location": "Waterloo, ON", "duration": "2024-2025", "description": "Led weekly tutorials for 40+ first-year students."},
    ],
    "projects": [{"name": "Resume Matcher", "technologies": ["Python", "Flask", "React"], "description": "A web app that matches resumes to opportunities using the Claude API."}],
    "awards": ["Dean's Honour List (2024)"],
}


def build_structured_profile(resume_text: str, mock=None) -> dict:
    """Use Claude to extract the resume text into a fixed-schema JSON profile.

    mock=None  -> follow the global MOCK_MODE setting
    mock=True/False -> override per request (used by the UI's Demo toggle)
    """
    use_mock = MOCK_MODE if mock is None else bool(mock)
    if use_mock:
        return dict(_MOCK_PROFILE)              # return demo data, skip the API call
    speed = "fast"
    # The prompt lists every field explicitly and ends with the strict
    # "JSON only" instruction so the output is easy to parse.
    prompt = f"""Extract this resume into structured JSON with these exact fields:
- name (string)
- email (string or null)
- phone (string or null)
- location (string or null)
- links (object with: linkedin, github — strings or null)
- education (array of objects with: school, degree, gpa, year, location)
- skills (object with: languages [array of strings], tools [array of strings], web [array of strings])
- experiences (array of objects with: category [one of "Work","Leadership","Research","Volunteer","Activity"], title, organization, location, duration, description)
- projects (array of objects with: name, technologies [array of strings], description)
- awards (array of strings)
- interests (array of strings)

Resume:
{resume_text}

Return ONLY valid JSON. No markdown fences. No commentary."""

    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            # A full resume's structured JSON routinely exceeds 2000 tokens; when
            # the response is truncated mid-object the JSON won't parse and we'd
            # silently return an empty profile (so the form fills in nothing).
            max_tokens=8000,
            messages=[{"role": "user", "content": prompt}],
        )
        return safe_json_parse(response.content[0].text)
    except Exception as e:
        # Never crash the request: return a valid (empty) profile plus an error note.
        return {
            "name": "",
            "email": None,
            "phone": None,
            "location": None,
            "links": {"linkedin": None, "github": None},
            "education": [],
            "skills": {"languages": [], "tools": [], "web": []},
            "experiences": [],
            "projects": [],
            "awards": [],
            "interests": [],
            "error": f"Profile extraction error: {str(e)}",
        }
