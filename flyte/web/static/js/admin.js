// Ops dashboard: fetches /api/admin/overview and renders KPIs, charts and tables.
import { Api, countUp, h, int, money, moneyShort, pct, reducedMotion, toast } from "./lib.js";
import { BarChart, Heatmap, TimeChart } from "./charts.js";

const shortDate = (iso, long) => {
  const d = new Date(`${iso}T00:00:00`);
  return d.toLocaleDateString("en-GB", long ? { weekday: "short", day: "numeric", month: "short" } : { day: "numeric", month: "short" });
};

class KpiStrip {
  static FORMATS = {
    revenue: moneyShort, avg_fare: money, load_factor: (v) => pct(v, 1), rask: (v) => `₦${v.toFixed(0)}`,
    otp: (v) => pct(v, 0), bookings: int, attach_rate: (v) => pct(v, 0), cancel_rate: (v) => pct(v, 1),
  };
  static render(kpis) {
    document.querySelectorAll("[data-kpi]").forEach((tile) => {
      const key = tile.dataset.kpi, k = kpis[key];
      if (!k) return;
      const fmt = KpiStrip.FORMATS[key] || int;
      countUp(tile.querySelector("[data-v]"), k.value ?? 0, { format: fmt });
      const d = tile.querySelector("[data-d]");
      if (k.delta == null) { d.textContent = ""; return; }
      const good = tile.hasAttribute("data-invert") ? k.delta < 0 : k.delta > 0;
      const flat = Math.abs(k.delta) < 0.005;
      d.className = `kpi__delta ${flat ? "is-flat" : good ? "is-up" : "is-down"}`;
      d.replaceChildren(
        h("span", {}, flat ? "→" : k.delta > 0 ? "▲" : "▼"),
        `${Math.abs(k.delta * 100).toFixed(1)}% vs previous 30 days`);
    });
  }
}

class SplitFlap {
  static CHARS = " ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789:–";
  static render(text, el) {
    const box = h("span", { class: "flap", "aria-label": text });
    const cells = [...text.toUpperCase()].map(() => h("b", { "aria-hidden": "true" }, " "));
    box.append(...cells);
    el.replaceChildren(box);
    if (reducedMotion()) { cells.forEach((c, i) => { c.textContent = text[i].toUpperCase(); }); return; }
    [...text.toUpperCase()].forEach((ch, i) => {
      let flips = 4 + ((i * 7) % 6);
      const timer = setInterval(() => {
        const cell = cells[i];
        cell.classList.remove("is-flipping"); void cell.offsetWidth; cell.classList.add("is-flipping");
        if (--flips <= 0) { cell.textContent = ch === " " ? " " : ch; clearInterval(timer); }
        else cell.textContent = SplitFlap.CHARS[(Math.random() * SplitFlap.CHARS.length) | 0];
      }, 70);
    });
  }
}

class Dashboard {
  constructor(root) { this.root = root; }

  async load() {
    try {
      this.data = await Api.get(this.root.dataset.src);
    } catch (err) {
      toast(err.message, "error");
      return;
    }
    const d = this.data;
    if (d.kpis.empty) { toast("No bookings yet. Insights appear after the first sale."); return; }
    KpiStrip.render(d.kpis);
    this.revenue(d.series);
    this.forecast(d.forecast);
    this.cabins(d.cabins);
    this.lead(d.lead_time);
    this.routes(d.routes);
    this.airlines(d.airlines);
    new Heatmap(document.getElementById("heatmap"), d.heatmap).mount();
    this.segments(d.segments);
    this.board(d.board);
    this.atRisk(d.at_risk);
    this.topCustomers(d.top_customers);
    new BarChart(document.getElementById("chart-ages"), {
      labels: d.ages.map((a) => a.band), values: d.ages.map((a) => a.passengers), color: "--series-1", height: 220, format: int,
    }).mount();
  }

  revenue(series) {
    new TimeChart(document.getElementById("chart-revenue"), {
      labels: series.dates, labelFormat: shortDate, format: (v) => moneyShort(v), height: 260,
      series: [
        { name: "Revenue", kind: "bar", values: series.revenue, color: "--seq-250" },
        { name: "7-day avg", kind: "line", values: series.revenue_ma7, color: "--series-1" },
      ],
    }).mount();
  }

