# 0243: "What needs you": land on a visible link, and prove the card's geometry

Status: todo
Depends on: 0242 | Base commit: after 0242 | Branch: claude/project-thread-0io75h
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Two things. First, the "Send the guest link" button on a stay line lands on `#stay-link`, which is a hidden input, so the host sees the top of the stay page and no link. It must land on `#now`, the visible panel with the "Copy your own link" button. Second, the two old dashboard browser tests in `test_host_quiet_dashboard_browser.py` measured the removed tiles and table. They become strict geometry tests for the card in EN, CS and VI, at phone and wide widths, with the sidebar open and collapsed.

## 2. Context

- Card markup: `section.needs-you#needs-action`; lines `li.needs-you-item[data-tone="red|amber|grey"][data-needs-you="stay|alert|setup|paste"]`, stay lines carry `data-needs-you-stay`; each line has `.needs-you-copy` (bold subject plus one sentence) and `.needs-you-actions` (one `.ui-btn`, plus a dismiss icon button on dismissible alerts). The first 5 lines are in `.needs-you > .needs-you-list`; the rest are in `details.needs-you-more` ("Show N more"). CSS: `workflow.css` (card border, item border plus a 4 px left edge coloured by tone, 44 px buttons, side by side from 720 px).
- On `/` the alert stack (`.notification-stack`) is not rendered; the card holds the alerts.
- Rich fixture `dashboard_rich_host`: one overdue stay (red line), one ready stay on a manual property (amber, "Send the report", `#now`), one stay arriving today without a form, four later stays (no line), plus the property's setup and paste lines.
- Sidebar state comes from `localStorage['ubyhost-sidebar-collapsed']` (`app.js`).
- Browser tests: `export PLAYWRIGHT_BROWSERS_PATH=/tmp/claude-0/pw UBYHOST_REQUIRE_BROWSER=1`.
- Owner rules: visible borders, 44 px touch targets, WCAG 2.2 AA focus ring, no horizontal scroll, layouts checked in EN, CS and VI.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/needs_you.py` | edit | one anchor (step 1) |
| `App/tests/test_needs_you_0240.py` | edit | one line (step 1) |
| `App/tests/test_signed_in_chrome.py` | edit | one line (step 1) |
| `App/tests/test_host_quiet_dashboard_browser.py` | edit | replace the two tests (step 2) |
| `App/tests/test_design_dashboard.py` | edit | remove the unused `import re` left by 0241 (step 3) |
| `docs/tasks/0243-report.md` | create | report |

No other file may change.

## 4. Steps

### Step 1. Land on the visible link

Command:

```
cd App && sed -i 's/base + "#stay-link"/base + "#now"/' app/needs_you.py && sed -i 's@/reservations/3?return_to=/#stay-link@/reservations/3?return_to=/#now@' tests/test_needs_you_0240.py && sed -i 's@?return_to=/#stay-link"@?return_to=/#now"@' tests/test_signed_in_chrome.py && grep -rn '#stay-link' app/needs_you.py tests/test_needs_you_0240.py tests/test_signed_in_chrome.py | tail -5
```

→ no output. Then `.venv/bin/python -m pytest tests/test_alert_stack.py tests/test_needs_you_0240.py tests/test_signed_in_chrome.py -q --tb=short 2>&1 | tail -10` → pass. Commit `0243 step 1`.

### Step 2. Replace the two old tests

In `App/tests/test_host_quiet_dashboard_browser.py`, delete everything from the line `def test_dashboard_geometry_locales_and_screenshots(dashboard_host, base):` to the end of the file (keep the fixtures and `_launch` above it). Append exactly this:

```python
WIDTHS = (360, 390, 760, 1280, 1440, 2000)
LOCALES = ("en", "cs", "vi")
TONE_RANK = {"red": 0, "amber": 1, "grey": 2}

