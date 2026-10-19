# 0172: stale host.css in production, and the manifest loophole

Status: review
Depends on: 0171 | Branch: claude/project-thread-5hw8cf
Executor: Haiku 5.5 | Fits one session

## 1. Objective

Production's Stays page overlaps rows because browsers and the CDN still hold the OLD `host.css` (it contains `grid-template-columns: subgrid` rules that the repo removed in 0135). `base.html` still references `/static/host.css?v=20261014-0102d`, a key from before those edits, and `/static/*?v=` is served immutable for a year. `tests/test_static_versions.py` did not catch it because `--write` re-records a changed file hash under an unchanged key.

Do two things:
1. Give every versioned static file that changed after its key was set a new key.
2. Make `--write` refuse to hide such a change.

## 2. Context

A script (orchestrator, run on origin/main plus current work) found: `host.css` (key `20261014-0102d`, `base.html`) changed since its key; `app.css` has key `20261006a-0168` in `base.html` but still `20261006a` in `public_legal_base.html` and `auth_base.html`, and its content changed in 0168. Everything else is fine.

## 3. Files

`App/app/templates/base.html`, `App/app/templates/public_legal_base.html`, `App/app/templates/auth_base.html`, any other template that references `host.css` or `app.css` with `?v=` (find with `grep -rn "static/host.css?v=\|static/app.css?v=" App/app/templates`), `App/tests/static_versions.json`, `App/tests/test_static_versions.py`, `docs/tasks/0172-*`.

## 4. Steps

1. From the repo root, list every template reference: `grep -rn "static/host.css?v=\|static/app.css?v=" App/app/templates | cut -c1-160 | tail -30`. Change every `host.css` key to `20261019-0172`. Change every `app.css` key (all templates, including `base.html`, `public_legal_base.html`, `auth_base.html`, `cleaning_shared.html` if it references it) to the single value `20261006a-0172`. Do not touch other files' keys.
2. In `App/tests/test_static_versions.py`, change the `--write` path so it compares against the existing `static_versions.json` first: if a file's sha256 changed and its key is unchanged, print `refusing: <name> changed but still has ?v=<key>` and exit non-zero without writing. A new key or a new file is written as before. Add one test `test_write_refuses_a_changed_file_under_an_unchanged_key` that calls the new check function (factor it out of the CLI) with a fake recorded manifest and a fake current manifest and asserts the refusal list names the file.
3. From `App/`: `.venv/bin/python tests/test_static_versions.py --write && .venv/bin/python -m pytest tests/test_static_versions.py -q 2>&1 | tail -3`. Expected: passed (3 tests).
4. Also check no other template mixes keys for one file: `grep -rhn "static/host.css?v=\|static/app.css?v=" App/app/templates | grep -o "?v=[^\"]*" | sort | uniq -c | tail`. Expected: one `host.css` key and one `app.css` key.
5. From `App/`, run the browser tests that load the shell once: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium .venv/bin/python -m pytest tests/test_host_controls_browser.py -q -rs 2>&1 | tail -5` (foreground, timeout 600000), then from the repo root `git checkout -- docs/tasks/0102-evidence && git clean -fdq docs/tasks/0102-evidence`. Expected: passed, 0 skipped.
6. Commit: `git add App/app/templates App/tests docs/tasks/0172-* && git commit` with message "0172: new keys for host.css and app.css, --write refuses silent changes" and the two trailers given by the orchestrator.

## 5. Do not touch

CSS and JS content; hard rules 1, 3, 8.

## 6. Commands

As in each step.

## 7. Acceptance

- [ ] One key per file; manifest refreshed; the new refusal test passes.

## 8. Stop and ask

An anchor is missing, or a test fails twice.

## 9. Report

`docs/tasks/0172-report.md`, short; `Status: review`.
