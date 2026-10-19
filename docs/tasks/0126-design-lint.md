# 0126: Design lint (raw colours, inline styles, page CSS, catalog classes) in CI

Status: review
Depends on: 0125 | Base commit: df8b842 | Branch: claude/project-thread-td6fpc
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

Part of [design-v2](../plans/design-v2.md). Commit each step as `0126 step k`. Never push, never open a PR.

## 1. Objective

Add `scripts/design_lint.py`, which fails when a host template on the enforced list contains a `<style>` block, a `style=""` attribute, a stylesheet or script link, a raw colour, or a class outside the catalog, and when the v2 host stylesheet contains a raw value. Wire it into the test suite and CI so drift is blocked from the first migrated page on (MASTER 11.1).

## 2. Context

Rules: MASTER 10 (never do) and 11.1 (lint). The enforced list starts with no templates; each page brief adds its templates to `docs/design/catalog.json`, so nothing fails today.

Anchor A, `.github/workflows/ci.yml`:

```
      - name: Lint for runtime errors
        run: ruff check app tests tools --select E9,F63,F7,F82,F401,F841
```

Anchor B, `docs/context/test-map.md`:

```
| A module with no row | `tests/test_<module name>*.py`; none exists: `-k <module name>` |
```

## 3. Files

| Path | Action | What |
|---|---|---|
| `scripts/design_lint.py` | create | the checker |
| `docs/design/catalog.json` | create | catalog classes, allowlisted hooks, enforced templates, enforced stylesheets |
| `App/tests/test_design_lint.py` | create | runs the checker; unit-tests each rule on a temp file |
| `.github/workflows/ci.yml` | edit | one step after ruff |
| `docs/context/test-map.md` | edit | one row |

No other file may change.

## 4. Steps

1. Create `docs/design/catalog.json`:

```json
{
  "master_version": "2.0.0",
  "classes": [
    "ui-page", "ui-ph", "ui-ph-main", "ui-ph-back", "ui-ph-meta", "ui-ph-acts", "ui-ph-menu",
    "ui-tabs", "ui-tab",
    "ui-toolbar", "ui-toolbar-search", "ui-toolbar-right", "ui-chips", "ui-chip", "ui-chip-x",
    "ui-body", "ui-body-list", "ui-body-detail", "ui-body-form", "ui-body-settings",
    "ui-btn", "ui-btn-primary", "ui-btn-secondary", "ui-btn-quiet", "ui-btn-danger", "ui-btn-compact", "ui-btn-icon", "ui-btn-loading", "ui-btn-group",
    "ui-field", "ui-field-err", "ui-label", "ui-opt", "ui-help", "ui-error", "ui-pair", "ui-check", "ui-toggle", "ui-switch", "ui-form-actions", "ui-sticky-actions", "ui-steps",
    "ui-table", "ui-row", "ui-cell-first", "ui-cell-r", "ui-cell-acts", "ui-sub", "ui-cards", "ui-card", "ui-card-l1", "ui-card-l2", "ui-card-l3", "ui-card-menu",
    "ui-badge", "ui-badge-action", "ui-badge-attention", "ui-badge-done", "ui-badge-neutral", "ui-badge-overdue",
    "ui-pdot", "ui-num", "ui-mono",
    "ui-section", "ui-section-h", "ui-stats", "ui-stat", "ui-facts", "ui-detail", "ui-detail-side", "ui-banner", "ui-banner-attention", "ui-banner-neutral", "ui-gcard",
    "ui-menu", "ui-menu-panel", "ui-menu-item", "ui-menu-danger",
    "ui-dialog", "ui-sheet", "ui-sheet-handle", "ui-toast",
    "ui-empty", "ui-tip", "ui-pagination",
    "ui-skel", "ui-bone", "ui-skel-h", "ui-skel-rows", "ui-skel-row", "ui-skel-cards", "ui-skel-card", "ui-skel-group",
    "ui-sidebar", "ui-brand", "ui-brand-mark", "ui-env", "ui-search-row", "ui-nav", "ui-nav-gap", "ui-nav-count", "ui-nav-bottom", "ui-account", "ui-avatar",
    "ui-topbar", "ui-tabbar", "ui-tabbar-ic",
    "ui-calendar", "ui-cal-h", "ui-cal-grid",
    "ui-icon", "ui-input", "ui-select", "ui-textarea"
  ],
  "hooks": ["sr-only", "skip-link", "grow", "hidden", "is-open", "is-on", "is-active", "row-menu", "row-menu-trigger", "row-menu-panel", "help-tip", "help-tip-btn", "help-tip-body", "toast", "toast-stack", "clickable-row"],
  "enforced_templates": [],
  "legacy": {},
  "enforced_stylesheets": ["App/app/static/host2.css"]
}
```

   Command: `python3 -c "import json;print(len(json.load(open('docs/design/catalog.json'))['classes']))"`. Expected: `114`.

