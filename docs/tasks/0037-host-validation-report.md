# 0037 report — Host validation and runtime readiness

Status: review

## Runtime readiness

`App/.venv` has Playwright 1.63.0; actual browser runs used system Chromium
`/usr/bin/chromium` 154.0.8037.57 via Playwright `executable_path`. The
official Playwright CDN download was blocked by the workspace proxy; no cache
metadata or browser binary was fabricated. Chromium tests required an
escalated local run because the standard sandbox blocks browser sockets.

The existing CI tools age 1.2.1, sqlite3 3.46.1 and ShellCheck 0.10.0 were
downloaded from signed Debian trixie packages and extracted to
`/tmp/ubyhost-ci-tools`; use that directory's `usr/bin` on `PATH`. The
repeatable helper is `/workspace/.cloud-setup/ubyhost/install-ci-tools.sh`.
Its ShellCheck check passed. Docker CLI 28.4.0 exists, but `docker info` was
blocked at `/var/run/docker.sock`; no daemon or permissions were changed.
Current runtime inventory and setup evidence are in the 0040 validation
report.

## Smoke and baseline findings

The first loopback smoke used a staging-password profile, but `tools/smoke.py`
does not sign in and landed on `/login`. The verified synthetic profile used
staging-only `UBYHOST_STAGING_NO_LOGIN=1`, a bootstrapped `smoke-admin`,
`smoke@example.invalid`, mock UbyPort, scheduler disabled and a fresh `/tmp`
database. Its property/operator fixtures belonged to that admin.

The first real-server pass exposed four stale smoke copy expectations: public
landing text in EN/CS and guest-link PIN copy. A read-only archive of base
commit `6545d094f41b717e33ca053cb74e022fa291f5d6` reproduced all four. Smoke
expectations now check signed-in dashboard/property content and the translated
PIN action/return target. Final smoke passed all 39 routes on initial run,
same-process repeat and app/mock restart. Both health endpoints returned 200;
database and writable data directory checks passed; mock SOAP was available,
batch size was 32, and its calendar returned four events. Only owned processes
were stopped. Logs: `/tmp/ubyhost-onboarding-final-smoke.t1lZQS/logs/`; base
reproduction: `/tmp/ubyhost-smoke-baseline.aTlNRu/`. Targeted Ruff passed.

While page edits were underway, the five released browser modules had 25
passed, 3 failed, 0 skipped. One failure was a dashboard HTTP 500 from an
undefined `needs_action` reference, subsequently fixed by its owner; the other
two were a month-filter edge assertion and download-skeleton browser check.
The initial trace was truncated, so this run is retained as a pre-fix baseline,
not final evidence.

The first full integration run had 2,990 passed, 28 failed, 0 skipped,
coverage 89.27% (86% required), exit 1, in 456.36s. Twelve environment-only
failures reproduced on the read-only base archive: reserved `.example` feed
requests and a conditional fetch used the injected proxy; three mocked URL
tests needed DNS for `www.google.com`; and a fake SES client inherited
`AWS_PROFILE`. Test-local isolation passed 63 tests, 0 failures/skips with
ambient proxy/AWS settings preserved. It bypasses proxy only for reserved
fixture hosts, maps DNS only in three mocked tests, and clears profile only for
the Stubber client. Application feed/mail logic and security assertions were
unchanged. The other 16 failures were assigned to page owners. An interrupted
follow-up run exited 143 at 26%; it is not a test result.

## Historical final suite and evidence

The released 0037 full suite completed with **3,022 passed, 0 skipped**, 7
warnings, coverage **89.53%** (86% threshold), exit 0, in 453.61s. Command from
`App/`:

```sh
.venv/bin/python -m pytest tests -q --cov=app --cov-report=term-missing --cov-fail-under=86 -rs
```

The run used system Chromium, `UBYHOST_REQUIRE_BROWSER=1`, fresh XDG paths,
mock UbyPort and disabled scheduler; smoke-only no-login/bootstrap variables
were unset. Log: `/tmp/ubyhost-luna-final-20261010T155852-released.log`.

Fictional-data screenshots and the review gallery are under
`/workspace/generated_images/host-design-application/` ([index](/workspace/generated_images/host-design-application/index.html)); the invoice set includes `picker-{360,390,1280}.png`, `form-{360,390,1280}.png` and `stay-{360,390,1280}.png`.

Final checks at that time: whole-tree Ruff, ShellCheck, strict pip-audit 2.9.0
(no known vulnerabilities), pip check and runtime lock inventory (49 pins, no
missing packages or version drift) passed. Informational mypy reported 175
diagnostics across 38 files, matching base exactly. Context lint passed with
existing orchestration warnings. Local Docker/gitleaks checks were unavailable
because the Docker socket was inaccessible; these remain CI checks. GitHub CI
status was not established by this local run.
