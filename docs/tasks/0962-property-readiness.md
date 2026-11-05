# 0962: Property readiness as the first compact overview (batch B04: P01, P02, P03)

Status: todo
Depends on: B03 (shell), not yet landed; this brief is built on the base below and the orchestrator rebases/merges after B03 | Base commit: 7b0355c45ccdd2557a28edfcfe228aa1dc766e36 | Branch: codex/0962-b04-property-readiness
Executor: Haiku 5.5 | Worktree: /tmp/ubyhost-b04-worktree | Fits one session: no. Expect a checkpoint after step 3 (see §8, executor.md "at the cap").

## 1. Objective

The property page shows its title, then six compact status pills (Calendars, Guest link, Foreigner police, Business details, Stay fee, Smart lock) as the first content group, before every settings section. The Preview aside (title, "Checklist details", second Copy link) is removed; each pill opens its section, and that section lists what is missing, from the same `readiness` object as before.

## 2. Context

Rules: AGENTS.md hard rules 1, 6, 7, 9, 10. Readiness, filing and lock-online predicates are NOT touched: `admin._readiness`, `_READINESS_REPORT_FIELDS`, `property_health`, `health` rows and `door_code.state` stay as they are. No new i18n keys: the patch reuses `apartment.form.readiness.missing`, `apartment.form.readiness.item.*`, `health.guest_link.*`, `health.door.*`.

**Current state on this base (read, not yet browser-measured):**
- `App/app/templates/_property_editor.html` already renders the six pills as `nav.prop-strip` (lines 47-66: `<nav class="prop-strip" aria-label="{{ t('property_page.strip.aria') }}">`, six `.sc` items `data-strip="calendars|guest|police|business|fee|door"`). The Guest link pill is `div.sc.sc-link` with `copy_inline('overview-guest-url', ...)`. Pills link to `#sec-*`; `app.js` `initPropSectionLinks` opens the section on click and on hashchange.
- `<aside class="preview" aria-labelledby="property-preview-title">` (line 436 to the end) holds: `<h3 id="property-preview-title">`, the setup-continue card, the Leon card, and `<details class="setup-readiness-help" data-setup-status>` with the full checklist and `copy_inline('readiness-permalink', ...)`.
- Strip CSS is `App/app/static/app2.css` lines 2438-2463 (`body.v2 .prop-strip{display:grid;...grid-auto-rows:1fr...}`, `min-height:64px`, `overflow-wrap:anywhere` on `b` and `small`). Desktop two-column layout comes from `body.v2 .form{...grid-template-columns:minmax(0,1fr) 300px}` (line 383) and `:has(> aside.preview)` (lines 2587-2591).
- `App/app/templates/apartment_form.html` and `partials/settings_back_header.html` need no change (title and header actions stay as they are). They stay on the allowlist only in case the executor must touch them; the patch does not.

**P01 reproduction (decision input, record the result):** the review says the owner's arrangement (six cards collapsed into a narrow right column, labels split into syllables, title below the config rows) did NOT reproduce on a fresh baseline. By reading this base, the six pills are a separate `nav` before `.form`, so the owner's exact arrangement is expected NOT to reproduce here. Step 0 measures it. Do not claim a fix for a state you did not reproduce: say "not reproduced; the pills now lead the page regardless".

