# 0281: Properties and Business cards keep a border on phone

Status: todo
Depends on: 0280 | Base commit: a6c532c | Branch: claude/project-thread-j2cl8a
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

On narrow widths the Properties list, the "Guest links and reporting timing" list and the Business & legal details list turn into cards with no outline, so one property runs into the next. Each card gets a visible 1 px border, rounded corners and a gap, like every other bordered control.

## 2. Context

Owner (2026-10-22, phone screenshot of Properties): "Properties page on phone, give it some borders." Standing rule: no borderless design; pills, rows, inputs keep visible borders.

`App/app/static/host.css` turns these tables into cards inside a container query on `.panel.list-cards` (container name `list-cards`):
```css
@container list-cards (max-width: 799.98px) {
  .host-workspace .lc-properties table,
  .host-workspace .lc-properties tbody { display: block; width: 100%; min-width: 0; }
```
and for businesses `@container list-cards (max-width: 949.98px) {` with `.host-workspace .lc-entities tr { ... border-bottom: 1px solid var(--line); }`. `host-design0123.css` reduces `.panel` to a top border only. Templates: `apartments.html` (two `.panel ... list-cards lc-properties` panels), `entities.html` (`.panel ... list-cards lc-entities`). The selected business row has class `row-selected` (pink background); it keeps its background.

`App/app/templates/base.html` line: `<link rel="stylesheet" href="/static/host2.css?v=20261022-0252d">`.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/static/host2.css | append | card borders |
| App/app/templates/base.html | edit | host2.css `?v=` key |
| App/tests/test_0281_card_borders_browser.py | new | geometry guard |

No other file may change.

## 4. Steps

1. Append to the end of `App/app/static/host2.css`:
```css
/* 0281: below their card switch point, Properties and Business rows are
   separate outlined cards (owner: no borderless look on phone). */
@container list-cards (max-width: 799.98px) {
  .host-workspace .lc-properties tbody { display: grid; gap: var(--space-3); }
  .host-workspace .lc-properties tr,
  .host-workspace .lc-properties tr:last-child { border: 1px solid var(--line-strong); border-radius: var(--radius-3); }
}
@container list-cards (max-width: 949.98px) {
  .host-workspace .lc-entities tbody { display: grid; gap: var(--space-3); }
  .host-workspace .lc-entities tr,
  .host-workspace .lc-entities tr:last-child { border: 1px solid var(--line-strong); border-radius: var(--radius-3); }
}
```
In `base.html` change `host2.css?v=20261022-0252d` to `host2.css?v=20261022-0281`. Commit `0281 step 1`.

2. Take shots from `App/`: `.venv/bin/python /mnt/project-files/design-reset/tools/shots.py --new-app $PWD --out /mnt/project-files/notify-sign/0281 --pages "/apartments,/entities,/entities?edit=1" --widths 390,820,1024,1280,2000 2>&1 | tail -3`. Expected `0 with problems`. Look at the three 390 shots once: every card has a full outline and a gap; the Edit and Invoice settings buttons sit below the business name, never on top of it. If the outline is cut, doubled or the panel adds a second frame around the cards, STOP and report.

3. Write `App/tests/test_0281_card_borders_browser.py` with Playwright, copying the server/login fixture pattern from `App/tests/test_0252_touch_sweep_browser.py` (read only its fixtures): at 390x844 on `/apartments` and `/entities`, every `.lc-properties tbody tr` / `.lc-entities tbody tr` has computed `border-top-width`, `border-left-width`, `border-right-width`, `border-bottom-width` all `1px`; on `/entities?edit=1`, inside each row the bounding boxes of the first-cell link `.row-primary-link` and of every `.ui-btn`/`.btn` in that row do not overlap. Commit `0281 step 3`.

## 5. Do not touch

`host.css`, `host-design0123.css`, templates other than `base.html`. Hard rules 6, 7.

## 6. Commands

From `App/`:
- `.venv/bin/python -m pytest tests/test_0281_card_borders_browser.py tests/test_static_versions.py tests/test_design_properties.py tests/test_design_guardrails_browser.py -q --tb=short -x -rs 2>&1 | tail -30` (0 skipped)

## 7. Acceptance

- [ ] Cards outlined at 390 and 820 on `/apartments` and `/entities`; desktop tables unchanged at 1280 and 2000.
- [ ] Buttons never cover the business name.
- [ ] Shots and `report.json` in `/mnt/project-files/notify-sign/0281/`.

## 8. Stop and ask

As in TEMPLATE §8.

## 9. Report

`docs/tasks/0281-report.md`, as in TEMPLATE §9.

## Risk list (for the reviewer)

`host2.css` tail.

## Owner steps

1. After deploy, open Properties on the phone: each property is a framed card.
