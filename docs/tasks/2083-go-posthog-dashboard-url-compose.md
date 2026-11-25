# 2083: Pass the optional dashboard URL to the Go slots

Status: review
Depends on: none | Base commit: f6be14e46b68677884e26533eef674b15cb89f6a | Branch: task/2083-go-posthog-dashboard-url-compose
Executor: Luna | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Pass the existing optional PostHog dashboard-link setting into the Go containers. Preserve the default and analytics behavior when the setting is absent.

## 2. Context

Go first. UbyPort filing correctness and privacy take priority. Use synthetic data and an isolated local PostgreSQL schema for tests. Review the named anchors against the approved base or its prerequisite tip.

- `App/app/config.py:529`

  ```text
  POSTHOG_APP_URL = os.environ.get("POSTHOG_APP_URL", "https://eu.posthog.com").strip().rstrip("/")
  ```
- `go/internal/web/billing/admin_page.go:131`

  ```text
  return or(trim(getenv("POSTHOG_APP_URL")), "https://eu.posthog.com")
  ```
- `deploy/lightsail/docker-compose.yml:229`

  ```text
  POSTHOG_ASSETS_HOST:
  ```

## 3. Files

| Path | Action | Purpose |
|---|---|---|
| `deploy/lightsail/docker-compose.yml` | edit | Forward the optional variable in the Go service block. |

The executor report and brief status follow section 9.

## 4. Steps

1. In the `ubyhost-go.environment` block insert `      POSTHOG_APP_URL:` immediately before `      POSTHOG_ASSETS_HOST:`. The second slot inherits that block. Do not add a default value or a project key.
2. Use the compose-config command in section 6 to look at those three keys only. Use a synthetic value with no real env file. Verify both Go slots show the supplied value and the diff is one line. Report it as optional because the audit did not establish a custom production value.

## 5. Do not touch

Keep billing links, privacy settings and the default `https://eu.posthog.com` behavior. Use config rendering only, with no containers or live service.

## 6. Commands

Run from the indicated directory with pipeline failure reporting on. Expect the listed cases to run and pass. Required database and browser cases must show zero skips.

```sh
POSTHOG_APP_URL=https://example.invalid docker compose --env-file /dev/null -f deploy/lightsail/docker-compose.yml --profile go config 2>&1 | rg '(ubyhost-go(-b)?:|POSTHOG_APP_URL:)' | tail -30
git diff --check 2>&1 | tail -30
```

Use fixture credentials and record only pass/fail, counts, and redacted diagnostics.

## 7. Acceptance

- [ ] Both rendered Go services receive the synthetic custom value.
- [ ] The one-line mapping adds no analytics, cookies or requests.

## 8. Stop and ask

Stop and report if an anchor diverges after listed prerequisites, a required test fails twice, a dependency or file outside section 3 is needed, or the executor limit is reached. Escalate any need for live credentials, a real provider, a deployed server, or a product decision.

## 9. Report

Write `docs/tasks/2083-report.md` with the changed paths, command results, counts, acceptance evidence and owner steps. Set the brief to `Status: review` after completing the checks. Use `Status: blocked` in the report if stopped.

## Risk list (for the reviewer)

`deploy/lightsail/docker-compose.yml`

## Owner steps

1. Apply this in the same release only if the optional custom link matters to your setup.
