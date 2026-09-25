# PLAN — Poplatek z pobytu (local stay fee) for UbyHost · v2 (simple)

> **What this is.** UbyHost will show each stay's guests **one total** of the local stay fee (*poplatek z pobytu*), with **one QR code** and a few international payment options.
> - The **host declares the rate per property** (e.g. 50 Kč per person per night). UbyHost multiplies it by nights and people.
> - People under 18 are excluded automatically. Other exemptions are declared discreetly on the form and decided by the host.
> - The host ticks **"Paid"** when they see the money.
> - A monthly list and CSV give the host the numbers for their own municipality's form.
>
> **What this is not.**
> - No per-city rates or city research. It works anywhere in Czechia because the host types the rate.
> - No filing with any authority, and no municipality-specific forms.
> - No bank API or payment checking, and UbyHost does not process payments.
> - No change to the Police house book.
> - No compliance guarantee.
>
> This file replaces v1 of `PLAN_POPLATEK_Z_POBYTU.md`. Do not overwrite `docs/POPLATEK_Z_POBYTU.md`; the owner merges by hand.

Research date for all sources: **2026-09-23** (§17).

---

## 0. Rules for the implementing agent (read first)

You are implementing a finished design. Do not redesign it.

1. **Do the steps in §16 in order, one step per commit.** Run the tests after every step, from `App/`: `.venv/bin/python -m pytest tests -q`. Do not prefix the command with `PYTHONPATH=App` (see `AGENTS.md`). Do not start the next step while tests are red.
2. **Use exactly the names given here**: files, functions, columns, routes, translation keys, CSS classes. Do not rename anything, and do not add extra fields, options, or "nice to have" features.
3. **Copy every user-facing string verbatim** from the tables in §13, into **both** `en` and `cs`. The parity tests fail if one language is missing a key.
   - All translators use Python `%`-formatting.
   - Placeholders look like `%(amount)s`.
   - A literal percent sign must be written `%%`.
4. **Do not touch** these unless this plan tells you to: UbyPort sending (`reporting.submit_*`), `validation.validate_guest`, the house book, automation, and the claim/PIN flow.
5. The **reference code** in §5 and §6 has been run and checked. Use it as written. Where this plan shows only a signature, write the body in the style of the surrounding file.
6. **If the code in the repo does not match what this plan describes**, stop and report the mismatch. Do not guess. Examples: a function that doesn't exist, a template block that looks different.
7. Keep the app **light-mode only**. Use existing CSS variables (`var(--g-ink)`, `var(--g-muted)`, `var(--g-line)`, `var(--g-surface)`, `var(--g-accent)`). Coral/accent is used only for the one primary button on a card.
8. **Security.**
   - Every host route starts with `guard = auth.require_login(request)` and loads rows through `access.*` (owner-scoped).
   - Every POST form includes `<input type="hidden" name="_csrf" value="{{ csrf_token }}">`.
   - Never mark host-typed text `|safe`.

---

## 1. How it works (the whole feature on one page)

| Topic | Decision |
|---|---|
| Where the rate comes from | `apartment.stay_fee_rate_czk`, typed by the host (0–50). **0 or empty = the feature is off** for that property. |
| Rate for a stay | Frozen on the stay the first time a form is saved (`reservation.stay_fee_rate_czk`), so a later rate change never alters old stays |
| Who is counted | every person with a **signed** form (`reporting.guest_has_signature`) |
| Nights per person | `(stay_to − stay_from).days`, using the guest's dates, else the booking's dates |
| Amount per person | nights × rate, **except**: under 18 on the arrival day → 0; stay longer than 60 days → 0; host decided "exempt" → 0; host decided "charge" → always nights × rate |
| Discreet exemption | a collapsed, optional "Anything your host should know?" row inside form step 1, with no mention of the fee. It **does not change the amount** the guest sees. The host sees it and decides. (§9) |
| What the guest sees | while people are missing: a one-line "stay fee so far". Once everyone has registered: **one card** with each person's line, **one total**, **one QR code** (with *Save QR image*), copyable bank details and international options, ordered for the viewer. The same details go in the completion e-mail. (§10) |
| Payment check | none. The host ticks **Mark as paid** on the stay (§11). The guest card then shrinks to "paid, thank you". |
| Toggle | `apartment.stay_fee_policy` `on` (default) / `off`, mirroring `passport_photo_policy`. `off` = guests see nothing and the host still sees amounts and the monthly list. |
| Host overview | `/stay-fees?month=YYYY-MM` + CSV (§12). The stay counts in the month of its **checkout**. |

### 1.1 UX walkthrough (what each person sees, in order)

This is the target experience. Every template change in §7–§12 implements one row of this table. If an instruction elsewhere seems to conflict with this table, follow the table and report the conflict.

**Guest (phone first, 375 px wide; the flow is unchanged except where noted)**

| # | Screen (existing file) | What changes | Why it's smooth |
|---|---|---|---|
| G1 | PIN → pick stay → claim (`pin.html`, `pick.html`, `claim.html`) | nothing | no new friction before the form |
| G2 | Form step 1 "Your details" (`form.html`, wizard step 1) | a **Document type** select above the document number. It is pre-set to *National ID* for Czech nationality and *Passport* otherwise, and follows the nationality select until the guest touches it. A collapsed **"Anything your host should know? (optional)"** row sits at the bottom of the step. | no extra wizard step (the step count stays 4, or 5 with the passport photo). The optional row is closed by default and says nothing about money. |
| G3 | Form steps 2–4 (residence, photo, signature + legal notice) | the legal notice gets one short "Local stay fee" paragraph | expectations are set before submitting, in the place guests already read the legal text |
| G4 | Stay hub after saving, while people are still missing (`stay.html`, `saved=1`) | a **one-line** note under the progress bar: "Stay fee so far: 400 Kč. Payment details appear once everyone has registered." | the primary action stays **Add person**. Nobody pays a partial amount. |
| G5 | Stay hub when everyone has registered | directly under the green all-done card: the **Stay fee card**. It lists each person's line, **one total** and the payment options, in the order that fits the viewer (see §10). On a phone the QR has a **Save QR image** button (banking apps can scan from the gallery). Every bank detail has a **Copy** button. | the guest paying on the same phone can't scan their own screen, so save/copy makes the QR usable. International guests see the options that work for them first. |
| G6 | Completion e-mail (`mail_notify.build_completion`, sent once when everyone is registered) | a "Local stay fee" section with the total, the transfer details and the online-pay button (if the host set one) | guests close the tab. The e-mail lets them pay later from any device, including one that can't open the stay page. |
| G7 | Stay hub after the host ticks Paid | the card shrinks to "Stay fee: 400 Kč — paid. Thank you." | closure; no stale QR |

**Host (desktop first)**

| # | Screen (existing file) | What changes |
|---|---|---|
| H1 | Property → edit (`apartment_form.html`) | a new **"Stay fee"** panel with its own link in the section nav (`#stay-fee-settings`), between the guest-link panel and Notes. Four inputs, rate first. |
| H2 | Legal entities (`entities.html`) | a bank account + BIC fields; an invalid account is rejected with a clear message |
| H3 | Stay detail (`reservation_detail.html`) | a **Stay fee** panel after the guest cards: a compact list (person · nights · amount). Rows where the guest ticked something in the optional row are **highlighted and expanded** with two buttons, *Charge* / *Exempt*. Other rows have a small *Change* disclosure. Then the total and **Mark as paid**. A warning shows when fewer people signed than the booking says. |
| H4 | Sidebar → Records → **Stay fee** (`/stay-fees`) | a monthly list by checkout month, totals, unpaid amount, CSV download |

No new colored chips in the stays list (DESIGN.md: "do not crowd tables with many colored chips").

---

## 2. Legal notes that shaped the design (short; cited)

- The fee is set by each **municipality (obec)** in its own decree (*obecně závazná vyhláška*). The statutory maximum is **50 Kč** per person per started day, excluding the arrival day: zákon č. 565/1990 Sb. §3c, §3d. That is why the host types the rate, and why the input is capped at 50.
- The **provider collects it from the guest** and remits it to the municipality (§3f). So the QR code pays the **host's** account.
- Only paid stays of **at most 60 consecutive days** are subject (§3a). People **under 18** are exempt (§3b(1)(b)). So are blind people, people dependent on help, **ZTP/P card holders and their companions** (§3b(1)(a)), and a few rarer groups. People **registered as living in that municipality** are not liable at all (§3, §16c). Municipalities may add further exemptions: the host handles them with the override.
- The provider must keep a **register (evidenční kniha)** of everyone staying, with the fee collected or the reason for exemption, and keep it **6 years** (§3g). The CSV in §12 carries those columns, and the new `doc_type` field fills the "druh průkazu" gap.
- Failing record-keeping or reporting duties can be fined up to **500 000 Kč** (daňový řád §247a). This is why exemptions are decided by the host and never by the guest's tick.

---

## 3. What already exists (do not rebuild)

| Existing | File | Used for |
|---|---|---|
| `passport_photo_policy` select in the property form | `templates/apartment_form.html` (inside `{% if editing %}`, panel `id="communication"`) | the pattern for the new toggle |
| Payload sanitising | `routes/admin.py::_apartment_payload` | add the new fields next to the passport lines |
| Column migration | `db.py` `SCHEMA` + `ADDED_COLUMNS` + `_add_missing_columns` | new columns |
| Signed-form check | `reporting.guest_has_signature(guest)` | who is counted |
| Age maths | `validation.normalise_birth_date`, `validation.age_on(birth, when)` | the under-18 rule |
| Date parsing | `validation.parse_iso_date` | nights |
| QR PNG example | `routes/admin_accounts.py::_totp_qr_data` | the same idea in `payments.qr_data_uri` |
| Stay hub | `routes/guest.py::stay_overview` → `templates/guest/stay.html` | fee card |
| Host stay page | `routes/admin.py::reservation_detail` → `templates/reservation_detail.html` | fee panel |
| Sidebar | `templates/base.html` (group `nav.records`) and `templates/_components.html::nav_icon` | new nav item |
| CSV style | `housebook.housebook_csv` (`;` separator, UTF-8 BOM) | the fee CSV |

---

## 4. Database changes (`App/app/db.py`)

Add each column **twice**, exactly like `passport_photo_policy`:
- (a) inside the `CREATE TABLE` in `SCHEMA`;
- (b) as a tuple in `ADDED_COLUMNS`.

No new tables.

