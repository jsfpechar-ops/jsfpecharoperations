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
  const skipZone = (el) => el.closest('[role=menu],.row-menu-panel,.sr-only,.visually-hidden,[aria-hidden=true],script,style,noscript,template,svg,.skeleton,[data-lint-ignore],.onboarding-finish,.onboarding-finish-strip,details:not([open]) > :not(summary)');
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
    // a block that stacks several text blocks (name over role) is judged by its children, not as one run of words
    if ([...el.children].some((c) => !['inline', 'inline-block', 'contents'].includes(getComputedStyle(c).display) && (c.innerText || '').trim())) continue;
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
  // page-help-wrap matches [class*=help] but is a title-row wrapper, not the small "?" badge.
  const help0 = (el) => el.matches('.help-tip,[class*=help]') && !el.matches('.page-help-wrap,.page-help,.page-help-body');
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
        const help = help0(b);
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
  // 9. A help "?" sits inline right after its heading or label: same line, no more than 32 px away. Never on its own line.
  const tipCircle = (tip) => {
    const dot = tip.querySelector('.page-help-dot');
    if (dot) { const d = dot.getBoundingClientRect(); return {left: d.left, right: d.right, cy: d.top + d.height / 2}; }
    const b = tip.querySelector('.help-tip-btn,.page-help-btn') || tip;
    const r = b.getBoundingClientRect();
    const mobile = r.width >= 40;
    const cx = mobile ? r.left + 9 : r.left + r.width / 2;
    return {left: cx - 9, right: cx + 9, cy: r.top + r.height / 2};
  };
  const anchorRect = (node, last) => {
    if (node.nodeType === 1 && node.matches('button,input,select,textarea,.ui-btn,.btn')) return node.getBoundingClientRect();
    const range = document.createRange();
    range.selectNodeContents(node);
    const rs = [...range.getClientRects()].filter((r) => r.width > 1 && r.height > 1);
    if (!rs.length) return null;
    return last ? rs[rs.length - 1] : rs[0];
  };
  const sideOf = (start, dir) => {
    for (let n = dir < 0 ? start.previousSibling : start.nextSibling; n; n = dir < 0 ? n.previousSibling : n.nextSibling) {
      if (n.nodeType === 3 && n.textContent.trim()) return n;
      if (n.nodeType === 1) {
        if (n.matches('.help-tip,.page-help-wrap,.page-help,script,style,template') || !vis(n)) continue;
        const cs = getComputedStyle(n);
        if (cs.position === 'absolute' || cs.position === 'fixed') continue;
        if ((n.innerText || '').trim() || n.querySelector('svg,img') || n.matches('button,a,input,select')) return n;
      }
    }
    return null;
  };
  for (const tip of document.body.querySelectorAll('.help-tip,details.page-help')) {
    if (!vis(tip.querySelector('.help-tip-btn,.page-help-btn') || tip) || skipZone(tip) || tip.closest('[data-lint-ignore]')) continue;
    const c = tipCircle(tip);
    let cur = tip, prev = null, next = null;
    for (let up = 0; up < 3 && cur && cur !== document.body; up++, cur = cur.parentElement) {
      prev = sideOf(cur, -1);
      next = prev ? null : sideOf(cur, 1);
      if (prev || next) break;
    }
    const anchor = prev || next;
    if (!anchor) continue;
    // After checkline label: anchor is the <span> text; use first line (wrapped labels have multi-line rects).
    const lastLine = !!prev && !tip.closest('label.checkline');
    const ar = anchorRect(anchor, lastLine);
    if (!ar) continue;
    const sameLine = c.cy >= ar.top - 3 && c.cy <= ar.bottom + 3;
    const gap = prev ? c.left - ar.right : ar.left - c.right;
    const cid = (tip.querySelector('[aria-controls]') || tip).getAttribute('aria-controls') || '';
    if (!sameLine) add('help-stranded', tip, '#' + cid + ' on its own line, ' + Math.round(Math.abs(c.cy - (ar.top + ar.bottom) / 2)) + 'px off its label');
    else if (gap > 32 || gap < -4) add('help-stranded', tip, '#' + cid + ' ' + Math.round(gap) + 'px from its label');
  }

  // 10. Phone and tablet (below 1024 px) patterns that read as "broken" even when nothing overlaps.
  const narrow = vw < 1024;
  const ctlSel = 'button,a.btn,a.ui-btn,.btn,.ui-btn,input:not([type=hidden]):not([type=checkbox]):not([type=radio]),select,textarea';
  const rectOf = (el) => el.getBoundingClientRect();
  // 10a. A table cell whose text is cut into one or two letters per line (a squeezed table).
  for (const cell of document.body.querySelectorAll('td,th')) {
    if (!vis(cell) || skipZone(cell)) continue;
    const text = (cell.innerText || '').replace(/\s+/g, ' ').trim();
    if (text.length < 4 || text.length > 30 || /[/:?=]/.test(text)) continue;
    const r = rectOf(cell);
    const lines = textLines(cell);
    const longest = Math.max(...words(text).map((x) => x.length));
    if (lines >= 2 && lines > words(text).length && longest >= 4) add('table-squeezed', cell, lines + ' lines for "' + text.slice(0, 18) + '"', Math.round(r.width) + 'px wide');
  }
  // 10b. Controls and labels stacked (or side by side) closer than 12 px.
  if (narrow) {
    const ctls = all.filter((el) => el.matches(ctlSel) && !el.closest('.help-tip,[class*=stepper],[class*=segmented],[role=tablist],[role=group],.tabbar,nav,.tab-bar,.seg,.pills,.chips,.row-menu-panel,summary,.dashboard-calendar,[class*=cal-grid],[class*=cal-day]') && !el.matches('[class*=cal-day]'));
    const rs = ctls.map(rectOf);
    for (let i = 0; i < ctls.length; i++) {
      for (let j = i + 1; j < ctls.length; j++) {
        if (ctls[i].contains(ctls[j]) || ctls[j].contains(ctls[i])) continue;
        const a = rs[i], b = rs[j];
        const hOverlap = Math.min(a.right, b.right) - Math.max(a.left, b.left);
        const vOverlap = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
        const vgap = Math.max(a.top, b.top) - Math.min(a.bottom, b.bottom);
        const hgap = Math.max(a.left, b.left) - Math.min(a.right, b.right);
        const fixed = (el) => getComputedStyle(el).position === 'fixed' || el.closest('[style*="position: fixed"]');
        if (fixed(ctls[i]) || fixed(ctls[j])) continue;
        if (hOverlap > 8 && vgap < 12 && vgap > -1 && vOverlap <= 0) add('tight-stack', ctls[j], 'only ' + Math.max(0, Math.round(vgap)) + 'px below "' + (ctls[i].innerText || ctls[i].name || '').trim().slice(0, 20) + '"');
        else if (vOverlap > 8 && hgap < 12 && hgap > -1 && hOverlap <= 0) add('tight-side', ctls[j], 'only ' + Math.max(0, Math.round(hgap)) + 'px beside "' + (ctls[i].innerText || ctls[i].name || '').trim().slice(0, 20) + '"');
      }
    }
    // a label or line of text right under a button
    for (const lab of all.filter((el) => el.matches('label,legend,h2,h3,h4,.field-label-row'))) {
      const lr = rectOf(lab);
      for (const c of ctls) {
        if (!c.matches('button,a.btn,a.ui-btn,.btn,.ui-btn') || c.contains(lab) || lab.contains(c)) continue;
        const cr = rectOf(c);
        const hOverlap = Math.min(lr.right, cr.right) - Math.max(lr.left, cr.left);
        const gap = lr.top - cr.bottom;
        if (hOverlap > 8 && gap >= -1 && gap < 12 && !(() => { for (let n = c; n && n !== document.documentElement; n = n.parentElement) if (getComputedStyle(n).position === 'fixed') return true; return false; })()) add('tight-stack', lab, 'label only ' + Math.max(0, Math.round(gap)) + 'px below button "' + (c.innerText || '').trim().slice(0, 20) + '"', 'at y=' + Math.round(lr.top + scrollY) + ' button ' + (c.className || c.tagName));
      }
    }
    // 10c. Half-width inputs on a phone: a field that could fill its column but stops short.
    if (vw < 768) {
      for (const inp of all.filter((el) => el.matches('input:not([type=hidden]):not([type=checkbox]):not([type=radio]):not([type=file]):not([type=range]):not([type=color]):not([type=submit]):not([type=button]),select,textarea'))) {
        const par = inp.parentElement;
        if (!par || inp.closest('.help-tip,[data-lint-ignore]')) continue;
        const ps = getComputedStyle(par);
        const pr = rectOf(par);
        const avail = pr.width - parseFloat(ps.paddingLeft) - parseFloat(ps.paddingRight);
        const ir = rectOf(inp);
        if (avail < 240) continue;
        // same-row siblings make a deliberate row (value + unit, from + to)
        const sibs = [...par.children].filter((c) => c !== inp && vis(c) && Math.abs(rectOf(c).top - ir.top) < ir.height && c.getBoundingClientRect().left > ir.right - 1);
        if (sibs.length || ps.display.includes('flex') && ps.flexDirection.startsWith('row') && par.children.length > 1) continue;
        if (ir.width < avail * 0.9 && ir.width > 0) add('half-width-input', inp, Math.round(ir.width) + 'px of ' + Math.round(avail) + 'px');
      }
    }
  }
  // 10d. A fieldset legend straddling its border line.
  for (const fs of document.body.querySelectorAll('fieldset')) {
    const lg = [...fs.children].find((c) => c.tagName === 'LEGEND');
    if (!lg || !vis(lg) || !vis(fs) || skipZone(fs)) continue;
    const fr = rectOf(fs), lr = rectOf(lg), fcs = getComputedStyle(fs);
    const bw = parseFloat(fcs.borderTopWidth) || 0;
    if (bw > 0 && fcs.borderTopStyle !== 'none' && lr.top < fr.top + bw && lr.bottom > fr.top) add('legend-overlap', lg, 'legend sits on the border line of its fieldset');
  }
  // 10e. Two filled red/primary buttons side by side or stacked in one place: only one is the primary action.
  const filled = (el) => { const c = getComputedStyle(el).backgroundColor.match(/\d+(\.\d+)?/g) || []; return c.length >= 3 && +(c[3] ?? 1) > 0.9 && +c[0] > 150 && +c[1] < 100 && +c[2] < 100; };
  for (const parent of new Set(all.filter((el) => el.matches('button,a.ui-btn,.btn,.ui-btn') && filled(el)).map((el) => el.closest('.actions,form,div,section,li,p,td') || el.parentElement))) {
    const reds = [...parent.querySelectorAll('button,a.ui-btn,.btn,.ui-btn')].filter((el) => vis(el) && filled(el) && getComputedStyle(el).position !== 'fixed');
    if (reds.length >= 2) add('double-primary', reds[1], reds.length + ' red filled buttons together; one must be secondary');
  }
  // 10f. A stray one-sided vertical rule inside a card (a border-right on the last cell).
  for (const el of all) {
    if (el.matches('table,thead,tbody,tr,td,th,button,input,select,textarea,a')) continue;
    const s = getComputedStyle(el);
    const r = rectOf(el);
    if (r.height < 20 || r.width < 20) continue;
    const bR = parseFloat(s.borderRightWidth) > 0 && s.borderRightStyle !== 'none';
    const bL = parseFloat(s.borderLeftWidth) > 0 && s.borderLeftStyle !== 'none';
    const par = el.parentElement;
    if (!par || !bR || bL || !narrow) continue;
    const kids = [...par.children].filter(vis);
    // a divider between two halves is fine; a rule on the last item, against the card edge, is stray
    if (kids.length && kids[kids.length - 1] === el && rectOf(par).right - r.right < 40 && !el.matches('aside')) add('stray-rule', el, 'right border on the last item');
  }
  // 11a. Header actions (0931): buttons beside an h1 share one row, same height and centre, one-line labels. Conservative.
  if (vw >= 768) {
    const actSel = 'button,a.ui-btn,.btn,.ui-btn';
    const isAct = (el) => el.matches(actSel) && vis(el) && !skipZone(el) && getComputedStyle(el).position !== 'fixed';
    for (const h of all.filter((el) => el.tagName === 'H1' && !el.closest('[role=dialog],dialog'))) {
      let box = h.parentElement;
      while (box && box !== document.body && ![...box.querySelectorAll(actSel)].some(isAct)) box = box.parentElement;
      if (!box || box === document.body) continue;
      const acts = [...box.querySelectorAll(actSel)].filter(isAct);
      const hr = rectOf(h);
      const beside = acts.filter((a) => { const r = rectOf(a); return r.top < hr.bottom && r.bottom > hr.top; });
      if (!beside.length) continue;
      if (beside.length >= 2) {
        const r0 = rectOf(beside[0]);
        const bad = beside.find((b) => { const r = rectOf(b); return Math.abs(r.height - r0.height) > 2 || Math.abs((r.top + r.bottom) / 2 - (r0.top + r0.bottom) / 2) > 4; });
        if (bad) add('header-actions-misaligned', bad, 'header buttons differ in height or vertical centre');
      }
      for (const b of beside) if (textLines(b) > 1) add('header-actions-misaligned', b, 'header button label wraps to two lines');
      if (beside.length === 1 && box.matches('.page-head') && acts.length > 1) add('header-actions-misaligned', beside[0], 'lone header button beside the h1 while other actions sit elsewhere in .page-head');
    }
  }

  // 11b. One form, one save button (0931). Czech and English labels.
  const saveRe = /save|uložit|ulozit/i;
  const submits = all.filter((el) => el.matches('button[type=submit],input[type=submit]') && vis(el));
  const saves = submits.filter((el) => saveRe.test((el.innerText || el.value || '').trim()));
  for (const form of new Set(saves.map((b) => b.closest('form')).filter(Boolean))) {
    const inForm = saves.filter((b) => b.closest('form') === form);
    if (inForm.length > 1) add('multiple-save-in-form', inForm[1], inForm.length + ' save submit buttons in one form');
  }
  for (const bar of all.filter((el) => getComputedStyle(el).position === 'fixed' && el.querySelector('button[type=submit],input[type=submit]'))) {
    const barSubmit = submits.filter((b) => bar.contains(b));
    const outside = saves.filter((b) => !bar.contains(b));
    if (barSubmit.length && outside.length) add('multiple-save-in-form', bar, 'fixed bar holds a submit while another save submit sits outside it');
  }

  // 11c. Two visible headings with the same text on one page (0931). Dialogs and nav excluded.
  const headSeen = new Map();
  for (const h of all.filter((el) => /^H[123]$/.test(el.tagName) && !el.closest('[role=dialog],dialog,nav'))) {
    const t = h.textContent.toLowerCase().trim().replace(/\s+/g, ' ');
    if (t.length < 3) continue;
    if (headSeen.has(t)) add('duplicate-heading', h, 'same heading text as an earlier one: "' + t.slice(0, 40) + '"');
    else headSeen.set(t, h);
  }

  // 10g. Stay detail (0912): the action buttons and the menu trigger share one row; one that sits alone
  // on a line under the primary action row is an orphan.
  for (const row of document.querySelectorAll('.stay-head-actions')) {
    if (!vis(row)) continue;
    const acts = [...row.querySelectorAll('button,a.btn,.row-menu > summary,details > summary')].filter((el) => vis(el) && !skipZone(el) && getComputedStyle(el).position !== 'fixed');
    if (acts.length < 2) continue;
    const tops = acts.map((el) => rectOf(el).top);
    const first = Math.min(...tops);
    for (const el of acts) {
      const top = rectOf(el).top;
      if (top - first <= 4) continue;
      const sharesLine = acts.some((other) => other !== el && Math.abs(rectOf(other).top - top) <= 4);
      if (!sharesLine) add('action-row-orphan', el, 'sits alone on its own line below the action row');
    }
  }

  // 11. Action rows at every width: buttons that overlap, wrap, or sit closer than 12 px.
  const actSel = 'button,a.btn,a.ui-btn,.btn,.ui-btn,input[type=submit]';
  const acts = all.filter((el) => el.matches(actSel) && !el.matches('.help-tip-btn') && !el.closest('.help-tip,[class*=stepper],[class*=segmented],[role=tablist],[role=group],.tabbar,nav,.tab-bar,.seg,.pills,.chips,.row-menu-panel,summary,.dashboard-calendar,[class*=cal-grid],[class*=cal-day]') && getComputedStyle(el).position !== 'fixed' && vis(el) && !skipZone(el));
  const rowKey = (el) => {
    const p = el.parentElement;
    return p && p.tagName === 'FORM' && p.parentElement ? p.parentElement : p;
  };
  const rowsOf = new Map();
  for (const el of acts) {
    const k = rowKey(el);
    if (!k) continue;
    if (!rowsOf.has(k)) rowsOf.set(k, []);
    rowsOf.get(k).push(el);
  }
  for (const row of rowsOf.values()) {
    if (row.length < 2) continue;
    for (let i = 0; i < row.length; i++) {
      for (let j = i + 1; j < row.length; j++) {
        const a = row[i], b = row[j];
        if (a.contains(b) || b.contains(a)) continue;
        const ra = rectOf(a), rb = rectOf(b);
        const ox = Math.min(ra.right, rb.right) - Math.max(ra.left, rb.left);
        const oy = Math.min(ra.bottom, rb.bottom) - Math.max(ra.top, rb.top);
        const hg = Math.max(rb.left - ra.right, ra.left - rb.right);
        if (ox > 1 && oy > 1) add('button-overlap', a, 'overlaps ' + name(b));
        else if (oy > 8 && hg >= -1 && hg < 12) add('tight-row', a, 'less than 12 px from ' + name(b));
      }
    }
    for (const el of row) {
      if (words(el.textContent || '').length >= 2 && textLines(el) >= 2) add('button-wraps', el, 'label wraps onto ' + textLines(el) + ' lines');
    }
  }

  return out;
})()
