# 2044: Deploy retry safety: keep rollback copies after an unfinished deploy, loud message after the switch

Status: todo
Depends on: 2043 is independent (different lines of `deploy.sh`); either may go first | Base commit: current tip of the working branch | Branch: task/2044-deploy-retry-safety
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Tier: A (deploy script; exact diffs only; fresh review of the full diff)

> **One PR mode.** Commit each step as `2044 step k`. Never push to `main`, never merge, never deploy.

## 1. Objective

(1) A deploy that did not finish must not let the next run overwrite `caddy/Caddyfile.previous` and the `ubyhost:previous` / `ubyhost-go:previous` tags with the new release. (2) A failure after the site already runs the new release prints one clear instruction (manual rollback; no automatic rollback, owner decision).

## 2. Context

Hard rules: 4 no new dependency; 3 no secrets. Line numbers below are approximate; always find anchors with `grep -nF`.

In `deploy/lightsail/scripts/deploy.sh`:
- Around line 169: `# 0710: keep the running Caddyfile for rollback.` followed by
```
if [ -f caddy/Caddyfile.active ]; then
  cp caddy/Caddyfile.active caddy/Caddyfile.previous
fi
```
- Around lines 301 to 308:
```
if docker image inspect ubyhost:local >/dev/null 2>&1; then
  docker tag ubyhost:local ubyhost:previous
  echo "Kept the running image as ubyhost:previous for rollback."
fi
if docker image inspect ubyhost-go:local >/dev/null 2>&1; then
  docker tag ubyhost-go:local ubyhost-go:previous
  echo "Kept the running Go image as ubyhost-go:previous for rollback."
fi
```
- `echo "==> Removing retired compose services"` (around line 466) is the point after which the site already runs the new release.
- After that line these `exit 1` sites do NOT call `rollback`: after `echo "Legal acceptance backfill failed." >&2`; after `echo "Document-number backfill failed." >&2`; after `echo "Plaintext document numbers remain after the backfill." >&2`; after `echo "Live database integrity check failed: ${LIVE_OK}" >&2`; after `echo "${table} row count fell from ${BEFORE_COUNTS[${table}]} to ${after}." >&2`; after the `ERROR: public smoke failed` echo. There are exactly six sites.
- Success marker: `git rev-parse HEAD > .deployed-sha` (around line 603), preceded by `# 0710: this commit is now the rollback target.`
- `deploy/lightsail/.gitignore` already lists `.deployed-sha`.

Marker rule: file `.deploy-in-progress` holds the target SHA. Written at the Caddyfile step; removed right after `.deployed-sha` is written. If it exists when a run starts, the previous run did not finish, so the existing rollback copies are still the last good release and are kept.

## 3. Files

| Path | Action | What |
|---|---|---|
| `deploy/lightsail/scripts/deploy.sh` | edit | marker, guarded copies, `fail_after_switch` |
| `deploy/lightsail/.gitignore` | edit | add `.deploy-in-progress` |
| `App/tests/test_pg_go_slot_script.py` | edit | static tests |
| `docs/tasks/2044-report.md` | create | the report |

No other file may change.

## 4. Steps

1. **Marker and guarded Caddyfile copy.** Replace the block in §2 (Caddyfile) with:
```
# 2044: .deploy-in-progress exists only while a deploy has not finished. If it is
# already there, the last run failed part-way: keep the rollback copies it made.
KEEP_ROLLBACK_COPIES=0
if [ -f .deploy-in-progress ]; then
  KEEP_ROLLBACK_COPIES=1
  echo "NOTE: previous deploy did not finish; keeping existing rollback copies" >&2
fi
git rev-parse HEAD > .deploy-in-progress

# 0710: keep the running Caddyfile for rollback.
if [ "${KEEP_ROLLBACK_COPIES}" != "1" ] && [ -f caddy/Caddyfile.active ]; then
  cp caddy/Caddyfile.active caddy/Caddyfile.previous
fi
```
   Check: `bash -n deploy/lightsail/scripts/deploy.sh 2>&1 | tail -30`.

2. **Guard the image tags.** Replace the two `if docker image inspect ubyhost:local ...` and `if docker image inspect ubyhost-go:local ...` conditions (the block in §2) so each reads:
   - `if [ "${KEEP_ROLLBACK_COPIES}" != "1" ] && docker image inspect ubyhost:local >/dev/null 2>&1; then`
   - `if [ "${KEEP_ROLLBACK_COPIES}" != "1" ] && docker image inspect ubyhost-go:local >/dev/null 2>&1; then`
   Leave the bodies unchanged.

