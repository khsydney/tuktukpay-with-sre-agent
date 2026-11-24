"""Build the TukTukPay control tower as a Dashboard Studio dashboard (tabs = pages of the mock-up), validate every
search against the stack, then create/update the view. Usage: python3 build_tower.py [--validate-only]"""
import json, sys
sys.path.insert(0, ".")
from stack import S

APP, NAME = "search", "tuktukpay_control_tower"
O11Y = "https://app.us1.signalfx.com/#"
ENV = "tuktukpay-demo"
P = "index=tuktukpay"
PAY = f"{P} event IN (payment.approved, payment.declined)"

ds, viz, layouts, tabs = {}, {}, {}, []
_n = [0]


def add_ds(query, name=None):
    _n[0] += 1
    k = f"ds_{_n[0]}"
    ds[k] = {"type": "ds.search", "name": name or k, "options": {"query": query.strip()}}
    return k


def single(title, query, unit="", ranges=None, under=""):
    k = add_ds(query)
    o = {"majorValue": "> sparklineValues | lastPoint()", "trendValue": "> sparklineValues | delta(-6)",
         "sparklineValues": "> primary | seriesByIndex(1)", "unit": unit, "underLabel": under, "sparklineDisplay": "below",
         "trendDisplay": "absolute", "backgroundColor": "transparent"}
    if ranges:
        o["majorColor"] = "> majorValue | rangeValue(majorColorEditorConfig)"
        o.pop("backgroundColor")
    v = {"type": "splunk.singlevalue", "title": title, "dataSources": {"primary": k}, "options": o}
    if ranges:
        v["context"] = {"majorColorEditorConfig": ranges}
    return v


def chart(kind, title, query, desc="", **opts):
    k = add_ds(query)
    return {"type": kind, "title": title, "description": desc, "dataSources": {"primary": k}, "options": opts}


def table(title, query, desc="", drill=None, **opts):
    v = chart("splunk.table", title, query, desc, **opts)
    if drill:
        v["eventHandlers"] = [drill]
    return v


def md(text):
    return {"type": "splunk.markdown", "options": {"markdown": text, "fontSize": "small"}}


def link_search():
    return {"type": "drilldown.linkToSearch", "options": {"type": "auto", "newTab": True}}


def link_url(url):
    return {"type": "drilldown.customUrl", "options": {"url": url, "newTab": True}}


GOOD_HIGH = [{"to": 85, "value": "#D41F1F"}, {"from": 85, "to": 89, "value": "#F8BE34"}, {"from": 89, "value": "#1CA30C"}]
BAD_HIGH = lambda w, c: [{"to": w, "value": "#1CA30C"}, {"from": w, "to": c, "value": "#F8BE34"}, {"from": c, "value": "#D41F1F"}]


def page(label, rows):
    """rows: list of lists of (viz, width) where widths in a row sum to 1200; heights given per row as first element."""
    lid = f"layout_{len(tabs) + 1}"
    structure, y = [], 0
    for h, items in rows:
        x = 0
        for v, w in items:
            vid = f"viz_{len(viz) + 1}"
            viz[vid] = v
            structure.append({"item": vid, "type": "block", "position": {"x": x, "y": y, "w": w, "h": h}})
            x += w
        y += h
    layouts[lid] = {"type": "grid", "options": {"width": 1200}, "structure": structure}
    tabs.append({"layoutId": lid, "label": label})


