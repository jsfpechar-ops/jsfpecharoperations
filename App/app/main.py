"""Application entrypoint."""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request, Response
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import auth, client_ip, config, db, env_guard, host_i18n, scheduler, security, seo
from .routes import admin, guest, legal
from .sample_calendar import sample_calendar_response

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
)
log = logging.getLogger("ubyhost")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db.init_db()
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
    missing_pins = db.query(
        "SELECT id FROM apartment WHERE permalink_pin IS NULL OR permalink_pin = ''"
    )
    for row in missing_pins:
        db.update("apartment", row["id"], {"permalink_pin": auth.new_permalink_pin()})
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


@app.middleware("http")
async def cloudflare_connecting_ip(request: Request, call_next):
    """Use the visitor IP when a trusted proxy forwards Cloudflare's header."""
    client_ip.apply_visitor_client(request.scope, request.headers)
    response = await call_next(request)
    security.attach_csrf_cookie(request, response)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(self), microphone=()")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none'; "
        "form-action 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
        "script-src 'self' 'unsafe-inline' https://challenges.cloudflare.com; "
        "frame-src https://challenges.cloudflare.com; "
        "connect-src 'self' https://challenges.cloudflare.com",
    )
    # Everything outside /static carries passport numbers, addresses and
    # signatures. Guests hand the phone back and hosts share laptops, so these
    # pages must not sit in history, the back/forward cache, or a proxy.
    if not request.url.path.startswith("/static/"):
        response.headers.setdefault("Cache-Control", "no-store, private")
    return response


app.mount("/static", StaticFiles(directory=str(config.BASE_DIR / "static")), name="static")
app.include_router(guest.router)
app.include_router(admin.router)
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
    payload = {
        "status": "ok" if data_writable else "degraded",
        "version": __import__("app").__version__,
        "data_dir_writable": data_writable,
    }
    if config.DEPLOYMENT != "production":
        payload.update(
            {"deployment": config.DEPLOYMENT, "ubyport_env": config.UBYPORT_ENV}
        )
    return payload


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return RedirectResponse("/static/favicon.png", status_code=307)