# 0243: every visible line of "What needs you", measured in one pass.
CARD_JS = """() => {
  const card = document.querySelector('.needs-you');
  if (!card) return null;
  const rect = el => { const b = el.getBoundingClientRect(); return {l: b.left, r: b.right, t: b.top, b: b.bottom, w: b.width, h: b.height}; };
  const style = el => getComputedStyle(el);
  const shown = el => el.offsetParent !== null;
  const items = [...card.querySelectorAll('.needs-you-item')].filter(shown).map(li => {
    const copy = li.querySelector('.needs-you-copy');
    const buttons = [...li.querySelectorAll('.needs-you-actions a, .needs-you-actions button')].filter(shown);
    return {
      kind: li.dataset.needsYou, tone: li.dataset.tone, text: copy.textContent.trim().slice(0, 80), box: rect(li),
      border: [style(li).borderTopStyle, parseFloat(style(li).borderTopWidth), parseFloat(style(li).borderLeftWidth), style(li).borderLeftColor],
      copy: rect(copy), copyOverflow: copy.scrollWidth > copy.clientWidth + 1,
      buttons: buttons.map(b => Object.assign(rect(b), {text: b.innerText.trim(), clipped: b.scrollWidth > b.clientWidth + 1})),
    };
  });
  return {card: rect(card), cardBorder: [style(card).borderTopStyle, parseFloat(style(card).borderTopWidth)], items,
          header: rect(document.querySelector('.ui-ph')),
          calendar: document.querySelector('#calendar') ? rect(document.querySelector('#calendar')) : null,
          scroll: document.documentElement.scrollWidth - innerWidth,
          stack: !!document.querySelector('.notification-stack')};
}"""


def _open(browser, base, cookie, locale, width, collapsed=False):
    context = browser.new_context(viewport={"width": width, "height": 1000})
    context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": base + "/"}])
    flag = "1" if collapsed else "0"
    context.add_init_script(f"try {{ localStorage.setItem('ubyhost-sidebar-collapsed', '{flag}'); }} catch (e) {{}}")
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(f"{base}/?lang={locale}")
    page.wait_for_load_state("networkidle")
    later = page.locator("#security-prompt [data-security-prompt-later]")
    if later.is_visible():
        later.click()
    page.evaluate("window.scrollTo(0, 0)")
    return context, page, errors


def _check_card(geo, width, label):
    """Borders, lane, touch targets, no overflow and no overlap for every visible line."""
    assert geo, f"{label}: no What needs you card"
    assert geo["scroll"] <= 1, (label, "horizontal scroll", geo["scroll"])
    assert not geo["stack"], f"{label}: the alert stack is shown next to the card"
    card = geo["card"]
    assert geo["cardBorder"][0] == "solid" and geo["cardBorder"][1] >= 1, (label, geo["cardBorder"])
    for edge in ("l", "r"):
        assert abs(card[edge] - geo["header"][edge]) <= 2, (label, "lane", card, geo["header"])
        if geo["calendar"]:
            assert abs(card[edge] - geo["calendar"][edge]) <= 2, (label, "calendar lane", card, geo["calendar"])
    if geo["calendar"]:
        assert geo["calendar"]["t"] >= card["b"] - 0.5, (label, "card overlaps calendar")
    tone_colours = {}
    for item in geo["items"]:
        where = (label, item["kind"], item["text"])
        box, copy = item["box"], item["copy"]
        assert box["l"] >= card["l"] - 0.5 and box["r"] <= card["r"] + 0.5, where
        assert item["border"][0] == "solid" and item["border"][1] >= 1, where + (item["border"],)
        assert item["border"][2] >= 3.5, where + (item["border"],)
        tone_colours.setdefault(item["tone"], set()).add(item["border"][3])
        assert not item["copyOverflow"], where
        assert copy["l"] >= box["l"] - 0.5 and copy["r"] <= box["r"] + 0.5, where
        assert 1 <= len(item["buttons"]) <= 2, where + (item["buttons"],)
        for button in item["buttons"]:
            assert button["h"] >= 43.5, where + (button,)
            assert button["w"] >= (43.5 if width <= 767 else 39.5), where + (button,)
            assert not button["clipped"], where + (button,)
            assert button["l"] >= box["l"] - 0.5 and button["r"] <= box["r"] + 0.5, where + (button,)
            assert button["t"] >= box["t"] - 0.5 and button["b"] <= box["b"] + 0.5, where + (button,)
            overlap_x = min(button["r"], copy["r"]) - max(button["l"], copy["l"])
            overlap_y = min(button["b"], copy["b"]) - max(button["t"], copy["t"])
            assert overlap_x <= 0.5 or overlap_y <= 0.5, where + ("button overlaps text", button, copy)
    for tone, colours in tone_colours.items():
        assert len(colours) == 1, (label, tone, colours)
    if "red" in tone_colours and "amber" in tone_colours:
        assert tone_colours["red"] != tone_colours["amber"], (label, tone_colours)


