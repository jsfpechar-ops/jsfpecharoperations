# 0995: Property page, Guest link card, calendar URLs, deep link, Leon row

Status: todo
Depends on: 0993, 0994 (all edit `app2.css` and `base.html`; run them first) | Base commit: 423d603 | Branch: task/0995-ux-property-page
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

On the property page: calm the Guest link card (heavy black focus box, "Copy link" jammed under the label), show the calendar feed URL in the Calendars table instead of a bare "URL ^" toggle, make `#sec-messages` land on the Guest experience section, and say what "Leon (AI) Off" is. All quick UX fixes.

## 2. Context

Rules: light mode only; copy rule 9; host-page UX gate (AGENTS rule 10). Keyboard focus must stay visible (design-system rule), so the black box is made lighter, never removed.

Anchors (each verbatim, else STOP):

`App/app/static/app2.css` lines 2595 to 2597 and 2608:
```
body.v2 .prop-strip div.sc.sc-link{display:block;padding:12px}
body.v2 .prop-strip .sc:hover{border-color:var(--ink3)}
body.v2 nav.prop-strip a.sc:focus,body.v2 nav.prop-strip a.sc:focus-visible,body.v2 nav.prop-strip a.sc-main:focus,body.v2 nav.prop-strip a.sc-main:focus-visible{outline:2px solid var(--ink)!important;outline-offset:2px;box-shadow:0 0 0 2px var(--ink)}
```
```
body.v2 .prop-strip .sc-actions{margin-top:8px;padding-left:20px}
```
`App/app/templates/_property_calendars.html` (inside the feed row, about lines 48 to 54):
```
            <td class="small feed-url" data-label="{{ t('apartment.form.feed.url') }}">
              <details class="feed-url-details">
                <summary>{{ t('apartment.form.feed.url') }}</summary>
                <span class="mono feed-url-value" id="feed-url-{{ feed.id }}">{{ feed.url }}</span>
              </details>
              {{ copy_button('feed-url-' ~ feed.id, t('common.copy_link')) }}
            </td>
```
`App/app/templates/_property_editor.html` line 88:
```
  {% if leon_card %}<div class="pv"><a class="r" href="{{ base_url }}/leon{% if leon_card != 'on' %}/setup{% endif %}" data-leon-card="{{ leon_card }}"><span>{{ t('leon_page.title') }}</span>{{ t('leon_page.card.' ~ leon_card) }}</a></div>{% endif %}
```
`App/app/host_i18n.py`: en `"leon_page.card.off": "Off",` (~10022), cs `"leon_page.card.off": "Vypnuto",` (~10132).
`App/app/static/app.js` (function `initPropSectionLinks`, about lines 2158 to 2168):
```
      if (node && node.tagName === "DETAILS" && node.classList.contains("prop-sec")) {
        node.open = true;
        if (target !== node && target.scrollIntoView) target.scrollIntoView();
      }
```
and later in the same function: `if (window.location.hash) openSection(window.location.hash);`. Cause of the wrong landing: on load the browser scrolls to the closed `#sec-messages` details first; other sections then open or lay out (Calendars is `open` by default for `?view=bookings` and the phone sections change height), so the final scroll position is wrong.
`App/app/templates/base.html` line 22 (`/static/app2.css?v=...`) and the `app.js?v=` script tag (about line 44).

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/static/app2.css | edit | focus ring, Copy link placement, feed URL cell |
| App/app/templates/_property_calendars.html | edit | URL always visible, truncated, copy button kept |
| App/app/templates/_property_editor.html | edit | Leon card hint |
| App/app/host_i18n.py | edit | 1 key, en and cs |
| App/app/static/app.js | edit | deep link scroll |
| App/app/templates/base.html | edit | bump `app2.css` and `app.js` keys |
| App/tests/test_host_property_deeplink_browser.py | create | one browser test for the deep link (copy fixtures from the nearest `tests/test_host_*_browser.py`) |

No other file may change.

## 4. Steps

