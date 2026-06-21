"""
app.py
------
Live backend for Urumuri Pharma Ltd inventory and order management.

This FastAPI service uses the existing sales history and adds inventory,
real order capture, and ceiling enforcement so the pharmacy can record
orders and keep stock accurate in a live environment.
"""

import random
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "sales.db"
MONTHLY_CEILING_RWF = 15_000_000

PRODUCT_CATALOG = [
    {"product": "Amodiaquine + Artesunate 25mg", "category": "Antimalarials", "unit_price_rwf": 1800, "reorder_level": 20},
    {"product": "Coartem 20/120mg", "category": "Antimalarials", "unit_price_rwf": 2200, "reorder_level": 18},
    {"product": "Quinine Sulphate 300mg", "category": "Antimalarials", "unit_price_rwf": 1500, "reorder_level": 20},
    {"product": "Amoxicillin 500mg", "category": "Antibiotics", "unit_price_rwf": 1200, "reorder_level": 25},
    {"product": "Ciprofloxacin 500mg", "category": "Antibiotics", "unit_price_rwf": 1600, "reorder_level": 20},
    {"product": "Metronidazole 400mg", "category": "Antibiotics", "unit_price_rwf": 900, "reorder_level": 22},
    {"product": "Paracetamol 500mg", "category": "Analgesics & Pain Relief", "unit_price_rwf": 500, "reorder_level": 40},
    {"product": "Ibuprofen 400mg", "category": "Analgesics & Pain Relief", "unit_price_rwf": 700, "reorder_level": 30},
    {"product": "Diclofenac Gel 50g", "category": "Analgesics & Pain Relief", "unit_price_rwf": 2500, "reorder_level": 18},
    {"product": "Multivitamin Syrup 100ml", "category": "Vitamins & Supplements", "unit_price_rwf": 3200, "reorder_level": 16},
    {"product": "Ferrous Sulphate + Folic Acid", "category": "Vitamins & Supplements", "unit_price_rwf": 1100, "reorder_level": 22},
    {"product": "Vitamin C 1000mg", "category": "Vitamins & Supplements", "unit_price_rwf": 1900, "reorder_level": 20},
    {"product": "Amlodipine 5mg", "category": "Antihypertensives", "unit_price_rwf": 1700, "reorder_level": 18},
    {"product": "Losartan 50mg", "category": "Antihypertensives", "unit_price_rwf": 2100, "reorder_level": 18},
    {"product": "Metformin 500mg", "category": "Diabetes Care", "unit_price_rwf": 1300, "reorder_level": 24},
    {"product": "Insulin Glargine Pen", "category": "Diabetes Care", "unit_price_rwf": 9500, "reorder_level": 12},
    {"product": "Oral Rehydration Salts", "category": "Maternal & Child Health", "unit_price_rwf": 600, "reorder_level": 30},
    {"product": "Prenatal Vitamins", "category": "Maternal & Child Health", "unit_price_rwf": 2800, "reorder_level": 18},
    {"product": "Cough Syrup 100ml", "category": "Cold & Flu", "unit_price_rwf": 1400, "reorder_level": 24},
    {"product": "Antihistamine Tablets", "category": "Cold & Flu", "unit_price_rwf": 800, "reorder_level": 28},
    {"product": "Hydrocortisone Cream 15g", "category": "Dermatology", "unit_price_rwf": 2300, "reorder_level": 18},
    {"product": "Surgical Gloves (box of 100)", "category": "Medical Supplies", "unit_price_rwf": 4500, "reorder_level": 14},
    {"product": "Disposable Syringes (box of 50)", "category": "Medical Supplies", "unit_price_rwf": 6200, "reorder_level": 14},
    {"product": "Digital Thermometer", "category": "Medical Supplies", "unit_price_rwf": 5800, "reorder_level": 10},
]

REGIONS = [
    "Kigali - Gasabo",
    "Kigali - Nyarugenge",
    "Kigali - Kicukiro",
    "Southern Province - Huye",
    "Northern Province - Musanze",
    "Western Province - Rubavu",
    "Eastern Province - Rwamagana",
]

