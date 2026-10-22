# 0239: Stay fee setup asks four boxes

Status: review
Depends on: main after PR #422 | Branch: claude/project-thread-kbrf7w
Executor: Haiku 5.5 | Fits one session: 30 tool calls

## 1. Objective

Owner (Josef, 2026-10-22): the stay fee setup must ask as little as possible. The setup wizard asks exactly four boxes: fee per night, variable symbol, council bank account, council name. "Monthly or quarterly" leaves the wizard (monthly is the database default; Settings can still change it). In property Settings the council's address, contact line and data box fold under "More details (optional)". No per-city prefill.

## 2. Context

- `App/app/templates/_stay_fee_fields.html` is the one fee editor; the wizard renders it with `fee_required = true`, Settings with it unset. Today the wizard shows rate, cadence, VS, account and hides the whole council block.
- `stay_fee.report_issues` refuses to finalise a report without `stay_fee_authority_name`; that is why the name moves into the wizard. Address, contact and data box are only printed on the PDF.
- `stay_fees.fee_form_values` always writes `stay_fee_cadence` (default "monthly"); with the select gone from the wizard, a wizard save would reset a stored "quarterly". Step 1 fixes that.
- The earlier "council block is never folded" rule in `tests/test_fee_setup_compatibility.py` is replaced by this owner decision.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/routes/stay_fees.py` | edit | step 1 |
| `App/app/templates/_stay_fee_fields.html` | edit | steps 2, 3 |
| `App/app/host_i18n.py`, `App/app/host_vi_i18n.py` | edit | step 4 |
| `docs/design/catalog.json` | edit | step 5 |
| `App/tests/test_fee_form_partial.py`, `App/tests/test_fee_setup_compatibility.py` | edit | steps 6, 7 |
| `docs/tasks/0239-report.md` | create | report |

## 4. Steps

1. `App/app/routes/stay_fees.py`, in `fee_form_values`. Anchor (exact lines):

```python
    cadence = _form_str(form, "stay_fee_cadence", "monthly")
    values = {
        "stay_fee_rate_czk": rate,
        "stay_fee_cadence": cadence if cadence in stay_fee.CADENCES else "monthly",
        "stay_fee_vs": (
            "".join(ch for ch in _form_str(form, "stay_fee_vs") if ch.isdigit())[:10] or None
        ),
    }
```

Replace with:

```python
    values = {
        "stay_fee_rate_czk": rate,
        "stay_fee_vs": (
            "".join(ch for ch in _form_str(form, "stay_fee_vs") if ch.isdigit())[:10] or None
        ),
    }
    # 0239: the setup wizard no longer asks the period; a form without it keeps
    # the stored one (new properties start monthly, the database default).
    if "stay_fee_cadence" in form:
        cadence = _form_str(form, "stay_fee_cadence", "monthly")
        values["stay_fee_cadence"] = cadence if cadence in stay_fee.CADENCES else "monthly"
```

Commit `0239 step 1`.

2. `App/app/templates/_stay_fee_fields.html`:
   - Line 2 comment: replace `Settings -> Reporting & fees -> Stay fee. Every section is visible: nothing is folded away. -#}` with `Settings -> Reporting & fees -> Stay fee and in the setup wizard (fee_required). 0239: the wizard asks rate, symbol, account and council name; the office's print-only details fold away in Settings. -#}`
   - Wrap the cadence field: put `{% if not fee_required %}` on its own line directly before the line `    <div class="field">` that precedes `{{ field_label('stay_fee_cadence'`, and `{% endif %}` on its own line directly after that field's closing `    </div>` (the one after `</select>`).

   Commit `0239 step 2`.

3. Same file, replace everything from the line starting `{#- 0205: the wizard asks only rate` up to and including the line `</div>{% endif %}` with:

