# 1090: Under-15 guests do not sign: the guest form note and the adult's role tick

Status: todo
Tier: A | Depends on: [1089](1089-under-15-signature.md) (server half, merged first) | Base: claude/1089-under-15-signature plus origin/main (step 0) | Branch: claude/1090-under-15-signature-ui
Executor: Fable 5.2 (owner tier override in decisions.md) | Attempts: 3 at most | Fits one session: stop at 60 tool calls or 60k tokens (section 8); reads stay at 150 lines or fewer
Review: a fresh Fable reviews the diff against this brief before the PR opens.
Report: docs/tasks/1090-report.md

## 1. Objective

The visible half of K-L04 (owner decision 2026-11-10; the rule, the columns and the save fields are in 1089 section 1 and step 5). On the guest form:

- **A guest under 15 on arrival:** the signature pad is replaced by one short note, "Children under 15 do not sign this form." When this phone already saved a signed adult (18+) on the booking, the note is followed by the adult's confirmation: the adult (a radio per adult when there are several) and the two role radios. Nothing is required: no tick still saves, and the house book says "Under 15, no signature required (§ 103(b))".
- **An adult (18+) whose phone already saved children under 15 on this booking that nobody signed for:** the signature step gains, under the pad, the confirmation sentence naming those children and the two role radios. The adult's own drawn signature is the one signature.
- **Everyone else (15 to 17, adults with no such child):** the form is exactly as today.

Both orders are covered because families fill the form in either order on one phone. Owner design call (reviewed 2026-11-10, recommended: keep): in the adult-first order, the adult confirms on the child's step and nothing is drawn again. Why it holds: the server links only an adult this same phone saved, 18 or over, with their own valid drawn signature, on the same booking (1089 step 5c); the record keeps its own time (`signed_for_at`) and wording version next to the adult's `signed_at`, so the house book shows the order honestly; the law asks for no child signature at all (§ 103(b)), so the tick is an extra assurance, not a filing condition. Sending the adult back to their own form to draw again would add a step families abandon and would store nothing more. Repeat this call under Questions in the report so the owner can still overrule it.

## 2. Context

- **What 1089 gives you (read only):** `validation.certainly_under_age`, `validation.certainly_at_least_age`, `reporting.UNDER_SIGN_AGE`, `reporting.ADULT_SIGNER_AGE`, `reporting.guest_under_15`, the four `guest.signed_for_*` columns, and in `guest_form_save` the posted fields: child form `signed_by` + `child_sign_role`; adult form `sign_for_ids` (repeated) + `sign_for_role`. Roles `parent`, `responsible_adult`. The server already drops a child's signature and links only this device's people, so the template and script only show and hide.
- **Signature step:** `App/app/templates/guest/form.html:293`-`:313`: the card `<div class="g-card" data-guest-step data-step-title="{{ t('signature') }}">`, the head, `<p class="g-intro" id="sig-help">`, `<div class="g-sign">` (canvas, status, clear), the hidden `#signature`, `{{ err_for('signature') }}`; then the review list, legal notice and save button (stay as they are). Arrival: hidden `stay_from` (`:69`).
- **Script (`App/app/static/signature.js`):** `function initSignature()` (`:18`); its submit guard `if (!hidden.value) {` (`:131`); the wizard's `stepIsValid` `if (canvas && signature && !signature.value) {` (`:708`); `initChildToggle` (`:236`-`:327`) is the model for parsing `birth_date` (`childBirth`), the typing guard and the listeners (input, change, blur, paste, pageshow); the init list `initChildToggle();` (`:1058`) ... `initGuestDraft();` (`:1069`). Cache key `signature.js?v=20261110-1087` in `guest/base.html:84` and `_signature_script.html:2`; `App/tests/static_versions.json` entries `"signature.js"` (`:162`) and `"guest.css"` (`:94`).
- **Radio look:** `.checkline input[type=checkbox]` (`App/app/static/guest.css:651`) styles the tick boxes; radios get the same rule by adding `.checkline input[type=radio]` to that selector (the only CSS change). Cache key `guest.css?v=20261110-1074a` (`base.html:14`).
- **No JavaScript:** the form already says JavaScript is needed to finish (`form.html:76`), because the pad needs it. A child needs no pad, so a child's form must be sendable without JavaScript: when the server does not know the age yet (new form, no birth date) it renders the pad **and** the child block visible; the script hides one on load. When it knows (edit, 422, relang), it renders only the right one.
- **Copy (rule 9):** the note is the only explanation; the role labels are the owner's words. Six guest languages: `App/app/i18n.py` (en, cs, de, es, fr: put each key under that language's `"signature_help"`, lines 387, 1150, 1870, 2413, 2956) and `App/app/guest_uk_i18n.py` (uk, under `:351`). `t()` formats `{names}` (`i18n.py:3265`).
- **Privacy:** names shown are only people this phone saved (`_owned_ids`), never anyone else on the booking.