# ---------------- Overview ----------------
page("Overview", [
    (70, [(md("**TukTukPay · 11.11 control tower** — read the gateway in ten seconds, then drill to the one payment, mandate or pod. "
              f"Logs: `index=tuktukpay` (HEC). Traces and detectors: Observability Cloud, environment `{ENV}` — "
              f"[APM]({O11Y}/apm?environments={ENV}) · [detectors]({O11Y}/alerts). Tabs follow the control-tower mock-up."), 1200)]),
    (150, [
        (single("Approval rate %", f"{PAY} | timechart span=5m count(eval(event=\"payment.approved\")) as a count as n | eval approval=round(100*a/n,1) | fields _time approval", "%", GOOD_HIGH, "authorised ÷ submitted"), 240),
        (single("Payments per 5 min", f"{PAY} | timechart span=5m count as payments"), 240),
        (single("Agent-initiated share %", f"{PAY} | timechart span=5m count(eval('payment.initiator'=\"agent\")) as ag count as n | eval share=round(100*ag/n,1) | fields _time share", "%", BAD_HIGH(15, 30), "payment.initiator=agent"), 240),
        (single("Mandates blocked %", f"{P} event IN (mandate.verified, mandate.blocked) | timechart span=15m count(eval(event=\"mandate.blocked\")) as b count as n | eval blocked=round(100*b/n,1) | fillnull value=0 blocked | fields _time blocked", "%", BAD_HIGH(10, 30), "mandate.blocked ÷ checked"), 240),
        (single("Failovers per 5 min", f"{P} event=route.failover | timechart span=5m count as failovers", "", BAD_HIGH(5, 50), "route.failover"), 240),
    ]),
    (330, [
        (chart("splunk.sankey", "Where payments went: initiator → acquirer → outcome",
               f"{PAY} | eval acq='payment.acquirer', init='payment.initiator', out='payment.outcome' | stats count by init acq out "
               "| appendpipe [ stats sum(count) as value by init acq | rename init as source, acq as target ] "
               "| appendpipe [ where isnull(source) | stats sum(count) as value by acq out | rename acq as source, out as target ] "
               "| where isnotnull(source) | table source target value",
               "Datadog's Sankey widget is limited to Product Analytics; this one runs on any SPL."), 720),
        (table("Declines by reason (top 8)", f"event=payment.declined {P} | stats count by payment.decline_reason | sort - count | head 8 | rename payment.decline_reason as reason",
               drill=link_search()), 480),
    ]),
    (260, [
        (chart("splunk.line", "Approval rate and agent share (%)",
               f"{PAY} | timechart span=10m count(eval(event=\"payment.approved\")) as a count(eval('payment.initiator'=\"agent\")) as ag count as n "
               "| eval \"Approval %\"=round(100*a/n,1), \"Agent share %\"=round(100*ag/n,1) | fields _time \"Approval %\" \"Agent share %\"",
               yAxisMin=0, yAxisMax=100), 720),
        (table("Service health from logs (last 15 min, errors and warnings)",
               f"{P} earliest=-15m severity IN (error, warn) | stats count(eval(severity=\"error\")) as errors count(eval(severity=\"warn\")) as warnings by service.name | sort - errors",
               drill=link_url(f"{O11Y}/apm/troubleshooting?environments={ENV}&service=$row.service.name.value$")), 480),
    ]),
])

