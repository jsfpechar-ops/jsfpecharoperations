# 0343: Photos on guest guide cards

Status: review
Depends on: 0292 merged | Base commit: after 0292 | Branch: task/0293-guide-photos
Executor: Haiku 5.5 (critical: Fable reviews the diff before merge) | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Let the host add up to six photos to a guide card ("this is the boiler, press this button"), see them on the card, and delete them. Photos are cleaned (no EXIF, re-encoded JPEG), shrunk to 1600 px, stored under `DATA_DIR/guide_photos`, and served only to the signed-in owner for now. Guests get them in 0344 ([plan](../plans/guest-guide.md)).

## 2. Context

- `guide_photo` already exists (migration 0013, brief 0341): `id, item_id (FK cascade), file_name UNIQUE, sort_order, created_at`.
- `passport_photos.reencode_image(content)` decodes an image with a pixel cap (decompression-bomb safe), applies EXIF orientation and returns a fresh JPEG with no metadata. It raises `ValueError` for anything it cannot decode. Reuse it; do not write a second decoder. Pillow is already a dependency (`qrcode[pil]`).
- Guide photos are host-written and meant for guests, so they are not encrypted at rest (unlike passport photos). They must still never carry location data, which `reencode_image` guarantees.
- A cascade from a deleted card or property removes rows, not files. `purge_orphans` (run by the existing nightly photo sweep in `scheduler.py`) removes files no row names, skipping files younger than one hour so an upload in progress is safe.
- Feature classes `guide-photos` and `guide-photo` are new in the catalog, styled in `workflow.css` with tokens only. Changing `workflow.css` means a new `?v=` key in `base.html` and a refreshed `tests/static_versions.json` (test-map row "Static files").
- The photo upload form sits above the text form, so a host who takes the photo first loses no typed text.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/guide_photos.py` | create | Add, list, get, delete, purge orphans |
| `App/tests/test_guide_photos.py` | create | Tests |
| `App/app/routes/guest_guide.py` | replace | Adds upload, serve, delete; custom-card delete also removes photo files |
| `App/app/templates/guest_guide_card.html` | replace | Adds the Photos section |
| `App/app/host_i18n.py` | edit | Add `_GUIDE_PHOTO_STRINGS` |
| `App/app/scheduler.py` | edit | Import and call `guide_photos.purge_orphans()` |
| `App/app/static/workflow.css` | edit | Three rules at the end |
| `App/app/templates/base.html` | edit | New `workflow.css?v=` key |
| `App/tests/static_versions.json` | regenerate | `tests/test_static_versions.py --write` |
| `docs/design/catalog.json` | edit | Two classes and their notes |

No other file may change.

## 4. Steps

1. Check 0342 is in: `ls App/app/routes/guest_guide.py App/app/templates/guest_guide_card.html 2>&1 | tail -30`. If either is missing, STOP (§8).

2. Create `App/app/guide_photos.py`:

```python
"""0343: photos on guest guide cards ("this is the boiler, press this button").

A photo is decoded and saved again as a fresh JPEG (``passport_photos.reencode_image``),
so no EXIF location or camera data survives, then shrunk to ``MAX_SIDE``. Files
live in ``DATA_DIR/guide_photos`` under a random name; the ``guide_photo`` row
ties a file to its card. Guides are host-written and meant for guests, so the
files are not encrypted. ``purge_orphans`` removes files whose row is gone
(a deleted card or property cascades the rows, not the files).
"""
from __future__ import annotations

import io
import os
import secrets
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image

from . import config, db, passport_photos
from .guest_guide import GuideError

PHOTOS_DIR = config.DATA_DIR / "guide_photos"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_PER_ITEM = 6
MAX_SIDE = 1600
JPEG_QUALITY = 82
ALLOWED_TYPES = ("image/jpeg", "image/jpg", "image/png", "image/webp")


def _dir() -> Path:
    PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
    return PHOTOS_DIR


def _shrink(content: bytes) -> bytes:
    with Image.open(io.BytesIO(content)) as image:
        image.thumbnail((MAX_SIDE, MAX_SIDE))
        out = io.BytesIO()
        image.save(out, format="JPEG", quality=JPEG_QUALITY)
    return out.getvalue()


