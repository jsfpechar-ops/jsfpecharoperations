# 0981a: Guest admin form on the v2 host shell (B03 split, guest path)

Status: todo
Depends on: `docs/tasks/0981-host-shell-forms.md` (gate + class list) | Base commit: `7b0355c45ccdd2557a28edfcfe228aa1dc766e36` | Branch: `codex/0961-b03-host-shell` (or integration)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Add `{% set v2 = true %}` to `guest_form_admin.html` and port the guest-form–only CSS class rules listed in `0981-host-shell-forms.md` §2 from legacy sheets into `app2.css`, scoped under `.ui-page` / v2 body rules, so Add guest matches neighbouring stay pages without loading v1 CSS.

## 2. Context

Full root cause, grep counts, and the **guest-form class list** live in `docs/tasks/0981-host-shell-forms.md` §2. Re-read that file; do not duplicate the long lists here.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/guest_form_admin.html` | edit | `{% set v2 = true %}` after `extends` (see 0981 gate patch) |
| `App/app/static/app2.css` | edit | Port guest-only classes (signature pad, passport preview, verify panel, etc.) |
| `App/app/templates/base.html` | edit | bump `app2.css?v=` when app2.css changes |
| `App/tests/static_versions.json` | regenerate | `python tests/test_static_versions.py --write` |
| `App/tests/` (per test-map) | edit | Browser/assert tests as in 0981 split proposal |

No other file may change unless the test-map row or a failing test proves it.

## 4. Steps

1. Re-run the two gates in `0981-host-shell-forms.md` §4 (`grep` for `set v2`, `grep -c` for classes in `app2.css`).
2. Apply the flag line only for this template; port CSS from `app.css` / `host.css` with tokens only (light mode).
3. Bump cache key; regenerate `static_versions.json`.
4. Run the test-map rows listed in `0981-host-shell-forms.md` “split to propose” for the guest path only.

## 5. Do not touch

Invoice form (`invoice_form.html`) — that is **0981b**. No new dependencies. No secrets.

## 6. Commands

From `App/`, per `docs/context/test-map.md` for guest form + v2 shell; each command ends `2>&1 | tail -30`. Use own `UBYHOST_DB` and `UBYHOST_SHOTS_DIR` for browser tests.

## 7. Acceptance

- [ ] `body.v2` and v2 sidebar on `/reservations/{id}/guests/new` at 390 / 768 / 1280.
- [ ] No horizontal scroll; controls meet touch targets.
- [ ] `test_static_versions.py` green after app2 bump.

## 8. Stop and ask

Per `docs/context/executor.md` if anchors move, tests fail twice, or scope creeps into 0981b files.

## 9. Report

Write `docs/tasks/0981a-report.md`; set this brief to `Status: review` or `blocked` as appropriate.

## Risk list (for the reviewer)

`app2.css` (large shared sheet), `guest_form_admin.html`, cache keys.

## Owner steps

Merge through the integration branch when green; deploy manually per owner process.