2. Create `scripts/design_lint.py`:

```python
#!/usr/bin/env python3
"""Design v2 lint (docs/design/MASTER.md section 11.1).

Checks the templates and stylesheets named in docs/design/catalog.json:
  T1 no <style> block, style="" attribute, <link rel="stylesheet"> or <script src> in a template
  T2 no raw colour (#hex, rgb(, hsl() in a template
  T3 every class token is in the catalog, the hook allowlist, or that
     template's own "legacy" list (old classes a page brief still carries;
     the cleanup brief empties these lists)
  T4 at most one ui-btn-primary per template file (a template is one screen)
  T5 every <svg in a template comes from the icon macro (no literal <path)
  S1 stylesheet: no #hex, rgb(, hsl(, font-family:, or a literal box-shadow
  S2 stylesheet: no bare px in margin, padding, gap, border-radius, font-size except 0 and 1px
Exit 1 with one line per finding; exit 0 and print OK otherwise.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "docs" / "design" / "catalog.json"

CLASS_ATTR = re.compile(r'class="([^"]*)"')
JINJA = re.compile(r"\{\{.*?\}\}|\{%.*?%\}|\{#.*?#\}", re.S)
RAW_COLOUR = re.compile(r"#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(")
PX_PROPS = re.compile(
    r"\b(margin|padding|gap|border-radius|font-size|row-gap|column-gap)(-[a-z]+)?\s*:\s*([^;]+);"
)
BARE_PX = re.compile(r"(?<![\w-])(\d*\.?\d+)px")


def _findings_template(path: Path, text: str, catalog: dict) -> list[str]:
    out: list[str] = []
    rel = path.relative_to(ROOT)
    if "<style" in text:
        out.append(f"{rel}: T1 <style> block")
    if re.search(r'\sstyle="', text):
        out.append(f"{rel}: T1 style attribute")
    if '<link rel="stylesheet"' in text or "<script src" in text:
        out.append(f"{rel}: T1 stylesheet or script link")
    plain = JINJA.sub(" ", text)
    for m in RAW_COLOUR.finditer(plain):
        out.append(f"{rel}: T2 raw colour {m.group(0)}")
    allowed = set(catalog["classes"]) | set(catalog["hooks"]) | set(catalog.get("legacy", {}).get(str(rel), []))
    for m in CLASS_ATTR.finditer(plain):
        for token in m.group(1).split():
            if token and token not in allowed:
                out.append(f"{rel}: T3 class not in catalog: {token}")
    if plain.count("ui-btn-primary") > 1:
        out.append(f"{rel}: T4 more than one ui-btn-primary")
    if "<path" in plain:
        out.append(f"{rel}: T5 literal svg path (use the icon macro)")
    return out


def _findings_stylesheet(path: Path, text: str) -> list[str]:
    out: list[str] = []
    rel = path.relative_to(ROOT)
    body = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    for m in RAW_COLOUR.finditer(body):
        out.append(f"{rel}: S1 raw colour {m.group(0)}")
    if "font-family:" in body:
        out.append(f"{rel}: S1 font-family outside tokens")
    for m in re.finditer(r"box-shadow\s*:\s*([^;]+);", body):
        if "var(" not in m.group(1) and m.group(1).strip() != "none":
            out.append(f"{rel}: S1 literal box-shadow")
    for m in PX_PROPS.finditer(body):
        for px in BARE_PX.finditer(m.group(3)):
            if px.group(1) not in ("0", "1"):
                out.append(f"{rel}: S2 bare {px.group(0)} in {m.group(1)}")
    return out


def run(catalog_path: Path = CATALOG) -> list[str]:
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    findings: list[str] = []
    for rel in catalog["enforced_templates"]:
        p = ROOT / rel
        if not p.exists():
            findings.append(f"{rel}: enforced template missing")
            continue
        findings += _findings_template(p, p.read_text(encoding="utf-8"), catalog)
    for rel in catalog["enforced_stylesheets"]:
        p = ROOT / rel
        if p.exists():
            findings += _findings_stylesheet(p, p.read_text(encoding="utf-8"))
    return findings


def main() -> int:
    findings = run()
    for line in findings:
        print("DESIGN", line)
    print("design lint:", "FAIL" if findings else "OK")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
```

   Command: `python3 scripts/design_lint.py`. Expected: `design lint: OK`.

