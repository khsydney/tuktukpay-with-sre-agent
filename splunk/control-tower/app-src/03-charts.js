/* ===== chart primitives (hand-built SVG; thin marks, hairline grid, one shared tooltip, table twins supplied by the caller) ===== */
const STC = { good: 'var(--st-good)', warning: 'var(--st-warn)', serious: 'var(--st-serious)', critical: 'var(--st-critical)', unknown: 'var(--st-unknown)' };
const STI = { good: 'OK', warning: '!', serious: '!!', critical: '!!!', unknown: '?' };
const SERIES = ['var(--s1)', 'var(--s2)', 'var(--s3)', 'var(--s4)', 'var(--s5)', 'var(--s7)', 'var(--s8)', 'var(--s6)'];
const seriesColor = (i) => SERIES[i % SERIES.length];

function niceMax(v) { if (v <= 0) return 1; const p = Math.pow(10, Math.floor(Math.log10(v))); const m = v / p; const n = m <= 1 ? 1 : m <= 2 ? 2 : m <= 2.5 ? 2.5 : m <= 5 ? 5 : 10; return n * p; }
function scaleLinear(d0, d1, r0, r1) { const f = (v) => r0 + (v - d0) / ((d1 - d0) || 1) * (r1 - r0); f.invert = (p) => d0 + (p - r0) / ((r1 - r0) || 1) * (d1 - d0); return f; }

function sparkline(values, opts = {}) {
  const w = opts.w || 120, h = opts.h || 28, pad = 2;
  const max = Math.max(...values), min = Math.min(...values);
  const x = scaleLinear(0, values.length - 1, pad, w - pad), y = scaleLinear(min, max === min ? min + 1 : max, h - pad, pad);
  const d = values.map((v, i) => (i ? 'L' : 'M') + x(i).toFixed(1) + ' ' + y(v).toFixed(1)).join(' ');
  const s = svg('svg', { class: 'spark', viewBox: `0 0 ${w} ${h}`, preserveAspectRatio: 'none', 'aria-hidden': 'true' });
  s.append(svg('path', { d, fill: 'none', stroke: opts.color || 'var(--dim)', 'stroke-width': 1.5, 'stroke-linejoin': 'round' }));
  const n = values.length - 1;
  s.append(svg('circle', { cx: x(n), cy: y(values[n]), r: 2.5, fill: opts.accent || 'var(--teal)' }));
  return s;
}

// statTile({label, value, unit, delta, deltaGood (true: up is good), spark, status, lane, href, tipRows})
function statTile(o) {
  const t = el('div.tile', { dataset: { s: o.status || 'good' }, role: o.href ? 'link' : null, tabindex: '0' });
  // lane badge on its own row so the status icon stays beside the label text instead of stranded when the row wraps
  if (o.lane) t.append(el('div.lanes', null, [laneBadge(o.lane)]));
  const lab = el('div.label', null, [document.createTextNode(o.label)]);
  if (o.status && o.status !== 'good') lab.prepend(el('span.status-ico', { dataset: { s: o.status }, text: STI[o.status], title: o.status }));   // a "!" chip coloured by severity
  t.append(lab);
  const vrow = el('div.vrow', null, [el('div.value', { text: o.value })]);
  if (o.delta != null) {
    const up = o.delta > 0, good = o.deltaGood === undefined ? up : (up === o.deltaGood);
    vrow.append(el('div.delta' + (o.delta === 0 ? '.flat' : good ? '.good' : '.bad'), { text: (o.delta > 0 ? '▲ ' : o.delta < 0 ? '▼ ' : '') + fmt.signed(o.delta) + (o.deltaUnit || '') + ' vs 1 h ago' }));
  }
  t.append(vrow);
  if (o.sub) t.append(el('div.delta.flat', { text: o.sub }));
  if (o.spark) t.append(sparkline(o.spark, { color: 'var(--dim)', accent: o.status && o.status !== 'good' ? STC[o.status] : 'var(--teal)' }));
  if (o.href) { t.addEventListener('click', () => go(o.href)); t.addEventListener('keydown', (e) => { if (e.key === 'Enter') go(o.href); }); }
  if (o.tipRows) { t.addEventListener('pointermove', (e) => tipShow(e, o.label, o.tipRows)); t.addEventListener('pointerleave', tipHide); }
  return t;
}

