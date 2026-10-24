import json
import os
import tempfile
from pathlib import Path
from app import auth, cleaning
from tests.test_host_stay_actions_browser import _browser, stay_actions_base, stay_actions_host, sync_api  # noqa: F401
from tests.test_lock_navigation_browser import world, _reset  # noqa: F401
from tests.test_cleaning_browser import origin, browser_context, loaded  # noqa: F401
from tests.test_cleaning import workspace  # noqa: F401

# Screenshots go to the CI artifact folder (or a temp dir), never a machine-specific path.
OUT = Path(os.environ.get("UBYHOST_SHOTS_DIR", tempfile.gettempdir())) / "0199-phone-geometry"
FAILS = []
MEASURE = """() => {
  const R = el => el.getBoundingClientRect();
  const vis = el => !!el && R(el).width > 0;
  const tl = (el, skip) => { const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT); let n;
    while ((n = w.nextNode())) { if (n.textContent.trim() && !(skip && n.parentElement && n.parentElement.closest(skip))) { const r = document.createRange(); r.selectNodeContents(n); const b = r.getBoundingClientRect(); if (b.width) return b.left; } } return null; };
  const lines = el => { const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT); const t = []; let n;
    while ((n = w.nextNode())) { if (!n.textContent.trim()) continue; let skip = false;
      for (let e = n.parentElement; e && el.contains(e); e = e.parentElement) { const s = getComputedStyle(e);
        if (e.getAttribute('aria-hidden') === 'true' || s.visibility === 'hidden' || s.opacity === '0' || (e !== el && (R(e).width === 0 || R(e).height === 0))) { skip = true; break; } }
      if (skip) continue;
      const r = document.createRange(); r.selectNodeContents(n);
      for (const b of r.getClientRects()) if (b.width && b.height) t.push(b.top); }
    const starts = []; for (const y of t.sort((a, b) => a - b)) if (!starts.length || y - starts[starts.length - 1] > 4) starts.push(y);
    return starts.length; };
  const q = s => document.querySelector(s);
  const f = v => (v === null || v === undefined) ? null : Math.round(v * 10) / 10;
  const cs = (el, p) => getComputedStyle(el)[p];
  const out = { vw: innerWidth, sw: document.documentElement.scrollWidth };
  const panel = q('.host-stay-detail .stay-command-panel'), gh = q('#guests .ui-section-h h2');
  const main = q('.host-stay-detail .stay-command-panel .stay-command-main');
  // badges align by their box, text by its text
  if (main && gh) out.A = f(R(main).left + parseFloat(cs(main, 'paddingLeft')) - tl(gh));
  const note = q('.stay-command-panel .stay-command-note'); if (note && gh) out.An = f(tl(note) - tl(gh));
  if (q('.stay-command-panel .journey') && main) out.Aj = f(R(q('.stay-command-panel .journey')).left - R(q('.stay-command-panel .stay-command-main')).left);
  const act = q('.host-stay-detail .stay-command-actions');
  if (act) {
    const btns = [...act.querySelectorAll('.ui-btn,.btn,button,a')].filter(vis);
    out.Bh = btns.map(b => f(R(b).height));
    out.Bwrap = btns.filter(b => lines(b) > 1).map(b => b.textContent.trim().slice(0, 18));
    out.Bw = f(R(act).width);
    out.Bkids = [...act.children].filter(vis).map(k => [f(R(k).left - R(act).left), f(R(k).width), f(R(k).top - R(act).top)]);
    const menu = act.querySelector('.row-menu-trigger');
    if (menu && vis(menu)) out.Bmenu = [f(R(menu).width), f(R(menu).height), f(R(act).right - R(menu).right)];
  }
  const gf = q('#guests .ui-section-h .ui-form-actions'), gsec = q('#guests .ui-section-h');
  if (gf && gsec) out.C = { group: f(R(gf).width), sec: f(R(gsec).width),
    kids: [...gf.children].filter(vis).map(k => [f(R(k).width), f(R(k).height)]),
    wrap: [...gf.querySelectorAll('a,button')].filter(b => vis(b) && lines(b) > 1).length };
  const fa = q('#stay-quick-edit form.settings-grid > .ui-form-actions');
  if (fa) out.D = [f(R(fa.querySelector('.ui-btn,button')).width), f(R(fa).width)];
  const ib = q('#stay-quick-edit .inline-edit-bar button[type=submit]');
  if (ib) out.Dinner = [f(R(ib).width), f(R(ib.parentElement).width)];
  const nav = q('.property-settings-nav');
  if (nav) { const chips = [...nav.querySelectorAll('a')].filter(vis);
    out.E = { rows: new Set(chips.map(c => Math.round(R(c).top))).size, chipH: chips.map(c => f(R(c).height)),
      navR: f(R(nav).right), laneR: f(R(nav.parentElement).right), navW: f(R(nav).width), scrollW: nav.scrollWidth,
      clientW: nav.clientWidth, ovx: cs(nav, 'overflowX') }; }
  const intro = q('#settings-lock .property-group-intro'), door = q('#door-code'), lg = q('#settings-lock'), acc = q('#settings-lock-account');
  // 97ac958 put the door-code window card between the intro and the panel: each gap in the stack must stay small.
  const dwin = q('#settings-lock [data-door-code-window]');
  if (intro && door) out.F = dwin ? f(Math.max(R(dwin).top - R(intro).bottom, R(door).top - R(dwin).bottom)) : f(R(door).top - R(intro).bottom);
  if (intro && lg && acc) out.Fd = { lgT: f(R(lg).top), introB: f(R(intro).bottom), lgB: f(R(lg).bottom), accT: f(R(acc).top),
    rowGap: cs(acc.parentElement, 'rowGap'), lgMB: cs(lg, 'marginBottom'), lgPB: cs(lg, 'paddingBottom'), accMT: cs(acc, 'marginTop'),
    accPT: cs(acc, 'paddingTop'), introMB: cs(intro, 'marginBottom'), introH: f(R(intro).height) };
  const h1 = q('.cleaning-page h1, .cleaning-page h2'), cal = q('#calendar');
  if (h1 && cal) out.G = [f(R(cal).left), f(R(h1).left)];
  const navB = [...document.querySelectorAll('.cleaning-page .dashboard-calendar [data-cal-prev],.cleaning-page .dashboard-calendar [data-cal-today],.cleaning-page .dashboard-calendar [data-cal-next]')].filter(vis);
  if (navB.length) out.H = navB.map(b => [cs(b, 'borderTopLeftRadius'), f(R(b).height)]);
  const sel = q('.cleaning-page .dashboard-calendar .cal-heading select, .cleaning-page .dashboard-calendar .cal-toolbar select');
  if (sel) out.Hsel = cs(sel, 'borderTopLeftRadius');
  if (panel && gh) { const pe = panel.firstElementChild, par = panel.parentElement;
    out.Ap = { pad: cs(panel, 'paddingLeft'), bl: cs(panel, 'borderLeftWidth'), pL: f(R(panel).left), childL: f(R(pe).left), parL: f(R(par).left), parPad: cs(par, 'paddingLeft'), parBL: cs(par, 'borderLeftWidth'), gsecPad: cs(gh.closest('.ui-section'), 'paddingLeft'), gsecL: f(R(gh.closest('.ui-section')).left), h2L: f(R(gh).left), mainPad: cs(q('#main-content'), 'paddingLeft') }; }
  if (intro && door) out.Fp = { dmt: cs(door, 'marginTop'), dpt: cs(door, 'paddingTop'), dcls: door.className.slice(0, 80), kidT: f(R(door.firstElementChild).top - R(door).top), kidMT: cs(door.firstElementChild, 'marginTop'), accDisp: getComputedStyle(acc).display, accGridCol: cs(acc, 'gridColumnStart'), navDisp: cs(q('.property-settings'), 'display'), gridRows: cs(q('.property-settings'), 'gridTemplateRows').slice(0, 80) };
  if (cal && h1) out.Gp = { calML: cs(cal, 'marginLeft'), calPL: cs(cal, 'paddingLeft'), calPar: f(R(cal.parentElement).left), calParPL: cs(cal.parentElement, 'paddingLeft'), h1L: f(R(h1).left), h1PL: cs(h1, 'paddingLeft'), h1Par: f(R(h1.parentElement).left), h1ParPL: cs(h1.parentElement, 'paddingLeft') };
  if (panel) out.Ad = [...panel.querySelectorAll('*')].filter(vis).slice(0, 8).map(e => [e.tagName, String(e.className).slice(0, 28), f(R(e).left), f(R(e).width)]);
  out.Gt = [...document.querySelectorAll('.cleaning-page a, .cleaning-page button')].filter(vis).slice(0, 8).map(e => [e.textContent.trim().slice(0, 16), f(R(e).left)]);
  const ch = q('#calendar .cal-heading'); if (ch) out.Gt2 = [f(tl(ch)), f(R(ch).left)];
  if (h1) out.Gt3 = f(tl(h1));
  out.bad = [...document.querySelectorAll('.ui-btn,.btn,button')].filter(b => vis(b) && (R(b).height > 46 || lines(b) > 1))
    .map(b => b.textContent.trim().slice(0, 20)).slice(0, 6);
  return out;
}"""

