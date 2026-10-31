# PR #583 fix report: visible acknowledgement and direct save actions

Status: review.

## What changed

- `App/app/routes/guest.py` — the save button now names its action: an edit is
  **Save changes**, an undeclared headcount keeps **Save details**, the last
  outstanding person sees **Submit registration**, anyone earlier sees **Save and
  continue to the next person**. After the save the reservation is re-read (the
  save can persist a headcount typed on the first form), so a newly completed
  guest advances to the next empty form only when the fresh read reports a known
  positive missing count. Edits and the final guest return to the summary.
- `App/app/templates/guest/form.html` — removed the outer `g-legal-fold`
  disclosure; the legal partial's own `.g-legal-text` disclosure is the single
  fold and the required acknowledgement stays visible outside it. Purpose help
  now sits at the details, residence, signature and conditional passport-step
  positions, reusing the existing `.g-why` pattern; the legal notice wording is
  unchanged.
- `App/app/templates/guest/claim.html` — the email disclosure takes its
  accessible name from `email_help_label` ("Why we need your email") and shows
  exactly one question mark; the guest-count field explains why the count is
  asked.
- `App/app/i18n.py`, `App/app/guest_uk_i18n.py` — save-action labels,
  shortened "Previous guest saved." status and the approved contextual-purpose
  copy in all six languages. No new legal claim; the purpose statements reuse
  existing approved source text.
- `App/app/static/guest.css` — one visible question mark on the claim disclosure
  (the generated marker duplicated the literal one).
- `App/tools/smoke.py` — a save now accepts either the completed summary or the
  "previous guest saved" status on the next form.
- `App/tests/test_guest_browser_e2e.py`, `App/tests/test_guest_navigation.py` —
  real-browser and HTTP coverage for the acknowledgement outside the collapsed
  notice, direct three-person progression, edit return-to-summary, unknown
  headcount, blank next-guest state, the save-action labels, purpose help at its
  matching step, and the email help's accessible label.
- `App/tests/test_demo_stay_exclusion.py`,
  `App/tests/test_design_guardrails_browser.py`,
  `App/tests/test_dashboard_calendar_browser.py` — date-boundary and browser
  ordering fixes so the existing checks measure what they document.
- `docs/tasks/screenshots-0451/` — 390 px evidence for the claim page, the
  acknowledgement screen, the next-guest form and the completion screen.

## Validation

- Focused suite: `.venv/bin/python -m pytest tests/test_guest_navigation.py
  tests/test_ticket_wallet_v3.py tests/test_ticket_wallet_v2.py
  tests/test_form_chrome.py tests/test_static_versions.py
  tests/test_guest_languages.py tests/test_guest_notice_ack.py
  tests/test_guest_a11y.py tests/test_guest_css_tokens.py
  tests/test_claim_copy.py -q` — 149 passed.
- Guest map plus geometry with the browser running:
  `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_guest_*.py
  tests/test_host_geometry.py -q -rs` — 576 passed, 0 skipped.
- Page smoke (mock UbyPort, staging profile): 44 pages checked, no dead pages,
  no server errors.
- `scripts/design_lint.py` OK; `scripts/context_lint.py` OK; `git diff --check`
  clean.

## 390 px screenshots

- `docs/tasks/screenshots-0451/claim-390.png` — guest-count purpose and the
  email disclosure's single question mark.
- `docs/tasks/screenshots-0451/acknowledgement-390.png` — legal text collapsed,
  acknowledgement and save action visible.
- `docs/tasks/screenshots-0451/next-guest-390.png` — "Previous guest saved.",
  blank next-person form.
- `docs/tasks/screenshots-0451/completion-summary-390.png` — completed
  registration.

## Remaining

- CI runs the full suite, smoke and four browser shards on the pushed head; no
  merge or deployment is performed here.
- Contextual help uses the approved purpose statements from the handoff bundle
  (0453); no legal wording, required field or upload condition changed.
