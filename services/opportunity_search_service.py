"""Opportunity search service: pull *live* opportunities off the web with Claude.

Uses Anthropic's built-in web_search tool to fetch current postings from
indeed.com (jobs/internships) and scholarshipscanada.com (scholarships),
then returns them in the same dict shape used everywhere else in the app
so they can be fed straight into score_opportunity_fit.

One Claude call per source. Each source is isolated — if Indeed fails,
ScholarshipsCanada still runs, and vice versa.
"""
import json
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit
import httpx
from config import CLAUDE_MODEL, MOCK_MODE, ADZUNA_APP_ID, ADZUNA_APP_KEY
from services.profile_service import safe_json_parse
from services.llm_client import client, web_search


# Per-source config: the sites to search, default type tag, and a short label.
# The "indeed" (jobs) source intentionally spans several boards + the major ATS
# platforms. Indeed alone is crawler-hostile and poorly indexed, so restricting
# to it starves the search; the boards and ATS/company sites ARE crawlable and
# carry direct posting URLs, which is how a search for a specific company (e.g.
# Questrade) actually surfaces its openings.
_SOURCES = {
    "indeed": {
        "domains": [
            "indeed.com", "ca.indeed.com",
            "linkedin.com", "glassdoor.ca", "glassdoor.com",
            "jobbank.gc.ca",
            "boards.greenhouse.io", "jobs.lever.co",
            "myworkdayjobs.com", "jobs.ashbyhq.com",
        ],
        "type": "Internship",
        "label": "job boards",
    },
    "scholarshipscanada": {
        "domains": ["scholarshipscanada.com"],
        "type": "Scholarship",
        "label": "ScholarshipsCanada",
    },
}


def _flatten_skills(skills) -> list:
    """Normalize skills into a flat list, tolerating both the structured shape
    ({languages, tools, web}) and the older flat-list shape."""
    if isinstance(skills, dict):
        out = []
        for group in skills.values():
            if isinstance(group, list):
                out.extend(group)
            elif group:
                out.append(group)
        return out
    if isinstance(skills, list):
        return skills
    return []


_CREDENTIAL = re.compile(
    r"^\s*(?:"
    r"b\.?\s?(?:a\.?sc|sc|eng|comm|ba|math|fa|hsc|ed|a|s)\b\.?|"
    r"m\.?\s?(?:a\.?sc|sc|eng|comm|ba|math|fa|a|s)\b\.?|"
    r"ph\.?\s?d\b\.?|m\.?d\b\.?|j\.?d\b\.?|"
    r"bachelor(?:'s)?(?:\s+of)?|master(?:'s)?(?:\s+of)?|associate(?:'s)?(?:\s+of)?|"
    r"honou?rs?|hons?|diploma(?:\s+in)?|degree(?:\s+in)?|undergraduate|graduate"
    r")\b[\s,]*", re.I)


def _study_field(degree) -> str:
    """Extract the field of study from a degree string, dropping the credential.

    Search backends return individual scholarship listings for "Computer Science
    scholarships" but mostly articles/landing pages for "BASc Computer Science
    scholarships" — so we strip leading credentials ("BASc", "Bachelor of", etc.)
    to get a clean field name for the query. Falls back to "student" if nothing
    is left (e.g. a bare "BBA").
    """
    s = re.sub(r"\(.*$", "", str(degree or "")).replace(",", " ").strip()
    prev = None
    while prev != s:                                   # strip stacked credentials
        prev = s
        s = _CREDENTIAL.sub("", s).strip()
    s = re.sub(r"^(of|in)\s+", "", s, flags=re.I)
    return re.sub(r"\s+", " ", s).strip() or "student"


