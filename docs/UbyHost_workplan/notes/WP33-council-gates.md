# WP33. Overdue stays in the default view, guest languages behind a switch

Patch: `series/0021-WP33-*.patch`. Stacked on 0020 (WP26). The later patches, now 0022 to 0034, apply on top of it unchanged.

Why. Council round 2 (`07_council_verdict_round2.md`) found two things that must be true before the first real host.

## What changed

- `App/app/routes/admin.py`. The default Stays view ("Upcoming & current") also lists every stay the dashboard counts as overdue and not yet reported. Before this, a stay whose deadline had passed with a guest unfiled dropped out of the list once the guests left, while the dashboard showed it as overdue. New helper `_overdue_unfinished_ids` reuses `reporting.dashboard_rows` and `FINISHED_STATUSES`, so the list and the dashboard use one rule. The "Past" and "All" views are unchanged.
- `App/app/i18n.py`. New `enabled_languages()` reads `UBYHOST_GUEST_LANGS` on every call. Default `en,cs`. English and Czech are always on. `supported_language`, and so the browser-language match, the `?lang=` link and the cookie, only accept enabled languages. A disabled language falls back to English.
- `App/app/routes/guest.py`. The language switcher lists only enabled languages.
- `App/tests/conftest.py`. The suite sets `UBYHOST_GUEST_LANGS=en,cs,de,es,fr` so every catalog stays tested.
- `deploy/lightsail/.env.example`, `docs/ENVIRONMENT.md`. The new variable.

## Tests

`App/tests/test_wp33_gates.py` (7):

- An overdue unfiled stay that arrived 10 to 20 days ago is in `/reservations`. This test fails without the `admin.py` change (checked).
- A filed stay from the same dates is not.
- The Past view shows both.
- Default languages are `en,cs`. A German browser gets English.
- `UBYHOST_GUEST_LANGS=en,cs,de` turns German on and leaves Spanish off.
- English and Czech cannot be switched off.
- The switcher offers only enabled languages.

## Owner step

When a native speaker has read a language, add it to `UBYHOST_GUEST_LANGS` in the server `.env` and restart. For example `UBYHOST_GUEST_LANGS=en,cs,de`.

## Not in this patch

The watchdog already mails the host for every stay at risk (WP23, `deadline_at_risk`). The round-2 verdict first listed that as missing. It was not.