def photos(apartment_id: int, item_id: int) -> List[Dict[str, Any]]:
    """The card's photos in upload order; empty for a card of another property."""
    rows = db.query(
        "SELECT p.* FROM guide_photo p JOIN guide_item i ON i.id = p.item_id "
        "WHERE p.item_id = ? AND i.apartment_id = ? ORDER BY p.sort_order, p.id",
        (item_id, apartment_id),
    )
    return [dict(row) for row in rows]


def get(apartment_id: int, item_id: int, photo_id: int) -> Optional[Dict[str, Any]]:
    row = db.query_one(
        "SELECT p.* FROM guide_photo p JOIN guide_item i ON i.id = p.item_id "
        "WHERE p.id = ? AND p.item_id = ? AND i.apartment_id = ?",
        (photo_id, item_id, apartment_id),
    )
    return dict(row) if row else None


def path_for(photo: Dict[str, Any]) -> Path:
    return PHOTOS_DIR / photo["file_name"]


def add(apartment_id: int, item_id: int, content: bytes, content_type: str) -> int:
    """Store one photo on the card; raises GuideError with a flash key."""
    if not db.query_one(
        "SELECT id FROM guide_item WHERE id = ? AND apartment_id = ?", (item_id, apartment_id)
    ):
        raise GuideError("flash.error.guide_no_such_item")
    ctype = (content_type or "").split(";", 1)[0].strip().lower()
    if ctype not in ALLOWED_TYPES or len(content) < 64:
        raise GuideError("flash.error.guide_photo_type")
    if len(content) > MAX_UPLOAD_BYTES:
        raise GuideError("flash.error.guide_photo_size")
    existing = photos(apartment_id, item_id)
    if len(existing) >= MAX_PER_ITEM:
        raise GuideError("flash.error.guide_photo_limit")
    try:
        clean = _shrink(passport_photos.reencode_image(content))
    except ValueError:
        raise GuideError("flash.error.guide_photo_type") from None
    name = secrets.token_hex(16) + ".jpg"
    target = _dir() / name
    tmp = target.with_suffix(".tmp")
    tmp.write_bytes(clean)
    os.replace(tmp, target)
    order = max((p["sort_order"] for p in existing), default=0) + 1
    return db.insert(
        "guide_photo",
        {"item_id": item_id, "file_name": name, "sort_order": order, "created_at": db.utcnow()},
    )


def delete(apartment_id: int, item_id: int, photo_id: int) -> bool:
    photo = get(apartment_id, item_id, photo_id)
    if not photo:
        return False
    db.execute("DELETE FROM guide_photo WHERE id = ?", (photo_id,))
    path_for(photo).unlink(missing_ok=True)
    return True


def purge_orphans() -> int:
    """Delete stored files no ``guide_photo`` row names any more; the count removed.

    A file younger than an hour is left alone: ``add`` writes the file before
    its row, so a sweep in between must not take it.
    """
    if not PHOTOS_DIR.is_dir():
        return 0
    known = {row["file_name"] for row in db.query("SELECT file_name FROM guide_photo")}
    cutoff = time.time() - 3600
    removed = 0
    for path in PHOTOS_DIR.iterdir():
        if path.is_file() and path.name not in known and path.stat().st_mtime < cutoff:
            path.unlink(missing_ok=True)
            removed += 1
    return removed
