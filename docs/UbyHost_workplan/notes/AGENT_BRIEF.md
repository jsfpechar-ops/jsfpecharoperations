# Brief for implementation agents (read fully before starting)

You implement one or more work packages (WPs) of UbyHost (FastAPI, Starlette, Jinja2, SQLite; Czech accommodation police-reporting SaaS). Real, production-quality code that Cursor will later apply.

## Environment
- Use the `mcp__workspace__bash` tool for ALL shell and file work (load it with ToolSearch query "select:mcp__workspace__bash" if it is deferred). Write files with heredocs or python inside that shell. Do not use host file tools on the repo.
- Your worktree: `/tmp/wp/wpNN` (given in your task), branch `wpNN`, based on local commit `wpbase` (= PR 230 head 4fd05de + test cleanup). Work only there. Read-only: everything else. No remote git operations of any kind (nothing is sent to GitHub). Never touch other worktrees.
- Python with all deps: `/tmp/pr230/App/.venv/bin/python`. Run tests from `<worktree>/App`: `/tmp/pr230/App/.venv/bin/python -m pytest -q tests/test_foo.py`.
- Every bash call must finish within about 170 s. Never background processes. Run test subsets: the files you touched, their related tests, and your new tests. If you change something central (db.py, main.py, base templates, i18n), also run a broad subset in chunks, e.g. `ls tests/test_[a-c]*.py` etc., each chunk in its own call.
- Lint: `/tmp/pr230/App/.venv/bin/python -m ruff check app tests tools --select E9,F63,F7,F82,F401,F841` (skip if ruff is not installed, and say so).

## Spec
- Plan files (read the README and your WP sections): `/sessions/wizardly-laughing-bell/mnt/outputs/cursor_plan/00_README_for_cursor.md`, `01_before_golive.md`, `02_after_golive.md`, `03_when_triggered.md`, background `UbyHost_architecture_review.md` (section 12 = owner decisions, overrides older text).
- Also read the repo's `AGENTS.md`.
- The spec was written from reading the code; line numbers may be off. If an assumption in the spec is wrong, adapt minimally and document it. Do not invent a larger design.

## Code rules
- Match existing style and helpers. No new dependency unless the WP names it.
- Every user-visible string in EN and CS through the existing i18n modules (`host_i18n.py`, `i18n.py`, `guide_i18n.py`). Czech must be natural and correct, with diacritics.
- Permanent rules: no analytics or third-party script on app, guest (`/l/...`) or auth pages; the DB claim (`claim_sendable`) is the only double-filing guard; never call UbyPort or fetch a feed inside an open transaction; all SQL via `db.py` helpers, parameterised, no new triggers or SQLite-only syntax.
- No secrets, real personal data or operator identity anywhere. Placeholders only.
- Tests for every behaviour in the WP's test list.

## Commits and deliverables
- One commit per WP, in the order given in your task, message `WPNN: <title>`. Use `git -c user.name=local -c user.email=local@example.invalid commit`.
- For each WP commit, write its patch: `git -C <worktree> format-patch -1 <sha> --stdout > notes/WPNN-<slug>.patch`. If your WPs are stacked (later WP builds on earlier), say so in the notes.
- For each WP write notes `notes/WPNN-<slug>.md` with these headings: Summary; Files changed (one line each); Tests added; Test commands and results (exact counts); Deviations from the spec and why; What Cursor must verify or adapt when applying on the real main; Manual steps for the owner. Plain language, no em dashes, no filler.
- Your final reply to the orchestrator: at most 200 words: patch paths, test results, deviations, open issues, anything risky.

## Update (round 3)
- Base for round-3 WPs is local branch `golive` (= wpbase + series 0001..0012, commit ae9a430), not wpbase. Patch/notes output: write the patch with `git format-patch -1 <sha> --stdout > /sessions/wizardly-laughing-bell/mnt/outputs/cursor_plan/round3/WPNN-<slug>.patch` and notes to `/sessions/wizardly-laughing-bell/mnt/outputs/cursor_plan/round3/WPNN-<slug>.md`.
- Browser tests now work. Prefix every pytest or playwright command with `LD_LIBRARY_PATH=/tmp/libs/root/usr/lib/aarch64-linux-gnu`. Run the guest browser e2e with `UBYHOST_REQUIRE_BROWSER=1` and `tests/test_host_geometry.py` when you touch any template or CSS.
- For screenshots: start the app with the demo seed (find how tests or `run.sh` seed demo data) on a local port inside one bash call, drive it with Playwright (python), save PNGs under `/sessions/wizardly-laughing-bell/mnt/outputs/cursor_plan/round3/shots/` and look at them with the Read tool on the host path `/Users/j.pechar/Library/Application Support/Claude/local-agent-mode-sessions/1b3caea5-ed38-486d-9d1c-e36fdcd2b279/2ed445f9-d701-4fc6-bf46-f41bd72f277d/cf0a213b/outputs/cursor_plan/round3/shots/<file>.png`. Stop the server at the end of the same bash call.
- Product principle (owner): UbyHost is privacy first. Store only what the law or the feature strictly needs. No tracking cookies, no third-party trackers in the app.
