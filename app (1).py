"""
app.py
------
FastAPI backend for the Urumuri Pharma Ltd analytics dashboard.

Reads from data/sales.db (SQLite) and exposes aggregated JSON
endpoints the frontend dashboard consumes. This is intentionally
simple and well-commented so it's easy to extend — swap SQLite for
Postgres/MySQL, add auth, add write endpoints, rewrite in Go, etc.

Run:
    pip install -r requirements.txt
    python3 data_generator.py        # generates data/sales.db (run once)
    uvicorn app:app --reload --port 8000

Then open frontend/index.html in a browser (or serve it with any
static file server) — it will fetch from http://localhost:8000/api/*.
"""

import sqlite3
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "sales.db"
MONTHLY_CEILING_RWF = 15_000_000

app = FastAPI(
    title="Urumuri Pharma Analytics API",
    description="Sales analytics for a Rwandan pharmaceutical distribution company.",
    version="1.0.0",
)

# Allow the static frontend (served from file:// or any localhost port) to call this API.
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


@app.get("/")
def root():
    return {
        "service": "Urumuri Pharma Analytics API",
        "currency": "RWF",
        "endpoints": [
            "/api/kpis",
            "/api/monthly-revenue",
            "/api/category-breakdown",
            "/api/region-breakdown",
            "/api/client-type-breakdown",
            "/api/top-products",
            "/api/recent-transactions",
        ],
    }


@app.get("/api/kpis")
def kpis():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS n, SUM(line_total_rwf) AS total FROM sales")
    row = cur.fetchone()
    total_orders, total_revenue = row["n"], row["total"] or 0

    cur.execute("""
        SELECT month, SUM(line_total_rwf) AS revenue
        FROM sales GROUP BY month ORDER BY revenue DESC LIMIT 1
    """)
    best = cur.fetchone()

    cur.execute("SELECT COUNT(DISTINCT region) AS n FROM sales")
    regions = cur.fetchone()["n"]

    cur.execute("SELECT COUNT(DISTINCT product) AS n FROM sales")
    products = cur.fetchone()["n"]

    conn.close()
    avg_order_value = round(total_revenue / total_orders) if total_orders else 0

    return {
        "total_revenue_rwf": total_revenue,
        "total_orders": total_orders,
        "avg_order_value_rwf": avg_order_value,
        "best_month": best["month"] if best else None,
        "best_month_revenue_rwf": best["revenue"] if best else 0,
        "active_regions": regions,
        "active_products": products,
        "monthly_ceiling_rwf": MONTHLY_CEILING_RWF,
    }


@app.get("/api/monthly-revenue")
def monthly_revenue():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT month, SUM(line_total_rwf) AS revenue_rwf
        FROM sales GROUP BY month ORDER BY month
    """)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


@app.get("/api/category-breakdown")
def category_breakdown():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT category, SUM(line_total_rwf) AS revenue_rwf
        FROM sales GROUP BY category ORDER BY revenue_rwf DESC
    """)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


@app.get("/api/region-breakdown")
def region_breakdown():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT region, SUM(line_total_rwf) AS revenue_rwf
        FROM sales GROUP BY region ORDER BY revenue_rwf DESC
    """)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


@app.get("/api/client-type-breakdown")
def client_type_breakdown():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT client_type, SUM(line_total_rwf) AS revenue_rwf
        FROM sales GROUP BY client_type ORDER BY revenue_rwf DESC
    """)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


@app.get("/api/top-products")
def top_products(limit: int = 8):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT product, SUM(line_total_rwf) AS revenue, SUM(quantity) AS units
        FROM sales GROUP BY product ORDER BY revenue DESC LIMIT ?
    """, (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


@app.get("/api/recent-transactions")
def recent_transactions(limit: int = 12):
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
