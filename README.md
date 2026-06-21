# Urumuri Pharma — Live Pharmacy Inventory & Orders Dashboard

This repository is now a live pharmacy operations dashboard for
**Urumuri Pharma Ltd**. It combines realistic sales history with a live
inventory and order capture system, while preserving the business rule
that no calendar month may exceed **RWF 15,000,000**.

## What the system does

- Maintains live inventory for a pharmacy product catalogue.
- Captures orders through a live form and updates stock immediately.
- Records each new order as a sales transaction in the backend.
- Enforces the monthly ceiling in the backend before accepting orders.
- Displays a clean, simple dashboard for pharmacists and pharmacy staff.

## Project structure

```
Dashboard/
├── app.py             FastAPI backend — inventory, orders, sales history
├── data_generator.py  Generates synthetic sales history data
├── data/              Generated dataset storage
│   ├── sales.csv
│   └── sales.db
├── index.html         Frontend dashboard
├── style.css          Frontend styling
├── app.js             Frontend logic for live inventory and orders
├── requirements.txt   Python backend dependencies
└── README.md          This documentation
```

## Quick start

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Generate the historical dataset once:

```bash
python data_generator.py
```

This creates `data/sales.csv` and `data/sales.db`.

3. Run the backend API:

```bash
python -m uvicorn app:app --reload --port 8000
```

4. Open `index.html` in your browser.

> Note: the frontend now depends on the live API. If the backend is not
> running, order placement is disabled.

## How the system works

### Backend (`app.py`)

The backend is a FastAPI app that reads the existing sales history from
`data/sales.db` and manages live pharmacy operations.

It provides:

- a live KPI summary
- current inventory status
- a list of valid regions and client types
- recent live orders
- order submission with validation and inventory updates

On startup, the backend also creates an `inventory` table if required and
seeds it with realistic stock levels for each product.

### Order workflow

When a new order is submitted, the backend:

1. validates request data
2. checks product stock
3. computes the new order total
4. checks the current month's total revenue
5. rejects the order if it would exceed the RWF 15,000,000 ceiling
6. otherwise writes the sale and reduces inventory

### Frontend (`index.html` + `app.js`)

The frontend is designed to be minimal and operational.
It shows:

- live connection status
- a small set of KPIs
- current inventory with reorder levels
- a simple order entry form
- recent orders list

It no longer depends on a static snapshot fallback; the live API must be
available for the order workflow.

## API contract

The backend exposes these endpoints:

| Endpoint | Purpose |
|---|---|
| `GET /api/kpis` | Live business KPIs and inventory metrics |
| `GET /api/inventory` | Current inventory rows with stock levels |
| `GET /api/products` | Product catalog / inventory list |
| `GET /api/metadata` | Valid regions and client types |
| `GET /api/orders` | Recent live orders |
| `POST /api/order` | Submit a new order and update inventory |

### `POST /api/order`

Accepted JSON payload:

- `product`
- `quantity`
- `client_name`
- `region`
- `client_type`

The backend returns a confirmed order response, or an error if stock is
insufficient or the monthly ceiling would be breached.

## Data generator (`data_generator.py`)

This script produces a realistic historical dataset for testing the
pharmacy dashboard.

It generates:

- `data/sales.csv` — raw transaction rows
- `data/sales.db` — SQLite sales database consumed by the backend

The generator respects the monthly revenue cap and creates a plausible
product mix for pharmacy operations.

## Business rule

The monthly ceiling of **RWF 15,000,000** is enforced by the backend.
This is a real operational constraint, not just a chart annotation.
Orders are rejected if they would push the current month's total over
this limit.

## Notes for future improvements

- **Swap the database.** The backend currently uses SQLite, but the
  same API contract can be kept with Postgres, MySQL, or another DB.
- **Add authentication.** There is no auth currently. Add API keys, JWT,
  or another auth layer for production.
- **Replace synthetic history with real data.** The generator can be
  replaced by actual POS/ERP imports while keeping the same sales schema.
- **Keep the frontend simple.** The current UI is intended for pharmacy
  staff who need a straightforward operational view.
