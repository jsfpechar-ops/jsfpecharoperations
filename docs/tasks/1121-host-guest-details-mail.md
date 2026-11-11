# 1121: Host mail with the guest details, and no host copy on the receipt

Status: todo
Depends on: 1120 | Base commit: 169ee203 (start from `main` once 1120 is merged) | Branch: task/1121-host-guest-details-mail
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

When everyone on a stay has registered, the host gets their own mail (`guest_details_host`) with each guest's name, nationality and police-filing state. When `guest_mail_pref.full_details(owner)` is True, the mail also shows date of birth, home address, document type and the document number as `•••• 1234`. The guest list is rendered at send time from the database, so the stored outbox row holds only the stay id. The guest receipt stops copying the host (Reply-To stays), because the host now has this mail.

## 2. Context

Spec: `docs/plans/guest-details-mail.md` ("Host mail", "Stored bodies", "Never in any mail"). Rules that apply:

- SQL only through `App/app/db.py` helpers (`db.query`, `db.query_one`, `db.execute`, `db.insert`), Postgres-portable.
- Never a full document or visa number, a signature or an ID photo in any mail. The code below never selects `visa_number*` or `signature_png*`.
- Secrets in mail bodies use the marker pattern: the stored body holds a marker, and the value is filled in at send time. Excerpt, `App/app/mail.py`:

```python
CLAIM_SECRET_MARKER = "{{claim_secret}}"
CLAIM_SECRET_KEY = "claim_secret_enc"
DOOR_CODE_MARKER = "{{door_code}}"
DOOR_CODE_KEY = "door_code_enc"
```

```python
def delivery_body(payload: Dict[str, Any]) -> str:
    ...
    return _with_door_code(_with_secret(stored_body(payload), payload), payload)
```

`_send_ses` and `_send_console` both call `delivery_body` / `delivery_html`. The console log and the outbox keep only `stored_body` (the marker form).

- Decryption: `db.query` decrypts any `*_enc` column it selected and returns it under the plain name (`App/app/db.py`, `_hydrate`). So `SELECT doc_number, doc_number_enc ...` gives `row["doc_number"]` as plain text, in memory only.
- How the host is copied today, `App/app/claim.py` `maybe_notify_completion`:

```python
    outbox_id = mail.enqueue(
        kind="completion",
        idempotency_key=f"completion:{reservation['id']}:{progress['filled']}",
        to_email=claim["email"],
        # The host is copied on the receipt as well as being the reply address,
        # so the guest's own record of the stay reaches them either way.
        cc_email=payload.get("reply_to", ""),
```

`payload["reply_to"]` comes from `mail_notify.guest_payload`, which reads `_entity_contact_email(apartment["legal_entity_id"])`, which is `legal_entity.contact_email`. Removing `cc_email` keeps Reply-To: `_send_ses` reads `payload.get("reply_to")` into `ReplyToAddresses`, independent of `cc_email`. The new host mail goes to the same `_entity_contact_email` address.

- Once per stay: `maybe_notify_completion` returns at once when `claim["completion_notified_at"]` is set, so the receipt goes once per stay. The host mail is queued in the same place with the matching key `guest_details_host:{reservation_id}:{filled}`, so it goes exactly as often as the receipt. Note: the plan says "one per submitted form". In this code the receipt is one per completed stay, so the host mail is one per completed stay too.
- 1120 adds `App/app/guest_mail_pref.py` with `def full_details(owner_user_id: int) -> bool`. Call only that function.
- Host copy: `mail_notify._text(lang, key)` reads `host_i18n`. `tests/test_host_i18n.py` requires English and Czech to have the same keys. Vietnamese falls back to English (`host_i18n.lookup`), so it gets no keys here. Host mail language is `mail_notify.HOST_MAIL_LANGUAGE` (`"en"`).
- `tests/test_claim_mail.py::test_the_registered_mail_kinds_are_the_ones_the_app_can_send` pins `mail.KINDS`, so it changes in Step 13. `test_every_mail_kind_is_classified_as_guest_or_host` needs the kind in `HOST_KINDS` (Step 3). `test_no_registered_mail_kind_is_dead` needs the literal `"guest_details_host"` outside mail.py; Step 8 supplies it.
- The receipt's "See your stay page (host only)" link was there only for the copied host. Step 12 stops passing `host_url` from claim.py. The builder keeps the parameter, so `tests/test_guest_mail.py` and `tests/test_completion_fee_mail_1077.py`, which call the builder directly, still pass.

