"""0146: one skeleton system on host pages, dead layout macros removed."""
from __future__ import annotations

import glob
import re

REMOVED = ("list_page_header", "list_toolbar", "sub_tabs", "breadcrumb", "row_reporting_actions", "list_section_heading")


def test_no_c05_markup_in_host_templates():
    for path in glob.glob("app/templates/*.html"):
        assert "c05" not in open(path, encoding="utf-8").read(), path


def test_removed_macros_are_neither_defined_nor_called():
    components = open("app/templates/_components.html", encoding="utf-8").read()
    pages = "".join(open(p, encoding="utf-8").read() for p in glob.glob("app/templates/**/*.html", recursive=True) if not p.endswith("_components.html"))
    for name in REMOVED:
        assert not re.search(r"\{%\s*macro\s+" + name + r"\(", components), name
        assert name + "(" not in pages, name
