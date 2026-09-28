# Guidance for AI agents

Before changing UbyHost’s user interface, read **[docs/DESIGN.md](docs/DESIGN.md)**.

**Dark mode:** Do not add or restore dark mode, system-theme switching, or
`prefers-color-scheme` dark styling unless the product owner explicitly requests
it in the current task. UbyHost is light-mode only by policy.

Application code lives under **`App/`**. Run tests from `App/` with:

```bash
.venv/bin/python -m pytest tests -q
```

Do not add `PYTHONPATH=App` here. From `App/` that resolves to `App/App`, which
on a case-insensitive filesystem (macOS) is the same directory as `App/app` —
so `app/operator.py` shadows the standard library `operator` module and pytest
fails during collection.

## Merging a pull request

Branch protection is not available on this private plan, so GitHub does not
enforce CI before a merge. **Never merge a PR until CI is green for the PR's
current head commit.** `gh pr checks` can briefly report a previous commit's
passing checks right after a force-push, so a "wait until nothing is pending"
loop can merge a commit whose own run is still failing. Use the committed
guard, which pins the head SHA and re-reads it immediately before merging:

```bash
scripts/merge-pr-on-green.sh <pr-number> [--merge|--squash|--rebase]
```

It refuses to merge while any check is pending or failed. `MERGE_GUARD_TIMEOUT`
(seconds, default 1800) bounds the wait.
