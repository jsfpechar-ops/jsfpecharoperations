"""PostgreSQL job queue: the scheduler enqueues a row, a consumer claims it.

A kind is on the queue when its id is in ``UBYHOST_JOB_QUEUE_KINDS``. The
producer (``enqueue``) is idempotent: one open row per kind. The consumer
(``drain``) claims one row per transaction with ``FOR UPDATE SKIP LOCKED``,
then runs the job outside that transaction, so a slow job never holds a row
lock.
"""
from __future__ import annotations

import logging
import os
import socket
import threading
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

from . import config, db

log = logging.getLogger("ubyhost.jobqueue")

LEASE_MINUTES = 60
MAX_ATTEMPTS = 5
BACKOFF_MINUTES = (1, 5, 15, 60)
KEEP_DONE_DAYS = 7
WORKER_ID = f"{socket.gethostname()}:{os.getpid()}"


def _require_postgres() -> None:
    if config.DB_BACKEND != "postgresql":
        raise RuntimeError("the job queue needs PostgreSQL")


def _stamp(delta: timedelta = timedelta(0)) -> str:
    """ISO text in UTC, the format db.utcnow() writes, shifted by ``delta``."""
    return (datetime.now(timezone.utc) + delta).replace(microsecond=0).isoformat()


def _interval(kind: str) -> Optional[int]:
    from . import scheduler

    return scheduler.job_intervals().get(kind)


def enqueue(kind: str) -> bool:
    """Add a due row for ``kind`` unless one is already open; True when added."""
    _require_postgres()
    now = db.utcnow()
    added = db.execute(
        "INSERT INTO job (kind, run_at, payload, created_at) VALUES (?, ?, '{}', ?) "
        "ON CONFLICT (kind) WHERE done_at IS NULL AND dead_at IS NULL DO NOTHING",
        (kind, now, now),
    )
    return added == 1


def claim() -> Optional[dict]:
    """Lease one due job for this worker; None when nothing is due or leased."""
    _require_postgres()
    now = db.utcnow()
    params = [now, WORKER_ID, now, _stamp(-timedelta(minutes=LEASE_MINUTES))]
    # Kinds the Go service runs are left to it (UBYHOST_GO_JOB_KINDS); the
    # clause is absent when that set is empty, so the SQL is unchanged then.
    go_clause = ""
    if config.GO_JOB_KINDS:
        go_clause = "AND NOT (kind = ANY(?)) "
        params.append(sorted(config.GO_JOB_KINDS))
    with db.cursor() as cur:
        cur.execute(
            f"""
            UPDATE job SET locked_at = ?, locked_by = ?, attempts = attempts + 1
            WHERE id = (
                SELECT id FROM job
                WHERE done_at IS NULL AND dead_at IS NULL AND run_at <= ?
                  AND (locked_at IS NULL OR locked_at < ?)
                  {go_clause}
                ORDER BY run_at, id
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            )
            RETURNING id, kind, payload, attempts
            """,
            tuple(params),
        )
        row = cur.fetchone()
    if row is None:
        return None
    return {"id": row[0], "kind": row[1], "payload": row[2], "attempts": row[3]}


def finish(job_id: int) -> None:
    """Record success; a row this worker no longer leases is left alone."""
    _require_postgres()
    db.execute(
        "UPDATE job SET done_at = ?, locked_at = NULL, locked_by = NULL, error = NULL "
        "WHERE id = ? AND locked_by = ?",
        (db.utcnow(), job_id, WORKER_ID),
    )


def fail(job: dict, exc: BaseException, interval_minutes: Optional[int]) -> None:
    """Record a failure: retry with backoff, or dead after MAX_ATTEMPTS."""
    _require_postgres()
    from . import scheduler

    error = f"{type(exc).__name__}: {exc}"[:300]
    if job["attempts"] >= MAX_ATTEMPTS:
        db.execute(
            "UPDATE job SET dead_at = ?, error = ?, locked_at = NULL, locked_by = NULL "
            "WHERE id = ? AND locked_by = ?",
            (db.utcnow(), error, job["id"], WORKER_ID),
        )
        scheduler._job_failed(job["kind"])
        return
    step = BACKOFF_MINUTES[min(job["attempts"] - 1, len(BACKOFF_MINUTES) - 1)]
    minutes = min(step, interval_minutes or 60)
    db.execute(
        "UPDATE job SET run_at = ?, error = ?, locked_at = NULL, locked_by = NULL "
        "WHERE id = ? AND locked_by = ?",
        (_stamp(timedelta(minutes=minutes)), error, job["id"], WORKER_ID),
    )


def purge() -> int:
    """Delete done or dead rows older than KEEP_DONE_DAYS; the number removed."""
    _require_postgres()
    cutoff = _stamp(-timedelta(days=KEEP_DONE_DAYS))
    return db.execute(
        "DELETE FROM job WHERE (done_at IS NOT NULL AND done_at < ?) "
        "OR (dead_at IS NOT NULL AND dead_at < ?)",
        (cutoff, cutoff),
    )


def drain(run: Callable[[str], None], stop: threading.Event, limit: int = 50) -> int:
    """Claim and run up to ``limit`` due jobs; the number run."""
    ran = 0
    for _ in range(limit):
        if stop.is_set():
            break
        job = claim()
        if job is None:
            break
        ran += 1
        try:
            run(job["kind"])
        except Exception as exc:  # the job wrappers catch their own errors; this is a backstop
            log.exception("queued job %s failed", job["kind"])
            fail(job, exc, _interval(job["kind"]))
        else:
            finish(job["id"])
    return ran