### Copy (exact)

| Key | en | cs | de | es | fr | uk |
|---|---|---|---|---|---|---|
| `u15_note` | Children under 15 do not sign this form. | Děti mladší 15 let tento formulář nepodepisují. | Kinder unter 15 Jahren unterschreiben dieses Formular nicht. | Los menores de 15 años no firman este formulario. | Les enfants de moins de 15 ans ne signent pas ce formulaire. | Діти до 15 років не підписують цю форму. |
| `sign_for_child` | I confirm that the details of {names}, under 15, are true and complete. | {names} (do 15 let): potvrzuji, že uvedené údaje jsou pravdivé a úplné. | Ich bestätige, dass die Angaben zu {names} (unter 15) wahr und vollständig sind. | Confirmo que los datos de {names} (menos de 15 años) son verdaderos y completos. | Je confirme que les informations concernant {names} (moins de 15 ans) sont exactes et complètes. | Підтверджую, що дані {names} (до 15 років) правдиві та повні. |
| `sign_for_who` | Signing adult | Podepisující dospělý | Unterschreibende erwachsene Person | Adulto que firma | Adulte signataire | Дорослий, що підписує |
| `sign_role_parent` | Parent or legal guardian | Rodič nebo zákonný zástupce | Elternteil oder gesetzlicher Vertreter | Padre, madre o tutor legal | Parent ou tuteur légal | Батько, мати або законний опікун |
| `sign_role_responsible` | Adult responsible for the child during this stay | Dospělý, který za dítě během tohoto pobytu odpovídá | Erwachsene Person, die während dieses Aufenthalts für das Kind verantwortlich ist | Adulto responsable del menor durante esta estancia | Adulte responsable de l'enfant pendant ce séjour | Дорослий, відповідальний за дитину під час цього перебування |

