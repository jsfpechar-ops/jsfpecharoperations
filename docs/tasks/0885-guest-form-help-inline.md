# 0885: Guest form: the purpose "?" sits on the step title line

Status: todo
Depends on: none (goes before 0344, which also bumps a key in guest/base.html) | Base commit: 83aea3e | Branch: task/0885-guest-help-inline
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

On each guest form step, the "Why we ask ..." help is today a grey card under the title, with a 26 px "?" that wraps to its own line (see `docs/tasks/screenshots-0838/person2-step1-390.png`). After this brief the help is a small round "?" (18 px ring, 44 px invisible tap target) right after the step title, on the same line; tapping it opens the explanation under the title line. Owner rule: help "?" inline right after the title or label, never below it; the panel opens below when tapped; at least 12 px between neighbours.

## 2. Context

Verified on 83aea3e (and prototyped in Chromium at 320, 390, 768 and 1280 px: "?" centre within 2 px of the title line centre, 13 px gap, panel opens 15 px under the title, full card width):

- `App/app/templates/guest/form.html` has four step-level help cards with the same shape: `identity` (lines 78-87), `address-stay` (198-203), `passport-photo` (245-250), `signature` (288-293). Each is `<details class="g-card g-why" data-purpose-help="...">` with a text `<summary class="g-why-summary">` placed under the `<h2>`.
- `App/app/static/guest.css` lines 991-1022 style `details.g-why` (the 26 px `::after` "?"). These rules stay: they still serve `guest-count` (form.html line 96, claim.html line 38) and the bottom "Why you are filling this in" card (`App/app/templates/guest/_why.html`, used by form, pick, claim). Those two are **out of scope**: the bottom card is a section of its own, its "?" is already on its line, and `tests/test_form_chrome.py` and `tests/test_guest_browser_e2e.py` (line 436) pin its shape.
- The new markup puts the `<h2>` and a `<details class="g-head-help">` inline inside a `<div class="g-step-head">`. A `<details>` cannot go inside an `<h2>`. There must be **no whitespace between `</h2>` and `<details`**: that is what keeps the "?" from wrapping away from the last word. Copy the replacement lines exactly.
- Copy: no new key, no i18n change. The visible label text becomes the summary's `aria-label` (same key, `*_purpose_help_label`), the visible text is only "?", the panel keeps its `*_purpose_help` key. `tests/test_guest_navigation.py` (line 1250) checks the label and body texts and the `data-purpose-help` markers are still in the page; they are.
- Without JavaScript it is a native `<details>`. `App/app/static/signature.js` line 535 focuses the first `input, select, textarea, button, summary` of a step; the help summary was first before and stays first. Do not touch it.
- Cache key: `guest.css` is referenced with `?v=` only in `App/app/templates/guest/base.html` line 14 among live templates (the `archive/` copy is ignored by `tests/test_static_versions.py`).
- Browser tests: `browser` fixture in `tests/test_guest_browser_e2e.py` skips when Chromium cannot start, unless `UBYHOST_REQUIRE_BROWSER=1`. If the launch fails with "Executable doesn't exist", add `UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium_headless_shell-1243/chrome-headless-shell-linux64/chrome-headless-shell` (check the folder name with `ls /opt/pw-browsers | tail -5`) to every browser command. Do not install anything.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/guest/form.html` | edit | 4 step titles get the inline "?" |
| `App/app/static/guest.css` | edit | New `.g-step-head` / `.g-head-help` / `.g-help-dot` block |
| `App/app/templates/guest/base.html` | edit | `guest.css` cache key |
| `App/tests/static_versions.json` | regenerate | by `tests/test_static_versions.py --write` |
| `App/tests/test_guest_browser_e2e.py` | edit | Same-line test at 320/390/768, screenshots |
| `docs/tasks/screenshots-0885/` | new | 3 PNGs |
| `docs/tasks/0885-report.md` | new | Report |

No other file may change.

## 4. Steps

All paths below are from the repo root; run commands from `App/`.

### Step 1. `form.html`, identity (step 1)

Anchor (`App/app/templates/guest/form.html`, lines 78-87, exact):
```html
    <h2>
      {{ t('your_details') }}
      {% if person_number and person_number > 1 %}
        <span class="g-chip">{{ t('person') }} {{ person_number }}</span>
      {% endif %}
    </h2>
    <details class="g-card g-why" data-purpose-help="identity">
      <summary class="g-why-summary">{{ t('identity_purpose_help_label') }}</summary>
      <p class="g-intro">{{ t('identity_purpose_help') }}</p>
    </details>