| Table | Column | Declaration | Meaning |
|---|---|---|---|
| apartment | `stay_fee_policy` | `TEXT NOT NULL DEFAULT 'on'` | `on` / `off`: show the fee to guests |
| apartment | `stay_fee_rate_czk` | `INTEGER NOT NULL DEFAULT 0` | rate per person per night; 0 = feature off |
| apartment | `stay_fee_payment_link` | `TEXT` | optional `https://` link (PayPal.me, Revolut, Wise, Stripe payment link…) |
| apartment | `stay_fee_cash` | `INTEGER NOT NULL DEFAULT 1` | 1 = guests may pay in cash on arrival |
| legal_entity | `bank_account` | `TEXT` | as typed: Czech `prefix-number/bank` or IBAN |
| legal_entity | `iban` | `TEXT` | derived by `payments.normalise_account` |
| legal_entity | `bic` | `TEXT` | optional |
| reservation | `stay_fee_rate_czk` | `INTEGER` | rate frozen for this stay |
| reservation | `stay_fee_paid_at` | `TEXT` | set when the host ticks Paid |
| reservation | `stay_fee_paid_amount_czk` | `INTEGER` | total at the moment of ticking |
| guest | `doc_type` | `TEXT` | one of `validation.DOC_TYPES` |
| guest | `fee_claim` | `TEXT` | `NULL` or `disability_card` / `local_resident` / `other` (what the guest said) |
| guest | `fee_host_decision` | `TEXT` | `NULL` (automatic) / `exempt` / `charge` |
| guest | `fee_host_reason` | `TEXT` | free text ≤ 120, required when the decision is `exempt` |

In `validation.py`, add this constant next to `CZECH_CODE`:

```python
DOC_TYPES = (
    "op", "pas", "prechodny_pobyt", "pobytova_karta_eu", "povoleni_pobyt",
    "povoleni_pobyt_cizinec", "trvaly_pobyt", "zadatel_mezinarodni_ochrana",
    "zadatel_docasna_ochrana",
)
```

**Acceptance:** a fresh test DB has all the columns, and an old DB gets them on `connect()`. New apartments have `stay_fee_policy='on'` and `stay_fee_rate_czk=0`.

---

## 5. New module `App/app/payments.py` (shared with the invoice plan) — reference code, tested

```python
"""Czech bank-account helpers and QR Platba (SPAYD 1.0) payloads."""
import base64
import io
import re
import unicodedata
from decimal import Decimal

import qrcode
from qrcode.constants import ERROR_CORRECT_M

_WEIGHTS = (6, 3, 7, 9, 10, 5, 8, 4, 2, 1)
_ACCOUNT_RE = re.compile(r"^(?:(\d{1,6})-)?(\d{2,10})/(\d{4})$")
_IBAN_RE = re.compile(r"^[A-Z]{2}\d{2}[A-Z0-9]{10,30}$")
_QR_CHARS = set("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ $+-./:")


def _mod11_ok(digits: str) -> bool:
    padded = digits.zfill(10)
    return sum(int(d) * w for d, w in zip(padded, _WEIGHTS)) % 11 == 0


def _iban_ok(iban: str) -> bool:
    moved = iban[4:] + iban[:4]
    return int("".join(str(int(ch, 36)) for ch in moved)) % 97 == 1


def normalise_account(raw: str) -> tuple:
    """Return (display_account, iban). Raise ValueError on bad input."""
    text = re.sub(r"\s+", "", raw or "").upper()
    if _IBAN_RE.match(text):
        if not _iban_ok(text):
            raise ValueError("iban_checksum")
        return text, text
    match = _ACCOUNT_RE.match(text)
    if not match:
        raise ValueError("account_format")
    prefix, number, bank = match.group(1) or "", match.group(2), match.group(3)
    if (prefix and not _mod11_ok(prefix)) or not _mod11_ok(number):
        raise ValueError("account_checksum")
    bban = bank + prefix.zfill(6) + number.zfill(10)
    check = 98 - int(bban + "123500") % 97
    display = f"{prefix}-{number}/{bank}" if prefix else f"{number}/{bank}"
    return display, f"CZ{check:02d}{bban}"


def format_iban(iban: str) -> str:
    return " ".join(iban[i:i + 4] for i in range(0, len(iban), 4))


def ascii_upper(text: str, limit: int) -> str:
    plain = unicodedata.normalize("NFKD", text or "")
    plain = "".join(ch for ch in plain if not unicodedata.combining(ch)).upper()
    plain = "".join(ch if ch in _QR_CHARS else " " for ch in plain)
    plain = re.sub(r" +", " ", plain).strip()
    return plain[:limit].rstrip()


def spayd(iban: str, amount, vs: str, message: str, bic: str = "") -> str:
    account = iban + (f"+{bic.upper()}" if bic else "")
    parts = [
        "SPD", "1.0",
        f"ACC:{account}",
        f"AM:{Decimal(amount):.2f}",
        "CC:CZK",
        f"X-VS:{vs}",
        f"MSG:{ascii_upper(message, 60)}",
    ]
    return "*".join(parts)


def qr_png_bytes(payload: str) -> bytes:
    qr = qrcode.QRCode(error_correction=ERROR_CORRECT_M, box_size=6, border=4)
    qr.add_data(payload)
    qr.make(fit=True)
    output = io.BytesIO()
    qr.make_image().save(output, format="PNG")
    return output.getvalue()


def qr_data_uri(payload: str) -> str:
    return "data:image/png;base64," + base64.b64encode(qr_png_bytes(payload)).decode()
```

Expected results (put these in `tests/test_payments.py`):

| Call | Result |
|---|---|
| `normalise_account("19-2000781379/0800")` | `("19-2000781379/0800", "CZ3008000000192000781379")` |
| `normalise_account("123/0600")` | `("123/0600", "CZ9106000000000000000123")` |
| `normalise_account("30015-5157998/6000")` | `("30015-5157998/6000", "CZ1760000300150005157998")` |
| `normalise_account("CZ30 0800 0000 1920 0078 1379")` | `("CZ3008000000192000781379", "CZ3008000000192000781379")` |
| `normalise_account("19-2000781378/0800")` | `ValueError("account_checksum")` |
| `normalise_account("abc")` | `ValueError("account_format")` |
| `normalise_account("CZ3108000000192000781379")` | `ValueError("iban_checksum")` |
| `spayd("CZ9106000000000000000123", 400, "8000000042", "Poplatek z pobytu 42")` | `SPD*1.0*ACC:CZ9106000000000000000123*AM:400.00*CC:CZK*X-VS:8000000042*MSG:POPLATEK Z POBYTU 42` |
| `ascii_upper("Příliš žluťoučký kůň * 100% ok", 60)` | `PRILIS ZLUTOUCKY KUN 100 OK` |
| `format_iban("CZ3008000000192000781379")` | `CZ30 0800 0000 1920 0078 1379` |
| `qr_data_uri("x")` | starts with `data:image/png;base64,` |

(The format follows the qr-platba.cz SPAYD 1.0 spec: max 46 chars for ACC, AM with a dot and 2 decimals, CZK only, VS ≤ 10 digits, MSG ≤ 60. The due date and CRC32 are optional and deliberately omitted.)

---

## 6. New module `App/app/stay_fee.py` — reference code

```python
"""Local stay fee (poplatek z pobytu): host-declared rate, one total per stay."""
from datetime import date
from typing import Any, Dict, Optional

from . import db, reporting, validation

MAX_CALENDAR_DAYS = 60   # zákon 565/1990 §3a: stays longer than this are not subject
ADULT_AGE = 18           # §3b(1)(b)
MAX_RATE_CZK = 50        # §3d
VS_PREFIX = "8"
CLAIM_CODES = ("disability_card", "local_resident", "other")
DECISIONS = ("exempt", "charge")


def is_active(apartment) -> bool:
    return bool(apartment) and int(apartment["stay_fee_rate_czk"] or 0) > 0


def shows_to_guest(apartment) -> bool:
    return is_active(apartment) and (apartment["stay_fee_policy"] or "on") == "on"


def conservative_birth(raw) -> Optional[date]:
    """Earliest possible birthday, so an unknown day/month never makes someone a minor."""
    digits = validation.normalise_birth_date(raw)
    if len(digits) != 8 or not digits.isdigit():
        return None
    day, month, year = int(digits[:2]), int(digits[2:4]), int(digits[4:])
    if year == 0:
        return None
    try:
        return date(year, month or 1, day or 1)
    except ValueError:
        return None


def stay_rate(reservation, apartment) -> int:
    return int(reservation["stay_fee_rate_czk"] or apartment["stay_fee_rate_czk"] or 0)


def snapshot_rate(reservation_id: int) -> None:
    """Freeze the property's current rate on the stay, once."""
    db.execute(
        "UPDATE reservation SET stay_fee_rate_czk = "
        "(SELECT a.stay_fee_rate_czk FROM apartment a WHERE a.id = reservation.apartment_id) "
        "WHERE id = ? AND stay_fee_rate_czk IS NULL",
        (reservation_id,),
    )


def stay_vs(reservation_id: int) -> str:
    return VS_PREFIX + str(reservation_id).zfill(9)


def person_fee(guest, reservation, rate: int) -> Dict[str, Any]:
    start = validation.parse_iso_date(guest["stay_from"] or reservation["date_from"])
    end = validation.parse_iso_date(guest["stay_to"] or reservation["date_to"])
    nights = max((end - start).days, 0) if start and end else 0
    decision = guest["fee_host_decision"]
    if decision == "exempt":
        charged, reason = 0, "host_exempt"
    elif decision == "charge":
        charged, reason = nights, None
    elif nights + 1 > MAX_CALENDAR_DAYS:
        charged, reason = 0, "over_60_days"
    else:
        birth = conservative_birth(guest["birth_date"])
        minor = bool(birth and start and validation.age_on(birth, start) < ADULT_AGE)
        charged, reason = (0, "under_18") if minor else (nights, None)
    return {
        "guest_id": guest["id"],
        "nights": nights,
        "charged_nights": charged,
        "amount_czk": charged * rate,
        "reason": reason,
        "claim": guest["fee_claim"],
        "host_decision": decision,
        "host_reason": guest["fee_host_reason"] or "",
    }


def stay_summary(reservation, apartment) -> Optional[Dict[str, Any]]:
    """None when the feature never applied to this stay."""
    if not is_active(apartment) and not int(reservation["stay_fee_rate_czk"] or 0):
        return None
    rate = stay_rate(reservation, apartment)
    guests = db.query(
        "SELECT * FROM guest WHERE reservation_id = ? ORDER BY id", (reservation["id"],)
    )
    people = [person_fee(g, reservation, rate) for g in guests if reporting.guest_has_signature(g)]
    return {
        "rate_czk": rate,
        "people": people,
        "total_czk": sum(p["amount_czk"] for p in people),
        "vs": stay_vs(reservation["id"]),
        "paid_at": reservation["stay_fee_paid_at"],
        "paid_amount_czk": reservation["stay_fee_paid_amount_czk"],
    }


def format_czk(amount: int) -> str:
    return f"{amount:,}".replace(",", " ")      # 1 200 with a no-break space
```

