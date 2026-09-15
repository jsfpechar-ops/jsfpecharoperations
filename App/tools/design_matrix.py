"""Capture the five critical UI screens across language and viewport.

Run against a populated local instance:
  UBYHOST_ADMIN_PASSWORD=... .venv/bin/python tools/design_matrix.py [base] [out]
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from walkthrough import render  # noqa: E402

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8080"
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "/opt/cursor/artifacts/ubyhost-design-matrix")
OUT.mkdir(parents=True, exist_ok=True)


def main() -> None:
    host = requests.Session()
    username = os.environ.get("UBYHOST_ADMIN_USERNAME", "admin")
    password = os.environ.get("UBYHOST_ADMIN_PASSWORD", "")
    logged_in = host.post(
        BASE + "/login",
        data={"username": username, "password": password},
        allow_redirects=False,
    )
    if logged_in.status_code != 303:
        raise SystemExit("Could not log in for the design matrix.")

    stays = host.get(BASE + "/reservations").text
    stay_match = re.search(r'data-href="/reservations/(\d+)', stays)
    if not stay_match:
        raise SystemExit("Populate at least one stay before capturing the design matrix.")
    stay_id = stay_match.group(1)

    links = host.get(BASE + "/guest-links").text
    token_match = re.search(r'value="[^"]*/l/([A-Za-z0-9]+)"', links)
    if not token_match:
        raise SystemExit("No guest link found.")
    token = token_match.group(1)
    pin_match = re.search(r'id="pin-\d+"[^>]*value="(\d{4,6})"', links)

    guest = requests.Session()
    if pin_match:
        guest.post(
            f"{BASE}/l/{token}/pin",
            data={"pin": pin_match.group(1), "return_to": f"/l/{token}"},
            allow_redirects=False,
        )
    picker = guest.get(f"{BASE}/l/{token}").text
    guest_stay = re.search(r'href="/l/[^/"]+/(\d+)', picker)
    guest_path = f"/l/{token}/{guest_stay.group(1)}/new" if guest_stay else f"/l/{token}"

    screens = {
        "overview": (host, "/"),
        "stays": (host, "/reservations"),
        "stay-detail": (host, f"/reservations/{stay_id}"),
        "housebook": (host, "/housebook"),
        "guest-form": (guest, guest_path),
    }
    for language in ("en", "cs"):
        host.cookies.set("ubyhost_lang", language, domain="127.0.0.1", path="/")
        for width in (390, 1440):
            for name, (session, path) in screens.items():
                separator = "&" if "?" in path else "?"
                url = path + (f"{separator}lang={language}" if name == "guest-form" else "")
                html = session.get(BASE + url).text
                target = OUT / f"{name}-{width}-light-{language}.png"
                render(html, target, width=width, height=1000)
                    print(target)


if __name__ == "__main__":
    main()