```
Replace with (the `<h2>` line is one line, ending in `<details ...>`):
```html
    <div class="g-step-head">
      <h2>{{ t('your_details') }}{% if person_number and person_number > 1 %} <span class="g-chip">{{ t('person') }} {{ person_number }}</span>{% endif %}</h2><details class="g-head-help" data-purpose-help="identity">
        <summary aria-label="{{ t('identity_purpose_help_label') }}"><span class="g-help-dot" aria-hidden="true">?</span></summary>
        <p class="g-intro">{{ t('identity_purpose_help') }}</p>
      </details>
    </div>
```
Check: `grep -c 'class="g-head-help"' app/templates/guest/form.html` prints `1`. Commit `0885 step 1`.

### Step 2. `form.html`, address-stay

Anchor (exact):
```html
    <h2>{{ t('residence_title') }}</h2>
    <p class="g-intro">{{ t('residence_help') }}</p>
    <details class="g-card g-why" data-purpose-help="address-stay">
      <summary class="g-why-summary">{{ t('address_purpose_help_label') }}</summary>
      <p class="g-intro">{{ t('address_purpose_help') }}</p>
    </details>
```
Replace with:
```html
    <div class="g-step-head">
      <h2>{{ t('residence_title') }}</h2><details class="g-head-help" data-purpose-help="address-stay">
        <summary aria-label="{{ t('address_purpose_help_label') }}"><span class="g-help-dot" aria-hidden="true">?</span></summary>
        <p class="g-intro">{{ t('address_purpose_help') }}</p>
      </details>
    </div>
    <p class="g-intro">{{ t('residence_help') }}</p>
```
Check: the grep of step 1 prints `2`. Commit `0885 step 2`.

### Step 3. `form.html`, passport-photo

Anchor (exact):
```html
    <h2>{{ t('passport_photo_title') }}</h2>
    <p class="g-intro">{{ t('passport_photo_help') }}</p>
    <details class="g-card g-why" data-purpose-help="passport-photo">
      <summary class="g-why-summary">{{ t('passport_photo_purpose_help_label') }}</summary>
      <p class="g-intro">{{ t('passport_photo_purpose_help') }}</p>
    </details>
```
Replace with:
```html
    <div class="g-step-head">
      <h2>{{ t('passport_photo_title') }}</h2><details class="g-head-help" data-purpose-help="passport-photo">
        <summary aria-label="{{ t('passport_photo_purpose_help_label') }}"><span class="g-help-dot" aria-hidden="true">?</span></summary>
        <p class="g-intro">{{ t('passport_photo_purpose_help') }}</p>
      </details>
    </div>
    <p class="g-intro">{{ t('passport_photo_help') }}</p>
```
Check: the grep prints `3`. Commit `0885 step 3`.

### Step 4. `form.html`, signature

Anchor (exact):
```html
    <h2>{{ t('signature') }}</h2>
    <p class="g-intro" id="sig-help">{{ t('signature_help') }}</p>
    <details class="g-card g-why" data-purpose-help="signature">
      <summary class="g-why-summary">{{ t('signature_purpose_help_label') }}</summary>
      <p class="g-intro">{{ t('signature_purpose_help') }}</p>
    </details>
```
Replace with:
```html
    <div class="g-step-head">
      <h2>{{ t('signature') }}</h2><details class="g-head-help" data-purpose-help="signature">
        <summary aria-label="{{ t('signature_purpose_help_label') }}"><span class="g-help-dot" aria-hidden="true">?</span></summary>
        <p class="g-intro">{{ t('signature_purpose_help') }}</p>
      </details>
    </div>
    <p class="g-intro" id="sig-help">{{ t('signature_help') }}</p>
```
Check: the grep prints `4`, and `grep -c 'class="g-card g-why" data-purpose-help' app/templates/guest/form.html` prints `0`. Commit `0885 step 4`.

### Step 5. `guest.css`

Anchor (`App/app/static/guest.css` line 1128, exact, one line):
```css
details.g-why.g-fold > summary.g-why-summary::after { display: none; }
```
Insert directly after that line (keep the anchor line):
```css

/* 0885: a step's purpose help is a small "?" at the end of the step title,
   never a card under it. Title and "?" share one line; the panel opens under
   that line. Native <details>, so it works without script. The summary is
   the 44 px tap target; only the 18 px ring is drawn. The template has no
   space between </h2> and <details>, so the "?" never wraps away alone. */