# ---------------- Acquirers & issuers ----------------
page("Acquirers & issuers", [
    (230, [(table("Acquirer scorecard",
                  f"{PAY} | stats count as payments count(eval(event=\"payment.approved\")) as approved perc90(acquirer.latency_ms) as p90_ms count(eval('route.failover'=\"true\")) as failovers by payment.acquirer "
                  "| eventstats sum(payments) as total | eval share_pct=round(100*payments/total,1), approval_pct=round(100*approved/payments,1), p90_ms=round(p90_ms) "
                  "| lookup acquirers.csv id as payment.acquirer OUTPUT name role | table name payment.acquirer share_pct approval_pct p90_ms failovers role | sort - share_pct",
                  "Approval = authorised ÷ submitted (Checkout.com's definition). Click a row for its trace view in APM.",
                  drill=link_url(f"{O11Y}/apm/tagspotlight?environments={ENV}&service=payment-router&tag=payment.acquirer")), 1200)]),
    (260, [
        (chart("splunk.line", "Approval rate by acquirer (%)",
               f"{PAY} | timechart span=10m count(eval(event=\"payment.approved\")) as a count as n by payment.acquirer "
               "| foreach a:* [ eval \"<<MATCHSTR>>\"=round(100*'a:<<MATCHSTR>>'/'n:<<MATCHSTR>>',1) ] | fields _time acq-*",
               yAxisMin=60, yAxisMax=100), 700),
        (chart("splunk.column", "Decline mix (Stripe's buckets)",
               f"{P} event IN (payment.declined, route.failover, payment.rejected) | eval bucket=case(event=\"route.failover\", \"timeout / failover\", event=\"payment.rejected\", \"invalid\", "
               "'payment.decline_reason' IN (\"risk_declined\") OR like('payment.decline_reason', \"mandate_%\"), \"blocked (risk / mandate)\", true(), \"issuer declined\") | timechart span=10m count by bucket",
               stackMode="stacked"), 500),
    ]),
    (280, [
        (table("Declines by BIN prefix × acquirer — the needle",
               f"event=payment.declined {P} | chart count over payment.card.bin by payment.acquirer limit=10 | addtotals | sort - Total | head 12",
               "Act 1: one BIN at one acquirer lights up. Click a cell to search those declines.", drill=link_search()), 700),
        (chart("splunk.column", "Failovers per 10 min by backup acquirer",
               f"{P} event=route.failover | timechart span=10m count by route.backup_acquirer"), 500),
    ]),
])

# ---------------- Agentic commerce governance ----------------
page("Agentic commerce governance", [
    (140, [
        (single("Agent payments per 15 min", f"{PAY} 'payment.initiator'=\"agent\" | timechart span=15m count as agent_payments"), 300),
        (single("Mandates verified per 15 min", f"{P} event=mandate.verified | timechart span=15m count as verified"), 300),
        (single("Mandates blocked per 15 min", f"{P} event=mandate.blocked | timechart span=15m count as blocked", "", BAD_HIGH(5, 20)), 300),
        (single("KYA registry errors per 15 min", f"{P} (event=kya.registry_unavailable OR 'mandate.block_reason'=\"mandate_kya_unavailable\") | timechart span=15m count as kya_down | fillnull value=0", "", BAD_HIGH(1, 10), "fail-closed blocks"), 300),
    ]),
    (90, [(md("**Mandate lifecycle** — agent asks the wallet → KYA lookup → mandate issued / refused → `checkout-api` verifies (limit, expiry, merchant, replay, KYA) → "
              "`mandate.verified` → acquirer, or `mandate.blocked` with a reason. When the registry is down every agent payment **fails closed** "
              "(`mandate_kya_unavailable`); human checkout is untouched. KYA tiers A–D are TukTukPay's own construct; vocabulary follows AP2 mandates."), 1200)]),
    (280, [
        (chart("splunk.bar", "Blocks by reason (mandate.block_reason)", f"{P} event=mandate.blocked | stats count by mandate.block_reason | sort - count"), 450),
        (table("Agents (KYA registry joined to mandate events)",
               f"{P} event IN (mandate.verified, mandate.blocked) | stats count(eval(event=\"mandate.verified\")) as verified count(eval(event=\"mandate.blocked\")) as blocked values(mandate.block_reason) as reasons by agent.id "
               "| lookup kya_registry.csv agent_id as agent.id OUTPUT operator kya_rating registered protocol | table agent.id operator kya_rating protocol registered verified blocked reasons | sort - blocked",
               "Click a row for that agent's mandate trail.", drill=link_search()), 750),
    ]),
    (240, [(chart("splunk.line", "Agent vs human: approval rate (%)",
                  f"{PAY} | timechart span=15m count(eval(event=\"payment.approved\" AND 'payment.initiator'=\"agent\")) as aa count(eval('payment.initiator'=\"agent\")) as an "
                  "count(eval(event=\"payment.approved\" AND 'payment.initiator'=\"human\")) as ha count(eval('payment.initiator'=\"human\")) as hn "
                  "| eval Agent=round(100*aa/an,1), Human=round(100*ha/hn,1) | fields _time Agent Human", yAxisMin=0, yAxisMax=100), 1200)]),
])

