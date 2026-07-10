"""Application service: generate a tailored resume + cover letter for one
opportunity, using the LLM. Also reports what info was missing from the profile.

The LLM returns the resume as STRUCTURED data (`resume_data`) — this is the single
source of truth. From it we derive:
  - a markdown `tailored_resume` for the editable on-screen preview, and
  - a LaTeX PDF (in latex_service) when the user clicks Download.
Keeping one structured source means the preview and the PDF can never disagree.
"""
import re
from config import LLM_MODEL, MOCK_MODE
from services.llm_client import client
from services.profile_service import safe_json_parse   # reuse the shared JSON parser



def _resume_data_to_markdown(rd: dict) -> str:
    """Render structured resume_data as the markdown shown in the preview.

    Mirrors the section order of the LaTeX layout (Experience, Projects,
    Education, Skills) so the preview matches the downloaded PDF. Inline
    **bold** and [text](url) authored by the LLM are passed through untouched —
    the frontend's mdToHtml renders them.
    """
    rd = rd or {}
    out = []
    name = rd.get("name") or "Your Name"
    out.append(f"# {name}")
    contacts = [c.get("text", "").strip() for c in (rd.get("contacts") or [])
                if isinstance(c, dict) and c.get("text", "").strip()]
    if contacts:
        out.append(" | ".join(contacts))

    def entries(*keys):
        for k in keys:
            v = rd.get(k)
            if isinstance(v, list) and v:
                return v
        return []

    def meta_line(*parts):
        joined = " · ".join(p for p in parts if p and str(p).strip())
        if joined:
            out.append(f"_{joined}_")

    def bullets(items):
        for b in (items or []):
            if str(b).strip():
                out.append(f"- {b}")

    exp = entries("experience", "experiences")
    if exp:
        out.append("\n## EXPERIENCE")
        for e in exp:
            head = e.get("title") or e.get("organization") or ""
            role = e.get("role") or ""
            out.append(f"### {head}" + (f" — {role}" if role else ""))
            meta_line(e.get("dates"), e.get("location"))
            bullets(e.get("bullets"))

    projects = entries("projects")
    if projects:
        out.append("\n## PROJECTS")
        for p in projects:
            out.append(f"### {p.get('name') or p.get('title') or ''}")
            meta_line(p.get("dates"))
            bullets(p.get("bullets"))

    edu = entries("education")
    if edu:
        out.append("\n## EDUCATION")
        for e in edu:
            head = e.get("school") or e.get("institution") or ""
            degree = e.get("degree") or ""
            out.append(f"### {head}" + (f" — {degree}" if degree else ""))
            meta_line(e.get("dates"), e.get("location"))
            bullets(e.get("bullets"))

    skills = entries("skills")
    if skills:
        out.append("\n## SKILLS")
        for s in skills:
            category = (s.get("category") or "").strip()
            items = s.get("items")
            if isinstance(items, list):
                items = ", ".join(str(x) for x in items if str(x).strip())
            items = (items or "").strip()
            if category or items:
                out.append(f"- **{category}:** {items}" if category else f"- {items}")

    return "\n".join(out).strip()


# Section headers recognized when parsing edited résumé markdown back to structure.
_SECTION_ALIASES = {
    "experience": "experience",
    "work experience": "experience",
    "projects": "projects",
    "education": "education",
    "skills": "skills",
    "technical skills": "skills",
}

# Matches a skills line like "**Languages:** Python, SQL".
_SKILL_RE = re.compile(r"\*\*(.+?):\*\*\s*(.*)$")


