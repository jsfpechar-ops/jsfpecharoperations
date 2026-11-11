# 1122: "What you sent" block on the guest receipt

Status: todo
Depends on: 1121 | Base commit: 169ee203 (start from `main` once 1121 is merged) | Branch: task/1122-guest-receipt-what-you-sent
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

The guest receipt (`build_completion`) gains a "What you sent" block. It lists the guests on the stay by name, and shows the masked document number (`•••• 1234`) only for guests typed in through the guest form since the claim was confirmed. Like 1121, the block is rendered at send time, so the outbox row holds only the stay id. The receipt still goes only to the verified claim address.

## 2. Context

Spec: `docs/plans/guest-details-mail.md` ("Guest receipt", "Never in any mail", "Stored bodies").

**Who "the submitter" is.** The data model cannot tell which guest row belongs to the person behind the claim address. `reservation_claim` holds `email`, `lang` and `claimed_at` but no guest id. `guest.is_lead` only marks the first guest row saved on the stay (`App/app/routes/guest.py`: `"is_lead": 1 if is_first else 0`), and that row may have been entered by the host. So the fallback rule applies:

- A guest with `entered_by = 'guest'` and `created_at >= reservation_claim.claimed_at` was typed in through this claim, so the line shows name plus masked document number.
- Any other guest (entered by the host, imported, or typed in before the current claim was confirmed) shows by name only.
- Nobody's date of birth or address is shown, because the code cannot say whose they are.

**The verified address.** `App/app/claim.py`:

```python
def maybe_notify_completion(reservation, apartment, *, force: bool = False) -> None:
    claim = _row(reservation["id"])
    if not claim or claim["state"] != CLAIMED or claim["completion_notified_at"]:
        return
```
The receipt is enqueued with `to_email=claim["email"]`. The state only becomes `CLAIMED` in `confirm()`, when the secret mailed to that address matches (`if token_hash(secret) != claim["token_hash"]: return False`). So the receipt goes only to an address that proved it receives mail. After 1121 it has no `cc_email`.

**Send-time rendering.** This brief reuses 1121's mechanism (`App/app/mail.py`): a marker in the stored body plus an id in the payload, filled in by `delivery_body` / `delivery_html`. Text as it stands **after 1121** (quoted from brief 1121, Steps 4 to 7):

```python
GUEST_DETAILS_MARKER = "{{guest_details}}"
GUEST_DETAILS_KEY = "guest_details_reservation_id"
```
```python
    return value.replace(GUEST_DETAILS_MARKER, block)


def stored_body(payload: Dict[str, Any]) -> str:
```
```python
    return _with_guest_details(
        _with_door_code(_with_secret(stored_body(payload), payload), payload),
        payload,
        as_html=False,
    )
```
1121 also added `mail_notify.mask_document_number(number)`: under 5 characters it shows `••••`, empty stays empty, otherwise `•••• ` plus the last 4. Its test seed lives in `App/tests/test_host_guest_details_mail.py` (`_env`, `_seed`, `_rows`, `LEAD`, `HOST`, `MASK`).

**Copy.** Guest mail keys live in `App/app/i18n.py` (en, cs, de, es, fr) and `App/app/guest_uk_i18n.py` (uk). `tests/test_guest_languages.py::test_every_guest_key_exists_in_all_five_languages` requires every key in every language, so all six get the keys.

**Context-rollout upload (orchestrator):** put files **flat** in the rollout bundle folder under docs/plans (no subfolder). MANIFEST and place_files script at that root.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/mail.py | edit | `RECEIPT_DETAILS_MARKER`/`KEY`; `_with_receipt_details`; both delivery functions call it |
| App/app/mail_notify.py | edit | `build_completion(sent_details=...)`; `render_receipt_details` |
| App/app/claim.py | edit | pass `sent_details=True`; put the stay id in the receipt payload |
| App/app/i18n.py | edit | 3 keys in en, cs, de, es, fr |
| App/app/guest_uk_i18n.py | edit | 3 keys in uk |
| App/tests/test_guest_receipt_sent_mail.py | create | new focused tests |
| docs/tasks/1122-guest-receipt-report.md | create | report |

No other file may change.

## 4. Steps

**Step 1.** Branch and check that 1121 has landed.
```bash
cd /home/user/jsfpecharoperations && git fetch origin main 2>&1 | tail -3 && git switch -c task/1122-guest-receipt-what-you-sent origin/main 2>&1 | tail -3 && grep -n 'GUEST_DETAILS_KEY = \|def mask_document_number' App/app/mail.py App/app/mail_notify.py | head -5
```
Expected: 2 lines. If either is missing, STOP (1121 not merged).

