"""0710: shared helpers for the v2 mockup-match and geometry tests. No tests live here."""
from __future__ import annotations

import re
from pathlib import Path

MOCKUP = Path(__file__).resolve().parents[2] / "docs/design/mockup/ubyhost-redesign-v2.html"
WIDTHS = (320, 390, 768, 1024, 1280, 1440)
DESKTOP = 1024  # box-layout checks only at widths >= DESKTOP; the phone mockup is not approved yet

STYLE_PROPS = (
    "font-size", "font-weight", "color", "background-color", "border-top-left-radius",
    "padding-top", "padding-right", "padding-bottom", "padding-left", "border-top-width",
    "border-bottom-color", "letter-spacing",
)

# accessibility: mockup coral and --ink3 fail WCAG AA; app uses darker shades (2026-11-01)
COLOR_OVERRIDES = {"rgb(212, 71, 47)": "rgb(208, 69, 45)", "rgb(138, 138, 132)": "rgb(107, 107, 101)"}

PAGES = [
    {
        "name": "overview",
        "path": "/",
        "view": "today",
        "selectors": [
            ".side", ".side .nav", ".side .nav.on", ".head h1", ".head .sub", ".head .btn",
            "main h2", ".todo .card", ".todo .ic", ".todo .t", ".todo p", ".quiet", ".card.cal",
            ".cal .cd", ".cal .cn", ".cal .bar", "main table th", "main table td", "main td small",
            "main .pill",
        ],
        "missing_ok": {},
    },
]


def mockup_url() -> str:
    return MOCKUP.resolve().as_uri()


def route_offline(page) -> None:
    """Only file: URLs load; every other request is refused."""
    page.route("**/*", lambda r: r.abort() if not r.request.url.startswith("file:") else r.continue_())


def show_view(page, key: str) -> None:
    page.evaluate(
        "k => document.querySelectorAll('.view').forEach(s => s.classList.toggle('on', s.dataset.v === k))",
        key,
    )


_COMPUTED_JS = """
([sel, props]) => {
  const vis = (e) => {
    const r = e.getBoundingClientRect();
    const s = getComputedStyle(e);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
  };
  const el = [...document.querySelectorAll(sel)].find(vis);
  if (!el) return null;
  const cs = getComputedStyle(el);
  const out = {};
  for (const p of props) out[p] = cs.getPropertyValue(p);
  return out;
}
"""


def computed(page, selector: str, props=STYLE_PROPS):
    """Computed styles of the first visible match, or None when nothing visible matches."""
    return page.evaluate(_COMPUTED_JS, [selector, list(props)])


