"""Regenerate every headline number straight from the deployed app.

Why this exists: the Aug-21 deck quoted figures that no longer matched what the
live URL returned — a 71% slip probability on a slide against 15% on the API —
because the JSON mirror, the local graph store and Aura had drifted into three
different projects without anything noticing. A number that is typed by hand
into a slide cannot be trusted a week later. A number that is regenerated from
the running deployment can.

So: this asks the live app, writes docs/NUMBERS.md, and is the only place any
published figure should ever be copied from.

    python scripts/verify_live_numbers.py                  # writes docs/NUMBERS.md
    python scripts/verify_live_numbers.py --check          # fails if the doc is stale
    python scripts/verify_live_numbers.py --base http://localhost:8000
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import date, timezone, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "NUMBERS.md"
LIVE = "https://foreman-yi3t.onrender.com"

# The free instance sleeps; the first call can pay a cold start of nearly a
# minute. That is a wait, not a failure.
TIMEOUT = 120


def call(base: str, path: str, payload: dict | None = None):
    url = f"{base}{path}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"} if data else {},
        method="POST" if data else "GET",
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read())


def money_line(m: dict, key: str) -> str:
    f = m.get(key, {})
    return f"{f.get('display', '?')} — {f.get('label', key)} ({f.get('source', '?')})"


def build(base: str) -> str:
    health = call(base, "/api/health")
    mats = call(base, "/api/materials")
    mc = call(base, "/api/montecarlo")
    money = call(base, "/api/money")

    # The two cascades the deck leads with: one that breaks the date, one the
    # schedule absorbs. Same engine, opposite answers.
    steel = call(base, "/api/cascade", {"material_id": "MAT-1", "delay_days": 21})
    switch = call(base, "/api/cascade", {"material_id": "MAT-2", "delay_days": 14})

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    L = []
    a = L.append
    a("# Foreman — the numbers, straight from the deployment")
    a("")
    a("> **Generated, never typed.** `python scripts/verify_live_numbers.py`")
    a(f"> Source: `{base}` · captured {stamp}")
    a("")
    a("Any figure that appears in a slide, a README or a message must be copied")
    a("from this file. If a number is not here, it is not claimed.")
    a("")
    a("## Instance")
    a("")
    a(f"- graph store: **{health.get('graph')}** ({health.get('graph_detail')})")
    a(f"- language model reachable: **{health.get('llm')}**")
    a(f"- materials tracked: **{len(mats)}**")
    a("")
    a("## Schedule risk (Monte-Carlo)")
    a("")
    a(f"- simulations: **{mc.get('n')}**")
    a(f"- vendor correlation applied: **{mc.get('vendor_correlation', 0.0)}**")
    a(f"- baseline handover: **{mc.get('baseline_handover')}**")
    a(f"- P(handover slips): **{mc.get('p_slip')}**")
    a(f"- mean slip: **{mc.get('mean_slip')} days** · P50 **{mc.get('p50_slip')}** · P90 **{mc.get('p90_slip')}**")
    a("")
    a("Top risk drivers:")
    a("")
    a("| material | risk contribution |")
    a("| --- | --- |")
    for d in (mc.get("drivers") or [])[:5]:
        a(f"| {d.get('name')} | {d.get('risk_contribution')} |")
    a("")
    a("## Cascade — the two headline scenarios")
    a("")
    a("| scenario | handover | slip | slipped | absorbed | confidence |")
    a("| --- | --- | --- | --- | --- | --- |")
    for label, c in (("Structural steel +21d", steel), ("LV switchgear +14d", switch)):
        a(f"| {label} | {c.get('baseline_handover')} → {c.get('handover_date')} "
          f"| **{c.get('handover_slip_days')}d** | {len(c.get('slipped') or [])} "
          f"| {len(c.get('absorbed') or [])} | {c.get('confidence')} |")
    a("")
    a("## Commercials")
    a("")
    for key in ("penalty_per_day", "daily_overhead"):
        if key in money:
            a(f"- {money_line(money, key)}")
    a("")
    return "\n".join(L) + "\n"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--base", default=LIVE, help="app to read from")
    p.add_argument("--check", action="store_true",
                   help="exit non-zero if the committed doc no longer matches")
    args = p.parse_args()

    try:
        doc = build(args.base)
    except (urllib.error.URLError, TimeoutError) as e:
        print(f"could not reach {args.base}: {e}", file=sys.stderr)
        return 2

    if args.check:
        if not OUT.exists():
            print("docs/NUMBERS.md has never been generated", file=sys.stderr)
            return 1
        # The timestamp line always moves; compare everything else.
        strip = lambda t: [l for l in t.splitlines() if not l.startswith("> Source:")]
        if strip(OUT.read_text()) != strip(doc):
            print("docs/NUMBERS.md is STALE — the deployment has moved. Regenerate it.",
                  file=sys.stderr)
            return 1
        print("docs/NUMBERS.md matches the deployment ✓")
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(doc)
    print(f"wrote {OUT.relative_to(ROOT)} from {args.base}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
