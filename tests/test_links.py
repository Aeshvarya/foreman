"""Guards for typed P6 relationships (FS / SS / FF / SF + lag) in the forward pass.

Every expected date below is worked out by hand from the rule for that link type,
so a failure here means the engine disagrees with the definition — not with
itself. Activity A: 5 days from day 0. Activity B: 3 days, linked to A.

Run:  python tests/test_links.py
"""
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from cascade import forward_pass          # noqa: E402
from graph import build_graph             # noqa: E402
from projects import _normalise           # noqa: E402

D0 = date(2027, 1, 4)
fails = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'} {label}" + ("" if ok else f"   got {got}, want {want}"))
    if not ok:
        fails.append(label)


def project(link=None, arrival=D0):
    b = {"id": "B", "name": "B", "duration_days": 3, "depends_on": ["A"],
         "needs_materials": [], "early_start": D0.isoformat()}
    if link is not None:
        b["links"] = [{"pred": "A", **link}]
    return {
        "project": {"name": "links", "handover_milestone": "B"},
        "suppliers": [{"id": "S", "name": "S"}],
        "materials": [{"id": "M", "name": "M", "supplier": "S",
                       "roj_date": D0.isoformat(), "expected_arrival": arrival.isoformat()}],
        "activities": [
            {"id": "A", "name": "A", "duration_days": 5, "depends_on": [],
             "needs_materials": ["M"], "early_start": D0.isoformat()},
            b,
        ],
    }


def b_start(link=None, arrival=D0):
    g = build_graph(_normalise(project(link, arrival)))
    return (forward_pass(g)["B"].start - D0).days


print("Each link type, by hand (A = days 0-5, B = 3 days)")
check("no links field = finish-to-start (old behaviour)", b_start(None), 5)
check("FS lag 0  -> B starts when A finishes, day 5",   b_start({"type": "FS", "lag_days": 0}), 5)
check("FS lag 2  -> day 7",                              b_start({"type": "FS", "lag_days": 2}), 7)
check("SS lag 1  -> B starts 1 day after A starts",      b_start({"type": "SS", "lag_days": 1}), 1)
check("FF lag 0  -> B finishes with A (5), starts 2",    b_start({"type": "FF", "lag_days": 0}), 2)
check("SF lag 4  -> B finishes by A.start+4, starts 1",  b_start({"type": "SF", "lag_days": 4}), 1)
check("negative lag (lead) FS -2 -> day 3",              b_start({"type": "FS", "lag_days": -2}), 3)

print("\nA late material travels through every link type")
late = D0 + timedelta(days=3)          # A now starts day 3, finishes day 8
check("SS lag 1: A starts day 3 -> B day 4",  b_start({"type": "SS", "lag_days": 1}, late), 4)
check("FF lag 0: A finishes day 8 -> B day 5", b_start({"type": "FF", "lag_days": 0}, late), 5)
check("FS lag 0: A finishes day 8 -> B day 8", b_start({"type": "FS", "lag_days": 0}, late), 8)

print("\nThe normaliser keeps good links and drops bad ones")
p = project({"type": "ss", "lag_days": "2"})
p["activities"][1]["links"].append({"pred": "A", "type": "XX", "lag_days": 0})    # bad type
p["activities"][1]["links"].append({"pred": "GHOST", "type": "FS", "lag_days": 0}) # not a predecessor
kept = _normalise(p)["activities"][1]["links"]
check("lower-case type and string lag are cleaned up", kept[0], {"pred": "A", "type": "SS", "lag_days": 2})
check("unknown type and unknown predecessor dropped", len(kept), 1)
check("projects without links carry no links key",
      "links" in _normalise(project(None))["activities"][1], False)

print(f"\n{'ALL LINK CHECKS PASSED ✓' if not fails else f'{len(fails)} FAILED: {fails}'}")
sys.exit(1 if fails else 0)
