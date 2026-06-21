"""
data_generator.py
------------------
Generates a year of realistic, synthetic sales data for a fictional
Rwandan pharmaceutical distribution company, "Urumuri Pharma Ltd".

Design constraint (set by the business): total revenue recorded in
ANY single calendar month must stay under RWF 15,000,000. This is
enforced by scaling daily transaction volume/price so the monthly
sum never crosses the ceiling, then writing the same dataset out as:

  - data/sales.csv            (raw transaction-level data)
  - data/sales.db             (SQLite, used by the FastAPI backend)
  - frontend/data.json        (pre-aggregated snapshot, used as a
                                static fallback if the API isn't running)

Run it with:  python3 data_generator.py
Only needs the Python standard library â€” no pip install required.
"""

import csv
import json
import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

random.seed(42)  # reproducible demo data

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
FRONTEND_DIR = BASE_DIR / "frontend"
DATA_DIR.mkdir(exist_ok=True)

MONTHLY_CEILING_RWF = 15_000_000

# ---------------------------------------------------------------------------
# Reference data â€” product catalogue, regions, and client types
# ---------------------------------------------------------------------------

PRODUCTS = [
    # (name, category, unit_price_rwf)
    ("Amodiaquine + Artesunate 25mg", "Antimalarials", 1800),
    ("Coartem 20/120mg", "Antimalarials", 2200),
    ("Quinine Sulphate 300mg", "Antimalarials", 1500),
    ("Amoxicillin 500mg", "Antibiotics", 1200),
    ("Ciprofloxacin 500mg", "Antibiotics", 1600),
    ("Metronidazole 400mg", "Antibiotics", 900),
    ("Paracetamol 500mg", "Analgesics & Pain Relief", 500),
    ("Ibuprofen 400mg", "Analgesics & Pain Relief", 700),
    ("Diclofenac Gel 50g", "Analgesics & Pain Relief", 2500),
    ("Multivitamin Syrup 100ml", "Vitamins & Supplements", 3200),
    ("Ferrous Sulphate + Folic Acid", "Vitamins & Supplements", 1100),
    ("Vitamin C 1000mg", "Vitamins & Supplements", 1900),
    ("Amlodipine 5mg", "Antihypertensives", 1700),
    ("Losartan 50mg", "Antihypertensives", 2100),
    ("Metformin 500mg", "Diabetes Care", 1300),
    ("Insulin Glargine Pen", "Diabetes Care", 9500),
    ("Oral Rehydration Salts", "Maternal & Child Health", 600),
    ("Prenatal Vitamins", "Maternal & Child Health", 2800),
    ("Cough Syrup 100ml", "Cold & Flu", 1400),
    ("Antihistamine Tablets", "Cold & Flu", 800),
    ("Hydrocortisone Cream 15g", "Dermatology", 2300),
    ("Surgical Gloves (box of 100)", "Medical Supplies", 4500),
    ("Disposable Syringes (box of 50)", "Medical Supplies", 6200),
    ("Digital Thermometer", "Medical Supplies", 5800),
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

CLIENT_NAMES = [
    "Gasabo District Hospital", "Nyarugenge Health Center", "Kicukiro Retail Pharmacy",
    "Huye Community Clinic", "Musanze District Hospital", "Rubavu Lakeside Pharmacy",
    "Rwamagana Health Center", "Kigali Wholesale Medical Supplies", "Remera Family Pharmacy",
    "Butare Polyclinic", "Gisenyi Health Post", "Kayonza District Hospital",
]

MONTHS_2025 = [date(2025, m, 1) for m in range(1, 13)]


def days_in_month(d: date):
    if d.month == 12:
        nxt = date(d.year + 1, 1, 1)
    else:
        nxt = date(d.year, d.month + 1, 1)
    return (nxt - d).days


def generate_transactions():
    """Yield transaction dicts, scaling daily volume so each month
    stays safely under the RWF 15,000,000 ceiling."""
    transactions = []
    txn_id = 1

    for month_start in MONTHS_2025:
        n_days = days_in_month(month_start)
        # Gentle upward trend across the year (seasonality + growth),
        # but always kept well below the ceiling with headroom for randomness.
        month_index = month_start.month
        growth_factor = 0.78 + (month_index / 12) * 0.22  # ~0.78 -> 1.0
        month_target = MONTHLY_CEILING_RWF * growth_factor * random.uniform(0.85, 0.93)

        running_total = 0
        day_cursor = month_start
        daily_target = month_target / n_days

        for _ in range(n_days):
            # 6-14 transactions per day, sized so the day roughly hits daily_target
            n_txns_today = random.randint(6, 14)
            remaining_budget = daily_target * random.uniform(0.85, 1.15)
            per_txn_budget = remaining_budget / n_txns_today

            for _ in range(n_txns_today):
                product_name, category, unit_price = random.choice(PRODUCTS)
                # quantity chosen so line total roughly matches per_txn_budget
                target_qty = max(1, round(per_txn_budget / unit_price))
                qty = max(1, target_qty + random.randint(-2, 3))
                line_total = qty * unit_price

                if running_total + line_total > MONTHLY_CEILING_RWF - 50_000:
                    continue  # safety valve: never breach the ceiling

                running_total += line_total
                client_idx = random.randint(0, len(CLIENT_NAMES) - 1)

                transactions.append({
                    "transaction_id": f"TXN-{txn_id:05d}",
                    "date": day_cursor.isoformat(),
                    "month": day_cursor.strftime("%Y-%m"),
                    "product": product_name,
                    "category": category,
                    "unit_price_rwf": unit_price,
                    "quantity": qty,
                    "line_total_rwf": line_total,
                    "region": REGIONS[client_idx % len(REGIONS)],
                    "client_name": CLIENT_NAMES[client_idx],
                    "client_type": CLIENT_TYPES[client_idx % len(CLIENT_TYPES)],
                })
                txn_id += 1

            day_cursor += timedelta(days=1)

    return transactions


def write_csv(transactions, path: Path):
    fieldnames = list(transactions[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(transactions)


def write_sqlite(transactions, path: Path):
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE sales (
            transaction_id TEXT PRIMARY KEY,
            date TEXT,
            month TEXT,
            product TEXT,
            category TEXT,
            unit_price_rwf INTEGER,
            quantity INTEGER,
            line_total_rwf INTEGER,
            region TEXT,
            client_name TEXT,
            client_type TEXT
        )
    """)
    cur.executemany(
        """INSERT INTO sales VALUES
        (:transaction_id, :date, :month, :product, :category,
         :unit_price_rwf, :quantity, :line_total_rwf, :region,
         :client_name, :client_type)""",
        transactions,
    )
    conn.commit()
    conn.close()


def build_snapshot(transactions):
    """Pre-aggregate everything the dashboard needs, for the static
    JSON fallback (so the frontend works even without the API running)."""
    monthly = {}
    category_totals = {}
    region_totals = {}
    product_totals = {}
    client_type_totals = {}

    for t in transactions:
        monthly.setdefault(t["month"], 0)
        monthly[t["month"]] += t["line_total_rwf"]

        category_totals.setdefault(t["category"], 0)
        category_totals[t["category"]] += t["line_total_rwf"]

        region_totals.setdefault(t["region"], 0)
        region_totals[t["region"]] += t["line_total_rwf"]

        product_totals.setdefault(t["product"], {"revenue": 0, "units": 0})
        product_totals[t["product"]]["revenue"] += t["line_total_rwf"]
        product_totals[t["product"]]["units"] += t["quantity"]

        client_type_totals.setdefault(t["client_type"], 0)
        client_type_totals[t["client_type"]] += t["line_total_rwf"]

    total_revenue = sum(monthly.values())
    total_orders = len(transactions)
    avg_order_value = round(total_revenue / total_orders) if total_orders else 0
    best_month = max(monthly, key=monthly.get)

    top_products = sorted(
        ({"product": k, **v} for k, v in product_totals.items()),
        key=lambda x: x["revenue"],
        reverse=True,
    )[:8]

    recent = sorted(transactions, key=lambda t: t["date"], reverse=True)[:12]

    snapshot = {
        "generated_for": "Urumuri Pharma Ltd",
        "currency": "RWF",
        "monthly_ceiling_rwf": MONTHLY_CEILING_RWF,
        "kpis": {
            "total_revenue_rwf": total_revenue,
            "total_orders": total_orders,
            "avg_order_value_rwf": avg_order_value,
            "best_month": best_month,
            "best_month_revenue_rwf": monthly[best_month],
            "active_regions": len(region_totals),
            "active_products": len(product_totals),
        },
        "monthly_revenue": [
            {"month": m, "revenue_rwf": monthly[m]} for m in sorted(monthly)
        ],
        "category_breakdown": [
            {"category": k, "revenue_rwf": v} for k, v in
            sorted(category_totals.items(), key=lambda x: x[1], reverse=True)
        ],
        "region_breakdown": [
            {"region": k, "revenue_rwf": v} for k, v in
            sorted(region_totals.items(), key=lambda x: x[1], reverse=True)
        ],
        "client_type_breakdown": [
            {"client_type": k, "revenue_rwf": v} for k, v in
            sorted(client_type_totals.items(), key=lambda x: x[1], reverse=True)
        ],
        "top_products": top_products,
        "recent_transactions": recent,
    }
    return snapshot


def main():
    transactions = generate_transactions()

    csv_path = DATA_DIR / "sales.csv"
    db_path = DATA_DIR / "sales.db"
    json_path = FRONTEND_DIR / "data.json"

    write_csv(transactions, csv_path)
    write_sqlite(transactions, db_path)

    snapshot = build_snapshot(transactions)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2)

    # Sanity check the ceiling constraint
    monthly_totals = {row["month"]: row["revenue_rwf"] for row in snapshot["monthly_revenue"]}
    breached = {m: v for m, v in monthly_totals.items() if v > MONTHLY_CEILING_RWF}

    print(f"Generated {len(transactions)} transactions across {len(monthly_totals)} months.")
    print(f"Wrote: {csv_path}")
    print(f"Wrote: {db_path}")
    print(f"Wrote: {json_path}")
    if breached:
        print(f"WARNING: months over ceiling: {breached}")
    else:
        print(f"OK: every month stayed under RWF {MONTHLY_CEILING_RWF:,}.")
        print(f"Highest month: {snapshot['kpis']['best_month']} "
              f"(RWF {snapshot['kpis']['best_month_revenue_rwf']:,})")


if __name__ == "__main__":
    main()

