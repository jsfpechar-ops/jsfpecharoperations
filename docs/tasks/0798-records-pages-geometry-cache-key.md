# 0798: Owner geometry rules on the four records pages, cache key, catalog, screenshots

Status: todo
Depends on: 0796, 0797 | Branch: claude/project-thread-v4nqi5 (main checkout, do NOT commit; the orchestrator commits)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Apply the owner's recurring geometry rules (brief 0775 §5b, owner shots `/mnt/project-files/ux-desktop-audit/josef-geometry-1102/`) and the owner's no-fine-print rule (§2 rule 6) on Odeslání (`/submissions`), Faktury (`/invoices`), Domovní kniha (`/housebook`) and Poplatek z pobytu (`/stay-fees`), then bump the cache key and the catalog, then take the screenshots.

## 2. Context (rules) (measure each with Playwright `getBoundingClientRect` at 390, 1024, 1280, 1440 on the rich-host fixture in `App/tests/v2_mockup.py`)

1. A help "?" toggle sits on the same line, right next to its title or label (`inline-flex`, `gap:var(--space-2)`), its top within 4 px of the title's top; never below it.
2. Every text node inside a `.card` is >= 16 px (`var(--space-4)`) from each card edge.
3. Text and a button beside or below it: gap >= 12 px (`var(--space-3)`); adjacent buttons: gap >= 12 px.
4. Row actions: sibling row buttons and the "···" menu button have equal height and centre y (diff <= 1 px).
5. Help labels are one word: "Otevřít" / "Open" (and the vi/uk equivalents), not "Otevřít nápovědu".
6. No descriptions or fine print on the page (owner 2026-11-02 13:04, Wolt has none): remove the one-line sub under the h1, step/section descriptions, hint and `ui-sub`/`small`/`muted` paragraphs. Text a host needs moves into the page's existing help "?" disclosure (`details.ui-how` body); text that only repeats a label or button is deleted (rule 9 of AGENTS.md). Keep: titles, labels, values, empty-state line, error messages, legally required text (grep `docs/UbyHost_workplan/04_legal_positions.md` if unsure and report it). Delete strings that become unused (cs/en/vi/uk).

## 3. Files

`App/app/templates/submissions.html`, `invoices.html`, `housebook.html`, `stay_fees.html`; `App/app/static/app2.css` (only the 0791, 0792, 0793, 0794 blocks); locale files only for rule 5 strings used by these pages (if the string is shared with other pages, change it anyway: the rule applies app-wide); `App/app/templates/base.html` (cache key); `App/tests/test_static_versions.py` via `--write`; `docs/design/catalog.json` (new classes from the 0791-0794 blocks, follow the existing entry format; `tests/test_design_lint.py` tells you what is missing).

## 4. Steps

1. Write one scratchpad Playwright script (`/tmp/claude-0/scratch-0798/measure.py`, not committed) that prints rule 1-4 violations per page and width. Run it; fix each violation with the smallest CSS change in that page's block; rerun until it prints none.
2. Rule 5: grep the four templates for the help label key; shorten the strings.
3. Cache key: in `base.html` bump `app2.css?v=` to `20261102-0798`; from `App/` run `.venv/bin/python tests/test_static_versions.py --write` if that is how the test updates (read its header first).
4. Catalog: add the missing classes; run the lint test.
5. Screenshots (rich-host fixture, full page): `docs/tasks/screenshots-0790/<page>-390.png` and `<page>-1280.png` for submissions, invoices, housebook, stay-fees (8 files, overwrite old ones). Look at each once.

## 5. Do not touch

Anything outside §3. No new dependency, colour or JS.

## 6. Commands (from `App/`, each `2>&1 | tail -30`)

1. `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -k "invoices or housebook or submissions or stay_fees" -q -rs --tb=short`
2. `.venv/bin/python -m pytest tests/test_static_versions.py tests/test_design_lint.py tests/test_design_ui_macros.py tests/test_host_i18n.py -q --tb=short`
3. From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`

## 7. Acceptance

- [ ] measure.py prints no violation on the four pages at 390/1024/1280/1440 (paste its final output, max 10 lines).
- [ ] Commands 1-3: 0 failed, 0 skipped.
- [ ] No `.sub`, `ui-sub`, hint or description paragraph left outside the help disclosure on the four pages (list what moved and what was deleted).
- [ ] 8 screenshots saved.

## 8. Stop and ask

Blocked if a fix fails twice, a file outside §3 needs a change, or 30 tool calls.

## 9. Report

Report `docs/tasks/0798-report.md`, 400 tokens at most. Do not commit or push.
