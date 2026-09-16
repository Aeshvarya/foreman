"""Turn a P6 activity table (CSV or Excel, one row per activity) into a Foreman project.

    python scripts/p6_csv_to_foreman.py EXPORT.csv --list                 # what's inside
    python scripts/p6_csv_to_foreman.py EXPORT.csv --project "Warehouse" --dry-run
    python scripts/p6_csv_to_foreman.py EXPORT.csv --project "Warehouse" --name "Demo A"

Use this when all you have is the activity table. If you have the .xer, use
xer_to_foreman.py instead: the .xer carries the real predecessor links. The
conversion lives in src/importers (shared with the app's Import screen);
src/importers/activity_table.py explains how links and room are inferred.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from importers import ImportProblem, build_import, format_report   # noqa: E402
from importers.activity_table import read_activity_table, table_projects   # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("table", type=Path)
    ap.add_argument("--list", action="store_true", help="list the projects in the file and stop")
    ap.add_argument("--project", help="project id (or its start) or part of the project name")
    ap.add_argument("--name", help="project name in Foreman")
    ap.add_argument("--handover", help="activity id to treat as handover")
    ap.add_argument("--pd", type=Path, help="P&D log (CSV or Excel) instead of schedule-derived materials")
    ap.add_argument("--map", action="append", default=[], metavar="FIELD=Column")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    data = a.table.read_bytes()
    try:
        if a.list or not a.project:
            for p in table_projects(read_activity_table(a.table.name, data)[0]):
                print(f"  {p['id'][:12]:12}  {p['activities']:>6} activities  {p['name'][:60]}")
            return
        project, report = build_import(
            a.table.name, data, project_id=a.project, name=a.name, handover=a.handover,
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
