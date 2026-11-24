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
