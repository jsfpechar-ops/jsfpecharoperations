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
    for m in re.finditer(r"font-family\s*:\s*([^;}]+)", body):
        if not m.group(1).strip().startswith("var("):
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