Worked examples (put these in `tests/test_stay_fee.py`; rate 50):

| # | Guest dates | Birth date | Host decision | Result |
|---|---|---|---|---|
| E1 | 2026-09-10 → 09-14 | 01.01.1990 | — | 4 nights, **200** |
| E2 | 2026-09-10 → 09-14 | 12.09.2008 (17 on arrival) | — | **0**, reason `under_18` |
| E3 | 2026-09-10 → 09-14 | 10.09.2008 (18 on arrival) | — | **200** |
| E4 | 2026-09-10 → 09-14 | `00002015` | — | **0** (treated as 01.01.2015) |
| E5 | 2026-09-10 → 09-14 | `00000000` | — | **200** (unknown birth date = adult) |
| E6 | 2026-06-01 → 07-30 (59 nights) | adult | — | **2 950** |
| E7 | 2026-06-01 → 07-31 (60 nights) | adult | — | **0**, `over_60_days` |
| E8 | 2026-09-10 → 09-14 | adult, `fee_claim='disability_card'` | — | **200** (a claim alone changes nothing) |
| E9 | same as E8 | adult | `exempt` | **0**, `host_exempt` |
| E10 | 2026-09-10 → 09-14 | 12.09.2008 | `charge` | **200** |
| E11 | a stay with 3 signed + 1 unsigned guest | adults | — | `people` has 3 entries; total 600 |

---

## 7. Property settings (mirror of `passport_photo_policy`)

### 7.1 `routes/admin.py::_apartment_payload`

Add this block **directly after** the three passport lines (`policy = _form_str(form, "passport_photo_policy", "off")` … `else "off"`). The `if` guard is required. The create form does not render these fields, and without the guard a missing checkbox would turn cash off.

```python
if "stay_fee_rate_czk" in form:
    fee_policy = _form_str(form, "stay_fee_policy", "on")
    payload["stay_fee_policy"] = fee_policy if fee_policy in ("on", "off") else "on"
    rate_raw = _form_str(form, "stay_fee_rate_czk", "0")
    rate = int(rate_raw) if rate_raw.isdigit() else 0
    payload["stay_fee_rate_czk"] = max(0, min(rate, stay_fee.MAX_RATE_CZK))
    link = _form_str(form, "stay_fee_payment_link", "")
    payload["stay_fee_payment_link"] = link if link.startswith("https://") and len(link) <= 300 else None
    payload["stay_fee_cash"] = 1 if form.get("stay_fee_cash") else 0
```

Add `stay_fee` to the `from .. import …` line at the top of `routes/admin.py`.

### 7.2 `templates/apartment_form.html` — its own panel

**(a) Section nav.** Inside the `{% if editing %}` branch of `<nav class="section-nav">`, directly after the `<a href="#communication">{{ t('apartment.form.nav.guest_link') }}</a>` line, add:

```html
    <a href="#stay-fee-settings">{{ t('apartment.form.nav.stay_fee') }}</a>
```

**(b) Panel.** Insert directly **before** the Notes panel. That is the `<div class="panel">` whose first child is `<h2 style="margin-top:0">{{ t('apartment.form.notes.title') }}</h2>`, i.e. after the closing `</div>` of `<div class="panel" id="communication">`:

```html
  {% if editing %}
  <div class="panel" id="stay-fee-settings">
    <h2 style="margin-top:0">{{ t('apartment.form.stay_fee.heading') }}</h2>
    <p class="small muted" style="margin-top:-4px">{{ t('apartment.form.stay_fee.lede') }}</p>
    <div class="field" style="max-width:220px">
      <label for="stay_fee_rate_czk">{{ t('apartment.form.stay_fee.rate_label') }}</label>
      <input type="number" id="stay_fee_rate_czk" name="stay_fee_rate_czk" min="0" max="50" step="1"
             inputmode="numeric" value="{{ apartment.stay_fee_rate_czk or 0 }}">
      <div class="hint">{{ t('apartment.form.stay_fee.rate_hint') }}</div>
    </div>
    <div class="field" style="max-width:320px">
      <label for="stay_fee_policy">{{ t('apartment.form.stay_fee_policy.label') }}</label>
      <select id="stay_fee_policy" name="stay_fee_policy">
        <option value="on" {% if (apartment.stay_fee_policy if editing else 'on') != 'off' %}selected{% endif %}>{{ t('apartment.form.stay_fee_policy.on') }}</option>
        <option value="off" {% if editing and apartment.stay_fee_policy == 'off' %}selected{% endif %}>{{ t('apartment.form.stay_fee_policy.off') }}</option>
      </select>
      <div class="hint">{{ t('apartment.form.stay_fee_policy.hint') }}</div>
    </div>
    <div class="field" style="max-width:420px">
      <label for="stay_fee_payment_link">{{ t('apartment.form.stay_fee.link_label') }}</label>
      <input type="url" id="stay_fee_payment_link" name="stay_fee_payment_link" maxlength="300"
             placeholder="https://" value="{{ apartment.stay_fee_payment_link or '' }}">
      <div class="hint">{{ t('apartment.form.stay_fee.link_hint') }}</div>
    </div>
    <div class="checkline" style="margin-top:6px">
      <input type="checkbox" id="stay_fee_cash" name="stay_fee_cash" value="1"
             {% if apartment.stay_fee_cash %}checked{% endif %}>
      <label for="stay_fee_cash">{{ t('apartment.form.stay_fee.cash_label') }}</label>
    </div>
    {% if (apartment.stay_fee_rate_czk or 0) > 0 and not entity_iban %}
      <p class="small warn-text" style="margin-top:12px">{{ t('apartment.form.stay_fee.no_iban') }}
        <a href="/entities">{{ t('nav.entities') }} &rarr;</a></p>
    {% endif %}
  </div>
  {% endif %}
```

The panel sits inside the same `<form>` as the rest of the page, so the page's existing **Save changes** button saves it. Do not add a second submit button.

In `routes/admin.py::apartment_detail`, add to the `render` context:

```python
"entity_iban": _entity_iban(apartment["legal_entity_id"]),
```

and define this helper next to `_apartment_payload`:

```python
def _entity_iban(entity_id) -> str:
    if not entity_id:
        return ""
    row = db.query_one("SELECT iban FROM legal_entity WHERE id = ?", (entity_id,))
    return (row["iban"] or "") if row else ""
```

### 7.3 Other places that mirror the passport toggle

| File | Add |
|---|---|
| `demo.py` (the demo apartment creator with the `passport_photo_policy` parameter) | For the **Vinohrady** demo apartment: `"stay_fee_rate_czk": 50`. For its demo entity: `bank_account="123/0600"`, `iban="CZ9106000000000000000123"`. Other demo apartments stay at 0. |
| `templates/guest/_legal_notice.html` | after the `{% if apartment.passport_photo_policy == 'required_foreign' %}…{% endif %}` block: `{% if apartment.stay_fee_rate_czk and apartment.stay_fee_rate_czk > 0 %}<h3>{{ t('legal_notice_stay_fee_title') }}</h3><p>{{ t('legal_notice_stay_fee_body') }}</p>{% endif %}` |
| `templates/guest/privacy.html` + `routes/guest.py::privacy_notice` | context `"stay_fee_active": stay_fee.is_active(apartment)`; after the passport block: `{% if stay_fee_active %}<h3>{{ t('privacy_stay_fee_title') }}</h3><p>{{ t('privacy_stay_fee_body') }}</p>{% endif %}` |

---

## 8. Legal entity: bank account

**`routes/admin.py`**
- Change `ENTITY_FIELDS` to `("name", "seat", "ico", "dic", "contact_email", "contact_phone", "bank_account", "bic")`.
- In both `create_entity` and `update_entity`, right after `payload = {field: …}`:

```python
if payload.get("bank_account"):
    try:
        payload["bank_account"], payload["iban"] = payments.normalise_account(payload["bank_account"])
    except ValueError:
        return _back("/entities", err=host_i18n.translate(host_i18n.lang_from_request(request), "entities.bank.invalid"))
else:
    payload["iban"] = None
payload["bic"] = (payload.get("bic") or "").replace(" ", "").upper() or None
```

**`templates/entities.html`**: add two fields after `contact_phone` in **both** the create form and the edit form. Copy the markup of the `contact_phone` field and change the name, id, label and value:
- `bank_account` — label `entities.bank.label`, hint `entities.bank.hint`, placeholder `123456789/0100`;
- `bic` — label `entities.bic.label`.

---

## 9. Guest form: document type + discreet optional row (no new wizard step)

Both additions render only when `fee_active` is true. In `routes/guest.py::_form_context`, add to the returned context:

```python
"fee_active": stay_fee.is_active(apartment),
"doc_types": validation.DOC_TYPES,
"municipality": apartment["addr_obec"] or "",
```

**Wizard rule.** The form is a stepped wizard: every element with `data-guest-step` becomes one screen (`static/signature.js::initGuestWizard`). **Do not add a new `data-guest-step` element.** Both additions go **inside step 1** (the card that starts with `<h2>{{ t('your_details') }}`).

### 9.1 Document type (inside `#doc-wrap`, above the document-number label)

In `templates/guest/form.html`, change the `<div class="g-field" id="doc-wrap">` block so it begins like this (the existing `doc_number` label and input stay below, unchanged):

```html
<div class="g-field" id="doc-wrap">
  {% if fee_active %}
  <label for="doc_type">{{ t('doc_type') }}</label>
  <select id="doc_type" name="doc_type" class="{{ bad('doc_type') }}" {{ invalid('doc_type') }}
          data-doc-type style="margin-bottom:14px">
    {% for code in doc_types %}
      <option value="{{ code }}" {% if (val('doc_type') or ('op' if val('nationality') == 'CZE' else 'pas')) == code %}selected{% endif %}>{{ t('doc_type_' ~ code) }}</option>
    {% endfor %}
  </select>
  {{ err_for('doc_type') }}
  {% endif %}
  <label for="doc_number">{{ t('doc_number') }}</label>
  …(existing lines unchanged)…
```

Putting it inside `#doc-wrap` means it hides together with the document number when "child in parent's passport" is ticked (`initChildToggle`). The server then stores `pas` (§9.3).

**Smart default (JS).** In `static/signature.js`, add this function and call it in the `DOMContentLoaded` handler right after `initResidenceCountry();`:

```js
  function initDocType() {
    var nationality = document.getElementById("nationality");
    var docType = document.querySelector("[data-doc-type]");
    if (!nationality || !docType) return;
    var touched = false;
    docType.addEventListener("change", function () { touched = true; });
    nationality.addEventListener("change", function () {
      if (touched) return;
      docType.value = nationality.value === "CZE" ? "op" : "pas";
    });
  }
```

