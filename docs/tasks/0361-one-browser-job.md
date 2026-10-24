# 0361: One sharded browser job that runs every browser test

Status: todo
Depends on: none (0360 runs in parallel; this PR goes green only after 0360 merges) | Base commit: 5439abe | Branch: task/0361-one-browser-job
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

About 31 `App/tests/*_browser.py` files run in no CI job: the `test` job has no Playwright, so they `importorskip` silently. Replace `guest-browser`, `calendar-review`, `door-code-access-review` and the path-filtered side workflows with one always-on `browser` job, split in 4 parallel shards, that collects every browser file by pattern, so a new browser test can never be forgotten again.

## 2. Context

- Production deploy refuses unless these check names are green, in `.github/workflows/deploy-lightsail.yml`: `need=["test","smoke","guest-browser","shellcheck","docker","secrets"]`. `guest-browser` becomes `browser` (the aggregator job below).
- The browser files today are listed by hand in the `guest-browser` job of `.github/workflows/ci.yml`. `calendar-review` and `door-code-access-review` re-run files that `test` or `guest-browser` already run; their only unique coverage is `tests/test_door_code_window_browser.py` (needs WebKit).
- `mobile-more.yml` runs `tests/test_design_shell_browser.py` with `UBYHOST_SHELL_BROWSERS: chromium,webkit`. `passkeys-client.yml` runs `node --test App/tests/test_passkeys_client.cjs` and `tests/test_passkeys_client_browser.py` with `PASSKEY_BROWSER` = chromium and webkit. `checkin-alerts.yml` only re-runs tests `test` already runs.
- Local browser runs in this container: `export PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 UBYHOST_UBYPORT_ENV=mock UBYHOST_DEPLOYMENT=staging UBYHOST_ENABLE_SCHEDULER=0`, venv `App/.venv`. Only Chromium is installed locally, so set `UBYHOST_SHELL_BROWSERS=chromium` locally and expect WebKit-only cases to fail locally (CI installs WebKit); list them, do not fix them.

## 3. Files

| Path | Action | What |
|---|---|---|
| `.github/workflows/ci.yml` | edit | Replace jobs `guest-browser`, `calendar-review`, `door-code-access-review` with `browser-shard` + `browser`; add the node passkey step to `test` |
| `.github/workflows/deploy-lightsail.yml` | edit | `"guest-browser"` becomes `"browser"` in the `need=[...]` list |
| `.github/workflows/mobile-more.yml` | delete | Folded into `browser` |
| `.github/workflows/passkeys-client.yml` | delete | Folded into `test` and `browser` |
| `.github/workflows/checkin-alerts.yml` | delete | Duplicate of `test` |
| `App/tests/test_guest_browser_e2e.py` | edit | Docstring: `guest-browser` becomes `browser` |
| `docs/DESIGN.md` | edit | Line with "`guest-browser` job": becomes "`browser` job" |
| `docs/tasks/0361-report.md` | create | Report, including the survey table |

No other file may change.

## 4. Steps

1. **Survey (no edits).** From `App/`, list the files: `ls tests/*_browser.py tests/test_guest_browser_e2e.py tests/test_host_geometry.py tests/test_wp28_geometry.py tests/test_onboarding_wizard_survival.py | sort -u | wc -l`. Run them in batches of about 10 files with the command in §6 (a), Bash timeout 600000 ms. Record per file: passed / failed (first failing test name) / skipped, and the batch time. Do NOT fix any failing test.
2. **ci.yml, test job.** After the step `Install system tools used by tests`, add:
   ```yaml
         - uses: actions/setup-node@v6
           with:
             node-version: "22"

         - name: Passkey client logic (node)
           working-directory: ${{ github.workspace }}
           run: node --test App/tests/test_passkeys_client.cjs
   ```
   Commit `0361 step 2`.
3. **ci.yml, browser jobs.** Delete the whole `guest-browser:`, `calendar-review:` and `door-code-access-review:` jobs. In their place (after `smoke:`), insert exactly the YAML in §4a. Commit `0361 step 3`.
4. **deploy-lightsail.yml.** Replace `"guest-browser"` with `"browser"` (one occurrence). Commit `0361 step 4`.
5. Delete the three side workflows (`git rm`). Edit the docstring in `App/tests/test_guest_browser_e2e.py` and the line in `docs/DESIGN.md` (`grep -nF 'guest-browser'`). Commit `0361 step 5`.
6. Run §6 (b) and (c). Write the report with the survey table. Commit `0361 step 6`.

### 4a. YAML to insert

