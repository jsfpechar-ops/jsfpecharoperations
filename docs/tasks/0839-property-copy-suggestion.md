# 0839: Add property: suggest "copy settings from" the last property

Status: todo
Depends on: 0841 (baseline first); runs **after** the property-editor and onboarding-speed threads merge | Base commit: b8c87df | Branch: task/0839-property-copy-suggest
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

On `/apartments/new`, a host who already has a property sees one link "Copy settings from <name>" above the form; one tap reloads the form with the existing copy-from prefill and its notice. Target: 3 to 2 taps for a second property (settings no longer re-entered).

## 2. Context

Verified on b8c87df, already built, do not redo:
- Purpose: `App/app/templates/_property_create.html` line 28 posts `default_purpose` = copied value or `10`.
- Operator: `App/app/templates/_property_operator.html` lines 8-14 preselect the only entity (`elif entities | length == 1`).
- Copy-from: `GET /apartments/new?copy_from=<id>` is handled by `_property_copy_form_context` (`App/app/routes/admin.py` around line 1583) and shows `apartment.form.copy_from.notice` ("Copied from %(name)s. Check and save."). No template links to it today (`grep -rn 'copy_from=' App/app/templates` is empty).

So the only change is the suggestion link. Copying carries filing settings (`automation_mode`, `submit_after_hours`); that is a suggestion the host confirms: the existing notice shows, nothing saves until "create" (UbyPort rule 1).

**Overlap:** `_property_create.html` and `admin.py` are near files the property-editor and onboarding-speed threads change. Do not run this brief until the coordinator says those threads merged; if any anchor below is missing, STOP. Do not touch `apartment_form.html` or any wizard file.

Anchors:
- `App/app/routes/admin.py` in `_render_apartment_new` (around line 1430):
```python
            "selected_entity_id": selected_entity_id,
```
- `App/app/templates/_property_create.html` line 21:
```html
    <form method="post" action="/apartments" class="property-create-form" id="property-create-form">
```
- `App/app/access.py` line 141: `def apartments(request: Request, columns: str = "*", include_archived: bool = False):`
- i18n anchors: `App/app/host_i18n.py` line 3922 (EN) and 4744 (CS) `"apartment.form.copy_from.notice"`; `App/app/host_vi_i18n.py` line 1745.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/routes/admin.py` | edit | `copy_suggestion` in `_render_apartment_new` |
| `App/app/templates/_property_create.html` | edit | One link |
| `App/app/host_i18n.py` | edit | EN + CS key |
| `App/app/host_vi_i18n.py` | edit | VI key |
| `App/tests/test_property_create_browser.py` | edit | Two tests |
| `docs/tasks/0839-report.md` | new | Report |

No other file may change.

## 4. Steps

1. `admin.py`: in `_render_apartment_new`, directly above `    return render(` (the one in that function), add:
```python
    copy_suggestion = None
    if not copy_ctx.get("copy_from_id"):
        own = list(access.apartments(request, "id, internal_name"))
        if own:
            copy_suggestion = max(own, key=lambda row: row["id"])
```
   and below `            "selected_entity_id": selected_entity_id,` add `            "copy_suggestion": copy_suggestion,`. Commit.
2. `_property_create.html`: directly above the form anchor insert:
```html
    {% if copy_suggestion and not copied_from_name %}
    <p class="property-create-copy-suggest"><a class="ui-btn ui-btn-secondary" href="/apartments/new?copy_from={{ copy_suggestion.id }}">{{ t('property_create.copy_suggest', name=copy_suggestion.internal_name) }}</a></p>
    {% endif %}
```
   Commit.
3. i18n below each `apartment.form.copy_from.notice` line: EN `        "property_create.copy_suggest": "Copy settings from %(name)s",`; CS `        "property_create.copy_suggest": "Převzít nastavení z %(name)s",`; VI `    "property_create.copy_suggest": "Sao chép cài đặt từ %(name)s",`. Commit.
4. Tests in `test_property_create_browser.py`, after `test_one_operator_is_chosen_and_one_submit_creates_a_manual_property`, reusing its setup: (a) a host with one property gets a link `href="/apartments/new?copy_from=<id>"`; (b) opening that href shows "Copied from" and no suggestion link; (c) a host with no property gets no link (add to (a) if the setup makes this easy). Commit.
5. Run §6 and take the 390 px screenshot of `/apartments/new` with the link. Commit.

## 5. Do not touch

`_property_copy_form_context`, the POST `/apartments` handler, `_property_operator.html`, `apartment_form.html`, wizard, onboarding and property-editor files. No autosave; address fields unchanged.

## 6. Commands

From `App/`:
1. Properties row: `.venv/bin/python -m pytest tests/test_onboarding*.py tests/test_property_*.py tests/test_first_*.py -q --tb=short -x -rs 2>&1 | tail -30`
2. Host row: `.venv/bin/python -m pytest tests/test_host_*.py tests/test_host_geometry.py tests/test_design_guardrails_browser.py -q --tb=short -x -rs 2>&1 | tail -30`
3. Copy row: `.venv/bin/python -m pytest tests/test_*_i18n.py tests/test_no_em_dashes.py tests/test_copy_cleanup.py tests/test_flash_literals.py -q --tb=short -x 2>&1 | tail -30`

Expected: all pass, 0 skipped.

## 7. Acceptance

- [ ] Second property: one tap on the link fills the form from the last property with the existing notice.
- [ ] First property: no link. Nothing saves without "create".
- [ ] Link sits at least 12 px from its neighbours (geometry/guardrail tests pass).
- [ ] Commands 1-3 pass, 0 skipped; one 390 px screenshot of `/apartments/new`.

## 8. Stop and ask

Stop, and write the report, if an excerpt is not found; a test fails twice; you reach 25 tool calls or about 50k tokens (report `blocked`, see executor.md); a new dependency seems needed; a file outside §3 needs a change; §5 would be touched; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0839-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with its last 5 lines, §7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

`App/app/routes/admin.py` (`access.apartments` must stay owner-scoped), `App/app/templates/_property_create.html` (overlap with other threads).

## Owner steps

1. Confirm the property-editor and onboarding-speed PRs are merged before starting this brief.
2. Check the screenshot, then merge with `scripts/merge-pr-on-green.sh <pr>` when CI is green.
