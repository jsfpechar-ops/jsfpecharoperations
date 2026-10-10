# 0037 report

Status: review

## 1. Runtime

- Installed `playwright==1.63.0` into `App/.venv`, matching the CI browser job.
- Installed system Chromium is `/usr/bin/chromium`, version `154.0.8037.57`.
- The official Playwright browser download failed at
  `https://cdn.playwright.dev/builds/cft/153.0.8010.12/linux64/chrome-linux64.zip`
  because the workspace proxy reset/refused the connection. No browser-cache
  metadata or binary was fabricated.
- Playwright's `executable_path` launch option successfully started the system
  Chromium in an escalated local runtime check.
- System installation with apt was unavailable because the workspace runs as
  UID 1000 without sudo. Following the environment's signed Debian repository
  setup, downloaded the trixie packages through `deb.debian.org` and extracted
  them to `/tmp/ubyhost-ci-tools`: age 1.2.1, sqlite3 3.46.1, ShellCheck
  0.10.0. Use `/tmp/ubyhost-ci-tools/usr/bin` on `PATH` for local CI checks.
- Reusable setup helper: `/workspace/.cloud-setup/ubyhost/install-ci-tools.sh`.
  Running it against the verified extracted tools succeeds without another
  package download; ShellCheck reports no findings in the helper.
- Docker CLI 28.4.0 is present, but `docker info` cannot access
  `/var/run/docker.sock` (`operation not permitted`). The Docker daemon was not
  started and socket permissions were not changed.
- `python3 scripts/context_lint.py` → `context lint: OK`. It reports existing
  orchestration warnings for shared open-brief files and the stale
  `docs/context/status.md` update count.

## 2.1 Onboarding smoke profile check

The first loopback run used the staging password profile, but `tools/smoke.py`
does not sign in; host requests followed `/login`. I then used the verified
synthetic profile: staging, `UBYHOST_STAGING_NO_LOGIN=1`, a bootstrapped
`smoke-admin` with `smoke@example.invalid`, mock UbyPort, scheduler off, and a
fresh `/tmp` database. The fixture now assigns its synthetic property and
operator to that admin, so actual host UI renders with the seeded records.

Before correcting assertions, this profile reached all 39 routes but failed
four stale copy checks: the Czech public brand copy at `/`, English public
copy at `/?lang=en`, and the PIN action text at `/guest-links?lang=en`. A
read-only archive of base commit
`6545d094f41b717e33ca053cb74e022fa291f5d6` reproduced exactly those four
failures. The replacement checks exercise dashboard title/section and seeded
property in English and Czech, plus the translated PIN action inside its
`regenerate-pin` form with the `/guest-links` return target.

Final real-server runs all passed: 39 pages, exit 0 for the initial run, a
repeat in the same server/database, and a repeat after restarting only the app
and mock. Both `/healthz` endpoints returned 200; app health had
`database_ok=true` and `data_dir_writable=true`. Mock SOAP availability was
true, maximum batch 32, and its sample calendar contained four events. Only
owned app/mock processes were stopped. Smoke logs:
`/tmp/ubyhost-onboarding-final-smoke.t1lZQS/logs/`; baseline logs:
`/tmp/ubyhost-smoke-baseline.aTlNRu/`. Targeted runtime Ruff check for
`tools/smoke.py` passed.

## 2. Baseline integration run

