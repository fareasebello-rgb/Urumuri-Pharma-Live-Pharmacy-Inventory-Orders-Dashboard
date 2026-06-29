const API_BASE = "http://localhost:8000/api";

const PALETTE = {
  gold: "#D9A130", goldDim: "#B4862C",
  sage: "#7FB69E", sageDim: "#5C8C77",
  clay: "#E2725B", teal600: "#246B61", teal700: "#18524B",
  cream: "#F2EFE6", creamDim: "#C9C7BC",
};

const CATEGORY_COLORS = [
  PALETTE.gold, PALETTE.sage, PALETTE.clay, PALETTE.teal600,
  PALETTE.goldDim, PALETTE.sageDim, PALETTE.teal700, PALETTE.creamDim,
  "#8C6BB1", "#4F8A8B",
];

const charts = {};
let snapshotCache = null;
let useLiveApi = false;
let currentInventory = [];

function fmtRWF(n) {
  return `RWF ${Math.round(n || 0).toLocaleString("en-US")}`;
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

function buildUrl(path, params = {}) {
  const usp = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => { if (v !== null && v !== undefined) usp.set(k, v); });
  const qs = usp.toString();
  return `${API_BASE}${path}${qs ? `?${qs}` : ""}`;
}

async function loadWindow(months) {
  if (useLiveApi) {
    try {
      const [kpis, monthly, category, region, clientType, top, insightsList, inventory] = await Promise.all([
        fetchJSON(buildUrl("/kpis", { months })),
        fetchJSON(buildUrl("/monthly-revenue", { months })),
        fetchJSON(buildUrl("/category-breakdown", { months })),
        fetchJSON(buildUrl("/region-breakdown", { months })),
        fetchJSON(buildUrl("/client-type-breakdown", { months })),
        fetchJSON(buildUrl("/top-products", { months, limit: 8 })),
        fetchJSON(buildUrl("/insights", { months })),
        fetchJSON(buildUrl("/inventory", { months })),
      ]);
      return {
        kpis, monthly_revenue: monthly, category_breakdown: category,
        region_breakdown: region, client_type_breakdown: clientType,
        top_products: top, insights: insightsList, inventory,
      };
    } catch (err) {
      console.warn("Live API call failed, using offline snapshot instead.", err);
      useLiveApi = false;
    }
  }
  const snap = snapshotCache.windows[String(months)] || snapshotCache.windows["12"];
  return snap;
}

async function loadNewOrders() {
  if (useLiveApi) {
    try {
      return await fetchJSON(`${API_BASE}/new-orders?limit=12`);
    } catch (err) {
      useLiveApi = false;
    }
  }
  return snapshotCache.new_orders;
}