PHONE = (360, 390)


def _measure(page, url, name, shot=True):
    page.goto(url)
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(200)
    m = page.evaluate(MEASURE)
    if shot:
        page.screenshot(path=str(OUT / f"{name}.png"), full_page=True)
    print("M", name, json.dumps(m, ensure_ascii=False))
    return m


def _flush():
    bad = [msg for ok, msg in FAILS if not ok]
    FAILS.clear()
    assert bad == [], "\n".join(bad)


def _ok(m, name):
    FAILS.append((m["sw"] <= m["vw"], f"{name}: page scrolls horizontally {m['sw']} > {m['vw']}"))


def _check_stay(m, name):
    _ok(m, name)
    if "A" in m:
        FAILS.append((abs(m["A"]) <= 1, f"{name}: A panel content offset {m['A']}"))
    if m.get("Aj") is not None:
        FAILS.append((abs(m["Aj"]) <= 1, f"{name}: A journey offset {m['Aj']}"))
    if m.get("An") is not None:
        FAILS.append((abs(m["An"]) <= 1, f"{name}: A note text offset {m['An']}"))
    if "Bh" in m:
        FAILS.append((m["Bwrap"] == [], f"{name}: B wrapped labels {m['Bwrap']}"))
        FAILS.append((all(43 <= h <= 45 for h in m["Bh"]), f"{name}: B heights {m['Bh']}"))
        kids = m["Bkids"]
        if len(kids) >= 2:
            FAILS.append((kids[0][1] >= m["Bw"] - 2, f"{name}: B first child not full row {kids}"))
    if "Bmenu" in m:
        FAILS.append((m["Bmenu"][0] == 44 and m["Bmenu"][1] == 44 and m["Bmenu"][2] <= 1, f"{name}: B menu {m['Bmenu']}"))
    if "C" in m:
        FAILS.append((m["C"]["group"] >= m["C"]["sec"] - 2, f"{name}: C group not full width {m['C']}"))
        FAILS.append((m["C"]["wrap"] == 0, f"{name}: C wrapped"))
        kids = m["C"]["kids"]
        FAILS.append((all(abs(k[0] - kids[0][0]) <= 1 and 43 <= k[1] <= 45 for k in kids), f"{name}: C kids {kids}"))
    if "D" in m:
        FAILS.append((abs(m["D"][0] - m["D"][1]) <= 2, f"{name}: D bottom save not full width {m['D']}"))


