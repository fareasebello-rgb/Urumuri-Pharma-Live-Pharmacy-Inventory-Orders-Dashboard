# Urumuri Pharma — Sales Analytics Dashboard

A sales analytics dashboard for **Urumuri Pharma Ltd**, a fictional Rwandan
pharmaceutical distribution company. All figures are in **RWF**, and the
demo dataset is generated so that **no calendar month exceeds RWF
15,000,000** in total revenue (a business rule, enforced in the data
generator and explained inline on the revenue chart).

Built so you can hand the folder to someone else and they can swap out
the backend without touching the frontend — the frontend only talks to
a small, documented JSON API (and falls back to a saved snapshot if
that API isn't running).

```
rwanda_pharma_dashboard/
├── backend/
│   ├── app.py              FastAPI app — serves the JSON API
│   ├── insights.py         Turns numbers into plain-language takeaways
│   ├── data_generator.py   Generates sales, inventory & insights (stdlib only)
│   └── requirements.txt
├── data/
│   ├── sales.csv            Raw transaction-level data
│   ├── inventory.csv        Stock levels & reorder thresholds
│   └── sales.db             SQLite database (sales + inventory tables)
├── frontend/
│   ├── index.html
│   ├── style.css            Design system (dark teal / gold / clay)
│   ├── app.js               Fetches data, renders charts, tables, search
│   └── data.json            Precomputed snapshot — both time windows — offline fallback
└── README.md
```

## What's on the dashboard

- **New orders** — latest transactions, right under the KPIs
- **Insights** — auto-generated sentences (growth %, top category, ceiling
  usage, reorder count, average order value), computed in Python
- **Time range toggle** — "All time (12 months)" vs "Last 6 months";
  re-slices every chart, table, and insight, including reorder urgency
- **Monthly revenue** chart with the RWF 15,000,000 ceiling drawn as a
  reference line, plus an (ⓘ) tooltip explaining what that ceiling means
- **Category / region / client-type** breakdowns
- **Top products** ranked by revenue
- **Inventory & reorder** (bottom of the page) — stock on hand, reorder
  threshold, days-of-stock-remaining, and a status badge, sorted by
  urgency (not alphabetically), with a search box to filter by product
  or category

## Quick start

**1. Generate the dataset** (only needs Python's standard library):

```bash
cd backend
python3 data_generator.py
```

This writes `data/sales.csv`, `data/inventory.csv`, `data/sales.db`,
and `frontend/data.json`.

**2. Run the backend API:**

```bash
cd backend
pip install -r requirements.txt
uvicorn app:app --reload --port 8000
```

**3. Open the dashboard:**

Open `frontend/index.html` in a browser. It tries
`http://localhost:8000/api/...` first; if the API isn't running, it
automatically falls back to `frontend/data.json`, which has both time
windows precomputed — so the dashboard, search, and the 6-month toggle
all keep working even without the backend up.

## The API

All endpoints below accept an optional `?months=6` to filter to the
most recent N months; omit it for all-time.

| Endpoint                          | Returns                                   |
|------------------------------------|--------------------------------------------|
| `GET /api/kpis`                   | Total revenue, orders, avg order value, best month, reorder count |
| `GET /api/monthly-revenue`        | `[{month, revenue_rwf}]`                  |
| `GET /api/category-breakdown`     | `[{category, revenue_rwf}]`               |
| `GET /api/region-breakdown`       | `[{region, revenue_rwf}]`                 |
| `GET /api/client-type-breakdown`  | `[{client_type, revenue_rwf}]`            |
| `GET /api/top-products?limit=8`   | `[{product, revenue, units}]`             |
| `GET /api/new-orders?limit=12`    | Latest transactions, newest first         |
| `GET /api/inventory?status=all\|reorder` | Stock levels + urgency, sorted by days-of-stock-remaining |
| `GET /api/insights`               | `[{type, text}]` — plain-language takeaways |

Keep these shapes the same and the frontend doesn't need to change at all.

## Notes for whoever upgrades the backend

- **Swap the database.** `app.py` reads SQLite directly with `sqlite3`.
  Point it at Postgres/MySQL (e.g. with SQLAlchemy) and keep the same
  endpoint shapes — nothing else needs to change.
- **Real data instead of synthetic.** Replace `data_generator.py`'s
  output with a real import job writing into the same two tables:
  `sales(transaction_id, date, month, product, category, unit_price_rwf,
  quantity, line_total_rwf, region, client_name, client_type)` and
  `inventory(product, category, unit_price_rwf, stock_on_hand,
  reorder_threshold, reorder_quantity, last_restocked)`.
- **Insights logic** lives in `backend/insights.py`, separate from the
  API routing in `app.py`, specifically so it's easy to find and extend
  with new rules (seasonality, anomaly flags, per-region alerts, etc.).
- **Auth.** There's none yet — add an auth dependency in FastAPI before
  this touches real business data.
- **Different language/framework.** The contract is just JSON over
  HTTP with CORS enabled, so the backend can be rewritten in anything
  as long as it serves the same routes and shapes.
- **The RWF 15,000,000 monthly ceiling** is a business rule, not a UI
  constraint — enforce it wherever new data is written, not just in
  the generator.

## Design

- Palette: deep clinical teal background, warm gold accent for data
  highlights, sage and clay as supporting colors.
- Type: Fraunces (display) for headings and big numbers, Inter for
  body text, IBM Plex Mono for all data/figures.
- Signature element: an animated EKG-style pulse line in the header.
