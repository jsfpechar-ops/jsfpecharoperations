"""0710: shared helpers for the v2 mockup-match and geometry tests. No tests live here."""
from __future__ import annotations

import re
from pathlib import Path

MOCKUP = Path(__file__).resolve().parents[2] / "docs/design/mockup/ubyhost-redesign-v2.html"
WIDTHS = (320, 390, 768, 1024, 1280, 1440)
DESKTOP = 1024  # box-layout checks only at widths >= DESKTOP; the phone mockup is not approved yet
PHONE_MOCKUP = Path(__file__).resolve().parents[2] / "docs/design/mockup/ubyhost-phone-v1.html"
PHONE_WIDTHS = (320, 390)

STYLE_PROPS = (
    "font-size", "font-weight", "color", "background-color", "border-top-left-radius",
    "padding-top", "padding-right", "padding-bottom", "padding-left", "border-top-width",
    "border-bottom-color", "letter-spacing",
)

# accessibility: mockup coral and --ink3 fail WCAG AA; app uses darker shades (2026-11-01)
COLOR_OVERRIDES = {"rgb(212, 71, 47)": "rgb(208, 69, 45)", "rgb(138, 138, 132)": "rgb(107, 107, 101)"}
# accessibility (AA contrast, 12 px minimum), 2026-11-01
SELECTOR_OVERRIDES = {
    ".side .nav": {"color": "rgb(184, 61, 40)", "border-bottom-color": "rgb(184, 61, 40)"},
    ".side .nav.on": {"color": "rgb(184, 61, 40)", "border-bottom-color": "rgb(184, 61, 40)"},
    ".cal .cd": {"font-size": "12px", "color": "rgb(184, 61, 40)", "border-bottom-color": "rgb(184, 61, 40)"},
    # demo Dnes table has one row, which is also the last row: the app draws no bottom border (tr:last-child rule), 2026-11-01
    "main tbody tr:first-child td": {"border-bottom-color": "rgb(28, 28, 26)"},
    # phone tab labels: the 12 px minimum text rule wins over the mockup's 11 px (orchestrator decision, 0718)
    ".tab": {"font-size": "12px"},
    ".tab:not(.on)": {"font-size": "12px"},
    ".tab.on": {"font-size": "12px"},
}
# style-compared only at computer width (phone design pending)
DESKTOP_ONLY = {".side", ".side .nav", ".side .nav.on"}
# calendar bars are 28 px tall: a dense 14-day timeline; WCAG 2.5.8 needs 24 px, and every stay is also a full-size row in the Dnes table and the stays list
TAP_EXEMPT_BELOW_DESKTOP = {".cal .bar": "dense 14-day timeline; 28 px meets WCAG 2.5.8 (24 px); every stay is also a full-size row in the Dnes table and the stays list"}


# app selector -> mockup selector at phone widths (the phone mockup calls the action bar .bar)
SELECTOR_ALIASES = {".actbar": ".bar"}
BOX_PROPS = ("width", "height", "margin-top", "margin-right", "margin-bottom", "margin-left")


def expected_value(selector: str, prop: str, mock_value: str) -> str:
    """Value the app must have: the override when the selector and property are listed, else the mockup value."""
    override = SELECTOR_OVERRIDES.get(selector, {}).get(prop)
    if override is not None:
        return override
    return COLOR_OVERRIDES.get(mock_value, mock_value)