**Context-rollout upload (orchestrator):** put files **flat** in the rollout bundle folder under docs/plans (no subfolder). MANIFEST and place_files script at that root.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/mail.py | edit | new kind; `GUEST_DETAILS_MARKER`/`KEY`; `_with_guest_details`; both delivery functions call it |
| App/app/mail_notify.py | edit | `mask_document_number`, `build_host_guest_details`, `render_guest_details`, `host_guest_details` |
| App/app/host_i18n.py | edit | `_GUEST_DETAILS_HOST_STRINGS` (en, cs) |
| App/app/claim.py | edit | drop the receipt cc; queue the host mail; drop `host_url` |
| App/tests/test_claim_mail.py | edit | add the kind to the pinned set |
| App/tests/test_host_guest_details_mail.py | create | new focused tests |
| docs/tasks/1121-report.md | create | report |

No other file may change.

## 4. Steps

**Step 1.** Branch and check that 1120 has landed.

```bash
cd /home/user/jsfpecharoperations && git fetch origin main 2>&1 | tail -3 && git switch -c task/1121-host-guest-details-mail origin/main 2>&1 | tail -3 && grep -n 'def full_details' App/app/guest_mail_pref.py | head -3
```
Expected: one line `def full_details(owner_user_id: int) -> bool:`. If the file is missing, STOP (1120 not merged).

**Step 2.** `App/app/mail.py`, in `KINDS`. Find:

```python
    "completion_update",
    "submission_problem",
```
Replace with:
```python
    "completion_update",
    "guest_details_host",
    "submission_problem",
```
Command: `grep -n '"guest_details_host"' App/app/mail.py | head -5`. Expected: 1 line.

**Step 3.** `App/app/mail.py`, `HOST_KINDS`. Find:

```python
HOST_KINDS = (
    "reminder_host",
```
Replace with:
```python
HOST_KINDS = (
    "reminder_host",
    # 1121: who registered, to the host; the guest list is rendered at send time.
    "guest_details_host",
```
Command: `grep -n '"guest_details_host"' App/app/mail.py | head -5`. Expected: 2 lines.

**Step 4.** `App/app/mail.py`. Find:

```python
DOOR_CODE_MARKER = "{{door_code}}"
DOOR_CODE_KEY = "door_code_enc"
```
Replace with:
```python
DOOR_CODE_MARKER = "{{door_code}}"
DOOR_CODE_KEY = "door_code_enc"
# 1121: a host mail's guest list. The stored body holds the marker and the
# payload holds only the stay id; names, birth dates, addresses and the masked
# document number are read from the database when the mail is sent.
GUEST_DETAILS_MARKER = "{{guest_details}}"
GUEST_DETAILS_KEY = "guest_details_reservation_id"
```
Command: `grep -n 'GUEST_DETAILS_' App/app/mail.py | head -5`. Expected: 2 lines.

**Step 5.** `App/app/mail.py`. Find:

```python
    return value.replace(
        DOOR_CODE_MARKER, door_codes.guest_pin_display(db.decrypt_field(token))
    )


def stored_body(payload: Dict[str, Any]) -> str:
```
Replace with:
```python
    return value.replace(
        DOOR_CODE_MARKER, door_codes.guest_pin_display(db.decrypt_field(token))
    )


def _with_guest_details(value: str, payload: Dict[str, Any], *, as_html: bool) -> str:
    """Render a host mail's guest list at send time (1121).

    Raises when the marker is present and the stay id is not: a mail that
    promises a guest list and shows a marker instead must retry, not go out.
    """
    if GUEST_DETAILS_MARKER not in value:
        return value
    reservation_id = payload.get(GUEST_DETAILS_KEY)
    if not reservation_id:
        raise db.DecryptionError("outbox payload has a guest list with no stay")
    from . import mail_notify

    block = mail_notify.render_guest_details(
        int(reservation_id), lang=str(payload.get("lang") or "en"), as_html=as_html
    )
    return value.replace(GUEST_DETAILS_MARKER, block)


def stored_body(payload: Dict[str, Any]) -> str:
```
Command: `grep -n 'def _with_guest_details' App/app/mail.py | head -3`. Expected: 1 line.

**Step 6.** `App/app/mail.py`, `delivery_body`. Find:

```python
    return _with_door_code(_with_secret(stored_body(payload), payload), payload)
```
Replace with:
```python
    return _with_guest_details(
        _with_door_code(_with_secret(stored_body(payload), payload), payload),
        payload,
        as_html=False,
    )
```
Command: `grep -n 'as_html=False' App/app/mail.py | head -3`. Expected: 1 line.