Use the apostrophe style of the neighbouring French strings. `{names}` may hold one child or several ("Anna Novak, Petr Novak"), so every sentence must read correctly for both; do not reword into a singular "the child".

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/routes/guest.py` | edit | Five context keys in `_form_context` (step 1) |
| `App/app/templates/guest/form.html` | edit | Signature step only (step 2) |
| `App/app/static/signature.js` | edit | `signatureWaived`, two guards, `initUnder15` (step 3) |
| `App/app/static/guest.css` | edit | One selector (step 3) |
| `App/app/templates/guest/base.html`, `App/app/templates/_signature_script.html` | edit | Cache keys `20261111-1090` |
| `App/tests/static_versions.json` | regenerate | Only by `--write` |
| `App/app/i18n.py`, `App/app/guest_uk_i18n.py` | edit | Five keys (step 4) |
| `App/tests/test_under15_signature_1090.py` | create | Render and no-JS tests (step 5) |
| `App/tests/test_under15_signature_1090_browser.py` | create | Browser tests (step 6) |
| `docs/tasks/screenshots-1090/` | create | Nine screenshots (step 6g) |
| `docs/tasks/1090-report.md` | create | Report, plus `Status: review` here |

## 4. Steps (commit after each: `1090 step k`)

0. **Base.** `git fetch origin main && git merge origin/main`. `git grep -n "SIGN_FOR_WORDING_VERSION\|def guest_signature_settled" origin/main -- App/app/reporting.py 2>&1 | tail -30` and `git grep -n "child_sign_role" origin/main -- App/app/routes/guest.py 2>&1 | tail -30` (they read `origin/main`, not this branch, which already carries the 1089 brief's branch): either one empty, or a merge conflict: STOP, `blocked` ("1089 not on main").
1. **Context (`_form_context`, `guest.py:1751`).** Before its `return`, compute from `values` (else the `guest` row): `birth` = `values.get("birth_date")` or `guest["birth_date"]`; `arrival` = `validation.parse_iso_date(values.get("stay_from") or (guest["stay_from"] if guest else "") or reservation["date_from"])`. Add:
   - `"under15"`: `None` when `birth` is empty, else `validation.certainly_under_age(birth, arrival, reporting.UNDER_SIGN_AGE)`.
   - `"adult_signer"`: `None` when `birth` is empty, else `certainly_at_least_age(birth, arrival, reporting.ADULT_SIGNER_AGE)`.
   - `"child_signers"`: `[{"id", "name"}]` for rows of this reservation whose id is in `_owned_ids(request)`, not this guest, `validation.is_valid_signature(signature_png)`, and `certainly_at_least_age(...)` on their own arrival (`reporting._stay_dates(row, reservation)[0]`); `name` = `first_name surname`. One `db.query("SELECT * FROM guest WHERE reservation_id = ?", ...)`, filtered in Python.
   - `"pending_children"`: same query, owned, not this guest, `reporting.guest_under_15(row, reservation)`, `signed_for_guest_id` empty; and `"pending_children_names"`: their names joined with `", "`.
   - `"selected_signer"`: `values.get("signed_by", "")`; `"selected_child_role"`: `values.get("child_sign_role", "")`; `"selected_sign_for_role"`: `values.get("sign_for_role", "")`.
   These three are filled in one place only: the 422 re-render in `guest_form_save` (the `context["values"].update({...})` block that echoes `legal_ack`, about `guest.py:2301`) gains `"signed_by"` (the posted value only when it is all digits, else `""`), and `"child_sign_role"` / `"sign_for_role"` (the posted value only when it is a key of `reporting.SIGN_FOR_ROLES`, else `""`). That is the only edit inside `guest_form_save`. **`guest_form_relang` echoes none of them:** like the drawn signature and the acknowledgement tick (`guest.py:2076`), a role tick attests to a sentence the guest can no longer see after a language switch.
   The host preview has no owned ids, so both lists are empty there. Run command A.
2. **`form.html`, signature step only.** Wrap `<p class="g-intro" id="sig-help">` through `{{ err_for('signature') }}` in `<div id="sig-block"{% if under15 %} hidden{% endif %}>` ... `</div>`; inside it, after `err_for('signature')`, add `{% if pending_children %}` a block `<div class="g-field" id="sign-for-children" role="radiogroup" aria-labelledby="sign-for-children-text"{% if adult_signer == false %} hidden{% endif %}>` with `<p class="g-intro" id="sign-for-children-text">{{ t('sign_for_child', names=pending_children_names) }}</p>`, one `<input type="hidden" name="sign_for_ids" value="{{ c.id }}">` per child, and two `<label class="checkline">` each holding `<input type="radio" name="sign_for_role" value="parent|responsible_adult">` and `<span>` with the role label. Directly after `#sig-block` add `<div id="u15-block"{% if under15 == false %} hidden{% endif %}>` with `<p class="g-intro" id="u15-note">{{ t('u15_note') }}</p>` and, `{% if child_signers %}`, `<div class="g-field" id="sign-for-child" role="radiogroup" aria-labelledby="sign-for-child-text">`: `<p class="g-intro" id="sign-for-child-text" data-template="{{ t('sign_for_child') }}">{{ t('sign_for_child', names=(val('first_name') ~ ' ' ~ val('surname')).strip()) }}</p>` (the child's own name from step one; the script refills it as they type, replacing `{names}` in `data-template`; check first that `t('sign_for_child')` without `names` returns the raw template and does not raise, else pass `names='{names}'`); then, only when `child_signers|length > 1`, a `<p class="g-intro">{{ t('sign_for_who') }}</p>` and one `checkline` radio `name="signed_by"` per signer (label: the name); when exactly one, `<input type="hidden" name="signed_by" value="{{ child_signers[0].id }}">`; then the two role radios `name="child_sign_role"`. Keep posted choices checked on a 422 re-render (`selected_signer`, `selected_child_role`, `selected_sign_for_role`); after a language switch they are unticked (step 1). No other markup, no new class, no inline style.
3. **Script and the one CSS selector.** In `signature.js`, directly above `function initSignature()`, at its indent: `function signatureWaived() { var block = document.getElementById("sig-block"); return !!(block && block.hidden); }` with a comment (brief 1090: a guest under 15 has no pad to fill). Change `if (!hidden.value) {` (`:131`) to `if (!hidden.value && !signatureWaived()) {` and `if (canvas && signature && !signature.value) {` (`:708`) to `if (canvas && signature && !signature.value && !signatureWaived()) {`. Above `initChildToggle`'s comment add `function initUnder15()`: return early without `#sig-block`; reuse a copy of the `childBirth` parse (it is local to `initChildToggle`; do not move it); `arrival` = the hidden `stay_from` only (not today: the rule is the arrival day); `under15` = earliest birthday (00 read as 1) gives age < 15; `adult` = latest birthday (00 month as 12, 00 day as the month's last day) gives age >= 18; an unparsed date is neither. `apply()`: skip while typing (the same `typing()` guard); `sigBlock.hidden = under15`; `u15Block.hidden = !under15`; `#sign-for-children` (if present) `.hidden = !adult`; fill `#sign-for-child-text` from its `data-template` with the typed first name and surname. Listeners as `initChildToggle` (birth input, change, blur, paste with `setTimeout 0`, `pageshow`) plus `input` on `#first_name` and `#surname`; call `apply()` once on load. It never sets a value, a `checked` or `required`. Add `    initUnder15();` directly under `    initChildToggle();` (`:1058`). In `guest.css:651` the selector becomes `.checkline input[type=checkbox],\n.checkline input[type=radio] {`. Bump both cache keys to `20261111-1090`, then from `App/`: `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -30` (diff: only the two entries). A later edit bumps to `20261111-1090b` and reruns it.
4. **Copy.** The five keys of section 2's table under each language's `"signature_help"`. Run command A.
5. **`App/tests/test_under15_signature_1090.py`** (no browser; seed as `test_guest_child_document.py` lines 39 to 130 and the 1089 test):
   a. Source pins: `initUnder15` has no `.value =`, `.checked =`, `.required`, `innerHTML`; both guards call `signatureWaived()`; `form.html` has one `id="sig-block"`, one `id="u15-block"`, and `sig-canvas` stays inside `#sig-block`.
   b. Render: a new form (no birth date): `#sig-block` and `#u15-block` both without `hidden`; a 422 re-render for a 10-year-old: `#sig-block` hidden, `#u15-block` shown; for a 16-year-old and an adult: the reverse. In each of the six languages (`?lang=`) the note text renders.
   c. Lists: after this client saved a signed adult, a child's form has `#sign-for-child` with a hidden `signed_by` equal to the adult's id; a second client's form has none and never shows the adult's name. After this client saved an unsigned child, an adult's form has `#sign-for-children` naming the child and a `sign_for_ids` input; once linked, it is gone. The host preview has neither block.
   c2. Re-render: a 422 on the child's form (say, no `legal_ack`) keeps `child_sign_role` and `signed_by` checked; a `signed_by` of `"1 OR 1"` or a role of `"boss"` is echoed nowhere in the HTML; the relang render of the same post has no role checked.
   d. **No JavaScript (plain POST, the way a browser without script posts):** the child's form with no `signature`, `signed_by` and `child_sign_role=parent` saves (303) and stores the link; with no role it saves with no link.
   Run command A.