Bump the cache-busting query on the script tag in `templates/guest/base.html` (`signature.js?v=…`) to today's date plus a letter, following the existing pattern.

### 9.2 The optional row — must not reveal that it affects the fee

Rules. Keep them all:
- It is a **closed `<details>`** at the bottom of step 1. It is open only if the guest already chose something, e.g. when re-editing, or after a validation error.
- The summary text is neutral: "Anything your host should know? (optional)". Nowhere in it do the words fee, money, exempt, discount, osvobození or sleva appear.
- Choosing an option **changes nothing the guest sees** anywhere. Only the host's decision (§11) changes an amount.
- The stay page never echoes the choice.

Insert as the **last child of the step-1 card**, i.e. directly before the closing `</div>` of the card that starts with `<h2>{{ t('your_details') }}`. That is the line just above `<div class="g-card" data-guest-step>` + `<h2>{{ t('residence_title') }}</h2>`, after the purpose field:

```html
  {% if fee_active %}
  <details class="g-more" {% if val('fee_claim') %}open{% endif %}>
    <summary>{{ t('extra_info_title') }}</summary>
    <p class="g-intro">{{ t('extra_info_help') }}</p>
    <label class="g-radio"><input type="radio" name="fee_claim" value="" {% if not val('fee_claim') %}checked{% endif %}> {{ t('extra_info_none') }}</label>
    <label class="g-radio"><input type="radio" name="fee_claim" value="disability_card" {% if val('fee_claim') == 'disability_card' %}checked{% endif %}> {{ t('extra_info_disability_card') }}</label>
    {% if municipality %}
    <label class="g-radio"><input type="radio" name="fee_claim" value="local_resident" {% if val('fee_claim') == 'local_resident' %}checked{% endif %}> {{ t('extra_info_local_resident', municipality=municipality) }}</label>
    {% endif %}
    <label class="g-radio"><input type="radio" name="fee_claim" value="other" {% if val('fee_claim') == 'other' %}checked{% endif %}> {{ t('extra_info_other') }}</label>
  </details>
  {% endif %}
```

Append to `static/guest.css`:

```css
.g-more { margin-top: 18px; border-top: 1px solid var(--g-line); padding-top: 14px; }
.g-more summary { cursor: pointer; color: var(--g-muted); font-weight: 600; min-height: 44px; display: flex; align-items: center; }
.g-more[open] summary { color: var(--g-ink); }
.g-radio { display: flex; gap: 10px; align-items: flex-start; min-height: 44px; padding: 10px 0; border-top: 1px solid var(--g-line); color: var(--g-ink); }
.g-radio:first-of-type { border-top: 0; }
.g-radio input { margin-top: 3px; }
```

(44 px is the tap-target minimum used on the guest pages; see DESIGN.md "Mobile and desktop".)

### 9.3 Saving (`routes/guest.py::guest_form_save`)

1. Near where `signature` and `legal_ack` are read:
   ```python
   fee_active = stay_fee.is_active(apartment)
   doc_type = "pas" if child_in_passport else (form.get("doc_type") or "").strip()
   fee_claim = (form.get("fee_claim") or "").strip()
   ```
   `child_in_passport` is already defined earlier in the function; put these lines after it.
2. With the other issue checks (before `issues = _localize_issues(issues, lang)`):
   ```python
   if fee_active and doc_type not in validation.DOC_TYPES:
       issues.append(validation.Issue("doc_type", translate("doc_type_missing")))
   ```
3. On the 422 re-render path, add to the `context["values"].update({...})` dict: `"doc_type": doc_type, "fee_claim": fee_claim`.
4. In the `payload.update({...})` before insert/update, add:
   ```python
   "doc_type": doc_type if doc_type in validation.DOC_TYPES else None,
   "fee_claim": fee_claim if fee_claim in stay_fee.CLAIM_CODES else None,
   ```
5. Directly after `db.audit("guest_form_saved", …)` (this must run **before** `claim.maybe_notify_completion(...)`, so the completion e-mail sees the frozen rate):
   ```python
   if fee_active:
       stay_fee.snapshot_rate(reservation_id)
   ```

**Host guest form.**
- In `routes/admin.py::_guest_payload`, before `return payload`:
  ```python
  doc_type = _form_str(form, "doc_type")
  payload["doc_type"] = doc_type if doc_type in validation.DOC_TYPES else None
  ```
- Add the same `doc_type` select to `templates/guest_form_admin.html`, directly above the document-number field. Use the host keys `guest.doc_type.label` and `guest.doc_type.<code>` (§13.3). Copy the field markup of the neighbouring select in that template. Do **not** add the optional row: the host uses the decision buttons (§11).
- In `guest_create` and `guest_update`, after the DB write, call `stay_fee.snapshot_rate(reservation_id)`. In `guest_update`, use `guest["reservation_id"]`.

---

## 10. Guest stay page: one card, one total, one QR, and the completion e-mail

### 10.1 `routes/guest.py`

Add this helper under `_person_row`:

```python
def _stay_fee_view(reservation, apartment, people, lang, *, complete: bool, czech_first: bool):
    if not stay_fee.shows_to_guest(apartment):
        return None
    summary = stay_fee.stay_summary(reservation, apartment)
    if not summary or not summary["people"]:
        return None
    t = i18n.translator(lang)
    labels = {row["id"]: (row["name"] or f"{t('person')} {row['index']}") for row in people}
    lines = [
        {
            "label": labels.get(p["guest_id"], t("person")),
            "nights": p["nights"],
            "amount": stay_fee.format_czk(p["amount_czk"]),
        }
        for p in summary["people"]
    ]
    pay = stay_fee.payment_details(reservation, apartment, summary)
    qr = ""
    if pay["iban"] and summary["total_czk"] > 0 and not summary["paid_at"]:
        qr = payments.qr_data_uri(
            payments.spayd(pay["iban"], summary["total_czk"], pay["vs"], pay["reference"], pay["bic"])
        )
    return {
        "rate": summary["rate_czk"],
        "lines": lines,
        "total": stay_fee.format_czk(summary["total_czk"]),
        "total_raw": summary["total_czk"],
        "paid": bool(summary["paid_at"]),
        "complete": complete,
        "czech_first": czech_first,
        "qr": qr,
        **pay,
    }
```

**New helper in `stay_fee.py`** (also used by the e-mail):

```python
def payment_details(reservation, apartment, summary) -> Dict[str, Any]:
    entity = (
        db.query_one("SELECT * FROM legal_entity WHERE id = ?", (apartment["legal_entity_id"],))
        if apartment["legal_entity_id"] else None
    )
    iban = (entity["iban"] or "") if entity else ""
    vs = summary["vs"]
    return {
        "iban": iban,
        "iban_display": payments.format_iban(iban) if iban else "",
        "account": (entity["bank_account"] or "") if entity and "/" in (entity["bank_account"] or "") else "",
        "bic": (entity["bic"] or "") if entity else "",
        "beneficiary": (entity["name"] or "") if entity else "",
        "vs": vs,
        "reference": payments.ascii_upper(f"POPLATEK Z POBYTU {vs}", 60),
        "amount_plain": str(summary["total_czk"]),
        "payment_link": apartment["stay_fee_payment_link"] or "",
        "cash": bool(apartment["stay_fee_cash"]),
    }
```

(`account` is filled only when the host typed a Czech-format number, i.e. one containing `/`. If they typed an IBAN, the Czech line is hidden. Add `payments` to the `stay_fee.py` imports.)

In `stay_overview`, after `remaining = …` is computed, add the lines below. They reuse the `owned` set that the function already builds for `_person_row`:

```python
czech_first = any(
    g["id"] in owned and (g["nationality"] or "").upper() == validation.CZECH_CODE
    for g in progress["guests"]
) or (not owned and lang == "cs")
```

Then add to `context.update({...})`:

```python
"stay_fee": _stay_fee_view(
    reservation, apartment, people, lang,
    complete=remaining is not None and remaining <= 0,
    czech_first=czech_first,
),
```

Add `payments` and `stay_fee` to the imports at the top of `routes/guest.py`.

### 10.2 `templates/guest/stay.html`

**Where.** Insert directly **after** the `{% endif %}` that closes the big `{% if expected is none %} … {% elif remaining is not none and remaining <= 0 %} … {% else %} … {% endif %}` chain, and **before** `{% for person in people if person.mine %}`. Since UX-52 the hub reads ① status → ② the one next action → ③ money → ④ your records → ⑤ host footer, so this spot is ③: right under the all-done card (when complete) or right under the progress bar and the **Add person** button (when not). The **Add person** button no longer sits at the bottom of the page — it is directly under the progress card while people are missing, and it stays the only coral button on the screen until the fee is due.

```html
{% if stay_fee %}
  {% if stay_fee.paid %}
    <div class="g-card g-fee g-fee-paid" id="stay-fee">
      <p class="g-intro" style="margin:0">{{ t('fee_paid_line', amount=stay_fee.total) }}</p>
    </div>
  {% elif not stay_fee.complete %}
    <p class="g-fee-soon" id="stay-fee">{{ t('fee_so_far', amount=stay_fee.total) }}</p>
  {% elif stay_fee.total_raw > 0 %}
    {% set fee_online %}
      {% if stay_fee.payment_link %}
        <div class="g-fee-option">
          <a class="g-btn" href="{{ stay_fee.payment_link }}" target="_blank" rel="noopener noreferrer nofollow">{{ t('fee_pay_online', amount=stay_fee.total) }}</a>
          <p class="small muted">{{ t('fee_pay_online_help') }}</p>
        </div>
      {% endif %}
    {% endset %}
    {% set fee_czech %}
      {% if stay_fee.qr %}
        <div class="g-fee-option">
          <h3>{{ t('fee_czech_bank_title') }}</h3>
          <figure class="g-fee-qr">
            <img src="{{ stay_fee.qr }}" width="176" height="176" alt="{{ t('fee_qr_alt') }}">
            <figcaption>QR Platba</figcaption>
          </figure>
          <a class="g-btn secondary slim" href="{{ stay_fee.qr }}" download="qr-platba-{{ stay_fee.vs }}.png">{{ t('fee_qr_save') }}</a>
          <p class="small muted">{{ t('fee_qr_save_help') }}</p>
        </div>
      {% endif %}
    {% endset %}
    {% set fee_transfer %}
      {% if stay_fee.iban %}
        <div class="g-fee-option">
          <h3>{{ t('fee_transfer_title') }}</h3>
          <p class="small muted" style="margin-top:0">{{ t('fee_beneficiary') }}: {{ stay_fee.beneficiary }}</p>
          {% for field_id, label, value in [
              ('fee-amount', t('fee_amount_label') ~ ' (CZK)', stay_fee.amount_plain),
              ('fee-account', t('fee_account_cz'), stay_fee.account),
              ('fee-iban', 'IBAN', stay_fee.iban),
              ('fee-bic', 'BIC / SWIFT', stay_fee.bic),
              ('fee-vs', t('fee_vs'), stay_fee.vs),
              ('fee-ref', t('fee_reference'), stay_fee.reference)] if value %}
            <div class="g-copy">
              <label for="{{ field_id }}">{{ label }}</label>
              <div class="g-copy-row">
                <input id="{{ field_id }}" type="text" readonly value="{{ value }}">
                <button class="g-btn secondary slim" type="button" data-copy="{{ field_id }}"
                        data-copied-label="{{ t('copied') }}">{{ t('copy') }}</button>
              </div>
            </div>
          {% endfor %}
          <p class="small muted">{{ t('fee_abroad_hint') }}</p>
        </div>
      {% endif %}
    {% endset %}

    <div class="g-card g-fee" id="stay-fee">
      <h2>{{ t('fee_title') }}</h2>
      <p class="g-intro">{{ t('fee_intro', rate=stay_fee.rate) }}</p>
      <dl class="g-summary-list g-fee-lines">
        {% for line in stay_fee.lines %}
          <dt>{{ line.label }}</dt>
          <dd>{{ t('fee_line', nights=line.nights, amount=line.amount) }}</dd>
        {% endfor %}
      </dl>
      <p class="g-fee-total">{{ t('fee_total', amount=stay_fee.total) }}</p>
      {% if stay_fee.czech_first %}
        {{ fee_czech }}{{ fee_transfer }}{{ fee_online }}
      {% else %}
        {{ fee_online }}{{ fee_transfer }}{{ fee_czech }}
      {% endif %}
      {% if stay_fee.cash %}
        <p class="g-intro">{{ t('fee_cash') }}</p>
      {% endif %}
      {% if not stay_fee.payment_link and not stay_fee.iban and not stay_fee.cash %}
        <p class="g-intro">{{ t('fee_as_agreed') }}</p>
      {% endif %}
      <p class="small muted">{{ t('fee_everyone') }}</p>
    </div>
  {% endif %}
{% endif %}
```