def _build_query(profile: dict, source_key: str, filters: dict = None) -> str:
    """Turn the profile (and any user search filters) into a focused query.

    `filters` may carry `company` and `employment_type` ("Full-time"/"Part-time").
    When present they steer the query toward what the user typed in the search
    bar, so the live search reflects their criteria instead of inferring purely
    from the profile.
    """
    filters = filters or {}
    company = (filters.get("company") or "").strip()
    emp = (filters.get("employment_type") or "").strip()

    skills = _flatten_skills(profile.get("skills"))[:5]
    interests = profile.get("interests") or []
    edu = (profile.get("education") or [{}])[0]
    field = edu.get("degree") or "student"
    year = edu.get("year") or ""

    if source_key == "indeed":
        if company:
            # Company-specific search: look up THAT company's openings directly.
            # Do NOT narrow by student/skills/interests here — that makes real
            # postings vanish. Fit-scoring against the profile still happens later.
            parts = [emp.lower()] if emp else []
            parts.append(f"jobs at {company} in Canada")
            return " ".join(parts)
        # Profile-based discovery (no company named): match field/skills/interests.
        parts = [emp.lower()] if emp else []
        parts.append("jobs and internships in Canada")
        lead = " ".join(parts)
        return (
            f"{lead} for a {year} {field} student. "
            f"Skills: {', '.join(skills) if skills else 'general'}. "
            f"Interests: {', '.join(interests) if interests else 'tech'}."
        )
    # scholarshipscanada — keep this keyword-style and field-focused (not a full
    # sentence, no interests): search backends like Tavily surface individual
    # scholarship listings for "<field> scholarships Canada" but mostly articles
    # and landing pages for verbose, interest-laden queries. Fit against the full
    # profile (interests included) is handled later by the scoring step.
    base = f"{_study_field(field)} scholarships Canada"
    if company:
        base += f" {company}"
    return base


def _synth_mock_for_filters(source_key: str, filters: dict) -> list:
    """Build demo postings that match the user's filters.

    The fixed _mock_for_source data only covers a few sample employers, so a
    demo-mode search for any other company ("Google", say) would return nothing.
    This synthesizes plausible postings for the searched company/type so Demo
    mode always reflects the search."""
    company = (filters.get("company") or "").strip()
    emp = (filters.get("employment_type") or "").strip() or "Full-time"
    if source_key == "indeed":
        org = company or "TechCorp"
        slug = org.replace(" ", "+")
        return [
            {
                "id": "live-indeed-demo-1",
                "title": f"{emp} Software Developer",
                "organization": org, "type": emp, "employment_type": emp,
                "field": "Computer Science", "location": "Toronto, ON",
                "gpa_requirement": "Not specified",
                "required_skills": "Python, Java, SQL, Git",
                "description": f"{emp} software engineering role at {org}. [Demo result generated to match your search.]",
                "deadline": "Rolling",
                "url": f"https://ca.indeed.com/jobs?q={slug}",
                "source": "indeed",
            },
            {
                "id": "live-indeed-demo-2",
                "title": f"{emp} Data Analyst",
                "organization": org, "type": emp, "employment_type": emp,
                "field": "Data", "location": "Remote (Canada)",
                "gpa_requirement": "Not specified",
                "required_skills": "Python, SQL, Excel",
                "description": f"{emp} data role at {org}. [Demo result generated to match your search.]",
                "deadline": "Rolling",
                "url": f"https://ca.indeed.com/jobs?q={slug}",
                "source": "indeed",
            },
        ]
    org = company or "A Canadian Foundation"
    slug = org.replace(" ", "+")
    return [{
        "id": "live-scholarshipscanada-demo-1",
        "title": f"{org} Scholarship",
        "organization": org, "type": "Scholarship", "employment_type": "",
        "field": "Any field", "location": "Canada",
        "gpa_requirement": "Not specified",
        "required_skills": "Academic achievement, community involvement",
        "description": f"Scholarship offered by {org}. [Demo result generated to match your search.]",
        "deadline": "Rolling",
        "url": f"https://www.scholarshipscanada.com/Scholarships/?q={slug}",
        "source": "scholarshipscanada",
    }]


