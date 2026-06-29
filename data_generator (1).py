"""
data_generator.py
------------------
Generates a year of realistic, synthetic data for a fictional Rwandan
pharmaceutical distribution company, "Urumuri Pharma Ltd":

  1. SALES   — transaction-level records (capped under RWF 15,000,000
               of revenue per calendar month — a business rule).
  2. INVENTORY — current stock-on-hand per product, with a reorder
               threshold, so the dashboard can flag what needs restocking.
  3. INSIGHTS — plain-language, auto-generated takeaways computed FROM
               the sales + inventory data (this is the "data analysis"
               layer — turning numbers into sentences a manager can act on).

Everything is computed twice: once for the full 12-month window, and
once for "last 6 months" — so the dashboard's time-range toggle has
something real to switch between, even offline.

Outputs:
  - data/sales.csv, data/sales.db        (raw transactions)
  - data/inventory.csv                    (raw inventory)
  - frontend/data.json                    (precomputed snapshot — both
                                            windows — used as the
                                            offline fallback)

Run with:  python3 data_generator.py
Only needs the Python standard library.
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
# Reference data
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
DATASET_END = date(2025, 12, 31)


def days_in_month(d: date):
    if d.month == 12:
        nxt = date(d.year + 1, 1, 1)
    else:
        nxt = date(d.year, d.month + 1, 1)
    return (nxt - d).days


def months_back(end_date: date, months: int) -> date:
    """First day of the month that is `months` months before end_date's month."""
    total = end_date.year * 12 + (end_date.month - 1) - months
    y, m = divmod(total, 12)
    return date(y, m + 1, 1)


# ---------------------------------------------------------------------------
# 1. SALES — transaction generation, capped under the monthly ceiling
# ---------------------------------------------------------------------------

def generate_transactions():
    transactions = []
    txn_id = 1

    for month_start in MONTHS_2025:
        n_days = days_in_month(month_start)
        month_index = month_start.month
        growth_factor = 0.78 + (month_index / 12) * 0.22
        month_target = MONTHLY_CEILING_RWF * growth_factor * random.uniform(0.85, 0.93)

        running_total = 0
        day_cursor = month_start
        daily_target = month_target / n_days

        for _ in range(n_days):
            n_txns_today = random.randint(6, 14)
            remaining_budget = daily_target * random.uniform(0.85, 1.15)
            per_txn_budget = remaining_budget / n_txns_today

            for _ in range(n_txns_today):
                product_name, category, unit_price = random.choice(PRODUCTS)
                target_qty = max(1, round(per_txn_budget / unit_price))
                qty = max(1, target_qty + random.randint(-2, 3))
                line_total = qty * unit_price

                if running_total + line_total > MONTHLY_CEILING_RWF - 50_000:
                    continue

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


# ---------------------------------------------------------------------------
# 2. INVENTORY — current stock, derived from how fast each product sells
# ---------------------------------------------------------------------------

def generate_inventory(transactions):
    """Stock-on-hand per product, with a reorder threshold based on how
    fast that product actually sells (2 weeks of average daily sales)."""
    units_sold = {name: 0 for name, _, _ in PRODUCTS}
    for t in transactions:
        units_sold[t["product"]] += t["quantity"]

    span_days = (DATASET_END - MONTHS_2025[0]).days + 1
    inventory = []

    for name, category, unit_price in PRODUCTS:
        avg_daily = units_sold[name] / span_days
        reorder_threshold = max(10, round(avg_daily * 14))   # 2 weeks of cover
        reorder_quantity = max(20, round(avg_daily * 30))    # restock to ~1 month

        # ~1 in 3 products is deliberately understocked, so the
        # "reorder" feature has real, varied examples to show.
        if random.random() < 0.33:
            stock = random.randint(0, max(1, reorder_threshold - 1))
        else:
            stock = random.randint(reorder_threshold, reorder_threshold * 4 + 60)

        last_restocked = DATASET_END - timedelta(days=random.randint(2, 55))

        inventory.append({
            "product": name,
            "category": category,
            "unit_price_rwf": unit_price,
            "stock_on_hand": stock,
            "reorder_threshold": reorder_threshold,
            "reorder_quantity": reorder_quantity,
            "last_restocked": last_restocked.isoformat(),
        })

    return inventory


