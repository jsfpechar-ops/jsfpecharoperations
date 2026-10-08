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
    analytics,
    auth,
    client_ip,
    config,
    db,
    env_guard,
    host_i18n,
    passport_photos,
    scheduler,
    security,
    seo,
    templating,
)
from .routes import admin, guest, invoices, legal, mail_unsubscribe, stay_fees
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
    if config.ROLE not in ("web", "all"):
        raise RuntimeError(
            f"UBYHOST_ROLE={config.ROLE!r} cannot serve HTTP; use web or all "
            "(the background worker starts with: python -m app.worker)"
        )
    from PIL import Image
    # The process-wide decompression-bomb bound. Passport photos (WP08) are the
    # largest images we decode, and passport_photos checks its own, stricter
    # limit from the header first; signatures and QR codes have their own
    # size checks too. Pillow raises at twice this value.
    Image.MAX_IMAGE_PIXELS = passport_photos.MAX_IMAGE_PIXELS
    # WP06: two web workers and the scheduler worker boot at the same moment.
    # Key creation, migrations, the first administrator and the PIN rotation
    # each assume they run alone, so they run one process at a time.
    with db.startup_lock():
        # Read the key here, where a bad one stops the app from booting. Left
        # lazy, it raised on the first page that signed a cookie: /healthz
        # answered 200 while /login answered 500, so the deploy's health check
        # passed and the broken release went live.
        config.secret_key()
        # Same reason for the data-encryption keys (WP16): a malformed
        # UBYHOST_DATA_KEYS must stop the boot, not the first page that reads
        # a guest.
        db.check_data_keys()
        db.init_db()
        bootstrap_link = auth.ensure_bootstrap_admin()
        rotate_weak_permalinks()
    if bootstrap_link:
        # The link itself stays out of the log: it logs the administrator in.
        # Staging is the exception: it has no shell and no mail, and its log is
        # readable only by whoever runs the service.
        log.warning(
            "Created the first administrator. Their first login link is in %s",
            config.DATA_DIR / "initial_admin_login",
        )
        if config.DEPLOYMENT == "staging":
            log.warning("staging first administrator login link: %s", bootstrap_link)
    log.info("database ready at %s", config.DB_PATH)
    log.info(
        "deployment=%s ubyport=%s endpoint=%s",
        config.DEPLOYMENT,
        config.UBYPORT_ENV,
        config.endpoint_for(),
    )
    env_guard.apply()
    if config.DEPLOYMENT == "staging":
        if auth.staging_expected_password():
            log.warning(
                "staging login: username=%s password=UBYHOST_STAGING_LOGIN_PASSWORD (Render Environment)",
                config.ADMIN_USERNAME or "admin",
            )
        else:
            log.warning(
                "staging login: set UBYHOST_STAGING_LOGIN_PASSWORD in Render Environment and redeploy"
            )
    if config.UBYPORT_ENV == "mock":
        log.warning(
            "Running against the MOCK UbyPort server - nothing is reported to the police. "
            "Set UBYHOST_UBYPORT_ENV=test or prod when you have credentials."
        )
    elif config.DEPLOYMENT == "production" and config.UBYPORT_ENV == "prod":
        log.warning(
            "LIVE production reporting is active — submissions go to the real police register."
        )
    if config.ROLE == "all":
        scheduler.start()
    elif config.ENABLE_SCHEDULER:
        log.info("role=web: background jobs run in the worker process (python -m app.worker)")
    try:
        yield
    finally:
        scheduler.shutdown()
        # After the scheduler, whose threads use them too.
        db.close_connections()


app = FastAPI(title="UbyHost", docs_url=None, redoc_url=None, lifespan=lifespan)


@app.exception_handler(security.ExpiredFormError)
async def expired_form_handler(_request: Request, exc: security.ExpiredFormError):
    """Refresh stale same-site forms without exposing a downloadable JSON body."""
    return RedirectResponse(exc.location, status_code=303)


def _wants_html(request: Request) -> bool:
    return not request.url.path.startswith("/api/") and "text/html" in request.headers.get("accept", "")


def _csp(extra_script: tuple = (), extra_connect: tuple = ()) -> str:
    script = " ".join(("'self' 'unsafe-inline' https://challenges.cloudflare.com",) + extra_script)
    connect = " ".join(("'self' https://challenges.cloudflare.com",) + extra_connect)
    return (
        "default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none'; "
        "form-action 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
        f"script-src {script}; "
        "frame-src https://challenges.cloudflare.com; "
        f"connect-src {connect}"
    )


# Host, guest and auth pages: no third-party origin beyond Turnstile, ever.
_CSP = _csp()