```

3. Replace the whole content of `App/app/routes/guest_guide.py` with:

```python
"""0342: the host's guest guide pages: the card list and one card's editor.

The data and every rule about it live in ``app.guest_guide``; these routes only
check the property belongs to the host, call it, and redirect.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse

from .. import access, auth, guest_guide, guide_photos, security, templating
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


def _card(request: Request, apartment, item, values, error: str = "", status_code: int = 200):
    return _render(
        request, "guest_guide_card.html", status_code=status_code,
        apartment=apartment, item=item, values=values, error=error,
        photos=guide_photos.photos(apartment["id"], item["id"]),
        max_photos=guide_photos.MAX_PER_ITEM,
    )


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
    return _card(request, apartment, item, item)


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
        return _card(request, apartment, item, values, error=exc.key, status_code=422)
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
    item = guest_guide.get(apartment_id, item_id)
    if not item or item["kind"] != "custom":
        raise HTTPException(404)
    for photo in guide_photos.photos(apartment_id, item_id):
        guide_photos.delete(apartment_id, item_id, photo["id"])
    guest_guide.delete_custom(apartment_id, item_id)
    return back(_base(apartment_id), msg=flash(request, "flash.guest_guide.deleted"))


@router.post("/apartments/{apartment_id}/guide/{item_id}/photos")
async def guide_photo_add(request: Request, apartment_id: int, item_id: int):
    guard = auth.require_login(request)
    if guard:
        return guard
    _home(request, apartment_id)
    if not guest_guide.get(apartment_id, item_id):
        raise HTTPException(404)
    card_url = f"{_base(apartment_id)}/{item_id}"
    form = await request.form()
    upload = form.get("photo")
    if upload is None or not hasattr(upload, "read"):
        return back(card_url, err=flash(request, "flash.error.guide_photo_type"))
    content = await upload.read(guide_photos.MAX_UPLOAD_BYTES + 1)
    try:
        # Decoding and shrinking a phone photo is CPU work; keep it off the event loop.
        await run_in_threadpool(guide_photos.add, apartment_id, item_id, content, upload.content_type or "")
    except guest_guide.GuideError as exc:
        return back(card_url, err=flash(request, exc.key))
    return back(card_url, msg=flash(request, "flash.guest_guide.photo_added"))


@router.get("/apartments/{apartment_id}/guide/{item_id}/photos/{photo_id}")
def guide_photo_file(request: Request, apartment_id: int, item_id: int, photo_id: int):
    guard = auth.require_login(request)
    if guard:
        return guard
    _home(request, apartment_id)
    photo = guide_photos.get(apartment_id, item_id, photo_id)
    path = guide_photos.path_for(photo) if photo else None
    if not path or not path.is_file():
        raise HTTPException(404)
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=3600"})


@router.post("/apartments/{apartment_id}/guide/{item_id}/photos/{photo_id}/delete")
def guide_photo_delete(request: Request, apartment_id: int, item_id: int, photo_id: int):
    guard = auth.require_login(request)
    if guard:
        return guard
    _home(request, apartment_id)
    if not guide_photos.delete(apartment_id, item_id, photo_id):
        raise HTTPException(404)
    return back(f"{_base(apartment_id)}/{item_id}", msg=flash(request, "flash.guest_guide.photo_deleted"))
```

4. Replace the whole content of `App/app/templates/guest_guide_card.html` with:

```html
{#- 0342: one guest guide card. "Save and next card" walks the host through
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
{% call ui_section(t('guest_guide.photos.title'), id='card-photos') %}
{% if photos %}
<ul class="guide-photos">
{% for photo in photos %}
<li class="guide-photo">
<img src="{{ base_url }}/{{ item.id }}/photos/{{ photo.id }}" alt="{{ t('guest_guide.photos.alt', n=loop.index, card=card_title) }}" loading="lazy">
<form method="post" action="{{ base_url }}/{{ item.id }}/photos/{{ photo.id }}/delete" data-confirm data-confirm-message="{{ t('guest_guide.photos.delete_confirm') }}">
<input type="hidden" name="_csrf" value="{{ csrf_token }}">
{{ ui_button(t('guest_guide.photos.delete'), 'quiet', type='submit', size='compact', icon_name='trash-2') }}
</form>
</li>
{% endfor %}
</ul>
{% endif %}
{% if photos | length < max_photos %}
<form method="post" action="{{ base_url }}/{{ item.id }}/photos" enctype="multipart/form-data">
<input type="hidden" name="_csrf" value="{{ csrf_token }}">
{{ ui_field('guide-photo', t('guest_guide.photos.add'), name='photo', type='file', help=t('guest_guide.photos.help', max=max_photos), attrs='accept="image/jpeg,image/png,image/webp" required') }}
<div class="ui-form-actions">{{ ui_button(t('guest_guide.photos.upload'), 'secondary', type='submit', icon_name='plus') }}</div>
</form>
{% else %}
<p class="ui-help">{{ t('guest_guide.photos.full', max=max_photos) }}</p>
{% endif %}
{% endcall %}

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

5. In `App/app/host_i18n.py`, find these two lines (once):

```python
for _lang, _strings in _GUEST_GUIDE_STRINGS.items():
    STRINGS[_lang].update(_strings)
```

Directly after them, insert one blank line and then:

```python
# 0343: photos on guest guide cards.
_GUIDE_PHOTO_STRINGS = {
    "en": {
        "guest_guide.photos.title": "Photos",
        "guest_guide.photos.add": "Add a photo",
        "guest_guide.photos.help": "Show the exact thing: the boiler display, the button, the key box. Up to %(max)s photos.",
        "guest_guide.photos.upload": "Upload photo",
        "guest_guide.photos.full": "This card has %(max)s photos, the most it can hold. Delete one to add another.",
        "guest_guide.photos.alt": "Photo %(n)s for %(card)s",
        "guest_guide.photos.delete": "Delete photo",
        "guest_guide.photos.delete_confirm": "Delete this photo? This cannot be undone.",
        "flash.guest_guide.photo_added": "Photo added.",
        "flash.guest_guide.photo_deleted": "Photo deleted.",
        "flash.error.guide_photo_type": "Upload a JPEG, PNG or WebP photo.",
        "flash.error.guide_photo_size": "The photo is too large. Use one under 10 MB.",
        "flash.error.guide_photo_limit": "This card already has the most photos it can hold.",
    },
    "cs": {
        "guest_guide.photos.title": "Fotky",
        "guest_guide.photos.add": "Přidat fotku",
        "guest_guide.photos.help": "Vyfoťte přesně tu věc: displej kotle, tlačítko, schránku na klíče. Nejvýš %(max)s fotek.",
        "guest_guide.photos.upload": "Nahrát fotku",
        "guest_guide.photos.full": "Karta už má %(max)s fotek, víc se nevejde. Pro další jednu smažte.",
        "guest_guide.photos.alt": "Fotka %(n)s ke kartě %(card)s",
        "guest_guide.photos.delete": "Smazat fotku",
        "guest_guide.photos.delete_confirm": "Smazat tuto fotku? Nelze to vrátit.",
        "flash.guest_guide.photo_added": "Fotka přidána.",
        "flash.guest_guide.photo_deleted": "Fotka smazána.",
        "flash.error.guide_photo_type": "Nahrajte fotku ve formátu JPEG, PNG nebo WebP.",
        "flash.error.guide_photo_size": "Fotka je příliš velká. Použijte menší než 10 MB.",
        "flash.error.guide_photo_limit": "Karta už má nejvíc fotek, kolik se vejde.",
    },
}

for _lang, _strings in _GUIDE_PHOTO_STRINGS.items():
    STRINGS[_lang].update(_strings)
```

6. In `App/app/scheduler.py`:
   - in the `from . import (` list, add `    guide_photos,` after `    filing_watchdog,`;
   - in `_job_photo_sweep`, after the three lines that call `passport_photos.purge_stale()` and log it, add:

```python
        orphans = guide_photos.purge_orphans()
        if orphans:
            log.info("guide photo sweep deleted %s orphaned file(s)", orphans)
```

7. Append to the end of `App/app/static/workflow.css` (one blank line before):

```css
/* 0343: photos on a guest guide card. */
.guide-photos { display: grid; grid-template-columns: repeat(auto-fill, minmax(9rem, 1fr)); gap: var(--space-3); margin: 0 0 var(--space-3); padding: 0; list-style: none; }
.guide-photo { display: grid; gap: var(--space-2); justify-items: start; min-width: 0; }
.guide-photo img { display: block; width: 100%; aspect-ratio: 4 / 3; object-fit: cover; border: 1px solid var(--border); border-radius: var(--radius-md); background: var(--surface); }
```

8. In `App/app/templates/base.html`, change the `workflow.css?v=` key to `20261024-0293` (if the current key is already newer than that, use `<today>-0293`). Then from `App/`: `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -30`.

9. In `docs/design/catalog.json`: append `"guide-photos"` and `"guide-photo"` to the end of `classes`, and add to `class_notes`:

```json
    "guide-photos": "0343 grid of a guest guide card's photos (a ul of guide-photo).",
    "guide-photo": "0343 one photo with its delete button under it."
```

10. Create `App/tests/test_guide_photos.py`:

```python
"""0343: photos on guest guide cards."""
from __future__ import annotations

import io
import os
import time

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import auth, config, db, guest_guide, guide_photos
from app.main import app
from tests.conftest import login_as


def _jpeg(size=(3000, 2000)) -> bytes:
    exif = Image.Exif()
    exif[0x010F] = "FictionalCam"  # Make
    out = io.BytesIO()
    Image.new("RGB", size, (120, 90, 60)).save(out, format="JPEG", exif=exif.tobytes())
    return out.getvalue()


@pytest.fixture
def ws(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "photos.sqlite3")
    monkeypatch.setattr(guide_photos, "PHOTOS_DIR", tmp_path / "guide_photos")
    monkeypatch.setattr(auth, "staging_no_login", lambda: False)
    db.init_db()
    owner = auth.create_account("photo-owner@example.test", "Photo owner", username="photo-owner", role="host")
    other = auth.create_account("photo-other@example.test", "Other owner", username="photo-other", role="host")
    now = db.utcnow()

    def home(name, user):
        apt_id = db.insert("apartment", {
            "owner_user_id": user, "internal_name": name, "active": 1, "created_at": now,
            "automation_mode": "manual",
        })
        guest_guide.ensure_defaults(db.query_one("SELECT * FROM apartment WHERE id = ?", (apt_id,)))
        return apt_id
    mine, foreign = home("Vivus / 3", owner), home("Other workspace", other)
    client = TestClient(app)
    assert login_as(client, "photo-owner", url="/login?lang=en", follow_redirects=False).status_code == 303
    heating = {r["kind"]: r for r in guest_guide.items(mine)}["heating"]["id"]
    foreign_heating = {r["kind"]: r for r in guest_guide.items(foreign)}["heating"]["id"]
    yield {"home": mine, "foreign": foreign, "item": heating, "foreign_item": foreign_heating, "client": client}


def _upload(ws, content, ctype="image/jpeg", apt=None, item=None):
    apt, item = apt or ws["home"], item or ws["item"]
    return ws["client"].post(
        f"/apartments/{apt}/guide/{item}/photos",
        files={"photo": ("boiler.jpg", content, ctype)}, follow_redirects=False,
    )


def test_upload_is_shrunk_cleaned_and_shown(ws):
    response = _upload(ws, _jpeg())
    assert response.status_code == 303 and "msg=" in response.headers["location"]
    [photo] = guide_photos.photos(ws["home"], ws["item"])
    stored = guide_photos.path_for(photo)
    with Image.open(stored) as image:
        assert max(image.size) == guide_photos.MAX_SIDE
        assert image.format == "JPEG"
        assert not image.getexif()
    page = ws["client"].get(f"/apartments/{ws['home']}/guide/{ws['item']}").text
    src = f"/apartments/{ws['home']}/guide/{ws['item']}/photos/{photo['id']}"
    assert src in page
    served = ws["client"].get(src)
    assert served.status_code == 200 and served.headers["content-type"] == "image/jpeg"


def test_not_an_image_is_refused(ws):
    response = _upload(ws, b"%PDF-1.4 " + b"x" * 100, ctype="application/pdf")
    assert "err=" in response.headers["location"]
    response = _upload(ws, b"x" * 100)  # says JPEG, is not
    assert "err=" in response.headers["location"]
    assert guide_photos.photos(ws["home"], ws["item"]) == []


def test_photo_limit(ws):
    small = _jpeg((40, 30))
    for _ in range(guide_photos.MAX_PER_ITEM):
        _upload(ws, small)
    response = _upload(ws, small)
    assert "err=" in response.headers["location"]
    assert len(guide_photos.photos(ws["home"], ws["item"])) == guide_photos.MAX_PER_ITEM
    page = ws["client"].get(f"/apartments/{ws['home']}/guide/{ws['item']}").text
    assert "Upload photo" not in page


def test_another_hosts_property_and_card_are_out_of_reach(ws):
    assert _upload(ws, _jpeg((40, 30)), apt=ws["foreign"], item=ws["foreign_item"]).status_code == 404
    assert _upload(ws, _jpeg((40, 30)), item=ws["foreign_item"]).status_code == 404
    guide_photos.add(ws["foreign"], ws["foreign_item"], _jpeg((40, 30)), "image/jpeg")
    [theirs] = guide_photos.photos(ws["foreign"], ws["foreign_item"])
    client = ws["client"]
    assert client.get(f"/apartments/{ws['home']}/guide/{ws['foreign_item']}/photos/{theirs['id']}").status_code == 404
    assert client.get(f"/apartments/{ws['home']}/guide/{ws['item']}/photos/{theirs['id']}").status_code == 404
    assert client.post(f"/apartments/{ws['home']}/guide/{ws['item']}/photos/{theirs['id']}/delete").status_code == 404
    assert guide_photos.path_for(theirs).is_file()


def test_delete_photo_and_custom_card_remove_files(ws):
    _upload(ws, _jpeg((40, 30)))
    [photo] = guide_photos.photos(ws["home"], ws["item"])
    ws["client"].post(f"/apartments/{ws['home']}/guide/{ws['item']}/photos/{photo['id']}/delete")
    assert guide_photos.photos(ws["home"], ws["item"]) == []
    assert not guide_photos.path_for(photo).exists()
    custom = guest_guide.add_custom(ws["home"], "kitchen", "Induction hob")
    _upload(ws, _jpeg((40, 30)), item=custom)
    [hob] = guide_photos.photos(ws["home"], custom)
    ws["client"].post(f"/apartments/{ws['home']}/guide/{custom}/delete")
    assert not guide_photos.path_for(hob).exists()


def test_purge_orphans_keeps_young_files_and_known_files(ws):
    _upload(ws, _jpeg((40, 30)))
    [kept] = guide_photos.photos(ws["home"], ws["item"])
    old = guide_photos.PHOTOS_DIR / "orphan-old.jpg"
    young = guide_photos.PHOTOS_DIR / "orphan-young.jpg"
    old.write_bytes(b"x")
    young.write_bytes(b"x")
    past = time.time() - 2 * 3600
    os.utime(old, (past, past))
    os.utime(guide_photos.path_for(kept), (past, past))
    assert guide_photos.purge_orphans() == 1
    assert not old.exists() and young.exists() and guide_photos.path_for(kept).exists()
```

## 5. Do not touch

`App/app/passport_photos.py`, `App/app/guest_guide.py`, migrations, `host2.css`, any guest template or guest route. No new dependency. Never log file content or names of uploaded files. Hard rules 3, 4 and 6 of AGENTS.md apply.

## 6. Commands

From `App/`:

- `.venv/bin/python -m pytest tests/test_guide_photos.py tests/test_guest_guide_pages.py tests/test_guest_guide.py -q --tb=short 2>&1 | tail -30`. Expected: 26 passed.
- `.venv/bin/python -m pytest tests/test_*_i18n.py tests/test_no_em_dashes.py tests/test_copy_cleanup.py tests/test_flash_literals.py tests/test_design_*.py tests/test_static_versions.py tests/test_wp07_cache_heartbeats.py tests/test_scheduler*.py -q --tb=short 2>&1 | tail -30`. Expected: 0 failed.
- `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_design_guardrails_browser.py -q --tb=short -k every_host_page 2>&1 | tail -30`. Expected: 1 passed (or say Chromium was missing).

From the repo root: `python3 scripts/design_lint.py 2>&1 | tail -30` and `python3 scripts/context_lint.py 2>&1 | tail -30`. Expected: both OK.

## 7. Acceptance

- [ ] Only the ten files of §3 change (plus the report).
- [ ] 26 guide tests pass; the other rows pass.
- [ ] Both lints OK.

## 8. Stop and ask

Stop, and write the report, if: 0342 is not merged; an anchor in steps 5, 6 or 8 is not found exactly once; a test fails twice; the design lint names a class; you reach 25 tool calls or about 50k tokens; a file outside §3 needs a change; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0293-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with its last 5 lines, §7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

- Upload handling: type check, 10 MB read cap (`read(MAX + 1)`), decode through `reencode_image` (pixel cap), random file name, atomic write. Read `guide_photos.add` line by line.
- Ownership: every photo query joins `guide_item` on `apartment_id`; the tests cover a foreign property, a foreign card and a photo id from another card.
- `purge_orphans` deletes files: check the one-hour guard and that it only walks `PHOTOS_DIR`.

## Owner steps

1. Review and merge once CI is green.
2. After deploy, the server's data volume holds `guide_photos/`. At up to 6 photos of about 300 KB per card, 20 cards is under 40 MB per property. Nothing to configure.