**Step 2.** `App/app/mail.py`. Find:
```python
GUEST_DETAILS_MARKER = "{{guest_details}}"
GUEST_DETAILS_KEY = "guest_details_reservation_id"
```
Replace with:
```python
GUEST_DETAILS_MARKER = "{{guest_details}}"
GUEST_DETAILS_KEY = "guest_details_reservation_id"
# 1122: the guest receipt's "What you sent" block, rendered the same way.
RECEIPT_DETAILS_MARKER = "{{receipt_details}}"
RECEIPT_DETAILS_KEY = "receipt_details_reservation_id"
```
Command: `grep -n 'RECEIPT_DETAILS_' App/app/mail.py | head -3`. Expected: 2 lines.

**Step 3.** `App/app/mail.py`. Find:
```python
    return value.replace(GUEST_DETAILS_MARKER, block)


def stored_body(payload: Dict[str, Any]) -> str:
```
Replace with:
```python
    return value.replace(GUEST_DETAILS_MARKER, block)


def _with_receipt_details(value: str, payload: Dict[str, Any], *, as_html: bool) -> str:
    """Render the receipt's "What you sent" block at send time (1122)."""
    if RECEIPT_DETAILS_MARKER not in value:
        return value
    reservation_id = payload.get(RECEIPT_DETAILS_KEY)
    if not reservation_id:
        raise db.DecryptionError("outbox payload has a receipt block with no stay")
    from . import mail_notify

    block = mail_notify.render_receipt_details(
        int(reservation_id), lang=str(payload.get("lang") or "en"), as_html=as_html
    )
    return value.replace(RECEIPT_DETAILS_MARKER, block)


def stored_body(payload: Dict[str, Any]) -> str:
```
Command: `grep -n 'def _with_receipt_details' App/app/mail.py | head -3`. Expected: 1 line.

**Step 4.** `App/app/mail.py`, `delivery_body`. Find:
```python
    return _with_guest_details(
        _with_door_code(_with_secret(stored_body(payload), payload), payload),
        payload,
        as_html=False,
    )
```
Replace with:
```python
    return _with_receipt_details(
        _with_guest_details(
            _with_door_code(_with_secret(stored_body(payload), payload), payload),
            payload,
            as_html=False,
        ),
        payload,
        as_html=False,
    )
```
Command: `grep -c 'as_html=False' App/app/mail.py`. Expected: `2`.

**Step 5.** `App/app/mail.py`, `delivery_html`. Find:
```python
    return _with_guest_details(
        _with_door_code(_with_secret(stored_html(payload), payload), payload),
        payload,
        as_html=True,
    )
```
Replace with:
```python
    return _with_receipt_details(
        _with_guest_details(
            _with_door_code(_with_secret(stored_html(payload), payload), payload),
            payload,
            as_html=True,
        ),
        payload,
        as_html=True,
    )
```
Command: `cd App && .venv/bin/python -c "import app.mail" 2>&1 | tail -5`. Expected: no output.

**Step 6.** `App/app/mail_notify.py`, `build_completion` signature (1121 does not change it). Find:
```python
    host_url: str = "",
    fee: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    """The receipt. It points at the stay, not at a new claim link.
```
Replace with:
```python
    host_url: str = "",
    fee: Optional[Dict[str, Any]] = None,
    sent_details: bool = False,
) -> Dict[str, str]:
    """The receipt. It points at the stay, not at a new claim link.
```
Command: `grep -n 'sent_details: bool = False' App/app/mail_notify.py | head -3`. Expected: 1 line.

**Step 7.** `App/app/mail_notify.py`, `build_completion` body. Find:
```python
        text_lines.extend(["", *(f"{label}: {value}" for label, value in rows)])

    spayd = ""
```
Replace with:
```python
        text_lines.extend(["", *(f"{label}: {value}" for label, value in rows)])

    # 1122: "What you sent", filled in at send time (render_receipt_details).
    if sent_details:
        blocks.append(mail.RECEIPT_DETAILS_MARKER)
        text_lines.extend(["", mail.RECEIPT_DETAILS_MARKER])

    spayd = ""
```
Command: `grep -n 'RECEIPT_DETAILS_MARKER' App/app/mail_notify.py | head -3`. Expected: 2 lines.

