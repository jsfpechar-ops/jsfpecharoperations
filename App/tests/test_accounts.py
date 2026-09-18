"""Account sessions and cross-workspace authorization boundaries."""
from __future__ import annotations

import base64
import json

from fastapi.testclient import TestClient

from app import auth, config, db, passport_photos
from app.main import app

PASSWORD = "Secure-Password-123"
NEW_PASSWORD = "Even-Better-Password-456"


def _login(username: str, password: str = PASSWORD) -> TestClient:
    client = TestClient(app)
    response = client.post(
        "/login",
        data={"username": username, "password": password},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return client


def _account(username: str, role: str = "host", must_change: bool = False) -> int:
    return auth.create_account(
        username, PASSWORD, username.title(), role=role, must_change_password=must_change
    )


def _apartment(owner_id: int, name: str, token: str) -> int:
    entity_id = db.insert(
        "legal_entity",
        {
            "name": f"{name} entity",
            "owner_user_id": owner_id,
            "created_at": db.utcnow(),
        },
    )
    return db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "owner_user_id": owner_id,
            "internal_name": name,
            "permalink_token": token,
            "permalink_pin": "1234",
            "automation_mode": "manual",
            "submit_after_hours": 24,
            "permalink_window_days": 3,
            "default_purpose": "10",
            "active": 1,
            "created_at": db.utcnow(),
        },
    )


def _clean_accounts() -> None:
    ids = [
        row["id"]
        for row in db.query("SELECT id FROM user_account WHERE username LIKE 'boundary-%'")
    ]
    for user_id in ids:
        db.execute("DELETE FROM alert WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM user_account WHERE id = ?", (user_id,))


