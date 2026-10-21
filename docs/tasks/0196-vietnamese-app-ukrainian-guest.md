# 0196: Vietnamese host app, Ukrainian guest form

Status: todo
Depends on: none | Branch: claude/project-thread-979wk1
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Wire in two languages whose text already exists: Vietnamese (`vi`) for the signed-in host app only, and Ukrainian (`uk`) for the guest pages only. The orchestrator translated everything; you only connect it.

## 2. Context

- Ukrainian text: `App/app/guest_uk_i18n.py` (`STRINGS`, `ENDONYM`, `LOCALE`, `PASS_MONTHS`, `PASS_WEEKDAYS`, `ISSUE_NOTE`, `PURPOSES`, `PASSPORT_UPLOAD`, `VALIDATION`, `COOKIES`). Country names are already in `App/app/data/countries.json` under `"uk"`.
- Vietnamese text: `App/app/host_vi_i18n.py` (`STRINGS`, `LOCALE`, `WEEKDAYS`, `PURPOSES`, `CLEANING_WORDS`, `VALIDATION`, `VALIDATION_PATTERNS`). It may still be partly empty while you work; a missing key falls back to English. Never edit either data module or `countries.json`.
- Ukrainian stays behind `UBYHOST_GUEST_LANGS` like de/es/fr (WP33): add it to `LANGUAGES`, not to `ALWAYS_ON`.
- Public and legal pages stay EN/CS. Vietnamese is offered only in the app shell and on the sign-in pages.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/i18n.py | edit | add `uk` |
| App/app/validation.py | edit | `PURPOSE_LABELS` uk, vi |
| App/app/validation_i18n.py | edit | `GUEST_MESSAGES["uk"]`, `localize` vi |
| App/app/codelists.py | edit | `label_key` accepts uk |
| App/app/cookie_inventory.py | edit | uk cookie texts |
| App/app/templating.py | edit | pass dates uk, `_nights_key` lang, public pages EN for vi |
| App/app/routes/guest.py | edit | upload refusals and note issue uk |
| App/app/host_i18n.py | edit | `vi`, `PUBLIC_LANGUAGES`, `lang.vi`, `plural_key` lang |
| App/app/seo.py | edit | hreflang/sitemap use `PUBLIC_LANGUAGES` |
| App/app/cleaning_i18n.py, App/app/routes/cleaning.py | edit | vi |
| App/app/static/signature.js, App/app/static/dashboard-calendar.js | edit | locales |
| templates: `_shell_sidebar.html`, `_shell_tabbar.html`, `auth_base.html`, `_signature_script.html`, `guest/base.html`, `_dashboard_calendar.html` | edit | vi button, `?v=` bumps |
| App/tests/test_guest_languages.py, test_guest_language.py, test_wp33_gates.py, test_host_i18n.py | edit | new languages |

## 4. Steps

1. `i18n.py`: `LANGUAGES = ("en", "cs", "de", "es", "fr", "uk")`; add `"uk": guest_uk_i18n.ENDONYM` to `ENDONYMS` (import `from . import guest_uk_i18n`); right after the closing `}` of `STRINGS` add `STRINGS["uk"] = dict(guest_uk_i18n.STRINGS)`. Fix the module docstring's first line to name Ukrainian and say the host app has its own languages (`host_i18n.LANGUAGES`).
2. `validation_i18n.py`: after `GUEST_MESSAGES` add `GUEST_MESSAGES["uk"] = dict(guest_uk_i18n.VALIDATION)`. In `localize`, when `lang == "vi"`: return `host_vi_i18n.VALIDATION.get(message)`, else the first `CS_PATTERNS[i][0]` that matches formatted with `host_vi_i18n.VALIDATION_PATTERNS[i]` (only if that index exists), else `message`. Czech behaviour unchanged.
3. `validation.py`: after `PURPOSE_LABELS` add `PURPOSE_LABELS["uk"] = dict(guest_uk_i18n.PURPOSES)` and `PURPOSE_LABELS["vi"] = dict(host_vi_i18n.PURPOSES)` only when that dict is non-empty. Watch for circular imports: the data modules import nothing from `app`.
4. `codelists.py` line with `label_key = lang if lang in ("cs", "de", "es", "fr") else "en"`: add `"uk"`.
5. `cookie_inventory.py`: after the existing `for _row in COOKIE_INVENTORY:` merge loop, add a loop that sets `_row["purpose"]["uk"], _row["lifetime"]["uk"] = guest_uk_i18n.COOKIES[name]` for every row that has `"purpose"` (every such name is in `COOKIES`).
6. `templating.py`: add `"uk": guest_uk_i18n.PASS_MONTHS` / `PASS_WEEKDAYS` to `_PASS_MONTHS` / `_PASS_WEEKDAYS`. `_nights_key(count, lang="")` passes `lang` to `host_i18n.plural_key`, and `_nights_label` passes its `lang`.
7. `routes/guest.py`: `PASSPORT_UPLOAD_MESSAGES["uk"] = dict(guest_uk_i18n.PASSPORT_UPLOAD)` (after the dict) and `"uk": guest_uk_i18n.ISSUE_NOTE` inside `_GUEST_ISSUE_MESSAGES["note"]`.
8. `host_i18n.py`:
   - `LANGUAGES = ("en", "cs", "vi")`, and below it `PUBLIC_LANGUAGES = ("en", "cs")` with a one-line comment: the public and legal pages are written in these only.
   - next to `"lang.cs"` in both the en block (`"lang.cs": "CS"`) and the cs block add `"lang.vi": "VI"`.
   - at the very end of the `_CALENDAR_STRINGS` merge loop (before `def normalise_language`): `from .host_vi_i18n import STRINGS as _VI_STRINGS` then `STRINGS["vi"] = dict(_VI_STRINGS)`.
   - `plural_key(base, n, lang="")`: when `lang == "uk"`, use the Ukrainian rule (one: `n % 10 == 1 and n % 100 != 11`; few: `n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14)`; else many). Otherwise unchanged. `translate_plural` passes `lang`; Vietnamese has one form, and its `.one`/`.few` keys carry the same text, so nothing else changes.
