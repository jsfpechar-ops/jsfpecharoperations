# 0972 report (B14): blocked after steps 2 to 4

Status: blocked. Reason: two group D tests that pass at base `7b0355c4` fail at HEAD, both in the help/back-header area the brief flags as risky (`settings_back_header.html`, `help_is_page` branch). Fixing them needs CSS or a new markup decision outside §3, so this is a stop under §8. Not verified: the exact cause (not bisected), and the 320 px lint scope (brief checks 390/768/1280 only).

Commits (branch `codex/0972-b14-help-settings`, not pushed):
- `f78eb79d` 0972 step 2: patch applied, 7 files as §3.
- `4ef41823` 0972 step 3: test block appended, plus `config` added to the top-level `from app import` line.
- `5bde965e` 0972 step 4: fixes (below).

Import fix (known finding): `sync_api` is already defined at module level (`sync_api = pytest.importorskip(...)`, line 24), and `base` and `login_as` already exist. Only `config` was missing from the top-level imports; added to line 19.

Deviations (all within §3 files):
1. `settings.html` account email row: `field_label(...)` (macro in `_components.html`, used by 32 call sites) replaced by identical inline markup with the contextual help label. Changing the macro would break `test_host_help_browser.py` (asserts the generic "Help" on a field label).
2. Test `test_0972_passkeys_and_help_labels_are_not_repeated`: `">User guide<"` replaced by a visible-text check, because `tip_label` splits the last word into a `tip-nowrap` span.
3. Test `test_0972_help_opens_by_pointer_and_keyboard...`: added `page.mouse.move(0, 0)` before the keyboard step. A stationary pointer let a scrolled help button trigger `pointerenter`.

Results (`UBYHOST_DB=/tmp/ubyhost-b14/db.sqlite`; browser runs with `UBYHOST_REQUIRE_BROWSER=1`, shots in `/tmp/ubyhost-b14`):
- A `test_0786_settings_geometry_browser.py`: 48 passed, 0 skipped.
- B settings/status tests: 69 passed.
- C copy tests: 46 passed.
- D host/browser/layout (39 files, run in chunks): 234 passed, 0 skipped, 7 failed:
  - `test_host_fee_navigation.py::test_frozen_report_order_and_forms` FAIL. Pre-existing: "Your records" is not in any app file at base `7b0355c4`.
  - `test_host_ux_acceptance.py` (4 tests: property editor, page family fit, rail/cards, keyboard focus) FAIL. Same on base, so pre-existing.
  - `test_host_wide_geometry_browser.py::test_direct_fee_backlinks_align_with_page_lane` FAIL. Passes at base. REGRESSION.
  - `test_layout_lint_browser.py::test_every_host_page_passes_the_layout_lint` FAIL: 36 `help-stranded` findings on `details.page-help` (fee-setup and property-detail at 320 px; the "?" sits on its own line, 48 px off the label). Passes at base. REGRESSION.
- E `test_static_versions.py`: 3 passed.
- F `scripts/context_lint.py`: FAIL on one error, `docs/tasks/0972-help-settings.md` is about 13,598 tokens over the 12,000 cap. The brief file is the cause, not the code. Warnings only otherwise.

Screenshots viewed (8 of 8), 390/768/1280 as named:
- settings-account-en-390: "?" on the last line of each label (New login e-mail, Business & legal details, User access, Security incidents). OK.
- settings-security-en-390: Signed-in devices, Passkeys, Two-factor "?" on the last line. "Registered 0" card. OK.
- help-open-pointer-security-390: popover opens under its "?", inside the 390 px width. OK.
- settings-technical-en-390: help-open headings show inline text, Guest e-mails status line "Mail backend console", activity "Recent activity (1 event)". Bottom nav overlays the full-page capture (artifact). OK.
- technical-mail-disabled-en-390: "Sending is off: no guest e-mail leaves this installation." with "Mail backend disabled". OK.
- settings-help-en-390: "User guide ?" on one line, button "Open user guide". OK.
- property-help-open-en-390: H1 "B14 Flat" alone, "?" beside it, 3-step panel below. OK.
- settings-security-cs-768: Czech labels, "?" on each last line, "Zaregistrováno 0". OK.
Not viewed: the other 22 screenshots.

§7 acceptance:
- H1 short title on Account, Security, Technical, Help: PASS (`test_0972_h1_is_the_short_title_only`).
- Property H1 stays short with help open; panel is sibling after `</h1>`: PASS (two tests).
- "?" on last line, 4 pages, EN/CS, 390/768/1280, no sideways scroll: PASS (`test_0972_help_stays_beside...`).
- Contextual unique help names: PASS.
- Pointer and keyboard open/Escape/Tab, focus ring, in viewport: PASS.
- Activity plural (0/1/many; CS one/few/many): PASS.
- Mail status from runtime backend, EN/CS: PASS.
- Passkeys once, "User guide" / "Open user guide": PASS.
- A to F green, 0 skipped: FAIL (D regressions above; F brief size).
- No change under static, mail.py, config.py, routes: PASS (`git diff` on those paths is empty).

Owner steps: none. Next: orchestrator decides the D regressions (new brief for the back-header page-help layout at 320 px), and shrinks the brief below the 12,000-token cap.