def _public_csp() -> str:
    """WP09: the CSP for the public pages that carry the Umami tag.

    Derived from UMAMI_SCRIPT_URL (and UMAMI_HOST_URL), never hard-coded, so
    the policy always matches the tag that templating rendered.
    """
    origin = analytics.script_origin()
    if not origin:
        return _CSP
    return _csp((origin,), analytics.connect_origins())


def _harden(response, public_analytics: bool = False):
    """Headers every page needs. The 500 handler runs outside the middleware."""
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(self), microphone=()")
    response.headers.setdefault(
        "Content-Security-Policy", _public_csp() if public_analytics else _CSP
    )
    return response


def _is_guest_path(request: Request) -> bool:
    """A guest link (``/l/...``): its error pages speak the guest's language."""
    return request.url.path == "/l" or request.url.path.startswith("/l/")


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(request: Request, exc: StarletteHTTPException):
    """A branded page for people; the JSON body stays for scripts and the API."""
    if exc.status_code not in (404, 405) or not _wants_html(request):
        return await http_exception_handler(request, exc)
    if _is_guest_path(request):
        response = guest.error_page(request, "not_found", exc.status_code)
    else:
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
            if _is_guest_path(request):
                response = guest.error_page(request, "server", 500)
            else:
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
    # A fresh counter per request (WP13). The route runs in a copy of this
    # context, which shares the object, so its queries land here.
    stats = db.start_request_stats()
    response = await call_next(request)
    security.attach_csrf_cookie(request, response)
    _harden(response, public_analytics=analytics.is_public_page(request))
    # Everything outside /static carries passport numbers, addresses and
    # signatures. Guests hand the phone back and hosts share laptops, so these
    # pages must not sit in history, the back/forward cache, or a proxy.
    if not request.url.path.startswith("/static/"):
        response.headers.setdefault("Cache-Control", "no-store, private")
    elif response.status_code in (200, 304):
        response.headers.setdefault("Cache-Control", _static_cache_control(request))
    if config.ACCESS_LOG:
        _log_access(request, response.status_code, started, stats)
    return response


# WP07: every /static URL in the templates carries ?v=<key>, and the key is
# bumped whenever the file changes, so a versioned asset may be cached for a
# year without revalidation. A request without ?v= (the /favicon.ico redirect,
# the logo in e-mails, a crawler fetching og:image) gets one day only, so a
# changed unversioned file is never stuck in a cache for a year.
_STATIC_VERSIONED = "public, max-age=31536000, immutable"
_STATIC_UNVERSIONED = "public, max-age=86400"


def _static_cache_control(request: Request) -> str:
    return _STATIC_VERSIONED if request.query_params.get("v") else _STATIC_UNVERSIONED


def _access_route(request: Request) -> str:
    """The matched route template, or a constant when nothing matched.

    The template (e.g. ``/l/{token}/{reservation_id}``) is used instead of
    ``request.url.path`` on purpose: a guest permalink token, a query string or
    a user agent must never reach a log line (OPS-3).
    """
    route = request.scope.get("route")
    return getattr(route, "path", None) or "<unmatched>"


def _log_access(
    request: Request,
    status_code: int,
    started: float,
    stats: "db.RequestStats | None" = None,
) -> None:
    path = request.url.path
    if path.startswith("/static/") or path == "/healthz":
        return
    stats = stats or db.RequestStats()
    # q, db_ms and lock_ms are counts and durations only; they carry nothing
    # from the request, so the line stays as PII-free as the route template.
    log_access.info(
        "method=%s route=%s status=%s ms=%d q=%d db_ms=%d lock_ms=%d",
        request.method,
        _access_route(request),
        status_code,
        int((time.perf_counter() - started) * 1000),
        stats.queries,
        int(stats.db_seconds * 1000),
        int(stats.lock_seconds * 1000),
    )


app.mount("/static", StaticFiles(directory=str(config.BASE_DIR / "static")), name="static")
app.include_router(guest.router)
app.include_router(admin.router)
app.include_router(invoices.router)
app.include_router(stay_fees.router)
app.include_router(legal.router)
# Public, outside the host CSRF dependency: RFC 8058 one-click posts (WP12).
app.include_router(mail_unsubscribe.router)


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
    if config.DEPLOYMENT == "staging" and database_ok:
        from . import auth

        expected = auth.staging_expected_password()
        staging_login = {
            "password_configured": bool(expected),
            "password_length": len(expected),
            "admin_username": auth.staging_admin_username(),
        }
        source = auth.staging_password_env_var()
        if source:
            staging_login["password_env_var"] = source
        payload["staging_login"] = staging_login
    return JSONResponse(payload, status_code=200 if healthy else 503)


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return RedirectResponse("/static/favicon.png", status_code=307)
