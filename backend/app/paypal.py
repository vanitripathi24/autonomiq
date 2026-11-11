"""PayPal Orders v2 / Payments / Refund / Webhooks client. Falls back to simulated mode without credentials."""
import json
import time
import uuid
import httpx
from . import config

_tok = {"v": None, "exp": 0.0}


def live() -> bool:
    return config.PAYPAL_LIVE


def _token():
    if _tok["v"] and time.time() < _tok["exp"] - 30:
        return _tok["v"]
    r = httpx.post(f"{config.PAYPAL_BASE}/v1/oauth2/token", data={"grant_type": "client_credentials"},
                   auth=(config.PAYPAL_CLIENT_ID, config.PAYPAL_CLIENT_SECRET), timeout=20)
    r.raise_for_status()
    j = r.json()
    _tok.update(v=j["access_token"], exp=time.time() + j.get("expires_in", 3000))
    return _tok["v"]


def _call(method, path, body=None):
    r = httpx.request(method, f"{config.PAYPAL_BASE}{path}", json=body, timeout=30, headers={
        "Authorization": f"Bearer {_token()}", "Content-Type": "application/json", "PayPal-Request-Id": uuid.uuid4().hex})
    if r.status_code >= 400:
        raise RuntimeError(f"PayPal {r.status_code}: {r.text[:300]}")
    return r.json() if r.content else {}


def create_order(deal_id: int, amount: float, description: str):
    if not live():
        return {"id": f"SIM-{uuid.uuid4().hex[:12].upper()}", "status": "CREATED", "simulated": True}
    return _call("POST", "/v2/checkout/orders", {
        "intent": "CAPTURE",
        "purchase_units": [{"reference_id": f"deal-{deal_id}", "custom_id": str(deal_id), "description": description[:120],
                            "amount": {"currency_code": "USD", "value": f"{amount:.2f}"}}],
    })


def capture_order(order_id: str, deal_id: int, amount: float):
    if not live() or order_id.startswith("SIM-"):
        cap = f"SIMCAP-{uuid.uuid4().hex[:10].upper()}"
        return {"id": order_id, "status": "COMPLETED", "simulated": True, "purchase_units": [{"payments": {"captures": [
            {"id": cap, "status": "COMPLETED", "custom_id": str(deal_id), "amount": {"currency_code": "USD", "value": f"{amount:.2f}"}}]}}]}
    return _call("POST", f"/v2/checkout/orders/{order_id}/capture")


def refund_capture(capture_id: str, amount: float):
    if not live() or capture_id.startswith("SIMCAP-"):
        return {"id": f"SIMREF-{uuid.uuid4().hex[:10].upper()}", "status": "COMPLETED", "simulated": True}
    return _call("POST", f"/v2/payments/captures/{capture_id}/refund", {"amount": {"value": f"{amount:.2f}", "currency_code": "USD"}})


def verify_webhook(headers, event: dict) -> bool:
    """Verify a webhook with PayPal's verify-webhook-signature API. Needs PAYPAL_WEBHOOK_ID."""
    if not (live() and config.PAYPAL_WEBHOOK_ID):
        return False
    try:
        res = _call("POST", "/v1/notifications/verify-webhook-signature", {
            "auth_algo": headers.get("paypal-auth-algo"), "cert_url": headers.get("paypal-cert-url"),
            "transmission_id": headers.get("paypal-transmission-id"), "transmission_sig": headers.get("paypal-transmission-sig"),
            "transmission_time": headers.get("paypal-transmission-time"), "webhook_id": config.PAYPAL_WEBHOOK_ID, "webhook_event": event})
        return res.get("verification_status") == "SUCCESS"
    except Exception:
        return False