Notes for the implementer:
- The page uses Jinja autoescaping, so `{% set x %}…{% endset %}` blocks are already safe markup. Do **not** add `|safe`.
- `data-copy` buttons already work on every guest page: `static/signature.js::initCopy` is loaded by `guest/base.html`. It copies the `<input>` whose id the button names, and swaps the label for `data-copied-label` for 1.4 s.
- The copy fields hold the **raw** IBAN without spaces, because many banking apps reject spaces.
- A total of 0 when complete shows nothing: there is nothing to say.

Append to `static/guest.css`:

```css
.g-fee h3 { font-size: 15px; margin: 18px 0 8px; color: var(--g-ink); }
.g-fee-total { font-weight: 700; font-size: 17px; margin: 12px 0 6px; color: var(--g-ink); }
.g-fee-option { padding-top: 14px; margin-top: 14px; border-top: 1px solid var(--g-line); }
.g-fee-qr { margin: 4px 0 10px; text-align: center; }
.g-fee-qr img { border: 1px solid var(--g-line); border-radius: 8px; background: #fff; }
.g-fee-qr figcaption { font-size: 13px; color: var(--g-muted); margin-top: 4px; }
.g-fee-soon { margin: -4px 0 16px; color: var(--g-muted); font-size: 14px; }
.g-copy { margin: 10px 0; }
.g-copy label { display: block; font-size: 13px; color: var(--g-muted); margin-bottom: 4px; }
.g-copy-row { display: flex; gap: 8px; }
.g-copy-row input { flex: 1 1 auto; min-width: 0; font-variant-numeric: tabular-nums; }
.g-copy-row .g-btn { flex: 0 0 auto; width: auto; }
```

**How international guests pay** (this is why the order changes):

| Guest | Works best | Order they see |
|---|---|---|
| Czech (their own form has nationality CZE) | QR Platba in any Czech banking app | QR → transfer → online |
| Slovak | a CZK transfer. The Czech QR usually won't scan in Slovak apps. | online → transfer → QR |
| Other EU/EEA, UK | a card via the host's link. A CZK transfer also works but the bank may charge a fee (SEPA is euro-only). | online → transfer → QR |
| US, China, rest of the world | a card via the host's link, or **cash on arrival**. Alipay/WeChat Pay are not supported. | online → transfer → QR |

UbyHost never processes the payment. The online button opens the host's own payment page.

### 10.3 Completion e-mail gets the fee (`mail_notify.py`, `claim.py`)

Guests close the tab after the last form. The completion receipt already goes to the claim e-mail exactly once, when everyone has registered (`claim.maybe_notify_completion`). That is the right moment.

1. **`stay_fee.py`** — add:
   ```python
   def mail_details(reservation, apartment) -> Optional[Dict[str, Any]]:
       if not shows_to_guest(apartment):
           return None
       summary = stay_summary(reservation, apartment)
       if not summary or summary["total_czk"] <= 0 or summary["paid_at"]:
           return None
       return {"total": format_czk(summary["total_czk"]), **payment_details(reservation, apartment, summary)}
   ```
2. **`claim.py::_guest_mail_content`** — in the `if kind == "completion":` branch, pass one extra argument to `mail_notify.build_completion(...)`: `stay_fee=stay_fee.mail_details(reservation, apartment)`. Add `stay_fee` to the imports in `claim.py`. There is no import cycle: `stay_fee` imports only `db`, `payments`, `reporting` and `validation`.
3. **`mail_notify.py::build_completion`** — the fee fills the **money slot** (`_block_panel`). Since UX-73 the receipt has a fixed order — status / money / secondary links / closing note / footer — and at most one coral button in the whole message, so the fee drops into the slot that was reserved for it instead of scattering four uppercase facts through the card.
   - Add the keyword parameter `stay_fee: Optional[Dict[str, Any]] = None` and, when it is set, hand `build_completion` one `money` panel:
     ```python
     money = {
         "amount": stay_fee["total"],                 # the bare number the subject names
         "title": _guest_text(lang, "mail_fee_title"),
         "rows": [
             (_guest_text(lang, "mail_fee_total"), stay_fee["total"]),
             ("IBAN", stay_fee["iban_display"], True),      # True → monospace, for copying
             *([("BIC / SWIFT", stay_fee["bic"], True)] if stay_fee.get("bic") else []),
             (_guest_text(lang, "fee_vs"), stay_fee["vs"], True),
             (_guest_text(lang, "fee_reference"), stay_fee["reference"], True),
         ],
         "action": (
             (stay_fee["payment_link"], _guest_text(lang, "fee_pay_online", amount=stay_fee["total"]))
             if stay_fee.get("payment_link") else None
         ),
         "note": _guest_text(lang, "fee_cash") if stay_fee.get("cash") else None,
     }
     ```
   - `_block_panel` renders that as one bordered sub-card on `CANVAS`: total first, then the transfer facts, then the cash line as muted text, then the button. Its button is the message's **only** coral button — the status slot stays buttonless and the stay link stays a quiet `_block_link`. A transfer-only fee (no `payment_link`) therefore has **no** button at all, which is why the panel's `action` is optional.
   - The subject switches to the fee-due variant (`mail_completion_subject_fee`) because `money["amount"]` is set. The intro switches with it: `mail_completion_intro_fee` replaces the "There is nothing else you need to do." sentence with the fee lead-in, so the receipt never promises closure while money is owed. That key carries the wording this table used to give for `mail_fee_body`, which the mail no longer uses as a separate section (the panel below is the details).
   - Pass the QR line as `secondary_note=_guest_text(lang, "mail_fee_qr_note")`, so it sits in the secondary-links slot next to the stay link.
   - The plain-text part mirrors the slot order through the existing `_panel_text_lines`, so `label: value` lines follow the intro and precede the stay link.
   - The mail does **not** include the QR image: inline images are unreliable across mail clients. The stay-page link in the same mail shows it.

---

## 11. Host: stay-fee panel on the stay page

### 11.1 Context (`routes/admin.py::reservation_detail`)

Add to the `render(... "reservation_detail.html", {...})` dict (the variables `reservation`, `apartment` and `progress` already exist in that function):

```python
"stay_fee": stay_fee.stay_summary(reservation, apartment),
"stay_fee_names": {
    g["id"]: f"{g['first_name'] or ''} {g['surname'] or ''}".strip() for g in progress["guests"]
},
"stay_fee_expected": reporting.expected_guest_count(reservation),
```

### 11.2 Template (`templates/reservation_detail.html`)

