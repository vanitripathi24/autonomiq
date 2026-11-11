"""End-to-end test: command -> negotiation -> approval -> PayPal (simulated) -> settlement -> refund."""
import os
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
for k in ("PAYPAL_CLIENT_ID", "PAYPAL_CLIENT_SECRET", "GEMINI_API_KEY", "OPENAI_API_KEY"):
    os.environ[k] = ""
from fastapi.testclient import TestClient
from app.main import app


def test_full_flow():
    with TestClient(app) as c:
        cmd = "Negotiate 100 units of Wireless Headphones with at least 25% profit margin."
        r = c.post("/api/command", json={"business_id": 1, "text": cmd}).json()
        assert r["intent"] == "restock" and r["result"]["deal_id"]
        assert r["result"]["margin"] >= 0.25
        did = r["result"]["deal_id"]
        assert c.post(f"/api/deals/{did}/approve").json()["status"] == "approved"
        order = c.post("/api/paypal/orders", json={"deal_id": did}).json()
        assert c.post(f"/api/paypal/orders/{order['id']}/capture").json()["status"] == "paid"
        assert c.post(f"/api/paypal/orders/{order['id']}/capture").json()["status"] == "paid"  # idempotent
        assert c.post(f"/api/deals/{did}/refund").json()["status"] == "refunded"
        cash = {b["id"]: b["cash"] for b in c.get("/api/businesses").json()}
        assert cash[1] == 25000


def test_floor_price_is_private():
    with TestClient(app) as c:
        assert all("floor_price" not in x for x in c.get("/api/listings").json())
