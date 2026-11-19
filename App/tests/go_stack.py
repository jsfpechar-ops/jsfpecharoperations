"""Caddy-like Go routing for browser tests (UBYHOST_GO_PATHS in the test process)."""
from __future__ import annotations

import functools
import importlib.util
import os
import re
import shutil
import socket
import subprocess
import threading
import time
from pathlib import Path
from typing import Callable

import httpx
import pytest
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

REPO_ROOT = Path(__file__).resolve().parents[2]
GO_DIR = REPO_ROOT / "go"
MIGRATIONS = REPO_ROOT / "App" / "migrations_pg"
PARAM = re.compile(r"\{[^/}]*\}")

_started_lock = threading.Lock()
_go_proc: subprocess.Popen | None = None
_go_base: str = ""
_go_log: Path | None = None


def go_paths_enabled() -> bool:
    raw = os.environ.get("UBYHOST_GO_PATHS", "").strip()
    return bool(raw) and raw != "/__go_off__"


def go_path_entries() -> list[str]:
    if not go_paths_enabled():
        return []
    raw = os.environ.get("UBYHOST_GO_PATHS", "").strip()
    return [p for part in raw.replace('"', "").split() for p in [part.strip()] if p]


@functools.lru_cache(maxsize=None)
def _parity_check():
    """scripts/go_parity_check.py, loaded once by path (it is not a package)."""
    spec = importlib.util.spec_from_file_location(
        "go_parity_check", REPO_ROOT / "scripts" / "go_parity_check.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def caddy_match(entry: str, sample: str) -> bool:
    """caddy_match of scripts/go_parity_check.py, so the two can never differ."""
    return _parity_check().caddy_match(entry, sample)


def path_routed_to_go(path: str) -> bool:
    return any(caddy_match(entry, path) for entry in go_path_entries())


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _database_url() -> str:
    url = os.environ.get("UBYHOST_DATABASE_URL") or os.environ.get("UBYHOST_TEST_DATABASE_URL")
    if not url:
        pytest.fail(
            "UBYHOST_GO_PATHS is set but neither UBYHOST_DATABASE_URL nor "
            "UBYHOST_TEST_DATABASE_URL points at PostgreSQL (Go web needs Postgres)"
        )
    return url


def _tail(path: Path, lines: int = 30) -> str:
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    return "\n".join(text.splitlines()[-lines:])


def ensure_go_running(public_base_url: str) -> str:
    """Start ubyhost-web once; return the Go base URL (http://host:port)."""
    global _go_proc, _go_base, _go_log
    if _go_proc is not None and _go_proc.poll() is None:
        return _go_base
    with _started_lock:
        if _go_proc is not None and _go_proc.poll() is None:
            return _go_base
        if shutil.which("go") is None:
            pytest.fail("UBYHOST_GO_PATHS is set but `go` is not on PATH")
        binary = Path(os.environ.get("TMPDIR", "/tmp")) / f"ubyhost-web-{os.getpid()}"
        build = subprocess.run(
            ["go", "build", "-o", str(binary), "./cmd/ubyhost-web"],
            cwd=GO_DIR,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if build.returncode:
            pytest.fail("go build ubyhost-web failed:\n" + (build.stderr or build.stdout)[-1500:])
        port = _free_port()
        go_addr = f"127.0.0.1:{port}"
        _go_base = f"http://{go_addr}"
        _go_log = Path(os.environ.get("TMPDIR", "/tmp")) / "ubyhost-go-web-test.log"
        env = {
            **os.environ,
            "UBYHOST_DATABASE_URL": _database_url(),
            "UBYHOST_GO_ADDR": go_addr,
            "UBYHOST_MIGRATIONS_DIR": str(MIGRATIONS),
            "UBYHOST_PUBLIC_BASE_URL": public_base_url,
            "UBYHOST_GO_JOB_KINDS": "",
            "UBYHOST_JOB_QUEUE_KINDS": "",
        }
        _go_log.write_text("", encoding="utf-8")
        log_fp = open(_go_log, "a", encoding="utf-8")
        _go_proc = subprocess.Popen(
            [str(binary)],
            cwd=REPO_ROOT,
            env=env,
            stdout=log_fp,
            stderr=subprocess.STDOUT,
        )
        deadline = time.time() + 30
        while time.time() < deadline:
            if _go_proc.poll() is not None:
                pytest.fail(
                    "ubyhost-web exited before /healthz\n" + _tail(_go_log)
                )
            try:
                r = httpx.get(_go_base + "/healthz", timeout=1.0)
                if r.status_code in (200, 503):
                    return _go_base
            except Exception:
                time.sleep(0.2)
        pytest.fail("ubyhost-web did not answer /healthz in time\n" + _tail(_go_log))
        return _go_base


def stop_go() -> None:
    global _go_proc
    if _go_proc is None:
        return
    _go_proc.terminate()
    try:
        _go_proc.wait(5)
    except Exception:
        _go_proc.kill()
    _go_proc = None


@pytest.fixture(scope="session", autouse=True)
def _go_stack_lifecycle():
    yield
    stop_go()


class GoPathMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, go_base_getter: Callable[[], str]) -> None:
        super().__init__(app)
        self._go_base_getter = go_base_getter

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if request.method not in {"GET", "HEAD"} or not path_routed_to_go(path):
            return await call_next(request)
        go_base = self._go_base_getter()
        query = request.url.query
        url = f"{go_base}{path}" + (f"?{query}" if query else "")
        headers = {k.decode(): v.decode() for k, v in request.headers.raw}
        body = await request.body()
        async with httpx.AsyncClient(follow_redirects=False) as client:
            upstream = await client.request(
                request.method,
                url,
                headers=headers,
                content=body,
            )
        if (
            upstream.status_code == 501
            and upstream.headers.get("x-ubyhost-not-ported") == "1"
        ):
            return await call_next(request)
        out_headers = dict(upstream.headers)
        for name in ("content-encoding", "transfer-encoding", "connection"):
            out_headers.pop(name, None)
        return Response(
            content=upstream.content,
            status_code=upstream.status_code,
            headers=out_headers,
            media_type=upstream.headers.get("content-type"),
        )


def seed_go_host_gate(user_id: int) -> None:
    """Go hostweb reads legal acceptance from the database (Python tests stub the Python gate only)."""
    from app import config, db

    now = db.utcnow()
    for document, version in (
        ("terms", config.TERMS_VERSION),
        ("privacy", config.PRIVACY_VERSION),
        ("dpa", config.DPA_VERSION),
    ):
        db.execute(
            "INSERT INTO legal_acceptance (user_account_id, document, version, accepted_at, method, ip, user_agent) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, document, version, now, "backfill", "", ""),
        )


def browser_app(py_app: ASGIApp, public_base_url: str) -> ASGIApp:
    """Wrap the Python app so listed paths hit Go like production Caddy."""
    if not go_paths_enabled():
        return py_app

    def getter() -> str:
        return ensure_go_running(public_base_url)

    return GoPathMiddleware(py_app, getter)