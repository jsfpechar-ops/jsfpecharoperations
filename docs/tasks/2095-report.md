# Report 2095: 3-layer duplicate-guest prevention, host alert & auto-filing guard

- Created `go/internal/ubyport/duplicate_guest.go` (`IsSamePerson`, `IsPossibleDuplicate`, `DuplicateGuestIDs`, ignoring `INPASS`) + tests.
- Layer 1: blocked same-person guest re-submission in `go/internal/web/guest/form_save.go` with localized inline error across all 6 guest languages.
- Layer 2: created `go/internal/calendar/duplicate_guest.go` (wired into `RunDeadlinesJob`), registered `duplicate_guest_in_stay` in `hostweb/layout/alerts.go`, `layout/i18n.json`, and `opspage/i18n.json` (zero guest PII).
- Layer 3: held higher-ID duplicate rows out of automatic `CollectSendable` in `go/internal/ubyport/collect.go` while still filing the first row on time.
- Verified green with Postgres 16 across `ubyport`, `web/guest`, `calendar`, `hostweb`, `hostweb/layout`, and `opspage`.