6. **`App/tests/test_under15_signature_1090_browser.py`**, modelled on `test_guest_child_visa_1079_browser.py` (imports at its lines 17-18, `_years_before` at 27, the typing test at 127). Arrival fixed by the seeded booking:
   a. **Child after adult, 390 px:** send an adult (signs), then open `/new`, type a 10-year-old's birth date: on the signature step the pad is gone, the note and the role radios are shown, the sentence carries the typed name; choose "Parent or legal guardian", send: the row has `signed_for_role == "parent"` and `signature_png == ""`.
   b. **Adult after child:** send a child first (no pad shown, no tick possible yet, sends without a tick), then an adult: `#sign-for-children` names the child; draw, tick "Adult responsible for the child during this stay", send: the child row is linked.
   c. **15 to 17 and adults:** a 16-year-old sees the pad and no note, and cannot leave the step unsigned (the existing message); an adult with no pending child sees today's step.
   d. **Typing and moving:** typing a birth date part-way changes nothing; changing 10-year-old to 30-year-old brings the pad back; `00.00.2012` shows the note, `00.00.2011` the pad (arrival 2026-10-20 style; pick dates against the seeded arrival).
   e. **Language switch:** a child's form switched to `cs` keeps the note (Czech) and the typed name in the sentence; the role is unticked again (it attested to the English sentence) and the form still sends with or without a new tick.
   f. **No JavaScript** (`java_script_enabled=False`): a child's form can be sent with no pad use; the row is saved.
   g. **Design unchanged, at 390, 768 and 1280** (`parametrize`): for an adult with no pending child, `#sig-block` has zero margin, padding and border (computed style), and unwrapping it with `page.evaluate` (move its children out, remove it) leaves the card height and the `#sig-canvas` box unchanged within 1 px; every `.g-field` on the step keeps `left` and `width`; no horizontal scroll; `Guest.check_layout` where it fits. Screenshots (full page) into `docs/tasks/screenshots-1090/`: `adult-{w}.png`, `child-note-{w}.png` (child with the role radios), `adult-signs-for-{w}.png`, nine in all.
   Look at each screenshot once; one line each in the report. Run command B.