def attach_velocity(inventory, transactions, cutoff: date | None):
    """Compute avg daily units sold (within the given window) per product,
    then derive days-of-stock-remaining and a needs_reorder flag. This is
    recomputed per time-window, so the 6-month vs all-time toggle changes
    the urgency estimate — sales velocity, not just current stock, drives it."""
    units = {row["product"]: 0 for row in inventory}
    window_txns = [t for t in transactions if not cutoff or date.fromisoformat(t["date"]) >= cutoff]
    if not window_txns:
        window_txns = transactions
    dates = [date.fromisoformat(t["date"]) for t in window_txns]
    span = max(1, (max(dates) - min(dates)).days + 1)

    for t in window_txns:
        units[t["product"]] += t["quantity"]

    out = []
    for row in inventory:
        avg_daily = units[row["product"]] / span
        days_remaining = round(row["stock_on_hand"] / avg_daily, 1) if avg_daily > 0 else None
        out.append({
            **row,
            "avg_daily_units_sold": round(avg_daily, 2),
            "days_of_stock_remaining": days_remaining,
            "needs_reorder": row["stock_on_hand"] <= row["reorder_threshold"],
        })

    # Urgency order, NOT alphabetical: needs-reorder first, then soonest to run out.
    out.sort(key=lambda r: (
        0 if r["needs_reorder"] else 1,
        r["days_of_stock_remaining"] if r["days_of_stock_remaining"] is not None else 9_999,
    ))
    return out


# ---------------------------------------------------------------------------
# 3. INSIGHTS — turning the numbers into plain-language takeaways
# ---------------------------------------------------------------------------

def compute_insights(transactions, inventory_with_velocity, cutoff: date | None):
    window_txns = [t for t in transactions if not cutoff or date.fromisoformat(t["date"]) >= cutoff]
    if not window_txns:
        window_txns = transactions

    monthly = {}
    category_totals = {}
    region_totals = {}
    for t in window_txns:
        monthly.setdefault(t["month"], 0)
        monthly[t["month"]] += t["line_total_rwf"]
        category_totals.setdefault(t["category"], 0)
        category_totals[t["category"]] += t["line_total_rwf"]
        region_totals.setdefault(t["region"], 0)
        region_totals[t["region"]] += t["line_total_rwf"]

    months_sorted = sorted(monthly)
    total_revenue = sum(monthly.values())
    insights = []

    # 1. Month-over-month growth
    if len(months_sorted) >= 2:
        latest, prev = months_sorted[-1], months_sorted[-2]
        growth = (monthly[latest] - monthly[prev]) / monthly[prev] * 100 if monthly[prev] else 0
        direction = "up" if growth >= 0 else "down"
        insights.append({
            "type": "positive" if growth >= 0 else "warning",
            "text": f"Revenue is {direction} {abs(round(growth))}% from {prev} to {latest}.",
        })

    # 2. Top category
    if category_totals:
        top_cat = max(category_totals, key=category_totals.get)
        share = round(category_totals[top_cat] / total_revenue * 100) if total_revenue else 0
        insights.append({
            "type": "neutral",
            "text": f"{top_cat} is the leading category, driving {share}% of revenue in this period.",
        })

    # 3. Top region
    if region_totals:
        top_region = max(region_totals, key=region_totals.get)
        share = round(region_totals[top_region] / total_revenue * 100) if total_revenue else 0
        insights.append({
            "type": "neutral",
            "text": f"{top_region} leads regional sales, contributing {share}% of revenue.",
        })

    # 4. Ceiling utilisation in the latest month
    if months_sorted:
        latest = months_sorted[-1]
        pct = round(monthly[latest] / MONTHLY_CEILING_RWF * 100)
        insights.append({
            "type": "warning" if pct >= 90 else "neutral",
            "text": f"{latest} used {pct}% of the RWF 15,000,000 monthly ceiling.",
        })

    # 5. Reorder alerts
    low_stock = [r for r in inventory_with_velocity if r["needs_reorder"]]
    if low_stock:
        insights.append({
            "type": "warning",
            "text": f"{len(low_stock)} product(s) are at or below their reorder threshold and need restocking.",
        })
    else:
        insights.append({
            "type": "positive",
            "text": "All products are currently above their reorder threshold.",
        })

    # 6. Average order value
    if window_txns:
        avg_order = round(total_revenue / len(window_txns))
        insights.append({
            "type": "neutral",
            "text": f"Average order value across this period is RWF {avg_order:,} over {len(window_txns):,} orders.",
        })

    return insights


# ---------------------------------------------------------------------------
# Aggregation helpers (shared by both time windows)
# ---------------------------------------------------------------------------