# ---------------- Risk model ----------------
page("Risk model", [
    (260, [
        (chart("splunk.line", "Approval rate by risk.model_version (%)",
               f"{PAY} | timechart span=10m count(eval(event=\"payment.approved\")) as a count as n by risk.model_version "
               "| foreach a:* [ eval \"<<MATCHSTR>>\"=round(100*'a:<<MATCHSTR>>'/'n:<<MATCHSTR>>',1) ] | fields - a:* n:*", yAxisMin=60, yAxisMax=100), 700),
        (chart("splunk.bar", "Risk declines by reason", f"{P} event=risk.declined | mvexpand risk.reasons | stats count by risk.reasons | sort - count | head 10"), 500),
    ]),
    (220, [(chart("splunk.line", "Inference latency from logs (risk.inference_ms, p90)",
                  f"{P} event IN (risk.canary_inference, risk.inference_slow) | timechart span=10m perc90(risk.inference_ms) as p90_ms by risk.model_version"), 700),
           (md(f"Act 2: the v3 canary false-declines IDR/PHP wallets and burns CPU. The detector line is 100 ms; the per-inference SLO on the logs is 50 ms. "
               f"[risk-engine in APM]({O11Y}/apm/troubleshooting?environments={ENV}&service=risk-engine) · AlwaysOn Profiling names `_infer_v3`."), 500)]),
])

# ---------------- Copilot cost & guardrails ----------------
page("Copilot cost & guardrails", [
    (140, [
        (single("Copilot cost per hour (USD)", f"{P} event=copilot.answered | timechart span=1h sum(copilot.cost_usd) as usd | eval usd=round(usd,2)", "$"), 300),
        (single("Tokens per 15 min", f"{P} event=copilot.answered | eval t='gen_ai.usage.input_tokens'+'gen_ai.usage.output_tokens' | timechart span=15m sum(t) as tokens"), 300),
        (single("Avg tool-loop iterations", f"{P} event=copilot.answered | timechart span=15m avg(copilot.iterations) as it | eval it=round(it,1)", "", BAD_HIGH(4, 8)), 300),
        (single("Guardrail blocks per 15 min", f"{P} event=copilot.answered guardrail.verdict=blocked | timechart span=15m count as blocks | fillnull value=0", "", BAD_HIGH(1, 5)), 300),
    ]),
    (260, [
        (chart("splunk.bar", "Cost by merchant (USD)", f"{P} event=copilot.answered | stats sum(copilot.cost_usd) as usd by merchant.id | eval usd=round(usd,2) | sort - usd"), 500),
        (table("Recent answers: tools, verdict, cost",
               f"{P} event=copilot.answered | table _time merchant.id gen_ai.request.model copilot.iterations gen_ai.tool.names guardrail.verdict copilot.cost_usd | head 50",
               f"OpenTelemetry GenAI spans feed the APM AI agents pages ([merchant-copilot]({O11Y}/apm/troubleshooting?environments={ENV}&service=merchant-copilot)).",
               drill=link_search()), 700),
    ]),
])

# ---------------- Ledger, settlement & webhooks ----------------
page("Ledger, settlement & webhooks", [
    (240, [
        (chart("splunk.line", "Ledger slow writes and pool waits per 10 min", f"{P} event IN (ledger.write_slow, db.pool.wait, ledger.write_failed) | timechart span=10m count by event"), 600),
        (chart("splunk.column", "Webhook deliveries by outcome", f"{P} event IN (webhook.delivered, webhook.delivery_failed, webhook.delivery_error, webhook.dead_lettered) | timechart span=10m count by event", stackMode="stacked"), 600),
    ]),
    (240, [(table("Reconciliation: approved payments today by merchant (to join with the the PSP daily file)",
                  f"{P} event=payment.approved earliest=@d | stats count as entries sum(payment.amount) as amount by merchant.id payment.currency "
                  "| lookup merchants.csv merchant_id as merchant.id OUTPUT category | sort - entries",
                  "Once the the PSP reconciliation CSV is loaded as recon_psp.csv, the difference column is one more lookup."), 1200)]),
])

