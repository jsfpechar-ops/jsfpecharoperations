"""Task 0001: move finished audits/plans to docs/archive/ and rewrite every reference.

Run from the repo root:  python3 archive_docs.py            (dry run, prints the plan)
                         python3 archive_docs.py --apply    (does it, with git mv)
"""
import os
import re
import subprocess
import sys

MOVE = [
    "FOLLOWUPS.md",
    "docs/UBYHOST_CODE_AUDIT.md", "docs/TECHNICAL_COMPLIANCE_AUDIT.md",
    "docs/SECURITY_REVIEW_2026-09-15.md", "docs/PHASE_1-6_REVIEW_2026-09-24.md",
    "docs/SKILL.md", "docs/LOGO_PROMPT.md", "docs/NEXT_MAIL_RELEASE.md",
    "docs/plans/UX_AUDIT.md", "docs/plans/UX_IMPLEMENTATION_REVIEW.md",
    "docs/plans/UbyHost_Audit_and_Cursor_Plan_2026-09-28.md",
    "docs/plans/UbyHost_prelaunch_review", "docs/plans/GDPR_COMPLIANCE_REVIEW_2026-09-27.md",
    "docs/plans/GDPR_REMEDIATION_PLAN.md", "docs/plans/PLAN_UX_UI_OVERHAUL.md",
    "docs/plans/PLAN_TICKET_WALLET_V2.md", "docs/plans/THREE_PLAN_GITHUB_DELIVERY.md",
    "docs/plans/PLAN_POPLATEK_Z_POBYTU.md", "docs/plans/host-app-redesign",
    "docs/UbyHost_workplan/series", "docs/UbyHost_workplan/notes", "docs/UbyHost_workplan/skills",
    "docs/UbyHost_workplan/00_README_for_cursor.md", "docs/UbyHost_workplan/01_before_golive.md",
    "docs/UbyHost_workplan/02_after_golive.md", "docs/UbyHost_workplan/05_owner_checklist.md",
    "docs/UbyHost_workplan/06_council_verdict.md", "docs/UbyHost_workplan/07_council_verdict_round2.md",
    "docs/UbyHost_workplan/MERGE_SEQUENCE.md", "docs/UbyHost_workplan/OWNER_MANUAL_SETUP.md",
    "docs/UbyHost_workplan/OWNER_PRODUCTION_STATUS.md",
    "docs/UbyHost_workplan/OWNER_WORKFLOW_STEP_BY_STEP.md",
    "docs/UbyHost_workplan/STAGING_ON_RENDER_STEP_BY_STEP.md",
    "docs/UbyHost_workplan/UbyHost_architecture_review.md",
]
TEXT_EXT = {".md", ".py", ".html", ".css", ".js", ".sh", ".yml", ".yaml", ".toml", ".txt", ".example"}
SKIP_DIRS = ("docs/archive/", "docs/context/", "docs/tasks/", ".git/")


def new_path(old: str) -> str:
    return "docs/archive/" + (old[len("docs/"):] if old.startswith("docs/") else old)


def tracked_files():
    out = subprocess.run(["git", "ls-files"], capture_output=True, text=True, check=True).stdout
    for f in out.splitlines():
        if f.startswith(SKIP_DIRS) or not os.path.isfile(f) or map_target(f):
            continue
        if os.path.splitext(f)[1] in TEXT_EXT or f.endswith(".env.example"):
            yield f


def map_target(target: str):
    """Repo-relative target -> archived repo-relative path, or None."""
    for old in MOVE:
        if target == old or target.startswith(old + "/"):
            return new_path(old) + target[len(old):]
    return None


def rewrite(text: str, fname: str) -> str:
    here = os.path.dirname(fname)

    # 1. Markdown relative links: [x](path#anchor)
    def link(m):
        url = m.group(2)
        if re.match(r"^[a-z]+:|^#|^/", url):
            return m.group(0)
        path, sep, anchor = url.partition("#")
        target = os.path.normpath(os.path.join(here, path)).replace(os.sep, "/")
        new = map_target(target)
        if not new:
            return m.group(0)
        rel = os.path.relpath(new, here or ".").replace(os.sep, "/")
        return f"{m.group(1)}({rel}{sep}{anchor})"
    text = re.sub(r"(\[[^\]]*\])\(([^)\s]+)\)", link, text)

    # 2. Full repo paths in prose and code comments (longest first).
    for old in sorted(MOVE, key=len, reverse=True):
        if old.startswith("docs/"):
            text = re.sub(r"(?<![\w/])" + re.escape(old) + r"(?=[/\s`'\").,:;#]|$)", new_path(old), text)
    # 3. Bare FOLLOWUPS.md mentions outside markdown links.
    text = re.sub(r"(?<![\w/(])FOLLOWUPS\.md", "docs/archive/FOLLOWUPS.md", text)
    return text


def main():
    apply = "--apply" in sys.argv
    missing = [p for p in MOVE if not os.path.exists(p)]
    if missing:
        print("STOP: these paths do not exist:", missing)
        return 1
    changes = []
    for f in tracked_files():
        with open(f, encoding="utf-8", errors="surrogateescape") as fh:
            old_text = fh.read()
        new_text = rewrite(old_text, f)
        if new_text != old_text:
            changes.append(f)
            if apply:
                with open(f, "w", encoding="utf-8", errors="surrogateescape") as fh:
                    fh.write(new_text)
    for old in MOVE:
        print(("MOVE " if apply else "would move ") + f"{old} -> {new_path(old)}")
        if apply:
            os.makedirs(os.path.dirname(new_path(old)), exist_ok=True)
            subprocess.run(["git", "mv", old, new_path(old)], check=True)
    for f in changes:
        print(("EDITED " if apply else "would edit ") + f)
    print(f"{len(MOVE)} moves, {len(changes)} files with rewritten references")
    return 0


if __name__ == "__main__":
    sys.exit(main())
