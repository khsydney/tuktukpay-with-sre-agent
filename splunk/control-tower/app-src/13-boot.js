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
