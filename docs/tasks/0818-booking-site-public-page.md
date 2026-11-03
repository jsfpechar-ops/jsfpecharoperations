# 0818: Booking site public page v2 (Czech first, calendar, price lines, pay)

Status: todo
Depends on: 0815, 0817 (both on main) | Base commit: tip of origin/main | Branch: task/0818-booking-site-public-page
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

The booking card on `/p/<slug>` becomes the approved mockup (`Main.dc.html`, 390 px): Czech first with a CS/EN switch, a server-rendered month calendar that shows booked and blocked nights and the chosen range, guests select, price lines, city-tax note, cancellation summary, name and e-mail fields, the terms checkbox and one pay button that posts to the existing `/p/<slug>/checkout` (0815). It all works without JavaScript: every calendar day is a plain link. The owner approved the mockups on 2 Nov 2026.

Deviations from the mockup, on purpose (list them in the report): (1) two fields "Celé jméno" and "E-mail" sit above the terms checkbox, because `/checkout` requires them; (2) the nights count is written with the existing plural helper ("3 noci", "1 noc") instead of a fixed word.

## 2. Context

Plan: `docs/plans/booking-site-v1.md` (rules in section 2). Rules live in `App/app/booking_site.py`: `settings`, `quote`, `earliest_check_in`, `TERMS_VERSION`. `quote()` returns `{"error": code}` or the price lines (`nightly_czk`, `nights`, `accommodation_czk`, `cleaning_fee_czk`, `total_czk`, `city_tax_on_site_czk`, `cancellation_policy`, `date_from`, `date_to`, `guests`).

