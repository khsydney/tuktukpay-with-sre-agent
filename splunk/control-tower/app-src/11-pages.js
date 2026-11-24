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