def _passes_filters(opp: dict, filters: dict) -> bool:
    """Keep an opportunity only if it matches the user's filters.

    company/employment_type are matched as case-insensitive substrings. Used to
    keep the demo (and a light live safety net) honest to what was searched."""
    company = (filters.get("company") or "").strip().lower()
    emp = (filters.get("employment_type") or "").strip().lower()
    if company and company not in (opp.get("organization") or "").lower():
        return False
    if emp:
        hay = " ".join([
            str(opp.get("employment_type") or ""), str(opp.get("type") or ""),
            str(opp.get("title") or ""), str(opp.get("description") or ""),
        ]).lower()
        if emp not in hay:
            return False
    return True


def _mock_for_source(source_key: str) -> list[dict]:
    """Cached demo opportunities returned when MOCK_MODE is on."""
    if source_key == "indeed":
        return [
            {
                "id": "live-indeed-1",
                "title": "Software Engineering Intern",
                "organization": "Shopify",
                "type": "Internship",
                "employment_type": "Full-time",
                "field": "Computer Science",
                "location": "Toronto, ON",
                "gpa_requirement": "No strict cutoff",
                "required_skills": "Python, JavaScript, React, Git",
                "description": "Full-stack engineering internship building merchant-facing features. 12-16 weeks, paid.",
                "deadline": "Rolling",
                "url": "https://ca.indeed.com/viewjob?jk=demo-shopify-swe",
                "source": "indeed",
            },
            {
                "id": "live-indeed-2",
                "title": "Backend Developer Intern",
                "organization": "Wealthsimple",
                "type": "Internship",
                "employment_type": "Full-time",
                "field": "Software Engineering",
                "location": "Toronto, ON (Hybrid)",
                "gpa_requirement": "3.0+",
                "required_skills": "Python, SQL, REST APIs, Git",
                "description": "Work on the core money-movement platform. Mentorship from senior engineers; ship code to production.",
                "deadline": "2026-06-15",
                "url": "https://ca.indeed.com/viewjob?jk=demo-wealthsimple-be",
                "source": "indeed",
            },
            {
                "id": "live-indeed-3",
                "title": "Part-time Data Analyst",
                "organization": "BrightPath Analytics",
                "type": "Part-time",
                "employment_type": "Part-time",
                "field": "Data",
                "location": "Remote (Canada)",
                "gpa_requirement": "Not specified",
                "required_skills": "Python, SQL, Excel, data visualization",
                "description": "Part-time (20 hrs/week) data analysis supporting a small product team. Flexible hours around classes.",
                "deadline": "Rolling",
                "url": "https://ca.indeed.com/viewjob?jk=demo-brightpath-da",
                "source": "indeed",
            },
        ]
    return [
        {
            "id": "live-scholarshipscanada-1",
            "title": "TD Scholarship for Community Leadership",
            "organization": "TD Bank Group",
            "type": "Scholarship",
            "field": "Any field",
            "location": "Canada",
            "gpa_requirement": "75%+ average",
            "required_skills": "Community leadership, volunteering, academic achievement",
            "description": "$70,000 over four years, plus paid summer employment with TD. For students who have made a significant community impact.",
            "deadline": "2026-11-15",
            "url": "https://www.scholarshipscanada.com/Scholarships/demo-td-community",
            "source": "scholarshipscanada",
        },
        {
            "id": "live-scholarshipscanada-2",
            "title": "RBC Future Launch Scholarship",
            "organization": "Royal Bank of Canada",
            "type": "Scholarship",
            "field": "Any field",
            "location": "Canada",
            "gpa_requirement": "No strict cutoff",
            "required_skills": "Demonstrated impact from a setback, future-of-work readiness",
            "description": "$1,500 awards for youth who have overcome adversity and are pursuing post-secondary education.",
            "deadline": "2026-02-28",
            "url": "https://www.scholarshipscanada.com/Scholarships/demo-rbc-future-launch",
            "source": "scholarshipscanada",
        },
    ]


