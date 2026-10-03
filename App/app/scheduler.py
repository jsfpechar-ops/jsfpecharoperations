"""Background jobs: calendar polling, automatic submission, deadline watch."""
from __future__ import annotations

import fcntl
import logging
import time

import requests
from apscheduler.schedulers.background import BackgroundScheduler

from . import (
    alerts,
    claim,
    config,
    db,
    dsr,
    filing_watchdog,
    host_i18n,
    icalsync,
    lifecycle_mail,
    mail,
    passport_photos,
    reporting,
    retention,
    signup,
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


def job_intervals() -> dict:
    """Minutes between two runs of each job, as ``start`` schedules them.

    The admin Operations page reads this to call a job late when its last
    success is older than twice the interval. ``retention`` is a daily cron.
    """
    return {
        "ical": config.ICAL_POLL_MINUTES,
        "submit": config.SUBMIT_SWEEP_MINUTES,
        "deadlines": 30,
        "mail": 5,
        "photo_sweep": 12 * 60,
        "retention": 24 * 60,
    }


JOB_LAST_OK_PREFIX = "job_last_ok:"


def _job_ok(job_id: str) -> None:
    alerts.resolve(f"job_failed:{job_id}")
    # Nothing else records a successful run, and a scheduler that silently
    # stopped looks exactly like one with nothing to do (WP10).
    try:
        db.set_setting(f"{JOB_LAST_OK_PREFIX}{job_id}", db.utcnow())
    except Exception:
        log.warning("could not record the last success of job %s", job_id, exc_info=True)


def _log_run(job_id: str, started: float, ok: bool, items: dict | None = None) -> None:
    """One line per job run with its duration and item counts (WP13).

    ``tools/perf_report.py`` reads these: ``job=<id> ok=<0|1> ms=<n>`` then
    ``key=<int>`` pairs. Only numbers, never names or URLs.
    """
    counts = " ".join(
        f"{key}={int(value)}"
        for key, value in (items or {}).items()
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    )
    log.info(
        "job run job=%s ok=%d ms=%d%s",
        job_id,
        1 if ok else 0,
        int((time.perf_counter() - started) * 1000),
        f" {counts}" if counts else "",
    )


def _job_sync_calendars() -> None:
    started = time.perf_counter()
    try:
        totals = icalsync.sync_all()
        log.info("calendar sync: %s", totals)
    except Exception:
        log.exception("calendar sync failed")
        _job_failed("ical")
        _log_run("ical", started, False)
        return
    _job_ok("ical")
    _log_run("ical", started, True, totals)
    _ping(config.HEARTBEAT_ICAL_URL, "ical")


def _job_submit() -> None:
    started = time.perf_counter()
    try:
        summary = reporting.sweep()
        if summary["submitted"] or summary["failed"]:
            log.info("ubyport sweep: %s", summary)
    except Exception:
        log.exception("ubyport sweep failed")
        _job_failed("submit")
        _log_run("submit", started, False)
        return
    _job_ok("submit")
    _log_run("submit", started, True, summary)
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
    started = time.perf_counter()
    watch_ok = True
    raised = due_requests = 0
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
        _log_run("deadlines", started, False)
        return
    if watch_ok:
        _job_ok("deadlines")
    _log_run(
        "deadlines", started, watch_ok,
        {
            "alerts": raised or 0,
            "requests_due": due_requests or 0,
            "at_risk": watchdog["at_risk"],
            "unknown_risk": watchdog.get("unknown_risk", 0),
            "awaiting_retry": watchdog.get("awaiting_retry", 0),
            "host_mails": watchdog["host_mails"],
            "digest": watchdog["digest"],
        },
    )
    # A failed deadline watch counts as a failure too: nobody is being told.
    _filing_heartbeat(watchdog["at_risk"] > 0 or not watch_ok)


def _filing_heartbeat(at_risk: bool) -> None:
    """Ping the filing dead-man switch: <url> when all is well, <url>/fail if not."""
    _ping(filing_watchdog.heartbeat_url(at_risk), "filing")


def _job_mail() -> None:
    started = time.perf_counter()
    failed = False
    items: dict = {}
    for name, step in (
        ("expire_holds", claim.expire_holds),
        ("drain", mail.drain),
        ("reminders", claim.sweep_reminders),
        # Once a day and only with UBYHOST_LIFECYCLE_MAIL=1 (WP12).
        ("lifecycle", lifecycle_mail.run_daily),
        ("purge", mail.purge_old),
    ):
        try:
            result = step()
            if result:
                log.info("mail job %s: %s", name, result)
            if isinstance(result, dict):
                for key, value in result.items():
                    items[f"{name}_{key}"] = value
            elif isinstance(result, int) and not isinstance(result, bool):
                items[name] = result
        except Exception:
            log.exception("mail job step %s failed", name)
            failed = True
    if failed:
        _job_failed("mail")
    else:
        _job_ok("mail")
        _ping(config.HEARTBEAT_MAIL_URL, "mail")
    _log_run("mail", started, not failed, items)


def _job_photo_sweep() -> None:
    """Delete passport images the host never got round to verifying.

    Retention runs here too because it is the same question - what may we still
    hold - and this is the only job that runs on a long enough cycle to be a
    backstop for the Settings button.
    """
    started = time.perf_counter()
    try:
        removed = passport_photos.purge_stale()
        if removed:
            log.info("passport photo sweep deleted %s file(s)", removed)
        blanked = reporting.purge_submission_payloads()
        if blanked:
            log.info("submission payload purge blanked %s envelope(s)", blanked)
        # WP20: unconfirmed sign-ups after 7 days, ad click IDs after the
        # Google Ads import window. Runs with sign-up off too, so switching
        # the feature off never leaves a click ID behind.
        signup_counts = signup.purge()
        if any(signup_counts.values()):
            log.info("signup purge: %s", signup_counts)
    except Exception:
        log.exception("passport photo sweep failed")
        _job_failed("photo_sweep")
        _log_run("photo_sweep", started, False)
        return
    _job_ok("photo_sweep")
    _log_run("photo_sweep", started, True, {"photos": removed or 0, "payloads": blanked or 0})


def _job_retention() -> None:
    """Compute (and, once enabled, apply) the retention schedule.

    Dry-run by default: it audits the exact row set and deletes nothing until
    ``UBYHOST_RETENTION_AUTOPURGE=1`` (see ``retention.run``).
    """
    started = time.perf_counter()
    try:
        summary = retention.run()
        if any(summary["counts"].values()):
            log.info("retention run: %s", summary)
    except Exception:
        log.exception("retention run failed")
        _job_failed("retention")
        _log_run("retention", started, False)
        return
    _job_ok("retention")
    _log_run("retention", started, True, summary.get("counts") or {})


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
    minutes = job_intervals()
    _scheduler.add_job(
        _job_sync_calendars, "interval", minutes=minutes["ical"],
        id="ical", max_instances=1, coalesce=True, next_run_time=_soon(),
    )
    _scheduler.add_job(
        _job_submit, "interval", minutes=minutes["submit"],
        id="submit", max_instances=1, coalesce=True,
    )
    _scheduler.add_job(
        _job_deadlines, "interval", minutes=minutes["deadlines"], id="deadlines",
        max_instances=1, coalesce=True,
    )
    _scheduler.add_job(
        _job_mail, "interval", minutes=minutes["mail"], id="mail", max_instances=1, coalesce=True,
    )
    _scheduler.add_job(
        _job_photo_sweep, "interval", minutes=minutes["photo_sweep"], id="photo_sweep",
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