**Scope note for the orchestrator/owner (extends the batch plan's file list):** removing the Preview aside and the checklist invalidates existing assertions in 11 test files and needs a one-line cache-key bump in `base.html`. Those exact edits are in patch 02 and the `base.html` line in patch 01. This is a deliberate extension of the plan's allowlist; the executor must not add anything beyond §3.

## 3. Files

| Path (under App/) | Action | What |
|---|---|---|
| app/templates/_property_editor.html | edit (patch 01) | Add `miss` builder + `section_missing` macro; move continue/Leon cards into `div.prop-after-strip` under the strip; `.form` gets `prop-form-single`; delete the whole `<aside class="preview">`; add missing-notes to sections basics, police, calendars, messages, lock |
| app/static/app2.css | edit (patch 01) | Strip becomes flex-wrap compact pills, bounded Copy link, `.prop-after-strip`, `.prop-form-single`, `.prop-sec-missing` (host component stylesheet that styles these pills; no new file) |
| app/templates/base.html | edit (patch 01) | `app2.css?v=20261105-0961a` to `20261105-0962a` (only way to satisfy test_static_versions) |
| tests/static_versions.json | edit (patch 01) | app2.css sha256 and key |
| tests/test_property_navigation_browser.py | append tests (patch 03) + stale edits (patch 02) | The B04 tests (the host browser file that already covers the property page); stale edits: remove `_aside`, `_FIT_JS` aside refs |
| tests/test_0251_tablet_browser.py, test_0396_leon_opt_in_browser.py, test_0534_property_page_v2.py, test_0541_property_page_phone_browser.py, test_design_guardrails_browser.py, test_onboarding_followup_browser.py, test_onboarding_wizard_browser.py, test_property_preview_sticky_browser.py (rewritten), test_property_readiness.py, test_status_colours.py, v2_mockup.py | stale-assertion edits only (patch 02) | Replace assertions about the removed Preview aside / checklist with assertions about the pills |

No other file may change. Patches live in `docs/tasks/0962-patches/` (part of the brief; never edit them).

| Patch | sha256 |
|---|---|
| 01-source.patch | 36e0c70399f4d69fb283a6551a578cbd7333b8b072e1daee2e94673a44a9081f |
| 02-stale-tests.patch | ce0cc9946b990e576617030b2bb65ada94445685cb9000cf990242ade264f10f |
| 03-new-tests.patch | 294f8e94a47397bd43d1504b3005478835be03dfdfc90e13112dc311a3668644 |

## 4. Steps

Work in `/tmp/ubyhost-b04-worktree` (already on branch `codex/0962-b04-property-readiness`). Every command ends `2>&1 | tail -30`. Commit after each step with the message `0962 step k`.

0. **Venv and P01 baseline.** From the worktree root: `[ -e App/.venv ] || ln -s /tmp/ubyhost-0958-worktree/App/.venv App/.venv`. Check the base: `git rev-parse HEAD` must start `7b0355c`. Verify patches: `sha256sum docs/tasks/0962-patches/*.patch` equals §3. Then measure the baseline: `git apply docs/tasks/0962-patches/03-new-tests.patch` (it applies alone on base), run from `App/`:
   `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/ubyhost-b04 .venv/bin/python -m pytest tests/test_property_navigation_browser.py -k "b04_pills_lead" -q --tb=short -x -rs 2>&1 | tail -30`
   Expected on base: FAIL (the `facts` dict in the message shows `preview` greater than 0). Write down from that dict: `count`, `order`, `stripTop`, `sectionTop`, `preview`. If `stripTop` is above `sectionTop` and `order` has six items, the owner's collapsed-column arrangement is NOT reproduced. Then `git checkout -- App/tests/test_property_navigation_browser.py`. Do not commit step 0.
1. **Source patch.** `git apply --whitespace=error docs/tasks/0962-patches/01-source.patch`. If it fails: STOP. Then from `App/`: `.venv/bin/python -c "from app.templating import templates; templates.env.get_template('_property_editor.html'); templates.env.get_template('apartment_form.html'); print('compiled')" 2>&1 | tail -30` must print `compiled`. Commit `0962 step 1`.
2. **Stale assertions.** `git apply --whitespace=error docs/tasks/0962-patches/02-stale-tests.patch`. Commit `0962 step 2`.
3. **New tests.** `git apply --whitespace=error docs/tasks/0962-patches/03-new-tests.patch`. Commit `0962 step 3`. (This is the usual checkpoint: if you are at ~25 tool calls, write the report as `blocked` with `Done: steps 0 to 3. Left: step 4 and 5.`)
4. **Run §6 commands in order.** One fix attempt per failing test, inside the files of §3 only (see §8 for what is allowed). After any CSS tweak run `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -30` and keep the key `20261105-0962a`.
5. **Screenshots and report.** Open every file under `/tmp/ubyhost-b04` once with the image reader and describe it in one line in the report (see §7). Write `docs/tasks/0962-report.md` (600 tokens at most), set `Status: review` in this brief, commit `0962 report`. Do not push, do not open a PR: the owner steps below do that.

### What the patch does (for your review of the diff, do not retype)

- Pills: `body.v2 .prop-strip{display:flex;flex-wrap:wrap;gap:8px;...}`, each `.sc{flex:1 1 140px;min-height:52px;padding:8px 12px;border-radius:12px}`, `div.sc.sc-link{flex-basis:176px}`; `b`/`small` use `overflow-wrap:break-word;word-break:normal;hyphens:manual` (a word is never split unless it alone is wider than the pill); the Copy link button is `display:block;width:100%;max-width:100%;min-height:44px;white-space:normal` inside the Guest link pill; below 360 px each pill is full width.
- Missing notes: `miss = {basics, police, calendars}` is filled from `readiness.invite` and `readiness.report` (items not done; `anchor == 'address'` goes to basics, `'calendars'` to calendars, `'ubyport'` to police, other invite items to basics). Messages shows `health.guest_link.*` text when `g_bad`; Lock shows `health.door.offline` or `health.door.times`. Stay fee has no readiness predicate, so it has no note (its pill still opens the section). Markup keeps `<li class="readiness-item"><a href="#anchor">Missing: IDUB</a><span class="readiness-why">...</span></li>` so existing assertions on "Missing: ..." and `href="#ubyport"` keep working.
- Left on purpose: dead `.preview`/`.pv` CSS rules, the `wizard.overview.details` and `property_page.preview.title` i18n strings (no deletion outside the file list).

## 5. Do not touch

- `app/routes/*` (including `admin._readiness`), `app/property_health.py`, `app/validation.py`, filing, `app/static/app.js`, `app/host_i18n.py`, `app/host_vi_i18n.py`, `docs/` other than this brief, its patches and the report.
- Hard rules: light mode only; Auth forms are not involved; no new dependency; no new outbound request; no new personal-data field; copy rule 9 (no new strings are added). Never print real guest data; fixtures are synthetic.
- Do not edit the three patch files. Do not commit anything under `/tmp`. No screenshot is committed.

## 6. Commands (from App/, in this order, each ends `2>&1 | tail -30`)

Set once per command: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/ubyhost-b04`. Browser and geometry commands must show 0 skipped (`-rs`). Use a 600000 ms timeout; if a command times out, rerun it in the background and tail its output.

1. New tests: `.venv/bin/python -m pytest tests/test_property_navigation_browser.py -k b04 -q --tb=short -x -rs 2>&1 | tail -30` (expect 7 passed, 0 skipped).
2. Host row, geometry row, design guard, UX lint: `.venv/bin/python -m pytest tests/test_host_*.py tests/test_host_geometry.py tests/test_design_guardrails_browser.py tests/test_layout_lint_browser.py -q --tb=short -x -rs 2>&1 | tail -30` (layout lint: zero findings on host pages).
3. v2 row: `.venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -q --tb=short -x -rs 2>&1 | tail -30`.
4. Property row plus the touched test files: `.venv/bin/python -m pytest tests/test_onboarding*.py tests/test_property_*.py tests/test_first_*.py tests/test_0534_property_page_v2.py tests/test_0541_property_page_phone_browser.py tests/test_0251_tablet_browser.py tests/test_0396_leon_opt_in.py tests/test_0396_leon_opt_in_browser.py tests/test_0404_leon_setup.py tests/test_status_colours.py tests/test_calmer_forms.py tests/test_0284_states_browser.py -q --tb=short -x -rs 2>&1 | tail -30`.
5. Static: `.venv/bin/python -m pytest tests/test_static_versions.py tests/test_wp07_cache_heartbeats.py -q --tb=short -x 2>&1 | tail -30`.
6. From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30` and `git diff --check 7b0355c45ccdd2557a28edfcfe228aa1dc766e36 2>&1 | tail -30`, then `git diff --stat 7b0355c45ccdd2557a28edfcfe228aa1dc766e36 2>&1 | tail -30` (only the §3 paths, plus this brief, its patches and the report).

## 7. Acceptance

- [ ] `git diff --stat` against the base lists only §3 paths (plus brief, patches, report).
- [ ] Commands 1 to 6 pass, 0 skipped, layout lint zero findings.
- [ ] Chromium, long Czech name and long English name, at 390, 768, 1280 and 1440 (test `test_b04_pills_lead_the_page_with_long_names`): six pills in the order Calendars, Guest link, Foreigner police, Business details, Stay fee, Smart lock; first content group under the title (above the first section); no clipped label; no word split; no overlap, Copy link inside the Guest link pill; no horizontal scroll.
- [ ] `aside.preview`, `.setup-readiness-help`, `[data-setup-status]`, `#readiness-permalink` and the text "Checklist details" are absent; `data-copy="overview-guest-url"` exists exactly once.
- [ ] Keyboard (test `test_b04_keyboard_enter_on_each_pill_opens_its_section`): each pill focusable with a visible outline; Enter opens the matching `#sec-*`; Tab order is pill, Guest link pill, Copy link button, next pill.
- [ ] Copy link shows readable "Copied" and stays inside its pill at 390 and 1280.
- [ ] An incomplete property: clicking the Foreigner police pill opens `#sec-police` and shows "Missing: IDUB" there.
- [ ] Screenshots in `/tmp/ubyhost-b04`, each opened once and described in one line (what you see: order, wrapping, Copy link position, any clipping): `b04-{cs,en}-{390,768,1280,1440}-longname.png` (8), `b04-copied-390.png`, `b04-copied-1280.png`, `b04-incomplete-police-390.png`. Populated state is the fixture property (calendar and Business details set); incomplete state is the last file.
- [ ] Report states: P01 baseline result from step 0 ("not reproduced" or the measured facts) and that readiness, filing and lock-online code is unchanged (`git diff` shows no `app/routes`, `property_health`, `validation`).

## 8. Stop and ask

Stop and write the report (`blocked` where it applies) if:

- `git apply` of any patch fails, a patch sha256 differs, or HEAD is not `7b0355c`;
- a test fails twice; allowed single fix: inside the §3 CSS block, change `flex` basis numbers (140 px, 176 px), padding or the 44 px button height, then re-run `tests/test_static_versions.py --write`; never loosen or delete a new B04 assertion, never touch a skipped test;
- the clipboard copy test cannot reach "Copied" (do not weaken it; report it);
- any test is skipped, any host layout lint finding appears, or the v2 mockup row still reports `.preview h3`/`.pv` missing after patch 02;
- a file outside §3 needs a change, a new dependency or i18n key seems needed, or readiness, filing or lock-online logic seems to need a change;
- you reach 25 tool calls or about 50k tokens (`Done: steps 0 to k. Left: steps k+1 to 5.`);
- you need push, merge, secrets, SSH or deploy.

## 9. Report

`docs/tasks/0962-report.md`, 600 tokens at most: 1. `git diff --stat`. 2. Each command with the last 5 lines. 3. §7 ticked. 4. Step 0 P01 facts. 5. One line per screenshot. 6. Deviations, questions, owner steps left. Then set `Status: review`.

## Risk list (for the reviewer)

- `App/app/templates/_property_editor.html`: aside removal and card relocation (setup-continue, Leon `data-leon-card`), `.form prop-form-single`, `miss` builder (readiness reuse only), notes in five sections.
- `App/app/static/app2.css` lines near 2438: pill flex layout, Copy link bounds, `.form.prop-form-single` at 1024 px and up.
- `App/tests/test_property_preview_sticky_browser.py` (rewritten), `App/tests/v2_mockup.py` (`missing_ok` gains `.preview h3`, `.pv`), `App/tests/test_property_readiness.py` (`_checklist` helper, count assertion relaxed to `<= 12`).
- Batch dependency: B03 (shell) will touch `base.html` and `app2.css`; expect a conflict on the `app2.css?v=` key and `tests/static_versions.json` (rerun `--write` after merging).
- Known limits: the Calendars missing note links to `#calendars` (no such id; pre-existing anchor, kept so existing assertions stay valid); Stay fee has no missing note; the owner's exact Czech workspace/build is not available, so P01 stays a separate verification.

## Owner steps

1. Open a terminal in `/tmp/ubyhost-b04-worktree` and check `git log --oneline -6` shows the step commits.
2. Push the branch: `git push -u origin codex/0962-b04-property-readiness`.
3. Open a pull request into `main` and paste the per-page screenshot descriptions and the design-system checklist from the report (UX gate, AGENTS rule 10).
4. Merge only with `scripts/merge-pr-on-green.sh <PR number>` after CI is green and after B03 is rebased in; deploy by hand as usual.
