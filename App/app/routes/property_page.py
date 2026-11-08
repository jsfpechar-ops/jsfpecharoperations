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

from .. import (booking_calendar, booking_cancel, booking_checkout, booking_manage, booking_rails, booking_site,
                config, db, host_i18n, property_page, rate_limit)

router = APIRouter()

_RATE_MAX = 120
_RATE_WINDOW = 3600


def _off() -> bool:
    return config.STRIPE_MODE not in ("test", "live") and not config.PUBLIC_BASE_URL


@router.get("/terms/booking")
def booking_terms_page(request: Request):
    """Public guest terms for card bookings (0900). Sets no cookie."""
    return render(request, "booking_terms.html",
                  {"show_nav": False, "lang": _page_lang(request)})


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
    lang = _page_lang(request)
    page["bookable"] = property_page.widget_ready(apartment_id)
    page["book_error"] = request.query_params.get("book", "")
    if page["book_error"] not in BOOK_ERRORS:
        page["book_error"] = ""
    if page["bookable"]:
        page["booking"] = _booking_view(slug, apartment_id, lang, request.query_params)
        page["pay_modes"] = booking_rails.pay_modes(apartment_id, _owner_of(apartment_id))
    # Only the page's own words are translated (owner decision 2 Nov 2026,
    # booking site v1); the host's listing copy stays verbatim.
    return render(request, "property_page.html",
                  {"page": page, "show_nav": False, "lang": lang})


def _page_lang(request: Request) -> str:
    """?lang=cs|en, then the saved language cookie, then Czech. Sets no cookie."""
    for value in (request.query_params.get("lang"), request.cookies.get(host_i18n.LANG_COOKIE)):
        if value in ("cs", "en"):
            return value
    return "cs"


def _href(slug: str, lang: str, ym: tuple, date_from: str = "", date_to: str = "",
          guests: int = 0) -> str:
    query = {"lang": lang, "month": f"{ym[0]}-{ym[1]:02d}"}
    if date_from:
        query["date_from"] = date_from
    if date_to:
        query["date_to"] = date_to
    if guests:
        query["guests"] = str(guests)
    return f"/p/{slug}?{urlencode(query)}#book"


def _month_param(value: str) -> tuple:
    today = booking_site._now(None).date()
    low = (today.year, today.month)
    high = booking_calendar.add_months(low[0], low[1], booking_calendar.HORIZON_MONTHS)
    try:
        year, month = (int(part) for part in str(value).split("-"))
        date(year, month, 1)
    except ValueError:
        return low
    return (year, month) if low <= (year, month) <= high else low


def _short_day(iso: str, lang: str) -> str:
    day = booking_calendar.parse_day(iso)
    if day is None:
        return ""
    return f"{day.day}. {day.month}." if lang == "cs" else day.isoformat()


