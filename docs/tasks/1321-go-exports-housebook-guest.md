# 1321: Go port of the house-book CSV and the guest Art 15/20 bundle, parity-checked against Python

Status: todo
Depends on: 1320 (merged or on this branch) | Base commit: the "1320 step 5" commit | Branch: task/1320-go-exports
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier A (guest data, decryption)

## 1. Objective

Add `GET /housebook.csv` (exports.housebook_download with housebook.housebook_rows / iter_housebook_csv_rows) and `GET /guests/{id}/export.json` (exports.guest_export_json with dsr.guest_export) to `go/internal/web/exports`, and extend the golden so both are compared with the real Python byte for byte. Still switched off: no `UBYHOST_GO_PATHS`, Caddy, compose or env change.

## 2. Context

Rules (AGENTS.md): 1 filing correctness (read-only; the "reported" column reads submit_state, nothing writes); 2 no new personal-data field, no outbound request; 3 fixtures are made up (`@example.test`, test-only keys); 4 no new dependency; 5 plain PostgreSQL.

**All code is pre-written and dry-run** on top of 1320. Sidecars: `docs/tasks/1321-files/<repo path>.txt`. Step 1 copies them; never retype or edit them.

| sha256 | file (repo path; sidecar = `docs/tasks/1321-files/<path>.txt`) | action |
|---|---|---|
| `a6d23e63320af9fcede7ead62903e188b7be8cbd1e69455631c1d3ecd003ecd4` | `go/internal/web/exports/housebook.go` | create |
| `f595210286d05f7cc65ad70e1ab121a4446b52e0603370019418c19c75f8274d` | `go/internal/web/exports/guest_json.go` | create |
| `3630c8337096ab5e53f67bf5cd470624da43b92786bfe95e6a241795e51a9e02` | `go/internal/web/exports/routes.go` | replace (two routes added) |
| `ca93c2124ef7d61ab7506e6da394188d47b7788a6f21e1a80ee3ace337102c1f` | `App/scripts/exports_golden.py` | replace (10 guests, 7 audit rows, 2 photo files, 14 cases added) |
| `54d3110311949cf05cb270d2da09d9ec71c73d489cf8f8b876fe6cb4583f3a96` | `App/tests/test_go_exports.py` | replace (two paths added) |
| `49035cb13605d09cdfca27f8393a7ed2b06161e6e2c053915d2635dfac48f056` | `go/internal/web/exports/testdata/exports_golden.json` | replace (generated, deterministic) |

`exports_test.go`, `exports.go`, `i18n_keys.txt` and `i18n.json` from 1320 already handle this (stale sessions, photo files, seeded audit rows, the `recent_login` and `identity_hidden_guest` keys); they do not change.

**How the Go copies Python:**

- House book: the `_housebook_sql` query (`$1::bigint IS NULL OR a.owner_user_id = $1`, apartment, `COALESCE(g.stay_from, r.date_from)` range and order); every encrypted guest pair is decrypted as db._hydrate does (doc, visa, signature, fee reason, birth date, street, city; a bad token is a 500); the 17 columns of `_housebook_export_row`: reported mapping and "filed by hand", receipt stamp lookup, `format_birth_date`, `compose_residence` in Czech (`countries.Name(code, "cs")`, 255 characters), `purpose_label(code, "cs")` (the cs column of validation.PURPOSES), and `signature_record` kinds (imported, own drawing, under 15 with an adult signer whose signature parses and who is certainly 18, else exempt, else missing). `is_valid_signature` reuses `validation.GuestIssues` (its signature issue is `parse_signature_data_url`, except that it accepts "imported", which is refused first). The age helpers assume stored birth dates are already `DDMMYYYY`, as go/internal/validation does.
- Guest bundle: `session_is_fresh` (`iat` within 600 s of `now`, else back to `/settings/security#settings-security` with `auth.error.recent_login`), ownership (404 "Not found."), identity gate for that guest id, then `SELECT * FROM guest` in PostgreSQL column order with decrypted plaintext fields and the `*_enc` tokens kept, `signature_png*` left out, `signature_present`, `passport_photo_present` (reportable, not host-entered, `passport_photo_at` set and a file `<id><ext>[.enc]` in `$UBYHOST_DATA_DIR/passport_photos`), notice, reservation, submissions (`has_receipt` boolean), `receipt_submission_id`, the token-exact audit trail; written as `json.dumps(..., ensure_ascii=False, indent=2)` by a small ordered encoder; audit `export_guest_dsr guest_id=N` after the bundle is built.

