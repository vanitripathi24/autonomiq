import math
import random
from datetime import date, timedelta
from .db import Base, engine
from . import models as m

RETAIL_PRODUCTS = [
    # sku, name, cost, price, stock, reorder, base demand/day, weekly trend %
    ("HP-100", "Wireless Headphones", 41.0, 79.99, 18, 40, 6.0, 2.2),
    ("SP-200", "Bluetooth Speaker", 32.0, 59.99, 95, 40, 3.2, 0.0),
    ("CH-300", "Phone Charger 20W", 6.5, 14.99, 260, 80, 9.0, 0.3),
    ("CB-400", "USB-C Cable", 2.2, 7.99, 340, 100, 8.0, -0.5),
    ("SW-500", "Smart Watch", 58.0, 89.99, 40, 15, 2.0, 0.8),
    ("GM-600", "Gaming Mouse", 24.0, 29.99, 70, 25, 2.6, 0.0),
]
# business, sku, list, floor, stock, reliability, delivery
LISTINGS = [
    (2, "HP-100", 68.0, 52.0, 150, 0.93, 5), (2, "SP-200", 46.0, 36.0, 120, 0.93, 5), (2, "CH-300", 8.5, 6.8, 600, 0.93, 5),
    (3, "HP-100", 64.0, 55.0, 100, 0.88, 4), (3, "SP-200", 44.0, 38.0, 80, 0.88, 4), (3, "GM-600", 22.0, 18.0, 200, 0.88, 4),
    (4, "HP-100", 72.0, 50.0, 300, 0.97, 3), (4, "SW-500", 56.0, 45.0, 80, 0.97, 3),
    (4, "GM-600", 21.0, 17.0, 300, 0.97, 3), (4, "CB-400", 3.0, 1.9, 900, 0.97, 3),
]


def seed(db):
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    biz = [
        m.Business(id=1, name="VoltRetail Electronics", kind="retailer", cash=25000, target_margin=0.25),
        m.Business(id=2, name="SonicWholesale", kind="supplier", cash=8000),
        m.Business(id=3, name="AudioHub Traders", kind="supplier", cash=5000),
        m.Business(id=4, name="NovaTech Distributors", kind="supplier", cash=12000),
    ]
    db.add_all(biz)
    rng = random.Random(7)
    today = date.today()
    for i, (sku, name, cost, price, stock, reorder, base, trend) in enumerate(RETAIL_PRODUCTS, start=1):
        p = m.Product(id=i, business_id=1, sku=sku, name=name, cost=cost, price=price, stock=stock, reorder_level=reorder)
        db.add(p)
        for d in range(90):
            day = today - timedelta(days=89 - d)
            weekly = 1 + 0.25 * (1 if day.weekday() >= 5 else 0) - 0.05 * (1 if day.weekday() == 1 else 0)
            level = base * (1 + trend / 100 * d / 7) * weekly
            qty = max(0, int(round(rng.gauss(level, level * 0.18))))
            if qty:
                db.add(m.Sale(business_id=1, product_id=i, qty=qty, unit_price=price, unit_cost=cost, day=day))
    for b, sku, lp, fp, st, rel, dd in LISTINGS:
        name = next(r[1] for r in RETAIL_PRODUCTS if r[0] == sku)
        db.add(m.Listing(business_id=b, sku=sku, name=name, list_price=lp, floor_price=fp, stock=st, reliability=rel, delivery_days=dd))
    db.commit()
