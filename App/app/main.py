"""Application entrypoint."""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import auth, config, db, host_i18n, scheduler
from .routes import admin, guest
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


@app.middleware("http")
async def cloudflare_connecting_ip(request: Request, call_next):
    """Use the visitor IP when traffic is proxied through Cloudflare."""
    cf_ip = request.headers.get("cf-connecting-ip")
    if cf_ip:
        _host, port = request.scope.get("client") or ("", 0)
        request.scope["client"] = (cf_ip, port or 0)
    return await call_next(request)


app.mount("/static", StaticFiles(directory=str(config.BASE_DIR / "static")), name="static")
app.include_router(guest.router)
app.include_router(admin.router)


@app.get("/sample-airbnb.ics", include_in_schema=False)
def sample_airbnb_calendar():
    return sample_calendar_response()


@app.post("/language", include_in_schema=False)
async def set_language(request: Request):
    form = await request.form()
    lang = host_i18n.normalise_language(str(form.get("lang", "")))
    target = str(form.get("next", "/") or "/")
    if not target.startswith("/") or target.startswith("//"):
        target = "/"
    response = RedirectResponse(target, status_code=303)
    response.set_cookie(
        host_i18n.LANG_COOKIE,
        lang,
        max_age=60 * 60 * 24 * 365,
        httponly=False,
        samesite="lax",
        secure=config.PUBLIC_BASE_URL.lower().startswith("https://"),
        path="/",
    )
    return response


@app.get("/healthz", include_in_schema=False)
def healthz():
    data_writable = os.access(config.DATA_DIR, os.W_OK)
    return {
        "status": "ok" if data_writable else "degraded",
        "version": __import__("app").__version__,
        "deployment": config.DEPLOYMENT,
        "ubyport_env": config.UBYPORT_ENV,
        "data_dir_writable": data_writable,
    }


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return RedirectResponse("/static/favicon.svg", status_code=307)