3. Create `App/tests/test_design_lint.py`:

```python
"""scripts/design_lint.py enforces docs/design/MASTER.md section 11.1."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "design_lint.py"

spec = importlib.util.spec_from_file_location("design_lint", SCRIPT)
design_lint = importlib.util.module_from_spec(spec)
spec.loader.exec_module(design_lint)
CATALOG = json.loads((ROOT / "docs" / "design" / "catalog.json").read_text(encoding="utf-8"))


def test_the_repository_passes_the_design_lint():
    result = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True, cwd=ROOT)
    assert result.returncode == 0, result.stdout + result.stderr


def _t(text):
    return design_lint._findings_template(ROOT / "App/app/templates/x.html", text, CATALOG)


def test_template_rules_catch_each_kind_of_drift():
    assert any("T1" in f for f in _t('<div style="margin:0"></div>'))
    assert any("T1" in f for f in _t("<style>.a{}</style>"))
    assert any("T2" in f for f in _t('<p class="ui-sub">#fff</p>'))
    assert any("T3" in f for f in _t('<p class="panel"></p>'))
    assert any("T4" in f for f in _t('<a class="ui-btn ui-btn-primary"></a><a class="ui-btn ui-btn-primary"></a>'))
    assert any("T5" in f for f in _t('<svg><path d="M0 0"/></svg>'))
    assert _t('<a class="ui-btn ui-btn-primary">{{ t("x") }}</a><span class="sr-only"></span>') == []


def test_stylesheet_rules_catch_raw_values():
    s = design_lint._findings_stylesheet
    p = ROOT / "App/app/static/host2.css"
    assert any("S1" in f for f in s(p, ".a{color:#c85a52}"))
    assert any("S1" in f for f in s(p, ".a{font-family:Arial}"))
    assert any("S2" in f for f in s(p, ".a{padding:9px 14px;}"))
    assert s(p, ".a{padding:var(--space-2) var(--control-px);border:1px solid var(--line);margin:0;}") == []
```

   Command: `cd App && .venv/bin/python -m pytest tests/test_design_lint.py -q --tb=short -x 2>&1 | tail -30`. Expected: `3 passed`.

4. In `.github/workflows/ci.yml`, replace Anchor A with:

```
      - name: Lint for runtime errors
        run: ruff check app tests tools --select E9,F63,F7,F82,F401,F841

      - name: Design lint (docs/design/MASTER.md 11.1)
        working-directory: ${{ github.workspace }}
        run: python3 scripts/design_lint.py
```

   Command: `grep -n 'Design lint' .github/workflows/ci.yml`. Expected: one line.

5. In `docs/context/test-map.md`, replace Anchor B with:

```
| Design system, catalog page, design lint | `test_design_*.py test_dev_ui*.py` |
| A module with no row | `tests/test_<module name>*.py`; none exists: `-k <module name>` |
```

   Command: `python3 scripts/context_lint.py 2>&1 | tail -3`. Expected: `context lint: OK`.

6. Commit: `git add scripts/design_lint.py docs/design/catalog.json App/tests/test_design_lint.py .github/workflows/ci.yml docs/context/test-map.md && git commit -m "0126 step 6: design lint in tests and CI"`.

## 5. Do not touch

Any template or stylesheet; `enforced_templates` stays empty in this brief; hard rules 3 and 8.

## 6. Commands

- `python3 scripts/design_lint.py` expected: `design lint: OK`.
- `cd App && .venv/bin/python -m pytest tests/test_design_lint.py tests/test_design_tokens.py -q --tb=short -x 2>&1 | tail -30` expected: `6 passed`.
- `cd App && .venv/bin/ruff check tests/test_design_lint.py --select E9,F63,F7,F82,F401,F841` expected: no output.
- `python3 scripts/context_lint.py 2>&1 | tail -3` expected: OK.

## 7. Acceptance

- [ ] The three tests pass and ruff is clean.
- [ ] `git diff df8b842 --stat` lists exactly the five files in section 3.
- [ ] CI yml has the new step directly after the ruff step.

## 8. Stop and ask

Stop, and write the report, if: an excerpt is not found; a test fails twice; you reach 25 tool calls or about 50k tokens (report as `blocked`); a new dependency seems needed; a file outside section 3 needs a change; section 5 would be touched; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0126-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with its last 5 lines, section 7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

`scripts/design_lint.py` (regexes), `.github/workflows/ci.yml`.

## Owner steps

None.
