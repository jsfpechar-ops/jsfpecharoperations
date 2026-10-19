(lang) => {
  const out = [];
  const vis = (el) => {
    const s = getComputedStyle(el);
    if (s.display === 'none' || s.visibility === 'hidden') return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  };
  const hidden = (el) => el.closest('[hidden],[aria-hidden=true],dialog:not([open]),template,.sr-only');
  const text = (el) => (el.innerText || el.textContent || '').trim();
  const name = (el) => (el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') + (el.classList.length ? '.' + [...el.classList].slice(0, 2).join('.') : '') + ' "' + text(el).replace(/\s+/g, ' ').slice(0, 30) + '"');
  const accName = (el) => {
    const al = el.getAttribute('aria-label');
    if (al && al.trim()) return al.trim();
    const lb = el.getAttribute('aria-labelledby');
    if (lb) {
      const t = lb.split(/\s+/).map((i) => document.getElementById(i)).filter(Boolean).map(text).join(' ').trim();
      if (t) return t;
    }
    if (el.labels && el.labels.length) {
      const t = [...el.labels].map(text).join(' ').trim();
      if (t) return t;
    }
    if (el.tagName === 'INPUT' && ['submit', 'button', 'reset'].includes(el.type) && el.value) return el.value;
    const t = text(el);
    if (t) return t;
    if (el.querySelector('img[alt]:not([alt=""]), svg[aria-label]')) return 'image';
    return (el.getAttribute('title') || '').trim();
  };
  // 1. document: language, title, one h1, no skipped heading levels
  const root = document.documentElement;
  if (root.lang !== lang) out.push(['html-lang', root.lang, lang]);
  if (!document.title.trim()) out.push(['title-missing']);
  const heads = [...document.querySelectorAll('h1,h2,h3,h4,h5,h6')].filter((h) => vis(h) && !h.closest('[hidden],dialog:not([open])'));
  const h1 = heads.filter((h) => h.tagName === 'H1');
  if (h1.length !== 1) out.push(['h1-count', h1.length]);
  let prev = 0;
  for (const h of heads) {
    const n = +h.tagName[1];
    if (prev && n > prev + 1) out.push(['heading-level-skipped', name(h), prev, n]);
    prev = n;
  }
  // 2. landmarks and the skip link (GOV.UK pattern: first control jumps to main)
  const mains = [...document.querySelectorAll('main,[role=main]')];
  if (mains.length !== 1) out.push(['main-count', mains.length]);
  const navs = [...document.querySelectorAll('nav')].filter(vis);
  if (navs.length > 1) for (const n of navs) if (!n.getAttribute('aria-label') && !n.getAttribute('aria-labelledby')) out.push(['nav-unlabelled', name(n)]);
  const first = [...document.querySelectorAll('a[href],button,input:not([type=hidden]),select,textarea,[tabindex]')].find((e) => !e.closest('[hidden]') && e.tabIndex >= 0);
  const target = first && first.matches('a[href^="#"]') ? document.querySelector(first.getAttribute('href')) : null;
  if (!target) out.push(['skip-link-missing', first ? name(first) : 'none']);
  // 3. every control has an accessible name; links say where they go
  const generic = ['click here', 'here', 'more', 'read more', 'link', 'klikněte zde', 'zde', 'více'];
  for (const el of document.querySelectorAll('a[href],button,input:not([type=hidden]),select,textarea,[role=button],[role=menuitem],[role=tab]')) {
    if (!vis(el) && !el.matches('.sr-only')) continue;
    if (el.closest('[hidden],dialog:not([open]),template')) continue;
    const n = accName(el);
    if (!n) out.push(['no-accessible-name', name(el)]);
    else if (el.matches('a[href]') && generic.includes(n.toLowerCase())) out.push(['generic-link-text', name(el)]);
  }
  for (const img of document.querySelectorAll('img')) if (!img.hasAttribute('alt')) out.push(['img-alt-missing', name(img)]);
  // 4. ids and aria references
  const seen = new Set();
  for (const el of document.querySelectorAll('[id]')) {
    if (seen.has(el.id)) out.push(['duplicate-id', el.id]);
    seen.add(el.id);
  }
  for (const el of document.querySelectorAll('[aria-labelledby],[aria-describedby],[aria-controls]')) {
    for (const attr of ['aria-labelledby', 'aria-describedby', 'aria-controls']) {
      for (const id of (el.getAttribute(attr) || '').split(/\s+/).filter(Boolean)) {
        if (!document.getElementById(id)) out.push(['aria-target-missing', name(el), attr, id]);
      }
    }
  }
  // 5. the open page is marked in navigation
  for (const n of navs) if (n.querySelector('a') && !n.querySelector('[aria-current]') && !n.matches('.ui-nav-bottom,.sub-tabs,[data-sub-tabs]')) out.push(['nav-no-current', name(n)]);
  // 6. colour contrast (WCAG 1.4.3): text against its real background
  const parse = (c) => {
    const m = c.match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    const p = m[1].split(/[ ,/]+/).filter(Boolean).map(Number);
    return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 };
  };
  const over = (f, b) => ({ r: f.r * f.a + b.r * (1 - f.a), g: f.g * f.a + b.g * (1 - f.a), b: f.b * f.a + b.b * (1 - f.a), a: 1 });
  const bgOf = (el) => {
    const stack = [];
    for (let a = el; a; a = a.parentElement) {
      const s = getComputedStyle(a);
      if (s.backgroundImage !== 'none') return null;
      const c = parse(s.backgroundColor);
      if (c && c.a > 0) { stack.push(c); if (c.a >= 1) break; }
    }
    let base = { r: 255, g: 255, b: 255, a: 1 };
    for (let i = stack.length - 1; i >= 0; i--) base = over(stack[i], base);
    return base;
  };
  const lum = (c) => {
    const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b);
  };
  const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
  const done = new Set();
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    const el = node.parentElement;
    if (!el || done.has(el) || !node.textContent.trim()) continue;
    done.add(el);
    if (!vis(el) || hidden(el) || el.closest(':disabled,[aria-disabled=true],script,style')) continue;
    const s = getComputedStyle(el);
    const bg = bgOf(el);
    const fg0 = parse(s.color);
    if (!bg || !fg0) continue;
    const fg = over(fg0, bg);
    const px = parseFloat(s.fontSize);
    const large = px >= 24 || (px >= 18.66 && +s.fontWeight >= 700);
    const r = ratio(fg, bg);
    if (r < (large ? 3 : 4.5) - 0.01) out.push(['contrast', name(el), r.toFixed(2), s.color, s.backgroundColor]);
  }
  // 7. target size (WCAG 2.5.8): buttons and fields are at least 24 by 24
  for (const el of document.querySelectorAll('button,.ui-btn,input:not([type=hidden]):not([type=checkbox]):not([type=radio]),select,[role=menuitem],[role=tab]')) {
    if (!vis(el) || hidden(el)) continue;
    const r = el.getBoundingClientRect();
    if (r.width < 23.5 || r.height < 23.5) out.push(['target-size-24', name(el), Math.round(r.width), Math.round(r.height)]);
  }
  return out;
}
