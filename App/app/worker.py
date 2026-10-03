"""Background worker: the scheduler in its own process (WP06).

Production runs the web app as two uvicorn workers with ``UBYHOST_ROLE=web``,
which never start the scheduler, and this process with ``UBYHOST_ROLE=worker``:

    python -m app.worker

It prepares the database the same way the web app does (under the shared
start-up lock), takes the existing scheduler lock on DATA_DIR/scheduler.lock,
starts the jobs and blocks until SIGTERM or SIGINT. It refuses to run when
another process already holds the scheduler lock, so two workers, or a worker
next to a single-process ``UBYHOST_ROLE=all`` app on the same volume, can never
both sweep and file the same guests.

There is no HTTP server. While the scheduler runs, the process touches
DATA_DIR/worker.alive every 30 s; the compose health check reads its age.
"""
from __future__ import annotations

import logging
import os
import signal
import sys
import threading
from pathlib import Path
from typing import Optional

from . import config, db, env_guard, scheduler

log = logging.getLogger("ubyhost.worker")

ALIVE_FILE = "worker.alive"
ALIVE_INTERVAL_SECONDS = 30

# Exit codes, so the compose logs and a supervisor can tell them apart.
EXIT_OK = 0
EXIT_LOCK_HELD = 3
EXIT_BAD_ROLE = 4


def alive_path() -> Path:
    return config.DATA_DIR / ALIVE_FILE


def _touch_alive() -> None:
    path = alive_path()
    try:
        path.touch(mode=0o600, exist_ok=True)
        os.utime(path, None)
    except OSError:
        log.warning("could not update %s", path, exc_info=True)


def prepare() -> None:
    """Start-up checks shared with the web app, safe next to booting web workers."""
    config.ensure_data_dir()
    with db.startup_lock():
        config.secret_key()
        db.init_db()
    env_guard.apply()


def run(stop: Optional[threading.Event] = None) -> int:
    """Run the scheduler until ``stop`` is set. Returns a process exit code."""
    if config.ROLE != "worker":
        log.error("UBYHOST_ROLE=%s; the background worker needs UBYHOST_ROLE=worker", config.ROLE)
        return EXIT_BAD_ROLE
    stop = stop or threading.Event()
    prepare()
    log.info(
        "worker starting (deployment=%s ubyport=%s)", config.DEPLOYMENT, config.UBYPORT_ENV
    )
    if config.ENABLE_SCHEDULER:
        if not scheduler.start():
            log.error(
                "another process holds %s; refusing to start a second scheduler",
                config.DATA_DIR / "scheduler.lock",
            )
            return EXIT_LOCK_HELD
    else:
        log.warning("UBYHOST_ENABLE_SCHEDULER=0: the worker is idle, no background job runs")
    try:
        while True:
            if config.ENABLE_SCHEDULER and not scheduler.running():
                log.error("the scheduler thread stopped; exiting so the container restarts")
                return 1
            _touch_alive()
            if stop.wait(ALIVE_INTERVAL_SECONDS):
                break
    finally:
        log.info("worker stopping; waiting for running jobs to finish")
        scheduler.shutdown()
        try:
            alive_path().unlink()
        except OSError:
            pass
    log.info("worker stopped")
    return EXIT_OK


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    stop = threading.Event()

    def _on_signal(signum, _frame):
        log.info("received signal %s", signum)
        stop.set()

    signal.signal(signal.SIGTERM, _on_signal)
    signal.signal(signal.SIGINT, _on_signal)
    return run(stop)


if __name__ == "__main__":
    sys.exit(main())
