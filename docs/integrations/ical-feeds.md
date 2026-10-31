# Integration: iCal calendar feeds

**Purpose:** import reservations (stays) from host booking calendars so that
registration deadlines can be computed. Calendars are read; nothing is written
back.

| Item | Value | Source |
|---|---|---|
| Protocol | HTTP(S) GET of an `.ics` URL, parsed with `icalendar` 7.3.0 | `App/requirements.txt`, `App/app/icalsync.py` |
| Base URL | per feed; stored per apartment in table `ical_feed` | `App/app/db.py:180` |
| Auth | none beyond the feed URL itself (the URL is the secret). `⚠️ UNKNOWN` whether any provider requires token-in-URL rotation | `App/app/feed_fetch.py` |
| Providers | `⚠️ UNKNOWN` — code mentions `airbnb.com` and `booking.com` (`App/app/*.py` grep); not confirmed as iCal sources. Read `App/app/icalsync.py` and `App/app/guide_i18n.py` context to confirm. | — |
| Size limit | 5 MiB (`MAX_FEED_BYTES`) | `App/app/feed_fetch.py:27` |
| Redirects | max 3 | `App/app/feed_fetch.py:30` |
| Private addresses | blocked unless `UBYHOST_ICAL_ALLOW_PRIVATE=1` (SSRF guard) | `App/app/config.py:452` |
| Timeouts | custom socket/urllib3 connection timeout | `App/app/feed_fetch.py:67-110` |
| Polling | every `UBYHOST_ICAL_POLL_MINUTES` (default 60), first run ~20 s after boot | `App/app/config.py:148`, `scheduler.py` (`ical`) |
| Open-sync | `UBYHOST_ICAL_OPEN_SYNC_MINUTES` (default 10) | `App/app/config.py:150` |
| Sandbox | `⚠️ UNKNOWN`; a test feed is `App/app/sample_calendar.py` | — |
| Retry | `⚠️ UNKNOWN` — internal retry policy of `icalsync` not read in full | — |
| Idempotency | reservation identity by UID; duplicates and recurrences: first occurrence only (`feed_duplicate_uid`, `feed_recurring_event`) | `docs/OPERATIONS.md § Scheduled jobs` |

Behaviour (from `docs/OPERATIONS.md`, consistent with the code paths listed):
- Recurrences (`RRULE`, `RDATE`, `EXDATE`) are **not** expanded — deliberate, so that no unconfirmed deadline is invented.
- Block-like summaries are skipped when new.
- Conditional fetch validators: `feed_fetch.py:47` limits validator length to 256.

Code: `App/app/icalsync.py`, `App/app/feed_fetch.py`, `App/app/feed_url.py`
(URL validation), `App/app/routes/` calendar-sync routes (`test_calendar_sync_ui.py`
exists in `App/tests/`).

## Official references

- Feed format: RFC 5545 https://datatracker.ietf.org/doc/rfc5545/ (see [REFERENCES](REFERENCES.md)).