Insert directly **before** `{% if submissions %}` (the line above `<h2 id="reports">`). Rows needing attention (the guest ticked something and the host hasn't decided) are highlighted and open. Every other row keeps its controls behind a small *Change* disclosure, so the panel stays calm.

```html
{% if stay_fee %}
{% set fee_review = stay_fee.people | selectattr('claim') | rejectattr('host_decision') | list %}
<section class="panel" id="stay-fee">
  <div style="display:flex;justify-content:space-between;align-items:baseline;gap:12px;flex-wrap:wrap">
    <h2 style="margin:0">{{ t('stay.fee.title') }}{% if fee_review %} <span class="small warn-text">· {{ t('stay.fee.to_review', n=fee_review | length) }}</span>{% endif %}</h2>
    <span class="small muted">{{ t('stay.fee.rate', rate=stay_fee.rate_czk) }}</span>
  </div>
  {% if stay_fee_expected and stay_fee.people | length < stay_fee_expected %}
    <p class="warn-text small" style="margin:10px 0 0">{{ t('stay.fee.headcount', signed=stay_fee.people | length, expected=stay_fee_expected) }}</p>
  {% endif %}
  {% if stay_fee.people %}
  <ul class="fee-rows">
    {% for p in stay_fee.people %}
    {% set review = p.claim and not p.host_decision %}
    <li class="fee-row {{ 'needs-review' if review }}">
      <div class="fee-row-main">
        <strong>{{ stay_fee_names.get(p.guest_id) or '—' }}</strong>
        <span class="small muted">{{ t('stay.fee.nights', n=p.nights) }}</span>
        <span class="fee-amount">{{ p.amount_czk }} Kč</span>
      </div>
      {% if p.reason %}
        <div class="small muted">{{ t('stay.fee.reason.' ~ p.reason) }}{% if p.host_reason %} — {{ p.host_reason }}{% endif %}</div>
      {% endif %}
      {% if p.claim %}
        <div class="small warn-text">{{ t('stay.fee.claim.' ~ p.claim) }}</div>
      {% endif %}
      <details {% if review %}open{% endif %}>
        <summary class="small">{{ t('stay.fee.change') }}</summary>
        <form method="post" action="/guests/{{ p.guest_id }}/stay-fee" class="fee-decision">
          <input type="hidden" name="_csrf" value="{{ csrf_token }}">
          <input type="text" name="reason" maxlength="120" value="{{ p.host_reason }}"
                 placeholder="{{ t('stay.fee.reason_placeholder') }}" aria-label="{{ t('stay.fee.reason_placeholder') }}">
          <button class="btn small" type="submit" name="decision" value="exempt">{{ t('stay.fee.decision.exempt') }}</button>
          <button class="btn small" type="submit" name="decision" value="charge">{{ t('stay.fee.decision.charge') }}</button>
          {% if p.host_decision %}
            <button class="btn small" type="submit" name="decision" value="">{{ t('stay.fee.decision.auto') }}</button>
          {% endif %}
        </form>
      </details>
    </li>
    {% endfor %}
  </ul>
  {% endif %}
  <div style="display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;border-top:1px solid var(--line);padding-top:12px">
    <strong>{{ t('stay.fee.total', amount=stay_fee.total_czk) }}</strong>
    <form method="post" action="/reservations/{{ reservation.id }}/stay-fee/paid" style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
      <input type="hidden" name="_csrf" value="{{ csrf_token }}">
      {% if stay_fee.paid_at %}
        <span class="small">{{ t('stay.fee.paid_on', date=stay_fee.paid_at[:10] | date_cz, amount=stay_fee.paid_amount_czk) }}</span>
        <input type="hidden" name="action" value="unpaid">
        <button class="btn small" type="submit">{{ t('stay.fee.mark_unpaid') }}</button>
      {% elif stay_fee.total_czk > 0 %}
        <input type="hidden" name="action" value="paid">
        <button class="btn accent primary" type="submit">{{ t('stay.fee.mark_paid') }}</button>
      {% endif %}
    </form>
  </div>
  {% if stay_fee.paid_at and stay_fee.paid_amount_czk != stay_fee.total_czk %}
    <p class="warn-text small">{{ t('stay.fee.paid_changed', amount=stay_fee.total_czk) }}</p>
  {% endif %}
</section>
{% endif %}
```

**Button order matters.** *Exempt* comes first, so pressing Enter in the reason field (which is where the host types an exemption reason) submits *Exempt*.

Append to `static/app.css`:

```css
.fee-rows { list-style: none; margin: 12px 0; padding: 0; }
.fee-row { padding: 12px 0; border-top: 1px solid var(--line); }
.fee-row:first-child { border-top: 0; }
.fee-row.needs-review { background: var(--warn-soft); border-radius: 8px; padding: 12px; margin: 4px 0; border-top: 0; }
.fee-row-main { display: flex; gap: 12px; align-items: baseline; flex-wrap: wrap; }
.fee-amount { margin-left: auto; font-weight: 600; font-variant-numeric: tabular-nums; }
.fee-row details summary { cursor: pointer; color: var(--muted); margin-top: 6px; }
.fee-decision { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 8px; }
.fee-decision input[type="text"] { flex: 1 1 220px; }
```

### 11.3 Routes (`routes/admin.py`, next to `guest_update`)

```python
@router.post("/guests/{guest_id}/stay-fee")
async def guest_stay_fee_decision(guest_id: int, request: Request):
    # guard = auth.require_login(request); if guard: return guard
    # guest = access.guest(request, guest_id); if not guest: return _back("/reservations", err=_flash(request, "flash.error.no_such_guest"))
    # form = await request.form()
    # decision = _form_str(form, "decision"); reason = _form_str(form, "reason")[:120]
    # if decision not in ("", "exempt", "charge"): decision = ""
    # if decision == "exempt" and len(reason.strip()) < 3:
    #     return _back(f"/reservations/{guest['reservation_id']}#stay-fee",
    #                  err=host_i18n.translate(host_i18n.lang_from_request(request), "stay.fee.reason_required"))
    # db.update("guest", guest_id, {"fee_host_decision": decision or None,
    #                               "fee_host_reason": reason or None, "updated_at": db.utcnow()})
    # db.audit("stay_fee_decision", f"guest={guest_id} decision={decision or 'auto'} reason={reason}")
    # return _back(f"/reservations/{guest['reservation_id']}#stay-fee", msg=_flash(request, "flash.stay_fee.saved"))


@router.post("/reservations/{reservation_id}/stay-fee/paid")
async def reservation_stay_fee_paid(reservation_id: int, request: Request):
    # guard; reservation = access.reservation(request, reservation_id); if not: _back("/reservations", err=_flash(request, "flash.error.no_such_stay"))
    # apartment = access.apartment(request, reservation["apartment_id"])
    # form = await request.form(); action = _form_str(form, "action")
    # if action == "paid":
    #     summary = stay_fee.stay_summary(reservation, apartment)
    #     db.update("reservation", reservation_id, {"stay_fee_paid_at": db.utcnow(),
    #               "stay_fee_paid_amount_czk": summary["total_czk"] if summary else 0})
    # else:
    #     db.update("reservation", reservation_id, {"stay_fee_paid_at": None, "stay_fee_paid_amount_czk": None})
    # db.audit("stay_fee_paid" if action == "paid" else "stay_fee_unpaid", f"reservation={reservation_id}")
    # return _back(f"/reservations/{reservation_id}#stay-fee", msg=_flash(request, "flash.stay_fee.saved"))
```

The commented lines are the exact body. Write them as real code in the repo's style. Check that `db.update` accepts a dict with `None` values; the existing `apartment_update` already does this.

Flash messages go through `_flash(request, key, **params)`, never an English literal — see UX-34 in `UX_AUDIT.md` and `tests/test_flash_literals.py`. Add `flash.stay_fee.saved` to `host_i18n.py` in **both** EN and CS in the same commit as the route.

---

## 12. Host: monthly overview `/stay-fees` + CSV

**Sidebar** (`templates/base.html`, in the `nav.records` group, directly after the House book `<a>`):

```html
<a href="/stay-fees" class="{{ 'active' if nav == 'stay_fees' }}">{{ nav_icon('fee') }}{{ t('nav.stay_fees') }}</a>
```

**Icon** (`templates/_components.html`, inside `nav_icon`, before `{% endif %}`):

```html
  {% elif name == 'fee' %}
    <svg class="nav-icon" viewBox="0 0 20 20" fill="none" aria-hidden="true"><rect x="3" y="5" width="14" height="10" rx="1.5" stroke="currentColor" stroke-width="1.5"/><circle cx="10" cy="10" r="2.25" stroke="currentColor" stroke-width="1.5"/><path d="M5.5 7.5v5M14.5 7.5v5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
```

**Command palette** (`routes/admin.py`, the `items` list with `nav.housebook`), add after it:

```python
{"label": t("nav.stay_fees"), "group": t("command.group.pages"), "url": "/stay-fees", "keywords": "poplatek z pobytu city tax"},
```

**New helpers in `stay_fee.py`:**

```python
def month_bounds(month: str) -> tuple:
    """'2026-09' -> ('2026-09-01', '2026-09-30'). Raise ValueError on bad input."""

def month_stays(owner_user_id, month: str) -> list:
    """Stays whose checkout (date_to) is in the month, where the fee applied."""
    # first, last = month_bounds(month)
    # rows = db.query(
    #   "SELECT r.*, a.internal_name, a.stay_fee_rate_czk AS apt_rate, a.id AS apt_id "
    #   "FROM reservation r JOIN apartment a ON a.id = r.apartment_id "
    #   "WHERE a.owner_user_id IS ? AND r.status = 'active' AND r.archived_at IS NULL "
    #   "AND r.date_to >= ? AND r.date_to <= ? "
    #   "AND (a.stay_fee_rate_czk > 0 OR r.stay_fee_rate_czk > 0) ORDER BY r.date_to, r.id",
    #   (owner_user_id, first, last))
    # for each row: apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (row["apt_id"],))
    #   summary = stay_summary(row, apartment); skip if None
    #   append {"reservation": row, "apartment": apartment, "summary": summary,
    #           "charged_people": count(amount>0), "free_people": count(amount==0),
    #           "charged_nights": sum(charged_nights), "free_nights": sum(nights - charged_nights)}
    # return the list

EXPORT_COLUMNS = (
    ("property", "Zařízení"), ("property_address", "Adresa zařízení"),
    ("stay_from", "Den počátku pobytu"), ("stay_to", "Den konce pobytu"),
    ("surname", "Příjmení"), ("first_name", "Jméno"),
    ("home_address", "Adresa místa přihlášení / v zahraničí"), ("birth_date", "Datum narození"),
    ("doc_type", "Druh průkazu"), ("doc_number", "Číslo průkazu"),
    ("nights", "Počet nocí"), ("charged_nights", "Nocí zpoplatněno"), ("rate_czk", "Sazba (Kč)"),
    ("amount_czk", "Poplatek (Kč)"), ("not_charged_reason", "Důvod nezpoplatnění"), ("paid", "Zaplaceno"),
)

def export_csv(owner_user_id, month: str) -> bytes:
    """One row per signed guest of month_stays(); ';' separator, UTF-8 BOM (as housebook_csv)."""
```

Values for `export_csv`:
- `property_address` = `addr_street addr_house_no/addr_orient_no, addr_zip addr_obec`.
- `home_address` = `validation.compose_residence(res_street, res_city, res_country, "cs")`.
- `birth_date` = `validation.format_birth_date(birth_date)`.
- `doc_type` = the Czech label from §13.3 `guest.doc_type.*` (use `host_i18n.translate("cs", …)`).
- `not_charged_reason`: `under_18` → "mladší 18 let", `over_60_days` → "pobyt delší než 60 dnů", `host_exempt` → the host's reason text, otherwise empty.
- `paid` = "ano" if the stay's `stay_fee_paid_at` is set, else "ne".

**Routes (`routes/admin.py`):**

| Method + path | Handler | Behaviour |
|---|---|---|
| `GET /stay-fees?month=YYYY-MM` | `stay_fees_view` | If `month` is missing or invalid, use the current month (`claim.prague_today()`). Render `stay_fees.html` with `month`, `prev_month`, `next_month`, `rows = stay_fee.month_stays(access.owner_id(request), month)` and `totals` (sum of `charged_people`, `free_people`, `charged_nights`, `free_nights`, `total_czk`, and paid total). |
| `GET /stay-fees.csv?month=YYYY-MM` | `stay_fees_csv` | `Response(stay_fee.export_csv(...), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="poplatek-z-pobytu-{month}.csv"'})` |

**Template `templates/stay_fees.html`**, modelled on `housebook.html`:
- `{% extends "base.html" %}{% set nav = 'stay_fees' %}` and `page_header(t('stay_fees.title'), t('stay_fees.lede'))`.
- Month navigation: `← {{ prev_month }}` · `{{ month }}` · `{{ next_month }} →` as links `?month=`.
- A table with columns: `stay_fees.col.property`, `.stay` (dates `date_cz`, linked to `/reservations/{id}#stay-fee`), `.charged_people`, `.free_people`, `.charged_nights`, `.total`, `.paid` (✓ or —).
- A totals row, bold.
- The CSV button: `<a class="btn" href="/stay-fees.csv?month={{ month }}">{{ t('stay_fees.export') }}</a>`.
- The help text `t('stay_fees.help')`.
- When there are no rows: `t('stay_fees.empty')`.

---

## 13. Copy (all strings; both languages)

### 13.1 Guest (`App/app/i18n.py`, `STRINGS["en"]` and `STRINGS["cs"]`)

| Key | EN | CS |
|---|---|---|
| `doc_type` | Document type | Druh dokladu |
| `doc_type_op` | National ID card | Občanský průkaz |
| `doc_type_pas` | Passport | Cestovní pas |
| `doc_type_prechodny_pobyt` | Certificate of temporary residence | Potvrzení o přechodném pobytu |
| `doc_type_pobytova_karta_eu` | Residence card of an EU citizen's family member | Pobytová karta rodinného příslušníka občana EU |
| `doc_type_povoleni_pobyt` | Residence permit | Průkaz o povolení k pobytu |
| `doc_type_povoleni_pobyt_cizinec` | Residence permit for a foreign national | Průkaz o povolení k pobytu pro cizince |
| `doc_type_trvaly_pobyt` | Permanent residence permit | Průkaz o povolení k trvalému pobytu |
| `doc_type_zadatel_mezinarodni_ochrana` | International protection applicant card | Průkaz žadatele o mezinárodní ochranu |
| `doc_type_zadatel_docasna_ochrana` | Temporary protection applicant card | Průkaz žadatele o dočasnou ochranu |
| `doc_type_missing` | Choose the type of your document. | Zvolte druh dokladu. |
| `extra_info_title` | Anything your host should know? (optional) | Chcete ubytovateli něco sdělit? (nepovinné) |
| `extra_info_help` | Choose one if it applies to you. Your host may ask to see a document when you arrive. | Vyberte, pokud se vás něco týká. Ubytovatel vás při příjezdu může požádat o doklad. |
| `extra_info_none` | None of these | Nic z toho |
| `extra_info_disability_card` | I hold a ZTP/P card, or I am accompanying its holder | Jsem držitel/ka průkazu ZTP/P nebo jeho průvodce |
| `extra_info_local_resident` | I have permanent residence in %(municipality)s | Mám trvalý pobyt v obci %(municipality)s |
| `extra_info_other` | Something else — I will tell my host | Něco jiného — řeknu ubytovateli |
| `fee_title` | Local stay fee | Poplatek z pobytu |
| `fee_intro` | The municipality charges %(rate)s Kč per person per night. Your host collects it by law and passes it on. | Obec vybírá %(rate)s Kč za osobu a noc. Ubytovatel ho ze zákona vybírá a odvádí. |
| `fee_line` | %(nights)s night(s) · %(amount)s Kč | %(nights)s noc(í) · %(amount)s Kč |
| `fee_total` | Total: %(amount)s Kč | Celkem: %(amount)s Kč |
| `fee_so_far` | Stay fee so far: %(amount)s Kč. Payment details appear once everyone has registered. | Poplatek z pobytu zatím: %(amount)s Kč. Platební údaje se zobrazí, až se zaregistrují všichni. |
| `fee_paid_line` | Stay fee: %(amount)s Kč — paid. Thank you. | Poplatek z pobytu: %(amount)s Kč — zaplaceno. Děkujeme. |
| `fee_pay_online` | Pay %(amount)s Kč online (card) | Zaplatit %(amount)s Kč online (kartou) |
| `fee_pay_online_help` | Opens your host's payment page. | Otevře platební stránku ubytovatele. |
| `fee_czech_bank_title` | Czech banking app | Česká bankovní aplikace |
| `fee_qr_alt` | QR code for paying the stay fee in a Czech banking app | QR kód pro zaplacení poplatku v bankovní aplikaci |
| `fee_qr_save` | Save QR image | Uložit QR kód |
| `fee_qr_save_help` | Paying on this phone? Save the image, then choose "scan QR from image" (or gallery) in your banking app. | Platíte na tomto telefonu? Uložte obrázek a v bankovní aplikaci zvolte „načíst QR z obrázku“ (z galerie). |
| `fee_transfer_title` | Bank transfer | Bankovní převod |
| `fee_amount_label` | Amount | Částka |
| `fee_beneficiary` | Beneficiary | Příjemce |
| `fee_account_cz` | Account (Czech format) | Číslo účtu |
| `fee_vs` | Variable symbol | Variabilní symbol |
| `fee_reference` | Payment reference | Zpráva pro příjemce |
| `copy` | Copy | Kopírovat |
| `copied` | Copied | Zkopírováno |
| `fee_abroad_hint` | From abroad: send the amount in Czech crowns (CZK) and include the reference. Your bank may charge a fee. | Ze zahraničí: pošlete částku v korunách (CZK) a uveďte zprávu pro příjemce. Banka může účtovat poplatek. |
| `fee_cash` | You can also pay in cash when you arrive. | Můžete zaplatit také hotově při příjezdu. |
| `fee_as_agreed` | Please pay your host as agreed. | Zaplaťte prosím ubytovateli podle dohody. |
| `fee_everyone` | Everyone staying must register, including children. | Registrovat se musí všichni ubytovaní, včetně dětí. |
| `mail_fee_title` | Local stay fee | Poplatek z pobytu |
| `mail_fee_qr_note` | The QR code for your banking app is on your stay page. | QR kód pro bankovní aplikaci najdete na stránce pobytu. |
| `mail_fee_total` | Total | Celkem |
| `legal_notice_stay_fee_title` | Local stay fee | Poplatek z pobytu |
| `legal_notice_stay_fee_body` | Your host must collect the municipal stay fee and keep a register of everyone staying (name, address, date of birth, document type and number, stay dates, fee), for 6 years (Act No. 565/1990 Coll., §3f–§3g). | Ubytovatel musí vybírat poplatek z pobytu a vést evidenční knihu všech ubytovaných (jméno, adresa, datum narození, druh a číslo dokladu, dny pobytu, poplatek) po dobu 6 let (zákon č. 565/1990 Sb., § 3f–3g). |
| `privacy_stay_fee_title` | Stay-fee register | Evidenční kniha poplatku z pobytu |
| `privacy_stay_fee_body` | Legal obligation (Art. 6(1)(c) GDPR; Act No. 565/1990 Coll., §3g). Kept for 6 years. | Právní povinnost (čl. 6 odst. 1 písm. c) GDPR; zákon č. 565/1990 Sb., § 3g). Uchovává se 6 let. |

