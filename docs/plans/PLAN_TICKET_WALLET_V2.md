# PLAN — Ticket Wallet v2: finish the guest registration redesign

**Owner decision (Joe, 29 Sep 2026):** the whole guest flow ships as **Flow 2, "Ticket Wallet"**, with the **V1 Airline Pass** as the stay picker. The product owner has explicitly released this surface from the layout rules in `docs/DESIGN.md` (the single-column-only / no-shadow / arrival-lane rules). The rules that still apply are the brand core in `docs/DESIGN.md` ("The three surfaces"): light mode only, no framework, no web fonts, EN/CS parity, accessibility.

**Where this file lives:** `docs/plans/PLAN_TICKET_WALLET_V2.md`.
**Design standard:** `docs/DESIGN.md`, section "Guest registration: Ticket Wallet". The new `DESIGN.md` ships with this plan (TW2-18).
**Target look:** `docs/plans/ticket-wallet/ticket-wallet-v2-real-app-375.png` and `…-desktop-cs.png`. These are screenshots of the finished result running in the real app.
**Repo state this plan was written against:** `main` @ `96ebfd3` (29 Sep 2026).
**Handoff folder (commit it with this plan):** `docs/plans/ticket-wallet/`, containing `ticket-wallet-v1.patch` (Part A), `ticket-wallet-full.reference.patch` (Part A + Part B, the finished state) and the real-app screenshots.

---

## 0. Where we are (read this first)

**`main` (@ `96ebfd3`) has no Ticket Wallet code yet.** The guest pages still use the "arrival lane" design from `docs/DESIGN.md`. The work comes in two parts, both in this plan:

- **Part A: the Ticket Wallet foundation ("v1").** It is delivered ready-made as `docs/plans/ticket-wallet/ticket-wallet-v1.patch`. That patch was built and rendered against `96ebfd3`. It adds:
  - `static/guest-ticket.css` (705 lines, sections 1–17: tokens, app bar, ticket, stub, type, buttons, fields, PIN, stepper, stay passes, folds, hub, stamp and boarding pass, host contact, mail illustration, motion);
  - `static/ticket.js` (95 lines: party stepper, progress mirror, sending spinner, submit-in-stub);
  - `templates/guest/_ticket.html` (the `moon`, `route` and `boarding_pass` macros);
  - a `pass_date` Jinja global in `templating.py` ("28 Sep", "Mon", localised EN/CS);
  - 32 `tw_*` keys in `i18n.py` (16 EN + 16 CS);
  - `<body class="tw">`, the two new assets and the `tw_route` / `tw_progress` blocks in `guest/base.html`;
  - `.tw-ticket` + `data-tw-label` wrappers in `pin`, `pick` (the V1 Airline Pass), `claim`, `confirm`, `stay`, `assigned`, `unavailable` and `form`.
- **Part B: v2**, which is what the rest of this plan is about. Part A on its own is not yet the prototype.

I applied Part A and drove the real app (a seeded local server, Playwright, 375×812). These are the problems Part B fixes:

| # | Screen | Problem (seen in the real render of Part A) | Fixed by |
|---|---|---|---|
| F0 | hub, form | Part A breaks 3 existing tests: it adds classes to two elements whose exact markup the tests assert. | TW2-00 |
| F1 | every page | The app bar wraps to 3 lines: "GUEST REGISTRATION / Old Town Loft, / Prague", plus a wide "English / Čeština" pill. It eats about 110px of a 812px phone. | TW2-02 |
| F2 | PIN | A single 120px text box with underscores. Nothing says "6 digits" at a glance. | TW2-03 |
| F3 | Pick | The "That's my stay →" pill wraps into a **3-line blob**, because `guest.css` gives `.g-lane-action` `max-width: 78px` at ≤430px. | TW2-04 |
| F4 | Pick | The host message uses the browser's default ▶ triangle. | TW2-04 |
| F5 | Claim | About 120 words of hint text under the e-mail field push the button below the fold. | TW2-05 |
| F6 | Form | There is no step tracker; the rail and the wizard bar are both hidden. The guest cannot tell "step 2 of 5". | TW2-06 |
| F7 | Form | The "Why" and "Host message" folds sit **above** the ticket on every step, so the first field starts about 330px down. | TW2-06 |
| F8 | Form | Date of birth is one free-text box. | TW2-07 |
| F9 | Form | Nationality and country are native `<select>`s with about 250 options. | TW2-08 |
| F10 | Form | Purpose is a native select with 15 official codes; most guests want "Tourism". | TW2-09 |
| F11 | Form | The signature pad has no "sign here" cue and no "signed" state. | TW2-11 |
| F12 | Form, last step | The legal notice is long, full-size text, and the acknowledgement tick box is easy to miss above the sticky stub. | TW2-12 |
| F13 | Hub, done | Needs the v2 polish. | TW2-13, TW2-14 |
| F14 | all | The host contact block is a tall card with two big grey pills. | TW2-15 |
| F15 | desktop | The ticket floats alone on a flat grey page. | TW2-16 |

**Baseline tests on `96ebfd3` (before any change):** 22 tests already fail. All are host-side and out of scope:

- `test_dashboard_queue_copy.py` (5)
- `test_flash_next_step.py` (9)
- `test_pin_rotation_flash.py` (1)
- `test_status_colours.py` (7)

Separately, six tests in `test_guest_navigation.py` are **order-dependent**: they fail when that file runs in one command with `test_stay_hub.py`, and pass in the full-suite order. Ignore them unless the full run fails.

**This plan has been dry-run end to end.** I applied Part A plus every code block in Part B to a clean copy of `96ebfd3` and ran the full suite in two halves (1,130 + 772 tests). The result is **exactly the same 22 host-side failures and nothing else**. I then drove the whole guest flow in a headless browser at 375×812 (EN) and 1280×860 (CS).

The finished result is `docs/plans/ticket-wallet/ticket-wallet-full.reference.patch`, with screenshots in `ticket-wallet-v2-real-app-375.png` and `…-desktop-cs.png`. **If a task's result does not look right, compare your files with the reference patch.**

**Known copy nit, out of scope:** the Czech `check_in` / `check_out` labels on the passes show "CHECK-IN" / "CHECK-OUT", because the CS dictionary uses those words. If you want "Příjezd" / "Odjezd", that is a separate one-line copy change; ask Joe.

## 1. Hard rules for this work

1. **Only these files may change.** Part A's patch touches exactly the files listed in §0 and nothing else. In Part B:
   - `App/app/static/guest-ticket.css` (append new sections; the only edits to existing lines are in TW2-00 and TW2-06);
   - `App/app/static/ticket.js` (add new functions; register them in `start()`);
   - these templates under `App/app/templates/guest/`: `base.html`, `pin.html`, `claim.html`, `form.html`, `stay.html`, `_ticket.html`;
   - `App/app/i18n.py` (new keys in **both** `en` and `cs`);
   - the new test file `App/tests/test_ticket_wallet_v2.py`;
   - the docs: `docs/DESIGN.md` (replaced whole, TW2-18), this plan and `docs/plans/ticket-wallet/`.
2. **Do not touch** `static/guest.css`, `static/signature.js`, `static/tokens.css`, any route or Python other than `i18n.py`, any host or marketing template, or any e-mail template. About 20 tests read `guest.css` and `signature.js` line by line.
3. **Never rename or remove** an existing `id`, `name`, `class`, `data-*` attribute or `t('…')` call in a guest template. The server, `signature.js` and the tests all depend on them. You may **add** attributes and elements.
4. **Everything new in JS is progressive enhancement.**
   - The original control stays in the DOM and keeps its `name`, which is what gets submitted.
   - The enhancement writes into that control and fires the `input` or `change` event on it.
   - With JS off, the page must work exactly as it does today.
5. **Light mode only.** Use no `prefers-color-scheme`.
6. **Motion:** everything new must stop under `prefers-reduced-motion: reduce`. v1 section 17 already contains a blanket rule for this, so put all new CSS **above** section 17's `@media (prefers-reduced-motion)` block, or repeat that block at the end.
7. **i18n:** every new key goes into `en` and `cs` in the same commit, using the exact text in §4.
8. **Asset versions:** when you change `guest-ticket.css` or `ticket.js`, bump the `?v=` in `guest/base.html` to `20260929b`. Use `…c`, `…d` and so on for each later change.
9. **One task = one commit**, with the message `guest(tw2): TW2-NN <title>`. Run `cd App && .venv/bin/python -m pytest tests -q` before every commit (use `python3 -m pytest` if there is no `.venv`). The only failures allowed are the 22 host-side baseline failures from §0. Part A adds 3 guest failures; TW2-00 removes them again.

