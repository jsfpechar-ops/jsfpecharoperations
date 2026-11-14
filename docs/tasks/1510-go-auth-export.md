# 1510: Go auth, admin downloads a workspace ZIP (`POST /admin/users/{id}/export`, dormant)

Status: review
Depends on: 1501, 1607 (`exports.BuildWorkspaceZip`) | Base commit: 859d114d5 | Branch: go-wave3
Executor: Haiku 5.5 (once unblocked) | Fits one session: 30 tool calls, 60k tokens

**One big PR mode** (when run): stay on the checked-out branch, commit `1510 step k`, no push, no PR.

**Not 1504 or 1509.** The pattern `POST /admin/users/{id}/export` does not conflict in `http.ServeMux` with 1504's or 1509's rows, and no code of theirs is needed. 1501 is named only because the package helpers this handler uses sit beside its `finish.go`; nothing of 1501's API is called.

## 1. Objective

Port `user_workspace_export` (`App/app/routes/admin_accounts.py` 1013-1039) to `go/internal/web/auth`: an admin with a fresh login downloads a ZIP of everything a host's workspace holds (housebook, guest forms, police receipts, stay-fee filings, invoices, manifest), with an audit row. Tier A (personal data of every guest of the workspace leaves the system); dormant until the owner routes the path.

## 2. Context

**Python, the source of truth** (`App/app/routes/admin_accounts.py` 1013-1039, verbatim):

```python
@router.post("/admin/users/{user_id}/export")
def user_workspace_export(user_id: int, request: Request):
    """Stream a ZIP of the workspace, then delete the temp file (BE-10)."""
    account, guard = _require_admin(request)
    if guard:
        return guard
    if not auth.session_is_fresh(request):
        return _back("/settings/security#settings-security", err=_flash(request, "auth.error.recent_login"))
    target = db.query_one("SELECT * FROM user_account WHERE id = ?", (user_id,))
    if not target:
        return _back(f"/admin/customers/{user_id}", err=_flash(request, "flash.error.no_such_user"))
    if not access.identity_visible(request):
        # Inside a host's workspace the ZIP is as blocked here as in Settings.
        return _back("/", err=_flash(request, "flash.error.identity_hidden_export"))
    path = workspace_export.build_workspace_zip(user_id)
    db.audit(
        "workspace_exported",
        f"user={user_id}",
        actor=account["username"],
        owner_user_id=user_id,
    )
    return FileResponse(
        path,
        media_type="application/zip",
        filename=f"workspace-{user_id}.zip",
        background=BackgroundTask(os.unlink, path),
    )
```

**What exists in Go and is reused** (all in package `auth` unless named):

- Gates as in `admin.go` `impersonate`: `hostweb.CSRF(w, r, d.getenv, at)`, `pathID(w, r, "user_id")` (422), `d.admin(w, r)` (`admingate.Require`).
- Fresh login: `session.IsFresh(h.Payload, 0, at)` (`go/internal/session/issue.go` 227; limit 0 is `FreshLoginSeconds`, the same as `auth.session_is_fresh` with no argument, `App/app/auth.py` 770-782).
- `hostweb.Back`, `flashFor`, `none`, `itoa`, `ptr`, `gated`, `d.audit`, `serverError`.
- `access.identity_visible` (`App/app/access.py` 22-36) is always true for an admin (line 30-31), and `_require_admin` has already required role admin, so that branch cannot be reached from this route. The Go handler keeps no branch for it; the brief says so in a comment. Python's `_back("/", err=flash.error.identity_hidden_export)` is therefore not ported.

**Needed from the exports briefs (the blocker):** a Go function equal to `build_workspace_zip(owner_user_id)` (`App/app/workspace_export.py` 34-117): `housebook.csv` (`housebook.iter_housebook_csv_rows` of `housebook_rows`), `archived_housebook.csv` when archived rows exist, `guests/<id>.pdf` per guest (`housebook.registration_form_pdf`, a failing guest skipped), `receipts/<submission id>.pdf` (base64 `receipt_pdf`, undecodable skipped), `stay_fees/<apartment>-<period>-v<version>.pdf|.csv` for filings not superseded (`stay_fee_filing.pdf_bytes`, `csv_bytes`), `invoices/<id>.pdf` (`pdf_blob`, a text blob encoded latin-1), and `manifest.json` (`generated_at`, `owner_user_id`, `counts` {guests, receipts, invoices, stay_fee_filings}, `housebook_rows`, `archived_rows`, `stay_fee_files`; `json.dumps(indent=2)` key order as written), DEFLATE, entries in that order. The same builder serves the host's own download in Settings (`POST /settings/workspace-export`, `App/app/routes/exports.py` 418-445), which is the exports thread's route; this brief only calls it. The ideal signature for this brief: `func BuildWorkspaceZip(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, ownerID int64, now time.Time, w io.Writer) error` (streams into the response, no temp file), or a temp-file variant returning a path that the handler removes after writing.

