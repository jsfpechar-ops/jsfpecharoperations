# 0037: Validate the host design changes in Chromium

Status: review
Report: docs/tasks/0037-host-validation-report.md
Depends on: 0033 shared host filters | Base commit: 6545d094f41b717e33ca053cb74e022fa291f5d6 | Branch: task/host-design-staging
Executor: Luna validation sub-agent | feature branch task/host-design-staging

## 1. Objective

Configure the existing browser tests to run in this cloud environment against
its installed Chromium while keeping CI's Playwright browser as the default.
Refresh the host-only assertions in the 39-route smoke check and its CI staging
profile. Run the released browser and geometry coverage after page changes
settle, then report the actual integration results and screenshots.

## 2. Context

From `AGENTS.md`:

> Template, CSS or guest-page change: browser and geometry tests pass with 0 skipped, plus screenshots in the report.

> No new dependency without an owner decision line in [decisions](docs/context/decisions.md).

> From `App/`: `.venv/bin/python -m pytest tests -q` (never set `PYTHONPATH=App`). From the repo root: `python3 scripts/context_lint.py`.

The existing CI browser job installs `playwright==1.63.0` and runs with
`UBYHOST_REQUIRE_BROWSER=1`. It downloads Playwright's browser bundle, but the
workspace proxy blocked that download. Playwright's documented
`executable_path` option can use `/usr/bin/chromium` in this environment. The
bounded helper honors that path only when `UBYHOST_BROWSER_EXECUTABLE` is set;
otherwise normal CI behavior is unchanged.

The tests use the isolated temporary database and mock UbyPort in
`App/tests/conftest.py`. Browser tests start local servers, so they can require
sandbox escalation. Set fresh `XDG_CONFIG_HOME` and `XDG_CACHE_HOME` paths
under `/tmp` for Chromium.

The full-suite baseline also exposed environment leakage into four mock-only
test modules: injected proxy settings intercepted reserved `.example` loopback
fixtures, `www.google.com` DNS was unavailable to three mocked URL-validation
tests, and the synthetic AWS profile prevented the stubbed SES test from
constructing its client. Test-local isolation must leave global proxy, TLS,
DNS-pinning, redirect, and AWS identity behavior unchanged outside those
synthetic tests.

Run order is 0032 shared host feedback, then 0033 shared host filters, then
this final cross-page validation. The overlap with `test_host_geometry.py` is
intentional: this task changes only browser startup configuration after the
page-owner test work is complete.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/tests/browser_support.py` | add | Select an explicit Chromium executable only when configured |
| `App/tests/test_host_geometry.py` | update | Use the shared launch configuration |
| `App/tests/test_wp28_geometry.py` | update | Use the shared launch configuration |
| `App/tests/test_invoice_stay_browser.py` | update | Use the shared launch configuration |
| `App/tests/test_download_skeleton_browser.py` | update | Use the shared launch configuration |
| `App/tests/test_guest_browser_e2e.py` | update | Use the shared launch configuration |
| `App/tests/test_feed_dns_pinning.py` | update | Bypass configured proxies only for reserved `.example` loopback fixtures |
| `App/tests/test_feed_url_ssrf.py` | update | Resolve `www.google.com` to a public test address only in three mocked URL-validation tests |
| `App/tests/test_ical_skip_unchanged.py` | update | Bypass configured proxies only for its reserved `.example` loopback conditional-fetch fixture |
| `App/tests/test_lifecycle_mail.py` | update | Remove injected AWS profile only inside the stubbed SES test |
| `App/tools/smoke.py` | update | Scope fixtures to the synthetic admin and check translated dashboard plus guest-link form semantics |
| `.github/workflows/ci.yml` | update | Configure the smoke job only for staging no-login, mock UbyPort, and scratch data |
| `/workspace/.cloud-setup/ubyhost/install-ci-tools.sh` | add outside repo | Prepare CI system tools in `/tmp` without root or repo dependency changes |
| `docs/tasks/0037-host-design-validation.md` | add | Validation task and exact scope |
| `docs/tasks/0037-host-validation-report.md` | add/update | Baseline and final validation evidence |

No other file may change for this task. New page-owner tests remain owned by
their respective agents; do not modify these files during validation:
`App/tests/test_host_controls_browser.py`,
`App/tests/test_host_feedback_browser.py`,
`App/tests/test_host_filter_panels_browser.py`,
`App/tests/test_host_invoice_items_browser.py`,
`App/tests/test_host_property_controls_browser.py`, and
`App/tests/test_host_quiet_dashboard_browser.py`.

## 4. Steps

1. Prepare the CI system tools without root or repository changes, if they are
   not already available:

   ```sh
   /workspace/.cloud-setup/ubyhost/install-ci-tools.sh
   export PATH="/tmp/ubyhost-ci-tools/usr/bin:$PATH"
   ```

2. Install the same Playwright version as CI into `App/.venv` if it is missing:

   ```sh
   .venv/bin/python -m pip install playwright==1.63.0
   ```

3. Keep all assertions and `UBYHOST_REQUIRE_BROWSER` guards. Add the approved
   shared helper to each released existing browser test module and use
   `playwright.chromium.launch(**chromium_launch_kwargs())`.
4. Run smoke with a fresh synthetic staging database; repeat against the same
   database and after restarting only the app/mock processes. Record health,
   SOAP, ICS, route count, and each command's exit status.
5. After page edits settle and the root orchestrator releases the final check,
   run the required browser suite with system Chromium, saving full output to a
   distinct log file and recording the subprocess exit status.
6. Run the four environment-sensitive modules with the ambient proxy and AWS
   profile present, confirming isolation is limited to synthetic test cases.
7. Run the new page-owner browser tests under the same required-browser
   environment. Run requested CI-equivalent checks and context lint only after
   root releases the final integration pass.
8. Update the report with exact commands, exit codes, pass/fail/skip counts,
   screenshots, and remaining issues.

## 5. Do not touch

Do not modify page implementation files or tests owned by page agents. Do not
change browser assertions, disable required-browser mode, fabricate Playwright
cache metadata, add a repository dependency, or contact production UbyPort,
TTLock, or mail services. Smoke maintenance may replace only stale host-copy
checks with translated dashboard and guest-link form semantics; retain all
routes and guest-flow checks. Restrict CI's no-login profile to the `smoke`
job, mock UbyPort, and runner-temp data. Environment isolation in the four
listed test modules must be local to the corresponding reserved-host, mocked
DNS, or stubbed SES tests; preserve real proxy/TLS settings, DNS-pinning and
SSRF assertions, conditional request assertions, and mail-header assertions.
Do not run a broad Docker build or start a new Docker daemon without the root
orchestrator's instruction.

## 6. Commands

From `App/`, use a fresh, task-specific log file for each complete run:

```sh
mkdir -p /tmp/ubyhost-luna-xdg/config /tmp/ubyhost-luna-xdg/cache \
  /workspace/generated_images/host-design-application
