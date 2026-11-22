# 2030: Guest forms send a real CSRF token (D2, production blocker)

Status: todo
Depends on: none | Base commit: main | Branch: task/2030-guest-csrf-real-token
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Every guest form page that posts (party, count, another, save, remove, relang, draft, scan, claim confirm, Leon questions) must render a real signed CSRF token and set the `ubyhost_csrf` cookie, as the PIN page already does. Today these pages render the placeholder `*`, so every POST gets `{"detail":"Cross-site request rejected."}` and no guest can claim or register.

## 2. Context

Root cause: `go/internal/web/guest/form_pages.go` line 840-842:

```go
func formPagesCSRF(r *http.Request) string { return formPagesCSRFToken() }

func formPagesCSRFToken() string { return "*" }
```

Callers: `form_pages.go:299`, `:589`, `stay_claim.go:253`, `:357` (`CSRFToken: formPagesCSRFToken()`). The `*` also goes into `<meta name="csrf-token">` (templates/base.tmpl:9), so `csrf.js` overwrites any good value with `*`. `csrfValid` (go/internal/hostweb/gate.go:213) rejects it, and `sameSite` then reports cross-site because the request has no matching Origin check path.

The working pattern is `mintGuestPageCSRF(w, r, getenv, now)` in `go/internal/web/guest/shared.go:185` (used by `pin.go:108`, `privacy.go:87`): it returns the token and sets the cookie. Golden tests normalise the token to `*` (`testdata/form_pages_golden.json`), so goldens should not change; if one does, STOP.

## 3. Files

| Path | Action | What |
|---|---|---|
| go/internal/web/guest/form_pages.go | edit | replace `formPagesCSRF(r)` use with a minted token; keep `w` in scope |
| go/internal/web/guest/stay_claim.go | edit | same for both render sites |
| go/internal/web/guest/*_test.go (new `csrf_forms_test.go`) | add | GET each form page, read `_csrf` and `ubyhost_csrf` cookie, POST it back, expect not 403 |

No other file may change.

## 4. Steps

1. Read the four call sites and their handler signatures (`grep -n formPagesCSRF go/internal/web/guest/*.go`, read 40 lines around each).
2. Delete `formPagesCSRF`/`formPagesCSRFToken`. At each site call `mintGuestPageCSRF(w, r, d.getenv, now)` before the body is written (cookie must be set before the first write); on error use the page's existing 500 path.
3. Add the round-trip test: for `/l/{token}/{id}/party` (claimed and unclaimed stay) and `/claim/confirm`, GET, extract token and cookie, POST, assert status is not 403 and no "Cross-site" text.
4. Run: `cd go && go test ./internal/web/guest/... ./internal/hostweb/... 2>&1 | tail -30`.

## 5. Do not touch

Python, templates, `hostweb/gate.go`, golden files, PIN and privacy pages. AGENTS.md rule 1 (filing correctness) and rule 2 (no new cookies: `ubyhost_csrf` already exists in the cookie inventory).

## 6. Commands

Step 4 command; expect `ok` for both packages. Then `python3 scripts/context_lint.py | tail -30`.

## 7. Acceptance

- [ ] No `"*"` CSRF placeholder remains in `go/internal/web/guest` (`grep -n 'return "\*"' go/internal/web/guest/*.go` empty).
- [ ] New round-trip test passes; goldens unchanged.
- [ ] Rule 7: no template/CSS change, so no screenshot needed; say so in the PR.
- [ ] Owner step after merge: on staging, open a guest link, enter PIN, submit the party step; it reaches the claim mail step.

## 8. Stop and ask

Excerpt not found; a golden changes; a test fails twice; 25 tool calls or about 50k tokens; a file outside §3 needs a change.

## 9. Report

`docs/tasks/2030-guest-csrf-real-token-report.md`
