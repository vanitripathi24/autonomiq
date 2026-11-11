"""Supplier Intelligence Agent: ranks catalogue listings. Floor prices are never exposed to buyers."""
from sqlalchemy import select
from .. import models as m


def rank(db, sku, qty, max_price, exclude_business=None):
    rows = []
    for L in db.scalars(select(m.Listing).where(m.Listing.sku == sku)):
        if L.business_id == exclude_business or L.stock <= 0:
            continue
        s = db.get(m.Business, L.business_id)
        price_score = min(1.0, max_price / L.list_price)
        stock_ok = min(1.0, L.stock / max(qty, 1))
        delivery = max(0.0, 1 - (L.delivery_days - 1) / 10)
        score = 0.45 * price_score + 0.25 * L.reliability + 0.20 * delivery + 0.10 * stock_ok
        rows.append({
            "listing_id": L.id, "supplier_id": s.id, "supplier": s.name, "sku": sku, "list_price": L.list_price,
            "stock": L.stock, "reliability": L.reliability, "delivery_days": L.delivery_days,
            "score": round(score, 3),
            "notes": f"{L.reliability*100:.0f}% on-time, {L.delivery_days}-day delivery, "
                     + ("full quantity in stock" if L.stock >= qty else f"only {L.stock} units available"),
        })
    return sorted(rows, key=lambda r: -r["score"])
