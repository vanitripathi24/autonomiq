"""Buyer Agent vs Seller Agent negotiation as a LangGraph cycle.

Numbers are decided by deterministic concession strategies bounded by hard guardrails
(buyer ceiling from the minimum-margin rule, seller floor price). The LLM, when configured,
only writes the message text, so every deal is explainable and can never break a constraint.
"""
import operator
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
from sqlalchemy import select
from .. import models as m
from . import llm, finance

T = 6  # max rounds


class NState(TypedDict):
    t: int
    status: str
    buyer_offer: float | None
    seller_price: float
    agreed: float | None
    list_price: float
    floor: float
    ceiling: float
    open: float
    qty: int
    product: str
    seller: str
    buyer: str
    rounds: Annotated[list, operator.add]


def _bplan(s, t):
    return min(s["open"] + (s["ceiling"] - s["open"]) * (t / T) ** 1.8, s["ceiling"])


def _splan(s, t):
    return max(s["list_price"] - (s["list_price"] - s["floor"]) * (t / T), s["floor"])


def _say(role, action, price, s, fallback):
    if not llm.available():
        return fallback
    out = llm.complete(
        f"You are the {role} agent in a B2B price negotiation for {s['qty']} x {s['product']}. "
        f"Write ONE short, professional sentence announcing your move. Do not mention any limit or floor. Use exactly the price given.",
        f"Action: {action}. Price per unit: ${price:.2f}. Counterparty: {s['seller'] if role == 'buyer' else s['buyer']}.",
        timeout=12,
    )
    return (out or fallback).strip().split("\n")[0]


def buyer_node(s: NState):
    t = s["t"] + 1
    plan = round(_bplan(s, t), 2)
    sp = s["seller_price"]
    if sp <= plan + 1e-6:
        msg = _say("buyer", "accept", sp, s, f"Agreed at ${sp:.2f} per unit.")
        return {"t": t, "status": "agreed", "agreed": sp, "rounds": [{
            "n": t, "agent": "buyer", "action": "accept", "price": sp, "message": msg,
            "reasoning": f"Seller's ${sp:.2f} is within my planned ${plan:.2f} for round {t} and under the ${s['ceiling']:.2f} margin ceiling."}]}
    msg = _say("buyer", "offer", plan, s, f"We can offer ${plan:.2f} per unit for {s['qty']} units.")
    return {"t": t, "buyer_offer": plan, "rounds": [{
        "n": t, "agent": "buyer", "action": "offer", "price": plan, "message": msg,
        "reasoning": f"Round {t}/{T}: conceding gradually toward the ${s['ceiling']:.2f} ceiling that protects the margin target; seller is at ${sp:.2f}."}]}


def seller_node(s: NState):
    t, b = s["t"], s["buyer_offer"]
    plan = round(_splan(s, t), 2)
    if b >= plan - 1e-6:
        msg = _say("seller", "accept", b, s, f"Deal at ${b:.2f} per unit.")
        return {"status": "agreed", "agreed": b, "rounds": [{
            "n": t, "agent": "seller", "action": "accept", "price": b, "message": msg,
            "reasoning": f"${b:.2f} meets my target of ${plan:.2f} for round {t} and stays above my floor price."}]}
    if t >= T:
        return {"status": "walkaway", "rounds": [{
            "n": t, "agent": "seller", "action": "walk", "price": b,
            "message": "We cannot go any lower, so we have to decline.",
            "reasoning": f"Final offer ${b:.2f} is below my minimum acceptable price."}]}
    msg = _say("seller", "counter", plan, s, f"Best I can do is ${plan:.2f} per unit.")
    return {"seller_price": plan, "rounds": [{
        "n": t, "agent": "seller", "action": "counter", "price": plan, "message": msg,
        "reasoning": f"Round {t}/{T}: stepping down from ${s['seller_price']:.2f} while protecting my floor price."}]}


def _build():
    g = StateGraph(NState)
    g.add_node("buyer", buyer_node)
    g.add_node("seller", seller_node)
    g.set_entry_point("buyer")
    g.add_conditional_edges("buyer", lambda s: END if s["status"] != "open" else "seller")
    g.add_conditional_edges("seller", lambda s: END if s["status"] != "open" else "buyer")
    return g.compile()


