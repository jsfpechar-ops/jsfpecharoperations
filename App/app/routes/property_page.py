"""Public property page route (brief 0430): /p/<slug> on the public host.

0430 ships the URL layer: history slug → 301, unpublished → 404, published →
a minimal stub. The full template (photos, cards, amenities) is brief 0431.
Public GET, rate-limited per the guide QR view pattern; no session, no
third-party scripts.
"""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse, RedirectResponse, Response

from ..templating import render

from datetime import date
from urllib.parse import urlencode

from .. import (booking_calendar, booking_checkout, booking_site, config, db, host_i18n,
                property_page, rate_limit)

router = APIRouter()

_RATE_MAX = 120
_RATE_WINDOW = 3600


def _off() -> bool:
    return config.STRIPE_MODE not in ("test", "live") and not config.PUBLIC_BASE_URL


@router.get("/p/{slug}")
def property_page_view(request: Request, slug: str):
    scope = "property_page"
    key = rate_limit.client_key(request, scope)
    if rate_limit.blocked(scope, key, _RATE_MAX, _RATE_WINDOW):
        return PlainTextResponse("slow down", status_code=429)
    rate_limit.record(scope, key)
    resolved = property_page.resolve(slug)
    if resolved is None:
        return Response(status_code=404)
    if "redirect" in resolved:
        return RedirectResponse(f"/p/{resolved['redirect']}", status_code=301)
    if resolved.get("missing"):
        return Response(status_code=404)
    apartment_id = int(resolved["apartment_id"])
    page = _page_context(apartment_id)
    if page is None:
        return Response(status_code=404)
    page["noindex"] = _noindex(apartment_id)
    page["og"] = _og(apartment_id, page)
    page["bookable"] = property_page.widget_ready(apartment_id)
    page["book_error"] = request.query_params.get("book", "")
    if page["book_error"] not in BOOK_ERRORS:
        page["book_error"] = ""
    # Owner decision (28 Oct): listing pages stay English — hosts' OTA copy is
    # not translated per listing; no per-language variants, no cookie switch.
    return render(request, "property_page.html",
                  {"page": page, "show_nav": False, "lang": "en"})


def _noindex(apartment_id: int) -> bool:
    row = db.query_one(
        "SELECT COALESCE(hide_from_search, 1) AS h FROM property_page WHERE apartment_id = ?",
        (apartment_id,),
    )
    return bool(row and row["h"])


def _og(apartment_id: int, page: dict) -> dict:
    from .. import config as _config

    base = _config.PUBLIC_BASE_URL.rstrip("/")
    photos = page.get("photos") or []
    return {
        "url": f"{base}/p/{property_page.account_row(apartment_id)['slug']}",
        "image": f"{base}{photos[0]}" if photos else "",
        "title": page["name"],
        "description": (page["description"] or "")[:200],
    }



def _page_context(apartment_id: int):
    """0431: the published page's sections, from confirmed data only."""
    import json

    apartment = db.query_one(
        "SELECT internal_name, addr_obec, addr_obec_cast FROM apartment WHERE id = ?",
        (apartment_id,),
    )
    if apartment is None:
        return None
    content = db.query_one(
        "SELECT * FROM property_page WHERE apartment_id = ?",
        (apartment_id,),
    )
    cards = [
        {
            "title": (row["title"] or "").strip(),
            "body": "\n".join(
                part
                for part in (
                    (row["steps"] or "").strip(),
                    (row["watch_out"] or "").strip(),
                    (row["location"] or "").strip(),
                )
                if part
            ),
        }
        for row in db.query(
            "SELECT title, steps, watch_out, location FROM guide_item"
            " WHERE apartment_id = ? AND visibility = 'everyone' AND state = 'done'"
            " ORDER BY topic, sort_order LIMIT 20",
            (apartment_id,),
        )
        if (row["title"] or row["steps"] or row["watch_out"])
    ]
    c = dict(content) if content is not None else {}
    return {
        "name": apartment["internal_name"],
        "district": " · ".join(
            p for p in (apartment["addr_obec"], apartment["addr_obec_cast"]) if p
        ),
        "description": c.get("description") or "",
        "checkin_text": c.get("checkin_text") or "",
        "checkout_text": c.get("checkout_text") or "",
        "photos": json.loads(c.get("photos_json") or "[]"),
        "amenities": json.loads(c.get("amenities_json") or "[]"),
        "cards": cards,
    }


@router.get("/photos/property/{name}")
def property_photo_file(request: Request, name: str):
    """0432: the re-hosted copy of the host's own listing photo. Public GET
    with a cache header; the OTA CDN URL is never referenced by the page."""
    import re as _re

    from fastapi.responses import FileResponse

    if not _re.fullmatch(r"[0-9a-f]{32}\.jpg", name):
        return Response(status_code=404)
    path = property_page.photos_dir() / name
    if not path.is_file():
        return Response(status_code=404)
    return FileResponse(path, media_type="image/jpeg",
                        headers={"Cache-Control": "public, max-age=86400"})