CLIENT_TYPES = [
    "District Hospital",
    "Health Center",
    "Retail Pharmacy",
    "Private Clinic",
    "Wholesale Distributor",
]

app = FastAPI(
    title="Urumuri Pharma Inventory & Orders API",
    description="Live pharmacy inventory and order capture for Urumuri Pharma Ltd.",
    version="1.0.0",
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


def initialize_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS inventory (
            product TEXT PRIMARY KEY,
            category TEXT,
            unit_price_rwf INTEGER,
            stock INTEGER,
            reorder_level INTEGER
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS orders (
            order_id TEXT PRIMARY KEY,
            transaction_id TEXT,
            created_at TEXT,
            date TEXT,
            month TEXT,
            product TEXT,
            category TEXT,
            quantity INTEGER,
            unit_price_rwf INTEGER,
            line_total_rwf INTEGER,
            region TEXT,
            client_name TEXT,
            client_type TEXT,
            status TEXT
        )
        """
    )
    cur.execute("SELECT COUNT(*) AS n FROM inventory")
    if cur.fetchone()["n"] == 0:
        random.seed(42)
        prepared = [
            (
                item["product"],
                item["category"],
                item["unit_price_rwf"],
                random.randint(120, 260),
                item["reorder_level"],
            )
            for item in PRODUCT_CATALOG
        ]
        cur.executemany(
            "INSERT INTO inventory (product, category, unit_price_rwf, stock, reorder_level) VALUES (?, ?, ?, ?, ?)",
            prepared,
        )
    conn.commit()
    conn.close()


@app.on_event("startup")
def startup():
    initialize_db()


def format_row(row):
    return {key: row[key] for key in row.keys()}


def current_month():
    return date.today().strftime("%Y-%m")


def next_transaction_id(cur):
    cur.execute("SELECT transaction_id FROM sales ORDER BY transaction_id DESC LIMIT 1")
    row = cur.fetchone()
    if not row:
        return "TXN-00001"
    try:
        current = int(row["transaction_id"].split("-")[-1])
        return f"TXN-{current + 1:05d}"
    except ValueError:
        return "TXN-00001"


def next_order_id():
    now = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"ORD-{now}-{random.randint(100, 999)}"


@app.get("/")
def root():
    return {
        "service": "Urumuri Pharma Inventory & Orders API",
        "currency": "RWF",
        "endpoints": [
            "/api/kpis",
            "/api/inventory",
            "/api/orders",
            "/api/products",
            "/api/metadata",
            "/api/order",
        ],
    }


@app.get("/api/kpis")
def kpis():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS n, SUM(line_total_rwf) AS total FROM sales")
    sales_row = cur.fetchone()
    total_orders = sales_row["n"]
    total_revenue = sales_row["total"] or 0

    cur.execute(
        "SELECT month, SUM(line_total_rwf) AS revenue FROM sales GROUP BY month ORDER BY revenue DESC LIMIT 1"
    )
    best = cur.fetchone()

    cur.execute(
        "SELECT SUM(stock * unit_price_rwf) AS inventory_value, SUM(CASE WHEN stock <= reorder_level THEN 1 ELSE 0 END) AS low_stock FROM inventory"
    )
    inventory_row = cur.fetchone()
    inventory_value = inventory_row["inventory_value"] or 0
    low_stock_count = inventory_row["low_stock"] or 0

    conn.close()
    avg_order_value = round(total_revenue / total_orders) if total_orders else 0

    return {
        "total_revenue_rwf": total_revenue,
        "total_orders": total_orders,
        "avg_order_value_rwf": avg_order_value,
        "best_month": best["month"] if best else None,
        "best_month_revenue_rwf": best["revenue"] if best else 0,
        "inventory_value_rwf": inventory_value,
        "low_stock_skus": low_stock_count,
        "monthly_ceiling_rwf": MONTHLY_CEILING_RWF,
    }


@app.get("/api/inventory")
def inventory():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT product, category, unit_price_rwf, stock, reorder_level FROM inventory ORDER BY category, product"
    )
    rows = [format_row(row) for row in cur.fetchall()]
    conn.close()
    return rows


@app.get("/api/products")
def products():
    return inventory()


@app.get("/api/metadata")
def metadata():
    return {"regions": REGIONS, "client_types": CLIENT_TYPES}


@app.get("/api/orders")
def recent_orders(limit: int = 20):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT order_id, transaction_id, created_at, date, product, quantity, line_total_rwf, region, client_name, client_type, status FROM orders ORDER BY created_at DESC LIMIT ?",
        (limit,),
    )
    rows = [format_row(row) for row in cur.fetchall()]
    conn.close()
    return rows


class OrderPayload(BaseModel):
    product: str
    quantity: int
    client_name: str
    region: str
    client_type: str


@app.post("/api/order")
def create_order(payload: OrderPayload):
    if payload.quantity < 1:
        raise HTTPException(status_code=400, detail="Quantity must be at least 1.")

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT product, category, unit_price_rwf, stock, reorder_level FROM inventory WHERE product = ?",
        (payload.product,),
    )
    row = cur.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Product not found in inventory.")

    if payload.quantity > row["stock"]:
        conn.close()
        raise HTTPException(
            status_code=400,
            detail=f"Not enough stock for {payload.product}. Available: {row['stock']}.",
        )

    today = date.today()
    order_month = today.strftime("%Y-%m")
    line_total = payload.quantity * row["unit_price_rwf"]

    cur.execute(
        "SELECT SUM(line_total_rwf) AS total FROM sales WHERE month = ?",
        (order_month,),
    )
    month_total = cur.fetchone()["total"] or 0
    if month_total + line_total > MONTHLY_CEILING_RWF:
        conn.close()
        raise HTTPException(
            status_code=400,
            detail=(
                "This order would exceed the business ceiling of RWF "
                f"{MONTHLY_CEILING_RWF:,} for {order_month}. "
                f"Current month total is RWF {month_total:,}."
            ),
        )

    transaction_id = next_transaction_id(cur)
    order_id = next_order_id()
    created_at = datetime.now().isoformat()
    line_item = {
        "transaction_id": transaction_id,
        "date": today.isoformat(),
        "month": order_month,
        "product": row["product"],
        "category": row["category"],
        "unit_price_rwf": row["unit_price_rwf"],
        "quantity": payload.quantity,
        "line_total_rwf": line_total,
        "region": payload.region,
        "client_name": payload.client_name,
        "client_type": payload.client_type,
    }

    cur.execute(
        "UPDATE inventory SET stock = stock - ? WHERE product = ?",
        (payload.quantity, payload.product),
    )
    cur.execute(
        "INSERT INTO sales (transaction_id, date, month, product, category, unit_price_rwf, quantity, line_total_rwf, region, client_name, client_type) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            line_item["transaction_id"],
            line_item["date"],
            line_item["month"],
            line_item["product"],
            line_item["category"],
            line_item["unit_price_rwf"],
            line_item["quantity"],
            line_item["line_total_rwf"],
            line_item["region"],
            line_item["client_name"],
            line_item["client_type"],
        ),
    )
    cur.execute(
        "INSERT INTO orders (order_id, transaction_id, created_at, date, month, product, category, quantity, unit_price_rwf, line_total_rwf, region, client_name, client_type, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            order_id,
            transaction_id,
            created_at,
            line_item["date"],
            line_item["month"],
            line_item["product"],
            line_item["category"],
            line_item["quantity"],
            line_item["unit_price_rwf"],
            line_item["line_total_rwf"],
            line_item["region"],
            line_item["client_name"],
            line_item["client_type"],
            "confirmed",
        ),
    )
    conn.commit()
    conn.close()

    return {
        "order_id": order_id,
        "transaction_id": transaction_id,
        "created_at": created_at,
        "product": line_item["product"],
        "quantity": line_item["quantity"],
        "line_total_rwf": line_item["line_total_rwf"],
        "remaining_stock": row["stock"] - payload.quantity,
        "monthly_ceiling_rwf": MONTHLY_CEILING_RWF,
        "month": order_month,
    }

