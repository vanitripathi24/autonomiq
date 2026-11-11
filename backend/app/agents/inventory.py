"""Inventory Agent: stock coverage, shortages and restock quantities from the demand forecast."""
import math
from sqlalchemy import select
from .. import models as m
from . import sales

SAFETY = 1.15  # 15% safety stock on top of forecast demand


def assess(db, business_id):
    out = []
    for p in db.scalars(select(m.Product).where(m.Product.business_id == business_id).order_by(m.Product.id)):
        fc = sales.forecast(db, business_id, p.id)
        avg = max(fc["avg_daily"], 0.01)
        cover = p.stock / avg
        shortage = max(0, math.ceil(fc["need_14d"] * SAFETY) - p.stock)
        status = "critical" if cover < 5 else "low" if cover < 14 else "overstock" if cover > 60 else "healthy"
        margin = (p.price - p.cost) / p.price if p.price else 0
        out.append({
            "product_id": p.id, "sku": p.sku, "name": p.name, "stock": p.stock, "reorder_level": p.reorder_level,
            "cost": p.cost, "price": p.price, "margin": round(margin, 4), "avg_daily": fc["avg_daily"],
            "trend_pct": fc["trend_pct"], "coverage_days": round(cover, 1), "need_14d": fc["need_14d"],
            "shortage": shortage, "status": status,
        })
    return out