def _collect_search_results(response) -> list:
    """The (url, title) pairs the web_search tool ACTUALLY returned — the only
    URLs we trust. Anything the model wrote that isn't one of these is dropped,
    so it can't smuggle in a fabricated (404 / wrong-company) link."""
    results = []
    for block in getattr(response, "content", []) or []:
        if getattr(block, "type", None) != "web_search_tool_result":
            continue
        content = getattr(block, "content", None)
        if not isinstance(content, list):     # could be an error object, not results
            continue
        for item in content:
            if getattr(item, "type", None) == "web_search_result":
                url = (getattr(item, "url", "") or "").strip()
                if url:
                    results.append({"url": url, "title": getattr(item, "title", "") or ""})
    return results


def _norm_url(u: str) -> str:
    """Normalize a URL for comparison: lowercase host, drop scheme/fragment and a
    trailing slash, keep path + query (the query can carry the job id, e.g. ?jk=)."""
    try:
        s = urlsplit((u or "").strip())
        base = (s.hostname or "") + (s.path or "").rstrip("/")
        full = base + ("?" + s.query if s.query else "")
        return full.lower()   # match leniently; the original URL is what we return
    except Exception:
        return (u or "").strip().lower()


def _norm_title(t: str) -> str:
    return " ".join((t or "").lower().split())


def _url_is_live(url: str, timeout: float = 6.0) -> bool:
    """Best-effort liveness check. Returns False ONLY on a clear 'gone' signal
    (404/410). Blocks (401/403/405/429), 5xx, and timeouts count as live, since
    bot-hostile sites (Indeed, LinkedIn) reject automated requests even when the
    posting exists — we'd rather keep a maybe-valid link than drop a real one."""
    headers = {"User-Agent": "Mozilla/5.0 (compatible; OpportuneBot/1.0)"}
    try:
        with httpx.Client(follow_redirects=True, timeout=timeout, headers=headers) as c:
            r = c.head(url)
            if r.status_code in (401, 403, 405):   # some sites reject HEAD; try GET
                r = c.get(url)
            return r.status_code not in (404, 410)
    except Exception:
        return True


_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(s: str) -> str:
    return _TAG_RE.sub("", s or "").strip()


# Adzuna is per-country (the country code sits in the URL path), so to cover
# both Canada and the US we query each endpoint and merge. The country name is
# appended to each location to disambiguate look-alikes (e.g. Vancouver, BC vs
# Vancouver, WA).
_ADZUNA_COUNTRIES = ("ca", "us")
_COUNTRY_NAMES = {"ca": "Canada", "us": "United States"}
# Listings pulled per country. With 2 countries this caps the live job list at
# _ADZUNA_PER_COUNTRY × 2 — 3 each = 6 shown total, balanced across CA and US.
_ADZUNA_PER_COUNTRY = 3


def _adzuna_location(loc: dict, cname: str) -> str:
    """Clean 'City, State/Province' label from Adzuna's `area` list, which runs
    [country, region, …, most-specific]. The state/province usually disambiguates
    CA vs US on its own (Vancouver, BC vs Vancouver, Washington); only when we
    have just a bare city or nothing do we fall back to appending the country.
    Preferred over `display_name`, which for US listings shows county, not state."""
    area = [a for a in (loc.get("area") or []) if a]
    country_token = area[0] if area else ""        # Adzuna uses "US" / "Canada" here
    region = area[1:]                              # drop the leading country token
    if len(region) >= 2:
        return f"{region[-1]}, {region[0]}"        # e.g. "King of Prussia, Pennsylvania"
    if len(region) == 1:
        label = region[0]                          # e.g. "British Columbia"
    else:
        label = _strip_html(loc.get("display_name") or "")
        if not label or label.lower() in (cname.lower(), country_token.lower()):
            return cname                           # only the country is known
    return label if cname.lower() in label.lower() else f"{label}, {cname}"


