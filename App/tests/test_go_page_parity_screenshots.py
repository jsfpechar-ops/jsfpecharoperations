"""Smoke tests for scripts/go_page_parity_screenshots.py (brief 1820)."""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1]
SCRIPT = APP_DIR / "scripts" / "go_page_parity_screenshots.py"


def test_compare_helpers_identical_and_invisible(tmp_path: Path):
    from PIL import Image

    sys.path.insert(0, str(APP_DIR / "scripts"))
    try:
        import go_page_parity_screenshots as mod
    finally:
        sys.path.pop(0)

    a = tmp_path / "a.png"
    b = tmp_path / "b.png"
    Image.new("RGB", (40, 20), (200, 100, 50)).save(a)
    shutil.copy(a, b)
    verdict, mx, hot, total, _ = mod.compare_images(a, b)
    assert verdict == "identical"
    assert mx == 0 and hot == 0

    c = tmp_path / "c.png"
    px = Image.open(a).load()
    img2 = Image.open(a).copy()
    img2.putpixel((5, 5), (px[5, 5][0] + 1, px[5, 5][1], px[5, 5][2]))
    img2.save(c)
    verdict2, mx2, hot2, _, note2 = mod.compare_images(a, c)
    assert verdict2 == "invisible"
    assert mx2 <= mod.INVISIBLE_MAX_DELTA
    assert "invisible" in note2 or hot2 == 0

    d = tmp_path / "d.png"
    Image.new("RGB", (40, 20), (10, 10, 10)).save(d)
    verdict3, _, hot3, _, _ = mod.compare_images(a, d)
    assert verdict3 == "visible"
    assert hot3 > 0


@pytest.mark.skipif(
    not os.environ.get("UBYHOST_TEST_DATABASE_URL") and not os.environ.get("UBYHOST_DATABASE_URL"),
    reason="Go web needs Postgres (UBYHOST_TEST_DATABASE_URL)",
)
@pytest.mark.skipif(shutil.which("go") is None, reason="go not on PATH")
def test_login_page_parity_smoke(tmp_path: Path):
    sync_api = pytest.importorskip("playwright.sync_api")
    _ = sync_api  # noqa: F841 — ensure playwright is installed

    from app import db
    from app.main import app

    db.init_db()
    import uvicorn

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 20
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    if not server.started:
        pytest.fail("python server did not start")
    py_base = f"http://127.0.0.1:{port}"

    sys.path.insert(0, str(APP_DIR))
    try:
        from go_stack import ensure_go_running
    finally:
        sys.path.pop(0)
    go_base = ensure_go_running(public_base=py_base)

    sys.path.insert(0, str(APP_DIR / "scripts"))
    try:
        import go_page_parity_screenshots as mod
    finally:
        sys.path.pop(0)

    out = tmp_path / "login-smoke"
    try:
        results = mod.run_case(
            name="login-smoke",
            path="/login?lang=en",
            out_dir=out,
            py_base=py_base,
            go_base=go_base,
            widths=(390,),
        )
    finally:
        server.should_exit = True
        thread.join(timeout=5)

    assert out.joinpath("parity-report.json").is_file()
    assert len(results) == 1
    assert results[0].verdict in ("identical", "invisible", "visible")
    assert results[0].side_png and Path(results[0].side_png).is_file()


def test_cli_help():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        cwd=APP_DIR,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert "--fail-on-visible" in result.stdout