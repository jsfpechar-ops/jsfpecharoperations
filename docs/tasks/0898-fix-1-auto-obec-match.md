# 0898-fix-1: same-obec exemption is exact-match only (remove near-miss and "Check residence")

Status: todo
Depends on: 0898 | Base commit: current branch `vibe/stay-fee-guest-payment-plan-73df64` (uncommitted 0898 work is on disk; the orchestrator commits, you do not commit or push) | Branch: same
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Owner decision (2026-11-04): the guest form is a legal declaration, so a typo in the city is the guest's own error. The same-obec exemption is fully automatic and **exact-match only** (after folding); there is no fuzzy matching and no "Check residence" task for the host. Remove the near-miss code, its flag, badge, help text and i18n keys that 0898 added, and show the host why a guest was exempted.

## 2. Context

Rule that stays (already in `App/app/stay_fee.py`, do not change): CZ residents only (`validation.CZECH_CODE`); `fold_text()` (diacritics, case, spacing); statutory-city district strip ("Praha 5", "Praha-Smíchov", "Brno-střed" → "Praha"/"Brno") via `_obec_key()`; alias `Prague → Praha`; host `fee_host_decision` wins both ways (`obec_auto` only when `decision is None`). "Prha", "Olomuc", "Brod" are simply a different city: liable, no flag, no note.

What to delete (anchors, all in `App/app/stay_fee.py` unless stated):
- comment block above `STATUTORY_DISTRICT_BASES` ("A near miss (Levenshtein <= 2) is flagged ...");
- `def _levenshtein(...)` and `def _obec_near_miss(...)`;
- in `guest_period`: the `obec_near = (...)` statement and `share["obec_near_miss"] = obec_near`;
- in `_apply_scope_boundary`: `share["obec_near_miss"] = False`;
- `_CHARGE_KEYS`: the `"obec_near_miss"` entry;
- `App/app/routes/stay_fees.py` `_guest_lines`: `check_residence = bool(line.get("obec_near_miss"))` and `"check_residence": check_residence,`;
- `App/app/templates/stay_fee_detail.html`: the `{% if line.check_residence %}...{% endif %}` block, and the top line `{%- from "_components.html" import help_tip with context -%}` (only if `grep -n help_tip` shows no other use in the file);
- `App/app/host_i18n.py`: keys `stay_fees.hint.check_residence` and `stay_fees.hint.check_residence_help` in both `en` and `cs`.

What to add: the register's existing hint `stay_fees.hint.local_resident` says "Check their registration on their ID before exempting", which is wrong now that the exemption is automatic. When the line is auto-exempt, show a host-facing reason instead. `_guest_lines` already builds `local_hint` (exact city match). Keep it, but it must not show when the guest was auto-exempted: auto-exempt gets the new reason line; `local_hint` stays only for a guest the host set to `charge` (the hint then tells the host the city matched). Nothing here reaches guests (plan §9 item 1).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/stay_fee.py` | edit | delete near-miss code and flag (list in §2) |
| `App/app/routes/stay_fees.py` | edit | drop `check_residence`; add `obec_resident` line flag; `local_hint` off when auto-exempt |
| `App/app/templates/stay_fee_detail.html` | edit | drop badge block and `help_tip` import; add reason line |
| `App/app/host_i18n.py` | edit | delete 2 keys x en/cs; add `stay_fees.hint.obec_resident` en + cs |
| `App/app/host_vi_i18n.py` | edit | add `stay_fees.hint.obec_resident` (vi), next to `stay_fees.hint.local_resident` |
| `App/tests/test_stay_fee_obec_0898.py` | edit | tests per §4 step 6 |
| `docs/tasks/screenshots-0898/*.png` | overwrite | 4 new screenshots |
| `docs/tasks/0898-fix-1-report.md` | create | report |

No other file may change.

## 4. Steps