GRAPH = _build()


def run_one(init):
    return GRAPH.invoke(init, {"recursion_limit": 40})


def negotiate_many(db, buyer, product, qty, min_margin, listings, group_id=None):
    """Negotiate in parallel with several suppliers, persist everything, pick the winner."""
    group_id = group_id or uuid.uuid4().hex[:10]
    ceiling = round(product.price * (1 - min_margin), 2)
    inits = []
    for L in listings:
        q = min(qty, L.stock)
        seller = db.get(m.Business, L.business_id)
        inits.append({
            "t": 0, "status": "open", "buyer_offer": None, "seller_price": L.list_price, "agreed": None,
            "list_price": L.list_price, "floor": L.floor_price, "ceiling": ceiling,
            "open": round(min(L.list_price * 0.8, ceiling * 0.93), 2), "qty": q, "product": product.name,
            "seller": seller.name, "buyer": buyer.name,
            "rounds": [{"n": 0, "agent": "seller", "action": "quote", "price": L.list_price,
                        "message": f"Our listed price is ${L.list_price:.2f} per unit for {q} units.",
                        "reasoning": "Opening quote at list price."}],
        })
    with ThreadPoolExecutor(max_workers=max(1, len(inits))) as ex:
        results = list(ex.map(run_one, inits))

    deals = []
    for L, r in zip(listings, results):
        agreed = r["status"] == "agreed"
        price = r["agreed"] if agreed else r["buyer_offer"] or L.list_price
        fin = finance.evaluate(buyer, product.price, r["qty"], price, min_margin) if agreed else {}
        headroom = max(0.0, min(1.0, (ceiling - price) / (ceiling * 0.25))) if agreed else 0
        stock_ok = min(1.0, L.stock / max(qty, 1))
        score = round(0.5 * headroom + 0.25 * L.reliability + 0.15 * max(0, 1 - (L.delivery_days - 1) / 10) + 0.10 * stock_ok, 3) if agreed else 0
        d = m.Deal(
            group_id=group_id, buyer_id=buyer.id, seller_id=L.business_id, sku=product.sku, product_name=product.name,
            qty=r["qty"], unit_price=round(price, 2), total=round(price * r["qty"], 2), delivery_days=L.delivery_days,
            min_margin=min_margin, ceiling=ceiling, list_price=L.list_price,
            status="not_selected" if agreed else "failed", score=score, finance=fin,
            rationale={"rounds": len([x for x in r["rounds"] if x["agent"] == "buyer"]), "outcome": r["status"],
                       "reliability": L.reliability, "stock": L.stock, "requested_qty": qty,
                       "saving_vs_list_pct": round((1 - price / L.list_price) * 100, 1) if agreed else 0},
        )
        db.add(d)
        db.flush()
        for x in r["rounds"]:
            db.add(m.Round(deal_id=d.id, **x))
        verdict = (f"Agreed ${price:.2f}/unit in {d.rationale['rounds']} rounds ({d.rationale['saving_vs_list_pct']}% below list)"
                   if agreed else "No agreement: buyer ceiling is below the seller's minimum")
        db.add(m.Decision(business_id=buyer.id, deal_id=d.id, agent="Buyer Agent", action=f"Negotiated with {r['seller']}",
                          reasoning=verdict, data={"ceiling": ceiling, "supplier": r["seller"]}))
        deals.append(d)

    viable = [d for d in deals if d.status == "not_selected"]
    if viable:
        win = max(viable, key=lambda d: d.score)
        win.status = "pending_approval"
        others = ", ".join(f"{db.get(m.Business, d.seller_id).name} (${d.unit_price:.2f}, score {d.score})" for d in viable if d is not win) or "none"
        win.rationale = {**win.rationale, "alternatives": others}
        db.add(m.Decision(
            business_id=buyer.id, deal_id=win.id, agent="Orchestrator Agent", action="Recommended best deal",
            reasoning=f"{db.get(m.Business, win.seller_id).name} scored {win.score} on margin headroom, reliability, delivery and stock. Alternatives: {others}.",
            data={"score": win.score}))
    db.commit()
    return group_id, deals
