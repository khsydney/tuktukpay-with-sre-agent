/* TukTukPay control tower — built from splunk/control-tower/app-src; do not edit here */
(function () {
/* ===== core: state, routing, DOM helpers, tooltip, seeded data ===== */
'use strict';

const $ = (sel, root) => (root || document).querySelector(sel);
const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));
const SVG_NS = 'http://www.w3.org/2000/svg';

// el('div.card.span-6', {title: 'x'}, [children]) — children may be strings (textContent) or nodes.
function el(spec, attrs, children) {
  const [tag, ...classes] = spec.split('.');
  const node = document.createElement(tag || 'div');
  if (classes.length) node.className = classes.join(' ');
  if (attrs) for (const [k, v] of Object.entries(attrs)) {
    if (v == null) continue;
    if (k === 'text') node.textContent = v;
    else if (k === 'html') node.innerHTML = v;            // only for our own static markup, never data
    else if (k.startsWith('on')) node.addEventListener(k.slice(2), v);
    else if (k === 'dataset') Object.assign(node.dataset, v);
    else node.setAttribute(k, v);
  }
  (children || []).forEach(c => { if (c == null) return; node.append(typeof c === 'string' ? document.createTextNode(c) : c); });
  return node;
}
function svg(tag, attrs, children) {
  const node = document.createElementNS(SVG_NS, tag);
  if (attrs) for (const [k, v] of Object.entries(attrs)) {
    if (v == null) continue;
    if (k === 'text') node.textContent = v;
    else if (k.startsWith('on')) node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v);
  }
  (children || []).forEach(c => { if (c != null) node.append(c); });
  return node;
}
const fmt = {
  num: (v, d = 0) => v == null ? '–' : Math.abs(v) >= 1e6 ? (v / 1e6).toFixed(1) + 'M' : Math.abs(v) >= 1e4 ? (v / 1e3).toFixed(0) + 'K' : Math.abs(v) >= 1e3 ? (v / 1e3).toFixed(1) + 'K' : Number(v).toFixed(d),
  pct: (v, d = 1) => v == null ? '–' : Number(v).toFixed(d) + '%',
  ms: (v) => v == null ? '–' : v >= 1000 ? (v / 1000).toFixed(2) + ' s' : Math.round(v) + ' ms',
  usd: (v) => v == null ? '–' : '$' + Number(v).toFixed(2),
  thb: (v) => v == null ? '–' : '฿' + fmt.num(v),
  signed: (v, d = 1) => (v > 0 ? '+' : '') + Number(v).toFixed(d),
};

/* ---- scenario state ---- */
const ACTS = {
  baseline: { label: 'Baseline', pill: 'Healthy', blurb: '11.11 ramp running normally: ~1,150 payments per 5 minutes, approval rate ≈ 91%, agents ≈ 5% of traffic.' },
  act1: { label: 'Act 1 · The one-in-ten-thousand decline', pill: 'Act 1 running', blurb: 'Festival spike ×10 and KBank hangs only for THB cards with BIN 457173 at merchant thai-airways; the router times out at 2.5 s and fails over to a backup acquirer with poor domestic approval.' },
  act2: { label: 'Act 2 · The model that drifted', pill: 'Act 2 running', blurb: 'Risk model v3 canary (20% of traffic) burns CPU on inference and false-declines wallets in IDR/PHP. Approval rate drops only for risk.model_version=v3.' },
  act3: { label: 'Act 3 · The copilot bill', pill: 'Act 3 running', blurb: 'The merchant copilot enters a tool-call loop (12 iterations, about 12× tokens per question) while prompt-injection questions try to trigger refund_payment; the guardrail blocks it.' },
  act4: { label: 'Act 4 · Agents are buying', pill: 'Act 4 running', blurb: 'Agent traffic surges to 25% of payments; 15% of mandates are violated (overspend, replay, forged token, wrong merchant, expired) and a poisoned listing injects instructions into shopping agents.' },
  act4b: { label: 'Act 4b · Know-Your-Agent registry down', pill: 'Act 4b running', blurb: 'The wallet’s Know-Your-Agent (KYA) registry stops answering. Every agent payment fails closed with mandate_kya_unavailable; human checkout is untouched.' },
  act5: { label: 'Act 5 · Ask, don’t dig', pill: 'Act 5 running', blurb: 'Ledger connection pool shrinks and INSERTs slow down; one merchant’s webhook endpoint turns flaky and retries pile up behind the payment stream.' },
  act6: { label: 'Act 6 · The leaky ledger', pill: 'Act 6 running', blurb: 'The ledger retains 6 MiB/s until its 384 MiB limit: OOMKilled, restart loop, a Kubernetes alert and a Remediation Plan from the AI Troubleshooting Agent.' },
  act7: { label: 'Act 7 · The bad rollout', pill: 'Act 7 running', blurb: 'wallet-sim exits 3 seconds after start as if a schema migration failed: CrashLoopBackOff, and every mandate-backed agent payment fails closed.' },
};
const RANGES = { '15m': { label: 'Last 15 min', n: 15, step: 60, span: '1m', earliest: '-15m' }, '1h': { label: 'Last 1 hour', n: 60, step: 60, span: '2m', earliest: '-60m' }, '4h': { label: 'Last 4 hours', n: 48, step: 300, span: '5m', earliest: '-4h' }, '24h': { label: 'Last 24 hours', n: 48, step: 1800, span: '30m', earliest: '-24h' } };
const S = { act: 'baseline', range: '1h', env: 'tuktukpay-demo' };
const INCIDENT_MIN_AGO = 11;   // the act "started" 11 minutes before "now" (21:14 → 21:03), whatever the range
function incidentAt() { const r = RANGES[S.range]; return Math.max(0.05, 1 - INCIDENT_MIN_AGO * 60 / ((r.n - 1) * r.step)); }

