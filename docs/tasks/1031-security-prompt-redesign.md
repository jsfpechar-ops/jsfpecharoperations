# 1031: Redesign the "Add a second way in?" prompt

Status: review

Executor: Haiku 5.5. Read AGENTS.md, docs/context/executor.md, this brief. Nothing else.
Branch: `claude/project-thread-2fhk70` (already checked out). Do not push; the orchestrator pushes.

## 1. Objective

The one-time login-security dialog (`#security-prompt` in `App/app/templates/base.html`) looks bad: stacked buttons touch, the passkey button has a double outline, descriptions float in tiny text, "Not now" is a big filled button, heavy grey border, cramped padding. Make it one calm rounded card (Wolt style): short title, one sentence, two equal option rows (bold title + one-line description under it, the whole row is the tap target, a chevron on the right), "Not now" as a quiet text button, footnote in muted text. Light mode only. Works without JavaScript and at 320 to 1280 px.

## 2. Context

Both stylesheets apply: `app.css` (non-v2 pages) and `app2.css` (`body.v2`, host dashboard).

## 3. Files

`App/app/templates/base.html`, `App/app/static/app.css`, `App/app/static/app2.css`, `docs/tasks/screenshots-1031/`.

## 5. Do not touch

- `App/app/static/passkeys.js` (logic, `data-passkey-add`, `data-passkey-supported`, `data-passkey-error`, `data-passkey-return`).
- Translation keys and strings (all 4 languages stay). No new keys.
- `data-security-prompt-later` must stay a `<button type="submit" value="later">` inside `<form method="dialog">`: ten tests click `#security-prompt [data-security-prompt-later]`.
- `id="security-prompt"`, `aria-labelledby`, `open` attribute, `.security-prompt` class.

## 4. Steps

### Step 1: template

File `App/app/templates/base.html`. Replace the whole block from `<dialog id="security-prompt"` to its closing `</dialog>` with:

```html
<dialog id="security-prompt" class="admin-dialog security-prompt" open aria-labelledby="security-prompt-title">
  <div class="security-prompt-body">
    <h2 id="security-prompt-title" class="security-prompt-title">{{ t('security_prompt.title') }}</h2>
    <p class="security-prompt-lede">{{ t('security_prompt.lede') }}</p>
    <div class="security-prompt-options">
      {% if prompt.passkeys %}
        <div class="security-prompt-option-wrap" data-passkey-supported hidden>
          <button class="security-prompt-option" type="button" data-passkey-add data-passkey-return="{{ request.url.path }}">
            <span class="security-prompt-option-text">
              <span class="security-prompt-option-title">{{ t('security_prompt.passkey') }}</span>
              <span class="security-prompt-option-help">{{ t('security_prompt.passkey_help') }}</span>
            </span>
            <span class="security-prompt-chevron" aria-hidden="true">&rsaquo;</span>
          </button>
          <p class="small err-text" data-passkey-error data-generic="{{ t('passkeys.error.failed') }}" role="alert" hidden></p>
        </div>
      {% endif %}
      <a class="security-prompt-option" href="/account/2fa/setup">
        <span class="security-prompt-option-text">
          <span class="security-prompt-option-title">{{ t('security_prompt.totp') }}</span>
          <span class="security-prompt-option-help">{{ t('security_prompt.totp_help') }}</span>
        </span>
        <span class="security-prompt-chevron" aria-hidden="true">&rsaquo;</span>
      </a>
    </div>
    <form method="dialog" class="security-prompt-later">
      <button class="security-prompt-later-btn" type="submit" value="later" data-security-prompt-later>{{ t('security_prompt.later') }}</button>
    </form>
    <p class="security-prompt-footnote">{{ t('security_prompt.footnote') }}</p>
  </div>
</dialog>
```

Note: `addPasskey` finds its scope with `button.closest(".settings-action-list, .security-prompt, .admin-dialog-form")`; `.security-prompt` is still the dialog, so the error box lookup keeps working. Check with `grep -n "function showError" -A8 App/app/static/passkeys.js | tail -12` that it finds `[data-passkey-error]` inside that scope; if not, STOP.

### Step 2: CSS

File `App/app/static/app.css`. Anchor: the line `.security-prompt { max-width: 460px; }` and the four `.security-prompt-*` lines under it (grep `-nF ".security-prompt"`). Delete those five lines and put this in their place (use only these tokens: `--surface`, `--ink`, `--ink-2`, `--line`, `--border-strong`, `--radius-lg`, `--radius-pill`, `--brand-action`, `--shadow-dialog`):

