"""Reading intent from activity names.

Which activities stand for a physical item arriving on site, what item each one
is about, and which milestone the project is judged against. Used when there is
no P&D log to say so directly.
"""
from __future__ import annotations

import re

# Activities that stand for a physical item arriving on site.
MATERIAL_RE = re.compile(r"deliver|fabricat|\bfab\b|manufactur|procurement|\bship|furnish", re.I)
NOT_MATERIAL_RE = re.compile(r"set ?up|general|admin|\bntp\b|\blog\b|schedule|submit|approv|"
                             r"release|drawing", re.I)
# Words that describe the step rather than the item, so "Fab/ Deliver - Foundation
# Rebar" and "1st Delivery/ ROJ - Foundation Rebar" both name "Foundation Rebar".
STEP_WORDS = re.compile(r"\b(?:fab|fabricate|fabrication|deliver|delivered|delivery|deliveries|"
                        r"rig|ship|shipping|procure|procurement|manufacture|manufacturing|"
                        r"furnish|1st|2nd|roj)\b", re.I)
LEAD_WEEKS = re.compile(r"\(\s*(\d+)\s*(?:wks?|weeks?)\s*\)", re.I)
# The milestone a project is judged against; delivery milestones can finish later.
COMPLETION_RE = re.compile(r"(final|substantial|project|contract)\s+completion|handover|"
                           r"certificate of occupancy|\bturnover\b", re.I)


def is_delivery(activity_name: str) -> bool:
    return bool(MATERIAL_RE.search(activity_name)) and not NOT_MATERIAL_RE.search(activity_name)


def item_name(activity_name: str) -> str:
    """The physical item an activity is about, without its step words or lead time."""
    s = STEP_WORDS.sub(" ", LEAD_WEEKS.sub(" ", activity_name))
    s = re.sub(r"^[\s\d.\-/&,]*(?:and\b)?[\s\-/&,]*", "", s)   # "23 - ", "/ - ", "and "
    s = re.sub(r"\s+", " ", s).strip(" -/&,.")
    return s or activity_name.strip()


def lead_time_days(activity_name: str, fallback_days: int) -> int:
    """A lead time written into the name, e.g. '(60 wks)', beats the activity's length."""
    weeks = LEAD_WEEKS.search(activity_name)
    return int(weeks.group(1)) * 7 if weeks else max(fallback_days, 1)
