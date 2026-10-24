# 0292: Host guest guide page and card editor

Status: review
Depends on: 0291 merged | Base commit: after 0291 | Branch: task/0292-guest-guide-pages
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Give the host a "Guest guide" page per property: every card grouped by topic in guest order, with its state, and a one-card editor with "Save and next card" that walks the host through every card still missing or waiting for a check. No AI and nothing guest-facing yet ([plan](../plans/guest-guide.md)).

## 2. Context

- All data rules live in `App/app/guest_guide.py` (0291). The routes only check ownership, call it, and redirect.
- Ownership: `access.apartment(request, id)` returns the row only for the signed-in host, so a foreign or archived property is a 404, and `guest_guide.get(apartment_id, item_id)` returns nothing for a card of another property.
- Host pages extend `host_page.html` and use only the catalog macros it imports (`ui_button`, `ui_badge`, `ui_field`, `ui_select`, `ui_textarea`, `ui_section`, `ui_table_begin/end`, `ui_banner`). The design lint enforces one `ui-btn-primary` per template and catalog classes only.
- The property page tabs in `apartment_form.html` are switched in place by `app.js` only when they carry `data-property-tab`. The new "Guest guide" tab is a plain link without it, so it opens its own page.
- Copy keys are new under `guest_guide.*` (the `guide.*` namespace belongs to the help page). en and cs must have the same keys; vi and uk fall back to English.
- POSTs in tests carry the CSRF token automatically (`tests/conftest.py`, `csrf_proof_on_form_posts`).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/routes/guest_guide.py` | create | List, add card, card editor, save, skip, delete |
| `App/app/templates/guest_guide.html` | create | The card list |
| `App/app/templates/guest_guide_card.html` | create | One card's editor |
| `App/tests/test_guest_guide_pages.py` | create | Route tests |
| `App/app/host_i18n.py` | edit | Add `_GUEST_GUIDE_STRINGS` (en, cs) |
| `App/app/main.py` | edit | Register the router |
| `App/app/templates/apartment_form.html` | edit | One tab link |
| `docs/design/catalog.json` | edit | Two `enforced_templates` entries |
| `App/tests/test_design_guardrails_browser.py` | edit | One route in the layout guard |

No other file may change.

## 4. Steps

1. Check 0291 is in: `ls App/app/guest_guide.py App/app/migrations/0013_guest_guide.sql 2>&1 | tail -30`. If either is missing, STOP (§8).

2. Create `App/app/routes/guest_guide.py` with exactly this content:

```python
"""0292: the host's guest guide pages: the card list and one card's editor.

The data and every rule about it live in ``app.guest_guide``; these routes only
check the property belongs to the host, call it, and redirect.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from .. import access, auth, guest_guide, security, templating
from .admin_helpers import back, flash

router = APIRouter(dependencies=[Depends(security.protect_host_post)])
PRIVATE = {"Cache-Control": "no-store"}


def _home(request: Request, apartment_id: int) -> Dict[str, Any]:
    row = access.apartment(request, apartment_id)
    if not row or row["archived_at"]:
        raise HTTPException(404)
    return dict(row)


def _base(apartment_id: int) -> str:
    return f"/apartments/{apartment_id}/guide"


def _render(request: Request, name: str, status_code: int = 200, **values):
    context = {"nav": "apartments", "visibility": guest_guide.VISIBILITY, **values}
    response = templating.render(request, name, context, status_code=status_code)
    response.headers.update(PRIVATE)
    return response


def _next_open(apartment_id: int, after_id: int) -> Optional[int]:
    """The next card in guest order that still needs the host, wrapping around."""
    rows = guest_guide.items(apartment_id)
    ids = [r["id"] for r in rows]
    start = ids.index(after_id) + 1 if after_id in ids else 0
    for row in rows[start:] + rows[:start]:
        if row["id"] != after_id and row["state"] in ("missing", "check"):
            return row["id"]
    return None


@router.get("/apartments/{apartment_id}/guide")
def guide_index(request: Request, apartment_id: int):
    guard = auth.require_login(request)
    if guard:
        return guard
    apartment = _home(request, apartment_id)
    guest_guide.ensure_defaults(apartment)
    rows = guest_guide.items(apartment_id)
    groups = [(topic, [r for r in rows if r["topic"] == topic]) for topic in guest_guide.TOPICS]
    return _render(
        request,
        "guest_guide.html",
        apartment=apartment,
        groups=[(topic, cards) for topic, cards in groups if cards],
        topics=guest_guide.TOPICS,
        must_have=guest_guide.MUST_HAVE,
        progress=guest_guide.progress(apartment_id),
        next_id=_next_open(apartment_id, 0),
    )


@router.post("/apartments/{apartment_id}/guide/cards")
async def guide_add(request: Request, apartment_id: int):
    guard = auth.require_login(request)
    if guard:
        return guard
    _home(request, apartment_id)
    form = await request.form()
    try:
        item_id = guest_guide.add_custom(apartment_id, str(form.get("topic", "")), str(form.get("title", "")))
    except guest_guide.GuideError as exc:
        return back(_base(apartment_id), err=flash(request, exc.key))
    return back(f"{_base(apartment_id)}/{item_id}")


@router.get("/apartments/{apartment_id}/guide/{item_id}")
def guide_card(request: Request, apartment_id: int, item_id: int):
    guard = auth.require_login(request)
    if guard:
        return guard
    apartment = _home(request, apartment_id)
    item = guest_guide.get(apartment_id, item_id)
    if not item:
        raise HTTPException(404)
    return _render(request, "guest_guide_card.html", apartment=apartment, item=item, values=item, error="")


@router.post("/apartments/{apartment_id}/guide/{item_id}")
async def guide_card_save(request: Request, apartment_id: int, item_id: int):
    guard = auth.require_login(request)
    if guard:
        return guard
    apartment = _home(request, apartment_id)
    item = guest_guide.get(apartment_id, item_id)
    if not item:
        raise HTTPException(404)
    form = await request.form()
    fields = {name: form.get(name, "") for name in guest_guide.LIMITS if name in form}
    fields["visibility"] = form.get("visibility", item["visibility"])
    try:
        guest_guide.save(apartment_id, item_id, fields)
    except guest_guide.GuideError as exc:
        values = {**item, **{k: str(v) for k, v in fields.items()}}
        return _render(
            request, "guest_guide_card.html", status_code=422,
            apartment=apartment, item=item, values=values, error=exc.key,
        )
    if form.get("then") == "next":
        next_id = _next_open(apartment_id, item_id)
        if next_id:
            return back(f"{_base(apartment_id)}/{next_id}", msg=flash(request, "flash.guest_guide.saved"))
    return back(_base(apartment_id), msg=flash(request, "flash.guest_guide.saved"))


@router.post("/apartments/{apartment_id}/guide/{item_id}/skip")
async def guide_card_skip(request: Request, apartment_id: int, item_id: int):
    guard = auth.require_login(request)
    if guard:
        return guard
    _home(request, apartment_id)
    form = await request.form()
    try:
        guest_guide.skip(apartment_id, item_id, skipped=form.get("skip") == "1")
    except guest_guide.GuideError:
        raise HTTPException(404) from None
    return back(_base(apartment_id))


@router.post("/apartments/{apartment_id}/guide/{item_id}/delete")
def guide_card_delete(request: Request, apartment_id: int, item_id: int):
    guard = auth.require_login(request)
    if guard:
        return guard
    _home(request, apartment_id)
    if not guest_guide.delete_custom(apartment_id, item_id):
        raise HTTPException(404)
    return back(_base(apartment_id), msg=flash(request, "flash.guest_guide.deleted"))
```

3. Create `App/app/templates/guest_guide.html` with exactly this content:

```html
{#- 0292: the host's guest guide, one property. Cards grouped by topic in
    guest order; a row opens the card editor. Data: app/guest_guide.py. -#}
{% extends "host_page.html" %}
{% set body_kind = 'list' %}
{% set base_url = '/apartments/' ~ apartment.id ~ '/guide' %}
{% block title %}{{ t('guest_guide.title') }} · {{ apartment.internal_name }} · UbyHost{% endblock %}
{% block page_title %}{{ t('guest_guide.title') }}{% endblock %}
{% block back_url %}/apartments/{{ apartment.id }}{% endblock %}
{% block back_label %}{{ apartment.internal_name }}{% endblock %}
{% block meta %}{{ t('guest_guide.progress', done=progress.done, total=progress.total) }}{% endblock %}
{% block primary_action %}{% if next_id %}{{ ui_button(t('guest_guide.continue'), 'primary', href=base_url ~ '/' ~ next_id) }}{% endif %}{% endblock %}
{% block body %}
{% set topic_options = [] %}{% for topic in topics %}{% set _ = topic_options.append((topic, t('guest_guide.topic.' ~ topic))) %}{% endfor %}
{% if progress.live %}
{{ ui_banner('neutral', t('guest_guide.live')) }}
{% else %}
{{ ui_banner('attention', t('guest_guide.not_live', done=progress.must_have_done, total=progress.must_have_total)) }}
{% endif %}
{% if progress.check %}{{ ui_banner('attention', t('guest_guide.check_waiting')) }}{% endif %}

{% for topic, cards in groups %}
{% call ui_section(t('guest_guide.topic.' ~ topic), id='topic-' ~ topic) %}
{{ ui_table_begin([(t('guest_guide.col.card'), ''), (t('guest_guide.col.state'), '')], label=t('guest_guide.topic.' ~ topic)) }}
{% for card in cards %}
{% set card_url = base_url ~ '/' ~ card.id %}
{% set card_title = card.title if card.kind == 'custom' else t('guest_guide.kind.' ~ card.kind ~ '.title') %}
<tr class="ui-row clickable-row" data-href="{{ card_url }}" tabindex="0" role="link" aria-label="{{ card_title }}">
  <td class="ui-cell-first" data-card="primary"><a href="{{ card_url }}">{{ card_title }}</a>{% if card.kind in must_have %} <span class="ui-sub">{{ t('guest_guide.must_have') }}</span>{% endif %}</td>
  <td data-card="badge">{% if card.state == 'done' %}{{ ui_badge('done', t('guest_guide.state.done')) }}{% elif card.state == 'check' %}{{ ui_badge('attention', t('guest_guide.state.check')) }}{% elif card.state == 'skipped' %}{{ ui_badge('neutral', t('guest_guide.state.skipped')) }}{% else %}{{ ui_badge('action', t('guest_guide.state.missing')) }}{% endif %}</td>
</tr>
{% endfor %}
{{ ui_table_end() }}
{% endcall %}
{% endfor %}

{% call ui_section(t('guest_guide.add.title'), id='add-card') %}
<form method="post" action="{{ base_url }}/cards">
<input type="hidden" name="_csrf" value="{{ csrf_token }}">
{{ ui_select('guide-add-topic', t('guest_guide.add.topic'), topic_options, name='topic') }}
{{ ui_field('guide-add-title', t('guest_guide.add.name'), name='title', placeholder=t('guest_guide.add.placeholder'), attrs='maxlength="120" required') }}
<div class="ui-form-actions">{{ ui_button(t('guest_guide.add.button'), 'secondary', type='submit', icon_name='plus') }}</div>
</form>
{% endcall %}
{% endblock %}
```

4. Create `App/app/templates/guest_guide_card.html` with exactly this content:

```html
{#- 0292: one guest guide card. "Save and next card" walks the host through
    every card that still needs them; the old free text arrives as a draft
    ('check') that guests never see until the host saves it. -#}
{% extends "host_page.html" %}
{% set body_kind = 'form' %}
{% set base_url = '/apartments/' ~ apartment.id ~ '/guide' %}
{% set custom = item.kind == 'custom' %}
{% set card_title = item.title if custom else t('guest_guide.kind.' ~ item.kind ~ '.title') %}
{% block title %}{{ card_title }} · {{ t('guest_guide.title') }} · UbyHost{% endblock %}
{% block page_title %}{{ card_title }}{% endblock %}
{% block back_url %}{{ base_url }}{% endblock %}
{% block back_label %}{{ t('guest_guide.title') }}{% endblock %}
{% block meta %}{{ t('guest_guide.custom_prompt') if custom else t('guest_guide.kind.' ~ item.kind ~ '.prompt') }}{% endblock %}
{% block body %}
{% set visibility_options = [] %}{% for level in visibility %}{% set _ = visibility_options.append((level, t('guest_guide.visibility.' ~ level))) %}{% endfor %}
{% if error %}{{ ui_banner('attention', t(error)) }}{% endif %}
{% if item.state == 'check' %}{{ ui_banner('attention', t('guest_guide.check_banner')) }}{% endif %}
{% if item.state == 'skipped' %}{{ ui_banner('neutral', t('guest_guide.skipped_banner')) }}{% endif %}
<form method="post" action="{{ base_url }}/{{ item.id }}">
<input type="hidden" name="_csrf" value="{{ csrf_token }}">
{% if custom %}{{ ui_field('guide-title', t('guest_guide.field.title'), name='title', value=values.title, attrs='maxlength="120" required') }}{% endif %}
{{ ui_field('guide-location', t('guest_guide.field.location'), name='location', value=values.location, help=t('guest_guide.field.location_help'), optional=true, attrs='maxlength="500"') }}
{{ ui_textarea('guide-steps', t('guest_guide.field.steps'), value=values.steps, name='steps', help=t('guest_guide.field.steps_help'), rows=8, attrs='maxlength="4000"') }}
{{ ui_textarea('guide-watch-out', t('guest_guide.field.watch_out'), value=values.watch_out, name='watch_out', help=t('guest_guide.field.watch_out_help'), optional=true, rows=3, attrs='maxlength="1000"') }}
{{ ui_field('guide-video', t('guest_guide.field.video'), name='video_url', value=values.video_url, type='url', help=t('guest_guide.field.video_help'), optional=true, attrs='maxlength="500" inputmode="url"') }}
{{ ui_select('guide-visibility', t('guest_guide.field.visibility'), visibility_options, selected=values.visibility, name='visibility', help=t('guest_guide.field.visibility_help')) }}
<div class="ui-form-actions">
{{ ui_button(t('guest_guide.save_next'), 'primary', type='submit', attrs='name="then" value="next"') }}
{{ ui_button(t('guest_guide.save'), 'secondary', type='submit') }}
</div>
</form>

{% call ui_section(t('guest_guide.more.title'), id='card-more') %}
<div class="ui-btn-group">
<form method="post" action="{{ base_url }}/{{ item.id }}/skip">
<input type="hidden" name="_csrf" value="{{ csrf_token }}">
{% if item.state == 'skipped' %}
<input type="hidden" name="skip" value="0">
{{ ui_button(t('guest_guide.unskip'), 'secondary', type='submit') }}
{% else %}
<input type="hidden" name="skip" value="1">
{{ ui_button(t('guest_guide.skip'), 'quiet', type='submit') }}
{% endif %}
</form>
{% if custom %}
<form method="post" action="{{ base_url }}/{{ item.id }}/delete" data-confirm data-confirm-message="{{ t('guest_guide.delete_confirm') }}">
<input type="hidden" name="_csrf" value="{{ csrf_token }}">
{{ ui_button(t('guest_guide.delete'), 'danger', type='submit') }}
</form>
{% endif %}
</div>
{% endcall %}
{% endblock %}
```

5. In `App/app/host_i18n.py`, find these two lines (they appear once):

```python
for _lang, _strings in _DOOR_CODE_WINDOW_STRINGS.items():
    STRINGS[_lang].update(_strings)
```

Directly after them, insert one blank line and then exactly this block:

```python
# 0292: the host's guest guide pages (app/routes/guest_guide.py).
_GUEST_GUIDE_STRINGS = {
    "en": {
        "guest_guide.title": "Guest guide",
        "guest_guide.tab": "Guest guide",
        "guest_guide.progress": "%(done)s of %(total)s cards done",
        "guest_guide.continue": "Continue",
        "guest_guide.live": "Guests can read this guide. Only cards marked Done reach them.",
        "guest_guide.not_live": "Guests cannot see the guide yet. Finish the must-have cards first (%(done)s of %(total)s done).",
        "guest_guide.check_waiting": "Some cards were filled in for you. Open them, check every word, and save. Guests never see a card you have not checked.",
        "guest_guide.must_have": "Must-have",
        "guest_guide.col.card": "Card",
        "guest_guide.col.state": "State",
        "guest_guide.state.missing": "Missing",
        "guest_guide.state.check": "Check this",
        "guest_guide.state.done": "Done",
        "guest_guide.state.skipped": "Not needed",
        "guest_guide.topic.arrival": "Arrival",
        "guest_guide.topic.wifi": "Wi-Fi and TV",
        "guest_guide.topic.heating": "Heating and hot water",
        "guest_guide.topic.kitchen": "Kitchen",
        "guest_guide.topic.rooms": "Rooms",
        "guest_guide.topic.bathroom": "Bathroom and laundry",
        "guest_guide.topic.rules": "House rules",
        "guest_guide.topic.trash": "Trash",
        "guest_guide.topic.checkout": "Checkout",
        "guest_guide.topic.area": "Nearby",
        "guest_guide.topic.emergency": "Emergencies",
        "guest_guide.kind.checkin.title": "Check-in and arrival",
        "guest_guide.kind.checkin.prompt": "How do guests find the building and the flat? Which entrance, which floor, which door?",
        "guest_guide.kind.keys.title": "Keys and lockbox",
        "guest_guide.kind.keys.prompt": "Where are the keys or the lockbox? How do guests open it, and what do they do with the keys when they leave?",
        "guest_guide.kind.parking.title": "Parking",
        "guest_guide.kind.parking.prompt": "Where can guests park, is it free, and is there anything they must not do?",
        "guest_guide.kind.garage.title": "Garage",
        "guest_guide.kind.garage.prompt": "How do guests open the garage: remote, code or key? Where is their spot?",
        "guest_guide.kind.wifi.title": "Wi-Fi",
        "guest_guide.kind.wifi.prompt": "Network name and password. Where is the router if the internet stops working?",
        "guest_guide.kind.tv.title": "TV and streaming",
        "guest_guide.kind.tv.prompt": "Which remote does what? How do guests open Netflix or YouTube?",
        "guest_guide.kind.heating.title": "Heating",
        "guest_guide.kind.heating.prompt": "Where is the boiler or thermostat? How do guests make it warmer? What does it show when something goes wrong, and what should they do?",
        "guest_guide.kind.hot_water.title": "Hot water",
        "guest_guide.kind.hot_water.prompt": "How long does hot water take? Is there a tank that runs out, and what do guests do if the water is cold?",
        "guest_guide.kind.air_conditioning.title": "Air conditioning",
        "guest_guide.kind.air_conditioning.prompt": "Where is the remote? Which buttons cool the room? Should windows stay closed?",
        "guest_guide.kind.kitchen_appliances.title": "Kitchen and appliances",
        "guest_guide.kind.kitchen_appliances.prompt": "How do guests turn on the hob and the oven? Anything that trips the fuse?",
        "guest_guide.kind.dishwasher.title": "Dishwasher",
        "guest_guide.kind.dishwasher.prompt": "Where are the tablets? Which programme should guests use?",
        "guest_guide.kind.coffee_machine.title": "Coffee machine",
        "guest_guide.kind.coffee_machine.prompt": "Which machine is it, where are the capsules or beans, and how do guests make a cup?",
        "guest_guide.kind.sofa_bed.title": "Sofa bed",
        "guest_guide.kind.sofa_bed.prompt": "How do guests open the sofa bed, and where is the extra bedding?",
        "guest_guide.kind.balcony.title": "Balcony",
        "guest_guide.kind.balcony.prompt": "How does the balcony door open? Is smoking allowed there?",
        "guest_guide.kind.washing_machine.title": "Washing machine",
        "guest_guide.kind.washing_machine.prompt": "Where is the detergent? Which programme should guests use, and where do clothes dry?",
        "guest_guide.kind.house_rules.title": "House rules",
        "guest_guide.kind.house_rules.prompt": "Quiet hours, smoking, pets, visitors. Anything the neighbours care about.",
        "guest_guide.kind.trash.title": "Trash and recycling",
        "guest_guide.kind.trash.prompt": "Where are the bins? Which bin is for what?",
        "guest_guide.kind.checkout.title": "Checkout",
        "guest_guide.kind.checkout.prompt": "What should guests do before they leave: keys, dishes, windows, heating?",
        "guest_guide.kind.area_tips.title": "Shops and tips nearby",
        "guest_guide.kind.area_tips.prompt": "The nearest shop, pharmacy and a place you like to eat.",
        "guest_guide.kind.emergency.title": "Emergencies",
        "guest_guide.kind.emergency.prompt": "Where are the fuse box and the main water valve? Who do guests call if you do not answer?",
        "guest_guide.custom_prompt": "Write it so a tired guest arriving at night can follow it.",
        "guest_guide.check_banner": "This card was filled in for you. Check every word, fix anything wrong, and save. Guests see it only after you save.",
        "guest_guide.skipped_banner": "You marked this card as not needed here. Guests do not see it.",
        "guest_guide.field.title": "Card name",
        "guest_guide.field.location": "Where is it?",
        "guest_guide.field.location_help": "For example: hallway cupboard, left of the door.",
        "guest_guide.field.steps": "How does it work?",
        "guest_guide.field.steps_help": "One step per line. Tip: tap the microphone on your keyboard and just talk.",
        "guest_guide.field.watch_out": "Watch out for",
        "guest_guide.field.watch_out_help": "What goes wrong most often, and what guests should never do.",
        "guest_guide.field.video": "Video link",
        "guest_guide.field.video_help": "A short phone video helps a lot. The link must start with https://.",
        "guest_guide.field.visibility": "Who can read this?",
        "guest_guide.field.visibility_help": "Codes and anything private should be for booked guests only.",
        "guest_guide.visibility.everyone": "Everyone with the QR code",
        "guest_guide.visibility.booked": "Booked guests during their stay",
        "guest_guide.visibility.host": "Only you",
        "guest_guide.save_next": "Save and next card",
        "guest_guide.save": "Save",
        "guest_guide.more.title": "More",
        "guest_guide.skip": "Not needed here",
        "guest_guide.unskip": "Bring the card back",
        "guest_guide.delete": "Delete card",
        "guest_guide.delete_confirm": "Delete this card? This cannot be undone.",
        "guest_guide.add.title": "Add a card",
        "guest_guide.add.topic": "Topic",
        "guest_guide.add.name": "Card name",
        "guest_guide.add.placeholder": "For example: Induction hob",
        "guest_guide.add.button": "Add a card",
        "flash.guest_guide.saved": "Card saved.",
        "flash.guest_guide.deleted": "Card deleted.",
        "flash.error.guide_unknown_card": "That card or topic does not exist.",
        "flash.error.guide_too_long": "One of the fields is too long. Shorten it and save again.",
        "flash.error.guide_video_url": "The video link must start with https://.",
        "flash.error.guide_visibility": "Choose who can read this card.",
        "flash.error.guide_no_such_item": "That card does not exist.",
        "flash.error.guide_title_required": "Give the card a name.",
    },
    "cs": {
        "guest_guide.title": "Průvodce pro hosty",
        "guest_guide.tab": "Průvodce pro hosty",
        "guest_guide.progress": "Hotovo %(done)s z %(total)s karet",
        "guest_guide.continue": "Pokračovat",
        "guest_guide.live": "Hosté průvodce vidí. Dostanou se k nim jen karty označené Hotovo.",
        "guest_guide.not_live": "Hosté průvodce zatím nevidí. Nejdřív dokončete povinné karty (hotovo %(done)s z %(total)s).",
        "guest_guide.check_waiting": "Některé karty jsme vyplnili za vás. Otevřete je, zkontrolujte každé slovo a uložte. Hosté nikdy neuvidí kartu, kterou jste nezkontrolovali.",
        "guest_guide.must_have": "Povinné",
        "guest_guide.col.card": "Karta",
        "guest_guide.col.state": "Stav",
        "guest_guide.state.missing": "Chybí",
        "guest_guide.state.check": "Zkontrolovat",
        "guest_guide.state.done": "Hotovo",
        "guest_guide.state.skipped": "Netýká se",
        "guest_guide.topic.arrival": "Příjezd",
        "guest_guide.topic.wifi": "Wi-Fi a televize",
        "guest_guide.topic.heating": "Topení a teplá voda",
        "guest_guide.topic.kitchen": "Kuchyň",
        "guest_guide.topic.rooms": "Pokoje",
        "guest_guide.topic.bathroom": "Koupelna a praní",
        "guest_guide.topic.rules": "Pravidla ubytování",
        "guest_guide.topic.trash": "Odpad",
        "guest_guide.topic.checkout": "Odjezd",
        "guest_guide.topic.area": "V okolí",
        "guest_guide.topic.emergency": "Nouzové situace",
        "guest_guide.kind.checkin.title": "Příjezd a check-in",
        "guest_guide.kind.checkin.prompt": "Jak hosté najdou dům a byt? Který vchod, které patro, které dveře?",
        "guest_guide.kind.keys.title": "Klíče a schránka na klíče",
        "guest_guide.kind.keys.prompt": "Kde jsou klíče nebo schránka? Jak ji hosté otevřou a co mají s klíči udělat při odjezdu?",
        "guest_guide.kind.parking.title": "Parkování",
        "guest_guide.kind.parking.prompt": "Kde mohou hosté parkovat, je to zdarma a co nesmějí dělat?",
        "guest_guide.kind.garage.title": "Garáž",
        "guest_guide.kind.garage.prompt": "Jak hosté otevřou garáž: ovladačem, kódem, nebo klíčem? Kde je jejich místo?",
        "guest_guide.kind.wifi.title": "Wi-Fi",
        "guest_guide.kind.wifi.prompt": "Název sítě a heslo. Kde je router, když internet přestane fungovat?",
        "guest_guide.kind.tv.title": "Televize a streamování",
        "guest_guide.kind.tv.prompt": "Který ovladač k čemu slouží? Jak hosté pustí Netflix nebo YouTube?",
        "guest_guide.kind.heating.title": "Topení",
        "guest_guide.kind.heating.prompt": "Kde je kotel nebo termostat? Jak hosté přitopí? Co kotel ukáže, když je něco špatně, a co mají hosté udělat?",
        "guest_guide.kind.hot_water.title": "Teplá voda",
        "guest_guide.kind.hot_water.prompt": "Jak dlouho trvá, než teče teplá voda? Je tam bojler, který se vyčerpá, a co mají hosté dělat, když teče studená?",
        "guest_guide.kind.air_conditioning.title": "Klimatizace",
        "guest_guide.kind.air_conditioning.prompt": "Kde je ovladač? Kterými tlačítky se chladí? Mají zůstat okna zavřená?",
        "guest_guide.kind.kitchen_appliances.title": "Kuchyň a spotřebiče",
        "guest_guide.kind.kitchen_appliances.prompt": "Jak hosté zapnou varnou desku a troubu? Vyhazuje něco jističe?",
        "guest_guide.kind.dishwasher.title": "Myčka",
        "guest_guide.kind.dishwasher.prompt": "Kde jsou tablety? Jaký program mají hosté použít?",
        "guest_guide.kind.coffee_machine.title": "Kávovar",
        "guest_guide.kind.coffee_machine.prompt": "Jaký je to kávovar, kde jsou kapsle nebo zrnka a jak si hosté udělají kávu?",
        "guest_guide.kind.sofa_bed.title": "Rozkládací pohovka",
        "guest_guide.kind.sofa_bed.prompt": "Jak hosté pohovku rozloží a kde je povlečení navíc?",
        "guest_guide.kind.balcony.title": "Balkon",
        "guest_guide.kind.balcony.prompt": "Jak se otevírají dveře na balkon? Smí se tam kouřit?",
        "guest_guide.kind.washing_machine.title": "Pračka",
        "guest_guide.kind.washing_machine.prompt": "Kde je prací prostředek? Jaký program mají hosté použít a kde se suší prádlo?",
        "guest_guide.kind.house_rules.title": "Pravidla ubytování",
        "guest_guide.kind.house_rules.prompt": "Noční klid, kouření, zvířata, návštěvy. Cokoli, na čem záleží sousedům.",
        "guest_guide.kind.trash.title": "Odpad a třídění",
        "guest_guide.kind.trash.prompt": "Kde jsou popelnice? Která je na co?",
        "guest_guide.kind.checkout.title": "Odjezd",
        "guest_guide.kind.checkout.prompt": "Co mají hosté udělat před odjezdem: klíče, nádobí, okna, topení?",
        "guest_guide.kind.area_tips.title": "Obchody a tipy v okolí",
        "guest_guide.kind.area_tips.prompt": "Nejbližší obchod, lékárna a podnik, kam rádi chodíte jíst.",
        "guest_guide.kind.emergency.title": "Nouzové situace",
        "guest_guide.kind.emergency.prompt": "Kde jsou jističe a hlavní uzávěr vody? Komu mají hosté volat, když se vám nedovolají?",
        "guest_guide.custom_prompt": "Napište to tak, aby to zvládl i unavený host, který přijede v noci.",
        "guest_guide.check_banner": "Tuto kartu jsme vyplnili za vás. Zkontrolujte každé slovo, opravte, co nesedí, a uložte. Hosté ji uvidí až po uložení.",
        "guest_guide.skipped_banner": "Tuto kartu jste označili, že se tu netýká. Hosté ji nevidí.",
        "guest_guide.field.title": "Název karty",
        "guest_guide.field.location": "Kde to je?",
        "guest_guide.field.location_help": "Například: skříň v předsíni, vlevo od dveří.",
        "guest_guide.field.steps": "Jak to funguje?",
        "guest_guide.field.steps_help": "Jeden krok na řádek. Tip: klepněte na mikrofon na klávesnici a prostě to nadiktujte.",
        "guest_guide.field.watch_out": "Na co si dát pozor",
        "guest_guide.field.watch_out_help": "Co se nejčastěji pokazí a co hosté nikdy nemají dělat.",
        "guest_guide.field.video": "Odkaz na video",
        "guest_guide.field.video_help": "Krátké video z telefonu hodně pomůže. Odkaz musí začínat https://.",
        "guest_guide.field.visibility": "Kdo to může číst?",
        "guest_guide.field.visibility_help": "Kódy a vše soukromé nechte jen pro hosty s rezervací.",
        "guest_guide.visibility.everyone": "Každý s QR kódem",
        "guest_guide.visibility.booked": "Hosté s rezervací během pobytu",
        "guest_guide.visibility.host": "Jen vy",
        "guest_guide.save_next": "Uložit a další karta",
        "guest_guide.save": "Uložit",
        "guest_guide.more.title": "Další možnosti",
        "guest_guide.skip": "Tady se netýká",
        "guest_guide.unskip": "Vrátit kartu",
        "guest_guide.delete": "Smazat kartu",
        "guest_guide.delete_confirm": "Smazat tuto kartu? Nelze to vrátit.",
        "guest_guide.add.title": "Přidat kartu",
        "guest_guide.add.topic": "Téma",
        "guest_guide.add.name": "Název karty",
        "guest_guide.add.placeholder": "Například: Indukční deska",
        "guest_guide.add.button": "Přidat kartu",
        "flash.guest_guide.saved": "Karta uložena.",
        "flash.guest_guide.deleted": "Karta smazána.",
        "flash.error.guide_unknown_card": "Taková karta nebo téma neexistuje.",
        "flash.error.guide_too_long": "Některé pole je příliš dlouhé. Zkraťte ho a uložte znovu.",
        "flash.error.guide_video_url": "Odkaz na video musí začínat https://.",
        "flash.error.guide_visibility": "Vyberte, kdo může kartu číst.",
        "flash.error.guide_no_such_item": "Taková karta neexistuje.",
        "flash.error.guide_title_required": "Pojmenujte kartu.",
    },
}

for _lang, _strings in _GUEST_GUIDE_STRINGS.items():
    STRINGS[_lang].update(_strings)
```

6. In `App/app/main.py`:
   - In the line `from .routes import admin, cleaning as cleaning_routes, dev_ui, guest, invoices, ...`, insert `guest_guide as guest_guide_routes, ` right after `guest, `.
   - After the line `app.include_router(cleaning_routes.router)`, add `app.include_router(guest_guide_routes.router)`.

7. In `App/app/templates/apartment_form.html`, inside `<nav class="ui-tabs property-tabs" ...>`, after the `{% endfor %}` that closes the tab loop and before `</nav>`, add exactly:

```html
  <a class="ui-tab" href="{{ base_url }}/guide">{{ t('guest_guide.tab') }}</a>
```

Do not add `data-property-tab` to it.

8. In `docs/design/catalog.json`, append to the `enforced_templates` list, after `"App/app/templates/admin_funnel.html"`:

```json
    "App/app/templates/guest_guide.html",
    "App/app/templates/guest_guide_card.html"
```

(add the comma after `admin_funnel.html"`).

9. In `App/tests/test_design_guardrails_browser.py`, in the `ROUTES.update({` block, after the line `    "cleaning": "/cleaning",` add:

```python
    "guest-guide": "/apartments/{property_id}/guide",
```

10. Create `App/tests/test_guest_guide_pages.py` with exactly this content:

```python
"""0292: the host's guest guide pages."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import auth, config, db, guest_guide
from app.main import app
from tests.conftest import login_as


