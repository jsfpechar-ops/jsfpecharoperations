#!/usr/bin/env python3
"""Check the agent context system (AGENTS.md, docs/context, docs/tasks).

Stdlib only. Run from anywhere:  python3 scripts/context_lint.py [--strict]
Exit 1 on any error. Warnings never fail unless --strict.
Rules and caps are documented in docs/context/README.md; change them here and there together.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Token cap per file (estimate: characters / 4). Keys are repo-relative paths or globs.
CAPS = {
    "AGENTS.md": 1500,
    "CLAUDE.md": 50,
    "GEMINI.md": 50,
    ".github/copilot-instructions.md": 50,
    ".cursor/rules/agents.mdc": 150,
    "docs/context/README.md": 700,
    "docs/context/status.md": 700,
    "docs/context/decisions.md": 2000,
    "docs/context/architecture.md": 1500,
    "docs/context/glossary.md": 700,
    "docs/context/workflow.md": 1800,
    "docs/context/prompts.md": 800,
    "docs/context/rules.md": 2500,
    "docs/context/known-issues.md": 2500,
    "docs/context/domains/*.md": 1000,
    "docs/tasks/TEMPLATE.md": 900,
    "docs/tasks/[0-9][0-9][0-9][0-9]-*-report.md": 1500,
    "docs/tasks/[0-9][0-9][0-9][0-9]-*.md": 12000,
    "docs/archive/README.md": 1500,
}
# Every AI's entry file must exist and send the reader to AGENTS.md.
POINTERS = ["CLAUDE.md", "GEMINI.md", ".github/copilot-instructions.md", ".cursor/rules/agents.mdc"]
# Files whose links and paths are checked.
CHECKED = ["AGENTS.md", "CLAUDE.md", "docs/context/**/*.md", "docs/tasks/*.md",
           "docs/archive/README.md", "docs/plans/README.md"]
# These must never point into docs/archive/ (except the archive index).
NO_ARCHIVE = ["AGENTS.md", "docs/context/status.md"]
BRIEF_SECTIONS = ["## 1. Objective", "## 2. Context", "## 3. Files", "## 4. Steps",
                  "## 5. Do not touch", "## 6. Commands", "## 7. Acceptance",
                  "## 8. Stop and ask", "## 9. Report"]
STATUSES = {"todo", "in-progress", "review", "done", "blocked", "replaced"}
PATH_PREFIXES = ("App/", "docs/", "scripts/", "deploy/", ".github/", ".cursor/")
PLACEHOLDER = re.compile(r"[<>*{}]|NNNN|YYYY|\.\.\.")

errors: list[str] = []
warnings: list[str] = []


def rel(p: Path) -> str:
    return p.relative_to(ROOT).as_posix()


def files(patterns: list[str]) -> list[Path]:
    out: set[Path] = set()
    for pat in patterns:
        out.update(p for p in ROOT.glob(pat) if p.is_file())
    return sorted(out)


def slug(heading: str) -> str:
    s = heading.strip().lower()
    s = re.sub(r"[`*~]", "", s)
    s = re.sub(r"[^\w\- ]", "", s)
    return s.replace(" ", "-")


def anchors(md: Path) -> set[str]:
    seen: dict[str, int] = {}
    out = set()
    for line in md.read_text(encoding="utf-8", errors="ignore").splitlines():
        m = re.match(r"^#{1,6} (.+)$", line)
        if not m:
            continue
        base = slug(m.group(1))
        n = seen.get(base, 0)
        seen[base] = n + 1
        out.add(base if n == 0 else f"{base}-{n}")
    return out


def check_caps() -> None:
    done: set[Path] = set()
    for pat, cap in CAPS.items():
        for p in sorted(ROOT.glob(pat)):
            if p in done or not p.is_file():
                continue
            done.add(p)
            tokens = len(p.read_text(encoding="utf-8", errors="ignore")) // 4
            if tokens > cap:
                errors.append(f"{rel(p)}: ~{tokens} tokens > cap {cap}. Split or compact "
                              "(see docs/context/workflow.md#compaction).")


def check_target(src: Path, target: str, what: str) -> None:
    target = target.strip()
    if not target or target.startswith(("http://", "https://", "mailto:")) or PLACEHOLDER.search(target):
        return
    path, _, anchor = target.partition("#")
    path = re.sub(r":\d+(-\d+)?$", "", path)  # strip :line
    if not path:
        dest = src
    elif what == "link":
        dest = (src.parent / path).resolve()
    else:
        dest = (ROOT / path).resolve()
    if not dest.exists():
        errors.append(f"{rel(src)}: {what} target missing: {target}")
        return
    if anchor and dest.suffix == ".md" and anchor not in anchors(dest):
        errors.append(f"{rel(src)}: anchor #{anchor} not found in {rel(dest)}")
    if rel(src) in NO_ARCHIVE and "docs/archive/" in rel(dest) and dest.name != "README.md":
        errors.append(f"{rel(src)}: must not point into docs/archive/ ({target})")


def check_links() -> None:
    for p in files(CHECKED):
        if rel(p).startswith("docs/tasks/"):
            continue  # briefs name files that do not exist yet
        text = p.read_text(encoding="utf-8", errors="ignore")
        text_no_code = re.sub(r"```.*?```", "", text, flags=re.S)
        for m in re.finditer(r"\]\(([^)\s]+)\)", text_no_code):
            check_target(p, m.group(1), "link")
        for m in re.finditer(r"`([^`\s]+)`", text_no_code):
            tok = m.group(1)
            if tok.startswith(PATH_PREFIXES) or tok in ("AGENTS.md", "CLAUDE.md"):
                check_target(p, tok, "path")


def check_briefs() -> None:
    for p in sorted((ROOT / "docs/tasks").glob("[0-9][0-9][0-9][0-9]-*.md")):
        if p.name.endswith("-report.md"):
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        m = re.search(r"^Status: *([a-z-]+)", text, flags=re.M)
        if not m or m.group(1) not in STATUSES:
            errors.append(f"{rel(p)}: needs a 'Status: <{'|'.join(sorted(STATUSES))}>' line")
            continue
        for sec in BRIEF_SECTIONS:
            if sec not in text:
                errors.append(f"{rel(p)}: missing section '{sec}'")
        report = p.with_name(p.name[:4] + "-report.md")
        if m.group(1) in ("review", "done") and not report.exists():
            errors.append(f"{rel(p)}: status {m.group(1)} but {rel(report)} is missing")


def check_known_issues() -> None:
    p = ROOT / "docs/context/known-issues.md"
    if not p.exists():
        return
    ids = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.startswith("| K-"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) != 5:
                errors.append(f"known-issues.md: row needs 5 cells: {line[:60]}")
            ids.append(cells[0])
    dup = {i for i in ids if ids.count(i) > 1}
    if dup:
        errors.append(f"known-issues.md: duplicate IDs {sorted(dup)}")


def git(*args: str) -> str:
    try:
        return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True,
                              text=True, timeout=20).stdout.strip()
    except Exception:
        return ""


def check_staleness() -> None:
    last_status = git("log", "-1", "--format=%ct", "--", "docs/context/status.md")
    if not last_status:
        return
    newer = git("rev-list", "--count", f"--since={int(last_status) + 1}", "HEAD", "--", "App/")
    if newer.isdigit() and int(newer) > 0:
        warnings.append(f"{newer} commit(s) touched App/ after the last status.md update. "
                        "Orchestrator: update docs/context/status.md at review.")


def next_numbers() -> str:
    tasks = [int(p.name[:4]) for p in (ROOT / "docs/tasks").glob("[0-9][0-9][0-9][0-9]-*.md")]
    migs = [int(p.name[:4]) for p in (ROOT / "App/app/migrations").glob("[0-9][0-9][0-9][0-9]_*.sql")]
    return (f"next free: task {max(tasks, default=0) + 1:04d} | "
            f"migration {max(migs, default=1) + 1:04d}")


def check_pointers() -> None:
    for name in POINTERS:
        p = ROOT / name
        if not p.is_file() or "AGENTS.md" not in p.read_text(encoding="utf-8"):
            errors.append(f"{name}: missing or does not point to AGENTS.md")


def main() -> int:
    strict = "--strict" in sys.argv
    check_caps()
    check_links()
    check_briefs()
    check_known_issues()
    check_staleness()
    check_pointers()
    for w in warnings:
        print(f"WARN  {w}")
    for e in errors:
        print(f"ERROR {e}")
    print(next_numbers())
    failed = bool(errors) or (strict and bool(warnings))
    print("context lint: FAIL" if failed else "context lint: OK")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
