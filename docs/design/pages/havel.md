# Page: Havel (AI) (`/havel`, templates `havel.html`, `_havel_thread.html`, `_havel_form.html`)

Master version: 2.0.0. Adds only; never overrides MASTER.md. Plan: docs/plans/havel-support-assistant.md section 17.

- Identity: nav `guide`, body_kind `detail`, title `havel.title`, page title `havel.name`, meta `havel.subtitle`, no back link.
- Header: no actions, no tabs; the composer's Send is the page's one primary.
- Body: one `ui-section`: the thread (`role="log"`) with host and Havel bubbles, compact secondary link buttons and a confirm card (0314) under a Havel bubble; the composer (textarea 600 chars, remaining-messages line, quiet New conversation when a conversation exists, primary Send, the AI note). Off or over a limit: the limit sentence replaces the textarea; the support exit stays.
- Empty state: the quick-help topics (0313); never a blank box.
- Tests: `test_havel_page.py`, `test_havel_browser.py` (0324), `test_design_guardrails_browser.py` (`ROUTES["havel"]`); screenshots 390 and 1280.
