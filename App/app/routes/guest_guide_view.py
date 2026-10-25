"""The guest side of the guest guide (brief 0344): two read-only doors.

* ``/l/{token}/{reservation_id}/guide``: "Your guide" for a booked guest, behind
  the same link, PIN and claim checks as the stay page. "booked" cards from the
  day before check-in until checkout; the "everyone" level outside that window.
* ``/g/{token}``: the QR code at the property. "everyone" cards only, for
  anyone who scanned it. The token is ``apartment.guide_token`` (guide_token.py),
  never the stay link token.

Both doors render only what ``guest_guide.for_guest`` returns (confirmed cards
of the allowed visibility, nothing until the guide is live) and serve a photo
only when its card is in that list. Nothing here writes guest data or logs it.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, RedirectResponse
from starlette.background import BackgroundTask

from .. import claim, guest_guide, guide_facts, guide_photos, guide_token, host_i18n, mail, rate_limit
from ..templating import render_guest
from .. import leon  # 0352: the Leon (AI) chat
from .. import guide_translate  # 0353: cards in the guest's language
from .guest import (
    _device_holds_claim,
    _host_owns_apartment,
    _language,
    _open_link,
    _require_pin,
    _reservation_for_guest,
    _shared,
    _unavailable,
    _with_lang,
)

router = APIRouter()

# A QR page is public, so one address gets a generous but finite number of
# page views per rate_limit window (15 minutes). Photos are not counted.
QR_MAX_VIEWS = 120

HARDEN = {
    "Cache-Control": "no-store",
    "X-Robots-Tag": "noindex, nofollow",
    "Referrer-Policy": "no-referrer",
}
PHOTO_HEADERS = {
    "Cache-Control": "private, max-age=3600",
    "X-Robots-Tag": "noindex",
    "Referrer-Policy": "no-referrer",
}


def booked_level(reservation, today: Optional[date] = None) -> str:
    """"booked" from the day before check-in through the checkout day, else "everyone"."""
    today = today or claim.prague_today()
    try:
        date_from = date.fromisoformat(reservation["date_from"])
        date_to = date.fromisoformat(reservation["date_to"])
    except (TypeError, ValueError):
        return "everyone"
    if date_from - timedelta(days=1) <= today <= date_to:
        return "booked"
    return "everyone"


def _copy_lang(lang: str) -> str:
    """Card and topic titles are host copy (en, cs); other guest languages read English."""
    return "cs" if lang == "cs" else "en"


def _cards(apartment_id: int, level: str, lang: str, photo_url) -> List[Dict[str, Any]]:
    hl = _copy_lang(lang)
    out = []
    for item in guide_facts.for_guest(apartment_id, level, lang):
        title = item["title"] if item["kind"] == "custom" else host_i18n.translate(hl, f"guest_guide.kind.{item['kind']}.title")
        out.append(
            {
                "id": item["id"],
                "kind": item["kind"],
                "topic": item["topic"],
                "title": title,
                "facts": item["facts"],
                "location": item["location"],
                "steps": [line.strip() for line in item["steps"].splitlines() if line.strip()],
                "watch_out": item["watch_out"],
                "video_url": item["video_url"] if item["video_url"].startswith("https://") else "",
                "photos": [photo_url(item["id"], p["id"]) for p in guide_photos.photos(apartment_id, item["id"])] if item["state"] == "done" else [],
            }
        )
    return out


def _groups(cards: List[Dict[str, Any]], lang: str):
    hl = _copy_lang(lang)
    groups = []
    for topic in guest_guide.TOPICS:
        mine = [c for c in cards if c["topic"] == topic]
        if mine:
            groups.append({"title": host_i18n.translate(hl, f"guest_guide.topic.{topic}"), "cards": mine})
    return groups


def _page(request: Request, lang: str, apartment, context: Dict[str, Any], level: str, photo_url, back_url: str = "",
          leon_url: str = ""):
    live = guest_guide.progress(apartment["id"])["live"]
    cards = _cards(apartment["id"], level, lang, photo_url) if live else []
    # 0353: cached translations in place; the missing ones are filled after the response.
    missing = guide_translate.apply(cards, lang)
    fill = bool(missing) and guide_translate.can_fill(apartment["id"])
    context.update(
        {
            "not_ready": not live,
            "level": level,
            "groups": _groups(cards, lang),
            "back_url": back_url,
            # 0352: the chat only while the guide is live and Leon is switched on.
            "leon_url": leon_url if live and leon.switched_on(apartment) else "",
            "leon_host": leon.host_first_name((context.get("host") or {}).get("name", "")),
            "translating": fill,
        }
    )
    response = render_guest(request, "guest/guide.html", context)
    response.headers.update(HARDEN)
    if fill:
        todo = [c for c in cards if int(c["id"]) in missing]
        response.background = BackgroundTask(guide_translate.fill, apartment["id"], lang, todo)
    return _with_lang(response, lang)


def _photo(apartment_id: int, level: str, item_id: int, photo_id: int):
    """The file, only when the card is one this level may read; else a bare 404."""
    # Only a written card serves photos; a facts-only card is a draft.
    if not any(item["id"] == item_id for item in guest_guide.for_guest(apartment_id, level)):
        return None
    photo = guide_photos.get(apartment_id, item_id, photo_id)
    path = guide_photos.path_for(photo) if photo else None
    if not path or not path.is_file():
        return None
    return FileResponse(path, media_type="image/jpeg", headers=PHOTO_HEADERS)


def _not_found(request: Request, lang: str, status_code: int = 404):
    response = _unavailable(request, lang, "bad_link", status_code)
    response.headers.update(HARDEN)
    return response


# --- the stay link door -------------------------------------------------------

def _stay_gate(request: Request, token: str, reservation_id: int):
    """Same checks as the stay page. Returns (apartment, reservation, lang, early response)."""
    lang = _language(request)
    apartment, token, early = _open_link(request, token, lang)
    if early:
        return None, None, token, lang, early
    pin_guard = _require_pin(request, token, lang)
    if pin_guard:
        return None, None, token, lang, pin_guard
    reservation = _reservation_for_guest(apartment, reservation_id, request)
    if not reservation:
        return None, None, token, lang, _unavailable(request, lang, "stay_gone", 404, token)
    claim_row = claim.ensure_row(reservation["id"])
    if not claim.guest_access_open(reservation, claim_row):
        return None, None, token, lang, _unavailable(request, lang, "stay_gone", 404, token)
    if mail.mail_enabled() and not _host_owns_apartment(request, apartment):
        if not claim.is_claimed(claim_row) or not _device_holds_claim(request, reservation["id"], claim_row):
            # The stay page explains the claim step; the guide waits behind it.
            stay = RedirectResponse(f"/l/{token}/{reservation['id']}?lang={lang}", status_code=303)
            return None, None, token, lang, stay
    return apartment, reservation, token, lang, None


@router.get("/l/{token}/{reservation_id}/guide")
def stay_guide(token: str, reservation_id: int, request: Request):
    apartment, reservation, token, lang, early = _stay_gate(request, token, reservation_id)
    if early:
        return early
    level = booked_level(reservation)
    base = f"/l/{token}/{reservation['id']}"
    context = _shared(request, token, lang, apartment)
    context.update({"apartment": apartment, "reservation": reservation, "door": "stay"})
    return _page(
        request, lang, apartment, context, level,
        lambda item_id, photo_id: f"{base}/guide/photos/{item_id}/{photo_id}",
        back_url=f"{base}?lang={lang}", leon_url=f"{base}/guide/leon",
    )


@router.get("/l/{token}/{reservation_id}/guide/photos/{item_id}/{photo_id}")
def stay_guide_photo(token: str, reservation_id: int, item_id: int, photo_id: int, request: Request):
    apartment, reservation, token, lang, early = _stay_gate(request, token, reservation_id)
    if early:
        return early
    return _photo(apartment["id"], booked_level(reservation), item_id, photo_id) or _not_found(request, lang)


# --- the QR door ----------------------------------------------------------------

def _qr_apartment(request: Request, token: str):
    lang = _language(request)
    key = rate_limit.client_key(request, "guide_qr")
    if rate_limit.blocked("guide_qr", key, QR_MAX_VIEWS):
        return None, lang, _not_found(request, lang, 429)
    apartment = guide_token.apartment_for(token)
    if not apartment:
        return None, lang, _not_found(request, lang)
    return apartment, lang, None


@router.get("/g/{token}")
def qr_guide(token: str, request: Request):
    apartment, lang, early = _qr_apartment(request, token)
    if early:
        return early
    rate_limit.record("guide_qr", rate_limit.client_key(request, "guide_qr"))
    context = _shared(request, "", lang, apartment)
    # No stay link on a public page: the privacy notice link carries the stay token.
    context.update({"token": "", "privacy_url": None, "door": "qr"})
    # A QR sticker outlives every stay: anyone who scans it sees the host's name,
    # never the phone or e-mail (owner, 2026-10-24). Booked guests get those on the stay page.
    context["host"] = {"name": (context.get("host") or {}).get("name", "")}
    return _page(
        request, lang, apartment, context, "everyone",
        lambda item_id, photo_id: f"/g/{token}/photos/{item_id}/{photo_id}", leon_url=f"/g/{token}/leon",
    )


@router.get("/g/{token}/photos/{item_id}/{photo_id}")
def qr_guide_photo(token: str, item_id: int, photo_id: int, request: Request):
    apartment, lang, early = _qr_apartment(request, token)
    if early:
        return early
    return _photo(apartment["id"], "everyone", item_id, photo_id) or _not_found(request, lang)
