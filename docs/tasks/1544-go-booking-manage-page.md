# 1544: Go guest booking page: manage and payment-details views (switched off)

Status: review
Depends on: 1543 | Base commit: none (one big PR) | Branch: the current branch
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Tier B (guest-facing, amounts, refund text, bank details). Review: Opus orchestrator reads the risk-listed files.

**One big PR mode.** Work on the current branch. Never create a branch, never push, never open a PR. Commit `1544 step k` after each step that changes a file. Acceptance checks use `git log --oneline --grep='^1544 step'`, not a fixed base commit.

## 1. Objective

Port `GET /p/{slug}/b/{booking_id}/{token}`: the guest's private booking page (status, dates, amounts, refund deadline, links) and, for a direct request that is waiting or expired, the page with the host's payment details and QR code. Together with 1351's calendar route this serves every GET under `/p/{slug}/b/...` except the two PDFs. The cancel POST and the PDFs are brief 1553 (blocked).

## 2. Context

Python mirrored (read-only, open only if a step fails): `App/app/routes/property_page.py` `_booking_or_none` 475-485, `_manage_lang` 488-492, `_manage_throttle` 495-500, `booking_manage_page` 503-533; `App/app/booking_manage.py` `mask_email` 12-14, `day_label` 17-19, `deadline_label` 22-34, `view` 37-74, `VISIBLE` 9; `App/app/booking_cancel.py` `refund_now` 22-25, `started` 28-30; `App/app/booking_site.py` `check_in_moment` 219-221, `refund_czk` 224-244 (the Go `RefundCZK` of 1351 is golden-tested against it); templates `booking_manage.html`, `property_page_requested.html`.

Parity table:

| Go | Python | Lines | Test with fixed numbers |
|---|---|---|---|
| `ManageHandler` | `booking_manage_page` | 503-533 | booking 501 (paid, moderate, 10 Dec 2026, check-in 15:00), clock 28 Nov 2026 10:00 UTC |
| `BuildManageView` | `view` | 37-74 | total 6 500, refund now 6 500 (more than 5 days left), city tax 50 x 2 x 3 = 300, state `paid` |
| `DeadlineLabel` | `deadline_label` | 22-34 | moderate: `5. 12. 2026 15:00` (cs), flexible: `2026-12-09 15:00`, non refundable: empty; DST day 26 Oct 2026 uses the wall clock |
| `Started` | `started` | 28-30 | check-in 15:00 Prague has started at 14:00 UTC, not one second earlier |
| `BookingForToken` | `_booking_or_none` | 475-485 | wrong token, pending booking, unknown id, another booking's token: all 404 |
| requested view | `property_page_requested.html` | | IBAN grouped, QR image, Revolut link, cash note, expired text |

Money: no amount is computed here except the two numbers above, both through code already pinned to Python (`RefundCZK`, `LoadSettings`). The refund line is shown only when the guest can still cancel (paid card booking, check-in not started).

Behaviour copied on purpose: rate limit 120 per hour per client on scope `booking_manage` (shared with the stay calendar, as in Python); the language is `?lang`, then the booking's own language, then Czech; `?e=` shows only `started`, `busy` and `refund_failed`; the page is `no-store` and `noindex`; the cancel form posts to `/p/{slug}/b/{id}/{token}/cancel` (Python until 1553).

Known differences (accepted): a non-numeric booking id is 404 (FastAPI 422); the e-mail shown is masked (`a***@domain`); a guest e-mail of NULL shows nothing; the invoice and correction links are only tested through the view flags (no invoice rows in the fixture), their query is `SELECT id FROM invoice WHERE corrects_invoice_id = $1`; the shell sets no CSRF cookie (1540).

No outbound request, no new personal data, no schema change.

**Paths fully served by Go after this brief:** `/p/{slug}/b/{booking_id}/{token}` (GET only) and, from 1351, `/p/{slug}/b/{booking_id}/{token}/calendar.ics`. Not fully Go: `/p/{slug}/b/{id}/{token}/cancel`, `invoice.pdf`, `correction.pdf` (Python, brief 1553).

**Goes live on deploy:** nothing unless `UBYHOST_GO_PATHS` already holds `/p/*`-style entries. I assumed it holds only `/p/*/*.ics`, `/p/*/b/*/*/calendar.ics` and `/photos/property/*` from 1351. A `/p/*/b/*/*` entry would send this page to Go the moment it deploys; that is intended once 1550's checks pass.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/cmd/ubyhost-web/register_web_booking_manage.go` | create (23 lines) | new file, copied from the sidecar |
| `go/internal/web/booking/manage.go` | create (287 lines) | new file, copied from the sidecar |
| `go/internal/web/booking/manage_test.go` | create (169 lines) | new file, copied from the sidecar |
| `go/internal/web/booking/templates/manage.tmpl` | create (51 lines) | new file, copied from the sidecar |
| `go/internal/web/booking/templates/requested.tmpl` | create (24 lines) | new file, copied from the sidecar |