7. Run section 6 and the UX gate (AGENTS rule 10: layout lint green, the screenshots opened, one line per page), then write the report.

## 5. Do not touch

Everything 1089 built (`validation.py`, `reporting.py`, `guest_form_save` except the three echoed values of step 1, `guest_form_relang`, `guest_remove`, `housebook.py`, migrations, retention), `App/app/ubyport/`, `go/`, `submit_*`, `guest_form_admin.html`, `_legal_notice.html`, archive templates, the 1079 child-in-passport markup and `initChildToggle` (copy, never move or edit), other `signature.js` functions, other CSS rules, any dependency. Never push to `main`.

## 6. Commands (each ends `2>&1 | tail -30`)

From `App/`:
- A: `.venv/bin/python -m pytest tests/test_under15_signature_1090.py tests/test_under15_signature_1089.py tests/test_static_versions.py tests/test_guest_languages.py tests/test_no_em_dashes.py tests/test_guest_child_visa_1079.py tests/test_design_guest_admin.py -q --tb=short -x`.
- B (0 skipped): `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_under15_signature_1090_browser.py tests/test_guest_child_visa_1079_browser.py tests/test_guest_form_input_browser.py tests/test_guest_browser_e2e.py tests/test_host_geometry.py tests/test_layout_lint_browser.py -q --tb=short -rs`.
- Test-map guest row: `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_guest_*.py -q --tb=short -x -rs` (0 skipped).

Repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

## 7. Acceptance

- [ ] 1089 on main and merged in (step 0).
- [ ] Under 15: note instead of the pad; with a signed adult from this phone, the adult and role radios; nothing required.
- [ ] Adult with pending children from this phone: the sentence naming them and the two role radios under the pad; links on send.
- [ ] 15 to 17 and other adults: the step exactly as today (6c, 6g).
- [ ] Without JavaScript a child's form sends and can carry the role.
- [ ] A role tick survives a 422 but not a language switch; only whitelisted values are echoed.
- [ ] Copy: five keys in en, cs, de, es, fr, uk; one CSS selector added; cache keys bumped, `static_versions.json` regenerated.
- [ ] Browser tests 0 skipped; layout lint green; nine screenshots, one line each.
- [ ] `git diff --stat origin/main` touches only section 3 files.

## 8. Stop and ask

STOP and report `blocked` if: step 0 finds 1089 missing; an anchor is missing; the change would need a server, storage, filing or other CSS edit; a browser test skips; the layout lint flags the new blocks and only a new CSS rule would fix it; a test fails twice on the same cause (attempt 3 of 3); 60 tool calls or 60k tokens (finish the step, commit, `Done: steps 0 to k. Left: steps k+1 to 7.`).

## 9. Report

`docs/tasks/1090-report.md`, 600 tokens at most: files changed, each command with its last 5 lines, section 7 ticked, one line per screenshot, layout-lint findings, the design-system checklist ticked, deviations, questions (include the adult-first design call from section 1). Set this brief `Status: review`. After the fresh Fable diff review, open one PR (body: K-L04 guest form half on top of 1089; no new field, cookie or request; filing untouched; per page what the 390/768/1280 screenshots show). Merge only with `scripts/merge-pr-on-green.sh`, after 1089.