def test_hosts_cannot_read_or_mutate_another_workspace():
    db.init_db()
    _clean_accounts()
    first_id = _account("boundary-first")
    second_id = _account("boundary-second")
    first_apartment = _apartment(first_id, "First private flat", "boundaryone")
    second_apartment = _apartment(second_id, "Second private flat", "boundarytwo")
    try:
        first = _login("boundary-first")
        listing = first.get("/apartments")
        assert "First private flat" in listing.text
        assert "Second private flat" not in listing.text

        assert first.get(
            f"/apartments/{second_apartment}", follow_redirects=False
        ).status_code == 303
        response = first.post(
            f"/apartments/{second_apartment}",
            data={"internal_name": "Stolen", "active": "1"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert db.query_one(
            "SELECT internal_name FROM apartment WHERE id = ?", (second_apartment,)
        )["internal_name"] == "Second private flat"

        # The same boundary applies to descendants reached only by numeric id.
        reservation_id = db.insert(
            "reservation",
            {
                "apartment_id": second_apartment,
                "source": "manual",
                "uid": "boundary-stay",
                "date_from": "2026-09-20",
                "date_to": "2026-09-22",
                "status": "active",
                "created_at": db.utcnow(),
                "updated_at": db.utcnow(),
            },
        )
        guest_id = db.insert(
            "guest",
            {
                "reservation_id": reservation_id,
                "surname": "OtherTenantSecret",
                "entered_by": "host",
                "submit_state": "pending",
                "created_at": db.utcnow(),
                "updated_at": db.utcnow(),
            },
        )
        db.update("guest", guest_id, {"passport_photo_at": db.utcnow()})
        passport_photos.save_photo(
            guest_id, b"\xff\xd8\xff" + (b"\x00" * 61), "image/jpeg"
        )
        submission_id = db.insert(
            "submission",
            {
                "apartment_id": second_apartment,
                "created_at": db.utcnow(),
                "state": "ok",
                "receipt_pdf": base64.b64encode(b"%PDF-test").decode(),
                "request_xml": "<private>other workspace</private>",
            },
        )
        assert first.get(f"/guests/{guest_id}", follow_redirects=False).status_code == 303
        assert first.get(
            f"/submissions/{submission_id}", follow_redirects=False
        ).status_code == 303
        assert first.get(f"/submissions/{submission_id}/receipt.pdf").status_code == 404
        assert first.get(f"/submissions/{submission_id}/request.xml").status_code == 404
        assert first.get(f"/guests/{guest_id}/passport-photo").status_code == 404
        assert first.get(f"/reservations/{reservation_id}", follow_redirects=False).status_code == 303
        assert first.get(f"/apartments/{first_apartment}").status_code == 200

        tainted_submission = db.insert(
            "submission",
            {
                "apartment_id": first_apartment,
                "created_at": db.utcnow(),
                "state": "ok",
                "guest_ids": json.dumps([guest_id]),
            },
        )
        detail = first.get(f"/submissions/{tainted_submission}")
        assert detail.status_code == 200
        assert "OtherTenantSecret" not in detail.text
    finally:
        if "guest_id" in locals():
            passport_photos.delete_photo(guest_id)
        _clean_accounts()


def test_reservation_detail_ignores_foreign_submission_reference():
    db.init_db()
    _clean_accounts()
    first_id = _account("boundary-first")
    second_id = _account("boundary-second")
    first_apartment = _apartment(first_id, "First flat", "boundary-first-fk")
    second_apartment = _apartment(second_id, "Second flat", "boundary-second-fk")
    now = db.utcnow()
    try:
        reservation_id = db.insert(
            "reservation",
            {
                "apartment_id": first_apartment,
                "source": "manual",
                "uid": "boundary-first-stay",
                "date_from": "2026-09-20",
                "date_to": "2026-09-22",
                "status": "active",
                "created_at": now,
                "updated_at": now,
            },
        )
        foreign_submission = db.insert(
            "submission",
            {
                "apartment_id": second_apartment,
                "created_at": now,
                "state": "ok",
                "pseudo_stamp": "FOREIGN-SUBMISSION-STAMP",
            },
        )
        db.insert(
            "guest",
            {
                "reservation_id": reservation_id,
                "surname": "Owned Guest",
                "entered_by": "host",
                "submit_state": "pending",
                "submission_id": foreign_submission,
                "created_at": now,
                "updated_at": now,
            },
        )

        page = _login("boundary-first").get(f"/reservations/{reservation_id}")

        assert page.status_code == 200
        assert "FOREIGN-SUBMISSION-STAMP" not in page.text
    finally:
        _clean_accounts()


def test_hosts_cannot_set_new_four_digit_pins():
    db.init_db()
    _clean_accounts()
    owner_id = _account("boundary-pin-owner")
    apartment_id = _apartment(owner_id, "PIN flat", "boundary-pin-update")
    db.update("apartment", apartment_id, {"permalink_pin": "654321"})
    try:
        response = _login("boundary-pin-owner").post(
            f"/apartments/{apartment_id}",
            data={
                "internal_name": "PIN flat",
                "active": "1",
                "permalink_pin": "1234",
            },
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert db.query_one(
            "SELECT permalink_pin FROM apartment WHERE id = ?", (apartment_id,)
        )["permalink_pin"] == "654321"
    finally:
        _clean_accounts()


def test_admin_can_open_a_host_workspace_without_knowing_the_password():
    db.init_db()
    _clean_accounts()
    admin_id = _account("boundary-admin", role="admin")
    host_id = _account("boundary-host")
    _apartment(host_id, "Host workspace flat", "boundaryhost")
    try:
        admin = _login("boundary-admin")
        users = admin.get("/admin/users")
        assert users.status_code == 200
        assert "boundary-host" in users.text
        assert PASSWORD not in users.text

        response = admin.post(
            f"/admin/users/{host_id}/impersonate", follow_redirects=False
        )
        assert response.status_code == 303
        workspace = admin.get("/")
        assert "Host workspace flat" in workspace.text
        assert "Previewing workspace" in workspace.text
        assert "Exit preview" in workspace.text

        admin.post("/admin/stop-impersonating", follow_redirects=False)
        assert admin.get("/admin/users").status_code == 200
        assert _login("boundary-host").get("/admin/users").status_code == 403
    finally:
        _clean_accounts()


def test_temporary_password_must_be_replaced_and_invalidates_old_sessions():
    db.init_db()
    _clean_accounts()
    user_id = _account("boundary-new", must_change=True)
    try:
        client = _login("boundary-new")
        assert client.get("/", follow_redirects=False).headers["location"] == "/account/password"
        changed = client.post(
            "/account/password",
            data={
                "current_password": PASSWORD,
                "new_password": NEW_PASSWORD,
                "confirm_password": NEW_PASSWORD,
            },
            follow_redirects=False,
        )
        assert changed.status_code == 303
        assert _login("boundary-new", NEW_PASSWORD).get("/").status_code == 200
        assert TestClient(app).post(
            "/login",
            data={"username": "boundary-new", "password": PASSWORD},
        ).status_code == 401
        row = db.query_one("SELECT must_change_password FROM user_account WHERE id = ?", (user_id,))
        assert row["must_change_password"] == 0
    finally:
        _clean_accounts()


def test_remember_me_extends_session_max_age():
    assert auth.session_max_age({"rm": 1}) == auth.SESSION_REMEMBER_MAX_AGE
    assert auth.session_max_age({}) == auth.SESSION_MAX_AGE
    assert auth.session_max_age(None) == auth.SESSION_MAX_AGE


def test_remember_me_login_keeps_session_active():
    db.init_db()
    _clean_accounts()
    _account("boundary-remember")
    try:
        client = TestClient(app)
        response = client.post(
            "/login",
            data={"username": "boundary-remember", "password": PASSWORD, "remember": "on"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert client.cookies.get(auth.SESSION_COOKIE)
        assert client.get("/").status_code == 200
    finally:
        _clean_accounts()


def test_bootstrap_admin_claims_existing_data(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "migration.db")
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "BOOTSTRAP_ADMIN", True)
    monkeypatch.setattr(config, "ADMIN_USERNAME", "first-admin")
    monkeypatch.setattr(config, "ADMIN_PASSWORD", PASSWORD)
    db.init_db()
    apartment_id = db.insert(
        "apartment",
        {
            "internal_name": "Legacy flat",
            "permalink_token": "legacymigration",
            "automation_mode": "manual",
            "submit_after_hours": 24,
            "permalink_window_days": 3,
            "default_purpose": "10",
            "active": 1,
            "created_at": db.utcnow(),
        },
    )

    assert auth.ensure_bootstrap_admin() == ""
    admin = db.query_one("SELECT * FROM user_account WHERE username = 'first-admin'")
    assert admin["role"] == "admin"
    assert auth.verify_password(PASSWORD, admin["password_hash"])
    assert db.query_one(
        "SELECT owner_user_id FROM apartment WHERE id = ?", (apartment_id,)
    )["owner_user_id"] == admin["id"]


def test_generate_password_meets_policy():
    for _ in range(20):
        password = auth.generate_password()
        assert not auth.password_error(password)


def test_admin_create_host_generates_password_when_missing():
    db.init_db()
    _clean_accounts()
    admin_id = _account("boundary-admin", role="admin")
    try:
        admin = _login("boundary-admin")
        response = admin.post(
            "/admin/users",
            data={"username": "boundary-auto", "display_name": "Auto Host"},
            follow_redirects=False,
        )
        # Shown in the response body, never in a redirect URL: see
        # tests/test_credential_handling.py for why.
        assert response.status_code == 200
        assert "Temporary password" in response.text
        assert "password" not in response.headers.get("location", "").lower()
        row = db.query_one(
            "SELECT * FROM user_account WHERE username = ?", ("boundary-auto",)
        )
        assert row is not None
        assert row["must_change_password"] == 1
    finally:
        _clean_accounts()


def test_legal_entity_rows_are_clickable_and_can_be_archived():
    db.init_db()
    _clean_accounts()
    admin_id = _account("boundary-admin", role="admin")
    entity_id = db.insert(
        "legal_entity",
        {
            "name": "Archive Test s.r.o.",
            "owner_user_id": admin_id,
            "created_at": db.utcnow(),
        },
    )
    try:
        admin = _login("boundary-admin")
        page = admin.get("/entities")
        assert 'class="clickable-row"' in page.text
        assert 'data-href="/entities?edit=' in page.text

        archived = admin.post(
            f"/entities/{entity_id}/archive",
            follow_redirects=False,
        )
        assert archived.status_code == 303
        row = db.query_one("SELECT archived_at FROM legal_entity WHERE id = ?", (entity_id,))
        assert row["archived_at"]

        restored = admin.post(
            f"/entities/{entity_id}/unarchive",
            follow_redirects=False,
        )
        assert restored.status_code == 303
        row = db.query_one("SELECT archived_at FROM legal_entity WHERE id = ?", (entity_id,))
        assert row["archived_at"] is None
    finally:
        db.execute("DELETE FROM legal_entity WHERE id = ?", (entity_id,))
        _clean_accounts()


def test_host_admin_portal_shows_ubyhost_support_email():
    db.init_db()
    _clean_accounts()
    _account("boundary-support")
    try:
        host = _login("boundary-support")
        overview = host.get("/")
        assert overview.status_code == 200
        assert 'href="mailto:support@ubyhost.com"' in overview.text
        assert "support@ubyhost.com" in overview.text
        settings = host.get("/settings")
        assert settings.status_code == 200
        assert "UbyHost support" in settings.text
        assert "support@ubyhost.com" in settings.text
        assert "Guests with a stay question" in settings.text
    finally:
        _clean_accounts()


def test_settings_archived_hub_lists_and_restores_entities():
    db.init_db()
    _clean_accounts()
    admin_id = _account("boundary-admin", role="admin")
    entity_id = db.insert(
        "legal_entity",
        {
            "name": "Hub Archive s.r.o.",
            "owner_user_id": admin_id,
            "created_at": db.utcnow(),
            "archived_at": db.utcnow(),
        },
    )
    try:
        admin = _login("boundary-admin")
        page = admin.get("/settings/archived")
        assert page.status_code == 200
        assert "Hub Archive s.r.o." in page.text
        assert "Legal entities (1)" in page.text

        settings = admin.get("/settings")
        assert "Open archive hub" in settings.text

        restored = admin.post(
            f"/entities/{entity_id}/unarchive",
            data={"return_to": "/settings/archived"},
            follow_redirects=False,
        )
        assert restored.status_code == 303
        assert restored.headers["location"].startswith("/settings/archived")
    finally:
        db.execute("DELETE FROM legal_entity WHERE id = ?", (entity_id,))
        _clean_accounts()


def test_remember_me_sets_thirty_day_session_cookie():
    db.init_db()
    _clean_accounts()
    _account("boundary-remember")
    try:
        client = TestClient(app)
        response = client.post(
            "/login",
            data={"username": "boundary-remember", "password": PASSWORD, "remember": "1"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        cookie = response.cookies.get(auth.SESSION_COOKIE)
        assert cookie
        set_cookie = response.headers.get_list("set-cookie")
        session_header = next(h for h in set_cookie if h.startswith(f"{auth.SESSION_COOKIE}="))
        assert f"Max-Age={auth.SESSION_REMEMBER_MAX_AGE}" in session_header
        assert "HttpOnly" in session_header
        assert "SameSite=strict" in session_header

        payload = auth._session_payload(cookie)
        assert payload and payload.get("rm") == 1
        assert auth.session_max_age(payload) == auth.SESSION_REMEMBER_MAX_AGE
    finally:
        _clean_accounts()


def test_csv_exports_stream_without_buffering_entire_file():
    """StreamingResponse endpoints should return CSV attachments."""
    db.init_db()
    _clean_accounts()
    _account("boundary-csv")
    try:
        client = TestClient(app)
        client.post(
            "/login",
            data={"username": "boundary-csv", "password": PASSWORD},
            follow_redirects=False,
        )
        housebook_csv = client.get("/housebook.csv")
        assert housebook_csv.status_code == 200
        assert "text/csv" in housebook_csv.headers["content-type"]
        assert housebook_csv.content.startswith(b"\xef\xbb\xbf")

        stays_csv = client.get(
            "/reservations.csv",
            params={"from": "2020-01-01", "to": "2035-12-31"},
        )
        assert stays_csv.status_code == 200
        assert "text/csv" in stays_csv.headers["content-type"]
        assert stays_csv.content.startswith(b"\xef\xbb\xbf")
    finally:
        _clean_accounts()


def test_legal_page_shows_operator_identity():
    response = TestClient(app).get("/legal")
    assert response.status_code == 200
    assert "Josef Pechar" in response.text
    assert "24005169" in response.text
    assert "Kubelíkova" in response.text


def test_terms_page_shows_operator_identity():
    response = TestClient(app).get("/terms")
    assert response.status_code == 200
    assert "Josef Pechar" in response.text
    assert "24005169" in response.text
    assert "Kubelíkova" in response.text
    assert "Terms of Service" in response.text or "Obchodní podmínky" in response.text


def test_login_page_links_to_terms():
    response = TestClient(app).get("/login")
    assert response.status_code == 200
    assert 'href="/terms"' in response.text
    assert "agree to the" in response.text or "souhlasíte" in response.text


def test_legal_page_links_to_terms():
    response = TestClient(app).get("/legal")
    assert response.status_code == 200
    assert 'href="/terms"' in response.text
    assert 'href="mailto:support@ubyhost.com"' in response.text


def test_privacy_page_shows_operator_identity():
    response = TestClient(app).get("/privacy")
    assert response.status_code == 200
    assert "Josef Pechar" in response.text
    assert "24005169" in response.text
    assert "Privacy Policy" in response.text or "Zásady ochrany osobních údajů" in response.text
    assert "ÚOOÚ" in response.text or "uoou.cz" in response.text
    assert "Version 1.2" in response.text or "Verze 1.2" in response.text
    assert "Bot Fight Mode" in response.text
    assert "HSTS" in response.text


def test_login_page_links_to_privacy():
    response = TestClient(app).get("/login")
    assert response.status_code == 200
    assert 'href="/privacy"' in response.text


def test_legal_and_terms_link_to_privacy():
    for path in ("/legal", "/terms"):
        response = TestClient(app).get(path)
        assert response.status_code == 200
        assert 'href="/privacy"' in response.text


def test_dpa_page_shows_operator_and_article_28():
    db.init_db()
    response = TestClient(app).get("/dpa")
    assert response.status_code == 200
    assert "Josef Pechar" in response.text
    assert "24005169" in response.text
    assert "Article 28" in response.text or "čl. 28" in response.text


def test_public_legal_pages_cross_link_dpa():
    db.init_db()
    for path in ("/legal", "/terms", "/privacy"):
        response = TestClient(app).get(path)
        assert response.status_code == 200
        assert 'href="/dpa"' in response.text


def test_login_audit_includes_legal_versions():
    db.init_db()
    from app import config

    client = TestClient(app)
    # Use bootstrap admin if present
    username = config.ADMIN_USERNAME
    password = config.ADMIN_PASSWORD or ""
    if not password:
        creds = config.DATA_DIR / "initial_admin_credentials"
        if creds.exists():
            for line in creds.read_text().splitlines():
                if line.startswith("password="):
                    password = line.split("=", 1)[1].strip()
    if password:
        client.post("/login", data={"username": username, "password": password})
        rows = db.query(
            "SELECT detail FROM audit WHERE action = ? ORDER BY id DESC LIMIT 1",
            ("login",),
        )
        if rows:
            detail = rows[0]["detail"]
            assert f"terms_v{config.TERMS_VERSION}" in detail
            assert f"privacy_v{config.PRIVACY_VERSION}" in detail
            assert f"dpa_v{config.DPA_VERSION}" in detail


def test_submissions_receipts_zip_downloads_bulk_dorucenky():
    db.init_db()
    _clean_accounts()
    owner_id = _account("boundary-receipts")
    apartment_id = _apartment(owner_id, "Receipt flat", "boundaryreceipts")
    submission_id = db.insert(
        "submission",
        {
            "apartment_id": apartment_id,
            "created_at": db.utcnow(),
            "state": "ok",
            "receipt_pdf": base64.b64encode(b"%PDF-1.4 dorucenka").decode(),
            "pseudo_stamp": "ABC-123",
        },
    )
    try:
        client = _login("boundary-receipts")
        page = client.get("/submissions")
        assert page.status_code == 200
        assert "Download Doručenky" in page.text

        response = client.get("/submissions/receipts.zip")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/zip")
        assert len(response.content) > 20
        assert response.content[:2] == b"PK"
    finally:
        db.execute("DELETE FROM submission WHERE id = ?", (submission_id,))
        _clean_accounts()


def test_non_remember_sessions_expire_after_twelve_hours(monkeypatch):
    db.init_db()
    _clean_accounts()
    user_id = _account("boundary-session")
    account = db.query_one("SELECT * FROM user_account WHERE id = ?", (user_id,))
    base = 1_700_000_000.0
    monkeypatch.setattr("itsdangerous.timed.time.time", lambda: base)
    try:
        token = auth.issue_session(account["id"], account["session_version"], remember=False)
        remember_token = auth.issue_session(account["id"], account["session_version"], remember=True)
        assert auth._session_payload(token) is not None
        assert auth._session_payload(remember_token) is not None

        monkeypatch.setattr(
            "itsdangerous.timed.time.time", lambda: base + auth.SESSION_MAX_AGE + 60
        )
        assert auth._session_payload(token) is None
        assert auth._session_payload(remember_token) is not None
    finally:
        _clean_accounts()


def test_every_id_route_is_ownership_scoped():
    """A numeric id must never be enough to reach another workspace.

    Structural rather than behavioural: it catches the next route added
    without an access.py lookup, which no per-route test would.
    """
    import inspect
    import re

    from app.routes import admin as admin_routes
    from app.routes import admin_accounts

    source = "\n".join(
        (inspect.getsource(admin_routes), inspect.getsource(admin_accounts))
    )
    blocks = re.split(r"\n(?=@router\.(?:get|post|put|delete)\()", source)

    # These act across workspaces on purpose and gate on the admin role
    # instead; see user_password_reset / user_impersonate / user_toggle.
    cross_workspace = {"/admin/users/{user_id}"}

    unscoped = []
    for block in blocks:
        header = re.match(r'@router\.(\w+)\("([^"]+)"', block)
        if not header:
            continue
        path = header.group(2)
        if not re.search(r"\{\w*_?id\}", path):
            continue
        if any(path.startswith(prefix) for prefix in cross_workspace):
            assert "_require_admin" in block, f"{path} must check the admin role"
            continue
        name = re.search(r"\n(?:async )?def (\w+)", block)
        if "require_login" not in block:
            unscoped.append((path, "no require_login"))
        elif "access." not in block:
            unscoped.append((path, f"no access.* lookup in {name.group(1) if name else '?'}"))

    assert not unscoped, f"routes reachable by id without ownership scoping: {unscoped}"


def test_production_without_accounts_fails_closed(monkeypatch):
    db.init_db()
    _clean_accounts()
    monkeypatch.setattr(config, "BOOTSTRAP_ADMIN", False)
    monkeypatch.setattr(config, "DEPLOYMENT", "production")

    response = TestClient(app).get("/", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"].startswith("/login")