// lineChart({labels, series:[{name, values, color}], yFmt, yMin, yMax, thresholds:[{value,label}], h, area:boolean, bands:[{from,to,label}]})
function lineChart(o) {
  const W = 640, H = o.h || 180, m = { t: 12, r: 70, b: 24, l: 44 };
  const n = o.labels.length;
  const all = o.series.flatMap(s => s.values).concat((o.thresholds || []).map(t => t.value));
  const yMax = o.yMax != null ? o.yMax : niceMax(Math.max(...all) * 1.08), yMin = o.yMin != null ? o.yMin : 0;
  const x = scaleLinear(0, n - 1, m.l, W - m.r), y = scaleLinear(yMin, yMax, H - m.b, m.t);
  const root = svg('svg', { class: 'chart', viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': o.aria || 'line chart' });
  const grid = svg('g', { class: 'grid' }), axis = svg('g', { class: 'axis' });
  for (let i = 0; i <= 4; i++) { const v = yMin + (yMax - yMin) * i / 4, yy = y(v); grid.append(svg('line', { x1: m.l, x2: W - m.r, y1: yy, y2: yy })); axis.append(svg('text', { x: m.l - 6, y: yy + 4, 'text-anchor': 'end', text: (o.yFmt || fmt.num)(v) })); }
  root.append(grid);
  const every = Math.max(1, Math.round(n / 6));
  for (let i = 0; i < n; i += every) axis.append(svg('text', { x: x(i), y: H - 6, 'text-anchor': 'middle', text: o.labels[i] }));
  axis.append(svg('line', { x1: m.l, x2: W - m.r, y1: H - m.b, y2: H - m.b }));
  root.append(axis);
  (o.bands || []).forEach(b => { root.append(svg('rect', { x: x(b.from), y: m.t, width: x(b.to) - x(b.from), height: H - m.b - m.t, fill: 'var(--st-warn)', opacity: .07 })); if (b.label) root.append(svg('text', { x: x(b.from) + 4, y: m.t + 10, text: b.label, fill: 'var(--st-warn)' })); });
  const g = svg('g', { class: 'series' });
  o.series.forEach((s, si) => {
    const c = s.color || seriesColor(si);
    const d = s.values.map((v, i) => (i ? 'L' : 'M') + x(i).toFixed(1) + ' ' + y(v).toFixed(1)).join(' ');
    if (o.area || s.area) g.append(svg('path', { class: 'area', d: d + ` L${x(n - 1)} ${y(yMin)} L${x(0)} ${y(yMin)} Z`, fill: c }));
    g.append(svg('path', { d, stroke: c, 'stroke-dasharray': s.dash ? '5 4' : null }));
    g.append(svg('circle', { cx: x(n - 1), cy: y(last(s.values)), r: 4, fill: c }));
    if (o.series.length <= 4) g.append(svg('text', { class: 'label-end', x: x(n - 1) + 8, y: y(last(s.values)) + 4 - (s.labelDy || 0), text: s.name.length > 14 ? s.name.slice(0, 13) + '…' : s.name }));
  });
  root.append(g);
  (o.thresholds || []).forEach(t => { root.append(svg('line', { class: 'threshold', x1: m.l, x2: W - m.r, y1: y(t.value), y2: y(t.value) })); root.append(svg('text', { class: 'threshold-label', x: W - m.r - 4, y: y(t.value) - 4, 'text-anchor': 'end', text: t.label })); });
  const cross = svg('line', { class: 'crosshair', x1: 0, x2: 0, y1: m.t, y2: H - m.b }); root.append(cross);
  const hit = svg('rect', { class: 'hit', x: m.l, y: m.t, width: W - m.r - m.l, height: H - m.b - m.t });
  const toIdx = (evt) => { const pt = root.createSVGPoint(); pt.x = evt.clientX; pt.y = evt.clientY; const p = pt.matrixTransform(root.getScreenCTM().inverse()); return Math.max(0, Math.min(n - 1, Math.round(x.invert(p.x)))); };
  hit.addEventListener('pointermove', (evt) => { const i = toIdx(evt); cross.setAttribute('x1', x(i)); cross.setAttribute('x2', x(i)); cross.style.opacity = 1; tipShow(evt, o.labels[i], o.series.map((s, si) => [s.name, (o.yFmt || fmt.num)(s.values[i]), s.color || seriesColor(si)])); });
  hit.addEventListener('pointerleave', () => { cross.style.opacity = 0; tipHide(); });
  root.append(hit);
  const wrap = el('div'); wrap.append(root);
  if (o.series.length > 1) wrap.append(legend(o.series.map((s, i) => ({ name: s.name, color: s.color || seriesColor(i) }))));
  return wrap;
}
function legend(items, square) { const l = el('div.legend'); items.forEach(it => { const s = el('span' + (square ? '.sq' : ''), { text: it.name }); s.style.setProperty('--c', it.color); l.append(s); }); return l; }

// stackedColumns({labels, series:[{name, values, color}], yFmt, h})
function stackedColumns(o) {
  const W = 640, H = o.h || 180, m = { t: 12, r: 12, b: 24, l: 44 }, n = o.labels.length;
  const totals = o.labels.map((_, i) => o.series.reduce((a, s) => a + s.values[i], 0));
  const yMax = o.yMax || niceMax(Math.max(...totals) * 1.05);
  const x = scaleLinear(0, n, m.l, W - m.r), y = scaleLinear(0, yMax, H - m.b, m.t);
  const bw = Math.min(24, (x(1) - x(0)) * 0.7);
  const root = svg('svg', { class: 'chart', viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': o.aria || 'stacked columns' });
  const grid = svg('g', { class: 'grid' }), axis = svg('g', { class: 'axis' });
  for (let i = 0; i <= 4; i++) { const v = yMax * i / 4; grid.append(svg('line', { x1: m.l, x2: W - m.r, y1: y(v), y2: y(v) })); axis.append(svg('text', { x: m.l - 6, y: y(v) + 4, 'text-anchor': 'end', text: (o.yFmt || fmt.num)(v) })); }
  root.append(grid);
  const every = Math.max(1, Math.round(n / 6));
  for (let i = 0; i < n; i += every) axis.append(svg('text', { x: x(i + 0.5), y: H - 6, 'text-anchor': 'middle', text: o.labels[i] }));
  axis.append(svg('line', { x1: m.l, x2: W - m.r, y1: H - m.b, y2: H - m.b })); root.append(axis);
  for (let i = 0; i < n; i++) {
    let acc = 0;
    o.series.forEach((s, si) => {
      const v = s.values[i]; if (v <= 0) return;
      const y0 = y(acc + v), hgt = y(acc) - y(acc + v); acc += v;
      const r = svg('rect', { class: 'bar seg', x: x(i + 0.5) - bw / 2, y: y0, width: bw, height: Math.max(hgt, 0), fill: s.color || seriesColor(si), rx: si === o.series.length - 1 ? 3 : 0 });
      r.addEventListener('pointermove', (evt) => tipShow(evt, o.labels[i], o.series.map((ss, j) => [ss.name, (o.yFmt || fmt.num)(ss.values[i]), ss.color || seriesColor(j)]).concat([['Total', (o.yFmt || fmt.num)(totals[i])]])));
      r.addEventListener('pointerleave', tipHide);
      root.append(r);
    });
  }
  const wrap = el('div'); wrap.append(root); wrap.append(legend(o.series.map((s, i) => ({ name: s.name, color: s.color || seriesColor(i) })), true));
  return wrap;
}

// hBars({items:[{label, value, color, status, href}], fmt, max})
function hBars(o) {
  const W = 640, rowH = 26, m = { l: 150, r: 70, t: 6 }, H = m.t + o.items.length * rowH + 6;
  const max = o.max || niceMax(Math.max(...o.items.map(i => i.value)) * 1.05);
  const x = scaleLinear(0, max, m.l, W - m.r);
  const root = svg('svg', { class: 'chart', viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': o.aria || 'bars' });
  o.items.forEach((it, i) => {
    const yy = m.t + i * rowH + 4, h = 18;
    root.append(svg('text', { x: m.l - 8, y: yy + 13, 'text-anchor': 'end', text: it.label }));
    const r = svg('rect', { class: 'bar', x: m.l, y: yy, width: Math.max(2, x(it.value) - m.l), height: h, rx: 4, fill: it.color || (it.status ? STC[it.status] : 'var(--s1)') });
    if (it.href) { r.style.cursor = 'pointer'; r.addEventListener('click', () => go(it.href)); }
    r.addEventListener('pointermove', (evt) => tipShow(evt, it.label, [[o.valueLabel || 'Value', (o.fmt || fmt.num)(it.value)]].concat(it.tip || [])));
    r.addEventListener('pointerleave', tipHide);
    root.append(r);
    root.append(svg('text', { class: 'label-end', x: x(it.value) + 6, y: yy + 13, text: (o.fmt || fmt.num)(it.value) }));
  });
  return root;
}

// sankey({cols:[[nodeIds]], nodes:{id:{label, color}}, links:[{s,t,v}], h})
function sankey(o) {
  const W = 640, H = o.h || 260, pad = { t: 8, b: 8 }, nodeW = 10, gap = 8;
  const colX = scaleLinear(0, o.cols.length - 1, 120, W - 140);
  const inflow = {}, outflow = {};
  o.links.forEach(l => { outflow[l.s] = (outflow[l.s] || 0) + l.v; inflow[l.t] = (inflow[l.t] || 0) + l.v; });
  const size = (id) => Math.max(inflow[id] || 0, outflow[id] || 0);
  const maxCol = Math.max(...o.cols.map(c => c.reduce((a, id) => a + size(id), 0)));
  const scale = (H - pad.t - pad.b - gap * 4) / maxCol;
  const pos = {};
  o.cols.forEach((ids, ci) => {
    const total = ids.reduce((a, id) => a + size(id) * scale, 0) + gap * (ids.length - 1);
    let yy = pad.t + (H - pad.t - pad.b - total) / 2;
    ids.forEach(id => { pos[id] = { x: colX(ci), y: yy, h: size(id) * scale, outY: yy, inY: yy }; yy += size(id) * scale + gap; });
  });
  const root = svg('svg', { class: 'chart', viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': o.aria || 'flow' });
  o.links.forEach(l => {
    const a = pos[l.s], b = pos[l.t], h = l.v * scale;
    const y0 = a.outY + h / 2, y1 = b.inY + h / 2; a.outY += h; b.inY += h;
    const x0 = a.x + nodeW, x1 = b.x, cx = (x0 + x1) / 2;
    const p = svg('path', { class: 'sk-link', d: `M${x0} ${y0} C${cx} ${y0} ${cx} ${y1} ${x1} ${y1}`, stroke: l.color || (o.nodes[l.t] && o.nodes[l.t].color) || 'var(--s1)', 'stroke-width': Math.max(1.5, h) });
    p.addEventListener('pointermove', (evt) => tipShow(evt, `${o.nodes[l.s].label} → ${o.nodes[l.t].label}`, [['Payments', fmt.num(l.v)], ['Share of source', fmt.pct(l.v / outflow[l.s] * 100)]]));
    p.addEventListener('pointerleave', tipHide);
    root.append(p);
  });
  Object.entries(pos).forEach(([id, p]) => {
    const nd = o.nodes[id], g = svg('g', { class: 'sk-node' });
    g.append(svg('rect', { x: p.x, y: p.y, width: nodeW, height: Math.max(p.h, 2), fill: nd.color || 'var(--ink-2)', rx: 2 }));
    const first = o.cols[0].includes(id);
    g.append(svg('text', { x: first ? p.x - 6 : p.x + nodeW + 6, y: p.y + Math.max(p.h, 2) / 2 + 4, 'text-anchor': first ? 'end' : 'start', text: `${nd.label} ${fmt.num(size(id))}`, fill: 'var(--text)' }));
    if (nd.href) { g.style.cursor = 'pointer'; g.addEventListener('click', () => go(nd.href)); }
    root.append(g);
  });
  return root;
}

// stateTimeline({rows:[{name, segs:[{from,to,s,label}], href}], labels})  from/to in [0,1]
function stateTimeline(o) {
  const W = o.w || 640, rowH = 24, m = { l: 150, r: 12, t: 4 }, H = m.t + o.rows.length * rowH + 18, n = o.labels.length;
  const x = scaleLinear(0, 1, m.l, W - m.r);
  const root = svg('svg', { class: 'chart', viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': o.aria || 'state timeline' });
  o.rows.forEach((row, i) => {
    const yy = m.t + i * rowH;
    const t = svg('text', { x: m.l - 8, y: yy + 15, 'text-anchor': 'end', text: row.name, fill: 'var(--text)' });
    if (row.href) { t.style.cursor = 'pointer'; t.addEventListener('click', () => go(row.href)); }
    root.append(t);
    row.segs.forEach(sg => {
      const g = svg('g', { class: 'state' });
      const w = x(sg.to) - x(sg.from);
      g.append(svg('rect', { x: x(sg.from) + 1, y: yy + 3, width: Math.max(w - 2, 1), height: rowH - 6, fill: STC[sg.s], opacity: sg.s === 'good' ? .55 : .9 }));
      if (w > 40) g.append(svg('text', { x: x(sg.from) + 6, y: yy + 15, text: (STI[sg.s] + ' ' + (sg.label || sg.s)).slice(0, Math.floor(w / 6)), fill: '#0C1724' }));
      g.addEventListener('pointermove', (evt) => tipShow(evt, row.name, [['State', sg.label || sg.s], ['From', o.labels[Math.min(n - 1, Math.floor(sg.from * (n - 1)))]], ['To', o.labels[Math.min(n - 1, Math.round(sg.to * (n - 1)))]]]));
      g.addEventListener('pointerleave', tipHide);
      root.append(g);
    });
  });
  const every = Math.max(1, Math.round(n / 6));
  for (let i = 0; i < n; i += every) root.append(svg('text', { x: x(i / (n - 1)), y: H - 4, 'text-anchor': 'middle', text: o.labels[i] }));
  return root;
}

// flowMap({w,h, nodes:[{id,label,sub,x,y,w,h,s,href,kind}], edges:[{from,to,label,cls,via:[[x,y]]}]}) — the service / mandate maps
function flowMap(o) {
  const W = o.w || 900, H = o.h || 360;
  const root = svg('svg', { class: 'chart', viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': o.aria || 'flow map' });
  const defs = svg('defs');
  ['edge', 'hot', 'warm'].forEach(k => defs.append(svg('marker', { id: 'arr-' + k + '-' + (o.key || 'm'), viewBox: '0 0 10 10', refX: 9, refY: 5, markerWidth: 7, markerHeight: 7, orient: 'auto-start-reverse' }, [svg('path', { d: 'M0 0 L10 5 L0 10 z', fill: k === 'hot' ? 'var(--st-critical)' : k === 'warm' ? 'var(--st-warn)' : 'var(--axis)' })])));
  root.append(defs);
  const byId = Object.fromEntries(o.nodes.map(n => [n.id, n]));
  const center = (n) => ({ x: n.x + (n.w || 120) / 2, y: n.y + (n.h || 46) / 2 });
  const edgePt = (n, towards) => { // point on the node border facing `towards`
    const c = center(n), w = (n.w || 120) / 2, h = (n.h || 46) / 2, dx = towards.x - c.x, dy = towards.y - c.y;
    if (Math.abs(dx) * h > Math.abs(dy) * w) return { x: c.x + Math.sign(dx) * w, y: c.y + dy * (w / Math.abs(dx || 1)) };
    return { x: c.x + dx * (h / Math.abs(dy || 1)), y: c.y + Math.sign(dy) * h };
  };
  o.edges.forEach(e => {
    const a = byId[e.from], b = byId[e.to]; if (!a || !b) return;
    const pts = [edgePt(a, e.via ? { x: e.via[0][0], y: e.via[0][1] } : center(b))].concat((e.via || []).map(v => ({ x: v[0], y: v[1] }))).concat([edgePt(b, e.via ? { x: e.via[e.via.length - 1][0], y: e.via[e.via.length - 1][1] } : center(a))]);
    const d = pts.map((p, i) => (i ? 'L' : 'M') + p.x.toFixed(1) + ' ' + p.y.toFixed(1)).join(' ');
    const cls = e.cls || 'edge';
    root.append(svg('path', { class: 'edge' + (cls !== 'edge' ? ' ' + cls : ''), d, 'marker-end': `url(#arr-${cls}-${o.key || 'm'})`, 'stroke-dasharray': e.dash ? '5 4' : null }));
    if (e.label) { const mid = pts[Math.floor((pts.length - 1) / 2)], nx = pts[Math.floor((pts.length - 1) / 2) + 1]; root.append(svg('text', { class: 'edge-label', x: (mid.x + nx.x) / 2, y: (mid.y + nx.y) / 2 - 5 + (e.labelDy || 0), 'text-anchor': 'middle', text: e.label, fill: cls === 'hot' ? 'var(--st-critical)' : cls === 'warm' ? 'var(--st-warn)' : null })); }
  });
  o.nodes.forEach(n => {
    const w = n.w || 120, h = n.h || 46, g = svg('g', { class: 'node', tabindex: n.href ? '0' : null, role: n.href ? 'link' : null });
    const s = n.s || 'good';
    g.append(svg('rect', { x: n.x, y: n.y, width: w, height: h, rx: n.kind === 'state' ? h / 2 : 8, fill: n.kind === 'state' ? 'var(--node-2)' : 'var(--node)' }));
    if (n.kind !== 'state') g.append(svg('rect', { x: n.x, y: n.y, width: 5, height: h, rx: 2, fill: STC[s] }));
    g.append(svg('text', { x: n.x + (n.kind === 'state' ? w / 2 : 14), y: n.y + (n.sub ? 19 : h / 2 + 4), 'text-anchor': n.kind === 'state' ? 'middle' : 'start', text: n.label, 'font-weight': 600 }));
    if (n.sub) g.append(svg('text', { x: n.x + 14, y: n.y + 35, text: n.sub, fill: s === 'good' ? 'var(--muted)' : STC[s] }));
    if (s !== 'good' && n.kind !== 'state') g.append(svg('text', { x: n.x + w - 10, y: n.y + 17, 'text-anchor': 'end', text: STI[s], fill: STC[s], 'font-weight': 700 }));
    if (n.href) { g.style.cursor = 'pointer'; g.addEventListener('click', () => go(n.href)); g.addEventListener('keydown', (e) => { if (e.key === 'Enter') go(n.href); }); }
    if (n.tip) { g.addEventListener('pointermove', (evt) => tipShow(evt, n.label, n.tip)); g.addEventListener('pointerleave', tipHide); }
    root.append(g);
  });
  (o.notes || []).forEach(t => root.append(svg('text', { x: t.x, y: t.y, text: t.text, fill: t.color || 'var(--muted)', 'font-style': 'italic' })));
  return root;
}

// heatmap({rows:[labels], cols:[labels], values:[[..]], fmt, max, onCell(r,c)})
function heatmap(o) {
  const W = 640, m = { l: 120, t: 22 }, cw = Math.min(70, (W - m.l) / o.cols.length), ch = 24, H = m.t + o.rows.length * ch + 4;
  const max = o.max || Math.max(...o.values.flat(), 1);
  const root = svg('svg', { class: 'chart heat', viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': o.aria || 'heatmap' });
  o.cols.forEach((c, j) => root.append(svg('text', { x: m.l + j * cw + cw / 2, y: 14, 'text-anchor': 'middle', text: c })));
  o.rows.forEach((r, i) => {
    root.append(svg('text', { x: m.l - 8, y: m.t + i * ch + 16, 'text-anchor': 'end', text: r, fill: 'var(--text)' }));
    o.cols.forEach((c, j) => {
      const v = o.values[i][j], op = v <= 0 ? 0.06 : 0.18 + 0.82 * Math.min(1, v / max);
      const g = svg('g');
      const rect = svg('rect', { x: m.l + j * cw, y: m.t + i * ch, width: cw, height: ch, rx: 3, fill: o.hot && v / max > 0.6 ? 'var(--st-critical)' : 'var(--s1)', 'fill-opacity': op });
      g.append(rect);
      if (cw > 44) g.append(svg('text', { x: m.l + j * cw + cw / 2, y: m.t + i * ch + 16, 'text-anchor': 'middle', text: (o.fmt || fmt.num)(v), fill: op > .6 ? '#fff' : 'var(--text)' }));
      g.addEventListener('pointermove', (evt) => tipShow(evt, `${r} × ${c}`, [[o.valueLabel || 'Value', (o.fmt || fmt.num)(v)]]));
      g.addEventListener('pointerleave', tipHide);
      if (o.onCell) { g.style.cursor = 'pointer'; g.addEventListener('click', () => o.onCell(r, c, v)); }
      root.append(g);
    });
  });
  return root;
}

// waterfall({spans:[{name, service, start, dur, s, tags:[[k,v]]}], total})  — one trace, Gantt style
function waterfall(o) {
  const W = 680, rowH = 22, m = { l: 290, r: 60, t: 18 }, H = m.t + o.spans.length * rowH + 6, total = o.total || Math.max(...o.spans.map(s => s.start + s.dur));
  const x = scaleLinear(0, total, m.l, W - m.r);
  const root = svg('svg', { class: 'chart', viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': o.aria || 'trace waterfall' });
  for (let i = 0; i <= 4; i++) { const v = total * i / 4; root.append(svg('line', { x1: x(v), x2: x(v), y1: m.t - 4, y2: H - 4, stroke: 'var(--grid)' })); root.append(svg('text', { x: x(v), y: 10, 'text-anchor': 'middle', text: fmt.ms(v) })); }
  o.spans.forEach((sp, i) => {
    const yy = m.t + i * rowH, depth = sp.depth || 0;
    root.append(svg('text', { x: 6 + depth * 12, y: yy + 14, text: sp.service, fill: 'var(--muted)' }));
    root.append(svg('text', { x: 130 + depth * 12, y: yy + 14, text: sp.name, fill: 'var(--text)' }));
    const r = svg('rect', { class: 'bar', x: x(sp.start), y: yy + 4, width: Math.max(2, x(sp.start + sp.dur) - x(sp.start)), height: 14, rx: 3, fill: sp.s ? STC[sp.s] : 'var(--s1)' });
    r.addEventListener('pointermove', (evt) => tipShow(evt, `${sp.service} · ${sp.name}`, [['Duration', fmt.ms(sp.dur)]].concat(sp.tags || [])));
    r.addEventListener('pointerleave', tipHide);
    root.append(r);
    root.append(svg('text', { class: 'label-end', x: x(sp.start + sp.dur) + 5, y: yy + 15, text: fmt.ms(sp.dur) }));
  });
  return root;
}

function meter(o) {
  const w = el('div', { style: 'display:grid;gap:4px' });
  w.append(el('div', { style: 'display:flex;justify-content:space-between;font-size:12px', text: '' }, [el('span', { text: o.label }), el('b', { text: o.text })]));
  const track = el('div', { style: 'height:8px;border-radius:4px;background:rgba(255,255,255,.2);overflow:hidden' });
  const fill = el('div', { style: `height:100%;width:${Math.min(100, o.pct)}%;background:${o.s ? STC[o.s] : 'var(--s1)'}` });
  track.append(fill); w.append(track); return w;
}