def _booking_view(slug: str, apartment_id: int, lang: str, params) -> dict:
    """Everything the booking card shows, from the query string (no JS)."""
    s = booking_site.settings(apartment_id)
    ym = _month_param(params.get("month", ""))
    date_from = str(params.get("date_from") or "")[:10]
    date_to = str(params.get("date_to") or "")[:10]
    cap = min(int(s["max_guests"]) or 10, booking_site.MAX_GUESTS)
    guests = min(max(_guests(params.get("guests") or 2), 1), cap)
    grid = booking_calendar.month_grid(
        apartment_id, ym[0], ym[1], date_from=date_from, date_to=date_to)
    for week in grid["weeks"]:
        for cell in week:
            cell["href"] = _href(slug, lang, ym, *cell["pick"], guests) if cell["pick"] else ""
    q = None
    q_error = ""
    if booking_calendar.parse_day(date_from) and booking_calendar.parse_day(date_to):
        q = booking_site.quote(apartment_id, date_from, date_to, guests)
        if q["error"]:
            q_error, q = q["error"], None
    kept = {"date_from": date_from, "date_to": date_to}
    return {
        "slug": slug,
        "grid": grid,
        "prev_href": _href(slug, lang, grid["prev"], date_from, date_to, guests) if grid["prev"] else "",
        "next_href": _href(slug, lang, grid["next"], date_from, date_to, guests) if grid["next"] else "",
        "q": q,
        "q_error": q_error,
        "guests": guests,
        "guest_options": list(range(1, cap + 1)),
        "month_value": f"{ym[0]}-{ym[1]:02d}",
        "date_from": date_from,
        "date_to": date_to,
        "arrive": _short_day(date_from, lang),
        "depart": _short_day(date_to, lang),
        "city_tax_rate": int(s["city_tax_czk"]),
        "terms_version": booking_site.TERMS_VERSION,
        "lang_href": {code: _href(slug, code, ym, **kept, guests=guests) for code in ("cs", "en")},
    }


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
    from urllib.parse import quote

    where = " ".join(p for p in (apartment["addr_obec"], apartment["addr_obec_cast"]) if p)
    # Town and district only; the street and number never leave the host side.
    map_url = f"https://mapy.cz/zakladni?q={quote(where)}" if where else ""
    return {
        "name": apartment["internal_name"],
        "district": " · ".join(
            p for p in (apartment["addr_obec"], apartment["addr_obec_cast"]) if p
        ),
        "description": c.get("description") or "",
        "house_rules": [
            ln.strip() for ln in (c.get("house_rules") or "").splitlines() if ln.strip()
        ],
        "map_url": map_url,
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


def _book_error(slug: str, kind: str, lang: str = "cs", form=None) -> Response:
    query = {"book": kind, "lang": lang}
    for name in ("date_from", "date_to", "guests"):
        value = str((form or {}).get(name) or "").strip()[:10]
        if value:
            query[name] = value
    return RedirectResponse(f"/p/{slug}?{urlencode(query)}#book", status_code=303)


def _owner_of(apartment_id: int) -> int:
    return int(db.query_one("SELECT owner_user_id FROM apartment WHERE id = ?", (apartment_id,))["owner_user_id"])


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
    lang = "cs" if str(form.get("lang") or "") == "cs" else "en"
    q = booking_site.quote(
        apartment_id,
        str(form.get("date_from") or "").strip(),
        str(form.get("date_to") or "").strip(),
        _guests(form.get("guests")),
    )
    if q["error"]:
        return _book_error(slug, q["error"], lang, form)
    name = " ".join(str(form.get("guest_name") or "").split())
    email = str(form.get("guest_email") or "").strip()
    if len(name) < 3:
        return _book_error(slug, "bad_name", lang, form)
    if not _EMAIL.fullmatch(email):
        return _book_error(slug, "bad_email", lang, form)
    if str(form.get("terms") or "") != "1":
        return _book_error(slug, "terms", lang, form)
    # A page opened before the terms text changed must not be accepted.
    if str(form.get("terms_version") or booking_site.TERMS_VERSION) != booking_site.TERMS_VERSION:
        return _book_error(slug, "terms", lang, form)
    modes = booking_rails.pay_modes(apartment_id, _owner_of(apartment_id))
    mode = str(form.get("pay_mode") or (modes[0] if len(modes) == 1 else "stripe"))
    if mode not in modes:
        return _book_error(slug, "unavailable", lang, form)
    if mode == "direct":
        sent = booking_checkout.start_direct(apartment_id, q, guest_name=name,
                                             guest_email=email, lang=lang)
        if sent.get("error"):
            return _book_error(slug, sent["error"], lang, form)
        booking = sent["booking"]
        from urllib.parse import urlsplit
        return RedirectResponse(urlsplit(booking_site.manage_url(booking)).path, status_code=303)
    result = booking_checkout.start(apartment_id, slug, q, guest_name=name,
                                    guest_email=email, lang=lang)
    if result.get("error"):
        return _book_error(slug, result["error"], lang, form)
    response = render(
        request,
        "property_page_pay.html",
        {"page": _page_context(apartment_id) or {}, "show_nav": False, "lang": lang,
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


@router.get("/p/{slug}/b/{booking_id}/{token}/invoice.pdf")
def booking_invoice_pdf(request: Request, slug: str, booking_id: int, token: str):
    """0820: the guest's invoice, by the signed booking link. 404 for anything else."""
    from .. import booking_invoice

    scope = "booking_invoice"
    key = rate_limit.client_key(request, scope)
    if rate_limit.blocked(scope, key, _RATE_MAX, _RATE_WINDOW):
        return PlainTextResponse("slow down", status_code=429)
    rate_limit.record(scope, key)
    if not booking_site.token_ok(booking_id, token):
        return Response(status_code=404)
    invoice_id = booking_invoice.ensure(booking_id)
    if invoice_id is None:
        return Response(status_code=404)
    from .. import invoices

    number = db.query_one("SELECT number FROM invoice WHERE id = ?", (invoice_id,))["number"]
    return Response(
        invoices.download_pdf(invoice_id),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="faktura-{number}.pdf"',
            "Cache-Control": "no-store",
            "X-Robots-Tag": "noindex",
        },
    )


@router.get("/p/{slug}/b/{booking_id}/{token}/correction.pdf")
def booking_correction_pdf(request: Request, slug: str, booking_id: int, token: str):
    """0901: the credit note of a partial refund, by the signed booking link. 404 otherwise."""
    scope = "booking_invoice"
    key = rate_limit.client_key(request, scope)
    if rate_limit.blocked(scope, key, _RATE_MAX, _RATE_WINDOW):
        return PlainTextResponse("slow down", status_code=429)
    rate_limit.record(scope, key)
    if not booking_site.token_ok(booking_id, token):
        return Response(status_code=404)
    booking = booking_site.get(booking_id)
    if booking is None or not booking.get("invoice_id"):
        return Response(status_code=404)
    from .. import invoices

    row = db.query_one(
        "SELECT id, number FROM invoice WHERE corrects_invoice_id = ? ORDER BY id DESC LIMIT 1",
        (int(booking["invoice_id"]),),
    )
    if row is None:
        return Response(status_code=404)
    return Response(
        invoices.download_pdf(row["id"]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="opravny-doklad-{row["number"]}.pdf"',
            "Cache-Control": "no-store",
            "X-Robots-Tag": "noindex",
        },
    )


def _booking_or_none(booking_id: int, token: str):
    if not booking_site.token_ok(booking_id, token):
        return None
    booking = booking_site.get(booking_id)
    if booking is None or booking["status"] not in booking_manage.VISIBLE:
        return None
    return booking


def _manage_lang(request: Request, booking) -> str:
    value = request.query_params.get("lang")
    if value in ("cs", "en"):
        return value
    return booking["lang"] if booking["lang"] in ("cs", "en") else "cs"


def _manage_throttle(request: Request, scope: str):
    key = rate_limit.client_key(request, scope)
    if rate_limit.blocked(scope, key, _RATE_MAX, _RATE_WINDOW):
        return PlainTextResponse("slow down", status_code=429)
    rate_limit.record(scope, key)
    return None


@router.get("/p/{slug}/b/{booking_id}/{token}")
def booking_manage_page(request: Request, slug: str, booking_id: int, token: str):
    """0821: the guest's private booking page (signed link from the e-mail)."""
    slow = _manage_throttle(request, "booking_manage")
    if slow:
        return slow
    booking = _booking_or_none(booking_id, token)
    if booking is None:
        return Response(status_code=404)
    lang = _manage_lang(request, booking)
    error = request.query_params.get("e", "")
    response = render(request, "booking_manage.html", {
        "show_nav": False, "lang": lang, "slug": slug, "token": token,
        "v": booking_manage.view(booking, lang),
        "error": error if error in ("started", "busy", "refund_failed") else "",
    })
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Robots-Tag"] = "noindex"
    return response


@router.post("/p/{slug}/b/{booking_id}/{token}/cancel")
def booking_manage_cancel(request: Request, slug: str, booking_id: int, token: str):
    slow = _manage_throttle(request, "booking_cancel")
    if slow:
        return slow
    booking = _booking_or_none(booking_id, token)
    if booking is None:
        return Response(status_code=404)
    result = booking_cancel.cancel(booking_id, by_host=False)
    lang = _manage_lang(request, booking)
    query = {"lang": lang}
    if result["error"] in ("started", "busy", "refund_failed"):
        query["e"] = result["error"]
    return RedirectResponse(f"/p/{slug}/b/{booking_id}/{token}?{urlencode(query)}", status_code=303)


@router.get("/p/{slug}/b/{booking_id}/{token}/calendar.ics")
def booking_manage_calendar(request: Request, slug: str, booking_id: int, token: str):
    slow = _manage_throttle(request, "booking_manage")
    if slow:
        return slow
    booking = _booking_or_none(booking_id, token)
    if booking is None or booking["status"] != "paid":
        return Response(status_code=404)
    name = (db.query_one("SELECT internal_name FROM apartment WHERE id = ?",
                         (booking["apartment_id"],)) or {"internal_name": ""})["internal_name"]
    return Response(
        booking_manage.calendar_ics(booking, name).encode("utf-8"),
        media_type="text/calendar; charset=utf-8",
        headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex",
                 "Content-Disposition": 'attachment; filename="stay.ics"'},
    )


@router.get("/p/{slug}/thanks")
def property_page_thanks(request: Request, slug: str):
    """Stripe's success_url. Shows no booking data: the confirmation e-mail
    (0816) is the record."""
    response = render(request, "property_page_booked.html",
                      {"show_nav": False, "slug": slug, "lang": _page_lang(request)})
    response.headers["X-Robots-Tag"] = "noindex"
    return response
