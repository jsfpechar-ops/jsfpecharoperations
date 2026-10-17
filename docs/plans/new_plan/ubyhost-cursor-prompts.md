# UbyHost: Cursor prompts, in order

**You upload to GitHub yourself**, into `docs/plans/`:

- `ubyhost-easy-fill-plan.md` (now also contains the 0043 brief)
- `ubyhost-onboarding-review-and-plan.md`
- `ubyhost-autofill-review.md`
- `platforms/airbnb.svg`, `platforms/booking.svg`, `platforms/echalupy.svg` → `docs/plans/platforms/`

Leave out the two `superhostem-*` files (the repo is public).

Then run **Prompt 0 once**: it turns the briefs inside those plans into task files. Merge it, then start the **5 lanes below in parallel**, one Cursor chat each.

---

## Prompt 0: create the task files from the plans (docs only)

```
Read AGENTS.md. Pull main. Create branch docs/easy-setup-briefs.

1. In these files: docs/plans/ubyhost-easy-fill-plan.md, docs/plans/ubyhost-onboarding-review-and-plan.md, docs/plans/ubyhost-autofill-review.md,
   extract every block between a line "<<<BRIEF" and a line "BRIEF>>>".
   Save each block, without the markers, as docs/tasks/<name>.md where <name> is the part after "Branch: task/" in that block.
   Expected 11 files: 0043-police-setup-fewer-fields, 0044-ws-request-letter, 0045-one-line-address, 0046-copy-property-settings,
   0047-dashboard-missing-banner, 0048-platform-logos, 0051-stay-fee-send-panel, 0054-setup-wizard-shell, 0055-ares-lookup,
   0061-invoice-autofill, 0062-calmer-forms. If a file is missing in docs/plans, or a task number already exists in docs/tasks, stop and tell me.
2. Append to docs/context/decisions.md:
   - 2026-10-11 | ARES lookup on host click, sends only the IČO, uses existing requests lib | owner | [0055](../tasks/0055-ares-lookup.md)
3. Run python3 scripts/context_lint.py and fix only lint issues in the files you added or in docs/plans/ubyhost-*.md (broken relative links, etc.).
4. Do not touch App/. Do not change the plans' content. Commit, push, open one PR titled "docs: task briefs 0043–0062 from easy-setup plans".
```

---

## Task prompts: 5 parallel lanes (after Prompt 0 is merged)

Start lanes A–E at the same time, each in its own Cursor chat. Each agent works in **its own git worktree**, so they don't step on each other. Tests already pick free ports, so parallel runs are safe. **Merge order when several are ready:** whichever PR is green first. The others rebase themselves (the prompt tells them to).

### Lane A: property form (in order, each after the previous is merged)
These all edit `apartment_form.html` and `routes/admin.py`, so they run one after another inside this lane.

**A1. 0043: police setup with 3 fields**
```
Read AGENTS.md. Run: git fetch origin && git worktree add ../uby-0043 -b task/0043-police-setup-fewer-fields origin/main, then work only inside ../uby-0043 (other Cursor agents are working in parallel in other worktrees; never touch the main checkout or another worktree). In the worktree, link the existing venv: ln -s "$(git rev-parse --path-format=absolute --git-common-dir)/../App/.venv" App/.venv (if that fails, create App/.venv and pip install -r requirements.txt -r requirements-dev.txt). Follow docs/tasks/0043-police-setup-fewer-fields.md exactly. Open only the files it names. Add new i18n keys next to keys with the same prefix, not at the end of the dict, so parallel PRs don't conflict. If any stop condition in §8 happens, stop and write the report. Before opening the PR, git fetch origin && git rebase origin/main and re-run the tests. Finish by writing docs/tasks/0043-report.md in the §9 format and opening one PR.
```

**A2. 0045: one-line address**
```
Read AGENTS.md. Run: git fetch origin && git worktree add ../uby-0045 -b task/0045-one-line-address origin/main, then work only inside ../uby-0045 (other Cursor agents are working in parallel in other worktrees; never touch the main checkout or another worktree). In the worktree, link the existing venv: ln -s "$(git rev-parse --path-format=absolute --git-common-dir)/../App/.venv" App/.venv (if that fails, create App/.venv and pip install -r requirements.txt -r requirements-dev.txt). Follow docs/tasks/0045-one-line-address.md exactly. Open only the files it names. Add new i18n keys next to keys with the same prefix, not at the end of the dict, so parallel PRs don't conflict. If any stop condition in §8 happens, stop and write the report. Before opening the PR, git fetch origin && git rebase origin/main and re-run the tests. Finish by writing docs/tasks/0045-report.md in the §9 format and opening one PR.
```

