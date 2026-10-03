"""W5.5: ``routes/admin.py`` is split by audience, not by accident.

The host routes now live in four modules - ``admin`` for the pages, ``api`` for
the command palette, ``onboarding`` for the first-run flow and ``exports`` for
everything that answers with bytes. These tests pin the split itself: which
module owns which path, that ``admin.router`` still includes all of them, that
the host POST protection survives the extra hop through ``include_router``, and
that the export routes are not shadowed by the int-typed path parameters that
share their prefix.
"""
from __future__ import annotations

import pathlib

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app import auth, db, reporting, security
from app.main import app
from app.routes import admin, admin_accounts, api, exports, onboarding

PASSWORD = "Secure-Password-123"
USERNAME = "route-split-host"

MOVED_PATHS = {
    api: {
        ("GET", "/api/command-palette"),
    },
    onboarding: {
        ("POST", "/demo"),
        ("POST", "/demo/reset"),
        ("GET", "/onboarding"),
        ("POST", "/onboarding/dismiss"),
        ("POST", "/onboarding/resume"),
        ("POST", "/celebrations/dismiss"),
    },
    exports: {
        ("GET", "/reservations.csv"),
        ("GET", "/guests/{guest_id}/form.pdf"),
        ("GET", "/guests/{guest_id}/export.json"),
        ("GET", "/submissions/receipts.zip"),
        ("GET", "/submissions/{submission_id}/receipt.pdf"),
        ("GET", "/submissions/{submission_id}/errors.pdf"),
        ("GET", "/submissions/{submission_id}/{which}.xml"),
        ("GET", "/housebook.csv"),
        ("GET", "/housebook/pdfs.zip"),
        ("GET", "/settings/archived"),
        ("POST", "/settings/purge-expired"),
        ("POST", "/settings/workspace-export"),
    },
}


@pytest.fixture(autouse=True)
def _database():
    """``TestClient(app)`` does not run the app's lifespan, so seed the schema."""
    db.init_db()


@pytest.fixture(scope="module", autouse=True)
def _host_account():
    """``require_login`` grants access when *no* accounts exist and bootstrap is off.

    The test environment disables bootstrap, so without an account the guard
    short-circuits and an anonymous request renders the page. Create one first
    so the guard is actually exercised.
    """
    db.init_db()
    if not db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,)):
        auth.create_account(USERNAME, PASSWORD, "Route Split", must_change_password=False)


def _routes(module):
    found = set()
    for route in module.router.routes:
        assert isinstance(route, APIRoute), f"{module.__name__} owns a nested router"
        for method in route.methods:
            if method in ("HEAD", "OPTIONS"):
                continue
            found.add((method, route.path))
    return found


def _included_routers():
    return [
        route.include_context.included_router
        for route in admin.router.routes
        if type(route).__name__ == "_IncludedRouter"
    ]


def _login() -> TestClient:
    client = TestClient(app)
    response = client.post(
        "/login",
        data={"username": USERNAME, "password": PASSWORD},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return client


@pytest.mark.parametrize("module", list(MOVED_PATHS))
def test_each_split_module_owns_exactly_the_routes_it_was_given(module):
    assert _routes(module) == MOVED_PATHS[module]


def test_the_admin_router_still_includes_every_split_module():
    included = _included_routers()
    for module in (api, onboarding, exports):
        assert module.router in included, f"{module.__name__} is not included"
    assert admin_accounts.router in included


def test_admin_keeps_only_the_host_pages():
    """The split is by audience: nothing that answers with bytes is left behind."""
    paths = {route.path for route in admin.router.routes if isinstance(route, APIRoute)}
    for module in (api, onboarding, exports):
        for _method, path in MOVED_PATHS[module]:
            assert path not in paths, f"{path} is still declared in admin.py"
    assert {"/", "/guide", "/entities", "/apartments", "/reservations"} <= paths


def test_the_export_router_is_included_before_the_int_path_parameters():
    """``/reservations.csv`` must be matched before ``/reservations/{id}``.

    Starlette matches in registration order, so including the export router
    anywhere after the ``{reservation_id}`` routes would make the CSV download
    answer 422 instead of streaming.
    """
    order = admin.router.routes
    export_index = next(
        i
        for i, route in enumerate(order)
        if type(route).__name__ == "_IncludedRouter"
        and route.include_context.included_router is exports.router
    )
    for shadowing in ("/reservations/{reservation_id}", "/submissions/{submission_id}"):
        shadow_index = next(
            i
            for i, route in enumerate(order)
            if isinstance(route, APIRoute) and route.path == shadowing
        )
        assert export_index < shadow_index, f"{shadowing} would shadow the export routes"


@pytest.mark.parametrize(
    "path",
    ["/demo", "/demo/reset", "/onboarding/dismiss", "/settings/purge-expired"],
)
def test_a_moved_post_route_still_demands_csrf_proof(path):
    """``protect_host_post`` rides along through ``include_router``.

    The token is supplied explicitly (and wrongly) so the session-wide conftest
    helper leaves the request alone and the dependency gets to reject it.
    """
    client = TestClient(app)
    response = client.post(
        path,
        data={security.CSRF_FIELD: "not-a-token"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].startswith("/login?notice=form_expired")


@pytest.mark.parametrize("path", ["/onboarding", "/settings/archived"])
def test_a_moved_get_route_still_demands_a_session(path):
    client = TestClient(app)
    response = client.get(path, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == f"/login?next={path}"


def test_the_moved_json_api_answers_401_rather_than_redirecting():
    """The command palette is fetched by script, so it must not send a 303."""
    client = TestClient(app)
    response = client.get("/api/command-palette", follow_redirects=False)
    assert response.status_code == 401
    assert response.json() == {"items": []}


def test_the_moved_exports_answer_over_http():
    client = _login()

    csv = client.get("/reservations.csv?from=2026-01-01&to=2026-01-31")
    assert csv.status_code == 200
    assert csv.headers["content-type"].startswith("text/csv")
    assert "Apartment;Arrival;Departure" in csv.text

    housebook = client.get("/housebook.csv")
    assert housebook.status_code == 200
    assert housebook.headers["content-type"].startswith("text/csv")

    palette = client.get("/api/command-palette")
    assert palette.status_code == 200
    assert isinstance(palette.json()["items"], list)

    assert client.get("/onboarding", follow_redirects=False).status_code == 200
    assert client.get("/settings/archived", follow_redirects=False).status_code == 200


def test_the_receipts_zip_route_is_not_shadowed_by_the_submission_detail_route():
    """``/submissions/receipts.zip`` is a literal sibling of ``/submissions/{id}``."""
    client = _login()
    response = client.get("/submissions/receipts.zip", follow_redirects=False)
    # Either a zip, or the "nothing to download yet" bounce - never the 422 that
    # an int path parameter would produce.
    assert response.status_code in (200, 303)
    assert response.status_code != 422


def test_dashboard_rows_lives_in_reporting_and_not_in_the_route_module():
    assert callable(reporting.dashboard_rows)
    assert not hasattr(admin, "dashboard_rows")


def test_the_stays_module_is_named_for_what_it_does():
    import app.stays_export as stays_export

    assert callable(stays_export.iter_export_csv_rows)
    assert not pathlib.Path(stays_export.__file__).name.startswith("stays_import")


def test_nothing_in_the_application_still_imports_stays_import():
    """The rename is complete: only historical prose mentions the old name."""
    package = pathlib.Path(__file__).resolve().parents[1] / "app"
    offenders = [
        str(path.relative_to(package))
        for path in package.rglob("*.py")
        if "stays_import" in path.read_text()
    ]
    assert offenders == []
