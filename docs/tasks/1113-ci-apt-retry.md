# 1113: CI `test` job: retry apt, keep the age check

Status: todo
Depends on: none (does not need PR #920) | Base commit: current main (22c5d255 at writing) | Branch: task/1113-ci-apt-retry
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

Exception to the usual rule: this brief edits `.github/workflows/ci.yml`. That is allowed here.

## Open questions (read first)

1. The task text quotes line 41 as `run: sudo apt-get update && sudo apt-get install -y --no-install-recommends age sqlite3`. That line does not exist in `.github/workflows/ci.yml` on PR #920's branch nor on main (`diff` of the two files is empty, so both have the same lines). The step "Install system tools used by tests" is at lines 38 to 60 and already has `timeout 90s`, a curl fallback for `age` (`install_age_binary`) and `|| true` on the `sqlite3` install. If the owner's failing log shows the one-line form, it comes from an older commit; rebase first. The change below still applies to today's step and is the same idea.
2. The existing curl fallback needs github.com. If the runner has no DNS at all, both paths fail. The retry loop gives DNS time to come back; nothing here can fix a runner with no network.
3. Only one workflow has `apt-get`: `.github/workflows/ci.yml`, lines 52 and 57 (checked with `grep -rn 'apt-get' .github`). No other workflow needs a change. `Dockerfile` and `deploy/` use apt too but are not workflows; do not touch them.
4. Only the owner can confirm this on a real CI run. Low risk: one CI step, no app code.

## 1. Objective

Make the apt part of the `test` job's "Install system tools used by tests" step survive a short DNS or mirror outage: apt retries each download itself, and a bounded loop retries the whole update plus install up to 3 times. The job must still fail if `age` is missing at the end.

## 2. Context

Rules: no new dependency, no unpinned action (this brief adds no `uses:`), the `workflow-lint` job (actionlint through docker, which runs shellcheck on `run:` blocks, then zizmor at high severity) and the `shellcheck` job must stay green. Quote variables, no new `uses:`.

Anchor, verbatim, `.github/workflows/ci.yml` lines 38 to 60 (find the start with `grep -nF "Install system tools used by tests" .github/workflows/ci.yml`):

```yaml
      - name: Install system tools used by tests
        run: |
          set -euo pipefail
          install_age_binary() {
            ver=1.2.1
            tmp="$(mktemp -d)"
            curl -fsSL "https://github.com/FiloSottile/age/releases/download/v${ver}/age-v${ver}-linux-amd64.tar.gz" \
              | tar -xzf - -C "${tmp}"
            sudo install -m 0755 "${tmp}/age/age" "${tmp}/age/age-keygen" /usr/local/bin/
            rm -rf "${tmp}"
          }
          if ! command -v age >/dev/null; then
            if ! (timeout 90s sudo apt-get update -qq && timeout 90s sudo apt-get install -y --no-install-recommends age); then
              install_age_binary
            fi
          fi
          if ! command -v sqlite3 >/dev/null; then
            timeout 90s sudo apt-get update -qq && timeout 90s sudo apt-get install -y --no-install-recommends sqlite3 || true
          fi
          age --version
          sqlite3 --version
```

If any line above is not found verbatim, STOP (section 8).

## 3. Files

| Path | Action | What |
|---|---|---|
| `.github/workflows/ci.yml` | edit | Add `apt_install` helper; use it in the two places that call `apt-get`; add a final `command -v age` check |

No other file may change.

## 4. Steps

1. Anchor check. Run:
   `grep -nF "timeout 90s sudo apt-get update -qq" .github/workflows/ci.yml | tail -30`
   Expected: exactly 2 lines (about 52 and 57). Any other count: STOP.

2. In `.github/workflows/ci.yml`, add the helper after the closing `}` of `install_age_binary`. Replace this exact text (the last line of the function and the next line):

   ```
             rm -rf "${tmp}"
           }
           if ! command -v age >/dev/null; then
   ```

   with:

   ```
             rm -rf "${tmp}"
           }
           apt_install() {
             local attempt
             for attempt in 1 2 3; do
               if timeout 90s sudo apt-get -o Acquire::Retries=5 update -qq \
                 && timeout 90s sudo apt-get -o Acquire::Retries=5 install -y --no-install-recommends "$@"; then
                 return 0
               fi
               echo "apt attempt ${attempt} of 3 failed for: $*" >&2
               if [ "${attempt}" -lt 3 ]; then
                 sleep 10
               fi
             done
             return 1
           }
           if ! command -v age >/dev/null; then
   ```

   Keep the 10-space indentation inside the `run: |` block exactly as shown (the block text starts at column 11 in the file; copy the indentation of the neighbouring lines).
   Check: `grep -nF "apt_install()" .github/workflows/ci.yml | tail -30` expects 1 line.

3. Replace this exact line (the `age` apt call):

   ```
               if ! (timeout 90s sudo apt-get update -qq && timeout 90s sudo apt-get install -y --no-install-recommends age); then
   ```

   with:

   ```
               if ! apt_install age; then
   ```

   Check: `grep -nF "apt_install age" .github/workflows/ci.yml | tail -30` expects 1 line. The `install_age_binary` fallback on the next line stays.

4. Replace this exact line (the `sqlite3` apt call):

   ```
               timeout 90s sudo apt-get update -qq && timeout 90s sudo apt-get install -y --no-install-recommends sqlite3 || true
   ```

   with:

   ```
               apt_install sqlite3 || true
   ```

   Check: `grep -nF "apt_install sqlite3" .github/workflows/ci.yml | tail -30` expects 1 line. `|| true` stays on purpose: `sqlite3 --version` two lines later still fails the step if it is missing.

5. Add the final age check. Replace this exact text:

   ```
             age --version
             sqlite3 --version
   ```

   with:

   ```
             command -v age >/dev/null
             age --version
             sqlite3 --version
   ```

   With `set -euo pipefail` at the top of the step, a missing `age` fails the job here.

6. Confirm no raw apt call is left. Run:
   `grep -n "apt-get" .github/workflows/ci.yml | tail -30`
   Expected: exactly 2 lines, both inside `apt_install` and both containing `-o Acquire::Retries=5`.

7. Parse check. Run:
   `python3 -c "import yaml,sys; yaml.safe_load(open(sys.argv[1]))" .github/workflows/ci.yml 2>&1 | tail -30`
   Expected: no output, exit 0. If PyYAML is not importable, run instead:
   `grep -c "apt_install" .github/workflows/ci.yml`
   Expected: 3 (definition, `age` call, `sqlite3` call; any other number: STOP). Then say in the report that the YAML parse was not run.

8. Shell syntax check of the step body (no extra tools needed). Run:
   `python3 -c "import yaml,sys; d=yaml.safe_load(open('.github/workflows/ci.yml')); s=[x for x in d['jobs']['test']['steps'] if x.get('name')=='Install system tools used by tests'][0]['run']; open('/tmp/step1113.sh','w').write(s)" && bash -n /tmp/step1113.sh && echo syntax-ok 2>&1 | tail -30`
   Expected: `syntax-ok`. If `shellcheck` is installed, also run `shellcheck -S warning /tmp/step1113.sh 2>&1 | tail -30` (expected: nothing new about `apt_install`).

9. Commit: `git add .github/workflows/ci.yml && git commit -m "1113 step 1"`.

## 5. Do not touch

- Any other step or job in `ci.yml`, any other workflow, `Dockerfile`, `deploy/`, `App/`, `docs/context/`.
- Do not change the `timeout 90s` values, the `age` version `1.2.1`, or add any `uses:` line.
- Hard rule 8: never push to `main`; the owner merges.

## 6. Commands

- `grep -n "apt-get" .github/workflows/ci.yml | tail -30` : 2 lines, both with `-o Acquire::Retries=5`.
- YAML parse (step 7): no output.
- `bash -n` of the step body (step 8): `syntax-ok`.
- No pytest: no test-map row covers a workflow edit. CI runs the rest.
- `python3 scripts/context_lint.py 2>&1 | tail -30` from the repo root: expected clean.

## 7. Acceptance

- [ ] `grep -c "Acquire::Retries=5" .github/workflows/ci.yml` prints 2.
- [ ] No `apt-get` call outside `apt_install` in any file under `.github/workflows` (`grep -rn "apt-get" .github/workflows | tail -30`: 2 lines).
- [ ] The loop is at most 3 attempts with a 10 s pause (`for attempt in 1 2 3`, `sleep 10`).
- [ ] `command -v age >/dev/null` is before `age --version`.
- [ ] YAML parses; step body passes `bash -n`.
- [ ] Owner: the PR's `test` job reaches "Run tests with coverage" (only a real run can show this).

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found verbatim (see Open questions 1: the file may be an older commit);
- a check fails twice;
- you reach 25 tool calls or about 50k tokens (report as `blocked`, see executor.md);
- a new dependency, or an extra file, seems needed;
- a step is unclear;
- you need push, merge, secrets or deploy (hand that to the owner).

## 9. Report

Write `docs/tasks/1113-report.md` (600 tokens at most) and set `Status: review`. It has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. Section 7 ticked.
4. Deviations (say if PyYAML or shellcheck was missing).
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

Read in full: `.github/workflows/ci.yml` lines 38 to 75 only (the one step). Check that quoting is intact (`"$@"`, `"${attempt}"`) because `workflow-lint` runs shellcheck on it.

## Owner steps

1. Open the PR for branch `task/1113-ci-apt-retry` on GitHub and wait for the checks.
2. Open the `test` check, then the step "Install system tools used by tests". It should be green, and the next steps should run, ending at "Run tests with coverage".
3. Check that `workflow-lint` and `shellcheck` are also green.
4. If the step failed with "Temporary failure resolving" three times, copy the last 20 lines of that step into the chat; that means the runner had no network at all.
5. Merge with `scripts/merge-pr-on-green.sh` once green.