async function detectApiAndCacheSnapshot() {
  snapshotCache = await fetchJSON("data.json");
  try {
    await fetchJSON(`${API_BASE}/kpis`);
    useLiveApi = true;
  } catch {
    useLiveApi = false;
  }
  setConnectionLabel(useLiveApi);
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
    { label: "Total revenue", value: `RWF ${fmtShort(d.kpis.total_revenue_rwf)}`, sub: fmtRWF(d.kpis.total_revenue_rwf) },
    { label: "Total orders", value: d.kpis.total_orders.toLocaleString("en-US"), sub: `Avg order ${fmtRWF(d.kpis.avg_order_value_rwf)}` },
    { label: "Best month", value: d.kpis.best_month, sub: `${fmtRWF(d.kpis.best_month_revenue_rwf)} · ${pctOfCeiling}% of ceiling`, warn: pctOfCeiling >= 95 },
    { label: "Coverage", value: `${d.kpis.active_regions} regions`, sub: `${d.kpis.active_products} active SKUs` },
    { label: "Stock alerts", value: `${d.kpis.reorder_count}`, sub: d.kpis.reorder_count > 0 ? "products need reordering" : "all stock healthy", warn: d.kpis.reorder_count > 0, link: true },
  ];

  const row = document.getElementById("kpi-row");
  row.innerHTML = cards.map(c => `
    <div class="kpi ${c.link ? "kpi--link" : ""}" ${c.link ? 'data-jump="inventory-section"' : ""}>
      <p class="kpi__label">${c.label}</p>
      <p class="kpi__value">${c.value}</p>
      <p class="kpi__sub ${c.warn ? "kpi__sub--warn" : ""}">${c.sub}</p>
    </div>
  `).join("");

  const jumpCard = row.querySelector("[data-jump]");
  if (jumpCard) {
    jumpCard.style.cursor = "pointer";
    jumpCard.addEventListener("click", () => {
      document.getElementById("inventory-section").scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }
}

function renderInsights(d) {
  const icons = { positive: "▲", warning: "⚠", neutral: "●" };
  const list = document.getElementById("insights-list");
  list.innerHTML = d.insights.map(i => `
    <li class="insight--${i.type}">
      <span class="insight__icon">${icons[i.type] || "●"}</span>
      <span>${i.text}</span>
    </li>
  `).join("");
}

function renderMonthlyChart(d) {
  const ctx = document.getElementById("chart-monthly");
  const labels = d.monthly_revenue.map(r => r.month);
  const values = d.monthly_revenue.map(r => r.revenue_rwf);
  const ceiling = d.kpis.monthly_ceiling_rwf || 15_000_000;

  if (charts.monthly) charts.monthly.destroy();
  charts.monthly = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Revenue", data: values,
          borderColor: PALETTE.gold, backgroundColor: "rgba(217,161,48,0.18)",
          pointBackgroundColor: PALETTE.gold, fill: true, tension: 0.35,
          borderWidth: 2.5, pointRadius: 3,
        },
        {
          label: "Monthly ceiling (RWF 15,000,000)",
          data: labels.map(() => ceiling),
          borderColor: PALETTE.clay, borderDash: [6, 6], borderWidth: 1.5,
          pointRadius: 0, fill: false,
        },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "#0A2826", borderColor: "rgba(242,239,230,0.15)", borderWidth: 1,
          titleFont: { family: "IBM Plex Mono" }, bodyFont: { family: "IBM Plex Mono" },
          callbacks: { label: (ctx) => `${ctx.dataset.label}: ${fmtRWF(ctx.parsed.y)}` },
        },
      },
      scales: {
        x: { grid: { color: "rgba(242,239,230,0.06)" }, ticks: { color: PALETTE.creamDim, font: { family: "IBM Plex Mono", size: 11 } } },
        y: {
          grid: { color: "rgba(242,239,230,0.06)" },
          ticks: { color: PALETTE.creamDim, font: { family: "IBM Plex Mono", size: 11 }, callback: (v) => fmtShort(v) },
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

  if (charts.category) charts.category.destroy();
  charts.category = new Chart(ctx, {
    type: "doughnut",
    data: { labels, datasets: [{ data: values, backgroundColor: colors, borderColor: "#0E3B36", borderWidth: 2 }] },
    options: {
      responsive: true, maintainAspectRatio: false, cutout: "62%",
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: (ctx) => `${ctx.label}: ${fmtRWF(ctx.parsed)}` } } },
    },
  });

  const total = values.reduce((a, b) => a + b, 0) || 1;
  const legend = document.getElementById("category-legend");
  legend.innerHTML = labels.map((label, i) => {
    const pct = Math.round((values[i] / total) * 100);
    return `<li><span class="swatch" style="background:${colors[i]}"></span>${label} · ${pct}%</li>`;
  }).join("");
}

function renderRegionChart(d) {
  const ctx = document.getElementById("chart-region");
  const sorted = [...d.region_breakdown].sort((a, b) => a.revenue_rwf - b.revenue_rwf);
  if (charts.region) charts.region.destroy();
  charts.region = new Chart(ctx, {
    type: "bar",
    data: { labels: sorted.map(r => r.region), datasets: [{ data: sorted.map(r => r.revenue_rwf), backgroundColor: PALETTE.sage, borderRadius: 4, maxBarThickness: 18 }] },
    options: {
      indexAxis: "y", responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: (ctx) => fmtRWF(ctx.parsed.x) } } },
      scales: {
        x: { grid: { color: "rgba(242,239,230,0.06)" }, ticks: { color: PALETTE.creamDim, font: { family: "IBM Plex Mono", size: 10 }, callback: (v) => fmtShort(v) } },
        y: { grid: { display: false }, ticks: { color: PALETTE.creamDim, font: { family: "Inter", size: 11 } } },
      },
    },
  });
}

