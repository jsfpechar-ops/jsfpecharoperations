# 0093: Visible host controls and contextual question-mark help

Status: todo
Depends on: 0092 reviewed | Initial source: 7b27d09402f9656b0c606c131793310925936526 | Branch: task/0093-visible-controls-contextual-help | PR base: task/production-host-ux-integration
Executor: Cursor local agent (composer, Kimi or GLM) | One host-presentation session; separate independently found bugs before release

## 1. Objective

Make essential values and controls directly visible in their relevant host section. Move routine explanatory prose to one shared accessible ? help pattern, removing configuration-hiding arrows and Suggested portal message.

## 2. Context

Owner's latest clarification explicitly overrides earlier accordion/disclosure proposals. Generic editable **guest-form message stays**; **Suggested portal message goes**. Do not confuse the two. Guest PIN is an essential value, not advanced information.

Initial source anchors in apartment_form.html: `<details class="more-options"`; `id="permalink_pin"`; `<details class="message-details" open>`; `t('guest_links.message_title')`; `t('apartment.form.guest_link.window_hint')`. _components.html has no verified reusable accessible host help component. app.js has disclosure/hash logic, not the requested host-wide help pattern. Inspect reviewed predecessors before using these anchors; retain their deliberate corrections.

Read AGENTS.md, the correction plan, 0091 audit matrix and 0092 report. Apply only to host surfaces. Legal/retention wording moves unchanged to Guidance; no statutory or guest privacy-notice rewrite. Important errors, status, required markers, values and action confirmations stay visible.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/_components.html` | edit | One reusable contextual-help macro |
| `App/app/static/host.css` | edit | Help positioning/trigger style and visible section headers |
| `App/app/static/app.js` | edit | Shared pointer/focus/tap/Escape behavior |
| `App/app/host_i18n.py` | edit | Short help labels, retain existing explanatory translations |
| `App/app/templates/apartment_form.html` | edit | Visible configuration, remove suggested-message block |
| `App/app/templates/_property_create.html` | edit | Visible address card; no help prose/chevron |
| `App/app/templates/_property_identity_fields.html` | edit | Shared field help |
| `App/app/templates/_property_address_fields.html` | edit | Shared field help |
| `App/app/templates/_property_operator.html` | edit | Shared field help, reliable default |
| `App/app/templates/_stay_fee_fields.html` | edit | Helper prose only |
| `App/app/templates/_account_parts.html` | edit | Helper prose only |
| `App/app/templates/dashboard.html` | edit | Routine host explanations only |
| `App/app/templates/apartments.html` | edit | Routine host explanations only |
| `App/app/templates/reservations.html` | edit | Routine explanations only; retain 0091 fit |
| `App/app/templates/reservation_detail.html` | edit | Routine explanations only; values/status visible |
| `App/app/templates/submissions.html` | edit | Routine explanations only; results/errors visible |
| `App/app/templates/housebook.html` | edit | Small ? help to Guide; preserve register layout |
| `App/app/templates/guide.html` | edit | Relocated explanation, one canonical copy |
| `App/app/templates/entities.html` | edit | Helper prose only; current identity visible |
| `App/app/templates/invoices.html` | edit | Helper prose only |
| `App/app/templates/invoice_settings.html` | edit | Helper prose only |
| `App/app/templates/invoice_form.html` | edit | Helper prose only |
| `App/app/templates/invoice_detail.html` | edit | Helper prose only; issued values visible |
| `App/app/templates/invoice_stay_picker.html` | edit | Helper prose only |
| `App/app/templates/stay_fees.html` | edit | Helper prose only |
| `App/app/templates/stay_fee_setup.html` | edit | Helper prose only |
| `App/app/templates/stay_fee_detail.html` | edit | Helper prose only; amounts/export/errors visible |
| `App/app/templates/settings.html` | edit | Helper prose only; essential controls visible |
| `App/app/templates/settings_archived.html` | edit | Helper prose only; archive facts visible |
| `App/app/templates/smart_locks.html` | edit | Contextual help; assignment/terms/status visible |
| `App/app/templates/onboarding.html` | edit | Routine help only, retain optional entry |
| `App/tests/test_host_help_browser.py` | create | Meaningful accessible-help and essential-value checks |
| `App/tests/test_host_property_controls_browser.py` | edit | Guest URL/PIN visibility and saved drafts |
| `App/tests/test_host_wide_geometry_browser.py` | edit | Popup bounds, no fit regression |
| `docs/tasks/0093-visible-controls-contextual-help.md` | edit | Lifecycle only |
| `docs/tasks/0093-report.md` | create | Report, maximum 1500 tokens |
| `docs/tasks/0093-evidence/` | create | Synthetic captures and per-field audit matrix |

Read-only: existing helpers, templating, fixtures, protected routes/validators, correction plan and execution protocol. No routes or data semantics change. If another host template has a needed change, list the exact finding for a scope correction rather than editing it silently.

## 4. Steps

1. Make a field-help inventory from the actual 0091 audit: route, field/section, current explanation key, whether it is routine help vs current state/error/action confirmation, proposed ? location/Guide anchor. Edit each listed template only where an actual helper exists. Do not perform a blanket `.hint { display:none }` or delete all muted text. Dates, sync outcomes, guest counts, statutory amounts, source names and actual error reasons are data, not explanations.
2. Introduce `host_help(id, label, text, guide_url='')` in _components.html. No new dependency. Put a real `type=button` ? trigger beside the field label, outside its label tag; accessible name is “Help: {label}” / “Nápověda: {label}”. Use unique IDs, aria-controls and native `popovertarget`/popover="auto" for no-JS keyboard/tap operation in supported browsers. The popover contains escaped existing translated explanation and an optional ordinary Guide link for longer instructions. Use role="note" for content with links, not an interactive role=tooltip. Preserve programmatic field descriptions with aria-describedby where appropriate, without making the help text permanently visible. A title-only implementation is unacceptable.
3. Shared JS enhances the same component for hover and focus, and leaves native click/tap working. It must show on pointerenter/focus, allow pointer/focus into the help content, close with Escape/outside click, keep the trigger focused after dismissal, and never submit the enclosing form. Do not immediately reopen a dismissed popup because focus remained on its trigger. Position against the trigger's bounding box, choose below/above as space allows, clamp within viewport with an 8px margin, cap width to min(320px, viewport-16px), allow text wrapping. Recompute on opening, resize and relevant scrolling. Native click works with JS disabled; unsupported popover browsers get a working Guide/help fallback. Do not ship an inaccessible hover-only implementation.
4. CSS follows existing colors/type/borders and sufficiently large pointer/touch target; no animations required. Popover appears only on demand, never covers the control with an always-open notice, and cannot extend beyond the screen. Test focus indication, contrast and touch target. One macro/style/behavior for every host field, not separately implemented hints per page.
5. Guest links: keep an ordinary section heading/bar and visible content in the selected Guest links view. At the top show guest URL + Copy and access PIN + Copy in a compact two-column row on desktop, stacked on mobile. Place the supported Change/Generate PIN and Change/Generate link actions directly beside the corresponding current values at the top, preserving exact handler/confirmation semantics. Then show the editable generic guest message and normal settings grid: readable name, upcoming-window days, past-link-window days, photo policy. Remove the More options wrapper without deleting or disabling its fields. Keep current value/limits and server behavior. Shorten labels if useful but put each full explanation under its own ?; no paragraphs underneath every input.
6. Remove the entire Suggested portal message `.message-details` block: its heading, boilerplate/pre elements and Copy suggested-message buttons. Remove `guest_link.message_help` prose belonging to it. Retain Preview as a visible ordinary action after guest URL/PIN, plus the existing regenerate-link/PIN buttons and their confirmations. Do not remove the customizable guest-form textarea, PIN generation, old-link compatibility or real guest preview.
7. Move the entire archive/restore setup-item out of #communication into Property information at the bottom of the main property form, separate from the normal save action. Keep its formmethod/formaction, return_to and confirmation behavior. Never submit another form inside it.

In relevant property settings, replace outer essential `details.property-section`/summary with ordinary section header/content markup, preserving IDs and selected-section navigation. If still using the pre-tab editor, essential sections remain visible rather than collapsed; when the approved tabs arrive, the selected section is shown by navigation, not by hiding fields under More options. Full form draft and hidden-by-tab successful controls must survive exactly as required by the navigation plan. Existing hash opening code safely no-ops on ordinary sections and scrolls to target. Do not introduce duplicate forms or IDs. Apply the same principle to essential controls in other named host pages.
8. In #door-code replace the raw checkbox sentence with a styled switch using the existing checkbox name=door_codes/value=1 and hidden door_codes_fields guard. Label “Automatic door codes” / “Automatické přístupové kódy”, a visible saved status “Enabled” / “Zapnuto” or “Off” / “Vypnuto”. Style the actual focusable input with a track/thumb and role=switch; do not replace successful-control semantics with a decorative div. Draft changes show an unsaved indication until a successful save; failed saves do not change saved status. Preserve eligibility, test-mode warning, lock selector, hours and all lifecycle guards. Use this shared treatment only for existing genuine optional-feature enable booleans, never for property active or acceptance boxes.

Long house-book legal material remains only in existing Guidance, reached by a small ?. No legal-duty accordion or legal paragraph under the working title. Credential/lock instructions use ? + Guide instead of an eight-step wall or configuration-hiding arrow. Actual credential inputs, connection result and lock assignment remain visible. Preserve required Terms acceptance and actual action warnings at their existing flows.
9. Replace routine descriptions beside fields in every named host family with the shared macro, reusing translations unchanged except owner-requested simplification. Keep top-level page purpose only if needed to navigate; do not remove an actionable empty-state instruction or important warning. This work is a consistent helper/visibility pass, not redesign of legal exports or the owner's approved house-book table.
10. Test: guest URL/PIN visible without clicking/opening anything; tab focus can Copy and use each field; no Suggested portal message; each helper opens on hover/focus/tap, remains reachable, closes with Escape/outside click, does not submit/change data, and fits narrow/zoomed viewport; descriptions available to assistive technology; JS disabled can open help and submit form; no duplicate IDs, lost inputs or interrupted form drafts. Run the full named-family matrix EN/CS and widths from the protocol. Capture representative guest links, address/reporting, house book and account/invoice help with synthetic data.

## 5. Do not touch

Routes/business semantics, schema, providers, retention, legal acceptance, public/guest pages, dependencies, sensitive guest/operator data, filing guards or exports. Do not hide errors/values/confirmation, enable tracking, rely only on hover/title or apply global display:none. No main merge/deploy.

## 6. Commands

Use the existing protocol environment/pinned browser. Executor only, from App:

```bash
UBYHOST_REQUIRE_BROWSER=1 UBYHOST_UBYPORT_ENV=mock UBYHOST_DEPLOYMENT=staging UBYHOST_ENABLE_SCHEDULER=0 .venv/bin/python -m pytest tests/test_host_help_browser.py tests/test_host_property_controls_browser.py tests/test_host_wide_geometry_browser.py -q -rs
UBYHOST_REQUIRE_BROWSER=1 UBYHOST_UBYPORT_ENV=mock UBYHOST_DEPLOYMENT=staging UBYHOST_ENABLE_SCHEDULER=0 .venv/bin/python -m pytest tests -q -rs --cov=app --cov-report=term-missing --cov-fail-under=86
.venv/bin/ruff check app tests tools --select E9,F63,F7,F82,F401,F841
```

From root: `python3 scripts/context_lint.py`; `git diff --check`; `git diff --name-only`. Expected green and zero required-browser skips; report real counts and baseline failures. Do not claim all-host consistency from only the property screenshot.

## 7. Acceptance

- [ ] All essential Guest links values/settings are directly visible; no More options or Suggested portal message.
- [ ] Routine explanations use the single ? component across the named host families; Help works on hover, focus, keyboard and touch/no JS.
- [ ] Important values, statuses, errors, required markers, confirmations and acceptance remain visible and functional; no changed submitted data.
- [ ] Actual EN/CS screenshots at 360/390/1280 and measured matrix through 2048; expanded/collapsed sidebar and narrow available lanes; popovers stay in viewport; required browsers zero skips.
- [ ] One editor/control per field, no form-submit from help, preserved drafts, no privacy leaks; exact-head CI green and all paths within §3.

## 8. Stop and ask

Stop for unexplained predecessor drift, required unlisted template, changed legal/data semantics or unavailable browser. Report exact finding/proposed patch; no guessing, skips or weakened acceptance. Do not reask already-approved design requirements.

## 9. Report

Write 0093-report.md, max 1500 tokens, status review. Record base/result SHA, changed files, commands/last output, counts/skips/coverage, acceptance, capture paths, audit matrix, deviations and owner steps. List each unsupported/not-reviewed family honestly. No “production fixed” until the candidate is deployed and verified.

## Risk list

Shared macro/JS interaction and positioning; generic template changes which could hide current state, duplicate IDs, lose inputs or affect confirmations; PIN copying; no-JS/help accessibility; privacy-safe screenshots.

## Owner steps

1. Use a fresh Cursor session after reviewed 0092 on task/production-host-ux-integration.
2. Review actual results and CI, then review all seven corrections together on staging.
3. Approve the exact staged SHA before production promotion; main currently triggers deployment, so do not merge for a preview.
