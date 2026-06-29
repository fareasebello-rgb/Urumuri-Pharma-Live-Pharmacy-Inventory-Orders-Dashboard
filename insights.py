from datetime import date

MONTHLY_CEILING_RWF = 15_000_000


def compute_insights(monthly: dict, category_totals: dict, region_totals: dict,
                      total_revenue: int, total_orders: int,
                      inventory_with_velocity: list) -> list:
    months_sorted = sorted(monthly)
    insights = []

    if len(months_sorted) >= 2:
        latest, prev = months_sorted[-1], months_sorted[-2]
        growth = (monthly[latest] - monthly[prev]) / monthly[prev] * 100 if monthly[prev] else 0
        direction = "up" if growth >= 0 else "down"
        insights.append({
            "type": "positive" if growth >= 0 else "warning",
            "text": f"Revenue is {direction} {abs(round(growth))}% from {prev} to {latest}.",
        })

    if category_totals:
        top_cat = max(category_totals, key=category_totals.get)
        share = round(category_totals[top_cat] / total_revenue * 100) if total_revenue else 0
        insights.append({
            "type": "neutral",
            "text": f"{top_cat} is the leading category, driving {share}% of revenue in this period.",
        })

    if region_totals:
        top_region = max(region_totals, key=region_totals.get)
        share = round(region_totals[top_region] / total_revenue * 100) if total_revenue else 0
        insights.append({
            "type": "neutral",
            "text": f"{top_region} leads regional sales, contributing {share}% of revenue.",
        })

    if months_sorted:
        latest = months_sorted[-1]
        pct = round(monthly[latest] / MONTHLY_CEILING_RWF * 100)
        insights.append({
            "type": "warning" if pct >= 90 else "neutral",
            "text": f"{latest} used {pct}% of the RWF 15,000,000 monthly ceiling.",
        })

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

    if total_orders:
        avg_order = round(total_revenue / total_orders)
        insights.append({
            "type": "neutral",
            "text": f"Average order value across this period is RWF {avg_order:,} over {total_orders:,} orders.",
        })

    return insights


def get_cutoff_date(max_date_str: str | None, months: int | None):
    if not months or not max_date_str:
        return None
    y, m, _ = map(int, max_date_str.split("-"))
    total = y * 12 + (m - 1) - months
    ny, nm = divmod(total, 12)
    return date(ny, nm + 1, 1).isoformat()