9. `seo.py`: `alternates`, `sitemap_xml` loop over `host_i18n.PUBLIC_LANGUAGES`; in `head_links`, a requested language not in `PUBLIC_LANGUAGES` counts as none.
10. `templating.render`: right after `request.state.lang = host_i18n.resolve_language(...)`, if `request.url.path in seo.INDEXABLE_PATHS and request.url.path != "/login" and request.state.lang not in host_i18n.PUBLIC_LANGUAGES`, set `request.state.lang = "en"`. Comment: public and legal pages exist in EN and CS only.
11. Switchers: in `_shell_sidebar.html`, `_shell_tabbar.html` and `auth_base.html` add a third button after the `cs` one, same markup: `value="vi"`, `{{ 'is-active' if lang == 'vi' }}`, `{{ t('lang.vi') }}`. Leave `_public_header.html` alone.
12. Cleaning: `cleaning_i18n.translator(lang)`: for `"vi"` return `host_vi_i18n.CLEANING_WORDS.get(key) or WORDS.get(key, (key, key))[0]`. In `routes/cleaning._context`: weekdays for `vi` are `host_vi_i18n.WEEKDAYS`; `cleaning_labels` for `vi` take `CLEANING_WORDS.get(key) or pair[0]`.
13. JS: `signature.js` locales add `uk: "uk-UA"`; `dashboard-calendar.js` line 83 becomes a map `{ cs: "cs-CZ", vi: "vi-VN" }[root.dataset.lang] || "en-GB"`. Bump `?v=` for both files everywhere they are referenced in templates to `20261021-0196` (not the archive template).
14. Tests:
   - `test_guest_languages.py`: `NEW = ("de", "es", "fr", "uk")`; tuple asserts include `"uk"`; legal facts: GDPR word map `{"de": "DSGVO", "es": "RGPD", "fr": "RGPD", "uk": "GDPR"}`, six map adds `"uk": "шість"`; country test adds `("uk", "Німеччина", "Чехія")`; the host-languages test becomes `("en", "cs", "vi")` and `supported_language("uk") is None`.
   - `test_guest_language.py`, `test_wp33_gates.py`: update the tuple asserts; nothing else.
   - `test_host_i18n.py`: add tests: (a) every `vi` key exists in `en` with the same `%(name)s` placeholders, and no `vi` value is empty; (b) a signed-out GET `/` with cookie `ubyhost_lang=vi` renders `<html lang="en"`; (c) `/sitemap.xml` has no `lang=vi`; (d) POST `/language` with `lang=vi` sets the cookie to `vi` (copy the existing endpoint test's pattern); (e) `host_i18n.plural_key("night", 21, "uk") == "night.one"` and `plural_key("night", 12, "uk") == "night"`.

## 5. Do not touch

`guest_uk_i18n.py`, `host_vi_i18n.py`, `countries.json`, any other catalog text, `_public_header.html`, public/legal templates. Hard rules 3, 6, 8, 9 of AGENTS.md.

## 6. Commands

From `App/`: `.venv/bin/python -m pytest tests/test_guest_languages.py tests/test_guest_language.py tests/test_wp33_gates.py tests/test_host_i18n.py tests/test_no_em_dashes.py tests/test_guest_i18n.py -q --tb=short -x 2>&1 | tail -30` (skip a file that does not exist). Then `cd .. && python3 scripts/context_lint.py 2>&1 | tail -5`.

## 7. Acceptance

- [ ] The commands above pass.
- [ ] `git diff --stat` touches only §3 files.

## 8. Stop and ask

An anchor is missing, a circular import appears that a local import cannot fix, or a test outside §6 fails.

## 9. Report

Steps 1 to 13 landed in commits "0196 step 1" to "0196 step 13". Step 14 (tests) and the screenshots follow; the orchestrator writes the PR body.
