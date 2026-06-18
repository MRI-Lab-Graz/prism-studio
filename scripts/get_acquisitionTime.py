#!/usr/bin/env python3
"""Extract T1w acquisition datetimes per subject/session from a BIDS rawdata tree
and report the time-of-day difference between ses-1 and ses-2."""

import json
import re
from datetime import datetime, time
from pathlib import Path

from openpyxl import Workbook

RAWDATA = Path("/Volumes/Thunder/129_PK01/rawdata")
OUTFILE = Path("/Volumes/Thunder/129_PK01/code/acquisition_times.tsv")
XLSX_OUTFILE = OUTFILE.with_suffix(".xlsx")

SUB_RE = re.compile(r"sub-(\d+)")
SES_RE = re.compile(r"ses-(\d+)")

# Some DICOM-derived JSONs report seconds as a single digit (e.g. "12:18:2.12"
# instead of "12:18:02.12"), which datetime.fromisoformat rejects outright.
TIME_SECONDS_RE = re.compile(r"(\d{2}:\d{2}):(\d)([.:]|$)")


def pad_seconds(dt_str: str) -> str:
    return TIME_SECONDS_RE.sub(r"\g<1>:0\2\3", dt_str)


def find_t1w_jsons():
    return sorted(RAWDATA.glob("sub-*/ses-*/anat/*T1w.json"))


def time_of_day_diff_minutes(t1: time, t2: time) -> float:
    """Absolute difference between two times-of-day, in minutes (0-720 range)."""
    m1 = t1.hour * 60 + t1.minute + t1.second / 60
    m2 = t2.hour * 60 + t2.minute + t2.second / 60
    diff = abs(m1 - m2)
    return min(diff, 1440 - diff)


def main():
    records = {}  # (sub, ses) -> datetime

    for jf in find_t1w_jsons():
        sub_m = SUB_RE.search(jf.parts[-4])
        ses_m = SES_RE.search(jf.parts[-3])
        if not sub_m or not ses_m:
            continue
        sub = f"sub-{sub_m.group(1)}"
        ses = f"ses-{ses_m.group(1)}"

        with open(jf) as f:
            data = json.load(f)

        dt_str = data.get("AcquisitionDateTime")
        if dt_str:
            dt_str = dt_str.strip()
        else:
            t_str = data.get("AcquisitionTime")
            acq_date = data.get("AcquisitionDate") or data.get("StudyDate")
            dt_str = f"{acq_date}T{t_str.strip()}" if t_str and acq_date else None

        dt = None
        if dt_str:
            try:
                dt = datetime.fromisoformat(pad_seconds(dt_str))
            except ValueError:
                dt = None

        records[(sub, ses)] = dt

    subs = sorted({s for s, _ in records}, key=lambda x: int(x.split("-")[1]))

    header = ["subject_id", "acq_time_ses-1", "acq_time_ses-2", "acq_time_ses-3",
               "diff_ses1_ses2_hh:mm", "diff_ses1_ses2_min"]
    rows = [header]

    for sub in subs:
        dt1 = records.get((sub, "ses-1"))
        dt2 = records.get((sub, "ses-2"))
        dt3 = records.get((sub, "ses-3"))

        t1_str = dt1.time().isoformat(timespec="seconds") if dt1 else "n/a"
        t2_str = dt2.time().isoformat(timespec="seconds") if dt2 else "n/a"
        t3_str = dt3.time().isoformat(timespec="seconds") if dt3 else "n/a"

        if dt1 and dt2:
            diff_min = time_of_day_diff_minutes(dt1.time(), dt2.time())
            total_rounded = int(round(diff_min))
            h, m = divmod(total_rounded, 60)
            diff_hhmm = f"{h:02d}:{m:02d}"
            diff_min_str = f"{diff_min:.1f}"
        else:
            diff_hhmm = "n/a"
            diff_min_str = "n/a"

        rows.append([sub, t1_str, t2_str, t3_str, diff_hhmm, diff_min_str])

    OUTFILE.write_text("\n".join("\t".join(row) for row in rows) + "\n")

    wb = Workbook()
    ws = wb.active
    ws.title = "acquisition_times"
    for row in rows:
        ws.append(row)
    wb.save(XLSX_OUTFILE)

    print(f"Wrote {len(subs)} subjects to {OUTFILE} and {XLSX_OUTFILE}")


if __name__ == "__main__":
    main()
