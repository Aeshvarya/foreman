"""Importers: real-world schedule exports in, a project that reproduces P6 out.

Every file here is SYNTHETIC -- built in this test, no customer data. Each one
carries a quirk real exports have, and the conversion has to survive it:

  .xer        finished work that ran out of sequence, a start-to-start link
              from work already in progress, starts stamped at the minute the
              working day ends, a negative lag across a weekend, level-of-effort
              and WBS rows, a link to another project, no CALENDAR table
  CSV         title rows above the header, P6's " A" (actual) and "*"
              (constrained) date markers, P6 display-name headers
  Excel       P6's two header rows (field names, then display names), real dates
  P&D log     a title row, customer column names, an item naming no activity,
              and a delivery already running late

The bar for every schedule: before anything is delayed, Foreman starts every
activity on its P6 date.

Run:  python tests/test_importers.py
"""
import io
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from graph import build_graph                         # noqa: E402
from importers import ImportProblem, build_import      # noqa: E402
from importers.tables import to_date                   # noqa: E402
from projects import _normalise                        # noqa: E402
from risk import breaking_point                        # noqa: E402

fails: list[str] = []


def check(label, cond, detail=""):
    (print(f"  ok   {label}") if cond
     else (fails.append(label), print(f"  FAIL {label}  {detail}")))


def raises(fn) -> str | None:
    try:
        fn()
    except ImportProblem as e:
        return str(e)
    return None


# ------------------------------------------------------------------ builders
def xer(tables: dict[str, list[dict]]) -> bytes:
    lines = ["ERMHDR\t15.2\t2026-03-30\tProject\tadmin"]
    for name, rows in tables.items():
        cols = list(rows[0].keys())
        lines += [f"%T\t{name}", "%F\t" + "\t".join(cols)]
        lines += ["%R\t" + "\t".join(str(r.get(c, "")) for c in cols) for r in rows]
    lines.append("%E")
    return "\r\n".join(lines).encode()


def task(tid, pid, name, es="", ee="", *, typ="TT_Task", status="TK_NotStart",
         act_s="", act_e="", wbs="W1"):
    return dict(task_id=tid, proj_id=pid, wbs_id=wbs, clndr_id="C1", task_type=typ,
                status_code=status, task_code=tid, task_name=name,
                act_start_date=act_s, act_end_date=act_e,
                early_start_date=es, early_end_date=ee,
                target_start_date="", target_end_date="")


def link(i, succ, pred, kind="PR_FS", lag_hr=0, proj="1", pred_proj="1"):
    return dict(task_pred_id=i, task_id=succ, pred_task_id=pred, proj_id=proj,
                pred_proj_id=pred_proj, pred_type=kind, lag_hr_cnt=lag_hr)


