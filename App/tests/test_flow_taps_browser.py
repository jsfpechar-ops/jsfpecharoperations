"""Measure taps and typed fields for six flows at 390 px (task 0841).

Seeds one host with one entity, two properties and a complete guest on the
first stay, plus a guest who has finished person 1. Runs scripts/flow_taps.py
against a live test server and writes flow-taps.json. No police submit route
is ever requested.
"""
import importlib.util
import json
import os
import pathlib
import secrets
import threading
import time

import pytest

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

import uvicorn

from app import auth, db
from app.main import app
from tests.browser_support import chromium_launch_kwargs
from tests.invoice_stay_helper import make_stay
from tests.test_guest_residence_prefill import TOKEN, _first_person_done
from tests.test_invoice_autofill import _complete_guest
from tests.test_invoice_stay_browser import _browser_session_cookie, _free_port

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "flow_taps.py"
SHOTS = os.environ.get("UBYHOST_SHOTS_DIR")
OPEN_ITEMS = {"calendar_move_extend_cancel", "cleaning_mark_assign", "single_send_confirm"}


def _load_flow_taps():
    spec = importlib.util.spec_from_file_location("flow_taps", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def base():
    db.init_db()
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 15
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    if not server.started:
        pytest.fail("the test server did not start")
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


def _launch(playwright):
    try:
        return playwright.chromium.launch(**chromium_launch_kwargs())
    except Exception as exc:
        if REQUIRE_BROWSER:
            raise
        pytest.skip(f"Chromium is not available: {exc}")


def test_flow_taps_measure_six_flows_at_390px(base, tmp_path):
    flow_taps = _load_flow_taps()

    # Guest first: _first_person_done resets its own seed data, so host seeding comes after.
    guest_client, guest_reservation, _ = _first_person_done("en")
    guest_cookies = [f"{c.name}={c.value}" for c in guest_client.cookies.jar]
    guest_path = f"/l/{TOKEN}/{guest_reservation['id']}?lang=en"

    username = f"flowtaps{secrets.token_hex(4)}"
    owner = auth.create_account(f"{username}@example.test", "Flow Taps", role="host", username=username)
    entity = db.insert("legal_entity", {
        "name": "Flow s.r.o.", "seat": "Praha 1", "ico": "04656679",
        "registry_entry": "Fyzická osoba zapsaná v živnostenském rejstříku",
        "vat_status": "non_payer", "invoice_due_days": 14,
        "owner_user_id": owner, "created_at": db.utcnow(),
    })
    stay = make_stay(owner, entity_id=entity)
    make_stay(owner, entity_id=entity)  # second property
    apartment = db.query_one("SELECT apartment_id FROM reservation WHERE id = ?", (stay,))["apartment_id"]
    _complete_guest(stay)

    session = _browser_session_cookie(username)
    host_cookie = f"{auth.SESSION_COOKIE}={session}"
    ids = {
        "apartment_id": str(apartment),
        "entity_id": str(entity),
        "stay_id": str(stay),
        "guest_path": guest_path,
    }

    submit_hits = []

    def on_request(request):
        if "/submit" in request.url:
            submit_hits.append(request.url)

    shots = pathlib.Path(SHOTS) if SHOTS else None
    if shots:
        shots.mkdir(parents=True, exist_ok=True)

    results = {}
    with sync_api.sync_playwright() as pw:
        browser = _launch(pw)
        for name in flow_taps.FLOWS:
            cookie = guest_cookies if name == "guest_second_person" else host_cookie
            shot = str(shots / f"{name}-390.png") if shots else None
            results[name] = flow_taps.run_flow(browser, name, base, ids, cookie, shot, on_request)
        context = flow_taps._context(browser, base, host_cookie)
        page = context.new_page()
        page.on("request", on_request)
        open_items = flow_taps.inspect_open_items(page, base, ids)
        context.close()
        browser.close()

    out_dir = shots or tmp_path
    (out_dir / "flow-taps.json").write_text(
        json.dumps({"flows": results, "open_items": open_items}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    assert set(results) == set(flow_taps.FLOWS)
    for name, result in results.items():
        if "not_measured" in result:
            assert name == "guest_second_person", (name, result)
            continue
        assert result["taps"] >= 1, (name, result)
    assert set(open_items) == OPEN_ITEMS
    assert all("present" in item and item.get("evidence") for item in open_items.values())
    assert submit_hits == []
