# Stay fee pages on Go: rollout

Briefs 1580 to 1588 port the 16 routes of `App/app/routes/stay_fees.py` and the hlášení PDF. They are all dormant: Caddy keeps `/stay-fees` on Python until `UBYHOST_GO_PATHS` names it. Owner, 2026-11-14: stays and filing come last, nothing is switched on without a clean staging run.

## Checks before any switch (owner or orchestrator, in this order)

1. Brief 1588 (all 16 routes registered) and the Go test job are green on the final commit of the PR.
2. Staging: seal one period on Go (`POST /stay-fees/<id>/finalize`), then download the PDF and CSV from **Python** and open the PDF. Then seal another on Python and download it from **Go**. Both sides read the same encrypted rows; any difference stops the rollout.
3. Open one real hlášení PDF made by Go next to one made by Python (brief 1580 compared draw operations only; nobody has looked at the page). Same text, same order, no overlap.
4. The UX gate of AGENTS.md rule 10 on the list (`/stay-fees`) and the detail page (`/stay-fees/<id>`): `test_layout_lint_browser.py`, the 390, 768 and 1280 px screenshots, one line per page in the PR.

## Switch order (each step: add to `UBYHOST_GO_PATHS`, run `caddy-validate.sh`, `docker compose up -d caddy`, open the page, wait one day)

Caddy matches paths, not methods, and `*` also matches `/`. So the pages cannot be switched one route at a time without a path that also catches the others. Use these paths:

1. Read only downloads: `/stay-fees/pdfs.zip`, `/stay-fees/*/pdf`, `/stay-fees/*/csv`.
2. Guest-pay preview (JSON, nothing saved): `/stay-fees/*/guest-pay-preview`.
3. The pages: `/stay-fees` (list). The detail page `/stay-fees/<id>` has no path of its own that leaves the POST routes below on Python; it moves with step 4.
4. Everything else in one step, because `/stay-fees/*` catches all of it: `/stay-fees/*`. After this the whole area is Go. The seal routes (`finalize`, `confirm-ready`) are filing writes: do this step only after checks 2 and 3, and not on a day when a filing deadline is near.

Rollback at any step: remove the path, `caddy-validate.sh`, `docker compose up -d caddy`. Rows sealed by Go stay valid for Python (check 2).

## Mail job

`stay_fee_mail` has a Go handler (brief 1242) and, with brief 1580, a PDF renderer. It is **not** switched on. To move it: add `stay_fee_mail` to `UBYHOST_JOB_QUEUE_KINDS` and `UBYHOST_GO_JOB_KINDS` together (see `docs/ENVIRONMENT.md`), after the pages are on Go and one dry week of sealed periods matches Python. Rollback: remove it from `UBYHOST_GO_JOB_KINDS`.

## Left on Python

The fee settings form in the property editor (`/apartments/<id>`), and its automation timing. Links from the Go pages to them keep working.
