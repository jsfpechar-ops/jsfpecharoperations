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

from .. import config, db, property_page, rate_limit

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
    return render(request, "property_page.html", {"page": page, "show_nav": False})


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


@router.get("/sitemap.xml")
def sitemap(request: Request):
    scope = "property_sitemap"
    key = rate_limit.client_key(request, scope)
    if rate_limit.blocked(scope, key, 60, _RATE_WINDOW):
        return PlainTextResponse("slow down", status_code=429)
    rate_limit.record(scope, key)
    from .. import config as _config

    base = _config.PUBLIC_BASE_URL.rstrip("/")
    urls = [
        f"<url><loc>{base}/p/{row['slug']}</loc>"
        + (f"<lastmod>{row['published_at']}</lastmod>" if row["published_at"] else "")
        + "</url>"
        for row in property_page.published_pages()
    ]
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + "".join(urls)
        + "</urlset>"
    )
    return Response(content=body, media_type="application/xml",
                    headers={"Cache-Control": "public, max-age=3600"})


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