def _check_focus(page, label):
    page.keyboard.press("Tab")
    button = page.locator(".needs-you > .needs-you-list .needs-you-actions .ui-btn").first
    button.focus()
    ring = button.evaluate("el => [getComputedStyle(el).outlineStyle, parseFloat(getComputedStyle(el).outlineWidth)]")
    assert ring[0] != "none" and ring[1] >= 2, (label, ring)


def test_dashboard_single_stay_needs_you_card(dashboard_host, base):
    shots = os.environ.get("UBYHOST_SHOTS_DIR")
    cookie = dashboard_host["client"].cookies.get(auth.SESSION_COOKIE)
    assert cookie
    stay_id = dashboard_host["reservation"]
    with sync_api.sync_playwright() as playwright:
        browser = _launch(playwright)
        for locale in LOCALES:
            for width in (360, 390, 1280):
                label = f"single/{locale}/{width}"
                context, page, errors = _open(browser, base, cookie, locale, width)
                assert "has-js" in (page.locator("html").get_attribute("class") or "")
                assert not errors, (label, errors)
                assert page.locator("[data-calendar]").count() == 1
                assert page.locator(".dashboard-stats, .dashboard-row, .ui-banner-attention").count() == 0, label
                line = page.locator(f'.needs-you-item[data-needs-you-stay="{stay_id}"]')
                assert line.count() == 1, label
                assert line.get_attribute("data-tone") == "amber", label
                link = line.locator(".needs-you-actions .ui-btn")
                assert link.count() == 1, label
                assert link.get_attribute("href") == f"/reservations/{stay_id}?return_to=/#now", label
                _check_card(page.evaluate(CARD_JS), width, label)
                _check_focus(page, label)
                if shots:
                    os.makedirs(shots, exist_ok=True)
                    page.mouse.click(1, 1)
                    page.evaluate("window.scrollTo(0, 0)")
                    page.screenshot(path=os.path.join(shots, f"dashboard-single-{locale}-{width}.png"), full_page=True)
                if locale == "en" and width == 390:
                    with page.expect_navigation():
                        link.click()
                    assert page.url.endswith(f"/reservations/{stay_id}?return_to=/#now")
                    assert page.locator("#now").is_visible()
                    assert page.evaluate("document.querySelector('#now').getBoundingClientRect().top") < 1000
                context.close()
        browser.close()


def test_dashboard_rich_needs_you_order_cap_and_geometry(dashboard_rich_host, base):
    shots = os.environ.get("UBYHOST_SHOTS_DIR")
    cookie = dashboard_rich_host["client"].cookies.get(auth.SESSION_COOKIE)
    assert cookie
    overdue, ready = dashboard_rich_host["overdue"], dashboard_rich_host["ready"]
    with sync_api.sync_playwright() as playwright:
        browser = _launch(playwright)
        for locale in LOCALES:
            for width in WIDTHS:
                for collapsed in ((False, True) if width >= 1280 else (False,)):
                    label = f"rich/{locale}/{width}/{'collapsed' if collapsed else 'open'}"
                    context, page, errors = _open(browser, base, cookie, locale, width, collapsed)
                    assert not errors, (label, errors)

                    # Order: red first, then amber, then grey, across every line (shown or behind "Show more").
                    tones = page.locator(".needs-you-item").evaluate_all("nodes => nodes.map(node => node.dataset.tone)")
                    assert tones, label
                    ranks = [TONE_RANK[tone] for tone in tones]
                    assert ranks == sorted(ranks), (label, tones)
                    first = page.locator(".needs-you > .needs-you-list > .needs-you-item").first
                    assert first.get_attribute("data-needs-you-stay") == str(overdue), label
                    assert first.get_attribute("data-tone") == "red", label
                    ready_line = page.locator(f'.needs-you-item[data-needs-you-stay="{ready}"]')
                    assert ready_line.count() == 1 and ready_line.get_attribute("data-tone") == "amber", label
                    assert ready_line.locator(".ui-btn").get_attribute("href") == f"/reservations/{ready}?return_to=/#now"
                    for later in dashboard_rich_host["incomplete"]:
                        assert page.locator(f'.needs-you-item[data-needs-you-stay="{later}"]').count() == 0, label

                    # At most five lines open; the rest behind one "Show N more".
                    shown = page.locator(".needs-you > .needs-you-list > .needs-you-item").count()
                    total = len(tones)
                    assert shown == min(total, 5), (label, shown, total)
                    more = page.locator(".needs-you-more:not([data-paste-check]) > summary")
                    assert more.count() == (1 if total > 5 else 0), label
                    if total > 5:
                        assert str(total - 5) in more.inner_text(), (label, more.inner_text())
                    if "paste" in page.locator(".needs-you-item").evaluate_all("nodes => nodes.map(node => node.dataset.needsYou)"):
                        assert page.locator(".needs-you-more[data-paste-check] > summary").is_visible(), label

                    # Header: one primary action; below 1024 px the rest sit in the overflow menu.
                    header_buttons = page.locator(".ui-ph-acts .ui-btn:not(.ui-ph-menu)")
                    visible_buttons = [button for button in header_buttons.all() if button.is_visible()]
                    if width < 1024:
                        assert len(visible_buttons) == 1, label
                        assert page.locator(".ui-ph-menu").is_visible(), label
                    header_boxes = [button.bounding_box() for button in visible_buttons]
                    assert all(abs(box["height"] - (44 if width <= 767 else 40)) <= 1 for box in header_boxes), label

                    _check_card(page.evaluate(CARD_JS), width, label)
                    _check_focus(page, label)
                    if shots:
                        os.makedirs(shots, exist_ok=True)
                        page.mouse.click(1, 1)
                        page.evaluate("window.scrollTo(0, 0)")
                        state = "collapsed" if collapsed else "open"
                        page.screenshot(path=os.path.join(shots, f"dashboard-{locale}-{width}-{state}.png"), full_page=True)
                    if total > 5:
                        more.click()
                        _check_card(page.evaluate(CARD_JS), width, label + "/more")
                        hidden_lines = page.locator(".needs-you-more .needs-you-item")
                        assert all(line.is_visible() for line in hidden_lines.all()), label
                    context.close()
        browser.close()