PAGES = [
    {
        "name": "overview",
        "path": "/",
        "view": "today",
        "phone_view": "dnes",
        "phone_selectors": [".tabs", ".tab", ".tab.on"],
        "selectors": [
            ".side", ".side .nav", ".side .nav.on", ".head h1", ".head .sub", ".head .btn",
            "main h2", ".todo .card", ".todo .ic", ".todo .t", ".todo p", ".quiet", ".card.cal",
            ".cal .cd", ".cal .cn", ".cal .bar.b-ok", ".cal .bar.b-warn", "main table th", "main tbody tr:first-child td", "main td small",
            "main .pill.p-ok", "main .pill.p-warn",
        ],
        "missing_ok": {
            ".cal .bar.b-ok": "demo data has no confirmed stay in the 14-day window; the tone follows the data",
            "main .pill.p-ok": "tone depends on data: the demo overview has no reported stay",
        },
    },
    {
        "name": "menu",
        "path": "/menu",
        "view": None,  # no desktop mockup screen: the Menu page is compared at phone widths only
        "selectors": [],
        "phone_view": "menu",
        "phone_selectors": [".tabs", ".tab:not(.on)", ".tab.on", ".big", ".card.me", ".list .row", ".row .t b", ".row .t small"],
        "missing_ok": {".row .t small": "menu rows have no subtitle yet: the mockup subtitles are demo copy and no approved menu copy exists (owner decision, 0718)"},
    },
    {
        "name": "stays",
        "path": "/reservations?range=all",
        "view": "stays",
        "phone_view": "pobyty",
        "selectors": [
            ".head h1", ".head .btn", ".head .btn.ghost", ".chips .chip", ".chip.on",
            "main table th", "main table td", "main td small", "main .pill",
        ],
        "phone_selectors": [
            ".tabs", ".tab.on", ".top .round", ".big", ".chips .chip", ".chip.on", ".grp",
            ".list .row", ".row .av", ".row .t b", ".row .t small", ".row .pill", ".list .link",
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
(args) => {
  const [width, exempt] = args;
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
  // visually hidden (sr-only, clipped, or 1 px absolute): not a tap target and not visible text
  const hiddenVisually = (e) => {
    if (e.classList.contains('sr-only') || (e.closest && e.closest('.sr-only'))) return true;
    const s = getComputedStyle(e);
    const r = e.getBoundingClientRect();
    if (s.clipPath && s.clipPath.startsWith('inset(50%')) return true;
    if (s.clip && s.clip !== 'auto' && /rect\(\s*0px/.test(s.clip)) return true;
    return s.position === 'absolute' && (r.width <= 1 || r.height <= 1);
  };

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
  const phoneMin = width < 1024 ? 44 : 24;
  for (const el of document.querySelectorAll('a, button, summary, [role=button], input, select')) {
    if (!vis(el)) continue;
    if (el.tagName === 'A' && el.closest('p')) continue;  // inline link inside a sentence
    const r = el.getBoundingClientRect();
    if (r.width <= 1 || r.height <= 1) continue;  // visually hidden (e.g. skip link), not a tap target
    if (hiddenVisually(el)) continue;
    const minT = exempt.some((s) => el.matches(s)) ? 24 : phoneMin;
    if (r.width < minT || r.height < minT) {
      out.push(`tap target ${r.width.toFixed(0)}x${r.height.toFixed(0)} (min ${minT}): ${label(el)} "${(el.textContent || '').trim().slice(0, 24)}"`);
    }
  }

  // 5. text smaller than 12 px
  for (const el of document.querySelectorAll('body *')) {
    if (!leafText(el) || !vis(el) || hiddenVisually(el)) continue;
    const fs = parseFloat(getComputedStyle(el).fontSize);
    if (fs < 12) out.push(`text ${fs}px: ${label(el)} "${el.textContent.trim().slice(0, 24)}"`);
  }

  // 6. exactly one h1
  const h1s = [...document.querySelectorAll('h1')].filter(vis).length;
  if (h1s !== 1) out.push(`expected one h1, found ${h1s}`);

  // 7. sidebar: 220 px column at computer width; below 1024 px the bottom tab bar replaces it (0718)
  const side = document.querySelector('.side');
  if (width >= 1024) {
    if (!side || !vis(side)) {
      out.push('.side is not visible');
    } else {
      const r = side.getBoundingClientRect();
      if (Math.abs(r.width - 220) > 1) out.push(`.side is ${r.width.toFixed(0)} px wide, expected 220`);
    }
  } else {
    if (side && vis(side)) out.push('.side is visible below 1024 px, expected the tab bar');
    const tabs = document.querySelector('.tabs');
    const tabList = tabs ? [...tabs.querySelectorAll('.tab')] : [];
    if (!tabs || !vis(tabs)) {
      out.push('.tabs is not visible below 1024 px');
    } else {
      const tr = tabs.getBoundingClientRect();
      if (Math.abs(tr.bottom - window.innerHeight) > 1) out.push(`.tabs bottom ${tr.bottom.toFixed(0)} is not the viewport bottom ${window.innerHeight}`);
      if (tabList.length !== 5) out.push(`.tabs has ${tabList.length} tabs, expected 5`);
      for (const t of tabList) {
        const r = t.getBoundingClientRect();
        if (r.width < 44 || r.height < 44) out.push(`tab ${r.width.toFixed(0)}x${r.height.toFixed(0)} (min 44): "${t.textContent.trim().slice(0, 24)}"`);
      }
      // scrolled to the bottom, no content of main may sit under the tab bar
      const mainEl = document.querySelector('main');
      if (mainEl) {
        window.scrollTo(0, 1e9);
        const bottoms = [...mainEl.querySelectorAll('*')].filter(vis).map(e => e.getBoundingClientRect().bottom);
        const lowest = bottoms.length ? Math.max(...bottoms) : 0;
        if (lowest > tr.top + 1) out.push(`main content ends at ${lowest.toFixed(0)} under the tab bar (top ${tr.top.toFixed(0)})`);
        window.scrollTo(0, 0);
      }
    }
  }

  // 8. todo: two columns at computer width (>= 1024 px), one column below 1024 px
  const cards = [...document.querySelectorAll('.todo .card')].filter(vis);
  if (cards.length >= 2) {
    const two = Math.abs(cards[1].getBoundingClientRect().left - cards[0].getBoundingClientRect().left) > 1;
    if (width >= 1024 && !two) out.push('.todo has one column at computer width, expected two');
    if (width < 1024 && two) out.push('.todo has two columns below 1024 px, expected one');
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
    return page.evaluate(_GEOMETRY_JS, [width, list(TAP_EXEMPT_BELOW_DESKTOP)])


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


def phone_url() -> str:
    return PHONE_MOCKUP.resolve().as_uri()


def show_phone_screen(page, key: str) -> None:
    """Shows one screen of the phone mockup (its screens are section.scr with data-s keys)."""
    page.evaluate(
        "k => document.querySelectorAll('.scr').forEach(s => s.classList.toggle('on', s.dataset.s === k))",
        key,
    )


def box_diffs(selector: str, app: dict, mock: dict, width: int) -> list[str]:
    """Phone box metrics: width within 2 px, height and margins within 1 px. Values that are not px are skipped."""
    out = []
    for prop in BOX_PROPS:
        a, m = _num(app[prop]), _num(mock[prop])
        if a is None or m is None:
            continue
        tol = 2 if prop == "width" else 1
        if abs(a - m) > tol:
            out.append(f"{selector} {prop} at {width} px: app={app[prop]} mockup={mock[prop]}")
    return out