**Step 7.** `App/app/mail.py`, `delivery_html`. Find:

```python
    return _with_door_code(_with_secret(stored_html(payload), payload), payload)
```
Replace with:
```python
    return _with_guest_details(
        _with_door_code(_with_secret(stored_html(payload), payload), payload),
        payload,
        as_html=True,
    )
```
Command: `cd App && .venv/bin/python -c "import app.mail" 2>&1 | tail -5`. Expected: no output.

**Step 8.** `App/app/mail_notify.py`. Find this exact line (it occurs once):

```python
def build_fee_update(
```
Replace it with the block below. The last line keeps `def build_fee_update(`.
```python
# --- 1121: who registered, to the host ----------------------------------------
#
# The stored body carries mail.GUEST_DETAILS_MARKER; render_guest_details fills
# it in at send time. Visa number, signature and photo are never selected.

GUEST_DETAILS_HOST_KIND = "guest_details_host"
_DOC_MASK = "••••"
_GUEST_STATE_KEYS = ("pending", "sent", "error", "blocked", "not_required")
_GUEST_DETAIL_COLUMNS = (
    "id, first_name, surname, nationality, submit_state, doc_type, "
    "doc_number, doc_number_enc, birth_date, birth_date_enc, "
    "res_street, res_street_enc, res_city, res_city_enc, res_country"
)


def mask_document_number(number: Optional[str]) -> str:
    """``•••• 1234``: the last four characters only.

    Spaces are ignored. A number shorter than five characters shows no
    characters at all (four of four would be the whole number). Empty stays empty.
    """
    clean = "".join(str(number or "").split())
    if not clean:
        return ""
    if len(clean) < 5:
        return _DOC_MASK
    return f"{_DOC_MASK} {clean[-4:]}"


def _guest_name(guest: Dict[str, Any], lang: str) -> str:
    parts = (str(guest.get("first_name") or "").strip(), str(guest.get("surname") or "").strip())
    return " ".join(p for p in parts if p) or _text(lang, "mail.guest_details_host.unnamed")


def _guest_detail_rows(guest: Dict[str, Any], lang: str, full: bool) -> List[Tuple[str, str]]:
    state = str(guest.get("submit_state") or "pending")
    state_text = (
        _text(lang, f"mail.guest_details_host.state.{state}")
        if state in _GUEST_STATE_KEYS
        else state
    )
    rows: List[Tuple[str, str]] = [
        (_text(lang, "mail.guest_details_host.nationality_label"),
         str(guest.get("nationality") or "").strip() or "–"),
        (_text(lang, "mail.guest_details_host.state_label"), state_text),
    ]
    if not full:
        return rows
    born = _fmt_date(guest.get("birth_date")) if guest.get("birth_date") else ""
    if born:
        rows.append((_text(lang, "mail.guest_details_host.birth_label"), born))
    address = ", ".join(
        p for p in (
            str(guest.get("res_street") or "").strip(),
            str(guest.get("res_city") or "").strip(),
            str(guest.get("res_country") or "").strip(),
        ) if p
    )
    if address:
        rows.append((_text(lang, "mail.guest_details_host.address_label"), address))
    if guest.get("doc_type"):
        rows.append((_text(lang, "mail.guest_details_host.doc_type_label"), str(guest["doc_type"])))
    masked = mask_document_number(guest.get("doc_number"))
    if masked:
        rows.append((_text(lang, "mail.guest_details_host.doc_number_label"), masked))
    return rows


def render_guest_details(reservation_id: int, *, lang: str, as_html: bool) -> str:
    """The per-guest part of the host mail, read from the database at send time."""
    from . import guest_mail_pref

    lang = host_i18n.normalise_language(lang)
    stay = db.query_one(
        "SELECT r.id, a.owner_user_id FROM reservation r "
        "JOIN apartment a ON a.id = r.apartment_id WHERE r.id = ?",
        (reservation_id,),
    )
    guests = (
        db.query(
            f"SELECT {_GUEST_DETAIL_COLUMNS} FROM guest "
            "WHERE reservation_id = ? AND archived_at IS NULL ORDER BY is_lead DESC, id",
            (reservation_id,),
        )
        if stay
        else []
    )
    if not guests:
        gone = _text(lang, "mail.guest_details_host.gone")
        return _block_paragraph(gone) if as_html else gone
    owner = stay["owner_user_id"]
    full = bool(owner) and guest_mail_pref.full_details(int(owner))
    parts: List[str] = []
    for row in guests:
        guest = dict(row)
        name = _guest_name(guest, lang)
        rows = _guest_detail_rows(guest, lang, full)
        if as_html:
            parts.append(_block_panel(name, rows))
        else:
            parts.append("\n".join([name, *(f"  {label}: {value}" for label, value in rows)]))
    return "".join(parts) if as_html else "\n\n".join(parts)


def build_host_guest_details(
    *,
    lang: str,
    property_name: str,
    dates: str,
    filled: int,
    expected: Optional[int],
    stay_url: str,
    fee_total: Optional[int] = None,
) -> Dict[str, str]:
    """The host mail around the guest list. It holds no guest field value."""
    lang = host_i18n.normalise_language(lang)
    subject = _text(lang, "mail.guest_details_host.subject", property=property_name)
    heading = _text(lang, "mail.guest_details_host.heading")
    intro = _text(lang, "mail.guest_details_host.intro", property=property_name, dates=dates)
    action = _text(lang, "mail.guest_details_host.action")
    footer = _text(lang, "mail.guest_details_host.footer")
    rows: List[Tuple[str, str]] = []
    if expected:
        rows.append((
            _text(lang, "mail.guest_details_host.count_label"),
            _text(lang, "mail.guest_details_host.count_value", filled=filled, expected=expected),
        ))
    if fee_total:
        rows.append((
            _text(lang, "mail.guest_details_host.fee_label"),
            _text(lang, "mail.guest_details_host.fee_value", total=fee_total),
        ))
    blocks = [_block_heading(heading), _block_paragraph(intro)]
    text_lines = [intro]
    if rows:
        blocks.append(_block_panel(_text(lang, "mail.guest_details_host.stay_title"), rows))
        text_lines.extend(["", *(f"{label}: {value}" for label, value in rows)])
    blocks.append(mail.GUEST_DETAILS_MARKER)
    text_lines.extend(["", mail.GUEST_DETAILS_MARKER])
    blocks.append(_block_button(stay_url, action))
    text_lines.extend(["", f"{action}: {stay_url}"])
    text = "\n".join([*text_lines, "", "--", "UbyHost", footer])
    return {
        "subject": subject,
        "text": text,
        "html": _shell(
            lang=lang,
            title=property_name,
            preheader=intro,
            blocks=blocks,
            footer_lines=["UbyHost", footer],
        ),
    }


def host_guest_details(
    apartment: Any,
    reservation: Any,
    *,
    filled: int,
    expected: Optional[int],
    fee_total: Optional[int] = None,
) -> Optional[int]:
    """Queue the host's mail of who registered. Called next to the receipt, so once per stay."""
    to_email = _entity_contact_email(apartment["legal_entity_id"] if apartment else None)
    if not to_email:
        return None
    lang = HOST_MAIL_LANGUAGE
    content = build_host_guest_details(
        lang=lang,
        property_name=property_label(apartment, lang),
        dates=validation.fmt_date_range(reservation["date_from"], reservation["date_to"]),
        filled=filled,
        expected=expected,
        stay_url=_app(f"/reservations/{reservation['id']}"),
        fee_total=fee_total,
    )
    return mail.enqueue(
        kind=GUEST_DETAILS_HOST_KIND,
        idempotency_key=f"{GUEST_DETAILS_HOST_KIND}:{reservation['id']}:{filled}",
        to_email=to_email,
        subject=content["subject"],
        payload={
            "text": content["text"],
            "html": content["html"],
            "lang": lang,
            mail.GUEST_DETAILS_KEY: int(reservation["id"]),
        },
        reservation_id=reservation["id"],
        apartment_id=apartment["id"],
        owner_user_id=apartment["owner_user_id"],
    )


def build_fee_update(
```
Command: `cd App && .venv/bin/python -c "import app.mail_notify as m; print(m.mask_document_number('AB1234567'), m.mask_document_number('1234'))" 2>&1 | tail -5`. Expected: `•••• 4567 ••••`.

