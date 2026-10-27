# Page: Havel (AI) (`/havel`, templates `havel.html`, `_havel_thread.html`, `_havel_form.html`)

Master version: 2.0.0. Adds only; never overrides MASTER.md. Plan: docs/plans/havel-support-assistant.md section 17.

- Identity: nav `guide`, body_kind `detail`, title `havel.title`, page title `havel.name`, meta `havel.subtitle`, no back link.
- Header: no actions, no tabs; the composer's Send is the page's one primary.
- Body: one `ui-section`: the thread (`role="log"`) with host and Havel bubbles, compact secondary link buttons and a confirm card (0314) under a Havel bubble; the composer (textarea 600 chars, quiet New conversation when a conversation exists, primary Send, the AI note). Off or over a limit: the limit sentence replaces the textarea; the support exit stays.
- Empty state: the quick-help topics (0313); never a blank box.
- Tests: `test_havel_page.py`, `test_havel_browser.py` (0324), `test_design_guardrails_browser.py` (`ROUTES["havel"]`); screenshots 390 and 1280.

## Quick help (0313)
- Empty state: `_havel_topics.html`, five topics from `havel_topics.py` (page-aware order); `/havel?topic=<id>&q=<id>` are real pages; `X-Havel: 1` returns `_havel_fragment.html` (items + form) for the panel (0324).

## Panel (0324)
- `#havel-sheet` in `base.html` for signed-in hosts, not on `/havel` itself. Launchers: `_shell_sidebar.html` (above Help & guide), `_shell_topbar.html` (left of search), `_shell_tabbar.html` More row.
- `havel.js`: fetch submit with `X-Havel: 1`, writing state, Enter sends, counter from 500, focus to the answer, `window.UbyHavel.open(text)` for 0322.

## Confirm cards (0314)
- `_havel_card.html` under the bubble: title is a question, facts, "Change" `<details>` with the real inputs, Cancel (`quiet`) and the verb button (`primary`; `danger` only for the new PIN). Posts to `/reservations`, `/cleaning/events`, `/apartments/{id}/regenerate-pin`, `/sync`. The guest-link card is read-only (mono link, Copy, PIN 18/600, quiet link to Guest links).
- Checks in `havel_actions.prepare`: property owned, active, not archived; dates ISO, within a year back and two ahead, departure after arrival; guests 1–60; e-mail shape; times HH:MM, end after start; a connected calendar for sync; a link key for the guest link. A failed check adds `havel.card.not_prepared` + `havel.reason.*` to the bubble and a link to the form instead of a card.
