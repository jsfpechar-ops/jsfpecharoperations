# 0819: Booking site host setup page (checklist, price and rules, calendar link, address, publish)

Status: todo
Depends on: 0818 merged (it adds the `pp.book.policy_name.*` keys and edits `host_i18n.py`; two briefs must not edit that file at once), 0814, 0817 | Base commit: tip of origin/main | Branch: task/0819-booking-site-host-setup
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

A Max host opens `/apartments/<id>/booking-site` and sees the approved mockup (`Host.dc.html`, 390 px): a 6-step checklist (4 of 6 style), the "Price and rules" form (saves through `booking_site.save_settings`), the private calendar link for Airbnb and Booking.com (`/p/<slug>/<token>.ics`) with a copy button, the site address with a QR code and a copy button, and the publish step. Hosts without the Max plan see one banner with a link to the plan page and no form. Everything saves with plain form posts (no JavaScript needed; the copy button is an enhancement and the link sits in a read-only field so it can be selected by hand).

Deviations from the mockup, on purpose (list them in the report): (1) the calendar link is shown in full inside a read-only field instead of masked, because without JavaScript the host must be able to copy it by hand; (2) the form also has "Minimum nights" and "Most guests" (the plan row for this brief lists them); (3) the list of bookings from the mockup is brief 0821, not this one.

## 2. Context

Plan: `docs/plans/booking-site-v1.md`. Rules and storage are in `App/app/booking_site.py` (`site_allowed(owner_user_id)`, `settings(aid)`, `save_settings(aid, values)` which raises `ValueError(<field name>)`, `ical_token(aid)`, `POLICIES`, `NOTICE_DAYS`). `save_settings` takes any of `nightly_price_czk, cleaning_fee_czk, min_nights, max_guests, cancellation_policy, advance_notice_days, same_day_cutoff_hour`. Every host screen follows `docs/design/MASTER.md` (section 13 checklist): the page extends `host_page.html`, uses only the macros of `_ui.html`, `_ui_layout.html`, `_components.html`, has no `<style>`, no `style=""`, no raw colour, and is listed in `docs/design/catalog.json` under `enforced_templates` so `scripts/design_lint.py` checks it. One primary button per group. Light mode only. Czech and English keys together (EN and CS parity, no em dash, button labels under 24 characters).

Copy rules (AGENTS.md 9): one explanation in one place; no sentence the button already says; write "no tracking cookies", never "no cookies".

