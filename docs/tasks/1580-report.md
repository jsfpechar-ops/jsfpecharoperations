# 1580 report

Status: review

## 1. Files changed

```
 go/cmd/ubyhost-web/register_job_stay_fee_mail.go   |   13 +-
 go/cmd/ubyhost-web/register_job_stay_fee_mail_test.go |   18 +-
 go/internal/pdf/doc.go                             |  134 +-
 go/internal/stayfeepdf/render.go                   |  510 ++
 go/internal/stayfeepdf/render_test.go              |  150 +
 go/internal/stayfeepdf/testdata/gen_golden.py      |  199 +
 go/internal/stayfeepdf/testdata/hlaseni_golden.json | 6516 +++++++++++++++++++
 7 files changed, 7462 insertions(+), 78 deletions(-)
```

## 2. Commands (last 5 lines)

**Step 0:** branch `wt-1580`; deps and original hashes matched; `stayfeepdf` absent; 7 sidecars.

**Step 1 sha256sum -c:** seven `: OK` lines.

**Step 2 (gofmt/build/vet):** silent (module downloads only in log).

**Step 3 PG:** installed `postgresql-16`; `server started` on port 55580.

**Step 4 packages:** five `ok` (`stayfeepdf`, `pdf`, `stayfee`, `stayfeemail`, `cmd/ubyhost-web`).

**Step 4 named -v:** `--- PASS` for `TestLayoutMatchesPythonOps` (stayfeepdf + pdf), `TestRenderIsPDFAndDeterministic`, `TestMultiPageHasTwoPages`, `TestAmountAndNights`, `TestStayFeeMailHasRenderer`; three `ok`; no `SKIP`/`FAIL`. **SKIP count: 0.**

**context_lint:** `context lint: OK`

## 3. §7 acceptance

- [x] sha256sum step 1 all `: OK`; step 0 originals matched
- [x] format/build/vet silent
- [x] five packages `ok`; named tests all `PASS`; SKIP 0
- [x] commits `1580 step 1` (and step 5); paths only §3
- [x] no `UBYHOST_GO_PATHS` / `UBYHOST_GO_JOB_KINDS` / App / Caddy changes; not pushed to `main`
- [x] UI N/A

## 4. Deviations

PostgreSQL 16 was not preinstalled; `apt install postgresql-16` then brief throwaway `pg55580` (coordinator required full DB tests).

## 5. Questions

None.

## 6. Owner steps left

None in brief; `stay_fee_mail` kind still off until 1589.