```css
.security-prompt {
  width: min(calc(100% - 32px), 440px);
  max-width: 440px;
  border: 0;
  border-radius: 20px;
  box-shadow: var(--shadow-dialog);
}
.security-prompt-body { padding: 28px 24px 20px; display: grid; gap: 0; }
.security-prompt-title { margin: 0 0 8px; font-size: 22px; line-height: 1.25; letter-spacing: -0.01em; color: var(--ink); }
.security-prompt-lede { margin: 0 0 20px; font-size: 15px; line-height: 1.5; color: var(--ink-2); }
.security-prompt-options { display: grid; gap: 12px; margin: 0 0 8px; }
.security-prompt-option-wrap { display: grid; gap: 8px; }
.security-prompt-option-wrap[hidden] { display: none; }
.security-prompt-option {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  min-height: 64px;
  padding: 14px 16px;
  box-sizing: border-box;
  border: 1px solid var(--line);
  border-radius: 14px;
  background: var(--surface);
  color: var(--ink);
  font: inherit;
  text-align: left;
  text-decoration: none;
  cursor: pointer;
  box-shadow: none;
}
.security-prompt-option:hover { border-color: var(--border-strong); background: #faf9f7; }
.security-prompt-option:focus-visible { outline: 2px solid var(--brand-action); outline-offset: 2px; }
.security-prompt-option:disabled { opacity: .6; cursor: default; }
.security-prompt-option-text { display: grid; gap: 2px; flex: 1 1 auto; min-width: 0; }
.security-prompt-option-title { font-size: 16px; font-weight: 600; line-height: 1.3; }
.security-prompt-option-help { font-size: 14px; line-height: 1.4; color: var(--ink-2); }
.security-prompt-chevron { flex: 0 0 auto; font-size: 24px; line-height: 1; color: var(--ink-2); }
.security-prompt-later { margin: 8px 0 0; text-align: center; }
.security-prompt-later-btn {
  min-height: 44px;
  padding: 8px 16px;
  border: 0;
  border-radius: var(--radius-pill);
  background: transparent;
  color: var(--ink-2);
  font: inherit;
  font-size: 15px;
  font-weight: 600;
  text-decoration: underline;
  text-underline-offset: 3px;
  cursor: pointer;
}
.security-prompt-later-btn:hover { color: var(--ink); }
.security-prompt-later-btn:focus-visible { outline: 2px solid var(--brand-action); outline-offset: 2px; }
.security-prompt-footnote { margin: 4px 0 0; text-align: center; font-size: 13px; line-height: 1.4; color: var(--ink-2); }
```

Then grep `-nF "body.v2 .btn"` is NOT needed. But check that no later rule restyles `.admin-dialog` with a border that beats this: `grep -nF ".admin-dialog," App/app/static/app.css` shows the rule near line 2856 with `border: 1px solid var(--border-strong)`. It comes later and has equal specificity to `.security-prompt`, so add `.admin-dialog.security-prompt { border: 0; }` directly after the `.security-prompt {...}` block above.

### Step 3: look at it (real-browser check)

From `App/`, start the app the way `docs/context/test-map.md` or an existing browser test does (grep `security-prompt-later` in `App/tests/test_host_quiet_dashboard_browser.py` to see how it logs in and reaches the dialog; copy that setup into a throwaway script `/tmp/shot_1031.py`, not committed). Take one screenshot of the open dialog each at 390x844, 768x1024, 1280x800, English and Czech (`cs`), save to `docs/tasks/screenshots-1031/` as `prompt-<lang>-<width>.png`. Open each and check: no overlap, options equal width and height, title wraps cleanly, nothing clipped at 390 px, no horizontal scroll. Also screenshot once at 390 px with JavaScript disabled to confirm the dialog is still readable.

If a screenshot shows a defect, fix the CSS once and retake. Second failure: STOP and report.

## 6. Commands

From `App/`:
`.venv/bin/python -m pytest tests/test_security_prompt_delay.py tests/test_passkeys.py tests/test_passkeys_client_browser.py tests/test_host_quiet_dashboard_browser.py tests/test_layout_lint_browser.py -q --tb=short -x -rs 2>&1 | tail -30`
0 skipped. From repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

## 7. Acceptance

Screenshots show a centred modal with two equal rows at 390/768/1280 in en and cs; section 6 tests green, 0 skipped.

## 8. Stop and ask

An anchor is not found, `showError` does not find the error box, a test fails twice, a screenshot defect survives one fix.

## 9. Report

Write `docs/tasks/1031-report.md`: Status, files changed, test output tail, per screenshot one line on what you saw. Commit steps as `1031 step 1`, `1031 step 2`, `1031 report`.

