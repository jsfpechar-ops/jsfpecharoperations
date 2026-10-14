# 0102: Onboarding wizard — one focused page per step

Status: todo
Depends on: 0100 merged (head 0cae4c6) | Base: origin/claude/quirky-lamport-9svmd1 | Branch: task/0102-onboarding-wizard | PR base: claude/quirky-lamport-9svmd1
Executor: Cursor local agent | One session

## 1. Objective
Replace the banner-style setup guide with a real step-by-step onboarding: one focused page per step, with the real fields on that page and one primary action. The owner tested staging: the banner doesn't lead the host, the step count is wrong, and the police fields sit below the banner unnoticed.

## 2. Context
- Owner feedback (2026-10-13): "make a proper onboarding flow, not a shortcut through message boxes"; lead first-time hosts "like children"; one thing to do at a time.
- Current code (0096/0100): App/app/property_setup.py (step state in `settings` key `property_setup:<id>`), App/app/templates/_property_setup_guide.html (banner), App/app/demo.py (demo stay, source='demo', excluded from filing — DO NOT change exclusion logic), the waiting-for-login copy in host_i18n.py (`setup_guide.*` keys, verified behaviour — reuse unchanged).
- Saves must reuse the existing handlers and field partials (one editor per setting): calendar add (feed route), police fields (_property_editor.html Reporting section partial / apartment_update with only those fields), stay fee (_stay_fee_fields.html + existing fee save), door lock (existing lock section/forms), automation (`_automation_timing_values` / POST /apartments/{id}/automation-timing). Each step form posts to the existing route with `return_to=/apartments/{id}/setup/<next>`; errors re-render on the step page with typed values.
- Rules: AGENTS.md hard rules 1, 2, 5, 6, 7, 9. No schema change. Light mode. EN + CS for every string. Works without JavaScript.

## 3. Files
| Path | Action | What |
|---|---|---|
| App/app/routes/onboarding_wizard.py | create | GET/POST /apartments/{id}/setup and /setup/{step}; owner checks via access.apartment |
| App/app/main.py | edit | include the router |
| App/app/templates/setup_wizard/_layout.html | create | focused layout: property name, "Step N of 8", 8-segment progress, Back, Exit setup; no property tabs or cards |
| App/app/templates/setup_wizard/{calendar,guest_link,try_it,police,stay_fee,door_lock,automation,done}.html | create | one page per step (§4) |
| App/app/property_setup.py | edit | 8 steps; step 1 "Property details" done when name+operator+address are present; next_step(); counts |
| App/app/templates/_property_setup_guide.html | delete | banner removed |
| App/app/templates/_property_overview.html, apartment_form.html | edit | remove banner include; add a compact "Continue setup · N of 8 done → Continue" card for incomplete properties; Guest links card shows "Ready · Copy link" (full link via copy button), not the /l/… path |
| App/app/routes/admin.py | edit | after successful create, redirect to /apartments/{id}/setup/calendar; remove guide-only context |
| App/app/static/host.css | edit | /* 0102 */ block |
| App/app/host_i18n.py | edit | grouped `# 0102` block, EN+CS |
| App/tests/test_onboarding_wizard_browser.py | create | §7 |
| App/tests/test_property_setup_guide_browser.py | delete/replace | superseded by the wizard test |

No other file may change, except tests that assert the removed banner (update them to the wizard; never weaken unrelated assertions).

