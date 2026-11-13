# 1205 report: lock vulnerability bumps

Status: blocked
Branch: exec-1205b (base 4e221d29)

## 1. Files changed

- `App/requirements.txt`: appended `pillow==13.0.0` (commit 7ae66fc8, `1205 step 1`).
- `App/requirements.lock`: NOT committed. Regenerated lock was reverted. Full generated diff saved at `/tmp/claude-0/-home-user-jsfpecharoperations/9b4fc399-e906-5543-b0f7-22fae18af6fa/scratchpad/1205/lock-regen.diff`.
- `docs/context/known-issues.md`: not edited (step 6 not reached).

## 2. Commands run

- `pip-compile ... --upgrade-package pillow==13.0.0 --upgrade-package pyasn1==0.6.5 --upgrade-package certifi==2026.10.18 requirements.txt`: exit OK, header unchanged (no edit needed).
- `git diff --stat -- App/requirements.lock`: 1 file, 249 insertions, 237 deletions.
- Not run: pip install of the lock, both pytest commands, pip-audit, context_lint. Stopped at step 5.

## 3. Acceptance (section 7)

- [x] Header lines 1 to 6 unchanged (no edit needed).
- [ ] Lock changes only the three packages: FAILED (see Deviations).
- [ ] Remaining checks not run.

## 4. Deviations

- Done: steps 1 to 4. Left: steps 5 (stopped) and 6, plus section 6 tests and audit.
- Lock diff is not limited to the three packages (brief section 8 stop). Packages changed beyond pillow, pyasn1, certifi: anthropic 2.3.0 to 2.6.0, boto3 1.43.108 to 1.43.126, botocore 1.43.118 to 1.43.127, cryptography 50.0.1 to 50.0.2, fastapi 0.142.2 to 0.162.2, psycopg 3.3.6 to 3.3.8 (plus psycopg-binary), python-multipart 0.0.32 to 0.0.33, reportlab 5.0.1 to 5.1.0, starlette 1.7.0 to 1.10.0, stripe 16.0.1 to 16.1.0.
- Likely cause: the committed lock was already stale against `requirements.txt` (for example anthropic, psycopg, stripe, reportlab), so any regeneration re-pins them. Not verified further.

## 5. Questions

- Accept the wider lock refresh as a separate decision, or should the lock be rebuilt with only the three bumps (needs an approach that does not re-resolve the other packages)?

## 6. Owner steps left

- None until the question above is answered.
