"""Orchestrator Agent: a LangGraph workflow that routes a plain-language command to the right agents."""
import operator
import re
from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
from sqlalchemy import select
from .. import models as m
from . import llm, inventory, pricing, supplier, sales, analyst, twin, negotiation

FLOWS = ["restock", "margin_review", "pricing", "forecast", "twin", "analyze"]


class OState(TypedDict):
    text: str
    business_id: int
    intent: str
    steps: Annotated[list, operator.add]
    result: dict
    summary: str


def step(agent, title, detail=""):
    return {"agent": agent, "title": title, "detail": detail}


def classify_rules(text):
    t = text.lower()
    if re.search(r"what (if|happens)|simulate|digital twin", t) or re.search(r"(reduce|lower|cut|raise|increase)\s+(the\s+)?price", t):
        return "twin"
    if re.search(r"low(er)?\s+(profit\s+)?margin", t):
        return "margin_review"
    if re.search(r"restock|running low|reorder|negotiat|best supplier|buy |order ", t):
        return "restock"
    if re.search(r"pric|discount", t):
        return "pricing"
    if re.search(r"forecast|predict|demand", t):
        return "forecast"
    return "analyze"


def classify(text):
    if llm.available():
        out = llm.complete_json(
            f"Classify a small-business owner's command into one intent of {FLOWS}. "
            "restock=buy stock/negotiate with suppliers; margin_review=find low-margin products and better suppliers; "
            "pricing=price recommendations; forecast=demand prediction; twin=what-if simulation; analyze=general performance. "
            'Reply as JSON {"intent": "..."}.', text)
        if out and out.get("intent") in FLOWS:
            return out["intent"]
    return classify_rules(text)


def match_product(text, products):
    t = text.lower()
    for p in products:
        words = [w for w in re.split(r"\W+", p.name.lower()) if len(w) > 3]
        if p.sku.lower() in t or any(w in t or w.rstrip("s") in t for w in words):
            return p
    return None


def parse_pct(text, pattern):
    mt = re.search(pattern, text.lower())
    return float(mt.group(1)) if mt else None