def _adzuna_fetch_country(country: str, params: dict) -> list[dict]:
    """Run one Adzuna country query and normalize its results to our opportunity
    shape. Raises on HTTP error so the caller can decide partial vs total failure."""
    url = f"https://api.adzuna.com/v1/api/jobs/{country}/search/1"
    with httpx.Client(timeout=15.0) as c:
        resp = c.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

    cname = _COUNTRY_NAMES.get(country, country.upper())
    out = []
    for j in (data.get("results") or []):
        link = (j.get("redirect_url") or "").strip()
        if not link:
            continue
        title = _strip_html(j.get("title") or "")
        ct = j.get("contract_time") or ""
        emp_type = "Full-time" if ct == "full_time" else ("Part-time" if ct == "part_time" else "Not specified")
        loc = _adzuna_location(j.get("location") or {}, cname)
        out.append({
            "id": f"live-adzuna-{country}-{j.get('id') or abs(hash(link)) % (10**9)}",
            "title": title,
            "organization": _strip_html((j.get("company") or {}).get("display_name") or ""),
            "type": "Internship" if "intern" in title.lower() else "Job",
            "employment_type": emp_type,
            "field": _strip_html((j.get("category") or {}).get("label") or ""),
            "location": loc,
            "gpa_requirement": "Not specified",
            "required_skills": "",
            "description": _strip_html(j.get("description") or "")[:400],
            "deadline": "Not specified",
            "url": link,
            "source": "adzuna",
        })
    return out


def _search_adzuna(profile: dict, filters: dict = None) -> list[dict]:
    """Live JOB search via Adzuna across Canada AND the US. Returns the same
    opportunity shape as the web_search path, but every URL is Adzuna's canonical
    apply link (`redirect_url`) — real by construction, so no grounding or HTTP
    validation is needed (that's the whole reason to prefer the API). The two
    country queries run concurrently; if one fails we still return the other's
    results, and only raise when both fail."""
    filters = filters or {}
    company = (filters.get("company") or "").strip()
    emp = (filters.get("employment_type") or "").strip().lower()

    # These params are country-independent — the country lives in the URL path,
    # so the same query runs against each Adzuna country endpoint.
    params = {
        "app_id": ADZUNA_APP_ID,
        "app_key": ADZUNA_APP_KEY,
        "results_per_page": _ADZUNA_PER_COUNTRY,
        "max_days_old": 60,
        "content-type": "application/json",
    }
    if company:
        params["what"] = company                         # all-terms match: that company
    else:
        # Profile-based discovery. Adzuna's `what` ANDs every word, which
        # over-narrows to zero for a multi-term profile query — so use `what_or`
        # (match ANY of the terms) and let fit-scoring rank the results after.
        skills = _flatten_skills(profile.get("skills"))[:3]
        interests = (profile.get("interests") or [])[:2]
        edu = (profile.get("education") or [{}])[0]
        field = edu.get("degree") or ""
        terms = " ".join(t for t in ([field] + interests + skills) if t).strip()
        params["what_or" if terms else "what"] = terms or "internship"
    if emp == "full-time":
        params["full_time"] = 1
    elif emp == "part-time":
        params["part_time"] = 1

    # Query both countries concurrently; isolate each so one failing endpoint
    # doesn't sink the other. Only a total failure (both errored) re-raises.
    results, errs = [], []
    with ThreadPoolExecutor(max_workers=len(_ADZUNA_COUNTRIES)) as pool:
        futs = {pool.submit(_adzuna_fetch_country, ctry, params): ctry for ctry in _ADZUNA_COUNTRIES}
        for fut, ctry in futs.items():
            try:
                results.extend(fut.result())
            except Exception as e:
                errs.append(f"{ctry}: {e}")
    if not results and errs:
        raise RuntimeError("Adzuna search failed — " + "; ".join(errs))
    return results


