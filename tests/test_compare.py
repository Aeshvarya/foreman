"""Comparing two updates of a schedule, on SYNTHETIC files only.

Covers both ways the versions arrive: two separate .xer exports, and one
database-style table that keeps the earlier upload's rows (is_active = FALSE)
next to the current ones.

Run:  python tests/test_compare.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from compare import compare                                   # noqa: E402
from importers import ImportProblem                           # noqa: E402
from importers.snapshots import pick_pair, snapshots          # noqa: E402

fails: list[str] = []


def check(label, cond, detail=""):
    (print(f"  ok   {label}") if cond
     else (fails.append(label), print(f"  FAIL {label}  {detail}")))


def xer(tasks, recalc):
    cols = ["task_id", "proj_id", "clndr_id", "task_type", "status_code", "task_code", "task_name",
            "act_start_date", "act_end_date", "early_start_date", "early_end_date", "total_float_hr_cnt"]
    lines = ["ERMHDR\t15.2", "%T\tPROJECT", "%F\tproj_id\tproj_short_name\tlast_recalc_date",
             f"%R\t1\tAlpha\t{recalc}", "%T\tCALENDAR", "%F\tclndr_id\tday_hr_cnt", "%R\tC1\t8",
             "%T\tTASK", "%F\t" + "\t".join(cols)]
    for t in tasks:
        lines.append("%R\t" + "\t".join(str(t.get(c, "")) for c in cols))
    return "\n".join(lines).encode()


def t(code, name, es, ee, tf_days, typ="TT_Task", status="TK_NotStart"):
    return dict(task_id=code, proj_id="1", clndr_id="C1", task_type=typ, status_code=status,
                task_code=code, task_name=name, early_start_date=f"{es} 08:00",
                early_end_date=f"{ee} 17:00", total_float_hr_cnt=tf_days * 8)


OLD = xer([t("A1", "Excavate", "2026-03-02", "2026-03-06", 0),
           t("A2", "Deliver Switchgear", "2026-03-09", "2026-03-13", 10),
           t("A3", "Install Switchgear", "2026-03-16", "2026-03-20", 10),
           t("A4", "Paint", "2026-03-16", "2026-03-18", 4),
           t("A9", "Final Completion", "2026-04-01", "2026-04-01", 0, typ="TT_FinMile")], "2026-03-01")
NEW = xer([t("A1", "Excavate", "2026-03-02", "2026-03-06", 0),
           t("A2", "Deliver Switchgear", "2026-03-19", "2026-03-23", 0),      # +10d, float gone
           t("A3", "Install Switchgear", "2026-03-24", "2026-03-30", 0),      # +10d
           t("A5", "Commissioning", "2026-03-31", "2026-04-02", 0),           # new
           t("A9", "Final Completion", "2026-04-06", "2026-04-06", 0, typ="TT_FinMile")], "2026-03-15")

print("Two .xer updates")
o, n = pick_pair(snapshots("old.xer", OLD), snapshots("new.xer", NEW), None, None, same_file=False)
r = compare(o, n)
c = r["counts"]
check("activities matched by id", (c["matched"], c["added"], c["removed"]) == (4, 1, 1), c)
check("three finish later (two deliveries +10d, completion +5d), median 10",
      c["later"] == 3 and r["median_shift_days"] == 10, (c, r["median_shift_days"]))
check("completion moved +5 days", r["completion"]["shift_days"] == 5, r["completion"])
check("float read in days from hours", r["top_float_lost"][0]["old_float"] == 10.0, r["top_float_lost"][:1])
check("two became critical", c["newly_critical"] == 2, c)
check("the delivery that moved is listed first",
      [x["id"] for x in r["deliveries"]] == ["A2"], r["deliveries"])
check("headline says it in one line",
      r["headline"].startswith("3 of 4 activities finish later") and "completion moved +5 days" in r["headline"],
      r["headline"])

print("\nOne table holding both uploads")
TABLE = ("project_id,project,activity_id,activity_name,start,finish,total_float,is_active\n"
         "p1,Alpha - 10 Mar,A1,Excavate,2026-03-02,2026-03-06,0,FALSE\n"
         "p1,Alpha - 10 Mar,A2,Deliver Switchgear,2026-03-09,2026-03-13,10,FALSE\n"
         "p1,Alpha - 10 Mar,A9,Final Completion,2026-04-01,2026-04-01,0,FALSE\n"
         "p1,Alpha - 28 Apr CURRENT,A1,Excavate,2026-03-02,2026-03-06,0,TRUE\n"
         "p1,Alpha - 28 Apr CURRENT,A2,Deliver Switchgear,2026-03-12,2026-03-16,7,TRUE\n"
         "p1,Alpha - 28 Apr CURRENT,A9,Final Completion,2026-04-01,2026-04-01,0,TRUE\n"
         "p2,Other job,B1,Survey,2026-05-01,2026-05-02,3,TRUE\n").encode()
snaps = snapshots("extract.csv", TABLE)
o, n = pick_pair(snaps, snaps, None, None, same_file=True)
check("earlier upload is 'older', current one is 'newer'",
      (o.label, n.label) == ("Alpha - 10 Mar", "Alpha - 28 Apr CURRENT"), (o.label, n.label))
r = compare(o, n)
check("delivery +3 days and 3 days of float lost",
      r["deliveries"] and r["deliveries"][0]["shift_days"] == 3 and r["deliveries"][0]["new_float"] == 7,
      r["deliveries"])
check("completion held", r["completion"]["shift_days"] == 0 and "completion held" in r["headline"])

print("\nRefusals")
try:
    pick_pair(snapshots("one.xer", OLD), snapshots("one.xer", OLD), None, None, same_file=True)
    check("one version and no second file is refused", False)
except ImportProblem as e:
    check("one version and no second file is refused, saying add the other update", "second file" in str(e))

print(f"\n{'ALL COMPARE CHECKS PASSED ✓' if not fails else f'{len(fails)} FAILED: {fails}'}")
sys.exit(1 if fails else 0)