**Strings** (append to `go/internal/web/auth/i18n_keys.txt` only if missing, then regenerate `i18n.json` as brief 1509 step 3 does): `auth.error.recent_login`, `flash.error.no_such_user`.

## 3. Files (planned)

| Path | Action | What |
|---|---|---|
| `go/internal/web/auth/export.go` | create (copy) | `workspaceExport` handler |
| `go/internal/web/auth/export_test.go` | create (copy) | golden replay (as 1509's `deletion_test.go`) plus a ZIP content check |
| `go/internal/web/auth/testdata/workspace_export.json` | create (copy, regenerated) | golden from Python |
| `App/scripts/auth_export_golden.py` | create (copy) | golden script reusing `auth_routes_golden.py` (go-first allowance 1) |
| `go/internal/web/auth/auth.go` | edit (script) | one row appended at the end of `Routes`: `{"POST /admin/users/{id}/export", "/admin/users/{id}/export", d.workspaceExport}` |
| `go/internal/web/auth/auth_test.go` | edit (script) | route count +1 (same script as 1509's `edit_routes.py`) |
| `go/internal/web/auth/i18n_keys.txt`, `i18n.json` | edit, regenerate | the two keys |

## 4. Steps (handler plan, for the writer who unblocks this)

The handler, in Python's order:

1. `at := d.now()`; `hostweb.CSRF` (fails: its own answer); `pathID(w, r, "user_id")` (422 JSON); `h, ok := d.admin(w, r)` (signed out: login redirect; host: 403 text; paused or acceptance pending: as `admingate`).
2. `!session.IsFresh(h.Payload, 0, at)`: `hostweb.Back(w, r, "/settings/security#settings-security", none, flashFor(r, "auth.error.recent_login"))`.
3. `SELECT id FROM user_account WHERE id = $1`; no row: `hostweb.Back(w, r, "/admin/customers/"+itoa(userID), none, flashFor(r, "flash.error.no_such_user"))`; other error: 500. No `active` check (Python has none).
4. Build the ZIP with the exports briefs' builder. Build it completely (temp file or buffer) before writing any header, so a build error is still a clean 500, as in Python where `build_workspace_zip` raises before the response exists.
5. `d.audit(ctx, &gated{h}, at, "workspace_exported", "user="+itoa(userID), h.Account.Username, ptr(userID))`; error: 500 (before any byte is sent).
6. Answer as Starlette `FileResponse` does, checked against the golden: status 200, `Content-Type: application/zip`, `Content-Disposition: attachment; filename="workspace-<id>.zip"` (the ASCII form; see the comment at `go/internal/web/exports/exports.go` 93 for how that package writes it), `Content-Length`, and Starlette's `last-modified` and `etag` (record them in the golden and decide: they describe a temp file that is deleted at once, so the brief may drop them as a stated difference; the `Cache-Control: no-store, private` of `main.go`'s wrapper stays). Then remove the temp file, as `BackgroundTask(os.unlink, path)`.

Golden cases to record (seed from `auth_routes_golden.base_seed()` plus one apartment, reservation, guest, submission with a receipt, filing and invoice for account 2): success (fresh login, `iat` -60) with the ZIP's entry names and manifest compared (not its bytes: `generated_at` and DEFLATE output differ); stale login (`iat` -3600, the redirect to Security); unknown user 99; bad id (422) signed in and out; host (403); signed out; no CSRF same-site and cross-site; impersonating admin with a fresh login (impersonator id in the audit row); account with an empty workspace (manifest with zero counts). Watch `audit` only (the route writes nothing else).

Tests the brief must run (0 skipped): `go test ./internal/web/auth/... ./cmd/ubyhost-web/... -count=1` with a PostgreSQL started on a unique port (for example 55520, data dir under `/var/tmp/pg55520`) as in brief 1509 step 4, and `pytest tests/test_go_auth_routes.py` from `App/`.

## 5. Do not touch

As brief 1509 section 5, plus the exports briefs' builder files (call them, never edit them) and `go/internal/web/exports/`.

## 6. Commands

None until unblocked.

## 7. Acceptance

- [ ] Unblocked: the Go builder exists, `Depends on` names its brief, and a sidecar with sha256 sums is written and verified by the brief writer as in 1509.

## 8. Stop and ask

Do not run this brief while `Status` is `blocked`.

## 9. Report

No report until it is run.

## Risk list (for the reviewer)

When unblocked: the fresh-login gate before the user lookup (Python's order), the audit row written before the first byte, no partial ZIP on an error, the temp file removed on every path, and that no admin without a fresh login can download.

## Owner steps

1. None now. After it is unblocked and merged: add `/admin/users/*/export` to `UBYHOST_GO_PATHS` together with the other `/admin/users` POST routes (1504, 1509), as in brief 1509's owner step 2, and on a test account check that the downloaded ZIP opens and its `manifest.json` counts match the workspace.