.g-step-head { margin: 0 0 12px; font-size: 21px; }
.g-step-head > h2 { display: inline; margin: 0; }
details.g-head-help { display: inline; }
details.g-head-help > summary {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  margin: -13px 0;
  vertical-align: middle;
  list-style: none;
  cursor: pointer;
  color: var(--g-muted);
}
details.g-head-help > summary::-webkit-details-marker { display: none; }
.g-help-dot {
  display: inline-grid;
  place-items: center;
  width: 18px;
  height: 18px;
  border: 1px solid var(--g-line);
  border-radius: 50%;
  font-size: 12px;
  font-weight: 700;
  line-height: 1;
}
details.g-head-help > .g-intro { margin: 10px 0 0; }
```
Check: `grep -c 'g-head-help' app/static/guest.css` prints `4`. Commit `0885 step 5`.

### Step 6. Cache key

In `App/app/templates/guest/base.html` line 14 replace `/static/guest.css?v=20261030-0429` with `/static/guest.css?v=20261102-0885`. Do not touch `templates/guest/archive/`. Then run `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -5` (it rewrites `tests/static_versions.json`). Commit both files: `0885 step 6`.

### Step 7. Test helpers in `tests/test_guest_browser_e2e.py`

7a. Find `grep -n '^PEOPLE = \[' tests/test_guest_browser_e2e.py` (one hit). Insert directly **before** that line:
```python
# 0885: the purpose "?" sits on the last line of its step title, small, with
# a 44 px tap target, 12 px or more from the title text.
HELP_BESIDE_TITLE_JS = """(marker) => {
  const help = document.querySelector(`[data-purpose-help="${marker}"]`);
  const lines = help.closest('.g-step-head').querySelector('h2').getClientRects();
  const line = lines[lines.length - 1];
  const tap = help.querySelector('summary').getBoundingClientRect();
  const dot = help.querySelector('.g-help-dot').getBoundingClientRect();
  return {title: (line.top + line.bottom) / 2, help: (dot.top + dot.bottom) / 2,
          gap: dot.left - line.right, dot: dot.width, tapW: tap.width, tapH: tap.height,
          lineBottom: line.bottom};
}"""

```
7b. Find `grep -n '^class Guest:' tests/test_guest_browser_e2e.py` (one hit). Insert directly **before** that line:
```python
SHOTS_0885 = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-0885"


def _shot_0885(page, name: str) -> None:
    """0885 evidence: person 2, step 1, only when asked to."""
    if os.environ.get("UBYHOST_0885_SHOTS") != "1":
        return
    SHOTS_0885.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SHOTS_0885 / name), full_page=True)


```
7c. Anchor (exact, inside `class Guest`):
```python
    def check_layout(self, where: str):
        for problem in self.page.evaluate(LAYOUT_JS):
            self.problems.append(f"{where}: {problem}")
```
Insert directly after it (one blank line between methods):
```python

    def check_help_beside_title(self, marker: str, widths=()):
        """0885: the "?" is on the title line, and opens its panel under it."""
        page = self.page
        for width in widths or (self.width,):
            if widths:
                page.set_viewport_size({"width": width, "height": 812})
            box = page.evaluate(HELP_BESIDE_TITLE_JS, marker)
            where = f"{marker} at {width}px"
            assert abs(box["title"] - box["help"]) <= 4, f"{where}: the ? is not on the title line {box}"
            assert box["gap"] >= 12, f"{where}: the ? is closer than 12px to the title {box}"
            assert 16 <= box["dot"] <= 20, f"{where}: the ? is not small {box}"
            assert box["tapW"] >= 44 and box["tapH"] >= 44, f"{where}: tap target under 44px {box}"
        if widths:
            page.set_viewport_size({"width": self.width, "height": 812})
        help_ = page.locator(f'[data-purpose-help="{marker}"]')
        help_.locator("summary").click()
        assert help_.evaluate("el => el.open")
        panel_top = help_.locator(".g-intro").evaluate("el => el.getBoundingClientRect().top")
        line_bottom = page.evaluate(HELP_BESIDE_TITLE_JS, marker)["lineBottom"]
        assert panel_top >= line_bottom, f"{marker}: the panel does not open under the title"
        help_.locator("summary").click()
        assert not help_.evaluate("el => el.open")
```
Commit `0885 step 7`.

### Step 8. Call the checks in `fill_form`

8a. Anchor (exact, in `fill_form`):
```python
        assert page.locator('[data-purpose-help="identity"]').is_visible()
```
Insert directly after it:
```python
        self.check_help_beside_title("identity", widths=(320, 390, 768))
        if number == 2 and self.lang == "en" and self.width in (390, 1280):
            _shot_0885(page, f"person2-step1-{self.width}.png")
            if self.width == 390:
                summary = page.locator('[data-purpose-help="identity"] summary')
                summary.click()
                _shot_0885(page, "person2-step1-open-390.png")
                summary.click()
