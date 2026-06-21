/* ===========================================================
   app.js — Urumuri Pharma Analytics Dashboard
   Tries the FastAPI backend first; if it isn't running, falls
   back to the static data.json snapshot so this still works
   when you just double-click index.html.
   =========================================================== */

const API_BASE = "http://localhost:8000/api";

const PALETTE = {
  gold: "#D9A130",
  goldDim: "#B4862C",
  sage: "#7FB69E",
  sageDim: "#5C8C77",
  clay: "#E2725B",
  teal600: "#246B61",
  teal700: "#18524B",
  cream: "#F2EFE6",
  creamDim: "#C9C7BC",
};

const CATEGORY_COLORS = [
  PALETTE.gold, PALETTE.sage, PALETTE.clay, PALETTE.teal600,
  PALETTE.goldDim, PALETTE.sageDim, PALETTE.teal700, PALETTE.creamDim,
  "#8C6BB1", "#4F8A8B",
];

function fmtRWF(n, opts = {}) {
  const rounded = Math.round(n || 0);
  const str = rounded.toLocaleString("en-US");
  return opts.short ? `RWF ${str}` : `RWF ${str}`;
}

function fmtShort(n) {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`;
  return `${n}`;
}

function fmtDate(iso) {
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("en-GB", { day: "2-digit", month: "short" });
}

async function fetchJSON(url) {
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`${url} -> ${res.status}`);
  return res.json();
}

async function loadData() {
  // Try the live API first.
  try {
    const [kpis, monthly, category, region, clientType, top, recent] = await Promise.all([
      fetchJSON(`${API_BASE}/kpis`),
      fetchJSON(`${API_BASE}/monthly-revenue`),
      fetchJSON(`${API_BASE}/category-breakdown`),
      fetchJSON(`${API_BASE}/region-breakdown`),
      fetchJSON(`${API_BASE}/client-type-breakdown`),
      fetchJSON(`${API_BASE}/top-products?limit=8`),
      fetchJSON(`${API_BASE}/recent-transactions?limit=12`),
    ]);
    setConnectionLabel(true);
    return {
      kpis,
      monthly_revenue: monthly,
      category_breakdown: category,
      region_breakdown: region,
      client_type_breakdown: clientType,
      top_products: top.map(r => ({ product: r.product, revenue: r.revenue, units: r.units })),
      recent_transactions: recent.map(r => ({
        date: r.date, client_name: r.client_name, product: r.product,
        region: r.region, line_total_rwf: r.line_total_rwf,
      })),
    };
  } catch (err) {
    console.warn("API not reachable, falling back to data.json snapshot.", err);
    setConnectionLabel(false);
    const snapshot = await fetchJSON("data.json");
    return snapshot;
  }
}

function setConnectionLabel(live) {
  const label = document.getElementById("connection-label");
  const dot = document.querySelector(".dot--live");
  if (live) {
    label.textContent = "Live API connected";
  } else {
    label.textContent = "Offline mode — showing saved snapshot";
    dot.style.background = PALETTE.creamDim;
    dot.style.animation = "none";
  }
}

function renderKPIs(d) {
  const ceiling = d.kpis.monthly_ceiling_rwf || 15_000_000;
  const pctOfCeiling = Math.round((d.kpis.best_month_revenue_rwf / ceiling) * 100);

  const cards = [
    {
      label: "Total revenue (YTD)",
      value: `RWF ${fmtShort(d.kpis.total_revenue_rwf)}`,
      sub: fmtRWF(d.kpis.total_revenue_rwf),
    },
    {
      label: "Total orders",
      value: d.kpis.total_orders.toLocaleString("en-US"),
      sub: `Avg order ${fmtRWF(d.kpis.avg_order_value_rwf)}`,
    },
    {
      label: "Best month",
      value: d.kpis.best_month,
      sub: `${fmtRWF(d.kpis.best_month_revenue_rwf)} · ${pctOfCeiling}% of ceiling`,
      warn: pctOfCeiling >= 95,
    },
    {
      label: "Coverage",
      value: `${d.kpis.active_regions} regions`,
      sub: `${d.kpis.active_products} active SKUs`,
    },
  ];

  const row = document.getElementById("kpi-row");
  row.innerHTML = cards.map(c => `
    <div class="kpi">
      <p class="kpi__label">${c.label}</p>
      <p class="kpi__value">${c.value}</p>
      <p class="kpi__sub ${c.warn ? "kpi__sub--warn" : ""}">${c.sub}</p>
    </div>
  `).join("");
}

function renderMonthlyChart(d) {
  const ctx = document.getElementById("chart-monthly");
  const labels = d.monthly_revenue.map(r => r.month);
  const values = d.monthly_revenue.map(r => r.revenue_rwf);
  const ceiling = d.kpis.monthly_ceiling_rwf || 15_000_000;

  new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Revenue",
          data: values,
          borderColor: PALETTE.gold,
          backgroundColor: "rgba(217,161,48,0.18)",
          pointBackgroundColor: PALETTE.gold,
          pointBorderColor: PALETTE.teal900 || "#0E3B36",
          fill: true,
          tension: 0.35,
          borderWidth: 2.5,
          pointRadius: 3,
        },
        {
          label: "Monthly ceiling (RWF 15,000,000)",
          data: labels.map(() => ceiling),
          borderColor: PALETTE.clay,
          borderDash: [6, 6],
          borderWidth: 1.5,
          pointRadius: 0,
          fill: false,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "#0A2826",
          borderColor: "rgba(242,239,230,0.15)",
          borderWidth: 1,
          titleFont: { family: "IBM Plex Mono" },
          bodyFont: { family: "IBM Plex Mono" },
          callbacks: {
            label: (ctx) => `${ctx.dataset.label}: ${fmtRWF(ctx.parsed.y)}`,
          },
        },
      },
      scales: {
        x: {
          grid: { color: "rgba(242,239,230,0.06)" },
          ticks: { color: PALETTE.creamDim, font: { family: "IBM Plex Mono", size: 11 } },
        },
        y: {
          grid: { color: "rgba(242,239,230,0.06)" },
          ticks: {
            color: PALETTE.creamDim,
            font: { family: "IBM Plex Mono", size: 11 },
            callback: (v) => fmtShort(v),
          },
          suggestedMax: ceiling * 1.1,
        },
      },
    },
  });
}

function renderCategoryChart(d) {
  const ctx = document.getElementById("chart-category");
  const labels = d.category_breakdown.map(r => r.category);
  const values = d.category_breakdown.map(r => r.revenue_rwf);
  const colors = labels.map((_, i) => CATEGORY_COLORS[i % CATEGORY_COLORS.length]);

  new Chart(ctx, {
    type: "doughnut",
    data: { labels, datasets: [{ data: values, backgroundColor: colors, borderColor: "#0E3B36", borderWidth: 2 }] },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: "62%",
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: { label: (ctx) => `${ctx.label}: ${fmtRWF(ctx.parsed)}` },
        },
      },
    },
  });

  const total = values.reduce((a, b) => a + b, 0);
  const legend = document.getElementById("category-legend");
  legend.innerHTML = labels.map((label, i) => {
    const pct = Math.round((values[i] / total) * 100);
    return `<li><span class="swatch" style="background:${colors[i]}"></span>${label} · ${pct}%</li>`;
  }).join("");
}

function renderRegionChart(d) {
  const ctx = document.getElementById("chart-region");
  const sorted = [...d.region_breakdown].sort((a, b) => a.revenue_rwf - b.revenue_rwf);
  new Chart(ctx, {
    type: "bar",
    data: {
      labels: sorted.map(r => r.region),
      datasets: [{
        data: sorted.map(r => r.revenue_rwf),
        backgroundColor: PALETTE.sage,
        borderRadius: 4,
        maxBarThickness: 18,
      }],
    },
    options: {
      indexAxis: "y",
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: (ctx) => fmtRWF(ctx.parsed.x) } },
      },
      scales: {
        x: {
          grid: { color: "rgba(242,239,230,0.06)" },
          ticks: { color: PALETTE.creamDim, font: { family: "IBM Plex Mono", size: 10 }, callback: (v) => fmtShort(v) },
        },
        y: {
          grid: { display: false },
          ticks: { color: PALETTE.creamDim, font: { family: "Inter", size: 11 } },
        },
      },
    },
  });
}

function renderClientChart(d) {
  const ctx = document.getElementById("chart-client");
  const sorted = [...d.client_type_breakdown].sort((a, b) => b.revenue_rwf - a.revenue_rwf);
  new Chart(ctx, {
    type: "bar",
    data: {
      labels: sorted.map(r => r.client_type),
      datasets: [{
        data: sorted.map(r => r.revenue_rwf),
        backgroundColor: PALETTE.gold,
        borderRadius: 4,
        maxBarThickness: 32,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: (ctx) => fmtRWF(ctx.parsed.y) } },
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: { color: PALETTE.creamDim, font: { family: "Inter", size: 10 }, maxRotation: 0, autoSkip: false },
        },
        y: {
          grid: { color: "rgba(242,239,230,0.06)" },
          ticks: { color: PALETTE.creamDim, font: { family: "IBM Plex Mono", size: 10 }, callback: (v) => fmtShort(v) },
        },
      },
    },
  });
}

function renderTopProducts(d) {
  const rows = [...d.top_products].sort((a, b) => b.revenue - a.revenue);
  const max = rows[0]?.revenue || 1;
  const tbody = document.querySelector("#top-products-table tbody");
  tbody.innerHTML = rows.map(r => `
    <tr>
      <td>${r.product}</td>
      <td class="num">${r.units.toLocaleString("en-US")}</td>
      <td class="num">${fmtRWF(r.revenue)}</td>
      <td style="min-width:120px">
        <div class="bar-cell">
          <div class="bar-track"><div class="bar-fill" style="width:${Math.max(4, (r.revenue / max) * 100)}%"></div></div>
        </div>
      </td>
    </tr>
  `).join("");
}

function renderRecent(d) {
  const tbody = document.querySelector("#recent-table tbody");
  tbody.innerHTML = d.recent_transactions.map(t => `
    <tr>
      <td>${fmtDate(t.date)}</td>
      <td>${t.client_name}</td>
      <td>${t.product}</td>
      <td><span class="tag">${t.region.split(" - ").pop()}</span></td>
      <td class="num">${fmtRWF(t.line_total_rwf)}</td>
    </tr>
  `).join("");
}

(async function init() {
  try {
    const d = await loadData();
    renderKPIs(d);
    renderMonthlyChart(d);
    renderCategoryChart(d);
    renderRegionChart(d);
    renderClientChart(d);
    renderTopProducts(d);
    renderRecent(d);
    document.getElementById("last-updated").textContent =
      `· loaded ${new Date().toLocaleTimeString("en-GB")}`;
  } catch (err) {
    console.error("Failed to load dashboard data:", err);
    document.getElementById("connection-label").textContent =
      "Could not load data — check data.json or the API.";
  }
})();
