"""What changed between two updates of a schedule.

Every week a scheduler re-runs P6 and the question is the same: what moved,
what quietly lost float, and did completion slip? P6 answers one activity at a
time. This lines two snapshots up by activity id and answers it for the whole
project, from P6's own dates and float -- no modelling, so nothing here is an
approximation of the schedule, only of which milestone "completion" is.
"""
from __future__ import annotations

import sys
from pathlib import Path
from statistics import median

sys.path.insert(0, str(Path(__file__).resolve().parent))

from importers.names import is_delivery              # noqa: E402
from importers.snapshots import Snapshot             # noqa: E402

TOP = 15


def _milestone(s: Snapshot) -> dict | None:
    k = s.finish_milestone()
    if k is None:
        return None
    return {"id": k, "name": s.activities[k].name, "finish": s.activities[k].finish.isoformat()}


def compare(older: Snapshot, newer: Snapshot, top: int = TOP) -> dict:
    a, b = older.activities, newer.activities
    common = [k for k in b if k in a]
    added = [k for k in b if k not in a]
    removed = [k for k in a if k not in b]
    shift = {k: (b[k].finish - a[k].finish).days for k in common}
    later = [k for k in common if shift[k] > 0]
    earlier = [k for k in common if shift[k] < 0]
    dfloat = {k: b[k].float_days - a[k].float_days for k in common
              if a[k].float_days is not None and b[k].float_days is not None}
    lost = [k for k, d in dfloat.items() if d < 0]
    gained = [k for k, d in dfloat.items() if d > 0]
    newly_critical = [k for k in dfloat if a[k].float_days > 0 >= b[k].float_days]

    def row(k: str) -> dict:
        return {"id": k, "name": b[k].name, "old_finish": a[k].finish.isoformat(),
                "new_finish": b[k].finish.isoformat(), "shift_days": shift[k],
                "old_float": a[k].float_days, "new_float": b[k].float_days, "done": b[k].done}

    still_open = [k for k in common if not b[k].done]
    top_slipped = sorted((k for k in still_open if shift[k] > 0), key=lambda k: (-shift[k], k))[:top]
    top_lost = sorted((k for k in still_open if dfloat.get(k, 0) < 0), key=lambda k: (dfloat[k], k))[:top]
    deliveries = sorted((k for k in still_open if is_delivery(b[k].name)
                         and (shift[k] > 0 or dfloat.get(k, 0) < 0)),
                        key=lambda k: (dfloat.get(k, 0), -shift[k], k))[:top]

    ca, cb = _milestone(older), _milestone(newer)
    completion_shift = None
    if ca and cb:
        from datetime import date
        completion_shift = (date.fromisoformat(cb["finish"]) - date.fromisoformat(ca["finish"])).days
    med = median(shift[k] for k in later) if later else None

    parts = [f"{len(later):,} of {len(common):,} activities finish later"
             + (f" (median +{med:g} days)" if med is not None else "")]
    if lost:
        parts.append(f"{len(lost):,} lost float")
    if newly_critical:
        parts.append(f"{len(newly_critical):,} became critical")
    if completion_shift is not None:
        parts.append("completion held" if completion_shift == 0 else
                     f"completion moved {'+' if completion_shift > 0 else ''}{completion_shift} days")
    headline = "; ".join(parts) + "."

    return {
        "older": older.summary(), "newer": newer.summary(),
        "headline": headline,
        "counts": {"matched": len(common), "added": len(added), "removed": len(removed),
                   "later": len(later), "earlier": len(earlier),
                   "unchanged": len(common) - len(later) - len(earlier),
                   "lost_float": len(lost), "gained_float": len(gained),
                   "newly_critical": len(newly_critical)},
        "median_shift_days": med,
        "completion": {"older": ca, "newer": cb, "shift_days": completion_shift},
        "top_slipped": [row(k) for k in top_slipped],
        "top_float_lost": [row(k) for k in top_lost],
        "deliveries": [row(k) for k in deliveries],
    }