**A3. 0046: copy from another property**
```
Read AGENTS.md. Run: git fetch origin && git worktree add ../uby-0046 -b task/0046-copy-property-settings origin/main, then work only inside ../uby-0046 (other Cursor agents are working in parallel in other worktrees; never touch the main checkout or another worktree). In the worktree, link the existing venv: ln -s "$(git rev-parse --path-format=absolute --git-common-dir)/../App/.venv" App/.venv (if that fails, create App/.venv and pip install -r requirements.txt -r requirements-dev.txt). Follow docs/tasks/0046-copy-property-settings.md exactly. Open only the files it names. Add new i18n keys next to keys with the same prefix, not at the end of the dict, so parallel PRs don't conflict. If any stop condition in §8 happens, stop and write the report. Before opening the PR, git fetch origin && git rebase origin/main and re-run the tests. Finish by writing docs/tasks/0046-report.md in the §9 format and opening one PR.
```

**A4. 0062: calmer forms**
```
Read AGENTS.md. Run: git fetch origin && git worktree add ../uby-0062 -b task/0062-calmer-forms origin/main, then work only inside ../uby-0062 (other Cursor agents are working in parallel in other worktrees; never touch the main checkout or another worktree). In the worktree, link the existing venv: ln -s "$(git rev-parse --path-format=absolute --git-common-dir)/../App/.venv" App/.venv (if that fails, create App/.venv and pip install -r requirements.txt -r requirements-dev.txt). Follow docs/tasks/0062-calmer-forms.md exactly. Open only the files it names. Add new i18n keys next to keys with the same prefix, not at the end of the dict, so parallel PRs don't conflict. If any stop condition in §8 happens, stop and write the report. Before opening the PR, git fetch origin && git rebase origin/main and re-run the tests. Finish by writing docs/tasks/0062-report.md in the §9 format and opening one PR.
```

**A5. 0044: "no police login yet" letter**
```
Read AGENTS.md. Run: git fetch origin && git worktree add ../uby-0044 -b task/0044-ws-request-letter origin/main, then work only inside ../uby-0044 (other Cursor agents are working in parallel in other worktrees; never touch the main checkout or another worktree). In the worktree, link the existing venv: ln -s "$(git rev-parse --path-format=absolute --git-common-dir)/../App/.venv" App/.venv (if that fails, create App/.venv and pip install -r requirements.txt -r requirements-dev.txt). Follow docs/tasks/0044-ws-request-letter.md exactly. Open only the files it names. Add new i18n keys next to keys with the same prefix, not at the end of the dict, so parallel PRs don't conflict. If any stop condition in §8 happens, stop and write the report. Before opening the PR, git fetch origin && git rebase origin/main and re-run the tests. Finish by writing docs/tasks/0044-report.md in the §9 format and opening one PR.
```

**A6. 0054: setup wizard, first screens**
```
Read AGENTS.md. Run: git fetch origin && git worktree add ../uby-0054 -b task/0054-setup-wizard-shell origin/main, then work only inside ../uby-0054 (other Cursor agents are working in parallel in other worktrees; never touch the main checkout or another worktree). In the worktree, link the existing venv: ln -s "$(git rev-parse --path-format=absolute --git-common-dir)/../App/.venv" App/.venv (if that fails, create App/.venv and pip install -r requirements.txt -r requirements-dev.txt). Follow docs/tasks/0054-setup-wizard-shell.md exactly. Open only the files it names. Add new i18n keys next to keys with the same prefix, not at the end of the dict, so parallel PRs don't conflict. If any stop condition in §8 happens, stop and write the report. Before opening the PR, git fetch origin && git rebase origin/main and re-run the tests. Finish by writing docs/tasks/0054-report.md in the §9 format and opening one PR.
```

### Lane B: invoices (0055, then 0061)
Both edit the invoice routes and form.

**B1. 0055: fill from IČO (ARES)**
```
Read AGENTS.md. Run: git fetch origin && git worktree add ../uby-0055 -b task/0055-ares-lookup origin/main, then work only inside ../uby-0055 (other Cursor agents are working in parallel in other worktrees; never touch the main checkout or another worktree). In the worktree, link the existing venv: ln -s "$(git rev-parse --path-format=absolute --git-common-dir)/../App/.venv" App/.venv (if that fails, create App/.venv and pip install -r requirements.txt -r requirements-dev.txt). The ARES decision line already exists in docs/context/decisions.md; do not add it again. Follow docs/tasks/0055-ares-lookup.md exactly. Open only the files it names. Add new i18n keys next to keys with the same prefix, not at the end of the dict, so parallel PRs don't conflict. If any stop condition in §8 happens, stop and write the report. Before opening the PR, git fetch origin && git rebase origin/main and re-run the tests. Finish by writing docs/tasks/0055-report.md in the §9 format and opening one PR.
```

