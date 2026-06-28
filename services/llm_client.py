"""Hack Club AI client shim.

Provides a tiny `client` object that mimics the slice of the Anthropic SDK the
rest of the app uses — `client.messages.create(...)` returning an object whose
`.content[0].text` holds the reply — but talks to Hack Club AI's free,
OpenAI-compatible chat-completions endpoint instead.

This lets the existing services keep their original call sites essentially
unchanged while costing nothing to run.

Also exposes `web_search()` — a thin wrapper over the free Hack Club Search API
used to ground live opportunity results (replacing Anthropic's built-in
web_search tool).
"""
import httpx

from config import (
    HACKCLUB_AI_API_KEY,
    HACKCLUB_AI_BASE_URL,
    HACKCLUB_SEARCH_API_KEY,
    HACKCLUB_SEARCH_URL,
)

# Longer timeout: drafting a full tailored resume can take a while.
_HTTP_TIMEOUT = httpx.Timeout(120.0, connect=15.0)


# --- Minimal response objects shaped like the Anthropic SDK's --------------
class _TextBlock:
    """Mimics an Anthropic text content block: has .type == 'text' and .text."""
    type = "text"

    def __init__(self, text: str):
        self.text = text or ""


class _Response:
    """Mimics an Anthropic Message: .content is a list of content blocks."""
    def __init__(self, text: str):
        self.content = [_TextBlock(text)]


class _Messages:
    """Implements .create(...) against Hack Club AI's chat-completions API."""

    def create(self, model, messages, max_tokens=1024, temperature=None, **_ignored):
        if not HACKCLUB_AI_API_KEY:
            raise RuntimeError(
                "HACKCLUB_AI_API_KEY is not set — get a free key at "
                "https://ai.hackclub.com/dashboard and add it to your .env."
            )
        # messages already use OpenAI-compatible roles ('user'/'system'/'assistant')
        # with string content, so they pass straight through.
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        if temperature is not None:
            payload["temperature"] = temperature

        headers = {
            "Authorization": f"Bearer {HACKCLUB_AI_API_KEY}",
            "Content-Type": "application/json",
        }
        url = HACKCLUB_AI_BASE_URL.rstrip("/") + "/chat/completions"
        resp = httpx.post(url, json=payload, headers=headers, timeout=_HTTP_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        text = (data.get("choices") or [{}])[0].get("message", {}).get("content", "") or ""
        return _Response(text)


class _Client:
    def __init__(self):
        self.messages = _Messages()


# Drop-in replacement for `anthropic.Anthropic(...)` used across the services.
client = _Client()


# --- Free web search (Hack Club Search) ------------------------------------
def web_search(query: str, allowed_domains=None, count: int = 8) -> list[dict]:
    """Return [{"url","title","description"}] from the Hack Club Search API.

    `allowed_domains` softly biases results: if any returned URLs are hosted on
    one of those domains, only those are kept; otherwise all results are returned
    (so a too-narrow allowlist never starves the search). Returns [] silently if
    no search key is configured or the request fails — callers degrade to their
    own fallbacks (e.g. Adzuna for jobs).
    """
    if not HACKCLUB_SEARCH_API_KEY:
        return []
    try:
        headers = {"Authorization": f"Bearer {HACKCLUB_SEARCH_API_KEY}"}
        params = {"q": (query or "")[:400], "count": count}
        resp = httpx.get(HACKCLUB_SEARCH_URL, params=params, headers=headers, timeout=20.0)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return []

    raw = ((data.get("web") or {}).get("results")) or data.get("results") or []
    results = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        url = (item.get("url") or "").strip()
        if not url:
            continue
        results.append({
            "url": url,
            "title": (item.get("title") or "").strip(),
            "description": (item.get("description") or item.get("snippet") or "").strip(),
        })

    if allowed_domains:
        doms = [d.lower() for d in allowed_domains]
        def _host_ok(u: str) -> bool:
            h = u.lower()
            return any(d in h for d in doms)
        filtered = [r for r in results if _host_ok(r["url"])]
        if filtered:
            return filtered
    return results