```

Command: `cd App && .venv/bin/ruff check tests/test_host_quiet_dashboard_browser.py --select E9,F63,F7,F82,F401,F841 2>&1 | tail -10`. If an import at the top of the file is now unused (F401), remove only that name from its import line. Then run §6 command 1. Commit `0243 step 2`.

If a geometry assertion fails, do not loosen it. Save a screenshot of the failing case with `UBYHOST_SHOTS_DIR=/mnt/project-files/foolproof-round2/0243-fail`, put the failing assertion message and the screenshot path in the report, and stop.

### Step 3. Unused import

0241 left `import re` unused in `App/tests/test_design_dashboard.py` (CI runs ruff F401). Delete the line `import re` there. Command: `cd App && .venv/bin/ruff check tests --select E9,F63,F7,F82,F401,F841 2>&1 | tail -5` → `All checks passed!`. Commit `0243 step 3`.

## 5. Do not touch

Everything outside §3. No CSS or template change: a geometry failure is a finding for the reviewer.

## 6. Commands

From `App/` with `export PLAYWRIGHT_BROWSERS_PATH=/tmp/claude-0/pw UBYHOST_REQUIRE_BROWSER=1`:

1. `.venv/bin/python -m pytest tests/test_alert_stack.py tests/test_host_quiet_dashboard_browser.py -q --tb=short -x 2>&1 | tail -20` → pass, 0 skipped.
2. `UBYHOST_SHOTS_DIR=/mnt/project-files/foolproof-round2/dashboard .venv/bin/python -m pytest tests/test_alert_stack.py tests/test_host_quiet_dashboard_browser.py -q --tb=line 2>&1 | tail -5`, then `ls /mnt/project-files/foolproof-round2/dashboard/ | wc -l` (expect 9 single plus 27 rich screenshots, 36 in all).
3. `.venv/bin/python -m pytest tests/test_alert_stack.py tests/test_host_list_layouts_browser.py -q --tb=short 2>&1 | tail -5` (it imports these fixtures).

## 7. Acceptance

- [ ] Step 1 tests pass.
- [ ] §6 commands 1 and 3 pass with 0 skipped; command 2 wrote 36 screenshots.

## 8. Stop and ask

Stop, and write the report, if: an anchor is not found; a test fails twice; you reach 25 tool calls; a file outside §3 needs a change; a step is unclear.

## 9. Report

Write `docs/tasks/0243-report.md` (600 tokens at most) with the last lines of each command, and set `Status: review`. Do not push or open a PR.

## Risk list (for the reviewer)

`App/app/needs_you.py` (one anchor). The new geometry tests decide what "right" means for the card.

## Owner steps

None.
