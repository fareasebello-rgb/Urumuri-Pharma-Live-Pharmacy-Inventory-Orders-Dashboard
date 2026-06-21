const API_BASE = "http://localhost:8000/api";

const PALETTE = {
  gold: "#D9A130",
  sage: "#7FB69E",
  clay: "#E2725B",
  creamDim: "#C9C7BC",
};

function fmtRWF(value) {
  const rounded = Math.round(value || 0);
  return `RWF ${rounded.toLocaleString("en-US")}`;
}

function setConnectionLabel(live) {
  const label = document.getElementById("connection-label");
  const dot = document.querySelector(".dot--live");
  const statusBox = document.getElementById("status-box");
  const formElements = document.querySelectorAll("#order-form input, #order-form select, #order-form button");

  formElements.forEach((element) => {
    element.disabled = !live;
  });

  if (live) {
    label.textContent = "Live API connected";
    dot.style.background = PALETTE.sage;
    statusBox.textContent = "Connected to the live inventory and order backend.";
    statusBox.className = "message message--info";
  } else {
    label.textContent = "Offline — live API unavailable";
    dot.style.background = "rgba(242,239,230,0.4)";
    statusBox.textContent = "Unable to reach the API. Orders are disabled until the backend is running.";
    statusBox.className = "message message--error";
  }
}

function setOrderStatus(message, type = "info") {
  const status = document.getElementById("order-status");
  status.textContent = message;
  status.className = `message message--${type}`;
  status.style.display = "block";
}

function clearOrderStatus() {
  const status = document.getElementById("order-status");
  status.textContent = "";
  status.className = "message message--hidden";
}

async function fetchJSON(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const detail = payload?.detail || response.statusText;
    throw new Error(`${response.status} ${detail}`);
  }
  return response.json();
}

async function loadData() {
  const [kpis, inventory, orders, metadata] = await Promise.all([
    fetchJSON(`${API_BASE}/kpis`),
    fetchJSON(`${API_BASE}/inventory`),
    fetchJSON(`${API_BASE}/orders`),
    fetchJSON(`${API_BASE}/metadata`),
  ]);

  setConnectionLabel(true);

  return { kpis, inventory, orders, metadata };
}

function renderKPIs(data) {
  const cards = [
    {
      label: "Total revenue (YTD)",
      value: fmtRWF(data.kpis.total_revenue_rwf),
      sub: `Avg order ${fmtRWF(data.kpis.avg_order_value_rwf)}`,
    },
    {
      label: "Sales orders",
      value: data.kpis.total_orders.toLocaleString("en-US"),
      sub: `Best month ${data.kpis.best_month || "—"}`,
    },
    {
      label: "Stock value",
      value: fmtRWF(data.kpis.inventory_value_rwf),
      sub: `${data.kpis.low_stock_skus} low-stock SKUs`,
      warn: data.kpis.low_stock_skus > 0,
    },
    {
      label: "Monthly ceiling",
      value: fmtRWF(data.kpis.monthly_ceiling_rwf),
      sub: "Business rule enforced for orders",
    },
  ];

  const row = document.getElementById("kpi-row");
  row.innerHTML = cards
    .map(
      (card) => `
      <div class="kpi">
        <p class="kpi__label">${card.label}</p>
        <p class="kpi__value">${card.value}</p>
        <p class="kpi__sub ${card.warn ? "kpi__sub--warn" : ""}">${card.sub}</p>
      </div>
    `
    )
    .join("");
}

function renderInventory(items) {
  const body = document.querySelector("#inventory-table tbody");
  body.innerHTML = items
    .map((item) => {
      const low = item.stock <= item.reorder_level;
      return `
        <tr>
          <td>${item.product}</td>
          <td>${item.category}</td>
          <td class="num">${fmtRWF(item.unit_price_rwf)}</td>
          <td class="num">${item.stock}</td>
          <td class="num ${low ? "kpi__sub--warn" : ""}">${item.reorder_level}</td>
        </tr>
      `;
    })
    .join("");
}

function renderRecentOrders(orders) {
  const body = document.querySelector("#recent-orders-table tbody");
  body.innerHTML = orders
    .map(
      (order) => `
        <tr>
          <td>${new Date(order.date).toLocaleDateString("en-GB")}</td>
          <td>${order.client_name}</td>
          <td>${order.product}</td>
          <td class="num">${order.quantity}</td>
          <td class="num">${fmtRWF(order.line_total_rwf)}</td>
        </tr>
      `
    )
    .join("");
}

function renderOrderForm(inventory, metadata) {
  const productSelect = document.getElementById("product");
  const regionSelect = document.getElementById("region");
  const clientTypeSelect = document.getElementById("client_type");

  productSelect.innerHTML = inventory
    .map((item) => `<option value="${item.product}">${item.product} — ${fmtRWF(item.unit_price_rwf)}</option>`)
    .join("");

  regionSelect.innerHTML = metadata.regions
    .map((region) => `<option value="${region}">${region}</option>`)
    .join("");

  clientTypeSelect.innerHTML = metadata.client_types
    .map((type) => `<option value="${type}">${type}</option>`)
    .join("");
}

async function submitOrder(event) {
  event.preventDefault();
  clearOrderStatus();

  const product = document.getElementById("product").value;
  const quantity = Number(document.getElementById("quantity").value);
  const client_name = document.getElementById("client_name").value.trim();
  const region = document.getElementById("region").value;
  const client_type = document.getElementById("client_type").value;

  if (!product || !quantity || !client_name || !region || !client_type) {
    setOrderStatus("Please complete all order fields.", "error");
    return;
  }

  const button = event.target.querySelector("button");
  button.disabled = true;
  button.textContent = "Placing order…";

  try {
    await fetchJSON(`${API_BASE}/order`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ product, quantity, client_name, region, client_type }),
    });

    setOrderStatus("Order accepted and inventory updated.", "success");
    event.target.reset();

    const data = await loadData();
    renderKPIs(data);
    renderInventory(data.inventory);
    renderRecentOrders(data.orders);
  } catch (err) {
    setOrderStatus(err.message, "error");
  } finally {
    button.disabled = false;
    button.textContent = "Place order";
  }
}

window.addEventListener("DOMContentLoaded", async () => {
  const orderForm = document.getElementById("order-form");
  orderForm.addEventListener("submit", submitOrder);

  try {
    const data = await loadData();
    renderKPIs(data);
    renderInventory(data.inventory);
    renderRecentOrders(data.orders);
    renderOrderForm(data.inventory, data.metadata);
    const lastUpdated = document.getElementById("last-updated");
    lastUpdated.textContent = `Updated ${new Date().toLocaleString()}`;
  } catch (error) {
    console.error(error);
    setConnectionLabel(false);
  }
});