### 13.2 Host — property form (`host_i18n._INTERFACE_STRINGS`, directly after the `apartment.form.passport_policy.*` keys)

| Key | EN | CS |
|---|---|---|
| `apartment.form.stay_fee.heading` | Local stay fee (poplatek z pobytu) | Poplatek z pobytu |
| `apartment.form.nav.stay_fee` | Stay fee | Poplatek z pobytu |
| `apartment.form.stay_fee.lede` | Guests see one total with payment options after everyone has registered. You mark it paid yourself. | Hosté po registraci všech uvidí jednu částku a možnosti platby. Zaplacení označíte sami. |
| `apartment.form.stay_fee.rate_label` | Rate per person per night (Kč) | Sazba za osobu a noc (Kč) |
| `apartment.form.stay_fee.rate_hint` | Use the rate from your municipality's decree (max 50 Kč). 0 turns the stay fee off for this property. | Zadejte sazbu z vyhlášky vaší obce (max. 50 Kč). 0 poplatek u této nemovitosti vypne. |
| `apartment.form.stay_fee_policy.label` | Show the stay fee to guests | Zobrazit poplatek hostům |
| `apartment.form.stay_fee_policy.on` | On (default) — guests see the total and payment options | Zapnuto (výchozí) — hosté uvidí částku a možnosti platby |
| `apartment.form.stay_fee_policy.off` | Off — you collect it outside UbyHost | Vypnuto — vybíráte ho mimo UbyHost |
| `apartment.form.stay_fee_policy.hint` | Either way you see the amounts on each stay and in the monthly overview. | V obou případech uvidíte částky u pobytu i v měsíčním přehledu. |
| `apartment.form.stay_fee.link_label` | Online payment link (optional) | Odkaz na online platbu (nepovinné) |
| `apartment.form.stay_fee.link_hint` | For guests without a Czech bank, e.g. a PayPal.me, Revolut, Wise or Stripe payment link. Must start with https://. | Pro hosty bez české banky, např. odkaz PayPal.me, Revolut, Wise nebo Stripe. Musí začínat https://. |
| `apartment.form.stay_fee.cash_label` | Guests may pay in cash on arrival | Hosté mohou platit hotově při příjezdu |
| `apartment.form.stay_fee.no_iban` | Add a bank account to the legal entity so guests see a QR code and transfer details. | Doplňte k subjektu bankovní účet, aby hosté viděli QR kód a údaje pro převod. |
| `entities.bank.label` | Bank account for guest payments | Bankovní účet pro platby hostů |
| `entities.bank.hint` | Czech format (prefix-number/bank code) or IBAN. | Český formát (předčíslí-číslo/kód banky) nebo IBAN. |
| `entities.bank.invalid` | That account number is not valid. Please check it. | Číslo účtu není platné. Zkontrolujte ho prosím. |
| `entities.bic.label` | BIC / SWIFT (optional) | BIC / SWIFT (nepovinné) |

### 13.3 Host — stay panel, monthly page, host guest form (`host_i18n.STRINGS`)

