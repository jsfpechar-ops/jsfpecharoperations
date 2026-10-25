# 0387: Leon (AI) chat gets the same support-chat look as Havel

Status: todo
Depends on: 0352 (merged); look follows 0386 (PR #508) | Base commit: HEAD of origin/main | Branch: claude/0387-leon-chat-look (already checked out; commit here)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Owner (Josef, 2026-10-25), after approving the new Havel look: "Might as well give the same similar look to Leon AI." Leon is the guest chat card at the end of the guest guide (`/g/<token>`, `templates/guest/_leon.html`). Today it looks like a form: every message is a bordered box with a "You"/"Leon (AI)" line inside, there is a "Your question" label over a big textarea, a "0 / 500" counter and a wide "Send" button. Reference look: `/mnt/project-files/havel-phone/real/answer-390.png` (Havel after 0386).

After this brief, the Leon card:
1. Header: a round solid accent avatar with a white chat icon, next to the title "Leon (AI)" and the intro line under it, smaller and muted.
2. Guest messages: solid accent bubble, white text, right-aligned, tail corner bottom-right, no visible "You" line (kept for screen readers).
3. Leon messages: soft neutral bubble with no border, tail corner bottom-left, the "Leon (AI)" line small and muted inside the bubble.
4. Host answers keep their green tint and their "<host>, your host, answered:" line, without the left border bar. Emergency messages stay as they are (bold, red 2 px border): safety beats looks.
5. The "Waiting for your host" note is a centred muted line, not a grey box.
6. Composer: the "Your question" label is visually hidden (kept for screen readers). One rounded pill holds the textarea, which starts at one line and grows to about 5 lines. Inside the pill, on the right, there is a round accent send button with an up-arrow icon, labelled with `leon_send`. The counter shows only when 50 or fewer characters are left.
7. No copy changes, no JS logic changes beyond the auto-grow and counter visibility.

## 2. Context

Rules: AGENTS.md 7 and docs/context/rules.md "Guest pages" (bump the `?v=` key in `templates/guest/base.html` for every guest CSS/JS file changed; guest browser tests 0 skipped). Guest templates are not covered by `scripts/design_lint.py`; guest.css uses its own `--g-*` tokens and raw px is normal there. Guest pages have no icon macro: write the two SVGs inline with `aria-hidden="true" focusable="false"`.

Current code (`grep -n` each before editing; STOP and report if one is missing):
- `App/app/templates/guest/_leon.html`: `<h2 id="leon-title">{{ t('leon_name') }}</h2>` then `<p class="g-intro">{{ t('leon_intro') }}</p>`; the form has `<label class="g-leon-label" for="leon-message">`, a `textarea#leon-message ... rows="2" maxlength="500" ... data-leon-input`, and `<div class="g-leon-bar">` holding `span.g-leon-count[data-leon-count]` and `button.g-btn.slim.g-leon-send[data-leon-send]`.
- `App/app/static/guest.css` ~1338-1360: all `.g-leon-*` rules. `.g-sr-only` exists (~1268). `.g-btn` (~831) sets `display:block; width:100%; padding: 15px 18px; box-shadow ...`.
- `App/app/static/guest-leon.js`: `bubble(role, kind, body)` builds `div.g-leon-msg.g-leon-msg--<role>` with `p.g-leon-who` and `p.g-leon-text`. Counter: `count.textContent = n + " / " + MAX; count.classList.toggle("g-leon-count--near", n > MAX - 50);` (~139).
- `App/app/templates/guest/base.html` line ~75: `guest-leon.js?v=20261024-0302`; find guest.css's `?v=` key in the same file.
- `App/tests/test_guest_leon_browser.py::test_the_chat_works_and_lays_out_on_a_phone` asserts `page.locator("[data-leon-count]").inner_text() == "5 / 500"`. A hidden element's innerText is "", so this assertion changes in step 5.

## 3. Files

| Path | Action |
|---|---|
| App/app/templates/guest/_leon.html | header, composer markup |
| App/app/static/guest.css | append one block |
| App/app/static/guest-leon.js | auto-grow, counter visibility |
| App/app/templates/guest/base.html | bump guest.css and guest-leon.js keys to `20261025-0387` |
| App/tests/static_versions.json | `--write`, if the test covers guest files |
| App/tests/test_guest_leon_browser.py | counter assertion, new look test |

## 4. Steps

1. **Header** (`_leon.html`): replace the `<h2>` and the `g-intro` lines with:
```html
  <div class="g-leon-head">
    <span class="g-leon-avatar" aria-hidden="true"><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M7.9 20A9 9 0 1 0 4 16.1L2 22Z"/></svg></span>
    <div class="g-leon-head-text"><h2 id="leon-title">{{ t('leon_name') }}</h2><p class="g-intro">{{ t('leon_intro') }}</p></div>
  </div>
```
2. **Composer** (`_leon.html`): add `g-sr-only` to the label's class (`class="g-leon-label g-sr-only"`). Replace the textarea and the whole `g-leon-bar` div with:
```html
    <div class="g-leon-pill">
      <textarea id="leon-message" name="message" rows="1" maxlength="500"
        placeholder="{{ t('leon_placeholder') }}" data-leon-input></textarea>
      <button type="submit" class="g-leon-send" data-leon-send aria-label="{{ t('leon_send') }}"><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="m5 12 7-7 7 7"/><path d="M12 19V5"/></svg></button>
    </div>
    <span class="g-leon-count" aria-hidden="true" data-leon-count hidden>0 / 500</span>
```
   The send button no longer has `g-btn slim`. Keep `data-leon-send` and `type="submit"`. Keep the error paragraph where it is.
3. **JS** (`guest-leon.js`), in the function that updates the counter (~139): after the `classList.toggle` line add `count.hidden = n <= MAX - 50;`. Then add an auto-grow on the same input event (find where that function is bound to `input`):
```js
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 132) + "px";
```
   Put these two lines inside the same counter function, so a reset after send (which already calls it, check) also shrinks the box. If the counter function is not called after the box is emptied on send, call it there.
4. **CSS**: append ONE block at the end of guest.css:
```css
/* 0387: Leon looks like a support chat, same family as Havel (owner 2026-10-25). */
.g-leon-head { display: flex; align-items: center; gap: 12px; margin: 0 0 16px; }
.g-leon-avatar { flex: none; display: inline-flex; align-items: center; justify-content: center; width: 40px; height: 40px; border-radius: var(--g-pill); background: var(--g-accent); color: var(--on-brand); }
.g-leon-head-text { min-width: 0; }
.g-leon-head h2 { margin: 0; }
.g-leon-head .g-intro { margin: 2px 0 0; font-size: 14px; line-height: 1.4; color: var(--g-muted); }
.g-leon-log { gap: 8px; }
.g-leon-msg { max-width: 82%; padding: 10px 14px; border: 0; border-radius: 18px; background: var(--g-surface-2); }
.g-leon-msg--leon { align-self: flex-start; border-bottom-left-radius: 6px; }
.g-leon-msg--guest { align-self: flex-end; background: var(--g-accent); border-bottom-right-radius: 6px; }
.g-leon-msg--guest .g-leon-text { color: var(--on-brand); }
.g-leon-msg--guest .g-leon-who { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
.g-leon-msg--guest .g-leon-queued { color: var(--on-brand); opacity: .85; }
.g-leon-msg--host { align-self: flex-start; border-left: 0; background: var(--g-ok-soft); border-bottom-left-radius: 6px; }
.g-leon-msg--asked { border-left: 0; }
.g-leon-msg--emergency { max-width: 100%; border: 2px solid var(--g-bad); border-radius: 14px; background: var(--g-bad-soft); }
.g-leon-who { font-size: 12px; }
.g-leon-waiting { padding: 4px 8px; background: transparent; text-align: center; color: var(--g-muted); font-size: 13.5px; }
.g-leon-pill { display: flex; align-items: flex-end; gap: 8px; padding: 4px 4px 4px 16px; border: 1px solid var(--g-line); border-radius: 26px; background: var(--g-surface); }
.g-leon-pill:focus-within { border-color: var(--g-accent); box-shadow: 0 0 0 3px var(--g-accent-ring); }
.g-leon-form .g-leon-pill textarea { flex: 1 1 auto; min-height: 0; height: 40px; margin: 0; padding: 9px 0; border: 0; border-radius: 0; background: transparent; box-shadow: none; resize: none; outline: none; font-size: 16px; line-height: 1.4; }
.g-leon-send { flex: none; display: inline-flex; align-items: center; justify-content: center; width: 44px; height: 44px; padding: 0; border: 0; border-radius: var(--g-pill); background: var(--brand-action); color: var(--on-brand); cursor: pointer; }
.g-leon-send:hover { background: var(--g-accent-hover); }
.g-leon-send:focus-visible { outline: 2px solid var(--g-accent); outline-offset: 2px; }
.g-leon-send:disabled { opacity: .6; cursor: default; }
.g-leon-count { display: block; margin: 6px 4px 0 0; text-align: right; }
.g-leon-count[hidden] { display: none; }
```
   Check every token used (`--g-surface-2`, `--on-brand`, `--brand-action`, `--g-accent-ring`, `--g-ok-soft`) exists: `grep -n -- "--on-brand\|--brand-action\|--g-surface-2" App/app/static/*.css`. If a guest textarea rule with higher specificity still paints a border or background inside the pill (look at the screenshot), raise the selector to `.g-leon-form .g-leon-pill textarea#leon-message`.
5. **Tests** (`test_guest_leon_browser.py`):
   - In `test_the_chat_works_and_lays_out_on_a_phone`, replace `assert page.locator("[data-leon-count]").inner_text() == "5 / 500"` with `assert page.locator("[data-leon-count]").is_hidden()`.
   - Add `test_leon_chat_look_on_a_phone` (same seeding and monkeypatches as that test, `en` only, 390x844). Assert: `.g-leon-avatar` is visible; the label `label[for=leon-message]` has a bounding box width ≤ 1; `.g-leon-send` is inside `.g-leon-pill` (box containment, 1 px tolerance) and is at least 44x44; filling 460 characters shows the counter with text `460 / 500`; filling `"line\n" * 8` makes the textarea taller than 40 px but at most 132; after sending "Hello" and the Leon reply, the guest bubble's computed `backgroundColor` differs from the Leon bubble's and `.g-leon-msg--guest .g-leon-who` has width ≤ 1; `document.documentElement.scrollWidth <= 390`. Save `leon-chat-390.png` (`page.locator("#leon").screenshot(...)`, the card only) to `SHOTS`, and also copy it to `docs/tasks/screenshots-0387/leon-chat-390.png`. Then, after `_host_answers(apartment_id)` and a reload, save `leon-chat-host-390.png` the same way.

## 5. Do not touch

Everything outside §3. No copy keys, no Leon routes, prompts, caps or queueing logic. Do not change the emergency message's colours or role.

## 6. Commands

From `App/`:
```
.venv/bin/ruff check app tests tools --select E9,F63,F7,F82,F401,F841 2>&1 | tail -5
UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium UBYHOST_REQUIRE_BROWSER=1 UBYHOST_UBYPORT_ENV=mock UBYHOST_DEPLOYMENT=staging UBYHOST_ENABLE_SCHEDULER=0 .venv/bin/python -m pytest tests/test_guest_leon_browser.py tests/test_guest_leon_chat.py tests/test_leon.py tests/test_guest_guide_browser.py tests/test_guest_browser_e2e.py tests/test_host_geometry.py tests/test_static_versions.py -q --tb=short -rs 2>&1 | tail -30
cd .. && git checkout -- $(git ls-files -m docs/tasks | grep -v 0387) 2>/dev/null; true
```
If a test fails, put its first assertion line in the report. Fix only if the cause is in a file from §3; otherwise stop.

## 7. Acceptance

- [ ] All §6 commands pass with 0 skipped, or the failure is in the report.
- [ ] `docs/tasks/screenshots-0387/leon-chat-390.png` and `leon-chat-host-390.png` exist; you looked at each once and they show the look in §1.

## 8. Stop and ask

As in TEMPLATE §8.

## 9. Report

`docs/tasks/0387-report.md` (200 tokens), `Status: review`. ONE commit `0387: Leon chat gets the support-chat look`, including this brief and the screenshots, ending with these two trailer lines:
```
Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Lvzax2VbKkYR4rb7JYLc3K
```
Do not push.
