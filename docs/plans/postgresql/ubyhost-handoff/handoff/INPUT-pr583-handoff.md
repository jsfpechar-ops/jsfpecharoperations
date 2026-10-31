# Fix and complete PR #583

**Repository:** `jsfpechar-ops/jsfpecharoperations`  
**PR:** [#583](https://github.com/jsfpechar-ops/jsfpecharoperations/pull/583)  
**Reviewed commit:** `69efd1a51212d2a2e20d96c62c8138a020496272`

Work on the existing PR branch. First check whether the head has changed and whether these fixes are already present. Follow `AGENTS.md` and the repository’s executor instructions.

## Required experience

For three guests:

1. Guest 1 completes their form and signs → **Save and continue to the next person** → guest 2 opens immediately.
2. Guest 2 completes their form and signs → **Save and continue to the next person** → guest 3 opens immediately.
3. Guest 3 completes their form and signs → **Submit registration** → completed registration summary.

There must be no mandatory **Saved / Add a person** page between guests.

The required acknowledgement stays visible. Optional legal explanations expand on demand.

Editing a saved guest is a separate action: **Save changes**, returning to the registration summary.

## Fix 1: keep the required acknowledgement visible

**File:** `App/app/templates/guest/form.html`

The PR currently wraps `_legal_notice.html` in an outer `<details>`. That partial already has its own disclosure for the legal text. Consequently, the required checkbox is hidden, and reading the notice requires opening two disclosures.

Replace:

```jinja2
    <details class="g-legal-fold">
      <summary>{{ t('legal_notice_title') }}</summary>
      {% include "guest/_legal_notice.html" %}
    </details>
```

With:

```jinja2
    {% include "guest/_legal_notice.html" %}
```

Keep the structure already introduced in `App/app/templates/guest/_legal_notice.html`:

```jinja2
<div class="g-card g-legal-notice" id="legal-notice">
  <details class="g-legal-text">
    <summary>{{ t('legal_notice_title') }}</summary>

    {# Existing complete legal notice stays here. #}
  </details>

  <div class="g-field legal-ack">
    <label class="checkline" for="legal_ack">
      <input type="checkbox"
             id="legal_ack"
             name="legal_ack"
             value="1"
             required
             {% if values.get('legal_ack') %}checked{% endif %}>
      <span>{{ t('legal_ack_label') }}</span>
    </label>
    {{ err_for('legal_ack') }}
  </div>
</div>
```

The comment above represents the existing legal content: **do not replace that content with the comment or delete it.**

Result:

- One disclosure opens the complete legal notice.
- The acknowledgement is visible even when the notice is collapsed.
- Server-side acknowledgement validation remains enforced.
- Existing legal wording remains intact.

## Fix 2: distinguish creating a guest from editing one

**File:** `App/app/routes/guest.py`  
**Function:** `_form_context`

The current `remaining == 1` condition mislabels edits after all guests are registered: `remaining` becomes zero, so the button promises another guest even though saving returns to the summary.

Immediately after calculating `remaining`, add:

```python
    if guest is not None:
        save_action_key = "guest_save_changes"
    elif remaining is None:
        # The fallback form can collect the headcount itself.
        # Do not claim the group is complete before that count is known.
        save_action_key = "guest_save_details"
    elif remaining <= 1:
        save_action_key = "submit_registration"
    else:
        save_action_key = "save_continue_next"
```

In `context.update(...)`, replace the PR’s `is_last_outstanding` entry and its associated comment with:

```python
            "save_action_key": save_action_key,
```

Keep the existing `just_saved` entry.

**File:** `App/app/templates/guest/form.html`

Replace:

```jinja2
    <button class="g-btn" type="submit">{{ t('submit_registration') if is_last_outstanding else t('save_continue_next') }}</button>
```

With:

```jinja2
    <button class="g-btn" type="submit">
      {{ t(save_action_key) }}
    </button>
```

Remove the obsolete comment claiming every nonfinal save advances to another person.

### Add translations

Add these entries to the corresponding existing language dictionaries. Do not replace the dictionaries.

| Language | `guest_save_changes` | `guest_save_details` |
|---|---|---|
| English | Save changes | Save details |
| Czech | Uložit změny | Uložit údaje |
| German | Änderungen speichern | Angaben speichern |
| Spanish | Guardar cambios | Guardar datos |
| French | Enregistrer les modifications | Enregistrer les informations |
| Ukrainian | Зберегти зміни | Зберегти дані |

English, Czech, German, Spanish, and French live in `App/app/i18n.py`. Ukrainian lives in `App/app/guest_uk_i18n.py`.

## Fix 3: make edit navigation match “Save changes”

**File:** `App/app/routes/guest.py`  
**Function:** `guest_form_save`

The PR applies direct progression to both new guests and edits. For an edit, return to the summary so the action matches **Save changes**.

Replace the redirect block after the existing reporting, door-code, and completion-notification calls with:

```python
    progress_after_save = reporting.reservation_progress(reservation)
    missing = progress_after_save["missing"]

    # Newly completed guests advance directly while people remain.
    # Editing an existing guest returns to the registration summary.
    continue_to_next = (
        existing is None
        and missing is not None
        and missing > 0
    )

    destination = _guest_link(token, reservation_id)
    if continue_to_next:
        destination += "/new"

    response = RedirectResponse(
        destination + _lang_q(lang, "&saved=1"),
        status_code=303,
    )
    _remember_owned(response, _owned_ids(request) + [saved_id])
    return _with_lang(response, lang)
```

Preserve the existing save validation, capacity checks, ownership checks, cookies, reporting calls, and notification guards.

Do not change police-filing behavior to implement this navigation change.

## What is still missing from the original request

### A. Contextual explanations are incomplete

The PR collapses the email/cookie paragraphs, but does not add explanations for the other information collected.

The current form contains:

- First name and surname.
- Date of birth.
- Nationality.
- Passport or ID number.
- Child-in-parent-document information.
- Visa number.
- Purpose of stay.
- Permanent address.
- Conditional document upload.
- Signature.

Some fields already have entry guidance. However, entry guidance is different from explaining **why the information is needed**. The shared `_why.html` currently provides only a general introduction, accuracy guidance, legal reference, and privacy link.

Complete this part of the request:

- Add relevant contextual help beside fields or logically grouped sections.
- Explain the purpose using existing approved legal/privacy sources.
- Reuse existing explanations instead of duplicating paragraphs.
- Keep formatting instructions and validation errors visible.
- Keep help usable by touch and keyboard.
- Preserve nationality-dependent and document-upload conditions.
- Do not invent legal requirements or change required fields.

### B. Email help needs a clear accessible label

The new email disclosure uses the generic `why_title` as its accessible name. Give it a localized label describing its purpose, such as **“Why we need your email”**.

Its CSS also adds a generated `?` while the summary contains a literal `?`. Use one visible question mark, avoiding duplicate decoration.

### C. The save-confirmation wording is unclear

The new English string is:

```python
"person_saved": "Previous guest saved. Now their details.",
```

“their” is ambiguous. A clearer replacement is:

```python
"person_saved": "Previous guest saved.",
```

The existing person counter and form heading provide the next action’s context. Review equivalent translations for clarity.

## Required regression coverage

Extend the existing test files and fixtures. Verify behavior rather than relying only on template-string assertions.

| Scenario | Expected result |
|---|---|
| One-person booking | “Submit registration”; save reaches completed summary. |
| Three-person booking, guest 1 | Save redirects directly to guest 2’s form. |
| Three-person booking, guest 2 | Save redirects directly to guest 3’s form. |
| Three-person booking, guest 3 | “Submit registration”; save reaches summary. |
| Edit eligible saved guest after completion | “Save changes”; save returns to summary. |
| Edit eligible saved guest while others remain | “Save changes”; save returns to summary. |
| Missing acknowledgement | Cannot save; checkbox and error are discoverable. |
| Collapsed legal notice | Acknowledgement remains visible. |
| Next guest’s form | Previous identity, signature, and acknowledgement are absent. |
| Validation failure | Entered values and valid signature are retained. |
| Reopen private link | Saved progress remains available. |
| Unknown-headcount fallback | Neutral action label; saved headcount determines progression. |

Add a real browser assertion that the checkbox is visible while `.g-legal-text` is closed. This catches the nesting bug that the current markup tests missed.

## CI and delivery requirements

At the reviewed commit, these checks failed:

- `test`
- `smoke`
- `browser shard 2`
- Aggregate `browser`

The previous reviewer could not retrieve failure annotations. **Their causes are not established.** Read the actual CI failures, fix regressions, and distinguish outdated flow expectations from unrelated failures. Do not weaken tests merely to make them pass.

Before returning the PR:

1. Run the focused checks required by the repository’s test map.
2. Pass the required browser and geometry checks with zero skipped tests.
3. Supply 390 px screenshots of the changed claim page, signature/acknowledgement screen, next-guest form, and completion screen.
4. Update the PR description to reflect the final behavior and actual verification.
5. Remove the invalid `Closes #0` line.
6. Keep merging and production deployment with the owner.

**Delivery report:** identify the fix commit, tests run, remaining failures, screenshot evidence, and any incomplete contextual-help wording.