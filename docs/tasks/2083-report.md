# 2083 report

Status: review

## Changed paths

- `deploy/lightsail/docker-compose.yml`: one line added, `POSTHOG_APP_URL:` in the `ubyhost-go` environment block (line 229), before `POSTHOG_ASSETS_HOST:`. No default value, no project key. The `ubyhost-go-b` slot inherits the block.

## Commands

1. `POSTHOG_APP_URL=https://example.invalid docker compose --env-file /dev/null -f deploy/lightsail/docker-compose.yml --profile go config | grep -E '(ubyhost-go(-b)?:|POSTHOG_APP_URL:)'`
   - `ubyhost-go:` shows `POSTHOG_APP_URL: https://example.invalid`
   - `ubyhost-go-b:` shows `POSTHOG_APP_URL: https://example.invalid`
   - Result: pass (2 of 2 Go slots receive the synthetic value)
2. `git diff --check`: pass (no output)

## Acceptance (section 7)

- [x] Both rendered Go services receive the synthetic custom value.
- [x] The mapping is one line and adds no analytics, cookies or requests.

## Deviations

- Used `grep -E` instead of `rg` for the filter in step 2. Same pattern, same result.
- Brief §9 asks for `Status: review`, so I changed `docs/tasks/2083-go-posthog-dashboard-url-compose.md` from `todo` to `review`.

## Owner steps

1. Apply this in the same release only if the optional custom link matters to your setup. The default `https://eu.posthog.com` behavior is unchanged when the variable is absent.