def _search_web(profile: dict, source_key: str, filters: dict = None) -> list[dict]:
    """Grounded web_search across this source's allowlisted sites — every URL is
    matched back to a real search hit, then HTTP-validated (see end of function)."""
    cfg = _SOURCES[source_key]
    query = _build_query(profile, source_key, filters)
    domains = cfg["domains"]

    # Ground results in REAL hits from the free Hack Club Search API (this
    # replaces Anthropic's built-in web_search tool). The model only selects and
    # describes among these — it never authors URLs.
    results_hits = web_search(query, allowed_domains=domains, count=10)
    if not results_hits:
        # No search key configured (or the search failed) — nothing to ground on.
        return []

    # Number the real hits so the model can copy exact URLs back out.
    listed = "\n".join(
        f"{idx + 1}. {h['title']}\n   URL: {h['url']}\n   {h.get('description', '')}"
        for idx, h in enumerate(results_hits)
    )

    prompt = f"""You are selecting real opportunities for this student profile.

Search query: {query}

Profile (for context — prefer postings that genuinely match):
{json.dumps(profile, ensure_ascii=False)}

Below are REAL web search results. Use ONLY these — do not invent postings or URLs.

Search results:
{listed}

From the results above, pick the ones that are individual {cfg['type'].lower()} postings
that fit the student, and return a JSON object with this exact shape:

{{
  "opportunities": [
    {{
      "title": "string",
      "organization": "string (the employer/company)",
      "type": "{cfg['type']}",
      "employment_type": "string ('Full-time', 'Part-time', or 'Not specified')",
      "field": "string (e.g. 'Computer Science', 'STEM', 'Any field')",
      "location": "string",
      "gpa_requirement": "string (or 'Not specified')",
      "required_skills": "string (comma-separated)",
      "description": "string (1-2 sentences from the posting)",
      "deadline": "string (YYYY-MM-DD if known, else 'Rolling' or 'Not specified')",
      "url": "string (copy the EXACT URL from the matching search result above)"
    }}
  ]
}}

Rules:
- Use ONLY the search results listed above.
- `url` MUST be copied verbatim from one of those results — never invent or guess one.
- Prefer URLs that link to a SINGLE posting, not a search-results or landing page.
- If none are a reasonable match, return {{"opportunities": []}}.
- Return ONLY valid JSON. No markdown fences. No commentary."""

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
    )

    # The URLs the search engine actually returned — the only ones we trust.
    real_results = results_hits
    by_norm, by_title = {}, {}
    for r in real_results:
        by_norm.setdefault(_norm_url(r["url"]), r["url"])
        t = _norm_title(r["title"])
        if t:
            by_title.setdefault(t, r["url"])

    # The model emits the JSON in a text block (the last one — thinking/tool
    # blocks may precede it).
    text = ""
    for block in response.content:
        if getattr(block, "type", None) == "text":
            text = block.text
    if not text:
        return []

    parsed = safe_json_parse(text)
    raw_items = parsed.get("opportunities", []) if isinstance(parsed, dict) else []

    def _to_opp(it, url):
        return {
            "id": f"live-{source_key}-{abs(hash(url)) % (10**9)}",
            "title": it.get("title", "").strip(),
            "organization": it.get("organization", "").strip(),
            "type": it.get("type") or cfg["type"],
            "employment_type": (it.get("employment_type") or "").strip(),
            "field": it.get("field", "").strip(),
            "location": it.get("location", "").strip(),
            "gpa_requirement": it.get("gpa_requirement", "Not specified"),
            "required_skills": it.get("required_skills", ""),
            "description": it.get("description", "").strip(),
            "deadline": it.get("deadline", "Not specified"),
            "url": url,
            "source": source_key,
        }

    out, seen = [], set()
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        # Resolve to a REAL url: exact match on what the model wrote, else match
        # the posting by title. Drop anything we can't ground in a real result.
        real_url = by_norm.get(_norm_url(item.get("url") or "")) or by_title.get(_norm_title(item.get("title")))
        if not real_url or real_url in seen:
            continue
        seen.add(real_url)
        out.append(_to_opp(item, real_url))

    # Safety net: if we saw NO web_search results to ground against (e.g. the
    # result-block shape ever differs from what we parse here), don't silently
    # return nothing — fall back to the model's own URLs. HTTP validation below
    # still drops the dead ones.
    if not out and not real_results:
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            u = (item.get("url") or "").strip()
            if not u or u in seen:
                continue
            seen.add(u)
            out.append(_to_opp(item, u))

    # Validate the surviving URLs still resolve; drop clearly-dead postings
    # (404/410). Concurrent with a short timeout, so this adds little latency.
    if out:
        with ThreadPoolExecutor(max_workers=min(8, len(out))) as pool:
            live = list(pool.map(lambda o: _url_is_live(o["url"]), out))
        out = [o for o, ok in zip(out, live) if ok]
    return out