def markdown_to_resume_data(md: str, base: dict = None) -> dict:
    """Inverse of `_resume_data_to_markdown`: parse résumé markdown (as generated,
    and then possibly hand-edited) back into the structured resume_data the LaTeX
    renderer consumes — so a downloaded PDF reflects the user's on-screen edits.

    `base` is the original resume_data; contacts are enriched from it by matching
    on text, so icons/links survive when the contact line wasn't edited. Tolerant
    of edits — unrecognized lines are skipped rather than breaking the parse.
    """
    base = base or {}
    name = ""
    contacts_text = []
    section = None
    cur = None
    experience, projects, education, skills = [], [], [], []
    seen_name = False
    seen_section = False

    def set_meta(entry, text, kind):
        parts = [p.strip() for p in text.split("·") if p.strip()]
        if kind == "projects":
            entry["dates"] = text.strip()
        else:
            if parts:
                entry["dates"] = parts[0]
            if len(parts) > 1:
                entry["location"] = " · ".join(parts[1:])

    for raw in (md or "").split("\n"):
        s = raw.strip()
        if not s:
            continue
        if s.startswith("### "):
            head = s[4:].strip()
            if section == "experience":
                title, _, role = head.partition(" — ")
                cur = {"title": title.strip(), "role": role.strip(),
                       "dates": "", "location": "", "bullets": []}
                experience.append(cur)
            elif section == "education":
                school, _, degree = head.partition(" — ")
                cur = {"school": school.strip(), "degree": degree.strip(),
                       "dates": "", "location": "", "bullets": []}
                education.append(cur)
            elif section == "projects":
                cur = {"name": head, "dates": "", "bullets": []}
                projects.append(cur)
            else:
                cur = None
            continue
        if s.startswith("## "):
            seen_section = True
            section = _SECTION_ALIASES.get(s[3:].strip().lower())
            cur = None
            continue
        if s.startswith("# "):
            if not seen_name:
                name = s[2:].strip()
                seen_name = True
            continue
        if (cur is not None and section in ("experience", "education", "projects")
                and s.startswith("_") and s.endswith("_") and len(s) >= 2):
            set_meta(cur, s[1:-1].strip(), section)
            continue
        if s.startswith("- ") or s.startswith("* "):
            content = s[2:].strip()
            if section == "skills":
                m = _SKILL_RE.match(content)
                if m:
                    skills.append({"category": m.group(1).strip(), "items": m.group(2).strip()})
                elif content:
                    skills.append({"category": "", "items": content})
            elif cur is not None:
                cur["bullets"].append(content)
            continue
        # Plain line: the contact line sits right after the name, before sections.
        if seen_name and not seen_section and not contacts_text:
            contacts_text = [c.strip() for c in s.split("|") if c.strip()]

    # Rebuild contacts, reusing the original type/url when the text is unchanged.
    by_text = {}
    for c in (base.get("contacts") or []):
        if isinstance(c, dict) and (c.get("text") or "").strip():
            by_text[c["text"].strip()] = c
    contacts = []
    for t in contacts_text:
        src = by_text.get(t)
        if src:
            contacts.append({k: src[k] for k in ("type", "text", "url") if src.get(k)})
        else:
            contacts.append({"text": t})

    return {
        "name": name or base.get("name") or "",
        "contacts": contacts if contacts else (base.get("contacts") or []),
        "experience": experience,
        "projects": projects,
        "education": education,
        "skills": skills,
    }


def _mock_application(opportunity: dict) -> dict:
    """Demo resume + cover letter returned when demo mode is on (no API call)."""
    title = opportunity.get("title", "the role")
    org = opportunity.get("organization", "the organization")
    resume_data = {
        "name": "Demo Student",
        "contacts": [
            {"type": "email", "text": "demo.student@email.com"},
            {"type": "phone", "text": "555-555-5555"},
            {"type": "github", "text": "github.com/demo", "url": "https://github.com/demo"},
            {"type": "location", "text": "Toronto, ON"},
        ],
        "experience": [{
            "title": "FinTech Startup",
            "dates": "May 2024 -- Aug. 2024",
            "role": "Software Developer Intern",
            "location": "Remote",
            "bullets": [
                "Built internal dashboards with **React and Flask** used by 30+ staff",
                "Automated weekly SQL reporting, **saving ~5 hours/week**",
            ],
        }],
        "projects": [{
            "name": "Resume Matcher",
            "dates": "2024",
            "bullets": [
                "AI-powered opportunity matcher built with Python, Flask, and React",
            ],
        }],
        "education": [{
            "school": "University of Waterloo",
            "dates": "2023 -- 2027",
            "degree": "BASc, Computer Science",
            "location": "Waterloo, ON",
            "bullets": [
                "**Coursework**: Data Structures, Algorithms, Databases",
            ],
        }],
        "skills": [
            {"category": "Languages", "items": "Python, JavaScript, SQL"},
            {"category": "Tools", "items": "React, Flask, Git, PostgreSQL"},
        ],
    }
    return {
        "resume_data": resume_data,
        "tailored_resume": _resume_data_to_markdown(resume_data),
        "cover_letter": (
            f"Dear {org} Hiring Team,\n\n"
            f"I am excited to apply for the {title} position. My experience building "
            "full-stack web applications and working with data aligns closely with "
            "what this role requires.\n\n"
            "[Demo content shown because MOCK_MODE is enabled.]\n\n"
            "Sincerely,\nDemo Student"
        ),
        "missing_details_needed": [
            "Specific dates of availability",
            "Portfolio or GitHub link",
        ],
        "resume_improvement_suggestions": [
            "Quantify project impact with metrics",
            "Add a leadership or teamwork example",
        ],
    }


