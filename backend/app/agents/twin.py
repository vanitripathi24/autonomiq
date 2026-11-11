"""Business Digital Twin: simulate decisions on forecast demand before executing them."""
from sqlalchemy import select
from .. import models as m
from . import sales


def _run(demand, stock, price, cost):
    rev = prof = lost = 0.0
    cum_r, cum_p, stockout = [], [], 0
    for d in demand:
        sold = min(stock, d)
        if d > stock:
            stockout += 1
            lost += d - stock
        stock -= sold
        rev += sold * price
        prof += sold * (price - cost)
        cum_r.append(round(rev, 2)); cum_p.append(round(prof, 2))
    return {"revenue": round(rev, 2), "profit": round(prof, 2), "lost_units": round(lost), "stockout_days": stockout,
            "cum_revenue": cum_r, "cum_profit": cum_p}


def simulate(db, business_id, price_change=0.0, stock_change=0.0, cost_change=0.0, horizon=30, product_id=None, elasticity=-1.4):
    q = select(m.Product).where(m.Product.business_id == business_id)
    if product_id:
        q = q.where(m.Product.id == product_id)
    base = {"cum_revenue": [0] * horizon, "cum_profit": [0] * horizon, "revenue": 0, "profit": 0, "lost_units": 0, "stockout_days": 0}
    scen = {k: (list(v) if isinstance(v, list) else v) for k, v in base.items()}
    for p in db.scalars(q):
        fc = sales.forecast(db, business_id, p.id, horizon)["forecast"]
        b = _run(fc, p.stock, p.price, p.cost)
        mult = (1 + price_change / 100) ** elasticity
        s = _run([d * mult for d in fc], p.stock * (1 + stock_change / 100), p.price * (1 + price_change / 100), p.cost * (1 + cost_change / 100))
        for acc, r in ((base, b), (scen, s)):
            for k in ("revenue", "profit", "lost_units", "stockout_days"):
                acc[k] += r[k]
            acc["cum_revenue"] = [a + c for a, c in zip(acc["cum_revenue"], r["cum_revenue"])]
            acc["cum_profit"] = [a + c for a, c in zip(acc["cum_profit"], r["cum_profit"])]
    d_rev, d_prof = scen["revenue"] - base["revenue"], scen["profit"] - base["profit"]
    insights = []
    if price_change:
        insights.append(f"A {price_change:+.0f}% price change shifts demand by about {((1+price_change/100)**elasticity-1)*100:+.0f}% (elasticity {elasticity}).")
    if stock_change and scen["lost_units"] < base["lost_units"]:
        insights.append(f"Extra stock recovers about {base['lost_units']-scen['lost_units']:.0f} units of otherwise lost sales.")
    if scen["stockout_days"] > 0:
        insights.append(f"Stock still runs out on {scen['stockout_days']} product-days; consider restocking.")
    insights.append(f"Profit over {horizon} days changes by ${d_prof:+,.0f} ({'better' if d_prof >= 0 else 'worse'}) with revenue ${d_rev:+,.0f}. No restocking is assumed.")
    return {"horizon": horizon, "baseline": base, "scenario": scen, "delta": {"revenue": round(d_rev, 2), "profit": round(d_prof, 2)}, "insights": insights}
