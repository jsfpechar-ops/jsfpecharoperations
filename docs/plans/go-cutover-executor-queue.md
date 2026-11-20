# Go cutover — executor queue

Written 2026-11-19 for Josef’s “everything on Go” push. Plans: [go-sqlite-final](../plans/go-sqlite-final.md) (phases 0–4), [python-retirement-plan](../plans/python-retirement-plan.md), [go-cutover-runbook](../plans/go-cutover-runbook.md) §5–6 (what still stays Python; [go-full-move-remaining](../plans/go-full-move-remaining.md) route gaps). Prod snapshot: 2026-11-19 ([status](../context/status.md) Production).

---

## Runnable now

One Haiku brief at a time on current `main`; read [executor](../context/executor.md). Do **not** edit `UBYHOST_GO_PATHS` in the repo.

| Brief | Why runnable |
|---|---|
| **[1730](../tasks/1730-go-submissions-reservations-read.md)** | Shrunk submissions/reservations **read** (list scope superseded by 1855–1858). Exact-diff sidecar on main: `docs/tasks/1730-files/`. |
| **[0852](../tasks/0852-fix-725-regressions.md)** | PR #725 regressions and v2 mockup baselines — start only if still open on main. |

**Shipped — rerun brief only to chase a regression** (do not treat as greenfield port work):

| Brief | Note |
|---|---|
| **[1793](../tasks/1793-cleaning-code-run-at-once.md)** | Merged **PR #1047**; re-execute the Haiku brief only if TTLock immediate kick or visible delete regresses. |

