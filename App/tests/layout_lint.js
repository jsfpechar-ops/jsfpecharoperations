// Layout lint (0900): catches what overlap/gap tests cannot see. Runs in the page.
// Returns a list of findings: [rule, element, detail...]. Used by
// test_layout_lint_browser.py on every host page at seven widths.
(() => {
  const out = [];
  const vw = window.innerWidth;
  const vis = (el) => {
    const r = el.getBoundingClientRect();
    if (r.width <= 0 || r.height <= 0) return false;
    for (let a = el; a && a !== document.documentElement; a = a.parentElement) {
      const cs = getComputedStyle(a);
      if (cs.display === 'none' || cs.visibility === 'hidden' || +cs.opacity === 0) return false;
      if (a.hidden) return false;
      if (a.tagName === 'DIALOG' && !a.open) return false;
    }
    return true;
  };
  const skipZone = (el) => el.closest('[role=menu],.row-menu-panel,.sr-only,.visually-hidden,[aria-hidden=true],script,style,noscript,template,svg,.skeleton,[data-lint-ignore],details:not([open]) > :not(summary)');
  const name = (el) => (el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') +
    (el.classList.length ? '.' + [...el.classList].slice(0, 3).join('.') : '') +
    ' "' + (el.textContent || el.getAttribute('aria-label') || '').trim().replace(/\s+/g, ' ').slice(0, 28) + '"');
  const words = (t) => t.trim().split(/\s+/).filter(Boolean);
  const own = (el) => [...el.childNodes].filter((n) => n.nodeType === 3).map((n) => n.textContent).join(' ').replace(/\s+/g, ' ').trim();
  const seen = new Set();
  const add = (rule, el, ...detail) => {
    const key = rule + '|' + name(el);
    if (seen.has(key)) return;
    seen.add(key);
    out.push([rule, name(el), ...detail]);
  };
  const textLines = (el) => {
    const tops = [];
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    for (let n; (n = walker.nextNode());) {
      if (!n.textContent.trim()) continue;
      const p = n.parentElement;
      if (p && (p.closest('svg,[role=menu],.sr-only') || !vis(p))) continue;
      const range = document.createRange();
      range.selectNodeContents(n);
      for (const r of range.getClientRects()) {
        if (r.width < 1 || r.height < 1) continue;
        if (!tops.some((t) => Math.abs(t - r.top) < r.height * 0.5)) tops.push(r.top);
      }
    }
    return tops.length;
  };

  const all = [...document.body.querySelectorAll('*')].filter((el) => !skipZone(el) && vis(el) && !el.matches('.skip-link') && el.getBoundingClientRect().width > 3);
  const leaves = all.filter((el) => own(el).length > 0);

  // 1. Word-per-line wrapping and strips too narrow to read.
  for (const el of leaves) {
    const s = getComputedStyle(el);
    if (s.display === 'inline') continue;
    const text = (el.innerText || own(el)).replace(/\s+/g, ' ').trim();
    const w = words(text);
    if (el.querySelector('input,select,textarea,button')) continue;
    const lines = textLines(el);
    const r = el.getBoundingClientRect();
    const em = parseFloat(s.fontSize) || 14;
    if (w.length >= 3 && lines >= 3 && w.length / lines < 1.4) add('word-per-line', el, w.length + ' words on ' + lines + ' lines', Math.round(r.width) + 'px wide');
    if (lines >= 3 && w.length >= 2 && r.width < em * 4.2 && text.length >= 8) add('too-narrow', el, Math.round(r.width) + 'px for "' + text.slice(0, 20) + '"');
  }

  // 2. A label squeezed beside a wider control, or a badge stranded far from its label.
  const isCtl = (el) => el.matches('button,a.btn,a.ui-btn,.btn,.ui-btn,input:not([type=hidden]),select,textarea');
  const isBadge = (el, r) => {
    const t = (el.innerText || '').trim();
    return el.matches('[class*=badge],[class*=step-num],[class*=num]') || (t.length > 0 && t.length <= 3 && r.width <= 44 && r.height <= 44);
  };
  const help0 = (el) => el.matches('.help-tip,[class*=help]');
  const rows = all.filter((el) => ['flex', 'inline-flex', 'grid'].includes(getComputedStyle(el).display));
  for (const row of rows) {
    const kids = [...row.children].filter((c) => vis(c) && !skipZone(c));
    if (kids.length < 2 || kids.length > 6) continue;
    const rects = kids.map((k) => k.getBoundingClientRect());
    const mid = (r) => (r.top + r.bottom) / 2;
    for (let i = 0; i < kids.length; i++) {
      const k = kids[i];
      if (isCtl(k) || isBadge(k, rects[i]) || words((k.innerText || '')).length < 2) continue;
      const lines = textLines(k);
      const wider = kids.some((o, j) => j !== i && isCtl(o) && Math.abs(mid(rects[j]) - mid(rects[i])) < rects[i].height / 2 + 4 && textLines(o) <= 1 && rects[j].width > rects[i].width * 1.2);
      if (lines >= 3 && wider) add('label-squeezed', k, lines + ' lines beside a wider control', Math.round(rects[i].width) + 'px');
    }
    for (let i = 0; i < kids.length; i++) {
      const b = kids[i], br = rects[i];
      if (!isBadge(b, br) || isCtl(b)) continue;
      for (let j = 0; j < kids.length; j++) {
        if (i === j || isCtl(kids[j]) || isBadge(kids[j], rects[j]) || !(kids[j].innerText || '').trim()) continue;
        const or = rects[j];
        if (Math.abs(mid(or) - mid(br)) > Math.max(or.height, br.height) / 2 + 2) continue;
        const range = document.createRange();
        range.selectNodeContents(kids[j]);
        const tr = range.getBoundingClientRect();
        const gap = help0(b) ? (or.left >= br.right ? or.left - br.right : br.left >= or.right ? br.left - or.right : 0) : (tr.left >= br.right ? tr.left - br.right : br.left >= tr.right ? br.left - tr.right : 0);
        const help = b.matches('.help-tip,[class*=help]');
        const badgeFirst = br.left < tr.left;
        // Status badges may sit at the far end on purpose; a help "?" or a leading step badge may not float away.
        if (gap > 24 && (help || badgeFirst)) {
          // a help "?" belongs to the nearest text beside it, not to a label further left
          const nearest = Math.min(...kids.filter((o, q) => q !== i && (o.innerText || '').trim() && !isCtl(o)).map((o) => { const t2 = o.getBoundingClientRect(); return t2.left >= br.right ? t2.left - br.right : br.left >= t2.right ? br.left - t2.right : 0; }));
          if (nearest > 24) add('badge-stranded', b, Math.round(nearest) + 'px from "' + (kids[j].innerText || '').trim().slice(0, 20) + '"');
        }
      }
    }
  }

  // 3. Clipped or truncated text.
  for (const el of all) {
    if (!own(el).length && !el.matches('button,a,.ui-badge,[class*=badge]')) continue;
    const s = getComputedStyle(el);
    if (el.clientWidth <= 4) continue;
    if (el.scrollWidth > el.clientWidth + 1) {
      if (s.textOverflow === 'ellipsis') {
        if (own(el).length <= 24 && !el.title && !el.closest('[title]')) add('truncated-short-text', el, el.scrollWidth + '>' + el.clientWidth);
      } else if (/hidden|clip/.test(s.overflowX)) add('clipped-text', el, el.scrollWidth + '>' + el.clientWidth);
    } else if (el.scrollHeight > el.clientHeight + 2 && s.webkitLineClamp === 'none' && /hidden|clip/.test(s.overflowY) && el.clientHeight > 0 && own(el) && s.display !== 'inline') {
      add('clipped-text', el, 'height ' + el.scrollHeight + '>' + el.clientHeight);
    }
  }

  // 4. Text boxes that overlap each other.
  const boxes = [];
  for (const el of leaves) {
    let fixed = false;
    for (let a = el; a && a !== document.body; a = a.parentElement) { const p = getComputedStyle(a).position; if (p === 'fixed' || p === 'sticky') { fixed = true; break; } }
    if (fixed) continue;
    const range = document.createRange();
    for (const n of el.childNodes) {
      if (n.nodeType !== 3 || !n.textContent.trim()) continue;
      range.selectNodeContents(n);
      // text clipped away by an overflow:hidden ancestor (ellipsis) is not visible, so it cannot overlap
      const clipped = (r) => {
        let x0 = r.left, x1 = r.right, y0 = r.top, y1 = r.bottom;
        for (let a = el; a && a !== document.body; a = a.parentElement) {
          const cs = getComputedStyle(a);
          const ar = a.getBoundingClientRect();
          if (/hidden|clip|auto|scroll/.test(cs.overflowX)) { x0 = Math.max(x0, ar.left); x1 = Math.min(x1, ar.right); }
          if (/hidden|clip/.test(cs.overflowY)) { y0 = Math.max(y0, ar.top); y1 = Math.min(y1, ar.bottom); }
        }
        return {left: x0, right: x1, top: y0, bottom: y1, width: x1 - x0, height: y1 - y0};
      };
      const rects = [...range.getClientRects()].filter((r) => r.width > 2 && r.height > 2).map(clipped).filter((r) => r.width > 2 && r.height > 2);
      if (rects.length) boxes.push({el, rects});
    }
  }
  const hit = (a, b) => { const w = Math.min(a.right, b.right) - Math.max(a.left, b.left); const h = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top); return w > 3 && h > 3 && w * h > 20; };
  for (let i = 0; i < Math.min(boxes.length, 1200); i++) for (let j = i + 1; j < Math.min(boxes.length, 1200); j++) {
    const A = boxes[i], B = boxes[j];
    if (A.el === B.el || A.el.contains(B.el) || B.el.contains(A.el)) continue;
    if (A.rects.some((a) => B.rects.some((b) => hit(a, b)))) add('text-overlap', A.el, name(B.el));
  }

  // 5. Elements outside the viewport (sideways), or the page scrolling sideways.
  const inScroller = (el) => { for (let a = el.parentElement; a && a !== document.body; a = a.parentElement) { const ox = getComputedStyle(a).overflowX; if (ox === 'auto' || ox === 'scroll') return true; } return false; };
  if (document.documentElement.scrollWidth > vw + 1) out.push(['page-scrolls-sideways', 'document', document.documentElement.scrollWidth, vw]);
  for (const el of leaves) {
    if (el.closest('.ui-table-wrap,.scroll-x,[data-scroll-x]') || inScroller(el)) continue;
    const r = el.getBoundingClientRect();
    if (r.right > vw + 1 || r.left < -1) add('outside-viewport', el, Math.round(r.left) + '..' + Math.round(r.right) + ' of ' + vw);
  }

  // 6. Visible boxes with nothing in them.
  for (const el of all) {
    const r = el.getBoundingClientRect();
    if (el.matches('button,a.btn,a.ui-btn,.btn,.ui-btn,.ui-badge')) {
      const hasText = (el.innerText || '').trim().length > 0;
      const hasIcon = !!el.querySelector('svg,img,i,picture,canvas,[class*=icon]') || el.matches('[class*=icon]');
      const pseudo = ['::before', '::after'].some((p) => { const c = getComputedStyle(el, p).content; return c && !['none', 'normal', '""', "''"].includes(c); });
      if (!hasText && !hasIcon && !pseudo && getComputedStyle(el).backgroundImage === 'none' && r.width > 8) add('empty-control', el, Math.round(r.width) + 'x' + Math.round(r.height));
    } else if (el.matches('.panel,.card,.ui-section,.ui-card') && el.children.length === 0 && !(el.innerText || '').trim() && r.height > 8) {
      const s = getComputedStyle(el);
      if (s.borderTopWidth !== '0px' || s.backgroundColor !== 'rgba(0, 0, 0, 0)') add('empty-box', el, Math.round(r.height) + 'px tall');
    }
  }

  // 7. Stray duplicate icons: identical svgs side by side, or an svg beside a drawn pseudo icon.
  for (const p of new Set([...all, document.body])) {
    const svgs = [...p.children].filter((c) => c.tagName.toLowerCase() === 'svg' && vis(c));
    if (svgs.length >= 2) {
      const sig = svgs.map((x) => x.innerHTML.replace(/\s+/g, ''));
      if (sig.some((x, i) => sig.indexOf(x) !== i)) add('duplicate-icon', p, svgs.length + ' identical svgs');
    }
    if (svgs.length >= 1 && p.matches('button,a,.ui-btn,.btn')) {
      const c = getComputedStyle(p, '::before').content;
      if (c && !['none', 'normal', '""', "''"].includes(c) && /^["'][^\s"']/.test(c)) add('icon-plus-pseudo-icon', p, c);
    }
  }

  // 8. Mixed stylesheets: legacy and v2 shells never load together; a file appears once.
  const sheets = [...document.querySelectorAll('link[rel=stylesheet]')].map((l) => l.getAttribute('href') || '');
  const file = (h) => h.split('?')[0].split('/').pop();
  const names = sheets.map(file);
  if (names.includes('app2.css') && names.includes('app.css')) out.push(['mixed-stylesheets', 'head', 'app2.css and app.css together']);
  if (names.includes('app2.css') && names.some((n) => ['host.css', 'host-design0123.css', 'host-controls.css'].includes(n))) out.push(['mixed-stylesheets', 'head', 'v2 shell with legacy host css']);
  for (const d of new Set(names.filter((n, i) => names.indexOf(n) !== i))) {
    const versions = new Set(sheets.filter((h) => file(h) === d));
    if (versions.size > 1) out.push(['mixed-stylesheets', 'head', d + ' loaded in ' + versions.size + ' versions']);
  }
  return out;
})()