  forecast(f) {
    const hist = f.history.dates.slice(-28), histV = f.history.values.slice(-28);
    const labels = [...hist, ...f.forecast.dates];
    const pad = (arr, before, after = 0) => [...Array(before).fill(null), ...arr, ...Array(after).fill(null)];
    // Join the forecast line to the last actual point so the two read as one story.
    const lastActual = histV[histV.length - 1];
    const meanJoined = [...Array(hist.length - 1).fill(null), lastActual, ...f.forecast.mean];
    new TimeChart(document.getElementById("chart-forecast"), {
      labels, labelFormat: shortDate, format: (v) => int(v), height: 260,
      series: [
        { name: "80% range", kind: "band", low: pad(f.forecast.low, hist.length), high: pad(f.forecast.high, hist.length), color: "--series-1" },
        { name: "Actual", kind: "line", values: pad(histV, 0, f.forecast.dates.length), color: "--ink-3" },
        { name: "Forecast", kind: "line", values: meanJoined, color: "--series-1", dashed: true },
      ],
    }).mount();
    document.getElementById("forecast-sub").textContent =
      `About ${int(f.next_7_days)} bookings expected in the next 7 days`;
    const bt = f.backtest;
    const pattern = Object.entries(f.weekly_pattern);
    const best = pattern.reduce((a, b) => (b[1] > a[1] ? b : a));
    const worst = pattern.reduce((a, b) => (b[1] < a[1] ? b : a));
    document.getElementById("model-card").replaceChildren(
      h("div", { class: "kpi" }, h("span", { class: "kpi__label" }, "Backtest error (MAPE, last 14 days)"),
        h("span", { class: "kpi__value num" }, bt.mape == null ? "n/a" : pct(bt.mape, 1)),
        h("span", { class: "kpi__note" }, bt.mae == null ? "" : `Off by about ${int(bt.mae)} bookings a day on average`)),
      h("hr", { class: "divider" }),
      h("p", { class: "small" }, h("strong", {}, "Trend: "), `${f.trend_per_day >= 0 ? "+" : ""}${f.trend_per_day.toFixed(2)} bookings/day each day`),
      h("p", { class: "small" }, h("strong", {}, "Weekly rhythm: "), `${best[0]} is the busiest booking day, ${worst[0]} the quietest.`),
      h("p", { class: "tiny muted" }, f.model),
    );
  }

  cabins(cabins) {
    new BarChart(document.getElementById("chart-cabins"), {
      labels: cabins.map((c) => c.cabin), values: cabins.map((c) => c.revenue), horizontal: true, color: "--series-1", format: moneyShort,
    }).mount();
  }

  lead(rows) {
    new BarChart(document.getElementById("chart-lead"), {
      labels: rows.map((r) => r.bin), values: rows.map((r) => r.bookings), color: "--series-1", height: 230, format: int,
    }).mount();
    new BarChart(document.getElementById("chart-leadfare"), {
      labels: rows.map((r) => r.bin), values: rows.map((r) => r.avg_economy_fare), color: "--series-2", height: 230, format: moneyShort, labelAll: true,
    }).mount();
  }

  routes(rows) {
    const maxRev = Math.max(...rows.map((r) => r.revenue), 1);
    const table = h("table", { class: "data" },
      h("thead", {}, h("tr", {}, ...["Route", "Revenue", "Load factor", "Avg fare", "Yield/km"].map((t, i) => h("th", { class: i > 2 ? "r" : "" }, t)))),
      h("tbody", {}, ...rows.map((r) => h("tr", {},
        h("td", {}, h("strong", {}, r.route), h("div", { class: "tiny muted" }, `${int(r.distance_km)} km, ${r.flights} flights`)),
        h("td", {}, h("div", { class: "inline-bar" }, h("div", { class: "meter", style: { "--v": r.revenue / maxRev } }, h("i", { style: { background: "var(--series-1)" } })), h("span", { class: "small num" }, moneyShort(r.revenue)))),
        h("td", { class: "num" }, pct(r.load_factor, 0)),
        h("td", { class: "r" }, money(r.avg_fare)),
        h("td", { class: "r" }, `₦${r.yield_per_km}`),
      ))));
    document.getElementById("routes").replaceChildren(table);
  }

  airlines(rows) {
    const box = document.getElementById("airlines");
    if (!rows.length) { box.replaceChildren(h("p", { class: "muted" }, "No airline data yet.")); return; }
    const maxShare = Math.max(...rows.map((r) => r.revenue_share), 0.01);
    box.replaceChildren(h("table", { class: "data" },
      h("thead", {}, h("tr", {}, ...["Airline", "Revenue share", "Avg fare", "Load factor", "On time", "Buy extra bags", "Bag fees"].map((t, i) => h("th", { class: i > 1 ? "r" : "" }, t)))),
      h("tbody", {}, ...rows.map((r) => h("tr", {},
        h("td", {}, h("span", { class: "row", style: { gap: "8px", flexWrap: "nowrap" } },
          h("span", { class: "al-badge al-badge--sm", style: { "--al": r.colour } }, r.code), h("strong", {}, r.airline)),
          h("div", { class: "tiny muted" }, `${int(r.bookings)} bookings, ${r.flights} flights flown`)),
        h("td", {}, h("div", { class: "inline-bar" }, h("div", { class: "meter", style: { "--v": r.revenue_share / maxShare } }, h("i", { style: { background: "var(--series-1)" } })), h("span", { class: "small num" }, pct(r.revenue_share)))),
        h("td", { class: "r" }, money(r.avg_fare)),
        h("td", { class: "r" }, pct(r.load_factor)),
        h("td", { class: "r" }, pct(r.otp)),
        h("td", { class: "r" }, pct(r.bag_rate)),
        h("td", { class: "r" }, moneyShort(r.bag_fees)),
      )))));
  }