- The public page extends `base.html` with `show_nav=False` and loads `tokens.css`, `app.css`, `components.css`. It has no stylesheet of its own: this brief adds one page-owned `<style>` block in `head_extra` (inline, no web font, no JS). Colours, radii, spacing and sizes come from `tokens.css` variables only. The mockup's raw hex values are NOT copied; the mapping is in step 5.
- CSP: `form-action 'self'` and `style-src 'self' 'unsafe-inline'`. No inline `<script>`. Stripe is reached only from the pay page (0815).
- Language: a visitor sees Czech unless `?lang=en` is in the URL, or the language cookie `ubyhost_lang` (`host_i18n.LANG_COOKIE`, already set by the site's own switcher) says `en`. The switch is two plain links that only add `?lang=`; no cookie is set by this page (no tracking cookies). Only the page's own words are translated; the host's description, amenities and guide cards stay verbatim.
- Existing tests that must stay green keep working because they set the cookie to `en` through `_client()`; two assertions that encode the old "English only" rule are rewritten in step 9.
- Money: whole CZK. The template macro `money` prints `1&nbsp;800&nbsp;Kč`.

Excerpt `App/app/routes/property_page.py` (imports, verbatim):

```python
from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse, RedirectResponse, Response

from ..templating import render

from .. import booking_checkout, booking_site, config, db, property_page, rate_limit
```

Excerpt `App/app/routes/property_page.py` (end of `property_page_view`, verbatim):

```python
    page["bookable"] = property_page.widget_ready(apartment_id)
    page["book_error"] = request.query_params.get("book", "")
    if page["book_error"] not in BOOK_ERRORS:
        page["book_error"] = ""
    # Owner decision (28 Oct): listing pages stay English — hosts' OTA copy is
    # not translated per listing; no per-language variants, no cookie switch.
    return render(request, "property_page.html",
                  {"page": page, "show_nav": False, "lang": "en"})
```

Excerpt `App/app/routes/property_page.py` (`_book_error`, verbatim):

```python
def _book_error(slug: str, kind: str) -> Response:
    return RedirectResponse(f"/p/{slug}?book={kind}#book", status_code=303)
```

Excerpt `App/app/routes/property_page.py` (checkout, from the form read to the end of the function, verbatim):

```python
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
```

Excerpt `App/app/routes/property_page.py` (thanks route, verbatim):

```python
    response = render(request, "property_page_booked.html",
                      {"show_nav": False, "slug": slug, "lang": "en"})
```

Excerpt `App/app/booking_checkout.py` (verbatim):

```python
                "success_url": f"{base}/p/{slug}/thanks",
                "cancel_url": f"{base}/p/{slug}?book=cancelled",
```

Excerpt `App/app/templates/property_page.html` (the block to replace, verbatim, from `{% if page.bookable %}` to its `{% endif %}`):

```html
    {% if page.bookable %}
    <div class="pp-book">
      <form method="post" action="/p/{{ page.og.url.rsplit('/', 1)[1] }}/book" class="ui-form">
        <h2>{{ t('pp.book.title') }}</h2>
        <label class="ui-field"><span>{{ t('pp.book.from') }}</span>
          <input class="ui-input" type="date" name="date_from" required></label>
        <label class="ui-field"><span>{{ t('pp.book.to') }}</span>
          <input class="ui-input" type="date" name="date_to" required></label>
        <label class="ui-field"><span>{{ t('pp.book.guests') }}</span>
          <input class="ui-input" type="number" name="guests" min="1" max="60" value="2" inputmode="numeric" required></label>
        {% if page.book_error %}<p class="ui-sub" role="alert" id="book">{{ t('pp.book.err.' ~ page.book_error) }}</p>{% endif %}
        <button class="ui-btn ui-btn-primary" type="submit">{{ t('pp.book.check') }}</button>
      </form>
    </div>
    {% endif %}
```

Excerpt `App/app/templates/property_page.html` (top, verbatim):

```html
{% block head_extra %}
{% if page.noindex %}<meta name="robots" content="noindex">{% endif %}
```

Excerpt `App/tests/test_property_page_meta.py` (verbatim):

```python
def test_listing_page_is_english_only(owner):
    """Owner decision (28 Oct): the listing page renders English even for a
    Czech visitor; OTA listing copy is never translated per listing."""
    client = TestClient(app)
    client.cookies.set("ubyhost_lang", "cs")
    response = client.get(f"/p/{_slug(owner)}")
    assert response.status_code == 200
    assert '<html lang="en">' in response.text
```

Excerpt `App/tests/test_booking_widget.py` (verbatim):

```python
    response = client.get(f"/p/{_slug(owner)}")
    assert "Book this place" not in response.text


def test_widget_shown_when_ready(owner, monkeypatch):
    _complete_account(owner, monkeypatch)
    client = _client()
    response = client.get(f"/p/{_slug(owner)}")
    assert "Book this place" in response.text
```

Excerpt `docs/context/decisions.md` (last line, verbatim, add yours after it):

```
- 2026-11-01 | Go: module go/, stdlib, pgx v5, go-ntlmssp v0.1.1, go-qrcode (11-02); crypto via Python fixtures | owner (waiver) | 0474, 0481, 0684
```

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/booking_calendar.py` | create | month grid for the page (pure, no JS) |
| `App/app/routes/property_page.py` | edit | language, booking view, `_book_error` keeps lang and dates, terms version, thanks language |
| `App/app/booking_checkout.py` | edit | success and cancel URLs carry `lang` |
| `App/app/templates/property_page.html` | edit | page-owned `<style>`, new booking card |
| `App/app/host_i18n.py` | edit | EN + CS keys (parity) |
| `App/tests/test_booking_calendar.py` | create | grid tests |
| `App/tests/test_booking_site_page.py` | create | page tests incl. weight |
| `App/tests/test_booking_site_page_browser.py` | create | 390/360/1280 geometry + screenshot |
| `App/tests/test_property_page_meta.py` | edit | rewrite the one English-only test |
| `App/tests/test_booking_widget.py` | edit | the two "Book this place" assertions |
| `docs/context/decisions.md` | edit | one line |
| `docs/tasks/0818-report.md`, `docs/tasks/screenshots-0818/booking-390.png` | create | report, screenshot |

No other file may change.

## 4. Steps

Commit after every step: `git add -A && git commit -qm "0818 step k"`.

**Step 1.** Create `App/app/booking_calendar.py` with exactly this content:

```python
"""Booking site calendar grid (brief 0818, plan booking-site-v1).

Server-rendered month grids for the public page: no JavaScript. Every day is
a plain link that sets ?date_from= or ?date_to=; the page re-renders.
A "night" is the day it starts: 16 Dec taken means the night 16 to 17 Dec.
"""
from __future__ import annotations

import calendar
from datetime import date, timedelta
from typing import Any, Dict, Optional, Set

from . import booking_site, db

HORIZON_MONTHS = 12


def parse_day(value: Any) -> Optional[date]:
    try:
        return date.fromisoformat(str(value or "").strip())
    except ValueError:
        return None


def add_months(year: int, month: int, n: int) -> tuple:
    index = year * 12 + (month - 1) + n
    return index // 12, index % 12 + 1


def taken_nights(apartment_id: int, start: date, end: date) -> Set[str]:
    """ISO dates in [start, end) whose night is booked or held."""
    out: Set[str] = set()
    rows = list(db.query(
        "SELECT date_from, date_to FROM reservation WHERE apartment_id = ?"
        " AND status = 'active' AND date_from < ? AND date_to > ?",
        (apartment_id, end.isoformat(), start.isoformat()),
    )) + list(db.query(
        "SELECT date_from, date_to FROM booking_hold WHERE apartment_id = ?"
        " AND expires_at > ? AND date_from < ? AND date_to > ?",
        (apartment_id, db.utcnow(), end.isoformat(), start.isoformat()),
    ))
    for row in rows:
        day = max(date.fromisoformat(str(row["date_from"])[:10]), start)
        last = min(date.fromisoformat(str(row["date_to"])[:10]), end)
        while day < last:
            out.add(day.isoformat())
            day += timedelta(days=1)
    return out


def month_grid(apartment_id: int, year: int, month: int, *, date_from: str = "",
               date_to: str = "", today: Optional[date] = None) -> Dict[str, Any]:
    """{"year", "month", "weeks": [[cell] * 7], "prev": (y, m) | None, "next": ...}.

    cell = {"day": int, "iso": str, "state": pad | past | taken | free | start
    | range | end, "pick": (date_from, date_to) | None}. ``pick`` is what the
    link sets; None means the day is not clickable.
    """
    settings = booking_site.settings(apartment_id)
    today = today or booking_site._now(None).date()
    earliest = booking_site.earliest_check_in(settings)
    first = date(year, month, 1)
    sel_from = parse_day(date_from)
    sel_to = parse_day(date_to)
    if sel_from is None or (sel_to is not None and sel_to <= sel_from):
        sel_to = None
    if sel_from is None:
        sel_to = None
    low = min(first, sel_from) if sel_from else first
    taken = taken_nights(apartment_id, low, first + timedelta(days=62))

    def nights_free(a: date, b: date) -> bool:
        day = a
        while day < b:
            if day.isoformat() in taken:
                return False
            day += timedelta(days=1)
        return True

    weeks = []
    for week in calendar.Calendar(firstweekday=0).monthdatescalendar(year, month):
        row = []
        for day in week:
            if day.month != month:
                row.append({"day": 0, "iso": "", "state": "pad", "pick": None})
                continue
            iso = day.isoformat()
            if day < earliest:
                state = "past"
            elif iso in taken:
                state = "taken"
            else:
                state = "free"
            pick = None
            if sel_from and sel_to is None and day > sel_from and nights_free(sel_from, day):
                pick = (sel_from.isoformat(), iso)
            elif state == "free":
                pick = (iso, "")
            if sel_from and iso == sel_from.isoformat():
                state = "start"
            elif sel_to and iso == sel_to.isoformat():
                state = "end"
            elif sel_from and sel_to and sel_from < day < sel_to:
                state = "range"
            row.append({"day": day.day, "iso": iso, "state": state, "pick": pick})
        weeks.append(row)
    this = (today.year, today.month)
    prev_ym = add_months(year, month, -1)
    next_ym = add_months(year, month, 1)
    last_ym = add_months(this[0], this[1], HORIZON_MONTHS)
    return {
        "year": year, "month": month, "weeks": weeks,
        "prev": prev_ym if prev_ym >= this else None,
        "next": next_ym if next_ym <= last_ym else None,
    }
```

(This code was run by the orchestrator against stubs: a free day after the start shows `pick=(start, day)`, a day behind a taken night starts a new range, the check-out day may be a taken day.) Run `cd App && .venv/bin/ruff check --select E9,F63,F7,F82,F401,F841 app/booking_calendar.py 2>&1 | tail -5`.

**Step 2.** `App/app/booking_checkout.py`. Find the two lines with `grep -nF 'success_url' app/booking_checkout.py`. Replace them (exact old text in section 2) with:

```python
                "success_url": f"{base}/p/{slug}/thanks?lang={lang}",
                "cancel_url": f"{base}/p/{slug}?book=cancelled&lang={lang}",
```

**Step 3.** `App/app/routes/property_page.py`, imports. Replace the line `from .. import booking_checkout, booking_site, config, db, property_page, rate_limit` with:

```python
from datetime import date
from urllib.parse import urlencode

from .. import (booking_calendar, booking_checkout, booking_site, config, db, host_i18n,
                property_page, rate_limit)
```

(Keep the `from ..templating import render` line where it is. If `ruff` later complains about import order, ignore: only the ruff rules in §6 matter.)

**Step 4.** Same file. (a) In `property_page_view` replace the block from `    page["bookable"] = ...` to the end of the function (old text in section 2) with:

```python
    lang = _page_lang(request)
    page["bookable"] = property_page.widget_ready(apartment_id)
    page["book_error"] = request.query_params.get("book", "")
    if page["book_error"] not in BOOK_ERRORS:
        page["book_error"] = ""
    if page["bookable"]:
        page["booking"] = _booking_view(slug, apartment_id, lang, request.query_params)
    # Only the page's own words are translated (owner decision 2 Nov 2026,
    # booking site v1); the host's listing copy stays verbatim.
    return render(request, "property_page.html",
                  {"page": page, "show_nav": False, "lang": lang})
```

(b) Directly above `def _noindex(` insert these helpers:

```python
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
```

**Step 5.** Same file, keep dates and language through errors. (a) Replace the whole `_book_error` function (old text in section 2) with:

```python
def _book_error(slug: str, kind: str, lang: str = "cs", form=None) -> Response:
    query = {"book": kind, "lang": lang}
    for name in ("date_from", "date_to", "guests"):
        value = str((form or {}).get(name) or "").strip()[:10]
        if value:
            query[name] = value
    return RedirectResponse(f"/p/{slug}?{urlencode(query)}#book", status_code=303)
```

(b) In `property_page_book` (the legacy `/book` route) change nothing: it still calls `_book_error(slug, q["error"])` and still renders in English.

(c) In `property_page_checkout` replace the block shown in section 2 (from `    form = await request.form()` to the closing `)` of the `render(` call) with:

```python
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
```

(d) In `property_page_thanks` replace the `render(...)` shown in section 2 with:

```python
    response = render(request, "property_page_booked.html",
                      {"show_nav": False, "slug": slug, "lang": _page_lang(request)})
```

Run `.venv/bin/ruff check --select E9,F63,F7,F82,F401,F841 app/routes/property_page.py 2>&1 | tail -5`.

**Step 6.** `App/app/host_i18n.py`: add keys. Find the English anchor with `grep -nF '"pp.book.err.cancelled"' app/host_i18n.py` (two hits: the English block first, then the Czech block). Insert the English keys directly after the first hit's line and the Czech keys after the second hit's line. Write Czech as real UTF-8 (like the `site_booking.mail.*` keys).

English:

```python
        "pp.cal.title": "Choose your dates",
        "pp.cal.prev": "Previous month",
        "pp.cal.next": "Next month",
        "pp.cal.month.1": "January", "pp.cal.month.2": "February", "pp.cal.month.3": "March",
        "pp.cal.month.4": "April", "pp.cal.month.5": "May", "pp.cal.month.6": "June",
        "pp.cal.month.7": "July", "pp.cal.month.8": "August", "pp.cal.month.9": "September",
        "pp.cal.month.10": "October", "pp.cal.month.11": "November", "pp.cal.month.12": "December",
        "pp.cal.dow.1": "Mon", "pp.cal.dow.2": "Tue", "pp.cal.dow.3": "Wed", "pp.cal.dow.4": "Thu",
        "pp.cal.dow.5": "Fri", "pp.cal.dow.6": "Sat", "pp.cal.dow.7": "Sun",
        "pp.cal.state.free": "free",
        "pp.cal.state.taken": "booked",
        "pp.cal.state.past": "not available",
        "pp.cal.state.start": "arrival",
        "pp.cal.state.end": "departure",
        "pp.cal.state.range": "selected",
        "pp.cal.pick_from": "Tap your arrival day.",
        "pp.cal.pick_to": "Now tap your departure day.",
        "pp.cal.summary": "Arrival %(from)s · departure %(to)s",
        "pp.cal.guests_apply": "Show price",
        "pp.book.nightly_line": "%(price)s × %(nights)s",
        "pp.book.city_tax_note": "City tax %(amount)s CZK (%(guests)s guests × %(nights)s nights × %(rate)s CZK) is paid on site.",
        "pp.book.policy_title": "Cancellation: %(name)s",
        "pp.book.policy_name.non_refundable": "Non-refundable",
        "pp.book.policy_name.flexible": "Flexible",
        "pp.book.policy_name.moderate": "Moderate",
        "pp.book.pay_card": "Pay %(total)s CZK by card",
        "pp.book.stripe_note": "Stripe processes the payment. You get the confirmation by e-mail.",
        "pp.lang.label": "Language",
```

Czech:

```python
        "pp.cal.title": "Vyberte termín",
        "pp.cal.prev": "Předchozí měsíc",
        "pp.cal.next": "Další měsíc",
        "pp.cal.month.1": "Leden", "pp.cal.month.2": "Únor", "pp.cal.month.3": "Březen",
        "pp.cal.month.4": "Duben", "pp.cal.month.5": "Květen", "pp.cal.month.6": "Červen",
        "pp.cal.month.7": "Červenec", "pp.cal.month.8": "Srpen", "pp.cal.month.9": "Září",
        "pp.cal.month.10": "Říjen", "pp.cal.month.11": "Listopad", "pp.cal.month.12": "Prosinec",
        "pp.cal.dow.1": "po", "pp.cal.dow.2": "út", "pp.cal.dow.3": "st", "pp.cal.dow.4": "čt",
        "pp.cal.dow.5": "pá", "pp.cal.dow.6": "so", "pp.cal.dow.7": "ne",
        "pp.cal.state.free": "volné",
        "pp.cal.state.taken": "obsazeno",
        "pp.cal.state.past": "nedostupné",
        "pp.cal.state.start": "příjezd",
        "pp.cal.state.end": "odjezd",
        "pp.cal.state.range": "vybráno",
        "pp.cal.pick_from": "Klepněte na den příjezdu.",
        "pp.cal.pick_to": "Teď klepněte na den odjezdu.",
        "pp.cal.summary": "Příjezd %(from)s · odjezd %(to)s",
        "pp.cal.guests_apply": "Zobrazit cenu",
        "pp.book.nightly_line": "%(price)s × %(nights)s",
        "pp.book.city_tax_note": "Městský poplatek %(amount)s Kč (%(guests)s hostů × %(nights)s nocí × %(rate)s Kč) platíte na místě.",
        "pp.book.policy_title": "Storno podmínky: %(name)s",
        "pp.book.policy_name.non_refundable": "Nevratná",
        "pp.book.policy_name.flexible": "Flexibilní",
        "pp.book.policy_name.moderate": "Střední",
        "pp.book.pay_card": "Zaplatit %(total)s Kč kartou",
        "pp.book.stripe_note": "Platbu zpracuje Stripe. Potvrzení dostanete e-mailem.",
        "pp.lang.label": "Jazyk",
```

Also check that the Czech block already has `pp.book.name`, `pp.book.email`, `pp.book.terms`, `pp.book.guests`, `pp.book.cleaning`, `pp.book.total`, `pp.book.policy.*`, `pp.book.err.*`, `pp.book.done`, `pp.book.back`: `grep -c '"pp.book.terms"' app/host_i18n.py` must print 2. If any key of that list has only 1 hit, STOP.

`pp.book.city_tax_note` keeps fixed words (a sentence, accepted); the guests select shows the bare number under the label `pp.book.guests`.

Run `cd App && .venv/bin/python -m pytest tests/test_host_i18n.py tests/test_no_em_dashes.py -q --tb=short -x 2>&1 | tail -15`.

**Step 7.** `App/app/templates/property_page.html`. First check the token names: for each of `--surface`, `--canvas`, `--line`, `--line-2`, `--ink`, `--ink-2`, `--ink-3`, `--accent`, `--on-accent`, `--accent-soft`, `--accent-ink`, `--danger`, `--st-done-bg`, `--st-done-ink`, `--surface-2`, `--radius-2`, `--radius-3`, `--space-2`, `--space-3`, `--space-4`, `--size-12`, `--size-13`, `--size-14`, `--size-15`, `--size-16`, `--size-22`: `grep -c -- '<name>:' app/static/tokens.css`. A 0 means STOP (brief section 8).

(a) Replace the line `{% if page.noindex %}<meta name="robots" content="noindex">{% endif %}` (once, in `head_extra`) with itself followed by this block (page-owned, tokens only; mapping from the mockup: card `#fff` = `--surface`, border `#deded9` = `--line`, button/input border `#c9c9c2` = `--line-2`, coral `#ad4942` = `--accent`, rose range `#f9e9e7`/`#fbf0ee` = `--accent-soft`, muted `#50504c` = `--ink-2`, `#6b6b66` = `--ink-3`, grey badge `#f1f1ef` = `--surface-2`, green `#e6f5ec`/`#1f5f3b` = `--st-done-bg`/`--st-done-ink`):

```html
<style>
.pp-bk { display: flex; flex-direction: column; gap: var(--space-4); max-width: 520px; margin-top: var(--space-6); }
.pp-bk-card { background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius-3); padding: var(--space-4); display: flex; flex-direction: column; gap: var(--space-3); font-size: var(--size-14); color: var(--ink); }
.pp-bk-card h2 { margin: 0; font-size: var(--size-16); font-weight: 700; }
.pp-bk-note { color: var(--ink-2); font-size: var(--size-13); margin: 0; }
.pp-bk-fine { color: var(--ink-3); font-size: var(--size-12); text-align: center; margin: 0; }
.pp-bk-months { display: flex; align-items: center; justify-content: space-between; }
.pp-bk-months strong { font-size: var(--size-15); }
.pp-bk-nav { display: inline-flex; align-items: center; justify-content: center; width: 44px; height: 44px; border: 1px solid var(--line-2); border-radius: var(--radius-2); background: var(--surface); color: var(--ink); text-decoration: none; font-size: var(--size-16); }
.pp-bk-nav[aria-disabled="true"] { color: var(--ink-3); border-color: var(--line); }
.pp-bk-grid { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 2px; text-align: center; }
.pp-bk-dow { font-size: var(--size-12); color: var(--ink-3); }
.pp-bk-day { display: flex; align-items: center; justify-content: center; min-height: 44px; font-size: var(--size-14); color: var(--ink); text-decoration: none; border-radius: var(--radius-2); }
a.pp-bk-day:hover { background: var(--surface-2); }
.pp-bk-day[data-state="past"], .pp-bk-day[data-state="taken"] { color: var(--ink-3); text-decoration: line-through; }
.pp-bk-day[data-state="range"] { background: var(--accent-soft); border-radius: 0; }
.pp-bk-day[data-state="start"], .pp-bk-day[data-state="end"] { background: var(--accent); color: var(--on-accent); font-weight: 700; }
.pp-bk-day[data-state="start"] { border-radius: var(--radius-2) 0 0 var(--radius-2); }
.pp-bk-day[data-state="end"] { border-radius: 0 var(--radius-2) var(--radius-2) 0; }
.pp-bk-row { display: flex; justify-content: space-between; gap: var(--space-3); }
.pp-bk-total { border-top: 1px solid var(--line); padding-top: var(--space-3); font-size: var(--size-16); font-weight: 700; }
.pp-bk-guests { display: flex; gap: var(--space-2); align-items: flex-end; }
.pp-bk-guests .ui-field { flex: 1; }
.pp-bk-error { background: var(--accent-soft); border-radius: var(--radius-2); padding: var(--space-3); margin: 0; color: var(--ink); }
.pp-bk-lang { text-align: center; font-size: var(--size-12); color: var(--ink-3); }
.pp-bk-lang a { display: inline-flex; align-items: center; justify-content: center; min-width: 44px; min-height: 44px; color: var(--ink-2); }
.pp-bk-lang a[aria-current="true"] { color: var(--ink); font-weight: 700; }
.pp-bk .ui-btn { width: 100%; }
@media (max-width: 480px) { .pp-bk { max-width: none; } }
</style>
```

(b) Replace the block `{% if page.bookable %} ... {% endif %}` (old text in section 2) with the following. Put the `money` macro first inside it (macros must sit inside a block):

```html
    {% if page.bookable %}
    {% set b = page.booking %}
    {% macro money(n) %}{{ ('{:,}'.format(n) | replace(',', '&nbsp;')) | safe }}&nbsp;{{ t('payments.czk') }}{% endmacro %}
    <section class="pp-book pp-bk" id="book" aria-labelledby="bk-title">
      <div class="pp-bk-card">
        <h2 id="bk-title">{{ t('pp.cal.title') }}</h2>
        <div class="pp-bk-months">
          {% if b.prev_href %}<a class="pp-bk-nav" href="{{ b.prev_href }}" aria-label="{{ t('pp.cal.prev') }}">&lsaquo;</a>{% else %}<span class="pp-bk-nav" aria-disabled="true">&lsaquo;</span>{% endif %}
          <strong>{{ t('pp.cal.month.' ~ b.grid.month) }} {{ b.grid.year }}</strong>
          {% if b.next_href %}<a class="pp-bk-nav" href="{{ b.next_href }}" aria-label="{{ t('pp.cal.next') }}">&rsaquo;</a>{% else %}<span class="pp-bk-nav" aria-disabled="true">&rsaquo;</span>{% endif %}
        </div>
        <div class="pp-bk-grid" role="grid">
          {% for n in range(1, 8) %}<div class="pp-bk-dow">{{ t('pp.cal.dow.' ~ n) }}</div>{% endfor %}
          {% for week in b.grid.weeks %}{% for cell in week %}
            {% if cell.state == 'pad' %}<span></span>
            {% elif cell.href %}<a class="pp-bk-day" data-state="{{ cell.state }}" href="{{ cell.href }}" aria-label="{{ cell.day }}. {{ b.grid.month }}. {{ b.grid.year }}, {{ t('pp.cal.state.' ~ cell.state) }}">{{ cell.day }}</a>
            {% else %}<span class="pp-bk-day" data-state="{{ cell.state }}" aria-label="{{ cell.day }}. {{ b.grid.month }}. {{ b.grid.year }}, {{ t('pp.cal.state.' ~ cell.state) }}">{{ cell.day }}</span>{% endif %}
          {% endfor %}{% endfor %}
        </div>
        <p class="pp-bk-note">
          {% if b.q %}{{ t('pp.cal.summary', **{'from': b.arrive, 'to': b.depart}) }} · {{ tp('stay_fees.nights', b.q.nights) }}
          {% elif b.date_from and not b.date_to %}{{ t('pp.cal.pick_to') }}
          {% else %}{{ t('pp.cal.pick_from') }}{% endif %}
        </p>
        <form method="get" action="/p/{{ b.slug }}#book" class="pp-bk-guests">
          <input type="hidden" name="lang" value="{{ lang }}">
          <input type="hidden" name="month" value="{{ b.month_value }}">
          <input type="hidden" name="date_from" value="{{ b.date_from }}">
          <input type="hidden" name="date_to" value="{{ b.date_to }}">
          <label class="ui-field"><span>{{ t('pp.book.guests') }}</span>
            <select class="ui-input" name="guests">{% for n in b.guest_options %}<option value="{{ n }}"{% if n == b.guests %} selected{% endif %}>{{ n }}</option>{% endfor %}</select></label>
          <button class="ui-btn ui-btn-secondary" type="submit">{{ t('pp.cal.guests_apply') }}</button>
        </form>
        {% if b.q_error or page.book_error %}
        <p class="pp-bk-error" role="alert">{{ t('pp.book.err.' ~ (b.q_error or page.book_error)) }}</p>
        {% endif %}
      </div>

      {% if b.q %}
      <div class="pp-bk-card">
        <div class="pp-bk-row"><span>{{ t('pp.book.nightly_line', price=money(b.q.nightly_czk), nights=b.q.nights) | safe }}</span><span>{{ money(b.q.accommodation_czk) }}</span></div>
        {% if b.q.cleaning_fee_czk %}<div class="pp-bk-row"><span>{{ t('pp.book.cleaning') }}</span><span>{{ money(b.q.cleaning_fee_czk) }}</span></div>{% endif %}
        <div class="pp-bk-row pp-bk-total"><span>{{ t('pp.book.total') }}</span><span>{{ money(b.q.total_czk) }}</span></div>
        {% if b.q.city_tax_on_site_czk %}<p class="pp-bk-note">{{ t('pp.book.city_tax_note', amount=b.q.city_tax_on_site_czk, guests=b.q.guests, nights=b.q.nights, rate=b.city_tax_rate) }}</p>{% endif %}
      </div>

      <div class="pp-bk-card">
        <h2>{{ t('pp.book.policy_title', name=t('pp.book.policy_name.' ~ b.q.cancellation_policy)) }}</h2>
        <p class="pp-bk-note">{{ t('pp.book.policy.' ~ b.q.cancellation_policy) }}</p>
      </div>

      <form method="post" action="/p/{{ b.slug }}/checkout" class="pp-bk-card ui-form">
        <input type="hidden" name="date_from" value="{{ b.q.date_from }}">
        <input type="hidden" name="date_to" value="{{ b.q.date_to }}">
        <input type="hidden" name="guests" value="{{ b.q.guests }}">
        <input type="hidden" name="lang" value="{{ lang }}">
        <input type="hidden" name="terms_version" value="{{ b.terms_version }}">
        <label class="ui-field"><span>{{ t('pp.book.name') }}</span>
          <input class="ui-input" type="text" name="guest_name" autocomplete="name" minlength="3" maxlength="120" required></label>
        <label class="ui-field"><span>{{ t('pp.book.email') }}</span>
          <input class="ui-input" type="email" name="guest_email" autocomplete="email" required></label>
        <label class="ui-check"><input type="checkbox" name="terms" value="1" required><span>{{ t('pp.book.terms') }}</span></label>
        <button class="ui-btn ui-btn-primary" type="submit">{{ t('pp.book.pay_card', total=b.q.total_czk) }}</button>
        <p class="pp-bk-fine">{{ t('pp.book.stripe_note') }}</p>
      </form>
      {% endif %}

      <nav class="pp-bk-lang" aria-label="{{ t('pp.lang.label') }}">
        <a href="{{ b.lang_href.cs }}" hreflang="cs" lang="cs"{% if lang == 'cs' %} aria-current="true"{% endif %}>CS</a>
        <a href="{{ b.lang_href.en }}" hreflang="en" lang="en"{% if lang == 'en' %} aria-current="true"{% endif %}>EN</a>
      </nav>
    </section>
    {% endif %}
```

Notes for this step: `tp` is the template plural helper (`templating.py`, `tp('stay_fees.nights', 3)` prints "3 noci"). `t('pp.cal.summary', **{'from': ...})` is used because `from` is a Jinja keyword. If the `money(...)` value passed into `t(...)` prints escaped `&amp;nbsp;` in the test of step 8, change `nightly_line` to be built in the template: `{{ money(b.q.nightly_czk) }} × {{ b.q.nights }}` and delete the `pp.book.nightly_line` keys.

**Step 8.** Create `App/tests/test_booking_calendar.py` (use the fixture pattern of `tests/test_booking_checkout.py`: copy its `OWNER`-style `_cleanup`, create an account, an apartment, `booking_site.save_settings(aid, {"nightly_price_czk": 2000})`; use another username `calhost`). Tests, each short:

1. `test_taken_and_hold_nights`: insert an active `reservation` (apartment, `source='manual'`, `uid='cal-1'`, `date_from='2027-05-10'`, `date_to='2027-05-13'`, `status='active'`, timestamps `db.utcnow()`) and `booking_checkout.hold_dates(aid, '2027-05-20', '2027-05-22')`; `taken_nights(aid, date(2027,5,1), date(2027,6,1))` equals the five ISO days 10, 11, 12, 20, 21.
2. `test_grid_marks_states`: `month_grid(aid, 2027, 5, date_from='2027-05-05', date_to='2027-05-08', today=date(2027,5,1))`: cell 2027-05-05 is `start`, 06 is `range`, 08 is `end`, 11 is `taken` with `pick is None`... (careful: a taken day with a selection from 05-05 and no `date_to` is not clickable; here `date_to` is set, so `pick is None` for taken days).
3. `test_pick_end_blocked_by_taken_night`: with only `date_from='2027-05-08'`, the cell for 2027-05-13 has `pick == ('2027-05-08', '2027-05-13')`? No: nights 10 to 12 are taken, so `pick == ('2027-05-13', '')`; the cell for 2027-05-10 has `pick == ('2027-05-08', '2027-05-10')` (check-out on the first taken day is fine).
4. `test_month_bounds`: `prev` is None for the current month (pass `today=date(2027,5,1)` and year/month 2027/5), `next` is `(2027, 6)`, and for 2028/5 `next` is None. (Past cells depend on `earliest_check_in`; do not assert them for 2027.)

Create `App/tests/test_booking_site_page.py` (same fixture style, `lang` cookie `en` where the test needs English; add the Stripe account row exactly as the `apartment` fixture in `test_booking_checkout.py` does so `bookable` is true, and `property_page.publish_page(aid, published=True)`). Tests:

1. `test_default_language_is_czech`: no cookie: GET `/p/<slug>` contains `Vyberte termín` and `<html lang="cs">`; with `?lang=en` contains `Choose your dates` and `<html lang="en">`; a cookie `ubyhost_lang=en` without `?lang` gives English; the response has no `set-cookie` header for the language.
2. `test_quote_card_shows_price_lines`: GET `?lang=cs&date_from=2027-03-10&date_to=2027-03-13&guests=2` (price 2000, cleaning 500 as in the checkout tests; set `stay_fee_rate_czk = 50` on the apartment with `db.execute`) contains `6500`-formatted text `6&nbsp;500`, `Úklid`, `3 noci`, `Zaplatit 6500 Kč kartou`, `Městský poplatek 300 Kč`, `Storno podmínky: Nevratná`, `name="terms"`, `name="terms_version"`, and the form action `/p/<slug>/checkout`.
3. `test_taken_nights_are_marked`: add a `reservation` row for 2027-03-20 to 2027-03-22; GET `?month=2027-03&lang=en` contains `data-state="taken"`; and a GET with `date_from=2027-03-20&date_to=2027-03-22` shows the English error `These dates are already taken.`.
4. `test_no_quote_without_dates`: GET with no dates has no `name="terms"` and contains `Tap your arrival day.` (`?lang=en`).
5. `test_old_terms_version_is_refused`: POST `/p/<slug>/checkout` (use the `fake_sessions` pattern from `test_booking_checkout.py`, copy `_FakeSessions` and the fixture) with a valid form plus `terms_version=1999-01-01`, `follow_redirects=False`: 303 and `book=terms` in `location`, and `lang=cs` also in `location`. With the correct `TERMS_VERSION` it is 200.
6. `test_error_redirect_keeps_dates_and_language`: POST with a bad e-mail: `location` contains `book=bad_email`, `lang=en`, `date_from=2027-03-10`.
7. `test_page_is_light`: the response for a quote request is under 60000 bytes and contains no `src="http` and no `<script` other than the two `defer` scripts of `base.html` (assert `html.count("<script") <= 3`).
8. `test_thanks_page_czech_default`: GET `/p/<slug>/thanks` without cookie has `Děkujeme` (look up the Czech text of `pp.book.done` with `host_i18n.translate("cs", "pp.book.done")` instead of hard-coding it).

Run `cd App && .venv/bin/python -m pytest tests/test_booking_calendar.py tests/test_booking_site_page.py -q --tb=short -x 2>&1 | tail -30`. Fix once if it fails.

**Step 9.** Rewrite the two old assertions.

(a) `App/tests/test_property_page_meta.py`: replace the function `test_listing_page_is_english_only` (old text in section 2) with:

```python
def test_listing_page_chrome_is_czech_first_and_listing_copy_stays_verbatim(owner):
    """Owner decision (2 Nov 2026, booking site v1): the page's own words follow
    ?lang= or the saved language, Czech by default; the host's listing copy is
    never translated."""
    client = TestClient(app)
    response = client.get(f"/p/{_slug(owner)}")
    assert response.status_code == 200
    assert '<html lang="cs">' in response.text
    client.cookies.set("ubyhost_lang", "en")
    assert '<html lang="en">' in client.get(f"/p/{_slug(owner)}").text
    assert '<html lang="en">' in client.get(f"/p/{_slug(owner)}?lang=en").text
```

(b) `App/tests/test_booking_widget.py`: in `test_widget_hidden_without_price_or_stripe` replace `assert "Book this place" not in response.text` with `assert "Choose your dates" not in response.text`; in `test_widget_shown_when_ready` replace `assert "Book this place" in response.text` with `assert "Choose your dates" in response.text`. Their `_client()` sets the English cookie, so no other change.

(c) `docs/context/decisions.md`: append one line after the last line:

```
- 2026-11-02 | Booking page: the page's own words are Czech first with a CS/EN switch (?lang= or the saved language, no cookie set); host listing copy stays verbatim. Supersedes the 2026-10-28 "English-only" line for the page chrome | owner (approved mockups) | 0818
```

**Step 10.** Browser test. Create `App/tests/test_booking_site_page_browser.py`. Copy the server fixture style of `tests/test_host_quiet_dashboard_browser.py` (open lines 11-24 and 152-177 once; copy the `REQUIRE_BROWSER` / `sync_api` import block, the `_launch` helper and a module-scope `base` fixture that starts `uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))` in a thread; do not import `dashboard_host`). Seed one bookable apartment in a module-scope fixture exactly like the `apartment` fixture of `test_booking_site_page.py` (module scope: create it once, clean up at the end; set `nightly_price_czk` 1800, `cleaning_fee_czk` 600, policy `moderate`, `stay_fee_rate_czk` 50; one active reservation from 2027-03-20 to 2027-03-22). One test, parametrised over widths 360, 390, 1280, opening `{base}/p/<slug>?lang=cs&month=2027-03&date_from=2027-03-10&date_to=2027-03-13&guests=2` in a fresh context of that width and asserting:

- `document.documentElement.scrollWidth <= window.innerWidth` (no horizontal scroll);
- every `.pp-bk-day`, `.pp-bk-nav`, `.pp-bk-card .ui-btn`, `.pp-bk-lang a` has a bounding box at least 44 px high (and 44 px wide for `.pp-bk-nav` and `.pp-bk-lang a`);
- the pay button text contains `Zaplatit`;
- the computed `background-color` of `.pp-bk-day[data-state="start"]` equals the computed `--accent` value (read with `getComputedStyle(document.documentElement).getPropertyValue('--accent')` resolved through a temporary element, or compare with the `.ui-btn-primary` background);
- at 390 only: `page.screenshot(path=<repo>/docs/tasks/screenshots-0818/booking-390.png, full_page=True)` (create the folder; compute the repo root from `Path(__file__).resolve().parents[2]`).

Also click the day `2027-03-14` link (`a.pp-bk-day[href*="date_from=2027-03-14"]`) in a second small test and assert the URL then contains `date_from=2027-03-14` and the page contains no `name="terms"` (a new range starts), proving the calendar works with no JavaScript (launch the context with `java_script_enabled=False`).

**Step 11.** Run everything in section 6, then write the report (section 9). Look at the screenshot once with Read; do not retake. Compare to the mockup by eye: card order (calendar, price lines, policy, form), the accent on the arrival and departure day, line-through on booked days.

## 5. Do not touch

`App/app/booking_site.py`, `booking_webhook.py`, `booking_ical.py`, `stripe_connect.py`, `App/app/main.py` (CSP), `db.py`, migrations, every CSS file, `property_page_book.html`, `property_page_pay.html`, `property_page_booked.html` (they keep working with the language the route passes), `routes/payments.py`. Hard rules 2 (no third-party script, no tracking cookie), 3, 4 (no dependency), 6, 9.

## 6. Commands

From `App/`:

```
.venv/bin/ruff check --select E9,F63,F7,F82,F401,F841 app/booking_calendar.py app/routes/property_page.py app/booking_checkout.py tests/test_booking_calendar.py tests/test_booking_site_page.py tests/test_booking_site_page_browser.py 2>&1 | tail -5
.venv/bin/python -m pytest tests/test_booking_calendar.py tests/test_booking_site_page.py tests/test_booking_checkout.py tests/test_booking_widget.py tests/test_booking_site.py tests/test_booking_webhook.py tests/test_booking_ical.py tests/test_property_page.py tests/test_property_page_meta.py tests/test_property_page_photos.py tests/test_property_slug.py tests/test_host_i18n.py tests/test_no_em_dashes.py tests/test_stripe_connect.py -q --tb=short -x 2>&1 | tail -30
UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_booking_site_page_browser.py tests/test_guest_browser_e2e.py tests/test_host_geometry.py -q --tb=short -x -rs 2>&1 | tail -30
```

From the repo root: `python3 scripts/design_lint.py 2>&1 | tail -5` and `python3 scripts/context_lint.py 2>&1 | tail -5`. If the browser run reports any skipped test, that is a failure (executor.md): write the report as `blocked` and say which. The browser run needs Chromium (`.cursor/install.sh`); if it is missing and cannot be installed, STOP.

## 7. Acceptance

- [ ] The three §6 test runs pass; the browser run shows `0 skipped`.
- [ ] `grep -nE '#[0-9a-fA-F]{3,8}\b|rgb\(' App/app/templates/property_page.html` prints nothing (no raw colour).
- [ ] `grep -c 'ui-input' App/app/templates/property_page.html` is at least 3; no web font, no `<script` added to the template.
- [ ] A fresh `GET /p/<slug>` (no cookie) is Czech; `?lang=en` is English; no `Set-Cookie` for the language.
- [ ] `git diff --stat origin/main` lists only the §3 files.
- [ ] One 390 px screenshot is at `docs/tasks/screenshots-0818/booking-390.png` and is named in the report.

## 8. Stop and ask

Stop, and write the report, if: an excerpt is not found; a token in step 7 is missing; a test fails twice; the browser run skips anything or Chromium is missing; a key listed in step 6 has only one language hit; you reach 25 tool calls or about 50k tokens (report as `blocked`, see executor.md); a new dependency seems needed; a file outside §3 needs a change; §5 would be touched; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0818-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with its last 5 lines, §7 ticked, the two mockup deviations from §1, anything else that differs, questions, owner steps left. Do not push.

## Risk list (for the reviewer)

- `property_page.html`: page-owned inline `<style>` (justified: the public page has no stylesheet; tokens only). The terms checkbox has no link to a terms text page: no such page exists yet; the lawyer text is an open owner item before live bookings.
- `routes/property_page.py`: the "English only" rule is replaced (decision line added); `_page_lang` reads the language cookie but never sets one.
- `booking_calendar.py`: a night is the day it starts; check-out may be on a booked day; the 62-day look-ahead means a range crossing a far month is re-checked by `quote()` (which is the authority).
- Guest count select applies through a GET button ("Zobrazit cenu"), not on change: no JS by design.
- `booking_checkout.py`: only two URL strings change; Stripe still never gets a redirect from a POST.

## Owner steps

1. Merge when CI is green.
2. Open `/p/<slug>` of a test host on a phone and compare with the mockup; do not share the link with real guests until 0816 and this brief are deployed and the terms text is approved.
