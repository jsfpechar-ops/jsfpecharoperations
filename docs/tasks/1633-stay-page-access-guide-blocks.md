# 1633: Stay page — entry-code access block + guide block on the completed page

Status: todo
Depends on: 1632 | Base commit: d39b1351 | Branch: task/1633-stay-page-access-guide-blocks
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier B (guest page)

## 1. Objective

On the gated stay page (`GET /l/{token}/{reservation_id}` → `templates/guest/stay.html`, completed state), show the building entry code above the apartment door code, and a prominent guide block (internal guide button when live + external guide link when set) after the door code.

## 2. Context

Anchor 1 — door-code block to sit below the new entry line, `App/app/templates/guest/stay.html:66-82`:

```html
  {% if door_code %}
    <div class="g-card" id="door-code">
      <h2>{{ t('door_code_title') }}</h2>
      {% if door_code.state == 'issued' %}
        <p class="g-door-code" aria-label="{{ t('door_code_title') }}">{{ door_code.pin }}</p>
```

Anchor 2 — current small guide card at the bottom, `App/app/templates/guest/stay.html:158-160`:

```html
{% if guide_live %}
  <a class="g-card g-guide-link" href="/l/{{ token }}/{{ reservation.id }}/guide?lang={{ lang }}" data-guide-link>{{ t('guide_title') }}</a>
{% endif %}
```

Anchor 3 — visibility window, `App/app/routes/guest_guide_view.py:57-70`:

```python
def booked_level(reservation, today: Optional[date] = None) -> str:
    """"booked" from the day before check-in through the checkout day, else "everyone"."""
```

Anchor 4 — live-gating: `guest_guide.progress(apartment_id)["live"]` (`App/app/guest_guide.py:294`); the stay handler already computes `guide_live` for the template (find it with `grep -n "guide_live" App/app/routes/guest.py`).

Rules: the entry code is decrypted at render only (`db.decrypt_field`) — the page is already behind permalink + PIN + device claim. Visibility = `booked_level(reservation) == "booked"` AND (`entry_code_until` is NULL or today <= `entry_code_until`). The entry code must never appear on the public QR guide (`/g/{token}`, `routes/guest_guide_view.py`), in Leon (`leon.guide_block` reads guide cards only), in logs, or analytics. External link: `target="_blank" rel="noopener noreferrer"`, show the URL's domain in the link text. Guest-page rules (`docs/context/rules.md` §Guest pages): bump the `?v=` cache key in `App/app/templates/guest/base.html` for each changed CSS/JS file; browser + geometry tests 0 skipped; one 390 px screenshot of the changed page in the report. Copy rule: new strings via `t('...')` i18n keys in every language (`App/app/i18n.py`), no hardcoded text.

Go-first note: `/l/...` is Python-served today; see the pending owner decision (decisions.md 2026-11-14). Do not port.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/routes/guest.py` | edit | in `stay_overview` context: `entry_code` (decrypted, or None when outside the visibility window / not set), `guide_external_url` + its domain, existing `guide_live` |
| `App/app/templates/guest/stay.html` | edit | new Access block at the top of the completed state: entry-code line, then existing door-code block, then fee; guide block after the door code (internal guide button when `guide_live`, external link when set) replacing/upgrading the bottom card |
| `App/app/templates/guest/base.html` | edit | `?v=` bump only if guest CSS/JS files change |
| `App/app/i18n.py` | edit | new `t()` keys, every language (e.g. `entry_code_title`, `guide_open`, `guide_external`) |
| `App/tests/test_guest_*.py` | add/edit | page shows entry code inside the window, hides it outside / after `entry_code_until`; external link rendered with domain; entry code absent from QR guide |

No other file may change.

## 4. Steps

1. Verify anchors verbatim (grep; stop if missing — §8).
2. `routes/guest.py` `stay_overview`: compute and pass `entry_code` (None unless booked-level AND within `entry_code_until`), `guide_external_url`, `guide_external_host` (domain via urllib.parse), keep `guide_live`.
3. `stay.html`: insert the access block before `{% if door_code %}` (anchor 1) and the guide block after it; keep the completed-state ordering: entry code → apartment door code → fee → guide.
4. i18n keys all languages.
5. Tests + §6 commands + 390 px screenshot.

## 5. Do not touch

`routes/guest_guide_view.py` (QR guide must stay clean), `leon.py`, `mail*.py`, `claim.py`, analytics, exports, door_codes.py logic. No new dependency. Secret-grep the staged diff; the entry code value must never appear in the diff.

## 6. Commands

From `App/`: `.venv/bin/python -m pytest tests/test_guest_*.py -q --tb=short -x 2>&1 | tail -30`
From `App/`: `.venv/bin/python -m pytest tests/test_guest_browser_e2e.py tests/test_host_geometry.py -q -rs 2>&1 | tail -30` (0 skipped)
From `App/`: `.venv/bin/python -m pytest tests/test_leon.py tests/test_guest_guide*.py tests/test_*_i18n.py -q --tb=short -x 2>&1 | tail -30`
From repo root: `python3 scripts/context_lint.py 2>&1 | tail -10`

## 7. Acceptance

- [ ] Completed stay page renders: entry code line (booked window, before `entry_code_until`), door-code block, fee, guide block with internal button (guide live) and external link (domain shown, `rel="noopener noreferrer"`).
- [ ] Entry code hidden outside the window / after `entry_code_until`; absent from `/g/{token}` QR page and Leon prompt (test).
- [ ] Guest browser/geometry tests 0 skipped; one 390 px screenshot of the stay page in the report.
- [ ] `?v=` bumped if CSS/JS changed.

## 8. Stop and ask

Stop and write the report if: an excerpt is not found; a test fails twice; 25 tool calls or ~50k tokens; a file outside §3 needs a change; §5 would be touched; you need push/merge/deploy.

## 9. Report

Write `docs/tasks/1633-report.md` (≤600 tokens), `Status: review`, one PR. Include the 390 px screenshot path.

## Risk list (for the reviewer)

`App/app/routes/guest.py`, `App/app/templates/guest/stay.html`.

## Owner steps

1. Open the 390 px screenshot of the completed stay page; confirm the access block ordering (entry → door → fee → guide).
2. Go-first decision for 1634 (decisions.md 2026-11-14).