No other file may change.

## 4. Steps

### Step 1: copy the files

From the repo root:

```bash
mkdir -p go/cmd/ubyhost-web && cp docs/tasks/1544-files/go/cmd/ubyhost-web/register_web_booking_manage.go.txt go/cmd/ubyhost-web/register_web_booking_manage.go
mkdir -p go/internal/web/booking && cp docs/tasks/1544-files/go/internal/web/booking/manage.go.txt go/internal/web/booking/manage.go
mkdir -p go/internal/web/booking && cp docs/tasks/1544-files/go/internal/web/booking/manage_test.go.txt go/internal/web/booking/manage_test.go
mkdir -p go/internal/web/booking/templates && cp docs/tasks/1544-files/go/internal/web/booking/templates/manage.tmpl.txt go/internal/web/booking/templates/manage.tmpl
mkdir -p go/internal/web/booking/templates && cp docs/tasks/1544-files/go/internal/web/booking/templates/requested.tmpl.txt go/internal/web/booking/templates/requested.tmpl
```

Expected: no output. Commit `1544 step 1`.

### Step 2: check the files and the string catalog

```bash
sha256sum -c <<'EOT' 2>&1 | tail -10
8cdeb09f2ecda73e5c51d65e0878edefd24128cef9f84cdc237f7f0669378a33  go/cmd/ubyhost-web/register_web_booking_manage.go
6407d591863c666a92f4a193fe62357d2cc73174ad30d6c5d6ab6109ee78c892  go/internal/web/booking/manage.go
bb021bbc3bd3c8db407703be680a77b60d21c5a25fb7485282a0a8f1a641d70d  go/internal/web/booking/manage_test.go
c26d93533884bd13fc8e5af78b8d6cbd6302b6a74c12871bcac432dc96009f6f  go/internal/web/booking/templates/manage.tmpl
d79d449d0a8f342f5b429fef5b95f12cc3210669286b4679da628d05c2bbbce3  go/internal/web/booking/templates/requested.tmpl
EOT
cd App && .venv/bin/python scripts/go_host_i18n.py --check 2>&1 | tail -3
```

Expected: every line `OK`; the catalog check prints nothing (1540 lists `bk.*` and `stay_fees.guest_pay.rail.*`). Stale catalog: STOP.

### Step 3: build, vet, format

```bash
cd go && go build ./... 2>&1 | tail -10 && go vet ./internal/web/booking/ ./cmd/ubyhost-web/ 2>&1 | tail -10 && gofmt -l internal cmd 2>&1 | tail -5
```

Expected: no output.

### Step 4: tests (section 6), then the report (section 9).

## 5. Do not touch

Everything outside section 3. Hard rules: no new dependency; never push to `main`; no secrets; no tracking cookie; never log guest data.

## 6. Commands

```bash
cd go && go test -count=1 ./internal/web/booking/ ./cmd/ubyhost-web/ 2>&1 | tail -10
```

Expected: `ok` for both. The new tests need PostgreSQL (`UBYHOST_TEST_DATABASE_URL`; CI sets it); without it they skip. Say in the report which you ran.

## 7. Acceptance

- [ ] Step 2 printed only `OK`.
- [ ] `git log --oneline --grep='^1544 step' | tail -5` shows step 1; `git show --stat --format=%s $(git log --grep='^1544 step 1' --format=%h -1) | tail -12` lists only section 3 paths.
- [ ] Both section 6 packages print `ok`, with the database variable set.
- [ ] `grep -c 'registerRoutes' go/cmd/ubyhost-web/register_web_booking_manage.go` prints 1.
- [ ] Screenshots: taken in brief 1550 before any switch.

## 8. Stop and ask

Stop, and write the report, if: a hash differs twice; a test fails twice; you reach 25 tool calls or about 50k tokens (report as `blocked`); a new dependency seems needed; a file outside section 3 needs a change; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/1544-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with its last 5 lines, section 7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

- `go/internal/web/booking/manage.go`: `BookingForToken` (the signed token is the only access check; which statuses are visible), `BuildManageView` (refund and deadline text), `ManageHandler` (rate limit, headers, the direct branch that shows bank details).
- `go/internal/web/booking/templates/requested.tmpl`: the inline QR (`dataURI` is only fed our own PNG).

## Owner steps

1. Nothing changes in production when this merges. Brief 1550 gives the switch order.