---

## 2. File map (Part B; Part A is the patch)

| File | What changes |
|---|---|
| `static/guest-ticket.css` | New sections 18–31 appended **before** section 17 (Motion). One existing line edited (TW2-06). |
| `static/ticket.js` | New functions `initPinCells`, `initDobCells`, `initCountryCombos`, `initPurposeChips`, `initTrackerLabels`, `initSignState`; all called from `start()`. |
| `templates/guest/base.html` | Asset `?v=` bump; `data-tw-*` label attributes on `<body>`. |
| `templates/guest/pin.html` | No markup change (JS builds the cells). |
| `templates/guest/claim.html` | Fold the two long e-mail hints into one `<details class="tw-more">`. |
| `templates/guest/form.html` | Add `data-tw-short` to each step; add the document-tip block; add labels on `.g-sign`; add purpose-chip data. |
| `templates/guest/stay.html` | Add the "next guest" hint and the stamp copy (TW2-13). |
| `templates/guest/_ticket.html` | No change. |
| `i18n.py` | New keys, listed in §4. |
| `tests/test_ticket_wallet_v2.py` | New file, §5. |
| `docs/DESIGN.md` | Replace the "Guest stay picker" section heading note (TW2-18). |

---

## 3. Tasks

Do them in this order: TW2-01, TW2-A, TW2-00, then TW2-02 onwards. Each task says **what the guest sees**, **exact code**, and **how to check it**.

### TW2-01 · Branch and baseline

```bash
git checkout main && git pull
git checkout -b feat/ticket-wallet-v2
cd App && .venv/bin/python -m pytest tests -q 2>&1 | tail -20 > /tmp/tw2-baseline.txt
```

Open `/tmp/tw2-baseline.txt`. The failures must be exactly the 22 host-side ones listed in §0. Save that list; it is your baseline. If anything **else** fails, stop and report it. There is no commit for this task.

### TW2-A · Apply the foundation (Part A)

The handoff folder `docs/plans/ticket-wallet/` must already be in the repo. If it is not, copy it in from the handoff first. Then:

```bash
git apply --check docs/plans/ticket-wallet/ticket-wallet-v1.patch   # must print nothing
git apply docs/plans/ticket-wallet/ticket-wallet-v1.patch
git status --short
```

`git status` must list exactly:

- 3 new files: `static/guest-ticket.css`, `static/ticket.js`, `templates/guest/_ticket.html`;
- 11 modified files: `i18n.py`, `templating.py`, `guest/base.html`, and the guest templates `assigned`, `claim`, `confirm`, `form`, `pick`, `pin`, `stay`, `unavailable`.

If `git apply --check` complains, **stop**: `main` has moved since this plan was written. Report which hunk failed; do not hand-merge.

Run the tests. You should see the 22 baseline failures plus exactly these 3:

- `test_stay_hub.py::test_the_next_action_sits_above_the_records`
- `test_stay_hub.py::test_the_records_fold_to_a_name_and_a_state`
- `test_guest_residence_prefill.py::test_the_hint_is_announced_as_a_status_not_an_alert`

Commit: `guest(tw): TW2-A Ticket Wallet foundation (skin, ticket.js, pass_date, templates)`. The next task fixes those 3.

### TW2-00 · Repair the three regressions from Part A

Part A added classes to two elements whose exact markup the tests assert. Put the state somewhere the tests do not look.

**(a)** `templates/guest/stay.html`. Find:

```html
  <details class="g-card g-summary {{ 'is-complete' if person.complete }}">
```

Replace it with:

```html
  <details class="g-card g-summary">
```

Then, directly after the `<summary class="g-summary-fold">…</summary>` line that follows it, add this line:

```html
    {% if person.complete %}<span class="tw-complete-mark" hidden></span>{% endif %}
```

**(b)** The same file. Find:

```html
      <div class="g-person {{ 'is-complete' if person.complete }}">
```

Replace it with:

```html
      <div class="g-person"{% if person.complete %} data-complete{% endif %}>
```

**(c)** `templates/guest/form.html`. Find:

```html
      <p class="hint tw-copied" role="status">
```

Replace it with:

```html
      <p class="hint" role="status" data-tw-copied>
```

**(d)** `static/guest-ticket.css` (this is an edit to existing v1 lines). Find:

```css
.tw details.g-summary.is-complete::before,
.tw .g-person.is-complete::before { background: var(--green); }
```

Replace it with:

```css
.tw details.g-summary:has(> .tw-complete-mark)::before,
.tw .g-person[data-complete]::before { background: var(--green); }
```

In the same file, find `.tw .tw-copied {` and replace it with `.tw [data-tw-copied] {`.

**Check:** `pytest tests/test_stay_hub.py tests/test_guest_residence_prefill.py -q` passes. Commit: `guest(tw2): TW2-00 keep v1 state out of the markup tests assert`.

### TW2-02 · App bar: one line, short language codes

**Guest sees:** a dark bar about 88px tall on a phone. The mark and "Old Town Loft, Prague" sit on one line, cut off with "…" if too long. Beside them is a small `EN | CS` switch. Under that are the route line ("29 SEP → 2 OCT · 3 NIGHTS") and the coral progress line. "Guest registration" is still read out by screen readers.

Append to `guest-ticket.css`, directly **above** the line `/* 17. Motion`:

```css
/* =======================================================================
   Ticket Wallet v2 — see docs/plans/PLAN_TICKET_WALLET_V2.md.
   Sections 18+ are v2. Section 17 (Motion) stays last on purpose so its
   reduced-motion rule also covers everything added here.
   ======================================================================= */

/* 18. App bar v2 --------------------------------------------------------- */
.tw .g-head { gap: 2px 12px; padding-top: 10px; }
.tw .g-head .g-title { flex: 1 1 auto; min-width: 0; }
.tw .g-head .g-title > div { min-width: 0; }
/* The words "Guest registration" stay in the page for screen readers and
   tests; the bar itself shows the property, which is what the guest reads. */
.tw .g-head h1 {
  position: absolute !important;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
  white-space: nowrap;
}
.tw .g-head .g-facility {
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}
/* "English" / "Čeština" become EN / CS on screen; the full word is still
   the link's accessible name because the text node is only shrunk. */
.tw .g-head .g-lang a {
  justify-content: center;
  min-width: 44px;
  padding: 0 10px;
  font-size: 0;
}
.tw .g-head .g-lang a::before {
  content: attr(hreflang);
  font-size: 12.5px;
  font-weight: 750;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.tw .tw-route { margin-top: 0; }
.tw .tw-progress { margin-top: 8px; }
```

**Check:** at 375px the bar is at most 96px tall, and the language links read "EN" and "CS". With VoiceOver or NVDA the link still reads "English". Bump `?v=` in `base.html` for `guest-ticket.css`.

### TW2-03 · PIN: six cells

**Guest sees:** six boxes. Typing fills them left to right, with a blinking coral caret in the current box. Pasting "482913" or using iOS/Android one-time-code autofill fills all six. When all six are filled they turn green. The existing Continue button still submits.

**How it works:** the real `#pin` input is placed *on top of* the six cells and made invisible. It still receives focus, typing, autofill and form submit; the cells only paint what it holds.

Add to `ticket.js`, inside the IIFE, above `// A page restored from the back/forward cache`:

```js
  // 5. PIN: paint the one real #pin input as six cells. The input sits on
  //    top of the cells, invisible, so focus, typing, paste and one-time-code
  //    autofill all still go to the real field.
  function initPinCells() {
    var input = document.querySelector(".tw .g-pin-input");
    if (!input || input.getAttribute("data-tw-cells")) return;
    input.setAttribute("data-tw-cells", "1");
    var size = parseInt(input.getAttribute("maxlength") || "6", 10);
    var box = document.createElement("div");
    box.className = "tw-pin";
    var cells = [];
    for (var i = 0; i < size; i += 1) {
      var cell = document.createElement("span");
      cell.className = "tw-pin-cell";
      cell.setAttribute("aria-hidden", "true");
      box.appendChild(cell);
      cells.push(cell);
    }
    input.parentNode.insertBefore(box, input);
    box.appendChild(input);
    if (input.getAttribute("aria-invalid") === "true") box.classList.add("is-bad");

    function paint() {
      var digits = input.value.replace(/\D/g, "").slice(0, size);
      if (digits !== input.value) input.value = digits;
      var focused = document.activeElement === input;
      cells.forEach(function (c, k) {
        c.textContent = digits.charAt(k);
        c.classList.toggle("is-filled", k < digits.length);
        c.classList.toggle("is-caret", focused && k === Math.min(digits.length, size - 1));
      });
      box.classList.toggle("is-complete", digits.length === size);
      if (digits.length) box.classList.remove("is-bad");
    }
    ["input", "focus", "blur", "keyup", "change"].forEach(function (name) {
      input.addEventListener(name, paint);
    });
    paint();
  }
```

