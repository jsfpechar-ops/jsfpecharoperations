"""Background jobs: calendar polling, automatic submission, deadline watch."""
from __future__ import annotations

import fcntl
import logging

import requests
from apscheduler.schedulers.background import BackgroundScheduler

from . import (
    alerts,
    claim,
    config,
    dsr,
    filing_watchdog,
    host_i18n,
    icalsync,
    mail,
    passport_photos,
    reporting,
    retention,
)

log = logging.getLogger("ubyhost.scheduler")
_scheduler = None
_lock_handle = None

# Losing the deadline watch or the submission sweep loses compliance
# monitoring, so those two failures are critical; the rest are warnings.
_JOB_LEVELS = {
    "ical": "warning",
    "submit": "critical",
    "deadlines": "critical",
    "mail": "warning",
    "photo_sweep": "warning",
    "retention": "warning",
}


def _job_failed(job_id: str) -> None:
    """Tell the host a background job died instead of only logging it."""
    lang = host_i18n.DEFAULT_LANGUAGE
    alerts.raise_alert(
        _JOB_LEVELS[job_id],
        "job_failed",
        host_i18n.translate(
            lang,
            "notification.job_failed.title",
            job=host_i18n.translate(lang, f"notification.job_name.{job_id}"),
        ),
        host_i18n.translate(lang, "notification.job_failed.detail"),
        dedupe_key=f"job_failed:{job_id}",
    )


def _job_ok(job_id: str) -> None:
    alerts.resolve(f"job_failed:{job_id}")


def _job_sync_calendars() -> None:
    try:
        totals = icalsync.sync_all()
        log.info("calendar sync: %s", totals)
    except Exception:
        log.exception("calendar sync failed")
        _job_failed("ical")
        return
    _job_ok("ical")
    _ping(config.HEARTBEAT_ICAL_URL, "ical")


def _job_submit() -> None:
    try:
        summary = reporting.sweep()
        if summary["submitted"] or summary["failed"]:
            log.info("ubyport sweep: %s", summary)
    except Exception:
        log.exception("ubyport sweep failed")
        _job_failed("submit")
        return
    _job_ok("submit")
    _heartbeat()


def _heartbeat() -> None:
    """Tell an external dead-man switch the submission sweep is alive."""
    _ping(config.HEARTBEAT_URL, "submit")


def _ping(url: str, job_id: str) -> None:
    """Ping one job's dead-man switch; a failed ping is logged, never raised."""
    if not url:
        return
    try:
        requests.get(url, timeout=5)
    except Exception:
        log.warning("heartbeat ping for %s failed", job_id, exc_info=True)


def _job_deadlines() -> None:
    watch_ok = True
    try:
        raised = reporting.check_deadlines()
        due_requests = dsr.raise_due_alerts()
        if raised or due_requests:
            log.info(
                "deadline watch raised %s alert(s), %s data-subject request(s) due",
                raised,
                due_requests,
            )
    except Exception:
        log.exception("deadline watch failed")
        _job_failed("deadlines")
        watch_ok = False
    # WP23: the filing watchdog runs even when the alert pass above failed,
    # because its mails and its heartbeat are what reach the owner when the
    # app itself is not being looked at.
    try:
        watchdog = filing_watchdog.run()
        if (
            watchdog["at_risk"] or watchdog.get("unknown_risk") or watchdog.get("awaiting_retry")
            or watchdog["host_mails"] or watchdog["digest"]
        ):
            log.info("filing watchdog: %s", watchdog)
    except Exception:
        # No ping at all: the external monitor alerts on the missing ping.
        log.exception("filing watchdog failed")
        _job_failed("deadlines")
        return
    if watch_ok:
        _job_ok("deadlines")
    # A failed deadline watch counts as a failure too: nobody is being told.
    _filing_heartbeat(watchdog["at_risk"] > 0 or not watch_ok)