```yaml
  browser-shard:
    # Every browser test, collected by pattern so none can be forgotten.
    # Four shards run in parallel; each needs Chromium, some need WebKit.
    name: browser shard ${{ matrix.shard }}
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        shard: [1, 2, 3, 4]
    defaults:
      run:
        working-directory: App

    steps:
      - uses: actions/checkout@v7

      - uses: actions/setup-python@v7
        with:
          python-version: "3.12"
          cache: pip
          cache-dependency-path: |
            App/requirements.txt
            App/requirements.lock
            App/requirements-dev.txt

      - name: Install dependencies, Chromium and WebKit
        run: |
          pip install --require-hashes -r requirements.lock && pip install -r requirements-dev.txt
          pip install playwright==1.63.0
          python -m playwright install --with-deps chromium webkit

      - name: Pick this shard's files
        id: files
        run: |
          files="$(ls tests/*_browser.py tests/test_guest_browser_e2e.py tests/test_host_geometry.py \
            tests/test_wp28_geometry.py tests/test_onboarding_wizard_survival.py | sort -u \
            | awk -v n=4 -v s=${{ matrix.shard }} '(NR - 1) % n == s - 1' | tr '\n' ' ')"
          echo "files=${files}" >> "$GITHUB_OUTPUT"
          echo "Shard ${{ matrix.shard }}: ${files}"

      - name: Run browser tests
        env:
          UBYHOST_UBYPORT_ENV: mock
          UBYHOST_DEPLOYMENT: staging
          UBYHOST_ENABLE_SCHEDULER: "0"
          UBYHOST_REQUIRE_BROWSER: "1"
          UBYHOST_SHELL_BROWSERS: chromium,webkit
          UBYHOST_SHOTS_DIR: ${{ runner.temp }}/browser-shots
          UBYHOST_WIDE_GEOMETRY_DIR: ${{ runner.temp }}/browser-shots/wide
          UBYHOST_CAPTURE_FILTERS: "1"
          UBYHOST_PASSKEY_SHOTS: ${{ runner.temp }}/browser-shots/passkey
        # REQUIRE_BROWSER turns "Chromium is missing" from a skip into a failure.
        run: python -m pytest ${{ steps.files.outputs.files }} -q -rs --junitxml=/tmp/ubyhost-tests.xml

      - name: Passkey login on WebKit
        if: matrix.shard == 1
        env:
          PASSKEY_BROWSER: webkit
          UBYHOST_REQUIRE_BROWSER: "1"
          UBYHOST_UBYPORT_ENV: mock
          UBYHOST_DEPLOYMENT: staging
          UBYHOST_ENABLE_SCHEDULER: "0"
          UBYHOST_PASSKEY_SHOTS: ${{ runner.temp }}/browser-shots/passkey-webkit
        run: python -m pytest tests/test_passkeys_client_browser.py -q -rs --junitxml=/tmp/passkey-webkit.xml
```
Then copy, unchanged, from the deleted `guest-browser` job: the steps `Summarize required browser checks`, its `${{ steps.browser_summary.outputs.summary ... }}` step, `Annotate failed tests` and the 8 `Test failure detail` steps. Then add:
```yaml
      - name: Upload screenshots
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: browser-shots-${{ matrix.shard }}
          path: |
            ${{ runner.temp }}/browser-shots
            docs/tasks/0102-evidence/
          if-no-files-found: warn

  browser:
    # The one name the deploy gate and the main ruleset require.
    if: always()
    needs: browser-shard
    runs-on: ubuntu-latest
    steps:
      - name: All browser shards passed
        run: test "${{ needs.browser-shard.result }}" = "success"
```

## 5. Do not touch

`App/app/`, every test file except the docstring in §3, `scripts/merge-pr-on-green.sh`, the jobs `test` (except step 2), `smoke`, `shellcheck`, `docker`, `context`, `secrets`, and every deploy workflow except the one word in step 4. Never skip, xfail or delete a test. Never push or merge.

## 6. Commands

(a) From `App/`, env from §2 plus `UBYHOST_SHELL_BROWSERS=chromium`: `.venv/bin/python -m pytest <10 files> -q -rs --tb=line -p no:cacheprovider 2>&1 | tail -30`

(b) YAML parses: `python3 -c "import yaml,sys; [yaml.safe_load(open(f)) for f in sys.argv[1:]]; print('ok')" .github/workflows/ci.yml .github/workflows/deploy-lightsail.yml 2>&1 | tail -5` (if PyYAML is missing, use `App/.venv/bin/python`; still missing: say so in the report, do not install it).

(c) `python3 scripts/context_lint.py 2>&1 | tail -5` ends with `context lint: OK`. `grep -rn "guest-browser" .github App/tests docs/DESIGN.md | tail -5` prints nothing.

## 7. Acceptance

- [ ] Survey table in the report: every browser file with passed / failed (test name) / skipped, plus total local time.
- [ ] `ci.yml` has no `guest-browser`, `calendar-review` or `door-code-access-review` job; it has `browser-shard` (4 shards) and `browser`.
- [ ] `deploy-lightsail.yml` requires `browser`.
- [ ] The three side workflows are deleted.
- [ ] §6 (b) prints `ok`, §6 (c) passes.

## 8. Stop and ask

Stop, and write the report, if: an anchor is not found; a step is unclear; you reach 25 tool calls or about 50k tokens (report `blocked`, keep the survey); you would need push, merge, secrets or a new dependency.

## 9. Report

Write `docs/tasks/0361-report.md` (1500 tokens at most, the survey table makes it longer) and set `Status: review`: files changed, commands with their last 5 lines, the survey table, §7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

`.github/workflows/ci.yml`, `.github/workflows/deploy-lightsail.yml`

## Owner steps

1. Merge only after every browser shard is green. Failing files from the survey get their own fix briefs first.
2. After merge, the main ruleset (owner settings pass) requires `browser`, not `guest-browser`.
