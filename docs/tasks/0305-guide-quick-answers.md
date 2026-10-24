# 0305: Quick answers wizard (yes/no facts inside the cards)

Status: todo
Depends on: 0304 merged | Base commit: after 0304 | Branch: task/0305-guide-quick-answers
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Yes/no facts (pets, smoking, lift, cot, dishwasher, ...) are not cards (owner, 2026-10-24). The host answers them in five short steps, one topic per screen ("Quick answers"); each answer becomes one short line inside the card it belongs to, for guests and for Leon. Example: the House rules card shows "No pets. No smoking. Quiet hours from 22:00 to 07:00." The last screen, "Your guide", sends the host to the cards still to write ([plan](../plans/guest-guide.md)).

## 2. Context

- 22 facts in 5 steps (`times`, `rules`, `access`, `kitchen`, `comfort`), all in `guide_facts.FACTS`: fact, step, type (`yesno`, `time`, `range`) and the default card it shows in.
- Storage: new table `guide_fact` (migration number: the guide's reserved range is used up, so take the next free number the context lint prints at run time) (one row per answered fact, primary key `apartment_id, fact`, `ON DELETE CASCADE`). "Not sure" or an invalid value deletes the row. A row `step.<step>` = `seen` remembers a saved or skipped step, so `/guide/quick` resumes at the first step not seen. Property facts, no personal data: no retention rule. Every route checks ownership through `_home` (the same check as every guide page).
- Guests and Leon read cards through `guide_facts.for_guest(apartment_id, level, lang)`: `guest_guide.for_guest` plus a `facts` list per card. A default card the host has not written still reaches guests when it has facts, with its own text left out (a draft is never shown). Leon gets the English lines as a `facts:` line inside the card block, and `_card_corpus` includes them, so a cited card covers times like 22:00.
- Guest lines exist in every guest language (en, cs, de, es, fr in `i18n.py`, uk in `guest_uk_i18n.py`); host copy in en and cs. All copy is in `docs/plans/0305-files/quick_copy.py`, written by `apply_quick_copy.py`. Never retype copy.
- UX: one primary button per screen ("Save and continue"), a quiet "Skip this step", "Step 2 of 5" in the page meta, the back link returns to the guide (stop any time, resume later). A yes/no question is a `fieldset` with a `legend` and three native radios styled as big tap chips (Yes, No, Not sure; "Not sure" is checked until the host answers): full width at 390 px, 48 px tall, the checked chip filled with ink like a pressed `ui-chip`, a focus ring from `--focus-ring-2`, no JavaScript. The chips are a feature class (`quick-choice`, `quick-choice-options`, `quick-choice-option`) in `catalog.json` `classes` and `class_notes`, styled in `workflow.css` with tokens only; no new shared macro. Times are `ui_field` time inputs; a browser shows no ghost text in a time field, so their help line carries the example.
- New screen: owner decision line "2026-10-24 Guest guide: Quick answers wizard screen (owner)" is in `docs/context/decisions.md`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/migrations/NNNN_guide_fact.sql` | create (cp) | Table `guide_fact` (NNNN: next free from the lint, step 1) |
| `App/app/guide_facts.py` | create (cp) | Facts, steps, save, lines, `for_guest` |
| `App/app/templates/guest_guide_quick.html` | create (cp) | One step |
| `App/app/templates/guest_guide_quick_done.html` | create (cp) | "Your guide" summary |
| `App/app/host_i18n.py`, `App/app/i18n.py`, `App/app/guest_uk_i18n.py` | edit (script) | Copy |
| `App/app/routes/guest_guide.py` | edit | Quick routes, list page flag |
| `App/app/templates/guest_guide.html` | edit | Button and banner |
| `App/app/leon.py` | edit | Facts in the prompt and the guardrail |
| `App/app/routes/guest_guide_view.py` | edit | Facts on the guest page |
| `App/app/templates/guest/guide.html` | edit | Fact line |
| `App/tests/test_quick_answers.py`, `App/tests/test_quick_answers_browser.py` | create (cp) | Tests |
| `docs/design/catalog.json` | edit | Three feature classes and their notes |
| `App/app/static/workflow.css` | append | Chip styles |
| `App/app/templates/base.html` | edit | New `?v=` key for workflow.css |
| `App/tests/static_versions.json` | regenerate | `test_static_versions.py --write` |

No other file may change. `docs/plans/0305-files/` is read only.

## 4. Steps

1. From the repo root run `python3 scripts/context_lint.py 2>&1 | grep 'next free'`. The guide's reserved migration range is used up: use the migration number this line prints at run time as NNNN (never a number from this brief). Then run, with that number:
   `cp docs/plans/0305-files/guide_fact.sql App/app/migrations/NNNN_guide_fact.sql`
   `cp docs/plans/0305-files/guide_facts.py App/app/guide_facts.py`
   `cp docs/plans/0305-files/guest_guide_quick.html docs/plans/0305-files/guest_guide_quick_done.html App/app/templates/`
   `cp docs/plans/0305-files/test_quick_answers.py docs/plans/0305-files/test_quick_answers_browser.py App/tests/`

2. From the repo root run `python3 docs/plans/0305-files/apply_quick_copy.py 2>&1 | tail -30`. Expected, exactly: `quick answers: 53 host keys x 2, 41 guest keys x 6`. Anything else: STOP.

3. In `App/app/routes/guest_guide.py` replace

```python
from .. import access, auth, config, guest_guide, guest_guide_import, guest_guide_merge, guide_photos, guide_token, payments, security, templating
```

with

```python
from .. import access, auth, config, guest_guide, guest_guide_import, guest_guide_merge, guide_facts, guide_photos, guide_token, host_i18n, payments, security, templating
```

4. In the same file replace

```python
        next_id=_next_open(apartment_id, 0),
        import_on=guest_guide_import.enabled(),
```

with

```python
        next_id=_next_open(apartment_id, 0),
        quick_next=guide_facts.next_step(apartment_id),
        import_on=guest_guide_import.enabled(),
```

5. In the same file, directly before the line `@router.get("/apartments/{apartment_id}/guide/{item_id}")`, insert (followed by two blank lines):

```python
@router.get("/apartments/{apartment_id}/guide/quick")
def guide_quick(request: Request, apartment_id: int):
    guard = auth.require_login(request)
    if guard:
        return guard
    _home(request, apartment_id)
    return back(f"{_base(apartment_id)}/quick/{guide_facts.next_step(apartment_id) or 'done'}")


@router.get("/apartments/{apartment_id}/guide/quick/done")
def guide_quick_done(request: Request, apartment_id: int):
    guard = auth.require_login(request)
    if guard:
        return guard
    apartment = _home(request, apartment_id)
    guest_guide.ensure_defaults(apartment)
    lang = host_i18n.lang_from_request(request)
    lines = guide_facts.lines(apartment_id, lang)
    rows = guest_guide.items(apartment_id)
    answered = [
        (host_i18n.translate(lang, f"guest_guide.kind.{r['kind']}.title"), " ".join(lines[r["kind"]]))
        for r in rows if r["kind"] in lines
    ]
    return _render(
        request, "guest_guide_quick_done.html", apartment=apartment, answered=answered,
        open_cards=[r for r in rows if r["state"] in ("missing", "check")],
        progress=guest_guide.progress(apartment_id), next_id=_next_open(apartment_id, 0),
        first_step=guide_facts.STEPS[0],
    )


@router.get("/apartments/{apartment_id}/guide/quick/{step}")
def guide_quick_step(request: Request, apartment_id: int, step: str):
    guard = auth.require_login(request)
    if guard:
        return guard
    apartment = _home(request, apartment_id)
    if step not in guide_facts.STEPS:
        raise HTTPException(404)
    index = guide_facts.STEPS.index(step)
    return _render(
        request, "guest_guide_quick.html", apartment=apartment, step=step,
        step_index=index + 1, step_total=len(guide_facts.STEPS), last=index == len(guide_facts.STEPS) - 1,
        facts=guide_facts.step_fields(apartment_id, step),
    )


@router.post("/apartments/{apartment_id}/guide/quick/{step}")
async def guide_quick_save(request: Request, apartment_id: int, step: str):
    guard = auth.require_login(request)
    if guard:
        return guard
    _home(request, apartment_id)
    if step not in guide_facts.STEPS:
        raise HTTPException(404)
    form = await request.form()
    if form.get("skip"):
        guide_facts.mark_seen(apartment_id, step)
    else:
        guide_facts.save_step(apartment_id, step, form)
    index = guide_facts.STEPS.index(step) + 1
    following = guide_facts.STEPS[index] if index < len(guide_facts.STEPS) else "done"
    return back(f"{_base(apartment_id)}/quick/{following}")
```

6. In `App/app/templates/guest_guide.html` replace

```html
{% block secondary_actions %}{{ ui_button(t('guest_guide.qr.link'), 'secondary', href=base_url ~ '/qr') }}{% endblock %}
```

with

```html
{% block secondary_actions %}{{ ui_button(t('guest_guide.quick.link'), 'secondary', href=base_url ~ '/quick') }}{{ ui_button(t('guest_guide.qr.link'), 'secondary', href=base_url ~ '/qr') }}{% endblock %}
```

7. In the same file replace

```html
{% if progress.check %}{{ ui_banner('attention', t('guest_guide.check_waiting')) }}{% endif %}
```

with

```html
{% if progress.check %}{{ ui_banner('attention', t('guest_guide.check_waiting')) }}{% endif %}
{% if quick_next %}{{ ui_banner('neutral', t('guest_guide.quick.banner'), t('guest_guide.quick.start'), base_url ~ '/quick') }}{% endif %}
```

8. In `App/app/leon.py` replace

```python
from . import ai, db, guest_guide, host_i18n, i18n, rate_limit
```

with

```python
from . import ai, db, guest_guide, guide_facts, host_i18n, i18n, rate_limit
```

9. In the same file replace

```python
        lines.append(f"[c{card['id']}] {card_title(card)}")
```

with

```python
        lines.append(f"[c{card['id']}] {card_title(card)}")
        facts = [_clean_card_text(f) for f in card.get("facts") or []]
        if facts:
            lines.append("facts: " + " ".join(facts))
```

10. In the same file replace

```python
        " ".join([card_title(c), str(c.get("location") or ""), str(c.get("steps") or ""), str(c.get("watch_out") or "")])
```

with

```python
        " ".join([card_title(c), " ".join(c.get("facts") or []), str(c.get("location") or ""), str(c.get("steps") or ""), str(c.get("watch_out") or "")])
```

11. In the same file replace

```python
    cards = guest_guide.for_guest(apartment_id, level)
```

with

```python
    cards = guide_facts.for_guest(apartment_id, level, "en")
```

12. In `App/app/routes/guest_guide_view.py` replace

```python
from .. import claim, guest_guide, guide_photos, guide_token, host_i18n, mail, rate_limit
```

with

```python
from .. import claim, guest_guide, guide_facts, guide_photos, guide_token, host_i18n, mail, rate_limit
```

13. In the same file replace

```python
    for item in guest_guide.for_guest(apartment_id, level):
```

with

```python
    for item in guide_facts.for_guest(apartment_id, level, lang):
```

14. In the same file replace

```python
                "title": title,
```

with

```python
                "title": title,
                "facts": item["facts"],
```

15. In the same file replace

```python
    if not any(item["id"] == item_id for item in guest_guide.for_guest(apartment_id, level)):
```

with

```python
    if not any(item["id"] == item_id for item in guide_facts.for_guest(apartment_id, level, "en")):
```

16. In `App/app/templates/guest/guide.html` replace

```html
        <h2>{{ card.title }}</h2>
```

with

```html
        <h2>{{ card.title }}</h2>
        {% if card.facts %}<p>{{ card.facts | join(' ') }}</p>{% endif %}
```

17. In `docs/design/catalog.json` replace

```json
    "guide-photos",
    "guide-photo"
  ],
