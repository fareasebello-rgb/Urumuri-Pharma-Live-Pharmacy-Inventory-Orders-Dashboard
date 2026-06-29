"""
app.py
------
FastAPI backend for the Urumuri Pharma Ltd analytics dashboard.

Reads from data/sales.db (SQLite) and exposes aggregated JSON
endpoints the frontend dashboard consumes. Most endpoints accept an
optional `?months=6` query param — pass it to filter the underlying
sales data to the most recent N months; omit it for all-time (12 months
in this dataset).

Run:
    pip install -r requirements.txt
    python3 data_generator.py        # generates data/sales.db (run once)
    uvicorn app:app --reload --port 8000

Then open frontend/index.html in a browser — it fetches from
http://localhost:8000/api/* and falls back to frontend/data.json if
the API isn't reachable.
"""

import sqlite3
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from insights import compute_insights, get_cutoff_date

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "sales.db"
MONTHLY_CEILING_RWF = 15_000_000

app = FastAPI(
    title="Urumuri Pharma Analytics API",
    description="Sales, inventory, and insights for a Rwandan pharmaceutical distribution company.",
    version="1.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_conn():
    if not DB_PATH.exists():
        raise HTTPException(
            status_code=500,
            detail="Database not found. Run 'python3 data_generator.py' first.",
        )
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def cutoff_for(conn, months: Optional[int]):
    if not months:
        return None
    cur = conn.cursor()
    cur.execute("SELECT MAX(date) AS d FROM sales")
    max_date = cur.fetchone()["d"]
    return get_cutoff_date(max_date, months)


def sales_rows(conn, cutoff):
    cur = conn.cursor()
    if cutoff:
        cur.execute("SELECT * FROM sales WHERE date >= ?", (cutoff,))
    else:
        cur.execute("SELECT * FROM sales")
    return [dict(r) for r in cur.fetchall()]


@app.get("/")
def root():
    return {
        "service": "Urumuri Pharma Analytics API",
        "currency": "RWF",
        "endpoints": [
            "/api/kpis?months=6",
            "/api/monthly-revenue?months=6",
            "/api/category-breakdown?months=6",
            "/api/region-breakdown?months=6",
            "/api/client-type-breakdown?months=6",
            "/api/top-products?months=6&limit=8",
            "/api/new-orders?limit=12",
            "/api/inventory?months=6&status=all|reorder",
            "/api/insights?months=6",
        ],
    }


@app.get("/api/kpis")
def kpis(months: Optional[int] = Query(None)):
    conn = get_conn()
    cutoff = cutoff_for(conn, months)
    rows = sales_rows(conn, cutoff)

    total_orders = len(rows)
    total_revenue = sum(r["line_total_rwf"] for r in rows)

    monthly = {}
    for r in rows:
        monthly.setdefault(r["month"], 0)
        monthly[r["month"]] += r["line_total_rwf"]
    best_month = max(monthly, key=monthly.get) if monthly else None

    regions = {r["region"] for r in rows}
    products = {r["product"] for r in rows}

    inv = inventory_rows(conn, cutoff)
    reorder_count = sum(1 for r in inv if r["needs_reorder"])

    conn.close()
    return {
        "total_revenue_rwf": total_revenue,
        "total_orders": total_orders,
        "avg_order_value_rwf": round(total_revenue / total_orders) if total_orders else 0,
        "best_month": best_month,
        "best_month_revenue_rwf": monthly.get(best_month, 0),
        "active_regions": len(regions),
        "active_products": len(products),
        "reorder_count": reorder_count,
        "monthly_ceiling_rwf": MONTHLY_CEILING_RWF,
    }


@app.get("/api/monthly-revenue")
def monthly_revenue(months: Optional[int] = Query(None)):
    conn = get_conn()
    cutoff = cutoff_for(conn, months)
    rows = sales_rows(conn, cutoff)
    conn.close()
    monthly = {}
    for r in rows:
        monthly.setdefault(r["month"], 0)
        monthly[r["month"]] += r["line_total_rwf"]
    return [{"month": m, "revenue_rwf": monthly[m]} for m in sorted(monthly)]


@app.get("/api/category-breakdown")
def category_breakdown(months: Optional[int] = Query(None)):
    conn = get_conn()
    cutoff = cutoff_for(conn, months)
    rows = sales_rows(conn, cutoff)
    conn.close()
    totals = {}
    for r in rows:
        totals.setdefault(r["category"], 0)
        totals[r["category"]] += r["line_total_rwf"]
    return sorted(
        ({"category": k, "revenue_rwf": v} for k, v in totals.items()),
        key=lambda x: x["revenue_rwf"], reverse=True,
    )


@app.get("/api/region-breakdown")
def region_breakdown(months: Optional[int] = Query(None)):
    conn = get_conn()
    cutoff = cutoff_for(conn, months)
    rows = sales_rows(conn, cutoff)
    conn.close()
    totals = {}
    for r in rows:
        totals.setdefault(r["region"], 0)
        totals[r["region"]] += r["line_total_rwf"]
    return sorted(
        ({"region": k, "revenue_rwf": v} for k, v in totals.items()),
        key=lambda x: x["revenue_rwf"], reverse=True,
    )


@app.get("/api/client-type-breakdown")
def client_type_breakdown(months: Optional[int] = Query(None)):
    conn = get_conn()
    cutoff = cutoff_for(conn, months)
    rows = sales_rows(conn, cutoff)
    conn.close()
    totals = {}
    for r in rows:
        totals.setdefault(r["client_type"], 0)
        totals[r["client_type"]] += r["line_total_rwf"]
    return sorted(
        ({"client_type": k, "revenue_rwf": v} for k, v in totals.items()),
        key=lambda x: x["revenue_rwf"], reverse=True,
    )


@app.get("/api/top-products")
def top_products(months: Optional[int] = Query(None), limit: int = 8):
    conn = get_conn()
    cutoff = cutoff_for(conn, months)
    rows = sales_rows(conn, cutoff)
    conn.close()
    totals = {}
    for r in rows:
        totals.setdefault(r["product"], {"revenue": 0, "units": 0})
        totals[r["product"]]["revenue"] += r["line_total_rwf"]
        totals[r["product"]]["units"] += r["quantity"]
    ranked = sorted(
        ({"product": k, **v} for k, v in totals.items()),
        key=lambda x: x["revenue"], reverse=True,
    )
    return ranked[:limit]


@app.get("/api/new-orders")
def new_orders(limit: int = 12):
    """Most recent transactions, newest first — shown as the
    'New Orders' panel near the top of the dashboard."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT transaction_id, date, product, category, quantity,
               line_total_rwf, region, client_name, client_type
        FROM sales ORDER BY date DESC, transaction_id DESC LIMIT ?
    """, (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def inventory_rows(conn, cutoff):
    """Inventory joined with sales velocity for the given window, sorted
    by urgency (needs_reorder first, then soonest to run out) — not
    alphabetical."""
    cur = conn.cursor()
    if cutoff:
        cur.execute("""
            SELECT product, SUM(quantity) AS units, MIN(date) AS d0, MAX(date) AS d1
            FROM sales WHERE date >= ? GROUP BY product
        """, (cutoff,))
    else:
        cur.execute("""
            SELECT product, SUM(quantity) AS units, MIN(date) AS d0, MAX(date) AS d1
            FROM sales GROUP BY product
        """)
    velocity = {}
    for row in cur.fetchall():
        from datetime import date as _date
        d0, d1 = _date.fromisoformat(row["d0"]), _date.fromisoformat(row["d1"])
        span = max(1, (d1 - d0).days + 1)
        velocity[row["product"]] = row["units"] / span

    cur.execute("SELECT * FROM inventory")
    items = []
    for row in cur.fetchall():
        d = dict(row)
        avg_daily = velocity.get(d["product"], 0)
        d["avg_daily_units_sold"] = round(avg_daily, 2)
        d["days_of_stock_remaining"] = round(d["stock_on_hand"] / avg_daily, 1) if avg_daily > 0 else None
        d["needs_reorder"] = d["stock_on_hand"] <= d["reorder_threshold"]
        items.append(d)

    items.sort(key=lambda r: (
        0 if r["needs_reorder"] else 1,
        r["days_of_stock_remaining"] if r["days_of_stock_remaining"] is not None else 9_999,
    ))
    return items


@app.get("/api/inventory")
def inventory(months: Optional[int] = Query(None), status: str = "all"):
    conn = get_conn()
    cutoff = cutoff_for(conn, months)
    items = inventory_rows(conn, cutoff)
    conn.close()
    if status == "reorder":
        items = [i for i in items if i["needs_reorder"]]
    return items


@app.get("/api/insights")
def insights(months: Optional[int] = Query(None)):
    conn = get_conn()
    cutoff = cutoff_for(conn, months)
    rows = sales_rows(conn, cutoff)
    inv = inventory_rows(conn, cutoff)
    conn.close()

    monthly, category_totals, region_totals = {}, {}, {}
    for r in rows:
        monthly.setdefault(r["month"], 0)
        monthly[r["month"]] += r["line_total_rwf"]
        category_totals.setdefault(r["category"], 0)
        category_totals[r["category"]] += r["line_total_rwf"]
        region_totals.setdefault(r["region"], 0)
        region_totals[r["region"]] += r["line_total_rwf"]

    total_revenue = sum(monthly.values())
    return compute_insights(monthly, category_totals, region_totals, total_revenue, len(rows), inv)