D = "2026-{}"
TASKS = [
    # finished, and T2 started before T1 closed: out of sequence
    task("T1", "1", "Mobilize", status="TK_Complete", act_s=D.format("03-02 07:00"), act_e=D.format("03-06 15:30")),
    task("T2", "1", "Excavate", status="TK_Complete", act_s=D.format("03-05 07:00"), act_e=D.format("03-13 15:30")),
    # in progress since 16 Mar; P6 places the remaining work from the 1 Apr data date
    task("T3", "1", "Pour Foundations", D.format("04-01 07:00"), D.format("04-10 15:30"),
         status="TK_Active", act_s=D.format("03-16 07:00")),
    task("T4", "1", "Erect Steel", D.format("04-06 07:00"), D.format("04-24 15:30")),
    task("T5", "1", "Fabricate Switchgear", D.format("04-06 07:00"), D.format("05-01 15:30")),
    task("T6", "1", "Deliver Switchgear", D.format("05-04 07:00"), D.format("05-05 15:30")),
    # stamped at 15:30 -- the minute T6's day ends -- so it really starts next morning
    task("T7", "1", "Install Switchgear", D.format("05-05 15:30"), D.format("05-12 15:30")),
    task("T8", "1", "Energize", D.format("05-13 07:00"), D.format("05-19 15:30")),
    # -3 working days from Tue 19 May lands on Fri 15 May: a weekend inside the lag
    task("T9", "1", "Punch List", D.format("05-15 07:00"), D.format("05-22 15:30")),
    task("T10", "1", "Final Completion", D.format("05-22 15:30"), D.format("05-22 15:30"), typ="TT_FinMile"),
    task("T11", "1", "Site Supervision", D.format("03-02 07:00"), D.format("05-22 15:30"), typ="TT_LOE"),
    task("T12", "1", "Phase summary", D.format("03-02 07:00"), D.format("05-22 15:30"), typ="TT_WBS"),
    task("T13", "1", "Deliver Rebar", status="TK_Complete", act_s=D.format("03-09 07:00"), act_e=D.format("03-10 15:30")),
    # a second, smaller project in the same file
    task("U1", "2", "Survey", D.format("06-01 07:00"), D.format("06-03 15:30")),
    task("U2", "2", "Deliver Pumps", D.format("06-04 07:00"), D.format("06-05 15:30")),
    task("U3", "2", "Annex Complete", D.format("06-05 15:30"), D.format("06-05 15:30"), typ="TT_FinMile"),
]
PREDS = [
    link(1, "T2", "T1"),                            # into finished work: ignored
    link(2, "T3", "T2"),
    link(3, "T4", "T3", "PR_SS", 80),               # SS +10d from an activity in progress
    link(4, "T6", "T5"),
    link(5, "T7", "T6"),
    link(6, "T8", "T7"),
    link(7, "T9", "T8", "PR_FS", -24),              # -3 working days, across a weekend
    link(8, "T10", "T9"),
    link(9, "T8", "T4"),
    link(10, "T11", "T1"),                          # to a level-of-effort row: dropped
    link(11, "T4", "U1", proj="1", pred_proj="2"),  # to another project: dropped
    link(12, "U2", "U1", proj="2", pred_proj="2"),
    link(13, "U3", "U2", proj="2", pred_proj="2"),
]
PROJECTS = [{"proj_id": "1", "proj_short_name": "Alpha Tower"},
            {"proj_id": "2", "proj_short_name": "Beta Annex"}]
XER_FILE = xer({"PROJECT": PROJECTS, "TASK": TASKS, "TASKPRED": PREDS})


# ---------------------------------------------------------------- .xer
print(".xer with every quirk at once")
proj, rep = build_import("alpha.xer", XER_FILE)
st = rep["stats"]
check("biggest project chosen by default", rep["chosen"] == "1", rep["chosen"])
check("both projects listed", [p["name"] for p in rep["projects"]] == ["Alpha Tower", "Beta Annex"])
check("starting schedule reproduces P6", rep["handover"]["matches_p6"],
      f"{rep['handover']['moved_before_any_delay']} moved")
check("handover is the finish milestone, on P6's date",
      (rep["handover"]["id"], rep["handover"]["p6_finish"]) == ("T10", "2026-05-22"), rep["handover"])
check("level-of-effort and WBS rows dropped", st.get("dropped_TT_LOE") == 1 and st.get("dropped_TT_WBS") == 1, st)
check("link into finished work ignored", st.get("links_into_completed") == 1, st)
check("link to another project dropped", st.get("links_cross_project") == 1, st)
check("start-to-start link counted from the actual start", st.get("start_links_from_actual_start") == 1, st)
check("a start at the day's end moves to next morning", st.get("start_at_day_end") == 1, st)
check("weekend lag trimmed to P6's dates", st.get("lags_trimmed_to_p6", 0) >= 1, st)
check("switchgear fab + delivery become ONE item; finished rebar isn't tracked",
      [m["name"] for m in proj["materials"]] == ["Switchgear"] and st.get("materials_already_done") == 1,
      [m["name"] for m in proj["materials"]])
check("missing CALENDAR table is said out loud", any("CALENDAR" in n for n in rep["notes"]))
check("no P&D log is said out loud", any("No P&D log" in w for w in rep["warnings"]))
check("the saved project keeps where it came from", proj["import"]["source"] == "alpha.xer")