**Step 9.** `App/app/host_i18n.py`. Find this exact line (it occurs once):

```python
def normalise_language(value: str | None) -> str:
```
Replace it with:
```python
# 1121: the host's mail of who registered (mail_notify.build_host_guest_details).
_GUEST_DETAILS_HOST_STRINGS = {
    "en": {
        "notification.mail_kind.guest_details_host": "guest details to the host",
        "mail.guest_details_host.subject": "%(property)s: guests registered",
        "mail.guest_details_host.heading": "Your guests have registered",
        "mail.guest_details_host.intro": "Everyone on the stay at %(property)s, %(dates)s, has filled in the form.",
        "mail.guest_details_host.stay_title": "Stay",
        "mail.guest_details_host.count_label": "Guests",
        "mail.guest_details_host.count_value": "%(filled)s of %(expected)s registered",
        "mail.guest_details_host.fee_label": "Stay fee",
        "mail.guest_details_host.fee_value": "%(total)s CZK",
        "mail.guest_details_host.nationality_label": "Nationality",
        "mail.guest_details_host.state_label": "Police filing",
        "mail.guest_details_host.state.pending": "Not filed yet",
        "mail.guest_details_host.state.sent": "Filed",
        "mail.guest_details_host.state.error": "Filing failed",
        "mail.guest_details_host.state.blocked": "Refused by the register",
        "mail.guest_details_host.state.not_required": "Not required",
        "mail.guest_details_host.birth_label": "Date of birth",
        "mail.guest_details_host.address_label": "Home address",
        "mail.guest_details_host.doc_type_label": "Document type",
        "mail.guest_details_host.doc_number_label": "Document number",
        "mail.guest_details_host.unnamed": "Guest without a name",
        "mail.guest_details_host.gone": "The guest list is no longer available.",
        "mail.guest_details_host.action": "Open the stay",
        "mail.guest_details_host.footer": "You are receiving this because a guest finished the check-in form for your property.",
    },
    "cs": {
        "notification.mail_kind.guest_details_host": "údaje o hostech pro ubytovatele",
        "mail.guest_details_host.subject": "%(property)s: hosté jsou zaregistrovaní",
        "mail.guest_details_host.heading": "Vaši hosté se zaregistrovali",
        "mail.guest_details_host.intro": "Všichni hosté pobytu v %(property)s, %(dates)s, vyplnili formulář.",
        "mail.guest_details_host.stay_title": "Pobyt",
        "mail.guest_details_host.count_label": "Hosté",
        "mail.guest_details_host.count_value": "zaregistrováno %(filled)s z %(expected)s",
        "mail.guest_details_host.fee_label": "Poplatek z pobytu",
        "mail.guest_details_host.fee_value": "%(total)s Kč",
        "mail.guest_details_host.nationality_label": "Státní občanství",
        "mail.guest_details_host.state_label": "Hlášení cizinecké policii",
        "mail.guest_details_host.state.pending": "Zatím neodesláno",
        "mail.guest_details_host.state.sent": "Odesláno",
        "mail.guest_details_host.state.error": "Odeslání selhalo",
        "mail.guest_details_host.state.blocked": "Odmítnuto registrem",
        "mail.guest_details_host.state.not_required": "Není potřeba",
        "mail.guest_details_host.birth_label": "Datum narození",
        "mail.guest_details_host.address_label": "Adresa bydliště",
        "mail.guest_details_host.doc_type_label": "Druh dokladu",
        "mail.guest_details_host.doc_number_label": "Číslo dokladu",
        "mail.guest_details_host.unnamed": "Host bez jména",
        "mail.guest_details_host.gone": "Seznam hostů už není k dispozici.",
        "mail.guest_details_host.action": "Otevřít pobyt",
        "mail.guest_details_host.footer": "Tento e-mail dostáváte, protože host dokončil registrační formulář pro vaše ubytování.",
    },
}
for _lang, _strings in _GUEST_DETAILS_HOST_STRINGS.items():
    STRINGS[_lang].update(_strings)


def normalise_language(value: str | None) -> str:
```
Command: `cd App && .venv/bin/python -c "from app import host_i18n as h; print(h.translate('cs','mail.guest_details_host.action'))" 2>&1 | tail -5`. Expected: `Otevřít pobyt`.

