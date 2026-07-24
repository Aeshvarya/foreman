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

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest")

_RATE_LIMITER = None
_CACHE: dict = {}


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


def invoke_text(prompt: str, temperature: float = 0.0, model: str | None = None) -> str:
    """Invoke the model and return plain text, robust to str- or list-content."""
    return _text(get_llm(temperature, model).invoke(prompt))


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