g = build_graph(_normalise(proj))
bp = breaking_point(g, proj["materials"][0]["id"])
check("the schedule actually cascades (switchgear has a breaking point)", bp is not None, bp)

_, rep2 = build_import("alpha.xer", XER_FILE, project_id="beta")
check("second project picked by name", rep2["chosen"] == "2" and rep2["handover"]["matches_p6"], rep2["chosen"])

loop = xer({"PROJECT": PROJECTS[:1],
            "TASK": [task("A", "1", "Deliver Pumps", D.format("06-01 07:00"), D.format("06-02 15:30")),
                     task("B", "1", "Install Pumps", D.format("06-03 07:00"), D.format("06-04 15:30")),
                     task("Z", "1", "Done", D.format("06-04 15:30"), D.format("06-04 15:30"), typ="TT_FinMile")],
            "TASKPRED": [link(1, "B", "A"), link(2, "A", "B"), link(3, "Z", "B")]})
_, rep3 = build_import("loop.xer", loop)
check("a loop is broken and reported, not a crash", any("loop" in w for w in rep3["warnings"]), rep3["warnings"])


# ---------------------------------------------------------------- P&D log
print("\nP&D log with a title row and a late delivery")
PD = (b"Procurement Log - Alpha Tower\n\n"
      b"Item Description,Vendor Name,P6 Activity ID,Required On Site Date,Forecast Delivery Date,Status\n"
      b"Switchgear,Volt Co,T7,2026-05-06,2026-05-06,Approved\n"
      b"Steel beams,SteelCo,T4,04/06/2026,05/04/2026,In Transit\n"
      b"Pumps,AquaCo,ZZZ999,2026-05-01,,Pending review\n"
      b"Rebar,SteelCo,T13,2026-03-09,2026-04-30,Delivered\n")      # feeds finished work
proj, rep = build_import("alpha.xer", XER_FILE, pd_filename="pd.csv", pd_data=PD)
mats = {m["name"]: m for m in proj["materials"]}
check("every P&D row becomes an item", sorted(mats) == ["Pumps", "Rebar", "Steel beams", "Switchgear"], sorted(mats))
check("an item feeding finished work can't push history",
      rep["stats"].get("materials_feeds_started_work") == 1
      and not any(mats["Rebar"]["id"] in a["needs_materials"] for a in proj["activities"]), rep["stats"])
check("status sets confidence (in transit = 0.90)", mats["Steel beams"]["confidence"] == 0.90
      and mats["Steel beams"]["shipment_status"] == "in_transit")
check("item naming no activity is flagged", any("don't name an activity" in w for w in rep["warnings"]))
check("late forecast pushing handover is reported as a finding",
      any("already push handover" in w for w in rep["warnings"]), rep["warnings"])
check("the P6 check ignores deliveries (still matches)", rep["handover"]["matches_p6"])


# ------------------------------------------------------------ activity table
print("\nActivity table (CSV) with title rows and P6 date markers")
CSV = (b"Warehouse schedule export\n\n"
       b"Activity ID,Activity Name,Original Duration(d),Start,Finish,Total Float(d),Free Float(d),WBS,Activity Status\n"
       b"A100,Mobilize,5,02-Mar-26 A,06-Mar-26 A,0,0,W1,Completed\n"
       b"A110,Excavate,5,09-Mar-26,13-Mar-26,10,0,W1,Not Started\n"
       b"A120,Fab/ Deliver - Rebar,10,09-Mar-26*,20-Mar-26,3,0,W2,Not Started\n"
       b"A130,Place Rebar,5,23-Mar-26,27-Mar-26,3,0,W2,Not Started\n"
       b"A140,Deliver Switchgear (12 wks),3,16-Mar-26,18-Mar-26,20,20,W3,Not Started\n"
       b"A150,Substantial Completion,0,30-Mar-26,30-Mar-26,0,0,W9,Not Started\n")


