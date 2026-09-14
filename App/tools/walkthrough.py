"""Drive the app through a full host + guest flow and screenshot every page.

This is a development aid: it fills the forms over HTTP the way a browser
would, then renders each resulting page with headless Chrome so the layout can
be reviewed. Run it against a throwaway database.

    .venv/bin/python tools/walkthrough.py [base_url] [out_dir]
"""
from __future__ import annotations

import base64
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

def _find_chrome() -> str:
    candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "google-chrome",
        "chromium",
        "chromium-browser",
    ]
    for candidate in candidates:
        if Path(candidate).exists() or shutil.which(candidate):
            return candidate
    raise SystemExit("No Chrome or Chromium binary found for rendering screenshots.")


CHROME = _find_chrome()
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8080"
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else ".screenshots")
PASSWORD = "Testpassword123"
MOCK = f"{urlparse(BASE).scheme}://{urlparse(BASE).hostname}:8081"

OUT.mkdir(parents=True, exist_ok=True)
session = requests.Session()
step = 0

SIGNATURE = "data:image/png;base64," + base64.b64encode(
    base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFAAH/q842iQAAAABJRU5ErkJggg=="
    )
).decode()


def render(html: str, target: Path, width: int = 1440, height: int = 1000) -> None:
    """Write one HTML string to a PNG with headless Chrome."""
    html = html.replace('href="/static/', f'href="{BASE}/static/')
    html = html.replace('src="/static/', f'src="{BASE}/static/')
    with tempfile.TemporaryDirectory() as profile:
        page = Path(profile) / "page.html"
        page.write_text(html)
        process = subprocess.Popen(
            [
                CHROME,
                "--headless=new",
                # Containers have no sandbox namespace and a tiny /dev/shm.
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--hide-scrollbars",
                "--no-first-run",
                "--disable-crash-reporter",
                "--disable-breakpad",
                "--disable-extensions",
                "--disable-sync",
                f"--user-data-dir={profile}/chrome",
                f"--window-size={width},{height}",
                "--screenshot=" + str(target),
                page.as_uri(),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        # Headless Chrome writes the PNG and then sometimes fails to exit when
        # there is no session bus, so wait for a PNG that has stopped growing
        # rather than for the process.
        deadline = time.monotonic() + 60
        last = -1
        while time.monotonic() < deadline:
            if process.poll() is not None:
                break
            size = target.stat().st_size if target.exists() else 0
            if size and size == last:
                break
            last = size
            time.sleep(0.4)
        if process.poll() is None:
            process.kill()
        process.wait(timeout=10)
        if not target.exists():
            raise SystemExit(f"Chrome produced no screenshot for {target.name}")


def shot(path: str, name: str, width: int = 1440, height: int = 1000) -> None:
    """Render one page with the session cookies and save a PNG."""
    global step
    step += 1
    target = OUT / f"{step:02d}-{name}.png"
    cookies = "; ".join(f"{c.name}={c.value}" for c in session.cookies)
    # Chrome cannot be handed cookies on the command line, so the page is
    # fetched here and written to a file that Chrome then renders.
    render(session.get(BASE + path).text, target, width, height)
    size = target.stat().st_size if target.exists() else 0
    print(f"  {target}  ({size // 1024} kB)  <- {path} [cookies: {len(cookies) > 0}]")


def post(path: str, data: dict | None = None, expect=(200, 303)) -> requests.Response:
    response = session.post(BASE + path, data=data, allow_redirects=False)
    assert response.status_code in expect, f"POST {path} -> {response.status_code}"
    return response


def main() -> None:
    landing = session.get(BASE + "/", allow_redirects=False)
    if landing.status_code == 303 and landing.headers.get("location", "").startswith("/login"):
        username = os.environ.get("UBYHOST_ADMIN_USERNAME", "admin")
        password = os.environ.get("UBYHOST_ADMIN_PASSWORD", "")
        if not password:
            credentials = Path(os.environ.get("UBYHOST_DATA_DIR", "data")) / "initial_admin_credentials"
            if credentials.exists():
                values = dict(
                    line.split("=", 1) for line in credentials.read_text().splitlines() if "=" in line
                )
                username = values.get("username", username)
                password = values.get("password", "")
        if not password:
            raise SystemExit(
                "Host login is enabled. Set UBYHOST_ADMIN_USERNAME and UBYHOST_ADMIN_PASSWORD."
            )
        logged_in = session.post(
            BASE + "/login",
            data={"username": username, "password": password},
            allow_redirects=False,
        )
        if logged_in.status_code != 303:
            raise SystemExit("Could not log in with the configured walkthrough credentials.")
        if logged_in.headers.get("location", "").startswith("/account/password"):
            changed = session.post(
                BASE + "/account/password",
                data={
                    "current_password": password,
                    "new_password": PASSWORD,
                    "confirm_password": PASSWORD,
                },
                allow_redirects=False,
            )
            if changed.status_code != 303:
                raise SystemExit("Could not complete the required first password change.")

    print("1. empty dashboard and login screen")
    shot("/", "dashboard-empty")
    shot("/login", "login")

    print("2. legal entity")
    post("/entities", {
        "name": "Josef Novák",
        "ico": "12345678",
        "seat": "Korunní 1234/12a, 120 00 Praha 2",
    })
    shot("/entities", "entities")

    print("3. apartment")
    entity_page = session.get(BASE + "/entities").text
    entity_id = re.search(r'name="legal_entity_id"[^>]*>|value="(\d+)"', entity_page)
    response = post("/apartments", {
        "internal_name": "Vinohrady Studio",
        "legal_entity_id": "1",
        "city_en": "Prague",
        "uby_idub": "100227887600",
        "uby_mark": "CZGFW",
        "uby_name": "Vinohrady Studio",
        "uby_contact": "host@example.com",
        "addr_okres": "Praha 2",
        "addr_obec": "Praha",
        "addr_obec_cast": "Vinohrady",
        "addr_street": "Korunní",
        "addr_house_no": "1234",
        "addr_orient_no": "12a",
        "addr_zip": "120 00",
        "uby_ws_user": "UBY-WS12cdef",
        "uby_ws_password": "mockpassword",
        "automation_mode": "immediate",
        "default_purpose": "10",
        "permalink_window_days": "3",
        "checkin_info": "Self check-in, key box code sent on the day of arrival.",
        "active": "on",
    })
    apartment_id = int(re.search(r"/apartments/(\d+)", response.headers["location"]).group(1))
    shot(f"/apartments/{apartment_id}", "apartment-saved")

    print("4. connection test + code lists")
    post(f"/apartments/{apartment_id}/test-connection")
    shot(f"/apartments/{apartment_id}", "apartment-connection-tested")
    post(f"/apartments/{apartment_id}/refresh-codelists")

    print("5. calendar feed")
    post(f"/apartments/{apartment_id}/feeds", {
        "url": f"{MOCK}/sample-airbnb.ics",
        "label": "Airbnb",
        "own_name": "Airbnb",
    })
    post("/sync")
    for _ in range(25):
        if 'data-href="/reservations/' in session.get(BASE + "/reservations").text:
            break
        time.sleep(0.2)
    shot(f"/apartments/{apartment_id}", "apartment-with-feed")
    shot("/", "dashboard-with-stays")
    shot("/reservations", "reservations")

    print("6. guest flow")
    page = session.get(BASE + f"/apartments/{apartment_id}").text
    token = re.search(r"/l/([A-Za-z0-9]{6,20})", page).group(1)
    guest = requests.Session()

    landing = guest.get(f"{BASE}/l/{token}", allow_redirects=True)
    print(f"   guest landed on {landing.url}")
    guest_shot(guest, f"/l/{token}", "guest-landing")

    # Guest links are PIN-gated by default, so clear the gate the way a guest
    # would after reading the PIN in their arrival message.
    if 'name="pin"' in landing.text:
        links = session.get(BASE + "/guest-links").text
        pin = re.search(
            rf'id="pin-{apartment_id}"[^>]*value="(\d{{4,6}})"', links
        ).group(1)
        print(f"   entering guest PIN {pin}")
        guest.post(f"{BASE}/l/{token}/pin", data={"pin": pin, "return_to": f"/l/{token}"},
                   allow_redirects=False)
        landing = guest.get(f"{BASE}/l/{token}", allow_redirects=True)
        guest_shot(guest, f"/l/{token}", "guest-landing-unlocked")

    # With one upcoming stay the link opens it directly; with several the guest
    # gets a picker first, so take the stay id from whichever page we landed on.
    found = re.search(r"/l/[^/]+/(\d+)", landing.url) or re.search(
        r'href="/l/[^/"]+/(\d+)', landing.text
    )
    assert found, f"no stay to fill in at {landing.url}"
    reservation_id = int(found.group(1))
    guest.post(f"{BASE}/l/{token}/{reservation_id}/party", data={"party_size": "2"},
               allow_redirects=False)
    guest_shot(guest, f"/l/{token}/{reservation_id}", "guest-stay-overview")
    guest_shot(guest, f"/l/{token}/{reservation_id}/new", "guest-form")
    guest_shot(guest, f"/l/{token}/{reservation_id}/new?lang=cs", "guest-form-czech")

    saved = guest.post(f"{BASE}/l/{token}/{reservation_id}/save", data={
        "surname": "Smith",
        "first_name": "John Paul",
        "birth_date": "1.1.1990",
        "nationality": "GBR",
        "doc_number": "P1234567",
        "res_street": "Baker Street 221B",
        "res_city": "London",
        "res_country": "GBR",
        "purpose": "10",
        "signature": SIGNATURE,
    }, allow_redirects=False)
    print(f"   guest form saved -> {saved.status_code}")
    guest_shot(guest, f"/l/{token}/{reservation_id}", "guest-after-submit")

    # An incomplete second attempt, to capture the validation screen.
    bad = guest.post(f"{BASE}/l/{token}/{reservation_id}/save", data={
        "surname": "X1",
        "first_name": "",
        "birth_date": "31.02.1990",
        "nationality": "UK",
        "doc_number": "AB1",
        "res_city": "",
        "res_country": "",
        "purpose": "10",
    }, allow_redirects=False)
    (OUT / "guest-validation.html").write_text(bad.text)
    render_html(bad.text, "guest-form-validation")

    print("7. host dashboard after report")
    shot("/", "dashboard-reported")
    shot(f"/reservations/{reservation_id}", "reservation-detail")
    shot("/submissions", "submissions")
    submissions = session.get(BASE + "/submissions").text
    match = re.search(r"/submissions/(\d+)", submissions)
    if match:
        submission_id = match.group(1)
        shot(f"/submissions/{submission_id}", "submission-detail")
        receipt = session.get(f"{BASE}/submissions/{submission_id}/receipt.pdf")
        print(f"   receipt.pdf: {receipt.status_code} {receipt.headers.get('content-type')} "
              f"{len(receipt.content)} bytes, starts {receipt.content[:5]!r}")
        (OUT / "receipt.pdf").write_bytes(receipt.content)

    guests = session.get(BASE + "/reservations/%d" % reservation_id).text
    guest_match = re.search(r"/guests/(\d+)", guests)
    if guest_match:
        shot(f"/guests/{guest_match.group(1)}", "guest-admin-form")
        pdf = session.get(f"{BASE}/guests/{guest_match.group(1)}/form.pdf")
        print(f"   registration form pdf: {pdf.status_code} {len(pdf.content)} bytes")
        (OUT / "registration-form.pdf").write_bytes(pdf.content)

    shot("/housebook", "housebook")
    shot("/settings", "settings")
    shot("/apartments", "apartments-list")
    csv = session.get(BASE + "/housebook.csv")
    print(f"   housebook.csv: {csv.status_code} {len(csv.content)} bytes")
    print(f"\nScreenshots in {OUT.resolve()}")


def guest_shot(guest_session, path: str, name: str) -> None:
    global session
    host_session, session = session, guest_session
    try:
        shot(path, name)
    finally:
        session = host_session


def render_html(html: str, name: str) -> None:
    global step
    step += 1
    target = OUT / f"{step:02d}-{name}.png"
    render(html, target)
    print(f"  {target}")


if __name__ == "__main__":
    main()
