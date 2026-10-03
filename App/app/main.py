"""Application entrypoint."""
from __future__ import annotations

import logging
import os
import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request, Response
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import JSONResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import (
    alerts,
    auth,
    client_ip,
    config,
    db,
    env_guard,
    host_i18n,
    scheduler,
    security,
    seo,
    templating,
)
from .routes import admin, guest, invoices, legal, stay_fees
from .sample_calendar import sample_calendar_response

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
)
log = logging.getLogger("ubyhost")
# OPS-3: one PII-free line per request, carrying the route template only.
log_access = logging.getLogger("ubyhost.access")


def rotate_weak_permalinks() -> int:
    """Replace missing or legacy short guest PINs; returns how many were rotated.

    ``auth.normalise_permalink_pin`` no longer accepts four digits, but that is
    not the gate the guest actually meets: ``verify_pin`` compares against the
    *stored* value, so a short PIN already in the database keeps opening the form
    until something replaces it. Rotating it here is what retires the weakness,
    and it is deliberately noisy — a log line and an apartment-scoped alert —
    because the host has to put the new PIN into the messages they send guests.

    Idempotent: a six-digit PIN is never selected, so a second run is a no-op.
    """
    weak = db.query(
        "SELECT id, permalink_pin FROM apartment "
        "WHERE permalink_pin IS NULL OR permalink_pin = '' OR LENGTH(permalink_pin) <> 6"
    )
    for row in weak:
        db.update("apartment", row["id"], {"permalink_pin": auth.new_permalink_pin()})
        log.warning(
            "Rotated the guest PIN for apartment %s to six digits (the stored one was %s). "
            "The old PIN no longer opens the guest form; share the new one.",
            row["id"],
            "missing" if not row["permalink_pin"] else f"{len(row['permalink_pin'])} digits",
        )
        alerts.raise_alert(
            "warning",
            "guest_pin_rotated",
            "The guest link PIN was replaced with a new six-digit PIN.",
            detail=(
                "Four-digit PINs are no longer accepted. Copy the new PIN from the "
                "apartment's guest link page and put it in the messages you send guests."
            ),
            dedupe_key=f"guest_pin_rotated:{row['id']}",
            apartment_id=row["id"],
        )
    return len(weak)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Explicit startup work, because importing config no longer creates the data
    # directory or writes the signing key to disk.
    config.ensure_data_dir()
    # Read the key here, where a bad one stops the app from booting. Left lazy,
    # it raised on the first page that signed a cookie: /healthz answered 200
    # while /login answered 500, so the deploy's health check passed and the
    # broken release went live.
    config.secret_key()
    db.init_db()
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = 12_000_000  # every image we render is a signature or a QR code
    bootstrap_password = auth.ensure_bootstrap_admin()
    admin_username = auth.normalise_username(config.ADMIN_USERNAME) or "admin"
    if bootstrap_password:
        log.warning(
            "Created the first administrator (%s). One-time password saved to %s",
            admin_username,
            config.DATA_DIR / "initial_admin_credentials",
        )
    elif bootstrap_password == "":
        log.info(
            "Created the first administrator (%s). Log in using UBYHOST_ADMIN_PASSWORD.",
            admin_username,
        )
    rotate_weak_permalinks()
    log.info("database ready at %s", config.DB_PATH)
    log.info(
        "deployment=%s ubyport=%s endpoint=%s",
        config.DEPLOYMENT,
        config.UBYPORT_ENV,
        config.endpoint_for(),
    )
    env_guard.apply()
    if config.UBYPORT_ENV == "mock":
        log.warning(
            "Running against the MOCK UbyPort server - nothing is reported to the police. "
            "Set UBYHOST_UBYPORT_ENV=test or prod when you have credentials."
        )
    elif config.DEPLOYMENT == "production" and config.UBYPORT_ENV == "prod":
        log.warning(
            "LIVE production reporting is active — submissions go to the real police register."
        )
    scheduler.start()
    try:
        yield
    finally:
        scheduler.shutdown()


app = FastAPI(title="UbyHost", docs_url=None, redoc_url=None, lifespan=lifespan)


@app.exception_handler(security.ExpiredFormError)
async def expired_form_handler(_request: Request, exc: security.ExpiredFormError):
    """Refresh stale same-site forms without exposing a downloadable JSON body."""
    return RedirectResponse(exc.location, status_code=303)


def _wants_html(request: Request) -> bool:
    return not request.url.path.startswith("/api/") and "text/html" in request.headers.get("accept", "")


_CSP = (
    "default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none'; "
    "form-action 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
    "script-src 'self' 'unsafe-inline' https://challenges.cloudflare.com; "
    "frame-src https://challenges.cloudflare.com; "
    "connect-src 'self' https://challenges.cloudflare.com"
)