```

with

```json
    "guide-photos",
    "guide-photo",
    "quick-choice",
    "quick-choice-options",
    "quick-choice-option"
  ],
```

18. In the same file replace

```json
    "guide-photo": "0293 one photo with its delete button under it."
  }
```

with

```json
    "guide-photo": "0293 one photo with its delete button under it.",
    "quick-choice": "0305 Quick answers: one yes/no question, a fieldset whose legend is a ui-label.",
    "quick-choice-options": "0305 the row of three answer chips, full width.",
    "quick-choice-option": "0305 one answer: a label holding a native radio and its chip text; the checked chip is filled like a pressed ui-chip."
  }
```

19. From the repo root run `cat docs/plans/0305-files/quick_choice.css >> App/app/static/workflow.css`.

20. In `App/app/templates/base.html` replace `/static/workflow.css?v=20261024-0293` with `/static/workflow.css?v=20261024-0305`.

21. From `App/` run `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -30`. Expected: one line starting with `wrote` and ending with `files)`. A line starting with `refusing`: STOP.

## 5. Do not touch

Everything else, including `guest_guide.py`, `db.py`, `retention.py`, `_ui.html` and every CSS file except `workflow.css`. No class beyond the three of step 17, no new macro, no new dependency.

## 6. Commands

From `App/`:

- `.venv/bin/python -m pytest tests/test_quick_answers.py tests/test_static_versions.py -q --tb=short 2>&1 | tail -30`. Expected: `10 passed`.
- `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_quick_answers_browser.py tests/test_guest_guide_browser.py -q -rs --tb=short 2>&1 | tail -30`. Expected: `3 passed`, 0 skipped (set `UBYHOST_BROWSER_EXECUTABLE` to the Chromium path if Playwright's own browser is missing). The test saves `App/.screenshots/0305-quick-rules-390.png`; look at it once.
- `.venv/bin/python -m pytest tests/test_guest_guide*.py tests/test_guide*.py tests/test_leon.py tests/test_migrations*.py tests/test_db*.py -q --tb=short 2>&1 | tail -30`. Expected: `0 failed`.
- `.venv/bin/python -m pytest tests/test_*_i18n.py tests/test_no_em_dashes.py tests/test_copy_cleanup.py tests/test_flash_literals.py tests/test_design_*.py -q --tb=line 2>&1 | tail -30`. Expected: exactly the 3 old failures in `tests/test_host_i18n.py` (two `..._vietnamese`, one `..._open_redirects`). Any other failure: fix once, then STOP.

From the repo root: `python3 scripts/design_lint.py 2>&1 | tail -30` and `python3 scripts/context_lint.py 2>&1 | tail -30`. Expected: both end with `OK`.

## 7. Acceptance

- [ ] Only the files of §3 change (plus the report).
- [ ] `test_quick_answers.py`: 7 passed; the browser row 3 passed, 0 skipped; the other rows pass.
- [ ] Both lints OK.

## 8. Stop and ask

Stop, and write the report, if: 0304 is not merged (`grep -c something_wrong App/app/guest_guide.py` is 0); step 2 prints anything but the expected line; an anchor is not found exactly once; a test fails twice; you reach 25 tool calls or about 50k tokens; a file outside §3 needs a change; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0305-report.md` (600 tokens at most) and set `Status: review`: files changed, the migration number used, the screenshot path, each command with its last 5 lines, §7 ticked, deviations, questions, owner steps left. The orchestrator adds 390 px screenshots of one step, the summary, the card list and the guest page (rule 7).

## Risk list (for the reviewer)

- Guest gate: `guide_facts.for_guest` keeps every rule of `guest_guide.for_guest` (live check, level, `done` only for host text) and adds only fact lines; a draft's text never leaves.
- Leon cites a card id whose corpus now holds the fact lines; numbers in them come from validated `HH:MM` values only.
- Ownership: every quick route calls `_home` before reading or writing; a foreign or unknown step is a 404.
- Migration: one table, no data change, cascade with the property.

## Owner steps

1. Review and merge once CI is green. The migration runs on deploy.