if UBYHOST_BROWSER_EXECUTABLE=/usr/bin/chromium \
  UBYHOST_REQUIRE_BROWSER=1 \
  UBYHOST_SHOTS_DIR=/workspace/generated_images/host-design-application \
  XDG_CONFIG_HOME=/tmp/ubyhost-luna-xdg/config \
  XDG_CACHE_HOME=/tmp/ubyhost-luna-xdg/cache \
  .venv/bin/python -m pytest \
    tests/*browser*.py tests/test_host_geometry.py tests/test_wp28_geometry.py \
    -q -rs \
    > /tmp/ubyhost-luna-browser-final.log 2>&1; then
  test_status=0
else
  test_status=$?
fi
tail -n 40 /tmp/ubyhost-luna-browser-final.log
printf 'pytest exit status: %s\n' "$test_status"
exit "$test_status"
```

The task-specific log filename must be changed for each run; do not use shared
pytest cache contents as evidence. From the repository root, run
`python3 scripts/context_lint.py` after the task text is valid.

## 7. Acceptance

- [x] Actual Chromium launches through Playwright with
  `UBYHOST_REQUIRE_BROWSER=1`; required browser tests have zero skips.
- [x] Existing geometry, download navigation, invoice and guest-flow
  assertions remain enabled and pass.
- [x] New page-owner browser tests pass in the same required-browser run.
- [x] English and Czech pages fit desktop and mobile widths without clipped
  controls or sideways page scrolling.
- [x] Fictional-data screenshots are saved only in
  `/workspace/generated_images/host-design-application` and listed in the
  report.
- [x] Baseline failures and final settled results are recorded separately.
- [x] CI smoke runs all 39 host and guest routes with synthetic staging auth
  and scratch data; repeated and post-restart runs exit successfully.

## 8. Stop and ask

Stop if this validation needs a file outside §3, a new repository dependency,
an assertion change, a production service, or an action reserved to the owner.
Report the exact blocker and continue with unaffected checks.

## 9. Report

Update `docs/tasks/0037-host-validation-report.md` (1,500 tokens maximum) with changed files,
actual commands and exit codes, the last five log lines for each command,
§7 acceptance, deviations, questions, and owner steps left. Mark the task
`Status: review` after the final integration checks pass; preserve any CI-only
checks that could not run as explicit owner follow-ups.

## Risk list (for the reviewer)

Review the shared helper, five existing browser launch-site changes, and the
final test log/results. Verify the default CI path still launches the
Playwright-managed browser when no executable environment variable is set.

## Owner steps

1. Review the completed report and screenshots.
2. Handle any environment action that requires owner-level privileges.
