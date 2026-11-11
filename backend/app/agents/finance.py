"""Finance Agent: cost, margin, profit and cash checks for a proposed purchase."""


def evaluate(buyer, retail_price, qty, unit_price, min_margin):
    total = round(qty * unit_price, 2)
    margin = (retail_price - unit_price) / retail_price if retail_price else 0
    profit = round(qty * (retail_price - unit_price), 2)
    checks = [
        {"name": "Meets minimum margin", "ok": margin + 1e-9 >= min_margin,
         "detail": f"{margin*100:.1f}% vs {min_margin*100:.0f}% required"},
        {"name": "Cash available", "ok": buyer.cash >= total,
         "detail": f"${buyer.cash:,.0f} on hand vs ${total:,.2f} needed"},
    ]
    return {
        "total": total, "unit_price": unit_price, "retail_price": retail_price, "margin": round(margin, 4),
        "expected_revenue": round(qty * retail_price, 2), "expected_profit": profit,
        "cash_after": round(buyer.cash - total, 2), "checks": checks, "all_ok": all(c["ok"] for c in checks),
    }