def aggregate_window(transactions, inventory, cutoff: date | None, label: str):
    window_txns = [t for t in transactions if not cutoff or date.fromisoformat(t["date"]) >= cutoff]
    if not window_txns:
        window_txns = transactions

    monthly, category_totals, region_totals, client_totals, product_totals = {}, {}, {}, {}, {}
    for t in window_txns:
        monthly.setdefault(t["month"], 0)
        monthly[t["month"]] += t["line_total_rwf"]
        category_totals.setdefault(t["category"], 0)
        category_totals[t["category"]] += t["line_total_rwf"]
        region_totals.setdefault(t["region"], 0)
        region_totals[t["region"]] += t["line_total_rwf"]
        client_totals.setdefault(t["client_type"], 0)
        client_totals[t["client_type"]] += t["line_total_rwf"]
        product_totals.setdefault(t["product"], {"revenue": 0, "units": 0})
        product_totals[t["product"]]["revenue"] += t["line_total_rwf"]
        product_totals[t["product"]]["units"] += t["quantity"]

    total_revenue = sum(monthly.values())
    total_orders = len(window_txns)
    months_sorted = sorted(monthly)
    best_month = max(monthly, key=monthly.get) if monthly else None

    inv_with_velocity = attach_velocity(inventory, transactions, cutoff)

    return {
        "label": label,
        "kpis": {
            "total_revenue_rwf": total_revenue,
            "total_orders": total_orders,
            "avg_order_value_rwf": round(total_revenue / total_orders) if total_orders else 0,
            "best_month": best_month,
            "best_month_revenue_rwf": monthly.get(best_month, 0),
            "active_regions": len(region_totals),
            "active_products": len(product_totals),
            "reorder_count": sum(1 for r in inv_with_velocity if r["needs_reorder"]),
            "monthly_ceiling_rwf": MONTHLY_CEILING_RWF,
        },
        "monthly_revenue": [{"month": m, "revenue_rwf": monthly[m]} for m in months_sorted],
        "category_breakdown": sorted(
            ({"category": k, "revenue_rwf": v} for k, v in category_totals.items()),
            key=lambda x: x["revenue_rwf"], reverse=True,
        ),
        "region_breakdown": sorted(
            ({"region": k, "revenue_rwf": v} for k, v in region_totals.items()),
            key=lambda x: x["revenue_rwf"], reverse=True,
        ),
        "client_type_breakdown": sorted(
            ({"client_type": k, "revenue_rwf": v} for k, v in client_totals.items()),
            key=lambda x: x["revenue_rwf"], reverse=True,
        ),
        "top_products": sorted(
            ({"product": k, **v} for k, v in product_totals.items()),
            key=lambda x: x["revenue"], reverse=True,
        )[:8],
        "insights": compute_insights(transactions, inv_with_velocity, cutoff),
        "inventory": inv_with_velocity,
    }


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------

def write_csv(rows, path: Path):
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_sqlite(transactions, inventory, path: Path):
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE sales (
            transaction_id TEXT PRIMARY KEY, date TEXT, month TEXT,
            product TEXT, category TEXT, unit_price_rwf INTEGER,
            quantity INTEGER, line_total_rwf INTEGER, region TEXT,
            client_name TEXT, client_type TEXT
        )
    """)
    cur.executemany(
        """INSERT INTO sales VALUES
        (:transaction_id, :date, :month, :product, :category,
         :unit_price_rwf, :quantity, :line_total_rwf, :region,
         :client_name, :client_type)""",
        transactions,
    )
    cur.execute("""
        CREATE TABLE inventory (
            product TEXT PRIMARY KEY, category TEXT, unit_price_rwf INTEGER,
            stock_on_hand INTEGER, reorder_threshold INTEGER,
            reorder_quantity INTEGER, last_restocked TEXT
        )
    """)
    cur.executemany(
        """INSERT INTO inventory VALUES
        (:product, :category, :unit_price_rwf, :stock_on_hand,
         :reorder_threshold, :reorder_quantity, :last_restocked)""",
        inventory,
    )
    conn.commit()
    conn.close()


def main():
    transactions = generate_transactions()
    inventory = generate_inventory(transactions)

    write_csv(transactions, DATA_DIR / "sales.csv")
    write_csv(inventory, DATA_DIR / "inventory.csv")
    write_sqlite(transactions, inventory, DATA_DIR / "sales.db")

    recent_orders = sorted(transactions, key=lambda t: t["date"], reverse=True)[:12]

    snapshot = {
        "generated_for": "Urumuri Pharma Ltd",
        "currency": "RWF",
        "monthly_ceiling_rwf": MONTHLY_CEILING_RWF,
        "new_orders": recent_orders,
        "windows": {
            "12": aggregate_window(transactions, inventory, None, "All time (12 months)"),
            "6": aggregate_window(transactions, inventory, months_back(DATASET_END, 6), "Last 6 months"),
        },
    }

    with open(FRONTEND_DIR / "data.json", "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2)

    monthly_totals = {row["month"]: row["revenue_rwf"] for row in snapshot["windows"]["12"]["monthly_revenue"]}
    breached = {m: v for m, v in monthly_totals.items() if v > MONTHLY_CEILING_RWF}

    print(f"Generated {len(transactions)} transactions, {len(inventory)} inventory rows.")
    print(f"Wrote: {DATA_DIR/'sales.csv'}, {DATA_DIR/'inventory.csv'}, {DATA_DIR/'sales.db'}")
    print(f"Wrote: {FRONTEND_DIR/'data.json'}")
    if breached:
        print(f"WARNING: months over ceiling: {breached}")
    else:
        print(f"OK: every month stayed under RWF {MONTHLY_CEILING_RWF:,}.")
    reorder_now = sum(1 for r in snapshot["windows"]["12"]["inventory"] if r["needs_reorder"])
    print(f"{reorder_now} product(s) currently need reordering.")


if __name__ == "__main__":
    main()