Add `initPinCells();` inside `start()`.

CSS (section 19), appended after section 18:

```css
/* 19. PIN cells v2 (built by ticket.js initPinCells) --------------------- */
.tw .tw-pin {
  position: relative;
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: var(--space-2);
  max-width: 400px;
}
.tw .tw-pin-cell {
  display: grid;
  place-items: center;
  height: 64px;
  border: 1.5px solid var(--border-strong);
  border-radius: var(--radius-md);
  background: var(--surface);
  color: var(--ink);
  font: 700 26px/1 var(--font-sans);
  transition: border-color var(--motion-fast), box-shadow var(--motion-fast), background var(--motion-fast);
}
.tw .tw-pin-cell.is-caret { border-color: var(--brand); box-shadow: 0 0 0 4px var(--focus-ring); }
.tw .tw-pin-cell.is-caret:empty::after {
  content: "";
  width: 2px;
  height: 28px;
  background: var(--brand);
  animation: tw-blink 1s steps(1) infinite;
}
.tw .tw-pin.is-complete .tw-pin-cell { border-color: var(--green); background: var(--green-bg); color: var(--green); }
.tw .tw-pin.is-bad .tw-pin-cell { border-color: var(--red); }
/* The real input covers the row, invisible. 16px stops iOS zooming in. */
.tw .tw-pin .g-pin-input {
  position: absolute;
  inset: 0;
  z-index: 1;
  width: 100%;
  height: 100%;
  margin: 0;
  padding: 0;
  border: 0;
  background: transparent;
  color: transparent;
  caret-color: transparent;
  font-size: 16px;
  letter-spacing: 0;
  opacity: 0.01;
  box-shadow: none;
}
@keyframes tw-blink { 50% { opacity: 0; } }
```

**Check:**
- Paste "123456" and the six cells fill.
- A wrong PIN comes back from the server with `aria-invalid`, and the cells show red borders until you type.
- With JS disabled you get the v1 single box.

### TW2-04 · Stay picker: fix the wrapping pill, style the host note

**Guest sees:** each pass's footer shows the property name on the left and a one-line "That's my stay →" pill on the right. The host message is a quiet card with a chevron; opened, the message appears in serif italics like a handwritten note.

CSS (section 20):

```css
/* 20. Stay picker v2 ----------------------------------------------------- */
.tw .tw-pass-foot { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); }
.tw .tw-pass-foot > span:first-child { min-width: 0; }
.tw .tw-pass-foot > span:first-child b { display: block; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
/* guest.css caps .g-lane-action at 78px on phones for the old lane layout;
   on a pass the pill must stay on one line. */
.tw .tw-pass-head > span:first-child { flex: 0 0 auto; white-space: nowrap; }
.tw .tw-pass-head .g-lane-status { text-align: right; }
.tw .tw-pass .g-lane-action {
  flex: 0 0 auto;
  max-width: none;
  padding-top: 0;
  white-space: nowrap;
  text-align: center;
}
.tw .g-arrival-message {
  margin-top: var(--space-4);
  padding: 0 var(--space-4);
  border: 1px solid color-mix(in srgb, var(--brand) 18%, var(--border));
  border-radius: var(--radius-lg);
  background: var(--surface);
}
.tw .g-arrival-message summary {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  list-style: none;
}
.tw .g-arrival-message summary::-webkit-details-marker { display: none; }
.tw .g-arrival-message summary::before {
  content: "";
  flex: 0 0 auto;
  width: 7px;
  height: 7px;
  border-right: 2px solid var(--brand-action);
  border-bottom: 2px solid var(--brand-action);
  transform: rotate(-45deg);
  transition: transform var(--motion-base) var(--ease-standard);
}
.tw .g-arrival-message[open] summary::before { transform: rotate(45deg); }
.tw .g-arrival-message p { margin: 0 0 var(--space-4); font: italic 17px/1.5 var(--tw-serif); color: var(--ink); }
```

**Check:** at 320px, 375px and 430px the pill is one line. `tests/test_guest_pick_status.py` still passes (the template is unchanged).

### TW2-05 · Claim: fold the long e-mail text

**Guest sees:**
- Under the e-mail field, **one** short line: *"We send your private link here. No marketing."*
- A coral "What we use your e-mail for ›" disclosure. Opening it shows the full original text (both paragraphs, word for word).
- The Send button is visible without scrolling at 375×812.

In `templates/guest/claim.html`, replace **only** these lines:

```html
      <div class="hint">{{ t('claim_email_help') }}</div>
      <div class="hint">{{ t('claim_cookie_help') }}
        {% if privacy_url %}<a href="{{ privacy_url }}">{{ t('privacy_link') }}</a>{% endif %}
      </div>
```

with:

```html
      <div class="hint">{{ t('tw_email_short') }}</div>
      <details class="tw-more">
        <summary>{{ t('tw_email_more') }}</summary>
        <div class="hint">{{ t('claim_email_help') }}</div>
        <div class="hint">{{ t('claim_cookie_help') }}
          {% if privacy_url %}<a href="{{ privacy_url }}">{{ t('privacy_link') }}</a>{% endif %}
        </div>
      </details>
```

The full text stays in the HTML, so tests that look for it still pass, and it remains available before submit.

CSS (section 21):

```css
/* 21. Quiet "more" disclosure (claim e-mail, anywhere small) ------------- */
.tw details.tw-more { margin-top: var(--space-2); }
.tw details.tw-more > summary {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  min-height: 44px;
  list-style: none;
  cursor: pointer;
  color: var(--brand-action);
  font-size: 14px;
  font-weight: 650;
}
.tw details.tw-more > summary::-webkit-details-marker { display: none; }
.tw details.tw-more > summary::after {
  content: "";
  width: 6px;
  height: 6px;
  border-right: 2px solid currentColor;
  border-bottom: 2px solid currentColor;
  transform: rotate(-45deg);
  transition: transform var(--motion-base) var(--ease-standard);
}
.tw details.tw-more[open] > summary::after { transform: rotate(45deg); }
.tw details.tw-more .hint { margin-top: var(--space-2); }
/* On the claim page the date card and why-fold used to sit above the ticket;
   the app bar already shows the dates, so the slim pass is enough. */
.tw .g-stay-summary + .tw-ticket { margin-top: 0; }
```

New i18n keys: `tw_email_short` and `tw_email_more` (see §4).

**Check:**
- At 375×812 the "Send me the form link" button is fully visible without scrolling, once the party size and e-mail are filled.
- Open "What we use your e-mail for" and the original two paragraphs are there.

### TW2-06 · Form: step tracker on top, folds underneath

