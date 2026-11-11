"""Business Analyst Agent: KPIs, problem detection and suggested actions."""
from datetime import date, timedelta
from collections import defaultdict
from sqlalchemy import select
from .. import models as m
from . import inventory, llm


def analyze(db, business):
    today = date.today()
    sales = db.scalars(select(m.Sale).where(m.Sale.business_id == business.id, m.Sale.day >= today - timedelta(days=59))).all()
    by_day = defaultdict(lambda: [0.0, 0.0])
    cur = [0.0, 0.0, 0]
    prev = [0.0, 0.0]
    for s in sales:
        rev, prof = s.qty * s.unit_price, s.qty * (s.unit_price - s.unit_cost)
        by_day[s.day][0] += rev
        by_day[s.day][1] += prof
        if s.day > today - timedelta(days=30):
            cur[0] += rev; cur[1] += prof; cur[2] += s.qty
        else:
            prev[0] += rev; prev[1] += prof
    series = []
    for i in range(59, -1, -1):
        d = today - timedelta(days=i)
        series.append({"day": d.isoformat(), "revenue": round(by_day[d][0], 2), "profit": round(by_day[d][1], 2)})
    inv = inventory.assess(db, business.id)
    issues = []
    for r in inv:
        if r["status"] in ("critical", "low"):
            issues.append({
                "severity": "high" if r["status"] == "critical" else "medium", "agent": "Inventory Agent",
                "title": f"{r['name']} will run out in about {r['coverage_days']:.0f} days",
                "detail": f"{r['stock']} in stock, forecast demand {r['avg_daily']}/day ({r['trend_pct']:+.0f}% trend).",
                "action": f"My inventory of {r['name']} is running low. Find the best supplier, negotiate a good deal, "
                          f"maintain at least {business.target_margin*100:.0f}% profit margin and prepare the payment.",
            })
        if r["margin"] < business.target_margin:
            issues.append({
                "severity": "medium", "agent": "Smart Pricing Agent",
                "title": f"{r['name']} margin is {r['margin']*100:.0f}%",
                "detail": f"Below the {business.target_margin*100:.0f}% target (cost ${r['cost']:.2f}, price ${r['price']:.2f}).",
                "action": "Find products with low profit margins and suggest a better supplier.",
            })
        if r["status"] == "overstock":
            issues.append({
                "severity": "low", "agent": "Inventory Agent", "title": f"{r['name']} is overstocked",
                "detail": f"{r['coverage_days']:.0f} days of cover; consider a discount.",
                "action": "Suggest better prices for my products.",
            })
    if prev[0] and cur[0] < prev[0] * 0.92:
        issues.append({"severity": "high", "agent": "Business Analyst Agent", "title": "Revenue fell versus the previous 30 days",
                       "detail": f"${cur[0]:,.0f} vs ${prev[0]:,.0f}.", "action": "How is my business performing?"})
    issues.sort(key=lambda i: {"high": 0, "medium": 1, "low": 2}[i["severity"]])
    margin = cur[1] / cur[0] if cur[0] else 0
    delta = (cur[0] / prev[0] - 1) * 100 if prev[0] else 0
    stock_value = sum(r["stock"] * r["cost"] for r in inv)
    facts = (f"Revenue ${cur[0]:,.0f} over 30 days ({delta:+.1f}% vs prior), profit ${cur[1]:,.0f} at {margin*100:.1f}% margin. "
             f"{len(issues)} issues found, {sum(1 for i in issues if i['severity']=='high')} high priority.")
    narrative = llm.complete("You are a concise business analyst for a small retailer. Two sentences, plain language.", facts) or facts
    return {
        "kpis": {"revenue_30d": round(cur[0], 2), "revenue_delta_pct": round(delta, 1), "profit_30d": round(cur[1], 2),
                 "margin_30d": round(margin, 4), "units_30d": cur[2], "cash": business.cash, "stock_value": round(stock_value, 2)},
        "series": series, "issues": issues, "narrative": narrative, "inventory": inv,
    }