**B2. 0061: invoice autofill**
```
Read AGENTS.md. Run: git fetch origin && git worktree add ../uby-0061 -b task/0061-invoice-autofill origin/main, then work only inside ../uby-0061 (other Cursor agents are working in parallel in other worktrees; never touch the main checkout or another worktree). In the worktree, link the existing venv: ln -s "$(git rev-parse --path-format=absolute --git-common-dir)/../App/.venv" App/.venv (if that fails, create App/.venv and pip install -r requirements.txt -r requirements-dev.txt). Follow docs/tasks/0061-invoice-autofill.md exactly. Open only the files it names. Add new i18n keys next to keys with the same prefix, not at the end of the dict, so parallel PRs don't conflict. If any stop condition in §8 happens, stop and write the report. Before opening the PR, git fetch origin && git rebase origin/main and re-run the tests. Finish by writing docs/tasks/0061-report.md in the §9 format and opening one PR.
```

### Lane C: platform logos
Independent.

**C1. 0048: platform logos**
```
Read AGENTS.md. Run: git fetch origin && git worktree add ../uby-0048 -b task/0048-platform-logos origin/main, then work only inside ../uby-0048 (other Cursor agents are working in parallel in other worktrees; never touch the main checkout or another worktree). In the worktree, link the existing venv: ln -s "$(git rev-parse --path-format=absolute --git-common-dir)/../App/.venv" App/.venv (if that fails, create App/.venv and pip install -r requirements.txt -r requirements-dev.txt). First copy docs/plans/platforms/airbnb.svg, booking.svg, echalupy.svg to App/app/static/platforms/ (check each has no <script>, no external href, no on* attributes). Follow docs/tasks/0048-platform-logos.md exactly. Open only the files it names. Add new i18n keys next to keys with the same prefix, not at the end of the dict, so parallel PRs don't conflict. If any stop condition in §8 happens, stop and write the report. Before opening the PR, git fetch origin && git rebase origin/main and re-run the tests. Finish by writing docs/tasks/0048-report.md in the §9 format and opening one PR.
```

### Lane D: stay fee
Independent (its own migration 0009; no other brief adds a migration).

**D1. 0051: "send by data box" panel**
```
Read AGENTS.md. Run: git fetch origin && git worktree add ../uby-0051 -b task/0051-stay-fee-send-panel origin/main, then work only inside ../uby-0051 (other Cursor agents are working in parallel in other worktrees; never touch the main checkout or another worktree). In the worktree, link the existing venv: ln -s "$(git rev-parse --path-format=absolute --git-common-dir)/../App/.venv" App/.venv (if that fails, create App/.venv and pip install -r requirements.txt -r requirements-dev.txt). Follow docs/tasks/0051-stay-fee-send-panel.md exactly. Open only the files it names. Add new i18n keys next to keys with the same prefix, not at the end of the dict, so parallel PRs don't conflict. If any stop condition in §8 happens, stop and write the report. Before opening the PR, git fetch origin && git rebase origin/main and re-run the tests. Finish by writing docs/tasks/0051-report.md in the §9 format and opening one PR.
```

### Lane E: dashboard banner
Independent (reads `_readiness`, doesn't change it).

**E1. 0047: one "what blocks reporting" banner**
```
Read AGENTS.md. Run: git fetch origin && git worktree add ../uby-0047 -b task/0047-dashboard-missing-banner origin/main, then work only inside ../uby-0047 (other Cursor agents are working in parallel in other worktrees; never touch the main checkout or another worktree). In the worktree, link the existing venv: ln -s "$(git rev-parse --path-format=absolute --git-common-dir)/../App/.venv" App/.venv (if that fails, create App/.venv and pip install -r requirements.txt -r requirements-dev.txt). Follow docs/tasks/0047-dashboard-missing-banner.md exactly. Open only the files it names. Add new i18n keys next to keys with the same prefix, not at the end of the dict, so parallel PRs don't conflict. If any stop condition in §8 happens, stop and write the report. Before opening the PR, git fetch origin && git rebase origin/main and re-run the tests. Finish by writing docs/tasks/0047-report.md in the §9 format and opening one PR.
```

When a lane finishes and you have time: lane A is the long one. After 0043 is merged, you can run **0046 next to 0045** (they touch different parts of the form; expect a small rebase).

### Where Cursor will stop and ask you (answer in the Cursor chat)

- **0043 §8.1:** are the 6 characters after `UBY-WS` in the police login the same as the facility mark (zkratka)? If you're not sure, say "keep the mark field visible".
- **0044 §8.1:** the police data-box ID and the subject line for the request letter, if you have them.