def generate_application(profile: dict, opportunity: dict, mock=None) -> dict:
    """Use the LLM to write a resume + cover letter tailored to one opportunity.

    mock=None -> follow global MOCK_MODE; True/False -> per-request override.
    Returns: resume_data (structured), tailored_resume (markdown derived from it),
    cover_letter, missing_details_needed, resume_improvement_suggestions.
    """
    use_mock = MOCK_MODE if mock is None else bool(mock)
    if use_mock:
        return _mock_application(opportunity)

    prompt = f"""You are writing a tailored job/scholarship application package.

Profile:
{profile}

Opportunity:
{opportunity}

Produce a resume as STRUCTURED data, reordered and reworded to emphasize what
matters most for THIS opportunity. Lead with the candidate's strongest, most
relevant material. Quantify impact where the profile supports it; never invent
facts, employers, dates, or numbers that aren't in the profile.

Inside any text field (bullets, skill items, etc.) you MAY use two markers:
  **bold**            for emphasis on key results/keywords
  [text](https://...) for links (GitHub, portfolio, publications)
Do NOT use any other markdown or LaTeX. Keep each bullet to one concise line.

Return JSON with these EXACT fields:
- resume_data: object with:
    - name: string
    - contacts: array of {{ "type": one of "phone"|"email"|"github"|"linkedin"|"website"|"location", "text": string (what's shown), "url": optional string }}. Include only contacts present in the profile.
    - experience: array of {{ "title": org/employer, "dates": e.g. "May 2024 -- Aug. 2024", "role": job title, "location": string, "bullets": array of strings }}
    - projects: array of {{ "name": string, "dates": string, "bullets": array of strings }}
    - education: array of {{ "school": string, "dates": string, "degree": string, "location": string, "bullets": array of strings (optional: coursework, honors) }}
    - skills: array of {{ "category": e.g. "Languages"|"Tools", "items": comma-separated string }}
  Omit any section that has no real content (use an empty array). Order entries within each section by relevance to this opportunity.
- cover_letter: string (250-350 words, specific to this opportunity and candidate, no generic filler)
- missing_details_needed: array of strings (information you had to guess or leave vague because the profile lacked it)
- resume_improvement_suggestions: array of strings (concrete things the student should add to their underlying profile)

Return ONLY valid JSON. No markdown fences. No commentary."""

    try:
        response = client.messages.create(
            model=LLM_MODEL,
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}],
        )
        result = safe_json_parse(response.content[0].text)
        result["resume_data"] = result.get("resume_data") or {}
        # Derive the preview markdown from the structured data so the on-screen
        # text and the downloadable PDF always agree.
        result["tailored_resume"] = _resume_data_to_markdown(result["resume_data"])
        result.setdefault("cover_letter", "")
        result.setdefault("missing_details_needed", [])
        result.setdefault("resume_improvement_suggestions", [])
        return result
    except Exception as e:
        # On failure, return empty docs with the error surfaced.
        return {
            "resume_data": {},
            "tailored_resume": "",
            "cover_letter": "",
            "missing_details_needed": [f"Generation error: {str(e)}"],
            "resume_improvement_suggestions": [],
        }
