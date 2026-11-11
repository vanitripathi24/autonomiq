"""Applies the business effects of PayPal payment events. Idempotent, so API capture and webhook can both call it."""
from sqlalchemy import select
from . import models as m


def _log(db, deal, agent, action, reasoning):
    db.add(m.Decision(business_id=deal.buyer_id, deal_id=deal.id, agent=agent, action=action, reasoning=reasoning))


def settle(db, deal, capture_id, source):
    if deal.status in ("paid", "refunded"):
        return False
    buyer, seller = db.get(m.Business, deal.buyer_id), db.get(m.Business, deal.seller_id)
    prod = db.scalar(select(m.Product).where(m.Product.business_id == buyer.id, m.Product.sku == deal.sku))
    lst = db.scalar(select(m.Listing).where(m.Listing.business_id == seller.id, m.Listing.sku == deal.sku))
    if prod:
        new = prod.stock + deal.qty
        prod.cost = round((prod.cost * prod.stock + deal.unit_price * deal.qty) / new, 2)
        prod.stock = new
    else:
        db.add(m.Product(business_id=buyer.id, sku=deal.sku, name=deal.product_name, cost=deal.unit_price,
                         price=round(deal.unit_price * 1.4, 2), stock=deal.qty, reorder_level=0))
    if lst:
        lst.stock = max(0, lst.stock - deal.qty)
    buyer.cash = round(buyer.cash - deal.total, 2)
    seller.cash = round(seller.cash + deal.total, 2)
    deal.status, deal.capture_id = "paid", capture_id
    db.add(m.Transaction(deal_id=deal.id, order_id=deal.paypal_order_id, capture_id=capture_id, amount=deal.total,
                         status="COMPLETED", kind="payment", source=source))
    _log(db, deal, "Finance Agent", "Payment settled",
         f"${deal.total:,.2f} paid to {seller.name} via PayPal. Added {deal.qty} units to inventory, updated average cost, adjusted both cash balances.")
    db.commit()
    return True


def reverse(db, deal, refund_id, source):
    if deal.status != "paid":
        return False
    buyer, seller = db.get(m.Business, deal.buyer_id), db.get(m.Business, deal.seller_id)
    prod = db.scalar(select(m.Product).where(m.Product.business_id == buyer.id, m.Product.sku == deal.sku))
    lst = db.scalar(select(m.Listing).where(m.Listing.business_id == seller.id, m.Listing.sku == deal.sku))
    if prod:
        prod.stock = max(0, prod.stock - deal.qty)
    if lst:
        lst.stock += deal.qty
    buyer.cash = round(buyer.cash + deal.total, 2)
    seller.cash = round(seller.cash - deal.total, 2)
    deal.status, deal.refund_id = "refunded", refund_id
    db.add(m.Transaction(deal_id=deal.id, order_id=deal.paypal_order_id, capture_id=deal.capture_id, amount=deal.total,
                         status="COMPLETED", kind="refund", source=source))
    _log(db, deal, "Finance Agent", "Refund processed", f"${deal.total:,.2f} returned by {seller.name}. Stock and cash reversed.")
    db.commit()
    return True
