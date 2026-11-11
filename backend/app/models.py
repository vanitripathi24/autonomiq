from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey, JSON, Boolean
from .db import Base


def to_dict(o):
    return {c.name: getattr(o, c.name) for c in o.__table__.columns}


class Business(Base):
    __tablename__ = "businesses"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    kind = Column(String, nullable=False)  # retailer | supplier
    cash = Column(Float, default=0)
    target_margin = Column(Float, default=0.25)


class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), index=True)
    sku = Column(String, index=True)
    name = Column(String)
    cost = Column(Float)
    price = Column(Float)
    stock = Column(Integer, default=0)
    reorder_level = Column(Integer, default=0)


class Sale(Base):
    __tablename__ = "sales"
    id = Column(Integer, primary_key=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), index=True)
    product_id = Column(Integer, ForeignKey("products.id"), index=True)
    qty = Column(Integer)
    unit_price = Column(Float)
    unit_cost = Column(Float)
    day = Column(Date, index=True)


class Listing(Base):
    """A supplier's catalogue entry. floor_price is private to the Seller Agent."""
    __tablename__ = "listings"
    id = Column(Integer, primary_key=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), index=True)
    sku = Column(String, index=True)
    name = Column(String)
    list_price = Column(Float)
    floor_price = Column(Float)
    stock = Column(Integer)
    reliability = Column(Float, default=0.9)
    delivery_days = Column(Integer, default=5)


class Deal(Base):
    __tablename__ = "deals"
    id = Column(Integer, primary_key=True)
    group_id = Column(String, index=True)
    buyer_id = Column(Integer, ForeignKey("businesses.id"), index=True)
    seller_id = Column(Integer, ForeignKey("businesses.id"), index=True)
    sku = Column(String)
    product_name = Column(String)
    qty = Column(Integer)
    unit_price = Column(Float)
    total = Column(Float)
    delivery_days = Column(Integer)
    min_margin = Column(Float)
    ceiling = Column(Float)
    list_price = Column(Float)
    status = Column(String, default="pending_approval")
    score = Column(Float, default=0)
    finance = Column(JSON, default=dict)
    rationale = Column(JSON, default=dict)
    paypal_order_id = Column(String)
    capture_id = Column(String)
    refund_id = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Round(Base):
    __tablename__ = "rounds"
    id = Column(Integer, primary_key=True)
    deal_id = Column(Integer, ForeignKey("deals.id"), index=True)
    n = Column(Integer)
    agent = Column(String)  # buyer | seller
    action = Column(String)  # quote | offer | counter | accept | walk
    price = Column(Float)
    message = Column(String)
    reasoning = Column(String)


class Decision(Base):
    __tablename__ = "decisions"
    id = Column(Integer, primary_key=True)
    business_id = Column(Integer, index=True)
    deal_id = Column(Integer, index=True, nullable=True)
    agent = Column(String)
    action = Column(String)
    reasoning = Column(String)
    data = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)


class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True)
    deal_id = Column(Integer, index=True)
    order_id = Column(String)
    capture_id = Column(String)
    amount = Column(Float)
    status = Column(String)
    kind = Column(String)  # payment | refund
    source = Column(String)  # api | webhook | simulated
    created_at = Column(DateTime, default=datetime.utcnow)


class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    id = Column(Integer, primary_key=True)
    event_id = Column(String, unique=True)
    event_type = Column(String)
    verified = Column(Boolean, default=False)
    payload = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
