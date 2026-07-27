"""Gemini LLM wrapper for Foreman's agents.

Uses Gemini's free tier (no card) via langchain-google-genai. One place to
configure the model + rate limiting so every agent stays consistent.

Model choice: `gemini-flash-lite-latest`. Measured free-tier headroom is far
higher than `gemini-2.5-flash` (which caps at 5 req/min and throttles a live
demo). A light rate-limiter is added as insurance.

Gemini 3.x returns message content as a LIST of parts, not a string, so always
extract text via `invoke_text()` / `complete()` — never touch `.content` raw.

Get a free key: https://aistudio.google.com/apikey  -> put in .env as GEMINI_API_KEY
"""

from __future__ import annotations

import hashlib
import os
import threading
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest")

_RATE_LIMITER = None
_CACHE: dict = {}

# ---------------------------------------------------------------- response cache
# Free-tier latency is fine on average (~3-7s) but has a long tail: the SAME
# prompt was measured at 1.0s, 6.8s and 36.5s. That tail is a live-demo hazard,
# so identical prompts are served from memory on repeat.
#
# This is a cache, not a fake: a miss always calls the real model, and every
# deterministic call (fact extraction, query planning) runs at temperature 0,
# where repeating a prompt is *defined* to give the same answer. Narration runs
# at 0.3, so caching there trades a little wording variety for a predictable
# demo — the underlying numbers come from the CPM engine either way.
#
# It also can't go stale behind your back: every prompt embeds the data it
# reasons over (the queried rows, the document text, the live scene JSON), so
# any change to the project changes the prompt, changes the key, and misses.
#
# Persisted to disk so a rehearsal warms the real demo — an API restart between
# practising and presenting would otherwise throw the warm cache away.
_RESPONSES: dict[str, str] = {}
_RESPONSES_LOCK = threading.Lock()
MAX_CACHED = 512

CACHE_FILE = Path(__file__).resolve().parents[2] / "data" / ".llm_cache.json"
CACHE_DISABLED = os.getenv("FOREMAN_NO_LLM_CACHE", "").lower() in {"1", "true", "yes"}


def _cache_key(model: str, temperature: float, prompt: str) -> str:
    return hashlib.sha256(
        f"{model}|{temperature}|{prompt}".encode()
    ).hexdigest()


def _load_disk_cache() -> None:
    global _RESPONSES
    if CACHE_DISABLED or not CACHE_FILE.exists():
        return
    try:
        import json
        data = json.loads(CACHE_FILE.read_text())
        if isinstance(data, dict):
            with _RESPONSES_LOCK:
                _RESPONSES.update({k: v for k, v in data.items() if isinstance(v, str)})
    except Exception:
        pass   # a corrupt cache must never break the app — just start empty


def _save_disk_cache() -> None:
    if CACHE_DISABLED:
        return
    try:
        import json
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with _RESPONSES_LOCK:
            snapshot = dict(_RESPONSES)
        tmp = CACHE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(snapshot))
        tmp.replace(CACHE_FILE)     # atomic — never leave a half-written cache
    except Exception:
        pass


def cache_stats() -> dict:
    with _RESPONSES_LOCK:
        return {"cached_responses": len(_RESPONSES), "limit": MAX_CACHED,
                "disk": str(CACHE_FILE), "disabled": CACHE_DISABLED}


def clear_cache() -> None:
    with _RESPONSES_LOCK:
        _RESPONSES.clear()
    try:
        CACHE_FILE.unlink(missing_ok=True)
    except Exception:
        pass


_load_disk_cache()


def has_key() -> bool:
    return bool(os.getenv("GEMINI_API_KEY"))


def _rate_limiter():
    global _RATE_LIMITER
    if _RATE_LIMITER is None:
        from langchain_core.rate_limiters import InMemoryRateLimiter
        # ~15 req/min with small bursts — safe under free-tier, snappy enough.
        _RATE_LIMITER = InMemoryRateLimiter(
            requests_per_second=0.25, check_every_n_seconds=0.1, max_bucket_size=8
        )
    return _RATE_LIMITER


def get_llm(temperature: float = 0.0, model: str | None = None):
    """Return a configured Gemini chat model (cached per model+temp)."""
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError(
            "GEMINI_API_KEY not set. Copy .env.example -> .env and add a free "
            "key from https://aistudio.google.com/apikey"
        )
    model = model or DEFAULT_MODEL
    ck = (model, temperature)
    if ck not in _CACHE:
        from langchain_google_genai import ChatGoogleGenerativeAI
        _CACHE[ck] = ChatGoogleGenerativeAI(
            model=model, temperature=temperature, google_api_key=key,
            max_retries=3, rate_limiter=_rate_limiter(),
        )
    return _CACHE[ck]


def invoke_text(prompt: str, temperature: float = 0.0, model: str | None = None,
                use_cache: bool = True) -> str:
    """Invoke the model and return plain text, robust to str- or list-content.

    Identical prompts are served from the in-memory response cache (see above)
    so a repeated question can't hit the free tier's long latency tail mid-demo.
    Pass `use_cache=False` to force a fresh call.
    """
    mdl = model or DEFAULT_MODEL
    key = _cache_key(mdl, temperature, prompt)
    if use_cache:
        with _RESPONSES_LOCK:
            hit = _RESPONSES.get(key)
        if hit is not None:
            return hit

    out = _text(get_llm(temperature, model).invoke(prompt))

    if use_cache and out:
        with _RESPONSES_LOCK:
            if len(_RESPONSES) >= MAX_CACHED:
                _RESPONSES.pop(next(iter(_RESPONSES)))   # simple FIFO eviction
            _RESPONSES[key] = out
        _save_disk_cache()
    return out


# Back-compat alias used around the codebase.
complete = invoke_text


def _text(resp) -> str:
    """Extract plain text from a langchain AIMessage (str or list-of-parts).

    Gemini 3.x returns content as a list of {'type':'text','text':...} parts;
    older models return a plain string. Parse content directly (avoids the
    deprecated `.text()` method).
    """
    c = getattr(resp, "content", resp)
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        out = []
        for p in c:
            if isinstance(p, dict):
                out.append(p.get("text", ""))
            elif isinstance(p, str):
                out.append(p)
        return "".join(out)
    return str(c)


if __name__ == "__main__":
    if not has_key():
        print("✗ No GEMINI_API_KEY in .env — add one to run the smoke test.")
        raise SystemExit(1)
    print(f"Model: {DEFAULT_MODEL}")
    out = complete("Reply with exactly: FOREMAN LLM ONLINE")
    print("Response:", out.strip())
    print("✓ Gemini reachable" if "FOREMAN" in out.upper() else "✗ unexpected reply")