```jinja
{#- 0239: the council name is needed to finalise a report, so the wizard asks it; the rest is only printed on the PDF. -#}
<div class="fee-setup-section" id="stay-fee-council">
  <h4 class="property-subsection-title">3. {{ t('stay_fees.setup.council') }}</h4>
  <div class="field">
    {{ field_label('stay_fee_authority_name', t('apartment.form.stay_fee.authority_name_label'), t('apartment.form.stay_fee.authority_name_help')) }}
    <input id="stay_fee_authority_name" name="stay_fee_authority_name" aria-describedby="stay_fee_authority_name-help" maxlength="200" value="{{ apartment.stay_fee_authority_name or '' }}"{% if fee_required %} required{% endif %}>
  </div>
  {% if not fee_required %}
  <details class="fee-more"{% if apartment.stay_fee_authority_address or apartment.stay_fee_authority_contact or apartment.stay_fee_authority_databox %} open{% endif %}>
    <summary>{{ t('stay_fees.setup.more_details') }}</summary>
    <div class="field">
      {{ field_label('stay_fee_authority_address', t('apartment.form.stay_fee.authority_address_label'), t('apartment.form.stay_fee.authority_address_help')) }}
      <input id="stay_fee_authority_address" name="stay_fee_authority_address" aria-describedby="stay_fee_authority_address-help" maxlength="200" value="{{ apartment.stay_fee_authority_address or '' }}">
    </div>
    <div class="field">
      {{ field_label('stay_fee_authority_contact', t('apartment.form.stay_fee.authority_contact_label'), t('apartment.form.stay_fee.authority_contact_help')) }}
      <input id="stay_fee_authority_contact" name="stay_fee_authority_contact" aria-describedby="stay_fee_authority_contact-help" maxlength="200" value="{{ apartment.stay_fee_authority_contact or '' }}">
    </div>
    <div class="field">
      {{ field_label('stay_fee_authority_databox', t('apartment.form.stay_fee.authority_databox_label'), t('apartment.form.stay_fee.authority_databox_hint')) }}
      <input id="stay_fee_authority_databox" name="stay_fee_authority_databox" maxlength="7" autocapitalize="off" spellcheck="false" aria-describedby="stay_fee_authority_databox-help" value="{{ apartment.stay_fee_authority_databox or '' }}">
    </div>
  </details>
  {% endif %}
</div>
```

Commit `0239 step 3`.

4. Strings. Add one line directly after each existing `"stay_fees.setup.council"` line:
   - `App/app/host_i18n.py` EN block (the line with `"Council and delivery"`): `        "stay_fees.setup.more_details": "More details (optional)",`
   - same file CS block (`"Úřad a doručení"`): `        "stay_fees.setup.more_details": "Další údaje (nepovinné)",`
   - `App/app/host_vi_i18n.py` (`"Chính quyền và cách gửi"`): `    "stay_fees.setup.more_details": "Thêm thông tin (không bắt buộc)",`

   Match each neighbour line's indentation. Commit `0239 step 4`.

5. Catalog. From the repo root run:

```
python3 - <<'PY'
import json
p = "docs/design/catalog.json"
c = json.load(open(p))
if "fee-more" not in c["classes"]:
    c["classes"].append("fee-more")
c["class_notes"]["fee-more"] = "Stay fee editor in Settings: folds the council's print-only details (address, contact, data box) (0239)."
json.dump(c, open(p, "w"), indent=2, ensure_ascii=False)
open(p, "a").write("\n")
PY
python3 scripts/design_lint.py | tail -3
```

Expected: `design lint: OK`. Then `git diff --stat docs/design/catalog.json` must show only a few lines; if hundreds of lines changed, run `git checkout docs/design/catalog.json`, add the two entries by hand with the Edit tool instead, and rerun the lint. Commit `0239 step 5`.

6. `App/tests/test_fee_form_partial.py`: in `test_a_form_without_the_office_fields_leaves_them_out`, anchor (exact line) `    for key in KEPT:` (the first occurrence) → insert directly before it: `    assert "stay_fee_cadence" not in values  # 0239: the wizard does not ask the period`. Commit `0239 step 6`.

7. `App/tests/test_fee_setup_compatibility.py`:
   - Anchor (exact line) `    assert "<details" not in section and "<summary" not in section` → replace with `    assert section.count('<details class="fee-more"') == 1  # 0239: print-only office details fold`
   - Anchor (exact line) `                # The council block is part of the editor, not a fold (plan section 4 rule 2).` → replace with `                # 0239: the council name stays visible; the print-only details fold.`
   - Anchor (exact lines):