1. `stay_fee.py`: `grep -nF "near_miss\|_levenshtein\|Levenshtein" App/app/stay_fee.py`, then make the deletions listed in §2. Rewrite the comment block to exactly:
   ```
   # --- same-obec residence (0898) ---------------------------------------------
   # Backend only. Exact match after folding; statutory-city district suffix dropped
   # ("Praha 5", "Praha-Smichov"); Prague folds to Praha. Anything else, a typo
   # included, is not exempt: the form is the guest's own declaration.
   ```
   Command: `cd App && .venv/bin/python -c "import app.stay_fee" 2>&1 | tail -30` (expect no output), then `grep -c "near_miss\|levenshtein" app/stay_fee.py` (expect 0).
2. `routes/stay_fees.py`, in `_guest_lines`: delete the `check_residence` line and its dict key. Change the `local_hint = bool(...)` expression to also require `not line.get("auto_obec_resident")`. Add to the dict `"obec_resident": bool(line.get("auto_obec_resident")),`. Make `"review"` stay `bool(line.get("auto_minor") or local_hint)` (unchanged). Check that the per-guest `line` dict from `property_period` carries `auto_obec_resident` (`grep -n auto_obec_resident App/app/stay_fee.py`); if the register lines drop it, STOP and ask (§8).
3. `stay_fee_detail.html`: replace the removed block with, right after the `local_hint` block:
   ```
   {% if line.obec_resident %}
     <div class="ui-sub fee-hint">{{ t('stay_fees.hint.obec_resident') }}</div>
   {% endif %}
   ```
   No badge, no `help_tip`, no `style=`. The row keeps the existing grey "Exempt" pill (`status_key`).
4. `host_i18n.py`: delete the 4 check-residence lines; add next to the other `stay_fees.hint.*` keys:
   - en `"stay_fees.hint.obec_resident": "Resident of the property's municipality: exempt automatically, from the city the guest declared. Change it with the decision below."`
   - cs `"stay_fees.hint.obec_resident": "Obyvatel obce nemovitosti: osvobozen automaticky podle města, které host uvedl. Změníte to rozhodnutím níže."`
   `host_vi_i18n.py`: `"stay_fees.hint.obec_resident": "Cư dân của địa phương này: được miễn tự động theo thành phố khách đã khai. Đổi bằng quyết định bên dưới.",`
   Copy rules: no em dashes (`test_no_em_dashes.py`). Command: `cd App && .venv/bin/python -m pytest tests/test_*_i18n.py tests/test_no_em_dashes.py tests/test_copy_cleanup.py -q --tb=short -x 2>&1 | tail -30`.