## 4. Steps
1. Step state: keep the `property_setup:<id>` key; steps = property, calendar, guest_link, try_it, police, stay_fee, door_lock, automation. Done-from-data: property (name, legal_entity_id, addr_obec, addr_house_no, addr_zip), calendar (≥1 feed or skipped), police (reporting readiness complete), stay_fee (rate set or skipped), door_lock (lock chosen or skipped), automation (saved once or "keep manual" chosen). guest_link/try_it are marked done by their buttons. Police "waiting" sets waiting=true and moves on, but police stays unfinished; done screen and overview card show "Police reporting: waiting for login" until complete.
2. Layout: heading "Set up {property}", subline "Step N of 8 · {step title}", progress bar (done = green, current = accent), content area max ~640px centred, one primary button bottom-right, Back link bottom-left, "Exit setup" small top-right (returns to the property Overview). Optional steps show "Skip this step" as a secondary text button. Never two filled buttons.
3. calendar: the platform + iCal URL + optional name fields (same names as _property_calendars.html form), primary "Add calendar"; secondary "Skip: I'll add stays manually". One sentence explaining what the calendar does.
4. guest_link: two big cards side by side (stacked < 600px): "Your guest link" (full URL, Copy) and "Your PIN" (large digits, Copy). Below: "Paste this into your platform's automated message" with a read-only preview and a "Copy message" button (link + PIN, EN/CS template). One sentence on why the PIN is needed. Primary "I've added it to my message".
5. try_it: "Try it yourself" — primary "Open the guest form" (creates/reuses the demo stay via demo.py, opens /l/… in a new tab with the demo PIN shown). The page shows "Waiting for your test registration…" with a "Check again" button (no JS polling needed; optional JS refresh every 5 s). When the demo has a guest: "This is what you'll see when a guest registers" + a small preview of the stay row + "Delete demo stay and continue" (primary) and "Keep it for now". Skip allowed: "Skip the test".
6. police: the actual police fields on the page (IDUB, web-service login, password, facility abbreviation, facility name, contact — same input names/help as the Reporting section), the "See an example police letter" button beside the heading, and the fine-print link to the Foreign Police page. Primary "Save and continue" (posts to the existing save; on missing fields re-render with errors). Secondary button (outlined, clearly visible, not a text link) "I'm still waiting for my police login", with the existing verified copy shown in a small note box right under the buttons.
7. stay_fee: the stay-fee fields from _stay_fee_fields.html with ? help; primary "Save and continue"; "Skip this step".
8. door_lock: intro "Optional. UbyHost works only with TTLock locks that have a gateway." + existing connect action; "Skip this step".
9. automation: three large radio cards (Only when I press send / Automatically after a delay [+ hours] / As soon as forms are complete) with one sentence each; primary "Finish setup".
10. done: checklist of the 8 steps with status (done / skipped / waiting), primary "Go to my property". If police is waiting, show it as an amber item with "Add police login" link back to the police step.
11. Remove the banner and its context; property Overview shows the compact continue card only when setup isn't complete and not dismissed ("Hide" on the card persists in the same settings key). Existing properties use the same done-from-data rules (so complete ones show nothing).

## 5. Do not touch
Filing/submit/scheduler code, demo exclusion filters, UbyPort client, fee arithmetic, invoices, TTLock client, schema/migrations, public/guest templates (except none), base.html ?v tags (bump only host.css/app.js to 20261013-0102 if you change them). No main push, no deploy.

## 6. Commands
From App/:
UBYHOST_BROWSER_EXECUTABLE=<local chromium if needed> UBYHOST_REQUIRE_BROWSER=1 UBYHOST_UBYPORT_ENV=mock UBYHOST_DEPLOYMENT=staging UBYHOST_ENABLE_SCHEDULER=0 .venv/bin/python -m pytest tests/test_onboarding_wizard_browser.py tests/test_demo_stay_exclusion.py tests/test_no_dead_internal_links.py tests/test_property_navigation_browser.py tests/test_host_ux_acceptance.py -q -rs
then the full suite: .venv/bin/python -m pytest tests -q -rs --cov=app --cov-fail-under=86
.venv/bin/ruff check app tests tools --select E9,F63,F7,F82,F401,F841 ; from repo root: python3 scripts/context_lint.py
Expected: all pass, 0 skipped browser tests; only env-only failures allowed are documented ones.

## 7. Acceptance
- [ ] Add property → lands on "Step 2 of 8 · Connect your calendar" with step 1 shown done.
- [ ] Each step page has exactly one filled button; optional steps have Skip; Back works; no property tabs/cards on wizard pages.
- [ ] Guest link step shows full link and PIN in two cards and a copyable message; no /l/ path fragment anywhere on Overview.
- [ ] Try-it creates a demo stay, the guest form opens, after a test registration the step shows the result; delete removes it; test_demo_stay_exclusion passes unchanged.
- [ ] Police fields are on the police step; Save and continue saves via the existing handler; "Still waiting" is a visible outlined button with the verified copy; done screen shows waiting until complete.
- [ ] Banner removed; incomplete properties show the compact continue card; complete ones show nothing.
- [ ] Browser test: full journey EN+CS at 390 and 1280, no-JS journey, geometry (no overflow) at 360/390/760/1280/1440; screenshots of every step in docs/tasks/0102-evidence/.
- [ ] Full suite + coverage pass; CI green on the PR.

## 8. Stop and ask
Stop and report if: an anchor/handler named above doesn't exist; a step can't reuse an existing save handler without changing its semantics; a schema change seems needed; a test fails twice; any filing/demo-exclusion code would need to change.

## 9. Report
docs/tasks/0102-report.md (≤1500 tokens), set Status: review: files changed (git diff --stat), commands with last 5 output lines, §7 ticked, deviations, questions, screenshot paths.

## Owner steps
1. Paste this prompt into a fresh Cursor chat.
2. When Cursor opens the PR, ask Claude to review it.
3. After approval, merge it into claude/quirky-lamport-9svmd1 with scripts/merge-pr-on-green.sh, then redeploy Render staging.