def _filing_heartbeat(at_risk: bool) -> None:
    """Ping the filing dead-man switch: <url> when all is well, <url>/fail if not."""
    _ping(filing_watchdog.heartbeat_url(at_risk), "filing")


def _job_mail() -> None:
    failed = False
    for name, step in (
        ("expire_holds", claim.expire_holds),
        ("drain", mail.drain),
        ("reminders", claim.sweep_reminders),
        ("purge", mail.purge_old),
    ):
        try:
            result = step()
            if result:
                log.info("mail job %s: %s", name, result)
        except Exception:
            log.exception("mail job step %s failed", name)
            failed = True
    if failed:
        _job_failed("mail")
    else:
        _job_ok("mail")
        _ping(config.HEARTBEAT_MAIL_URL, "mail")


def _job_photo_sweep() -> None:
    """Delete passport images the host never got round to verifying.

    Retention runs here too because it is the same question - what may we still
    hold - and this is the only job that runs on a long enough cycle to be a
    backstop for the Settings button.
    """
    try:
        removed = passport_photos.purge_stale()
        if removed:
            log.info("passport photo sweep deleted %s file(s)", removed)
        blanked = reporting.purge_submission_payloads()
        if blanked:
            log.info("submission payload purge blanked %s envelope(s)", blanked)
    except Exception:
        log.exception("passport photo sweep failed")
        _job_failed("photo_sweep")
        return
    _job_ok("photo_sweep")


def _job_retention() -> None:
    """Compute (and, once enabled, apply) the retention schedule.

    Dry-run by default: it audits the exact row set and deletes nothing until
    ``UBYHOST_RETENTION_AUTOPURGE=1`` (see ``retention.run``).
    """
    try:
        summary = retention.run()
        if any(summary["counts"].values()):
            log.info("retention run: %s", summary)
    except Exception:
        log.exception("retention run failed")
        _job_failed("retention")
        return
    _job_ok("retention")


def _acquire_single_instance_lock() -> bool:
    """Hold an exclusive lock on DATA_DIR/scheduler.lock for this process's life.

    A second worker or a second container on the same volume would otherwise
    run its own sweep and file the same guests at the same time.
    """
    global _lock_handle
    handle = open(config.DATA_DIR / "scheduler.lock", "a+")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        return False
    _lock_handle = handle
    return True


def start() -> bool:
    """Start the background jobs here; True when this process now runs them.

    False when the scheduler is switched off or another process (or container
    on the same volume) already holds the scheduler lock.
    """
    global _scheduler
    if _scheduler:
        return True
    if not config.ENABLE_SCHEDULER:
        return False
    if not _acquire_single_instance_lock():
        log.warning("another process holds the scheduler lock; not starting a scheduler here")
        return False
    _scheduler = BackgroundScheduler(timezone=config.TIMEZONE)
    _scheduler.add_job(
        _job_sync_calendars, "interval", minutes=config.ICAL_POLL_MINUTES,
        id="ical", max_instances=1, coalesce=True, next_run_time=_soon(),
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
    _scheduler.add_job(
        _job_retention, "cron", hour=3, minute=30, id="retention",
        max_instances=1, coalesce=True,
    )
    _scheduler.start()
    log.info(
        "scheduler started (ical every %s min, submit every %s min)",
        config.ICAL_POLL_MINUTES,
        config.SUBMIT_SWEEP_MINUTES,
    )
    return True


def running() -> bool:
    """Whether this process runs the scheduler and its thread is alive."""
    return bool(_scheduler and _scheduler.running)


def _soon():
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    return datetime.now(ZoneInfo(config.TIMEZONE)) + timedelta(seconds=20)


def shutdown() -> None:
    global _scheduler, _lock_handle
    if _scheduler:
        # wait=True: a batch already on the wire must record its answer (compose stop_grace_period is 90 s).
        _scheduler.shutdown(wait=True)
        _scheduler = None
    if _lock_handle:
        _lock_handle.close()
        _lock_handle = None