**Step 8.** `App/app/mail_notify.py`. Find this exact line (it occurs once; after 1121 it sits right under `host_guest_details`):
```python
def build_fee_update(
```
Replace it with:
```python
# --- 1122: "What you sent" on the guest receipt --------------------------------

_RECEIPT_GUEST_COLUMNS = "id, first_name, surname, doc_number, doc_number_enc, entered_by, created_at"


def render_receipt_details(reservation_id: int, *, lang: str, as_html: bool) -> str:
    """The receipt's "What you sent" block, read from the database at send time.

    The claim does not record which guest row is the person behind the claim
    address, so no birth date or address is shown for anyone. A guest typed in
    through the guest form since the claim was confirmed shows the masked
    document number; anyone else (entered by the host, imported, or typed in
    before the current claim) is shown by name only.
    """
    title = _guest_text(lang, "mail_completion_sent_title")
    claim_row = db.query_one(
        "SELECT claimed_at FROM reservation_claim WHERE reservation_id = ?", (reservation_id,)
    )
    since = str((claim_row["claimed_at"] if claim_row else "") or "")
    guests = db.query(
        f"SELECT {_RECEIPT_GUEST_COLUMNS} FROM guest "
        "WHERE reservation_id = ? AND archived_at IS NULL ORDER BY is_lead DESC, id",
        (reservation_id,),
    )
    lines: List[str] = []
    for row in guests:
        guest = dict(row)
        parts = (str(guest.get("first_name") or "").strip(), str(guest.get("surname") or "").strip())
        line = " ".join(p for p in parts if p) or _guest_text(lang, "mail_completion_sent_unnamed")
        typed_here = (
            guest.get("entered_by") == "guest"
            and bool(since)
            and str(guest.get("created_at") or "") >= since
        )
        masked = mask_document_number(guest.get("doc_number")) if typed_here else ""
        if masked:
            line = f"{line} – {_guest_text(lang, 'mail_completion_sent_doc_label')}: {masked}"
        lines.append(line)
    if not lines:
        return ""
    if as_html:
        return _block_section(title, lines[0]) + "".join(_block_paragraph(l) for l in lines[1:])
    return "\n".join([title, *lines])


def build_fee_update(
```
Command: `cd App && .venv/bin/python -c "import app.mail_notify as m; print(callable(m.render_receipt_details))" 2>&1 | tail -5`. Expected: `True`.

**Step 9.** `App/app/claim.py`, `_guest_mail_content` (text after 1121, which removed the `host_url=` line just above). Find:
```python
                fee=_completion_fee(apartment, reservation),
                **_completion_facts(apartment, reservation, lang),
```
Replace with:
```python
                fee=_completion_fee(apartment, reservation),
                sent_details=True,
                **_completion_facts(apartment, reservation, lang),
```
Command: `grep -n 'sent_details=True' App/app/claim.py | head -3`. Expected: 1 line.

**Step 10.** `App/app/claim.py`, `maybe_notify_completion`. Find:
```python
    if code_row is not None:
        payload[mail.DOOR_CODE_KEY] = code_row["pin_enc"]
```
Replace with:
```python
    if code_row is not None:
        payload[mail.DOOR_CODE_KEY] = code_row["pin_enc"]
    if mail.RECEIPT_DETAILS_MARKER in payload.get("text", ""):
        # 1122: ids only; the guest names are read when the mail is sent.
        payload[mail.RECEIPT_DETAILS_KEY] = int(reservation["id"])
```
Command: `grep -n 'RECEIPT_DETAILS_KEY' App/app/claim.py | head -3`. Expected: 1 line.

**Steps 11 to 15.** `App/app/i18n.py`: one edit per language. In each, find the line on the left (8-space indent, it occurs once) and replace it with that same line followed by the three lines on the right.

| Step | Find (exact line) | Add after it |
|---|---|---|
| 11 (en) | `        "mail_completion_fee_once": "Choose one way to pay:",` | `        "mail_completion_sent_title": "What you sent",`<br>`        "mail_completion_sent_doc_label": "Document number",`<br>`        "mail_completion_sent_unnamed": "Guest",` |
| 12 (cs) | `        "mail_completion_fee_once": "Vyberte si jeden způsob platby:",` | `        "mail_completion_sent_title": "Co jste odeslali",`<br>`        "mail_completion_sent_doc_label": "Číslo dokladu",`<br>`        "mail_completion_sent_unnamed": "Host",` |
| 13 (de) | `        "mail_completion_fee_once": "Wählen Sie eine Zahlungsart:",` | `        "mail_completion_sent_title": "Was Sie gesendet haben",`<br>`        "mail_completion_sent_doc_label": "Dokumentnummer",`<br>`        "mail_completion_sent_unnamed": "Gast",` |
| 14 (es) | `        "mail_completion_fee_once": "Elija una forma de pago:",` | `        "mail_completion_sent_title": "Lo que ha enviado",`<br>`        "mail_completion_sent_doc_label": "Número de documento",`<br>`        "mail_completion_sent_unnamed": "Huésped",` |
| 15 (fr) | `        "mail_completion_fee_once": "Choisissez un moyen de paiement :",` | `        "mail_completion_sent_title": "Ce que vous avez envoyé",`<br>`        "mail_completion_sent_doc_label": "Numéro du document",`<br>`        "mail_completion_sent_unnamed": "Voyageur",` |

