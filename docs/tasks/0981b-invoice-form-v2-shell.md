# 0981b: Invoice detailed form on the v2 host shell (B03 split, invoice path)

Status: todo
Depends on: `docs/tasks/0981-host-shell-forms.md` (gate + class list) | Base commit: `7b0355c45ccdd2557a28edfcfe228aa1dc766e36` | Branch: `codex/0961-b03-host-shell` (or integration)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Add `{% set v2 = true %}` to `invoice_form.html` and port the invoice-form–only CSS class rules listed in `0981-host-shell-forms.md` §2 from legacy sheets into `app2.css`, scoped for v2, so Generate invoice / detailed invoice editor matches list pages without loading v1 CSS.

## 2. Context

Full root cause, grep counts, and the **invoice-form class list** live in `docs/tasks/0981-host-shell-forms.md` §2. Re-read that file; do not duplicate the long lists here.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/invoice_form.html` | edit | `{% set v2 = true %}` after `extends` (see 0981 gate patch) |
| `App/app/static/app2.css` | edit | Port invoice-only classes (`invoice-form`, `invoice-more`, toolbar, etc.) |
| `App/app/templates/base.html` | edit | bump `app2.css?v=` when app2.css changes |
| `App/tests/static_versions.json` | regenerate | `python tests/test_static_versions.py --write` |
| `App/tests/` (per test-map) | edit | Browser/assert tests as in 0981 split proposal |

No other file may change unless the test-map row or a failing test proves it. **Do not edit `guest_form_admin.html`** — that is **0981a**.

## 4. Steps

1. Re-run the two gates in `0981-host-shell-forms.md` §4.
2. Apply the flag for `invoice_form.html` only; port CSS from `host.css` / `host2.css` / `app.css` with tokens only.
3. Bump cache key; regenerate `static_versions.json`.
4. Run the test-map rows listed in `0981-host-shell-forms.md` for the invoice path only.

## 5. Do not touch

Guest admin form — **0981a**. No new dependencies.

## 6. Commands

From `App/`, per test-map for invoices + v2 shell; browser runs need `UBYHOST_REQUIRE_BROWSER=1` and own DB/shots.

## 7. Acceptance

- [ ] `body.v2` on invoice new/detail flows at 390 / 768 / 1280.
- [ ] No horizontal scroll; invoice controls readable.
- [ ] `test_static_versions.py` green.

## 8. Stop and ask

Per `docs/context/executor.md` if anchors move, tests fail twice, or scope creeps into 0981a files.

## 9. Report

Write `docs/tasks/0981b-report.md`.

## Risk list (for the reviewer)

`app2.css`, `invoice_form.html`, shared invoice macros, cache keys.

## Owner steps

Merge when green; deploy manually.
