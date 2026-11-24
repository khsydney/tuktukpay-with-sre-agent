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