Command after Step 15: `grep -c '"mail_completion_sent_title"' App/app/i18n.py`. Expected: `5`.

**Step 16.** `App/app/guest_uk_i18n.py` (4-space indent). Find:
```python
    "mail_completion_fee_once": "Оберіть один спосіб оплати:",
```
Replace with:
```python
    "mail_completion_fee_once": "Оберіть один спосіб оплати:",
    "mail_completion_sent_title": "Що ви надіслали",
    "mail_completion_sent_doc_label": "Номер документа",
    "mail_completion_sent_unnamed": "Гість",
```
Command: `cd App && .venv/bin/python -c "from app import i18n; print(all('mail_completion_sent_title' in i18n.STRINGS[l] for l in i18n.LANGUAGES))" 2>&1 | tail -5`. Expected: `True`.

**Step 17.** Create `App/tests/test_guest_receipt_sent_mail.py` with exactly:

```python
"""Guest receipt "What you sent" block (task 1122).

Names for everyone; the masked document number only for guests typed in
through the guest form since the claim was confirmed; no birth date or address
for anyone. Rendered at send time, so the outbox row holds the stay id only.
All guest data here is made up.
"""
from __future__ import annotations

import html
import json

from app import claim, db, door_codes, guest_mail_pref, i18n, mail, mail_notify
# _env is the autouse fixture of that file; importing it here applies it here too.
from tests.test_host_guest_details_mail import LEAD, MASK, _env, _rows, _seed  # noqa: F401

NEW_KEYS = (
    "mail_completion_sent_title",
    "mail_completion_sent_doc_label",
    "mail_completion_sent_unnamed",
)


def _complete(monkeypatch, seed):
    monkeypatch.setattr(guest_mail_pref, "full_details", lambda owner_user_id: False)
    monkeypatch.setattr(
        claim.reporting, "reservation_progress",
        lambda *a, **k: {"expected": 2, "filled": 2, "incomplete": []},
    )
    monkeypatch.setattr(door_codes, "completion_door_code", lambda *a, **k: ("none", None, None))
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (seed["apartment"],))
    reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (seed["stay"],))
    claim.maybe_notify_completion(reservation, apartment)
    (row,) = _rows(seed["stay"], "completion")
    payload = json.loads(row["payload"])
    return row, payload, mail.delivery_body(payload), html.unescape(mail.delivery_html(payload))


def test_guests_typed_in_through_this_claim_show_a_masked_document(monkeypatch):
    seed = _seed()
    _row, _payload, text, page = _complete(monkeypatch, seed)
    for part in (text, page):
        assert "What you sent" in part
        assert f"Jana Testova – Document number: {MASK} 4567" in part
        assert f"Petr Ukazka – Document number: {MASK} 4321" in part
        for absent in ("AB1234567", "XY7654321", "V99887766", "Testgasse", "Musterweg",
                       "1990", "1985"):
            assert absent not in part, absent


def test_a_guest_the_host_entered_is_named_only(monkeypatch):
    seed = _seed()
    db.execute("UPDATE guest SET entered_by = 'host' WHERE id = ?", (seed["guests"][1],))
    _row, _payload, text, page = _complete(monkeypatch, seed)
    for part in (text, page):
        assert "Petr Ukazka" in part
        assert "4321" not in part
        assert f"{MASK} 4567" in part


def test_a_guest_typed_in_before_the_claim_is_named_only(monkeypatch):
    seed = _seed()
    db.execute(
        "UPDATE guest SET created_at = ? WHERE id = ?",
        ("2000-01-01T00:00:00+00:00", seed["guests"][1]),
    )
    _row, _payload, text, page = _complete(monkeypatch, seed)
    for part in (text, page):
        assert "Petr Ukazka" in part
        assert "4321" not in part


def test_the_receipt_row_holds_the_stay_id_and_goes_to_the_claim_address_only(monkeypatch):
    seed = _seed()
    row, payload, _text, _page = _complete(monkeypatch, seed)
    assert row["to_email"] == LEAD
    assert row["cc_email"] is None
    assert payload[mail.RECEIPT_DETAILS_KEY] == seed["stay"]
    assert mail.RECEIPT_DETAILS_MARKER in payload["text"]
    stored = " ".join([row["subject"] or "", row["payload"] or ""])
    for value in ("Jana", "Testova", "Petr", "Ukazka", "4567", "4321", "AB1234567"):
        assert value not in stored, value


def test_the_builder_adds_the_marker_only_when_asked():
    common = dict(lang="en", property_name="Test Flat", dates="1 Mar 2030 – 4 Mar 2030",
                  stay_url="https://example.test/l/x/1")
    assert mail.RECEIPT_DETAILS_MARKER not in mail_notify.build_completion(**common)["text"]
    with_block = mail_notify.build_completion(**common, sent_details=True)
    assert mail.RECEIPT_DETAILS_MARKER in with_block["text"]
    assert mail.RECEIPT_DETAILS_MARKER in with_block["html"]


def test_every_guest_language_has_the_new_keys():
    for lang in i18n.LANGUAGES:
        for key in NEW_KEYS:
            assert key in i18n.STRINGS[lang], (lang, key)
```
Command:
```bash
cd /home/user/jsfpecharoperations/App && .venv/bin/python -m pytest tests/test_guest_receipt_sent_mail.py -q --tb=short -x 2>&1 | tail -30
```
Expected: `6 passed`.

