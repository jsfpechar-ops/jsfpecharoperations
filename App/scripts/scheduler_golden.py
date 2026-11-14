"""Write go/internal/scheduler/testdata/python_schedule.json from the real Python.

Run from App/ (create the venv first if missing:
python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt):

    .venv/bin/python scripts/scheduler_golden.py

It calls the real app.scheduler.start() with every job kind on the queue (the
configuration UBYHOST_SCHEDULER=go requires) and a recording stand-in for
APScheduler's BackgroundScheduler, so every add_job call is captured exactly as
scheduler.py makes it: id, trigger type, trigger arguments and an explicit
first run time. Nothing is enqueued and no database is opened. For each
captured enqueue job it then builds the real APScheduler trigger in the
scheduler's time zone and lists the first FIRES fire times after each instant
in STARTS, the way APScheduler computes them with no misfire (first run: the
explicit next_run_time, else trigger.get_next_fire_time(None, start); then
trigger.get_next_fire_time(previous, previous)). The starts sit just before
both 2026 daylight saving changes in Europe/Prague and a day before each, on
a plain winter day exactly at a cron time, and a millisecond before one.
go/internal/scheduler/parity_test.go replays the same starts in Go and
compares every fire time and every trigger argument.
"""

from __future__ import annotations

import functools
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

APP = Path(__file__).resolve().parents[1]
OUT = APP.parent / "go" / "internal" / "scheduler" / "testdata" / "python_schedule.json"

FIRES = 30
# Local wall times in the scheduler's zone (Europe/Prague).
STARTS = [
    (2026, 3, 29, 1, 47, 13, 250000),  # 02:00 CET jumps to 03:00 CEST this night
    (2026, 10, 25, 1, 47, 13, 250000),  # 03:00 CEST falls back to 02:00 CET this night
    (2026, 3, 28, 1, 47, 13, 250000),  # the day before: cron runs cross the change
    (2026, 10, 24, 1, 47, 13, 250000),  # the day before: cron runs cross the change
    (2026, 1, 15, 6, 0, 0, 0),  # exactly at the billing cron time
    (2026, 7, 1, 4, 14, 59, 999000),  # a millisecond before the stripe_sweep cron time
]
JOB_OPTIONS = {"id", "max_instances", "coalesce", "next_run_time", "misfire_grace_time", "replace_existing"}

os.environ.setdefault("UBYHOST_DATA_DIR", tempfile.mkdtemp(prefix="ubyhost-scheduler-golden-"))
# The golden holds the defaults; parity_test.go checks the two variables apart.
os.environ.pop("UBYHOST_ICAL_POLL_MINUTES", None)
os.environ.pop("UBYHOST_SUBMIT_SWEEP_MINUTES", None)
sys.path.insert(0, str(APP))

from apscheduler.triggers.cron import CronTrigger  # noqa: E402
from apscheduler.triggers.interval import IntervalTrigger  # noqa: E402

from app import config, jobqueue, scheduler  # noqa: E402


class Recorder:
    """Stands in for BackgroundScheduler: records add_job, starts nothing."""

    def __init__(self, timezone=None):
        self.timezone = timezone
        self.jobs = []
        self.running = True

    def add_job(self, func, trigger, **kwargs):
        self.jobs.append((func, trigger, kwargs))

    def start(self):
        pass

    def shutdown(self, wait=True):
        self.running = False


def capture():
    config.ENABLE_SCHEDULER = True
    config.DB_BACKEND = "postgresql"
    config.JOB_QUEUE_KINDS = frozenset(scheduler.JOB_KINDS)
    config.GO_JOB_KINDS = frozenset({"deadlines"})
    scheduler.BackgroundScheduler = Recorder
    called_at = datetime.now(timezone.utc)
    if not scheduler.start():
        sys.exit("STOP: scheduler.start() returned False")
    recorder = scheduler._scheduler
    scheduler._scheduler = None
    return recorder, called_at


def utc(dt):
    return dt.astimezone(timezone.utc).isoformat(timespec="microseconds")


def main() -> int:
    recorder, called_at = capture()
    tz = ZoneInfo(recorder.timezone)
    jobs = []
    for func, trigger, kwargs in recorder.jobs:
        kind = kwargs["id"]
        if kind == "job_queue":
            continue
        if not (isinstance(func, functools.partial) and func.func is jobqueue.enqueue and func.args == (kind,)):
            sys.exit(f"STOP: {kind} does not enqueue")
        args = {k: v for k, v in kwargs.items() if k not in JOB_OPTIONS}
        first_delay = None
        if "next_run_time" in kwargs:
            first_delay = round((kwargs["next_run_time"] - called_at).total_seconds())
        jobs.append(
            {
                "kind": kind,
                "trigger": trigger,
                "args": args,
                "first_delay_seconds": first_delay,
                "max_instances": kwargs.get("max_instances"),
                "coalesce": kwargs.get("coalesce"),
            }
        )
    windows = []
    for parts in STARTS:
        start = datetime(*parts, tzinfo=tz)
        out = []
        for job in jobs:
            if job["trigger"] == "interval":
                trig = IntervalTrigger(**job["args"], timezone=tz, start_date=start + timedelta(**job["args"]))
            elif job["trigger"] == "cron":
                trig = CronTrigger(**job["args"], timezone=tz)
            else:
                sys.exit(f"STOP: unknown trigger {job['trigger']}")
            if job["first_delay_seconds"] is not None:
                fire = start + timedelta(seconds=job["first_delay_seconds"])
            else:
                fire = trig.get_next_fire_time(None, start)
            fires = []
            for _ in range(FIRES):
                fires.append({"utc": utc(fire), "local": fire.astimezone(tz).isoformat(timespec="microseconds")})
                fire = trig.get_next_fire_time(fire, fire)
            out.append({"kind": job["kind"], "fires": fires})
        windows.append({"start_utc": utc(start), "start_local": start.isoformat(timespec="microseconds"), "jobs": out})
    data = {
        "source": "App/app/scheduler.py start(), APScheduler triggers",
        "timezone": str(recorder.timezone),
        "job_kinds": sorted(scheduler.JOB_KINDS),
        "job_intervals": scheduler.job_intervals(),
        "jobs": jobs,
        "windows": windows,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
