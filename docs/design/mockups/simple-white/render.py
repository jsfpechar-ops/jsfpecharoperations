"""Render the mockups to PNG (host pages: desktop and tablet only; guest pages: phone): App/.venv/bin/python docs/design/mockups/simple-white/render.py OUT_DIR"""
import re
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).parent
SIDE = (HERE / "_side.html").read_text()
HOST_PAGES = ("stay", "stay-archived")
GUEST_PAGES = ("guest-email", "guest-sent")


def build(tmp: Path) -> None:
    (tmp / "simple.css").write_text((HERE / "simple.css").read_text())
    for name in HOST_PAGES + GUEST_PAGES:
        html = (HERE / f"{name}.html").read_text()
        html = re.sub(r"<!--SIDE:(\w+)-->", lambda m: SIDE.replace(f'data-k="{m.group(1)}"', 'class="on"'), html)
        (tmp / f"{name}.html").write_text(html)


def main(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as d, sync_playwright() as p:
        tmp = Path(d)
        build(tmp)
        browser = p.chromium.launch()
        jobs = [(n, w, 820) for n in HOST_PAGES for w in (1280, 1024)] + [(n, 390, 844) for n in GUEST_PAGES]
        for name, width, height in jobs:
            page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=2)
            page.goto((tmp / f"{name}.html").as_uri())
            page.screenshot(path=str(out / f"{name}-{width}.png"), full_page=True)
            page.close()
        browser.close()


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/mockups"))
