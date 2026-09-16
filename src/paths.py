"""Exact shortcuts for the questions the app asks thousands of times.

The radar, the morning brief and Monte-Carlo all ask one question over and
over: "if these deliveries move, when does handover start?" A full forward pass
per question is fine for 12 activities and painful for 5,000 -- the radar took
13 s on a 5,369-activity schedule, Monte-Carlo the same again.

But the forward pass only ever takes a maximum and adds a fixed amount. An
activity starts at the latest of its own planned start, each predecessor's
start plus a fixed offset (set by the link type, the lag and the durations),
and each of its materials' arrival. Durations don't change in these questions,
so handover's start is

    start(handover) = max( K,  max over materials m of  arrival(m) + L(m) )

where L(m) is the longest path from material m to handover and K is the latest
start the activities' own planned dates force on it. One backward sweep gives
both. After that, "what if these arrive d days late" is a max over a few
hundred numbers instead of a pass over the whole schedule -- and the answer is
identical, not approximate. tests/test_fastpaths.py checks that against the
full forward pass on randomly generated schedules.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

import networkx as nx
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cascade import _activity_order, _d    # noqa: E402
from graph import MATERIAL                 # noqa: E402


def _in_edges(g: nx.DiGraph, act_id: str, dur: dict[str, int]) -> list[tuple[str, int]]:
    """(predecessor, start-to-start offset) for every link into an activity.

    Mirrors forward_pass line for line: typed links when the activity has
    them, plain finish-to-start `depends_on` otherwise.
    """
    node = g.nodes[act_id]
    d_v = dur[act_id]
    links = node.get("links")
    if not links:
        return [(u, dur[u]) for u in node["depends_on"]]
    out = []
    for ln in links:
        u = ln["pred"]
        if u not in dur:                 # forward_pass skips unscheduled preds
            continue
        lag, d_u = int(ln.get("lag_days", 0)), dur[u]
        kind = ln.get("type", "FS")
        if kind == "SS":
            w = lag
        elif kind == "FF":
            w = d_u + lag - d_v
        elif kind == "SF":
            w = lag - d_v
        else:                            # FS, and anything unrecognised
            w = d_u + lag
        out.append((u, w))
    return out


@dataclass
class HandoverModel:
    """Handover's start as a closed-form function of material arrivals."""
    handover: str
    base_start: int                      # date.toordinal() of the baseline start
    handover_duration: int
    floor: int                           # K: what planned starts alone force
    materials: list[str] = field(default_factory=list)   # those that can reach handover
    arrival: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=np.int64))
    reach: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=np.int64))
    index: dict[str, int] = field(default_factory=dict)

    def room(self, material_id: str) -> int | None:
        """Days this material can slip before handover moves; None if it can't reach it."""
        i = self.index.get(material_id)
        if i is None:
            return None
        return self.base_start - int(self.arrival[i] + self.reach[i])

    def slip_for(self, material_id: str, delay_days: int) -> int:
        """Handover slip, in days, if only this material arrives `delay_days` late."""
        r = self.room(material_id)
        return 0 if r is None else max(0, delay_days - r)

    def breaking_point(self, material_id: str, max_days: int) -> int | None:
        """Smallest whole-day delay that moves handover, if it is within max_days."""
        r = self.room(material_id)
        if r is None or r + 1 > max_days:
            return None
        return r + 1

    def starts(self, extra_days: np.ndarray) -> np.ndarray:
        """Handover start for many scenarios at once.

        extra_days has one row per scenario and one column per entry in
        `materials` (whole days late; negative = early).
        """
        if not self.materials:
            return np.full(extra_days.shape[0], self.floor, dtype=np.int64)
        latest = (self.arrival + self.reach + extra_days).max(axis=1)
        return np.maximum(self.floor, latest)


def handover_model(g: nx.DiGraph) -> HandoverModel:
    order = _activity_order(g)
    dur = {a: max(0, int(g.nodes[a]["duration_days"])) for a in order}
    h = g.graph["handover"]

    succ: dict[str, list[tuple[str, int]]] = {a: [] for a in order}
    for v in order:
        for u, w in _in_edges(g, v, dur):
            succ[u].append((v, w))

    # longest start-to-start path from each activity to handover
    lp: dict[str, int] = {h: 0}
    for u in reversed(order):
        if u == h:
            continue
        best = None
        for v, w in succ[u]:
            if v in lp and (best is None or w + lp[v] > best):
                best = w + lp[v]
        if best is not None:
            lp[u] = best

    floor = max(_d(g.nodes[a]["early_start"]).toordinal() + lp[a] for a in lp)

    needed_by: dict[str, list[str]] = {}
    for a in order:
        for m in g.nodes[a]["needs_materials"]:
            needed_by.setdefault(m, []).append(a)
    mats, arr, reach = [], [], []
    for m, node in g.nodes(data=True):
        if node.get("kind") != MATERIAL:
            continue
        ls = [lp[a] for a in needed_by.get(m, []) if a in lp]
        if ls:
            mats.append(m)
            arr.append(_d(node["expected_arrival"]).toordinal())
            reach.append(max(ls))
    arrival = np.array(arr, dtype=np.int64)
    reach_a = np.array(reach, dtype=np.int64)
    base = max(floor, int((arrival + reach_a).max())) if mats else floor
    return HandoverModel(handover=h, base_start=base, handover_duration=dur[h], floor=floor,
                         materials=mats, arrival=arrival, reach=reach_a,
                         index={m: i for i, m in enumerate(mats)})
