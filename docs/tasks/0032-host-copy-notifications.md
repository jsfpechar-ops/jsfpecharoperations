# 0032: Shared host copy and notification feedback

Status: review
Depends on: none | Base commit: 6545d094f41b717e33ca053cb74e022fa291f5d6 | Branch: task/host-design-staging
Executor: Luna local agent | Fits one session

## 1. Objective

Replace transient signed-in host notifications with the approved light feedback
cards and add the owner's copy-to-checkmark interaction. Copy confirmations must
reflect actual success and retain stable geometry; no filing logic changes.

## 2. Context

Light-only, existing tokens, no new dependency, no tracking or storage of copied
values. Preserve actual reporting results, server flash meaning, Undo and sticky
warnings/errors. Never turn a send click into reported/accepted success. Privacy,
retention, database, report state machines and receipt proof are out of scope.
Unknown flash messages receive neutral information styling, not inferred success.

Read only this brief, AGENTS.md and the files in §3. Review-only visual reference:
`docs/plans/host-control-review.html`, functions `copyButton`, `copyActual`,
`feedbackToast`, page `feedback`; and `docs/plans/host-feedback-review.md`.
Do not copy the fictional data/demo handlers or replace the command engine.
The example's SVG checkmark/stack are approved; decorative demo looping is not.

Exact anchors (stop if missing):

`App/app/static/app.js`:

```js
  function initCopy() {
    document.querySelectorAll("[data-copy]").forEach(function (button) {
```

```js
  function initToasts() {
    document.querySelectorAll("[data-toast]").forEach(function (toast) {
```

```js
      if (item.copy) {
        Promise.resolve(navigator.clipboard && navigator.clipboard.writeText(item.copy)).then(function () {
```

`App/app/templates/base.html`:

```html
<body class="layout-host {{ 'host-workspace' if show_nav | default(true) }} {{ 'no-nav' if not (show_nav | default(true)) }}">
```

```html
<div class="toast-stack" role="status" aria-live="polite">
```

