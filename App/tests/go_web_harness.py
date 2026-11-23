"""Browser harness: local Go ubyhost-web binary with throwaway PostgreSQL."""
from __future__ import annotations

import json
import mimetypes
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse

import itsdangerous
import psycopg
import pytest

REPO = Path(__file__).resolve().parents[2]
APP_DIR = REPO / "App"
GO_DIR = REPO / "go"
STATIC_DIR = APP_DIR / "app" / "static"
MIGRATIONS_DIR = APP_DIR / "migrations_pg"
FIXTURE_SECRET = "harness-fixture-secret-012345678901234567"
SHOT_WIDTHS = (390, 768, 1280)

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

from tests.browser_support import chromium_launch_kwargs, settle_motion

LINT = (Path(__file__).parent / "layout_lint.js").read_text()


def _out_dir() -> Path:
    base = os.environ.get("UBYHOST_SHOTS_DIR")
    return Path(base) / "layout-lint" if base else Path("/tmp/ubyhost-layout-lint")


def _fail_or_skip(reason: str) -> None:
    if REQUIRE_BROWSER:
        pytest.fail(reason)
    pytest.skip(reason)


def _tail(text: str, n: int = 30) -> str:
    return "\n".join(text.splitlines()[-n:])


def _database_url(base: str, name: str) -> str:
    parsed = urlparse(base)
    return urlunparse(parsed._replace(path=f"/{name}"))


def _pick_port() -> int:
    for port in range(18100, 18200):
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            probe.bind(("127.0.0.1", port))
            return port
        except OSError:
            continue
        finally:
            probe.close()
    pytest.fail("no free port in 18100-18199")