def _check_lock(m, name):
    _ok(m, name)
    FAILS.append((m["E"]["rows"] <= 3 and m["E"]["scrollW"] <= m["E"]["clientW"] + 1, f"{name}: E chips hidden off-screen {m['E']}"))
    FAILS.append((m["E"]["navR"] <= m["E"]["laneR"] + 1, f"{name}: E nav leaves lane {m['E']}"))
    FAILS.append((m["F"] is not None and m["F"] <= 24, f"{name}: F gap {m['F']} {m.get('Fd')}"))


def test_stay(stay_actions_host, stay_actions_base):
    OUT.mkdir(parents=True, exist_ok=True)
    cookie = stay_actions_host["client"].cookies.get(auth.SESSION_COOKIE)
    ids = stay_actions_host["ids"]
    with sync_api.sync_playwright() as p:
        b = _browser(p)
        c = b.new_context(viewport={"width": 390, "height": 844})
        c.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": stay_actions_base + "/"}])
        pg = c.new_page()
        for w in PHONE:
            pg.set_viewport_size({"width": w, "height": 844})
            for lang in ("en", "cs", "vi"):
                for key in ("incomplete", "ready", "failed"):
                    name = f"stay-{key}-{lang}-{w}"
                    _check_stay(_measure(pg, f"{stay_actions_base}/reservations/{ids[key]}?lang={lang}", name), name)
        pg.set_viewport_size({"width": 1280, "height": 900})
        _measure(pg, f"{stay_actions_base}/reservations/{ids['ready']}?lang=en", "desk-stay-ready-en-1280", shot=False)
        b.close()
    _flush()


def test_lock(world):
    _reset(world)
    with sync_api.sync_playwright() as p:
        b = _browser(p)
        c = b.new_context(viewport={"width": 390, "height": 844})
        c.add_cookies([{"name": auth.SESSION_COOKIE, "value": world["cookie"], "url": world["base"] + "/"}])
        pg = c.new_page()
        for w in PHONE:
            pg.set_viewport_size({"width": w, "height": 844})
            for lang in ("en", "cs", "vi"):
                name = f"lock-{lang}-{w}"
                _check_lock(_measure(pg, f"{world['base']}/apartments/{world['apartment']}?view=settings&section=lock&lang={lang}", name), name)
                _measure(pg, f"{world['base']}/apartments?lang={lang}", f"properties-{lang}-{w}", shot=True)
        pg.set_viewport_size({"width": 1280, "height": 900})
        _measure(pg, f"{world['base']}/apartments/{world['apartment']}?view=settings&section=lock&lang=en", "desk-lock-en-1280", shot=False)
        b.close()
    _flush()


def test_cleaning(workspace, origin):
    _, token = cleaning.new_share(workspace["owner"], [workspace["home"]])
    with sync_api.sync_playwright() as p:
        for w in PHONE:
            b, c = browser_context(p, workspace, origin, width=w)
            pg = c.new_page()
            for lang in ("en", "cs", "vi"):
                name = f"cleaning-host-{lang}-{w}"
                m = _measure(pg, f"{origin}/cleaning?lang={lang}", name)
                _ok(m, name)
                if token:
                    name = f"cleaning-shared-{lang}-{w}"
                    m = _measure(pg, f"{origin}/cleaning/shared/{token}?lang={lang}", name)
                    _ok(m, name)
                    FAILS.append((all(r == "8px" for r, h in m["H"]), f"{name}: H nav {m['H']}"))
                    FAILS.append((m["Hsel"] == "8px", f"{name}: H select radius {m['Hsel']}"))
            b.close()
        b.close()
    _flush()