1. `app2.css` line 2597: replace `outline:2px solid var(--ink)!important;outline-offset:2px;box-shadow:0 0 0 2px var(--ink)}` with `outline:2px solid var(--acc)!important;outline-offset:2px;border-radius:12px;box-shadow:none}` (selectors unchanged). Check `--acc` exists: `grep -c "\-\-acc:" App/app/static/tokens.css | tail -30`.
2. `app2.css` line 2595: replace with `body.v2 .prop-strip div.sc.sc-link{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:8px 12px;padding:12px}`; line 2608: replace with `body.v2 .prop-strip .sc-actions{margin:0;padding:0;flex:0 0 auto}`. Keep line 2609 (`.sc-actions .btn{min-height:44px}`) as is. The `.sc-main` link needs `flex:1 1 140px;min-width:0`: add that to the existing `.sc-main` rule on line 2605 by appending `;flex:1 1 140px`.
3. `_property_calendars.html`: replace the `<td class="small feed-url" ...>` block (anchor above) with:
```
            <td class="small feed-url" data-label="{{ t('apartment.form.feed.url') }}">
              <span class="mono feed-url-value" id="feed-url-{{ feed.id }}" title="{{ feed.url }}">{{ feed.url }}</span>
              {{ copy_button('feed-url-' ~ feed.id, t('common.copy_link')) }}
            </td>
```
Check `grep -rn "feed-url-details" App/app App/tests | tail -30`; if a test or stylesheet depends on it, update that reference too (stylesheet rule can be deleted, test expectation changed to `feed-url-value`).
4. `app2.css` append:
```
/* 0995: the feed URL is shown, clipped with an ellipsis; the full text stays in title and in the copy button */
body.v2 .feed-table .feed-url-value{display:block;max-width:240px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
@media (max-width:1023px){body.v2 .feed-table .feed-url-value{max-width:100%}}
```
5. `_property_editor.html` line 88: replace `<span>{{ t('leon_page.title') }}</span>` with `<span>{{ t('leon_page.title') }} <small>{{ t('leon_page.card.hint') }}</small></span>`. `host_i18n.py`: after the en `leon_page.card.off` line add `"leon_page.card.hint": "answers guest questions",` and after the cs one `"leon_page.card.hint": "odpovídá na dotazy hostů",`.
6. `app.js`: replace the anchor block with:
```
      if (node && node.tagName === "DETAILS" && node.classList.contains("prop-sec")) {
        node.open = true;
        var goTo = target && target !== node ? target : node;
        if (goTo.scrollIntoView) goTo.scrollIntoView();
      }
```
and replace `if (window.location.hash) openSection(window.location.hash);` with `if (window.location.hash) { openSection(window.location.hash); window.addEventListener("load", function () { openSection(window.location.hash); }); }`.
7. `base.html`: set `app2.css?v=` to `20261107-0995` and the `app.js?v=` value to `20261107-0995`.
8. Create `App/tests/test_host_property_deeplink_browser.py`: load `/apartments/<id>#sec-messages` (logged-in host fixture copied from the nearest browser test), assert `details#sec-messages` has `open`, and that its `summary` bounding box top is between 0 and the viewport height. Also assert the Copy link button and the "Guest link" label share one row at 1280 (same `y` within 60 px).

## 5. Do not touch

`host_vi_i18n.py`; the `.sc` strip for other cards; `leon_settings.html`. No new dependency.

## 6. Commands (from `App/`)

- `.venv/bin/python -m pytest tests/test_property_*.py tests/test_host_*.py tests/test_host_geometry.py tests/test_host_property_deeplink_browser.py -q --tb=short -x 2>&1 | tail -30` (browser 0 skipped, `UBYHOST_REQUIRE_BROWSER=1`).
- `.venv/bin/python -m pytest tests/test_icalsync.py tests/test_calendar_*.py tests/test_*_i18n.py tests/test_static_versions.py tests/test_no_em_dashes.py -q --tb=short -x 2>&1 | tail -30`
- UX gate: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_layout_lint_browser.py tests/test_design_guardrails_browser.py -q -x 2>&1 | tail -30`; read the property page 390/768/1280 screenshots.
- `python3 scripts/context_lint.py 2>&1 | tail -30` from the repo root.

## 7. Acceptance

- [ ] Guest link card: thin coral focus ring, "Copy link" on the same row as the label at 1280, wraps under it at 390.
- [ ] Calendars table shows each URL clipped with an ellipsis, plus the Copy link button; no "URL ^" toggle.
- [ ] `/apartments/<id>#sec-messages` opens and scrolls to Guest experience (new test green).
- [ ] The Leon row reads "Leon (AI) answers guest questions" and "Off".
- [ ] Layout lint zero findings, 0 skipped; 390 px screenshot in the report; per page "390: ...; 768: ...; 1280: ..." in the PR; design-system checklist ticked.

## 8. Stop and ask

An excerpt is not found; a test fails twice; 25 tool calls; a file outside section 3 needs a change; the deep-link test still fails after step 6 (report what you saw, do not guess).

## 9. Report

`docs/tasks/0995-report.md` (600 tokens at most), `Status: review`: files changed, last 5 lines of each command, section 7 ticked, deviations.
