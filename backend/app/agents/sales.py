"""Sales Intelligence Agent: demand forecasting with scikit-learn (trend + day-of-week Ridge regression)."""
from datetime import date, timedelta
import numpy as np
from sklearn.linear_model import Ridge
from sqlalchemy import select, func
from .. import models as m


def series(db, business_id, product_id, days=90):
    end = date.today()
    start = end - timedelta(days=days - 1)
    rows = db.execute(
        select(m.Sale.day, func.sum(m.Sale.qty))
        .where(m.Sale.business_id == business_id, m.Sale.product_id == product_id, m.Sale.day >= start)
        .group_by(m.Sale.day)
    ).all()
    by_day = {r[0]: r[1] for r in rows}
    ds = [start + timedelta(i) for i in range(days)]
    return ds, np.array([by_day.get(x, 0) for x in ds], dtype=float)


def _features(ds, offset):
    t = (np.arange(len(ds)) + offset) / 90.0
    dow = np.eye(7)[[x.weekday() for x in ds]]
    return np.column_stack([t, dow])


def forecast(db, business_id, product_id, horizon=14):
    ds, y = series(db, business_id, product_id)
    n, hold = len(y), 14
    model = Ridge(alpha=0.5).fit(_features(ds[:-hold], 0), y[:-hold])
    pred = np.clip(model.predict(_features(ds[-hold:], n - hold)), 0, None)
    mape = float(np.mean(np.abs(y[-hold:] - pred) / np.maximum(y[-hold:], 1)) * 100)
    model = Ridge(alpha=0.5).fit(_features(ds, 0), y)
    fds = [ds[-1] + timedelta(i + 1) for i in range(horizon)]
    fc = np.clip(model.predict(_features(fds, n)), 0, None)
    recent = float(y[-14:].mean())
    avg = float(fc.mean())
    return {
        "history_dates": [d.isoformat() for d in ds[-30:]],
        "history": [int(v) for v in y[-30:]],
        "dates": [d.isoformat() for d in fds],
        "forecast": [round(float(v), 1) for v in fc],
        "avg_daily": round(avg, 2),
        "recent_daily": round(recent, 2),
        "trend_pct": round((avg / recent - 1) * 100, 1) if recent > 0 else 0.0,
        "need_14d": int(np.ceil(fc[:14].sum())),
        "mape": round(mape, 1),
    }
