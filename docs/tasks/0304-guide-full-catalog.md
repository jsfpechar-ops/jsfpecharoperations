# 0304: The full card catalog (few, rich cards with ghost text)

Status: todo
Depends on: 0291 to 0300 merged | Base commit: after 0300 | Branch: task/0304-guide-full-catalog
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Every property gets 17 cards that together cover what a guest asks (owner, 2026-10-24: "cover EVERYTHING about a property", "make the cards as less as possible"). Each card's prompt is a short checklist, and every text field shows greyed ghost text: a detailed, invented example for that card, gone as soon as the host types ([plan](../plans/guest-guide.md)). Yes/no facts (pets, lift, cot, ...) are not cards: they come in 0305 (Quick answers).

## 2. Context

- Catalog after this brief: 11 topics (keys unchanged), 24 built-in kinds. 17 are default cards (every property). The other 7 (`garage`, `tv`, `air_conditioning`, `dishwasher`, `coffee_machine`, `sofa_bed`, `balcony`) are narrower cards kept because data and 0298 use them: they appear only where an import or earlier data created them. New kinds: `getting_here`, `bedrooms`, `bathroom`, `something_wrong`. No kind key is renamed or removed; `MUST_HAVE` stays the same five.
- All copy (titles, checklists, ghost text, en and cs) is in `docs/plans/0304-files/catalog_copy.py`; `apply_catalog.py` writes it into the code. Never retype copy.
- `ensure_defaults` runs on every list page load (0292). `add_kind` is idempotent (`ON CONFLICT DO NOTHING` on `uq_guide_item_kind`), so existing properties get the new cards on their next visit; text already written is never touched.
- `items()` now takes topic and order of a built-in card from the catalog, not from the stored row, so new cards sit in the right place next to old rows.
- Guests read card titles in en or cs; other guest languages read English (`_copy_lang` in `routes/guest_guide_view.py`, 0294). So en and cs cover every guest language.
- 0298's merge prompt lists `KINDS` itself, so it follows the catalog with no change.
- Ghost text is the HTML `placeholder` attribute: the browser never submits it. Newlines in a textarea placeholder render as line breaks. `ui_field` already takes `placeholder`; `ui_textarea` gets the same argument here. Placeholder colour: `--ink-muted` (#73736e on white, 4.8:1, AA); browser defaults are lighter than AA in Safari and Firefox.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/guest_guide.py` | edit (script + steps 2 to 4) | Catalog, `ensure_defaults`, `items`, `progress` |
| `App/app/host_i18n.py` | edit (script) | Topic and card copy, ghost text, progress lines |
| `App/app/templates/_ui.html` | edit | `ui_textarea` takes `placeholder` |
| `App/app/templates/guest_guide_card.html` | edit | Ghost text on the three fields |
| `App/app/templates/guest_guide.html` | edit | Progress line |
| `App/app/static/host2.css` | edit | Placeholder colour |
| `App/app/templates/base.html` | edit | New `?v=` key for host2.css |
| `App/tests/static_versions.json` | regenerate | `test_static_versions.py --write` |
| `App/tests/test_guest_guide.py` | append | Catalog tests |
| `App/tests/test_guest_guide_pages.py` | edit, append | Progress line, ghost text test |

No other file may change. `docs/plans/0304-files/` is read only.

## 4. Steps

1. From the repo root run `python3 docs/plans/0304-files/apply_catalog.py 2>&1 | tail -30`. Expected, exactly: `catalog: 11 topics, 24 cards, 17 default`. Anything else (for example `AssertionError: already applied`): STOP.

2. In `App/app/guest_guide.py` replace

```python
    for kind in DEFAULT_KINDS:
        add_kind(apartment["id"], kind)
```

with

```python
    have = {r["kind"] for r in db.query("SELECT kind FROM guide_item WHERE apartment_id = ?", (apartment["id"],))}
    for kind in DEFAULT_KINDS:
        if kind not in have:
            add_kind(apartment["id"], kind)
```

3. In the same file replace

```python
    out = [dict(row) for row in rows]
    out.sort(key=lambda r: TOPICS.index(r["topic"]) if r["topic"] in TOPICS else len(TOPICS))
```

with

```python
    out = [dict(row) for row in rows]
    for row in out:
        if row["kind"] in KINDS:
            # The catalog decides where a built-in card sits, so cards added later
            # (0304) line up with the ones a property already had.
            row["topic"], row["sort_order"] = KINDS[row["kind"]], _order(row["kind"])
    out.sort(key=lambda r: (TOPICS.index(r["topic"]) if r["topic"] in TOPICS else len(TOPICS), r["sort_order"], r["id"]))
```

4. In the same file replace

```python
    return {
        "done": done,
        "total": len(counted),
```

with

```python
    return {
        "done": done,
        "total": len(counted),
        # Skipped counts as answered: the host has dealt with the card.
        "answered": sum(1 for r in rows if r["state"] in ("done", "skipped")),
        "cards": len(rows),
```

5. In `App/app/templates/_ui.html` replace

```html
{% macro ui_textarea(id, label, value='', name='', help='', error='', optional=false, rows=3, attrs='') -%}
```

with

```html
{% macro ui_textarea(id, label, value='', name='', help='', error='', optional=false, rows=3, attrs='', placeholder='') -%}
```

6. In the same file replace

```html
  <textarea class="ui-textarea" id="{{ id }}" name="{{ name or id }}" rows="{{ rows }}"{% if error %}
```

with

```html
  <textarea class="ui-textarea" id="{{ id }}" name="{{ name or id }}" rows="{{ rows }}"{% if placeholder %} placeholder="{{ placeholder }}"{% endif %}{% if error %}
```

7. In `App/app/templates/guest_guide_card.html` replace these three lines

```html
{{ ui_field('guide-location', t('guest_guide.field.location'), name='location', value=values.location, help=t('guest_guide.field.location_help'), optional=true, attrs='maxlength="500"') }}
{{ ui_textarea('guide-steps', t('guest_guide.field.steps'), value=values.steps, name='steps', help=t('guest_guide.field.steps_help'), rows=8, attrs='maxlength="4000"') }}
{{ ui_textarea('guide-watch-out', t('guest_guide.field.watch_out'), value=values.watch_out, name='watch_out', help=t('guest_guide.field.watch_out_help'), optional=true, rows=3, attrs='maxlength="1000"') }}
```

with

```html
{% set ph = 'guest_guide.custom.ph.' if custom else 'guest_guide.kind.' ~ item.kind ~ '.ph.' %}
{{ ui_field('guide-location', t('guest_guide.field.location'), name='location', value=values.location, help=t('guest_guide.field.location_help'), optional=true, attrs='maxlength="500"', placeholder=t(ph ~ 'location')) }}
{{ ui_textarea('guide-steps', t('guest_guide.field.steps'), value=values.steps, name='steps', help=t('guest_guide.field.steps_help'), rows=8, attrs='maxlength="4000"', placeholder=t(ph ~ 'steps')) }}
{{ ui_textarea('guide-watch-out', t('guest_guide.field.watch_out'), value=values.watch_out, name='watch_out', help=t('guest_guide.field.watch_out_help'), optional=true, rows=3, attrs='maxlength="1000"', placeholder=t(ph ~ 'watch_out')) }}
```

8. In `App/app/templates/guest_guide.html` replace

```html
{% block meta %}{{ t('guest_guide.progress', done=progress.done, total=progress.total) }}{% endblock %}
```

with

```html
{% block meta %}{% if progress.live %}{{ t('guest_guide.progress_live', answered=progress.answered, total=progress.cards) }}{% else %}{{ t('guest_guide.progress', answered=progress.answered, total=progress.cards) }}{% endif %}{% endblock %}
```

9. In `App/app/static/host2.css`, directly after the line that starts with `.host-workspace .ui-field .ui-textarea { height: auto;`, insert this line:

```css
.host-workspace .ui-field :is(.ui-input, .ui-textarea)::placeholder { color: var(--ink-muted); opacity: 1; }
```

10. In `App/app/templates/base.html` replace `/static/host2.css?v=20261022-0289` with `/static/host2.css?v=20261024-0304` (a changed stylesheet needs a new key; the old one is cached for a year).

11. From `App/` run `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -30`. Expected: one line starting with `wrote` and ending with `files)`. A line starting with `refusing`: STOP.

12. From the repo root run `cat docs/plans/0304-files/test_catalog_append.py >> App/tests/test_guest_guide.py` and `cat docs/plans/0304-files/test_pages_append.py >> App/tests/test_guest_guide_pages.py`.

13. In `App/tests/test_guest_guide_pages.py` replace

```python
    assert len(_cards(ws["home"])) == len(guest_guide.DEFAULT_KINDS)
```

with

```python
    assert len(_cards(ws["home"])) == len(guest_guide.DEFAULT_KINDS)
    assert f"0 of {len(guest_guide.DEFAULT_KINDS)} cards answered" in body
```

## 5. Do not touch

Everything else, including `guest_guide_merge.py`, `leon.py`, `routes/`, `i18n.py`, `docs/design/catalog.json`. No new class, no migration.

## 6. Commands

From `App/`:

- `.venv/bin/python -m pytest tests/test_guest_guide*.py tests/test_guide*.py tests/test_leon.py -q --tb=short 2>&1 | tail -30`. Expected: `0 failed` (about 144 passed, 2 skipped).
- `.venv/bin/python -m pytest tests/test_static_versions.py -q --tb=short 2>&1 | tail -30`. Expected: `0 failed`.
- `.venv/bin/python -m pytest tests/test_*_i18n.py tests/test_no_em_dashes.py tests/test_copy_cleanup.py tests/test_flash_literals.py tests/test_design_*.py -q --tb=line 2>&1 | tail -30`. Expected: exactly 3 failed, all in `tests/test_host_i18n.py` (`..._vietnamese` twice and `test_language_endpoint_sets_cookie_and_rejects_open_redirects`; they fail before this brief too). Any other failure: fix once, then STOP.

From the repo root: `python3 scripts/design_lint.py 2>&1 | tail -30` and `python3 scripts/context_lint.py 2>&1 | tail -30`. Expected: both end with `OK`.

## 7. Acceptance

- [ ] Only the files of §3 change (plus the report).
- [ ] The new tests pass: catalog complete in en and cs, existing property gets the new cards and keeps its text, skipped counts as answered, ghost text shown and never saved.
- [ ] Both lints OK.

## 8. Stop and ask

Stop, and write the report, if: step 1 prints anything but the expected line; an anchor is not found exactly once; a test fails twice; you reach 25 tool calls or about 50k tokens; a file outside §3 needs a change; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0304-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with its last 5 lines, §7 ticked, deviations, questions, owner steps left. The orchestrator adds one 390 px screenshot each of the card list and the Wi-Fi card (rule 7: template and CSS change).

## Risk list (for the reviewer)

- No data changes: new cards are inserted empty; existing rows keep text, state and source. Kinds outside `DEFAULT_KINDS` are never created by `ensure_defaults`.
- `items()` reorders built-in cards by the catalog: guest page, Leon (`for_guest`) and the list page all read `items()`.
- Ghost text is escaped by the macros; `catalog_copy.py` holds no `"`, `<`, `>` or `&`.

## Owner steps

1. Review and merge once CI is green.
