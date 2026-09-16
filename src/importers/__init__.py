"""Turning real schedule exports into Foreman projects.

    from importers import build_import, ImportProblem
    project, report = build_import("schedule.xer", data, pd_filename="pd.xlsx", pd_data=pd)
"""
from .core import FORMAT_LABEL, build_import, detect_format, format_report   # noqa: F401
from .tables import ImportProblem                                            # noqa: F401
