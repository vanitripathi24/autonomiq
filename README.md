# AUTONOMIQ

An AI-powered autonomous business operating system for the PayPal AI Hackathon. A team of agents analyses a business, negotiates with suppliers on the owner's behalf, and pays through PayPal once the owner approves.

**Flow:** business intelligence → autonomous negotiation → PayPal execution → updated books.

## What is built

| Area | What it does |
|---|---|
| Command center | Plain-language commands routed by a LangGraph orchestrator to the right agents, with a visible activity trail |
| Business Analyst, Inventory, Sales Intelligence | KPIs, issue detection, stock cover, and a scikit-learn demand forecast (trend + day-of-week Ridge model with a 14-day backtest) |
| Smart Pricing | Price recommendations from stock cover, demand trend and a margin floor, applied only on approval |
| Supplier Intelligence | Ranks suppliers on price vs margin limit, reliability, delivery and stock |
| Buyer and Seller agents | A LangGraph negotiation cycle run in parallel against the top three suppliers. Numbers come from bounded concession strategies (buyer ceiling from the margin rule, seller floor price); an LLM only writes the messages, so no deal can break a limit |
| Finance Agent | Total cost, margin, profit and cash checks before approval |
| Digital Twin | 30-day what-if simulation of price, inventory and supplier-cost changes |
| Collaborative network | Switch between the retailer and three supplier accounts. Suppliers tune their own Seller Agent (list and private floor price) |
| Explainable trail | Every decision logged with reasoning; every negotiation round can be replayed |
| PayPal | JS SDK checkout, Orders API v2 create and capture, Refund API, webhooks (with signature verification), idempotent settlement |

AG Grid is used for all data tables. Without PayPal keys the app runs a simulated checkout that exercises the same code paths (order, capture, webhook record, settlement, refund).

## Run locally

```bash
# backend
cd backend
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                   # optional, add keys here
uvicorn app.main:app --reload --port 8000

# frontend (new terminal)
cd frontend
npm install
npm run dev                                            # http://localhost:5173
```

The database is created and seeded on first start (SQLite). Use "Reset demo data" in the sidebar to restore it. To use Supabase or any Postgres, set `DATABASE_URL=postgresql+psycopg2://...`.

Tests: `cd backend && pytest -q tests`

## Turn on PayPal Sandbox

1. In the PayPal Developer Dashboard create a Sandbox app and copy the **Client ID** and **Secret** into `backend/.env` (`PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`). The sidebar then shows "PayPal Sandbox" and the real PayPal buttons appear on approved deals. Pay with a sandbox personal (buyer) account.
2. Webhooks: expose the API (Render URL, or ngrok locally) and add a sandbox webhook pointing to `https://YOUR-API/api/paypal/webhook` with these events: `CHECKOUT.ORDER.APPROVED`, `PAYMENT.CAPTURE.COMPLETED`, `PAYMENT.CAPTURE.DENIED`, `PAYMENT.CAPTURE.REFUNDED`. Put the webhook's ID in `PAYPAL_WEBHOOK_ID`. Signatures are then verified through PayPal's verify-webhook-signature API and unverified requests are rejected.
3. Settlement is idempotent, so the capture response and the webhook can both arrive without double-counting.

## Add an LLM (optional)

Set `GEMINI_API_KEY` (or `OPENAI_API_KEY`). The LLM then classifies commands, writes negotiation messages and summaries. Without a key, a deterministic rules engine does all of it.

## Deploy on Render

`render.yaml` defines an API web service and a static site. Set `VITE_API_URL` on the site to the API URL, and `CORS_ORIGINS` on the API to the site URL. Import `postman/AUTONOMIQ.postman_collection.json` into Postman and set `base_url`.

## Demo script (5 minutes)

1. Sign in as **VoltRetail Electronics**. The dashboard flags Wireless Headphones (about 2 days of stock) and Gaming Mouse (20% margin).
2. Command center: run the first example, or "Negotiate 100 units of Wireless Headphones with at least 25% profit margin." Watch the agents shortlist, negotiate with three suppliers and recommend one.
3. Open the deal: replay the negotiation, compare competing offers, read the finance checks, approve.
4. Pay with PayPal. Check Payments for the capture and the webhook event, and the Inventory page for updated stock and average cost.
5. Switch to **NovaTech Distributors** (or whichever supplier won): the deal and revenue appear; adjust the Seller Agent's floor price under Supplier network.
6. Back as the retailer: try the Digital Twin (price -10%, stock +20%) and Smart Pricing. Show the Decision trail.

## Notes and limits

- Authentication is not included; the account switcher exists for the demo. Add auth before real use.
- PayPal intent is `CAPTURE`. An authorize-then-capture flow (hold funds until stock is verified) is a natural extension in `paypal.py`.
- Forecasts use 90 days of seeded data; the digital twin assumes no restocking during the simulated period.
