"""Turn a Primavera P6 schedule (.xer) -- and optionally a P&D log -- into a Foreman project.

    python scripts/xer_to_foreman.py SCHEDULE.xer --pd PD_LOG.csv --name "My Project"
    python scripts/xer_to_foreman.py SCHEDULE.xer --dry-run          # report only, save nothing

The conversion itself lives in src/importers, shared with the app's Import
screen; src/importers/xer.py documents what comes from where and what is
approximated. Without --pd, the schedule's own fabricate / deliver / procure
activities stand in for P&D items, with a placeholder confidence.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from importers import ImportProblem, build_import, format_report   # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("xer", type=Path)
    ap.add_argument("--pd", type=Path, help="P&D / procurement log (CSV or Excel)")
    ap.add_argument("--materials-from-schedule", action="store_true",
                    help="(the default without --pd; kept so older commands still run)")
    ap.add_argument("--name", help="project name in Foreman")
    ap.add_argument("--proj-id", help="XER proj_id, if the file holds several projects")
    ap.add_argument("--handover", help="activity code to treat as handover")
    ap.add_argument("--map", action="append", default=[], metavar="FIELD=Column",
                    help="pin a P&D field to a column, e.g. --map arrival='Promised Date'")
    ap.add_argument("--dry-run", action="store_true", help="print the report, save nothing")
    a = ap.parse_args()

    try:
        project, report = build_import(
            a.xer.name, a.xer.read_bytes(), project_id=a.proj_id, name=a.name, handover=a.handover,
            pd_filename=a.pd.name if a.pd else None, pd_data=a.pd.read_bytes() if a.pd else None,
            pd_overrides=dict(m.split("=", 1) for m in a.map))
    except ImportProblem as e:
        sys.exit(f"✗ {e}")
    print(format_report(report))
    if a.dry_run:
        print("(dry run — nothing saved)")
        return
    from projects import create_project
    print(f"\n✅ saved as project '{create_project(project)}' and made active — reload Foreman")


if __name__ == "__main__":
    main()