**Step 10.** `App/app/claim.py`, `maybe_notify_completion`. Find:

```python
        to_email=claim["email"],
        # The host is copied on the receipt as well as being the reply address,
        # so the guest's own record of the stay reaches them either way.
        cc_email=payload.get("reply_to", ""),
```
Replace with:
```python
        to_email=claim["email"],
        # 1121: the host has their own mail (mail_notify.host_guest_details),
        # so the receipt is not copied to them. payload["reply_to"] still sends
        # the guest's answer to the host.
```
Command: `grep -n 'cc_email' App/app/claim.py | head -5`. Expected: no output.

**Step 11.** `App/app/claim.py`, same function. Find:

```python
        owner_user_id=apartment["owner_user_id"],
    )
    db.execute(
        "UPDATE reservation_claim SET completion_notified_at = ?, updated_at = ? "
```
Replace with:
```python
        owner_user_id=apartment["owner_user_id"],
    )
    try:
        fee_now = _completion_fee(apartment, reservation)
        mail_notify.host_guest_details(
            apartment,
            reservation,
            filled=progress["filled"],
            expected=expected,
            fee_total=fee_now["total"] if fee_now else None,
        )
    except Exception:  # the host mail must never cost the guest their receipt
        log.exception("host guest details not queued reservation_id=%s", reservation["id"])
    db.execute(
        "UPDATE reservation_claim SET completion_notified_at = ?, updated_at = ? "
```
Command: `grep -n 'host_guest_details' App/app/claim.py | head -3`. Expected: 1 line.