def _search_one_source(profile: dict, source_key: str, filters: dict = None) -> list[dict]:
    """One source of live results. Jobs come from Adzuna's real listings when the
    API is configured (canonical apply URLs, no fabrication); otherwise — and for
    scholarships — a grounded web_search."""
    if source_key == "indeed" and ADZUNA_APP_ID and ADZUNA_APP_KEY:
        return _search_adzuna(profile, filters)
    return _search_web(profile, source_key, filters)


def search_live_opportunities(profile: dict, sources: list, mock=None, filters: dict = None,
                              errors: list = None) -> list:
    """Search live opportunities across the requested sources.

    `sources` selects job vs scholarship sites (["indeed"] vs
    ["scholarshipscanada"]). `filters` (company, employment_type) steer the query
    and trim the results so a search for e.g. "part-time at Shopify" reflects
    those criteria. If `errors` (a list) is passed, per-source failures are
    appended to it so the caller can tell "no matches" apart from "search broke."
    Returns a flat list of opportunity dicts (Opportunity-model shape + url/source)."""
    use_mock = MOCK_MODE if mock is None else bool(mock)
    filters = filters or {}
    requested = [s for s in (sources or []) if s in _SOURCES]
    if not requested:
        requested = list(_SOURCES.keys())

    if use_mock:
        results = []
        for s in requested:
            results.extend(_mock_for_source(s))
        # Filter the demo data so it reflects the user's search criteria.
        filtered = [o for o in results if _passes_filters(o, filters)]
        # If the filters excluded all sample data (e.g. a company we don't have
        # canned data for), synthesize matching postings so the demo still works.
        if not filtered and (filters.get("company") or filters.get("employment_type")):
            synth = []
            for s in requested:
                synth.extend(_synth_mock_for_filters(s, filters))
            return [o for o in synth if _passes_filters(o, filters)]
        return filtered

    # Search every requested source concurrently. Each _search_one_source call is
    # a slow web_search request (up to max_uses searches), so running the sources
    # in parallel instead of one after another roughly halves this step. The
    # Anthropic SDK releases the GIL while waiting on the network, so threads are
    # enough — no async needed.
    results = []
    with ThreadPoolExecutor(max_workers=max(1, len(requested))) as pool:
        futures = {pool.submit(_search_one_source, profile, s, filters): s
                   for s in requested}
        for future, s in futures.items():            # dict preserves submission order
            try:
                results.extend(future.result())
            except Exception as e:
                # Record the failure (so the caller can surface it) but keep going
                # so another source still has a chance.
                if errors is not None:
                    errors.append(f"{_SOURCES[s]['label']}: {e}")
                print(f"[opportunity_search] {s} failed: {e}")

    # Light safety net: enforce the company filter (the query already reflects
    # the rest; we avoid over-pruning live results on employment_type).
    company = (filters.get("company") or "").strip().lower()
    if company:
        # Keep postings that mention the company in the org, title, or URL — the
        # URL catches ATS pages like boards.greenhouse.io/<company>/... where the
        # company name lives in the path rather than the organization field.
        def _company_match(o):
            hay = " ".join([
                str(o.get("organization") or ""),
                str(o.get("title") or ""),
                str(o.get("url") or ""),
            ]).lower()
            return company in hay
        results = [o for o in results if _company_match(o)]
    return results
