# 1640 report

Status: review

## Files changed

- `deploy/lightsail/docker-compose.yml`: `ubyhost-go` volume `ubyhost-data:/data:ro` becomes `ubyhost-data:/data` (1 insertion, 1 deletion).
- `docs/LIGHTSAIL.md`: one sentence appended to the `ubyhost-go` line (line 56) on the writable mount.
- `docs/tasks/1640-report.md`: this report.

## Commands

- `python3 -c "...yaml.safe_load..."`: `['ubyhost-pgsock:/var/run/postgresql', 'ubyhost-data:/data']`
- `grep -c 'ubyhost-data:/data:ro' deploy/lightsail/docker-compose.yml`: `0`
- `python3 scripts/context_lint.py`: `context lint: OK` (WARN lines are pre-existing open-brief overlaps, none about the one new edit beyond docs/LIGHTSAIL.md, which is named by open briefs 1210 and 1640).

## Section 7 acceptance

- [x] `git diff --stat integration/ses-photo...HEAD`: only the three paths of §3 (the report included), compose 1 insertion, 1 deletion.
- [x] `ubyhost-data:/data:ro` count is 0.
- [x] YAML parse printed the two-item list.
- [x] `context_lint.py` reports no error.

## Tests

No tests run (config and doc change only; no test-map row applies). SKIP count: 0.

## Deviations

- Brief says set Status: review and open one PR; the caller said never open a PR. No PR opened, nothing pushed.
- Step 0 anchor found at line 290, not 286 (brief said "or near it").

## Questions

None.

## Owner steps left

Nothing changes in production until deploy. Then on the server: `docker compose --profile go up -d ubyhost-go`, and check with `docker compose exec ubyhost-go sh -c 'touch /data/.w && rm /data/.w && echo writable'`.
