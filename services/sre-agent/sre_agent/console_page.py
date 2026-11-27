"""The agent console's single page: status strip, symptom question bar, alerts and cases, a centre column with the
hypothesis tree, the service map (Topology) and the agent trace (steps by actor, every raw MCP call), and the war-room brief with the
decision box first. Inline CSS and JavaScript; every value goes in with textContent. Design and colour codes from
https://www.splunk.com/ (the war-room design rules); ?facilitator=1 shows the injected faults (hidden by default: they give the answer away)."""

PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>TukTukPay AI SRE agent</title>
<link rel="icon" href="/brand/favicon.svg" type="image/svg+xml">
<style>
@font-face{font-family:"Inter";font-weight:400;font-display:swap;src:url("/brand/Inter-Regular.woff2") format("woff2")}@font-face{font-family:"Inter";font-weight:600;font-display:swap;src:url("/brand/Inter-SemiBold.woff2") format("woff2")}
/* Colour has one meaning: coral = alerting/faulty, jade = healthy/verified, amber = degraded/inconclusive and (solid) the root cause, blue = being researched. Weights 400/600. */
:root{--p1:rgba(255,255,255,.1);--p2:rgba(255,255,255,.16);--solid:#0C1724;--line:rgba(255,255,255,.2);--text:#FFFFFF;--dim:#D5DCE5;--mute:#B8C0CC;--edge:rgba(255,255,255,.35);--edge2:rgba(255,255,255,.6);--acc:#FFFFFF;--acc-ink:#0C1724;--main:#CE0070;--ok:#63B58F;--warn:#FFAB0F;--bad:#E8707A;--root:#F0A04B;--ai:#8FB4F0;--wire:rgba(255,255,255,.5);--chip:#2A3360;--chipbad:#2B1A33;--mono:ui-monospace,SFMono-Regular,Menlo,monospace;--heading:linear-gradient(90deg,#FFAB0F 5%,#FF712B 40.5%,#FF0F7B 85.5%);--lift:inset 0 1px 0 rgba(255,255,255,.22),0 2px 12px rgba(0,0,0,.12),0 14px 32px rgba(0,0,0,.5)}
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
.item button,.hv button{padding:0 8px;font-size:12px;line-height:24px;justify-self:start}.hv{display:flex;gap:4px}
.item button.primary{color:var(--acc);border-color:var(--acc);margin-top:4px}
@media (hover:hover){.item .hv{position:absolute;right:8px;bottom:4px;visibility:hidden;opacity:0;padding:4px;border-radius:16px;background:rgba(12,23,36,.94);box-shadow:0 2px 8px rgba(0,0,0,.35);transition:opacity .12s}#side:not(.ready)>*{visibility:hidden}.item:hover .hv,.item:focus-within .hv{visibility:visible;opacity:1}}
.item.merged{border-left-color:var(--warn)}.tag{display:inline-block;font-size:12px;padding:0 8px;border:1px solid var(--acc);color:var(--acc);border-radius:4px;margin-right:8px;cursor:pointer;background:transparent}.tag.warn{border-color:var(--warn);color:var(--warn)}
/* centre column */
.vt{display:flex;gap:4px;padding:8px;border-bottom:1px solid var(--line);align-items:center;flex:none}.vt button{border:0;font-weight:600;color:var(--mute);padding:8px 16px}.vt button:hover{color:var(--text)}
.vt button[aria-selected=true]{color:var(--acc-ink);background:#fff}.vt .sp{flex:1}.vt .live{font-size:12px;color:var(--mute)}
.legend{display:flex;flex-wrap:wrap;align-items:center;gap:8px 16px;font-size:12px;color:var(--mute);padding:12px 16px 0}.legend .line{display:inline-block;width:16px;border-top:2px solid var(--acc);vertical-align:middle;margin-right:4px}
.note{font-size:12px;color:var(--mute);padding:8px 16px 0}
.pill{font-size:12px;padding:0 8px;border-radius:999px;border:1px solid var(--line);font-weight:600;color:var(--mute);white-space:nowrap}
.pill.validated{color:var(--ok);border-color:var(--ok)}.pill.inconclusive{color:var(--warn);border-color:var(--warn)}.pill.nottested{border-style:dashed}.pill.open{color:var(--acc);border-color:var(--acc)}.pill.rc{border-color:var(--acc);color:var(--acc)}.pill .i{width:12px;height:12px;vertical-align:-2px}
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
.bx.validated{border-left-color:var(--ok)}.bx.invalidated{border-left-color:var(--edge2);color:var(--mute)}.bx.inconclusive{border-left-color:var(--warn)}.bx.nottested{border-style:dashed;border-left-style:solid;color:var(--mute)}.bx.open{border-left-color:var(--acc)}
.bx.alert{border-left-color:var(--bad);width:224px;min-height:0}
.bx.root{border:2px solid var(--acc);border-left-width:4px;background:#232D5C}.bx.root.validated{border-left-color:var(--ok)}.bx.root[aria-pressed=true]{background:#343E6C}
.bx .rc{color:var(--acc);font-weight:600;white-space:nowrap}
/* hypothesis tree canvas: #cv clips, #tree.world is the one transformed layer (the camera); nodes keep a fixed width and the camera zooms instead.
   Calm scheme (27 Nov 2026): no glow and no lit outlines. Status = a small tinted pill with an icon, plus line style. The root cause is the one bold element (amber). */
#pane-tree,#pane-topo{display:flex;flex-direction:column;overflow:hidden}
.cv .secs{position:absolute;left:12px;top:12px;right:12px;display:flex;gap:4px;flex-wrap:wrap;z-index:3;pointer-events:none}.secs button{pointer-events:auto;padding:0 12px;font-size:12px;line-height:24px;border-color:var(--line);background:#101A45}.secs button:hover{background:#232D5C}
.secs button:disabled{color:var(--mute);border-style:dashed}.secs button[aria-current=true]{background:#fff;border-color:#fff;color:var(--acc-ink);font-weight:600}
.cv .legend{position:absolute;left:12px;bottom:8px;max-width:calc(100% - 80px);padding:4px 12px;border-radius:12px;background:#101A45;border:1px solid var(--line);z-index:2;pointer-events:none;gap:4px 12px}.cv .legend:empty{display:none}.cv .legend .line{width:24px;border-top:3px solid var(--root)}
:is(#pane-tree,#pane-topo,#trace) .pill{border:0;background:rgba(255,255,255,.08);padding:2px 10px;display:inline-flex;gap:6px;align-items:center;color:var(--mute)}:is(#pane-tree,#pane-topo,#trace) .pill .i{width:12px;height:12px}
:is(#pane-tree,#pane-topo,#trace) .pill.validated{color:var(--ok)}:is(#pane-tree,#pane-topo,#trace) .pill.open{color:var(--ai)}:is(#pane-tree,#pane-topo,#trace) .pill.inconclusive{color:var(--warn)}:is(#pane-tree,#pane-topo,#trace) .pill.rc{background:var(--root);color:#0C1724}
/* coral text needs a darker pill to stay readable; pills in the trace sit on the pane itself, so theirs are solid */
:is(#pane-tree,#pane-topo,#trace) .pill:is(.alerting,.failed){background:var(--chipbad);color:var(--bad)}#trace .pill:not(.rc,.alerting,.failed){background:var(--chip)}
.cv{position:relative;flex:1;min-height:320px;overflow:hidden;margin:16px 16px 8px;border-radius:16px;background:rgba(255,255,255,.06);box-shadow:inset 0 1px 0 rgba(255,255,255,.18);cursor:grab;touch-action:none;-webkit-user-select:none;user-select:none}
.cv.drag{cursor:grabbing}.cv:focus-visible{outline:2px solid var(--acc);outline-offset:2px}.cv .empty{margin:0;position:absolute;inset:0;display:grid;place-items:center;padding:24px;cursor:default}
.world{position:absolute;left:0;top:0;transform-origin:0 0;display:flex;flex-direction:column;align-items:center;width:max-content;padding:24px;overflow:visible;will-change:transform;--bw:260px}
.world .bx{cursor:pointer;min-height:0;padding:12px 16px 16px;border-radius:16px;border:1px solid var(--line);background:#1A2450;line-height:1.45;animation:nodein .3s ease}@keyframes nodein{from{opacity:0}to{opacity:1}}
.world .bx:hover,.world .bx[aria-pressed=true]{background:#232D5C}.world .bx .k{font-size:13px;gap:8px;margin-bottom:8px}.world .bx .k .when{margin-left:auto;white-space:nowrap}.world .bx .m{white-space:normal;color:var(--dim);margin-top:8px;padding-top:0}
.world .bx.validated{border-color:rgba(255,255,255,.7)}.world .bx.invalidated{opacity:.62;color:var(--text)}.world .bx.invalidated .k,#pane-tree .world .bx.invalidated .pill{color:var(--dim)}.world .bx.open{border-style:dashed;border-color:var(--ai)}.world .bx.nottested{border-style:dashed;opacity:.7;color:var(--text)}
.world .bx.alert{width:300px;border-left:4px solid var(--bad)}.world .bx.alert .k b{color:var(--bad)}.world .bx.alert .tt{font-weight:600}
.world .bx.root{border:2px solid var(--root);padding:11px 15px 15px;background:#1A2450}.world .bx.root[aria-pressed=true]{background:#232D5C}
/* line style repeats the meaning: solid 3px amber = path to the root cause (drawn by #rpath), moving blue dashes = being researched, dim dots = ruled out, thin grey = the rest */
.world li>.dr{position:absolute;top:0;left:50%;height:24px;width:2px;margin-left:-1px;pointer-events:none;display:none}
.world li.open::after,.world li.out::after{border-left-color:transparent}.world li.open:last-child::before,.world li.out:last-child::before{border-right-color:transparent}
.world li.open>.dr{display:block;background:repeating-linear-gradient(180deg,var(--ai) 0 6px,transparent 6px 12px);background-size:2px 12px;animation:flow .9s linear infinite}@keyframes flow{to{background-position:0 12px}}
.world li.out>.dr{display:block;background:repeating-linear-gradient(180deg,rgba(255,255,255,.3) 0 2px,transparent 2px 8px)}
.world li.path::after,.world ul.path::before{border-left-color:var(--edge)}.world li.path:last-child::before{border-right-color:var(--edge)}
#rpath{position:absolute;left:0;top:0;width:1px;height:1px;overflow:visible;pointer-events:none}#rpath path{fill:none;stroke:var(--root);stroke-width:3;stroke-linejoin:round;stroke-linecap:round}
.ph,.cc{position:relative;flex:none;margin-top:32px}.ph::before,.cc::before{content:"";position:absolute;left:50%;top:-33px;height:32px;border-left:2px solid var(--edge);margin-left:-1px}.cc.linked::before{display:none}
.ph{width:220px;text-align:center;padding:12px 16px;border-radius:16px;border:1px dashed var(--line);color:var(--mute);font-size:13px}
.ph i{position:absolute;inset:0;border-radius:16px;overflow:hidden;pointer-events:none}.ph i::after{content:"";position:absolute;inset:0;background:linear-gradient(100deg,transparent 30%,rgba(255,255,255,.16) 50%,transparent 70%);animation:sheen 1.4s linear infinite}@keyframes sheen{from{transform:translateX(-100%)}to{transform:translateX(100%)}}
.cc{width:560px;text-align:left;border-radius:16px;background:#16205A;border:1px solid var(--line);padding:12px 16px 16px;line-height:1.45;animation:nodein .3s ease}
.cc .lb{display:flex;align-items:center;gap:8px;font-size:13px;color:var(--mute);margin-bottom:8px}.cc .ct{font-size:18px;font-weight:600;line-height:1.3;margin-bottom:12px;overflow-wrap:anywhere}
.cc .two{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.cc .two>div{background:rgba(255,255,255,.08);border-radius:12px;padding:8px 12px}.cc .l2{font-size:13px;font-weight:600;color:var(--mute);margin:0 0 4px}.cc p{margin:0;color:var(--dim);overflow-wrap:anywhere}
.cc .steps{display:grid;grid-template-columns:auto minmax(0,1fr);gap:8px 12px;color:var(--dim)}.cc .steps .no{color:var(--mute);text-align:right}.cc .steps .vf{color:var(--text)}.cc .steps .pill{margin-right:8px}
.cvc{position:absolute;right:16px;top:50%;transform:translateY(-50%);display:flex;flex-direction:column;background:#101A45;border:1px solid var(--line);border-radius:12px;overflow:hidden;z-index:3;cursor:default}
.cvc button{width:40px;height:40px;padding:0;display:grid;place-items:center;border:0;border-bottom:1px solid var(--line);border-radius:0;background:transparent}.cvc button:last-child{border-bottom:0}.cvc button:hover{background:rgba(255,255,255,.12)}
.cvc button[aria-pressed=true]{background:#0064DA}.cvc button:focus-visible{outline-offset:-2px}.cvc .i{width:20px;height:20px;vertical-align:0}
.cv .detail{position:absolute;left:12px;right:72px;bottom:8px;max-height:48%;overflow:auto;padding:12px 16px 16px;border-radius:16px;background:#101A45;border:1px solid var(--line);z-index:4;cursor:default;-webkit-user-select:text;user-select:text;touch-action:auto}.cv.has-detail .legend{display:none}
.cv .detail .lab{display:flex;align-items:center;justify-content:space-between;margin:0 0 8px}.cv .detail .lab button{padding:0 8px;font-size:12px;line-height:24px;font-weight:400}.cv .detail .node{border:0!important;border-radius:0;background:none;padding:0}
/* service map: the same canvas as the tree. Boxes sit where the layout code puts them and never change size; right-angle lines run under them, arrow at the callee.
   Status = pill (text and icon) plus line style: amber 2px border and solid 3px amber line = root cause and the path to it, coral band = alerting, blue dashes = suspected, grey dashes = not in this case */
.world.map{display:block;padding:0}#mapempty{align-content:center;justify-items:center;gap:12px;text-align:center;padding:24px 72px}#pane-topo .legend{max-width:calc(100% - 24px)}#mapempty .i{color:var(--bad)}
#medges{position:absolute;left:0;top:0;width:1px;height:1px;overflow:visible;pointer-events:none}#medges .me{fill:none;stroke:var(--wire);stroke-width:2}#medges .me.on{stroke:var(--root);stroke-width:3}#medges .mk path{fill:rgba(255,255,255,.75)}#medges .mk.on path{fill:var(--root)}
.sv{position:absolute;z-index:1;width:180px;height:120px;display:grid;grid-template-columns:36px minmax(0,1fr);grid-template-rows:36px minmax(0,1fr);gap:6px 8px;padding:12px;border-radius:16px;border:1px solid var(--line);background:#1A2450;color:var(--text);text-align:left;line-height:1.3}
.sv:hover{background:#232D5C;border-color:var(--line)}.sv[aria-pressed=true],.sv[aria-pressed=true]:hover{background:#2A3463;border-color:var(--edge2)}
.sv .ti{width:36px;height:36px;border-radius:12px;display:grid;place-items:center;background:rgba(255,255,255,.1);box-shadow:inset 0 1px 0 rgba(255,255,255,.22)}.sv .ti .i{width:22px;height:22px;stroke-width:1.75;vertical-align:0}
.sv .tx{grid-column:1/-1;grid-row:2;min-width:0;display:flex;flex-direction:column}.sv .tx span{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.sv .nm{font-size:15px;font-weight:600}.sv .ro{font-size:12.5px;color:var(--dim)}.sv .fx{font-size:12px;color:var(--dim);min-height:16px}.sv .fx.num{color:var(--text);font-variant-numeric:tabular-nums}
.sv .ps{grid-column:2;grid-row:1;justify-self:end;align-self:start;display:flex;gap:6px;align-items:center;min-width:0;max-width:100%;overflow:hidden}
.sv.alert,.sv.alert:hover{border-left:4px solid var(--bad);padding-left:9px}.sv.suspect,.sv.suspect:hover{border-style:dashed;border-color:var(--ai)}.sv.root,.sv.root:hover{border:2px solid var(--root);padding:11px}
.sv.root .ti{background:rgba(240,160,75,.2);color:var(--root)}.sv.alert .ti{background:rgba(232,112,122,.18);color:var(--bad)}.sv.suspect .ti{background:rgba(143,180,240,.16);color:var(--ai)}
.sv.na{border-style:dashed}.sv.na .ti,.sv.na .tx{opacity:.7}#pane-topo .sv.na .pill{color:var(--dim)}
.cv .legend .line.call{border-top:2px solid var(--wire);position:relative;margin-right:10px}.cv .legend .line.call::after{content:"";position:absolute;right:-6px;top:-5px;border:4px solid transparent;border-left:6px solid rgba(255,255,255,.75)}
.mapnote{flex:none;min-height:28px;padding:0 16px 8px}
.nums{display:grid;grid-template-columns:repeat(auto-fit,minmax(88px,1fr));gap:4px 16px;margin-top:8px;font-size:12px;color:var(--mute)}.nums span{display:flex;flex-direction:column;min-width:0}.nums b{font-size:14px;color:var(--text)}
button.hid{padding:0 6px;border-radius:6px;border:1px solid var(--line);font:12px/20px var(--mono);color:var(--text);justify-self:start;align-self:start}
@media (prefers-reduced-motion:reduce){.world .bx,.cc,.world li.open>.dr,.ph i::after{animation:none}.tr .cx{transition:none}}
.detail{padding:0 16px 16px}.lab{font-size:12px;color:var(--mute);margin:16px 0 8px;font-weight:600}
.node{border:1px solid var(--line);border-left:4px solid var(--edge);border-radius:16px;background:var(--p1);padding:8px 16px}.node.validated{border-left-color:var(--ok)}.node.inconclusive{border-left-color:var(--warn)}.node.root{border-color:var(--acc)}.node.root.validated{border-left-color:var(--ok)}
.nh{display:flex;gap:8px;align-items:center;flex-wrap:wrap;font-size:12px;color:var(--mute);margin-bottom:4px}.nh .id{font-family:var(--mono)}.nh .sp{flex:1}.fd{color:var(--mute);margin-top:4px}
.ck{font-size:12px;color:var(--mute);margin-top:4px}.ck.good b{color:var(--ok)}.ck.bad b{color:var(--warn)}
.evd{display:grid;grid-template-columns:64px minmax(0,1fr);gap:8px;padding:8px 0;border-top:1px solid var(--line)}.sig{font-size:12px;color:var(--mute);text-transform:capitalize}
/* agent trace: steps on a rail (time, who acted, what happened, how long) and plain rows of one shape under each step. Status = icon and pill, never colour alone */
#trace{display:flex;flex-direction:column;flex:1;min-height:0;position:relative}
.tbar{display:flex;align-items:center;gap:12px;flex:none;min-height:44px;padding:8px 16px;border-bottom:1px solid var(--line);font-size:13px;color:var(--dim)}.tbar .ts{flex:1;min-width:0;display:flex;gap:8px;align-items:center}.tbar .ts span{min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.tbar .ts .i{flex:none;color:var(--mute);vertical-align:0}#trace.live .tbar .ts .i{color:var(--ai)}.tbar button{padding:0 12px;font-size:12px;line-height:26px;white-space:nowrap}
#tlog{padding:12px 16px 16px;--at:48px}#tlog:focus-visible{outline:2px solid var(--acc);outline-offset:-2px}#tlog .empty{margin:40px 8px}#tlog details{margin:0}
.seg{position:relative;display:grid;grid-template-columns:var(--at) 28px minmax(0,1fr);column-gap:10px;padding-bottom:12px}
.seg::before{content:"";position:absolute;left:calc(var(--at) + 23px);top:30px;bottom:-2px;width:2px;background:var(--line)}.seg:last-child::before{display:none}
.seg>.at{font:12px var(--mono);color:var(--mute);text-align:right;padding-top:6px;white-space:nowrap}
.seg>.nd{width:28px;height:28px;border-radius:50%;display:grid;place-items:center;background:#1A2450;border:1px solid var(--line);color:var(--dim);position:relative;z-index:1}.seg>.nd .i{width:16px;height:16px;vertical-align:0}
.seg.model>.nd{color:var(--ai)}.seg.person>.nd{background:#fff;border-color:#fff;color:var(--acc-ink)}.seg.run>.nd{border-style:dashed;border-color:var(--ai);color:var(--ai)}.seg.minor>.nd{width:10px;height:10px;margin:9px}
.sh{display:flex;flex-wrap:wrap;align-items:baseline;gap:0 8px;min-height:28px;padding-top:4px;min-width:0}.sh .who{font-size:12px;font-weight:600;min-width:46px;color:var(--dim)}.seg.model .who{color:var(--ai)}.seg.person .who{color:var(--text)}
.sh .tt{font-weight:600;overflow-wrap:anywhere}.sh .sm{color:var(--dim);font-size:13px;overflow-wrap:anywhere}.sh .du{margin-left:auto;font:12px var(--mono);color:var(--mute);white-space:nowrap}.seg.minor .tt{font-weight:400;font-size:13px;color:var(--dim)}
.sb{grid-column:3;min-width:0;overflow-wrap:anywhere}
.tr{display:block}.tr .ln{display:grid;grid-template-columns:18px minmax(0,1fr) auto;column-gap:8px;align-items:start;padding:4px 0;color:var(--text)}
.tr summary.ln{grid-template-columns:18px minmax(0,1fr) auto 16px;list-style:none;cursor:pointer;border-radius:8px;font-size:14px;color:var(--text)}.tr summary.ln::-webkit-details-marker{display:none}.tr summary.ln:hover{background:rgba(255,255,255,.06)}
.tr .ico,.tr .cx{display:grid;place-items:center;height:21px;color:var(--mute)}.tr .ico .i,.tr .cx .i{vertical-align:0}.tr .cx{transition:transform .15s}.tr[open]>summary .cx{transform:rotate(180deg)}
.tr .me2{font:12px var(--mono);color:var(--mute);white-space:nowrap;display:inline-flex;gap:8px;align-items:center;min-height:21px}
.tr.ok>.ln .ico,.tr.raw .me2 .i{color:var(--ok)}.tr.bad>.ln .ico,.tr.raw.bad .me2 .i{color:var(--bad)}.tr.wait>.ln .ico{color:var(--ai)}
.mo{font:12px var(--mono);color:var(--mute)}.mo .srv{color:var(--dim)}.mo.full{white-space:pre-wrap;word-break:break-all;margin:0 0 4px}
.tr .s2{font-size:12px;color:var(--dim);margin-top:2px}.tr .sl{display:flex;gap:12px;align-items:center;margin-top:2px;min-height:20px}.tr .sg{flex:1;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.tr .rs2{flex:none;min-width:136px;justify-content:flex-end;font:12px var(--mono);color:var(--mute);display:inline-flex;gap:8px;align-items:center}
.tr .nx{font-size:12px;color:var(--mute)}.tr .more{padding:0 0 8px 26px}.raws{padding-left:26px}
.tr.raw .ln,.tr.ev .ln{padding:2px 0;font-size:13px}.tr.raw .mn{min-width:0}.tr.raw .mo{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.tr.nt .ln,.tr.hy .ln{font-size:13px;color:var(--dim)}.hyl{display:flex;flex-wrap:wrap;gap:2px 8px;align-items:baseline}.hyl .hx{flex:1 1 260px;min-width:0}
.tr.rs .ln{padding-bottom:6px}.lb2{font-size:12px;color:var(--mute)}
.stg{display:grid;grid-template-columns:repeat(auto-fit,minmax(112px,1fr));gap:8px 16px;font-size:12px;color:var(--mute)}.stg span{display:flex;flex-direction:column;min-width:0}.stg b{font-size:15px;color:var(--text)}.stg small{font-size:12px;color:var(--dim)}
.tnew{position:absolute;right:24px;bottom:12px;z-index:2;display:inline-flex;gap:6px;align-items:center;background:#fff;border-color:#fff;color:var(--acc-ink);font-weight:600;font-size:12px;padding:4px 12px;box-shadow:0 4px 16px rgba(0,0,0,.4)}.tnew:hover{background:var(--dim);border-color:var(--dim)}.tnew .i{vertical-align:0}
#trace.noraw .tr.raw{display:none}
.plain{font-size:12px;color:var(--mute)}
details{margin:4px 0}summary{cursor:pointer;color:var(--mute);font-size:12px}
pre{white-space:pre-wrap;word-break:break-all;font:12px var(--mono);background:rgba(0,0,0,.3);border:1px solid var(--line);border-radius:12px;padding:8px;margin:4px 0 0;max-height:224px;overflow:auto}
.follow{display:flex;gap:8px;padding:8px 16px;border-top:1px solid var(--line);flex:none}.follow input{flex:1}.follow button.stopbtn{color:var(--bad);border-color:var(--bad)}
/* brief */
.brief{padding:8px 24px 24px}.brief h3{font-size:16px;line-height:1.4;margin:16px 0 8px}.brief p{margin:0 0 8px}.brief ul{margin:4px 0 8px;padding-left:16px}
.decide{background:var(--p2);border:1px solid var(--line);border-radius:16px;padding:16px;margin:8px 0 8px}.decide.reserve{min-height:320px}.decide.live{background:#232D5C;border-color:#fff;position:sticky;top:0;z-index:2;box-shadow:0 8px 24px rgba(0,0,0,.3)}.decide.live::before{content:"";display:block;width:32px;height:4px;margin-bottom:8px;border-radius:2px;background:linear-gradient(90deg,#FF0F7B,#FF712B)}
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
@media (max-width:1100px){html,body{height:auto}.grid{grid-template-columns:minmax(0,1fr);padding:0 16px 16px}.pane:last-child{order:-1}.scroll{overflow:visible}.ht{overflow-x:auto}.world{overflow:visible}.cv{flex:none;height:480px}header{padding:12px 16px}.ask{max-width:none;flex-basis:100%;margin-left:0}.brief{padding:8px 16px 16px}.decide.live{position:static}.strip{margin:0 16px}.tile{padding:8px 16px}.chips{padding:8px 16px}}
@media (max-width:600px){.world{--bw:220px}.world .bx.alert{width:260px}.cc{width:340px}.cc .two{grid-template-columns:minmax(0,1fr)}.mapnote{min-height:62px}#mapempty{padding:24px 64px 24px 16px}.tbar{min-height:60px;font-size:12px}.tbar .ts span{white-space:normal;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical}#tlog{--at:0px;padding:12px 12px 16px}.seg{grid-template-columns:28px minmax(0,1fr)}.seg>.at{display:none}.seg::before{left:13px}.sb{grid-column:2}.sh .who{min-width:0}.tr .more,.raws{padding-left:12px}}
@media (max-width:480px){header h1{font-size:20px;white-space:normal}.grid,.strip,.chips{min-width:0}.vt{gap:0;padding:8px 4px}.vt button{white-space:nowrap;padding:8px 10px;font-size:13px}.vt .live{display:none}}
</style></head><body>
<svg width="0" height="0" style="position:absolute" aria-hidden="true"><symbol id="ic-check" viewBox="0 0 24 24"><path d="M5 12l5 5l10 -10"/></symbol><symbol id="ic-x" viewBox="0 0 24 24"><path d="M18 6l-12 12"/><path d="M6 6l12 12"/></symbol><symbol id="ic-external" viewBox="0 0 24 24"><path d="M12 6h-6a2 2 0 0 0 -2 2v10a2 2 0 0 0 2 2h10a2 2 0 0 0 2 -2v-6"/><path d="M11 13l9 -9"/><path d="M15 4h5v5"/></symbol><symbol id="ic-plus" viewBox="0 0 24 24"><path d="M12 5l0 14"/><path d="M5 12l14 0"/></symbol><symbol id="ic-minus" viewBox="0 0 24 24"><path d="M5 12l14 0"/></symbol><symbol id="ic-maximize" viewBox="0 0 24 24"><path d="M4 8v-2a2 2 0 0 1 2 -2h2"/><path d="M4 16v2a2 2 0 0 0 2 2h2"/><path d="M16 4h2a2 2 0 0 1 2 2v2"/><path d="M16 20h2a2 2 0 0 0 2 -2v-2"/></symbol><symbol id="ic-current-location" viewBox="0 0 24 24"><path d="M9 12a3 3 0 1 0 6 0a3 3 0 1 0 -6 0"/><path d="M4 12a8 8 0 1 0 16 0a8 8 0 1 0 -16 0"/><path d="M12 2l0 2"/><path d="M12 20l0 2"/><path d="M20 12l2 0"/><path d="M2 12l2 0"/></symbol><symbol id="ic-alert-triangle" viewBox="0 0 24 24"><path d="M12 9v4"/><path d="M10.363 3.591l-8.106 13.534a1.914 1.914 0 0 0 1.636 2.871h16.214a1.914 1.914 0 0 0 1.636 -2.87l-8.106 -13.536a1.914 1.914 0 0 0 -3.274 0"/><path d="M12 16h.01"/></symbol><symbol id="ic-bulb" viewBox="0 0 24 24"><path d="M3 12h1m8 -9v1m8 8h1m-15.4 -6.4l.7 .7m12.1 -.7l-.7 .7"/><path d="M9 16a5 5 0 1 1 6 0a3.5 3.5 0 0 0 -1 3a2 2 0 0 1 -4 0a3.5 3.5 0 0 0 -1 -3"/><path d="M9.7 17l4.6 0"/></symbol><symbol id="ic-list-check" viewBox="0 0 24 24"><path d="M3.5 5.5l1.5 1.5l2.5 -2.5"/><path d="M3.5 11.5l1.5 1.5l2.5 -2.5"/><path d="M3.5 17.5l1.5 1.5l2.5 -2.5"/><path d="M11 6l9 0"/><path d="M11 12l9 0"/><path d="M11 18l9 0"/></symbol><symbol id="ic-credit-card" viewBox="0 0 24 24"><path d="M3 8a3 3 0 0 1 3 -3h12a3 3 0 0 1 3 3v8a3 3 0 0 1 -3 3h-12a3 3 0 0 1 -3 -3l0 -8"/><path d="M3 10l18 0"/><path d="M7 15l.01 0"/><path d="M11 15l2 0"/></symbol><symbol id="ic-shield" viewBox="0 0 24 24"><path d="M12 3a12 12 0 0 0 8.5 3a12 12 0 0 1 -8.5 15a12 12 0 0 1 -8.5 -15a12 12 0 0 0 8.5 -3"/></symbol><symbol id="ic-arrows-split-2" viewBox="0 0 24 24"><path d="M21 17h-5.397a5 5 0 0 1 -4.096 -2.133l-.514 -.734a5 5 0 0 0 -4.096 -2.133h-3.897"/><path d="M21 7h-5.395a5 5 0 0 0 -4.098 2.135l-.51 .73a5 5 0 0 1 -4.097 2.135h-3.9"/><path d="M18 10l3 -3l-3 -3"/><path d="M18 20l3 -3l-3 -3"/></symbol><symbol id="ic-building-bank" viewBox="0 0 24 24"><path d="M3 21l18 0"/><path d="M3 10l18 0"/><path d="M5 6l7 -3l7 3"/><path d="M4 10l0 11"/><path d="M20 10l0 11"/><path d="M8 14l0 3"/><path d="M12 14l0 3"/><path d="M16 14l0 3"/></symbol><symbol id="ic-book-2" viewBox="0 0 24 24"><path d="M19 4v16h-12a2 2 0 0 1 -2 -2v-12a2 2 0 0 1 2 -2h12"/><path d="M19 16h-12a2 2 0 0 0 -2 2"/><path d="M9 8h6"/></symbol><symbol id="ic-wallet" viewBox="0 0 24 24"><path d="M17 8v-3a1 1 0 0 0 -1 -1h-10a2 2 0 0 0 0 4h12a1 1 0 0 1 1 1v3m0 4v3a1 1 0 0 1 -1 1h-12a2 2 0 0 1 -2 -2v-12"/><path d="M20 12v4h-4a2 2 0 0 1 0 -4h4"/></symbol><symbol id="ic-message-chatbot" viewBox="0 0 24 24"><path d="M18 4a3 3 0 0 1 3 3v8a3 3 0 0 1 -3 3h-5l-5 3v-3h-2a3 3 0 0 1 -3 -3v-8a3 3 0 0 1 3 -3h12"/><path d="M9.5 9h.01"/><path d="M14.5 9h.01"/><path d="M9.5 13a3.5 3.5 0 0 0 5 0"/></symbol><symbol id="ic-webhook" viewBox="0 0 24 24"><path d="M4.876 13.61a4 4 0 1 0 6.124 3.39h6"/><path d="M15.066 20.502a4 4 0 1 0 1.934 -7.502c-.706 0 -1.424 .179 -2 .5l-3 -5.5"/><path d="M16 8a4 4 0 1 0 -8 0c0 1.506 .77 2.818 2 3.5l-3 5.5"/></symbol><symbol id="ic-building-store" viewBox="0 0 24 24"><path d="M3 21l18 0"/><path d="M3 7v1a3 3 0 0 0 6 0v-1m0 1a3 3 0 0 0 6 0v-1m0 1a3 3 0 0 0 6 0v-1h-18l2 -4h14l2 4"/><path d="M5 21l0 -10.15"/><path d="M19 21l0 -10.15"/><path d="M9 21v-4a2 2 0 0 1 2 -2h2a2 2 0 0 1 2 2v4"/></symbol><symbol id="ic-shopping-cart" viewBox="0 0 24 24"><path d="M4 19a2 2 0 1 0 4 0a2 2 0 1 0 -4 0"/><path d="M15 19a2 2 0 1 0 4 0a2 2 0 1 0 -4 0"/><path d="M17 17h-11v-14h-2"/><path d="M6 5l14 1l-1 7h-13"/></symbol><symbol id="ic-server-2" viewBox="0 0 24 24"><path d="M3 7a3 3 0 0 1 3 -3h12a3 3 0 0 1 3 3v2a3 3 0 0 1 -3 3h-12a3 3 0 0 1 -3 -3v-2"/><path d="M3 15a3 3 0 0 1 3 -3h12a3 3 0 0 1 3 3v2a3 3 0 0 1 -3 3h-12a3 3 0 0 1 -3 -3l0 -2"/><path d="M7 8l0 .01"/><path d="M7 16l0 .01"/><path d="M11 8h6"/><path d="M11 16h6"/></symbol><symbol id="ic-search" viewBox="0 0 24 24"><path d="M3 10a7 7 0 1 0 14 0a7 7 0 1 0 -14 0"/><path d="M21 21l-6 -6"/></symbol><symbol id="ic-code" viewBox="0 0 24 24"><path d="M7 8l-4 4l4 4"/><path d="M17 8l4 4l-4 4"/><path d="M14 4l-4 16"/></symbol><symbol id="ic-sparkles" viewBox="0 0 24 24"><path d="M16 18a2 2 0 0 1 2 2a2 2 0 0 1 2 -2a2 2 0 0 1 -2 -2a2 2 0 0 1 -2 2m0 -12a2 2 0 0 1 2 2a2 2 0 0 1 2 -2a2 2 0 0 1 -2 -2a2 2 0 0 1 -2 2m-7 12a6 6 0 0 1 6 -6a6 6 0 0 1 -6 -6a6 6 0 0 1 -6 6a6 6 0 0 1 6 6"/></symbol><symbol id="ic-user" viewBox="0 0 24 24"><path d="M8 7a4 4 0 1 0 8 0a4 4 0 0 0 -8 0"/><path d="M6 21v-2a4 4 0 0 1 4 -4h4a4 4 0 0 1 4 4v2"/></symbol><symbol id="ic-plug-connected" viewBox="0 0 24 24"><path d="M7 12l5 5l-1.5 1.5a3.536 3.536 0 1 1 -5 -5l1.5 -1.5"/><path d="M17 12l-5 -5l1.5 -1.5a3.536 3.536 0 1 1 5 5l-1.5 1.5"/><path d="M3 21l2.5 -2.5"/><path d="M18.5 5.5l2.5 -2.5"/><path d="M10 11l-2 2"/><path d="M13 14l-2 2"/></symbol><symbol id="ic-file-text" viewBox="0 0 24 24"><path d="M14 3v4a1 1 0 0 0 1 1h4"/><path d="M17 21h-10a2 2 0 0 1 -2 -2v-14a2 2 0 0 1 2 -2h7l5 5v11a2 2 0 0 1 -2 2"/><path d="M9 9l1 0"/><path d="M9 13l6 0"/><path d="M9 17l6 0"/></symbol><symbol id="ic-binary-tree" viewBox="0 0 24 24"><path d="M6 20a2 2 0 1 0 -4 0a2 2 0 0 0 4 0"/><path d="M16 4a2 2 0 1 0 -4 0a2 2 0 0 0 4 0"/><path d="M16 20a2 2 0 1 0 -4 0a2 2 0 0 0 4 0"/><path d="M11 12a2 2 0 1 0 -4 0a2 2 0 0 0 4 0"/><path d="M21 12a2 2 0 1 0 -4 0a2 2 0 0 0 4 0"/><path d="M5.058 18.306l2.88 -4.606"/><path d="M10.061 10.303l2.877 -4.604"/><path d="M10.065 13.705l2.876 4.6"/><path d="M15.063 5.7l2.881 4.61"/></symbol><symbol id="ic-circle-dashed" viewBox="0 0 24 24"><path d="M8.56 3.69a9 9 0 0 0 -2.92 1.95"/><path d="M3.69 8.56a9 9 0 0 0 -.69 3.44"/><path d="M3.69 15.44a9 9 0 0 0 1.95 2.92"/><path d="M8.56 20.31a9 9 0 0 0 3.44 .69"/><path d="M15.44 20.31a9 9 0 0 0 2.92 -1.95"/><path d="M20.31 15.44a9 9 0 0 0 .69 -3.44"/><path d="M20.31 8.56a9 9 0 0 0 -1.95 -2.92"/><path d="M15.44 3.69a9 9 0 0 0 -3.44 -.69"/></symbol><symbol id="ic-chevron-down" viewBox="0 0 24 24"><path d="M6 9l6 6l6 -6"/></symbol><symbol id="ic-info-circle" viewBox="0 0 24 24"><path d="M3 12a9 9 0 1 0 18 0a9 9 0 0 0 -18 0"/><path d="M12 9h.01"/><path d="M11 12h1v4h1"/></symbol></svg>
<div class="aurora"></div>
<header><img class="logo" src="/brand/splunk-logo-white.svg" alt="Splunk by Cisco" onerror="this.remove()"><h1 class="gt">TukTukPay AI SRE agent</h1><span class="meta" id="mode">…</span><form class="ask" id="askform"><input id="symptom" aria-label="Describe a symptom to investigate" placeholder="Describe what you see, e.g. card payments failing at checkout" autocomplete="off"><button type="submit">Investigate</button></form></header>
<div class="strip" id="strip"><div class="tile"><div class="l">Status</div><div class="v">…</div><div class="s">loading</div></div></div>
<div class="chips" id="chips" aria-label="Example symptoms"></div>
<div class="grid">
  <section class="pane" aria-label="Alerts and cases"><div class="scroll" id="side"><div id="needs" hidden><div class="sub"><span class="gt">Needs your decision</span> <span class="count" id="needcount">0</span></div><div id="decisions"></div></div><div class="sub"><span class="gt">Open alerts</span> <span class="clr" id="clr-alerts"></span></div><div id="alerts"><div class="item"><span class="s">loading…</span></div></div><div class="sub"><span class="gt">Recent cases</span> <span class="clr" id="clr-cases"></span></div><div id="cases"></div></div></section>
  <section class="pane" aria-label="Agent reasoning"><div class="vt" role="tablist" id="vt"><span class="sp"></span><span class="live" id="runstate"></span></div>
    <div class="scroll" id="pane-tree"><div class="note" id="treenote"></div>
      <div class="cv" id="cv" tabindex="0" role="group" aria-label="Hypothesis tree canvas. Drag or use the arrow keys to move, scroll or press plus and minus to zoom, press 0 to fit the whole tree."><div class="empty" id="treeempty"></div><div class="ht world" id="tree" role="group" aria-label="Hypothesis tree" hidden></div>
        <div class="secs" id="secs" role="group" aria-label="Jump to a part of the tree"></div><div class="cvc" id="cvc" role="group" aria-label="Canvas controls"></div><div class="legend" id="legend"></div><div class="detail" id="detail" aria-live="polite" hidden></div></div></div>
    <div class="scroll" id="pane-topo" hidden><div class="cv" id="mcv" tabindex="0" role="group" aria-label="Service map canvas. Drag or use the arrow keys to move, scroll or press plus and minus to zoom, press 0 to fit the whole map."><div class="empty" id="mapempty"></div><div class="world map" id="map" role="group" aria-label="Service map" hidden></div>
        <div class="cvc" id="mcvc" role="group" aria-label="Map controls"></div><div class="legend" id="tlegend"></div><div class="detail" id="tdetail" aria-live="polite" hidden></div></div><div class="note mapnote" id="toponote"></div></div>
    <div id="trace" hidden><div class="tbar"><span class="ts" id="tstat" role="status"><span></span></span><button type="button" id="trawbtn" title="Show or hide every raw call to Observability Cloud and Splunk in the list"></button></div>
      <div class="scroll" id="tlog" role="log" aria-label="Agent trace" tabindex="0"></div><button type="button" class="tnew" id="tnew" hidden>New steps below </button></div>
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
function at(e) { const t = Number(e.t) || Date.parse(e.ts) / 1000; if (t0 == null) t0 = t; return '+' + Math.max(0, t - t0).toFixed(1) + 's'; }   // seconds since the first step of the case
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

const STATUS_LABEL = { validated: 'Verified', invalidated: 'Ruled out', inconclusive: 'Inconclusive', 'not tested': 'Not tested', open: 'Researching' };
const STATUS_ICON = { validated: 'check', invalidated: 'x' };   // the icon repeats what the colour says
const stKey = (s) => String(s || 'inconclusive').replace(' ', '');
const nb = (t) => String(t || '').replace(/-/g, '‑');   // service names never break at a hyphen
const firstSentence = (t) => String(t || '').split(/(?<=\.)\s/)[0];
const restSentences = (t) => String(t || '').split(/(?<=\.)\s/).slice(1).join(' ');
const PANES = [['pane-tree', 'Hypothesis tree'], ['pane-topo', 'Topology'], ['trace', 'Agent trace']];
const LEDGER_TOOLS = ['hypothesis_open', 'hypothesis_verdict'];
let briefData = null, tabPicked = false, briefCase = null, topoGraph = null, run = null;
let tree = { nodes: [], alert: null, evidence: [], method: null, selected: null };
function setTab(id) { const was = $('#' + id).hidden, shown = id === 'pane-tree' && was; PANES.forEach(([x]) => { $('#' + x).hidden = x !== id; }); $('#vt').querySelectorAll('button').forEach(b => b.setAttribute('aria-selected', String(b.dataset.pane === id)));
  if (shown) requestAnimationFrame(() => aim(0));   // a canvas has no size while its tab is hidden: place the camera when it appears
  if (was && id === 'pane-topo') requestAnimationFrame(() => aimMap(0)); if (was && id === 'trace' && tr.live) TLOG.scrollTop = TLOG.scrollHeight; }   // a running case opens on its newest step
PANES.forEach(([id, label]) => { const b = el('button', null, label); b.type = 'button'; b.dataset.pane = id; b.setAttribute('role', 'tab'); b.onclick = () => { tabPicked = true; setTab(id); }; $('#vt').insertBefore(b, $('#vt').querySelector('.sp')); });
function treeUpsert(n) { const i = tree.nodes.findIndex(x => x.id === n.id); if (i < 0) tree.nodes.push(n); else tree.nodes[i] = Object.assign(tree.nodes[i], n); tree.method = 'tree'; if (!tabPicked && $('#pane-tree').hidden) setTab('pane-tree');
  clearTimeout(tv.drawTimer); tv.drawTimer = setTimeout(drawTree, 80); mapSoon(); }   // siblings of one burst appear together: one layout change instead of a jump per node
function rootNode(nodes) {   // the deepest validated node; a fault marked independent is not this alert's root cause. None while the run is still going
  if (tv.investigating) return null; const v = nodes.filter(n => n.status === 'validated'); const main = v.filter(n => !n.independent); const pick = main.length ? main : v;
  return pick.sort((a, b) => (b.depth || 1) - (a.depth || 1))[0] || null;
}
function treeCard(n, isRoot) {
  const d = el('div', 'node ' + stKey(n.status) + (isRoot ? ' root' : '')); const nh = el('div', 'nh'); nh.append(el('span', 'id', n.id));
  if (isRoot) nh.append(el('span', 'pill rc', 'Root cause')); nh.append(statusPill(n.status)); if (n.independent) nh.append(el('span', 'pill', 'Separate fault')); nh.append(el('span', 'sp'));
  const meta = [n.tool_calls ? `${n.tool_calls} tool call${n.tool_calls > 1 ? 's' : ''}` : '', n.seconds ? `${n.seconds} s` : ''].filter(Boolean).join(' · '); if (meta) nh.append(el('span', null, meta));
  d.append(nh, el('div', null, n.statement || '')); if (n.finding) d.append(el('div', 'fd', n.finding));
  const seen = n.last_seen_min != null && n.last_seen_min !== '' && Number(n.last_seen_min) >= 0;
  [n.component && n.component !== 'none' ? `Component: ${n.component}` : '', seen ? `Signal last seen: ${Number(n.last_seen_min) === 0 ? 'in the latest data' : n.last_seen_min + ' min ago'}` : '', n.test_plan && n.status === 'open' ? `Test: ${n.test_plan}` : '']
    .filter(Boolean).forEach(t => d.append(el('div', 'ck', t)));
  (n.checks || []).forEach(c => { const good = /^corroborated/.test(c); const k = el('div', 'ck ' + (good ? 'good' : 'bad')); const m = el('b', null, good ? '' : '! '); if (good) m.append(ic('check'), ' '); k.append(m, 'Code check: ' + c); d.append(k); });
  const known = (id) => tree.evidence.find(x => x.evidence_id === id) || {};
  const ev = (n.evidence || []).length ? n.evidence : (n.evidence_ids || []).map(id => ({ evidence_id: id }));
  ev.forEach(v => { const k = known(v.evidence_id), r = el('div', 'evd'); r.append(el('span', 'sig', v.signal || k.signal || 'source'), el('span', null, v.finding || k.finding || v.evidence_id || '')); d.append(r); });
  return d;
}
function statusPill(status) { const p = el('span', 'pill ' + stKey(status)); if (STATUS_ICON[status]) p.append(ic(STATUS_ICON[status]), ' '); p.append(STATUS_LABEL[status] || status || 'Inconclusive'); return p; }

// ---- Hypothesis tree canvas. Every node lives in one transformed layer (#tree) and is updated in place, keyed by its id (a rebuild
// would lose clicks and restart animations); the camera (makeCanvas below) is a CSS transform. Follow mode fits the view to the nodes being worked on.
// Motion as measured from a reference recording (27 Nov 2026): smooth-zoom path, cubic ease-out, 500 ms, zoom never above 1.
const CV = $('#cv'), WORLD = $('#tree'), EMPTY = $('#treeempty'), REDUCED = window.matchMedia('(prefers-reduced-motion: reduce)');
const KMIN = 0.2, KMAX = 1.5, OPEN_K = 0.62, MOVE_MS = 500, SETTLE_MS = 700;
const TREECAM = makeCanvas(CV, WORLD, { user: () => userMoved(), moved: () => markSection(), fitAll: () => { setMode('all'); fitTo([WORLD], MOVE_MS); },
  insets: () => { const D = $('#detail'), under = D.hidden ? $('#legend').offsetHeight : D.offsetHeight; return [16, 64, $('#secs').offsetHeight + 24, under ? under + 16 : 16]; } });   // room for the chips above, the legend or the node card below and the controls on the right
const cam = TREECAM.cam, applyCam = TREECAM.apply, camTo = TREECAM.to, boxOf = TREECAM.boxOf, fitTo = TREECAM.fit, zoomBy = TREECAM.zoomBy;
// mode: open = a stored case as first shown (alert and hypotheses, readable) · all = whole tree in view · follow = track the work · free = moved by the user · rest = left where the run ended
const tv = { els: new Map(), touched: new Set(), investigating: false, mode: 'all', goal: null, settle: 0, settleTimer: 0, timer: 0, sel: null, grew: false, focus: null, drawTimer: 0 };
const TOP_UL = el('ul'), ROOT_LI = el('li'), ALERT_B = el('button', 'bx alert'), PH = el('div', 'ph'), CONC = el('div', 'cc'), NEXT = el('div', 'cc next');
ALERT_B.type = 'button'; ALERT_B.setAttribute('aria-pressed', 'false'); ALERT_B.onclick = () => showNode('', true);
const SVGNS = 'http://www.w3.org/2000/svg', RPATH = document.createElementNS(SVGNS, 'svg'), RP = document.createElementNS(SVGNS, 'path'); RPATH.id = 'rpath'; RPATH.setAttribute('aria-hidden', 'true'); RPATH.append(RP);
ROOT_LI.append(ALERT_B); TOP_UL.append(ROOT_LI); PH.append(el('i'), 'Investigating…'); PH.hidden = CONC.hidden = NEXT.hidden = true;
CONC.setAttribute('role', 'group'); CONC.setAttribute('aria-label', 'Conclusion'); NEXT.setAttribute('role', 'group'); NEXT.setAttribute('aria-label', 'Next steps');
WORLD.append(TOP_UL, RPATH, PH, CONC, NEXT);
const SECS = [['alert', 'Alert', () => [ALERT_B]], ['hyp', 'Hypotheses', () => [...tv.els.values()].map(v => v.b)], ['conc', 'Conclusion', () => CONC.hidden ? [] : [CONC]], ['next', 'Next steps', () => NEXT.hidden ? [] : [NEXT]]];
SECS.forEach(([key, label, els]) => { const b = el('button', null, label); b.type = 'button'; b.dataset.sec = key; b.onclick = () => { userMoved(); fitTo(els(), MOVE_MS); }; $('#secs').append(b); });
const CTL = {};
[['zin', 'plus', 'Zoom in', () => { userMoved(); zoomBy(1.25, 200); }], ['zout', 'minus', 'Zoom out', () => { userMoved(); zoomBy(0.8, 200); }],
  ['zfit', 'maximize', 'Fit the whole tree', () => { setMode('all'); fitTo([WORLD], MOVE_MS); }],
  ['zfollow', 'current-location', 'Follow the investigation', () => { if (tv.mode === 'follow') setMode('free'); else { setMode('follow'); aim(MOVE_MS); } }]]
  .forEach(([id, icon, label, fn]) => { const b = el('button'); b.type = 'button'; b.id = id; b.title = label; b.setAttribute('aria-label', label); b.append(ic(icon)); b.onclick = fn; CTL[id] = b; $('#cvc').append(b); });

function zoomPath(p0, p1) {   // van Wijk and Nuij "smooth and efficient zooming and panning" between two views [cx, cy, width]; rho = sqrt 2 (the d3.interpolateZoom formula)
  const rho = Math.SQRT2, [ux0, uy0, w0] = p0, [ux1, uy1, w1] = p1, dx = ux1 - ux0, dy = uy1 - uy0, d2 = dx * dx + dy * dy;
  if (d2 < 1e-12) { const S = Math.log(w1 / w0) / rho; return (t) => [ux0 + t * dx, uy0 + t * dy, w0 * Math.exp(rho * t * S)]; }
  const d1 = Math.sqrt(d2), b0 = (w1 * w1 - w0 * w0 + 4 * d2) / (2 * w0 * 2 * d1), b1 = (w1 * w1 - w0 * w0 - 4 * d2) / (2 * w1 * 2 * d1);
  const r0 = Math.log(Math.sqrt(b0 * b0 + 1) - b0), r1 = Math.log(Math.sqrt(b1 * b1 + 1) - b1), S = (r1 - r0) / rho, c0 = Math.cosh(r0);
  return (t) => { const s = t * S, u = w0 / (2 * d1) * (c0 * Math.tanh(rho * s + r0) - Math.sinh(r0)); return [ux0 + u * dx, uy0 + u * dy, w0 * c0 / Math.cosh(rho * s + r0)]; };
}
// ---- One pan-and-zoom canvas, used by the hypothesis tree and by the service map: cv clips, world is the one transformed layer (the camera is a CSS transform).
// o.insets() is the room to keep clear, [left, right, top, bottom]; o.user() runs when the reader takes the view; o.moved() after a move settles; o.fitAll() answers the 0 key.
function makeCanvas(cv, world, o) {
  const cam = { x: 0, y: 0, k: 1, raf: 0 }; let drag = null, swallow = false;
  const apply = () => { world.style.transform = `translate(${cam.x}px,${cam.y}px) scale(${cam.k})`; };
  function move(to, ms) {   // a new move cancels the running one and starts from the current view
    cancelAnimationFrame(cam.raf); cam.raf = 0;
    const W = cv.clientWidth, Hh = cv.clientHeight;
    if (!ms || REDUCED.matches || !W || !Hh) { cam.x = to.x; cam.y = to.y; cam.k = to.k; apply(); o.moved(); return; }
    const px = W / 2, py = Hh / 2, w = Math.max(W, Hh), path = zoomPath([(px - cam.x) / cam.k, (py - cam.y) / cam.k, w / cam.k], [(px - to.x) / to.k, (py - to.y) / to.k, w / to.k]), start = performance.now();
    const step = (now) => { const t = Math.min(1, Math.max(0, (now - start) / ms)), l = path(1 - Math.pow(1 - t, 3)), k = w / l[2];
      cam.k = k; cam.x = px - l[0] * k; cam.y = py - l[1] * k;
      if (t < 1) { apply(); cam.raf = requestAnimationFrame(step); } else { cam.raf = 0; cam.x = to.x; cam.y = to.y; cam.k = to.k; apply(); o.moved(); } };
    cam.raf = requestAnimationFrame(step);
  }
  function boxOf(els) {   // bounding box of the given elements in the layer's own coordinates
    const wr = world.getBoundingClientRect(), k = (wr.width / world.offsetWidth) || 1; let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    els.forEach(n => { if (!n || !n.isConnected) return; const r = n.getBoundingClientRect(); if (!r.width && !r.height) return;
      x0 = Math.min(x0, (r.left - wr.left) / k); y0 = Math.min(y0, (r.top - wr.top) / k); x1 = Math.max(x1, (r.right - wr.left) / k); y1 = Math.max(y1, (r.bottom - wr.top) / k); });
    return x0 === Infinity ? null : { x: x0, y: y0, w: Math.max(1, x1 - x0), h: Math.max(1, y1 - y0) };
  }
  function fit(els, ms, floor, cap) {   // never closer than 1:1 (or cap); small padding; with a floor the view stays readable and starts at the top of what does not fit
    const b = boxOf(els), W = cv.clientWidth, Hh = cv.clientHeight; if (!b || !W || !Hh) return;
    const [il, ir, it, ib] = o.insets(), w = Math.max(40, W - il - ir), h = Math.max(40, Hh - it - ib);
    const f = Math.min(1, w / b.w, h / b.h), k = Math.min(cap || 1, Math.max(floor || KMIN, f));
    move({ k, x: il + w / 2 - k * (b.x + b.w / 2), y: k > f && k * b.h > h ? it - k * b.y : it + h / 2 - k * (b.y + b.h / 2) }, ms);
  }
  function zoomBy(f, ms, px, py) { const W = cv.clientWidth, Hh = cv.clientHeight; if (px == null) { px = W / 2; py = Hh / 2; }
    const k = Math.max(KMIN, Math.min(KMAX, cam.k * f)), r = k / cam.k; move({ k, x: px - (px - cam.x) * r, y: py - (py - cam.y) * r }, ms); }
  // pointer, wheel and keyboard: any of them hands the view to the reader
  cv.addEventListener('pointerdown', (ev) => { if (ev.button !== 0 || ev.target.closest('.cvc,.secs,.detail')) return; drag = { id: ev.pointerId, x: ev.clientX, y: ev.clientY, cx: cam.x, cy: cam.y, on: false }; });
  cv.addEventListener('pointermove', (ev) => { const d = drag; if (!d || ev.pointerId !== d.id) return; const dx = ev.clientX - d.x, dy = ev.clientY - d.y;
    if (!d.on) { if (Math.hypot(dx, dy) < 5) return; d.on = true; o.user(); d.cx = cam.x; d.cy = cam.y; try { cv.setPointerCapture(d.id); } catch (x) { /* pointer already gone */ } cv.classList.add('drag'); }
    cam.x = d.cx + dx; cam.y = d.cy + dy; apply(); });
  const endDrag = (ev) => { const d = drag; if (!d || ev.pointerId !== d.id) return; drag = null; if (!d.on) return; cv.classList.remove('drag'); swallow = true; setTimeout(() => { swallow = false; }, 0); o.moved(); };
  cv.addEventListener('pointerup', endDrag); cv.addEventListener('pointercancel', endDrag);
  cv.addEventListener('click', (ev) => { if (swallow) { ev.stopPropagation(); ev.preventDefault(); } }, true);   // a drag that ends on a box is not a click on it
  cv.addEventListener('wheel', (ev) => { if (world.hidden || ev.target.closest('.detail')) return; ev.preventDefault(); o.user(); const r = cv.getBoundingClientRect();
    zoomBy(Math.exp(-ev.deltaY * (ev.deltaMode === 1 ? 0.05 : 0.002) * (ev.ctrlKey ? 4 : 1)), 0, ev.clientX - r.left, ev.clientY - r.top); }, { passive: false });
  cv.addEventListener('keydown', (ev) => { if (ev.target !== cv || world.hidden || ev.metaKey || ev.ctrlKey || ev.altKey) return;
    const pan = { ArrowLeft: [64, 0], ArrowRight: [-64, 0], ArrowUp: [0, 64], ArrowDown: [0, -64] }[ev.key];
    if (pan) { o.user(); move({ k: cam.k, x: cam.x + pan[0], y: cam.y + pan[1] }, 0); } else if (ev.key === '+' || ev.key === '=') { o.user(); zoomBy(1.25, 200); } else if (ev.key === '-') { o.user(); zoomBy(0.8, 200); }
    else if (ev.key === '0') o.fitAll(); else return; ev.preventDefault(); });
  cv.addEventListener('scroll', () => { cv.scrollTop = 0; cv.scrollLeft = 0; });   // focusing a box must not scroll the clipped area under the camera
  world.addEventListener('focusin', (ev) => {   // keyboard focus on a box outside the view brings it in
    const b = ev.target.closest('.bx,.sv'); if (!b || !b.matches(':focus-visible')) return; const r = b.getBoundingClientRect(), c = cv.getBoundingClientRect();
    const dx = r.left < c.left + 8 ? c.left + 8 - r.left : r.right > c.right - 8 ? c.right - 8 - r.right : 0, dy = r.top < c.top + 8 ? c.top + 8 - r.top : r.bottom > c.bottom - 8 ? c.bottom - 8 - r.bottom : 0;
    if (dx || dy) { o.user(); move({ k: cam.k, x: cam.x + dx, y: cam.y + dy }, 200); } });
  return { cam, apply, to: move, boxOf, fit, zoomBy };
}
function activeEls() {   // what follow mode frames: the nodes that just appeared, their parent and the placeholder; with nothing new, the ones still being researched
  const ids = new Set(tv.touched); if (!ids.size) tree.nodes.forEach(n => { if (n.status === 'open') ids.add(n.id); });
  const out = new Set(); ids.forEach(id => { const v = tv.els.get(id); if (!v) return; out.add(v.b); const n = tree.nodes.find(x => x.id === id), p = n && tv.els.get(n.parent); out.add(p ? p.b : ALERT_B); });
  if (!out.size) out.add(ALERT_B); if (!PH.hidden) out.add(PH);
  return [...out];
}
function drawPath() {   // one solid amber line from the alert down to the root cause, over the grey connectors (parent bottom, 24px stem, across, 24px drop)
  const root = rootNode(tree.nodes.slice()), chain = []; for (let n = root; n; n = tree.nodes.find(x => x.id === n.parent)) chain.unshift(n.id);
  let d = '', prev = ALERT_B;
  chain.forEach(id => { const v = tv.els.get(id), a = prev && boxOf([prev]), b = v && boxOf([v.b]); if (!a || !b) { prev = null; return; }
    d += `M${(a.x + a.w / 2).toFixed(1)},${(a.y + a.h).toFixed(1)}V${(b.y - 24).toFixed(1)}H${(b.x + b.w / 2).toFixed(1)}V${b.y.toFixed(1)}`; prev = v.b; });
  const leaf = root && prev && prev !== ALERT_B && !tree.nodes.some(n => n.parent === root.id), a = leaf && !CONC.hidden && boxOf([prev]), c = a && boxOf([CONC]);   // a leaf root cause runs on into the conclusion
  if (c) d += `M${(a.x + a.w / 2).toFixed(1)},${(a.y + a.h).toFixed(1)}V${(c.y - 16).toFixed(1)}H${(c.x + c.w / 2).toFixed(1)}V${c.y.toFixed(1)}`;
  CONC.classList.toggle('linked', !!c); RP.setAttribute('d', d);
}
function aim(ms) {   // put the camera where the current mode wants it
  if (WORLD.hidden || !CV.clientWidth) return; drawPath();
  if (tv.goal === 'answer') { tv.goal = null; if (!CONC.hidden && tv.mode !== 'free') { fitTo([CONC, NEXT.hidden ? null : NEXT], ms); return; } }   // a run just ended: show the answer once
  if (tv.mode === 'follow' && tv.investigating) {   // a new frame only when the tree grew; a resize or the follow button re-frames the same nodes
    if (tv.grew || !tv.focus || tv.focus.some(n => !n.isConnected)) tv.focus = activeEls();
    tv.grew = false; tv.touched.clear(); fitTo(tv.focus, ms); }
  else if (tv.mode === 'all') fitTo([WORLD], ms);
  else if (tv.mode === 'open') {   // the whole tree with its conclusion fits only at about 0.4, too small to read: open on the path to the root cause
    const chain = []; for (let n = rootNode(tree.nodes.slice()); n; n = tree.nodes.find(x => x.id === n.parent)) chain.push(n.id);
    const on = (chain.length ? chain : tree.nodes.map(n => n.id)).map(id => tv.els.get(id)).filter(Boolean).map(v => v.b);
    fitTo([ALERT_B, ...on], ms, OPEN_K);
  }
}
function aimSoon(instant) {   // events come in bursts: measure once, after layout
  clearTimeout(tv.timer); tv.timer = setTimeout(() => requestAnimationFrame(() => aim(instant || performance.now() < tv.settle ? 0 : MOVE_MS)), 60);
}
function setMode(m) { tv.mode = m; CTL.zfollow.setAttribute('aria-pressed', String(m === 'follow')); CTL.zfollow.disabled = !tv.investigating && m !== 'follow';
  CTL.zfollow.title = tv.investigating || m === 'follow' ? (m === 'follow' ? 'Following the investigation (click to stop)' : 'Follow the investigation') : 'Follow is available while an investigation runs'; }
function userMoved() { cancelAnimationFrame(cam.raf); cam.raf = 0; clearTimeout(tv.timer); if (tv.mode !== 'free') setMode('free'); }
function setInvestigating(on) {   // a run starts with follow on; when it ends the view stays where it is and follow switches off
  if (tv.investigating === on) return; tv.investigating = on; PH.hidden = !on;
  if (on) { tv.grew = true; tv.focus = null; setMode('follow'); } else { if (tv.mode === 'follow') { tv.goal = briefData ? 'answer' : null; setMode('rest'); } else setMode(tv.mode); }
  drawTree(); aimSoon(); mapSoon();
}
function markSection() {   // the chip of the part nearest the middle of the view
  const c = CV.getBoundingClientRect(), mx = c.left + c.width / 2, my = c.top + c.height / 2; let best = null, bd = Infinity;
  SECS.forEach(([key, , els]) => { const list = els().filter(n => n && n.isConnected && !n.hidden); const b = $(`#secs [data-sec=${key}]`); b.disabled = !list.length || WORLD.hidden; if (b.disabled) return;
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity; list.forEach(n => { const r = n.getBoundingClientRect(); x0 = Math.min(x0, r.left); y0 = Math.min(y0, r.top); x1 = Math.max(x1, r.right); y1 = Math.max(y1, r.bottom); });
    const d = Math.hypot(Math.max(x0 - mx, 0, mx - x1), Math.max(y0 - my, 0, my - y1)) + Math.hypot((x0 + x1) / 2 - mx, (y0 + y1) / 2 - my) / 1e3; if (d < bd) { bd = d; best = key; } });
  document.querySelectorAll('#secs button').forEach(b => { if (b.dataset.sec === best && !b.disabled) b.setAttribute('aria-current', 'true'); else b.removeAttribute('aria-current'); });
}
function showNode(id, byUser) {   // the node's card, a sheet over the bottom of the canvas (evidence, code checks); '' is the alert, null closes it
  const D = $('#detail'), root = rootNode(tree.nodes.slice()); tv.sel = id;
  WORLD.querySelectorAll('.bx').forEach(x => x.setAttribute('aria-pressed', 'false'));
  const n = id ? tree.nodes.find(x => x.id === id) : null, v = id ? tv.els.get(id) : null;
  if (id == null || (id !== '' && (!n || !v))) { tv.sel = null; D.hidden = true; D.replaceChildren(); CV.classList.remove('has-detail'); return; }
  const head = el('div', 'lab', id === '' ? 'Selected: alert' : `Selected: ${n.id}`), x = el('button', null, 'Close'); x.type = 'button'; x.onclick = () => showNode(null); head.append(x);
  if (id === '') { ALERT_B.setAttribute('aria-pressed', 'true'); const a = tree.alert || {}, d = el('div', 'node'); d.append(el('div', 'nh', a.since ? 'Alert since ' + a.since : 'Alert'), el('div', null, a.all || a.title || (current ? 'Case ' + current : ''))); D.replaceChildren(head, d); }
  else { v.b.setAttribute('aria-pressed', 'true'); D.replaceChildren(head, treeCard(n, !!root && n.id === root.id)); }
  D.hidden = false; CV.classList.add('has-detail');
  if (byUser) {   // keep the clicked node clear of the sheet
    const b = id === '' ? ALERT_B : v.b, r = b.getBoundingClientRect(), d = D.getBoundingClientRect(), top = CV.getBoundingClientRect().top + $('#secs').offsetHeight + 24;
    let dy = Math.min(0, d.top - 12 - r.bottom); if (r.top + dy < top) dy = top - r.top;
    if (Math.abs(dy) > 1) { userMoved(); camTo({ k: cam.k, x: cam.x, y: cam.y + dy }, 200); }
  }
}
function paintNode(v, n, isRoot) {
  const b = v.b, st = stKey(n.status); b.className = 'bx ' + st + (isRoot ? ' root' : ''); b.title = n.statement || '';
  const k = el('div', 'k'); k.append(el('span', 'id', n.id), statusPill(n.status)); if (isRoot) k.append(el('span', 'pill rc', 'Root cause')); else if (n.independent) k.append(el('span', 'pill', 'Separate fault'));
  if (n.seconds) k.append(el('span', 'when', `${n.seconds} s`));
  const kids = [k, el('div', 'tt', nb(firstSentence(n.statement)))]; if (n.component && n.component !== 'none') kids.push(el('div', 'm', n.component));
  b.replaceChildren(...kids);
}
function paintConclusion() {   // Conclusion and Next steps nodes from the investigation result; older cases lack the new fields, so each part falls back
  const e = briefData; CONC.hidden = !e; if (!e) { NEXT.hidden = true; return; }
  const pa = e.proposed_action, paType = (pa && pa.type) || pa || '', rationale = e.rationale || (pa && pa.rationale) || '';
  const mode = String(e.failure_mode || '').replace(/_/g, ' '), svc = e.root_cause_service && e.root_cause_service !== 'none' ? e.root_cause_service : '';
  const title = e.title || firstSentence(e.summary) || [svc, mode].filter(Boolean).join(', ') || 'No fault found';
  const cause = e.mechanism || (e.title ? e.summary : restSentences(e.summary)) || (e.cause_chain || []).join(' → ') || e.summary || 'Not stated.';
  const lb = el('div', 'lb'); lb.append(ic('bulb'), 'Conclusion');
  const two = el('div', 'two'), cell = (label, text) => { const c = el('div'); c.append(el('div', 'l2', label), el('p', null, text)); two.append(c); };
  cell('Root cause', cause); cell('Impact', e.impact || 'Not measured.');
  CONC.replaceChildren(lb, el('div', 'ct', nb(title)), two);
  const steps = (e.next_steps || []).filter(Boolean), list = steps.length ? steps : (rationale && !['no_action', 'inconclusive', ''].includes(String(paType)) ? [rationale] : []);
  NEXT.hidden = !list.length; if (!list.length) return;
  const nl = el('div', 'lb'); nl.append(ic('list-check'), 'Next steps'); const ol = el('div', 'steps'); ol.setAttribute('role', 'list');
  list.forEach((x, i) => { const row = el('span'); row.setAttribute('role', 'listitem'); if (steps.length > 1 && i === list.length - 1) { row.className = 'vf'; const v = el('span', 'pill validated'); v.append(ic('check'), 'Verify'); row.append(v); }   // the last step says how to check the fix worked
    row.append(String(x).replace(/^verify:\s*/i, '')); ol.append(el('span', 'no', `${i + 1}.`), row); });
  NEXT.replaceChildren(nl, ol);
}
function drawTree() {   // sync the layer with tree.nodes in place; returns nothing, moves the camera only when something changed
  const L = $('#legend'), N = $('#treenote'), has = !!(tree.nodes.length || tree.alert); let changed = WORLD.hidden === has, grew = changed;
  EMPTY.hidden = has; WORLD.hidden = !has; N.textContent = '';
  if (!has) { EMPTY.textContent = current ? 'The hypotheses appear here when the agent has written them. Follow the live steps under Agent trace.' : 'Open a case or press Triage on an alert to see its hypothesis tree.';
    tv.els.forEach(v => v.li.remove()); tv.els.clear(); tv.touched.clear(); tv.focus = null; showNode(null); CONC.hidden = NEXT.hidden = true; RP.setAttribute('d', ''); L.replaceChildren(); setMode(tv.mode); markSection(); return; }
  const a = tree.alert || {}, ak = el('div', 'k'), ah = el('b'); ah.append(ic('alert-triangle'), ' Alert'); ak.append(ah); if (a.since) ak.append(el('span', 'when', 'since ' + a.since));
  const akids = [ak, el('div', 'tt', nb(a.title || 'Case ' + (current || '')))]; if (a.more) akids.push(el('div', 'm', `+ ${a.more} grouped alert${a.more > 1 ? 's' : ''}`));
  const asig = JSON.stringify([a.title, a.since, a.more, current]); if (ALERT_B.dataset.sig !== asig) { ALERT_B.dataset.sig = asig; ALERT_B.title = a.all || ''; ALERT_B.replaceChildren(...akids); }
  const ids = new Set(tree.nodes.map(n => n.id));
  tv.els.forEach((v, id) => { if (!ids.has(id)) { v.li.remove(); tv.els.delete(id); tv.touched.delete(id); changed = true; } });   // dropped by a reset
  const root = rootNode(tree.nodes.slice()), path = new Set(); for (let n = root; n; n = tree.nodes.find(x => x.id === n.parent)) path.add(n.id);
  tree.nodes.slice().sort((x, y) => (x.depth || 1) - (y.depth || 1)).forEach(n => {   // parents first; the sort is stable, so siblings keep their order of arrival
    let v = tv.els.get(n.id);
    if (!v) { const li = el('li'), b = el('button', 'bx'), dr = el('i', 'dr'); b.type = 'button'; b.dataset.node = n.id; b.setAttribute('aria-pressed', 'false'); b.onclick = () => showNode(n.id, true); li.append(dr, b);
      const host = (tv.els.get(n.parent) || {}).li || ROOT_LI; let ul = host.querySelector(':scope > ul'); if (!ul) { ul = el('ul'); host.append(ul); } ul.append(li);
      v = { li, b, sig: '', status: null }; tv.els.set(n.id, v); tv.touched.add(n.id); changed = grew = true; }
    const isRoot = !!root && n.id === root.id, sig = JSON.stringify([n.status, n.statement, isRoot, n.seconds, n.tool_calls, n.independent, n.component]);
    if (v.sig !== sig) { paintNode(v, n, isRoot); v.sig = sig; v.status = n.status; changed = true; }   // a verdict repaints the node where it is; the camera stays
    v.li.className = n.status === 'open' ? 'open' : n.status === 'invalidated' && !path.has(n.id) ? 'out' : '';
  });
  WORLD.querySelectorAll('ul').forEach(u => { if (u !== TOP_UL && !u.children.length) u.remove(); });
  const wasConc = !CONC.hidden, csig = briefData ? JSON.stringify([briefData.case_id, briefData.title, briefData.summary, briefData.mechanism, briefData.impact, briefData.next_steps, briefData.rationale, briefData.proposed_action]) : '';
  if (CONC.dataset.sig !== csig) { CONC.dataset.sig = csig; paintConclusion(); changed = true; } if (wasConc !== !CONC.hidden) changed = grew = true;
  if (tree.method === 'loop') N.textContent = 'This case was stored without a hypothesis ledger, so its hypotheses are shown one level deep.';
  L.replaceChildren(); const line = el('span'), li_ = el('i'); li_.className = 'line'; line.append(li_, 'path to the root cause'); if (root) L.append(line);
  Object.keys(STATUS_LABEL).forEach(k => { const c = tree.nodes.filter(n => (n.status || 'inconclusive') === k).length; if (c) { const s = el('span'); s.append(statusPill(k), ` ${c}`); L.append(s); } });
  if (tv.sel != null) showNode(tv.sel === '' || ids.has(tv.sel) ? tv.sel : null);   // refresh the open card with the node's latest data
  drawPath(); setMode(tv.mode); markSection(); if (grew) tv.grew = true; if (grew || (changed && tv.mode !== 'follow')) aimSoon();
}
function setAlert(detectors, since) { const ds = [...new Set((detectors || []).map(short))]; if (ds.length) tree.alert = { title: ds[0], more: ds.length - 1, all: ds.join(' + '), since: hhmm(since) }; }
// ---- Service map (Topology tab). The layout is computed here, callers on the left and callees on the right, and drawn once per map; after that every box is
// updated in place, so a status that arrives never moves anything. Status comes only from this case: its alerts, its hypotheses and evidence and, once the run
// has ended, its root cause. The map itself is the console's cached copy (/api/topology): this page never asks the gateway, and it shows no injected-fault names.
const SVC = {   // the picture and the role of each service, in plain words
  'checkout-api': ['credit-card', 'Takes payment requests'], 'risk-engine': ['shield', 'Scores fraud risk'], 'payment-router': ['arrows-split-2', 'Picks the acquirer'],
  'acquirer-sim': ['building-bank', 'The acquiring banks'], 'ledger': ['book-2', 'Records every payment'], 'wallet-sim': ['wallet', 'Wallets, agent mandates'],
  'merchant-copilot': ['message-chatbot', 'Merchant AI assistant'], 'webhook-dispatcher': ['webhook', 'Notifies merchants'], 'merchant-sim': ['building-store', 'Simulated merchants'],
  'shopping-agent': ['shopping-cart', 'AI agent that shops'] };
const SVC_LABEL = { root: 'Root cause', alert: 'Alerting', suspect: 'Suspected', ok: 'Cleared', seen: 'In evidence', next: 'Check next', na: 'No evidence' };
const SVC_PILL = { root: ['rc'], alert: ['alerting', 'alert-triangle'], suspect: ['open', 'search'], ok: ['validated', 'check'], seen: [''], next: ['', 'search'], na: ['nottested'] };
const MCV = $('#mcv'), MAPW = $('#map'), MEMPTY = $('#mapempty');
const BW = 180, BH = 120, GX = 72, GV = 56, GY = 12, MPAD = 8, WAYH = 20, ARW = 7, MAP_FLOOR = 0.6;
const MAP_VERT = true;   // a tree from the top down at every width, like the hypothesis tree (27 Nov 2026); false lays it left to right again
const mv = { sig: '', lay: null, model: null, els: new Map(), sel: null, up: false, free: false, all: false, focus: null, legend: 0, timer: 0, aimTimer: 0 };
let svcStats = {}, caseDets = [];
function mapLayout(edges, vert) {   // layered by the longest call chain: callers above, what they call below (vert), or left to right; an edge that skips a layer gets a waypoint in it, so no line runs under a box
  const names = new Set(Object.keys(edges)); Object.values(edges).forEach(v => (v || []).forEach(x => names.add(x)));
  const N = [...names].sort(), out = {}; N.forEach(n => { out[n] = [...new Set(edges[n] || [])].filter(x => x !== n).sort(); });
  // a call back up the chain would loop the layering: that edge is laid out reversed and its arrow drawn the true way
  const seen = {}, back = new Set(), visit = (n) => { seen[n] = 1; out[n].forEach(m => { if (seen[m] === 1) back.add(n + '>' + m); else if (!seen[m]) visit(m); }); seen[n] = 2; };
  [...N.filter(n => !N.some(a => out[a].includes(n))), ...N].forEach(n => { if (!seen[n]) visit(n); });
  const links = new Map();   // one drawn connection per pair: a is its first end, b its second; fwd and rev say which way the calls go
  N.forEach(a => out[a].forEach(b => { const rev = back.has(a + '>' + b), l = rev ? b : a, r = rev ? a : b, L = links.get(l + '>' + r) || { a: l, b: r, fwd: false, rev: false }; if (rev) L.rev = true; else L.fwd = true; links.set(l + '>' + r, L); }));
  const col = {}; N.forEach(n => { col[n] = 0; });
  for (let i = 0; i < N.length; i++) links.forEach(L => { if (col[L.b] < col[L.a] + 1) col[L.b] = col[L.a] + 1; });
  const cols = []; N.forEach(n => { (cols[col[n]] = cols[col[n]] || []).push(n); });
  const way = {}, ins = {}, outs = {}, hop = (a, b) => { (outs[a] = outs[a] || []).push(b); (ins[b] = ins[b] || []).push(a); };
  links.forEach(L => { L.via = [L.a]; for (let c = col[L.a] + 1; c < col[L.b]; c++) { const w = `${L.a}>${L.b}#${c}`; way[w] = 1; col[w] = c; cols[c].push(w); L.via.push(w); }
    L.via.push(L.b); for (let i = 1; i < L.via.length; i++) hop(L.via[i - 1], L.via[i]); });
  // order inside each layer: the average position of the neighbours, a few sweeps each way (fewer crossings); services nothing connects to go last
  const pos = {}, index = () => cols.forEach(c => c.forEach((n, i) => { pos[n] = i; })); index();
  const order = (c, nb) => { const key = {}; c.forEach((n, i) => { const l = nb[n] || []; key[n] = l.length ? l.reduce((s, x) => s + pos[x], 0) / l.length : (ins[n] || outs[n]) ? i : 1e6 + i; });
    c.sort((p, q) => key[p] - key[q] || pos[p] - pos[q]); index(); };
  for (let i = 0; i < 4; i++) { for (let c = 1; c < cols.length; c++) order(cols[c], ins); for (let c = cols.length - 2; c >= 0; c--) order(cols[c], outs); }
  // then two neighbours in a layer swap places while that removes a crossing, or shortens the lines without adding one
  const hops = []; Object.keys(outs).forEach(a => outs[a].forEach(b => hops.push([a, b])));
  const cost = () => { let x = 0, d = 0; hops.forEach(([a, b], i) => { d += Math.abs(pos[a] - pos[b]); for (let j = 0; j < i; j++) { const [c, e] = hops[j]; if (col[a] === col[c] && (pos[a] - pos[c]) * (pos[b] - pos[e]) < 0) x++; } }); return x * 1000 + d; };
  const swap = (c, i) => { [c[i], c[i + 1]] = [c[i + 1], c[i]]; pos[c[i]] = i; pos[c[i + 1]] = i + 1; };
  for (let n = 0, again = true; again && n < 20; n++) { again = false; cols.forEach(c => { for (let i = 0; i + 1 < c.length; i++) { const was = cost(); swap(c, i); if (cost() < was) again = true; else swap(c, i); } }); }
  // "along" is the direction the calls flow in, "across" the other one. The longest layer sets the grid; every other box sits as near
  // as it can to the boxes it connects to (a line passing through on its way elsewhere counts only when there is no box), so most lines run straight
  const SA = vert ? BH : BW, GA = vert ? GV : GX, size = (n) => way[n] ? WAYH : vert ? BW : BH, len = (c) => c.reduce((s, n) => s + size(n), 0) + GY * (c.length - 1), ac = {};
  let anchor = 0; cols.forEach((c, i) => { if (len(c) > len(cols[anchor])) anchor = i; });
  const place = (c, nb) => { let top = MPAD; c.forEach(n => { const all = (nb && nb[n]) || [], real = all.filter(x => !way[x]), l = real.length ? real : all, want = l.length ? l.reduce((s, x) => s + ac[x] + size(x) / 2, 0) / l.length - size(n) / 2 : top; ac[n] = Math.max(top, want); top = ac[n] + size(n) + GY; }); };
  place(cols[anchor], null); for (let c = anchor + 1; c < cols.length; c++) place(cols[c], ins); for (let c = anchor - 1; c >= 0; c--) place(cols[c], outs);
  let across = 0; cols.forEach(c => c.forEach(n => { across = Math.max(across, ac[n] + size(n)); })); across += MPAD;
  const along = MPAD * 2 + cols.length * SA + (cols.length - 1) * GA, al = (n) => MPAD + col[n] * (SA + GA);
  // lines: right angles only. In each gap a caller gets its own lane for the run across; a caller that lines up with another caller's
  // callee takes a lane before that caller's, so its way out never runs along the other's way in
  const mid = (n) => ac[n] + size(n) / 2, route = {};
  for (let g = 0; g < cols.length - 1; g++) {
    const a0 = MPAD + g * (SA + GA) + SA, a1 = a0 + GA, callers = cols[g].filter(a => (outs[a] || []).some(b => Math.abs(mid(b) - mid(a)) > 0.5)), first = {}; callers.forEach(a => { first[a] = new Set(); });
    callers.forEach(u => (outs[u] || []).forEach(v => callers.forEach(w => { if (w !== u && Math.abs(mid(w) - mid(v)) < 0.5 && !(outs[w] || []).includes(v)) first[u].add(w); })));
    const lane = [], left = new Set(callers); while (left.size) { const pick = [...left].find(a => ![...first[a]].some(b => left.has(b))) || [...left][0]; lane.push(pick); left.delete(pick); }
    cols[g].forEach(a => (outs[a] || []).forEach(b => { const i = lane.indexOf(a), la = i < 0 ? (a0 + a1) / 2 : a0 + (i + 1) * GA / (lane.length + 1); route[a + '>' + b] = [[a0, mid(a)], [la, mid(a)], [la, mid(b)], [a1, mid(b)]]; }));
  }
  const f1 = (v) => v.toFixed(1), xy = (q) => vert ? [q[1], q[0]] : q, rounded = (pts) => {   // corners rounded by up to 10px, after dropping repeated points
    const p = pts.map(xy).filter((q, i, all) => !i || Math.abs(q[0] - all[i - 1][0]) > 0.5 || Math.abs(q[1] - all[i - 1][1]) > 0.5)
      .filter((q, i, all) => !i || i === all.length - 1 || Math.abs((q[0] - all[i - 1][0]) * (all[i + 1][1] - q[1]) - (q[1] - all[i - 1][1]) * (all[i + 1][0] - q[0])) > 0.01);   // and points on a straight run
    let d = `M${f1(p[0][0])},${f1(p[0][1])}`;
    for (let i = 1; i < p.length - 1; i++) { const a = p[i - 1], b = p[i], c = p[i + 1], la = Math.hypot(b[0] - a[0], b[1] - a[1]), lc = Math.hypot(c[0] - b[0], c[1] - b[1]), k = Math.min(10, la / 2, lc / 2);
      d += `L${f1(b[0] + (a[0] - b[0]) * k / la)},${f1(b[1] + (a[1] - b[1]) * k / la)}Q${f1(b[0])},${f1(b[1])} ${f1(b[0] + (c[0] - b[0]) * k / lc)},${f1(b[1] + (c[1] - b[1]) * k / lc)}`; }
    const z = p[p.length - 1]; return d + `L${f1(z[0])},${f1(z[1])}`; };
  links.forEach(L => { const pts = []; for (let i = 1; i < L.via.length; i++) route[L.via[i - 1] + '>' + L.via[i]].forEach(q => pts.push(q.slice()));
    if (L.rev) pts[0][0] += ARW; if (L.fwd) pts[pts.length - 1][0] -= ARW; L.d = rounded(pts); });   // room for the arrowhead at the callee's end
  const x = {}, y = {}; N.forEach(n => { x[n] = vert ? ac[n] : al(n); y[n] = vert ? al(n) : ac[n]; });
  return { N, out, vert, cols: cols.map(c => c.filter(n => !way[n])), x, y, W: vert ? across : along, H: vert ? along : across, links: [...links.values()] };
}
const svgEl = (tag, attrs) => { const n = document.createElementNS(SVGNS, tag); Object.entries(attrs || {}).forEach(([k, v]) => n.setAttribute(k, v)); return n; };
function buildMap(g) {   // boxes and lines for one map; called again only when the map itself changes
  const lay = mv.lay = mapLayout(g.edges || {}, MAP_VERT); mv.els.clear(); mv.model = null; showSvc(null);
  const svg = svgEl('svg', { id: 'medges', 'aria-hidden': 'true' }), defs = svgEl('defs');
  [['mk', 'mk'], ['mk-on', 'mk on']].forEach(([id, cls]) => { const m = svgEl('marker', { id, class: cls, viewBox: '0 0 10 10', markerWidth: 10, markerHeight: 10, markerUnits: 'userSpaceOnUse', refX: 2, refY: 5, orient: 'auto-start-reverse' }); m.append(svgEl('path', { d: 'M0,1L8,5L0,9z' })); defs.append(m); });
  svg.append(defs); lay.links.forEach(L => { L.el = svgEl('path', { class: 'me', d: L.d }); svg.append(L.el); });
  MAPW.replaceChildren(svg); MAPW.style.width = lay.W + 'px'; MAPW.style.height = lay.H + 'px';
  lay.cols.forEach(c => c.forEach(n => { const b = el('button', 'sv'); b.type = 'button'; b.dataset.svc = n; b.style.left = lay.x[n] + 'px'; b.style.top = lay.y[n] + 'px'; b.setAttribute('aria-pressed', 'false');
    b.onclick = () => showSvc(mv.sel === n ? null : n, true); MAPW.append(b); mv.els.set(n, { b, sig: null }); }));
}
const pct = (r) => { r = (Number(r) || 0) * 100; return r === 0 ? '0%' : r < 0.1 ? 'under 0.1%' : r.toFixed(1) + '%'; };
const pctShort = (r) => { r = (Number(r) || 0) * 100; return r === 0 ? '0%' : r < 0.1 ? '<0.1%' : r < 10 ? r.toFixed(1) + '%' : Math.round(r) + '%'; };   // short enough for one line of a box
function setStats(rows) { (Array.isArray(rows) ? rows : []).forEach(r => { if (r && r.service && r.requests != null) svcStats[r.service] = r; }); }   // every service's numbers, as the engine sends and stores them
function readSummary(text) {   // per-service numbers from the agent's own services summary: its preview is the first rows as JSON, cut off after 700 characters, so only whole rows count
  (String(text || '').match(/\{"service": ?"[^"]+"[^{}]*\}/g) || []).forEach(m => { try { const r = JSON.parse(m); if (r.service && r.requests != null) svcStats[r.service] = r; } catch (x) { /* a row cut in half */ } });
}
function mapModel() {   // what this case says about each service
  const e = briefData, lay = mv.lay, names = lay.N, nodes = tree.nodes || [];
  const rx = {}; names.forEach(n => { rx[n] = new RegExp('(^|[^a-z0-9-])' + n.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '($|[^a-z0-9-])', 'i'); });
  const says = (t, n) => rx[n].test(String(t || '')), compOf = (h) => String(h.component || '').split(/[\s\/,;:()]+/).find(t => names.includes(t)) || null;
  const rc = e && names.includes(e.root_cause_service) ? e.root_cause_service : null, alerting = names.filter(n => caseDets.some(d => says(short(d), n)));
  const nx = (e && e.topology && e.topology.check_next) || [], st = {}, used = {};
  names.forEach(n => { const comp = nodes.filter(h => compOf(h) === n), H = nodes.filter(h => compOf(h) === n || says(h.finding, n) || says(h.statement, n));
    const E = ((e && e.evidence) || []).filter(v => says(v.finding, n)), R = ((e && e.ruled_out) || []).filter(t => says(t, n)), N2 = nx.filter(v => v.service === n), alert = alerting.includes(n), s = svcStats[n] || null;
    const key = n === rc ? 'root' : alert ? 'alert' : !e && comp.some(h => h.status === 'validated') ? 'suspect' : R.length || (comp.length && comp.every(h => h.status === 'invalidated')) ? 'ok' : H.length || E.length ? 'seen' : N2.length ? 'next' : 'na';
    const count = H.length + E.length + R.length, facts = s ? (Number(s.requests) > 0 ? `${pctShort(s.error_rate)} errors, p90 ${fmtMs(s.p90_ms)}` : 'No requests in the window') : count ? `${count} mention${count > 1 ? 's' : ''} in this case` : '';
    st[n] = { key, alert, facts, stats: s, H, E, R, N2 }; used[key] = (used[key] || 0) + 1; });
  // the path follows the calls between the alerting service and the root cause, whichever of the two is upstream
  const find = (a, b) => { const q = [[a]], s = new Set([a]); while (q.length) { const p = q.shift(), h = p[p.length - 1]; if (h === b) return p; (lay.out[h] || []).forEach(v => { if (!s.has(v)) { s.add(v); q.push(p.concat(v)); } }); } return null; };
  const path = new Set(), on = new Set(); if (rc) alerting.forEach(a => { const p = a === rc ? null : find(a, rc) || find(rc, a); if (p) p.forEach((v, i) => { on.add(v); if (i) path.add(p[i - 1] + '>' + v); }); });
  const focus = on.size ? [...on] : rc ? [rc] : [...alerting.slice(0, 3), ...names.filter(n => st[n].key === 'suspect').slice(0, 2)];   // while the run goes on: the alert and what the agent suspects
  return { st, used, path, focus, primary: rc || alerting[0] || null };
}
function svcPills(s, one) {   // one: a box has room for a single pill, so a root cause that also raised the alert carries the alert's icon in its pill
  const mk = (k, icon = SVC_PILL[k][1]) => { const p = el('span', 'pill ' + SVC_PILL[k][0]); if (icon) p.append(ic(icon)); p.append(SVC_LABEL[k]); return p; };
  return s.key === 'root' && s.alert ? (one ? [mk('root', SVC_PILL.alert[1])] : [mk('root'), mk('alert')]) : [mk(s.key)];
}
function paintSvc(n, v, M) {   // one box, repainted where it is and only when what it shows changed
  const s = M.st[n], sig = JSON.stringify([s.key, s.alert, s.facts]); if (v.sig === sig) return; v.sig = sig;
  const meta = SVC[n] || ['server-2', ''], b = v.b; b.className = 'sv ' + s.key; b.title = [n, meta[1], s.key === 'root' && s.alert ? 'Root cause, and it raised the alert' : '', s.stats ? `${fmtK(s.stats.requests)} requests, ${fmtK(s.stats.errors)} errors` : ''].filter(Boolean).join('. ');
  const ti = el('span', 'ti'), tx = el('span', 'tx'), ps = el('span', 'ps'); ti.append(ic(meta[0])); tx.append(el('span', 'nm', nb(n)), el('span', 'ro', meta[1]), el('span', s.stats ? 'fx num' : 'fx', s.facts)); svcPills(s, true).forEach(p => ps.append(p));
  b.replaceChildren(ti, tx, ps);
}
const mapInsets = () => { const D = $('#tdetail'), card = D.hidden ? 0 : D.offsetHeight + 16, lg = $('#tlegend').offsetHeight; return [16, 64, card && mv.up ? card : 16, card && !mv.up ? card : lg ? lg + 16 : 16]; };   // clear of the legend and of the open card, whichever edge that is on
const MAPCAM = makeCanvas(MCV, MAPW, { insets: mapInsets, moved: () => {}, user: () => mapUserMoved(),
  fitAll: () => { mv.free = false; mv.all = true; MAPCAM.fit([MAPW], MOVE_MS); } });
[['mzin', 'plus', 'Zoom in', () => { mapUserMoved(); MAPCAM.zoomBy(1.25, 200); }], ['mzout', 'minus', 'Zoom out', () => { mapUserMoved(); MAPCAM.zoomBy(0.8, 200); }],
  ['mzfit', 'maximize', 'Fit the whole map', () => { mv.free = false; mv.all = true; MAPCAM.fit([MAPW], MOVE_MS); }]]
  .forEach(([id, icon, label, fn]) => { const b = el('button'); b.type = 'button'; b.id = id; b.title = label; b.setAttribute('aria-label', label); b.append(ic(icon)); b.onclick = fn; $('#mcvc').append(b); });
function mapUserMoved() { cancelAnimationFrame(MAPCAM.cam.raf); MAPCAM.cam.raf = 0; clearTimeout(mv.aimTimer); mv.free = true; mv.all = false; }
function aimMap(ms) {   // the whole map when it stays readable; on a small screen the path from the alert to the root cause, or just the box that matters most
  if (MAPW.hidden || !MCV.clientWidth || !mv.lay || mv.free) return;
  const [il, ir, it, ib] = mapInsets(), W = Math.max(40, MCV.clientWidth - il - ir), Hh = Math.max(40, MCV.clientHeight - it - ib), M = mv.model;
  if (mv.all || Math.min(1, W / mv.lay.W, Hh / mv.lay.H) >= MAP_FLOOR) { MAPCAM.fit([MAPW], ms); return; }
  const boxes = ((M && M.focus) || []).map(n => (mv.els.get(n) || {}).b).filter(Boolean), b = boxes.length ? MAPCAM.boxOf(boxes) : null;
  if (!b) MAPCAM.fit([MAPW], ms, MAP_FLOOR);
  else if (Math.min(1, W / b.w, Hh / b.h) >= MAP_FLOOR) MAPCAM.fit(boxes, ms);
  else MAPCAM.fit([(mv.els.get(M.primary) || { b: boxes[0] }).b], ms, 0, 0.8);
}
function aimMapSoon(ms) { clearTimeout(mv.aimTimer); mv.aimTimer = setTimeout(() => requestAnimationFrame(() => aimMap(ms)), 60); }
function mapSoon() { clearTimeout(mv.timer); mv.timer = setTimeout(drawMap, 80); }   // events come in bursts: one repaint
function loadMap() {   // the map rarely changes: the copy already here stays on screen while the console is asked again
  if (!topoGraph || topoGraph.error) { topoGraph = null; drawMap(); } else drawMap();
  api('/api/topology').then(g => { topoGraph = g && (g.edges || g.error) ? g : { error: 'the console sent no map' }; drawMap(); }).catch(x => { topoGraph = { error: (x && x.message) || String(x) }; drawMap(); }); }
function showSvc(n, byUser) {   // the service's card, a sheet over the map (numbers, calls, what this case found); null closes it
  const D = $('#tdetail'); mv.sel = n && mv.els.has(n) && mv.model ? n : null;
  mv.els.forEach((v, k) => v.b.setAttribute('aria-pressed', String(k === mv.sel)));
  if (!mv.sel) { D.hidden = true; D.replaceChildren(); MCV.classList.remove('has-detail'); return; }
  const s = mv.model.st[n], lay = mv.lay, head = el('div', 'lab', `Selected: ${n}`), x = el('button', null, 'Close'); x.type = 'button'; x.onclick = () => showSvc(null); head.append(x);
  const d = el('div', 'node'), nh = el('div', 'nh'); svcPills(s).forEach(p => nh.append(p)); d.append(nh);
  const callers = lay.N.filter(a => lay.out[a].includes(n)), list = (l) => l.length ? l.join(', ') : 'nothing on this map';
  d.append(el('div', null, `${(SVC[n] || ['', 'A service on the map'])[1]}. Calls ${list(lay.out[n])}; called by ${list(callers)}.`));
  if (s.key === 'root' && !s.alert) d.append(el('div', 'ck', 'This service raised no alert of its own in this case.'));
  if (s.stats) { const g = el('div', 'nums'), cell = (k, v) => { const c = el('span'); c.append(k, el('b', null, v)); g.append(c); }, r = s.stats;
    cell('Requests', Number(r.requests).toLocaleString()); cell('Errors', `${Number(r.errors).toLocaleString()} (${pct(r.error_rate)})`); cell('p50', fmtMs(r.p50_ms)); cell('p90', fmtMs(r.p90_ms)); cell('p99', fmtMs(r.p99_ms));
    d.append(g, el('div', 'ck', 'From the services summary the agent collected as evidence for this case.')); }
  s.H.forEach(h => { const r = el('div', 'evd'), id = el('button', 'hid', h.id), t = el('span'); id.type = 'button'; id.title = 'Show in the hypothesis tree'; id.onclick = () => gotoNode(h.id); t.append(statusPill(h.status), ' ', h.finding || h.statement || ''); r.append(id, t); d.append(r); });
  s.E.forEach(v => { const r = el('div', 'evd'); r.append(el('span', 'sig', v.signal || 'source'), el('span', null, v.finding)); d.append(r); });
  s.R.forEach(t => { const r = el('div', 'evd'); r.append(el('span', 'sig', 'Ruled out'), el('span', null, t)); d.append(r); });
  s.N2.forEach(v => { const r = el('div', 'evd'); r.append(el('span', 'sig', 'Next'), el('span', null, `Silent in this case and downstream of the alert (${(v.path || []).join(' to ')}): the agent lists it to check next.`)); d.append(r); });
  if (!s.stats && !s.H.length && !s.E.length && !s.R.length && !s.N2.length) d.append(el('div', 'ck', 'This case has no evidence about this service.'));
  D.replaceChildren(head, d); D.hidden = false; MCV.classList.add('has-detail');
  if (byUser) {   // the card opens below or above the clicked box so the map stays where it is: on the side with room for it, and of two such sides
    // the one that leaves the path to the root cause in view, then the roomier one
    const r = mv.els.get(n).b.getBoundingClientRect(), cv = MCV.getBoundingClientRect(), room = (up) => up ? r.top - cv.top - 20 : cv.bottom - r.bottom - 20, tall = (up) => Math.max(120, Math.min(room(up), cv.height * 0.48));
    const hides = (up) => { const a = up ? cv.top + 8 : cv.bottom - 8 - tall(up), z = a + tall(up); return (mv.model.focus || []).filter(f => f !== n && mv.els.has(f)).filter(f => { const q = mv.els.get(f).b.getBoundingClientRect(); return q.bottom > a && q.top < z; }).length; };
    const fits = (up) => room(up) >= 120, up = mv.up = fits(true) !== fits(false) ? fits(true) : hides(true) !== hides(false) ? hides(true) < hides(false) : room(true) > room(false);
    D.style.top = up ? '8px' : 'auto'; D.style.bottom = up ? 'auto' : '8px'; D.style.maxHeight = tall(up) + 'px';
    // only a box with no room on either side (a small screen) makes the map move, and by no more than clears it
    const dr = D.getBoundingClientRect(), c = MAPCAM.cam; let dy = up ? Math.max(0, dr.bottom + 12 - r.top) : Math.min(0, dr.top - 12 - r.bottom);
    if (up && r.bottom + dy > cv.bottom - 16) dy = cv.bottom - 16 - r.bottom; if (!up && r.top + dy < cv.top + 16) dy = cv.top + 16 - r.top;
    if (Math.abs(dy) > 1) { mapUserMoved(); MAPCAM.to({ k: c.k, x: c.x, y: c.y + dy }, 200); }
  }
}
function drawMap() {
  const N = $('#toponote'), L = $('#tlegend'), g = topoGraph, bad = !!(current && g && g.error);
  const msg = !current ? 'Open a case or press Triage on an alert to see the services around it.' : !g ? 'Loading the service map…' : bad ? `The service map did not load: ${g.error}. The console serves it at /api/topology; check that the console is still running.`
    : !Object.keys(g.edges || {}).length ? 'The console has no service map yet.' : '';
  MEMPTY.hidden = !msg; MAPW.hidden = !!msg; document.querySelectorAll('#mcvc button').forEach(b => { b.disabled = !!msg; });
  if (msg) { const t = el('div'); if (bad) t.append(ic('alert-triangle'), ' '); t.append(msg); MEMPTY.replaceChildren(t);
    if (bad) { const b = el('button', null, 'Load the map again'); b.type = 'button'; b.onclick = () => { b.disabled = true; loadMap(); }; MEMPTY.append(b); }
    showSvc(null); L.replaceChildren(); N.textContent = ''; return; }
  const sig = JSON.stringify(g.edges); let fresh = false;
  if (sig !== mv.sig || !mv.lay) { mv.sig = sig; buildMap(g); fresh = true; }
  const M = mv.model = mapModel(); mv.els.forEach((v, n) => paintSvc(n, v, M));
  mv.lay.links.forEach(l => { const on = (l.fwd && M.path.has(l.a + '>' + l.b)) || (l.rev && M.path.has(l.b + '>' + l.a)), mk = `url(#mk${on ? '-on' : ''})`; l.el.setAttribute('class', on ? 'me on' : 'me');
    if (l.fwd) l.el.setAttribute('marker-end', mk); if (l.rev) l.el.setAttribute('marker-start', mk); if (on && l.el.nextSibling) l.el.parentNode.append(l.el); });   // the amber path is drawn over the grey lines
  L.replaceChildren(); const item = (cls, text) => { const s = el('span'), i = el('i'); i.className = cls; s.append(i, text); L.append(s); };
  if (M.path.size) item('line', 'path to the root cause'); item('line call', 'calls');
  Object.keys(SVC_LABEL).forEach(k => { if (M.used[k]) { const s = el('span'), [cls, icon] = SVC_PILL[k], p = el('span', 'pill ' + cls); if (icon) p.append(ic(icon)); p.append(SVC_LABEL[k]); s.append(p, ` ${M.used[k]}`); L.append(s); } });
  N.textContent = (g.source === 'static' ? 'Service map: the recorded copy, because the live map has not loaded.' : 'Service map: live, from Observability Cloud.') + ' Each status comes from this case only.';
  if (mv.sel) showSvc(mv.els.has(mv.sel) ? mv.sel : null);   // refresh the open card with the latest data
  const focus = JSON.stringify(M.focus), lh = $('#tdetail').hidden ? L.offsetHeight : mv.legend;   // the camera moves again when what matters changed, or when the legend over the map grew a line
  if (fresh || focus !== mv.focus || lh !== mv.legend) { const first = fresh || mv.focus == null; mv.focus = focus; mv.legend = lh; aimMapSoon(first ? 0 : MOVE_MS); }
}
function setRun(r) { run = r; const t = $('#runtile'); if (t) t.replaceWith(runTile()); const s = $('#runstate'); if (s) s.textContent = r && r.seconds != null ? `done in ${Math.round(r.seconds)} s` : ''; }
function fmtK(n) { n = Number(n) || 0; return n >= 1000 ? (n / 1000).toFixed(1) + 'k' : String(n); }
function runTile() { const t = run ? tile('Agent run · this case', `${Math.round(run.seconds || 0)} s · $${Number(run.cost || 0).toFixed(2)}`, `${fmtK(run.tokens)} tokens · ${run.calls} tool calls`) : tile('Agent run · this case', '–', 'no finished run open'); t.id = 'runtile'; if (run) t.title = 'Model: ' + mdl(run.model); return t; }

// ---- Agent trace: what was done, in order, grouped into steps. Each step has one header that says who acted (code, the model or a person), what happened and
// how long it took; under it come plain rows of one shape (icon, text, numbers on the right, detail that opens under the row). A row is only ever added at the
// end or updated in place at the same height, and the view follows the newest row only while the reader is already at the bottom.
const TLOG = $('#tlog'), TNEW = $('#tnew'), TSTAT = $('#tstat');
const ACTOR = { code: ['code', 'Code'], model: ['sparkles', 'Model'], person: ['user', 'Person'] };
const SRV = { 'o11y-mcp-gateway': 'o11y', 'splunk-mcp-server': 'splunk', 'splunk-rest': 'splunk-rest' };
const fmtS = (s) => !isFinite(s) || s < 0 ? '' : s < 10 ? s.toFixed(1) + ' s' : Math.round(s) + ' s';
const fmtMs = (ms) => { ms = Number(ms) || 0; return ms < 1000 ? (ms < 10 ? ms.toFixed(1) : String(Math.round(ms))) + ' ms' : (ms / 1000).toFixed(ms < 10000 ? 2 : 1) + ' s'; };
const tOf = (e) => (e && (Number(e.t) || Date.parse(e.ts) / 1000)) || 0;
const plural = (n, w) => `${n} ${w}${n === 1 ? '' : 's'}`;
let tr = {};
function traceReset(text) {   // an empty log that says why it is empty
  tr = { seg: null, ev: null, calls: new Map(), pending: [], live: false, stored: false, done: false, rounds: 0, raw: 0, failed: 0, sections: 0, lastT: 0, model: '', phase: '' };
  const e = el('div', 'empty'); if (text instanceof Node) e.append(text); else e.textContent = text; TLOG.replaceChildren(e); TNEW.hidden = true; TLOG.scrollTop = 0; traceStatus();
}
const atBottom = () => TLOG.scrollHeight - TLOG.scrollTop - TLOG.clientHeight < 48;
function stick(fn) {   // change the log; follow the change only when the reader was at the newest row already, otherwise offer the way down
  const follow = atBottom(), r = fn(); if (follow) TLOG.scrollTop = TLOG.scrollHeight; else TNEW.hidden = false; return r;
}
TLOG.addEventListener('scroll', () => { if (atBottom()) TNEW.hidden = true; }, { passive: true });
TNEW.onclick = () => { TLOG.scrollTop = TLOG.scrollHeight; TNEW.hidden = true; TLOG.focus({ preventScroll: true }); };
function pillOf(cls, label, icon) { const p = el('span', 'pill ' + cls); if (icon) p.append(ic(icon)); p.append(label); return p; }
function seg(e, actor, title, o) {   // a new step. o: sum (second part of the header), minor (a one-line note), pill, timed (show how long it took), think (the time starts where the step before ended)
  o = o || {}; if (!TLOG.querySelector('.seg')) TLOG.replaceChildren();
  if (tr.ev) endEvidence(); if (tr.seg) tr.seg.el.classList.remove('run');
  const t = tOf(e), s = { el: el('div', 'seg ' + (o.minor ? 'minor' : actor)), t0: o.think && tr.lastT ? tr.lastT : t, timed: !!o.timed }, a = el('span', 'at', t ? at(e) : '');
  if (t) a.title = new Date(t * 1000).toISOString().slice(11, 19) + ' UTC';
  const nd = el('span', 'nd'), sh = el('div', 'sh'); if (!o.minor) { nd.append(ic(ACTOR[actor][0])); sh.append(el('span', 'who', ACTOR[actor][1])); }
  s.tt = el('span', 'tt', title); s.sm = el('span', 'sm', o.sum || ''); s.du = el('span', 'du'); sh.append(s.tt, s.sm); if (o.pill) sh.append(o.pill); sh.append(s.du);
  s.sb = el('div', 'sb'); s.el.append(a, nd, sh, s.sb); if (tr.live && o.timed) s.el.classList.add('run');
  stick(() => TLOG.append(s.el)); tr.seg = s; return s;
}
const note = (e, text) => seg(e, 'code', text, { minor: true });
function trow(o) {   // one row: icon, main text or node, optional second line, numbers on the right, optional detail that opens under the row
  const r = el(o.more ? 'details' : 'div', 'tr ' + (o.cls || '')), ln = el(o.more ? 'summary' : 'div', 'ln'), ico = el('span', 'ico'), main = el('div', 'mn'), meta = el('span', 'me2');
  if (o.icon) ico.append(ic(o.icon)); if (o.main instanceof Node) main.append(o.main); else main.textContent = o.main || '';
  let sub = null; if (o.sub != null) { sub = el('div', 's2'); if (o.sub instanceof Node) sub.append(o.sub); else sub.textContent = o.sub; main.append(sub); }
  [].concat(o.meta || []).forEach(m => meta.append(m));
  ln.append(ico, main, meta); if (o.more) { const c = el('span', 'cx'); c.append(ic('chevron-down')); ln.append(c); r.append(ln, o.more); } else r.append(ln);
  if (o.e && tOf(o.e)) ln.title = at(o.e);
  return { r, ico, main, meta, sub };
}
function add(s, row) { s = s || tr.seg || seg(null, 'code', 'Activity'); stick(() => s.sb.append(row.wrap || row.r)); return row; }
function endEvidence() { const s = tr.ev; tr.ev = null; s.tt.textContent = 'Collected the evidence'; s.sm.textContent = `${plural(tr.sections, 'section')}, ${plural(s.raw || 0, 'raw call')}${s.failed ? `, ${s.failed} failed` : ''}`; }
function callRow(s, c, o) {   // a tool call the model asked for: its purpose and the call; the result lands on the same lines when it comes back
  o = o || {}; const args = Object.entries(c.args || {}).filter(([k]) => k !== 'why').map(([k, v]) => `${k}=${typeof v === 'string' ? v : JSON.stringify(v)}`).join(', '), text = `${c.tool}(${args})`;
  const main = el('div'), sub = el('div', 'sl'), sg = el('span', 'sg mo', text), res = el('span', 'rs2', o.stored ? '' : 'running'), pre = el('pre', null, o.stored ? 'The case file keeps the call, not its result.' : 'No result yet.'), more = el('div', 'more');
  main.append(el('b', 'nx', 'Next: '), document.createTextNode((c.args && c.args.why) || c.tool)); sub.append(sg, res); more.append(el('div', 'mo full', text), pre);
  const row = trow({ cls: 'call wait', icon: 'circle-dashed', main, sub, more, e: o.e }), wrap = el('div', 'cw'), raws = el('div', 'raws'); wrap.append(row.r, raws);
  const call = Object.assign(row, { wrap, raws, pre, sg, res, ms: 0, text }); if (c.id) tr.calls.set(c.id, call); if (!o.stored) tr.pending.push(call); add(s, call); return call;
}
function callDone(call, ok, summary, preview, extra) {
  tr.pending = tr.pending.filter(x => x !== call); call.r.className = 'tr call ' + (ok ? 'ok' : 'bad'); call.ico.replaceChildren(ic(ok ? 'check' : 'x'));
  if (preview != null) call.pre.textContent = preview;
  if (ok) call.res.replaceChildren(...[summary, call.ms ? fmtMs(call.ms) : '', extra].filter(Boolean).map(x => el('span', null, x)));
  else { call.res.replaceChildren(pillOf('failed', 'Failed', 'x')); const why = preview ? String(preview).split('\n')[0] : ''; if (why) { call.sg.textContent = why; call.sg.title = call.text; } }
}
function flushPending() { tr.pending.forEach(c => { c.res.textContent = 'no result recorded'; }); tr.pending = []; }   // the round ended without these coming back
function rawRow(e) {   // one raw call to Observability Cloud or Splunk, under the tool call or the evidence step that made it
  tr.raw++; if (!e.ok) tr.failed++;
  const main = el('span', 'mo'), meta = [el('span', null, fmtMs(e.ms)), ic(e.ok ? 'check' : 'x')], more = el('div', 'more'), why = el('span'); main.append(el('span', 'srv', SRV[e.server] || e.server || ''), ' ', e.tool || '');
  more.append(el('pre', null, (e.params || '') + (e.error ? '\n\nerror: ' + e.error : '')));
  why.append(pillOf('failed', 'Failed', 'x'), ' ', e.error || 'no reason given');
  const row = trow({ cls: 'raw' + (e.ok ? '' : ' bad'), icon: 'plug-connected', main, sub: e.ok ? null : why, meta, more, e }), call = tr.pending[0];
  if (call) { call.ms += Number(e.ms) || 0; stick(() => call.raws.append(row.r)); return; }
  const s = tr.ev || tr.seg; if (s) { s.raw = (s.raw || 0) + 1; if (!e.ok) s.failed = (s.failed || 0) + 1; } add(tr.ev, row);
}
function evRow(e) { tr.sections++; const more = el('div', 'more'); more.append(el('pre', null, e.preview || '')); add(tr.ev, trow({ cls: 'ev', icon: 'file-text', main: String(e.section).replace(/_/g, ' '), meta: e.summary, more, e })); }
function hyRow(e, id, status, text) {   // a hypothesis opened or judged; its id opens it in the tree
  const main = el('div'), b = el('button', 'hid', id); b.type = 'button'; b.title = 'Show in the hypothesis tree'; b.onclick = () => gotoNode(id);
  if (tr.ev) seg(e, 'model', 'Hypothesis tree updated');   // never under the evidence step
  main.className = 'hyl'; main.append(b, statusPill(status), el('span', 'hx', text || '')); add(null, trow({ cls: 'hy', main, meta: tOf(e) ? at(e) : '' }));
}
function roundSeg(e) {   // one model round: its reasoning summary, the checks it asks for, what it wrote into the hypothesis tree
  const tcs = e.tool_calls || [], data = tcs.filter(c => !LEDGER_TOOLS.includes(c.tool)), ledger = tcs.filter(c => LEDGER_TOOLS.includes(c.tool));   // the tree shows the ledger calls; no "Next:" row for them
  const did = [data.length ? `asked for ${plural(data.length, 'check')}` : '', ledger.length ? 'updated the hypothesis tree' : ''].filter(Boolean).join(' and ') || (e.chat ? 'wrote the answer' : 'wrote the conclusion');
  flushPending(); tr.rounds++; const m = mdl(e.model), s = seg(e, 'model', `${e.chat ? 'Follow-up round' : 'Round'} ${e.step}: ${did}`, { sum: m && m !== tr.model ? m : '', timed: true, think: true }); tr.model = m;
  if (e.reasoning) { const w = el('div'); w.append(el('div', 'lb2', 'Reasoning summary'), rich(e.reasoning)); add(s, trow({ cls: 'rs', main: w })); }
  if (e.text) add(s, trow({ cls: 'rs', main: e.text }));
  data.forEach(c => callRow(s, c, { e }));
  if (ledger.length) { const o = ledger.filter(c => c.tool === 'hypothesis_open').length, v = ledger.length - o;
    add(s, trow({ cls: 'nt', icon: 'binary-tree', main: `Hypothesis tree updated: ${[o ? `${o} opened` : '', v ? `${v} verdict${v > 1 ? 's' : ''}` : ''].filter(Boolean).join(', ')}.` })); }
}
function toolResult(e) {
  const args = Object.assign({}, e.args), call = tr.calls.get(e.id) || callRow(null, { id: e.id, tool: e.tool, args }, { e });   // a result with no request seen (a reconnect, the scripted mock): show it as its own row
  callDone(call, !!e.ok, e.summary, e.preview);
}
function textRow(text, o) { return add(null, trow(Object.assign({ main: text }, o))); }
function traceLive(on) { tr.live = on; if (!on) { flushPending(); if (tr.ev) endEvidence(); if (tr.seg) tr.seg.el.classList.remove('run'); } }
function traceTick(e) {   // after every event: how long the step has taken so far, and the line above the list
  const t = tOf(e), s = tr.seg; if (t) { tr.lastT = t; if (s && s.timed && t >= s.t0) s.du.textContent = fmtS(t - s.t0); }
  traceStatus();
}
function traceStatus() {
  // the line above the list stays where it is: what is being waited for (while a run is live) and the totals. Nothing in the list moves to say so
  const counts = [tr.rounds ? plural(tr.rounds, 'model round') : '', plural(tr.raw || 0, 'raw call'), tr.failed ? `${tr.failed} failed` : ''].filter(Boolean).join(', '), n = (tr.pending || []).length;
  const now = tr.ev ? 'Collecting the evidence' : n ? `Waiting for ${plural(n, 'check')}` : tr.phase === 'policy' ? 'Checking the action against the policy' : tr.phase === 'exec' ? 'Waiting for the executor' : 'Waiting for the model';
  const text = !current ? 'No case open' : tr.streamDown ? 'The live stream stopped. Reconnecting…' : tr.stored ? 'Stored case: the live steps were not kept' : tr.live ? `${now}. So far: ${counts}` : tr.rounds || tr.raw ? `Finished: ${counts}` : 'Waiting for the first step';
  const live = !!tr.live && !!current && !tr.streamDown; $('#trace').classList.toggle('live', live); TSTAT.querySelector('use').setAttribute('href', '#ic-' + (live ? 'circle-dashed' : tr.rounds || tr.raw ? 'check' : 'info-circle'));
  if (TSTAT.lastChild.textContent !== text) { TSTAT.lastChild.textContent = text; TSTAT.title = text; }
}
function setRaw(show) { $('#trace').classList.toggle('noraw', !show); const b = $('#trawbtn'); b.textContent = show ? 'Hide raw calls' : 'Show raw calls'; try { localStorage.setItem('sre.trace.raw', show ? '1' : '0'); } catch (x) { /* private mode */ } }
$('#trawbtn').onclick = () => setRaw($('#trace').classList.contains('noraw'));
{ let v = '1'; try { v = localStorage.getItem('sre.trace.raw') || '1'; } catch (x) { /* private mode */ } setRaw(v !== '0'); }
function gotoNode(id) {   // from a row or a service card to the hypothesis in the tree
  tabPicked = true; setTab('pane-tree'); requestAnimationFrame(() => { const v = tv.els.get(id); if (!v) return; userMoved(); fitTo([v.b], MOVE_MS, OPEN_K); showNode(id); v.b.focus({ preventScroll: true }); });
}
function traceStored(c) {   // a case from before this session: no live steps, so show what its file holds (state changes, the model's tool calls, the result)
  tr.stored = true; const when = (ts) => ({ t: Date.parse(ts) / 1000 || Number(c.opened_epoch) || 0 }), inv = c.investigation, st = c.stats || {};
  const s0 = seg(when(c.opened_at), 'code', 'Case opened', { sum: `${c.id}, before this console session` });
  add(s0, trow({ cls: 'nt', icon: 'info-circle', main: 'The live steps of this run were not kept. Below is what the case file holds: the alerts, the tool calls the model made, the result and the state changes.' }));
  (c.incidents || []).forEach(i => add(s0, trow({ icon: 'alert-triangle', main: short(i.detector), meta: i.since ? 'since ' + hhmm(i.since) : '' })));
  const calls = new Map(); (c.transcript || []).forEach(x => calls.set(x.id || calls.size, Object.assign({}, calls.get(x.id), x)));   // the file holds a call twice (tool log and transcript)
  if (calls.size) { const bad = [...calls.values()].filter(x => x.ok === false).length, s = seg(null, 'model', 'Tool calls on file', { sum: `${plural(calls.size, 'call')}${bad ? `, ${bad} failed` : ''}` });
    calls.forEach(x => { const call = callRow(s, x, { stored: true }), size = x.chars != null ? `${Number(x.chars).toLocaleString()} characters` : '';
      if (x.ok === false) callDone(call, false, 'failed'); else if (x.ok === true) callDone(call, true, size, null, x.truncated ? 'cut to fit' : ''); else { call.r.className = 'tr call'; call.ico.replaceChildren(); call.res.textContent = size; } }); }
  if (inv) { const tok = (st.input_tokens || 0) + (st.output_tokens || 0) + (st.cache_read_tokens || 0), s = seg(st.seconds ? { t: when(c.opened_at).t + Number(st.seconds) } : null, 'model', 'Conclusion: brief stored', { sum: mdl(st.model) });
    textRow(nb(inv.title || firstSentence(inv.summary) || 'No fault found'), { cls: 'rs' });
    add(s, statRow([['Tool calls', String((st.bundle_tool_calls || 0) + (st.investigator_tool_calls || 0)), `${st.bundle_tool_calls || 0} by code, ${st.investigator_tool_calls || 0} by the model`], ['Model tokens', tok.toLocaleString()], ['Cost', '$' + Number(st.cost_usd || 0).toFixed(4)], ['Time', fmtS(Number(st.seconds))]])); }
  else textRow('No investigation result was stored for this case.', { cls: 'nt', icon: 'info-circle' });
  if ((c.history || []).length) { const s = seg(null, 'code', 'State changes', { sum: plural(c.history.length, 'change') });
    c.history.forEach(h => add(s, trow({ main: `From ${String(h.from).replace(/_/g, ' ')} to ${String(h.to).replace(/_/g, ' ')}${h.reason ? ': ' + [].concat(h.reason).join('; ') : ''}`, sub: h.action ? `${h.action}, policy: ${h.requirement}` : null, meta: h.ts ? String(h.ts).slice(11, 19) + 'Z' : '' }))); }
  TLOG.scrollTop = 0; TNEW.hidden = true;   // nothing is running: a stored case reads from the top
}
function statRow(cells) { const g = el('div', 'stg'); cells.filter(c => c[1]).forEach(([k, v, sub]) => { const c = el('span'); c.append(k, el('b', null, v)); if (sub) c.append(el('small', null, sub)); g.append(c); }); return trow({ cls: 'st', main: g }); }

function render(e) {
  if (REFRESH_ON.has(e.event) && e.case_id === current) refreshSoon(current);
  render1(e); traceTick(e);
}
function render1(e) {
  switch (e.event) {
    case 'sre.tree.reset': { const had = tree.nodes.length; tree.nodes = []; tree.method = null; showNode(null); drawTree(); mapSoon();   // a new investigator run (also the re-run with the stronger model) starts its own tree
      if (had) note(e, 'Hypothesis tree cleared: a new investigator run starts.'); return; }
    case 'sre.tree.branch': treeUpsert({ id: e.node, parent: e.parent, depth: e.depth, statement: e.statement, test_plan: e.test_plan, status: 'open' }); return hyRow(e, e.node, 'open', e.statement);
    case 'sre.tree.verdict': treeUpsert({ id: e.node, parent: e.parent, depth: e.depth, statement: e.statement, status: e.status || 'inconclusive', model_verdict: e.model_verdict, checks: e.checks, finding: e.finding, evidence: e.evidence, component: e.component,
      last_seen_min: e.last_seen_min, independent: e.independent, tool_calls: e.tool_calls, seconds: e.seconds }); return hyRow(e, e.node, e.status || 'inconclusive', e.finding || e.statement);
    case 'sre.case.opened': { setAlert(e.detectors); caseDets = e.detectors || []; drawTree(); mapSoon(); const s = seg(e, 'code', 'Case opened', { sum: e.case_id });
      (e.detectors || []).forEach(d => add(s, trow({ icon: 'alert-triangle', main: short(d) }))); return; }
    case 'sre.case.incident_attached': return note(e, `Added ${short(e.detector)} to case ${e.case_id}: ${relPath(e)} (${e.gap_s} s after it opened)`);
    case 'sre.case.tie_suggested': return note(e, `Possible tie: this case ${REL[e.relation] || e.relation} ${e.other_case} (${(e.other_detectors || []).map(short).join(' + ')}) via ${(e.path || []).join(' → ')}`);
    case 'sre.case.incident_added': return note(e, `Added ${short(e.detector)} to case ${e.case_id} (by ${e.by})`);
    case 'sre.case.merged': return note(e, `Case ${e.merged_case} merged into ${e.case_id} by ${who(e.by)}`);
    case 'sre.case.merged_away': return note(e, `This case was merged into ${e.into} by ${who(e.by)}`);
    case 'sre.case.tie_dismissed': return note(e, `Tie with ${e.other_case} marked not related by ${who(e.by)}`);
    case 'sre.console.starting': setRunning(true); setInvestigating(true); tr.live = true; return note(e, 'Connecting to Observability Cloud and Splunk Enterprise…');
    case 'sre.case.investigating': setRunning(true); setInvestigating(true); tr.live = true; tr.sections = 0; { const s = seg(e, 'code', 'Collecting the evidence', { sum: 'before the model sees anything', timed: true }); tr.ev = s; } return;
    case 'sre.mcp.call': calls[e.server] = (calls[e.server] || 0) + 1; return rawRow(e);
    case 'sre.rca.evidence': if (e.section === 'services_summary') { if (e.services) setStats(e.services); else readSummary(e.preview); mapSoon(); } return evRow(e);
    case 'sre.rca.step': {
      if (e.stop_reason === 'evidence_check') { flushPending(); const s = seg(e, 'code', 'Check by code');
        add(s, trow({ cls: 'rs', main: rich(String(e.reasoning || 'The answer lacked a metric/trace or log signal; one more round requested.').replace(/^Check by code: (.)/, (m, c) => c.toUpperCase())) })); return; }
      return roundSeg(e);
    }
    case 'sre.rca.tool': if (e.tool === 'services_summary') { readSummary(e.preview); mapSoon(); } return toolResult(e);
    case 'sre.case.escalated_model': { const s = seg(e, 'code', 'Escalated to a stronger model', { sum: e.to_model }); add(s, trow({ cls: 'rs', main: `First answer was weak (${e.reason}); re-investigating the same evidence with ${e.to_model}.` })); return; }
    case 'sre.case.investigated': {
      renderBrief(e, null); setInvestigating(false); flushPending(); tr.phase = 'policy';
      const tok = (Number(e.input_tokens) || 0) + (Number(e.output_tokens) || 0) + (Number(e.cache_read_tokens) || 0), n = Object.values(calls).reduce((a, b) => a + b, 0);
      setRun({ seconds: e.seconds, cost: e.cost_usd, tokens: tok, calls: n, model: e.model });
      const s = seg(e, 'model', 'Conclusion: brief submitted', { sum: mdl(e.model) });
      add(s, trow({ cls: 'rs', main: nb(e.title || firstSentence(e.summary) || [e.root_cause_service, String(e.failure_mode || '').replace(/_/g, ' ')].filter(Boolean).join(', ') || 'No fault found') }));
      add(s, statRow([['Raw calls', String(n), `Observability Cloud ${calls['o11y-mcp-gateway']}, Splunk ${calls['splunk-mcp-server'] + calls['splunk-rest']}`], ['Model tokens', tok.toLocaleString()], ['Cost', '$' + Number(e.cost_usd || 0).toFixed(4)], ['Time', `${e.seconds} s`]])); return;
    }
    case 'remediation.proposed': { renderAction(e); const s = seg(e, 'code', 'Action proposed', { sum: `policy: ${e.requirement}` });
      add(s, trow({ main: e.real_world || e.action, sub: e.real_world ? e.action : null })); add(s, trow({ cls: 'nt', icon: 'info-circle', main: e.requirement === 'ask' ? 'A person has to approve it. The decision is in the brief.' : 'The decision is in the brief.' })); return; }
    case 'approval.decided': { decided(e.decision); const did = `${e.decision === 'approve' ? 'Approved' : 'Rejected'} by ${e.approver}`; status(did); tr.live = e.decision === 'approve'; tr.phase = 'exec'; seg(e, /^policy:/.test(String(e.approver)) ? 'code' : 'person', did); return; }
    case 'remediation.executing': status('Executor re-checking state, then acting…'); seg(e, 'code', 'Executor', { sum: 're-checks the state, then acts', timed: true }); return;
    case 'remediation.refused': { status('Executor refused: ' + e.reason, 'bad'); tr.live = false; const s = seg(e, 'code', 'Executor refused', { pill: pillOf('failed', 'Refused', 'x') }); add(s, trow({ cls: 'rs', main: 'Refused: ' + e.reason })); return; }
    case 'remediation.state': return textRow(`State before ${JSON.stringify(e.pre_state)}, after ${JSON.stringify(e.post_state)}`, { icon: 'info-circle', e });
    case 'remediation.executed': status(`Action ${e.executed ? 'executed' : 'NOT executed'}`, e.executed ? '' : 'bad'); return textRow(`Action ${e.executed ? 'executed' : 'not executed'}`, { cls: e.executed ? 'ok' : 'bad', icon: e.executed ? 'check' : 'x', meta: e.executed ? '' : pillOf('failed', 'Not executed', 'x'), e });
    case 'remediation.verified': status(e.outcome_ok ? `Verified by the fixed query (last value ${e.value})` : `Not verified (last value ${e.value}); escalated to a human`, e.outcome_ok ? 'good' : 'bad'); tr.live = false;
      return textRow(e.outcome_ok ? `Verified by the fixed query (last value ${e.value}).` : `Not verified (last value ${e.value}).`, { cls: e.outcome_ok ? 'ok' : 'bad', icon: e.outcome_ok ? 'check' : 'x', meta: pillOf(e.outcome_ok ? 'validated' : 'failed', e.outcome_ok ? 'Verified' : 'Not verified', e.outcome_ok ? 'check' : 'x'), e });
    case 'sre.case.mitigated_awaiting_clear': status('Mitigated — waiting for the detector to clear on its own', 'good'); return note(e, 'Mitigated: waiting for the detector to clear.');
    case 'sre.case.escalated': { setInvestigating(false); const why = [].concat(e.reason || 'escalated to a human').join('; '); if (!briefShown) renderEnd('Escalated to a human: no answer', [].concat(e.reason || 'escalated').join('; ')); status('Escalated to a human: ' + [].concat(e.reason || '').join('; '), 'bad');
      const s = seg(e, 'code', 'Escalated to a person', { pill: pillOf('failed', 'Escalated', 'alert-triangle') }); add(s, trow({ cls: 'rs', main: why })); return; }
    case 'sre.audit.write_failed': { const s = seg(e, 'code', 'Audit record lost', { pill: pillOf('failed', 'Failed', 'x') }); add(s, trow({ cls: 'rs', main: `Audit record ${e.lost_event} did not reach index ${e.index}: ${e.error} (${e.failures_total} lost so far)` })); return; }
    case 'sre.case.inconclusive': { setInvestigating(false); if (!briefShown) renderEnd('Inconclusive: no answer', [].concat(e.reason || 'the investigation did not reach a conclusion').join('; '));
      const s = seg(e, 'model', 'Inconclusive', { pill: pillOf('inconclusive', 'No answer') }); add(s, trow({ cls: 'rs', main: 'The evidence above is for a person to read.' })); return; }
    case 'sre.case.stop_requested': return note(e, `Stop requested by ${e.by}: waiting for the current call to return…`);
    case 'sre.case.stopped': { setRunning(false); setInvestigating(false); traceLive(false);
      renderEnd('Stopped by the operator', `Stopped by ${e.by} during ${e.stage}, after ${e.model_calls} model call(s), $${Number(e.cost_usd || 0).toFixed(4)} spent. Nothing was proposed or executed.`, 'closed');
      const s = seg(e, 'person', `Stopped by ${e.by}`, { pill: pillOf('failed', 'Stopped', 'x') }); add(s, trow({ cls: 'rs', main: `Stopped during ${e.stage}. ${e.model_calls} model call(s), $${Number(e.cost_usd || 0).toFixed(4)} spent; nothing proposed or executed.` })); return; }
    case 'sre.case.escalation_failed': { const s = seg(e, 'code', 'Escalation failed', { pill: pillOf('failed', 'Failed', 'x') }); add(s, trow({ cls: 'rs', main: `The re-run with ${mdl(e.to_model)} failed (${e.error}). Keeping the first answer from ${mdl(e.kept_model)}.` })); return; }
    case 'sre.llm.retry': return note(e, `The model API refused the request (${e.error}); retrying once in ${e.after_s}s…`);
    case 'sre.case.closed': return note(e, `Case closed${e.reason ? ': ' + String(e.reason).slice(0, 160) : ''}`);
    case 'sre.case.paged': { status(`Paged ${e.team} (simulated)`); const s = seg(e, 'person', `${who(e.by)} paged ${e.team}`); if (e.note) add(s, trow({ cls: 'nt', icon: 'info-circle', main: e.note })); return; }
    case 'sre.case.acknowledged': return note(e, `Acknowledged by ${e.by}: ${e.note}`);
    case 'sre.case.rerun_requested': return note(e, `Re-run requested by ${e.by}: a new case was opened`);
    case 'sre.chat.question': { setRunning(true); tr.live = true; tr.phase = ''; const s = seg(e, 'person', `${e.by} asked`); add(s, trow({ cls: 'rs', main: e.question })); return; }
    case 'sre.chat.done': setRunning(false); traceLive(false); return;
    case 'sre.chat.answer': { flushPending(); const s = seg(e, 'model', 'Answer', { sum: `${mdl(e.model)}, $${Number(e.cost_usd || 0).toFixed(4)}` }); add(s, trow({ cls: 'rs', main: rich(e.answer) })); return; }
    case 'sre.console.error': { const s = seg(e, 'code', 'Console error', { pill: pillOf('failed', 'Error', 'alert-triangle') }); add(s, trow({ cls: 'rs', main: e.error })); return; }
    case 'sre.console.done': setRunning(false); setInvestigating(false); traceLive(false); loadSide();
      if (!briefShown && e.state && e.state !== 'investigating') renderEnd(`Case ended: ${String(e.state).replace(/_/g, ' ')}`, 'The investigation ended without a brief; the reasoning pane shows how far it got.');
      return;
    case 'sre.console.history': return renderHistory(e);
  }
}

function list(label, items, fill) { if (!(items || []).length) return null; const w = el('div'); w.append(el('div', 'lab', label)); const ul = el('ul'); items.forEach(x => { const li = el('li'); fill(li, x); ul.append(li); }); w.append(ul); return w; }
function renderEnd(title, reason, state) {   // the case ended without an investigation result: say so instead of "Investigating…"
  briefShown = true; const b = $('#brief'); b.replaceChildren();
  b.append(el('span', 'cat', 'No brief'), el('h3', null, title));
  const r = el('div', null, reason); r.style.color = 'var(--warn)'; b.append(r);
  b.append(plain('The evidence collected so far is in the reasoning pane. Re-run the RCA (root cause analysis) for a fresh investigation, or page the owning team.'));
  b.append(caseActions(current, null, { state }));
  const st = el('div', 'lab'); st.id = 'execstatus'; b.append(st); paintStatus();
}
function renderBrief(e, pageTeam) {
  briefShown = true; const b = $('#brief'); b.replaceChildren();
  if (briefCase !== e.case_id) { briefCase = e.case_id; showNode(null); }
  tree.evidence = e.evidence || []; setAlert(e.detectors, e.incidents_since); briefData = e;
  if ((e.tree || []).length) { tree.nodes = e.tree; tree.method = 'tree'; }
  else if (tree.method !== 'tree') { tree.nodes = (e.hypotheses || []).map((h, i) => Object.assign({ id: 'H' + (i + 1), parent: null, depth: 1 }, h)); tree.method = 'loop'; }
  caseDets = e.detectors || caseDets; drawTree(); drawMap(); if (!tabPicked) setTab('pane-tree');
  mergeBanners(e).forEach(x => b.append(x));
  const dbox = el('div', 'decide'); dbox.id = 'decidebox'; const slot = el('div'); slot.id = 'actionslot'; dbox.append(slot); b.append(dbox);
  const pa = (e.proposed_action && e.proposed_action.type) || e.proposed_action || 'inconclusive';
  renderAction({ case_id: e.case_id, action: pa, requirement: pa === 'no_action' ? 'none' : pa === 'inconclusive' ? 'none' : 'pending', tier: '–' }, true);
  dbox.append(caseActions(e.case_id, e.page_team || pageTeam, e));
  const st = el('div', 'plain'); st.id = 'execstatus'; st.style.marginTop = '8px'; dbox.append(st);
  const sum = e.summary || [e.root_cause_service, String(e.failure_mode || '').replace(/_/g, ' ')].filter(Boolean).join(' · ') || 'Investigation result';
  b.append(el('h3', null, nb(e.title || firstSentence(sum))));
  const facts = el('div', 'facts'); const fact = (k, v) => { if (!v) return; const s = el('span'); s.append(k, typeof v === 'string' ? el('b', null, v) : v); facts.append(s); };
  fact('Root cause', nb(e.root_cause_service)); fact('Mode', String(e.failure_mode || '').replace(/_/g, ' '));
  if (e.confidence != null) { const pc = Math.round(Number(e.confidence) * 100), c = el('div', 'conf'), bar = el('div', 'bar'), i = el('i'); i.style.width = pc + '%'; bar.append(i); c.append(bar, el('b', null, pc + '%')); c.setAttribute('aria-label', `Confidence ${pc} percent`); fact('Confidence', c); }
  fact('Started', e.started_at ? hhmm(e.started_at) || e.started_at : ''); fact('Page team', nb(e.page_team || pageTeam));
  const tr = (e.evidence || []).map(v => /trace ([0-9a-f]{8,32})/i.exec(v.finding || '')).find(Boolean);
  if (tr) { let v = tr[1]; if (v.length >= 16) { const a = el('a', null, v.slice(0, 8) + ' '); a.append(ic('external')); a.href = 'https://app.us1.signalfx.com/#/apm/traces/' + v; a.target = '_blank'; a.rel = 'noopener'; v = a; } fact('Trace', v); }
  b.append(facts);
  const more = e.title ? (e.summary || '') : restSentences(sum); if (more) b.append(el('p', null, more));
  if (e.mechanism) b.append(el('div', 'lab', 'Root cause'), el('p', null, e.mechanism));
  if (e.impact) b.append(el('div', 'lab', 'Customer impact'), el('p', null, e.impact));
  if ((e.cause_chain || []).length) { b.append(el('div', 'lab', 'Cause chain · root cause → alert')); const ol = el('ol', 'chain'); e.cause_chain.forEach(x => ol.append(el('li', null, x))); b.append(ol); }
  const ns = (e.next_steps || []).filter(Boolean); if (ns.length) { b.append(el('div', 'lab', 'Next steps')); const ol = el('ol', 'chain'); ns.forEach(x => ol.append(el('li', null, x))); b.append(ol); }
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
  const box = $('#decidebox'), ask = !placeholder && e.requirement === 'ask'; if (box) { box.classList.toggle('live', ask); box.classList.toggle('reserve', !!placeholder && e.requirement === 'pending'); }
  const head = (label, title) => slot.append(el('div', 'l', label), el('div', 'ttl', nb(String(title || '').replace(/^./, c => c.toUpperCase()))));
  if (placeholder) {
    if (e.action === 'no_action') { head('No action needed', 'Nothing to change in the platform'); slot.append(el('div', 'm', 'Page the owning team, close, or re-run the RCA (root cause analysis) below.')); }
    else if (e.action === 'inconclusive') { head('Inconclusive', 'No action proposed'); slot.append(el('div', 'm', 'The evidence is in the agent trace. Page the owning team or re-run the RCA.')); }
    else { head('Proposed', e.action); slot.append(el('div', 'm', 'Waiting for the policy decision…')); }
    return;
  }
  head(ask ? 'Awaiting your approval' : e.action === 'no_action' ? 'No action needed' : `Action: ${String(e.requirement || '').replace(/^none \(|\)$/g, '')}`, e.action === 'no_action' ? 'Notify and close' : (e.real_world || e.action));
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
  const b = $('#decidebox'); if (!b) return; b.classList.remove('live'); const l = b.querySelector('.l'); if (l) l.textContent = d === 'approve' ? 'Approved: acting and verifying' : 'Rejected';
  const a = b.querySelector('.approve'); if (a) a.parentElement.remove();
}
function renderHistory(h) { const c = h.case; caseDets = (c.incidents || []).map(i => i.detector); setStats(c.services); traceStored(c); renderStored(c, h.page_team); mapSoon(); }
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
  tree = { nodes: [], alert: null, evidence: [], method: null, selected: null }; tabPicked = false; briefData = null; setRun(null); setTab('trace');
  cancelAnimationFrame(cam.raf); cam.raf = 0; cam.x = cam.y = 0; cam.k = 1; applyCam(); tv.investigating = false; tv.goal = null; PH.hidden = true; setMode('open'); tv.settle = performance.now() + SETTLE_MS; clearTimeout(tv.settleTimer);
  tv.settleTimer = setTimeout(() => { if (!tv.investigating && tv.mode !== 'free') { tv.goal = null; setMode('open'); } aim(0); }, SETTLE_MS + 80);   // a finished or stored case opens on its alert and hypotheses
  svcStats = {}; caseDets = []; mv.free = mv.all = false; mv.focus = null; showSvc(null); drawTree(); loadMap();
  traceReset('Waiting for the first step of this case…'); $('#brief').replaceChildren(el('div', 'empty', 'Investigating… the brief appears when the investigation concludes.'));
  $('#q').disabled = false; $('#q').placeholder = `Follow-up about ${cid}… e.g. “why not a config change?”`;
  if (es) es.close(); let opened = false; es = new EventSource(`/api/stream/${encodeURIComponent(cid)}`);
  // the console sends every step of the case again when the stream reconnects: start the list over instead of showing each step twice
  es.onopen = () => { if (cid !== current) return; if (opened) { t0 = null; calls = freshCalls(); traceReset('Reconnected. Reading the steps of this case again…'); } opened = true; tr.streamDown = false; traceStatus(); };
  es.onerror = () => { if (cid === current) { tr.streamDown = true; traceStatus(); } };
  es.onmessage = (m) => { try { render(JSON.parse(m.data)); } catch (x) { console.error(x); } };
  document.querySelectorAll('#cases .item, #decisions .item').forEach(n => n.classList.toggle('on', n.dataset.cid === cid));
}
async function start(body) { const r = await api('/api/investigate', body); if (r.case_id) { open(r.case_id); loadSide(); } else toast(r.error || 'could not start', true); }

function tile(label, value, sub, cls) { const t = el('div', 'tile'); const v = el('div', 'v'); if (cls) v.append(el('span', 'dot ' + cls)); v.append(value); t.append(el('div', 'l', label), v, el('div', 's', sub || '')); return t; }
async function loadStatus() {
  const r = await api('/api/status'); const s = r.status || {}; const st = $('#strip'); st.replaceChildren();
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
let sideParts = 0;
function sideReady(bit) { sideParts |= bit; if (sideParts === 3) $('#side').classList.add('ready'); }
setTimeout(() => sideReady(3), 4000);   // never leave the box hidden when one of the two reads hangs
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
      sideReady(1);
    });
    const inc = await api('/api/incidents'); const a = $('#alerts'); a.replaceChildren(); clearCtl('alerts', inc.hidden || 0, !(inc.incidents || []).length);
    if (inc.error && !inc.incidents) { a.append(el('div', 'item', 'Could not read incidents: ' + inc.error)); sideReady(2); return; }
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
    sideReady(2);
  } catch (x) { $('#alerts').replaceChildren(el('div', 'item', 'Could not load alerts and cases: ' + (x && x.message || x))); sideReady(3); }
}
PRESETS.forEach(([label, q]) => { const b = el('button', null, label); b.type = 'button'; b.onclick = () => { $('#symptom').value = q; $('#symptom').focus(); }; $('#chips').append(b); });
if (window.ResizeObserver) { new ResizeObserver(() => aimSoon(true)).observe(CV); new ResizeObserver(() => { mapSoon(); aimMapSoon(0); }).observe(MCV); } else window.addEventListener('resize', () => { aimSoon(true); mapSoon(); aimMapSoon(0); });   // a canvas also changes size when a card opens under it
if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => aimSoon(true));   // Inter arriving changes node heights
TNEW.append(ic('chevron-down')); TSTAT.prepend(ic('circle-dashed'));
{ const f = document.createDocumentFragment(); f.append('Ask a question above, or press ', el('b', null, 'Triage'), ' on an alert. Every step appears here as it happens, grouped by who acted: the evidence code collects, each model round with its reasoning summary and the checks it asks for, and every raw MCP (Model Context Protocol) call to Splunk Observability Cloud and Splunk Enterprise with its arguments and timing.'); traceReset(f); }
drawTree(); drawMap();
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
