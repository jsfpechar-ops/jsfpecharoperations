# 1632: Host UI — entry door code field + external guide URL field

Status: todo
Depends on: 1631 | Base commit: d39b1351 | Branch: task/1632-host-ui-entry-code-guide-url
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier B (host UI)

## 1. Objective

Let the host set a building/gate entry code (label + code + optional valid-until) in the Smart lock section of apartment settings, and an external guide URL (https-only) on the guide editor. Entry code is stored encrypted and displayed write-only/masked; the audit log never contains the value.

## 2. Context

Anchor 1 — the existing Smart lock POST to mirror, `App/app/routes/admin.py:2496-2515`:

```python
@router.post("/apartments/{apartment_id}/door-codes")
async def apartment_door_codes(apartment_id: int, request: Request):
    """0954: the Turn on / Turn off buttons in the Smart lock section. No JavaScript."""
    guard = auth.require_login(request)
    if guard:
        return guard
    apartment = access.apartment(request, apartment_id)
    if not apartment or not ttlock.allowed_for(apartment["owner_user_id"]):
        return _back("/apartments", err=_flash(request, "flash.error.smart_locks_unavailable"))
    form = await request.form()
    here = f"/apartments/{apartment_id}?view=settings&section=lock#sec-lock"
```

Anchor 2 — secrets pattern, `App/app/cleaning_codes.py:119-124` (validation regex) and `db.encrypt_field(...)` for storage; audit without value: `db.audit("door_codes_off", f"apartment={apartment_id}")` (admin.py:2513).

Anchor 3 — https-only URL validation to copy, `App/app/guest_guide.py:186-188`:

```python
    url = out.get("video_url")
    if url and not url.startswith("https://"):
        raise GuideError("flash.error.guide_video_url")
```

plus the stricter parse in `App/app/guest_guide_import.py:89` (require https scheme, reject userinfo and port). Apply both to `guide_external_url`.

Anchor 4 — the Smart lock panel template: `App/app/templates/_smart_locks_panel.html` (find with `grep -rln "door-codes" App/app/templates/`). Guide editor template: `App/app/templates/guide.html`. Design system: `docs/design/design-system.md` then MASTER.md; no JavaScript-required controls (AGENTS.md rule 6).

UX gate (AGENTS.md rule 10): this brief touches host pages — merge only after `test_layout_lint_browser.py` green, 390/768/1280 screenshots of each touched page reviewed, design-system checklist ticked in the PR.

Go-first note: `/apartments/...` and the guide editor are Python-served today (`UBYHOST_GO_PATHS` unset). The pending owner decision (decisions.md 2026-11-14) covers port-first vs Python-now; do not port anything in this brief.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/routes/admin.py` | edit | new `POST /apartments/{apartment_id}/entry-code` next to `apartment_door_codes`: validate, `db.encrypt_field` into `entry_code_enc`, set `entry_code_label`/`entry_code_until`, `db.audit("entry_code_set", f"apartment={apartment_id}")` — no value — redirect back to the lock section |
| `App/app/templates/_smart_locks_panel.html` | edit | "Entry door code" fields (label, code, valid-until) in the Smart lock section; code input is write-only (password-style), value never re-rendered — show masked/"set" state only |
| `App/app/routes/guest_guide.py` | edit | save `guide_external_url` on the apartment from the guide editor; https + strict parse; store nullable |
| `App/app/templates/guide.html` | edit | external guide URL field, shown with its domain once saved |
| `App/app/i18n.py` (and host i18n catalogs as applicable) | edit | new keys in every language: labels, flashes, masked-state text |
| `App/tests/test_host_*.py` or new test | add | POST sets encrypted column + audit string has no code; URL rejected unless https without userinfo/port |

No other file may change.

## 4. Steps

1. Read the anchors above verbatim (grep them; stop if missing — §8).
2. Add the entry-code POST in `routes/admin.py` mirroring anchor 1's guard/access pattern; store via `db.encrypt_field`; clear = set `entry_code_enc` NULL. Audit event name `entry_code_set` with `apartment={id}` only.
3. Add the form section to `_smart_locks_panel.html` (no-JS form, design-system classes; code field `type="password"` autocomplete off, never pre-filled).
4. Add `guide_external_url` save in `routes/guest_guide.py` with the anchor-3 validation; add the field to `guide.html`.
5. i18n keys in every language catalog used by these pages (`guide_i18n.py`/`host_vi_i18n.py` if that is where host flashes live — check where `flash.error.smart_locks_unavailable` is defined and put the new keys in the same catalog, all languages).
6. Tests + commands in §6; screenshots per §7.

## 5. Do not touch

Guest templates, `routes/guest.py`, `mail*.py`, `claim.py`, `door_codes.py`, the frozen migration dir, `db.SCHEMA`. No new dependency. No value of any code in logs/audit/flash. Never `git add -A`; secret-grep the staged diff before commit.

## 6. Commands

From `App/`: `.venv/bin/python -m pytest tests/test_host_*.py tests/test_host_geometry.py -q --tb=short -x -rs 2>&1 | tail -30` (0 skipped)
From `App/`: `.venv/bin/python -m pytest tests/test_layout_lint_browser.py -q --tb=short -x 2>&1 | tail -30`
From `App/`: `.venv/bin/python -m pytest tests/test_guide*.py tests/test_*_i18n.py tests/test_copy_cleanup.py tests/test_flash_literals.py -q --tb=short -x 2>&1 | tail -30`
From repo root: `python3 scripts/context_lint.py 2>&1 | tail -10`

## 7. Acceptance

- [ ] Host can set/clear the entry code; `entry_code_enc` is ciphertext in DB; audit row contains no code value; UI shows masked state, never the code.
- [ ] `guide_external_url` rejects `http://`, userinfo, and ports; accepts `https://notion.site/...`.
- [ ] Host geometry + layout lint green, 0 skipped; one 390 px screenshot per touched page attached to the report (768/1280 also if layout changed); design-system checklist ticked in the PR.
- [ ] `test_guide_coverage.py` passes if host Help & guide strings changed (PR template box).

## 8. Stop and ask

Stop and write the report if: an excerpt is not found; a test fails twice; 25 tool calls or ~50k tokens reached; a file outside §3 needs a change; §5 would be touched; you need push/merge/deploy.

## 9. Report

Write `docs/tasks/1632-report.md` (≤600 tokens), `Status: review`, one PR with the PR-template checklists filled.

## Risk list (for the reviewer)

`App/app/routes/admin.py`, `App/app/routes/guest_guide.py`, `App/app/templates/_smart_locks_panel.html`, i18n catalogs.

## Owner steps

1. Review screenshots (390/768/1280) of apartment settings lock section and guide editor.
2. Go-first decision for 1633/1634 (decisions.md 2026-11-14).
