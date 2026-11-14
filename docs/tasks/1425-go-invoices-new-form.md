# 1425: Go invoice pages: the stay picker and the invoice form

Status: review
Depends on: 1423 (merged or on this branch) | Base commit: the working branch head (no fixed commit) | Branch: the current branch (one big PR)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier A

> **One big PR mode.** Work on the current branch: never create a branch, never push, never open a PR. Commit `1425 step k` after each step that changes a file. The owner opens one pull request for all briefs.

## 1. Objective

Add `GET /invoices/new` to the Go invoice package, still switched off: the stay picker (no `reservation_id`) and the invoice form for one stay, with the lead guest suggested as buyer, the last price on the property as a hint, the remembered payment method and the next number. The templates `invoice_stay_picker.html` and `invoice_form.html` become Go templates; the form's inline script is copied unchanged.

## 2. Context

Rules (AGENTS.md): 1 filing is untouched (nothing here reads or writes UbyPort data); 2 no new personal-data field and no new outbound request (the lead guest's address is read, decrypted and shown to the owner of the stay only, as Python does); 3 fixtures are made up (`@example.test`, no real names); 4 no new dependency (stdlib, pgx and packages already in go.mod); 5 plain PostgreSQL SQL, no schema change; 7 and 10 (screenshots, UX gate) do not apply yet: the pages are not served, no path is in `UBYHOST_GO_PATHS`, and the UX gate is the owner step at the switch (brief 1427, Owner steps).

**All code is pre-written, compiled and tested** by the brief writer in a scratch worktree, in brief order 1420 to 1427. Sidecars live under `docs/tasks/1425-files/<repo path>.txt`; step 1 copies them byte for byte. You write no application code. Never retype or edit a copied file. A sha256 mismatch: STOP (§8).

| sha256 | file (repo path; sidecar = `docs/tasks/1425-files/<path>.txt`) |
|---|---|
| `822ad8628cecec0ae1880b3e97b9c29b1326f0862a1f485b56d5e5491aabbcd5` | `go/internal/web/invoices/countries.go` |
| `5eaf8dd82ddd1f62141146d12958e939cbe9a197f649c0daaebbe8ec9e01e83d` | `go/internal/web/invoices/countries.json` |
| `967dd35a77f6810fb723ced134b5b01c83ecb5dbdd04ef3f814f90ba12f6c122` | `go/internal/web/invoices/guest.go` |
| `70f7d998fce71a345057f3976a6d6a85390b5986b10ade807a3666d065d55cf1` | `go/internal/web/invoices/formctx.go` |
| `bc3cd1661411489e7a607f66164bb07a6224df74acf6a53b4d7588e164ca0392` | `go/internal/web/invoices/pages_new.go` |
| `e67f3db429be1a4ecebcae3be85a78ca34ad92dd4d180e8c80eef6f8505bff15` | `go/internal/web/invoices/templates/picker.tmpl` |
| `82690cf85e7464dc1d2b35bcc95b7ed5054e6b23c19f0b90d6fabf45a3256f92` | `go/internal/web/invoices/templates/form.tmpl` |
| `ad9220816f054bdcd503b9f691535a19616b99ff1df2eceb6a473769233886b2` | `go/internal/web/invoices/new_test.go` |

**Parity (Python -> Go):**

| Python | Go |
|---|---|
| invoice_new, routes/invoices.py 444-489 | `newHandler`/`newPage` in pages_new.go |
| _form_context 266-301, _form_state 244-263 (+ invoices.form_item_rows 209-234) | `formContext`, `formState`, `formItemRows` in formctx.go |
| _lead_guest 149-158, _guest_buyer_values 161-170, _merge_guest_fill 173-177, _drop_guest_suggestion 180-189 | guest.go |
| codelists.nationality_options (codelists.py 128-165) | countries.go (the `codelist` rows of kind `staty` when there are 150 or more, else the bundled ISO list) |
| templates invoice_stay_picker.html, invoice_form.html | templates/picker.tmpl, templates/form.tmpl |

**Flow (as Python):** no `reservation_id` (or an empty one): the picker (stays from 400 days ago to 365 days ahead, newest first, at most 200, without cancelled or demo stays; up to six quick links to started stays without a live invoice). A `reservation_id`: the stay must be the host's (else back to `/invoices/new` with `invoice.err.no_stay`), pass `stay_problem` (its key is the flash), and have no live invoice (else a redirect to that invoice with `invoice.err.stay_has_invoice`); the operator is the property's operator when it has one, else `?entity=` or the first business; when `?entity=` is not that operator's id the page redirects (303) to `/invoices/new?reservation_id=<id>&entity=<id>` once; with no business the page shows only the `invoice.err.no_entity` banner.

**Personal data (Tier A):** the buyer suggestion reads the lead guest of the stay: the lowest-id guest that `validation.GuestIsComplete` accepts; their first name, surname, street, city and country fill blank buyer fields on the first open only, and the host checks them before issuing. The street and city are stored encrypted; `guest.go` decrypts them in memory with `secure.LoadDataKeys` exactly as `go/internal/calendar` does, never logs them, and a guest of another host's stay is unreachable because the stay was loaded through the host's own properties. `fill_from_guest` and the company flow (brief 1427) use the same code.

**Other behaviours the tests pin:** the form shows the VAT column only for a VAT payer and the operator picker only when the host has two or more businesses (hidden otherwise); the buyer e-mail starts as the reservation's `guest_email`; the price hint is the unit price of the last issued accommodation line on that property for this owner (whole numbers without decimals); a new invoice starts with the payment method of the operator's last paid invoice; the supplier link is `/entities?edit=<id>&next=<urlencoded /invoices/new?...>#entity-invoice`; the country list is sorted ignoring accents.

Deviations: `countries.json` is a copy of `go/internal/countries/countries.json` (that package exports no list; a test fails when the two differ); the Prague date for the tax-point default and the duzp field comes from `pragueDay`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/invoices/countries.go` | create | nationality options |
| `go/internal/web/invoices/countries.json` | create | copy of go/internal/countries/countries.json |
| `go/internal/web/invoices/guest.go` | create | lead guest suggestion (decrypts address fields) |
| `go/internal/web/invoices/formctx.go` | create | form context and state |
| `go/internal/web/invoices/pages_new.go` | create | GET /invoices/new |
| `go/internal/web/invoices/templates/picker.tmpl` | create | invoice_stay_picker.html |
| `go/internal/web/invoices/templates/form.tmpl` | create | invoice_form.html (script unchanged) |
| `go/internal/web/invoices/new_test.go` | create | picker, form, redirects, guest suggestion, price hint |

No other file may change.

## 4. Steps

0. Checks (repo root): `ls go/internal/web/invoices/pages_list.go go/internal/web/invoices/store.go | tail -3` lists both; `ls go/internal/web/invoices/formctx.go 2>&1 | tail -2` says "No such file"; `grep -cF 'def invoice_new(request: Request):' App/app/routes/invoices.py` and `grep -cF 'def _form_context(' App/app/routes/invoices.py` each print 1 or more; `grep -cF 'func GuestIsComplete(' go/internal/validation/validation.go` prints 1 or more; `find docs/tasks/1425-files -name '*.txt' | wc -l` prints `8`.

1. Copy and check (one call, repo root):

   ```bash
   cd docs/tasks/1425-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")"; cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum go/internal/web/invoices/countries.go go/internal/web/invoices/countries.json go/internal/web/invoices/guest.go go/internal/web/invoices/formctx.go go/internal/web/invoices/pages_new.go go/internal/web/invoices/templates/picker.tmpl go/internal/web/invoices/templates/form.tmpl go/internal/web/invoices/new_test.go | tail -30
   ```

   All 8 hashes must equal §2. Commit "1425 step 1".

2. PostgreSQL. If `UBYHOST_TEST_DATABASE_URL` is already set to a server you may create databases on, skip to step 3. Else start a throwaway one (as root; `pg_ctl` refuses root, so it runs as `postgres`):

   ```bash
   mkdir -p /var/tmp/pg1420 && chown postgres /var/tmp/pg1420 && su postgres -c 'cd /tmp && /usr/lib/postgresql/16/bin/initdb -D /var/tmp/pg1420/data -A trust -U postgres >/dev/null && /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg1420/data -o "-p 55432 -k /var/tmp/pg1420" -l /var/tmp/pg1420/log start' 2>&1 | tail -3
   ```

   Then use `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55432/postgres` in step 3. A server on that port already (another brief's): use it. No PostgreSQL 16 binaries at that path: write "CI only (no PostgreSQL)" in the report and run step 3 without the variable; the database tests then SKIP, which is expected and not a pass.

3. Build and test (repo root, one call per line; each ends with `2>&1 | tail -30`):

   ```bash
   cd go && gofmt -l internal/web/invoices cmd/ubyhost-web 2>&1 | tail -30
   cd go && go build ./... 2>&1 | tail -30
   cd go && go vet ./internal/web/invoices/... ./cmd/... 2>&1 | tail -30
   cd go && UBYHOST_TEST_DATABASE_URL=<url> go test -count=1 ./internal/web/invoices/... ./cmd/ubyhost-web/... 2>&1 | tail -30
   ```

   Expected: the first three print nothing; the last prints `ok  \tgithub.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/invoices\t<time>` and `ok  \t...go/cmd/ubyhost-web\t<time>`. A `FAIL`, a `[build failed]` or a vet line: read the last 30 lines once, then STOP (§8).

4. Write the report (§9) and commit "1425 step 3".

## 5. Do not touch

Everything outside §3. In particular: `go/internal/hostweb/` (layout, `i18n.json`), `go/internal/session/`, `go/internal/jobs/`, `go/cmd/ubyhost-web/main.go`, `go/internal/pdf/`, `go/internal/billingjob/`, `go/internal/mail/`, `App/tests/conftest.py`, every Python file under `App/app/`, `docs/context/status.md`, `test-map.md`, `decisions.md`, `known-issues.md`, `docs/ENVIRONMENT.md`. Never set `UBYHOST_GO_PATHS`, edit Caddy or compose, push, merge or deploy. Never edit a copied file to make a test pass: a failing sidecar test is a STOP (§8). Hard rules 2, 3, 4, 5 as in §2.

## 6. Commands

Step 3 only, plus from the repo root `python3 scripts/context_lint.py 2>&1 | tail -30` (prints `context lint: OK`). Never the full suite, never `pytest tests`.

## 7. Acceptance

- [ ] The 8 sha256 values match §2.
- [ ] `gofmt -l` prints nothing; `go build ./...` and `go vet` print nothing.
- [ ] `go test` prints `ok` for `internal/web/invoices` and `cmd/ubyhost-web`; with PostgreSQL there is no `--- SKIP` line in `go test -v` (without it the report says "CI only").
- [ ] `cd go && UBYHOST_TEST_DATABASE_URL=<url> go test -count=1 -v -run 'TestPicker|TestForm|TestBundled' ./internal/web/invoices/ 2>&1 | grep -c '^--- PASS'` prints 8.
- [ ] `git log --oneline --grep='^1425 step' | tail -5` shows the step commits, and `git show --stat --format=%s $(git log --format=%h --grep='^1425 step') | tail -30` lists only §3 paths.
- [ ] Nothing pushed, no branch created.

## 8. Stop and ask

Stop, and write the report, if:

- an anchor or a check in step 0 is not as written;
- a sha256 in step 1 does not match;
- `gofmt -l` prints a file, `go build` or `go vet` prints anything, or a test fails twice (read the last 30 lines once; never edit a copied file);
- you reach 25 tool calls or about 50k tokens (report as `blocked`, see executor.md);
- a new dependency seems needed, or a file outside §3 needs a change;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1425-report.md` (600 tokens at most) and set this brief's `Status: review`: diff stat, each command with its last 5 lines, §7 ticked, deviations, questions, owner steps left (none).

## Risk list (for the reviewer)

`guest.go` first: which guest is read (`reservation_id`, not archived, lowest id, complete), which fields leave the function (name, street, city, country only), decryption failure is an error and never a blank. `pages_new.go` `newPage`: the stay is loaded with the owner join before any guest or price is read. `formctx.go`: the price hint query is owner-scoped. `templates/form.tmpl`: the `<script>` is a verbatim copy of lines 307-531 of `invoice_form.html` (compare with `diff <(sed -n '307,531p' App/app/templates/invoice_form.html) <(sed -n '/^<script>/,/^<\/script>/p' go/internal/web/invoices/templates/form.tmpl)`, which prints nothing).

## Owner steps

None: nothing is switched on. The pages stay dormant until the owner adds paths to `UBYHOST_GO_PATHS` (listed in brief 1427, Owner steps).
