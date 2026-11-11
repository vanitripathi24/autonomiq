"""Smart Pricing Agent: demand-, stock- and margin-aware price recommendations."""
import math
from sqlalchemy import select
from .. import models as m
from . import inventory


def _psych(p):
    return math.floor(p) + 0.99


def recommend(db, business_id):
    biz = db.get(m.Business, business_id)
    target = biz.target_margin
    recs = []
    for r in inventory.assess(db, business_id):
        cost, price = r["cost"], r["price"]
        floor_price = cost / (1 - target)
        adj, why = 0.0, []
        cover, trend = r["coverage_days"], r["trend_pct"]
        if cover < 7 and trend > 3:
            adj += 0.05
            why.append(f"only {cover:.0f} days of stock with demand up {trend:.0f}%")
        elif cover < 7:
            adj += 0.03
            why.append(f"only {cover:.0f} days of stock left")
        if cover > 60 and trend <= 0:
            adj -= 0.07
            why.append(f"{cover:.0f} days of stock and flat demand: clear excess")
        elif cover > 45:
            adj -= 0.03
            why.append(f"{cover:.0f} days of stock: mild discount to move units")
        if trend > 10:
            adj += 0.02
            why.append(f"demand rising {trend:.0f}%")
        elif trend < -10:
            adj -= 0.02
            why.append(f"demand falling {abs(trend):.0f}%")
        new = price * (1 + adj)
        if r["margin"] < target:
            why.append(f"margin {r['margin']*100:.0f}% is below the {target*100:.0f}% target")
        new = min(max(new, floor_price), price * 1.15)
        new = _psych(new)
        if new < floor_price:
            new += 1
        new = round(new, 2)
        if abs(new - price) < 0.01:
            continue
        recs.append({
            "product_id": r["product_id"], "sku": r["sku"], "name": r["name"], "current_price": price,
            "suggested_price": new, "change_pct": round((new / price - 1) * 100, 1),
            "current_margin": r["margin"], "new_margin": round((new - cost) / new, 4),
            "reason": "; ".join(why) or "keep margin at target",
        })
    return recs