# --- booking widget (brief 0434) -----------------------------------------------


BOOK_ERRORS = ("bad_dates", "min_nights", "too_soon", "guests", "no_price", "taken",
               "bad_email", "bad_name", "terms", "unavailable", "cancelled")
_EMAIL = __import__("re").compile(r"[^@\s]{1,64}@[^@\s]{1,200}\.[^@\s]{2,30}")
_CHECKOUT_MAX = 20
_CHECKOUT_WINDOW = 3600


def _bookable_apartment(slug: str):
    resolved = property_page.resolve(slug)
    if resolved is None or "redirect" in resolved or resolved.get("missing"):
        return None
    apartment_id = int(resolved["apartment_id"])
    if not property_page.widget_ready(apartment_id):
        return None
    return apartment_id


def _guests(value) -> int:
    try:
        return int(str(value or "").strip())
    except ValueError:
        return 0


@router.post("/p/{slug}/book")
async def property_page_book(request: Request, slug: str):
    """No-JS form POST: dates + guests -> the quote and the guest form.
    Nothing is held here; the hold starts at /checkout."""
    apartment_id = _bookable_apartment(slug)
    if apartment_id is None:
        return Response(status_code=404)
    form = await request.form()
    q = booking_site.quote(
        apartment_id,
        str(form.get("date_from") or "").strip(),
        str(form.get("date_to") or "").strip(),
        _guests(form.get("guests") or 1),
    )
    if q["error"]:
        return _book_error(slug, q["error"])
    return render(
        request,
        "property_page_book.html",
        {"page": _page_context(apartment_id) or {}, "show_nav": False, "lang": "en",
         "slug": slug, "q": q},
    )


def _book_error(slug: str, kind: str) -> Response:
    return RedirectResponse(f"/p/{slug}?book={kind}#book", status_code=303)


@router.post("/p/{slug}/checkout")
async def property_page_checkout(request: Request, slug: str):
    """Hold + pending booking + Stripe session, then a page with one link to
    Stripe (a POST never redirects off-site: CSP form-action 'self')."""
    scope = "property_page_checkout"
    key = rate_limit.client_key(request, scope)
    if rate_limit.blocked(scope, key, _CHECKOUT_MAX, _CHECKOUT_WINDOW):
        return PlainTextResponse("slow down", status_code=429)
    rate_limit.record(scope, key)
    apartment_id = _bookable_apartment(slug)
    if apartment_id is None:
        return Response(status_code=404)
    form = await request.form()
    q = booking_site.quote(
        apartment_id,
        str(form.get("date_from") or "").strip(),
        str(form.get("date_to") or "").strip(),
        _guests(form.get("guests")),
    )
    if q["error"]:
        return _book_error(slug, q["error"])
    name = " ".join(str(form.get("guest_name") or "").split())
    email = str(form.get("guest_email") or "").strip()
    if len(name) < 3:
        return _book_error(slug, "bad_name")
    if not _EMAIL.fullmatch(email):
        return _book_error(slug, "bad_email")
    if str(form.get("terms") or "") != "1":
        return _book_error(slug, "terms")
    lang = "cs" if str(form.get("lang") or "") == "cs" else "en"
    result = booking_checkout.start(apartment_id, slug, q, guest_name=name,
                                    guest_email=email, lang=lang)
    if result.get("error"):
        return _book_error(slug, result["error"])
    response = render(
        request,
        "property_page_pay.html",
        {"page": _page_context(apartment_id) or {}, "show_nav": False, "lang": "en",
         "pay_url": result["url"], "total": q["total_czk"]},
    )
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Robots-Tag"] = "noindex"
    return response


@router.get("/p/{slug}/{token}.ics")
def property_page_ical(request: Request, slug: str, token: str):
    """0817: private calendar feed for Airbnb / Booking.com import."""
    from .. import booking_ical

    scope = "property_page_ical"
    key = rate_limit.client_key(request, scope)
    if rate_limit.blocked(scope, key, _RATE_MAX, _RATE_WINDOW):
        return PlainTextResponse("slow down", status_code=429)
    rate_limit.record(scope, key)
    apartment_id = booking_ical.apartment_for_slug(slug)
    if apartment_id is None or not booking_ical.token_ok(apartment_id, token):
        return Response(status_code=404)
    return Response(
        booking_ical.export_ics(apartment_id).encode("utf-8"),
        media_type="text/calendar; charset=utf-8",
        headers={"Cache-Control": "private, max-age=300", "X-Robots-Tag": "noindex"},
    )


@router.get("/p/{slug}/thanks")
def property_page_thanks(request: Request, slug: str):
    """Stripe's success_url. Shows no booking data: the confirmation e-mail
    (0816) is the record."""
    response = render(request, "property_page_booked.html",
                      {"show_nav": False, "slug": slug, "lang": "en"})
    response.headers["X-Robots-Tag"] = "noindex"
    return response
