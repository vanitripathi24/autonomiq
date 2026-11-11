import uuid
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select, or_
from sqlalchemy.orm import Session
from . import models as m, config, paypal, settlement, seed as seeder
from .db import get_db
from .models import to_dict
from .agents import analyst, sales, inventory, pricing, supplier, twin, orchestrator, negotiation, llm

router = APIRouter(prefix="/api")


def biz_or_404(db, bid):
    b = db.get(m.Business, bid)
    if not b:
        raise HTTPException(404, "Business not found")
    return b


def deal_or_404(db, did):
    d = db.get(m.Deal, did)
    if not d:
        raise HTTPException(404, "Deal not found")
    return d


@router.get("/health")
def health():
    return {"ok": True}


@router.get("/config")
def get_config():
    return {"paypal": {"client_id": config.PAYPAL_CLIENT_ID, "live": paypal.live(), "webhook_verification": bool(config.PAYPAL_WEBHOOK_ID),
                       "mode": "Sandbox" if "sandbox" in config.PAYPAL_BASE else "Live"},
            "llm": llm.provider()}


@router.get("/businesses")
def businesses(db: Session = Depends(get_db)):
    return [to_dict(b) for b in db.scalars(select(m.Business).order_by(m.Business.id))]


@router.post("/reset")
def reset(db: Session = Depends(get_db)):
    seeder.seed(db)
    return {"ok": True}


# ---------- dashboards ----------
@router.get("/dashboard")
def dashboard(business_id: int, db: Session = Depends(get_db)):
    b = biz_or_404(db, business_id)
    if b.kind == "retailer":
        return {"kind": "retailer", "business": to_dict(b), **analyst.analyze(db, b)}
    listings = db.scalars(select(m.Listing).where(m.Listing.business_id == b.id)).all()
    paid = db.scalars(select(m.Deal).where(m.Deal.seller_id == b.id, m.Deal.status == "paid")).all()
    open_deals = db.scalars(select(m.Deal).where(m.Deal.seller_id == b.id, m.Deal.status.in_(["pending_approval", "approved"]))).all()
    return {"kind": "supplier", "business": to_dict(b), "kpis": {
        "cash": b.cash, "revenue": round(sum(d.total for d in paid), 2), "units_sold": sum(d.qty for d in paid),
        "open_deals": len(open_deals), "stock_value": round(sum(l.stock * l.floor_price for l in listings), 2)},
        "listings": [to_dict(l) for l in listings]}


# ---------- inventory, sales, pricing ----------
@router.get("/products")
def products(business_id: int, db: Session = Depends(get_db)):
    return inventory.assess(db, business_id)


class ProductPatch(BaseModel):
    price: float | None = None
    cost: float | None = None
    stock: int | None = None
    reorder_level: int | None = None


