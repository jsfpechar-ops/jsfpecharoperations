# Known issues: recent entries

Moved out of [known-issues](known-issues.md) on 2026-11-22 when that file hit its token cap, and
continued here. Same IDs; grep both files. HR (owner decides) applies here too.

**Sources:** [map](known-issue-sources.md).

- K-UI-CACHE: bump `?v=` on edits; 1y cache (0172).
- K-NAV-418: 3 host_i18n tests fail. K-CHECKIN #435, K-MORE #436 undeployed.
- K-PK0290: passkey fix open.
- K-CF01: mid-session challenge: see CLOUDFLARE Rule 3.
- K-PG-ORDER: goose tests fail after icalsync locally; CI OK.
- 0897 guest pay gaps: Slovak QR, PG 00007 unrun, no mark-as-paid, e-mail link, copy, legal sign-off.
- K-PICK: guest-enhancements.js:207 blur timer not cleared on refocus (1079).
- K-HOUSEBOOK: house book Details popover unreachable at 390/768 (zero-size trigger).
- K-FLAKY-DC: flaky `test_door_codes_safeguards` move test (test-postgres-full); OK on rerun.
- K-GUEST-DATES: es/fr guest dates row wraps at 375, 360 px.
- K-1091D: `test_1091_d` name no longer matches its test.
- K-TAP43: local only (CI green): `test_design_guardrails_browser.py` guest-new 390 "Cancel" tap target 43 < 44.
- K-H0 (1094): NULL checkin_hour TypeError door_codes ~179/436; foreign guest_id on /save; guest_form_saved audit lacks fields.
- K-MOCK-HC (1865): `mock-ubyport` in deploy/lightsail/docker-compose.yml inherits the app image HEALTHCHECK (Dockerfile:32 probes 127.0.0.1:8080/healthz) but listens on 8081 → shows unhealthy while serving. Server-side workaround on Ubyhost-test-env: untracked docker-compose.override.yml re-pointing the probe. Upstream fix: add a healthcheck block to the mock-ubyport service.
- K-STG-WAF (1865): staging.ubyhost.com inherits the ubyhost.com zone WAF → `/login` answers `cf-mitigated: challenge`; browsers pass, curl/CI logins cannot. Fix options: WAF skip rule scoped to the staging host, or a separate zone/domain for staging.
- K-SEC-TOKEN (1865): a Cloudflare API token was pasted into a chat session on 2026-11-20 → owner revokes it (Cloudflare → My Profile → API Tokens). Never paste tokens/keys into chat.
- K-PAR01 (2019 gate): `App/scripts/go_page_parity_screenshots.py` cannot run — `ModuleNotFoundError: No module named 'app'` when invoked as a script, and `TypeError: ensure_go_running() got an unexpected keyword argument 'public_base'` under `-m`. **No Go-vs-Python visual diff exists for the 2011-2018 series** because of it; 2016's screenshots were skipped for this reason. Brief 2021.
- K-PAR02 (2010 §2.4): **closed 2026-11-23 (brief 2022).** Go ports Python's claim device rule: when `UBYHOST_MAIL_BACKEND` is `console` or `ses`, `formPagesRequireClaim`, the stay hub (`stay_claim.go`), and `StayGate` require `ubyhost_claim` (`DeviceHoldsClaim`) or a host session; mail off skips the gate (same as Python). See `docs/tasks/2022-report.md`.
- K-UX-ADMIN (2019 gate): `/admin` at 390 clips a tab label to "Sy…", wraps a money KPI mid-number, renders 27+25 rows as tables with no pagination, and has 80/105/112 interaction targets under 44 px. Brief 2023.
- K-UX-BOOKSITES (2019 gate): `/booking-sites` has a row with no property name (data or template — unknown), a singular title, and four 30 px "Set up" targets. Brief 2024.
- K-UX-APT (2019 gate): `/apartments/{id}/booking-site` renders a stray unstyled property name above the chrome and a 39 px "See plans"; the guide-questions page uses the wordmark as H1 plus a second heading, a coral heading, and a third tab-bar variant. Brief 2025.
- K-UX-GUEST (2019 gate): `/guests/{id}` marks a field "(optional)" then reports "required", renders red validation errors — including a signature error — on a **clean GET**, stacks five helper lines, and has a 12×12 input. Brief 2026.
- K-UX-INK (2019 gate): `--ink-faint` (`App/app/static/tokens.css:23`) is **3.13:1 on white and 2.92:1 on canvas** — fails AA for normal text wherever helper text and fine print use it. Primary 5.51, coral links 6.90 pass. Brief 2027.
- K-UX-ADMINBRANCH (2019 gate): `/` as admin renders the **host dashboard**; there is no admin branch on `/`. Owner decision, not briefed.
- K-FLAKE-DOORMOVE (2026-11-23): `test_door_codes_safeguards.py::test_an_undeleted_old_code_after_a_move_tells_the_host` failed once on postgres full shard 2 at 00:42 Prague (`assert None`), passes 3/3 locally; dates come from `deadlines.local_now()`, likely a midnight boundary flake. Not briefed.
- K-2029-NOTPORTED (brief 2029): groups B and C in `go/internal/web/properties/` still save nothing and show interim flash `flash.error.not_saved_here` until briefs 2031 and the re-render ports land: `apartment_small_posts.go:115`, `:262`, `:545`, `:549`.
- K-BACKUP-SLOT (fixed 2026-11-23): `backup.sh`, `backup_snapshot.sh` and `deploy.sh` looked only for compose service `ubyhost-go`, so a backup refused with slot B live; now `lib-docker.sh` `ubyhost_app_service` picks the running slot, and `backup.sh` retries 3 x 20 s before it exits non-zero. Caddy keeps both slots as upstreams (stopped-slot health-check noise accepted).
- K-PY-DOORHOURS (2026-11-24): Python `door_codes._stay_checkin_label` raises TypeError when `apartment.checkin_hour` or `checkout_hour` is NULL (guest/host stay pages and door-code jobs 500). Production has 0 such ttlock apartments; Go hides the card and logs. Goes away with the all-Go deploy.
- K-STAGING-FEATURES (2026-11-24): staging lacks production's Turnstile, AI/Leon, door codes, guest PIN, guest-language list and stay-fee guest pay, so staging does not exercise those Go paths; covered by the parity gate instead. Owner declined further staging setup.
- K-GO-HCAUDIT (2026-11-25, follow-up): Go does not write `reservation_headcount_lowered`/`restored` audit rows (non-blocker).
- K-GO-MAILMISS (2026-11-25, follow-up): Go alerts on a mail whose stay ID is missing after 8 attempts instead of at once as Python does (non-blocker).