**Verified by the brief writer:** with these files over 1320, gofmt empty, vet clean, `TestGoldenParity` PASS on local PostgreSQL 16, golden `--check` clean, pytest 3 passed on PostgreSQL; mutations (adult age 18 → 50, `signature_png_enc` kept, audit LIKE dropped, impersonator dropped) each failed the Go test.

## 3. Files

The six paths in §2, plus `docs/tasks/1321-report.md` (create). No other file may change.

## 4. Steps

0. Checks (repo root): `git branch --show-current` prints `task/1320-go-exports`; `git log --oneline -5 | grep -c '1320 step 5'` prints 1; `ls go/internal/web/exports/housebook.go go/internal/web/exports/guest_json.go 2>&1 | tail -5` says "No such file" twice; `sha256sum go/internal/web/exports/exports_test.go | cut -c1-12` prints `80fa3aff095f`. Anything else: STOP.

1. Copy and check (one call, repo root):

   ```bash
   cd docs/tasks/1321-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum go/internal/web/exports/housebook.go go/internal/web/exports/guest_json.go go/internal/web/exports/routes.go App/scripts/exports_golden.py App/tests/test_go_exports.py go/internal/web/exports/testdata/exports_golden.json | tail -30
   ```

   All six hashes must equal §2. Commit "1321 step 1".

2. PostgreSQL: as brief 1320 step 2 (reuse the server if it still runs: `su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg1320/data status' | tail -1`; if stopped, run only its `pg_ctl ... start` part).

3. Run brief 1320 steps 3, 4 and 5 unchanged (golden `--check` clean; `TestGoldenParity` PASS; pytest green). Write the report (§9) and commit "1321 step 3".

## 5. Do not touch

Everything in brief 1320 §5, plus every 1320 file not listed in §2 (`exports.go`, `submissions.go`, `stays.go`, `exports_test.go`, `i18n*`, `register_web_exports.go`).

## 6. Commands

Brief 1320 steps 3-5. From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

## 7. Acceptance

- [ ] The six sha256 values match §2.
- [ ] Golden `--check` clean; `TestGoldenParity` PASS on PostgreSQL (or "CI only" with the reason); pytest green.
- [ ] `git diff --stat HEAD~2..HEAD | tail -15` lists only §3 paths.
- [ ] Commits "1321 step 1" and "1321 step 3"; nothing pushed.

## 8. Stop and ask

As brief 1320 §8.

## 9. Report

Write `docs/tasks/1321-report.md` (600 tokens at most) and set this brief's `Status: review`: diff stat, each command with its last 5 lines, §7 ticked, deviations, questions, owner steps left (none).

## Risk list (for the reviewer)

`housebook.go` against App/app/housebook.py 95-245 and reporting.py `signature_record` (282-321), `guest_filed_by_hand`, `guest_under_15`; `guest_json.go` against exports.py 116-137, dsr.py 87-150 and reporting.guest_has_passport_photo. Check the decryption pairs, the excluded rows (archived, restricted, ignored, demo), the owner filters, the CSV column order, the JSON key order and escapes, and that the guest audit query uses `IS NOT DISTINCT FROM` and the literal `LIKE 'guest\_%' ESCAPE '\'`. Known and accepted: the submissions list in the bundle has no ORDER BY in Python either (both read the same PostgreSQL plan); birth dates are assumed normalised (`normalise_birth_date` is not ported, as in go/internal/validation); Python `str.upper()`/`strip()` are `strings.ToUpper`/`TrimSpace`.

## Owner steps

None: nothing is switched on.
