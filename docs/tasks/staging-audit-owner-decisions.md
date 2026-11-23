# Staging audit: owner decisions (2026-11-22)

Briefs: 2030 and 2031 merged (#1273 and the guest CSRF PR); 2032 in docs/tasks. The rest is intended behaviour or config, no executor work.
Not defects (intended or config):

- `/dashboard/calendar` without `from`/`to` is 422 `invalid_range` in Python too (`App/app/routes/dashboard_calendar.py:110-122`); Go matches. Callers must send the range. Close as intended.
- `/signup` 404: Go returns 404 when `UBYHOST_SIGNUP_ENABLED` is off (`go/internal/web/auth/signup_pages.go:122`); `.env.example` default is 0. Decision: turn signup on for staging so the signup mail kinds can be audited (`UBYHOST_SIGNUP_ENABLED=1`), and decide when it is on in production.
- `/admin/exports` and `/exports` 404: Python never had these routes; exports are per-resource (`/reservations.csv`, `/guests/{id}/form.pdf`, `/guests/{id}/export.json`, `App/app/routes/exports.py`). Close as intended; no index page is planned.
- Guest `?lang=vi`: `UBYHOST_GUEST_LANGS` defaults to `en,cs` (`go/internal/web/guest/shell.go:65`) and `.env.example` sets `en,cs`; before #1263 the Go container did not even receive the variable. Decision: is Vietnamese a guest language? If yes, add `vi` to `UBYHOST_GUEST_LANGS` after the guest catalog has `vi` strings (shell.go notes the catalog has none); if no, leave it.
- Staging `/` shows the dashboard: `UBYHOST_STAGING_NO_LOGIN`, expected.
