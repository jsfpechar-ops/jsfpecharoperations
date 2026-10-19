(phone) => {
  const out = [];
  const vw = window.innerWidth;
  const vis = (el) => {
    const s = getComputedStyle(el);
    if (s.display === 'none' || s.visibility === 'hidden' || +s.opacity === 0) return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  };
  const inScroller = (el) => { for (let a = el.parentElement; a && a !== document.body; a = a.parentElement) { const ox = getComputedStyle(a).overflowX; if (ox === 'auto' || ox === 'scroll') return true; } return false; };
  const name = (el) => (el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') + (el.classList.length ? '.' + [...el.classList].slice(0, 3).join('.') : '') + ' "' + (el.textContent || el.value || el.getAttribute('aria-label') || '').trim().replace(/\s+/g, ' ').slice(0, 30) + '"');
  // 1. no sideways page scroll
  const sw = document.documentElement.scrollWidth;
  if (sw > vw + 1) out.push(['page-scroll', sw, vw]);
  // 2. nothing under the rail or past the right edge
  const ws = document.querySelector('.host-workspace main, .host-workspace') || document.body;
  const lane = ws.getBoundingClientRect();
  for (const el of ws.querySelectorAll('h1,h2,h3,p,label,a,button,input,select,textarea,td,th,li,.ui-badge,img,svg')) {
    if (!vis(el) || el.closest('[role=menu],[hidden],dialog:not([open]),.ui-table-wrap,.scroll-x,[data-scroll-x]')) continue;
    if (inScroller(el)) continue;
    const r = el.getBoundingClientRect();
    if (r.left < lane.left - 1) out.push(['under-rail', name(el), Math.round(r.left), Math.round(lane.left)]);
    if (r.right > vw + 1) out.push(['past-right-edge', name(el), Math.round(r.right), vw]);
  }
  // 3. clipped or overlapping text: an element whose text is cut by its own box
  for (const el of ws.querySelectorAll('td,th,h1,h2,h3,p,a,button,label,.ui-badge,li')) {
    if (!vis(el) || el.closest('[role=menu],[hidden]')) continue;
    const s = getComputedStyle(el);
    if (s.textOverflow === 'ellipsis' || el.clientHeight <= 2 || el.clientWidth <= 2) continue;
    if (el.scrollHeight > el.clientHeight + 2 && s.overflowY !== 'visible' && s.overflowY !== 'auto' && s.overflowY !== 'scroll' && el.clientHeight > 0) out.push(['text-clipped', name(el), el.scrollHeight, el.clientHeight]);
  }
  // table rows must contain their cells (catches fixed row heights with wrapping text)
  for (const tr of ws.querySelectorAll('tr')) {
    if (!vis(tr)) continue;
    const rr = tr.getBoundingClientRect();
    for (const td of tr.children) {
      if (!vis(td)) continue;
      for (const kid of td.querySelectorAll('*')) {
        if (!vis(kid) || kid.closest('[role=menu]') || kid.tagName === 'IFRAME') continue;
        const kr = kid.getBoundingClientRect();
        if (kr.bottom > rr.bottom + 2 || kr.top < rr.top - 2) { out.push(['spills-out-of-row', name(kid), Math.round(kr.top), Math.round(kr.bottom), Math.round(rr.top), Math.round(rr.bottom)]); break; }
      }
    }
  }
  // 4. buttons that share a row have one height and one centre line
  const btnSel = '.ui-btn:not(.row-menu-trigger):not(.ui-btn-icon),.btn,input[type=submit],button[type=submit]';
  const parents = new Set([...ws.querySelectorAll(btnSel)].filter(vis).map((b) => b.parentElement));
  for (const p of parents) {
    const bs = [...p.children].filter((c) => c.matches(btnSel) && vis(c));
    // also buttons wrapped one level deep in a form (inline-form pattern)
    for (const c of p.children) if (c.tagName === 'FORM') for (const b of c.children) if (b.matches(btnSel) && vis(b)) bs.push(b);
    for (let i = 0; i < bs.length; i++) for (let j = i + 1; j < bs.length; j++) {
      const a = bs[i].getBoundingClientRect(), b = bs[j].getBoundingClientRect();
      const sameRow = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > 0;
      if (!sameRow) continue;
      if (Math.abs(a.height - b.height) > 2) out.push(['button-heights-differ', name(bs[i]), Math.round(a.height), name(bs[j]), Math.round(b.height)]);
      else if (Math.abs((a.top + a.bottom) / 2 - (b.top + b.bottom) / 2) > 2) out.push(['buttons-misaligned', name(bs[i]), name(bs[j])]);
    }
  }
  // 5. phone tap targets
  if (phone) {
    for (const el of ws.querySelectorAll('button,.ui-btn,input:not([type=hidden]):not([type=checkbox]):not([type=radio]),select,[role=menuitem],[role=tab]')) {
      if (!vis(el) || el.closest('[role=menu],[hidden]')) continue;
      const r = el.getBoundingClientRect();
      if (r.height < 43.5 || r.width < 43.5) out.push(['tap-target-small', name(el), Math.round(r.width), Math.round(r.height)]);
    }
  }
  return out;
}