# ---------------- Incidents & AI SRE ----------------
page("Incidents & AI SRE", [
    (300, [(table("Detector state changes (Observability Cloud → Splunk platform integration)",
                  f"{P} sourcetype=\"o11y:detector\" | table _time detector severity status incidentId service.name detectorUrl | sort - _time",
                  "Empty until the 'Splunk platform' notification integration is attached to the 20 TukTukPay detectors. Click a row to open the detector.",
                  drill=link_url("$row.detectorUrl.value$")), 1200)]),
    (240, [(table("Act timeline: chaos flags flipped from the war-room panel (config.changed)",
                  f"{P} event=config.changed | table _time service.name feature_flag.name feature_flag.enabled feature_flag.params | sort - _time | head 30", drill=link_search()), 1200)]),
])

definition = {
    "title": "TukTukPay · 11.11 control tower",
    "description": "Agentic commerce from the payment gateway's side: Splunk Cloud logs + Observability Cloud links. Built from the control-tower design",
    "inputs": {"input_time": {"type": "input.timerange", "title": "Time range", "options": {"token": "global_time", "defaultValue": "-4h,now"}}},
    "defaults": {"dataSources": {"ds.search": {"options": {"queryParameters": {"earliest": "$global_time.earliest$", "latest": "$global_time.latest$"}, "refresh": "60s", "refreshType": "delay"}}}},
    "dataSources": ds, "visualizations": viz,
    "layout": {"globalInputs": ["input_time"], "tabs": {"items": tabs}, "layoutDefinitions": layouts},
}

# ---- validate every search ----
bad = 0
for k, d in ds.items():
    r = S.search(d["options"]["query"], earliest="-4h")
    errs = [m["text"] for m in r.get("messages", []) if m["type"] in ("ERROR", "FATAL")] + ([r["error"]] if "error" in r else [])
    rows = len(r.get("results", []))
    if errs: bad += 1
    print(f"{k}: rows={rows} {'ERR ' + errs[0][:160] if errs else ''}")
print("searches:", len(ds), "with errors:", bad, "| tabs:", len(tabs), "| visualizations:", len(viz))
if "--validate-only" in sys.argv or bad:
    sys.exit(0 if not bad else 1)

xml = ('<dashboard version="2" theme="dark">\n  <label>TukTukPay · 11.11 control tower</label>\n  <description>Agentic commerce from the payment gateway side</description>\n'
       f'  <definition><![CDATA[{json.dumps(definition, indent=1)}]]></definition>\n'
       '  <meta type="hiddenElements"><![CDATA[{"hideEdit": false, "hideOpenInSearch": false, "hideExport": false}]]></meta>\n</dashboard>')
st, b = S.get(f"/servicesNS/nobody/{APP}/data/ui/views/{NAME}")
if st == 200:
    st, b = S.post(f"/servicesNS/nobody/{APP}/data/ui/views/{NAME}", {"eai:data": xml})
else:
    st, b = S.post(f"/servicesNS/nobody/{APP}/data/ui/views", {"name": NAME, "eai:data": xml})
print("save view:", st, b[:200] if st not in (200, 201) else "ok")
if st in (200, 201):
    st2, b2 = S.post(f"/servicesNS/nobody/{APP}/data/ui/views/{NAME}/acl", {"sharing": "app", "owner": "nobody", "perms.read": "*", "perms.write": "admin,sc_admin"})
    print("share:", st2, "ok" if st2 == 200 else b2[:200])
    print("URL: https://example-stack.splunkcloud.com/en-US/app/search/" + NAME)