5. Tests, `App/tests/test_stay_fee_obec_0898.py` (`grep -n obec_near_miss` first):
   - `test_obec_rule_is_inert_without_a_cz_resident_match`, `test_cz_resident_of_the_same_obec_...`, `test_scope_boundary_clears_the_obec_flags`, `test_different_obec_is_liable_...`: delete every `obec_near_miss` assertion.
   - Replace `test_near_miss_is_flagged_and_still_liable` with:
     ```python
     def test_typo_is_liable_and_has_no_flag():
         for city in ("Prha", "Olomuc", "Praga", "Brod"):
             share = stay_fee.guest_period(_guest(res_city=city), RES, FIRST, LAST, apartment=PROPERTY)
             assert share["liable_nights"] == 4, city
             assert share["auto_obec_resident"] is False and "obec_near_miss" not in share, city
     ```
   - Keep `test_same_obec_matching_rules` (it already lists "Praha 5", "Praha-Smíchov", "Prague" as matches and "Prha" as refusal) and `test_host_charge_decision_beats_a_same_obec_match`; add to the matches there nothing else.
   - `test_charge_for_reservation_applies_the_rules`: change `flags` to `(liable_nights, auto_obec_resident)` pairs: `[(4, False), (0, False), (0, True), (4, False), (4, False), (0, False)]`; comment on the "Prha" guest becomes `# typo: liable`.
   - Add a route test (reuse the file's `host` fixture and `_property`/`_finalize_stay` helpers like `test_sealed_period_...`): a guest with `res_country=CZ`, `res_city="Praha 5"`, property `addr_obec="Praha"`; `client.get(f"/stay-fees/{apartment_id}?month=2026-08")` text contains the `en` string of `stay_fees.hint.obec_resident`, does not contain "Check residence"; with `res_city="Prha"` it contains neither.
   - `test_sealed_period_keeps_its_filed_numbers_...` stays unchanged and must pass.
   Command: `cd App && .venv/bin/python -m pytest tests/test_stay_fee*.py -q --tb=short -x 2>&1 | tail -30`.
6. UX gate (AGENTS.md rule 10). Read the design-system checklist `docs/design/design-system.md` (grep, ranges of 150 lines or fewer). Run from `App/`: `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_layout_lint_browser.py tests/test_host_geometry.py -q -rs --tb=short 2>&1 | tail -30` (0 skipped), then `cd .. && python3 scripts/design_lint.py 2>&1 | tail -5`. Seed a property with `addr_obec="Praha"` and guests: Adult (liable), "Praha 5" CZ (auto-exempt), "Prha" CZ (liable). Overwrite `docs/tasks/screenshots-0898/stay-fee-detail-en-{390,768,1280}.png` and `stay-fee-detail-cs-390.png` and open each. Write per page in the report what you saw (reason line under the "Praha 5" guest, grey "Exempt" pill, nothing under "Prha", no sideways scroll, no truncation). Then `git status --short | tail -30`; any other PNG that tests modified: `git checkout -- <that file>`.
7. Write `docs/tasks/0898-fix-1-report.md` (600 tokens at most, TEMPLATE §9), set its `Status: review`; do not commit.

## 5. Do not touch

Everything not in §3, including the guest templates and routes (nothing here reaches guests), `stay_fee_filing.py` (sealed periods unchanged), migrations, `docs/context/*`, `docs/plans/*`. No new dependency, no data file. AGENTS.md rules 3, 6, 7, 9, 10 apply.

## 6. Commands

As given per step. Final check from the repo root: `python3 scripts/context_lint.py 2>&1 | tail -5`.

## 7. Acceptance

- [ ] `grep -rn "near_miss\|check_residence\|_levenshtein" App/app App/tests | grep -v pyc` prints only the one `"obec_near_miss" not in share` assertion in the new typo test (and the old pin in `test_guest_period_without_apartment_keeps_the_old_output`).
- [ ] "Prha", "Olomuc", "Praga", "Brod" vs property "Praha": liable, no flag. "Praha 5", "Praha-Smíchov", "Prague": exempt.
- [ ] Host `charge` beats a match; host `exempt` still exempt; sealed period test unchanged and green.
- [ ] `test_stay_fee*.py`, i18n/copy tests, layout lint + geometry (0 skipped), design_lint, context_lint all green.
- [ ] 4 screenshots (EN 390/768/1280, CS 390) opened; per-page notes in the report; the design-system checklist ticked in the report.
- [ ] No guest-facing file changed (`git diff --stat` shows none under `templates/guest/`).

## 8. Stop and ask

Per TEMPLATE.md §8, plus: the register line dicts do not carry `auto_obec_resident`; an anchor in §2 is not found verbatim; a layout-lint finding appears (never silence it).

## 9. Report

`docs/tasks/0898-fix-1-report.md`, per TEMPLATE §9.

## Risk list (reviewer)

`App/app/stay_fee.py` diff in `guest_period`; `routes/stay_fees.py` `_guest_lines`; `stay_fee_detail.html` guest line.

## Owner steps

1. Nothing to run. The orchestrator will add this line to `docs/context/decisions.md`: "2026-11-04 [stay-fee] Same-obec exemption is automatic and exact-match only (fold + statutory-city district strip + Prague alias, CZ residents, host decision wins). No fuzzy matching, no 'Check residence' task, no municipality data file: the guest form is a legal declaration and a typo is the guest's own error; RÚIAN autocomplete (0933) makes typos rare."
2. Host comms note (from 0898): live fee periods drop same-obec residents after deploy; sealed filings are unchanged. A guest who typed their own town wrongly is charged.