Command: see the required-browser command in
[`0037-host-design-validation.md`](0037-host-design-validation.md#4-commands).

Result: **25 passed, 3 failed, 0 skipped** across the five released existing
browser test modules. The run occurred while page edits were still in progress.

Known failure:

- `tests/test_host_geometry.py::test_dashboard_actions_share_height_and_gap`
  loaded `/` with HTTP 500. The dashboard handler referenced an undefined
  `needs_action` name at `App/app/routes/admin.py:299`, then the geometry test
  timed out waiting for `.dashboard-actions .action-group`. The dashboard
  owner has since corrected the reference to `queue['needs_action']` and is
  addressing a separate More-trigger issue found in their current browser run.

The other two failed node IDs are
`tests/test_host_geometry.py::test_the_month_filter_shares_its_page_edges`
and
`tests/test_download_skeleton_browser.py::test_every_host_download_button_keeps_the_page_visible`.
Their detailed failure output was truncated by the execution tool. They need
rechecking after the owning page changes settle. Do not count these baseline
failures as final validation.

The initial run's full traceback was truncated by the execution tool, so its
raw log was not retained. Future test runs will use a separate log file and
record the actual subprocess exit status.

## 2.1 Environment-sensitive unit tests

The full suite later reported 28 failures. Twelve environment-sensitive
failures were reproduced on a read-only archive of base commit
`6545d094f41b717e33ca053cb74e022fa291f5d6`: seven loopback feed tests and the
real conditional-fetch test sent reserved `.example` fixture requests through
the injected workspace proxy; three mocked URL-validation tests needed DNS for
`www.google.com`; the Stubber-only SES test inherited a synthetic
`AWS_PROFILE`. The baseline run was 12 failed / 26 passed, log
`/tmp/ubyhost-luna-baseline-env.khDakC/env-baseline.log`.

Added test-local isolation in the four listed modules only. Proxy bypass is
limited to reserved `.example` hosts; three URL-validation tests map only
`www.google.com` to public address `93.184.216.34`; the SES Stubber test
removes only `AWS_PROFILE` while constructing its fake-credential client. The
focused run with ambient proxy and AWS environment still present passed **63,
0 failed, 0 skipped** (exit 0), with one existing Starlette deprecation
warning. Log: `/tmp/ubyhost-luna-hermetic-20261010T154809.log`. Feed/mail
application code and security assertions were not changed.

## 2.2 Full-suite integration baseline

The required-browser coverage run completed with **2,990 passed, 28 failed,
0 skipped**, coverage 89.27% against an 86% threshold (exit 1), in 456.36 s.
Full log: `/tmp/ubyhost-luna-final-20261010T153221Z.tXVHR2/pytest-coverage.log`.
The 12 environment failures above are corrected by the focused changes; the
other 16 failures were assigned to dashboard, properties, filters, and invoice
owners. This is a pre-fix integration baseline, not the final combined result.
An attempted post-fix full run was stopped at 26% when the orchestrator asked
to wait for the dashboard type annotation; it exited 143 and is not a result
(`/tmp/ubyhost-luna-final-20261010T155428.log`).

## 2.3 Final released integration run

From `App/`, with `UBYHOST_BROWSER_EXECUTABLE=/usr/bin/chromium`,
`UBYHOST_REQUIRE_BROWSER=1`, fresh XDG paths, staging mock UbyPort and scheduler
disabled; smoke-only no-login/bootstrap variables were unset:

```sh
.venv/bin/python -m pytest tests -q --cov=app --cov-report=term-missing --cov-fail-under=86 -rs
```

Exit 0: **3,022 passed, 0 skipped**, 7 warnings in 453.61 s; coverage 89.53%
(86% required). Full log:
`/tmp/ubyhost-luna-final-20261010T155852-released.log`. Final output:
`TOTAL 15892 1664 90%`; `Required test coverage of 86% reached`; `3022 passed,
7 warnings in 453.61s`; exit status 0.

## 3. Evidence

Final fictional-data screenshots and cross-page gallery are in
`/workspace/generated_images/host-design-application/`:
[`index.html`](/workspace/generated_images/host-design-application/index.html)
contains the generated review gallery; invoice screenshots include
`picker-{360,390,1280}.png`, `form-{360,390,1280}.png`, and
`stay-{360,390,1280}.png`. All use fictional test data.

## 4. Final checks and owner follow-up

Final checks: whole-tree Ruff passed (exit 0,
`/tmp/ubyhost-luna-final-ruff-20261010.log`); ShellCheck passed (exit 0,
`/tmp/ubyhost-luna-final-shellcheck-20261010.log`); strict pip-audit found no
known vulnerabilities (exit 0, `/tmp/ubyhost-luna-pip-audit-20261010.log`);
pip check found no broken requirements (exit 0,
`/tmp/ubyhost-luna-final-pip-check-20261010.log`; pip disabled its non-writable
default cache). Runtime `requirements.lock` inventory found 49 pins, no missing
packages and no version mismatches. Tool versions: pip-audit 2.9.0, Ruff
0.16.9, mypy 2.3.1, Playwright 1.63.0 (inventory log
`/tmp/ubyhost-luna-final-runtime-inventory-20261010.log`).

Informational mypy remains nonzero with 175 diagnostics across 38 files
(`/tmp/ubyhost-luna-final-mypy-20261010.log`); the same command on base commit
reported the same 175 diagnostics and no semantic differences. Context lint
passed (exit 0, `/tmp/ubyhost-luna-final-context-lint-review.log`). Local
Docker/gitleaks checks could not run because this
environment cannot access `/var/run/docker.sock`; the daemon was not started.
CI triggers on pull requests, not feature-branch pushes, so a PR is required
before GitHub CI (including Docker/gitleaks) can provide green results.
