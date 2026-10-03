"""WP06: the scheduler runs in its own process; web workers never start it."""
from __future__ import annotations

import fcntl
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import config, db, scheduler, worker
from app.main import app

APP_DIR = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def _no_scheduler_left_running():
    yield
    scheduler.shutdown()


def _private_data(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "worker.db")


def test_web_role_lifespan_does_not_start_the_scheduler(monkeypatch):
    monkeypatch.setattr(config, "ROLE", "web")
    monkeypatch.setattr(config, "ENABLE_SCHEDULER", True)
    calls = []
    monkeypatch.setattr(scheduler, "start", lambda: calls.append("start") or True)
    with TestClient(app) as client:
        assert client.get("/healthz").status_code == 200
    assert calls == []
    assert scheduler._scheduler is None


def test_all_role_lifespan_still_starts_the_scheduler(monkeypatch):
    """Local development and the single-process Render staging service."""
    monkeypatch.setattr(config, "ROLE", "all")
    monkeypatch.setattr(config, "ENABLE_SCHEDULER", True)
    calls = []
    monkeypatch.setattr(scheduler, "start", lambda: calls.append("start") or True)
    with TestClient(app):
        pass
    assert calls == ["start"]


def test_worker_role_refuses_to_serve_http(monkeypatch):
    monkeypatch.setattr(config, "ROLE", "worker")
    with pytest.raises(RuntimeError, match="app.worker"):
        with TestClient(app):
            pass


def test_the_worker_starts_the_scheduler_and_stops_on_request(monkeypatch, tmp_path):
    _private_data(monkeypatch, tmp_path)
    monkeypatch.setattr(config, "ROLE", "worker")
    monkeypatch.setattr(config, "ENABLE_SCHEDULER", True)
    stop = threading.Event()
    result = {}
    thread = threading.Thread(target=lambda: result.update(code=worker.run(stop)))
    thread.start()
    try:
        deadline = time.monotonic() + 15
        while not (scheduler.running() and worker.alive_path().exists()):
            assert time.monotonic() < deadline, "the worker never started the scheduler"
            time.sleep(0.05)
        assert {job.id for job in scheduler._scheduler.get_jobs()} >= {"ical", "submit", "mail"}
        # The worker ran the same migrations as the web app.
        assert db.query_one("SELECT COUNT(*) AS n FROM user_account") is not None
    finally:
        stop.set()
        thread.join(timeout=30)
    assert result["code"] == worker.EXIT_OK
    assert not scheduler.running()
    assert not worker.alive_path().exists()


def test_the_worker_refuses_a_second_scheduler_while_the_lock_is_held(monkeypatch, tmp_path):
    _private_data(monkeypatch, tmp_path)
    monkeypatch.setattr(config, "ROLE", "worker")
    monkeypatch.setattr(config, "ENABLE_SCHEDULER", True)
    with open(tmp_path / "scheduler.lock", "a+") as held:
        fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert worker.run(threading.Event()) == worker.EXIT_LOCK_HELD
    assert not scheduler.running()


def test_the_worker_needs_the_worker_role(monkeypatch, tmp_path):
    _private_data(monkeypatch, tmp_path)
    monkeypatch.setattr(config, "ROLE", "web")
    assert worker.run(threading.Event()) == worker.EXIT_BAD_ROLE


def _worker_env(tmp_path: Path) -> dict:
    env = os.environ.copy()
    env.update(
        {
            "UBYHOST_DATA_DIR": str(tmp_path),
            "UBYHOST_DB": str(tmp_path / "worker.db"),
            "UBYHOST_ROLE": "worker",
            "UBYHOST_ENABLE_SCHEDULER": "1",
            "UBYHOST_SECRET_KEY": "test-secret-key-not-for-real-use",
        }
    )
    return env


def test_worker_process_exits_cleanly_on_sigterm(tmp_path):
    proc = subprocess.Popen(
        [sys.executable, "-m", "app.worker"],
        cwd=APP_DIR,
        env=_worker_env(tmp_path),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        deadline = time.monotonic() + 30
        while not (tmp_path / worker.ALIVE_FILE).exists():
            assert proc.poll() is None, proc.communicate()[0]
            assert time.monotonic() < deadline, "worker never became alive"
            time.sleep(0.1)
        proc.send_signal(signal.SIGTERM)
        output, _ = proc.communicate(timeout=60)
    finally:
        if proc.poll() is None:
            proc.kill()
    assert proc.returncode == worker.EXIT_OK, output
    assert "scheduler started" in output
    assert "worker stopped" in output


def test_second_worker_process_exits_while_the_first_holds_the_lock(tmp_path):
    with open(tmp_path / "scheduler.lock", "a+") as held:
        fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
        proc = subprocess.run(
            [sys.executable, "-m", "app.worker"],
            cwd=APP_DIR,
            env=_worker_env(tmp_path),
            capture_output=True,
            text=True,
            timeout=60,
        )
    assert proc.returncode == worker.EXIT_LOCK_HELD
    assert "refusing to start a second scheduler" in proc.stderr + proc.stdout
