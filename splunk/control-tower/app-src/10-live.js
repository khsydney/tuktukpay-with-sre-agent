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
