"""Capture the same URL on Python FastAPI and Go, then compare screenshots.

Run from App/:

    .venv/bin/python scripts/go_page_parity_screenshots.py \\
        --name login --path '/login?lang=en' --out /tmp/parity-login

The tool writes per width: ``<name>-<w>-py.png``, ``<name>-<w>-go.png``,
``<name>-<w>-side.png`` (Python left, Go right), ``<name>-<w>-diff.png``, and
``parity-report.json`` / ``parity-report.md`` in ``--out``.

Python renders through a local uvicorn of ``app.main:app`` (no Go proxy).
Go uses ``--go-base`` or starts ``ubyhost-web`` when ``UBYHOST_TEST_DATABASE_URL``
(or ``UBYHOST_DATABASE_URL``) is set. Brief 1820.

A logged-in page needs ``--py-cookie-value`` and ``--go-cookie-value``: the two
stacks sign their own sessions, so one token only ever works on the stack that
issued it, and comparing a signed-in page with one token compares a signed-in
page with an anonymous one. ``--cookie-value`` still sets both, for a bare
``/login`` comparison.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import sys
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

APP = Path(__file__).resolve().parents[1]
REPO = APP.parent
# Running this as ``scripts/<name>.py`` puts ``App/scripts`` on sys.path, not ``App/``, so
# ``from app import db`` failed. Make the documented invocation work without PYTHONPATH.
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))
WIDTHS_DEFAULT = (390, 768, 1280)
# Sub-pixel antialiasing and font hinting stay under this per RGB channel.
INVISIBLE_MAX_DELTA = 2
# When more than this fraction of pixels differ above INVISIBLE_MAX_DELTA, the diff is visible.
VISIBLE_RATIO = 0.0005


@dataclass
class WidthResult:
    width: int
    py_png: str
    go_png: str
    side_png: str
    diff_png: str
    verdict: str  # identical | invisible | visible
    max_delta: int
    diff_pixels: int
    total_pixels: int
    note: str = ""


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "page"


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _start_uvicorn(public_base: str) -> tuple[str, Any]:
    import uvicorn
    from app import db
    from app.main import app

    db.init_db()
    port = _free_port()
    host = "127.0.0.1"
    server = uvicorn.Server(uvicorn.Config(app, host=host, port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 20
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    if not server.started:
        raise RuntimeError("Python test server did not start")
    return f"http://{host}:{port}", server


def _go_base_from_env() -> str | None:
    url = os.environ.get("GO_PAGE_PARITY_GO_BASE", "").strip()
    if url:
        return url.rstrip("/")
    db = os.environ.get("UBYHOST_DATABASE_URL") or os.environ.get("UBYHOST_TEST_DATABASE_URL")
    if not db:
        return None
    # Import only when Postgres is configured (Go binary needs it).
    sys.path.insert(0, str(APP / "tests"))
    try:
        from go_stack import ensure_go_running  # type: ignore

        # The helper takes the public base positionally and returns the URL it actually serves on.
        return ensure_go_running("http://127.0.0.1:1")
    finally:
        sys.path.pop(0)


def compare_images(py_path: Path, go_path: Path) -> tuple[str, int, int, int, str]:
    from PIL import Image, ImageChops

    py = Image.open(py_path).convert("RGB")
    go = Image.open(go_path).convert("RGB")
    if py.size != go.size:
        w = min(py.width, go.width)
        h = min(py.height, go.height)
        py = py.crop((0, 0, w, h))
        go = go.crop((0, 0, w, h))
        note = f"cropped to {w}x{h} for compare"
    else:
        note = ""
    diff = ImageChops.difference(py, go)
    bbox = diff.getbbox()
    if bbox is None:
        return "identical", 0, 0, py.width * py.height, note
    flat = diff.get_flattened_data() if hasattr(diff, "get_flattened_data") else diff.getdata()
    pixels = list(flat)
    total = len(pixels)
    max_delta = 0
    hot = 0
    for r, g, b in pixels:
        peak = max(r, g, b)
        max_delta = max(max_delta, peak)
        if peak > INVISIBLE_MAX_DELTA:
            hot += 1
    ratio = hot / total if total else 0.0
    if hot == 0 or (max_delta <= INVISIBLE_MAX_DELTA and ratio <= VISIBLE_RATIO):
        return "invisible", max_delta, hot, total, note or "within invisible tolerance"
    return "visible", max_delta, hot, total, note


def write_diff_image(py_path: Path, go_path: Path, out_path: Path) -> None:
    from PIL import Image, ImageChops, ImageEnhance

    py = Image.open(py_path).convert("RGB")
    go = Image.open(go_path).convert("RGB")
    w = min(py.width, go.width)
    h = min(py.height, go.height)
    py = py.crop((0, 0, w, h))
    go = go.crop((0, 0, w, h))
    diff = ImageChops.difference(py, go)
    boosted = ImageEnhance.Brightness(diff).enhance(4.0)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    boosted.save(out_path, format="PNG")


def write_side_by_side(py_path: Path, go_path: Path, out_path: Path) -> None:
    from PIL import Image

    py = Image.open(py_path).convert("RGB")
    go = Image.open(go_path).convert("RGB")
    gap = 4
    height = max(py.height, go.height)
    canvas = Image.new("RGB", (py.width + gap + go.width, height), (32, 32, 32))
    canvas.paste(py, (0, 0))
    canvas.paste(go, (py.width + gap, 0))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, format="PNG")


def capture_png(
    playwright,
    base: str,
    path: str,
    width: int,
    dest: Path,
    *,
    cookie_name: str | None = None,
    cookie_value: str | None = None,
    settle: bool = True,
) -> None:
    from tests.browser_support import chromium_launch_kwargs, settle_motion

    dest.parent.mkdir(parents=True, exist_ok=True)
    browser = playwright.chromium.launch(**chromium_launch_kwargs())
    try:
        context = browser.new_context(viewport={"width": width, "height": 900})
        cookies = []
        if cookie_name and cookie_value:
            cookies.append({"name": cookie_name, "value": cookie_value, "url": base + "/"})
        if cookies:
            context.add_cookies(cookies)

        page = context.new_page()
        url = base.rstrip("/") + path
        response = page.goto(url, wait_until="networkidle")
        if response is None or response.status >= 400:
            raise RuntimeError(f"{url} returned {getattr(response, 'status', None)}")
        if settle:
            settle_motion(page)
        page.evaluate("window.scrollTo(0, 0)")
        page.screenshot(path=str(dest), full_page=True)
        context.close()
    finally:
        browser.close()


def _run_pre_sql(statements: Iterable[str]) -> None:
    """Neutralise one-shot state before each stack's capture.

    Python and Go share one database here, so anything that fires once and then
    marks itself done is consumed by whichever stack rendered first, and the
    second capture differs for a reason that is not the page. The known case is
    ``user_account.two_factor_prompted_at``: the "Add a second way in?" dialog
    (task 0004) shows on the first app page after login and ``app.js`` clears it
    on open, so ``/reservations`` read ``visible`` at 390 px against an identical
    page until this ran. Pass the neutraliser once per statement:

        --pre-sql "UPDATE user_account SET two_factor_prompted_at = NULL"
    """
    pending = [s for s in statements if s.strip()]
    if not pending:
        return
    from app import db

    for statement in pending:
        db.execute(statement)


def run_case(
    *,
    name: str,
    path: str,
    out_dir: Path,
    py_base: str,
    go_base: str,
    widths: Iterable[int] = WIDTHS_DEFAULT,
    cookie_name: str | None = None,
    cookie_value: str | None = None,
    py_cookie_value: str | None = None,
    go_cookie_value: str | None = None,
    pre_sql: Iterable[str] = (),
) -> list[WidthResult]:
    import playwright.sync_api as sync_api

    slug = _slug(name)
    out_dir.mkdir(parents=True, exist_ok=True)
    results: list[WidthResult] = []
    with sync_api.sync_playwright() as playwright:
        for width in widths:
            py_png = out_dir / f"{slug}-{width}-py.png"
            go_png = out_dir / f"{slug}-{width}-go.png"
            side_png = out_dir / f"{slug}-{width}-side.png"
            diff_png = out_dir / f"{slug}-{width}-diff.png"
            _run_pre_sql(pre_sql)
            capture_png(
                playwright, py_base, path, width, py_png,
                cookie_name=cookie_name, cookie_value=py_cookie_value or cookie_value,
            )
            _run_pre_sql(pre_sql)
            capture_png(
                playwright, go_base, path, width, go_png,
                cookie_name=cookie_name, cookie_value=go_cookie_value or cookie_value,
            )
            write_side_by_side(py_png, go_png, side_png)
            write_diff_image(py_png, go_png, diff_png)
            verdict, max_delta, diff_px, total_px, note = compare_images(py_png, go_png)
            results.append(
                WidthResult(
                    width=width,
                    py_png=str(py_png),
                    go_png=str(go_png),
                    side_png=str(side_png),
                    diff_png=str(diff_png),
                    verdict=verdict,
                    max_delta=max_delta,
                    diff_pixels=diff_px,
                    total_pixels=total_px,
                    note=note,
                )
            )
    report_json = out_dir / "parity-report.json"
    report_md = out_dir / "parity-report.md"
    payload = {
        "name": name,
        "path": path,
        "py_base": py_base,
        "go_base": go_base,
        "widths": [asdict(r) for r in results],
    }
    report_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    lines = [
        f"# Page parity: {name}",
        "",
        f"Path: `{path}`",
        "",
        "| width | verdict | max Δ | diff px | note |",
        "| --- | --- | ---: | ---: | --- |",
    ]
    for r in results:
        lines.append(
            f"| {r.width} | {r.verdict} | {r.max_delta} | {r.diff_pixels} | {r.note} |"
        )
    lines.append("")
    invisible = [r for r in results if r.verdict == "invisible"]
    if invisible:
        lines.append("## Allowed invisible diffs")
        lines.append("")
        for r in invisible:
            lines.append(
                f"- **{r.width}px**: max channel delta {r.max_delta}, "
                f"{r.diff_pixels}/{r.total_pixels} hot pixels — {r.note}"
            )
        lines.append("")
    visible = [r for r in results if r.verdict == "visible"]
    if visible:
        lines.append("## Visible diffs (explain before merge)")
        lines.append("")
        for r in visible:
            lines.append(f"- **{r.width}px**: see `{Path(r.diff_png).name}`")
        lines.append("")
    report_md.write_text("\n".join(lines), encoding="utf-8")
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Python vs Go page screenshot parity")
    parser.add_argument("--name", "--case", dest="name", required=True, help="case label for output files")
    parser.add_argument("--path", required=True, help="URL path and query, e.g. /login?lang=en")
    parser.add_argument("--out", type=Path, required=True, help="output directory")
    parser.add_argument("--py-base", help="Python origin (default: local uvicorn)")
    parser.add_argument("--go-base", help="Go origin (default: start ubyhost-web when DB URL set)")
    parser.add_argument("--cookie-name", default=os.environ.get("UBYHOST_SESSION_COOKIE", "ubyhost_session"))
    parser.add_argument("--cookie-value", default=os.environ.get("GO_PAGE_PARITY_COOKIE", ""))
    parser.add_argument(
        "--py-cookie-value",
        default=os.environ.get("GO_PAGE_PARITY_PY_COOKIE", ""),
        help="session token for the Python stack only; the two sign their own "
        "sessions, so a logged-in page needs one value per stack",
    )
    parser.add_argument(
        "--go-cookie-value",
        default=os.environ.get("GO_PAGE_PARITY_GO_COOKIE", ""),
        help="session token for the Go stack only",
    )
    parser.add_argument("--widths", default=",".join(str(w) for w in WIDTHS_DEFAULT))
    parser.add_argument("--fail-on-visible", action="store_true", help="exit 1 when any width is visible")
    parser.add_argument(
        "--pre-sql",
        action="append",
        default=[],
        help="statement run before each stack renders, to neutralise one-shot state "
        "(e.g. \"UPDATE user_account SET two_factor_prompted_at = NULL\"); repeatable",
    )
    args = parser.parse_args(argv)

    widths = tuple(int(w.strip()) for w in args.widths.split(",") if w.strip())
    py_server = None
    try:
        if args.py_base:
            py_base = args.py_base.rstrip("/")
        else:
            os.chdir(APP)
            py_base, py_server = _start_uvicorn("http://127.0.0.1:1")

        go_base = (args.go_base or _go_base_from_env() or "").rstrip("/")
        if not go_base:
            print(
                "go base missing: pass --go-base or set UBYHOST_TEST_DATABASE_URL",
                file=sys.stderr,
            )
            return 2

        py_val = (args.py_cookie_value or args.cookie_value) or None
        go_val = (args.go_cookie_value or args.cookie_value) or None
        cookie_val = py_val or go_val
        cookie_name = args.cookie_name if cookie_val else None
        results = run_case(
            name=args.name,
            path=args.path,
            out_dir=args.out,
            py_base=py_base,
            go_base=go_base,
            widths=widths,
            cookie_name=cookie_name,
            cookie_value=cookie_val,
            py_cookie_value=py_val,
            go_cookie_value=go_val,
            pre_sql=args.pre_sql,
        )
    finally:
        if py_server is not None:
            py_server.should_exit = True

    worst = max((r.verdict == "visible" for r in results), default=False)
    for r in results:
        print(f"{r.width}px: {r.verdict} (max_delta={r.max_delta}, diff_pixels={r.diff_pixels})")
    print(f"wrote {args.out / 'parity-report.md'}")
    if worst and args.fail_on_visible:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())