**Blocked until exact-diff sidecars exist** (`docs/tasks/NNNN-files/`, sha256 table, anchors per [workflow](../context/workflow.md#writing-briefs-for-haiku)):

| Brief | Sidecar dir (missing on main) |
|---|---|
| **[1770](../tasks/1770-go-mail-job.md)** | `docs/tasks/1770-files/` |

Same rule for most other **17xx** briefs marked “Executable only after its exact-diff pass”. Prefer this section over ad-hoc picks.

---

## Production already on Go (2026-11-19)

| Item | State |
|---|---|
| **Deploy** | `HEAD` = `origin/main` (`a734a72f`); last deploy exit 0 |
| **Go service** | `ubyhost-go` healthy; Postgres goose 22, schema **v45**, 75 tables; `UBYHOST_SCHEMA_APPLY=go` |
| **`UBYHOST_GO_PATHS`** | **104 tokens** — runbook waves largely applied: public legal, billing, login/passkeys, partial stay-fees **downloads**, partial invoices, guide/Havel/Leon, onboarding/dismissals, property **read** slices, cleaning partial, etc. |
| **Stays** | **`GET/POST /reservations`** (list) → **Go** (303 when logged out). **`/reservations/{id}*`**, archive POST, **submit** → **Python** |
| **Still Python (routing)** | Full **`/stay-fees/*` seal** (`finalize`, `confirm-ready`), guest **`/l/*`**, property **forms** (`POST /apartments`, detail save, many `POST /apartments/*`), filing **submit** buttons |
| **Jobs** | Go queues most kinds; **mail** + **door_codes** still Python worker (1770/1771 open) |
| **Owner UX** | Logged-in Stays list on Go: browser pass **outstanding**; possible raw i18n on mid-onboarding (`onboarding.skip` / `setup.banner.*`) — confirm in browser |

---

## In flight before the 17xx backlog

| Briefs | Role |
|---|---|
| **[1855–1858](../tasks)** | Go **Stays list** port (`go/internal/web/stays`); owner adds exact `/reservations` (prod **done** 11-19). Finish merge, parity goldens, UX gate, 0-skipped browser rows |
| **[1859](../tasks/1859-hide-payments-booking-python.md)** | Python half **merged** (#1095). **Do not set `UBYHOST_PAYMENTS_HIDDEN=1` on prod** until **Go half** 404-gates `/payments*` (prod routes those paths via Go today; booking-site paths already Python-only). Interim: drop `/payments*` from `UBYHOST_GO_PATHS` only if owner accepts tier flip. |
| **1860–1864** | **Reserved Stays lane** (no `docs/tasks/186*.md` on `main` yet). Project rule: **do not add `/reservations/*`** to Caddy until **[1863](../tasks)** (owner path wave). Writer should map numbers to: list hardening, submissions read, stay detail GET, prefix switch, create/quick-edit POSTs — or fold into shrunk **1730** / **1731** |

---

## Executor order (after 1860–1864)

One Haiku brief at a time; respect [go-sqlite-final](../plans/go-sqlite-final.md) file-conflict chains. **Phase 0** items can start in parallel where noted.

### Gate and retirement prep (Phase 0)

| Order | Briefs | Notes |
|---|---|---|
| 1 | **[1790](../tasks/1790-route-completeness-gate.md)** | CI allow-list of Python-only routes — run early; shrinks every later brief |
| 2 | **[1780](../tasks/1780-go-ops-scripts-subcommands.md)**, **[1781](../tasks/1781-stripe-webhook-path-decision.md)** | Backups/deploy off Python; Stripe path stays off paths until decided |
| 3 | **1474, 1475** | SQLite schema authority (plan §5) |
| 4 | **1750**, **1775** | Utility routes; invoice mail builder (unblocks 1776) |

### Stays / submissions (Phase 2 — **1730 overlap**)

**Overlap:** [1730](../tasks/1730-go-submissions-reservations-read.md) lists **GET `/reservations`** and list parity — **superseded by 1855–1858**. After 1860–1864, run 1730 **only for** `GET /submissions`, `GET /submissions/{id}`, **`GET /reservations/{id}`** (or split briefs). Exact-diff pass must drop duplicate list scope. Sidecar **`docs/tasks/1730-files/`** is on main — **runnable** (see top section).

| Chain | Briefs |
|---|---|
| Stays read + writes | **1730** (shrunk) → **[1731](../tasks/1731-go-reservation-edit-posts.md)** → **[1732](../tasks/1732-go-claim-filed-by-hand.md)** |
| Host guest edit | **1733** on main; **1734** / **1735** / **1737** exact-diff sidecars ready 2026-11-20 → **[1737](../tasks/1737-go-stays-completeness-wave.md)** (wave H; **submit** routes wait for **1741**) |
| Dashboard | **[1751](../tasks/1751-go-dashboard.md)** after shrunk 1730 |

### Cleaning gaps

Go has schedule/share (1310) and host shell (1570 review); **11 routes** still missing per [go-full-move-remaining](../plans/go-full-move-remaining.md) §2.

| Order | Briefs |
|---|---|
| 1 | **[1793](../tasks/1793-cleaning-code-run-at-once.md)** — shipped **#1047**; brief **rerun-only** for regression |
| 2 | **1570** → **[1571](../tasks/1571-go-cleaning-event-save.md)** → **[1572](../tasks/1572-go-cleaning-settings-shares.md)** → **[1573](../tasks/1573-go-cleaning-door-codes.md)** |
| 3 | Owner **cleaning** path wave after 1573 + completeness test (mirror 1737 pattern) |

### Property chain P (Phase 1)

**1700** → **1701** → **1702** → **1702b** → **1702c** → **1702d** → **1702e** (+ **1702e1–3**) → **[1703](../tasks/1703-go-apartment-small-posts.md)** → **1704** → **[1705](../tasks/1705-go-property-settings-switch.md)** (wave P checklist). **1706** → **[1707](../tasks/1707-go-smart-locks-routes.md)** in parallel after **1704** (TTLock).

### Filing F (Phase 3 — owner sign-off each switch)

**[1740](../tasks/1740-go-filing-f1-send-endpoint.md)** → **[1742](../tasks/1742-go-filing-soak-check.md)** (1 week) → **[1741](../tasks/1741-go-filing-f2-buttons.md)**. No guest wave G path switch until **1741** soaked.

### Guest chain G (Phase 3, paths last)

**1720** → **1721** → **1722** → **1723** → **1724** → **1725** → **1726** → **[1728](../tasks/1728-go-guest-completeness-wave.md)**. **1720** can build early (1713 needs language port); **`/l/*` off paths** until F2 sign-off.

### Jobs + booking + invoices (parallel lanes)

- **1770** mail job → **1771** door_codes → **1772** scheduler Block S → **1773** retention/stay_fee_mail enable (owner checklist). **1770 blocked** until `docs/tasks/1770-files/`.
- **1710** → **1711** → **1712** → **1713** → **1714** (booking; many paths blocked while Payments hidden)
- **1776** after **1775** + **1429**

### Retire Python (Phase 4)

**[1782](../tasks/1782-go-caddy-everything-to-go.md)** after **every wave** + **1772** + quiet week → **1479** with **1782** (delete `App/`). SQLite **1476–1480** per [sqlite-retirement](../plans/sqlite-retirement.md).

---

## Owner `UBYHOST_GO_PATHS` — safe now vs blocked

| Safe to add now (if token missing; runbook waves **1, 1b, 2, 2b, 6** and other **read-only** slices) | **Do not add** until brief / gate |
|---|---|
| Public, unsubscribe, exports (not purge), privacy, billing, customer admin, login waves already on prod — diff live line vs [go-cutover-runbook](../plans/go-cutover-runbook.md) §3 | **`/stay-fees/*`** seal — wave **10 step 4** only after steps 1–3 + dry week |
| Exact **`/reservations`** list only (already on prod) | **`/reservations/*`** wildcard until **1863** (+ Go handlers for detail/POST) |
| Stay-fees **PDF/CSV** prefixes (step 1) if not already present | **`POST /reservations/{id}/submit`**, **`submit-ready`** — **1740–1741** |
| More **invoice** tokens per wave 9 order (never `/invoices/*`) | **`/settings/purge-expired`**, **`retention`/`stay_fee_mail` job kinds** — runbook §5 |
| | Bare **`/apartments`**, **`/entities`**; **`/webhooks/stripe`**; **`/demo`** |

---

## Python retirement gates (G1–G9)

From [python-retirement-plan](../plans/python-retirement-plan.md) §2–3. Dates slip one day per failed gate.

| Gate | Target (Prague) | What |
|---|---|---|
| W1 | **2026-11-18** | `billing` 06:00 + `stay_fee_mail` 07:00 on Go ok |
| G1, G2 | **2026-11-18 – 11-30** | `guide_import` + **one real police filing** on Go |
| G3 | **by 2026-11-27** | **1780** deployed; backups without Python containers |
| G4 | **2026-11-30** | Stop Python **worker** |
| G5 | **2026-12-07** | Caddy default → Go; **1790** allow-list empty or “drop” per route |
| G6 | **2026-12-15** | SQLite S11 / rollback path ends |
| G7 | **2026-12-16 – 12-18** | **`ubyhost` leaves compose** (**1782**) |
| G8 | **2026-12-28** | Quiet week after stage 3 |
| G9 | **on/after 2027-01-18** | Merge **1479**, delete **`App/`** (30 days after stage 3) |

---

## What stays Python until ports + gates (runbook §6)

Until the rows above are done: **guest registration** (`/l/*`, `/g/*`), **host guest edit**, **filing submit UI**, **property/entity create & save** (unless on Go), **booking guest `/p/*`** (Payments hidden), **cleaning** POST gaps, **dashboard `/`**, **`main.py` utilities** (1750), **mail/door_codes** jobs, **`/dev/ui`**, **`/webhooks/stripe`** (1781), Python containers as **SQLite rollback** until **G6**.

**Executor rule:** Prefer existing `docs/tasks/17xx.md` + exact-diff passes; only writer adds **1860–1864** briefs if the Stays lane split is not covered by shrunk **1730/1731**.