_GEOMETRY_JS = r"""
(width) => {
  const out = [];
  const vis = (e) => {
    const r = e.getBoundingClientRect();
    const s = getComputedStyle(e);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
  };
  const label = (e) => `<${e.tagName.toLowerCase()} class="${e.getAttribute('class') || ''}">`;
  const scrollAuto = (el) => {
    for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
      const o = getComputedStyle(p).overflowX;
      if (o === 'auto' || o === 'scroll') return true;
    }
    return false;
  };
  const leafText = (e) => [...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim() !== '');

  // 1. horizontal page scroll
  const de = document.documentElement;
  if (de.scrollWidth > window.innerWidth) {
    out.push(`horizontal page scroll: scrollWidth ${de.scrollWidth} > innerWidth ${window.innerWidth}`);
  }

  // 2. elements in main that stick out of their nearest card
  const main = document.querySelector('main');
  if (main) {
    for (const el of main.querySelectorAll('*')) {
      if (!vis(el)) continue;
      const card = el.parentElement && el.parentElement.closest('.card');
      if (!card || scrollAuto(el)) continue;
      const er = el.getBoundingClientRect().right;
      const cr = card.getBoundingClientRect().right;
      if (er > cr + 1) out.push(`past card edge by ${(er - cr).toFixed(1)} px: ${label(el)}`);
    }
  }

  // 3. overlapping text inside heads, todo cards and table rows
  const texts = (c) => [...c.querySelectorAll('*')].filter(e => leafText(e) && vis(e));
  for (const c of document.querySelectorAll('.head, .todo .card, tr')) {
    if (!vis(c)) continue;
    const items = texts(c);
    for (let i = 0; i < items.length; i++) {
      for (let j = i + 1; j < items.length; j++) {
        const a = items[i], b = items[j];
        if (a.contains(b) || b.contains(a)) continue;
        const ra = a.getBoundingClientRect(), rb = b.getBoundingClientRect();
        const w = Math.min(ra.right, rb.right) - Math.max(ra.left, rb.left);
        const h = Math.min(ra.bottom, rb.bottom) - Math.max(ra.top, rb.top);
        if (w > 2 && h > 2) {
          out.push(`overlapping text in ${label(c)}: "${a.textContent.trim().slice(0, 30)}" and "${b.textContent.trim().slice(0, 30)}"`);
        }
      }
    }
  }

  // 4. tap targets
  const minT = width < 1024 ? 44 : 24;
  for (const el of document.querySelectorAll('a, button, summary, [role=button], input, select')) {
    if (!vis(el)) continue;
    if (el.tagName === 'A' && el.closest('p')) continue;  // inline link inside a sentence
    const r = el.getBoundingClientRect();
    if (r.width < minT || r.height < minT) {
      out.push(`tap target ${r.width.toFixed(0)}x${r.height.toFixed(0)} (min ${minT}): ${label(el)} "${(el.textContent || '').trim().slice(0, 24)}"`);
    }
  }

  // 5. text smaller than 12 px
  for (const el of document.querySelectorAll('body *')) {
    if (!leafText(el) || !vis(el)) continue;
    const fs = parseFloat(getComputedStyle(el).fontSize);
    if (fs < 12) out.push(`text ${fs}px: ${label(el)} "${el.textContent.trim().slice(0, 24)}"`);
  }

  // 6. exactly one h1
  const h1s = [...document.querySelectorAll('h1')].filter(vis).length;
  if (h1s !== 1) out.push(`expected one h1, found ${h1s}`);

  // 7. sidebar: 220 px column at computer width, top bar at phone width
  const side = document.querySelector('.side');
  if (!side || !vis(side)) {
    out.push('.side is not visible');
  } else {
    const r = side.getBoundingClientRect();
    if (width >= 1024 && Math.abs(r.width - 220) > 1) out.push(`.side is ${r.width.toFixed(0)} px wide, expected 220`);
    if (width < 768 && r.height > 72) out.push(`.side is ${r.height.toFixed(0)} px tall at phone width, max 72`);
  }

  // 8. todo: two columns at computer width, one column at phone width
  const cards = [...document.querySelectorAll('.todo .card')].filter(vis);
  if (cards.length >= 2 && (width >= 1024 || width < 768)) {
    const two = Math.abs(cards[1].getBoundingClientRect().left - cards[0].getBoundingClientRect().left) > 1;
    if (width >= 1024 && !two) out.push('.todo has one column at computer width, expected two');
    if (width < 768 && two) out.push('.todo has two columns at phone width, expected one');
  }

  // 9. last table row menu opens inside the viewport
  const sum = [...document.querySelectorAll('main tr:last-child details summary')].find(vis);
  if (sum) {
    const det = sum.parentElement;
    const wasOpen = det.open;
    sum.scrollIntoView({ block: 'center' });
    if (!wasOpen) sum.click();
    const menu = [...det.children].find(c => c.tagName !== 'SUMMARY');
    if (!det.open || !menu) {
      out.push('last table row menu did not open');
    } else {
      const r = menu.getBoundingClientRect();
      const iw = window.innerWidth, ih = window.innerHeight;
      if (r.left < -0.5 || r.top < -0.5 || r.right > iw + 0.5 || r.bottom > ih + 0.5) {
        out.push(`last table row menu outside the viewport: left ${r.left.toFixed(0)}, top ${r.top.toFixed(0)}, right ${r.right.toFixed(0)}, bottom ${r.bottom.toFixed(0)} (viewport ${iw}x${ih})`);
      }
    }
    if (!wasOpen && det.open) sum.click();
  }
  return out;
}
"""


def geometry_findings(page, width: int) -> list[str]:
    """One string per layout problem at this width. Empty list means the page passes."""
    return page.evaluate(_GEOMETRY_JS, width)


_NUM_RE = re.compile(r"^(-?\d+(?:\.\d+)?)(px)?$")


def _num(value: str):
    m = _NUM_RE.match(value)
    return float(m.group(1)) if m else None


def same_value(prop: str, app: str, mock: str) -> bool:
    """Numbers within 1 px (or 1 unit); colours and other text must match exactly."""
    app = "0px" if app == "normal" else app
    mock = "0px" if mock == "normal" else mock
    if app == mock:
        return True
    if app.startswith("rgb") or mock.startswith("rgb"):
        return False
    fa, fm = _num(app), _num(mock)
    return fa is not None and fm is not None and abs(fa - fm) <= 1
