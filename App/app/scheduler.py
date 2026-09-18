"""Background jobs: calendar polling, automatic submission, deadline watch."""
from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from . import claim, config, db, icalsync, mail, passport_photos, reporting

log = logging.getLogger("ubyhost.scheduler")
_scheduler = None


def _job_sync_calendars() -> None:
    try:
        totals = icalsync.sync_all()
        log.info("calendar sync: %s", totals)
    except Exception:
        log.exception("calendar sync failed")


def _job_submit() -> None:
    try:
        summary = reporting.sweep()
        if summary["submitted"] or summary["failed"]:
            log.info("ubyport sweep: %s", summary)
    except Exception:
        log.exception("ubyport sweep failed")


def _job_deadlines() -> None:
    try:
        raised = reporting.check_deadlines()
        if raised:
            log.info("deadline watch raised %s alert(s)", raised)
    except Exception:
        log.exception("deadline watch failed")


def _job_mail() -> None:
    try:
        claim.expire_holds()
        summary = mail.drain()
        if summary["sent"] or summary["failed"]:
            log.info("mail drain: %s", summary)
        reminders = claim.sweep_reminders()
        if any(reminders.values()):
            log.info("mail reminders: %s", reminders)
        purged = mail.purge_old()
        if purged:
            log.info("mail purge deleted %s row(s)", purged)
    except Exception:
        log.exception("mail drain failed")


def _job_photo_sweep() -> None:
    """Delete passport images the host never got round to verifying."""
    try:
        removed = passport_photos.purge_stale()
        if removed:
            log.info("passport photo sweep deleted %s file(s)", removed)
    except Exception:
        log.exception("passport photo sweep failed")


def start() -> None:
    global _scheduler
    if _scheduler or not config.ENABLE_SCHEDULER:
        return
    _scheduler = BackgroundScheduler(timezone=config.TIMEZONE)
    _scheduler.add_job(
        _job_sync_calendars, "interval", minutes=config.ICAL_POLL_MINUTES,
        id="ical", next_run_time=None, max_instances=1, coalesce=True,
    )
    _scheduler.add_job(
        _job_submit, "interval", minutes=config.SUBMIT_SWEEP_MINUTES,
        id="submit", max_instances=1, coalesce=True,
    )
    _scheduler.add_job(
        _job_deadlines, "interval", minutes=30, id="deadlines", max_instances=1, coalesce=True,
    )
    _scheduler.add_job(
        _job_mail, "interval", minutes=5, id="mail", max_instances=1, coalesce=True,
    )
    _scheduler.add_job(
        _job_photo_sweep, "interval", hours=12, id="photo_sweep",
        max_instances=1, coalesce=True, next_run_time=_soon(),
    )
    _scheduler.start()
    # Kick off a first calendar sync shortly after boot rather than waiting
    # a full interval, but only if feeds actually exist.
    if db.query_one("SELECT 1 AS x FROM ical_feed WHERE active = 1"):
        _scheduler.modify_job("ical", next_run_time=_soon())
    log.info(
        "scheduler started (ical every %s min, submit every %s min)",
        config.ICAL_POLL_MINUTES,
        config.SUBMIT_SWEEP_MINUTES,
    )


def _soon():
    from datetime import datetime, timedelta

    return datetime.now() + timedelta(seconds=20)


def shutdown() -> None:
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