def _harden(response):
    """Headers every page needs. The 500 handler runs outside the middleware."""
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(self), microphone=()")
    response.headers.setdefault("Content-Security-Policy", _CSP)
    return response


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(request: Request, exc: StarletteHTTPException):
    """A branded page for people; the JSON body stays for scripts and the API."""
    if exc.status_code not in (404, 405) or not _wants_html(request):
        return await http_exception_handler(request, exc)
    response = templating.render(
        request, "error.html", {"error_kind": "not_found"}, status_code=exc.status_code
    )
    if exc.headers:
        response.headers.update(exc.headers)  # keeps Allow on a 405
    return response


@app.exception_handler(Exception)
async def server_error_handler(request: Request, exc: Exception):
    """Log the failure and show a calm page instead of a bare 500 text."""
    # The route template, never the path: guest links carry a token (OPS-3).
    log.exception("unhandled error on %s", _access_route(request))
    response = None
    if _wants_html(request):
        try:
            response = templating.render(request, "error.html", {"error_kind": "server"}, status_code=500)
        except Exception:
            log.exception("error page failed to render")
    if response is None:
        response = PlainTextResponse("Internal Server Error", status_code=500)
    response.headers["Cache-Control"] = "no-store, private"
    return _harden(response)


@app.exception_handler(security.GuestFormExpiredError)
async def guest_form_expired_handler(request: Request, exc: security.GuestFormExpiredError):
    """Tell a guest their form expired instead of returning a bare 403 body."""
    return guest.csrf_expired_page(request, exc.token)


@app.middleware("http")
async def cloudflare_connecting_ip(request: Request, call_next):
    """Use the visitor IP when a trusted proxy forwards Cloudflare's header."""
    client_ip.apply_visitor_client(request.scope, request.headers)
    started = time.perf_counter()
    response = await call_next(request)
    security.attach_csrf_cookie(request, response)
    _harden(response)
    # Everything outside /static carries passport numbers, addresses and
    # signatures. Guests hand the phone back and hosts share laptops, so these
    # pages must not sit in history, the back/forward cache, or a proxy.
    if not request.url.path.startswith("/static/"):
        response.headers.setdefault("Cache-Control", "no-store, private")
    if config.ACCESS_LOG:
        _log_access(request, response.status_code, started)
    return response


def _access_route(request: Request) -> str:
    """The matched route template, or a constant when nothing matched.

    The template (e.g. ``/l/{token}/{reservation_id}``) is used instead of
    ``request.url.path`` on purpose: a guest permalink token, a query string or
    a user agent must never reach a log line (OPS-3).
    """
    route = request.scope.get("route")
    return getattr(route, "path", None) or "<unmatched>"


def _log_access(request: Request, status_code: int, started: float) -> None:
    path = request.url.path
    if path.startswith("/static/") or path == "/healthz":
        return
    log_access.info(
        "method=%s route=%s status=%s ms=%d",
        request.method,
        _access_route(request),
        status_code,
        int((time.perf_counter() - started) * 1000),
    )


app.mount("/static", StaticFiles(directory=str(config.BASE_DIR / "static")), name="static")
app.include_router(guest.router)
app.include_router(admin.router)
app.include_router(invoices.router)
app.include_router(stay_fees.router)
app.include_router(legal.router)


@app.get("/sample-airbnb.ics", include_in_schema=False)
def sample_airbnb_calendar():
    return sample_calendar_response()


@app.get("/robots.txt", include_in_schema=False)
def robots():
    return Response(seo.robots_txt(), media_type="text/plain; charset=utf-8")


@app.get("/sitemap.xml", include_in_schema=False)
def sitemap():
    return Response(seo.sitemap_xml(), media_type="application/xml")


@app.post(
    "/language",
    include_in_schema=False,
    dependencies=[Depends(security.protect_host_post)],
)
async def set_language(request: Request):
    form = await request.form()
    lang = host_i18n.normalise_language(str(form.get("lang", "")))
    target = str(form.get("next", "/") or "/")
    target = security.safe_local_path(target, "/")
    response = RedirectResponse(target, status_code=303)
    host_i18n.remember_language(response, lang)
    return response


@app.get("/healthz", include_in_schema=False)
def healthz():
    data_writable = os.access(config.DATA_DIR, os.W_OK)
    try:
        database_ok = bool(db.query_one("SELECT 1 AS ok"))
    except Exception:
        log.exception("healthz database check failed")
        database_ok = False
    healthy = data_writable and database_ok
    payload = {
        "status": "ok" if healthy else "degraded",
        "version": __import__("app").__version__,
        "data_dir_writable": data_writable,
        "database_ok": database_ok,
    }
    if config.DEPLOYMENT != "production":
        payload.update(
            {"deployment": config.DEPLOYMENT, "ubyport_env": config.UBYPORT_ENV}
        )
    return JSONResponse(payload, status_code=200 if healthy else 503)


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return RedirectResponse("/static/favicon.png", status_code=307)