**Step 12.** `App/app/claim.py`, `_guest_mail_content`. Delete this exact line (it occurs once):

```python
                host_url=f"{config.app_base_url()}/reservations/{reservation['id']}",
```
Command: `grep -n 'host_url' App/app/claim.py | head -3`. Expected: no output.

**Step 13.** `App/tests/test_claim_mail.py`. Find:

```python
        # 1078: the changed stay-fee total, after the completion mail.
        "completion_update",
```
Replace with:
```python
        # 1078: the changed stay-fee total, after the completion mail.
        "completion_update",
        # 1121: who registered, to the host.
        "guest_details_host",
```
Command: `grep -n '"guest_details_host"' App/tests/test_claim_mail.py | head -3`. Expected: 1 line.

**Step 14.** Create `App/tests/test_host_guest_details_mail.py` with exactly:

```python
"""Host guest-details mail (task 1121).

The host gets their own mail of who registered. The guest list is rendered at
send time, so the outbox row holds the stay id and no guest value. The document
number shows its last four characters only. The guest receipt is no longer
copied to the host. All guest data here is made up.
"""
from __future__ import annotations

import html
import json

import pytest

from app import claim, config, db, door_codes, guest_mail_pref, mail, mail_notify, validation

PREFIX = "gdh1121-"
HOST = "host@gdh.test"
LEAD = "lead@gdh.test"
MASK = "••••"
_counter = 0


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    db.init_db()
    _purge()
    monkeypatch.setattr(config, "MAIL_BACKEND", "console")
    monkeypatch.setattr(mail, "mail_enabled", lambda: True)
    monkeypatch.setattr(mail, "drain", lambda limit=8: {})
    yield
    _purge()


def _purge():
    for owner in db.query("SELECT id FROM user_account WHERE username LIKE ?", (PREFIX + "%",)):
        oid = owner["id"]
        for apt in db.query("SELECT id FROM apartment WHERE owner_user_id = ?", (oid,)):
            for stay in db.query("SELECT id FROM reservation WHERE apartment_id = ?", (apt["id"],)):
                db.execute("DELETE FROM guest WHERE reservation_id = ?", (stay["id"],))
                db.execute("DELETE FROM reservation_claim WHERE reservation_id = ?", (stay["id"],))
            db.execute("DELETE FROM alert WHERE apartment_id = ?", (apt["id"],))
            db.execute("DELETE FROM reservation WHERE apartment_id = ?", (apt["id"],))
        db.execute("DELETE FROM email_outbox WHERE owner_user_id = ?", (oid,))
        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (oid,))
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (oid,))
        db.execute("DELETE FROM user_account WHERE id = ?", (oid,))


def _seed() -> dict:
    """A claimed stay with two made-up guests typed in through the guest form."""
    global _counter
    _counter += 1
    now = db.utcnow()
    owner = db.insert("user_account", {
        "username": f"{PREFIX}{_counter}", "display_name": "Host",
        "password_hash": "x", "role": "host", "created_at": now,
    })
    entity = db.insert("legal_entity", {
        "name": "Test Host s.r.o.", "seat": "Praha", "created_at": now,
        "owner_user_id": owner, "contact_email": HOST,
    })
    apartment = db.insert("apartment", {
        "legal_entity_id": entity, "owner_user_id": owner, "internal_name": "Test Flat",
        "permalink_token": f"{PREFIX}tok-{_counter}", "automation_mode": "manual",
        "default_purpose": "10", "active": 1, "created_at": now,
    })
    stay = db.insert("reservation", {
        "apartment_id": apartment, "source": "manual", "uid": f"{PREFIX}stay-{_counter}",
        "date_from": "2030-03-01", "date_to": "2030-03-04", "status": "active",
        "created_at": now, "updated_at": now,
    })
    db.execute(
        "INSERT INTO reservation_claim (reservation_id, state, email, lang, token_version, "
        "claimed_at, created_at, updated_at) VALUES (?, 'claimed', ?, 'en', 0, ?, ?, ?)",
        (stay, LEAD, now, now, now),
    )
    lead = db.insert("guest", {
        "reservation_id": stay, "first_name": "Jana", "surname": "Testova",
        "birth_date": "1990-02-03", "nationality": "DEU", "doc_type": "P",
        "doc_number": "AB1234567", "visa_number": "V99887766",
        "res_street": "Testgasse 1", "res_city": "Teststadt", "res_country": "DEU",
        "is_lead": 1, "entered_by": "guest", "created_at": db.utcnow(), "updated_at": db.utcnow(),
    })
    other = db.insert("guest", {
        "reservation_id": stay, "first_name": "Petr", "surname": "Ukazka",
        "birth_date": "1985-07-08", "nationality": "AUT", "doc_type": "ID",
        "doc_number": "XY7654321", "res_street": "Musterweg 9", "res_city": "Musterort",
        "res_country": "AUT", "is_lead": 0, "entered_by": "guest",
        "created_at": db.utcnow(), "updated_at": db.utcnow(),
    })
    return {"owner": owner, "apartment": apartment, "stay": stay, "guests": (lead, other)}


def _rows(stay: int, kind: str):
    return db.query(
        "SELECT * FROM email_outbox WHERE kind = ? AND reservation_id = ? ORDER BY id",
        (kind, stay),
    )


def _queue(seed: dict):
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (seed["apartment"],))
    reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (seed["stay"],))
    return mail_notify.host_guest_details(apartment, reservation, filled=2, expected=2)


def _delivered(seed: dict):
    (row,) = _rows(seed["stay"], "guest_details_host")
    payload = json.loads(row["payload"])
    return mail.delivery_body(payload), html.unescape(mail.delivery_html(payload))


def test_mask_shows_the_last_four_only():
    assert mail_notify.mask_document_number("AB1234567") == f"{MASK} 4567"
    assert mail_notify.mask_document_number(" AB 123 4567 ") == f"{MASK} 4567"
    assert mail_notify.mask_document_number("12345") == f"{MASK} 2345"
    assert mail_notify.mask_document_number("1234") == MASK
    assert mail_notify.mask_document_number("1") == MASK
    assert mail_notify.mask_document_number("") == ""
    assert mail_notify.mask_document_number(None) == ""


def test_always_content_names_the_guests_and_nothing_more(monkeypatch):
    monkeypatch.setattr(guest_mail_pref, "full_details", lambda owner_user_id: False)
    seed = _seed()
    _queue(seed)
    text, page = _delivered(seed)
    for part in (text, page):
        assert "Jana Testova" in part
        assert "Petr Ukazka" in part
        assert "DEU" in part
        assert "Not filed yet" in part
        assert "2 of 2 registered" in part
        for absent in ("4567", "4321", "Testgasse", "Date of birth", MASK):
            assert absent not in part, absent


def test_full_details_add_birth_address_and_a_masked_document(monkeypatch):
    monkeypatch.setattr(guest_mail_pref, "full_details", lambda owner_user_id: True)
    seed = _seed()
    _queue(seed)
    text, page = _delivered(seed)
    born = validation.fmt_date("1990-02-03")
    for part in (text, page):
        assert f"{MASK} 4567" in part
        assert f"{MASK} 4321" in part
        assert born in part
        assert "Testgasse 1, Teststadt, DEU" in part
        for secret in ("AB1234567", "XY7654321", "V99887766"):
            assert secret not in part, secret


def test_the_outbox_row_holds_the_stay_id_and_no_guest_value(monkeypatch):
    monkeypatch.setattr(guest_mail_pref, "full_details", lambda owner_user_id: True)
    seed = _seed()
    _queue(seed)
    (row,) = _rows(seed["stay"], "guest_details_host")
    stored = " ".join([row["subject"] or "", row["payload"] or ""])
    for value in ("Jana", "Testova", "Petr", "Ukazka", "4567", "4321", "AB1234567",
                  "1990", "1985", "Testgasse", "Teststadt", "Musterweg"):
        assert value not in stored, value
    payload = json.loads(row["payload"])
    assert payload[mail.GUEST_DETAILS_KEY] == seed["stay"]
    assert mail.GUEST_DETAILS_MARKER in payload["text"]
    assert mail.GUEST_DETAILS_MARKER in payload["html"]
    assert row["to_email"] == HOST
    assert row["cc_email"] is None


def test_a_second_queue_for_the_same_count_is_the_same_mail():
    seed = _seed()
    assert _queue(seed) == _queue(seed)
    assert len(_rows(seed["stay"], "guest_details_host")) == 1


def test_the_receipt_is_not_copied_to_the_host_and_the_host_gets_their_own(monkeypatch):
    monkeypatch.setattr(guest_mail_pref, "full_details", lambda owner_user_id: False)
    monkeypatch.setattr(
        claim.reporting, "reservation_progress",
        lambda *a, **k: {"expected": 2, "filled": 2, "incomplete": []},
    )
    monkeypatch.setattr(door_codes, "completion_door_code", lambda *a, **k: ("none", None, None))
    seed = _seed()
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (seed["apartment"],))
    for _ in range(2):
        reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (seed["stay"],))
        claim.maybe_notify_completion(reservation, apartment)
    (receipt,) = _rows(seed["stay"], "completion")
    assert receipt["to_email"] == LEAD
    assert receipt["cc_email"] is None
    payload = json.loads(receipt["payload"])
    assert payload["reply_to"] == HOST
    assert "(host only)" not in payload["text"]
    (host_mail,) = _rows(seed["stay"], "guest_details_host")
    assert host_mail["to_email"] == HOST
```
Command:
```bash
cd /home/user/jsfpecharoperations/App && .venv/bin/python -m pytest tests/test_host_guest_details_mail.py -q --tb=short -x 2>&1 | tail -30
```
Expected: `6 passed`.