/* ---- seeded pseudo-random data so every page shows the same numbers for the same act ---- */
function hash(s) { let h = 2166136261; for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); } return h >>> 0; }
function rng(seed) { let a = hash(seed); return () => { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
// series(key, fn) → array of n values; fn(t, incident) where t in [0,1] across the window and incident in [0,1] after the act starts (0 before).
function series(key, fn, noise = 0.04) {
  const n = RANGES[S.range].n, r = rng(key + ':' + S.act + ':' + S.range), out = [];
  for (let i = 0; i < n; i++) {
    const t = i / (n - 1), ia = incidentAt(), inc = S.act === 'baseline' ? 0 : Math.max(0, (t - ia) / (1 - ia));
    const v = fn(t, inc, i);
    out.push(v * (1 + (r() - 0.5) * 2 * noise));
  }
  return out;
}
const last = (a) => a[a.length - 1];
const avg = (a) => a.reduce((x, y) => x + y, 0) / a.length;
const ramp = (inc, k = 6) => 1 - Math.exp(-inc * k);          // fast rise after the incident starts
const inAct = (...acts) => acts.includes(S.act);
function timeLabels() {
  const { n, step } = RANGES[S.range], now = new Date(2026, 10, 11, 21, 14), out = [];
  for (let i = 0; i < n; i++) { const d = new Date(now.getTime() - (n - 1 - i) * step * 1000); out.push(d.toTimeString().slice(0, 5)); }
  return out;
}
const status = (v, warn, crit, higherIsBad = true) => higherIsBad ? (v >= crit ? 'critical' : v >= warn ? 'warning' : 'good') : (v <= crit ? 'critical' : v <= warn ? 'warning' : 'good');

/* ---- shared tooltip (one node, textContent only) ---- */
const tip = { node: null, title: null, rows: null };
function tipInit() {
  tip.node = el('div.tip', { role: 'status', 'aria-live': 'polite' });
  tip.title = el('div.t'); tip.rows = el('div');
  tip.node.append(tip.title, tip.rows); document.body.append(tip.node);
}
function tipShow(evt, title, rows) {
  tip.title.textContent = title || ''; tip.rows.replaceChildren();
  (rows || []).forEach(([k, v, c]) => {
    const key = el('span.k'); if (c) { const i = el('i'); i.style.setProperty('--c', c); key.append(i); } key.append(document.createTextNode(k));
    tip.rows.append(el('div.r', null, [key, el('span.v', { text: String(v) })]));
  });
  tipMove(evt); tip.node.classList.add('show');
}
function tipMove(evt) {
  const w = tip.node.offsetWidth || 160, h = tip.node.offsetHeight || 60;
  let x = evt.clientX + 14, y = evt.clientY + 14;
  if (x + w > window.innerWidth - 8) x = evt.clientX - w - 14;
  if (y + h > window.innerHeight - 8) y = evt.clientY - h - 14;
  tip.node.style.left = x + 'px'; tip.node.style.top = y + 'px';
}
function tipHide() { tip.node.classList.remove('show'); }

/* ---- toast ---- */
function toast(msg) { const t = $('#toast'); t.textContent = msg; t.classList.add('show'); clearTimeout(toast.timer); toast.timer = setTimeout(() => t.classList.remove('show'), 5000); }

/* ---- deep links into Observability Cloud (realm us1); the mock-up only shows where a click would go ---- */
const O11Y = 'https://app.us1.signalfx.com/#';
const links = {
  apm: (svc) => `${O11Y}/apm/troubleshooting?environments=${S.env}&service=${svc}`,
  trace: (id) => `${O11Y}/apm/traces/${id}`,
  tagSpotlight: (svc, tag) => `${O11Y}/apm/tagspotlight?environments=${S.env}&service=${svc}&tag=${tag}`,
  k8s: (pod) => `${O11Y}/infra/entity/kubernetes?pod=${pod}`,
  detector: (name) => `${O11Y}/alerts?detector=${encodeURIComponent(name)}`,
  logs: (spl) => `https://example-stack.splunkcloud.com/en-US/app/search/search?q=${encodeURIComponent('search index=tuktukpay ' + spl)}`,
};
function fakeNav(evt, what, url) { evt.preventDefault(); toast(`Mock-up: this would open ${what} → ${url}`); }

/* ---- card + lane badge helpers ---- */
const LANES = {
  metrics: { lane: 'metrics', text: 'O11y Metric Search', title: 'Dashboard Studio “O11y Metric Search” data source: SignalFlow run live in Observability Cloud, nothing indexed in Splunk Cloud' },
  sim: { lane: 'metrics', text: 'sim_metrics', title: 'Infrastructure Monitoring Add-on modular input streaming SignalFlow results into index sim_metrics (license-exempt), queried with mstats' },
  simflow: { lane: 'metrics', text: '| sim flow', title: 'On-demand SignalFlow through the sim command, run only when this page is opened' },
  logs: { lane: 'logs', text: 'HEC logs · index=tuktukpay', title: 'Structured JSON events from every service over HEC (HTTP Event Collector), searched with SPL' },
  alerts: { lane: 'alerts', text: 'detector events (HEC)', title: 'Observability Cloud detectors → “Splunk platform” notification integration → index tuktukpay_alerts' },
  spans: { lane: 'spans', text: 'spans · dual-export', title: 'OpenTelemetry Collector splunk_hec exporter copies a filtered set of spans (errors, slow, agent-initiated, 1-in-20 baseline) with every tag into index tuktukpay_traces; Observability Cloud keeps the full-fidelity original' },
  kv: { lane: 'kv', text: 'KV Store / lookup', title: 'Reference data kept in Splunk Cloud: acquirer catalogue, BIN ranges, merchant list, the PSP reconciliation file' },
  mcp: { lane: 'mcp', text: 'MCP gateway', title: 'Splunk MCP Gateway: o11y_* tools for Observability Cloud plus splunk_* tools for SPL in the same assistant session' },
};
function laneBadge(key) { const l = LANES[key]; return el('span.lane', { dataset: { lane: l.lane }, title: l.title, text: l.text }); }
// card({title, sub, lanes:['logs'], span:6, link:{label, url, what}, body: node|fn, table: fn → table node, note})
function card(o) {
  const c = el('div.card.span-' + (o.span || 6));
  const head = el('div.card-head', null, [el('h3', { text: o.title })]);
  (o.lanes || []).forEach(k => head.append(laneBadge(k)));
  const tools = el('div.tools');
  let tableOn = false, bodyNode, tableNode;
  const body = el('div.body');
  const render = () => {
    body.replaceChildren();
    if (tableOn && o.table) { tableNode = tableNode || o.table(); body.append(tableNode); }
    else { bodyNode = bodyNode || (typeof o.body === 'function' ? o.body() : o.body); body.append(bodyNode); }
  };
  if (o.table) tools.append(el('button', { type: 'button', 'aria-pressed': 'false', text: 'Table', onclick: (e) => { tableOn = !tableOn; e.currentTarget.setAttribute('aria-pressed', String(tableOn)); render(); } }));
  if (o.link) tools.append(el('a', { href: o.link.url, text: o.link.label, onclick: (e) => fakeNav(e, o.link.what || o.link.label, o.link.url) }));
  head.append(tools); c.append(head);
  if (o.sub) c.append(el('div.card-sub', { text: o.sub }));
  render(); c.append(body);
  if (o.note) c.append(el('div.note', { text: o.note }));
  return c;
}
function simpleTable(columns, rows, opts) {
  const t = el('table.tbl'); const thead = el('thead'); const tr = el('tr');
  columns.forEach(col => tr.append(el('th' + (col.num ? '.num' : ''), { text: col.label }))); thead.append(tr); t.append(thead);
  const tb = el('tbody');
  rows.forEach(row => {
    const r = el('tr' + (opts && opts.onRow ? '.row-link' : ''));
    columns.forEach(col => {
      const td = el('td' + (col.num ? '.num' : ''));
      const v = row[col.key];
      if (col.status) td.append(el('span.cell-s', { dataset: { s: col.status(row) } }));
      td.append(document.createTextNode(col.fmt ? col.fmt(v, row) : String(v == null ? '–' : v)));
      r.append(td);
    });
    if (opts && opts.onRow) r.addEventListener('click', () => opts.onRow(row));
    tb.append(r);
  });
  t.append(tb); return el('div.tbl-wrap', null, [t]);
}
function tableFromSeries(labels, seriesList, fmtFn) {
  const cols = [{ key: 't', label: 'Time' }].concat(seriesList.map((s, i) => ({ key: 's' + i, label: s.name, num: true, fmt: (v) => fmtFn ? fmtFn(v) : fmt.num(v, 1) })));
  const rows = labels.map((t, i) => { const r = { t }; seriesList.forEach((s, j) => r['s' + j] = s.values[i]); return r; });
  return simpleTable(cols, rows);
}

/* ---- routing ---- */
const PAGES = {};        // id → { title, group, nav, acts, render(params) }
function route() {
  const h = location.hash.replace(/^#\/?/, '') || 'overview';
  const [path, qs] = h.split('?');
  const parts = path.split('/'); const id = parts[0]; const param = parts.slice(1).join('/');
  const page = PAGES[id] || PAGES.overview;
  const content = $('#content'); content.replaceChildren();
  const crumbs = el('div.crumbs'); crumbs.append(el('a', { href: '#/overview', text: 'Control tower' }));
  if (id !== 'overview') { crumbs.append(' / '); crumbs.append(el('a', { href: '#/' + id, text: page.title })); }
  if (param) { crumbs.append(' / '); crumbs.append(document.createTextNode(decodeURIComponent(param))); }
  content.append(crumbs);
  if (S.act !== 'baseline') content.append(el('div.callout.act-banner', null, [el('b', { text: ACTS[S.act].label + ' — ' }), document.createTextNode(ACTS[S.act].blurb)]));
  try { content.append(page.render(param)); } catch (e) { console.error(e); content.append(el('div.callout', { text: 'This page failed to render: ' + e.message })); }
  $$('.nav a').forEach(a => a.classList.toggle('active', a.getAttribute('href') === '#/' + id));
  window.scrollTo({ top: 0 });
}
function go(hashPath) { location.hash = hashPath; }
function pageHeader(title, lead, acts) {
  const w = el('div');
  w.append(el('div.page-title', null, [el('h2', { text: title }), acts ? el('span.acts', { text: 'Acts ' + acts }) : null]));
  if (lead) w.append(el('p.page-lead', { text: lead }));
  return w;
}
function rerender() { $('#act-pill').textContent = ACTS[S.act].pill; $('#act-pill').classList.toggle('on', S.act !== 'baseline'); navStatus(); route(); }

/* ---- sidebar status dots per page (the war-room "is this act hurting that page" glance) ---- */
function pageStatus(id) {
  const m = {
    overview: { act1: 'critical', act2: 'serious', act3: 'warning', act4: 'serious', act4b: 'critical', act5: 'warning', act6: 'critical', act7: 'critical' },
    flow: { act1: 'critical', act2: 'warning', act4b: 'critical', act5: 'warning', act6: 'critical', act7: 'critical' },
    acquirers: { act1: 'critical' },
    agentic: { act4: 'serious', act4b: 'critical', act7: 'critical' },
    risk: { act2: 'critical' },
    copilot: { act3: 'critical' },
    ledger: { act5: 'warning', act6: 'critical' },
    k8s: { act6: 'critical', act7: 'critical' },
    incidents: { act1: 'critical', act2: 'serious', act3: 'warning', act4: 'serious', act4b: 'critical', act5: 'warning', act6: 'critical', act7: 'critical' },
    forensics: { act1: 'critical' },
  };
  return (m[id] && m[id][S.act]) || 'good';
}
function navStatus() { $$('.nav a').forEach(a => { const id = a.getAttribute('href').replace('#/', ''); const d = a.querySelector('.dot'); if (d) d.dataset.s = pageStatus(id); }); }

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

/* ===== live data layer: Splunk searches through the logged-in session, Observability Cloud through the
   Splunk Observability Cloud app's proxy. No credentials in the page. ===== */
const LIVE = {
  root: '/' + (location.pathname.split('/')[1] || 'en-US') + '/splunkd/__raw',
  idx: 'index=tuktukpay',
  env: 'tuktukpay-demo',
};
const PAYQ = `${LIVE.idx} event IN (payment.approved, payment.declined)`;
S.range = '1h';

function csrf() { const m = document.cookie.match(/splunkweb_csrf_token_\d+=([^;]+)/); return m ? decodeURIComponent(m[1]) : ''; }

// at most three searches in flight (the stack caps concurrent searches per user); 503 = quota hit → wait and retry
const SLOTS = { busy: 0, max: 3, q: [] };
async function slot(fn) {
  if (SLOTS.busy >= SLOTS.max) await new Promise(r => SLOTS.q.push(r));
  SLOTS.busy++;
  try { return await fn(); } finally { SLOTS.busy--; const n = SLOTS.q.shift(); if (n) n(); }
}
async function spl(query, earliest, latest) {
  for (let attempt = 0; ; attempt++) {
    try { return await slot(() => splOnce(query, earliest, latest)); }
    catch (e) { if (attempt < 3 && /HTTP (503|429)/.test(e.message)) { await new Promise(r => setTimeout(r, 1500 * (attempt + 1))); continue; } throw e; }
  }
}
// one search, one round trip (oneshot); results are rows of strings
async function splOnce(query, earliest, latest) {
  const q = query.trim().startsWith('|') ? query.trim() : 'search ' + query.trim();
  const body = new URLSearchParams({ search: q, exec_mode: 'oneshot', output_mode: 'json', count: '0',
    earliest_time: earliest || RANGES[S.range].earliest, latest_time: latest || 'now' });
  const ctl = new AbortController(); const timer = setTimeout(() => ctl.abort(), 60000);
  try {
    const res = await fetch(`${LIVE.root}/services/search/jobs`, { method: 'POST', body, credentials: 'same-origin', signal: ctl.signal,
      headers: { 'X-Splunk-Form-Key': csrf(), 'X-Requested-With': 'XMLHttpRequest', 'Content-Type': 'application/x-www-form-urlencoded' } });
    if (!res.ok) throw new Error(`search HTTP ${res.status}`);
    const d = await res.json();
    const err = (d.messages || []).find(m => m.type === 'FATAL' || m.type === 'ERROR');
    if (err) throw new Error(err.text);
    return d.results || [];
  } finally { clearTimeout(timer); }
}

async function o11yGet(path, params) {
  const qs = new URLSearchParams(Object.assign({ output_mode: 'json' }, params || {}));
  const res = await fetch(`${LIVE.root}/services/o11y${path}?${qs}`, { credentials: 'same-origin', headers: { 'X-Splunk-Form-Key': csrf(), 'X-Requested-With': 'XMLHttpRequest' } });
  if (!res.ok) throw new Error(`Observability Cloud proxy HTTP ${res.status}`);
  return res.json();
}

// Observability Cloud metric window: returns {labels, series:[{name, values}]} keyed by a dimension
async function o11yWindow(query, dim, resolutionMs, agg) {   // agg 'min': series sharing a name keep the lowest value instead of adding up
  const end = Date.now(), start = end - RANGES[S.range].n * RANGES[S.range].step * 1000;
  const res = resolutionMs || RANGES[S.range].step * 1000;
  // the API only takes these resolutions (a 30 min one is HTTP 400): fetch the nearest finer one, bucket at `res`
  const qres = [3600000, 300000, 60000, 10000, 1000].find(r => r <= res) || 1000;
  const [w, meta] = await Promise.all([
    o11yGet('/v1/timeserieswindow', { query, startMS: start, endMS: end, resolution: qres }),
    o11yGet('/v2/metrictimeseries', { query, limit: 200 }),
  ]);
  const name = {}; (meta.results || []).forEach(m => { name[m.id] = (m.dimensions || {})[dim] || m.id; });
  const buckets = []; for (let t = Math.floor(start / res) * res; t <= end; t += res) buckets.push(t);
  const byName = {};
  Object.entries(w.data || {}).forEach(([id, pts]) => {
    const n = name[id] || id; byName[n] = byName[n] || new Array(buckets.length).fill(null);
    const last = new Array(buckets.length).fill(null);   // one series: its latest value in each bucket
    pts.forEach(([ts, v]) => { const i = qres === res ? Math.round((ts - buckets[0]) / res) : Math.floor((ts - buckets[0]) / res); if (i >= 0 && i < buckets.length) last[i] = Number(v) || 0; });
    last.forEach((v, i) => { if (v != null) byName[n][i] = byName[n][i] == null ? v : agg === 'min' ? Math.min(byName[n][i], v) : byName[n][i] + v; });   // series sharing a name add up
  });
  // gauges and cumulative counters: a bucket without a datapoint keeps the last value
  Object.values(byName).forEach(a => { let prev = a.find(v => v != null) || 0; for (let i = 0; i < a.length; i++) { if (a[i] == null) a[i] = prev; else prev = a[i]; } });
  return { labels: buckets.map(t => new Date(t).toTimeString().slice(0, 5)), series: Object.entries(byName).map(([n, values]) => ({ name: n, values })) };
}

// APM p90 of one service in ms: the service's own series (not the indexed-tag breakdowns), successful requests
async function apmP90(svc) {
  const w = await o11yWindow(`sf_metric:"service.request.duration.ns.p90" AND sf_environment:"${LIVE.env}" AND sf_service:"${svc}" AND sf_error:"false" AND NOT _exists_:sf_dimensionalized`, 'sf_service');
  return { labels: w.labels, values: w.series.length ? w.series[0].values.map(v => Math.round(v / 1e6)) : [] };
}
// CPU of one container as % of its limit, the way the "container CPU at its limit" detector computes it
async function cpuPct(container) {
  const f = `k8s.namespace.name:"tuktukpay" AND k8s.container.name:"${container}"`;
  const [u, l] = await Promise.all([o11yWindow(`sf_metric:"container.cpu.usage" AND ${f}`, 'k8s.container.name'), o11yWindow(`sf_metric:"k8s.container.cpu_limit" AND ${f}`, 'k8s.container.name')]);
  const uv = (u.series[0] || {}).values || [], lv = (l.series[0] || {}).values || [];
  return { labels: u.labels, values: uv.map((v, i) => lv[i] ? Math.round(100 * v / lv[i]) : null), limit: lastNum(lv) };
}
const noErr = (p) => p.catch(e => ({ error: e.message, labels: [], values: [], series: [] }));
// per-bucket states → state-timeline segments ([{s, label}] of length n → [{from, to, s, label}])
function runs(states) {
  const n = states.length, out = [];
  states.forEach((st, i) => { const prev = out[out.length - 1]; if (prev && prev.s === st.s && prev.label === st.label) prev.to = (i + 1) / n; else out.push({ from: i / n, to: (i + 1) / n, s: st.s, label: st.label }); });
  return out.length ? out : [{ from: 0, to: 1, s: 'unknown', label: 'no data' }];
}
// what the AI Troubleshooting Agent is built to conclude for an act: shown as the expected finding, never as its live output
function expectedAgent(res, trigger) {
  if (!res) return aiAgentCard(null, trigger);
  return el('div', null, [el('div.note', { text: `Expected finding for ${ACTS[S.act].label} — the agent’s real output and Remediation Plan are on the alert in Observability Cloud.` }), aiAgentCard(res, trigger),
    el('div.btn-row', { style: 'margin-top:8px' }, [o11yLink('Open the alert in Observability Cloud', `${O11Y}/alerts`, true)])]);
}
function aiAgentCard(res, trigger) {
  if (!res) return el('div.callout', { text: 'Nothing running: the AI Troubleshooting Agent starts automatically when an APM service alert, an APM business-transaction error alert or a Kubernetes alert fires (' + trigger + ').' });
  const w = el('div', { style: 'display:grid;gap:8px;font-size:12px' });
  w.append(el('div', null, [el('b', { text: 'Impact · ' }), document.createTextNode(res.impact)]));
  const ul = el('ul', { style: 'margin:0;padding-left:16px' }); res.causes.forEach(([c, s]) => ul.append(el('li', null, [el('span.chip', { dataset: { s }, text: STI[s] }), document.createTextNode(' ' + c)]))); w.append(el('div', null, [el('b', { text: 'Suspected root causes' }), ul]));
  const ev = el('ul', { style: 'margin:0;padding-left:16px;color:var(--muted)' }); res.evidence.forEach(e => ev.append(el('li', { text: e }))); w.append(el('div', null, [el('b', { text: 'Evidence' }), ev]));
  if (res.plan) { const pl = el('ol', { style: 'margin:0;padding-left:16px' }); res.plan.forEach(p => pl.append(el('li', { text: p }))); w.append(el('div', null, [el('b', { text: 'Remediation Plan (Kubernetes alerts only, human approves each step)' }), pl])); }
  else w.append(el('div.note', { text: 'Remediation Plans are generated for Kubernetes alerts only; for APM alerts the agent stops at root cause and evidence.' }));
  return w;
}

// timechart rows → {labels, cols:{field:[numbers]}}
function tc(rows) {
  const labels = rows.map(r => r._time ? new Date(r._time).toTimeString().slice(0, 5) : '');   // local clock, like the Observability Cloud charts
  const cols = {};
  rows.forEach((r, i) => Object.keys(r).forEach(k => { if (k.startsWith('_') || k === 'NULL') return; (cols[k] = cols[k] || new Array(rows.length).fill(null))[i] = (r[k] === '' || r[k] == null || isNaN(Number(r[k]))) ? null : Number(r[k]); }));
  // an empty bucket (no payments → no rate) carries the last known value instead of dropping to zero
  Object.values(cols).forEach(a => { let prev = a.find(v => v != null); if (prev == null) prev = 0; for (let i = 0; i < a.length; i++) { if (a[i] == null) a[i] = prev; else prev = a[i]; } });
  return { labels, cols };
}
const num = (v, d = 0) => (v == null || v === '' || isNaN(Number(v))) ? null : Number(Number(v).toFixed(d));
const lastNum = (a) => { for (let i = a.length - 1; i >= 0; i--) if (a[i] != null && !isNaN(a[i])) return a[i]; return null; };
const span = () => RANGES[S.range].span;

/* ---- which act is running: the chaos flags the war-room panel logs as config.changed ---- */
// festival_spike (acts 1, 2, 4, 6) and agent_traffic_surge (acts 4, 4b, 7) are shared by several presets, so they never decide the act
const FLAG_ACT = { acquirer_kbank_timeout: 'act1', router_failover_disabled: 'act1', risk_model_drift: 'act2', copilot_tool_loop: 'act3', copilot_prompt_injection: 'act3',
  agent_mandate_violations: 'act4', catalog_prompt_injection: 'act4', kya_registry_down: 'act4b', ledger_db_slow: 'act5', webhook_merchant_flaky: 'act5',
  ledger_memory_leak: 'act6', wallet_crash_loop: 'act7' };
// A service logs only flag *transitions* it sees, so a pod that restarts with a flag already off (wallet-sim after
// Act 7's crash loop) never logs the "off" and the flag looks on forever. So an "on" counts only if no flag was switched
// off after it (a later scenario change; 30 s slack covers services logging one switch a poll apart), and the newest
// act-specific flag among those names the act.
async function detectAct() {
  const rows = await spl(`${LIVE.idx} event=config.changed | stats latest(feature_flag.enabled) as on latest(_time) as since by feature_flag.name`, '-24h');
  const lastOff = Math.max(0, ...rows.filter(r => r.on !== 'true').map(r => Number(r.since) || 0));
  const on = rows.filter(r => r.on === 'true').map(r => ({ flag: r['feature_flag.name'], since: Number(r.since) || 0 })).sort((a, b) => b.since - a.since);
  const fresh = on.filter(r => r.since >= lastOff - 30);                // switched on after the last scenario change
  const newest = FLAG_ACT[(fresh.find(r => FLAG_ACT[r.flag]) || {}).flag] || null;   // newest act-specific flag
  const live = on.filter(r => r.since >= lastOff - 30 || (newest && FLAG_ACT[r.flag] === newest));
  const acts = [...new Set(live.map(r => FLAG_ACT[r.flag]).filter(Boolean))];
  const since = live.filter(r => newest && FLAG_ACT[r.flag] === newest).map(r => r.since).filter(Boolean);
  LIVE.flags = live.map(r => r.flag); LIVE.since = since.length ? Math.min(...since) * 1000 : null;
  LIVE.detected = newest || 'baseline';                                   // the act switched on last; all live flags are listed
  S.act = S.pick && S.pick !== 'auto' ? S.pick : LIVE.detected;          // Scenario dropdown: Auto follows the flags
  LIVE.acts = acts;
}

/* ---- open detector incidents, read from the Observability Cloud API through the app's proxy (our detectors only:
   the org is shared). Detector events over HEC from the "Splunk platform" integration are merged in once it exists. ---- */
const DET_PREFIX = `TukTukPay [${LIVE.env}] `;
const SEV = { critical: 'critical', major: 'serious', minor: 'warning', warning: 'warning', info: 'warning' };
const sevOf = (v) => SEV[String(v || '').toLowerCase()] || 'serious';
// service a detector watches, from its name (Kubernetes and platform-wide detectors have none)
const DET_SVC = [['merchant-copilot', 'merchant-copilot'], ['copilot', 'merchant-copilot'], ['checkout-api', 'checkout-api'], ['risk-engine', 'risk-engine'], ['payment-router', 'payment-router'],
  ['ledger', 'ledger'], ['wallet-sim', 'wallet-sim'], ['Know-Your-Agent', 'wallet-sim'], ['merchant-sim', 'merchant-sim'], ['webhook', 'webhook-dispatcher'], ['agent', 'checkout-api'], ['approval', 'checkout-api']];
const svcOf = (name) => (DET_SVC.find(([k]) => name.includes(k)) || [])[1] || '';
LANES.alerts = { lane: 'alerts', text: 'detectors · Observability Cloud', title: 'Open incidents of the TukTukPay detectors, read live from the Observability Cloud API through the Splunk Observability Cloud app; detector events sent over HEC (HTTP Event Collector) by the “Splunk platform” notification integration are added once it is attached' };
// clock time of an incident; older than today also gets the date
const whenAt = (ms) => { if (!ms) return '–'; const d = new Date(ms), t = d.toTimeString().slice(0, 5); return d.toDateString() === new Date().toDateString() ? t : d.toLocaleDateString([], { day: 'numeric', month: 'short' }) + ' ' + t; };
const DETS = { at: 0, list: [] };
async function o11yIncidents() {
  if (Date.now() - DETS.at > 600000) {   // the detector list rarely changes: refresh it every 10 min
    const r = await o11yGet('/v2/detector', { name: DET_PREFIX.trim(), limit: 100 });
    DETS.list = (r.results || []).filter(d => d.name.startsWith(DET_PREFIX)); DETS.at = Date.now();
  }
  const per = await Promise.all(DETS.list.map(d => o11yGet(`/v2/detector/${d.id}/incidents`).catch(() => [])));
  return per.flat().filter(i => i.active !== false && i.anomalyState === 'ANOMALOUS').map(i => {
    const name = (i.detectorName || '').replace(DET_PREFIX, '');
    return { detector: name, sev: sevOf(i.severity), severity: i.severity, service: svcOf(name), since: i.anomalyStateUpdateTimestamp || ((i.events || [])[0] || {}).timestamp,
      incidentId: i.incidentId, url: `${O11Y}/detector/v2/${i.detectorId}/edit` };
  }).sort((a, b) => ['critical', 'serious', 'warning'].indexOf(a.sev) - ['critical', 'serious', 'warning'].indexOf(b.sev) || b.since - a.since);
}

/* ---- service health: error/warn log volume plus open detector incidents ---- */
async function detectHealth() {
  const [logs, hec, api] = await Promise.all([
    spl(`${LIVE.idx} severity IN (error, warn) | stats count(eval(severity="error")) as e count(eval(severity="warn")) as w by service.name`, '-10m'),
    spl(`${LIVE.idx} sourcetype="o11y:detector" | stats latest(status) as status latest(severity) as sev latest(_time) as since latest(incidentId) as incidentId latest(detectorUrl) as url by detector service.name | where status!="ok"`, '-24h'),
    o11yIncidents().catch(e => { console.warn('Observability Cloud incidents:', e.message); LIVE.incidentError = e.message; return null; }),
  ]);
  if (api) LIVE.incidentError = null;
  const st = {};
  logs.forEach(r => { const e = Number(r.e), w = Number(r.w); st[r['service.name']] = e >= 20 ? 'critical' : e >= 3 || w >= 60 ? 'serious' : e > 0 || w >= 15 ? 'warning' : 'good'; });
  const rank = { good: 0, warning: 1, serious: 2, critical: 3 };
  const det = (api || []).slice();
  hec.forEach(r => { const name = String(r.detector || '').replace(DET_PREFIX, ''); if (!det.some(d => d.detector === name)) det.push({ detector: name, sev: sevOf(r.sev), severity: r.sev, service: r['service.name'] || svcOf(name), since: Number(r.since) * 1000, incidentId: r.incidentId, url: r.url }); });
  det.forEach(r => { [r.service, /Know-Your-Agent/.test(r.detector) ? 'kya' : null].forEach(n => { if (n && rank[r.sev] > rank[st[n] || 'good']) st[n] = r.sev; }); });
  LIVE.health = st; LIVE.openDetectors = det;
}

/* ---- deep links: real ones now ---- */
function fakeNav(evt, what, url) { evt.preventDefault(); window.open(url, '_blank', 'noopener'); }
links.logs = (q) => `/${location.pathname.split('/')[1] || 'en-US'}/app/search/search?q=${encodeURIComponent('search ' + LIVE.idx + ' ' + q)}&earliest=${RANGES[S.range].earliest}&latest=now`;
const searchLink = (label, q) => el('a.btn', { href: links.logs(q), target: '_blank', rel: 'noopener', text: label });
const o11yLink = (label, url, primary) => el('a.btn' + (primary ? '.primary' : ''), { href: url, target: '_blank', rel: 'noopener', text: label });
function emptyNote(text) { return el('div.callout', { text }); }
fmt.usd = (v) => v == null ? '–' : Math.abs(v) < 1 ? '$' + Number(v).toFixed(4) : '$' + Number(v).toFixed(2);
// tables: show Splunk ISO timestamps as local HH:MM:SS
const _simpleTable = simpleTable;
simpleTable = function (columns, rows, opts) {
  return _simpleTable(columns.map(c => c.key === '_time' && !c.fmt ? Object.assign({}, c, { label: 'Time', fmt: (v) => v ? new Date(v).toLocaleTimeString([], { hour12: false }) : '–' }) : c), rows, opts);
};

/* ===== live pages: same layout and components as the mock-up, numbers from index=tuktukpay and Observability Cloud ===== */
for (const k of Object.keys(PAGES)) delete PAGES[k];
const ACQ_NAMES = { 'acq-kbank': 'KBank', 'acq-uob': 'UOB', 'acq-cimb': 'CIMB', 'acq-alipayplus': 'Alipay+', 'acq-itmx': 'ITMX' };
const APM = (svc) => `${O11Y}/apm/troubleshooting?environments=${LIVE.env}&service=${svc}`;
const TAGS = (svc, tag) => `${O11Y}/apm/tagspotlight?environments=${LIVE.env}&service=${svc}&tag=${tag}`;
const lineFrom = (t, names, colors) => names.filter(n => t.cols[n]).map((n, i) => ({ name: n, values: t.cols[n], color: colors ? colors[i] : undefined }));
const pct = (a, n) => n > 0 ? Math.round(1000 * a / n) / 10 : null;

/* ---------- Overview ---------- */
const spanMin = () => parseInt(span(), 10) || 1;
PAGES.overview = { title: 'Overview', group: 'Status', async load() {
  const s = span();
  const [k, m, risk, sk, extra, wh, p90] = await Promise.all([
    spl(`${PAYQ} | timechart span=${s} count(eval(event="payment.approved")) as a count as n count(eval('payment.initiator'="agent")) as ag | eval approval=round(100*a/n,1), share=round(100*ag/n,1), payments=n | fields _time approval share payments`),
    spl(`${LIVE.idx} event IN (mandate.verified, mandate.blocked) | timechart span=${s} count(eval(event="mandate.blocked")) as b count as n | eval blocked=if(n>0, round(100*b/n,1), 0) | fields _time blocked`),
    spl(`${PAYQ} | stats count as n count(eval(event="payment.declined")) as d by merchant.id | lookup merchants.csv merchant_id as merchant.id OUTPUT avg_ticket_thb expected_approval_pct | eval excess=max(d - n*(100-expected_approval_pct)/100, 0) | stats sum(eval(excess*avg_ticket_thb)) as thb`, '-5m'),
    spl(`${PAYQ} | eval acq='payment.acquirer', init='payment.initiator', out='payment.outcome' | stats count by init acq out | appendpipe [ stats sum(count) as value by init acq | rename init as source, acq as target ] | appendpipe [ where isnull(source) | stats sum(count) as value by acq out | rename acq as source, out as target ] | where isnotnull(source) | table source target value`, '-5m'),
    spl(`${LIVE.idx} event IN (mandate.blocked, route.failover) | eval source=if(event="mandate.blocked", "agent", 'payment.acquirer'), target=if(event="mandate.blocked", "blocked", "failover") | stats count as value by source target`, '-5m'),
    spl(`${LIVE.idx} event=webhook.backlog | timechart span=${s} max(messaging.lag_ms) as lag`),
    noErr(apmP90('checkout-api')),
  ]);
  return { k: tc(k), m: tc(m), risk: Number((risk[0] || {}).thb || 0) / 5, sk: sk.concat(extra), wh: tc(wh), p90 };
}, render(d) {
  const w = el('div');
  w.append(pageHeader('11.11 control tower', 'Read the state of the payment gateway in ten seconds, then drill to the one transaction, mandate or pod that explains it. Every panel says which data lane feeds it.'));
  const app = d.k.cols.approval || [], pay = d.k.cols.payments || [], ag = d.k.cols.share || [], mb = d.m.cols.blocked || [], p90 = d.p90.values || [], whb = (d.wh.cols.lag || []).map(v => Math.round(v / 1000));
  const L = lastNum, inc = LIVE.openDetectors || [], dl = (a) => a.length > 6 && L(a) != null ? L(a) - a[0] : null;
  w.append(el('div.tiles', null, [
    statTile({ label: `Approval rate (${span()})`, value: fmt.pct(L(app)), delta: dl(app), deltaUnit: ' pt', deltaGood: true, spark: app.length ? app : [0], status: L(app) == null ? 'good' : status(L(app), 89, 86, false), lane: 'logs', href: '#/acquirers', tipRows: [['Formula', 'authorised ÷ submitted to an acquirer'], ['Detector', 'approval rate below 85%']] }),
    statTile({ label: `Payments per ${span()}`, value: fmt.num(L(pay)), delta: pay.length > 6 && pay[0] ? Math.round((L(pay) / pay[0] - 1) * 100) : null, deltaUnit: '%', deltaGood: true, spark: pay.length ? pay : [0], lane: 'logs', href: '#/flow' }),
    statTile({ label: 'Revenue at risk / min', value: fmt.thb(Math.max(0, d.risk)), sub: 'declines above each merchant’s expected rate × avg ticket (last 5 min)', status: d.risk > 60000 ? 'critical' : d.risk > 15000 ? 'warning' : 'good', lane: 'kv', href: '#/acquirers' }),
    statTile({ label: 'Agent-initiated share', value: fmt.pct(L(ag)), delta: dl(ag), deltaUnit: ' pt', deltaGood: true, spark: ag.length ? ag : [0], status: L(ag) > 20 ? 'warning' : 'good', lane: 'logs', href: '#/agentic' }),
    statTile({ label: 'Mandates blocked', value: fmt.pct(L(mb)), delta: dl(mb), deltaUnit: ' pt', deltaGood: false, spark: mb.length ? mb : [0], status: L(mb) == null ? 'good' : status(L(mb), 10, 30), lane: 'logs', href: '#/agentic', tipRows: [['Event', 'mandate.blocked / mandate.verified'], ['Detector', 'mandate blocks above 10% of AMP payments']] }),
    statTile({ label: 'checkout-api p90', value: d.p90.error ? '–' : fmt.ms(L(p90)), delta: dl(p90) == null ? null : Math.round(dl(p90)), deltaUnit: ' ms', deltaGood: false, spark: p90.length ? p90 : [0], status: L(p90) == null ? 'good' : status(L(p90), 900, 1500), lane: 'metrics', href: '#/flow', sub: d.p90.error ? 'Observability Cloud: ' + d.p90.error : 'APM service p90' }),
    statTile({ label: 'Webhook backlog', value: fmt.num(L(whb) || 0) + ' s', spark: whb.length ? whb : [0], status: status(L(whb) || 0, 10, 30), lane: 'logs', href: '#/ledger', sub: 'messaging.lag_ms from webhook.backlog' }),
    statTile({ label: 'Open incidents', value: String(inc.length), sub: inc.length ? inc.filter(i => i.sev === 'critical').length + ' critical' : 'no detector in anomalous state', status: inc.some(i => i.sev === 'critical') ? 'critical' : inc.length ? 'warning' : 'good', lane: 'alerts', href: '#/incidents' }),
  ]));
  const g = el('div.grid', { style: 'margin-top:12px' });
  const nodes = { human: { label: 'Human checkout', color: 'var(--s1)' }, agent: { label: 'AI agent (mandate)', color: 'var(--s7)', href: '#/agentic' }, blocked: { label: 'Blocked at mandate', color: 'var(--st-serious)', href: '#/agentic' },
    approved: { label: 'Approved', color: 'var(--s3)' }, declined: { label: 'Declined', color: 'var(--st-critical)', href: '#/acquirers' }, failover: { label: 'Failed over (retried)', color: 'var(--st-warn)', href: '#/forensics' } };
  Object.entries(ACQ_NAMES).forEach(([id, n]) => nodes[id] = { label: n, color: 'var(--s4)', href: '#/acquirers/' + id });
  const links2 = d.sk.map(r => ({ s: r.source, t: r.target, v: Number(r.value) })).filter(l => l.v > 0 && nodes[l.s] && nodes[l.t]);
  const cols = [['human', 'agent'].filter(x => links2.some(l => l.s === x)), Object.keys(ACQ_NAMES).concat(['blocked']).filter(x => links2.some(l => l.t === x)), ['approved', 'declined', 'failover'].filter(x => links2.some(l => l.t === x))];
  g.append(card({ title: 'Where payments went (last 5 min)', span: 7, lanes: ['logs', 'kv'], sub: 'initiator → acquirer → outcome; click a node to open its page', body: () => links2.length ? sankey({ cols, nodes, links: links2, h: 270, aria: 'Payments by initiator, acquirer and outcome' }) : emptyNote('No payments in the last 5 minutes — is traffic paused on the war-room panel?'),
    note: 'Built from the payment, mandate.blocked and route.failover log events joined with the acquirer catalogue lookup. Datadog’s Sankey widget is limited to Product Analytics; this one runs on any SPL.',
    table: () => simpleTable([{ key: 'source', label: 'From' }, { key: 'target', label: 'To' }, { key: 'value', label: 'Payments', num: true }], d.sk) }));
  g.append(card({ title: 'Incidents (detector state)', span: 5, lanes: ['alerts'], sub: 'open incidents of the TukTukPay detectors, live from Observability Cloud', body: () => inc.length ? incidentList(inc.map(r => ({ name: r.detector, s: r.sev, when: r.since ? whenAt(r.since) : '', note: (r.service ? r.service + ' · ' : '') + 'detector state: anomalous', href: '#/incidents' })))
    : emptyNote(LIVE.incidentError ? 'Could not read incidents from Observability Cloud: ' + LIVE.incidentError : (LIVE.flags || []).length ? `No detector is anomalous yet. Chaos flags on now: ${LIVE.flags.join(', ')}.` : 'No detector is in an anomalous state. Start an act from the war-room panel to see the tower react.') }));
  const since = LIVE.since && S.act === LIVE.detected && Date.now() - LIVE.since < 86400000 ? d.k.labels.findIndex(l => l >= new Date(LIVE.since).toTimeString().slice(0, 5)) : -1;   // first bucket after the act started
  g.append(card({ title: 'Approval rate and agent share', span: 7, lanes: ['logs'], body: () => lineChart({ labels: d.k.labels, series: [{ name: 'Approval %', values: app, color: 'var(--s1)' }, { name: 'Agent share %', values: ag, color: 'var(--s7)' }], yMin: 0, yMax: 100, yFmt: (v) => fmt.num(v) + '%', thresholds: [{ value: 85, label: 'detector 85%' }],
    bands: since >= 0 ? [{ from: since, to: d.k.labels.length - 1, label: ACTS[S.act].label.split(' · ')[0] + ' started' }] : [] }),
    table: () => tableFromSeries(d.k.labels, [{ name: 'Approval %', values: app }, { name: 'Agent %', values: ag }]) }));
  g.append(card({ title: 'Service health strip', span: 5, lanes: ['alerts', 'logs'], sub: 'detector state and error logs per service; full map on the Flow page', body: () => healthStrip() }));
  w.append(g); return w;
} };
function healthStrip() {
  const st = LIVE.health || {}, items = [['checkout-api', '#/flow'], ['risk-engine', '#/risk'], ['payment-router', '#/acquirers'], ['acquirer-sim', '#/acquirers'], ['ledger', '#/ledger'], ['webhook-dispatcher', '#/ledger'], ['merchant-copilot', '#/copilot'], ['shopping-agent', '#/agentic'], ['wallet-sim', '#/k8s'], ['kya', '#/agentic']];
  const w = el('div', { style: 'display:flex;flex-wrap:wrap;gap:6px' });
  items.forEach(([id, href]) => { const s = st[id] || 'good'; w.append(el('button.chip', { type: 'button', dataset: { s }, text: STI[s] + ' ' + id, onclick: () => go(href), style: 'background:transparent;cursor:pointer' })); });
  return w;
}

/* ---------- Payment flow map ---------- */
PAGES.flow = { title: 'Payment flow map', group: 'Status', async load() {
  const [acq, p90, slow, kya, rk, ld] = await Promise.all([
    spl(`${PAYQ} | stats count as n count(eval(event="payment.approved")) as a by payment.acquirer | join type=left payment.acquirer [ search ${LIVE.idx} event IN (acquirer.timeout, route.failover, acquirer.host_unresponsive) | stats count as t by payment.acquirer ]`, '-10m'),
    spl(`${PAYQ} | stats perc90(duration_ms) as p90`, '-10m'),
    spl(`${LIVE.idx} event IN (ledger.write_slow, db.pool.wait, ledger.write_failed, risk.inference_slow, webhook.delivery_failed, kya.registry_unavailable, service.crashed, memory.pressure) | stats count by event`, '-10m'),
    spl(`${LIVE.idx} event=mandate.blocked mandate.block_reason=mandate_kya_unavailable | stats count`, '-10m'),
    noErr(apmP90('risk-engine')), noErr(apmP90('ledger')),
  ]);
  return { acq, p90: Number((p90[0] || {}).p90 || 0), ev: Object.fromEntries(slow.map(r => [r.event, Number(r.count)])), kyaBlocked: Number((kya[0] || {}).count || 0), rk: lastNum(rk.values || []), ld: lastNum(ld.values || []) };
}, render(d) {
  const st = Object.assign({}, LIVE.health || {}), ev = d.ev;
  const acqSt = {}; d.acq.forEach(r => { const ap = pct(Number(r.a), Number(r.n)), t = Number(r.t || 0); acqSt[r['payment.acquirer']] = t > 50 ? 'critical' : t > 5 || (ap != null && ap < 80) ? 'serious' : 'good'; });
  if (ev['kya.registry_unavailable'] || d.kyaBlocked) { st.kya = 'critical'; st['shopping-agent'] = 'critical'; }
  if (ev['service.crashed']) st['wallet-sim'] = 'critical';
  if (ev['memory.pressure']) st.ledger = 'critical'; else if (ev['ledger.write_slow'] || ev['db.pool.wait']) st.ledger = st.ledger === 'critical' ? 'critical' : 'serious';
  if (ev['webhook.delivery_failed']) st['webhook-dispatcher'] = 'warning';
  if (ev['risk.inference_slow']) st['risk-engine'] = st['risk-engine'] || 'warning';
  Object.assign(st, acqSt);
  const N = (id, label, x, y, sub, href, w2) => ({ id, label, x, y, w: w2 || 150, s: st[id] || 'good', sub, href });
  const fo = d.acq.reduce((a, r) => a + Number(r.t || 0), 0);
  const nodes = [
    N('shopping-agent', 'Shopping agents', 20, 40, 'AMP · AP2 · TAP', '#/agentic'), N('merchant-storefront', 'Storefront / API', 20, 150, 'web · app · api', '#/overview'),
    N('wallet-sim', 'Wallet (mandates)', 20, 260, 'issues task mandates', '#/agentic'), N('kya', 'KYA registry', 20, 350, 'ratings A–D', '#/agentic'),
    N('checkout-api', 'checkout-api', 250, 150, 'Go · p90 ' + fmt.ms(d.p90), '#/forensics', 140), N('risk-engine', 'risk-engine', 470, 50, 'Python · p90 ' + fmt.ms(d.rk), '#/risk'),
    N('payment-router', 'payment-router', 470, 150, 'Java · failovers ' + fo, '#/acquirers'), N('ledger', 'ledger', 470, 260, 'Node · Postgres · p90 ' + fmt.ms(d.ld), '#/ledger'),
    N('webhook-dispatcher', 'webhook-dispatcher', 470, 350, 'Python · Redis Streams', '#/ledger'),
    ...Object.entries(ACQ_NAMES).map(([id, n], i) => N(id, n, 700, 20 + i * 60, (() => { const r = d.acq.find(x => x['payment.acquirer'] === id); return r ? `approval ${fmt.pct(pct(Number(r.a), Number(r.n)))}` : 'no traffic'; })(), '#/acquirers/' + id, 110)),
    N('merchant-sim', 'Merchants', 700, 350, 'webhook endpoints', '#/ledger', 110), N('merchant-copilot', 'merchant-copilot', 850, 150, 'LLM · tools', '#/copilot', 100), N('llm', 'LLM provider', 850, 50, 'Bedrock / mock', '#/copilot', 100),
  ];
  const hot = (id) => st[id] === 'critical' ? 'hot' : st[id] === 'serious' || st[id] === 'warning' ? 'warm' : 'edge';
  const edges = [
    { from: 'merchant-storefront', to: 'checkout-api', label: '/v1/payments', labelDy: 14 }, { from: 'shopping-agent', to: 'checkout-api', label: 'mandate + payment', cls: hot('shopping-agent') },
    { from: 'wallet-sim', to: 'shopping-agent', dash: true, via: [[10, 283], [10, 63]] }, { from: 'checkout-api', to: 'kya', label: 'verify mandate → KYA', cls: hot('kya'), via: [[320, 373]] },
    { from: 'checkout-api', to: 'risk-engine', label: 'score', cls: hot('risk-engine') }, { from: 'checkout-api', to: 'payment-router', label: 'authorise', cls: hot('payment-router') },
    { from: 'checkout-api', to: 'ledger', label: 'record', cls: hot('ledger') }, { from: 'ledger', to: 'webhook-dispatcher', label: 'stream', dash: true },
    { from: 'webhook-dispatcher', to: 'merchant-sim', label: 'webhooks', cls: hot('webhook-dispatcher'), labelDy: 14 },
    ...Object.keys(ACQ_NAMES).map(id => ({ from: 'payment-router', to: id, cls: hot(id) })),
    { from: 'merchant-copilot', to: 'llm', label: 'chat · execute_tool', cls: hot('merchant-copilot') }, { from: 'merchant-copilot', to: 'ledger', label: 'tool: lookup_payment', dash: true, via: [[900, 330], [640, 330]] },
  ];
  const w = el('div');
  w.append(pageHeader('Payment flow map', 'The gateway as the PSP sees it: every box is a service or a counterparty, coloured by the worst detector or error-log state feeding it in the last 10 minutes (colour plus icon, never colour alone). Click a box for its page.', '1 · 2 · 4 · 4b · 5 · 6 · 7'));
  const g = el('div.grid');
  g.append(card({ title: 'Live service and counterparty map', span: 12, lanes: ['alerts', 'metrics', 'logs'], body: () => flowMap({ w: 960, h: 410, key: 'flow', nodes, edges, aria: 'Service map coloured by detector state' }),
    note: 'Node colour = worst of the open detector incidents (Observability Cloud) and the error / warning log volume of the last 10 minutes; p90 on the risk-engine and ledger boxes is the APM service p90. In Dashboard Studio this is the Network Graph visualisation (Splunk Cloud 10.4.2604+).' }));
  const bad = nodes.filter(n => n.s !== 'good').map(n => `${n.label} ${n.s}`);
  g.append(card({ title: 'What the colours mean today', span: 6, lanes: ['alerts'], body: () => el('div.callout', { text: S.act !== 'baseline' ? ACTS[S.act].blurb + (bad.length ? '  Now: ' + bad.join(', ') + '.' : '') : bad.length ? 'Not all clear: ' + bad.join(', ') + '. Open the box for the evidence.' : 'All detectors clear and no error bursts in the logs. The map changes colour the moment a detector fires.' }) }));
  g.append(card({ title: 'Jump straight to the evidence', span: 6, lanes: ['mcp'], body: () => el('div.btn-row', null, [
    o11yLink('checkout-api in APM', APM('checkout-api'), true), o11yLink('Tag Spotlight · payment.acquirer', TAGS('checkout-api', 'payment.acquirer')),
    searchLink('SPL · failovers by backup acquirer', 'event=route.failover | stats count by payment.acquirer route.backup_acquirer'),
    el('button.btn', { type: 'button', text: 'Ask: why is approval down?', onclick: () => askOpen('why') }) ]) }));
  w.append(g); return w;
} };

/* ---------- Acquirers & issuers (+ entity page) ---------- */
PAGES.acquirers = { title: 'Acquirers & issuers', group: 'Payments', async load(param) {
  const s = span();
  if (param) {
    const [ap, codes, bins, meta] = await Promise.all([
      spl(`${LIVE.idx} (event IN (payment.approved, payment.declined, route.failover)) payment.acquirer="${param}" | timechart span=${s} count(eval(event="payment.approved")) as a count(eval(event!="route.failover")) as n count(eval(event="route.failover")) as failovers perc90(acquirer.latency_ms) as p90 | eval approval=round(100*a/n,1) | fields _time approval p90 failovers`),
      spl(`${LIVE.idx} event IN (acquirer.authorised, acquirer.declined) payment.acquirer="${param}" | stats count by acquirer.response_code | sort - count | head 8`),
      spl(`${LIVE.idx} event IN (payment.approved, payment.declined, route.failover) payment.acquirer="${param}" | stats count(eval(event!="route.failover")) as n count(eval(event!="payment.approved")) as err values(merchant.id) as merchant latest(payment.card.network) as payment.card.network by payment.card.bin | where err>0 | eval rate=round(100*err/max(n,1),2) | sort - err | head 8`),
      spl(`${PAYQ} | stats count as n count(eval('payment.acquirer'="${param}")) as mine | eval share=round(100*mine/n,1) | eval id="${param}" | lookup acquirers.csv id OUTPUT role`),
    ]);
    return { param, ap: tc(ap), codes, bins, meta };
  }
  const [score, ap, mix, heat, fo] = await Promise.all([
    spl(`${PAYQ} | stats count as payments count(eval(event="payment.approved")) as approved perc90(acquirer.latency_ms) as p90 by payment.acquirer | eventstats sum(payments) as total | eval share=round(100*payments/total,1), approval=round(100*approved/payments,1), p90=round(p90) | lookup acquirers.csv id as payment.acquirer OUTPUT name role | sort - share`),
    spl(`${PAYQ} | eval acq='payment.acquirer' | bin _time span=${s} | stats count(eval(event="payment.approved")) as a count as n by _time acq | eval ap=round(100*a/n,1) | xyseries _time acq ap`),
    spl(`${LIVE.idx} event IN (payment.declined, route.failover, payment.rejected) | eval bucket=case(event="route.failover", "timeout / failover", event="payment.rejected", "invalid", 'payment.decline_reason'="risk_declined" OR like('payment.decline_reason', "mandate_%"), "blocked (risk / mandate)", true(), "issuer declined") | timechart span=${s} count by bucket`),
    spl(`${LIVE.idx} event IN (payment.declined, route.failover) | eval acq='payment.acquirer', bin='payment.card.bin' | chart count over bin by acq limit=10 | addtotals | sort - Total | head 6`, '-15m'),
    spl(`${LIVE.idx} event=route.failover | timechart span=${s} count as failovers`),
  ]);
  return { score, ap: tc(ap), mix: tc(mix), heat, fo: tc(fo) };
}, render(d, param) {
  if (param) return acquirerEntityLive(d);
  const w = el('div');
  w.append(pageHeader('Acquirers and issuers', 'Authorisation rate per acquirer (authorised ÷ submitted), the decline mix split the way Stripe and Adyen report it, and the BIN-level view that finds the one-in-ten-thousand decline.', '1 · 2'));
  const g = el('div.grid');
  const rows = d.score.map(r => { const a = d.ap.cols[r['payment.acquirer']] || []; return Object.assign({}, r, { delta: a.length > 1 ? lastNum(a) - a[0] : null }); });
  g.append(card({ title: 'Acquirer scorecard', span: 12, lanes: ['logs', 'kv'], body: () => simpleTable([
    { key: 'name', label: 'Acquirer', status: (r) => Number(r.approval) < 80 ? 'critical' : Number(r.approval) < 86 ? 'warning' : 'good' }, { key: 'share', label: 'Share of volume', num: true, fmt: (v) => fmt.pct(Number(v), 0) }, { key: 'approval', label: 'Approval rate', num: true, fmt: (v) => fmt.pct(Number(v)) },
    { key: 'delta', label: 'Δ vs range start', num: true, fmt: (v) => v == null ? '–' : fmt.signed(v) + ' pt' }, { key: 'p90', label: 'p90 latency', num: true, fmt: (v) => fmt.ms(Number(v)) }, { key: 'role', label: 'Role' }], rows, { onRow: (r) => go('#/acquirers/' + r['payment.acquirer']) }),
    note: 'Rows open the acquirer page. Approval rate = payment.approved ÷ (approved + declined) by payment.acquirer from the logs; p90 is acquirer.latency_ms; the role column is the acquirers.csv lookup.' }));
  const acqSeries = Object.keys(d.ap.cols).map((k, i) => ({ name: ACQ_NAMES[k] || k, values: d.ap.cols[k], color: seriesColor(i) }));
  g.append(card({ title: 'Approval rate by acquirer', span: 7, lanes: ['logs'], body: () => acqSeries.length ? lineChart({ labels: d.ap.labels, series: acqSeries, yMin: 70, yMax: 100, yFmt: (v) => fmt.num(v) + '%', h: 200 }) : emptyNote('No payments in range.'),
    table: () => tableFromSeries(d.ap.labels, acqSeries, (v) => fmt.pct(v)) }));
  const order = ['issuer declined', 'blocked (risk / mandate)', 'timeout / failover', 'invalid'], names = ['Issuer declined', 'Blocked (risk / mandate)', 'Timeout / failover', 'Invalid'], colors = ['var(--s1)', 'var(--s7)', 'var(--s2)', 'var(--s4)'];
  const mixSeries = order.map((n, i) => ({ name: names[i], values: d.mix.cols[n] || d.mix.labels.map(() => 0), color: colors[i] }));
  g.append(card({ title: 'Decline mix', span: 5, lanes: ['logs'], sub: 'issuer declined · blocked before the network (risk / mandate) · timeout & failover · invalid request', body: () => d.mix.labels.length ? stackedColumns({ labels: d.mix.labels, series: mixSeries, h: 200 }) : emptyNote('No declines in range.'),
    table: () => tableFromSeries(d.mix.labels, mixSeries), note: 'SPL over payment.declined / route.failover / payment.rejected events; the buckets follow Stripe’s decline taxonomy so the PSP’s operators recognise them.' }));
  const acqCols = Object.keys(ACQ_NAMES).filter(a => d.heat.some(r => r[a] != null));
  g.append(card({ title: 'Errors by BIN prefix × acquirer (last 15 min)', span: 7, lanes: ['logs'], sub: 'the needle: one BIN at one acquirer',
    body: () => d.heat.length ? heatmap({ rows: d.heat.map(r => r.bin), cols: acqCols.map(a => ACQ_NAMES[a]), values: d.heat.map(r => acqCols.map(a => Number(r[a] || 0))), hot: true, valueLabel: 'declines + failovers',
      onCell: (bin, acqName, v) => { if (v > 10) go('#/forensics'); else { const id = Object.keys(ACQ_NAMES).find(k => ACQ_NAMES[k] === acqName); window.open(links.logs(`event IN (payment.declined, route.failover) payment.card.bin=${bin} payment.acquirer=${id}`), '_blank'); } } }) : emptyNote('No declines or failovers in the last 15 minutes.'),
    note: 'payment.declined + route.failover events by payment.card.bin × payment.acquirer (Observability Cloud keeps every trace too; Trace Analyzer finds the same cell without indexing the tag). A hot cell opens the trace forensics.' }));
  const fpm = (d.fo.cols.failovers || []).map(v => Math.round(10 * v / spanMin()) / 10);
  g.append(card({ title: 'Failovers per minute', span: 5, lanes: ['logs'], body: () => lineChart({ labels: d.fo.labels.length ? d.fo.labels : ['–'], series: [{ name: 'route.failover', values: fpm.length ? fpm : [0], color: 'var(--s2)' }], h: 200 }),
    note: 'route.failover events from payment-router; the Act 1 signature is failovers rising while KBank p90 climbs to the 2.5 s timeout.' }));
  w.append(g); return w;
} };
function acquirerEntityLive(d) {
  const id = d.param, name = ACQ_NAMES[id] || id, ap = d.ap.cols.approval || [], p90 = d.ap.cols.p90 || [], fo = d.ap.cols.failovers || [];
  const role = (d.meta[0] || {}).role, share = Number((d.meta[0] || {}).share);
  const w = el('div');
  w.append(pageHeader(`${name} (${id})`, (role ? role + '. ' : '') + 'Entity page: everything the tower knows about this counterparty, with the deep link into the APM service that talks to it.', '1'));
  const dl = (a) => a.length > 1 && lastNum(a) != null ? lastNum(a) - a[0] : null;
  w.append(el('div.tiles', null, [
    statTile({ label: 'Approval rate', value: fmt.pct(lastNum(ap)), delta: dl(ap), deltaUnit: ' pt', deltaGood: true, spark: ap.length ? ap : [0], status: lastNum(ap) == null ? 'good' : status(lastNum(ap), 86, 80, false), lane: 'logs' }),
    statTile({ label: 'p90 latency', value: fmt.ms(lastNum(p90)), delta: dl(p90) == null ? null : Math.round(dl(p90)), deltaUnit: ' ms', deltaGood: false, spark: p90.length ? p90 : [0], status: lastNum(p90) == null ? 'good' : status(lastNum(p90), 900, 2000), lane: 'logs' }),
    statTile({ label: 'Share of volume', value: isNaN(share) ? '–' : fmt.pct(share, 0), sub: 'of submitted payments', lane: 'logs' }),
    statTile({ label: 'Failovers from here', value: fmt.num(Math.round(10 * (lastNum(fo) || 0) / spanMin()) / 10), sub: 'route.failover / min', spark: fo.length ? fo : [0], status: (lastNum(fo) || 0) > 5 * spanMin() ? 'critical' : (lastNum(fo) || 0) > 0 ? 'warning' : 'good', lane: 'logs' }),
  ]));
  const g = el('div.grid', { style: 'margin-top:12px' });
  g.append(card({ title: 'Approval rate', span: 7, lanes: ['logs'], body: () => lineChart({ labels: d.ap.labels.length ? d.ap.labels : ['–'], series: [{ name: 'Approval %', values: ap.length ? ap : [0], color: 'var(--s1)' }], yMin: 70, yMax: 100, yFmt: (v) => fmt.num(v) + '%', h: 160 }) }));
  g.append(card({ title: 'Response codes (ISO 8583)', span: 5, lanes: ['logs'], body: () => d.codes.length ? hBars({ items: d.codes.map(r => ({ label: r['acquirer.response_code'], value: Number(r.count), status: ['91', '96'].includes(r['acquirer.response_code']) ? 'critical' : undefined })), valueLabel: 'responses' }) : emptyNote('No responses in range.'),
    note: 'acquirer.authorised / acquirer.declined events carry acquirer.response_code; code 91 is what the router treats as retryable and fails over.' }));
  g.append(card({ title: `Declines by BIN prefix at ${name}`, span: 7, lanes: ['logs'], body: () => d.bins.length ? simpleTable([{ key: 'payment.card.bin', label: 'BIN' }, { key: 'payment.card.network', label: 'Issuer network' }, { key: 'merchant', label: 'Merchant' }, { key: 'err', label: 'Declines + failovers', num: true }, { key: 'rate', label: 'Error rate', num: true, fmt: (v) => fmt.pct(Number(v)) }],
    d.bins.map(r => Object.assign({}, r, { merchant: [].concat(r.merchant || []).slice(0, 2).join(', ') })), { onRow: (r) => Number(r.err) > 10 ? go('#/forensics') : window.open(links.logs(`event IN (payment.declined, route.failover) payment.acquirer=${id} payment.card.bin=${r['payment.card.bin']}`), '_blank') }) : emptyNote('No declines or failovers at this acquirer in range.'),
    note: 'Rows with more than 10 errors open the trace forensics page; others open the search. In Datadog this table needs payment.card.bin as a custom tag on retained spans; with a 15-minute live window and retention filters, last hour’s rows are gone unless a filter kept them.' }));
  g.append(card({ title: 'Deep links', span: 5, lanes: ['mcp'], body: () => el('div.btn-row', null, [o11yLink('payment-router in APM', APM('payment-router'), true), o11yLink('Tag Spotlight · payment.acquirer=' + id, TAGS('payment-router', 'payment.acquirer')), searchLink('SPL · response codes over time', `event IN (acquirer.authorised, acquirer.declined) payment.acquirer=${id} | timechart count by acquirer.response_code`)]) }));
  w.append(g); return w;
}

/* ---------- Trace forensics: the latest failed-over (else declined) payment, from its own log lines ---------- */
PAGES.forensics = { title: 'Trace forensics', group: 'Payments', async load() {
  let pick = await spl(`${LIVE.idx} event=route.failover | head 1 | table trace_id`, '-24h');
  let kind = 'failed over';
  if (!pick.length) { pick = await spl(`${LIVE.idx} event=payment.declined | head 1 | table trace_id`, '-24h'); kind = 'declined'; }
  const tid = (pick[0] || {}).trace_id;
  const [ev, mix, cell, late, cfg] = await Promise.all([
    tid ? spl(`${LIVE.idx} trace_id="${tid}" | sort _time | table _time service.name event duration_ms merchant.id payment.card.bin payment.acquirer route.backup_acquirer route.attempt_summary acquirer.response_code payment.decline_reason payment.outcome severity`, '-24h') : Promise.resolve([]),
    spl(`${LIVE.idx} event IN (payment.approved, payment.declined, route.failover) | stats count(eval(event="payment.approved")) as a count(eval(event!="route.failover")) as n count(eval(event="route.failover")) as fo min(eval(if(event="route.failover", _time, null()))) as first_fo`),
    spl(`${LIVE.idx} event IN (payment.declined, route.failover) | stats count as c dc(merchant.id) as m values(merchant.id) as merchants by payment.card.bin payment.acquirer | sort - c | head 1`, '-15m'),
    spl(`${LIVE.idx} event=acquirer.late_response | stats count as c max(acquirer.latency_ms) as ms latest(payment.acquirer) as acq`),
    spl(`${LIVE.idx} event=config.changed feature_flag.enabled=true | head 1 | table _time feature_flag.name`, '-24h'),
  ]);
  return { tid, kind, ev, mix: mix[0] || {}, cell: cell[0], late: late[0] || {}, cfg: cfg[0] };
}, render(d) {
  const w = el('div');
  w.append(pageHeader('Trace forensics: the one-in-ten-thousand decline', 'One payment, every hop, with the business tags on each line: the most recent payment that failed over (or, if none, was declined), from every log line that carries its trace_id. One click opens the full trace in APM.', '1'));
  const g = el('div.grid'), sum = (d.ev.find(r => r['route.attempt_summary']) || {})['route.attempt_summary'];   // used by the trace card and the steps
  if (!d.tid) g.append(card({ title: 'No failed-over or declined payment in the last 24 hours', span: 12, lanes: ['logs'], body: () => emptyNote('Start Act 1 from the war-room panel to produce one.') }));
  else {
    const t0 = Date.parse(d.ev[0]._time);
    const spans = d.ev.map(r => ({ service: r['service.name'], name: r.event, start: Math.max(0, Date.parse(r._time) - t0 - Number(r.duration_ms || 0)), dur: Math.max(1, Number(r.duration_ms || 1)),
      s: /failover|timeout|failed/.test(r.event) ? 'critical' : /declined/.test(r.event) ? 'warning' : undefined,
      tags: ['merchant.id', 'payment.card.bin', 'payment.acquirer', 'route.backup_acquirer', 'route.attempt_summary', 'acquirer.response_code', 'payment.decline_reason'].filter(k => r[k]).map(k => [k, r[k]]) }));
    g.append(card({ title: `Trace ${d.tid.slice(0, 4)}…${d.tid.slice(-2)} — ${d.kind}${sum ? ': ' + sum : ''}`, span: 12, lanes: ['logs'], sub: 'hover a bar for its tags; bars = each service’s own duration_ms, placed where its log line ended',
      link: { label: 'Open in Trace Analyzer', url: links.trace(d.tid), what: 'the trace in Splunk APM' }, body: () => waterfall({ spans, aria: 'Trace waterfall' }),
      note: 'Observability Cloud keeps the full-fidelity trace for 8 days (15/30 on request); the log lines with the same trace_id stay SPL-searchable and joinable with the mandate and reconciliation data for as long as the index retains them.',
      table: () => simpleTable(['_time', 'service.name', 'event', 'duration_ms', 'payment.acquirer', 'acquirer.response_code', 'payment.decline_reason'].map(k => ({ key: k, label: k })), d.ev) }));
  }
  const m = d.mix, ap = pct(Number(m.a || 0), Number(m.n || 0)), fo = Number(m.fo || 0), c = d.cell, late = d.late;
  const step = (ok, text) => el('li' + (ok ? '.ok' : ''), { text });
  g.append(card({ title: 'How the tower found it', span: 7, lanes: ['spans', 'logs'], link: { label: 'SPL · late response and config change', url: links.logs('event IN (acquirer.late_response, config.changed) | table _time event payment.acquirer acquirer.latency_ms feature_flag.name'), what: 'Splunk search' }, body: () => el('ol.steps', null, [
    step(fo > 0, `Approval rate in range ${fmt.pct(ap)}; the decline mix shows ${fmt.num(fo)} timeouts / failovers` + (m.first_fo ? `, the first at ${new Date(Number(m.first_fo) * 1000).toTimeString().slice(0, 5)}.` : '.')),
    step(c && Number(c.c) > 10, c ? `BIN × acquirer heat map (last 15 min): hottest cell ${c['payment.card.bin']} × ${ACQ_NAMES[c['payment.acquirer']] || c['payment.acquirer']}, ${fmt.num(Number(c.c))} errors, merchant ${[].concat(c.merchants || []).slice(0, 2).join(', ')}${Number(c.m) > 2 ? ' …' : ''}.` : 'BIN × acquirer heat map: no hot cell in the last 15 minutes.'),
    el('li' + (d.kind === 'failed over' ? '.blocked' : ''), { text: d.tid ? `Click the cell → this trace: ${sum || d.kind}.` : 'Click the cell → every failing trace (none in the last 24 hours).' }),
    step(Number(late.c) > 0 || d.cfg, (Number(late.c) > 0 ? `SPL join: ${fmt.num(Number(late.c))} acquirer.late_response events (${ACQ_NAMES[late.acq] || late.acq} answered after up to ${fmt.ms(Number(late.ms))}); ` : 'SPL join: no acquirer.late_response events in range; ') + (d.cfg ? `config.changed shows ${d.cfg['feature_flag.name']} switched on at ${new Date(d.cfg._time).toTimeString().slice(0, 8)}.` : 'no chaos flag switched on in 24 h.')),
    step(true, 'Ask the tower: "which merchants are affected and what is the revenue at risk?" → one answer from the same SPL and Observability Cloud calls.'),
  ]) }));
  g.append(card({ title: 'The honest Datadog comparison', span: 5, lanes: ['kv'], body: () => el('div.callout.dd', { html: '<b>Datadog:</b> trace metrics (hits, errors, latency) are computed from 100% of traffic, so the amber tile and the error-rate chart look the same. The difference is this page: with the Agent’s default head sampling (about 10 traces per second per Agent) and Live Search’s rolling 15-minute window, a trace from an hour ago survives only if a retention filter kept it. Splunk APM keeps every trace (NoSample) and Trace Analyzer searches unindexed tags such as payment.card.bin across the whole retention window.' }) }));
  w.append(g); return w;
} };

/* ---------- Agentic commerce governance ---------- */
PAGES.agentic = { title: 'Agentic commerce governance', group: 'Payments', async load() {
  const s = span();
  const [counts, reasons, agents, trend, share] = await Promise.all([
    spl(`${LIVE.idx} (event IN (mandate.issued, mandate.refused, mandate.verified, mandate.blocked, kya.registry_unavailable, kya.agent_unknown, agent.untrusted_content, guardrail.prompt_injection_suspected) OR (event IN (payment.approved, payment.declined) payment.initiator=agent)) | eval k=if(event IN ("payment.approved","payment.declined"), "agent:" . event, event) | stats count by k`),
    spl(`${LIVE.idx} event=mandate.blocked | stats count by mandate.block_reason | sort - count`),
    spl(`${LIVE.idx} event IN (mandate.verified, mandate.blocked, mandate.refused, kya.agent_unknown) | stats count(eval(event IN ("mandate.verified","mandate.blocked"))) as n count(eval(event="mandate.blocked")) as blocked latest(event) as last_event latest(mandate.block_reason) as last_reason by agent.id | eventstats sum(n) as total | eval share=if(total>0, round(100*n/total,1), 0) | lookup kya_registry.csv agent_id as agent.id OUTPUT operator kya_rating registered protocol | sort - share`),
    spl(`${LIVE.idx} event IN (payment.approved, payment.declined, mandate.verified, mandate.blocked, agent.untrusted_content, guardrail.prompt_injection_suspected, kya.registry_unavailable, service.crashed) | timechart span=${s} count(eval(event IN ("payment.approved","payment.declined") AND 'payment.initiator'="agent")) as an count(eval(event IN ("payment.approved","payment.declined"))) as n count(eval(event IN ("payment.approved","payment.declined") AND 'payment.initiator'="human")) as hn count(eval(event="payment.approved" AND 'payment.initiator'="human")) as ha count(eval(event="mandate.blocked")) as mb count(eval(event IN ("mandate.verified","mandate.blocked"))) as mn count(eval(event IN ("agent.untrusted_content","guardrail.prompt_injection_suspected"))) as inj count(eval(event="kya.registry_unavailable" OR 'mandate.block_reason'="mandate_kya_unavailable")) as kya count(eval(event="service.crashed" AND 'service.name'="wallet-sim")) as crash count(eval('mandate.block_reason'="mandate_kya_unavailable")) as fc | eval share=if(n>0, round(100*an/n,1), 0), blocked=if(mn>0, round(100*mb/mn,1), 0), human=if(hn>0, round(100*ha/hn,1), null()) | fields _time share blocked inj kya crash fc human`),
    spl(`${PAYQ} | stats count(eval('payment.initiator'="agent")) as ag count as n count(eval('payment.initiator'="agent" AND 'agent.verified'="false")) as unv`, '-15m'),
  ]);
  return { c: Object.fromEntries(counts.map(r => [r.k, Number(r.count)])), reasons, agents, trend: tc(trend), share: share[0] || {} };
}, render(d) {
  const c = (k) => d.c[k] || 0, regDown = c('kya.registry_unavailable') > 0 || d.reasons.some(r => r['mandate.block_reason'] === 'mandate_kya_unavailable');
  const checked = c('mandate.verified') + c('mandate.blocked');
  const w = el('div');
  w.append(pageHeader('Agentic commerce governance', 'Every agent payment carries a wallet-issued task mandate. This page is the regulator-readable view: who the agents are, what they were allowed to do, where each violation was stopped, and proof that the gateway fails closed when it cannot verify.', '4 · 4b · 7'));
  const T = d.trend, sh = T.cols.share || [], mb = T.cols.blocked || [], inj = T.cols.inj || [], dl = (a) => a.length > 1 ? lastNum(a) - a[0] : null;
  const injN = c('agent.untrusted_content') + c('guardrail.prompt_injection_suspected'), unv = Number(d.share.unv || 0), agN = Number(d.share.ag || 0);
  w.append(el('div.tiles', null, [
    statTile({ label: 'Agent-initiated share', value: fmt.pct(lastNum(sh)), delta: dl(sh), deltaUnit: ' pt', spark: sh.length ? sh : [0], status: lastNum(sh) > 20 ? 'warning' : 'good', lane: 'logs', tipRows: [['Field', 'payment.initiator=agent'], ['Events', 'payment.approved / payment.declined']] }),
    statTile({ label: 'Mandates blocked', value: fmt.pct(pct(c('mandate.blocked'), checked)), delta: dl(mb), deltaUnit: ' pt', deltaGood: false, spark: mb.length ? mb : [0], sub: `${fmt.num(c('mandate.blocked'))} of ${fmt.num(checked)} checked`, status: checked ? status(pct(c('mandate.blocked'), checked), 10, 30) : 'good', lane: 'logs' }),
    statTile({ label: 'KYA registry availability', value: regDown ? 'DOWN' : 'up', spark: (T.cols.kya || [0]).map(v => v > 0 ? 0 : 100), status: regDown ? 'critical' : 'good', lane: 'logs', sub: regDown ? 'fail-closed: agents cannot pay' : 'no kya.registry_unavailable in range' }),
    statTile({ label: 'Prompt injection suspected', value: fmt.num(injN), sub: 'agent.untrusted_content + guardrail events in range', spark: inj.length ? inj : [0], status: injN > 0 ? 'serious' : 'good', lane: 'logs' }),
    statTile({ label: 'Unverified agents paying', value: fmt.pct(pct(unv, agN)), sub: `agent.verified=false, ${fmt.num(unv)} payments (15 min)`, status: unv > 0 ? 'warning' : 'good', lane: 'logs' }),
  ]));
  const g = el('div.grid', { style: 'margin-top:12px' });
  g.append(card({ title: 'Mandate lifecycle (in range)', span: 12, lanes: ['logs'], sub: 'state diagram with live counts; the magenta path is where agents are being stopped right now', body: () => mandateDiagramLive(d, regDown),
    note: 'States come from the log events mandate.issued → mandate.verified / mandate.blocked (reason) → payment.approved, plus kya.agent_unknown and mandate.refused from the wallet. Vocabulary follows AP2 (Agent Payments Protocol) intent / cart / payment mandates; KYA tiers A–D are TukTukPay’s own construct.' }));
  g.append(card({ title: 'Blocks by reason', span: 5, lanes: ['logs'], body: () => d.reasons.length ? hBars({ items: d.reasons.map(r => ({ label: r['mandate.block_reason'], value: Number(r.count), status: r['mandate.block_reason'] === 'mandate_kya_unavailable' ? 'critical' : undefined })), valueLabel: 'mandate.blocked' }) : emptyNote('No mandate blocked in range.'),
    note: 'mandate.block_reason is an indexed span tag, so the same split is one click away in Tag Spotlight.' }));
  g.append(card({ title: 'Registered agents (Know-Your-Agent)', span: 7, lanes: ['kv', 'logs'], body: () => d.agents.length ? simpleTable([
    { key: 'agent.id', label: 'Agent', status: (r) => r.registered === 'false' || !r.registered ? 'critical' : r.kya_rating === 'C' ? 'warning' : 'good' }, { key: 'operator', label: 'Operator' }, { key: 'kya_rating', label: 'KYA' }, { key: 'protocol', label: 'Protocol' },
    { key: 'share', label: 'Share of agent volume', num: true, fmt: (v) => fmt.pct(Number(v), 0) }, { key: 'blocked', label: 'Blocked', num: true }, { key: 'outcome', label: 'Last outcome', fmt: (v, r) => r.last_event === 'mandate.blocked' ? 'blocked_by_mandate: ' + (r.last_reason || '') : r.last_event === 'mandate.verified' ? 'purchased' : r.last_event ? r.last_event.replace('mandate.refused', 'refused_unregistered_agent') : '–' }], d.agents,
    { onRow: (r) => window.open(links.logs(`event=mandate.* agent.id="${r['agent.id']}" | table _time event mandate.verdict mandate.block_reason amp.task_id payment.amount`), '_blank') }) : emptyNote('No agent mandates in range.'),
    note: 'The registry (kya_registry.csv lookup, a copy of the wallet’s KYA table) joined with agent.id on the mandate events. Click a row for that agent’s full mandate trail.' }));
  const n = T.labels.length, kya = T.cols.kya || [], crash = T.cols.crash || [], fc = T.cols.fc || [], hu = T.cols.human || [];
  const avail = [
    { name: 'KYA registry', segs: runs(T.labels.map((_, i) => kya[i] > 0 ? { s: 'critical', label: 'unavailable (503)' } : { s: 'good', label: 'up' })) },
    { name: 'wallet-sim pod', href: '#/k8s', segs: runs(T.labels.map((_, i) => crash[i] > 0 ? { s: 'critical', label: 'crashed' } : { s: 'good', label: 'running' })) },
    { name: 'Mandate verification', segs: runs(T.labels.map((_, i) => fc[i] > 0 ? { s: 'critical', label: 'fail closed' } : { s: 'good', label: 'verifying' })) },
    { name: 'Human checkout', segs: runs(T.labels.map((_, i) => hu[i] != null && hu[i] < 80 ? { s: 'warning', label: 'approval below 80%' } : { s: 'good', label: 'unaffected' })) },
  ];
  g.append(card({ title: 'Registry and wallet availability', span: 5, lanes: ['logs', 'alerts'], body: () => n ? stateTimeline({ labels: T.labels, rows: avail, aria: 'Availability of the wallet and the KYA registry' }) : emptyNote('No events in range.'),
    note: 'State per time bucket from kya.registry_unavailable, service.crashed (wallet-sim) and mandate.blocked reason mandate_kya_unavailable — the fail-closed proof for the audit trail.' }));
  g.append(card({ title: 'Agent vs human: approval and share', span: 7, lanes: ['logs'], body: () => n ? lineChart({ labels: T.labels, series: [{ name: 'Agent share %', values: sh, color: 'var(--s7)' }, { name: 'Blocked %', values: mb, color: 'var(--s8)' }, { name: 'Injection / ' + span(), values: inj, color: 'var(--s2)' }], yMin: 0, yMax: 100, yFmt: (v) => fmt.num(v), h: 170 }) : emptyNote('No payments in range.'),
    table: () => tableFromSeries(T.labels, [{ name: 'Agent %', values: sh }, { name: 'Blocked %', values: mb }, { name: 'Injection', values: inj }]) }));
  g.append(card({ title: 'Evidence links', span: 5, lanes: ['mcp'], body: () => el('div.btn-row', null, [o11yLink('Tag Spotlight · mandate.block_reason', TAGS('checkout-api', 'mandate.block_reason'), true),
    searchLink('SPL · blocks by agent and KYA tier', 'event=mandate.blocked | stats count by mandate.block_reason agent.id amp.kya.rating'),
    o11yLink('Detector · KYA registry unavailable', ((LIVE.openDetectors || []).find(x => /Know-Your-Agent/.test(x.detector)) || {}).url || `${O11Y}/alerts`),
    el('button.btn', { type: 'button', text: 'Ask: did any agent pay outside its mandate?', onclick: () => askOpen('mandate') })]) }));
  w.append(g); return w;
} };
function mandateDiagramLive(d, regDown) {
  const c = (k) => d.c[k] || 0, blocked = c('mandate.blocked');
  const st = (n, label, x, y, s, sub, w) => ({ id: n, label, x, y, w: w || 170, h: 46, s, sub, kind: 'box' });
  const nodes = [
    st('agent', 'Agent asks wallet', 10, 130, 'good', 'task, budget, merchants, TTL'), st('kya', 'KYA lookup', 240, 30, regDown ? 'critical' : 'good', regDown ? 'registry unreachable' : 'rating A–D'),
    st('issued', 'Mandate issued', 240, 130, 'good', fmt.num(c('mandate.issued')) + ' mandate.issued'), st('refused', 'Refused (unregistered)', 240, 230, c('mandate.refused') + c('kya.agent_unknown') > 0 ? 'warning' : 'good', fmt.num(c('mandate.refused') + c('kya.agent_unknown')) + ' refused / unknown'),
    st('verify', 'checkout-api verifies', 480, 130, regDown ? 'critical' : blocked > 0 ? 'serious' : 'good', 'limit · expiry · merchant · replay · KYA', 200),
    st('blocked', 'Blocked', 750, 230, blocked > 50 ? 'critical' : blocked > 0 ? 'serious' : 'good', fmt.num(blocked) + ' mandate.blocked'), st('verified', 'Verified → risk → acquirer', 750, 130, 'good', fmt.num(c('mandate.verified')) + ' mandate.verified', 190),
    st('approved', 'Approved', 1000, 90, 'good', fmt.num(c('agent:payment.approved')) + ' agent payments', 160), st('declined', 'Declined', 1000, 170, 'good', fmt.num(c('agent:payment.declined')) + ' agent payments', 160),
  ];
  const top = d.reasons.slice(0, 3).map(r => r['mandate.block_reason'].replace('mandate_', '')).join(' · ') || 'none';
  const edges = [{ from: 'agent', to: 'kya', label: 'agent.id', cls: regDown ? 'hot' : 'edge' }, { from: 'kya', to: 'issued', label: 'registered', cls: regDown ? 'hot' : 'edge' },
    { from: 'kya', to: 'refused', label: 'unknown', via: [[200, 53], [200, 253]] }, { from: 'issued', to: 'verify', label: 'pays', labelDy: 14 }, { from: 'verify', to: 'verified', label: 'ok', labelDy: 14 },
    { from: 'verify', to: 'blocked', label: regDown ? 'mandate_kya_unavailable: fail closed' : top, cls: regDown ? 'hot' : blocked > 0 ? 'warm' : 'edge', labelDy: 16 }, { from: 'verified', to: 'approved' }, { from: 'verified', to: 'declined' }];
  return flowMap({ w: 1170, h: 290, key: 'mandate', nodes, edges, notes: regDown ? [{ x: 480, y: 280, text: 'Fail closed: no mandate can be verified while the registry is down, so no agent payment reaches an acquirer.', color: 'var(--st-critical)' }] : [] });
}

/* ---------- Risk model ---------- */
PAGES.risk = { title: 'Risk model', group: 'Payments', async load() {
  const s = span();
  const [byModel, reasons, canary, p90, cpu] = await Promise.all([
    spl(`${PAYQ} | eval mv='risk.model_version' | bin _time span=${s} | stats count(eval(event="payment.approved")) as a count as n by _time mv | eval ap=round(100*a/n,1) | xyseries _time mv ap`),
    spl(`${LIVE.idx} event=risk.declined | eval r='risk.reasons' | mvexpand r | stats count by r | sort - count | head 8`),
    spl(`${LIVE.idx} event IN (risk.canary_inference, risk.inference_slow, risk.declined) | stats latest(risk.canary_pct) as pct`),
    noErr(apmP90('risk-engine')), noErr(cpuPct('risk-engine')),
  ]);
  return { m: tc(byModel), reasons, canary: (canary[0] || {}).pct, p90, cpu };
}, render(d) {
  const w = el('div');
  w.append(pageHeader('Risk model: canary v3 vs baseline v2', 'Classic ML monitoring done with business numbers: the approval rate sliced by risk.model_version, the inference latency the SLO is built on, and the CPU that explains it.', '2'));
  const v2 = d.m.cols.v2 || [], v3 = d.m.cols.v3 || [], p90 = d.p90.values || [], cpu = (d.cpu.values || []).map(v => v || 0), dl = (a) => a.length > 1 && lastNum(a) != null ? lastNum(a) - a[0] : null;
  const canary = d.canary !== undefined && d.canary !== '' ? Number(d.canary) : null;
  w.append(el('div.tiles', null, [
    statTile({ label: 'Approval rate · v3 canary', value: v3.length ? fmt.pct(lastNum(v3)) : '–', delta: dl(v3), deltaUnit: ' pt', spark: v3.length ? v3 : [0], status: v3.length ? status(lastNum(v3), 88, 84, false) : 'good', lane: 'logs', sub: v3.length ? 'risk.model_version=v3' : 'no v3 traffic (Act 2 off)' }),
    statTile({ label: 'Approval rate · v2', value: fmt.pct(lastNum(v2)), delta: dl(v2), deltaUnit: ' pt', spark: v2.length ? v2 : [0], lane: 'logs' }),
    statTile({ label: 'risk-engine p90', value: d.p90.error ? '–' : fmt.ms(lastNum(p90)), delta: dl(p90) == null ? null : Math.round(dl(p90)), deltaUnit: ' ms', deltaGood: false, spark: p90.length ? p90 : [0], status: lastNum(p90) == null ? 'good' : status(lastNum(p90), 80, 100), lane: 'metrics', tipRows: [['Detector', 'risk-engine p90 latency above 100ms'], ['AI Troubleshooting Agent', 'runs automatically on this APM service alert']] }),
    statTile({ label: 'risk-engine CPU vs limit', value: d.cpu.error || lastNum(cpu) == null ? '–' : fmt.pct(lastNum(cpu), 0), spark: cpu.length ? cpu : [0], status: status(lastNum(cpu) || 0, 70, 90), lane: 'metrics', sub: d.cpu.limit ? `limit ${Math.round(d.cpu.limit * 1000)}m` : 'container.cpu.usage ÷ cpu_limit' }),
    statTile({ label: 'Canary share', value: canary == null ? '–' : fmt.pct(canary, 0), sub: 'risk.canary_pct', lane: 'logs' }),
  ]));
  const g = el('div.grid', { style: 'margin-top:12px' });
  const ms = Object.keys(d.m.cols).map((k, i) => ({ name: k === 'v2' ? 'v2 (baseline)' : k === 'v3' ? 'v3 (canary)' : k, values: d.m.cols[k], color: k === 'v3' ? 'var(--s2)' : k === 'v2' ? 'var(--s1)' : seriesColor(i) }));
  g.append(card({ title: 'Approval rate by model version', span: 7, lanes: ['logs'], body: () => ms.length ? lineChart({ labels: d.m.labels, series: ms, yMin: 60, yMax: 100, yFmt: (v) => fmt.num(v) + '%', h: 190 }) : emptyNote('No payments in range.'),
    table: () => tableFromSeries(d.m.labels, ms, (v) => fmt.pct(v)), note: (ms.length < 2 ? 'Only one model version is serving — start Act 2 to put the v3 canary on 20% of traffic. ' : '') + 'Payments by risk.model_version × outcome from the logs. In Datadog this is a custom metric with merchant × model × reason dimensions — ask what that costs per 100 custom metrics.' }));
  g.append(card({ title: 'False declines by reason (v3)', span: 5, lanes: ['logs'], body: () => d.reasons.length ? hBars({ items: d.reasons.map(r => ({ label: r.r, value: Number(r.count), status: /v3/.test(r.r) ? 'critical' : undefined })), valueLabel: 'risk.declined in range' }) : emptyNote('No risk declines in range.'),
    note: 'risk.declined events carry risk.reasons; the IDR/PHP wallet declines (wallet_geo_risk_v3) are the v3 regression.' }));
  g.append(card({ title: 'Inference latency and CPU', span: 7, lanes: ['metrics'], body: () => p90.length || cpu.length ? lineChart({ labels: (d.p90.labels || []).length ? d.p90.labels : d.cpu.labels, series: [{ name: 'p90 ms', values: p90, color: 'var(--s1)' }, { name: 'CPU % of limit', values: cpu, color: 'var(--s4)' }].filter(x => x.values.length), h: 170, thresholds: [{ value: 100, label: 'detector 100 ms' }] }) : emptyNote('Observability Cloud: ' + (d.p90.error || d.cpu.error || 'no data')),
    note: 'APM p90 of risk-engine and container.cpu.usage ÷ k8s.container.cpu_limit, both from Observability Cloud, on one axis. 100 ms is the detector threshold; the per-inference SLO carried on the logs (risk.inference_slo_ms) is 50 ms. AlwaysOn Profiling names _infer_v3 as the hot function behind the CPU line.' }));
  g.append(card({ title: 'AI Troubleshooting Agent', span: 5, lanes: ['alerts'], body: () => expectedAgent(S.act === 'act2' ? { impact: 'risk-engine p90 above 100 ms; checkout-api p90 rises with it; approval rate falls only for risk.model_version=v3', causes: [['CPU saturation in risk-engine pods after canary v3 rollout', 'critical'], ['Downstream: checkout-api latency inherited from risk-engine', 'warning']], evidence: ['Exemplar trace: risk-engine POST /v1/score, span tag risk.model_version=v3', 'Logs: risk.inference_slow risk.inference_ms rising; config.changed risk_model_drift', 'Profiling: _infer_v3 hot stack'], plan: null } : null, 'APM service alert on risk-engine') }));
  g.append(card({ title: 'Deep links', span: 12, lanes: ['mcp'], body: () => el('div.btn-row', null, [o11yLink('risk-engine in APM', APM('risk-engine'), true), o11yLink('Tag Spotlight · risk.model_version', TAGS('risk-engine', 'risk.model_version')), o11yLink('AlwaysOn Profiling · risk-engine', `${O11Y}/apm/profiling?service=risk-engine&environments=${LIVE.env}`), searchLink('SPL · declines by reason and model', 'event=risk.declined | stats count by risk.reasons risk.model_version')]) }));
  w.append(g); return w;
} };

/* ---------- Copilot cost & guardrails ---------- */
PAGES.copilot = { title: 'Copilot cost & guardrails', group: 'AI', async load() {
  const s = span();
  const [t, byM, gr, blk, p90] = await Promise.all([
    spl(`${LIVE.idx} event=copilot.answered | timechart span=${s} sum(gen_ai.usage.input_tokens) as input sum(gen_ai.usage.output_tokens) as output sum(copilot.cost_usd) as cost avg(copilot.iterations) as iterations`),
    spl(`${LIVE.idx} event=copilot.answered | stats sum(copilot.cost_usd) as usd count as questions avg(copilot.iterations) as it by merchant.id | eval it=round(it,1) | sort - usd`),
    spl(`${LIVE.idx} event IN (copilot.answered, guardrail.action_blocked, guardrail.prompt_injection_suspected, copilot.tool_loop_suspected) | eval tool=coalesce('gen_ai.tool.name', mvjoin('gen_ai.tool.names', ", ")), why=case(event="guardrail.action_blocked", "blocked by guardrail: " . mvjoin('guardrail.rules', ", "), event="guardrail.prompt_injection_suspected", "prompt injection: " . mvjoin('guardrail.rules', ", "), event="copilot.tool_loop_suspected", "tool loop: " . 'copilot.iterations' . " iterations, " . 'copilot.repeated_tool_calls' . " repeated calls", true(), "answered in " . 'copilot.iterations' . " iterations") | sort - _time | dedup 5 event sortby - _time | table _time event merchant.id tool guardrail.verdict why | head 12`),
    spl(`${LIVE.idx} event=guardrail.action_blocked | timechart span=${s} count as blocks`),
    noErr(apmP90('merchant-copilot')),
  ]);
  return { t: tc(t), byM, gr, blk: tc(blk), p90 };
}, render(d) {
  const m = spanMin(), inp = (d.t.cols.input || []).map(v => Math.round(v / m)), out = (d.t.cols.output || []).map(v => Math.round(v / m)), tok = inp.map((v, i) => v + (out[i] || 0));
  const cost = (d.t.cols.cost || []).map(v => v * 60 / m), it = d.t.cols.iterations || [], blk = (d.blk.cols.blocks || []).map(v => v * 5 / m), p90 = d.p90.values || [];
  const pc = (a) => a.length > 1 && a[0] ? Math.round((lastNum(a) / a[0] - 1) * 100) : null;
  const w = el('div');
  w.append(pageHeader('Merchant copilot: tokens, cost, guardrails', 'The LLM copilot is instrumented with the OpenTelemetry GenAI semantic conventions, so its invoke_agent → chat → execute_tool spans sit in the same trace as the ledger lookups the tools make. This page is the bill and the safety record.', '3'));
  w.append(el('div.tiles', null, [
    statTile({ label: 'Tokens per minute', value: fmt.num(lastNum(tok) || 0), delta: pc(tok), deltaUnit: '%', deltaGood: false, spark: tok.length ? tok : [0], status: status(lastNum(tok) || 0, 20000, 60000), lane: 'logs', tipRows: [['Detector', 'copilot token burn above 20k tokens/min'], ['Attribute', 'gen_ai.usage.input_tokens / output_tokens']] }),
    statTile({ label: 'Estimated cost per hour', value: fmt.usd(lastNum(cost) || 0), delta: pc(cost), deltaUnit: '%', deltaGood: false, spark: cost.length ? cost : [0], status: status(lastNum(cost) || 0, 20, 50), lane: 'logs', sub: 'copilot.cost_usd at the current rate' }),
    statTile({ label: 'Tool-loop iterations (avg)', value: fmt.num(lastNum(it) || 0, 1), spark: it.length ? it : [0], status: status(lastNum(it) || 0, 5, 9), lane: 'logs', sub: 'copilot.iterations' }),
    statTile({ label: 'Guardrail blocks / 5 min', value: fmt.num(Math.round(lastNum(blk) || 0)), spark: blk.length ? blk : [0], status: (lastNum(blk) || 0) > 2 ? 'serious' : 'good', lane: 'logs', sub: 'guardrail.action_blocked (refund_payment)' }),
    statTile({ label: 'Copilot p90', value: d.p90.error || lastNum(p90) == null ? '–' : fmt.ms(lastNum(p90)), spark: p90.length ? p90 : [0], status: lastNum(p90) == null ? 'good' : status(lastNum(p90), 3000, 5000), lane: 'metrics', sub: 'merchant-copilot APM' }),
  ]));
  const g = el('div.grid', { style: 'margin-top:12px' });
  g.append(card({ title: 'Tokens per minute by type', span: 7, lanes: ['logs'], body: () => d.t.labels.length ? stackedColumns({ labels: d.t.labels, series: [{ name: 'input', values: inp, color: 'var(--s1)' }, { name: 'output', values: out, color: 'var(--s3)' }], h: 190 }) : emptyNote('No copilot answers in range.'),
    table: () => tableFromSeries(d.t.labels, [{ name: 'input', values: inp }, { name: 'output', values: out }]) }));
  const hrs = RANGES[S.range].n * RANGES[S.range].step / 3600;
  g.append(card({ title: 'Cost per hour by merchant', span: 5, lanes: ['logs'], body: () => d.byM.length ? hBars({ items: d.byM.map(r => ({ label: r['merchant.id'], value: Number(r.usd) / hrs, tip: [['Questions', r.questions], ['Avg iterations', r.it]] })), fmt: fmt.usd, valueLabel: 'USD / hour' }) : emptyNote('No copilot answers in range.'),
    note: 'copilot.cost_usd summed by merchant.id over the range, as a rate per hour.' }));
  g.append(card({ title: 'Guardrail verdicts and attempted tools', span: 7, lanes: ['logs'], body: () => d.gr.length ? simpleTable([{ key: '_time', label: 'When' }, { key: 'merchant.id', label: 'Merchant', fmt: (v) => v || '–' }, { key: 'tool', label: 'Tool requested', fmt: (v) => v || '–' }, { key: 'guardrail.verdict', label: 'Verdict', status: (r) => /block|flag/.test(r['guardrail.verdict'] || '') || r.event !== 'copilot.answered' ? 'serious' : 'good' }, { key: 'why', label: 'Why' }], d.gr) : emptyNote('No copilot answers or guardrail events in range.'),
    note: 'copilot.answered events with gen_ai.tool.names and guardrail.verdict, plus guardrail.action_blocked / prompt_injection_suspected and copilot.tool_loop_suspected; the newest five of each kind. The blocked rows are prompt-injection attempts to trigger refund_payment.' }));
  g.append(card({ title: 'Product note', span: 5, lanes: ['kv'], body: () => el('div.callout', { html: '<b>Which Splunk screen:</b> the APM “AI agents” pages and the “AI agent tokens and costs” dashboard (10 Sep 2026) are fed by the standard OpenTelemetry GenAI spans the services already emit — no extra SDK. Those APM pages carry a “scheduled for deprecation” notice (no date) in favour of <b>Splunk Agent Observability</b> (Galileo: evaluations, guardrails, tokenomics, 30-day traces), which needs its own OTLP export with project/agent-stream headers and access requested from Splunk. Show both; name them correctly. <b>Datadog:</b> Agent Observability is GA, billed per LLM span (free 40K/month, Pro from $160/month for 100K), accepts OTel GenAI spans but cost estimation can be unavailable for them.' }) }));
  g.append(card({ title: 'Deep links', span: 12, lanes: ['mcp'], body: () => el('div.btn-row', null, [o11yLink('merchant-copilot in APM (AI agents pages)', APM('merchant-copilot'), true), o11yLink('Tag Spotlight · gen_ai.tool.name', TAGS('merchant-copilot', 'gen_ai.tool.name')), searchLink('SPL · cost and iterations by merchant', 'event=copilot.answered | stats sum(copilot.cost_usd) avg(copilot.iterations) by merchant.id'), el('button.btn', { type: 'button', text: 'Ask: what did the copilot cost today?', onclick: () => askOpen('cost') })]) }));
  w.append(g); return w;
} };

/* ---------- Ledger, settlement & webhooks ---------- */
PAGES.ledger = { title: 'Ledger, settlement & webhooks', group: 'Operations', async load() {
  const s = span(), f = 'k8s.namespace.name:"tuktukpay" AND k8s.container.name:"ledger"';
  const [pool, wh, rec, p90, mem, lim] = await Promise.all([
    spl(`${LIVE.idx} event IN (ledger.write_slow, db.pool.wait) | timechart span=${s} max(db.pool.wait_ms) as pool`),
    spl(`${LIVE.idx} event IN (webhook.delivered, webhook.delivery_failed, webhook.delivery_error, webhook.dead_lettered, webhook.backlog) | timechart span=${s} count(eval(event="webhook.delivered")) as retried count(eval(event IN ("webhook.delivery_failed","webhook.delivery_error"))) as failed count(eval(event="webhook.dead_lettered")) as dead max(messaging.lag_ms) as lag`),
    spl(`${LIVE.idx} event=payment.approved | stats count as ledger sum(payment.amount) as amount by merchant.id | lookup recon_psp_sample.csv merchant_id as merchant.id OUTPUT entries as file amount_thb as file_thb | eval diff=if(isnull(file), null(), ledger-file), thb=if(isnull(file), null(), round(amount-file_thb)) | sort - ledger`, '@d'),
    noErr(apmP90('ledger')),
    noErr(o11yWindow(`sf_metric:"container.memory.working_set" AND ${f}`, 'k8s.container.name')), noErr(o11yWindow(`sf_metric:"k8s.container.memory_limit" AND ${f}`, 'k8s.container.name')),
  ]);
  return { pool: tc(pool), wh: tc(wh), rec, p90, mem, lim };
}, render(d) {
  const w = el('div');
  w.append(pageHeader('Ledger, settlement and webhooks', 'What the merchant feels after the authorisation: was the payment recorded, did the webhook arrive, will tonight’s reconciliation file balance.', '5 · 6'));
  const p90 = d.p90.values || [], pool = d.pool.cols.pool || [], memB = ((d.mem.series || [])[0] || {}).values || [], mem = memB.map(v => Math.round(v / 1048576)), limit = Math.round((lastNum(((d.lim.series || [])[0] || {}).values || []) || 0) / 1048576);
  const retried = d.wh.cols.retried || [], failed = d.wh.cols.failed || [], dead = d.wh.cols.dead || [], whb = (d.wh.cols.lag || []).map(v => Math.round(v / 1000));
  const sum = (a) => a.reduce((x, y) => x + (y || 0), 0), recOpen = d.rec.filter(r => r.diff !== undefined && r.diff !== '' && Number(r.diff) !== 0).length, recLoaded = d.rec.some(r => r.diff !== undefined && r.diff !== '');
  w.append(el('div.tiles', null, [
    statTile({ label: 'ledger p90', value: d.p90.error || lastNum(p90) == null ? '–' : fmt.ms(lastNum(p90)), spark: p90.length ? p90 : [0], status: lastNum(p90) == null ? 'good' : status(lastNum(p90), 300, 400), lane: 'metrics', tipRows: [['Detector', 'ledger p90 latency above 400ms']] }),
    statTile({ label: 'DB pool wait', value: fmt.ms(lastNum(pool) || 0), spark: pool.length ? pool : [0], status: status(lastNum(pool) || 0, 100, 300), lane: 'logs', sub: 'db.pool.wait_ms on ledger.write_slow / db.pool.wait' }),
    statTile({ label: 'ledger memory', value: mem.length ? fmt.num(lastNum(mem)) + ' MiB' + (limit ? ' / ' + limit : '') : '–', spark: mem.length ? mem : [0], status: limit ? status(lastNum(mem) || 0, limit * .78, limit * .94) : 'good', lane: 'metrics', href: '#/k8s' }),
    statTile({ label: 'Webhook failures', value: fmt.num(sum(failed) + sum(dead)), spark: failed.length ? failed : [0], status: sum(dead) > 0 ? 'serious' : sum(failed) > 0 ? 'warning' : 'good', lane: 'logs', sub: 'delivery_failed / _error / dead_lettered in range' }),
    statTile({ label: 'Webhook backlog', value: fmt.num(lastNum(whb) || 0) + ' s', spark: whb.length ? whb : [0], status: status(lastNum(whb) || 0, 10, 30), lane: 'logs' }),
    statTile({ label: 'Reconciliation (T-1)', value: !recLoaded ? 'no file' : recOpen ? recOpen + ' open' : 'balanced', sub: 'the PSP daily file vs ledger', status: recOpen ? 'warning' : 'good', lane: 'kv' }),
  ]));
  const g = el('div.grid', { style: 'margin-top:12px' });
  const lbl = (d.p90.labels || []).length ? d.p90.labels : d.pool.labels;
  g.append(card({ title: 'Ledger latency and pool wait', span: 7, lanes: ['metrics', 'logs'], body: () => p90.length || pool.length ? lineChart({ labels: lbl, series: [{ name: 'p90 ms', values: p90, color: 'var(--s1)' }, { name: 'pool wait ms', values: pool.length === lbl.length ? pool : lbl.map(() => 0), color: 'var(--s2)' }].filter(x => x.values.length), h: 180, thresholds: [{ value: 400, label: 'detector 400 ms' }] }) : emptyNote('No ledger latency data in range.'),
    table: () => tableFromSeries(lbl, [{ name: 'p90', values: p90 }, { name: 'pool wait', values: pool }], fmt.ms), note: 'p90 is the APM service p90 of ledger (Observability Cloud); pool wait is the worst db.pool.wait_ms per bucket from the logs (0 when no request waited over 100 ms).' }));
  g.append(card({ title: 'Webhook deliveries by outcome', span: 5, lanes: ['logs'], body: () => d.wh.labels.length ? stackedColumns({ labels: d.wh.labels, series: [{ name: 'delivered after retry', values: retried, color: 'var(--s4)' }, { name: 'failed attempt', values: failed, color: 'var(--s8)' }, { name: 'dead-lettered', values: dead, color: 'var(--st-critical)' }], h: 180 }) : emptyNote('No webhook retries or failures in range.'),
    note: 'Counts per bucket. First-try deliveries log at DEBUG and are not exported, so only retries and failures show; merchant lazada-th answering 503 in Act 5 retries 30 s, 1 m, 2 m … and dead-letters after the last attempt (webhook.dead_lettered).' }));
  g.append(card({ title: 'Reconciliation against the the PSP daily file', span: 7, lanes: ['kv', 'logs'], body: () => simpleTable([{ key: 'merchant.id', label: 'Merchant' }, { key: 'ledger', label: 'Ledger entries', num: true }, { key: 'file', label: 'In recon file', num: true }, { key: 'diff', label: 'Difference', num: true, status: (r) => r.diff === undefined || r.diff === '' ? 'unknown' : Number(r.diff) === 0 ? 'good' : 'warning' }, { key: 'thb', label: 'THB', num: true, fmt: (v) => v === undefined || v === '' ? '–' : fmt.thb(Number(v)) }], d.rec),
    note: (recLoaded ? '' : 'recon_psp_sample.csv on this stack has no rows yet, so the file side shows –. ') + 'Ledger entries = payment.approved today (ledger.entry_recorded is DEBUG). The daily reconciliation CSV (delivered by SFTP before 04:00 GMT+7) is a lookup; the join is one SPL statement. Datadog has no query language that joins a file like this with metrics and logs.' }));
  g.append(card({ title: 'AI Troubleshooting Agent', span: 5, lanes: ['alerts'], body: () => expectedAgent(S.act === 'act5' ? { impact: 'ledger p90 above 400 ms; checkout-api p90 rises with it; webhook backlog for merchant lazada-th', causes: [['Connection-pool exhaustion in ledger (db.pool.wait_ms) after pool size dropped to 4', 'critical'], ['Slow INSERTs on postgres', 'warning']], evidence: ['Logs: ledger.write_slow with db.pool.wait_ms; config.changed ledger_db_slow pool_size=4', 'Exemplar trace: INSERT transaction', 'Database Query Performance: INSERT INTO transactions p90 up'], plan: null } : S.act === 'act6' ? { impact: 'ledger pod OOMKilled repeatedly; deployment below desired replicas; checkout-api errors', causes: [['Memory leak in ledger: RSS grows to the memory limit', 'critical']], evidence: ['Kubernetes: container restart count > 0, reason OOMKilled', 'Logs: memory.pressure before every restart', 'Metric: container memory vs limit sawtooth'], plan: ['Roll back ledger to the previous ReplicaSet (kubectl rollout undo deploy/ledger)', 'Raise the memory limit to 512 MiB as a stop-gap while the leak is fixed', 'Open a ticket with the heap profile from AlwaysOn Profiling (Node.js memory)'] } : null, 'APM service alert on ledger or a Kubernetes alert') }));
  g.append(card({ title: 'Deep links', span: 12, lanes: ['mcp'], body: () => el('div.btn-row', null, [o11yLink('ledger in APM · Database Query Performance', APM('ledger'), true), o11yLink('webhook-dispatcher in APM', APM('webhook-dispatcher')), searchLink('SPL · slow writes and failed webhooks', 'event IN (ledger.write_slow, webhook.delivery_failed, webhook.dead_lettered) | timechart count by event'), el('a.btn', { href: '#/k8s', text: 'Kubernetes health (ledger pod)' })]) }));
  w.append(g); return w;
} };

/* ---------- Kubernetes health (Observability Cloud metrics through the app proxy) ---------- */
const POD_ROWS = [['checkout-api'], ['risk-engine'], ['payment-router'], ['ledger', '#/ledger'], ['wallet-sim', '#/agentic'], ['webhook-dispatcher'], ['merchant-copilot']];
PAGES.k8s = { title: 'Kubernetes health', group: 'Operations', async load() {
  const ns = 'k8s.namespace.name:"tuktukpay"', lf = `${ns} AND k8s.container.name:"ledger"`;
  const [restarts, ready, mem, lim] = await Promise.all([
    noErr(o11yWindow(`sf_metric:"k8s.container.restarts" AND ${ns}`, 'k8s.container.name')),
    noErr(o11yWindow(`sf_metric:"k8s.container.ready" AND ${ns}`, 'k8s.container.name', null, 'min')),
    noErr(o11yWindow(`sf_metric:"container.memory.working_set" AND ${lf}`, 'k8s.container.name')),
    noErr(o11yWindow(`sf_metric:"k8s.container.memory_limit" AND ${lf}`, 'k8s.container.name')),
  ]);
  return { restarts, ready, mem, lim };
}, render(d) {
  const w = el('div');
  w.append(pageHeader('Kubernetes health', 'Pod state over time for the gateway namespace, the restart counters the AutoDetect detectors watch, and the Remediation Plan the AI Troubleshooting Agent writes for Kubernetes alerts.', '6 · 7'));
  const g = el('div.grid');
  const ser = (r, n) => ((r.series || []).find(x => x.name === n) || {}).values || [];
  const L = d.ready.labels && d.ready.labels.length ? d.ready.labels : d.restarts.labels || [];
  const rows = POD_ROWS.map(([n, href]) => { const rd = ser(d.ready, n), rs = ser(d.restarts, n);
    return { name: n, href, segs: rd.length ? runs(rd.map((v, i) => i > 0 && rs[i] > rs[i - 1] ? { s: 'critical', label: 'restarted' } : v < 1 ? { s: 'warning', label: 'not ready' } : { s: 'good', label: 'Running' })) : [{ from: 0, to: 1, s: 'unknown', label: 'no data' }] }; });
  g.append(card({ title: 'Pod status timeline · namespace tuktukpay', span: 12, lanes: ['metrics'], body: () => d.ready.error ? emptyNote('Observability Cloud: ' + d.ready.error) : stateTimeline({ labels: L.length ? L : ['–'], rows, w: 1100, aria: 'Pod status timeline' }),
    note: 'Per container: magenta = k8s.container.restarts went up in that bucket, amber = a pod of it was not ready (k8s.container.ready = 0, includes rollouts), green = running; from Observability Cloud through the app proxy. Clicking a row opens its page.' }));
  const mem = (((d.mem.series || [])[0] || {}).values || []).map(v => Math.round(v / 1048576)), limit = Math.round((lastNum(((d.lim.series || [])[0] || {}).values || []) || 0) / 1048576);
  g.append(card({ title: 'ledger memory vs limit', span: 6, lanes: ['metrics'], body: () => d.mem.error ? emptyNote('Observability Cloud: ' + d.mem.error) : mem.length ? lineChart({ labels: d.mem.labels, series: [{ name: 'working set MiB', values: mem, color: 'var(--s1)', area: true }], yMax: Math.max(limit, ...mem) * 1.05 || undefined, thresholds: limit ? [{ value: limit, label: `limit ${limit} MiB` }] : [], h: 170 }) : emptyNote('No memory series for ledger.'),
    note: 'The Act 6 sawtooth: memory grows until the limit, OOMKilled, restart, repeat. The clusters cap crash-loop back-off at 30 s so the pod recovers quickly once the leak stops.' }));
  const rl = ser(d.restarts, 'ledger'), rw = ser(d.restarts, 'wallet-sim');
  g.append(card({ title: 'Container restarts', span: 6, lanes: ['metrics'], body: () => d.restarts.error ? emptyNote('Observability Cloud: ' + d.restarts.error) : lineChart({ labels: d.restarts.labels.length ? d.restarts.labels : ['–'], series: [{ name: 'ledger', values: rl.length ? rl : [0], color: 'var(--s2)' }, { name: 'wallet-sim', values: rw.length ? rw : [0], color: 'var(--s7)' }], h: 170, yFmt: (v) => fmt.num(v) }),
    table: () => tableFromSeries(d.restarts.labels || [], [{ name: 'ledger', values: rl }, { name: 'wallet-sim', values: rw }], (v) => fmt.num(v)) }));
  g.append(card({ title: 'AI Troubleshooting Agent · Remediation Plan', span: 12, lanes: ['alerts'], body: () => expectedAgent(S.act === 'act6' ? { impact: 'ledger OOMKilled repeatedly, deployment ledger 0/1 available for minutes at a time; checkout-api errors', causes: [['Memory leak in ledger: RSS grows to the memory limit', 'critical']], evidence: ['Kubernetes: container restart count > 0, last termination reason OOMKilled', 'Logs: memory.pressure before each restart', 'YAML diff: no limit change; image unchanged'], plan: ['Roll back ledger to the previous ReplicaSet', 'Raise memory limit to 512 MiB as a stop-gap', 'Open a ticket with the heap profile from AlwaysOn Profiling (Node.js memory)'] } : S.act === 'act7' ? { impact: 'wallet-sim CrashLoopBackOff (exit code 3 seconds after start); KYA registry unavailable; agent payments fail closed', causes: [['Bad rollout: wallet-sim exits during schema migration', 'critical']], evidence: ['Kubernetes: restart count rising, state waiting reason CrashLoopBackOff', 'Logs: service.crashed exit_code=3 "migration failed"', 'Deployment history: image tag changed'], plan: ['kubectl rollout undo deploy/wallet-sim', 'Verify GET /v1/kya returns 200 and mandate.verified resumes', 'Add a readiness probe on /v1/kya'] } : null, 'a Kubernetes alert') }));
  w.append(g); return w;
} };

/* ---------- Incidents & AI SRE ---------- */
PAGES.incidents = { title: 'Incidents & AI SRE', group: 'Status', async load() {
  return { inc: LIVE.openDetectors || [] };   // open incidents were fetched by detectHealth() for this render
}, render(d) {
  const inc = d.inc, w = el('div');
  w.append(pageHeader('Incidents and AI SRE', 'Every TukTukPay detector in an anomalous state now, read live from Observability Cloud, grouped into the incident it belongs to, with what the AI Troubleshooting Agent should conclude for the act. This is the audit log of the night.', 'all'));
  const g = el('div.grid');
  g.append(card({ title: 'Detector states (anomalous now)', span: 7, lanes: ['alerts'], body: () => inc.length ? simpleTable([{ key: 'since', label: 'Since', fmt: whenAt }, { key: 'detector', label: 'Detector', status: (r) => r.sev }, { key: 'severity', label: 'Severity' }, { key: 'service', label: 'Service', fmt: (v) => v || '–' }], inc, { onRow: (r) => r.url && window.open(r.url, '_blank', 'noopener') })
    : emptyNote(LIVE.incidentError ? 'Could not read incidents from Observability Cloud (' + LIVE.incidentError + '). Is the Splunk Observability Cloud app configured on this stack?' : 'No TukTukPay detector is anomalous. Start an act from the war-room panel; its detectors open incidents here within a few minutes.'),
    link: { label: 'Open alerts in Observability Cloud', url: `${O11Y}/alerts`, what: 'Observability Cloud alerts' } }));
  g.append(card({ title: 'Incident timeline', span: 5, lanes: ['alerts'], body: () => stateTimeline({ labels: liveLabels(), rows: incidentRows(inc) }), note: 'One row per open detector across the selected range; colour = severity; hover for the window. Intelligent alert grouping in Observability Cloud (AI SRE) bundles these into one incident.' }));
  g.append(card({ title: 'What the AI Troubleshooting Agent should conclude', span: 12, lanes: ['alerts', 'mcp'], body: () => incidentSummary() }));
  w.append(g); return w;
} };
function liveLabels() {   // clock labels across the selected range, ending now
  const r = RANGES[S.range], end = Date.now(), out = [];
  for (let i = 0; i < r.n; i++) out.push(new Date(end - (r.n - 1 - i) * r.step * 1000).toTimeString().slice(0, 5));
  return out;
}
function incidentRows(inc) {
  if (!inc.length) return [{ name: 'all detectors', segs: [{ from: 0, to: 1, s: 'good', label: 'ok' }] }];
  const r = RANGES[S.range], end = Date.now(), start = end - (r.n - 1) * r.step * 1000, t = whenAt;
  return inc.map(i => { const f = i.since ? Math.min(1, Math.max(0, (i.since - start) / (end - start))) : 0;
    return { name: i.detector.slice(0, 34), segs: [{ from: 0, to: f, s: 'good', label: 'ok until ' + t(Math.max(start, i.since || start)) }, { from: f, to: 1, s: i.sev, label: 'anomalous since ' + (i.since ? t(i.since) : 'before the range') }] }; });
}
// reference for the presenter: the conclusion each act is built to produce (the agent's real Remediation Plan is on the alert page)
function incidentSummary() {
  const m = {
    act1: 'Incident 11.11-0421 · checkout-api and payment-router latency. Suspected root cause: acquirer acq-kbank timing out for THB cards (BIN 457173) at merchant thai-airways; router failing over to acq-uob with cross-border declines. Evidence: 184 error spans, route.failover ×168 in 55 s, acquirer.late_response. Remediation Plan: not generated (APM alert).',
    act2: 'Incident 11.11-0422 · risk-engine latency. Suspected root cause: CPU saturation after the v3 canary (profiling: _infer_v3). Evidence in the previous page. Remediation Plan: not generated (APM alert).',
    act3: 'Incident 11.11-0423 · copilot token burn. Suspected root cause: tool-call loop (copilot.tool_loop_suspected) triggered by prompt-injected questions; guardrail blocked refund_payment. Recommendation: cap iterations, add tool allow-list per merchant role.',
    act4: 'Incident 11.11-0424 · mandate blocks above 10%. Suspected root cause: agent traffic surge with 15% policy violations; dealhunter.app (KYA C) mandate_over_limit, promo-hunter-bot refused as unregistered. Poisoned listing detected (agent.untrusted_content, security.prompt_injection.suspected).',
    act4b: 'Incident 11.11-0425 · Know-Your-Agent registry unavailable. Suspected root cause: wallet-sim registry database unreachable (503). Impact: every agent payment fails closed; human checkout unaffected. Evidence: kya.registry_unavailable events, mandate.blocked reason mandate_kya_unavailable.',
    act5: 'Incident 11.11-0426 · ledger latency and webhook dead-letters. Suspected root cause: ledger connection pool shrunk to 4; merchant lazada-th webhook endpoint returning 503. Remediation Plan: not generated (APM alert).',
    act6: 'Incident 11.11-0427 · Kubernetes container restarted (ledger). Suspected root cause: memory leak to the 384 MiB limit (OOMKilled ×13). Remediation Plan: roll back / raise limit / profile heap — human approves each step.',
    act7: 'Incident 11.11-0428 · Kubernetes container restarted (wallet-sim). Suspected root cause: bad rollout, exit code 3 during schema migration. Remediation Plan: kubectl rollout undo; verify /v1/kya; add readiness probe.',
  };
  if (!m[S.act]) return emptyNote('No act running, so there is nothing to conclude. Start an act from the war-room panel (or pick one in Scenario to read its expected conclusion).');
  return el('div', null, [el('div.callout', { text: m[S.act] }), el('div.btn-row', null, [o11yLink('Open the alert and its Remediation Plan', `${O11Y}/alerts`, true)])]);
}

/* ---------- Ask the tower: live answers from the same calls the MCP tools make ---------- */
const ASKQ = {
  why: { q: 'Why is the approval rate down right now?', calls: ['splunk: approval by acquirer, now vs previous 30 min', 'splunk: route.failover by backup acquirer', 'splunk: active chaos flags'], run: async () => {
    const [byAcq, fo] = await Promise.all([
      spl(`${PAYQ} earliest=-60m | eval w=if(_time>=relative_time(now(),"-10m"),"now","before") | stats count(eval(event="payment.approved")) as a count as n by payment.acquirer w | eval ap=round(100*a/n,1) | xyseries payment.acquirer w ap`, '-60m'),
      spl(`${LIVE.idx} event=route.failover | stats count by payment.acquirer route.backup_acquirer | sort - count | head 3`, '-15m'),
    ]);
    const drops = byAcq.map(r => ({ a: ACQ_NAMES[r['payment.acquirer']] || r['payment.acquirer'], d: Number(r.now) - Number(r.before) })).filter(x => !isNaN(x.d)).sort((x, y) => x.d - y.d);
    const parts = [];
    if (drops[0] && drops[0].d < -2) parts.push(`${drops[0].a} approval moved ${drops[0].d.toFixed(1)} points in the last 10 minutes`);
    if (fo.length) parts.push(`${fo.reduce((a, r) => a + Number(r.count), 0)} failovers in 15 min, mostly ${ACQ_NAMES[fo[0]['payment.acquirer']] || fo[0]['payment.acquirer']} → ${ACQ_NAMES[fo[0]['route.backup_acquirer']] || fo[0]['route.backup_acquirer']}`);
    if ((LIVE.flags || []).length) parts.push(`chaos flags on: ${LIVE.flags.join(', ')}`);
    return parts.length ? parts.join('; ') + '.' : 'No acquirer moved more than 2 points, no failovers, no chaos flag: approval is within its normal range.';
  } },
  mandate: { q: 'Did any agent pay outside its mandate?', calls: ['splunk: mandate.* by block reason, agent, KYA tier'], run: async () => {
    const r = await spl(`${LIVE.idx} event=mandate.blocked | stats count by mandate.block_reason agent.id | sort - count | head 6`);
    const v = await spl(`${LIVE.idx} event=mandate.verified | stats count`);
    if (!r.length) return `No. ${fmt.num(Number((v[0] || {}).count || 0))} mandates verified and none blocked in range.`;
    return `No approved payment lacked a verified mandate. Blocked at amp.verify_mandate: ` + r.map(x => `${x['mandate.block_reason']} ×${x.count} (${x['agent.id']})`).join(', ') + '. Every block has a trace and a mandate.blocked event with amp.task_id.';
  } },
  cost: { q: 'What did the copilot cost and which merchant drove it?', calls: ['splunk: copilot.answered cost and iterations by merchant'], run: async () => {
    const r = await spl(`${LIVE.idx} event=copilot.answered | stats sum(copilot.cost_usd) as usd avg(copilot.iterations) as it by merchant.id | eventstats sum(usd) as total | eval share=round(100*usd/total) | sort - usd | head 3`);
    if (!r.length) return 'No copilot answers in range.';
    return `$${Number(r[0].total).toFixed(3)} in range; ${r[0]['merchant.id']} drives ${r[0].share}% (avg ${Number(r[0].it).toFixed(1)} tool iterations per answer).`;
  } },
  k8s: { q: 'Which pods restarted and what should I do?', calls: ['o11y: k8s.container.restarts by container (namespace tuktukpay)', 'splunk: memory.pressure / service.crashed'], run: async () => {
    const [w, ev] = await Promise.all([o11yWindow('sf_metric:"k8s.container.restarts" AND k8s.namespace.name:"tuktukpay"', 'k8s.container.name').catch(() => null), spl(`${LIVE.idx} event IN (memory.pressure, service.crashed) | stats count by service.name event`)]);
    const grew = w ? w.series.map(s => ({ n: s.name, d: Math.max(...s.values) - Math.min(...s.values) })).filter(x => x.d > 0) : [];
    const parts = grew.map(x => `${x.n} restarted ${x.d}×`).concat(ev.map(x => `${x['service.name']}: ${x.event} ×${x.count}`));
    return parts.length ? parts.join('; ') + '. Open the Kubernetes alert in Observability Cloud for the Remediation Plan (roll back / raise limit / heap profile).' : 'No container restarted in range.';
  } },
};
function askOpen(key) {
  $('#drawer').classList.add('open');
  if (!key) return;
  const a = ASKQ[key], log = $('#ask-log');
  log.append(el('div.msg.user', { text: a.q }));
  a.calls.forEach(c => log.append(el('div.msg.tool', { text: '→ ' + c })));
  const m = el('div.msg.assistant', null, [el('b', { text: 'Tower · ' }), document.createTextNode('working…')]); log.append(m); log.scrollTop = log.scrollHeight;
  a.run().then(t => { m.lastChild.textContent = t; }).catch(e => { m.lastChild.textContent = 'Could not answer: ' + e.message; });
}
function askInit() {
  const q = $('#ask-q');
  Object.entries(ASKQ).forEach(([k, a]) => q.append(el('button.q', { type: 'button', text: a.q, onclick: () => askOpen(k) })));
  $('#ask-log').append(el('div.msg.assistant', { html: '<b>Live:</b> each answer runs the same searches and Observability Cloud calls the MCP gateway’s <code>splunk_*</code> and <code>o11y_*</code> tools would, and states only what the data shows. An LLM over the MCP gateway turns this into a conversation; that runs from Claude Code, not inside this page.' }));
  $('#ask-open').addEventListener('click', () => askOpen());
  $('#ask-close').addEventListener('click', () => $('#drawer').classList.remove('open'));
}

/* ===== frame, async routing, auto-refresh ===== */
function incidentList(inc) {
  const ul = el('ul.incidents');
  inc.forEach(i => ul.append(el('li', { onclick: () => go(i.href) }, [el('span.chip', { dataset: { s: i.s }, text: STI[i.s] + ' ' + i.s }), el('div.what', null, [el('b', { text: i.name }), el('span', { text: i.note })]), el('span.when', { text: i.when })])));
  return ul;
}
function pageStatus(id) {
  const h = LIVE.health || {}, worst = (ids) => ids.map(x => h[x] || 'good').sort((a, b) => ['good', 'warning', 'serious', 'critical'].indexOf(b) - ['good', 'warning', 'serious', 'critical'].indexOf(a))[0];
  const m = { overview: Object.keys(h), flow: Object.keys(h), acquirers: ['payment-router', 'acquirer-sim'], forensics: ['checkout-api', 'payment-router'], agentic: ['shopping-agent', 'wallet-sim'],
    risk: ['risk-engine'], copilot: ['merchant-copilot'], ledger: ['ledger', 'webhook-dispatcher', 'merchant-sim'], k8s: [], incidents: Object.keys(h) };
  const order = ['good', 'warning', 'serious', 'critical'], s = worst(m[id] || []) || 'good';
  if (id !== 'incidents' && id !== 'overview') return s;
  return (LIVE.openDetectors || []).map(d => d.sev).concat(s).sort((a, b) => order.indexOf(b) - order.indexOf(a))[0];   // worst open detector
}
let routeSeq = 0;
async function route() {
  const h = location.hash.replace(/^#\/?/, '') || 'overview';
  const parts = h.split('?')[0].split('/'), id = parts[0], param = parts.slice(1).join('/');
  const page = PAGES[id] || PAGES.overview, seq = ++routeSeq, content = $('#content');
  $$('.nav a').forEach(a => a.classList.toggle('active', a.getAttribute('href') === '#/' + (PAGES[id] ? id : 'overview')));
  content.style.opacity = content.childElementCount ? '.55' : '1';   // keep the previous frame while refetching
  try {
    await Promise.all([detectAct(), detectHealth()]);
    const data = await page.load(param);
    if (seq !== routeSeq) return;
    const crumbs = el('div.crumbs'); crumbs.append(el('a', { href: '#/overview', text: 'Control tower' }));
    if (id !== 'overview' && PAGES[id]) { crumbs.append(' / '); crumbs.append(el('a', { href: '#/' + id, text: page.title })); }
    if (param) { crumbs.append(' / '); crumbs.append(document.createTextNode(ACQ_NAMES[param] || decodeURIComponent(param))); }
    crumbs.append(el('span', { style: 'float:right', text: 'updated ' + new Date().toTimeString().slice(0, 8) }));
    const nodes = [crumbs];
    const picked = S.act !== LIVE.detected;   // chosen in the Scenario dropdown but not what the flags say is running
    if (S.act !== 'baseline') nodes.push(el('div.callout.act-banner', null, [el('b', { text: ACTS[S.act].label + ' — ' }), document.createTextNode(ACTS[S.act].blurb + (picked
      ? '  Not running now: start it from the war-room panel; the charts below are live.' : LIVE.flags.length ? `  (flags on: ${LIVE.flags.join(', ')})` : ''))]));
    else if (picked) nodes.push(el('div.callout.act-banner', null, [el('b', { text: 'Baseline view — ' }), document.createTextNode(`${ACTS[LIVE.detected].label} is running (flags on: ${LIVE.flags.join(', ')}).`)]));
    nodes.push(page.render(data, param));
    content.replaceChildren(...nodes);
  } catch (e) {
    console.error(e);
    if (seq === routeSeq) content.replaceChildren(el('div.callout', { text: 'Could not load this page: ' + e.message + ' — the page retries on the next refresh.' }));
  } finally { if (seq === routeSeq) content.style.opacity = '1'; }
  const running = LIVE.detected && LIVE.detected !== 'baseline';
  $('#act-pill').textContent = running ? ACTS[LIVE.detected].pill : 'No act running';   // the pill always tells the truth
  $('#act-pill').classList.toggle('on', running);
  navStatus();
}
function rerender() { route(); }

const FRAME = `
<div class="frame">
  <header class="topbar">
    <h1>TukTukPay Control Tower</h1>
    <span class="env" title="Observability Cloud environment and the Splunk Cloud index this app reads">env ${LIVE.env} · ${LIVE.idx}</span>
    <span class="spacer"></span>
    <label class="ctl">Scenario <select id="act-select" aria-label="Scenario (storyline act)"></select></label>
    <label class="ctl">Range <select id="range-select" aria-label="Time range"></select></label>
    <span class="act-pill" id="act-pill">…</span>
    <button class="ask-btn" id="ask-open" type="button"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M16 18a2 2 0 0 1 2 2a2 2 0 0 1 2 -2a2 2 0 0 1 -2 -2a2 2 0 0 1 -2 2zm0 -12a2 2 0 0 1 2 2a2 2 0 0 1 2 -2a2 2 0 0 1 -2 -2a2 2 0 0 1 -2 2zm-7 12a6 6 0 0 1 6 -6a6 6 0 0 1 -6 -6a6 6 0 0 1 -6 6a6 6 0 0 1 6 6z"/></svg> Ask the tower</button>
  </header>
  <aside class="sidebar"><ul class="nav" id="nav"></ul>
    <div class="legend">Live from index=tuktukpay and Observability Cloud. Dot = worst state feeding that page. Refreshes every 60 s. Badges say which data lane feeds each panel.</div></aside>
  <main class="content" id="content" aria-live="polite"><div class="callout">Loading the tower…</div></main>
</div>
<aside class="drawer" id="drawer" aria-label="Ask the tower">
  <header><h3><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M16 18a2 2 0 0 1 2 2a2 2 0 0 1 2 -2a2 2 0 0 1 -2 -2a2 2 0 0 1 -2 2zm0 -12a2 2 0 0 1 2 2a2 2 0 0 1 2 -2a2 2 0 0 1 -2 -2a2 2 0 0 1 -2 2zm-7 12a6 6 0 0 1 6 -6a6 6 0 0 1 -6 -6a6 6 0 0 1 -6 6a6 6 0 0 1 6 6z"/></svg> Ask the tower</h3><span class="lane" data-lane="mcp">live searches</span><button class="btn" id="ask-close" type="button">Close</button></header>
  <div class="log" id="ask-log"></div><div class="ask" id="ask-q"></div>
</aside>
<div class="toast" id="toast" role="status"></div>`;

function towerBoot() {
  const root = document.getElementById('tower-root');
  if (!root || root.dataset.booted) return;
  root.dataset.booted = '1';
  root.innerHTML = FRAME;   // static markup only; every data value is inserted with textContent
  tipInit();
  const nav = $('#nav'); let group = null; const ORDER = ['Status', 'Payments', 'AI', 'Operations'];
  Object.entries(PAGES).sort((a, b) => ORDER.indexOf(a[1].group) - ORDER.indexOf(b[1].group)).forEach(([id, p]) => {
    if (p.group !== group) { group = p.group; nav.append(el('li.group', { text: group })); }
    nav.append(el('li', null, [el('a', { href: '#/' + id }, [document.createTextNode(p.title), el('span.dot', { dataset: { s: 'good' } })])]));
  });
  const as = $('#act-select'); as.append(el('option', { value: 'auto', text: 'Auto (live)' }));
  Object.entries(ACTS).forEach(([k, a]) => as.append(el('option', { value: k, text: a.label })));
  try { S.pick = localStorage.getItem('tower.scenario') || 'auto'; } catch (e) { S.pick = 'auto'; }
  if (![...as.options].some(o => o.value === S.pick)) S.pick = 'auto';
  as.value = S.pick; as.addEventListener('change', () => {
    S.pick = as.value; try { localStorage.setItem('tower.scenario', S.pick); } catch (e) { /* private window */ }
    toast(S.pick === 'auto' ? 'Following the act the war-room panel is running' : ACTS[S.pick].label + ' — start it from the war-room panel to see it in the data');
    route();
  });
  const rs = $('#range-select'); Object.entries(RANGES).forEach(([k, r]) => rs.append(el('option', { value: k, text: r.label })));
  rs.value = S.range; rs.addEventListener('change', () => { S.range = rs.value; route(); });
  window.addEventListener('hashchange', route);
  askInit();
  route();
  setInterval(() => { if (document.visibilityState === 'visible' && !$('#drawer').classList.contains('open')) route(); }, 60000);
}
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', towerBoot); else towerBoot();
setTimeout(towerBoot, 500); setTimeout(towerBoot, 2000);   // Simple XML renders the HTML panel after the script loads

})();
