"""The agent console's single page: status strip, symptom question bar, alerts and cases, a centre column with the
hypothesis tree, the service topology and the live agent trace (every raw MCP call), and the war-room brief with the
decision box first. Inline CSS and JavaScript; every value goes in with textContent. Design and colour codes from
https://www.splunk.com/ (the war-room design rules); ?facilitator=1 shows the injected faults (hidden by default: they give the answer away)."""

PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>TukTukPay AI SRE agent</title>
<link rel="icon" href="/brand/favicon.svg" type="image/svg+xml">
<style>
@font-face{font-family:"Inter";font-weight:400;font-display:swap;src:url("/brand/Inter-Regular.woff2") format("woff2")}@font-face{font-family:"Inter";font-weight:600;font-display:swap;src:url("/brand/Inter-SemiBold.woff2") format("woff2")}
/* Colour has one meaning: magenta = alerting/faulty, green = healthy/validated, amber = degraded/inconclusive, white = the agent's path. Weights 400/600. */
:root{--p1:rgba(255,255,255,.1);--p2:rgba(255,255,255,.16);--solid:#0C1724;--line:rgba(255,255,255,.2);--text:#FFFFFF;--dim:#D5DCE5;--mute:#B8C0CC;--edge:rgba(255,255,255,.35);--edge2:rgba(255,255,255,.6);--acc:#FFFFFF;--acc-ink:#0C1724;--main:#CE0070;--ok:#2FCB8B;--warn:#FFAB0F;--bad:#FF0F7B;--mono:ui-monospace,SFMono-Regular,Menlo,monospace;--heading:linear-gradient(90deg,#FFAB0F 5%,#FF712B 40.5%,#FF0F7B 85.5%);--lift:inset 0 1px 0 rgba(255,255,255,.22),0 2px 12px rgba(0,0,0,.12),0 14px 32px rgba(0,0,0,.5)}
*{box-sizing:border-box}html,body{height:100%}body{position:relative;z-index:0;margin:0;background:radial-gradient(55% 900px at 0 100%,rgba(150,0,80,.6),transparent 75%) no-repeat,radial-gradient(60% 1000px at 100% 100%,rgba(170,60,35,.6),transparent 75%) no-repeat,linear-gradient(180deg,#000 0,#00052A 420px,#000B3F 1100px,#000B3F 100%);color:var(--text);font:400 14px/1.5 "Inter",system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;font-variant-numeric:tabular-nums;display:flex;flex-direction:column}
.aurora{position:absolute;top:0;left:0;right:0;height:320px;z-index:-1;overflow:hidden;pointer-events:none;background:radial-gradient(45% 75% at 67% -12%,rgba(238,29,98,.6),transparent 72%),radial-gradient(30% 55% at 60% -14%,rgba(249,157,28,.75),transparent 72%),radial-gradient(35% 70% at 100% -5%,rgba(70,20,170,.5),transparent 72%);-webkit-mask-image:linear-gradient(180deg,#000 45%,transparent);mask-image:linear-gradient(180deg,#000 45%,transparent)}
.i{width:14px;height:14px;flex:none;display:inline-block;vertical-align:-2px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
.gt{width:fit-content;background:var(--heading);-webkit-background-clip:text;background-clip:text;color:transparent}
b,strong,h1,h2,h3,h4{font-weight:600}a{color:var(--acc)}code{font:12px var(--mono);background:var(--p2);padding:0 4px;border-radius:4px}
button{font:inherit;cursor:pointer;border-radius:24px;padding:8px 16px;border:1px solid var(--edge2);background:transparent;color:var(--text)}
button:hover{border-color:var(--text);background:var(--p1)}button:disabled{opacity:.6;cursor:default}
button:focus-visible,input:focus-visible,textarea:focus-visible,a:focus-visible,summary:focus-visible,.item:focus-visible{outline:2px solid var(--acc);outline-offset:2px}
input::placeholder,textarea::placeholder{color:var(--mute)}
input,textarea{font:inherit;background:var(--p1);border:1px solid var(--edge);border-radius:24px;color:var(--text);padding:8px 12px;min-width:0}
header{display:flex;align-items:center;gap:16px;padding:16px 24px 12px;flex-wrap:wrap}.logo{display:block;height:32px;width:auto}
header h1{margin:0;font-size:24px;line-height:1.2;white-space:nowrap}header .meta{color:var(--dim);font-size:12px}
.ask{flex:1;display:flex;gap:8px;max-width:720px;margin-left:auto;min-width:280px}.ask input{flex:1}.ask button{background:var(--main);border-color:var(--main);color:#fff;font-weight:600}.ask button:hover{background:var(--bad);border-color:var(--bad);color:#000}body:has(.decide.live) .ask button{background:#fff;border-color:#fff;color:var(--acc-ink)}
.strip{display:flex;margin:0 24px;overflow-x:auto;flex:none;background:var(--p1);border-radius:24px;box-shadow:var(--lift);backdrop-filter:blur(8px)}
.tile{flex:1;min-width:160px;padding:12px 24px;border-right:1px solid var(--line)}.tile:last-child{border-right:0}
.tile .l{font-size:12px;color:var(--mute)}.tile .v{font-size:20px;font-weight:600;display:flex;align-items:center;gap:8px;white-space:nowrap}.tile .s{font-size:12px;color:var(--mute);overflow-wrap:anywhere}
.dot{width:8px;height:8px;border-radius:50%;flex:none;background:var(--mute);display:inline-block}.dot.good{background:var(--ok)}.dot.warn{background:var(--warn)}.dot.bad{background:var(--bad)}
.fchip{display:inline-block;font:12px var(--mono);border:1px solid var(--bad);color:var(--bad);border-radius:999px;padding:0 8px;margin:4px 4px 0 0}.fchip.load{border-color:var(--edge);color:var(--mute)}
.chips{display:flex;flex-wrap:wrap;gap:8px;padding:12px 24px;flex:none}.chips button{border-radius:999px;padding:0 12px;font-size:12px;line-height:24px}
.grid{display:grid;grid-template-columns:272px minmax(0,2.2fr) minmax(0,1fr);gap:16px;padding:0 24px 24px;flex:1;min-height:0}
.pane{min-width:0;display:flex;flex-direction:column;min-height:0;overflow:hidden;background:var(--p1);border-radius:24px;box-shadow:var(--lift);backdrop-filter:blur(8px)}
.scroll{overflow:auto;flex:1;min-height:0}[hidden]{display:none!important}
.sub{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:16px 16px 8px;font-size:16px;font-weight:600}.sub .clr,.sub .count{font-size:12px}
.clr{display:flex;gap:8px;align-items:center;white-space:nowrap}.clr button{padding:0 8px;font-size:12px;line-height:24px;font-weight:400}.clr .link{border:0;color:var(--acc);text-decoration:underline}
.count{font-size:12px;padding:0 8px;border-radius:999px;border:1px solid var(--warn);color:var(--warn)}
.item{position:relative;display:grid;gap:0;padding:8px 16px 8px 32px;border-left:2px solid transparent;cursor:pointer;overflow-wrap:anywhere;min-width:0}
.item:hover{background:var(--p1)}.item.on{background:var(--p2);border-left-color:var(--acc)}.item>.dot{position:absolute;left:14px;top:15px}
.item .t{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}.item .s{font-size:12px;color:var(--mute);display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.item button,.hv button{padding:0 8px;font-size:12px;line-height:24px;justify-self:start}.hv{display:flex;gap:4px;flex-wrap:wrap;margin-top:4px}
.item button.primary{color:var(--acc);border-color:var(--acc);margin-top:4px}
@media (hover:hover){.item .hv{display:none}.item:hover .hv,.item:focus-within .hv,.item.on .hv{display:flex}}
.item.merged{border-left-color:var(--warn)}.tag{display:inline-block;font-size:12px;padding:0 8px;border:1px solid var(--acc);color:var(--acc);border-radius:4px;margin-right:8px;cursor:pointer;background:transparent}.tag.warn{border-color:var(--warn);color:var(--warn)}
/* centre column */
.vt{display:flex;gap:4px;padding:8px;border-bottom:1px solid var(--line);align-items:center;flex:none}.vt button{border:0;font-weight:600;color:var(--mute);padding:8px 16px}.vt button:hover{color:var(--text)}
.vt button[aria-selected=true]{color:var(--acc-ink);background:#fff}.vt .sp{flex:1}.vt .live{font-size:12px;color:var(--mute)}
.legend{display:flex;flex-wrap:wrap;align-items:center;gap:8px 16px;font-size:12px;color:var(--mute);padding:12px 16px 0}.legend .line{display:inline-block;width:16px;border-top:2px solid var(--acc);vertical-align:middle;margin-right:4px}
.note{font-size:12px;color:var(--mute);padding:8px 16px 0}
.pill{font-size:12px;padding:0 8px;border-radius:999px;border:1px solid var(--line);font-weight:600;color:var(--mute);white-space:nowrap}
.pill.validated{color:var(--ok);border-color:var(--ok)}.pill.inconclusive{color:var(--warn);border-color:var(--warn)}.pill.nottested{border-style:dashed}.pill.open{color:var(--acc);border-color:var(--acc)}.pill.rc{border-color:var(--acc);color:var(--acc)}
/* top-down tree: li = [box, ul of children in a row]; connectors drawn with pseudo-elements */
.ht{overflow-x:auto;padding:8px 0 16px;display:flex}.ht ul{list-style:none;margin:0;padding:24px 0 0;display:flex;justify-content:center;position:relative}.ht>ul{padding-top:0;margin:0 auto}
.ht li{display:flex;flex-direction:column;align-items:center;position:relative;padding:24px 4px 0}.ht>ul>li{padding-top:0}
.ht li::before,.ht li::after{content:"";position:absolute;top:0;width:50%;height:24px;border-top:2px solid var(--edge)}.ht li::before{right:50%}.ht li::after{left:50%;border-left:2px solid var(--edge);margin-left:-1px}
.ht>ul>li::before,.ht>ul>li::after{display:none}.ht li:first-child::before,.ht li:last-child::after{border-top:0}.ht li:last-child::after{border-left:0}.ht li:last-child::before{border-right:2px solid var(--edge);margin-right:-1px}
.ht li:only-child::before{display:none}.ht li:only-child::after{border-top:0;border-left:2px solid var(--edge)}
.ht ul ul::before{content:"";position:absolute;top:0;left:50%;height:24px;border-left:2px solid var(--edge);margin-left:-1px}
.ht li.path::after,.ht ul.path::before{border-left-color:var(--acc)}.ht li.path:last-child::before{border-right-color:var(--acc)}
.bx{flex:none;width:var(--bw,124px);min-height:96px;display:flex;flex-direction:column;text-align:left;padding:8px;border-radius:12px;background:#1A2450;border:1px solid var(--line);border-left:4px solid var(--edge);line-height:1.35;position:relative;z-index:1}
.bx:hover,.bx[aria-pressed=true]{background:#2A3463}.bx .k{display:flex;flex-wrap:wrap;gap:4px 8px;align-items:center;font-size:12px;color:var(--mute);margin-bottom:4px}.bx .k .id{font-family:var(--mono)}
.bx .tt{display:-webkit-box;-webkit-line-clamp:4;-webkit-box-orient:vertical;overflow:hidden;overflow-wrap:normal;hyphens:none}.bx .m{font-size:12px;color:var(--mute);margin-top:auto;padding-top:4px;white-space:nowrap}
.bx.validated,.bx.svc-ok{border-left-color:var(--ok)}.bx.invalidated{border-left-color:var(--edge2);color:var(--mute)}.bx.inconclusive,.bx.svc-warn{border-left-color:var(--warn)}.bx.nottested,.bx.svc-na{border-style:dashed;border-left-style:solid;color:var(--mute)}.bx.open{border-left-color:var(--acc)}
.bx.alert,.bx.svc-alert,.bx.svc-root{border-left-color:var(--bad)}.bx.alert{width:224px;min-height:0}.topo .bx{min-height:64px}
.bx.root{border:2px solid var(--acc);border-left-width:4px;background:#232D5C}.bx.root.validated{border-left-color:var(--ok)}.bx.root.svc-root{border-left-color:var(--bad)}.bx.root[aria-pressed=true]{background:#343E6C}
.bx .rc{color:var(--acc);font-weight:600;white-space:nowrap}
.detail{padding:0 16px 16px}.lab{font-size:12px;color:var(--mute);margin:16px 0 8px;font-weight:600}
.node{border:1px solid var(--line);border-left:4px solid var(--edge);border-radius:16px;background:var(--p1);padding:8px 16px}.node.validated{border-left-color:var(--ok)}.node.inconclusive{border-left-color:var(--warn)}.node.root{border-color:var(--acc)}.node.root.validated{border-left-color:var(--ok)}
.nh{display:flex;gap:8px;align-items:center;flex-wrap:wrap;font-size:12px;color:var(--mute);margin-bottom:4px}.nh .id{font-family:var(--mono)}.nh .sp{flex:1}.fd{color:var(--mute);margin-top:4px}
.ck{font-size:12px;color:var(--mute);margin-top:4px}.ck.good b{color:var(--ok)}.ck.bad b{color:var(--warn)}
.evd{display:grid;grid-template-columns:64px minmax(0,1fr);gap:8px;padding:8px 0;border-top:1px solid var(--line)}.sig{font-size:12px;color:var(--mute);text-transform:capitalize}
/* agent trace */
#trace{padding:8px 16px}.row{display:grid;grid-template-columns:56px minmax(0,1fr);gap:8px;padding:4px 0;overflow-wrap:anywhere}.row .at{font:12px var(--mono);color:var(--mute);padding-top:2px;text-align:right}
.box{border:1px solid var(--line);border-radius:16px;padding:8px 12px;background:var(--p1)}.box.think{border-left:4px solid #0064DA}.box.act{border-left:4px solid var(--warn)}.box.done{border-left:4px solid var(--ok)}.box.err{border-left:4px solid var(--bad)}.box.user{background:var(--p2)}
.box .who{font-size:12px;color:var(--mute);margin-bottom:4px}.mcp{font:12px var(--mono);color:var(--text)}.mcp .srv,.mcp .ms{color:var(--mute)}.mcp .ms.bad{color:var(--bad)}
.plain{font-size:12px;color:var(--mute)}.why{font-size:12px;color:var(--mute);margin-top:4px}.why b{color:var(--acc)}
details{margin:4px 0}summary{cursor:pointer;color:var(--mute);font-size:12px}
pre{white-space:pre-wrap;word-break:break-all;font:12px var(--mono);background:rgba(0,0,0,.3);border:1px solid var(--line);border-radius:12px;padding:8px;margin:4px 0 0;max-height:224px;overflow:auto}
.follow{display:flex;gap:8px;padding:8px 16px;border-top:1px solid var(--line);flex:none}.follow input{flex:1}.follow button.stopbtn{color:var(--bad);border-color:var(--bad)}
/* brief */
.brief{padding:8px 24px 24px}.brief h3{font-size:16px;line-height:1.4;margin:16px 0 8px}.brief p{margin:0 0 8px}.brief ul{margin:4px 0 8px;padding-left:16px}
.decide{background:var(--p2);border:1px solid var(--line);border-radius:16px;padding:16px;margin:8px 0 8px}.decide.live{background:#232D5C;border-color:#fff;position:sticky;top:0;z-index:2;box-shadow:0 8px 24px rgba(0,0,0,.3)}.decide.live::before{content:"";display:block;width:32px;height:4px;margin-bottom:8px;border-radius:2px;background:linear-gradient(90deg,#FF0F7B,#FF712B)}
.decide .l{font-size:12px;color:var(--mute);font-weight:600}.decide.live .l{color:var(--acc)}.decide .ttl{font-size:20px;font-weight:600;line-height:1.3;margin:4px 0}.decide .m{font-size:12px;color:var(--mute)}
.btns{display:flex;gap:8px;flex-wrap:wrap;margin-top:16px}.btns.minor{margin-top:8px}.btns.minor button{padding:4px 8px;font-size:12px}.approve{background:var(--main);border-color:var(--main);color:#fff;font-weight:600}.approve:hover{background:var(--bad);border-color:var(--bad);color:#000}
.facts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px 16px;margin:8px 0 16px;font-size:12px;color:var(--mute)}.facts span{display:flex;flex-direction:column;min-width:0}.facts b,.facts a{font-size:14px;color:var(--text)}.facts a{color:var(--acc)}
.conf{display:flex;align-items:center;gap:8px;flex-direction:row!important}.conf .bar{flex:1;max-width:64px;height:8px;border-radius:4px;background:var(--line);overflow:hidden}.conf .bar i{display:block;height:100%;background:var(--ok)}
.chain{list-style:none;padding:0!important;margin:0;counter-reset:c}.chain li{position:relative;padding:0 0 8px 32px;counter-increment:c}.chain li::before{content:counter(c);position:absolute;left:0;top:0;width:24px;height:24px;border-radius:50%;background:var(--p2);border:1px solid var(--line);font-size:12px;display:grid;place-items:center;color:var(--mute)}.chain li:first-child::before{border-color:var(--acc);color:var(--acc)}
.kv{display:grid;grid-template-columns:88px minmax(0,1fr);gap:4px 8px;margin-top:8px;overflow-wrap:anywhere}.kv .k{font-size:12px;color:var(--mute);padding-top:2px}
.fb{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-top:16px;padding-top:16px;border-top:1px solid var(--line);color:var(--mute)}.fb button{padding:4px 8px;font-size:12px}
.cat{display:inline-block;font-size:12px;font-weight:600;color:var(--mute)}
.empty{color:var(--mute);text-align:center;margin:40px 24px}.err{color:var(--bad)}
.banner{border:1px solid var(--acc);border-radius:16px;padding:8px 16px;margin:8px 0;display:grid;gap:8px}.banner .h{font-weight:600}.banner .s{font-size:12px}.banner button{justify-self:start;color:var(--acc);border-color:var(--acc);padding:4px 8px;font-size:12px}
.banner.warn{border-color:var(--warn)}.banner.warn button{color:var(--warn);border-color:var(--warn)}
.ties{margin-top:8px}.ties .head{font-size:12px;font-weight:600;color:var(--mute);margin:8px 0}.ties .item{padding:8px;border:1px solid var(--line);border-radius:16px;margin-bottom:8px;cursor:default;background:var(--p1)}.ties .item .s{-webkit-line-clamp:unset;display:block}
.ties .foot{display:flex;gap:4px;flex-wrap:wrap;margin-top:8px}.ties .foot button{padding:4px 8px;font-size:12px;line-height:1.5}.ties .foot .go{color:var(--acc);border-color:var(--acc)}
dialog.modal{background:var(--solid);color:var(--text);border:1px solid var(--line);border-radius:24px;padding:24px;width:min(500px,92vw);box-shadow:0 24px 72px rgba(0,0,0,.5)}dialog.modal::backdrop{background:rgba(0,0,0,.6)}
.modal h4{margin:0 0 8px;font-size:16px}.modal .msg{margin:0 0 16px;color:var(--mute)}.modal .msg b{color:var(--text)}.modal label{display:block;font-size:12px;color:var(--mute);margin:4px 0 8px}
.modal textarea{width:100%;min-height:72px;resize:vertical}.modal .quick{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 8px}.modal .quick button{border-radius:999px;padding:0 12px;font-size:12px;line-height:24px}.modal .quick button.on{border-color:var(--acc);color:var(--acc)}
.modal .foot{display:flex;justify-content:flex-end;gap:8px;margin-top:16px}.modal .go{background:var(--main);border-color:var(--main);color:#fff;font-weight:600}.modal .go.danger{background:var(--bad);border-color:var(--bad);color:#000}
#toast{position:fixed;right:16px;bottom:16px;max-width:min(440px,90vw);background:var(--solid);border:1px solid var(--line);border-left:4px solid var(--acc);border-radius:16px;padding:8px 16px;box-shadow:0 8px 40px rgba(0,0,0,.4);opacity:0;transform:translateY(8px);transition:opacity .2s,transform .2s;pointer-events:none;z-index:10}#toast.show{opacity:1;transform:none}#toast.bad{border-left-color:var(--bad)}
@media (max-width:1100px){html,body{height:auto}.grid{grid-template-columns:minmax(0,1fr);padding:0 16px 16px}.pane:last-child{order:-1}.scroll{overflow:visible}.ht{overflow-x:auto}header{padding:12px 16px}.ask{max-width:none;flex-basis:100%;margin-left:0}.brief{padding:8px 16px 16px}.decide.live{position:static}.strip{margin:0 16px}.tile{padding:8px 16px}.chips{padding:8px 16px}}
@media (max-width:480px){header h1{font-size:20px;white-space:normal}.grid,.strip,.chips{min-width:0}}
</style></head><body>
<svg width="0" height="0" style="position:absolute" aria-hidden="true"><symbol id="ic-check" viewBox="0 0 24 24"><path d="M5 12l5 5l10 -10"/></symbol><symbol id="ic-x" viewBox="0 0 24 24"><path d="M18 6l-12 12"/><path d="M6 6l12 12"/></symbol><symbol id="ic-external" viewBox="0 0 24 24"><path d="M12 6h-6a2 2 0 0 0 -2 2v10a2 2 0 0 0 2 2h10a2 2 0 0 0 2 -2v-6"/><path d="M11 13l9 -9"/><path d="M15 4h5v5"/></symbol></svg>
<div class="aurora"></div>
<header><img class="logo" src="/brand/splunk-logo-white.svg" alt="Splunk by Cisco" onerror="this.remove()"><h1 class="gt">TukTukPay AI SRE agent</h1><span class="meta" id="mode">…</span><form class="ask" id="askform"><input id="symptom" aria-label="Describe a symptom to investigate" placeholder="Describe what you see, e.g. card payments failing at checkout" autocomplete="off"><button type="submit">Investigate</button></form></header>
<div class="strip" id="strip"><div class="tile"><div class="l">Status</div><div class="v">…</div><div class="s">loading</div></div></div>
<div class="chips" id="chips" aria-label="Example symptoms"></div>
<div class="grid">
  <section class="pane" aria-label="Alerts and cases"><div class="scroll"><div id="needs" hidden><div class="sub"><span class="gt">Needs your decision</span> <span class="count" id="needcount">0</span></div><div id="decisions"></div></div><div class="sub"><span class="gt">Open alerts</span> <span class="clr" id="clr-alerts"></span></div><div id="alerts"><div class="item"><span class="s">loading…</span></div></div><div class="sub"><span class="gt">Recent cases</span> <span class="clr" id="clr-cases"></span></div><div id="cases"></div></div></section>
  <section class="pane" aria-label="Agent reasoning"><div class="vt" role="tablist" id="vt"><span class="sp"></span><span class="live" id="runstate"></span></div>
    <div class="scroll" id="pane-tree"><div class="note" id="treenote"></div><div class="legend" id="legend"></div><div class="ht" id="tree" role="group" aria-label="Hypothesis tree"></div><div class="detail" id="detail" aria-live="polite"></div></div>
    <div class="scroll" id="pane-topo" hidden><div class="note" id="toponote"></div><div class="legend" id="tlegend"></div><div class="ht topo" id="topo" role="group" aria-label="Service topology"></div><div class="detail" id="tdetail" aria-live="polite"></div></div>
    <div class="scroll" id="trace" hidden><div class="empty">Ask a question above, or press <b>Triage</b> on an alert. Every step appears here as it happens: the evidence code collects, each model step with its reasoning, and every raw MCP call to Splunk Observability Cloud and Splunk Enterprise with its arguments and timing.</div></div>
    <form class="follow" id="follow"><input id="q" aria-label="Follow-up question" placeholder="Follow-up question about this case…" autocomplete="off" disabled><button type="button" id="stop" class="stopbtn" hidden title="Stop the running investigation or follow-up at its next checkpoint">Stop</button><button type="submit">Ask</button></form></section>
  <section class="pane" aria-label="War-room brief"><div class="scroll brief" id="brief"><div class="empty">The brief appears when the investigation concludes: the decision, impact, root cause, the team to page and the evidence.</div></div></section>
</div>
<div id="toast" role="status" aria-live="polite"></div>
<script>
'use strict';
window.addEventListener('error', (e) => { const a = document.getElementById('alerts'); if (a) a.textContent = 'Page error: ' + e.message; });
window.addEventListener('unhandledrejection', (e) => { const a = document.getElementById('alerts'); if (a) a.textContent = 'Request failed: ' + ((e.reason && e.reason.message) || e.reason); });
const H = { 'Content-Type': 'application/json' };
const $ = (s) => document.querySelector(s);
function el(tag, cls, text) { const n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; }
function ic(name) { const s = document.createElementNS('http://www.w3.org/2000/svg', 'svg'); s.setAttribute('class', 'i'); s.setAttribute('aria-hidden', 'true'); const u = document.createElementNS('http://www.w3.org/2000/svg', 'use'); u.setAttribute('href', '#ic-' + name); s.append(u); return s; }
const api = (p, body) => fetch(p, body ? { method: 'POST', headers: H, body: JSON.stringify(body) } : { headers: H }).then(r => r.json());
const short = (d) => String(d || '').replace(/^TukTukPay \[[^\]]+\] /, '').replace(/^Reported symptom \(operator question\): /, 'question: ');
const mdl = (m) => String(m || '').replace('global.anthropic.', '');
const CATEGORY = { dependency_degraded: 'DEPENDENCY', config_change: 'CHANGE', resource_exhaustion: 'INFRASTRUCTURE', bad_release: 'RELEASE', capacity: 'CAPACITY',
  abuse_or_governance: 'GOVERNANCE', application_bug: 'APPLICATION', unknown: 'UNDETERMINED' };
const PRESETS = [
  ['Card payments failing', 'Merchants report card payments failing or timing out at checkout. What is going on and what should we do?'],
  ['Checkout is slow', 'Checkout is slow for customers right now. Find the cause.'],
  ['Agent payments blocked', 'Shopping agents say their payments are being blocked. Is something broken?'],
  ['Copilot cost spike', 'The merchant copilot bill is spiking. What is driving it?'],
  ['Pods restarting', 'Some pods keep restarting. Which ones and why?'],
  ['Webhooks failing', 'A merchant says they stopped receiving payment webhooks. Investigate.'],
];
const freshCalls = () => ({ 'o11y-mcp-gateway': 0, 'splunk-mcp-server': 0, 'splunk-rest': 0 });
let current = null, es = null, t0 = null, calls = freshCalls(), briefShown = false;
function setRunning(on) { const b = $('#stop'); if (!b) return; b.hidden = !on; if (on) { b.disabled = false; b.textContent = 'Stop'; } }

function rich(text) {   // tiny safe formatter: **bold**, `code`, "- " bullets, headings; text nodes only
  const out = el('div'); let ul = null;
  String(text || '').split('\n').forEach(line => {
    const bullet = /^\s*[-*] /.test(line), head = /^#{1,4} /.test(line);
    if (!line.trim()) { ul = null; return; }
    let target = out;
    if (bullet) { if (!ul) { ul = el('ul'); out.append(ul); } target = ul; } else ul = null;
    const node = el(bullet ? 'li' : head ? 'b' : 'p'); node.style.margin = bullet ? '2px 0' : '3px 0'; if (head) node.style.display = 'block';
    line.replace(/^\s*[-*] |^#{1,4} /, '').split(/(\*\*[^*]+\*\*|`[^`]+`)/).forEach(part => {
      if (/^\*\*[^*]+\*\*$/.test(part)) node.append(el('b', null, part.slice(2, -2)));
      else if (/^`[^`]+`$/.test(part)) { const c = el('code', null, part.slice(1, -1)); c.style.font = '12px var(--mono)'; node.append(c); }
      else node.append(document.createTextNode(part));
    });
    target.append(node);
  });
  return out;
}
function details(label, text) { const d = el('details'); d.append(el('summary', null, label), el('pre', null, text || '')); return d; }
function at(e) { const t = Number(e.t) || Date.parse(e.ts) / 1000; if (t0 == null) t0 = t; return '+' + Math.max(0, t - t0).toFixed(1) + 's'; }
function row(e, node) { const r = el('div', 'row'); r.append(el('div', 'at', at(e)), node); $('#trace').append(r); $('#trace').scrollTop = $('#trace').scrollHeight; return r; }
function box(cls, who, nodes) { const b = el('div', 'box ' + (cls || '')); if (who) b.append(el('div', 'who', who)); (nodes || []).forEach(n => n && b.append(typeof n === 'string' ? el('div', null, n) : n)); return b; }
function plain(t) { return el('div', 'plain', t); }
const REL = { likely_cause_of: 'may be the cause of', likely_symptom_of: 'may be a symptom of', same_service: 'same service as' };
const relPath = (j) => (j.path || []).length > 1 ? j.path.join(' → ') : String(j.rule || j.relation || '').replace(/_/g, ' ');
const hhmm = (ts) => ts ? String(ts).slice(11, 16) + 'Z' : '';
const who = (by) => String(by || '').replace(/@console$/, '');
function groupedNode(list) {   // merged / added alerts as highlighted chips; topology joins as plain text
  if (!(list || []).length) return null; const w = el('div');
  list.forEach(j => { const line = el('div');
    if (j.rule === 'merged') { const t = el('span', 'tag', `MERGED from ${j.from_case || 'another case'}`); if (j.from_case) t.onclick = () => open(j.from_case); line.append(t, document.createTextNode(`${short(j.detector)}${j.by ? ` · by ${who(j.by)}` : ''}${j.at ? ` at ${hhmm(j.at)}` : ''}`)); }
    else if (j.rule === 'added') line.append(el('span', 'tag', 'ADDED'), document.createTextNode(`${short(j.detector)}${j.by ? ` · by ${who(j.by)}` : ''}${j.at ? ` at ${hhmm(j.at)}` : ''}`));
    else line.append(document.createTextNode(`${short(j.detector)}: ${relPath(j)}${j.gap_s != null ? ` (${j.gap_s} s after the first signal)` : ''}`));
    w.append(line); });
  return w;
}
function mergeBanners(e) {   // highlighted, like the Close case button: merged away, or alerts added after the brief
  const out = [];
  if (e.merged_into) {
    const bn = el('div', 'banner'); bn.append(el('div', 'h', `Merged into case ${e.merged_into}`),
      el('div', 's', `${e.merged_by ? 'By ' + who(e.merged_by) + (e.merged_at ? ' at ' + hhmm(e.merged_at) : '') + '. ' : ''}This case is closed; its alerts are now investigated in ${e.merged_into}. The brief below is this case's own, from before the merge.`));
    const go = el('button', null, `Open ${e.merged_into}`); go.onclick = () => open(e.merged_into); bn.append(go); out.push(bn);
  }
  const un = e.unreviewed_alerts || [];
  if (un.length && e.state !== 'closed') {
    const bn = el('div', 'banner warn'); bn.append(el('div', 'h', `${un.length} alert${un.length > 1 ? 's' : ''} merged in after this brief was written`),
      el('div', 's', `${un.map(short).join(' + ')}. The root cause and action below do not consider ${un.length > 1 ? 'them' : 'it'} yet.`));
    const rr = el('button', null, 'Re-run RCA with all alerts'); rr.onclick = async () => { if (!(await confirmRerun('all alerts of this case'))) return; rr.disabled = true;
      api('/api/rerun', { case_id: e.case_id }).then(r => { if (r.case_id) { open(r.case_id); loadSide(); } else { rr.disabled = false; toast(r.error, true); } }); };
    bn.append(rr); out.push(bn);
  }
  return out;
}
const relText = (rel, other) => rel === 'same_service' ? `Same service as ${other}` : rel === 'likely_cause_of' ? `This case may be the cause of ${other}` : `This case may be a symptom of ${other}`;
async function loadTies(cid, slot) {   // fetched when shown, so case states and firing alerts are current
  const v = await api(`/api/ties/${encodeURIComponent(cid)}`); slot.replaceChildren(); if (v.error) return;
  if (!(v.cases || []).length && !(v.alerts || []).length) return;
  slot.classList.add('ties'); slot.append(el('div', 'head', 'Possible ties (service map) — not merged'));
  const card = (lines, buttons) => { const r = el('div', 'item'); lines.forEach(([cls, t]) => { const n = el('div', cls, t); if (!cls) n.style.fontWeight = '600'; r.append(n); }); const f = el('div', 'foot'); buttons.forEach(b => f.append(b)); r.append(f); slot.append(r); return r; };
  const btn = (label, cls, fn) => { const b = el('button', cls, label); b.type = 'button'; b.onclick = fn; return b; };
  (v.alerts || []).forEach(a => {
    let add; const r = card([[null, `${relText(a.relation, 'an open alert with no case')}: ${short(a.detector)}`],
      ['s', `${(a.path || []).join(' → ')} · firing since ${String(a.since || '').replace('T', ' ').slice(0, 16)} UTC`]], [
      btn('Triage separately', null, () => start({ incident_id: a.incident_id })),
      add = btn('Add to this case', 'go', async () => { add.disabled = true; const x = await api('/api/tie/attach', { case_id: cid, incident_id: a.incident_id });
        if (x.error) { toast(x.error, true); add.disabled = false; return; } toast(`Added ${short(a.detector)} to ${cid}. ${x.note || ''}`); refreshCase(cid); loadSide(); })]);
  });
  (v.cases || []).forEach(t => {
    const g = Number(t.gap_s) || 0; let m, d;
    const r = card([[null, `${relText(t.relation, 'case ' + t.case_id)}: ${(t.detectors || []).map(short).join(' + ')}`],
      ['s', `case ${String(t.state || '').replace(/_/g, ' ')} · alert ${t.alert_firing ? 'still firing' : 'cleared'} · ${(t.path || []).join(' → ')} · opened ${Math.abs(g)} s ${g >= 0 ? 'before' : 'after'} this case`]], [
      btn('Open', null, () => open(t.case_id)),
      d = btn('Not related', 'reject', async () => { m.disabled = d.disabled = true; const x = await api('/api/tie/dismiss', { case_id: cid, other_case_id: t.case_id });
        if (x.error) { toast(x.error, true); m.disabled = d.disabled = false; return; } toast(`Tie to ${t.case_id} dismissed`); r.remove(); loadSide(); }),
      m = btn('Merge into this case', 'go', async () => { m.disabled = d.disabled = true; const x = await api('/api/tie/merge', { case_id: cid, other_case_id: t.case_id });
        if (x.error) { toast(x.error, true); m.disabled = d.disabled = false; return; } toast(`Merged ${t.case_id} into ${cid}. ${x.note || ''}`); refreshCase(cid); loadSide(); })]);
  });
}

const STATUS_LABEL = { validated: 'Validated', invalidated: 'Ruled out', inconclusive: 'Inconclusive', 'not tested': 'Not tested', open: 'Testing…' };
const stKey = (s) => String(s || 'inconclusive').replace(' ', '');
const nb = (t) => String(t || '').replace(/-/g, '‑');   // service names never break at a hyphen
const firstSentence = (t) => String(t || '').split(/(?<=\.)\s/)[0];
const restSentences = (t) => String(t || '').split(/(?<=\.)\s/).slice(1).join(' ');
const PANES = [['pane-tree', 'Hypothesis tree'], ['pane-topo', 'Topology'], ['trace', 'Agent trace']];
let briefData = null, tabPicked = false, briefCase = null, topoGraph = null, lastStatus = {}, run = null;
let tree = { nodes: [], alert: null, evidence: [], method: null, selected: null };
function setTab(id) { PANES.forEach(([x]) => { $('#' + x).hidden = x !== id; }); $('#vt').querySelectorAll('button').forEach(b => b.setAttribute('aria-selected', String(b.dataset.pane === id))); }
PANES.forEach(([id, label]) => { const b = el('button', null, label); b.type = 'button'; b.dataset.pane = id; b.setAttribute('role', 'tab'); b.onclick = () => { tabPicked = true; setTab(id); }; $('#vt').insertBefore(b, $('#vt').querySelector('.sp')); });
function treeUpsert(n) { const i = tree.nodes.findIndex(x => x.id === n.id); if (i < 0) tree.nodes.push(n); else tree.nodes[i] = Object.assign(tree.nodes[i], n); tree.method = 'tree'; drawTree(); }
function rootNode(nodes) {   // the deepest validated node; a fault marked independent is not this alert's root cause
  const v = nodes.filter(n => n.status === 'validated'); const main = v.filter(n => !n.independent); const pick = main.length ? main : v;
  return pick.sort((a, b) => (b.depth || 1) - (a.depth || 1))[0] || null;
}
function treeCard(n, isRoot) {
  const d = el('div', 'node ' + stKey(n.status) + (isRoot ? ' root' : '')); const nh = el('div', 'nh'); nh.append(el('span', 'id', n.id));
  if (isRoot) nh.append(el('span', 'pill rc', 'Root cause')); nh.append(el('span', 'pill ' + stKey(n.status), STATUS_LABEL[n.status] || n.status || '?'), el('span', 'sp'));
  if (n.tool_calls) nh.append(el('span', null, `${n.tool_calls} tool call${n.tool_calls > 1 ? 's' : ''} · ${n.seconds} s`));
  d.append(nh, el('div', null, n.statement)); if (n.finding) d.append(el('div', 'fd', n.finding));
  (n.checks || []).forEach(c => { const good = /^corroborated/.test(c); const k = el('div', 'ck ' + (good ? 'good' : 'bad')); const m = el('b', null, good ? '' : '! '); if (good) m.append(ic('check'), ' '); k.append(m, 'Code check: ' + c); d.append(k); });
  const ev = (n.evidence || []).length ? n.evidence : (n.evidence_ids || []).map(id => tree.evidence.find(x => x.evidence_id === id) || { signal: 'source', finding: id });
  ev.forEach(v => { const r = el('div', 'evd'); r.append(el('span', 'sig', v.signal || 'evidence'), el('span', null, v.finding || v.evidence_id || '')); d.append(r); });
  return d;
}
function drawTree() {
  const P = $('#tree'), L = $('#legend'), D = $('#detail'), N = $('#treenote'); P.replaceChildren(); L.replaceChildren(); D.replaceChildren(); N.textContent = '';
  if (!tree.nodes.length) { P.append(el('div', 'empty', current ? 'The hypotheses appear here when the agent has written them. Follow the live steps under Agent trace.' : 'Open a case or press Triage on an alert to see its hypothesis tree.')); return; }
  const ids = new Set(tree.nodes.map(n => n.id)), kids = {}; tree.nodes.forEach(n => { const p = ids.has(n.parent) ? n.parent : ''; (kids[p] = kids[p] || []).push(n); });
  const root = rootNode(tree.nodes.slice()), path = new Set(); for (let n = root; n; n = tree.nodes.find(x => x.id === n.parent)) path.add(n.id);
  const leaves = tree.nodes.filter(n => !kids[n.id]).length, w = ($('#vt').clientWidth || 800) - 16;
  P.style.setProperty('--bw', Math.max(124, Math.min(240, Math.floor(w / Math.max(leaves, 1)) - 8)) + 'px');
  if (tree.method !== 'tree') N.textContent = 'This case ran the single-loop method, so its hypotheses are one level deep. SRE_AGENT_METHOD=tree adds sub-hypotheses.';
  const line = el('span'), li_ = el('i'); li_.className = 'line'; line.append(li_, 'path to the root cause'); if (root) L.append(line);
  Object.keys(STATUS_LABEL).forEach(k => { const c = tree.nodes.filter(n => (n.status || 'inconclusive') === k).length; if (c) { const s = el('span'); s.append(el('span', 'pill ' + stKey(k), STATUS_LABEL[k]), ` ${c}`); L.append(s); } });
  const show = (n, b) => { P.querySelectorAll('.bx').forEach(x => x.setAttribute('aria-pressed', String(x === b))); tree.selected = n.id; D.replaceChildren(el('div', 'lab', `Selected · ${n.id}`), treeCard(n, root && n.id === root.id)); };
  let pick = null; const want = tree.selected && ids.has(tree.selected) ? tree.selected : root ? root.id : tree.nodes[0].id;
  const box = (n) => {
    const isRoot = root && n.id === root.id, b = el('button', 'bx ' + stKey(n.status) + (isRoot ? ' root' : '')); b.type = 'button'; b.title = n.statement; const k = el('div', 'k');
    k.append(el('span', 'dot ' + ({ validated: 'good', inconclusive: 'warn' }[n.status] || '')), el('span', 'id', n.id)); if (isRoot) k.append(el('span', 'rc', 'ROOT CAUSE')); else k.append(el('span', null, STATUS_LABEL[n.status] || n.status || '?'));
    b.append(k, el('div', 'tt', nb(firstSentence(n.statement)))); if (n.tool_calls) b.append(el('div', 'm', `${n.tool_calls} call${n.tool_calls > 1 ? 's' : ''} · ${n.seconds} s`));
    b.setAttribute('aria-pressed', 'false'); b.onclick = () => show(n, b); if (n.id === want) pick = [n, b];
    const li = el('li', path.has(n.id) && (ids.has(n.parent) ? path.has(n.parent) : true) ? 'path' : null); li.append(b);
    if (kids[n.id]) { const ul = el('ul', path.has(n.id) && kids[n.id].some(c => path.has(c.id)) ? 'path' : null); kids[n.id].forEach(c => ul.append(box(c))); li.append(ul); }
    return li;
  };
  const al = el('button', 'bx alert'); al.type = 'button'; const a = tree.alert || {}; const ak = el('div', 'k'); ak.append(el('span', 'dot bad'), el('span', null, `Alert${a.since ? ' · ' + a.since : ''}`)); al.append(ak, el('div', 'tt', nb(a.title || 'Case ' + current)));
  if (a.more) al.append(el('div', 'm', `+ ${a.more} grouped alert${a.more > 1 ? 's' : ''}`)); al.title = a.all || '';
  const ul = el('ul', root ? 'path' : null); (kids[''] || []).forEach(n => ul.append(box(n))); const top = el('li'); top.append(al, ul); const tu = el('ul'); tu.append(top); P.append(tu);
  if (pick) show(...pick);
}
function setAlert(detectors, since) { const ds = [...new Set((detectors || []).map(short))]; if (ds.length) tree.alert = { title: ds[0], more: ds.length - 1, all: ds.join(' + '), since: hhmm(since) }; }
function drawTopology(e) {   // caller → callee tree from the service map; status only from this case's own data
  const P = $('#topo'), L = $('#tlegend'), D = $('#tdetail'), N = $('#toponote'); P.replaceChildren(); L.replaceChildren(); D.replaceChildren(); N.textContent = '';
  if (!e) { P.append(el('div', 'empty', 'Open a case to see the services around it.')); return; }
  if (!topoGraph) { P.append(el('div', 'empty', 'Loading the service map…')); return; }
  if (topoGraph.error) { P.append(el('div', 'empty err', 'Could not load the service map: ' + topoGraph.error)); return; }
  const edges = topoGraph.edges || {}, names = new Set(Object.keys(edges)); Object.values(edges).forEach(v => v.forEach(x => names.add(x)));
  const rc = e.root_cause_service, alerting = [...names].filter(n => (e.detectors || []).some(d => short(d).includes(n)));
  const focus = new Set(alerting); if (names.has(rc)) focus.add(rc);
  const callers = (n) => [...names].filter(a => (edges[a] || []).includes(n));
  const tops = new Set(), climb = (n, seen) => { if (seen.has(n)) return; seen.add(n); const c = callers(n); if (!c.length) tops.add(n); c.forEach(x => climb(x, seen)); };
  focus.forEach(n => climb(n, new Set())); if (!tops.size) [...names].filter(n => !callers(n).length).forEach(n => tops.add(n));
  const find = (a, b) => { const q = [[a]], s = new Set([a]); while (q.length) { const p = q.shift(), h = p[p.length - 1]; if (h === b) return p; (edges[h] || []).forEach(x => { if (!s.has(x)) { s.add(x); q.push(p.concat(x)); } }); } return null; };
  const path = new Set(); alerting.forEach(a => { if (names.has(rc)) (find(a, rc) || []).forEach(x => path.add(x)); });
  const notes = (n) => [...(e.evidence || []).map(v => v.finding), ...(e.ruled_out || [])].filter(t => String(t).includes(n));
  const ruled = (n) => (e.ruled_out || []).some(t => String(t).includes(n));
  const stOf = (n) => n === rc ? 'root' : alerting.includes(n) ? 'alert' : (lastStatus.unhealthy || []).includes(n) ? 'warn' : ruled(n) ? 'ok' : notes(n).length ? 'seen' : 'na';
  const LABEL = { root: 'Faulty', alert: 'Alerting', warn: 'Unhealthy', ok: 'Ruled out', seen: 'In evidence', na: 'No evidence' }, DOT = { root: 'bad', alert: 'bad', warn: 'warn', ok: 'good' };
  N.textContent = topoGraph.source === 'static' ? 'Service map recorded on EKS (Amazon Elastic Kubernetes Service); the live map has not loaded.' : 'Live APM (Application Performance Monitoring) service map.';
  if (path.size > 1) { const line = el('span'); const i = el('i'); i.className = 'line'; line.append(i, 'agent path: alerting service → root cause'); L.append(line); }
  const used = new Set(); const seen = new Set(); let pick = null;
  const show = (n, b) => { P.querySelectorAll('.bx').forEach(x => x.setAttribute('aria-pressed', String(x === b))); const t = notes(n);
    D.replaceChildren(el('div', 'lab', `Selected · ${n} · ${LABEL[stOf(n)]}`), ...(t.length ? t.map(x => el('p', null, x)) : [el('p', 'plain', 'This case has no evidence about this service.')])); };
  const box = (n, parent) => { seen.add(n); const st = stOf(n); used.add(st); const isRoot = n === rc, b = el('button', 'bx ' + (st === 'root' ? 'svc-root' : st === 'alert' ? 'svc-alert' : st === 'warn' ? 'svc-warn' : st === 'ok' ? 'svc-ok' : 'svc-na') + (isRoot ? ' root' : '')); b.type = 'button'; b.title = (notes(n)[0] || n);
    const k = el('div', 'k'); k.append(el('span', 'dot ' + (DOT[st] || '')), el('span', null, LABEL[st])); if (isRoot) k.append(el('span', 'rc', 'ROOT CAUSE')); b.append(k, el('div', 'tt', nb(n))); b.setAttribute('aria-pressed', 'false'); b.onclick = () => show(n, b); if (isRoot || (!pick && alerting.includes(n))) pick = [n, b];
    const li = el('li', path.has(n) && parent && path.has(parent) ? 'path' : null); li.append(b); const ks = (edges[n] || []).filter(x => !seen.has(x));
    if (ks.length) { const ul = el('ul', path.has(n) && ks.some(x => path.has(x)) ? 'path' : null); ks.forEach(x => ul.append(box(x, n))); li.append(ul); } return li; };
  const tu = el('ul'); [...tops].sort().forEach(n => tu.append(box(n, null))); P.append(tu);
  Object.keys(LABEL).filter(k => used.has(k)).forEach(k => { const s = el('span'); s.append(el('span', 'dot ' + (DOT[k] || '')), ' ' + LABEL[k]); s.style.whiteSpace = 'nowrap'; L.append(s); });
  if (pick) show(...pick);
}
function setRun(r) { run = r; const t = $('#runtile'); if (t) t.replaceWith(runTile()); const s = $('#runstate'); if (s) s.textContent = r && r.seconds != null ? `done in ${Math.round(r.seconds)} s` : ''; }
function fmtK(n) { n = Number(n) || 0; return n >= 1000 ? (n / 1000).toFixed(1) + 'k' : String(n); }
function runTile() { const t = run ? tile('Agent run · this case', `${Math.round(run.seconds || 0)} s · $${Number(run.cost || 0).toFixed(2)}`, `${fmtK(run.tokens)} tokens · ${run.calls} tool calls`) : tile('Agent run · this case', '–', 'no finished run open'); t.id = 'runtile'; if (run) t.title = 'Model: ' + mdl(run.model); return t; }

function render(e) {
  if (REFRESH_ON.has(e.event) && e.case_id === current) refreshSoon(current);
  switch (e.event) {
    case 'sre.tree.branch': treeUpsert({ id: e.node, parent: e.parent, depth: e.depth, statement: e.statement, status: 'open' }); return row(e, plain(`Hypothesis ${e.node}: ${e.statement}`));
    case 'sre.tree.verdict': treeUpsert({ id: e.node, parent: e.parent, depth: e.depth, statement: e.statement, status: e.status, checks: e.checks, finding: e.finding, evidence: e.evidence, tool_calls: e.tool_calls, seconds: e.seconds }); return row(e, plain(`Hypothesis ${e.node}: ${STATUS_LABEL[e.status] || e.status}${e.finding ? ' — ' + e.finding : ''}`));
    case 'sre.case.opened': setAlert(e.detectors); drawTree(); return row(e, plain(`Case ${e.case_id} opened for ${(e.detectors || []).map(short).join(' + ')}`));
    case 'sre.case.incident_attached': return row(e, plain(`Added ${short(e.detector)} to case ${e.case_id}: ${relPath(e)} (${e.gap_s} s after it opened)`));
    case 'sre.case.tie_suggested': return row(e, plain(`Possible tie: this case ${REL[e.relation] || e.relation} ${e.other_case} (${(e.other_detectors || []).map(short).join(' + ')}) via ${(e.path || []).join(' → ')}`));
    case 'sre.case.incident_added': return row(e, plain(`Added ${short(e.detector)} to case ${e.case_id} (by ${e.by})`));
    case 'sre.case.merged': return row(e, plain(`Case ${e.merged_case} merged into ${e.case_id} by ${who(e.by)}`));
    case 'sre.case.merged_away': return row(e, plain(`This case was merged into ${e.into} by ${who(e.by)}`));
    case 'sre.case.tie_dismissed': return row(e, plain(`Tie with ${e.other_case} marked not related by ${who(e.by)}`));
    case 'sre.console.starting': setRunning(true); return row(e, plain('Connecting to Observability Cloud and Splunk Enterprise…'));
    case 'sre.case.investigating': setRunning(true); return row(e, plain('Collecting evidence by code before the model sees anything…'));
    case 'sre.mcp.call': {
      calls[e.server] = (calls[e.server] || 0) + 1;
      const d = el('details'); const s = el('summary'); const m = el('span', 'mcp');
      m.append(el('span', 'srv', e.server === 'splunk-mcp-server' ? 'splunk: ' : e.server === 'splunk-rest' ? 'splunk-rest: ' : 'o11y: '), document.createTextNode(e.tool + ' '),
        (() => { const t = el('span', 'ms' + (e.ok ? '' : ' bad')); t.append(ic(e.ok ? 'check' : 'x'), ` ${e.ms} ms`); return t; })());
      s.append(m); d.append(s, el('pre', null, (e.params || '') + (e.error ? '\n\nerror: ' + e.error : '')));
      return row(e, d);
    }
    case 'sre.rca.evidence': return row(e, details(`evidence ready: ${String(e.section).replace(/_/g, ' ')} — ${e.summary}`, e.preview));
    case 'sre.rca.step': {
      if (e.stop_reason === 'evidence_check') return row(e, box('act', 'evidence check by code', [rich(e.reasoning || 'The answer lacked a metric/trace or log signal; one more round requested.')]));
      const nodes = [];
      if (e.reasoning) nodes.push(rich(e.reasoning));
      if (e.text) nodes.push(el('div', null, e.text));
      (e.tool_calls || []).forEach(c => { const w = el('div', 'why'); w.append(el('b', null, 'Next: '), document.createTextNode((c.args && c.args.why) || c.tool)); nodes.push(w); });
      if (!nodes.length) nodes.push(plain(e.chat ? 'Writing the answer…' : 'Writing the conclusion…'));
      return row(e, box('think', `${mdl(e.model)} · step ${e.step}${e.reasoning ? ' · reasoning summary' : ''}`, nodes));
    }
    case 'sre.rca.tool': {
      const args = Object.entries(e.args || {}).filter(([k]) => k !== 'why').map(([k, v]) => `${k}=${typeof v === 'string' ? v : JSON.stringify(v)}`).join(', ');
      return row(e, details(`${e.ok ? 'ok' : 'failed'}: ${e.tool}(${args}) → ${e.summary}`, e.preview));
    }
    case 'sre.case.escalated_model': return row(e, box('act', 'escalation', [`First answer was weak (${e.reason}); re-investigating the same evidence with ${e.to_model}.`]));
    case 'sre.case.investigated': {
      renderBrief(e, null);
      setRun({ seconds: e.seconds, cost: e.cost_usd, tokens: (Number(e.input_tokens) || 0) + (Number(e.output_tokens) || 0) + (Number(e.cache_read_tokens) || 0), calls: Object.values(calls).reduce((a, b) => a + b, 0), model: e.model });
      const tok = (Number(e.input_tokens) || 0) + (Number(e.output_tokens) || 0) + (Number(e.cache_read_tokens) || 0);
      const n = Object.values(calls).reduce((a, b) => a + b, 0);
      return row(e, box('done', 'brief submitted', [`Done: ${n} MCP calls (Observability Cloud ${calls['o11y-mcp-gateway']}, Splunk ${calls['splunk-mcp-server'] + calls['splunk-rest']}), ${tok.toLocaleString()} LLM tokens, $${Number(e.cost_usd || 0).toFixed(4)}, ${e.seconds}s · ${mdl(e.model)}`]));
    }
    case 'remediation.proposed': renderAction(e); return row(e, plain(`Proposed ${e.action} — policy: ${e.requirement}. See the brief →`));
    case 'approval.decided': decided(e.decision); status(`${e.decision === 'approve' ? 'Approved' : 'Rejected'} by ${e.approver}`); return row(e, plain(`${e.decision === 'approve' ? 'Approved' : 'Rejected'} by ${e.approver}`));
    case 'remediation.executing': status('Executor re-checking state, then acting…'); return row(e, plain('Executor re-checking state, then acting…'));
    case 'remediation.refused': status('Executor refused: ' + e.reason, 'bad'); return row(e, box('err', 'executor', ['Refused: ' + e.reason]));
    case 'remediation.state': return row(e, plain(`State before ${JSON.stringify(e.pre_state)} → after ${JSON.stringify(e.post_state)}`));
    case 'remediation.executed': status(`Action ${e.executed ? 'executed' : 'NOT executed'}`, e.executed ? '' : 'bad'); return row(e, plain(`Action ${e.executed ? 'executed' : 'NOT executed'}`));
    case 'remediation.verified': status(e.outcome_ok ? `Verified by the fixed query (last value ${e.value})` : `Not verified (last value ${e.value}); escalated to a human`, e.outcome_ok ? 'good' : 'bad');
      return row(e, box(e.outcome_ok ? 'done' : 'err', 'verification', [e.outcome_ok ? `Verified (last value ${e.value}).` : `Not verified (last value ${e.value}).`]));
    case 'sre.case.mitigated_awaiting_clear': status('Mitigated — waiting for the detector to clear on its own', 'good'); return row(e, plain('Mitigated — waiting for the detector to clear.'));
    case 'sre.case.escalated': if (!briefShown) renderEnd('Escalated to a human: no answer', [].concat(e.reason || 'escalated').join('; ')); status('Escalated to a human: ' + [].concat(e.reason || '').join('; '), 'bad'); return row(e, box('err', 'escalated', [[].concat(e.reason || 'escalated to a human').join('; ')]));
    case 'sre.audit.write_failed': return row(e, box('err', 'audit', [`Audit record ${e.lost_event} did not reach index ${e.index}: ${e.error} (${e.failures_total} lost so far)`]));
    case 'sre.case.inconclusive': if (!briefShown) renderEnd('Inconclusive: no answer', [].concat(e.reason || 'the investigation did not reach a conclusion').join('; '));
      return row(e, box('act', null, ['Inconclusive: the evidence above is for a human.']));
    case 'sre.case.stop_requested': return row(e, plain(`Stop requested by ${e.by}: waiting for the current call to return…`));
    case 'sre.case.stopped': setRunning(false);
      renderEnd('Stopped by the operator', `Stopped by ${e.by} during ${e.stage}, after ${e.model_calls} model call(s), $${Number(e.cost_usd || 0).toFixed(4)} spent. Nothing was proposed or executed.`, 'closed');
      return row(e, box('err', 'stopped', [`Stopped by ${e.by} during ${e.stage}. ${e.model_calls} model call(s), $${Number(e.cost_usd || 0).toFixed(4)} spent; nothing proposed or executed.`]));
    case 'sre.case.escalation_failed': return row(e, box('act', 'escalation failed', [`The re-run with ${mdl(e.to_model)} failed (${e.error}). Keeping the first answer from ${mdl(e.kept_model)}.`]));
    case 'sre.llm.retry': return row(e, plain(`The model API refused the request (${e.error}); retrying once in ${e.after_s}s…`));
    case 'sre.case.closed': return row(e, plain(`Case closed${e.reason ? ': ' + String(e.reason).slice(0, 160) : ''}`));
    case 'sre.case.paged': status(`Paged ${e.team} (simulated)`); return row(e, box('act', 'page', [`${e.by} paged ${e.team}. ${e.note}`]));
    case 'sre.case.acknowledged': return row(e, plain(`Acknowledged by ${e.by}: ${e.note}`));
    case 'sre.case.rerun_requested': return row(e, plain(`Re-run requested by ${e.by} — a new case was opened`));
    case 'sre.chat.question': setRunning(true); return row(e, box('user', e.by, [e.question]));
    case 'sre.chat.done': setRunning(false); return;
    case 'sre.chat.answer': return row(e, box('done', `${mdl(e.model)} · $${Number(e.cost_usd || 0).toFixed(4)}`, [rich(e.answer)]));
    case 'sre.console.error': return row(e, box('err', 'error', [e.error]));
    case 'sre.console.done': setRunning(false); loadSide();
      if (!briefShown && e.state && e.state !== 'investigating') renderEnd(`Case ended: ${String(e.state).replace(/_/g, ' ')}`, 'The investigation ended without a brief; the reasoning pane shows how far it got.');
      return;
    case 'sre.console.history': return renderHistory(e);
  }
}

function list(label, items, fill) { if (!(items || []).length) return null; const w = el('div'); w.append(el('div', 'lab', label)); const ul = el('ul'); items.forEach(x => { const li = el('li'); fill(li, x); ul.append(li); }); w.append(ul); return w; }
function renderEnd(title, reason, state) {   // the case ended without an investigation result: say so instead of "Investigating…"
  briefShown = true; const b = $('#brief'); b.replaceChildren();
  b.append(el('span', 'cat', 'NO BRIEF'), el('h3', null, title));
  const r = el('div', null, reason); r.style.color = 'var(--warn)'; b.append(r);
  b.append(plain('The evidence collected so far is in the reasoning pane. Re-run the RCA (root cause analysis) for a fresh investigation, or page the owning team.'));
  b.append(caseActions(current, null, { state }));
  const st = el('div', 'lab'); st.id = 'execstatus'; b.append(st); paintStatus();
}
function renderBrief(e, pageTeam) {
  briefShown = true; const b = $('#brief'); b.replaceChildren();
  if (briefCase !== e.case_id) { briefCase = e.case_id; tree.selected = null; }
  tree.evidence = e.evidence || []; setAlert(e.detectors, e.incidents_since); briefData = e;
  if ((e.tree || []).length) { tree.nodes = e.tree; tree.method = 'tree'; }
  else if (tree.method !== 'tree') { tree.nodes = (e.hypotheses || []).map((h, i) => Object.assign({ id: 'H' + (i + 1), parent: null, depth: 1 }, h)); tree.method = 'loop'; }
  drawTree(); drawTopology(e); if (!tabPicked) setTab('pane-tree');
  mergeBanners(e).forEach(x => b.append(x));
  const dbox = el('div', 'decide'); dbox.id = 'decidebox'; const slot = el('div'); slot.id = 'actionslot'; dbox.append(slot); b.append(dbox);
  const pa = (e.proposed_action && e.proposed_action.type) || e.proposed_action || 'inconclusive';
  renderAction({ case_id: e.case_id, action: pa, requirement: pa === 'no_action' ? 'none' : pa === 'inconclusive' ? 'none' : 'pending', tier: '–' }, true);
  dbox.append(caseActions(e.case_id, e.page_team || pageTeam, e));
  const st = el('div', 'plain'); st.id = 'execstatus'; st.style.marginTop = '8px'; dbox.append(st);
  const sum = e.summary || `${e.root_cause_service} · ${String(e.failure_mode || '').replace(/_/g, ' ')}`;
  b.append(el('h3', null, nb(firstSentence(sum))));
  const facts = el('div', 'facts'); const fact = (k, v) => { if (!v) return; const s = el('span'); s.append(k, typeof v === 'string' ? el('b', null, v) : v); facts.append(s); };
  fact('Root cause', nb(e.root_cause_service)); fact('Mode', String(e.failure_mode || '').replace(/_/g, ' '));
  if (e.confidence != null) { const pc = Math.round(Number(e.confidence) * 100), c = el('div', 'conf'), bar = el('div', 'bar'), i = el('i'); i.style.width = pc + '%'; bar.append(i); c.append(bar, el('b', null, pc + '%')); c.setAttribute('aria-label', `Confidence ${pc} percent`); fact('Confidence', c); }
  fact('Started', e.started_at ? hhmm(e.started_at) || e.started_at : ''); fact('Page team', nb(e.page_team || pageTeam));
  const tr = (e.evidence || []).map(v => /trace ([0-9a-f]{8,32})/i.exec(v.finding || '')).find(Boolean);
  if (tr) { let v = tr[1]; if (v.length >= 16) { const a = el('a', null, v.slice(0, 8) + ' '); a.append(ic('external')); a.href = 'https://app.us1.signalfx.com/#/apm/traces/' + v; a.target = '_blank'; a.rel = 'noopener'; v = a; } fact('Trace', v); }
  b.append(facts);
  const more = restSentences(sum); if (more) b.append(el('p', null, more));
  if (e.impact) b.append(el('div', 'lab', 'Customer impact'), el('p', null, e.impact));
  if ((e.cause_chain || []).length) { b.append(el('div', 'lab', 'Cause chain · root cause → alert')); const ol = el('ol', 'chain'); e.cause_chain.forEach(x => ol.append(el('li', null, x))); b.append(ol); }
  if ((e.evidence || []).length) { b.append(el('div', 'lab', 'Evidence')); e.evidence.forEach(v => { const r = el('div', 'evd'); r.append(el('span', 'sig', v.signal), el('span', null, v.finding)); b.append(r); }); }
  if ((e.ruled_out || []).length) { const d = el('details'); d.append(el('summary', null, `Ruled out (${e.ruled_out.length})`)); const ul = el('ul'); e.ruled_out.forEach(x => ul.append(el('li', null, x))); d.append(ul); b.append(d); }
  const kv = el('div', 'kv'); const add = (k, v) => { if (v) kv.append(el('div', 'k', k), typeof v === 'string' ? el('div', null, v) : v); };
  add('Trigger', (e.detectors || []).map(short).join(' + ')); add('Grouped', groupedNode(e.incidents_joined));
  add('Check next', ((e.topology || {}).check_next || []).slice(0, 3).map(x => `${x.service} (${x.path.join(' → ')}), silent`).join('; ')); b.append(kv);
  const tslot = el('div'); b.append(tslot); if (e.case_id) loadTies(e.case_id, tslot);
  if (e.evidence_gap) { const g = el('p', null, 'Evidence gap: ' + e.evidence_gap); g.style.color = 'var(--warn)'; b.append(g); }
  if (e.escalation_error) { const g = el('p', null, 'Escalation: ' + e.escalation_error); g.style.color = 'var(--warn)'; b.append(g); }
  if (e.narrative) b.append(details('Full narrative', e.narrative));
  const fb = el('div', 'fb'); fb.append('Was the root cause right?');
  [['Yes', 'right'], ['No', 'wrong']].forEach(([label, verdict]) => { const x = el('button', null, label); x.type = 'button'; x.onclick = () => { fb.querySelectorAll('button').forEach(y => { y.disabled = true; }); api('/api/feedback', { case_id: e.case_id, verdict }).then(r => { if (r.error) { toast(r.error, true); fb.querySelectorAll('button').forEach(y => { y.disabled = false; }); } else toast('Recorded in the audit trail'); }); }; fb.append(x); });
  b.append(fb); paintStatus();
}
let toastTimer = null;
function toast(text, bad) { const t = $('#toast'); t.textContent = text; t.className = 'show' + (bad ? ' bad' : ''); clearTimeout(toastTimer); toastTimer = setTimeout(() => { t.className = bad ? 'bad' : ''; }, bad ? 7000 : 3500); }
function modal({ title, body, ok = 'OK', danger = false, reasons = null }) {   // in-page dialog; resolves to the reason text, true, or null (cancel)
  return new Promise(resolve => {
    const d = el('dialog', 'modal'); d.append(el('h4', null, title));
    (Array.isArray(body) ? body : [body]).forEach(x => { if (x) d.append(typeof x === 'string' ? el('p', 'msg', x) : x); });
    let ta = null;
    if (reasons) {
      d.append(el('label', null, 'Reason (kept in the audit trail)'));
      const q = el('div', 'quick');
      reasons.forEach(r => { const b = el('button', null, r); b.type = 'button'; b.onclick = () => { ta.value = r; q.querySelectorAll('button').forEach(x => x.classList.toggle('on', x === b)); ta.focus(); }; q.append(b); });
      ta = el('textarea'); ta.placeholder = 'Why is this case being closed?'; d.append(q, ta);
    }
    const foot = el('div', 'foot'); const no = el('button', 'reject', 'Cancel'); const yes = el('button', 'go' + (danger ? ' danger' : ''), ok);
    no.type = yes.type = 'button'; foot.append(no, yes); d.append(foot);
    const done = (v) => { d.close(); d.remove(); resolve(v); };
    no.onclick = () => done(null); d.addEventListener('cancel', (ev) => { ev.preventDefault(); done(null); });
    yes.onclick = () => { if (ta && !ta.value.trim()) { ta.focus(); ta.style.borderColor = 'var(--warn)'; return; } done(ta ? ta.value.trim() : true); };
    if (ta) ta.addEventListener('keydown', (ev) => { if (ev.key === 'Enter' && (ev.metaKey || ev.ctrlKey)) yes.click(); });
    document.body.append(d); d.showModal(); (ta || yes).focus();
  });
}
const CLOSE_REASONS = ['stale alert', 'false positive', 'duplicate of another case', 'fixed outside the agent', 'demo / test case'];
async function closeCase(cid, btn) {
  const msg = el('p', 'msg'); msg.append('Case ', el('b', null, cid), ' will be closed. If it has a proposed action waiting for approval, that action is rejected and recorded as rejected.');
  const reason = await modal({ title: 'Close case', body: msg, ok: 'Close case', danger: true, reasons: CLOSE_REASONS });
  if (reason === null) return;
  if (btn) btn.disabled = true;
  const r = await api('/api/close', { case_id: cid, reason });
  if (r.error) { toast(r.error, true); if (btn) btn.disabled = false; return; }
  toast(`Case ${cid} closed: ${reason}`); if (cid === current) status(`Case closed (${reason})`); loadSide();
}
async function confirmRerun(what) {
  return modal({ title: 'Re-run the investigation', body: [`A fresh investigation of ${what} starts now; the earlier case stays as it is.`, 'It uses the model (typically $0.05–0.40) and takes about a minute.'], ok: 'Re-run RCA' });
}
const CLOSABLE = ['proposed', 'awaiting_approval', 'inconclusive', 'escalated', 'verification_failed', 'mitigated_awaiting_clear', 'resolved'];
function caseActions(cid, team, e) {
  const w = el('div', 'btns minor');
  const mk = (label, cls, fn) => { const x = el('button', cls, label); x.type = 'button'; x.onclick = () => fn(x); w.append(x); return x; };
  mk(`Page ${team || 'on-call'}`, null, (x) => { x.disabled = true; api('/api/page', { case_id: cid }).then(r => { status(r.ok ? `Paged ${r.team} (simulated — no paging integration connected; recorded in the audit trail)` : r.error); }); });
  mk('Re-run RCA', null, async (x) => { if (!(await confirmRerun('this alert'))) return; x.disabled = true;
    api('/api/rerun', { case_id: cid }).then(r => { if (r.case_id) { open(r.case_id); loadSide(); } else { x.disabled = false; toast(r.error, true); } }); });
  if (!e || e.state !== 'closed') mk('Close case', null, (x) => closeCase(cid, x));
  mk('Copy brief', null, () => { const txt = $('#brief').innerText; (navigator.clipboard ? navigator.clipboard.writeText(txt) : Promise.reject()).then(() => status('Brief copied'), () => status('Copy not available in this browser')); });
  return w;
}
function renderAction(e, placeholder) {
  const slot = $('#actionslot'); if (!slot) return; slot.replaceChildren();
  const box = $('#decidebox'), ask = !placeholder && e.requirement === 'ask'; if (box) box.classList.toggle('live', ask);
  const head = (label, title) => slot.append(el('div', 'l', label), el('div', 'ttl', nb(String(title || '').replace(/^./, c => c.toUpperCase()))));
  if (placeholder) {
    if (e.action === 'no_action') { head('NO ACTION NEEDED', 'Nothing to change in the platform'); slot.append(el('div', 'm', 'Page the owning team, close, or re-run the RCA (root cause analysis) below.')); }
    else if (e.action === 'inconclusive') { head('INCONCLUSIVE', 'No action proposed'); slot.append(el('div', 'm', 'The evidence is in the agent trace. Page the owning team or re-run the RCA.')); }
    else { head('PROPOSED', e.action); slot.append(el('div', 'm', 'Waiting for the policy decision…')); }
    return;
  }
  head(ask ? 'AWAITING YOUR APPROVAL' : e.action === 'no_action' ? 'NO ACTION NEEDED' : `ACTION · ${String(e.requirement || '').replace(/^none \(|\)$/g, '').toUpperCase()}`, e.action === 'no_action' ? 'Notify and close' : (e.real_world || e.action));
  const line = []; if (e.jev) line.push(`Guardrail: ${e.jev === 'allow' ? 'allowed' : e.jev}${e.jev_mode && e.jev_mode !== 'real' ? ' (' + e.jev_mode + ')' : ''}`); if (e.verification) line.push('Checked after: ' + e.verification);
  if (line.length) slot.append(el('div', 'm', line.join(' · ')));
  if (ask) {
    const bt = el('div', 'btns'); const ok = el('button', 'approve', 'Approve'); const no = el('button', null, 'Reject'); ok.type = no.type = 'button';
    ok.onclick = () => { ok.disabled = no.disabled = true; api('/api/approve', { case_id: e.case_id, plan_hash: e.plan_hash }); };
    no.onclick = () => { ok.disabled = no.disabled = true; api('/api/reject', { case_id: e.case_id, reason: 'rejected in the console' }).then(() => { status('Rejected'); loadSide(); }); };
    bt.append(ok, no); slot.append(bt);
  }
  const d = el('details'); d.append(el('summary', null, 'Details'), el('div', 'm', `${e.action} · policy: ${e.requirement === 'ask' ? 'a human must approve' : e.requirement} (tier ${e.tier})`));
  if ([].concat(e.reasons || []).length) d.append(el('div', 'm', 'Policy: ' + [].concat(e.reasons).join('; ')));
  if (e.request && Object.keys(e.request).length && e.action !== 'no_action') d.append(details('Exact request the executor will send', JSON.stringify(e.request, null, 1)));
  slot.append(d);
}
let statusNote = null;   // the last outcome line for the open case; survives a redraw of the brief
function paintStatus() { const s = $('#execstatus'); if (!s || !statusNote || statusNote.cid !== current) return; s.textContent = statusNote.text; s.style.color = statusNote.cls === 'bad' ? 'var(--bad)' : statusNote.cls === 'good' ? 'var(--ok)' : 'var(--mute)'; }
function status(text, cls) { statusNote = { cid: current, text, cls }; paintStatus(); }
function decided(d) {   // the human has answered: the box stops asking at once, the executor's steps follow in the status line
  const b = $('#decidebox'); if (!b) return; b.classList.remove('live'); const l = b.querySelector('.l'); if (l) l.textContent = d === 'approve' ? 'APPROVED · ACTING AND VERIFYING' : 'REJECTED';
  const a = b.querySelector('.approve'); if (a) a.parentElement.remove();
}
function renderHistory(h) {
  const c = h.case; row({ t: Date.parse(c.opened_at) / 1000 }, plain(`Case ${c.id} ran before this console session; showing its stored result. Live steps appear for cases started here.`));
  renderStored(c, h.page_team);
}
// events that change a case after its brief was drawn: redraw the brief from the stored case (no page reload)
const REFRESH_ON = new Set(['sre.case.merged', 'sre.case.merged_away', 'sre.case.incident_added', 'sre.case.incident_attached', 'sre.case.tie_dismissed',
  'sre.case.tie_suggested', 'sre.case.closed', 'sre.case.closed_by_operator', 'sre.case.mitigated_awaiting_clear', 'sre.case.resolved', 'sre.case.verification_failed']);
let refreshTimer = null;
function refreshSoon(cid) { clearTimeout(refreshTimer); refreshTimer = setTimeout(() => { refreshCase(cid); loadSide(); }, 300); }
async function refreshCase(cid) {
  if (!cid || cid !== current) return;
  const c = await api(`/api/case/${encodeURIComponent(cid)}`);
  if (c.error || cid !== current || ['open', 'investigating'].includes(c.state)) return;   // a running investigation draws its own brief
  renderStored(c, c.page_team);
}
function renderStored(c, pageTeam) {
  const inv = c.investigation, st = c.stats;
  if (st) setRun({ seconds: st.seconds, cost: st.cost_usd, tokens: (st.input_tokens || 0) + (st.output_tokens || 0) + (st.cache_read_tokens || 0), calls: (st.bundle_tool_calls || 0) + (st.investigator_tool_calls || 0), model: st.model });
  if (!inv) { const last = (c.history || []).slice(-1)[0] || {}; if (!['open', 'investigating'].includes(c.state)) renderEnd(`Case ${String(c.state).replace(/_/g, ' ')}`, [].concat(last.reason || 'no investigation result was stored').join('; '), c.state); return; }
  renderBrief(Object.assign({}, inv, { case_id: c.id, state: c.state, detectors: (c.incidents || []).map(i => i.detector), ties: Object.values(c.ties || {}), topology: c.topology, incidents_since: (c.incidents || []).map(i => i.since).filter(Boolean).sort()[0], merged_into: c.merged_into, merged_by: c.merged_by, merged_at: c.merged_at,
    unreviewed_alerts: c.unreviewed_alerts !== undefined ? c.unreviewed_alerts : (c.investigation ? (c.incidents || []).filter(i => i.joined && ['merged', 'added'].includes(i.joined.rule)).map(i => i.detector) : []),
    incidents_joined: (c.incidents || []).filter(i => i.joined).map(i => Object.assign({ detector: i.detector }, i.joined)) }), pageTeam);
  const d = c.decision; if (d && d.action) renderAction({ case_id: c.id, action: d.action, real_world: d.real_world, requirement: c.state === 'awaiting_approval' ? d.requirement : `none (${String(c.state).replace(/_/g, ' ')})`,
    tier: d.tier, reasons: d.reasons, verification: (d.verification || {}).description, request: d.request_preview, jev: (d.jev || {}).verdict, jev_mode: (d.jev || {}).mode, plan_hash: d.plan_hash });
}
function open(cid) {
  current = cid; t0 = null; calls = freshCalls(); briefShown = false; setRunning(false);
  tree = { nodes: [], alert: null, evidence: [], method: null, selected: null }; tabPicked = false; briefData = null; setRun(null); setTab('trace'); drawTree(); drawTopology(null);
  $('#trace').replaceChildren(); $('#brief').replaceChildren(el('div', 'empty', 'Investigating… the brief appears when the investigation concludes.'));
  $('#q').disabled = false; $('#q').placeholder = `Follow-up about ${cid}… e.g. “why not a config change?”`;
  api('/api/topology').then(g => { topoGraph = g; drawTopology(briefData); }).catch(x => { topoGraph = { error: x.message }; drawTopology(briefData); });
  if (es) es.close(); es = new EventSource(`/api/stream/${encodeURIComponent(cid)}`);
  es.onmessage = (m) => { try { render(JSON.parse(m.data)); } catch (x) { console.error(x); } };
  document.querySelectorAll('#cases .item, #decisions .item').forEach(n => n.classList.toggle('on', n.dataset.cid === cid));
}
async function start(body) { const r = await api('/api/investigate', body); if (r.case_id) { open(r.case_id); loadSide(); } else toast(r.error || 'could not start', true); }

function tile(label, value, sub, cls) { const t = el('div', 'tile'); const v = el('div', 'v'); if (cls) v.append(el('span', 'dot ' + cls)); v.append(value); t.append(el('div', 'l', label), v, el('div', 's', sub || '')); return t; }
async function loadStatus() {
  const r = await api('/api/status'); const s = r.status || {}; const st = $('#strip'); st.replaceChildren(); lastStatus = s;
  if (!r.status) { st.append(tile('Status', '…', r.error ? 'error: ' + r.error : 'loading…'), runTile()); setTimeout(loadStatus, 3000); return; }
  st.append(tile('Approval rate · 5 min', s.approval_pct == null ? '–' : s.approval_pct + '%', `${(s.payments_5m || 0).toLocaleString()} payments`, s.approval_pct == null ? '' : s.approval_pct < 85 ? 'bad' : s.approval_pct < 90 ? 'warn' : 'good'));
  st.append(tile('checkout-api p90', ((s.checkout_p90_ms || 0) / 1000).toFixed(1) + ' s', 'APM · 5 min', s.checkout_p90_ms > 1500 ? 'bad' : s.checkout_p90_ms > 1000 ? 'warn' : 'good'));
  st.append(tile('payment-router errors', (s.router_error_pct || 0) + '%', 'APM · 5 min', s.router_error_pct > 5 ? 'bad' : s.router_error_pct > 1 ? 'warn' : 'good'));
  st.append(tile('Open alerts', String(r.open_alerts), (s.unhealthy || []).length ? 'unhealthy: ' + s.unhealthy.join(', ') : 'all services Ok', r.open_alerts ? 'warn' : 'good'));
  st.append(runTile());
  if (new URLSearchParams(location.search).get('facilitator')) {   // hidden by default: the flag names give the answer away
    const f = tile('Faults injected (war room)', String((s.faults_on || []).length), '', (s.faults_on || []).length ? 'bad' : 'good');
    const sub = f.querySelector('.s'); (s.faults_on || []).forEach(x => sub.append(el('span', 'fchip', x))); (s.load_on || []).forEach(x => sub.append(el('span', 'fchip load', x)));
    if (s.faults_on == null) sub.textContent = 'war-room panel not reachable';
    st.append(f);
  }
}
function clearCtl(what, hidden, nothingShown) {   // Clear hides finished items (nothing deleted); Show brings them back
  const w = $(`#clr-${what}`); if (!w) return; w.replaceChildren();
  if (hidden) { const sh = el('button', 'link', `Show ${hidden} hidden`); sh.onclick = async () => { await api('/api/unclear', { what }); loadSide(); }; w.append(sh); }
  if (!nothingShown) { const cl = el('button', null, 'Clear'); cl.title = what === 'cases' ? 'Hide finished cases (awaiting approval and running cases stay)' : 'Hide the alerts open now; a new firing shows again';
    cl.onclick = async () => { await api('/api/clear', { what }); toast(what === 'cases' ? 'Finished cases hidden' : 'Current alerts hidden'); loadSide(); }; w.append(cl); }
}
async function loadSide() {
  try {
    api('/api/cases').then(cs => {
      $('#mode').textContent = `tuktukpay-demo · ${cs.settings.provider === 'mock' ? 'scripted mock (no AI)' : cs.settings.provider} · approval: ${cs.settings.policy === 'ask' ? 'ask first' : cs.settings.policy}`;
      const c = $('#cases'), dc = $('#decisions'); c.replaceChildren(); dc.replaceChildren(); clearCtl('cases', cs.hidden || 0, !(cs.cases || []).length);
      const waiting = (cs.cases || []).filter(x => x.state === 'awaiting_approval'); $('#needs').hidden = !waiting.length; $('#needcount').textContent = String(waiting.length);
      if (!(cs.cases || []).length) c.append(el('div', 'item', 'No cases yet.'));
      (cs.cases || []).forEach(x => { const it = el('div', 'item'); it.dataset.cid = x.id; it.tabIndex = 0; it.classList.toggle('on', x.id === current);
        it.onkeydown = (ev) => { if (ev.key === 'Enter' && ev.target === it) open(x.id); };
        it.append(el('span', 'dot ' + ({ awaiting_approval: 'warn', resolved: 'good', mitigated_awaiting_clear: 'good', escalated: 'bad', verification_failed: 'bad', investigating: 'warn' }[x.state] || '')), el('span', 't', `${x.id} · ${String(x.state).replace(/_/g, ' ')}`), el('span', 's', `${(x.detectors || []).map(short).join(' + ')}${x.action ? ' → ' + x.action : ''}`));
        // merged cases in amber, like the merge banner in the brief; each card names both ends of the merge
        if (x.merged_into) { it.classList.add('merged'); const t = el('span', 'tag warn', `MERGED: ${x.id} → ${x.merged_into}`); t.title = `Open ${x.merged_into}`;
          t.onclick = (ev) => { ev.stopPropagation(); open(x.merged_into); }; const w = el('div'); w.append(t); it.append(w); }
        [...new Set(x.merged_from || [])].forEach(src => { it.classList.add('merged'); const t = el('span', 'tag warn', `MERGED: ${src} → ${x.id}`); t.title = `Open ${src}`;
          t.onclick = (ev) => { ev.stopPropagation(); open(src); }; const w = el('div'); w.append(t); it.append(w); });
        if (CLOSABLE.includes(x.state)) { const cb = el('button', null, 'Close case'); cb.onclick = (ev) => { ev.stopPropagation(); closeCase(x.id, cb); }; const hv = el('div', 'hv'); hv.append(cb); it.append(hv); }
        it.onclick = () => open(x.id); (x.state === 'awaiting_approval' ? dc : c).append(it); });
    });
    const inc = await api('/api/incidents'); const a = $('#alerts'); a.replaceChildren(); clearCtl('alerts', inc.hidden || 0, !(inc.incidents || []).length);
    if (inc.error && !inc.incidents) { a.append(el('div', 'item', 'Could not read incidents: ' + inc.error)); return; }
    ((inc.auto || {}).waiting || []).forEach(g => a.append(el('div', 'item', g.held ? `Grouping ${g.signals} signal(s): waiting for a free case slot` : `Grouping ${g.signals} signal(s): the agent starts in ${g.starts_in_s} s if still firing`)));
    if (!(inc.incidents || []).length) a.append(el('div', 'item', inc.hidden ? `No new alerts (${inc.hidden} cleared, still firing).` : 'No TukTukPay detector is firing. Ask a question above, or start an act from the war-room panel.'));
    (inc.incidents || []).forEach(i => {
      const it = el('div', 'item'); it.tabIndex = 0; it.append(el('span', 'dot ' + (/critical|major/i.test(i.severity || '') ? 'bad' : 'warn')), el('span', 't', short(i.detector)), el('span', 's', `${i.severity} · since ${hhmm(i.since)}`));
      if (i.case_id) {
        it.append(el('span', 's', `case ${i.case_id} · ${String(i.case_state || '').replace(/_/g, ' ')}`));
        const btns = el('div', 'hv'); it.onkeydown = (ev) => { if (ev.key === 'Enter' && ev.target === it) open(i.case_id); };
        const b = el('button', null, 'Open case'); b.onclick = (ev) => { ev.stopPropagation(); open(i.case_id); }; btns.append(b);
        if (!['open', 'investigating', 'remediating', 'verifying'].includes(i.case_state)) {   // the alert is still firing: investigate it again
          const rr = el('button', null, 'Re-run RCA'); rr.onclick = async (ev) => { ev.stopPropagation(); if (!(await confirmRerun(`“${short(i.detector)}”`))) return;
            rr.disabled = true; start({ incident_id: i.incident_id, rerun: true }).finally(() => { rr.disabled = false; }); }; btns.append(rr);
        }
        if (CLOSABLE.includes(i.case_state)) { const cb = el('button', null, 'Close case'); cb.onclick = (ev) => { ev.stopPropagation(); closeCase(i.case_id, cb); }; btns.append(cb); }
        it.append(btns);
        it.onclick = () => open(i.case_id);
      } else {
        const b = el('button', 'primary', 'Triage'); b.onclick = (ev) => { ev.stopPropagation(); b.disabled = true; start({ incident_id: i.incident_id }).finally(() => { b.disabled = false; }); };
        it.append(b);
      }
      a.append(it);
    });
  } catch (x) { $('#alerts').replaceChildren(el('div', 'item', 'Could not load alerts and cases: ' + (x && x.message || x))); }
}
PRESETS.forEach(([label, q]) => { const b = el('button', null, label); b.type = 'button'; b.onclick = () => { $('#symptom').value = q; $('#symptom').focus(); }; $('#chips').append(b); });
window.addEventListener('resize', () => { if (tree.nodes.length) drawTree(); });
drawTree(); drawTopology(null);
$('#askform').onsubmit = (ev) => { ev.preventDefault(); const q = $('#symptom').value.trim(); if (q) start({ question: q }); };
$('#follow').onsubmit = (ev) => { ev.preventDefault(); const q = $('#q').value.trim(); if (!q || !current) return; $('#q').value = '';
  api('/api/ask', { case_id: current, question: q }).then(r => { if (r.error) toast(r.error, true); else if (r.case_id) { open(r.case_id); loadSide(); } }); };
$('#stop').onclick = () => { if (!current) return; const b = $('#stop'); b.disabled = true; b.textContent = 'Stopping…';
  api('/api/stop', { case_id: current }).then(r => { if (r.error) { toast(r.error, true); b.disabled = false; b.textContent = 'Stop'; } }); };
loadSide(); loadStatus(); setInterval(loadSide, 10000); setInterval(loadStatus, 30000);
const pre = new URLSearchParams(location.search).get('case'); if (pre) open(pre);
</script></body></html>"""


def page() -> str:
    return PAGE