def run(db, business_id, text):
    biz = db.get(m.Business, business_id)

    def n_classify(s):
        intent = classify(s["text"])
        agents = {"restock": "Inventory, Supplier Intelligence, Buyer/Seller, Finance",
                  "margin_review": "Smart Pricing, Supplier Intelligence", "pricing": "Smart Pricing, Sales Intelligence",
                  "forecast": "Sales Intelligence, Inventory", "twin": "Digital Twin, Sales Intelligence",
                  "analyze": "Business Analyst, Inventory"}[intent]
        db.add(m.Decision(business_id=business_id, agent="Orchestrator Agent", action="Routed command",
                          reasoning=f'"{s["text"][:140]}" understood as {intent}; activating {agents}.'))
        return {"intent": intent, "steps": [step("Orchestrator Agent", "Understood your request", f"Intent: {intent.replace('_', ' ')}. Activating {agents} agents.")]}

    def n_restock(s):
        steps = []
        products = db.scalars(select(m.Product).where(m.Product.business_id == business_id).order_by(m.Product.id)).all()
        assess = {r["product_id"]: r for r in inventory.assess(db, business_id)}
        prod = match_product(s["text"], products)
        if not prod:
            risky = sorted(assess.values(), key=lambda r: r["coverage_days"])
            prod = db.get(m.Product, risky[0]["product_id"])
        a = assess[prod.id]
        steps.append(step("Inventory Agent", f"Checked stock for {prod.name}",
                          f"{a['stock']} in stock, forecast demand {a['avg_daily']}/day ({a['trend_pct']:+.0f}% trend) gives {a['coverage_days']:.0f} days of cover. "
                          f"14-day need with safety stock leaves a shortfall of {a['shortage']} units."))
        text_no_pct = re.sub(r"\d+(\.\d+)?\s*%", " ", s["text"])
        nums = re.findall(r"\b(\d{1,5})\b", text_no_pct)
        qty = int(nums[0]) if nums else a["shortage"]
        if qty <= 0:
            return {"steps": steps, "result": {"type": "restock", "message": f"{prod.name} has enough stock for the next 14 days. No purchase needed."}}
        mm = parse_pct(s["text"], r"(\d+(?:\.\d+)?)\s*%")
        min_margin = (mm / 100) if mm else biz.target_margin
        ceiling = round(prod.price * (1 - min_margin), 2)
        steps.append(step("Finance Agent", "Set the price limit",
                          f"Selling at ${prod.price:.2f} with at least {min_margin*100:.0f}% margin means paying no more than ${ceiling:.2f} per unit."))
        ranked = supplier.rank(db, prod.sku, qty, ceiling, exclude_business=business_id)[:3]
        if not ranked:
            return {"steps": steps, "result": {"type": "restock", "message": f"No registered supplier lists {prod.name}."}}
        steps.append(step("Supplier Intelligence Agent", f"Shortlisted {len(ranked)} suppliers",
                          "; ".join(f"{r['supplier']} (list ${r['list_price']:.2f}, {r['notes']})" for r in ranked)))
        listings = [db.get(m.Listing, r["listing_id"]) for r in ranked]
        gid, deals = negotiation.negotiate_many(db, biz, prod, qty, min_margin, listings)
        for d in deals:
            sname = db.get(m.Business, d.seller_id).name
            if d.status == "failed":
                steps.append(step("Buyer Agent", f"Negotiated with {sname}", "No agreement: their minimum price is above our ceiling."))
            else:
                steps.append(step("Buyer Agent", f"Negotiated with {sname}",
                                  f"Settled at ${d.unit_price:.2f} per unit after {d.rationale['rounds']} rounds, {d.rationale['saving_vs_list_pct']}% below their list price."))
        win = next((d for d in deals if d.status == "pending_approval"), None)
        if not win:
            return {"steps": steps, "result": {"type": "restock", "group_id": gid, "message": "No supplier would agree to terms within your margin limit."}}
        wname = db.get(m.Business, win.seller_id).name
        f = win.finance
        steps.append(step("Orchestrator Agent", f"Recommended {wname}",
                          f"Best balance of price, reliability and delivery (score {win.score}). {win.rationale.get('alternatives', '')}"))
        steps.append(step("Finance Agent", "Checked profitability",
                          f"Total ${win.total:,.2f} for {win.qty} units. Margin {f['margin']*100:.1f}%, expected profit ${f['expected_profit']:,.0f}, cash after payment ${f['cash_after']:,.0f}."))
        steps.append(step("Orchestrator Agent", "Waiting for your approval", "Approve the deal to continue to PayPal checkout."))
        return {"steps": steps, "result": {"type": "restock", "deal_id": win.id, "group_id": gid, "supplier": wname,
                                           "qty": win.qty, "unit_price": win.unit_price, "total": win.total, "margin": f["margin"]}}

    def n_margin(s):
        steps, items = [], []
        for r in inventory.assess(db, business_id):
            if r["margin"] < biz.target_margin:
                ceiling = round(r["price"] * (1 - biz.target_margin), 2)
                ranked = supplier.rank(db, r["sku"], 100, ceiling, exclude_business=business_id)
                best = ranked[0] if ranked else None
                items.append({"sku": r["sku"], "name": r["name"], "margin": r["margin"], "cost": r["cost"], "target_cost": ceiling,
                              "best_supplier": best["supplier"] if best else None, "list_price": best["list_price"] if best else None,
                              "command": f"Negotiate 100 units of {r['name']} with at least {biz.target_margin*100:.0f}% profit margin."})
        steps.append(step("Smart Pricing Agent", f"Found {len(items)} product(s) under the {biz.target_margin*100:.0f}% margin target",
                          ", ".join(f"{i['name']} ({i['margin']*100:.0f}%)" for i in items) or "All products meet the target."))
        for i in items:
            steps.append(step("Supplier Intelligence Agent", f"Looked for cheaper supply of {i['name']}",
                              f"{i['best_supplier']} lists at ${i['list_price']:.2f}; you need cost ≤ ${i['target_cost']:.2f} to hit target." if i["best_supplier"] else "No supplier found."))
        return {"steps": steps, "result": {"type": "margin_review", "items": items}}

    def n_pricing(s):
        recs = pricing.recommend(db, business_id)
        return {"steps": [step("Smart Pricing Agent", f"Prepared {len(recs)} price recommendation(s)",
                               "; ".join(f"{r['name']}: ${r['current_price']:.2f} → ${r['suggested_price']:.2f}" for r in recs) or "Current prices already fit demand and margin goals.")],
                "result": {"type": "pricing", "recommendations": recs}}

    def n_forecast(s):
        products = db.scalars(select(m.Product).where(m.Product.business_id == business_id)).all()
        prod = match_product(s["text"], products)
        rows = []
        for p in ([prod] if prod else products):
            fc = sales.forecast(db, business_id, p.id)
            rows.append({"sku": p.sku, "name": p.name, "next_14d": fc["need_14d"], "avg_daily": fc["avg_daily"], "trend_pct": fc["trend_pct"], "mape": fc["mape"]})
        return {"steps": [step("Sales Intelligence Agent", "Forecast demand for the next 14 days",
                               "; ".join(f"{r['name']}: {r['next_14d']} units ({r['trend_pct']:+.0f}%)" for r in rows))],
                "result": {"type": "forecast", "rows": rows}}

    def n_twin(s):
        t = s["text"].lower()
        pc = parse_pct(t, r"(?:reduce|lower|cut|decrease|drop)\s+(?:the\s+)?prices?\s+(?:by\s+)?(\d+(?:\.\d+)?)")
        pc = -pc if pc else parse_pct(t, r"(?:raise|increase)\s+(?:the\s+)?prices?\s+(?:by\s+)?(\d+(?:\.\d+)?)")
        sc = parse_pct(t, r"(?:increase|raise|add)\s+(?:the\s+)?(?:inventory|stock)\s+(?:by\s+)?(\d+(?:\.\d+)?)")
        cc = -6.0 if re.search(r"change\s+supplier|switch\s+supplier|new\s+supplier", t) else 0.0
        if pc is None and sc is None and not cc:
            pc = -10.0
        sim = twin.simulate(db, business_id, pc or 0, sc or 0, cc, 30)
        d = sim["delta"]
        return {"steps": [step("Digital Twin", "Simulated 30 days",
                               f"Price {pc or 0:+.0f}%, stock {sc or 0:+.0f}%, supplier cost {cc:+.0f}%: profit ${d['profit']:+,.0f}, revenue ${d['revenue']:+,.0f}.")],
                "result": {"type": "twin", "params": {"price_change": pc or 0, "stock_change": sc or 0, "cost_change": cc}, "sim": sim}}

    def n_analyze(s):
        a = analyst.analyze(db, biz)
        return {"steps": [step("Business Analyst Agent", "Reviewed the last 30 days", a["narrative"]),
                          step("Inventory Agent", f"Flagged {len(a['issues'])} issue(s)", "; ".join(i["title"] for i in a["issues"]) or "No problems found.")],
                "result": {"type": "analyze", "kpis": a["kpis"], "issues": a["issues"]}}

    def n_summarize(s):
        facts = " ".join(f"{x['agent']}: {x['title']}. {x['detail']}" for x in s["steps"])
        summary = llm.complete("You are AUTONOMIQ's orchestrator. Summarise what the agents did in 2-3 plain sentences for a shop owner. Keep every number exact.", facts) if llm.available() else None
        if not summary:
            r = s["result"]
            summary = (r.get("message") or
                       (f"{r['supplier']} offers {r['qty']} units at ${r['unit_price']:.2f} each (${r['total']:,.2f} total, {r['margin']*100:.1f}% margin). Review and approve to pay with PayPal." if r.get("deal_id") else
                        s["steps"][-1]["detail"]))
        db.add(m.Decision(business_id=business_id, deal_id=s["result"].get("deal_id"), agent="Orchestrator Agent", action="Completed command", reasoning=summary))
        db.commit()
        return {"summary": summary}

    g = StateGraph(OState)
    g.add_node("classify", n_classify)
    for name, fn in (("restock", n_restock), ("margin_review", n_margin), ("pricing", n_pricing), ("forecast", n_forecast), ("twin", n_twin), ("analyze", n_analyze)):
        g.add_node(name, fn)
        g.add_edge(name, "summarize")
    g.add_node("summarize", n_summarize)
    g.set_entry_point("classify")
    g.add_conditional_edges("classify", lambda s: s["intent"], {k: k for k in FLOWS})
    g.add_edge("summarize", END)
    out = g.compile().invoke({"text": text, "business_id": business_id, "intent": "", "steps": [], "result": {}, "summary": ""})
    return {"intent": out["intent"], "steps": out["steps"], "result": out["result"], "summary": out["summary"]}