| Key | EN | CS |
|---|---|---|
| `nav.stay_fees` | Stay fee | Poplatek z pobytu |
| `stay.fee.title` | Stay fee | Poplatek z pobytu |
| `stay.fee.rate` | Rate for this stay: %(rate)s Kč per person per night | Sazba pro tento pobyt: %(rate)s Kč za osobu a noc |
| `stay.fee.headcount` | Only %(signed)s of %(expected)s guests have signed a form. Unregistered guests are not in the total. | Formulář podepsalo jen %(signed)s z %(expected)s hostů. Neregistrovaní hosté nejsou v celkové částce. |
| `stay.fee.nights` | %(n)s night(s) | %(n)s noc(í) |
| `stay.fee.to_review` | %(n)s to review | %(n)s ke kontrole |
| `stay.fee.change` | Change | Změnit |
| `stay.fee.reason.under_18` | under 18 | mladší 18 let |
| `stay.fee.reason.over_60_days` | stay over 60 days | pobyt delší než 60 dnů |
| `stay.fee.reason.host_exempt` | exempted by you | osvobozeno vámi |
| `stay.fee.claim.disability_card` | ZTP/P card or companion — check the card | ZTP/P nebo průvodce — ověřte průkaz |
| `stay.fee.claim.local_resident` | Permanent residence in this municipality — check the ID | Trvalý pobyt v obci — ověřte doklad |
| `stay.fee.claim.other` | Something else — ask the guest | Něco jiného — zeptejte se hosta |
| `stay.fee.decision.auto` | Automatic | Automaticky |
| `stay.fee.decision.charge` | Charge | Účtovat |
| `stay.fee.decision.exempt` | Exempt | Osvobodit |
| `stay.fee.reason_placeholder` | Reason (required to exempt) | Důvod (povinný pro osvobození) |
| `stay.fee.reason_required` | Give a reason when you exempt someone. | Při osvobození uveďte důvod. |
| `stay.fee.total` | Total: %(amount)s Kč | Celkem: %(amount)s Kč |
| `stay.fee.mark_paid` | Mark as paid | Označit jako zaplaceno |
| `stay.fee.mark_unpaid` | Undo "paid" | Zrušit „zaplaceno“ |
| `stay.fee.paid_on` | Marked paid on %(date)s (%(amount)s Kč) | Označeno jako zaplaceno %(date)s (%(amount)s Kč) |
| `stay.fee.paid_changed` | The total has changed since then; it is now %(amount)s Kč. | Částka se mezitím změnila, nyní je %(amount)s Kč. |
| `stay_fees.title` | Stay fee | Poplatek z pobytu |
| `stay_fees.lede` | Stays that checked out this month, with the fee per stay. Use the numbers for your municipality's report. | Pobyty s odjezdem v tomto měsíci a poplatek za každý z nich. Čísla použijte pro hlášení obci. |
| `stay_fees.col.property` | Property | Nemovitost |
| `stay_fees.col.stay` | Stay | Pobyt |
| `stay_fees.col.charged_people` | People charged | Zpoplatněné osoby |
| `stay_fees.col.free_people` | People not charged | Nezpoplatněné osoby |
| `stay_fees.col.charged_nights` | Nights charged | Zpoplatněné noci |
| `stay_fees.col.total` | Fee | Poplatek |
| `stay_fees.col.paid` | Paid | Zaplaceno |
| `stay_fees.totals` | Total | Celkem |
| `stay_fees.export` | Download register (CSV) | Stáhnout evidenci (CSV) |
| `stay_fees.help` | The CSV lists every registered guest with the details the stay-fee register needs. UbyHost does not file anything for you. | CSV obsahuje všechny registrované hosty s údaji pro evidenční knihu. UbyHost za vás nic nepodává. |
| `stay_fees.empty` | No stays with the stay fee checked out this month. | Tento měsíc nebyl žádný pobyt s poplatkem. |
| `guest.doc_type.label` | Document type | Druh dokladu |
| `guest.doc_type.op` … `guest.doc_type.zadatel_docasna_ochrana` | same texts as the guest `doc_type_*` keys in §13.1 | same texts as §13.1 |

(The last row means nine keys: `guest.doc_type.<code>` for every code in `DOC_TYPES`, with the same EN/CS text as the guest keys.)

---

## 14. Tests (new files in `App/tests/`; copy fixtures and helpers from neighbouring tests such as `test_guest_navigation.py`)

| File | Must cover |
|---|---|
| `test_payments.py` | every row of the table in §5 |
| `test_stay_fee.py` | E1–E11 from §6; `snapshot_rate` sets the rate once and never overwrites it; `stay_summary` is None when the property rate is 0 and there is no snapshot |
| `test_stay_fee_settings.py` | new apartments: policy `on`, rate 0, cash 1; saving the edit form with rate `75` stores 50, `abc` stores 0; a link without `https://` is stored as None; the create form (no fee fields posted) leaves the defaults; the entity bank account `19-2000781379/0800` stores the IBAN `CZ3008000000192000781379`; an invalid account shows the error and saves nothing |
| `test_stay_fee_guest.py` | **Form:** rate 0 → no doc-type select, no `.g-more`; rate 50 → both present **inside step 1** and the number of `data-guest-step` elements is unchanged vs rate 0; a missing `doc_type` → 422; a child in the parent's passport saves `doc_type='pas'`. **Stay page:** with 2 of 3 expected signed → the `.g-fee-soon` line with the running total, and **no** QR or `.g-fee` card; with 3 of 3 signed → exactly **one** `#stay-fee` card, exactly **one** QR `<img>`, the total 3 × nights × 50, a *Save QR image* link with a `download` attribute, and copy inputs holding the raw IBAN (no spaces) and the VS; the card also shows after the last person signs (remaining = 0 branch); a CZE-owned form → the QR block comes before the online button in the HTML, a non-CZE form → the online button comes first (when a link is set); a `fee_claim` does **not** change the total; the stay page HTML never contains "exempt", "osvobozen" or the chosen claim text; policy off → nothing; paid → only the `fee_paid_line` sentence, no QR. **E-mail:** when the last form completes a claimed stay, the queued `completion` mail text contains the total, the IBAN and the VS; with policy off or a total of 0 it contains none of them. |
| `test_stay_fee_host.py` | *Exempt* without a reason → error; with a reason → amount 0 and an audit row; the `decision` values `exempt`/`charge`/`""` come from the button that was pressed; a row with a claim and no decision renders with the `needs-review` class and an open `<details>`; mark paid stores the total; undo clears it; the headcount warning appears when signed < expected; the property page has the `#stay-fee-settings` panel and nav link, and saving the page keeps the fee values; `/stay-fees` lists a stay by checkout month; the CSV has a BOM, `;`, the header from `EXPORT_COLUMNS` and one row per signed guest; other owners' stays never appear |
| i18n parity | existing parity tests must pass |

---

## 15. Non-goals, and what a lawyer should glance at

**Non-goals.** No per-city rates. No authority filing or municipal forms. No bank API, payment matching or refunds. No EUR payments or EPC (euro) QR. No Alipay/WeChat. No immutable register or month closing. No alerts or scheduler jobs. No change to UbyPort or the house book.

**Quick legal check before launch** (short list):
1. The 60-day cut-off rule (`nights + 1 > 60` → not charged) and the "under 18 on arrival day" rule.
2. That a CSV exported from live guest rows (which the host can still edit) is an acceptable *evidenční kniha* (§3g(3) asks for "trvalost zápisů").
3. That the 6-year house-book purge (6 years after checkout) satisfies §3g(4) ("6 let ode dne provedení posledního zápisu").
4. The neutral "Additional information" wording, including whether to also ask for evidence.
5. Counting a stay in the month of checkout.

---

## 16. Build this in this order (one commit per step; tests green after each)

| # | Step | Files | Done when |
|---|---|---|---|
| 1 | DB columns + `DOC_TYPES` | `db.py`, `validation.py` | §4 acceptance; all existing tests pass |
| 2 | `payments.py` + tests | `payments.py`, `tests/test_payments.py` | every §5 row passes |
| 3 | `stay_fee.py` core + tests | `stay_fee.py`, `tests/test_stay_fee.py` | E1–E11 pass |
| 4 | Entity bank account | `routes/admin.py` (`ENTITY_FIELDS`, create/update), `templates/entities.html`, §13.2 entity keys | the entity rows of `test_stay_fee_settings.py` pass |
| 5 | Property settings | `_apartment_payload`, `apartment_detail` context, `apartment_form.html`, §13.2 keys, `demo.py` | the property rows of `test_stay_fee_settings.py` pass |
| 6 | Guest form: doc-type select inside `#doc-wrap` + `initDocType` JS + optional row in step 1 + save + host form doc type | `routes/guest.py`, `templates/guest/form.html`, `static/signature.js`, `templates/guest/base.html` (cache-bust), `static/guest.css`, `routes/admin.py::_guest_payload`, `guest_create`, `guest_update`, `templates/guest_form_admin.html`, §13.1 + §13.3 doc keys | the **Form** rows of `test_stay_fee_guest.py` pass; manually, changing nationality flips the doc type until you touch it |
| 7 | Guest stay card (so-far line, full card, save/copy, ordering) | `stay_fee.payment_details`, `routes/guest.py` (`_stay_fee_view`, context), `templates/guest/stay.html`, `static/guest.css`, §13.1 fee keys | the **Stay page** rows of `test_stay_fee_guest.py` pass |
| 7b | Completion e-mail fee section | `stay_fee.mail_details`, `claim.py::_guest_mail_content`, `mail_notify.py::build_completion`, §13.1 `mail_fee_*` keys | the **E-mail** rows pass; `test_guest_mail.py` parity passes |
| 8 | Legal notice + privacy | `_legal_notice.html`, `privacy.html`, `privacy_notice` | the sections render only when the rate is > 0 |
| 9 | Host stay panel + two routes | `reservation_detail` context, `reservation_detail.html`, the §11.3 routes, §13.3 `stay.fee.*` keys | the host rows of `test_stay_fee_host.py` pass |
| 10 | Monthly page + CSV + sidebar + icon + palette | `stay_fee.py` helpers, `routes/admin.py`, `templates/stay_fees.html`, `base.html`, `_components.html`, §13.3 `stay_fees.*` keys | the remaining host rows pass |
| 11 | Docs | `App/README.md` "What it deliberately does not do": change the fee line to "Shows guests the local stay fee at a rate the host sets per property; does not file or check payments." | — |
| 12 | Manual check | — | On a phone (375 px), EN and CS: fill 2 of 3 forms → only the so-far line; fill the 3rd → the card appears right under the all-done card; *Save QR image* saves a PNG that a Czech banking app reads via "scan from image"; every *Copy* button copies. On desktop: the property Stay-fee panel, and the stay panel review row → Exempt → the total drops → the guest page updates. Light mode only. |

---

## 17. Sources (retrieved 2026-09-23)

| What | URL |
|---|---|
| Zákon č. 565/1990 Sb., o místních poplatcích — consolidated text from 1. 1. 2025 (§3, §3a, §3b, §3c, §3d, §3f, §3g, §16c) | https://www.mesec.cz/zakony/zakon-o-mistnich-poplatcich/uplne/ |
| Daňový řád §247a (fines up to 500 000 Kč for record-keeping duties) | https://www.mesec.cz/zakony/danovy-rad/f6835459/ |
| QR Platba — SPAYD format specification | https://qr-platba.cz/pro-vyvojare/specifikace-formatu/ |
| QR Platba — graphic manual (error-correction level M, quiet zone, "QR Platba" label) | https://qr-platba.cz/graficky-manual/ |
| ČNB — IBAN structure | https://www.cnb.cz/cs/platebni-styk/iban/ |
| Fakturoid — QR on invoices (CZ/SK only; Czech QR not readable by Slovak apps; no due date in the QR) | https://www.fakturoid.cz/podpora/faktury/qr-kod-na-fakture |