**Guest sees:**
- A thin line "3 nights · Person 1 of 2".
- Under it, **five labelled segments**: `Details · Document · Home · Sign · Check`. The current one is coral with coral text, finished ones are coral, and future ones are grey. Tapping a finished segment goes back to that step (this reuses the rail's existing edit buttons).
- The "Why you are filling this in" and "A message from your host" folds now sit **below** the ticket.

**6a. Edit one existing v1 line.** In section 2 of `guest-ticket.css`, delete exactly this line:

```css
.tw .g-checkin-rail { display: none !important; }
```

**6b. Add short step names.** These go in `templates/guest/form.html`. Add one attribute to each `data-guest-step` element; do not change anything else on those lines:

| Existing element (find by its `data-step-title`) | Add |
|---|---|
| `data-step-title="{{ t('your_details') }}"` | `data-tw-short="{{ t('tw_step_details') }}"` |
| `data-step-title="{{ t('tw_document_title') }}"` | `data-tw-short="{{ t('tw_step_document') }}"` |
| `data-step-title="{{ t('residence_title') }}"` | `data-tw-short="{{ t('tw_step_home') }}"` |
| `data-step-title="{{ t('passport_photo_title') }}"` | `data-tw-short="{{ t('tw_step_photo') }}"` |
| `data-step-title="{{ t('signature') }}"` | `data-tw-short="{{ t('tw_step_sign') }}"` |
| `data-step-title="{{ t('legal_notice_title') }}"` | `data-tw-short="{{ t('tw_step_check') }}"` |

**6c. JS: swap the long step names for the short ones in the tracker.** `signature.js` rebuilds the list on every `guest-wizard:shown` event. The ticket.js listener is registered later, so it runs after that rebuild and rewrites the labels.

```js
  // 6. The check-in rail (built by signature.js) becomes the top tracker.
  //    Its labels are the long step titles; show the short ones instead.
  function initTrackerLabels() {
    var form = document.querySelector("[data-guest-wizard]");
    var list = document.querySelector("[data-checkin-steps]");
    if (!form || !list) return;
    var nationality = form.querySelector('[name="nationality"]');
    function liveSteps() {
      // The same filter signature.js uses: a step can opt out for one nationality.
      return Array.prototype.slice.call(form.querySelectorAll("[data-guest-step]")).filter(function (s) {
        var skip = s.getAttribute("data-guest-step-skip-when");
        return !skip || !nationality || nationality.value !== skip;
      });
    }
    function relabel(event) {
      var steps = event && event.detail && event.detail.steps
        ? Array.prototype.slice.call(event.detail.steps)
        : liveSteps();
      var items = list.querySelectorAll(".g-checkin-step");
      Array.prototype.forEach.call(items, function (item, index) {
        var step = steps[index];
        var short = step && step.getAttribute("data-tw-short");
        var name = item.querySelector("span:not(.sr-only)");
        if (short && name) {
          name.textContent = short;
          item.setAttribute("title", step.getAttribute("data-step-title") || short);
        }
      });
    }
    form.addEventListener("guest-wizard:shown", relabel);
    relabel();
  }
```

Add `initTrackerLabels();` to `start()`. It must come **after** `initSubmitStub();` in that list; the order inside `start()` otherwise does not matter.

**6d. CSS (section 22):**

```css
/* 22. Form tracker v2 (the old check-in rail, shown on every width) ------ */
.tw .g-checkin-rail,
.tw .g-checkin-page main > .g-checkin-rail {
  display: block;
  position: static;
  margin: 0 0 var(--space-4);
}
.tw .g-checkin-stay { display: block; padding: 0 4px; border: 0; background: none; }
.tw .g-checkin-stay .g-property-mark,
.tw .g-checkin-stay-body strong,
.tw .g-checkin-stay-body span:first-of-type { display: none; }
.tw .g-checkin-stay-body span { font-size: 13.5px; font-weight: 650; color: var(--ink-muted); }
.tw .g-checkin-steps-title {
  position: absolute !important;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
}
.tw .g-checkin-steps { display: flex; gap: 4px; margin: var(--space-2) 0 0; padding: 0; border: 0; }
.tw .g-checkin-step {
  position: relative;
  display: block;
  flex: 1 1 0;
  min-width: 0;
  padding: 10px 0 12px;
  border: 0;
  border-top: 4px solid var(--border);
  color: var(--ink-faint);
  font-size: 11px;
  font-weight: 700;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.tw .g-checkin-step i { display: none; }
.tw .g-checkin-step.is-done { border-top-color: var(--brand); color: var(--ink-muted); }
.tw .g-checkin-step.is-current { border-top-color: var(--brand); color: var(--brand-ink); }
/* The rail's Change button covers the whole finished segment. */
.tw .g-checkin-step-edit {
  position: absolute;
  inset: -8px 0 0;
  width: 100%;
  margin: 0;
  padding: 0;
  opacity: 0;
  cursor: pointer;
}
.tw .g-checkin-step:focus-within { outline: 2px solid var(--brand); outline-offset: 2px; border-radius: 4px; }
/* Help folds go under the ticket on the form. */
.tw .g-checkin-main { display: flex; flex-direction: column; }
.tw .g-checkin-main > * { order: 1; }
.tw .g-checkin-main > .g-back,
.tw .g-checkin-main > .g-err { order: 0; }
.tw .g-checkin-main > details { order: 2; }
```

**Check:**
- On step 1 the tracker shows `Details` in coral and the rest grey.
- Go to step 3; tap `Details` and you are back on step 1 with your typing kept.
- For a Czech guest with passport photos enabled, the Photo step disappears from the tracker (the list is rebuilt from the filtered steps).
- At 1280px the tracker is still on top, not a side rail.

### TW2-07 · Date of birth: three boxes

**Guest sees:**
- Three boxes labelled **Day / Month / Year**, each showing the numeric keypad.
- Typing "14" jumps to Month, and "03" jumps to Year.
- Backspace in an empty box goes back one box.
- Pasting "14.03.1988" or "1988-03-14" into any box fills all three.
- Underneath, the existing read-back appears as a green chip: "✓ You entered 14 March 1988".

The real `#birth_date` input stays, hidden. `signature.js` still formats it, reads it back and validates it.

JS:

```js
  // 7. Date of birth: Day / Month / Year boxes that write "DD.MM.YYYY" into
  //    the real #birth_date, so signature.js keeps formatting, the read-back
  //    and validation exactly as before.
  function initDobCells() {
    var real = document.getElementById("birth_date");
    if (!real || real.getAttribute("data-tw-cells")) return;
    real.setAttribute("data-tw-cells", "1");
    var names = [
      [real.getAttribute("data-tw-day") || "Day", 2, "DD", "bday-day"],
      [real.getAttribute("data-tw-month") || "Month", 2, "MM", "bday-month"],
      [real.getAttribute("data-tw-year") || "Year", 4, "YYYY", "bday-year"]
    ];
    var group = document.createElement("div");
    group.className = "tw-dob";
    group.setAttribute("role", "group");
    var label = document.querySelector('label[for="birth_date"]');
    if (label) {
      if (!label.id) label.id = "birth_date_label";
      group.setAttribute("aria-labelledby", label.id);
    }
    var boxes = names.map(function (n, k) {
      var wrap = document.createElement("label");
      wrap.className = "tw-dob-part";
      var small = document.createElement("small");
      small.textContent = n[0];
      var box = document.createElement("input");
      box.type = "text";
      box.inputMode = "numeric";
      box.maxLength = n[1];
      box.placeholder = n[2];
      box.autocomplete = n[3];
      box.id = "birth_date_" + ["d", "m", "y"][k];
      if (real.getAttribute("aria-invalid")) {
        box.setAttribute("aria-invalid", "true");
        box.setAttribute("aria-describedby", real.getAttribute("aria-describedby") || "");
        box.className = "bad";
      }
      wrap.appendChild(small);
      wrap.appendChild(box);
      group.appendChild(wrap);
      return box;
    });
    real.parentNode.insertBefore(group, real);
    real.classList.add("tw-vh");
    real.setAttribute("tabindex", "-1");
    real.setAttribute("aria-hidden", "true");

    function split() {
      var m = /^(\d{0,2})\.?(\d{0,2})\.?(\d{0,4})$/.exec(real.value || "");
      boxes[0].value = m ? m[1] : "";
      boxes[1].value = m ? m[2] : "";
      boxes[2].value = m ? m[3] : "";
    }
    function join() {
      var d = boxes[0].value, mo = boxes[1].value, y = boxes[2].value;
      var digits = d + (d.length === 2 ? mo : "") + (d.length === 2 && mo.length === 2 ? y : "");
      real.value = digits;
      real.dispatchEvent(new Event("input", { bubbles: true }));
    }
    function pad(box) {
      if (box.value.length === 1 && box !== boxes[2]) box.value = "0" + box.value;
    }
    boxes.forEach(function (box, k) {
      box.addEventListener("input", function () {
        box.value = box.value.replace(/\D/g, "").slice(0, box.maxLength);
        box.classList.remove("bad");
        join();
        if (box.value.length === box.maxLength && boxes[k + 1]) boxes[k + 1].focus();
      });
      box.addEventListener("blur", function () { pad(box); join(); });
      box.addEventListener("keydown", function (e) {
        if (e.key === "Backspace" && !box.value && boxes[k - 1]) boxes[k - 1].focus();
      });
      box.addEventListener("paste", function (e) {
        var text = ((e.clipboardData || window.clipboardData).getData("text") || "").trim();
        if (/\d{1,4}\D\d{1,2}\D\d{1,4}|\d{8}/.test(text)) {
          e.preventDefault();
          real.value = text;
          real.dispatchEvent(new Event("input", { bubbles: true }));
          split();
        }
      });
    });
    // The wizard focuses the real field when it is invalid; send the guest
    // to the first box that still needs digits instead.
    real.addEventListener("focus", function () {
      var target = boxes.filter(function (b) { return b.value.length < b.maxLength; })[0] || boxes[0];
      target.focus();
    });
    real.addEventListener("invalid", function () {
      boxes.forEach(function (b) { if (b.value.length < b.maxLength) b.classList.add("bad"); });
    });
    split();
  }
```

Give the real input the translated box labels in `form.html`. On the `#birth_date` `<input …>` tag, add the three attributes below and keep every attribute that is already there:

```html
data-tw-day="{{ t('tw_dob_day') }}" data-tw-month="{{ t('tw_dob_month') }}" data-tw-year="{{ t('tw_dob_year') }}"
```

CSS (section 23):

```css
/* 23. Date of birth boxes (ticket.js initDobCells) ------------------------ */
.tw .tw-dob { display: grid; grid-template-columns: 1fr 1fr 1.6fr; gap: var(--space-2); }
.tw .tw-dob-part { display: block; }
.tw .tw-dob-part small { display: block; margin-bottom: 4px; color: var(--ink-muted); font-size: 12px; font-weight: 650; }
.tw .tw-dob-part input { width: 100%; text-align: center; font-variant-numeric: tabular-nums; }
.tw #birth-date-readback:not(:empty) {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-top: var(--space-2);
  padding: 4px 12px;
  border-radius: var(--radius-pill);
  background: var(--green-bg);
  color: var(--green);
  font-weight: 650;
}
.tw #birth-date-readback:not(:empty)::before { content: "\2713"; font-weight: 800; }
```

Add `initDobCells();` to `start()`.

**Check:**
- Type 1, 4, 0, 3, 1, 9, 8, 8 and the read-back says "14 March 1988".
- The review list says "14 March 1988".
- Server-side validation of an impossible date ("31.02.1990") still returns the error and highlights the boxes.
- `tests/test_guest_dob_separator.py` still passes.

### TW2-08 · Nationality and country: type-to-search

**Guest sees:**
- A text field showing the current country, for example "Germany".
- Focusing it and typing "ger" or "deu" narrows the list, with common countries first.
- Arrow keys and Enter pick; Escape closes.
- Picking closes the list and updates everything that listens today: the visa field hides for EU countries, the passport-photo step appears or disappears, and the residence country copies the nationality.

The real `<select>` stays in the DOM (hidden) and is still what gets submitted.

JS:

```js
  // 8. Country search over the real <select> (nationality, residence country).
  function initCountryCombos() {
    ["nationality", "res_country"].forEach(function (id) {
      var select = document.getElementById(id);
      if (!select || select.getAttribute("data-tw-combo")) return;
      select.setAttribute("data-tw-combo", "1");
      var seen = {};
      var options = [];
      Array.prototype.forEach.call(select.options, function (o) {
        if (!o.value || seen[o.value]) return;
        seen[o.value] = true;
        options.push({ code: o.value, label: o.textContent.trim() });
      });
      function norm(s) {
        return String(s || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
      }
      var wrap = document.createElement("div");
      wrap.className = "tw-combo";
      var input = document.createElement("input");
      input.type = "text";
      input.id = id + "_search";
      input.className = select.className;
      input.autocomplete = "off";
      input.setAttribute("role", "combobox");
      input.setAttribute("aria-autocomplete", "list");
      input.setAttribute("aria-expanded", "false");
      input.setAttribute("aria-controls", id + "_list");
      input.placeholder = select.getAttribute("data-tw-placeholder") || "";
      if (select.getAttribute("aria-invalid")) {
        input.setAttribute("aria-invalid", "true");
        input.setAttribute("aria-describedby", select.getAttribute("aria-describedby") || "");
      }
      var list = document.createElement("ul");
      list.id = id + "_list";
      list.className = "tw-combo-list";
      list.setAttribute("role", "listbox");
      list.hidden = true;
      wrap.appendChild(input);
      wrap.appendChild(list);
      select.parentNode.insertBefore(wrap, select);
      select.classList.add("tw-vh");
      select.setAttribute("tabindex", "-1");
      select.setAttribute("aria-hidden", "true");
      var label = document.querySelector('label[for="' + id + '"]');
      if (label) label.setAttribute("for", input.id);

      var active = -1;
      var shown = [];
      function currentLabel() {
        var o = select.options[select.selectedIndex];
        return o && o.value ? o.textContent.trim() : "";
      }
      function sync() { if (document.activeElement !== input) input.value = currentLabel(); }
      function render(query) {
        var q = norm(query);
        shown = options.filter(function (o) {
          return !q || norm(o.label).indexOf(q) !== -1 || norm(o.code).indexOf(q) === 0;
        }).slice(0, 60);
        list.textContent = "";
        if (!shown.length) {
          var none = document.createElement("li");
          none.className = "tw-combo-none";
          none.textContent = select.getAttribute("data-tw-none") || "—";
          list.appendChild(none);
        }
        shown.forEach(function (o, k) {
          var li = document.createElement("li");
          li.id = id + "_opt_" + k;
          li.setAttribute("role", "option");
          li.setAttribute("aria-selected", o.code === select.value ? "true" : "false");
          var code = document.createElement("b");
          code.textContent = o.code;
          li.appendChild(code);
          li.appendChild(document.createTextNode(o.label));
          li.addEventListener("mousedown", function (e) { e.preventDefault(); pick(o); });
          list.appendChild(li);
        });
        active = -1;
        open(true);
      }
      function open(yes) {
        list.hidden = !yes;
        input.setAttribute("aria-expanded", yes ? "true" : "false");
        if (!yes) input.removeAttribute("aria-activedescendant");
      }
      function highlight(k) {
        var items = list.querySelectorAll('[role="option"]');
        if (!items.length) return;
        active = (k + items.length) % items.length;
        Array.prototype.forEach.call(items, function (li, i) { li.classList.toggle("is-active", i === active); });
        input.setAttribute("aria-activedescendant", items[active].id);
        items[active].scrollIntoView({ block: "nearest" });
      }
      function pick(o) {
        select.value = o.code;
        select.dispatchEvent(new Event("change", { bubbles: true }));
        input.value = o.label;
        input.classList.remove("bad");
        input.removeAttribute("aria-invalid");
        open(false);
      }
      input.addEventListener("focus", function () { input.select(); render(""); });
      input.addEventListener("input", function () { render(input.value); });
      input.addEventListener("keydown", function (e) {
        if (e.key === "ArrowDown") { e.preventDefault(); if (list.hidden) render(input.value); highlight(active + 1); }
        else if (e.key === "ArrowUp") { e.preventDefault(); highlight(active - 1); }
        else if (e.key === "Enter" && !list.hidden) {
          e.preventDefault();
          if (shown[active]) pick(shown[active]); else if (shown.length === 1) pick(shown[0]);
        } else if (e.key === "Escape") { open(false); input.value = currentLabel(); }
      });
      input.addEventListener("blur", function () { setTimeout(function () { open(false); input.value = currentLabel(); }, 120); });
      // Wizard validation focuses the hidden select; hand focus to the search.
      select.addEventListener("focus", function () { input.focus(); });
      select.addEventListener("invalid", function () { input.classList.add("bad"); });
      // Other scripts change the select directly (residence copies nationality).
      document.addEventListener("change", function () { setTimeout(sync, 0); });
      sync();
    });
  }
```

Add to both `<select id="nationality" …>` and `<select id="res_country" …>` in `form.html`, keeping all existing attributes:

```html
data-tw-placeholder="{{ t('tw_country_search') }}" data-tw-none="{{ t('tw_country_none') }}"
```

CSS (section 24):

```css
/* 24. Country search (ticket.js initCountryCombos) ------------------------ */
.tw .tw-combo { position: relative; }
.tw .tw-combo input { padding-right: 44px; }
.tw .tw-combo::after {
  content: "";
  position: absolute;
  right: 18px;
  top: 22px;
  width: 8px;
  height: 8px;
  border-right: 2px solid var(--ink-muted);
  border-bottom: 2px solid var(--ink-muted);
  transform: rotate(45deg);
  pointer-events: none;
}
.tw .tw-combo-list {
  position: absolute;
  z-index: 30;
  left: 0;
  right: 0;
  top: calc(100% + 6px);
  max-height: 280px;
  margin: 0;
  padding: var(--space-1);
  overflow: auto;
  list-style: none;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-popover);
}
.tw .tw-combo-list li {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  min-height: 48px;
  padding: 0 var(--space-3);
  border-radius: var(--radius-sm);
  color: var(--ink);
  cursor: pointer;
}
.tw .tw-combo-list li b { width: 36px; color: var(--ink-muted); font-size: 12px; }
.tw .tw-combo-list li:hover,
.tw .tw-combo-list li.is-active { background: var(--surface-hover); }
.tw .tw-combo-list li[aria-selected="true"] { color: var(--brand-ink); font-weight: 650; }
.tw .tw-combo-list .tw-combo-none { color: var(--ink-muted); cursor: default; }
.tw .tw-vh {
  position: absolute !important;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
  white-space: nowrap;
}
```

Add `initCountryCombos();` to `start()`.

**Check:**
- Type "czech" and pick Czechia: the passport-photo step disappears (when that property requires photos) and the visa field hides.
- Pick Ukraine and the visa field shows.
- On the Home step, residence country already shows the nationality.
- Submit and the server receives the ISO code.
- `tests/test_guest_country_picker.py` still passes; it reads server HTML, which is unchanged.

### TW2-09 · Purpose: chips

**Guest sees:** four chips, **Tourism · Business · Visiting family or friends · Study**, plus **Other…**. Tourism is pre-selected (it is today's default). Tapping Other… reveals the full official list (the real select). If the saved value is something rare, the select is shown from the start with Other… pressed.

JS:

```js
  // 9. Purpose: the four common codes as chips over the real <select>.
  function initPurposeChips() {
    var select = document.getElementById("purpose");
    if (!select || select.getAttribute("data-tw-chips")) return;
    select.setAttribute("data-tw-chips", "1");
    var common = (select.getAttribute("data-tw-common") || "10,01,03,11").split(",");
    var group = document.createElement("div");
    group.className = "tw-chips";
    group.setAttribute("role", "group");
    var label = document.querySelector('label[for="purpose"]');
    if (label) {
      if (!label.id) label.id = "purpose_label";
      group.setAttribute("aria-labelledby", label.id);
    }
    var buttons = [];
    common.forEach(function (code) {
      var o = select.querySelector('option[value="' + code + '"]');
      if (!o) return;
      var b = document.createElement("button");
      b.type = "button";
      b.className = "tw-chip";
      b.textContent = o.textContent.trim();
      b.setAttribute("data-code", code);
      b.addEventListener("click", function () {
        select.value = code;
        select.dispatchEvent(new Event("change", { bubbles: true }));
        paint(false);
      });
      group.appendChild(b);
      buttons.push(b);
    });
    var other = document.createElement("button");
    other.type = "button";
    other.className = "tw-chip is-other";
    other.textContent = select.getAttribute("data-tw-other") || "Other…";
    other.addEventListener("click", function () { paint(true); select.focus(); });
    group.appendChild(other);
    select.parentNode.insertBefore(group, select);

    function paint(showSelect) {
      var inCommon = common.indexOf(select.value) !== -1;
      var openSelect = showSelect || !inCommon;
      buttons.forEach(function (b) {
        b.setAttribute("aria-pressed", !openSelect && b.getAttribute("data-code") === select.value ? "true" : "false");
      });
      other.setAttribute("aria-pressed", openSelect ? "true" : "false");
      select.classList.toggle("tw-vh", !openSelect);
      if (openSelect) select.removeAttribute("tabindex"); else select.setAttribute("tabindex", "-1");
    }
    select.addEventListener("change", function () { paint(common.indexOf(select.value) === -1); });
    paint(false);
  }
```

On `<select id="purpose" name="purpose">` in `form.html`, add:

```html
data-tw-common="10,01,03,11" data-tw-other="{{ t('tw_purpose_other') }}"
```

CSS (section 25):

```css
/* 25. Purpose chips (ticket.js initPurposeChips) -------------------------- */
.tw .tw-chips { display: flex; flex-wrap: wrap; gap: var(--space-2); margin-bottom: var(--space-3); }
.tw .tw-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 48px;
  padding: 0 var(--space-4);
  border: 1.5px solid var(--border-strong);
  border-radius: var(--radius-pill);
  background: var(--surface);
  color: var(--ink);
  font: inherit;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
}
.tw .tw-chip[aria-pressed="true"] {
  border-color: var(--brand-action);
  background: var(--brand-soft);
  color: var(--brand-ink);
}
.tw .tw-chip[aria-pressed="true"]:not(.is-other)::before { content: "\2713"; font-weight: 800; }
```

Add `initPurposeChips();` to `start()`.

**Check:**
- The default is Tourism, and its chip is pressed.
- Pick Business, and the review list says "Business".
- Pick Other…, then choose "Transit" in the select; the review says "Transit".
- Reload the edit page of that guest and the select is shown with Other… pressed.

### TW2-10 · Document tip and copied-address card

**Guest sees:**
- Under "Travel document number", a small **drawn passport page**. It has a photo block, grey lines, and a pulsing coral rectangle top-right where the number usually is.
- For guest 2 and later, the existing "Copied from Anna …" line becomes a **green card with a ✓**.

In `form.html`, directly **after** `<div class="hint">{{ t('doc_number_help') }}</div>` (inside `#doc-wrap`), add:

```html
      <div class="tw-doc-tip" aria-hidden="true">
        <span class="tw-doc-page"><i class="tw-doc-photo"></i><i class="tw-doc-no"></i><i class="tw-doc-lines"></i></span>
      </div>
```

CSS (section 26):

```css
/* 26. Document tip + copied address ------------------------------------- */
.tw .tw-doc-tip { margin-top: var(--space-3); }
.tw .tw-doc-page {
  position: relative;
  display: block;
  width: 168px;
  height: 108px;
  border: 1.5px solid var(--border-strong);
  border-radius: 10px;
  background: linear-gradient(180deg, var(--canvas) 0 100%);
}
.tw .tw-doc-photo {
  position: absolute;
  left: 12px;
  top: 18px;
  width: 38px;
  height: 48px;
  border-radius: 4px;
  background: var(--border);
}
.tw .tw-doc-no {
  position: absolute;
  right: 12px;
  top: 12px;
  width: 58px;
  height: 14px;
  border-radius: 3px;
  background: color-mix(in srgb, var(--brand) 25%, transparent);
  outline: 2px solid var(--brand);
  animation: tw-pulse 1.8s var(--ease-standard) infinite;
}
.tw .tw-doc-lines {
  position: absolute;
  left: 60px;
  right: 12px;
  top: 36px;
  height: 30px;
  background: repeating-linear-gradient(180deg, var(--border) 0 4px, transparent 4px 10px);
}
.tw .tw-doc-page::after {
  content: "";
  position: absolute;
  left: 12px;
  right: 12px;
  bottom: 12px;
  height: 14px;
  background: repeating-linear-gradient(90deg, var(--border-strong) 0 6px, transparent 6px 9px);
  opacity: 0.6;
}
@keyframes tw-pulse { 50% { outline-color: color-mix(in srgb, var(--brand) 30%, transparent); } }
.tw [data-tw-copied] {
  background: var(--green-bg);
  border-color: color-mix(in srgb, var(--green) 35%, transparent);
  color: var(--green);
}
.tw [data-tw-copied]::before {
  content: "\2713";
  display: grid;
  place-items: center;
  flex: 0 0 auto;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--green);
  color: var(--on-brand);
  font-weight: 800;
}
```

**Check:**
- On the Document step the drawing is visible and not announced by screen readers.
- Add guest 2, and on Home the green copied card shows with the first guest's address pre-filled (the server already does the copy).

### TW2-11 · Signature: "Sign here" and "Signed"

**Guest sees:**
- A taller (200px) pad with a light baseline and the grey words "Sign here" under it.
- After drawing, the frame turns solid ink and the words change to green "✓ Signed".
- Clear resets it.

In `form.html`, change `<div class="g-sign">` to:

```html
<div class="g-sign" data-tw-sign="{{ t('tw_sign_here') }}" data-tw-signed="{{ t('tw_signed') }}">
```

JS:

```js
  // 10. Signature pad: mirror "has a signature" onto the pad for styling.
  function initSignState() {
    var pad = document.querySelector(".tw .g-sign");
    var hidden = document.getElementById("signature");
    var canvas = document.getElementById("sig-canvas");
    if (!pad || !hidden || !canvas) return;
    function sync() { pad.classList.toggle("is-signed", !!hidden.value); }
    ["mouseup", "touchend", "pointerup", "keyup"].forEach(function (name) {
      canvas.addEventListener(name, function () { setTimeout(sync, 30); });
    });
    var clear = document.getElementById("sig-clear");
    if (clear) clear.addEventListener("click", function () { setTimeout(sync, 30); });
    sync();
  }
```

CSS (section 27):

```css
/* 27. Signature pad v2 --------------------------------------------------- */
.tw .g-sign {
  position: relative;
  border: 1.5px dashed var(--border-strong);
  border-radius: var(--radius-lg);
}
.tw .g-sign canvas { height: 200px; }
.tw .g-sign::before {
  content: "";
  position: absolute;
  left: 8%;
  right: 8%;
  top: 150px;
  border-bottom: 1.5px solid var(--border);
  pointer-events: none;
}
.tw .g-sign::after {
  content: attr(data-tw-sign);
  position: absolute;
  left: 8%;
  top: 158px;
  color: var(--ink-faint);
  font-size: 13px;
  pointer-events: none;
}
.tw .g-sign.is-signed { border-style: solid; border-color: var(--ink-muted); }
.tw .g-sign.is-signed::after { content: "\2713  " attr(data-tw-signed); color: var(--green); font-weight: 650; }
.tw .g-sign .bar { border-radius: 0 0 var(--radius-lg) var(--radius-lg); }
```

Add `initSignState();` to `start()`.

**Check:**
- Draw and the frame turns solid with "✓ Signed". Clear brings back "Sign here".
- `tests/test_guest_signature_kept.py` passes. On the edit page with a kept signature, the pad shows "✓ Signed" on load.

### TW2-12 · Check step: compact review and a visible acknowledgement

**Guest sees:**
- The review list becomes clean rows: label on the left, value on the right, and a coral "Change" link.
- Legal information is in a light grey box at 14px.
- The acknowledgement tick box is a **highlighted coral-edged box** that is always directly above the Submit stub.

CSS only (section 28):

```css
/* 28. Check step: review rows, compact legal, visible ack ---------------- */
.tw .g-review-list { display: block; margin: 0 0 var(--space-5); border: 1px solid var(--border); border-radius: var(--radius-lg); overflow: hidden; }
.tw .g-review-list dt {
  padding: var(--space-3) var(--space-4) 0;
  color: var(--ink-muted);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.tw .g-review-list dd {
  margin: 0;
  padding: 2px var(--space-4) var(--space-3);
  border-bottom: 1px solid var(--border);
  color: var(--ink);
  font-weight: 600;
}
.tw .g-review-list dd:last-of-type { border-bottom: 0; }
.tw .g-legal-notice {
  margin: 0 0 var(--space-4);
  padding: var(--space-4) !important;
  border-radius: var(--radius-lg);
  background: var(--canvas-subtle) !important;
}
.tw .g-legal-notice h2 { font: 650 17px/1.3 var(--font-sans) !important; }
.tw .g-legal-notice h3 { font-size: 13.5px; }
.tw .g-legal-notice p { font-size: 13.5px; }
.tw .g-legal-notice .legal-ack {
  margin: var(--space-4) calc(-1 * var(--space-4)) calc(-1 * var(--space-4));
  padding: var(--space-4);
  border-top: 0;
  border-radius: 0 0 var(--radius-lg) var(--radius-lg);
  background: var(--brand-soft);
  box-shadow: inset 0 0 0 1.5px color-mix(in srgb, var(--brand) 35%, transparent);
}
.tw .g-legal-notice .legal-ack .checkline span { color: var(--ink); font-weight: 650; }
.tw .g-legal-notice .legal-ack input[type="checkbox"] { width: 22px; height: 22px; accent-color: var(--brand-action); }
```

**Check:**
- On the last step, scroll to the bottom of the ticket: the coral acknowledgement box sits directly above the sticky Back / Submit stub, and nothing overlaps it.
- `tests/test_guest_why_passport.py`, `test_terms_copy.py` and the legal-notice tests still pass (no markup change).

### TW2-13 · Hub and saved: guest cards and the stamp moment

**Guest sees:**
- After saving guest 1: a green "SAVED" ticket with the **REGISTERED stamp** springing in, and "Saved — thank you". Below it, the group ticket has one coral button, "Add a person".
- The group list shows each guest as a card with a coloured left edge: green = registered, coral = current, grey = waiting.

In `stay.html` there is **no change**. Keep `t('add_person')`: `tests/test_stay_hub.py` asserts the text "Add a person" on this page.

CSS (section 29):

```css
/* 29. Hub v2 ------------------------------------------------------------- */
.tw .g-still-missing { font-weight: 650; color: var(--brand-ink); }
.tw details.g-summary > summary.g-summary-fold::after { color: var(--ink-faint); }
.tw .g-saved .tw-stamp { margin-bottom: var(--space-4); }
.tw .g-saved h2 { color: var(--ink) !important; }
```

**Check:** save guest 1 of 2 and you see the stamp. The next action is one coral "Add a person" button, and guest 1's card has a green left edge.

### TW2-14 · Done: boarding passes

v1 already renders the boarding passes. v2 adds:

- one line under the passes: **"Keep this page — it is your confirmation."** (new key `tw_done_keep`);
- a 150ms stagger (already in v1);
- a subtle "tear-off" rise on each pass.

In `stay.html`, directly after the closing `</div>` of `<div class="tw-bps">`, inside the same `{% if passes %}`, add:

```html
        <p class="g-intro tw-keep">{{ t('tw_done_keep') }}</p>
```

CSS (section 30):

```css
/* 30. Done v2 ------------------------------------------------------------ */
.tw .tw-keep { margin: var(--space-4) 0 0; font-size: 14px; text-align: center; }
.tw .tw-bp { box-shadow: 0 18px 36px -28px rgba(20, 20, 18, 0.45); }
```

### TW2-15 · Host contact: one compact row

**Guest sees:** a single white row at the bottom. The first line is a small uppercase "YOUR HOST" with the legal entity's name under it, then the help sentence in 13px. Below that are two pills side by side: **☎ phone** and **✉ e-mail**, each at least 44px, with coral icons.

CSS only (section 31). The icons are CSS masks with data URIs; the CSP allows `img-src data:`.

```css
/* 31. Host contact v2 ---------------------------------------------------- */
.tw #host-contact { grid-template-columns: 1fr; padding: var(--space-4) var(--space-5); }
.tw #host-contact h2 {
  font: 700 11.5px/1.2 var(--font-sans) !important;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--ink-muted);
}
.tw #host-contact .g-intro { font-size: 13px; }
.tw #host-contact p:not(.g-intro):not(.hint) { display: inline-flex; margin-right: var(--space-2); }
.tw #host-contact a::before {
  content: "";
  width: 16px;
  height: 16px;
  margin-right: 8px;
  background: var(--brand-action);
  -webkit-mask: var(--tw-ico) center / contain no-repeat;
  mask: var(--tw-ico) center / contain no-repeat;
}
.tw #host-contact a[href^="tel:"] {
  --tw-ico: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1 1 .4 1.9.7 2.8a2 2 0 0 1-.5 2.1L8 9.9a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.8.7a2 2 0 0 1 1.7 2z'/%3E%3C/svg%3E");
}
.tw #host-contact a[href^="mailto:"] {
  --tw-ico: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Crect x='3' y='5' width='18' height='14' rx='2'/%3E%3Cpath d='M3 7l9 6 9-6'/%3E%3C/svg%3E");
}
```

**Check:** the host block takes about 150px on a phone, not about 250px, and phone and e-mail sit side by side when they fit. `tests/test_guest_tap_targets.py` passes (the links stay at least 44px).

### TW2-16 · Desktop: the ticket gets a place to sit

**Guest sees (≥1020px):**
- A soft, very light coral radial wash behind the column.
- A faint dashed "route line" running down the left and right edges of the page, like the edge of a ticket stack.
- The column grows to 680px, and tickets lift slightly more.

Add to section 18 (or as section 18b):

```css
@media (min-width: 1020px) {
  .tw {
    background:
      radial-gradient(1200px 600px at 50% -10%, color-mix(in srgb, var(--brand) 10%, transparent), transparent 70%),
      repeating-linear-gradient(180deg, transparent 0 14px, color-mix(in srgb, var(--ink) 7%, transparent) 14px 22px) left 32px top 0 / 2px 100% no-repeat,
      repeating-linear-gradient(180deg, transparent 0 14px, color-mix(in srgb, var(--ink) 7%, transparent) 14px 22px) right 32px top 0 / 2px 100% no-repeat,
      var(--tw-page);
  }
  .tw .g-wrap,
  .tw .g-checkin-page { max-width: 680px; }
  .tw .tw-ticket,
  .tw [data-guest-step] { box-shadow: 0 40px 80px -48px rgba(20, 20, 18, 0.45); }
}
```

### TW2-17 · i18n keys

Add every key in §4 to **both** `STRINGS["en"]` and `STRINGS["cs"]` in `App/app/i18n.py`. Put them directly after the existing `"tw_document_title"` line in each language block. Run the parity tests:

```bash
.venv/bin/python -m pytest tests/test_host_i18n.py tests/test_guest_language.py tests/test_public_copy_i18n.py -q
```

Do this task **together with** the first task that uses a key. TW2-05 is the first; its commit adds all the keys at once.

### TW2-18 · Docs

1. Replace `docs/DESIGN.md` **completely** with the `DESIGN.md` delivered with this plan. It keeps every existing product rule (light mode, stack, logo, contact split, host message, late registration, guest e-mail, passport uploads, UbyPort timing, agents, consent banner) and adds three things:
   - the three-surface overview and the shared brand core;
   - the **Ticket Wallet** guest standard, which replaces the old "Arrival lane" picker section;
   - the **Host app: Effortless** standard (principles, click budgets, layout, components, WCAG 2.2 AA);
   - the **Public marketing site: locked** rule.
2. Several tests mention `DESIGN.md` only in their docstrings, and none of them read the file. Run the tests anyway.
3. Add this plan to `docs/plans/README.md`, in the same format as the other entries.

### TW2-19 · New test file

Create `App/tests/test_ticket_wallet_v2.py` with the content in §5. Run it; it must pass.

### TW2-20 · Final QA (no commit unless you fix something)

Run the local app with a seeded property. Use the demo seed, or create one by hand: a property with a PIN, a message from the host, a phone and an e-mail, and three stays with the first arriving today. Walk the whole flow at **375×812** and at **1280×800**, in **EN and CS**:

1. PIN: cells, paste, wrong PIN turns red.
2. Pick: three passes, each pill on one line, host note card.
3. Claim: stepper, short e-mail hint, the fold opens, Send is visible.
4. Check e-mail screen, then confirm.
5. Form: the tracker; the date boxes and read-back; country search (a Czech guest, then a Ukrainian guest); document tip; purpose chips and Other…; Home with the green copied card for guest 2; signature Sign here → Signed; the check step with its rows and the coral acknowledgement; Submit spinner.
6. Saved stamp, then Add a person, then guest 2, then done: two boarding passes and "Keep this page".
7. Keyboard only: Tab through everything; every focus ring is visible; the country list works with ↑↓ Enter Esc.
8. Turn on reduced motion in OS settings: nothing animates.
9. With JavaScript disabled, the whole flow still submits (plain inputs, v1 look).
10. Run `pytest` and confirm that only the 22 host-side baseline failures remain.

Make a screenshot of each screen at 375px and attach them to the PR.

---

## 4. New i18n keys (exact text)

| Key | EN | CS |
|---|---|---|
| `tw_email_short` | We send your private link here. No marketing. | Pošleme sem váš soukromý odkaz. Žádný marketing. |
| `tw_email_more` | What we use your e-mail for | K čemu váš e-mail použijeme |
| `tw_step_details` | Details | Údaje |
| `tw_step_document` | Document | Doklad |
| `tw_step_home` | Home | Bydliště |
| `tw_step_photo` | Photo | Foto |
| `tw_step_sign` | Sign | Podpis |
| `tw_step_check` | Check | Kontrola |
| `tw_dob_day` | Day | Den |
| `tw_dob_month` | Month | Měsíc |
| `tw_dob_year` | Year | Rok |
| `tw_country_search` | Start typing a country | Začněte psát zemi |
| `tw_country_none` | No country matches | Žádná země neodpovídá |
| `tw_purpose_other` | Other… | Jiný… |
| `tw_sign_here` | Sign here with your finger | Podepište se zde prstem |
| `tw_signed` | Signed | Podepsáno |
| `tw_done_keep` | Keep this page — it is your confirmation. | Tuto stránku si nechte — je to vaše potvrzení. |

---

## 5. `App/tests/test_ticket_wallet_v2.py`

```python
"""Ticket Wallet v2 (docs/plans/PLAN_TICKET_WALLET_V2.md): the skin's
contract with the templates, the enhancement script and the dictionary."""
import re
from pathlib import Path

from app import i18n

APP = Path(__file__).resolve().parents[1] / "app"
CSS = (APP / "static" / "guest-ticket.css").read_text(encoding="utf-8")
JS = (APP / "static" / "ticket.js").read_text(encoding="utf-8")
FORM = (APP / "templates" / "guest" / "form.html").read_text(encoding="utf-8")
CLAIM = (APP / "templates" / "guest" / "claim.html").read_text(encoding="utf-8")
BASE = (APP / "templates" / "guest" / "base.html").read_text(encoding="utf-8")

NEW_KEYS = [
    "tw_email_short", "tw_email_more", "tw_step_details", "tw_step_document",
    "tw_step_home", "tw_step_photo", "tw_step_sign", "tw_step_check",
    "tw_dob_day", "tw_dob_month", "tw_dob_year", "tw_country_search",
    "tw_country_none", "tw_purpose_other", "tw_sign_here", "tw_signed",
    "tw_done_keep",
]


def test_every_new_key_exists_in_both_languages():
    for key in NEW_KEYS:
        assert i18n.STRINGS["en"].get(key), f"en.{key}"
        assert i18n.STRINGS["cs"].get(key), f"cs.{key}"


def test_every_enhancement_is_registered_in_start():
    start = JS[JS.index("function start()"):]
    for name in ("initPinCells", "initDobCells", "initCountryCombos",
                 "initPurposeChips", "initTrackerLabels", "initSignState"):
        assert f"function {name}(" in JS, name
        assert f"{name}();" in start, f"{name} is defined but never called"


def test_the_rail_is_no_longer_hidden():
    assert ".tw .g-checkin-rail { display: none !important; }" not in CSS


def test_v2_sections_come_before_the_motion_section():
    """Section 17's reduced-motion rule must be last so it covers v2."""
    assert CSS.index("/* 18. App bar v2") < CSS.index("/* 17. Motion")


def test_every_form_step_has_a_short_label():
    # "data-guest-step-skip-when" must not count as a step of its own.
    steps = re.findall(r"data-guest-step(?=[\s>])", FORM)
    assert steps and len(steps) == FORM.count("data-tw-short=")


def test_the_real_controls_keep_their_names():
    for name in ('name="birth_date"', 'name="nationality"', 'name="res_country"',
                 'name="purpose"', 'name="signature"', 'id="sig-canvas"'):
        assert name in FORM, name


def test_the_full_email_text_is_still_on_the_claim_page():
    assert "t('claim_email_help')" in CLAIM
    assert "t('claim_cookie_help')" in CLAIM
    assert 'class="tw-more"' in CLAIM


def test_assets_are_cache_busted_past_v1():
    assert "guest-ticket.css?v=20260929a" not in BASE
    assert "ticket.js?v=20260929a" not in BASE


def test_no_dark_mode_sneaks_in():
    assert "prefers-color-scheme" not in CSS
```

---

## 6. Definition of done

- [ ] TW2-A, TW2-00 and TW2-02 to TW2-19 are committed, one commit each, and `pytest` shows only the 22 host-side baseline failures.
- [ ] At 375×812, every screen of the flow matches the prototype's structure: app bar, one ticket, the stub holding the only coral button.
- [ ] The flow works with JavaScript off.
- [ ] Keyboard and screen-reader paths work: labels, the combobox's `aria-activedescendant`, the tracker buttons' `aria-label`s.
- [ ] Reduced motion stops every animation.
- [ ] EN and CS screenshots are attached to the PR.
- [ ] `docs/DESIGN.md` is the new version, and `docs/plans/ticket-wallet/` is committed.
