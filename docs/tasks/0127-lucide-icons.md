# 0127: Vendored Lucide icons as an inline SVG macro

Status: review
Depends on: 0126 | Base commit: df8b842 | Branch: claude/project-thread-td6fpc
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

Part of [design-v2](../plans/design-v2.md). Commit each step as `0127 step k`. Never push, never open a PR.

## 1. Objective

Add `App/app/templates/_icons.html` with one `icon(name, size=20, cls='')` macro that renders a vendored Lucide icon (ISC license, lucide-static 0.552.0) as inline SVG, so no template ever draws an icon by hand or loads one from a CDN (MASTER 6.1, privacy rule). No template uses it yet.

## 2. Context

Rules: hard rule 2 (no third-party scripts or CDNs), MASTER 6.1 (icon table, stroke 1.75 nav and 2 in buttons, round caps and joins), MASTER 10.6. The path data below is copied verbatim from lucide-static 0.552.0 (ISC). Keep the `d` strings exactly.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/_icons.html` | create | the macro and the icon table |
| `App/tests/test_design_icons.py` | create | every MASTER icon name renders; unknown names fail loudly; the license line is present |
| `App/LICENSES/lucide.txt` | create | the ISC text |

No other file may change.

## 4. Steps

1. Create `App/LICENSES/lucide.txt`:

```
Lucide icons (https://lucide.dev), vendored from lucide-static 0.552.0 as inline SVG in App/app/templates/_icons.html.

ISC License

Copyright (c) for portions of Lucide are held by Cole Bemis 2013-2022 as part of Feather (MIT). All other copyright (c) for Lucide are held by Lucide Contributors 2022.

Permission to use, copy, modify, and/or distribute this software for any purpose with or without fee is hereby granted, provided that the above copyright notice and this permission notice appear in all copies.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
```

   Command: `test -f App/LICENSES/lucide.txt && echo ok`. Expected: `ok`.

2. Create `App/app/templates/_icons.html` (the whole file):

```
{#- Lucide icons, ISC license, vendored from lucide-static 0.552.0 (App/LICENSES/lucide.txt).
    docs/design/MASTER.md 6.1: the only source of icons in host templates.
    icon(name, size, cls): size 20 in navigation and rows, 16 inside buttons, 24 in the tab bar.
    Every call is aria-hidden; the visible or aria-label text lives on the control. -#}
{% set ICONS = {
  'layout-dashboard': '<rect width="7" height="9" x="3" y="3" rx="1"/><rect width="7" height="5" x="14" y="3" rx="1"/><rect width="7" height="9" x="14" y="12" rx="1"/><rect width="7" height="5" x="3" y="16" rx="1"/>',
  'calendar-days': '<path d="M8 2v4"/><path d="M16 2v4"/><rect width="18" height="18" x="3" y="4" rx="2"/><path d="M3 10h18"/><path d="M8 14h.01"/><path d="M12 14h.01"/><path d="M16 14h.01"/><path d="M8 18h.01"/><path d="M12 18h.01"/><path d="M16 18h.01"/>',
  'house': '<path d="M15 21v-8a1 1 0 0 0-1-1h-4a1 1 0 0 0-1 1v8"/><path d="M3 10a2 2 0 0 1 .709-1.528l7-5.999a2 2 0 0 1 2.582 0l7 5.999A2 2 0 0 1 21 10v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
  'receipt': '<path d="M4 2v20l2-1 2 1 2-1 2 1 2-1 2 1 2-1 2 1V2l-2 1-2-1-2 1-2-1-2 1-2-1-2 1Z"/><path d="M16 8h-6a2 2 0 1 0 0 4h4a2 2 0 1 1 0 4H8"/><path d="M12 17.5v-11"/>',
  'brush-cleaning': '<path d="m16 22-1-4"/><path d="M19 13.99a1 1 0 0 0 1-1V12a2 2 0 0 0-2-2h-3a1 1 0 0 1-1-1V4a2 2 0 0 0-4 0v5a1 1 0 0 1-1 1H6a2 2 0 0 0-2 2v.99a1 1 0 0 0 1 1"/><path d="M5 14h14l1.973 6.767A1 1 0 0 1 20 22H4a1 1 0 0 1-.973-1.233z"/><path d="m8 22 1-4"/>',
  'coins': '<circle cx="8" cy="8" r="6"/><path d="M18.09 10.37A6 6 0 1 1 10.34 18"/><path d="M7 6h1v4"/><path d="m16.71 13.88.7.71-2.82 2.82"/>',
  'settings': '<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/>',
  'key-round': '<path d="M2.586 17.414A2 2 0 0 0 2 18.828V21a1 1 0 0 0 1 1h3a1 1 0 0 0 1-1v-1a1 1 0 0 1 1-1h1a1 1 0 0 0 1-1v-1a1 1 0 0 1 1-1h.172a2 2 0 0 0 1.414-.586l.814-.814a6.5 6.5 0 1 0-4-4z"/><circle cx="16.5" cy="7.5" r=".5" fill="currentColor"/>',
  'book-open': '<path d="M12 7v14"/><path d="M3 18a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h5a4 4 0 0 1 4 4 4 4 0 0 1 4-4h5a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1h-6a3 3 0 0 0-3 3 3 3 0 0 0-3-3z"/>',
  'shield': '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/>',
  'ellipsis': '<circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/><circle cx="5" cy="12" r="1"/>',
  'ellipsis-vertical': '<circle cx="12" cy="12" r="1"/><circle cx="12" cy="5" r="1"/><circle cx="12" cy="19" r="1"/>',
  'search': '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
  'plus': '<path d="M5 12h14"/><path d="M12 5v14"/>',
  'x': '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
  'arrow-left': '<path d="m12 19-7-7 7-7"/><path d="M19 12H5"/>',
  'chevron-left': '<path d="m15 18-6-6 6-6"/>',
  'chevron-right': '<path d="m9 18 6-6-6-6"/>',
  'chevron-down': '<path d="m6 9 6 6 6-6"/>',
  'sliders-horizontal': '<path d="M21 4h-7"/><path d="M10 4H3"/><path d="M21 12h-9"/><path d="M8 12H3"/><path d="M21 20h-5"/><path d="M12 20H3"/><path d="M14 2v4"/><path d="M8 10v4"/><path d="M16 18v4"/>',
  'copy': '<rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>',
  'download': '<path d="M12 15V3"/><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5"/>',
  'send': '<path d="M14.536 21.686a.5.5 0 0 0 .937-.024l6.5-19a.496.496 0 0 0-.635-.635l-19 6.5a.5.5 0 0 0-.024.937l7.93 3.18a2 2 0 0 1 1.112 1.11z"/><path d="m21.854 2.147-10.94 10.939"/>',
  'refresh-cw': '<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/>',
  'pencil': '<path d="M21.174 6.812a1 1 0 0 0-3.986-3.987L3.842 16.174a2 2 0 0 0-.5.83l-1.321 4.352a.5.5 0 0 0 .623.622l4.353-1.32a2 2 0 0 0 .83-.497z"/><path d="m15 5 4 4"/>',
  'trash-2': '<path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/><line x1="10" x2="10" y1="11" y2="17"/><line x1="14" x2="14" y1="11" y2="17"/>',
  'circle-help': '<circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><path d="M12 17h.01"/>',
  'triangle-alert': '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
  'check': '<path d="M20 6 9 17l-5-5"/>',
  'external-link': '<path d="M15 3h6v6"/><path d="M10 14 21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>',
  'info': '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
  'menu': '<path d="M4 12h16"/><path d="M4 18h16"/><path d="M4 6h16"/>',
  'panel-left': '<rect width="18" height="18" x="3" y="3" rx="2"/><path d="M9 3v18"/>',
  'log-out': '<path d="m16 17 5-5-5-5"/><path d="M21 12H9"/><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>',
  'languages': '<path d="m5 8 6 6"/><path d="m4 14 6-6 2-3"/><path d="M2 5h12"/><path d="M7 2h1"/><path d="m22 22-5-10-5 10"/><path d="M14 18h6"/>',
  'archive': '<rect width="20" height="5" x="2" y="3" rx="1"/><path d="M4 8v11a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8"/><path d="M10 12h4"/>',
  'file-lock': '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><rect width="8" height="6" x="8" y="12" rx="1"/><path d="M15 12v-2a3 3 0 1 0-6 0v2"/>',
  'users': '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>'
} %}
{% macro icon(name, size=20, cls='') -%}
{%- if name not in ICONS %}{{ undefined_icon_name_raises_here[name] }}{% endif -%}
<svg class="ui-icon{{ ' ' ~ cls if cls }}" width="{{ size }}" height="{{ size }}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="{{ 2 if size <= 16 else 1.75 }}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false" data-icon="{{ name }}">{{ ICONS[name] | safe }}</svg>
{%- endmacro %}
```

   Note: the `undefined_icon_name_raises_here[name]` line makes Jinja raise `UndefinedError` for a name that is not in the table, so a typo fails a test instead of rendering nothing. Command: `cd App && .venv/bin/python -c "
from jinja2 import Environment, FileSystemLoader, StrictUndefined
env = Environment(loader=FileSystemLoader('app/templates'), undefined=StrictUndefined)
t = env.from_string('{% from \"_icons.html\" import icon %}{{ icon(\"house\") }}{{ icon(\"plus\", 16) }}')
html = t.render(); print(len(html), 'stroke-width=\"2\"' in html, 'stroke-width=\"1.75\"' in html)"`. Expected: a number, `True True`.

3. Create `App/tests/test_design_icons.py`:

```python
"""_icons.html: vendored Lucide icons (ISC), docs/design/MASTER.md 6.1."""
from pathlib import Path

import jinja2
import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "app"
ENV = jinja2.Environment(loader=jinja2.FileSystemLoader(str(APP_DIR / "templates")), undefined=jinja2.StrictUndefined)

MASTER_ICONS = [
    "layout-dashboard", "calendar-days", "house", "receipt", "brush-cleaning", "coins", "settings",
    "key-round", "book-open", "shield", "ellipsis", "ellipsis-vertical", "search", "plus", "x",
    "arrow-left", "chevron-left", "chevron-right", "chevron-down", "sliders-horizontal", "copy",
    "download", "send", "refresh-cw", "pencil", "trash-2", "circle-help", "triangle-alert", "check",
    "external-link", "info", "menu", "panel-left", "log-out", "languages", "archive", "file-lock", "users",
]


def _render(name, size=20):
    return ENV.from_string('{% from "_icons.html" import icon %}{{ icon(name, size) }}').render(name=name, size=size)


@pytest.mark.parametrize("name", MASTER_ICONS)
def test_every_master_icon_renders_inline_and_hidden(name):
    html = _render(name)
    assert html.startswith("<svg class=\"ui-icon\"")
    assert f'data-icon="{name}"' in html
    assert 'aria-hidden="true"' in html
    assert 'viewBox="0 0 24 24"' in html
    assert "http" not in html


def test_button_size_uses_stroke_two_and_nav_size_uses_one_seventy_five():
    assert 'stroke-width="2"' in _render("plus", 16)
    assert 'stroke-width="1.75"' in _render("plus", 20)


def test_an_unknown_icon_name_fails_instead_of_rendering_nothing():
    with pytest.raises(jinja2.exceptions.UndefinedError):
        _render("broom")


def test_the_license_is_vendored():
    text = (APP_DIR.parent / "LICENSES" / "lucide.txt").read_text(encoding="utf-8")
    assert "ISC License" in text and "lucide-static 0.552.0" in text
    assert "ISC license" in (APP_DIR / "templates" / "_icons.html").read_text(encoding="utf-8")
```

   Command: `cd App && .venv/bin/python -m pytest tests/test_design_icons.py -q --tb=short -x 2>&1 | tail -30`. Expected: `41 passed`.

4. Commit: `git add App/app/templates/_icons.html App/tests/test_design_icons.py App/LICENSES/lucide.txt && git commit -m "0127 step 4: vendored Lucide icon macro"`.

## 5. Do not touch

`_components.html` (its `nav_icon` stays until 0141), `base.html`, any stylesheet; hard rules 2, 3, 8.

## 6. Commands

- `cd App && .venv/bin/python -m pytest tests/test_design_icons.py tests/test_design_lint.py -q --tb=short -x 2>&1 | tail -30` expected: `44 passed`.
- `python3 scripts/design_lint.py` expected: OK.

## 7. Acceptance

- [ ] 41 icon tests pass; an unknown name raises.
- [ ] `grep -c "http" App/app/templates/_icons.html` prints `1` (only the lucide.dev mention inside the comment of LICENSES is outside; the macro file has the comment line only).
- [ ] `git diff df8b842 --stat` lists exactly the three files in section 3.

## 8. Stop and ask

Stop, and write the report, if: an excerpt is not found; a test fails twice; you reach 25 tool calls or about 50k tokens (report as `blocked`); a new dependency seems needed; a file outside section 3 needs a change; section 5 would be touched; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0127-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with its last 5 lines, section 7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

`App/app/templates/_icons.html` (path data copied verbatim).

## Owner steps

None.