@router.put("/products/{pid}")
def patch_product(pid: int, body: ProductPatch, db: Session = Depends(get_db)):
    p = db.get(m.Product, pid)
    if not p:
        raise HTTPException(404, "Product not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(p, k, v)
    db.commit()
    return to_dict(p)


@router.get("/sales")
def sales_list(business_id: int, limit: int = 300, db: Session = Depends(get_db)):
    rows = db.execute(select(m.Sale, m.Product.name).join(m.Product, m.Product.id == m.Sale.product_id)
                      .where(m.Sale.business_id == business_id).order_by(m.Sale.day.desc(), m.Sale.id.desc()).limit(limit)).all()
    return [{**to_dict(s), "product": n, "revenue": round(s.qty * s.unit_price, 2), "profit": round(s.qty * (s.unit_price - s.unit_cost), 2)} for s, n in rows]


@router.get("/forecast")
def forecast(business_id: int, product_id: int, horizon: int = 14, db: Session = Depends(get_db)):
    return sales.forecast(db, business_id, product_id, horizon)


@router.get("/pricing")
def pricing_recs(business_id: int, db: Session = Depends(get_db)):
    return pricing.recommend(db, business_id)


class PriceItem(BaseModel):
    product_id: int
    price: float


class PriceApply(BaseModel):
    items: list[PriceItem]


@router.post("/pricing/apply")
def pricing_apply(body: PriceApply, db: Session = Depends(get_db)):
    for it in body.items:
        p = db.get(m.Product, it.product_id)
        if p:
            db.add(m.Decision(business_id=p.business_id, agent="Smart Pricing Agent", action=f"Repriced {p.name}",
                              reasoning=f"Price changed from ${p.price:.2f} to ${it.price:.2f} on the owner's approval."))
            p.price = it.price
    db.commit()
    return {"ok": True, "applied": len(body.items)}


# ---------- network: listings & supplier intelligence ----------
@router.get("/listings")
def listings(business_id: int | None = None, db: Session = Depends(get_db)):
    q = select(m.Listing, m.Business.name).join(m.Business, m.Business.id == m.Listing.business_id)
    if business_id:
        q = q.where(m.Listing.business_id == business_id)
    out = []
    for l, name in db.execute(q.order_by(m.Listing.sku, m.Listing.list_price)).all():
        d = to_dict(l)
        d["supplier"] = name
        if not business_id:
            d.pop("floor_price")  # private to the seller agent
        out.append(d)
    return out


class ListingPatch(BaseModel):
    list_price: float | None = None
    floor_price: float | None = None
    stock: int | None = None


@router.put("/listings/{lid}")
def patch_listing(lid: int, body: ListingPatch, db: Session = Depends(get_db)):
    l = db.get(m.Listing, lid)
    if not l:
        raise HTTPException(404, "Listing not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(l, k, v)
    db.commit()
    return to_dict(l)


@router.get("/suppliers/rank")
def rank(sku: str, qty: int = 100, max_price: float = 60, exclude: int | None = None, db: Session = Depends(get_db)):
    return supplier.rank(db, sku, qty, max_price, exclude)


# ---------- twin, command, negotiation ----------
class TwinBody(BaseModel):
    business_id: int
    price_change: float = 0
    stock_change: float = 0
    cost_change: float = 0
    horizon: int = 30
    product_id: int | None = None


@router.post("/twin")
def twin_sim(b: TwinBody, db: Session = Depends(get_db)):
    return twin.simulate(db, b.business_id, b.price_change, b.stock_change, b.cost_change, b.horizon, b.product_id)


class CommandBody(BaseModel):
    business_id: int
    text: str


@router.post("/command")
def command(b: CommandBody, db: Session = Depends(get_db)):
    biz = biz_or_404(db, b.business_id)
    if biz.kind != "retailer":
        raise HTTPException(400, "The command center is available for retailer accounts. Suppliers tune their Seller Agent under Network.")
    return orchestrator.run(db, b.business_id, b.text)


class NegotiateBody(BaseModel):
    business_id: int
    sku: str
    qty: int
    min_margin: float = 0.25
    supplier_ids: list[int] | None = None


@router.post("/negotiate")
def negotiate(b: NegotiateBody, db: Session = Depends(get_db)):
    buyer = biz_or_404(db, b.business_id)
    prod = db.scalar(select(m.Product).where(m.Product.business_id == buyer.id, m.Product.sku == b.sku))
    if not prod:
        raise HTTPException(404, "SKU not in your catalogue")
    q = select(m.Listing).where(m.Listing.sku == b.sku, m.Listing.business_id != buyer.id, m.Listing.stock > 0)
    if b.supplier_ids:
        q = q.where(m.Listing.business_id.in_(b.supplier_ids))
    ls = db.scalars(q).all()
    if not ls:
        raise HTTPException(404, "No suppliers list this SKU")
    gid, deals = negotiation.negotiate_many(db, buyer, prod, b.qty, b.min_margin, ls)
    return {"group_id": gid, "deals": [to_dict(d) for d in deals]}


# ---------- deals ----------
def deal_view(db, d):
    out = to_dict(d)
    out["buyer"] = db.get(m.Business, d.buyer_id).name
    out["seller"] = db.get(m.Business, d.seller_id).name
    return out


@router.get("/deals")
def deals(business_id: int, db: Session = Depends(get_db)):
    q = select(m.Deal).where(or_(m.Deal.buyer_id == business_id, m.Deal.seller_id == business_id),
                             m.Deal.status.notin_(["not_selected", "failed"])).order_by(m.Deal.id.desc())
    return [deal_view(db, d) for d in db.scalars(q)]


@router.get("/deals/{did}")
def deal_detail(did: int, db: Session = Depends(get_db)):
    d = deal_or_404(db, did)
    rounds = db.scalars(select(m.Round).where(m.Round.deal_id == did).order_by(m.Round.id)).all()
    alts = db.scalars(select(m.Deal).where(m.Deal.group_id == d.group_id).order_by(m.Deal.score.desc())).all()
    logs = db.scalars(select(m.Decision).where(m.Decision.deal_id == did).order_by(m.Decision.id)).all()
    txs = db.scalars(select(m.Transaction).where(m.Transaction.deal_id == did).order_by(m.Transaction.id)).all()
    return {**deal_view(db, d), "rounds": [to_dict(r) for r in rounds], "competing": [deal_view(db, a) for a in alts],
            "decisions": [to_dict(x) for x in logs], "transactions": [to_dict(t) for t in txs]}


@router.post("/deals/{did}/approve")
def approve(did: int, db: Session = Depends(get_db)):
    d = deal_or_404(db, did)
    if d.status != "pending_approval":
        raise HTTPException(400, f"Deal is {d.status}")
    d.status = "approved"
    db.add(m.Decision(business_id=d.buyer_id, deal_id=d.id, agent="Owner", action="Approved deal",
                      reasoning=f"Owner approved ${d.total:,.2f} for {d.qty} x {d.product_name}."))
    db.commit()
    return deal_view(db, d)


@router.post("/deals/{did}/reject")
def reject(did: int, db: Session = Depends(get_db)):
    d = deal_or_404(db, did)
    if d.status not in ("pending_approval", "approved"):
        raise HTTPException(400, f"Deal is {d.status}")
    d.status = "rejected"
    db.add(m.Decision(business_id=d.buyer_id, deal_id=d.id, agent="Owner", action="Rejected deal", reasoning="Owner declined the proposed terms."))
    db.commit()
    return deal_view(db, d)


# ---------- PayPal ----------
class OrderBody(BaseModel):
    deal_id: int


@router.post("/paypal/orders")
def create_order(b: OrderBody, db: Session = Depends(get_db)):
    d = deal_or_404(db, b.deal_id)
    if d.status not in ("approved", "payment_failed"):
        raise HTTPException(400, "Approve the deal before paying")
    try:
        order = paypal.create_order(d.id, d.total, f"{d.qty} x {d.product_name} from {db.get(m.Business, d.seller_id).name}")
    except Exception as e:
        raise HTTPException(502, str(e))
    d.paypal_order_id = order["id"]
    db.add(m.Decision(business_id=d.buyer_id, deal_id=d.id, agent="Finance Agent", action="Created PayPal order",
                      reasoning=f"Order {order['id']} for ${d.total:,.2f} ({'simulated' if order.get('simulated') else 'PayPal Sandbox'})."))
    db.commit()
    return {"id": order["id"], "simulated": bool(order.get("simulated"))}


def _record_event(db, event, verified):
    eid = event.get("id") or f"EVT-{uuid.uuid4().hex[:10]}"
    if db.scalar(select(m.WebhookEvent).where(m.WebhookEvent.event_id == eid)):
        return False
    db.add(m.WebhookEvent(event_id=eid, event_type=event.get("event_type"), verified=verified, payload=event))
    db.commit()
    return True


def _find_deal(db, res):
    if res.get("custom_id", "").isdigit():
        d = db.get(m.Deal, int(res["custom_id"]))
        if d:
            return d
    oid = (res.get("supplementary_data", {}).get("related_ids", {}) or {}).get("order_id") or res.get("id")
    d = db.scalar(select(m.Deal).where(m.Deal.paypal_order_id == oid)) if oid else None
    if d:
        return d
    for link in res.get("links", []):
        if link.get("rel") == "up":
            cap = link["href"].rstrip("/").split("/")[-1]
            return db.scalar(select(m.Deal).where(m.Deal.capture_id == cap))
    return None


def _apply_event(db, event, source):
    t, res = event.get("event_type", ""), event.get("resource", {}) or {}
    d = _find_deal(db, res)
    if not d:
        return
    if t == "PAYMENT.CAPTURE.COMPLETED":
        settlement.settle(db, d, res.get("id"), source)
    elif t in ("PAYMENT.CAPTURE.DENIED", "PAYMENT.CAPTURE.DECLINED") and d.status in ("approved", "payment_failed"):
        d.status = "payment_failed"
        db.add(m.Decision(business_id=d.buyer_id, deal_id=d.id, agent="Finance Agent", action="Payment failed", reasoning="PayPal reported the capture was denied."))
        db.commit()
    elif t == "PAYMENT.CAPTURE.REFUNDED":
        settlement.reverse(db, d, res.get("id"), source)


@router.post("/paypal/orders/{order_id}/capture")
def capture(order_id: str, db: Session = Depends(get_db)):
    d = db.scalar(select(m.Deal).where(m.Deal.paypal_order_id == order_id))
    if not d:
        raise HTTPException(404, "Unknown order")
    try:
        res = paypal.capture_order(order_id, d.id, d.total)
    except Exception as e:
        raise HTTPException(502, str(e))
    cap = res["purchase_units"][0]["payments"]["captures"][0]
    if cap["status"] == "COMPLETED":
        settlement.settle(db, d, cap["id"], "simulated" if res.get("simulated") else "api")
        if res.get("simulated"):  # mimic the webhook PayPal would send
            ev = {"id": f"WH-SIM-{uuid.uuid4().hex[:8]}", "event_type": "PAYMENT.CAPTURE.COMPLETED", "resource": {**cap, "custom_id": str(d.id)}}
            _record_event(db, ev, False)
    else:
        d.status = "payment_failed"
        db.commit()
    return deal_view(db, d)


@router.post("/paypal/webhook")
async def webhook(request: Request, db: Session = Depends(get_db)):
    event = await request.json()
    verified = paypal.verify_webhook({k.lower(): v for k, v in request.headers.items()}, event)
    if paypal.live() and config.PAYPAL_WEBHOOK_ID and not verified:
        raise HTTPException(400, "Webhook signature verification failed")
    if _record_event(db, event, verified):
        _apply_event(db, event, "webhook")
    return {"ok": True}


@router.post("/deals/{did}/refund")
def refund(did: int, db: Session = Depends(get_db)):
    d = deal_or_404(db, did)
    if d.status != "paid" or not d.capture_id:
        raise HTTPException(400, "Only paid deals can be refunded")
    try:
        res = paypal.refund_capture(d.capture_id, d.total)
    except Exception as e:
        raise HTTPException(502, str(e))
    settlement.reverse(db, d, res["id"], "simulated" if res.get("simulated") else "api")
    if res.get("simulated"):
        _record_event(db, {"id": f"WH-SIM-{uuid.uuid4().hex[:8]}", "event_type": "PAYMENT.CAPTURE.REFUNDED",
                           "resource": {"id": res["id"], "custom_id": str(d.id), "status": "COMPLETED"}}, False)
    return deal_view(db, d)


@router.get("/transactions")
def transactions(business_id: int, db: Session = Depends(get_db)):
    q = (select(m.Transaction, m.Deal).join(m.Deal, m.Deal.id == m.Transaction.deal_id)
         .where(or_(m.Deal.buyer_id == business_id, m.Deal.seller_id == business_id)).order_by(m.Transaction.id.desc()))
    return [{**to_dict(t), "product": d.product_name, "qty": d.qty, "buyer": db.get(m.Business, d.buyer_id).name,
             "seller": db.get(m.Business, d.seller_id).name} for t, d in db.execute(q).all()]


@router.get("/webhooks")
def webhooks(db: Session = Depends(get_db)):
    return [to_dict(w) | {"payload": None} for w in db.scalars(select(m.WebhookEvent).order_by(m.WebhookEvent.id.desc()).limit(50))]


@router.get("/decisions")
def decisions(business_id: int, deal_id: int | None = None, limit: int = 200, db: Session = Depends(get_db)):
    q = select(m.Decision).where(m.Decision.business_id == business_id)
    if deal_id:
        q = q.where(m.Decision.deal_id == deal_id)
    return [to_dict(x) for x in db.scalars(q.order_by(m.Decision.id.desc()).limit(limit))]