3. **Helper.** Insert the helper directly above the line `# 0710: the site as visitors reach it (Cloudflare, Caddy, app). About 60 s.`:
```
# 2044: after the Go slot switch the site runs the new release. No automatic
# rollback (owner decision); tell the operator exactly what to do.
fail_after_switch() {
  echo "$1" >&2
  echo "DEPLOY FAILED AFTER SWITCH: the site runs the new release. Do not re-run the workflow. To go back run: ROLLBACK_CONFIRM=yes ./scripts/rollback-prod.sh" >&2
  exit 1
}
```

4. **Use it at the six sites.** At each of the six sites in §2 (all after `Removing retired compose services`), replace the pair
   `echo "<reason text>" >&2` + `exit 1`
   by one call `fail_after_switch "<same reason text>"`. Examples: `fail_after_switch "Legal acceptance backfill failed."`; `fail_after_switch "Live database integrity check failed: ${LIVE_OK}"`; `fail_after_switch "${table} row count fell from ${BEFORE_COUNTS[${table}]} to ${after}."`; for the smoke site keep the full original `ERROR: public smoke failed (DNS/TLS/Cloudflare?). ...` text as the argument. Do not change any `exit 1` that sits before the removal line or that already calls `rollback`.
   Check: `grep -nF 'fail_after_switch' deploy/lightsail/scripts/deploy.sh | tail -30` shows 1 definition plus 6 calls.

5. **Clear the marker on success.** Replace
```
git rev-parse HEAD > .deployed-sha
```
   with
```
git rev-parse HEAD > .deployed-sha
rm -f .deploy-in-progress
```

6. **Gitignore.** Append the line `.deploy-in-progress` to `deploy/lightsail/.gitignore` (after `.deployed-sha`).

7. **Tests.** Append to `App/tests/test_pg_go_slot_script.py`:
```python
def test_deploy_keeps_rollback_copies_after_unfinished_deploy():
    text = DEPLOY.read_text(encoding="utf-8")
    assert "previous deploy did not finish; keeping existing rollback copies" in text
    marker = text.index("git rev-parse HEAD > .deploy-in-progress")
    assert marker < text.index("cp caddy/Caddyfile.active caddy/Caddyfile.previous")
    assert text.count('"${KEEP_ROLLBACK_COPIES}" != "1"') == 3
    assert text.index("git rev-parse HEAD > .deployed-sha\nrm -f .deploy-in-progress") > marker
    assert ".deploy-in-progress" in (ROOT / "deploy/lightsail/.gitignore").read_text(encoding="utf-8")


def test_deploy_failures_after_switch_print_the_rollback_command():
    text = DEPLOY.read_text(encoding="utf-8")
    assert "ROLLBACK_CONFIRM=yes ./scripts/rollback-prod.sh" in text
    assert "DEPLOY FAILED AFTER SWITCH: the site runs the new release. Do not re-run the workflow." in text
    tail = text.split('echo "==> Removing retired compose services"', 1)[1]
    assert tail.count("fail_after_switch ") == 6
```

## 5. Do not touch

`rollback()`, `rollback-schema-prep.sh` (that is brief 2043), the slot rotation block, `public_ok`, any exit that is before the removal line, `.deployed-sha` semantics, `App/` other than the one test file, `go/`.

## 6. Commands

- `shellcheck -S error deploy/lightsail/scripts/*.sh 2>&1 | tail -30` (no output = pass)
- `bash -n deploy/lightsail/scripts/deploy.sh 2>&1 | tail -30`
- `cd App && .venv/bin/python -m pytest tests/test_pg_go_slot_script.py tests/test_pg_backup_scripts.py -q --tb=short -x 2>&1 | tail -30` (expect all passed)
- `python3 scripts/context_lint.py 2>&1 | tail -30` (from repo root)

## 7. Acceptance

- [ ] The marker is written after the required-variable check, before the Caddyfile copy; removed only after `.deployed-sha`.
- [ ] Caddyfile copy and both `:previous` tags are skipped when the marker existed at start, and the NOTE is printed to stderr.
- [ ] `grep -cF 'fail_after_switch' deploy/lightsail/scripts/deploy.sh` prints 7.
- [ ] `.deploy-in-progress` is in `deploy/lightsail/.gitignore`.
- [ ] §6 commands pass.

## 8. Stop and ask

Any anchor not found verbatim; a site in §2 cannot be found or there are not exactly six; a test fails twice. Do not guess.

## 9. Report

Write `docs/tasks/2044-report.md` (600 tokens at most): files changed, each §6 command with its last 5 lines, §7 ticked, Deviations, Questions. Set `Status: review`, open one draft PR, do not merge. Owner steps: merge with `scripts/merge-pr-on-green.sh`. Note for the owner: the marker lives on the server; if a stuck marker should be cleared by hand, `rm deploy/lightsail/.deploy-in-progress`.
