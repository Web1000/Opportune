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
    TAVILY_API_KEY,
    TAVILY_SEARCH_URL,
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
def _apply_domain_bias(results: list[dict], allowed_domains) -> list[dict]:
    """Soft domain filter: if any results are on an allowed domain keep only
    those, otherwise return all (a too-narrow allowlist never starves search)."""
    if not allowed_domains:
        return results
    doms = [d.lower() for d in allowed_domains]
    filtered = [r for r in results if any(d in r["url"].lower() for d in doms)]
    return filtered or results


def _tavily_search(query: str, allowed_domains, count: int):
    """Search via Tavily. Returns a list of hits, or None when Tavily is not
    configured or the request fails (so the caller can fall back)."""
    if not TAVILY_API_KEY:
        return None
    try:
        payload = {
            "query": (query or "")[:400],
            "max_results": count,
            "search_depth": "basic",
        }
        if allowed_domains:
            # Tavily filters by domain server-side, so results come back scoped.
            payload["include_domains"] = list(allowed_domains)
        headers = {
            "Authorization": f"Bearer {TAVILY_API_KEY}",
            "Content-Type": "application/json",
        }
        resp = httpx.post(TAVILY_SEARCH_URL, json=payload, headers=headers, timeout=20.0)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"[web_search] Tavily failed, will try fallback: {e}")
        return None

    results = []
    for item in data.get("results", []):
        if not isinstance(item, dict):
            continue
        url = (item.get("url") or "").strip()
        if not url:
            continue
        results.append({
            "url": url,
            "title": (item.get("title") or "").strip(),
            "description": (item.get("content") or "").strip(),
        })
    return _apply_domain_bias(results, allowed_domains)


def _hackclub_search(query: str, allowed_domains, count: int) -> list[dict]:
    """Search via the Hack Club Search API. Returns [] if unconfigured/failed."""
    if not HACKCLUB_SEARCH_API_KEY:
        return []
    try:
        headers = {"Authorization": f"Bearer {HACKCLUB_SEARCH_API_KEY}"}
        params = {"q": (query or "")[:400], "count": count}
        resp = httpx.get(HACKCLUB_SEARCH_URL, params=params, headers=headers, timeout=20.0)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"[web_search] Hack Club Search failed: {e}")
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
    return _apply_domain_bias(results, allowed_domains)


def web_search(query: str, allowed_domains=None, count: int = 8) -> list[dict]:
    """Return [{"url","title","description"}] from a live web-search backend.

    Prefers Tavily when TAVILY_API_KEY is set (reliable, with server-side domain
    filtering); falls back to the Hack Club Search API if Tavily is unconfigured
    or its request fails. `allowed_domains` softly biases results to those hosts.
    Returns [] silently if no backend is available — callers then degrade to
    their own fallbacks (e.g. Adzuna for jobs).
    """
    hits = _tavily_search(query, allowed_domains, count)
    if hits is not None:
        return hits
    return _hackclub_search(query, allowed_domains, count)