function renderClientChart(d) {
  const ctx = document.getElementById("chart-client");
  const sorted = [...d.client_type_breakdown].sort((a, b) => b.revenue_rwf - a.revenue_rwf);
  if (charts.client) charts.client.destroy();
  charts.client = new Chart(ctx, {
    type: "bar",
    data: { labels: sorted.map(r => r.client_type), datasets: [{ data: sorted.map(r => r.revenue_rwf), backgroundColor: PALETTE.gold, borderRadius: 4, maxBarThickness: 32 }] },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: (ctx) => fmtRWF(ctx.parsed.y) } } },
      scales: {
        x: { grid: { display: false }, ticks: { color: PALETTE.creamDim, font: { family: "Inter", size: 10 }, maxRotation: 0, autoSkip: false } },
        y: { grid: { color: "rgba(242,239,230,0.06)" }, ticks: { color: PALETTE.creamDim, font: { family: "IBM Plex Mono", size: 10 }, callback: (v) => fmtShort(v) } },
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
        <div class="bar-cell"><div class="bar-track"><div class="bar-fill" style="width:${Math.max(4, (r.revenue / max) * 100)}%"></div></div></div>
      </td>
    </tr>
  `).join("");
}

function renderNewOrders(orders) {
  const tbody = document.querySelector("#new-orders-table tbody");
  tbody.innerHTML = orders.map(t => `
    <tr>
      <td>${fmtDate(t.date)}</td>
      <td>${t.client_name}</td>
      <td>${t.product}</td>
      <td><span class="tag">${t.region.split(" - ").pop()}</span></td>
      <td class="num">${fmtRWF(t.line_total_rwf)}</td>
    </tr>
  `).join("");
}

function statusBadge(row) {
  if (row.needs_reorder) return `<span class="status-badge status-badge--reorder">Reorder now</span>`;
  if (row.days_of_stock_remaining !== null && row.days_of_stock_remaining < 21) {
    return `<span class="status-badge status-badge--low">Low — watch</span>`;
  }
  return `<span class="status-badge status-badge--healthy">Healthy</span>`;
}

function renderInventoryTable(rows) {
  const tbody = document.querySelector("#inventory-table tbody");
  const empty = document.getElementById("inventory-empty");
  if (!rows.length) {
    tbody.innerHTML = "";
    empty.hidden = false;
    return;
  }
  empty.hidden = true;
  tbody.innerHTML = rows.map(r => `
    <tr>
      <td>${r.product}</td>
      <td>${r.category}</td>
      <td class="num">${r.stock_on_hand.toLocaleString("en-US")}</td>
      <td class="num">${r.reorder_threshold.toLocaleString("en-US")}</td>
      <td class="num">${r.days_of_stock_remaining === null ? "—" : r.days_of_stock_remaining}</td>
      <td>${statusBadge(r)}</td>
    </tr>
  `).join("");
}

function renderInventory(d) {
  currentInventory = d.inventory;
  const reorderCount = currentInventory.filter(r => r.needs_reorder).length;
  document.getElementById("reorder-count-tag").textContent =
    reorderCount === 1 ? "1 needs reorder" : `${reorderCount} need reorder`;
  applyInventorySearch();
}

function applyInventorySearch() {
  const q = (document.getElementById("inventory-search").value || "").trim().toLowerCase();
  const filtered = q
    ? currentInventory.filter(r => r.product.toLowerCase().includes(q) || r.category.toLowerCase().includes(q))
    : currentInventory;
  renderInventoryTable(filtered);
}

async function renderForWindow(months) {
  const d = await loadWindow(months);
  const steps = [
    () => renderKPIs(d),
    () => renderInsights(d),
    () => renderMonthlyChart(d),
    () => renderCategoryChart(d),
    () => renderRegionChart(d),
    () => renderClientChart(d),
    () => renderTopProducts(d),
    () => renderInventory(d),
  ];
  for (const step of steps) {
    try { step(); } catch (err) { console.error("Render step failed:", err); }
  }
  document.getElementById("last-updated").textContent = `· loaded ${new Date().toLocaleTimeString("en-GB")}`;
}

function setupRangeToggle() {
  const buttons = document.querySelectorAll("#range-toggle .segmented__btn");
  buttons.forEach(btn => {
    btn.addEventListener("click", async () => {
      buttons.forEach(b => { b.classList.remove("is-active"); b.setAttribute("aria-selected", "false"); });
      btn.classList.add("is-active");
      btn.setAttribute("aria-selected", "true");
      await renderForWindow(Number(btn.dataset.months));
    });
  });
}

function setupSearch() {
  document.getElementById("inventory-search").addEventListener("input", applyInventorySearch);
}

(async function init() {
  try {
    await detectApiAndCacheSnapshot();
  } catch (err) {
    console.error("Failed to load any data source:", err);
    document.getElementById("connection-label").textContent = "Could not load data — check data.json or the API.";
    return;
  }
  setupRangeToggle();
  setupSearch();
  try {
    const orders = await loadNewOrders();
    renderNewOrders(orders);
  } catch (err) {
    console.error("Failed to load new orders:", err);
  }
  await renderForWindow(12);
})();