def _seed(conn: psycopg.Connection) -> tuple[int, int]:
    username = "lint_harness_host"
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO user_account (username, password_hash, role, active, session_version, created_at, email)
               VALUES (%s, 'x', 'host', 1, 1, '2026-01-01T00:00:00+00:00', %s) RETURNING id""",
            (username, f"{username}@example.test"),
        )
        host_id = cur.fetchone()[0]
        cur.execute(
            "UPDATE user_account SET two_factor_prompted_at = '2026-01-01T00:00:00+00:00' WHERE id = %s",
            (host_id,),
        )
        for doc, version in (("terms", "t1"), ("privacy", "p1"), ("dpa", "d1")):
            cur.execute(
                """INSERT INTO legal_acceptance (user_account_id, document, version, accepted_at, method)
                   VALUES (%s, %s, %s, '2026-01-01T00:00:00+00:00', 'backfill')""",
                (host_id, doc, version),
            )
        cur.execute(
            """INSERT INTO apartment (owner_user_id, internal_name, created_at)
               VALUES (%s, %s, '2026-01-01T00:00:00+00:00') RETURNING id""",
            (host_id, "Layout lint flat"),
        )
        apartment_id = cur.fetchone()[0]
    conn.commit()
    return host_id, apartment_id


@pytest.fixture(scope="module")
def go_web(tmp_path_factory):
    if shutil.which("go") is None:
        _fail_or_skip("go not found in PATH")
    base_url = os.environ.get("UBYHOST_TEST_DATABASE_URL")
    if not base_url:
        _fail_or_skip("UBYHOST_TEST_DATABASE_URL not set")

    db_name = f"ubyhost_golint_{secrets.token_hex(4)}"
    test_db_url = _database_url(base_url, db_name)

    admin = psycopg.connect(base_url, autocommit=True)
    try:
        admin.execute(f'CREATE DATABASE "{db_name}"')
    finally:
        admin.close()

    work = tmp_path_factory.mktemp("go-web")
    binary = work / "ubyhost-web"
    log_file = work / "ubyhost-web.log"
    data_dir = work / "data"
    data_dir.mkdir()

    build = subprocess.run(
        # CI containers check out the repo as another user, so git refuses VCS stamping.
        ["go", "build", "-buildvcs=false", "-o", str(binary), "./cmd/ubyhost-web"],
        cwd=GO_DIR,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    if build.returncode != 0:
        pytest.fail("go build failed:\n" + _tail(build.stdout + build.stderr))

    schema = subprocess.run(
        [sys.executable, "scripts/pg_schema.py", "apply", "--expect-database", db_name],
        cwd=APP_DIR,
        env={**os.environ, "UBYHOST_DATABASE_URL": test_db_url},
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    if schema.returncode != 0:
        pytest.fail("pg_schema.py apply failed:\n" + _tail(schema.stdout + schema.stderr))

    seed_conn = psycopg.connect(test_db_url)
    try:
        host_id, apartment_id = _seed(seed_conn)
    finally:
        seed_conn.close()

    port = _pick_port()
    base_http = f"http://127.0.0.1:{port}"
    proc_env = {
        **os.environ,
        "UBYHOST_DATABASE_URL": test_db_url,
        "UBYHOST_GO_ADDR": f"127.0.0.1:{port}",
        "UBYHOST_MIGRATIONS_DIR": str(MIGRATIONS_DIR.resolve()),
        "UBYHOST_SECRET_KEY": FIXTURE_SECRET,
        "UBYHOST_PUBLIC_BASE_URL": base_http,
        "UBYHOST_TERMS_VERSION": "t1",
        "UBYHOST_PRIVACY_VERSION": "p1",
        "UBYHOST_DPA_VERSION": "d1",
        "UBYHOST_DATA_DIR": str(data_dir),
        "UBYHOST_AI_FEATURES": "leon",
        "UBYHOST_ANTHROPIC_API_KEY": "harness-fixture-anthropic-key",
    }

    with open(log_file, "w", encoding="utf-8") as log_handle:
        proc = subprocess.Popen(
            [str(binary)],
            env=proc_env,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
        )

    deadline = time.time() + 20
    healthy = False
    while time.time() < deadline:
        if proc.poll() is not None:
            break
        try:
            with urllib.request.urlopen(f"{base_http}/healthz", timeout=1) as resp:
                if resp.status == 200:
                    healthy = True
                    break
        except (urllib.error.URLError, TimeoutError):
            pass
        time.sleep(0.25)

    if not healthy:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        log_text = log_file.read_text(encoding="utf-8", errors="replace")
        pytest.fail("Go binary did not become healthy:\n" + _tail(log_text))

    try:
        yield {
            "base_url": base_http,
            "host_id": host_id,
            "apartment_id": apartment_id,
            "secret": FIXTURE_SECRET,
            "database_url": test_db_url,
        }
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        admin = psycopg.connect(base_url, autocommit=True)
        try:
            admin.execute(f'DROP DATABASE "{db_name}" WITH (FORCE)')
        finally:
            admin.close()


@pytest.fixture(scope="module")
def go_cookie(go_web):
    payload = {"uid": go_web["host_id"], "sv": 1, "iat": int(time.time())}
    serializer = itsdangerous.URLSafeTimedSerializer(go_web["secret"], salt="ubyhost-session")
    return serializer.dumps(payload)


def register_static_routes(context) -> None:
    def static_route(route) -> None:
        rel = re.sub(r".*/static/", "", route.request.url).split("?", 1)[0]
        if ".." in rel or rel.startswith("/"):
            route.abort(403)
            return
        target = (STATIC_DIR / rel).resolve()
        if not str(target).startswith(str(STATIC_DIR.resolve())):
            route.abort(403)
            return
        if not target.is_file():
            route.fulfill(status=404, body="not found")
            return
        mime, _ = mimetypes.guess_type(target.name)
        headers = {"content-type": mime or "application/octet-stream"}
        route.fulfill(status=200, headers=headers, body=target.read_bytes())

    context.route("**/static/**", static_route)


def lint_go_paths(
    go_web: dict[str, Any],
    paths: dict[str, str],
    cookie: str,
    *,
    extra: dict[str, Callable[[Any], None]] | None = None,
    after: dict[str, Callable[[Any], None]] | None = None,
    shot_labels: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Run layout lint at 390/768/1280 for each named Go path."""
    out = _out_dir()
    out.mkdir(parents=True, exist_ok=True)
    findings: list[dict[str, Any]] = []
    base_url = go_web["base_url"]
    labels = shot_labels or {}

    with sync_api.sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(**chromium_launch_kwargs())
        except Exception:
            if REQUIRE_BROWSER:
                raise
            pytest.skip("Chromium is required for Go layout lint")

        for width in SHOT_WIDTHS:
            context = browser.new_context(viewport={"width": width, "height": 1000})
            context.add_cookies(
                [
                    {"name": "ubyhost_session", "value": cookie, "url": base_url + "/"},
                    {"name": "ubyhost_lang", "value": "en", "url": base_url + "/"},
                ]
            )
            register_static_routes(context)
            page = context.new_page()
            for name, path in paths.items():
                if extra and name in extra:
                    extra[name](page)
                response = page.goto(f"{base_url}{path}")
                status = response.status if response else 599
                assert status < 400, f"{name}/{width}: HTTP {status}"
                page.wait_for_load_state("networkidle")
                if after and name in after:
                    after[name](page)
                    page.wait_for_load_state("networkidle")
                settle_motion(page)
                page.evaluate("window.scrollTo(0, 0)")
                for item in page.evaluate(LINT):
                    findings.append({"route": name, "width": width, "finding": item})
                label = labels.get(name, name)
                page.screenshot(path=str(out / f"{label}-{width}.png"), full_page=True)
            context.close()
        browser.close()
    return findings


def assert_no_layout_findings(findings: list[dict[str, Any]]) -> None:
    counts: dict[str, int] = {}
    for row in findings:
        counts[row["finding"][0]] = counts.get(row["finding"][0], 0) + 1
    unique: dict[str, list[str]] = {}
    for row in findings:
        unique.setdefault(json.dumps(row["finding"][:2]), []).append(f"{row['route']}@{row['width']}")
    lines = [
        f"{key} on {', '.join(pages[:4])}{' ...' if len(pages) > 4 else ''} ({len(pages)}x)"
        for key, pages in list(unique.items())[:60]
    ]
    assert not findings, f"{len(findings)} layout-lint findings {counts}\n" + "\n".join(lines)