```python
                              "stay_fee_authority_name", "stay_fee_authority_databox"):
```
   → replace with
```python
                              "stay_fee_authority_name"):
```
   - Anchor (exact line) `                assert page.locator("#stay-fee-settings details").count() == 0` → replace with these two lines:

```python
                assert page.locator("#stay-fee-settings details").count() == 1
                page.locator("#stay-fee-council details.fee-more > summary").click()
```

   - Append this test at the end of the file (after the last line):

```python


def test_the_wizard_asks_four_fee_boxes(host):
    """0239: rate, symbol, account and council name; no period, no print-only office details."""
    client, owner_id, entity_id = host
    apartment_id = _property(owner_id, entity_id)
    page = client.get(f"/apartments/{apartment_id}/setup/stay_fee?lang=en").text
    form = page.split('id="stay-fee-form"', 1)[1].split("</form>", 1)[0]
    for name in ("stay_fee_rate_czk", "stay_fee_vs", "stay_fee_council_account", "stay_fee_authority_name"):
        assert f'name="{name}"' in form, name
    for name in ("stay_fee_cadence", "stay_fee_authority_address", "stay_fee_authority_contact",
                 "stay_fee_authority_databox"):
        assert f'name="{name}"' not in form, name
    assert re.search(r'name="stay_fee_authority_name"[^>]*required', form)
```

   If `_property(owner_id, entity_id)` needs more arguments, copy the call style used in `test_fee_editor_is_the_only_one_and_shows_the_council_block`. Commit `0239 step 7`.

8. Run from `App/` (timeout 600000 ms):

```
.venv/bin/python -m pytest tests/test_fee_form_partial.py tests/test_fee_setup_compatibility.py tests/test_onboarding_wizard_survival.py tests/test_host_ux_acceptance.py tests/test_host_i18n.py tests/test_copy_property_settings.py tests/test_stay_fee.py tests/test_stay_fee_finalize.py tests/test_stay_fee_signature.py -q --tb=short 2>&1 | tail -15
```

then (timeout 600000 ms):

```
UBYHOST_REQUIRE_BROWSER=1 PLAYWRIGHT_BROWSERS_PATH=/tmp/claude-0/pw .venv/bin/python -m pytest tests/test_fee_setup_compatibility.py tests/test_onboarding_wizard_browser.py tests/test_design_setup_wizard_browser.py -q --tb=short -rs 2>&1 | tail -15
```

Expected: all passed, 0 skipped. Then from the repo root restore test evidence: `git status --short | head -20`; for every modified path under `docs/tasks/` other than your report and this brief, run `git checkout -- <path>`; delete untracked PNGs that the tests wrote under `docs/tasks/` with `git clean -fq docs/tasks/0102-evidence/` (and any other evidence folder listed as untracked).

9. Screenshots (rule 7). From `App/`, for LANG in `en`, `cs` (one command each):

```
PLAYWRIGHT_BROWSERS_PATH=/tmp/claude-0/pw .venv/bin/python /mnt/project-files/design-reset/tools/shots.py --new-app /home/user/jsfpecharoperations/App --out /mnt/project-files/stay-fee-four-boxes/LANG/ --pages "/apartments/1/setup/stay_fee,/apartments/1?view=settings&section=reporting" --widths 390,1280,2000 --lang LANG 2>&1 | tail -8
```

Then look once (Read tool) at the EN 390 px wizard shot and write one line about it.

## 5. Do not touch

Everything outside section 3. No CSS change.

## 6. Commands

As in section 4.

## 7. Acceptance

- [ ] Wizard shows exactly the four boxes (step 7 test).
- [ ] A wizard save keeps a stored quarterly period (step 1).
- [ ] Step 8 tests pass, 0 skipped; step 9 shots saved.

## 8. Stop and ask

A test fails twice, or an anchor is missing: stop and report the last 30 lines.

## 9. Report

Write `docs/tasks/0239-report.md` (500 tokens at most): commits, step 8 last lines, step 9 file list and your one line. Set `Status: review`, commit both as `0239 report` (git add those two files only). Do not push.
