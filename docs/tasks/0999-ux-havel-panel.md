# 0999: Havel panel restyle (pill topic grid, shorter greeting, soft sheet)

Status: todo
Depends on: none | Base commit: HEAD of main when you start | Branch: task/0999-ux-havel-panel
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Restyle the Havel (AI) support panel to the owner mockup `/mnt/project-files/ux-shots/havel-before-after.png` (right half): topic chips become rounded pills in a 2-column grid with an icon tile, the duplicated "Havel (AI)" label above the first bubble goes, the greeting and subtitle get shorter, the sheet gets 22px top corners and a soft shadow, and the close button is a 44px target with the design-system focus ring. Visual and copy only: no backend, no new route, no new JS.

## 2. Context

Rules: light mode only; copy rule 9 (no sentence the button already says); host-page UX gate (AGENTS rule 10); new/changed copy goes in `host_i18n.py` for `en` and `cs` (`host_vi_i18n.py` untouched, it falls back). Open the mockup once with Read. Read nothing else; grep, then ranges of 150 lines or fewer.

Facts already checked by the orchestrator:

- The panel is `App/app/templates/_havel_panel.html` (dialog `#havel-sheet`); the greeting and topic chips are in `_havel_topics.html`. The composer (textarea plus send button, in `.havel-input`) already exists and loads on first open, pinned below the scrolling `.havel-thread`. Do not add or change it.
- **Decision on "Other topic":** the free-text composer exists, but eight browser tests click `[data-havel-other]`. Keep the "Other topic" chip. With 5 topics it makes a 6th tile, so the 2-column grid ends even. Do not remove it.
- The `/havel` full page (`.havel-v2`) has its own chip rules at app2.css ~1270 (one column, max 420px). Scope every new chip rule to `.havel-dialog` so that page is unchanged.
- Tokens exist: `--coral-50`, `--coral-100`, `--accent-ink`, `--sand-50`, `--ink`, `--line`, `--shadow-2`, `--focus-ring-2` (tokens.css).

Anchors (each must be found verbatim, else STOP):

`App/app/templates/_havel_topics.html` line 9 to 12:
```
<div class="havel-msg havel-msg-havel havel-greeting" data-havel-greeting>
  <div class="havel-who"><span class="havel-avatar" aria-hidden="true">{{ icon('message-circle-question', 16) }}</span><span class="havel-name">{{ t('havel.name') }}</span></div>
  <div class="havel-bubble"><p>{{ t('havel.intro') }}</p></div>
</div>
```
`_havel_topics.html` (last chip block):
```
    {% for tp in havel_topics %}<a class="ui-chip havel-chip" href="/havel?topic={{ tp.id }}" data-havel-topic-link>{{ icon(tp.icon, 16) }}{{ t(tp.label) }}</a>{% endfor %}
    <a class="ui-chip havel-chip" href="/havel?ask=1" data-havel-topic-link data-havel-other>{{ icon('pencil', 16) }}{{ t('havel.topic.other') }}</a>
```
`_havel_panel.html`:
```
      <button class="ui-btn ui-btn-quiet ui-btn-icon" type="button" data-sheet-close aria-label="{{ t('havel.close') }}">{{ icon('x', 20) }}</button>
```
`App/app/host_i18n.py` en `        "havel.subtitle": "Support assistant",` and `        "havel.intro": "Hello, I'm Havel, UbyHost's AI assistant. Pick a topic below or ask me how something works. I explain step by step, and nothing changes until you confirm it.",`; cs `        "havel.subtitle": "Asistent podpory",` and the cs `havel.intro` line starting `        "havel.intro": "Dobrý den, jsem Havel`.
`App/app/static/app2.css` ends with some last rule; you append at the end. `App/app/templates/base.html` line 22: `<link rel="stylesheet" data-turbo-track="reload" href="/static/app2.css?v=...">` (match only up to `/static/app2.css?v=`).

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/templates/_havel_topics.html | edit | drop the sender label in the greeting; wrap chip icon in a tile |
| App/app/templates/_havel_panel.html | edit | class `havel-close` on the close button |
| App/app/static/app2.css | edit | append pill grid, tile, sheet, close rules |
| App/app/templates/base.html | edit | bump app2.css cache key |
| App/app/host_i18n.py | edit | `havel.subtitle` and `havel.intro`, en + cs |
| App/tests/test_havel_panel.py | edit | greeting text assertions (2 lines) |
| App/tests/test_havel_browser.py | edit | cs greeting assertion (1 line) |

No other file may change.

## 4. Steps