**Step 15.** Run the test-map rows for mail and claim, plus the host catalogue test:
```bash
cd /home/user/jsfpecharoperations/App && .venv/bin/python -m pytest tests/test_ses_mail.py tests/test_mail_*.py tests/test_*_mail.py tests/test_lifecycle_mail.py tests/test_notification_copy.py tests/test_claim_*.py tests/test_host_i18n.py tests/test_completion_fee_mail_1077.py -q --tb=short -x 2>&1 | tail -30
cd /home/user/jsfpecharoperations && python3 scripts/context_lint.py 2>&1 | tail -30
```
Expected: all passed, 0 failed; lint clean.

**Step 16.** Commit, push the branch, open a **draft** PR (as executor.md says), write the report (§9).

## 5. Do not touch

- `App/app/guest_mail_pref.py` (1120 owns it; only call `full_details`).
- `App/app/fee_update.py`: `completion_update` still copies the host. That is out of scope; name it under Questions in the report.
- `build_completion` in mail_notify.py (1122 owns it), migrations, `App/app/retention.py`, legal and privacy copy (1123).
- Hard rules: SQL only through `App/app/db.py` helpers, Postgres-portable; no new dependency; no schema change in this brief; never a full document or visa number, a signature or an ID photo in a mail; public repo, no real guest data in tests (all test data is made up); copy rule: no sentence the button already says.