@pytest.fixture
def ws(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "guide.sqlite3")
    monkeypatch.setattr(auth, "staging_no_login", lambda: False)
    db.init_db()
    owner = auth.create_account("guide-owner@example.test", "Guide owner", username="guide-owner", role="host")
    other = auth.create_account("guide-other@example.test", "Other owner", username="guide-other", role="host")
    now = db.utcnow()

    def home(name, user, **extra):
        return db.insert("apartment", {
            "owner_user_id": user, "internal_name": name, "active": 1, "created_at": now,
            "automation_mode": "manual", **extra,
        })
    mine = home("Vivus / 3", owner, checkout_info="Leave the keys on the table.")
    foreign = home("Other workspace", other)
    client = TestClient(app)
    assert login_as(client, "guide-owner", url="/login?lang=en", follow_redirects=False).status_code == 303
    yield {"home": mine, "foreign": foreign, "client": client}


def _cards(apt_id):
    return {r["kind"]: r for r in guest_guide.items(apt_id)}


def test_guide_page_lists_default_cards_in_topics(ws):
    response = ws["client"].get(f"/apartments/{ws['home']}/guide")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body = response.text
    for text in ("Guest guide", "Heating and hot water", "Hot water", "Must-have", "Check this"):
        assert text in body
    assert "Guests cannot see the guide yet" in body
    assert "guest_guide." not in body  # every key has copy
    assert len(_cards(ws["home"])) == len(guest_guide.DEFAULT_KINDS)