```
8b. Anchor (exact):
```python
        assert page.locator('[data-purpose-help="address-stay"]').is_visible()
```
Insert directly after it: `        self.check_help_beside_title("address-stay")`
8c. Anchor (exact):
```python
        assert page.locator('[data-purpose-help="signature"]').is_visible()
```
Insert directly after it: `        self.check_help_beside_title("signature")`

Commit `0885 step 8`.

### Step 9. Run §6, take the screenshots, look at each once

Run commands 1 to 4. Open each PNG once: the "?" is a small ring right after "Person 2" on the title line; the open shot shows the text under the title. Commit the PNGs: `0885 step 9`.

## 5. Do not touch

`App/app/templates/guest/_why.html`, `claim.html`, `pick.html`, the `guest-count` help in form.html (line 96), the existing `details.g-why` / `.g-fold` / `.g-claim-help` CSS, `App/app/i18n.py`, `App/app/static/signature.js`, `templates/guest/archive/`, `tests/test_form_chrome.py`, `tests/test_guest_navigation.py`, routes, UbyPort code.

## 6. Commands

From `App/` (add `UBYHOST_BROWSER_EXECUTABLE=...` from §2 if Chromium will not start; allow up to 10 minutes for command 3):
1. `.venv/bin/python -m pytest tests/test_static_versions.py tests/test_wp07_cache_heartbeats.py tests/test_form_chrome.py tests/test_guest_navigation.py -q --tb=short -x 2>&1 | tail -30`
2. `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_guest_browser_e2e.py -q --tb=short -x -rs 2>&1 | tail -30`
3. Guest row: `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_guest_*.py tests/test_host_geometry.py -q --tb=short -x -rs 2>&1 | tail -30`
4. Screenshots: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_0885_SHOTS=1 .venv/bin/python -m pytest "tests/test_guest_browser_e2e.py::test_a_group_of_three_registers_everyone_on_one_phone[en-390]" "tests/test_guest_browser_e2e.py::test_a_group_of_three_registers_everyone_on_one_phone[en-1280]" -q --tb=short -x -rs 2>&1 | tail -30`, then `ls ../docs/tasks/screenshots-0885/ | tail -5` lists `person2-step1-390.png`, `person2-step1-open-390.png`, `person2-step1-1280.png`.
5. From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`

Expected: all pass, 0 skipped in 2, 3 and 4; lint clean.

## 7. Acceptance

- [ ] On all four steps the "?" sits right after the title on the same line (test: centre within 4 px at 320, 390 and 768 for identity; at the run width for address and signature).
- [ ] The ring is 16 to 20 px, the tap target at least 44 x 44 px, the gap to the title at least 12 px (same test).
- [ ] Tapping opens the explanation under the title line; tapping again closes it. No JavaScript needed (`<details>`).
- [ ] No grey help card under any step title; the bottom "Why you are filling this in" card is unchanged.
- [ ] `guest.css` key bumped, `static_versions.json` regenerated.
- [ ] Commands 1 to 5 pass, 0 skipped.
- [ ] Screenshots in `docs/tasks/screenshots-0885/`: person 2 step 1 at 390 (closed and open) and 1280.

## 8. Stop and ask

Stop, and write the report, if: an anchor is not found verbatim; a test fails twice; the same-line assertion fails (report the printed box, do not tune the numbers or the tolerance); Chromium cannot start even with `UBYHOST_BROWSER_EXECUTABLE`; any test is skipped; you reach 25 tool calls or about 50k tokens (report `blocked`, see executor.md); a file outside §3 needs a change; §5 would be touched; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0885-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with its last 5 lines, §7 ticked, deviations, questions, owner steps left, the three screenshot paths.

## Risk list (for the reviewer)

- `App/app/templates/guest/form.html`: no whitespace between `</h2>` and `<details`; the chip stays inside the `<h2>`, so on person 2+ the order is title, chip, "?".
- `App/app/static/guest.css`: inline `<details>` relies on the block panel breaking out of the line (prototyped in Chromium only; WebKit not run, see owner step 2).
- Left as they are, possible follow-up: the `guest-count` help under the party-size hint (form and claim page) still sits under its field.

## Owner steps

1. Open the three screenshots in `docs/tasks/screenshots-0885/` and check the "?" sits beside "Your details".
2. On your iPhone, after deploy to staging: open a guest link, tap the "?" next to "Your details"; the text opens under the title, tap again to close it.
3. Merge with `scripts/merge-pr-on-green.sh <pr>` when CI is green.
