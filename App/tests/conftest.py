"""Test environment: a throwaway database and no background scheduler.

These variables must be set before anything under ``app`` is imported, because
``app.config`` reads the environment once at import time.
"""
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest
import requests

_TMP = Path(tempfile.mkdtemp(prefix="ubyhost-tests-"))
PROJECT_DIR = Path(__file__).resolve().parent.parent


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


MOCK_PORT = _free_port()

os.environ.setdefault("UBYHOST_DATA_DIR", str(_TMP))
os.environ.setdefault("UBYHOST_DB", str(_TMP / "test.db"))
os.environ.setdefault("UBYHOST_SECRET_KEY", "test-secret-key-not-for-real-use")
os.environ.setdefault("UBYHOST_ENABLE_SCHEDULER", "0")
os.environ.setdefault("UBYHOST_UBYPORT_ENV", "mock")
os.environ.setdefault("UBYHOST_MOCK_URL", f"http://127.0.0.1:{MOCK_PORT}/ws_uby/ws_uby.svc")
os.environ["MOCK_UBYPORT_STATE"] = str(_TMP / "mock_state.json")
os.environ["MOCK_UBYPORT_PORT"] = str(MOCK_PORT)


@pytest.fixture(scope="session")
def mock_ubyport():
    """The stand-in police service, so the whole path is exercised for real."""
    process = subprocess.Popen(
        [sys.executable, "-m", "mock_ubyport.server"],
        cwd=str(PROJECT_DIR),
        env=dict(os.environ),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    base = f"http://127.0.0.1:{MOCK_PORT}"
    deadline = time.time() + 30
    while time.time() < deadline:
        if process.poll() is not None:
            output = (process.stdout.read() or b"").decode(errors="replace")
            raise RuntimeError(f"mock UbyPort exited early:\n{output}")
        try:
            if requests.get(base + "/healthz", timeout=1).status_code == 200:
                break
        except requests.RequestException:
            time.sleep(0.2)
    else:
        process.kill()
        raise RuntimeError("mock UbyPort did not start in time")
    try:
        yield base
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
