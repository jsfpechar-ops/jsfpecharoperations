# 0387: Completion mail shows the stay at a glance

Status: todo
Depends on: none | Base commit: 4e17592 | Branch: claude/project-thread-j8pnyp (already checked out, commit here)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

The "You're all set" receipt (guest gets it, host is CC'd) gains a small bordered "Your stay" panel: guests registered ("3 of 3"), check-in, check-out and the property address, so nobody has to open the app to check. The long raw stay URL is replaced by a short underlined "See your stay page" link (owner: "the stay link is a bit weird for guests"). The dates leave the intro sentence because the panel now carries them.

Privacy: no guest names, ID numbers or birth dates. Only counts and property data.

## 2. Context

- `App/app/mail_notify.py` `build_completion` (around line 1613) builds the HTML and text parts. `_block_panel(title, rows)` (line ~298) is the bordered label/value sub-card the invoice mail uses. `_block_quiet_link(url, label)` (line ~374) is a labelled underlined link with no raw URL.
- `App/app/claim.py` `_guest_mail_content` (line ~337) calls `build_completion`; it already takes `filled` and `expected`. `maybe_notify_completion` (line ~649) has `progress["filled"]` and `expected` but does not pass them.
- Apartment columns: `checkin_hour`, `checkout_hour` (INTEGER, may be NULL), `addr_street`, `addr_house_no`, `addr_obec` (may be NULL). Row may be a dict without these keys in tests: never let a missing key break the mail.
- Guest catalogues: `App/app/i18n.py` `STRINGS` for en, cs, de, es, fr; `App/app/guest_uk_i18n.py` for uk. Each has a `"mail_completion_note"` entry; add the new keys right after it.
- No em dashes in copy.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/i18n.py | edit | intro without dates (5 langs), 8 new keys (5 langs) |
| App/app/guest_uk_i18n.py | edit | same for uk |
| App/app/mail_notify.py | edit | `build_completion`: panel + quiet link |
| App/app/claim.py | edit | `_completion_facts` helper, pass facts and counts |
| App/tests/test_guest_mail.py | edit | update 2 tests, add 2 tests, extend `NEW_GUEST_KEYS` |
| docs/tasks/0387-report.md | new | report |
| docs/tasks/screenshots-0387/ | new | preview PNGs |

No other file may change, except a test that fails only because the intro lost its dates (§8: fix once, list it under Deviations).

## 4. Steps

### Step 1: catalogue strings

In every `"mail_completion_intro"` value (en, cs, de, es, fr in i18n.py; uk in guest_uk_i18n.py) delete the substring ` (%(dates)s)` (space included). Nothing else in those values changes.

After each language's `"mail_completion_note"` entry add these keys (values below, `%(...)s` placeholders exact):

| key | en | cs | de | es | fr | uk |
|---|---|---|---|---|---|---|
| mail_completion_panel_title | Your stay | Váš pobyt | Ihr Aufenthalt | Su estancia | Votre séjour | Ваше проживання |
| mail_completion_guests_label | Guests registered | Registrovaní hosté | Registrierte Gäste | Huéspedes registrados | Voyageurs enregistrés | Зареєстровано гостей |
| mail_completion_guests_value | %(filled)s of %(expected)s | %(filled)s z %(expected)s | %(filled)s von %(expected)s | %(filled)s de %(expected)s | %(filled)s sur %(expected)s | %(filled)s з %(expected)s |
| mail_completion_checkin_label | Check-in | Příjezd | Check-in | Llegada | Arrivée | Заселення |
| mail_completion_checkin_value | %(date)s, from %(time)s | %(date)s od %(time)s | %(date)s ab %(time)s | %(date)s, desde las %(time)s | %(date)s, à partir de %(time)s | %(date)s, з %(time)s |
| mail_completion_checkout_label | Check-out | Odjezd | Check-out | Salida | Départ | Виселення |
| mail_completion_checkout_value | %(date)s, by %(time)s | %(date)s do %(time)s | %(date)s bis %(time)s | %(date)s, antes de las %(time)s | %(date)s, avant %(time)s | %(date)s, до %(time)s |
| mail_completion_address_label | Address | Adresa | Adresse | Dirección | Adresse | Адреса |

Command: `cd App && .venv/bin/python -m pytest tests/test_guest_languages.py -q --tb=short -x 2>&1 | tail -30`

### Step 2: `build_completion` in mail_notify.py

Add keyword params after `door_code`:

```python
    filled: Optional[int] = None,
    expected: Optional[int] = None,
    checkin: str = "",
    checkout: str = "",
    address: str = "",
```

Right after `text_lines = [intro]` insert:

```python
    # The stay at a glance, so neither the guest nor the copied host has to
    # open the app to check. Counts and property facts only, never a guest's
    # name or document.
    rows: List[Tuple[str, str]] = []
    if expected:
        rows.append((
            _guest_text(lang, "mail_completion_guests_label"),
            _guest_text(
                lang, "mail_completion_guests_value", filled=filled or 0, expected=expected
            ),
        ))
    if checkin:
        rows.append((_guest_text(lang, "mail_completion_checkin_label"), checkin))
    if checkout:
        rows.append((_guest_text(lang, "mail_completion_checkout_label"), checkout))
    if address:
        rows.append((_guest_text(lang, "mail_completion_address_label"), address))
    if rows:
        blocks.append(_block_panel(_guest_text(lang, "mail_completion_panel_title"), rows))
        text_lines.extend(["", *(f"{label}: {value}" for label, value in rows)])
```

Replace `blocks.append(_block_link(stay_url, action))` with `blocks.append(_block_quiet_link(stay_url, action))`. Keep the text-part line `f"{action}: {stay_url}"` as is. In the docstring, add one sentence: "The stay link is a labelled link, not a printed address: the URL is long and means nothing to a guest."

### Step 3: claim.py

Add this helper directly above `def _guest_mail_content(`:

```python
def _completion_facts(apartment, reservation, lang: str) -> Dict[str, str]:
    """Check-in, check-out and address for the receipt's stay panel.

    Each is optional: a property without hours or an address still gets its
    receipt, with fewer rows. Any read failure drops the facts, never the mail.
    """
    t = i18n.translator(lang)

    def col(row, name):
        try:
            return row[name]
        except (KeyError, IndexError, TypeError):
            return None

    def moment(day, hour, key):
        shown = validation.fmt_date(day) or ""
        if not shown or hour is None or hour == "":
            return shown
        return t(key, date=shown, time=f"{int(hour):02d}:00")

    try:
        street = " ".join(
            str(part).strip()
            for part in (col(apartment, "addr_street"), col(apartment, "addr_house_no"))
            if part and str(part).strip()
        )
        town = (col(apartment, "addr_obec") or "").strip()
        return {
            "checkin": moment(
                reservation["date_from"], col(apartment, "checkin_hour"),
                "mail_completion_checkin_value",
            ),
            "checkout": moment(
                reservation["date_to"], col(apartment, "checkout_hour"),
                "mail_completion_checkout_value",
            ),
            "address": ", ".join(part for part in (street, town) if part),
        }
    except Exception:
        return {}
```

In `_guest_mail_content`, the `if kind == "completion":` call to `mail_notify.build_completion(` gains:

```python
                filled=filled,
                expected=expected,
                **_completion_facts(apartment, reservation, lang),
```

In `maybe_notify_completion`, the `_guest_mail_content("completion", ...)` call gains `filled=progress["filled"],` and `expected=expected,`.

Command: `cd App && .venv/bin/python -m pytest tests/test_claim_mail.py tests/test_claim_fallback_text.py tests/test_claim_resend_complete.py -q --tb=short -x 2>&1 | tail -30`

### Step 4: tests in test_guest_mail.py

1. Add the 8 new keys to `NEW_GUEST_KEYS`.
2. `test_the_completion_mail_links_to_the_stay`: replace the `>{stay}</a>` assertion and its comment with `assert f'href="{stay}"' in content["html"]` and `assert f">{stay}</a>" not in content["html"]` (comment: the URL is a link target, not printed text; the text part still carries it).
3. `test_the_completion_mail_closes_with_nothing_left_to_do`: remove ` (2026-01-05 – 2026-01-08)` from both expected intros.
4. New test `test_the_completion_mail_shows_the_stay_at_a_glance`: call `mail_notify.build_completion` like `_completion_content` plus `filled=3, expected=3, checkin="05.01.2026, from 15:00", checkout="08.01.2026, by 10:00", address="Dlouhá 12, Praha"`; assert in `html.unescape(content["html"])` and in `content["text"]`: "Your stay", "Guests registered", "3 of 3", "05.01.2026, from 15:00", "Dlouhá 12, Praha". Repeat for `lang="cs"` asserting "Váš pobyt" and "3 z 3".
5. New test `test_the_completion_mail_without_facts_has_no_panel`: `_completion_content()` html does not contain "Your stay".

Command: `cd App && .venv/bin/python -m pytest tests/test_guest_mail.py tests/test_guest_languages.py tests/test_property_names_in_mail.py tests/test_mail_side_padding.py -q --tb=short -x 2>&1 | tail -30`

### Step 5: preview screenshots

Write a throwaway script outside the repo (`/tmp/claude-0/preview_0387.py`, not committed) that, from `App/`, imports `app.mail_notify`, calls `build_completion` for `en`, `cs` and `uk` with `property_name="Downtown Comfort in a Spacious Apartment"`, `dates="23.10.2026 – 26.10.2026"`, `stay_url="https://ubyhost.com/l/demo/17"`, `host={"name": "Demo Host", "email": "host@example.com", "phone": "+420 777 000 000"}`, `filled=3, expected=3`, check-in/out built with the step 1 value strings (23.10.2026 15:00, 26.10.2026 10:00) and `address="Dlouhá 12, Praha"`. Write each HTML to `docs/tasks/screenshots-0387/completion-<lang>.html` and screenshot it with Playwright chromium at 390 px wide, full page, to `docs/tasks/screenshots-0387/completion-<lang>-390.png`. Commit the PNGs only (delete the .html files). Look at each once.

### Step 6: context lint

`python3 scripts/context_lint.py 2>&1 | tail -30`

## 5. Do not touch

Other mails, `_block_link` itself, `_guest_fallback_text`, templates, CSS, migrations. No push, no PR (orchestrator does it). No new dependency.

## 6. Commands

Only the commands in steps 1, 3, 4 and 6.

## 7. Acceptance

- [ ] All step commands pass.
- [ ] Completion HTML has no printed stay URL; text part still has it.
- [ ] Panel shows count, check-in, check-out, address in en/cs/uk previews.
- [ ] 3 PNGs in docs/tasks/screenshots-0387/.

## 8. Stop and ask

As in TEMPLATE.md: excerpt not found, a test fails twice, 25 tool calls, file outside §3 (except the dates-in-intro test noted in §3).

## 9. Report

`docs/tasks/0387-report.md`, 600 tokens at most, as TEMPLATE.md §9. Commit each step as `0387 step k`.

## Risk list (for the reviewer)

App/app/claim.py, App/app/mail_notify.py.

## Owner steps

1. Review the draft PR and the screenshots, then merge with `scripts/merge-pr-on-green.sh`.
2. Deploy as usual.

## Addendum A (owner, 2026-10-25): the link is for the host, not the guest

Owner: "See your stay (for host) maybe? So the guest won't click it." The receipt goes to the guest with the host CC'd. The guest stay link leaves the mail; in its place a host-only link to the stay in the app. A guest who taps it only reaches the sign-in page.

Files: App/app/i18n.py, App/app/guest_uk_i18n.py, App/app/mail_notify.py, App/app/claim.py, App/tests/test_guest_mail.py, the 3 previews. Nothing else.

### Step A1: catalogue

Remove the `mail_completion_address_label` entry from every language (step A6 drops the address row). After each language's `"mail_completion_checkout_value"` entry add `mail_completion_host_action`:
en `For your host: open this stay in UbyHost` · cs `Pro hostitele: otevřít pobyt v UbyHost` · de `Für Ihren Gastgeber: Aufenthalt in UbyHost öffnen` · es `Para su anfitrión: abrir la estancia en UbyHost` · fr `Pour votre hôte : ouvrir le séjour dans UbyHost` · uk `Для господаря: відкрити проживання в UbyHost`.
Keep `mail_completion_action` in the catalogues (the plain-text fallback in claim.py still uses it).

### Step A2: `build_completion`

Add keyword param `host_url: str = ""` after `address` (step A6 then removes `address`). Replace the "Slot 2" block (the `_block_quiet_link(stay_url, action)` line and the `text_lines.extend(["", f"{action}: {stay_url}"])` line) with:

```python
    # Slot 2: one quiet link, for the copied host only. The guest's own stay
    # page is already open on the device that registered; a second guest
    # link here only invited a tap with nothing behind it.
    if host_url:
        host_action = _guest_text(lang, "mail_completion_host_action")
        blocks.append(_block_quiet_link(host_url, host_action))
        text_lines.extend(["", f"{host_action}: {host_url}"])
```

Delete the now unused `action = _guest_text(lang, "mail_completion_action")` line. Keep the `stay_url` parameter (callers pass it) but it is no longer printed; change the docstring sentence about the stay link to: "The only link is for the copied host and opens the stay in the app; the guest gets no link, because their stay page is already on their device."

### Step A3: claim.py

In `_guest_mail_content`'s `build_completion(` call add
`host_url=f"{config.app_base_url()}/reservations/{reservation['id']}",`.
(`config` is already imported in claim.py.)

### Step A4: tests (test_guest_mail.py)

- Add `"mail_completion_host_action"` to `NEW_GUEST_KEYS`.
- `test_the_completion_mail_links_to_the_stay`: rename to `test_the_completion_mail_links_only_the_host`; build with `host_url="https://app.example.test/reservations/1"`; assert that URL is in html and text, "For your host: open this stay in UbyHost" is in both, and the guest stay URL (`/l/{TOKEN}/1`) is in neither.
- `test_the_completion_mail_closes_with_nothing_left_to_do`: drop the `action` assertions (keep the tuple shape or remove the field, your choice, but keep every other assertion).

Commands: `cd App && .venv/bin/python -m pytest tests/test_guest_mail.py tests/test_guest_languages.py tests/test_property_names_in_mail.py tests/test_mail_side_padding.py tests/test_claim_mail.py tests/test_claim_fallback_text.py tests/test_claim_resend_complete.py -q --tb=short 2>&1 | tail -30`

### Step A6: no address row (owner: "No need for address, there's already property name")

- mail_notify.py `build_completion`: remove the `address` parameter and the `if address:` row.
- claim.py `_completion_facts`: remove the `street` and `town` lines and the `"address"` key; docstring first line becomes "Check-in and check-out for the receipt's stay panel."
- test_guest_mail.py: remove `mail_completion_address_label` from `NEW_GUEST_KEYS`; the at-a-glance test no longer passes or asserts an address, and asserts "Address" is not in the html.

### Step A5: previews

Re-render the 3 previews as in step 5, adding `host_url="https://app.ubyhost.com/reservations/17"` and without `address` (uk with uk enabled). Commit as `0387 addendum A`. Append a 3-line "Addendum A" section to the report.

## Addendum B (owner, 2026-10-25)

Host link label is now "See your stay page (host only)" in six languages (owner):

- en: See your stay page (host only)
- cs: Zobrazit stránku pobytu (jen pro hostitele)
- de: Zur Aufenthaltsseite (nur für Gastgeber)
- es: Ver la página de su estancia (solo anfitrión)
- fr: Voir la page du séjour (hôte uniquement)
- uk: Переглянути сторінку проживання (лише для господаря)