def test_foreign_property_is_not_found(ws):
    client = ws["client"]
    assert client.get(f"/apartments/{ws['foreign']}/guide").status_code == 404
    response = client.post(f"/apartments/{ws['foreign']}/guide/cards", data={"topic": "kitchen", "title": "Hob"})
    assert response.status_code == 404
    assert guest_guide.items(ws["foreign"]) == []


def test_card_from_another_property_is_not_found(ws):
    client = ws["client"]
    client.get(f"/apartments/{ws['home']}/guide")
    guest_guide.ensure_defaults(db.query_one("SELECT * FROM apartment WHERE id = ?", (ws["foreign"],)))
    foreign_wifi = _cards(ws["foreign"])["wifi"]["id"]
    assert client.get(f"/apartments/{ws['home']}/guide/{foreign_wifi}").status_code == 404
    response = client.post(f"/apartments/{ws['home']}/guide/{foreign_wifi}", data={"steps": "x"})
    assert response.status_code == 404
    assert _cards(ws["foreign"])["wifi"]["steps"] == ""


def test_save_and_next_walks_to_the_next_open_card(ws):
    client = ws["client"]
    client.get(f"/apartments/{ws['home']}/guide")
    cards = _cards(ws["home"])
    response = client.post(
        f"/apartments/{ws['home']}/guide/{cards['checkin']['id']}",
        data={"location": "Main door, 2nd floor", "steps": "Ring 3\nTake the lift", "watch_out": "",
              "video_url": "", "visibility": "everyone", "then": "next"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].startswith(f"/apartments/{ws['home']}/guide/{cards['keys']['id']}")
    assert _cards(ws["home"])["checkin"]["state"] == "done"


def test_plain_save_returns_to_the_list(ws):
    client = ws["client"]
    client.get(f"/apartments/{ws['home']}/guide")
    wifi = _cards(ws["home"])["wifi"]
    response = client.post(
        f"/apartments/{ws['home']}/guide/{wifi['id']}",
        data={"steps": "Network Vivus", "visibility": "booked"}, follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].startswith(f"/apartments/{ws['home']}/guide?msg=")
    assert _cards(ws["home"])["wifi"]["visibility"] == "booked"


def test_bad_input_re_renders_with_the_error(ws):
    client = ws["client"]
    client.get(f"/apartments/{ws['home']}/guide")
    wifi = _cards(ws["home"])["wifi"]
    response = client.post(
        f"/apartments/{ws['home']}/guide/{wifi['id']}",
        data={"steps": "Network Vivus", "video_url": "http://example.test/v", "visibility": "everyone"},
    )
    assert response.status_code == 422
    assert "must start with https://" in response.text
    assert "Network Vivus" in response.text  # the host's text is kept
    assert _cards(ws["home"])["wifi"]["state"] == "missing"


def test_old_checkout_text_shows_as_a_draft(ws):
    client = ws["client"]
    client.get(f"/apartments/{ws['home']}/guide")
    checkout = _cards(ws["home"])["checkout"]
    page = client.get(f"/apartments/{ws['home']}/guide/{checkout['id']}").text
    assert "This card was filled in for you" in page
    assert "Leave the keys on the table." in page


def test_skip_and_bring_back(ws):
    client = ws["client"]
    client.get(f"/apartments/{ws['home']}/guide")
    trash = _cards(ws["home"])["trash"]
    client.post(f"/apartments/{ws['home']}/guide/{trash['id']}/skip", data={"skip": "1"})
    assert _cards(ws["home"])["trash"]["state"] == "skipped"
    client.post(f"/apartments/{ws['home']}/guide/{trash['id']}/skip", data={"skip": "0"})
    assert _cards(ws["home"])["trash"]["state"] == "missing"


def test_custom_card_add_and_delete(ws):
    client = ws["client"]
    response = client.post(
        f"/apartments/{ws['home']}/guide/cards", data={"topic": "kitchen", "title": "Induction hob"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    custom = [r for r in guest_guide.items(ws["home"]) if r["kind"] == "custom"]
    assert len(custom) == 1 and custom[0]["title"] == "Induction hob"
    assert response.headers["location"].startswith(f"/apartments/{ws['home']}/guide/{custom[0]['id']}")
    assert "Delete card" in client.get(f"/apartments/{ws['home']}/guide/{custom[0]['id']}").text
    client.post(f"/apartments/{ws['home']}/guide/{custom[0]['id']}/delete")
    assert [r for r in guest_guide.items(ws["home"]) if r["kind"] == "custom"] == []
    wifi = _cards(ws["home"])["wifi"]
    assert client.post(f"/apartments/{ws['home']}/guide/{wifi['id']}/delete").status_code == 404


def test_czech_page(ws):
    client = ws["client"]
    client.cookies.set("ubyhost_lang", "cs")
    body = client.get(f"/apartments/{ws['home']}/guide?lang=cs").text
    assert "Průvodce pro hosty" in body
    assert "Topení a teplá voda" in body


def test_property_page_links_to_the_guide(ws):
    body = ws["client"].get(f"/apartments/{ws['home']}").text
    assert f'href="/apartments/{ws["home"]}/guide"' in body
```

Command: `cd App && .venv/bin/python -m pytest tests/test_guest_guide_pages.py tests/test_guest_guide.py -q --tb=short -x 2>&1 | tail -30`. Expected: 20 passed.

## 5. Do not touch

`App/app/guest_guide.py`, the migrations, `App/app/static/`, the other property templates (`_property_*.html`), CSS. No new class outside the catalog, no new dependency. Hard rules 3 and 6 of AGENTS.md apply.

## 6. Commands

From `App/`:

- `.venv/bin/python -m pytest tests/test_guest_guide_pages.py tests/test_guest_guide.py -q --tb=short 2>&1 | tail -30`. Expected: 20 passed.
- `.venv/bin/python -m pytest tests/test_*_i18n.py tests/test_no_em_dashes.py tests/test_copy_cleanup.py tests/test_flash_literals.py tests/test_design_*.py -q --tb=short 2>&1 | tail -30`. Expected: 0 failed.
- `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_design_guardrails_browser.py -q --tb=short -k every_host_page 2>&1 | tail -30`. Expected: 1 passed. If Chromium is missing on your machine, say so in the report; CI runs it.

From the repo root:

- `python3 scripts/design_lint.py 2>&1 | tail -30`. Expected: `design lint: OK`.
- `python3 scripts/context_lint.py 2>&1 | tail -30`. Expected: `context lint: OK`.

## 7. Acceptance

- [ ] `git diff --stat main` lists only the nine files of §3 (plus the report).
- [ ] 20 guide tests pass; the copy and design rows pass; the layout guard passes (or the report says Chromium was missing).
- [ ] Both lints OK.

## 8. Stop and ask

Stop, and write the report, if:

- 0291 is not merged (step 1);
- an anchor line in steps 5 to 9 is not found exactly once;
- a test fails twice;
- the design lint names a class (do not add it to the catalog);
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a file outside §3 needs a change;
- you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0292-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `App/app/routes/guest_guide.py`: every route must call `_home` before touching data (ownership). The tests cover a foreign property and a foreign card.
- Copy: read the Czech strings once on a phone (orchestrator checked 390 px screenshots in en and cs before writing this brief).

## Owner steps

1. Review and merge the PR once CI is green.
2. After the next deploy, open a property, tap "Guest guide", and fill one card with "Save and next card". Guests still see nothing until 0294.