**Step 18.** Run the test-map rows for mail and claim, plus the guest catalogue tests:
```bash
cd /home/user/jsfpecharoperations/App && .venv/bin/python -m pytest tests/test_ses_mail.py tests/test_mail_*.py tests/test_*_mail.py tests/test_lifecycle_mail.py tests/test_notification_copy.py tests/test_claim_*.py tests/test_guest_languages.py tests/test_completion_fee_mail_1077.py tests/test_confirmation_with_door_code.py -q --tb=short -x 2>&1 | tail -30
cd /home/user/jsfpecharoperations && python3 scripts/context_lint.py 2>&1 | tail -30
```
Expected: all passed, 0 failed; lint clean.

**Step 19.** Commit, push the branch, open a **draft** PR (as executor.md says), write the report (§9).

## 5. Do not touch

- 1121's functions (`_with_guest_details`, `render_guest_details`, `host_guest_details`, `mask_document_number`): call them, do not edit them.
- `App/app/guest_mail_pref.py`, `App/app/fee_update.py`, migrations, `App/app/retention.py`, legal and privacy copy (1123).
- The receipt's recipient: it stays `to_email=claim["email"]`, with no `cc_email`.
- Hard rules: SQL only through `App/app/db.py` helpers, Postgres-portable; no new dependency; no schema change in this brief; never a full document or visa number, a signature or an ID photo in a mail; public repo, no real guest data in tests (all test data is made up); copy rule: no sentence the button already says.

## 6. Commands

Each one is in the step that uses it. Tests: Step 17 (new file, `6 passed`) and Step 18 (mail and claim rows of the test-map, plus `test_guest_languages.py`, `test_completion_fee_mail_1077.py` and `test_confirmation_with_door_code.py`, because the receipt and the guest catalogue changed). Never the full suite.

## 7. Acceptance

- [ ] `tests/test_guest_receipt_sent_mail.py`: 6 passed.
- [ ] Step 18 command: 0 failed.
- [ ] `grep -c '"mail_completion_sent_title"' App/app/i18n.py App/app/guest_uk_i18n.py` prints 5 and 1.
- [ ] `git diff --stat origin/main` lists only the §3 files.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found (most likely because 1121 is not merged, or was changed in review);
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1122-guest-receipt-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `App/app/mail_notify.py` `render_receipt_details`: the `entered_by`/`created_at >= claimed_at` rule is the only thing that keeps one guest's masked number out of another's inbox. Check it, and check that no birth date or address is selected.
- `App/app/claim.py`: the payload key is set only when the marker is in the text, so a fallback body (composer failure) carries no stray key.

## Owner steps

1. Open the draft PR for `task/1122-guest-receipt-what-you-sent` on GitHub.
2. When CI is green and the review is done, click "Ready for review".
3. Merge it with `scripts/merge-pr-on-green.sh <PR number>` from the repo root.