```html
    <div class="toast err" data-toast data-toast-sticky>
```

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/static/app.js` | Edit | Shared feedback, timer/dismissal/queue handling, truthful copy API/fallback and command-copy path |
| `App/app/static/host.css` | Edit | Host-workspace-scoped light cards, copy/checkmark geometry, mobile and reduced motion |
| `App/app/templates/base.html` | Edit | Host feedback shell, translated data labels, separate announcement regions, preserve existing flash/Undo markup and no-JS content |
| `App/app/host_i18n.py` | Edit targeted keys only | Generic failure/manual-copy and notification labels in EN/CS; reuse `common.copied`, existing copied labels and `a11y.dismiss_notification` |
| `App/tests/test_host_feedback_browser.py` | Add | Real Chromium checks of clipboard success/failure, feedback timers/focus/Undo and geometry |
| `App/tests/test_host_geometry.py` | Read only | Existing browser/geometry conventions and required checks |
| `docs/plans/host-control-review.html` | Read only | Approved standalone component reference |
| `docs/plans/host-feedback-review.md` | Read only | Scope, outcomes and design rationale |
| `docs/tasks/0032-host-copy-notifications.md` | Create/update | Brief and status |
| `docs/tasks/0032-report.md` | Create | Evidence and owner steps |

No other file may change. Existing host copy markup must work through shared
enhancement; if a specific template needs changes, report that follow-up rather
than expanding this brief. Keep public/guest/auth enhancements behavior intact.

## 4. Steps

1. Confirm anchors/base and create the branch. Read only the named source ranges
   and existing geometry fixture conventions. Inspect the reference component;
   do not copy its page-specific demo logic into production.
2. Provide one signed-in host feedback service in the existing bundle. Use white
   bordered cards with a semantic icon, readable wrapping and 44px dismissal.
   No dark skin, bounce, auto-generated event or new library. Existing errors
   remain red/sticky; ordinary unknown flash messages remain neutral information.
   Keep the existing Undo form/CSRF/action and milestone dismissal behavior.
3. Make feedback available even when there is no server flash on initial load.
   Keep server-rendered messages readable without JS. Use a non-live visual rail
   plus separate polite success/info and assertive error announcements; announce
   each message once, without nesting duplicate live regions. Never place copied
   values or personal details into a new notification or browser record.
4. Maximum three visible notifications, deduplicate repeats and queue excess
   without losing errors. Success/info expire after seven seconds. Pause timers
   on hover, focus and hidden document; resume only when all pause reasons clear.
   Error/warning/partial/Undo messages remain until dismissed. Preserve original
   sticky markers. A dismissal from keyboard focus returns focus to the origin
   where it still exists. Motion reduction removes decoration, not feedback.
5. Refactor `initCopy` to use one actual copy operation and outcome handler for
   every signed-in host `[data-copy]` control. Retain input/text-block selection.
   Await `navigator.clipboard.writeText`; fallback may report success only if
   `document.execCommand('copy')` returns true. Handle synchronous errors and
   rejected promises. On failure, keep selected text available and show a
   translated persistent failure/manual-copy notice; never display Copied.
6. After successful copy, show the approved overlapping copy/checkmark SVG
   and stroke effect in place. Use coral confirmation, existing translated labels
   and reserved icon/label space; do not replace and lose existing icons. Buttons
   retain their position/width/height and keyboard focus, then return to normal.
   Toast success is semantic green and contains only the outcome. Icon-only
   controls retain an accessible name and at least 44px touch targets.
7. Route the existing command palette's `item.copy` branch through the same
   truthful copy operation. Missing Clipboard API or rejection is not success.
   Preserve fuzzy matching, endpoint, permission scope, actions and dialog
   navigation. Do not replace its result text before success or hide a failure.
8. Add the meaningful browser checks below, run §6 and capture EN/CS at 360,
   390, 471 and 1280px. Include a denial/unsupported/fallback-false case so the
   current false-success bug is exercised, not just the checkmark CSS.
9. Write the report and set Status: review. Open a draft PR from this branch if
   available; do not push main, merge or deploy. Report unavailable credentials
   or failed checks rather than broadening scope.

## 5. Do not touch

No routes/reporting/worker/claim/ubyport/database/retention files. Do not change
send/retry operations, statuses, flash text semantics, invoice fields, address
requirements, filters, dashboard policy, public/auth/guest layouts or search
engine behavior. Do not replace persistent banners, report evidence or inline
validation with temporary notifications. No dependency, secret, guest data or
outbound endpoint additions.

## 6. Commands

From `App/`:

```sh
.venv/bin/python -m pytest tests/test_host_feedback_browser.py tests/test_host_geometry.py -q
.venv/bin/python -m pytest tests -q
```

Both must pass, with browser/geometry checks executing and zero skips. Follow
the existing test fixture's Chromium installation instructions if needed; do
not silently skip unavailable browsers. From the repository root:

```sh
python3 scripts/context_lint.py
```

Context lint passes. Run the repository's normal CI/format checks before review;
record exact outputs. No App tests were run by the orchestrator.

## 7. Acceptance

- [ ] Actual host link/message copy, clipboard denial, absent API and false
  legacy fallback all produce truthful outcomes; no unhandled rejection.
- [ ] Copy icon/label confirmation does not move/resize the control in EN/CS;
  existing SVG, focus and correct source text are retained.
- [ ] Current command-copy action uses the same outcome contract; other search
  navigation/keyboard functionality still works.
- [ ] Success/info, sticky error/Undo, repeated updates and queue overflow work;
  no fake send/acceptance result is added.
- [ ] Hover + focus + hidden-tab pause/resume do not race; errors remain visible.
- [ ] Announcements occur once; dismiss is keyboard reachable and restores focus;
  reduced motion, long wrapped text and mobile safe-area placement work.
- [ ] Undo still submits its existing guarded form; no-JS server messages remain
  readable; public/guest/auth behaviors are unaffected.
- [ ] EN/CS screenshots and measured no-overflow/no-layout-shift evidence at
  360, 390, 471 and 1280px, all required tests green with zero skips.

## 8. Stop and ask

Stop and report if an anchor is missing, base has drifted, a test fails twice,
a new dependency or out-of-scope file is needed, or filing/retention/permissions
would change. Do not use the standalone preview's passing checks as application
evidence. Need merge/deploy/secrets/SSH: hand exact steps to the owner.

## 9. Report

Write `docs/tasks/0032-report.md` (≤1,500 tokens): files changed, commands and
last five output lines, acceptance ticked, screenshot links, deviations,
questions, owner steps left. Set brief Status: review. Link the draft PR if one
was created; do not claim implementation beyond this brief.

## Risk list

`app.js` copy and command-copy contracts; live-region duplication and focus
handling; base flash/Undo CSRF structure; host-only CSS scope; tests executing
real browser checks rather than skipping.

## Owner steps

1. Review the PR's EN/CS before/after screenshots and command results.
2. Merge only after the required checks are green, using the repository merge
   script. Production deploy remains manual and is not part of this brief.