def check_table(label, proj, rep):
    check(f"{label}: all six activities read", rep["counts"]["activities"] == 6, rep["counts"])
    check(f"{label}: starting schedule reproduces P6", rep["handover"]["matches_p6"])
    check(f"{label}: completion milestone is handover", rep["handover"]["id"] == "A150", rep["handover"])
    check(f"{label}: inferred links are flagged", any("no predecessor links" in w for w in rep["warnings"]))
    names = {m["name"]: m for m in proj["materials"]}
    check(f"{label}: two items, named by what arrives", sorted(names) == ["Rebar", "Switchgear"], sorted(names))
    check(f"{label}: '(12 wks)' read as the lead time", names.get("Switchgear", {}).get("lead_time_days") == 84)
    g = build_graph(_normalise(proj))
    ids = {m["name"]: m["id"] for m in proj["materials"]}
    check(f"{label}: rebar can slip its 3 days of float, not a 4th",
          breaking_point(g, ids["Rebar"]) == 4, breaking_point(g, ids["Rebar"]))
    check(f"{label}: switchgear can slip 20 days", breaking_point(g, ids["Switchgear"]) == 21,
          breaking_point(g, ids["Switchgear"]))


check_table("CSV", *build_import("warehouse.csv", CSV))

print("\nActivity table (Excel) with P6's two header rows")
from openpyxl import Workbook                              # noqa: E402

wb = Workbook()
ws = wb.active
ws.append(["task_code", "task_name", "target_drtn_hr_cnt", "start_date", "end_date",
           "total_float_hr_cnt", "free_float_hr_cnt", "wbs_id", "status_code"])
ws.append(["Activity ID", "Activity Name", "Original Duration(d)", "Start", "Finish",
           "Total Float(d)", "Free Float(d)", "WBS", "Activity Status"])
for line in CSV.decode().splitlines()[3:]:
    c = line.split(",")
    ws.append([c[0], c[1], float(c[2]), datetime.strptime(c[3].rstrip(" A*"), "%d-%b-%y"),
               datetime.strptime(c[4].rstrip(" A*"), "%d-%b-%y"), float(c[5]), float(c[6]), c[7], c[8]])
buf = io.BytesIO()
wb.save(buf)
check_table("Excel", *build_import("warehouse.xlsx", buf.getvalue()))


# ---------------------------------------------------------------- refusals
print("\nFiles it must refuse, with a reason a person can act on")
check("a PDF is refused", raises(lambda: build_import("plan.pdf", b"%PDF-1.4")) is not None)
check("old .xls is refused with a way out",
      "xlsx" in (raises(lambda: build_import("old.xls", b"\xd0\xcf\x11\xe0")) or ""))
check("an .xer with no activities is refused",
      raises(lambda: build_import("empty.xer", xer({"PROJECT": PROJECTS}))) is not None)
check("a table with no header is refused, naming the columns it needs",
      "activity_id" in (raises(lambda: build_import("notes.csv", b"hello\nworld\n")) or ""))
NO_DELIVERIES = CSV.replace(b"Fab/ Deliver - Rebar", b"Tie Rebar").replace(b"Deliver Switchgear", b"Wire Panels")
check("nothing to track and no P&D log is refused, saying add the P&D log",
      "P&D" in (raises(lambda: build_import("w.csv", NO_DELIVERIES)) or ""))


# ---------------------------------------------------------------- dates
print("\nDates the way exports write them")
for raw, want in [("2026-04-28", date(2026, 4, 28)), ("28-Apr-26 A", date(2026, 4, 28)),
                  ("28-Apr-26*", date(2026, 4, 28)), ("04/28/2026", date(2026, 4, 28)),
                  ("2026-03-20 18:01:52.421821+00", date(2026, 3, 20)),
                  (datetime(2026, 4, 28, 8), date(2026, 4, 28)), ("", None), ("TBD", None)]:
    check(f"{raw!r} -> {want}", to_date(raw) == want, to_date(raw))

print(f"\n{'ALL IMPORTER CHECKS PASSED ✓' if not fails else f'{len(fails)} FAILED: {fails}'}")
sys.exit(1 if fails else 0)
