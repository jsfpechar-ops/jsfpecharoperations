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
os.environ.setdefault("UBYHOST_GUEST_PIN", "0")
os.environ.setdefault("UBYHOST_BOOTSTRAP_ADMIN", "0")
os.environ.setdefault("UBYHOST_UBYPORT_ENV", "mock")
os.environ.setdefault("UBYHOST_MAIL_BACKEND", "console")
os.environ["UBYHOST_MOCK_URL"] = f"http://127.0.0.1:{MOCK_PORT}/ws_uby/ws_uby.svc"
os.environ.setdefault("UBYHOST_ICAL_ALLOW_PRIVATE", "1")
os.environ["MOCK_UBYPORT_STATE"] = str(_TMP / "mock_state.json")
os.environ["MOCK_UBYPORT_PORT"] = str(MOCK_PORT)


def complete_guest_claim(
    client,
    token: str,
    reservation_id: int,
    *,
    email: str = "guest@example.test",
    party_size: int = 2,
    lang: str = "en",
) -> str:
    """Assign the stay to an e-mail and set the browser claim cookie.

    GET of the magic link must not assign; tests confirm with POST like a guest.
    """
    from app import claim, db

    reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (reservation_id,))
    apartment = db.query_one(
        "SELECT * FROM apartment WHERE permalink_token = ?", (token,)
    )
    row = claim.ensure_row(reservation_id)
    # Fixtures may reuse stays that a previous test explicitly locked.
    if not claim.guest_access_open(reservation, row):
        claim.reopen_guest_access(reservation_id)
        row = claim.ensure_row(reservation_id)
    ok, err, secret = claim.start_claim(
        reservation,
        apartment,
        email=email,
        party_size=party_size,
        lang=lang,
        resend=claim.is_claimed(row),
    )
    assert ok, err
    response = client.post(
        f"/l/{token}/{reservation_id}/claim/confirm",
        data={"secret": secret},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return secret


@pytest.fixture(scope="session")
def mock_ubyport():
    """The stand-in police service, so the whole path is exercised for real."""
    log_path = _TMP / "mock-ubyport.log"
    env = dict(os.environ)
    env["PYTHONPATH"] = str(PROJECT_DIR) + os.pathsep + env.get("PYTHONPATH", "")
    env["MOCK_UBYPORT_PORT"] = str(MOCK_PORT)
    with log_path.open("ab") as log_file:
        process = subprocess.Popen(
            [sys.executable, "-m", "mock_ubyport.server", str(MOCK_PORT)],
            cwd=str(PROJECT_DIR),
            env=env,
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )
    base = f"http://127.0.0.1:{MOCK_PORT}"
    deadline = time.time() + 30
    while time.time() < deadline:
        if process.poll() is not None:
            raise RuntimeError("mock UbyPort exited early")
        try:
            if requests.get(base + "/healthz", timeout=1).status_code == 200:
                break
        except requests.RequestException:
            time.sleep(0.2)
    else:
        process.kill()
        detail = log_path.read_text(errors="replace") if log_path.exists() else ""
        raise RuntimeError(
            f"mock UbyPort did not start in time on {base}\n{detail}"
        )
    try:
        yield base
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