  segments(seg) {
    const box = document.getElementById("segments");
    if (!seg.segments.length) { box.replaceChildren(h("p", { class: "muted" }, "Not enough passengers to segment yet.")); return; }
    document.getElementById("seg-sub").textContent =
      `K-means (k=4) on ${int(seg.n)} passengers: trips, spend, lead time, premium share. Silhouette ${seg.silhouette}`;
    box.replaceChildren(...seg.segments.map((s) => h("div", { class: "segment" },
      h("h4", {}, s.name),
      h("p", {}, s.description),
      h("div", {}, h("div", { class: "meter-label" }, h("span", {}, "Share of revenue"), h("strong", {}, pct(s.share_of_revenue))),
        h("div", { class: "meter" }, h("i", { style: { width: pct(s.share_of_revenue, 1), background: "var(--series-1)" } }))),
      h("dl", {},
        h("dt", {}, "Passengers"), h("dd", {}, `${int(s.size)} (${pct(s.share_of_passengers)})`),
        h("dt", {}, "Trips each"), h("dd", {}, s.avg_trips.toFixed(1)),
        h("dt", {}, "Spend each"), h("dd", {}, moneyShort(s.avg_spend)),
        h("dt", {}, "Books ahead"), h("dd", {}, `${s.avg_lead_days} days`),
        h("dt", {}, "Premium cabins"), h("dd", {}, pct(s.premium_share))),
    )));
  }

  board(rows) {
    const statusClass = (st) => (st === "Cancelled" ? "st-bad" : st === "Delayed" ? "st-warn" : "st-ok");
    const table = h("table", {},
      h("thead", {}, h("tr", {}, ...["Time", "Flight", "To", "Load", "Status"].map((t) => h("th", {}, t)))),
      h("tbody"));
    const body = table.querySelector("tbody");
    rows.forEach((r) => {
      const tr = h("tr", {}, h("td", {}), h("td", {}), h("td", {}), h("td", { class: "num" }, pct(r.load_factor)), h("td", { class: statusClass(r.status) }));
      body.append(tr);
      SplitFlap.render(r.departure.slice(11, 16), tr.children[0]);
      SplitFlap.render(r.number, tr.children[1]);
      tr.children[2].textContent = `${r.destination}`;
      tr.children[4].textContent = r.status === "Delayed" ? `Delayed ${r.delay_minutes}m` : r.status;
    });
    if (!rows.length) body.append(h("tr", {}, h("td", { colspan: 5 }, "No departures in the next 72 hours.")));
    document.getElementById("board").replaceChildren(table);
  }

  atRisk(rows) {
    const box = document.getElementById("at-risk");
    if (!rows.length) { box.replaceChildren(h("p", { class: "muted" }, "Every flight in the next 10 days is on pace.")); return; }
    box.replaceChildren(h("div", { class: "table-wrap" }, h("table", { class: "data" },
      h("thead", {}, h("tr", {}, ...["Flight", "Departs", "Sold", "Usual by now", ""].map((t) => h("th", {}, t)))),
      h("tbody", {}, ...rows.map((r) => h("tr", {},
        h("td", {}, h("strong", {}, r.number), h("div", { class: "tiny muted" }, `${r.origin_code} → ${r.destination_code}`)),
        h("td", { class: "small num" }, `${r.departure.slice(5, 16)}`),
        h("td", { class: "num" }, pct(r.load_factor)),
        h("td", { class: "num" }, pct(r.expected_load_factor)),
        h("td", {}, h("span", { class: "chip chip--bad" }, `${Math.round(r.gap * 100)} pts`)),
      ))))));
  }

  topCustomers(rows) {
    document.getElementById("top-customers").replaceChildren(h("table", { class: "data" },
      h("thead", {}, h("tr", {}, ...["Passenger", "Tier", "Trips", "Spend"].map((t, i) => h("th", { class: i > 1 ? "r" : "" }, t)))),
      h("tbody", {}, ...rows.map((r) => h("tr", {},
        h("td", {}, h("strong", {}, r.name)), h("td", {}, h("span", { class: "chip" }, r.tier)),
        h("td", { class: "r" }, r.trips), h("td", { class: "r" }, moneyShort(r.spend)))))));
  }
}

const root = document.getElementById("dashboard");
if (root) new Dashboard(root).load();