1. `_havel_topics.html`: delete the whole `<div class="havel-who">...</div>` line inside the `havel-greeting` block (line 10 above) only. Leave every other `havel-who` (answers keep their label). Check: `grep -c 'havel-who' App/app/templates/_havel_topics.html | tail -30` prints one fewer than before (was 4, now 3).
2. `_havel_topics.html`: in the two chip lines replace `{{ icon(tp.icon, 16) }}{{ t(tp.label) }}` with `<span class="havel-chip-ico" aria-hidden="true">{{ icon(tp.icon, 16) }}</span><span class="havel-chip-text">{{ t(tp.label) }}</span>` and `{{ icon('pencil', 16) }}{{ t('havel.topic.other') }}` with `<span class="havel-chip-ico" aria-hidden="true">{{ icon('pencil', 16) }}</span><span class="havel-chip-text">{{ t('havel.topic.other') }}</span>`. Do not touch the question chips (`havel.q.*`), back chips or the "Didn't help" chip.
3. `_havel_panel.html`: change `class="ui-btn ui-btn-quiet ui-btn-icon"` to `class="ui-btn ui-btn-quiet ui-btn-icon havel-close"` on the close button.
4. `host_i18n.py` en: `"havel.subtitle": "Ask how things work",` and `"havel.intro": "Hi, I'm Havel. Pick a topic or ask me anything. I never change anything without your OK.",`. cs: `"havel.subtitle": "Zeptejte se, jak věci fungují",` and `"havel.intro": "Dobrý den, jsem Havel. Vyberte téma nebo se zeptejte na cokoli. Nic nezměním bez vašeho souhlasu.",`. Keep the surrounding indentation and trailing commas. Check: `python3 -c "import ast,sys; ast.parse(open('App/app/host_i18n.py').read())" | tail -30` prints nothing.
5. Append to `app2.css`:
```
/* 0999: Havel panel restyle. Scoped to the dialog so the /havel page keeps its own list. */
body.v2 .havel-dialog .ui-sheet{border-radius:22px 22px 0 0;box-shadow:0 -6px 28px rgba(20,20,18,.14),0 2px 8px rgba(20,20,18,.06)}
@media (min-width:768px){body.v2 .havel-dialog .ui-sheet{border-radius:22px}}
body.v2 .havel-dialog .havel-topics .havel-chips{display:grid;grid-template-columns:1fr 1fr;gap:10px;width:100%}
body.v2 .havel-dialog .havel-topics .havel-chips>.havel-chip[data-havel-topic-link]:not([data-havel-ask-open]){display:flex;align-items:center;gap:10px;box-sizing:border-box;min-height:48px;padding:8px 12px;border-radius:14px;border:1px solid var(--line);background:var(--sand-50);color:var(--ink);font-weight:500;font-size:var(--size-15);line-height:1.25;text-align:left;white-space:normal;overflow-wrap:anywhere}
body.v2 .havel-dialog .havel-topics .havel-chips>.havel-chip:hover{background:var(--sand-100);color:var(--ink)}
body.v2 .havel-dialog .havel-chip-ico{flex:none;display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;border-radius:8px;background:var(--coral-100);color:var(--accent-ink)}
body.v2 .havel-dialog .havel-chip-text{min-width:0}
body.v2 .havel-dialog .havel-close{width:44px;height:44px;min-width:44px;min-height:44px;border-radius:50%;background:var(--sand-150);color:var(--ink)}
body.v2 .havel-dialog .havel-close:focus-visible{outline:0;box-shadow:var(--focus-ring-2)}
```
   Question chips (inside a topic, `.havel-chips` with no `.havel-chip-ico`) also become a 2-column grid by the third rule; if a question label wraps to 3 lines at 390 px, add `body.v2 .havel-dialog .havel-topics .havel-chips:not(:has(.havel-chip-ico)){grid-template-columns:1fr}` and say so in the report.
6. `base.html` line 22: set the value after `/static/app2.css?v=` to `20261107-0999`. Check: `grep -n "app2.css?v=" App/app/templates/base.html | tail -30`.
7. Tests: `grep -n "Hello, I'm Havel" App/tests/test_havel_panel.py | tail -30` (two assertions) and change `"Hello, I'm Havel"` to `"Hi, I'm Havel"`; in `test_havel_browser.py` change `"Dobrý den, jsem Havel"` (line ~213) to the same cs prefix, which is unchanged, so only edit it if it no longer matches. Then `grep -rn "Support assistant\|Asistent podpory" App/tests | tail -30`: if a test asserts the old subtitle, update it to the new one.

## 5. Do not touch

`havel.js`, `routes/`, `_havel_form.html`, `_havel_thread.html`, `_havel_card.html`, the `/havel` page rules (app2.css 1257-1272), `host_vi_i18n.py`, the composer, `app.css`. AGENTS rules: no new dependency, no new outbound request, no new personal-data field, no tracking cookies, light mode only.

## 6. Commands

From `App/`:
- `.venv/bin/python -m pytest tests/test_havel_panel.py tests/test_havel_topics.py tests/test_havel_page.py -q --tb=short -x 2>&1 | tail -30` expect all pass.
- `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_havel_browser.py tests/test_0386_havel_phone_look_browser.py tests/test_0391_havel_topics_first_browser.py tests/test_0395_havel_panel_layer_browser.py -q --tb=short -x 2>&1 | tail -30` expect pass, 0 skipped.
- UX gate: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -x 2>&1 | tail -30` green, 0 skipped. Then take 390 / 768 / 1280 screenshots of the open panel (dialog open, greeting visible) with the same Playwright helper `test_0395_havel_panel_layer_browser.py` uses, and read them.
- From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

## 7. Acceptance

- [ ] Greeting bubble has no "Havel (AI)" label above it; header shows the new subtitle; greeting reads the new en/cs text.
- [ ] Topic chips: 2-column grid, radius 14px, 1px neutral border, ink text (not red), icon in a 28px tinted tile, each at least 48px tall; "Other topic" chip still present.
- [ ] Sheet has 22px top corners and a soft shadow; close button is 44x44 with the `--focus-ring-2` ring on keyboard focus, no heavy red outline.
- [ ] Composer still pinned at the bottom, unchanged.
- [ ] The test-map rows pass with 0 skipped; layout lint zero findings; screenshots at 390/768/1280 read, and the PR body says per page "390: ...; 768: ...; 1280: ..." plus the design-system checklist ticked. One 390 px screenshot attached in the report.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (report as `blocked`);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a layout-lint finding appears that you cannot fix inside §3 (never silence it);
- you need push, merge, secrets, SSH or deploy (hand to the owner with the exact command).

## 9. Report

Write `docs/tasks/0999-report.md` (600 tokens at most) and set `Status: review`. It has: files changed (`git diff --stat`), each command with the last 5 lines, §7 ticked, deviations.