QR helper: `payments.qr_data_uri(url)` in `App/app/payments.py` returns a `data:` URI (CSP allows `img-src data:`); the guide QR page uses it the same way. Copy button: macro `copy_button(target_id, label='')` in `_components.html` (works with JS; it copies the text of the element with that id, or an input's value).

Host routes for the property page live in `App/app/routes/payments.py`. Excerpt of its imports (verbatim):

```python
from .. import access, auth, config, db, host_i18n, i18n, mail, payment_links, payment_request, payment_services, payments_consent, security, stripe_connect
from ..templating import render
from .admin_helpers import back as _back
from .admin_helpers import flash as _flash
```

Excerpt `App/app/routes/payments.py` (the end of `property_page_photo_delete`; add the new routes directly after it, verbatim):

```python
    pp.delete_photo(apartment_id, str(form.get("path") or ""))
    return _back(f"/apartments/{apartment_id}/page", msg=_flash(request, "payments.page.saved"))
```

Excerpt `App/app/templates/property_page_review.html` (head of file, the model for a host page of this kind, verbatim):

```html
{% extends "host_page.html" %}
{% set nav = 'properties' %}
{% set body_kind = 'form' %}
{% block title %}{{ t('payments.page.title') }} · {{ apartment.internal_name }}{% endblock %}
{% block primary_action %}{% endblock %}
{% block tabs %}{% endblock %}
{% block toolbar %}{% endblock %}
{% block body %}
```

Excerpt `App/app/templates/property_page_review.html` (the preview link; add the new link right after it, verbatim):

```html
    {% if published %}<a class="ui-btn ui-btn-secondary ui-btn-compact" href="/p/{{ slug }}" target="_blank">{{ t('payments.page.preview') }}</a>{% endif %}
```

Macro signatures to use (verbatim from the repo):

```
_ui.html:        ui_button(label, variant='secondary', href='', type='button', size='regular', icon_name='', loading=false, disabled=false, attrs='', id='')
_ui.html:        ui_badge(kind, label, overdue=false)          # kind: action | attention | done | neutral
_ui.html:        ui_field(id, label, name='', value='', type='text', help='', error='', optional=false, attrs='', placeholder='')
_ui.html:        ui_select(id, label, options, selected='', name='', help='', error='', optional=false, attrs='')   # options: list of (value, label)
_ui_layout.html: ui_section(title, actions='', id='')  (call block holds the content)
_ui_layout.html: ui_facts(pairs)  # list of (key, value_html)
_ui_layout.html: ui_banner(kind, text, action_label='', action_href='')
_components.html: choice_card(name, value, label, checked=false, help_id='', help_text='', type='radio')   # a call block adds extra text
_components.html: copy_button(target_id, label='')
```

Each host POST form carries `<input type="hidden" name="_csrf" value="{{ csrf_token }}">`.

Excerpt `docs/design/catalog.json` (verbatim, in `enforced_templates`):

```
        "App/app/templates/dev_ui.html",
```

Excerpt `App/tests/test_design_guardrails_browser.py` (verbatim):

```python
ROUTES.update({
    "cleaning": "/cleaning",
    "settings-account": "/settings",
    "havel": "/havel",
    "payments": "/payments",
})
```

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/booking_setup.py` | create | checklist steps, form parsing, "calendar linked" mark |
| `App/app/routes/payments.py` | edit | `GET` and `POST /apartments/{id}/booking-site` |
| `App/app/templates/booking_site_setup.html` | create | the page |
| `App/app/templates/property_page_review.html` | edit | one link to the new page |
| `App/app/host_i18n.py` | edit | EN + CS keys `bsite.*` |
| `docs/design/pages/booking-site.md` | create | page add-on, under 40 lines |
| `docs/design/catalog.json` | edit | add the template to `enforced_templates` |
| `App/tests/test_booking_setup.py` | create | steps, parsing, routes |
| `App/tests/test_booking_site_host_browser.py` | create | 390 and 1280 geometry + screenshot |
| `App/tests/test_design_guardrails_browser.py` | edit | one route in `ROUTES` |
| `docs/tasks/0819-report.md`, `docs/tasks/screenshots-0819/booking-site-390.png` | create | report, screenshot |

No other file may change.

## 4. Steps

Commit after every step: `git add -A && git commit -qm "0819 step k"`.

**Step 1.** Create `App/app/booking_setup.py`:

```python
"""Booking site setup page logic (brief 0819, plan booking-site-v1)."""
from __future__ import annotations

import json
from typing import Any, Dict, List

from . import booking_site, db, property_page, stripe_connect

ORDER = ("stripe", "page", "price", "policy", "calendar", "publish")
ERR_FIELDS = ("nightly_price_czk", "cleaning_fee_czk", "min_nights", "max_guests",
              "cancellation_policy", "advance_notice_days")
# "<days>" or "<0>:<cutoff hour>" (same-day booking until that hour, Prague).
NOTICE_OPTIONS = ("0:12", "0:15", "0:18", "0:21", "1", "2", "3", "7")


def _ical_key(apartment_id: int) -> str:
    return f"booking_site_ical_done:{int(apartment_id)}"


def mark_calendar_done(apartment_id: int) -> None:
    db.set_setting(_ical_key(apartment_id), "1")


def steps(apartment_id: int, owner_user_id: int) -> List[Dict[str, Any]]:
    """The six setup steps in order; exactly one is `current` (the first open one)."""
    s = booking_site.settings(apartment_id)
    page = property_page.page_for(apartment_id)
    account = stripe_connect.account_for_owner(owner_user_id)
    photos = json.loads(page["photos_json"] or "[]")
    done = {
        "stripe": bool(account and account["onboarding_state"] == "complete"),
        "page": bool(photos) and bool((page["description"] or "").strip()),
        "price": int(s["nightly_price_czk"] or 0) > 0,
        "policy": db.get_setting(f"booking_site:{int(apartment_id)}") is not None,
        "calendar": db.get_setting(_ical_key(apartment_id)) == "1",
        "publish": bool(page["published"]),
    }
    current = next((key for key in ORDER if not done[key]), "")
    return [{"key": key, "done": done[key], "current": key == current} for key in ORDER]


def can_publish(rows: List[Dict[str, Any]]) -> bool:
    """Stripe connected and a price set; the other steps are advice."""
    done = {row["key"]: row["done"] for row in rows}
    return bool(done["stripe"] and done["price"])


def notice_value(s: Dict[str, Any]) -> str:
    if int(s["advance_notice_days"]) == 0:
        value = f"0:{int(s['same_day_cutoff_hour'])}"
        return value if value in NOTICE_OPTIONS else "0:18"
    return str(int(s["advance_notice_days"]))


def _whole(form, name: str, *, empty_is_zero: bool = False) -> int:
    text = str(form.get(name) or "").strip().replace(" ", "")
    if not text and empty_is_zero:
        return 0
    if not text.isdigit():
        raise ValueError(name)
    return int(text)


def parse_form(form) -> Dict[str, Any]:
    """Form fields to `save_settings` values. Raises ValueError(<field>)."""
    values: Dict[str, Any] = {
        "nightly_price_czk": _whole(form, "nightly_price_czk"),
        "cleaning_fee_czk": _whole(form, "cleaning_fee_czk", empty_is_zero=True),
        "min_nights": _whole(form, "min_nights"),
        "max_guests": _whole(form, "max_guests", empty_is_zero=True),
        "cancellation_policy": str(form.get("cancellation_policy") or ""),
    }
    notice = str(form.get("notice") or "")
    if notice not in NOTICE_OPTIONS:
        raise ValueError("advance_notice_days")
    days, _, hour = notice.partition(":")
    values["advance_notice_days"] = int(days)
    if hour:
        values["same_day_cutoff_hour"] = int(hour)
    return values


def error_field(exc: ValueError) -> str:
    """The i18n suffix for a `save_settings` / `parse_form` error."""
    field = {"same_day_cutoff_hour": "advance_notice_days"}.get(str(exc), str(exc))
    return field if field in ERR_FIELDS else "nightly_price_czk"
```

Run `cd App && .venv/bin/ruff check --select E9,F63,F7,F82,F401,F841 app/booking_setup.py 2>&1 | tail -5`.

**Step 2.** `App/app/routes/payments.py`: after the two lines of the `property_page_photo_delete` ending (section 2), insert:

```python


# --- booking site setup (brief 0819) ---------------------------------------------


def _bsite_apartment(request: Request, apartment_id: int):
    owner_id = access.owner_id(request)
    row = db.query_one(
        "SELECT id, internal_name FROM apartment WHERE id = ? AND owner_user_id = ?",
        (apartment_id, owner_id),
    )
    return row, owner_id


@router.get("/apartments/{apartment_id}/booking-site")
def booking_site_setup(request: Request, apartment_id: int):
    guard = auth.require_login(request)
    if guard:
        return guard
    apartment, owner_id = _bsite_apartment(request, apartment_id)
    if apartment is None:
        return Response(status_code=404)
    from .. import booking_setup, booking_site, property_page as pp
    from .. import payments as payments_mod

    context: Dict[str, Any] = {
        "nav": "properties", "apartment": apartment,
        "allowed": booking_site.site_allowed(owner_id),
    }
    if context["allowed"]:
        lang = host_i18n.lang_from_request(request)
        s = booking_site.settings(apartment_id)
        slug = pp.ensure_slug(apartment_id)["slug"]
        page_url = f"{config.PUBLIC_BASE_URL.rstrip('/')}/p/{slug}"
        rows = booking_setup.steps(apartment_id, owner_id)
        context.update(
            s=s,
            steps=rows,
            steps_done=sum(1 for row in rows if row["done"]),
            can_publish=booking_setup.can_publish(rows),
            published=any(row["key"] == "publish" and row["done"] for row in rows),
            page_url=page_url,
            ical_url=f"{page_url}/{booking_site.ical_token(apartment_id)}.ics",
            qr=payments_mod.qr_data_uri(page_url),
            notice_value=booking_setup.notice_value(s),
            notice_options=[
                (value, host_i18n.translate(lang, "bsite.notice." + value.replace(":", "_")))
                for value in booking_setup.NOTICE_OPTIONS
            ],
            policies=booking_site.POLICIES,
        )
    return render(request, "booking_site_setup.html", context)


@router.post("/apartments/{apartment_id}/booking-site")
async def booking_site_save(request: Request, apartment_id: int):
    guard = auth.require_login(request)
    if guard:
        return guard
    apartment, owner_id = _bsite_apartment(request, apartment_id)
    if apartment is None:
        return Response(status_code=404)
    from .. import booking_setup, booking_site, property_page as pp

    here = f"/apartments/{apartment_id}/booking-site"
    if not booking_site.site_allowed(owner_id):
        return _back(here, err=_flash(request, "bsite.err.not_max"))
    form = await request.form()
    if "ical_done" in form:
        booking_setup.mark_calendar_done(apartment_id)
        return _back(here, msg=_flash(request, "bsite.flash.ical_done"))
    if "publish" in form or "unpublish" in form:
        if "publish" in form and not booking_setup.can_publish(booking_setup.steps(apartment_id, owner_id)):
            return _back(here, err=_flash(request, "bsite.err.publish_not_ready"))
        pp.publish_page(apartment_id, published="publish" in form)
        key = "bsite.flash.published" if "publish" in form else "bsite.flash.unpublished"
        return _back(here, msg=_flash(request, key))
    try:
        booking_site.save_settings(apartment_id, booking_setup.parse_form(form))
    except ValueError as exc:
        return _back(here + "#rules", err=_flash(request, "bsite.err." + booking_setup.error_field(exc)))
    return _back(here, msg=_flash(request, "payments.page.saved"))
```

If `Dict` / `Any` are not imported in this file, they are (line 11 imports `Any, Dict, List`). Run ruff on the file (rules as step 1).

**Step 3.** `App/app/host_i18n.py`: keys. Anchor: `grep -nF '"payments.page.saved"' app/host_i18n.py` has two hits (English block, then Czech block). Insert the English keys after the first hit's line and the Czech keys after the second hit's line. Czech as real UTF-8.

English:

```python
        "bsite.title": "Booking site",
        "bsite.max_only": "The booking site is part of the Max plan.",
        "bsite.max_cta": "See plans",
        "bsite.steps.title": "Setup, step by step (%(done)s of 6)",
        "bsite.step.stripe": "Payments through Stripe are connected",
        "bsite.step.page": "Photos and description",
        "bsite.step.price": "Price per night and cleaning",
        "bsite.step.policy": "Cancellation terms",
        "bsite.step.calendar": "Connect the calendar to Airbnb",
        "bsite.step.publish": "Publish the site",
        "bsite.badge.done": "Done",
        "bsite.badge.next": "Next step",
        "bsite.badge.wait": "Waiting",
        "bsite.act.stripe": "Connect Stripe",
        "bsite.act.page": "Edit the page",
        "bsite.act.price": "Set the price",
        "bsite.act.calendar": "Show the link",
        "bsite.rules.title": "Price and rules",
        "bsite.f.price": "Price per night (CZK)",
        "bsite.f.cleaning": "Cleaning (CZK, once per stay)",
        "bsite.f.min_nights": "Minimum nights",
        "bsite.f.max_guests": "Most guests (0 = no limit)",
        "bsite.f.notice": "Book at the latest",
        "bsite.f.policy": "Cancellation terms",
        "bsite.notice.0_12": "On the arrival day until 12:00",
        "bsite.notice.0_15": "On the arrival day until 15:00",
        "bsite.notice.0_18": "On the arrival day until 18:00",
        "bsite.notice.0_21": "On the arrival day until 21:00",
        "bsite.notice.1": "1 day before arrival",
        "bsite.notice.2": "2 days before arrival",
        "bsite.notice.3": "3 days before arrival",
        "bsite.notice.7": "7 days before arrival",
        "bsite.policy_detail.non_refundable": "no refund after payment",
        "bsite.policy_detail.flexible": "full refund until 24 h before arrival",
        "bsite.policy_detail.moderate": "full refund until 5 days before, then half",
        "bsite.ical.title": "Calendar for Airbnb and Booking.com",
        "bsite.ical.help": "Paste this link into Airbnb (Calendar, Import calendar). Nights booked on the site are blocked there.",
        "bsite.ical.done_btn": "I pasted the link",
        "bsite.url.title": "Site address",
        "bsite.url.qr_alt": "QR code of the site address",
        "bsite.publish.btn": "Publish the site",
        "bsite.unpublish.btn": "Unpublish",
        "bsite.flash.published": "The booking site is live.",
        "bsite.flash.unpublished": "The booking site is hidden.",
        "bsite.flash.ical_done": "Marked as connected.",
        "bsite.err.not_max": "The booking site needs the Max plan.",
        "bsite.err.publish_not_ready": "Connect Stripe and set a price before you publish.",
        "bsite.err.nightly_price_czk": "Enter a price per night of 1 to 1000000 CZK.",
        "bsite.err.cleaning_fee_czk": "Enter the cleaning fee as a whole number of CZK, or 0.",
        "bsite.err.min_nights": "Minimum nights: a whole number from 1 to 30.",
        "bsite.err.max_guests": "Most guests: a whole number from 0 to 60.",
        "bsite.err.cancellation_policy": "Pick one of the three cancellation terms.",
        "bsite.err.advance_notice_days": "Pick when guests can book at the latest.",
```

Czech:

```python
        "bsite.title": "Rezervační web",
        "bsite.max_only": "Rezervační web patří do tarifu Max.",
        "bsite.max_cta": "Zobrazit tarify",
        "bsite.steps.title": "Nastavení krok za krokem (%(done)s z 6)",
        "bsite.step.stripe": "Platby přes Stripe jsou propojené",
        "bsite.step.page": "Fotky a popis bytu",
        "bsite.step.price": "Cena za noc a úklid",
        "bsite.step.policy": "Storno podmínky",
        "bsite.step.calendar": "Propojte kalendář s Airbnb",
        "bsite.step.publish": "Zveřejnit web",
        "bsite.badge.done": "Hotovo",
        "bsite.badge.next": "Další krok",
        "bsite.badge.wait": "Čeká",
        "bsite.act.stripe": "Propojit Stripe",
        "bsite.act.page": "Upravit stránku",
        "bsite.act.price": "Nastavit cenu",
        "bsite.act.calendar": "Ukázat odkaz",
        "bsite.rules.title": "Cena a pravidla",
        "bsite.f.price": "Cena za noc (Kč)",
        "bsite.f.cleaning": "Úklid (Kč, jednou za pobyt)",
        "bsite.f.min_nights": "Nejméně nocí",
        "bsite.f.max_guests": "Nejvíce hostů (0 = bez omezení)",
        "bsite.f.notice": "Rezervovat nejpozději",
        "bsite.f.policy": "Storno podmínky",
        "bsite.notice.0_12": "V den příjezdu do 12:00",
        "bsite.notice.0_15": "V den příjezdu do 15:00",
        "bsite.notice.0_18": "V den příjezdu do 18:00",
        "bsite.notice.0_21": "V den příjezdu do 21:00",
        "bsite.notice.1": "1 den před příjezdem",
        "bsite.notice.2": "2 dny před příjezdem",
        "bsite.notice.3": "3 dny před příjezdem",
        "bsite.notice.7": "7 dní před příjezdem",
        "bsite.policy_detail.non_refundable": "po zaplacení se nic nevrací",
        "bsite.policy_detail.flexible": "celá částka do 24 h před příjezdem",
        "bsite.policy_detail.moderate": "celá částka do 5 dní, potom polovina",
        "bsite.ical.title": "Kalendář pro Airbnb a Booking.com",
        "bsite.ical.help": "Vložte tento odkaz do Airbnb (Kalendář, Import kalendáře). Obsazené noci z webu se tam zablokují.",
        "bsite.ical.done_btn": "Odkaz jsem vložil(a)",
        "bsite.url.title": "Adresa webu",
        "bsite.url.qr_alt": "QR kód adresy webu",
        "bsite.publish.btn": "Zveřejnit web",
        "bsite.unpublish.btn": "Skrýt web",
        "bsite.flash.published": "Rezervační web je zveřejněný.",
        "bsite.flash.unpublished": "Rezervační web je skrytý.",
        "bsite.flash.ical_done": "Označeno jako propojené.",
        "bsite.err.not_max": "Rezervační web vyžaduje tarif Max.",
        "bsite.err.publish_not_ready": "Před zveřejněním propojte Stripe a nastavte cenu.",
        "bsite.err.nightly_price_czk": "Zadejte cenu za noc od 1 do 1000000 Kč.",
        "bsite.err.cleaning_fee_czk": "Zadejte úklid jako celé číslo v Kč, nebo 0.",
        "bsite.err.min_nights": "Nejméně nocí: celé číslo od 1 do 30.",
        "bsite.err.max_guests": "Nejvíce hostů: celé číslo od 0 do 60.",
        "bsite.err.cancellation_policy": "Vyberte jedny ze tří storno podmínek.",
        "bsite.err.advance_notice_days": "Vyberte, kdy nejpozději lze rezervovat.",
```

Also check `grep -c '"pp.book.policy_name.moderate"' app/host_i18n.py` prints 2 (from 0818) and `grep -c '"common.copy"' app/host_i18n.py` prints 2. Otherwise STOP. Run `.venv/bin/python -m pytest tests/test_host_i18n.py tests/test_no_em_dashes.py -q --tb=short -x 2>&1 | tail -15`.

**Step 4.** Create `App/app/templates/booking_site_setup.html`. Mapping from the mockup: card = `ui_section`; step rows = `ui_facts` pairs (step text, badge or button); input = `ui_field`; the three cancellation cards = `choice_card`; secondary buttons = `ui_button`. No class, style or colour of your own.

```html
{% extends "host_page.html" %}
{% from "_ui.html" import ui_button, ui_badge, ui_field, ui_select with context %}
{% from "_ui_layout.html" import ui_section, ui_facts, ui_banner with context %}
{% from "_components.html" import choice_card, copy_button with context %}
{% set nav = 'properties' %}
{% set body_kind = 'form' %}
{% block title %}{{ t('bsite.title') }} · {{ apartment.internal_name }}{% endblock %}
{% block back_url %}/apartments/{{ apartment.id }}/page{% endblock %}
{% block back_label %}{{ t('payments.page.title') }}{% endblock %}
{% block meta %}{{ apartment.internal_name }}{% endblock %}
{% block primary_action %}{% endblock %}
{% block tabs %}{% endblock %}
{% block toolbar %}{% endblock %}
{% block body %}
{% if not allowed %}
{{ ui_banner('attention', t('bsite.max_only'), t('bsite.max_cta'), '/predplatne') }}
{% else %}
{% call ui_section(t('bsite.steps.title', done=steps_done)) %}
<dl class="ui-facts">
  {% for row in steps %}
  <div>
    <dt>{{ t('bsite.step.' ~ row.key) }}</dt>
    <dd>
      {% if row.done %}{{ ui_badge('done', t('bsite.badge.done')) }}
      {% elif row.current %}{{ ui_badge('action', t('bsite.badge.next')) }}
      {% else %}{{ ui_badge('neutral', t('bsite.badge.wait')) }}{% endif %}
      {# the current step's one action button goes here, see below #}
    </dd>
  </div>
  {% endfor %}
</dl>
{% endcall %}
```

This is the same markup `ui_facts` prints (`ui-facts` is in the catalog); the Jinja `do` tag is not enabled in this repo, so the list is written by hand.

Each current (not done) step also gets one action link in its `dd`, next to the badge, using `ui_button(label, 'secondary', href=..., size='compact')`: stripe -> `/payments` (`bsite.act.stripe`), page -> `/apartments/{{ apartment.id }}/page` (`bsite.act.page`), price and policy -> `#rules` (`bsite.act.price`), calendar -> `#ical` (`bsite.act.calendar`). The publish step has no link: its button is in the publish section below. Only the current step shows its action.

Then the rest of the body, in this order, each section a `ui_section` call block:

1. `id="rules"`, title `t('bsite.rules.title')`: `<form method="post" action="/apartments/{{ apartment.id }}/booking-site">` with `_csrf`, then `ui_field('nightly_price_czk', t('bsite.f.price'), value=s.nightly_price_czk, type='number', attrs='min="1" inputmode="numeric" required')`, the same for `cleaning_fee_czk` (min 0), `min_nights` (min 1 max 30), `max_guests` (min 0 max 60); `ui_select('notice', t('bsite.f.notice'), notice_options, selected=notice_value)`; the label `t('bsite.f.policy')` in a `<p class="ui-label">`; then `<div class="ui-choice-cards">` with, for each `p in policies`, `{% call choice_card('cancellation_policy', p, t('pp.book.policy_name.' ~ p), s.cancellation_policy == p) %}<span class="ui-sub">{{ t('bsite.policy_detail.' ~ p) }}</span>{% endcall %}`; then `ui_button(t('common.save'), 'primary', type='submit')`.
2. `id="ical"`, title `t('bsite.ical.title')`: `<p class="ui-sub">{{ t('bsite.ical.help') }}</p>`, `<input class="ui-input ui-mono" id="ical-url" type="text" readonly value="{{ ical_url }}" aria-label="{{ t('bsite.ical.title') }}">`, `{{ copy_button('ical-url') }}`, and a small POST form (`_csrf`, hidden `ical_done=1`, `ui_button(t('bsite.ical.done_btn'), 'secondary', type='submit', size='compact')`).
3. title `t('bsite.url.title')`: `<p><a href="{{ page_url }}" id="page-url">{{ page_url }}</a></p>`, `{{ copy_button('page-url') }}`, `<img src="{{ qr }}" alt="{{ t('bsite.url.qr_alt') }}" width="160" height="160">`.
4. title `t('bsite.step.publish')`: one POST form with `_csrf`; if `published`: `ui_badge('done', t('payments.page.live'))` and `ui_button(t('bsite.unpublish.btn'), 'secondary', type='submit', attrs='name="unpublish" value="1"')`; else `ui_button(t('bsite.publish.btn'), 'primary', type='submit', attrs='name="publish" value="1"' ~ ('' if can_publish else ' disabled'))`. A disabled publish button is OK: the route re-checks. Only one primary button per button group.
5. `{% endif %}` and `{% endblock %}`.

Run `python3 scripts/design_lint.py 2>&1 | tail -10` after step 6 (the template must be in the catalog first). Any unknown class: delete it from the template; do not add classes to the catalog.

**Step 5.** `App/app/templates/property_page_review.html`: after the preview link line (section 2) add:

```html
    <a class="ui-btn ui-btn-secondary ui-btn-compact" href="/apartments/{{ apartment.id }}/booking-site">{{ t('bsite.title') }}</a>
```

**Step 6.** `docs/design/catalog.json`: add the line `"App/app/templates/booking_site_setup.html",` after the `dev_ui.html` line (same indentation). Then `python3 scripts/design_lint.py 2>&1 | tail -10` must print `design lint: OK`.

**Step 7.** Create `docs/design/pages/booking-site.md` from `docs/design/pages/TEMPLATE.md` (read it once; under 40 lines; no px, no colours). Fill: nav `properties`; body_kind `form`; title key `bsite.title`; back link `payments.page.title` -> `/apartments/<id>/page`; no primary action in the header; sections in order: setup steps (facts list with badge `done | action | neutral`), price and rules (form, three choice cards, one primary Save), calendar link (read-only field, copy button, "I pasted the link"), site address (link, copy button, QR), publish (one primary button, disabled until Stripe and price are done); Max gate banner `bsite.max_only` -> `/predplatne`; empty state: none; tests: this brief's files; screenshots 390 and 1280.

**Step 8.** Tests. Create `App/tests/test_booking_setup.py`. Copy the `owner` / `client` fixtures and `_cleanup` of `tests/test_property_page.py` (username `bsitehost`; also delete `site_booking`, `booking_hold`, `reservation`, `stripe_account` rows and the `settings` rows `booking_site:<aid>` and `booking_site_ical_done:<aid>` of the apartment in `_cleanup`). Tests:

1. `test_steps_start_open_and_advance`: new apartment: `booking_setup.steps(aid, oid)` has six rows, only `stripe` is `current`, none done except maybe none; after inserting a complete `stripe_account` row (copy from `test_booking_checkout.py`'s `apartment` fixture with `mode` = `config.STRIPE_MODE` via monkeypatch of `config.STRIPE_MODE` to `"test"`) and `booking_site.save_settings(aid, {"nightly_price_czk": 1800})`: `stripe`, `price` and `policy` are done and `page` is the current one; `can_publish` is True.
2. `test_parse_form_and_errors`: `parse_form({"nightly_price_czk": "1 800", "cleaning_fee_czk": "", "min_nights": "2", "max_guests": "", "cancellation_policy": "moderate", "notice": "0:18"})` equals the expected dict (`cleaning_fee_czk` 0, `max_guests` 0, `advance_notice_days` 0, `same_day_cutoff_hour` 18); `notice: "5"` raises `ValueError("advance_notice_days")`; `nightly_price_czk: "abc"` raises `ValueError("nightly_price_czk")`; `error_field(ValueError("same_day_cutoff_hour")) == "advance_notice_days"`.
3. `test_page_renders_for_the_owner` (client fixture): GET `/apartments/<aid>/booking-site?lang=en` is 200, contains `Setup, step by step (0 of 6)`, `name="nightly_price_czk"`, `/predplatne` NOT present, the iCal URL `.ics` and a `data:image/png;base64` QR; GET for another user's apartment id is 404.
4. `test_save_settings_roundtrip`: POST the form (`_csrf` is not needed with the `TestClient` helper? Follow how `tests/test_property_page.py` posts to `/apartments/<id>/page`; copy that approach for the token) with price 1800, cleaning 600, min_nights 2, max_guests 4, policy `moderate`, notice `0:18`; follow redirects off: 303; `booking_site.settings(aid)` shows the values and `property_page.nightly_price(aid) == 1800`. A bad price (`0`) redirects with an error and changes nothing.
5. `test_max_gate`: monkeypatch `booking_site.site_allowed` to return False: GET shows `/predplatne` and no `nightly_price_czk` field; POST is refused (303 with an error, settings unchanged).
6. `test_publish_needs_stripe_and_price`: POST `publish=1` with nothing set: page stays unpublished; with the Stripe row and a price: `property_page.page_for(aid)["published"]` is truthy; POST `unpublish=1` clears it.
7. `test_ical_done_mark`: POST `ical_done=1`: the `calendar` step is done.

Add to `App/tests/test_design_guardrails_browser.py`, inside the `ROUTES.update({...})` dict, the line `    "booking-site": "/apartments/{property_id}/booking-site",` after `"payments": "/payments",`.

Create `App/tests/test_booking_site_host_browser.py`: reuse the fixtures of `tests/test_design_guardrails_browser.py` (import `wide_base`, `wide_host`, `_wait_for_host_layout`, `_dismiss_optional_security_prompt`, `GUARD` exactly as that file does). One test opens `/apartments/<wide_host["apartments"][0]>/booking-site?lang=cs` at 390 and at 1280 with the host session cookie (copy the way `test_every_host_page_passes_the_layout_guard` does it), and asserts: `scrollWidth <= innerWidth`; every `button, a.ui-btn, input, select` that is visible is at least 44 px high at 390; the layout guard from `design_guard.js` reports no violation (call it as the existing test does); one `ui-btn-primary` at most in each `form`. At 390 it saves `page.screenshot(path=<repo root>/docs/tasks/screenshots-0819/booking-site-390.png, full_page=True)` (create the folder).

Run: `cd App && .venv/bin/python -m pytest tests/test_booking_setup.py -q --tb=short -x 2>&1 | tail -30`. Fix once if red.

**Step 9.** Run everything in section 6. Read the screenshot once with the Read tool and compare with the mockup: checklist first with one coral "next step" badge, form, calendar link, address with QR, publish. Write the report.

## 5. Do not touch

`App/app/booking_site.py`, `booking_checkout.py`, `booking_webhook.py`, `booking_ical.py`, `stripe_connect.py`, `property_page.py` (module), `routes/property_page.py`, every CSS and JS file, `db.py`, migrations, the public templates. Hard rules 2, 3, 4 (QR comes from the existing `qrcode` use in `payments.py`; no dependency added), 6 (light mode; forms work without JavaScript), 7.

## 6. Commands

From `App/`:

```
.venv/bin/ruff check --select E9,F63,F7,F82,F401,F841 app/booking_setup.py app/routes/payments.py tests/test_booking_setup.py tests/test_booking_site_host_browser.py 2>&1 | tail -5
.venv/bin/python -m pytest tests/test_booking_setup.py tests/test_booking_site.py tests/test_booking_ical.py tests/test_property_page.py tests/test_property_page_meta.py tests/test_property_slug.py tests/test_payments_dashboard.py tests/test_payment_request_model.py tests/test_stripe_connect.py tests/test_host_i18n.py tests/test_no_em_dashes.py tests/test_design_lint.py tests/test_design_properties.py tests/test_design_ui_macros.py tests/test_dev_ui.py -q --tb=short -x 2>&1 | tail -30
UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_booking_site_host_browser.py tests/test_design_guardrails_browser.py tests/test_host_geometry.py -q --tb=short -x -rs 2>&1 | tail -30
```


From the repo root: `python3 scripts/design_lint.py 2>&1 | tail -5` and `python3 scripts/context_lint.py 2>&1 | tail -5`. Any skipped browser test is a failure: report `blocked`.

## 7. Acceptance

- [ ] The three §6 runs pass; the browser run shows `0 skipped`.
- [ ] `python3 scripts/design_lint.py` prints `design lint: OK` with the template listed in `enforced_templates`.
- [ ] `grep -nE 'style=|<style|#[0-9a-fA-F]{3,8}\b' App/app/templates/booking_site_setup.html` prints nothing.
- [ ] A non-Max host (billing on, plan standard) sees only the banner; a Max host sees the form. (Covered by `test_max_gate`.)
- [ ] The form saves without JavaScript; the link field is selectable by hand.
- [ ] `docs/design/pages/booking-site.md` exists and has fewer than 40 lines.
- [ ] `git diff --stat origin/main` lists only the §3 files.
- [ ] One 390 px screenshot at `docs/tasks/screenshots-0819/booking-site-390.png`, named in the report.

## 8. Stop and ask

Stop, and write the report, if: an excerpt is not found; `pp.book.policy_name.moderate` is missing (0818 not merged); a test fails twice; the browser run skips anything or Chromium is missing; the design lint finds a class you cannot replace; you reach 25 tool calls or about 50k tokens (report as `blocked`); a new dependency seems needed; a file outside §3 needs a change; §5 would be touched; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0819-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with its last 5 lines, §7 ticked, the three deviations from §1, questions, owner steps left. Do not push.

## Risk list (for the reviewer)

- `routes/payments.py`: ownership check by `access.owner_id`; the Max gate is repeated on the POST; `ical_token()` writes a setting on first GET (by design, 0814).
- The calendar link is a secret in a read-only field on the host's own screen; it is not logged. Resetting the token is out of v1 (known gap, note in known-issues if the owner wants it).
- "Calendar linked" is a host-confirmed mark (we cannot see whether Airbnb fetched the feed); the step is advice, not a gate for publishing.
- The publish gate is Stripe complete and a price; photos and description are advice.
- `catalog.json` gains one template; no new class.

## Owner steps

1. Merge when CI is green.
2. Set the two test hosts to the Max plan in the billing cockpit, then open `/apartments/<id>/booking-site` on a phone and go through the six steps without help (plan section 5, step 4).