## 6. Commands

Each one is in the step that uses it. Tests: Step 14 (new file, `6 passed`) and Step 15 (mail and claim rows of the test-map, plus `test_host_i18n.py` and `test_completion_fee_mail_1077.py` because their guarded code changed). Never the full suite.

## 7. Acceptance

- [ ] `grep -n 'cc_email' App/app/claim.py` prints nothing.
- [ ] `grep -c 'guest_details_host' App/app/mail.py` prints 2.
- [ ] `tests/test_host_guest_details_mail.py`: 6 passed.
- [ ] Step 15 command: 0 failed.
- [ ] `git diff --stat origin/main` lists only the §3 files.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change (for example, a test that lists host mail kinds or a docs file that a test checks);
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1121-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `App/app/mail.py`: `delivery_body` / `delivery_html` now render the guest list. Check that nothing writes the delivered form to a table (only `stored_body` is logged).
- `App/app/mail_notify.py`: `render_guest_details` must select no `visa_number*` or `signature_png*`, and must call `full_details` at send time.
- `App/app/claim.py`: the host mail sits inside `try/except`, so it can never block the receipt or `completion_notified_at`.

## Owner steps

1. Open the draft PR for `task/1121-host-guest-details-mail` on GitHub.
2. When CI is green and the review is done, click "Ready for review".
3. Merge it with `scripts/merge-pr-on-green.sh <PR number>` from the repo root.
4. Full details stay off for every workspace until 1123b's DPA version bump is live, so this can ship before the lawyer answers.
