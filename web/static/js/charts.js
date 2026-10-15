// Tiny dependency-free SVG chart kit (OOP): TimeChart, BarChart, Heatmap.
import { h, s } from "./lib.js";

const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

function niceTicks(max, count = 4) {
  if (max <= 0) return [0, 1];
  const raw = max / count;
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((st) => st >= raw);
  const ticks = [];
  for (let v = 0; v <= max + step * 0.001; v += step) ticks.push(v);
  if (ticks[ticks.length - 1] < max) ticks.push(ticks[ticks.length - 1] + step);
  return ticks;
}

class Chart {
  constructor(el, { height = 260, format = String } = {}) {
    this.el = el;
    this.height = height;
    this.format = format;
    this.tooltip = h("div", { class: "tooltip", role: "status" });
    this.ro = new ResizeObserver(() => this.render());
    document.addEventListener("themechange", () => this.render());
    matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => this.render());
  }
  mount() {
    this.el.replaceChildren();
    this.ro.observe(this.el);
    this.render();
    return this;
  }
  get width() { return Math.max(260, this.el.clientWidth || 600); }
  show(x, y, html) {
    this.tooltip.innerHTML = html;
    this.tooltip.style.left = `${x}px`;
    this.tooltip.style.top = `${y}px`;
    this.tooltip.classList.add("is-on");
  }
  hide() { this.tooltip.classList.remove("is-on"); }
}

/** Categorical-x chart that can mix bars, lines and an uncertainty band on one y-axis. */
export class TimeChart extends Chart {
  constructor(el, { labels, series, labelFormat = (l) => l, ...opts }) {
    super(el, opts);
    this.labels = labels;
    this.series = series;
    this.labelFormat = labelFormat;
  }

  render() {
    const W = this.width, H = this.height, m = { t: 12, r: 12, b: 26, l: 54 };
    const iw = W - m.l - m.r, ih = H - m.t - m.b, n = this.labels.length;
    const max = Math.max(1, ...this.series.flatMap((sr) => [...(sr.values || []), ...(sr.high || [])].filter((v) => v != null)));
    const ticks = niceTicks(max);
    const top = ticks[ticks.length - 1];
    const x = (i) => m.l + (n === 1 ? iw / 2 : (i + 0.5) * (iw / n));
    const y = (v) => m.t + ih - (v / top) * ih;
    const band = iw / n;
    const svg = s("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": this.el.dataset.label || "Chart" });

    for (const t of ticks) {
      svg.append(s("line", { class: "gridline", x1: m.l, x2: W - m.r, y1: y(t), y2: y(t) }));
      svg.append(s("text", { x: m.l - 8, y: y(t) + 4, "text-anchor": "end" }, this.format(t, true)));
    }
    const every = Math.ceil(n / Math.max(2, Math.floor(iw / 70)));
    this.labels.forEach((l, i) => {
      if (i % every === 0) svg.append(s("text", { x: x(i), y: H - 6, "text-anchor": "middle" }, this.labelFormat(l)));
    });

    for (const sr of this.series) {
      const color = css(sr.color) || sr.color;
      if (sr.kind === "bar") {
        const bw = Math.max(2, band - 2);
        sr.values.forEach((v, i) => {
          if (v == null) return;
          const hgt = Math.max(0, m.t + ih - y(v));
          svg.append(s("rect", { x: x(i) - bw / 2, y: y(v), width: bw, height: hgt, rx: Math.min(3, bw / 2), fill: color }));
        });
      } else if (sr.kind === "band") {
        const pts = sr.high.map((v, i) => (v == null ? null : [x(i), y(v)])).filter(Boolean);
        const low = sr.low.map((v, i) => (v == null ? null : [x(i), y(v)])).filter(Boolean).reverse();
        if (pts.length) svg.append(s("path", { d: `M${[...pts, ...low].map((p) => p.join(",")).join(" L")} Z`, fill: color, opacity: 0.18 }));
      } else {
        let d = "", pen = false;
        sr.values.forEach((v, i) => {
          if (v == null) { pen = false; return; }
          d += `${pen ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)} `; pen = true;
        });
        svg.append(s("path", { d, fill: "none", stroke: color, "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round", "stroke-dasharray": sr.dashed ? "5 4" : null }));
      }
    }

    // Crosshair + tooltip
    const cross = s("line", { class: "tip-line", y1: m.t, y2: m.t + ih, opacity: 0 });
    const dots = this.series.filter((sr) => sr.kind === "line").map((sr) => s("circle", { r: 4, fill: css(sr.color) || sr.color, stroke: css("--paper"), "stroke-width": 2, opacity: 0 }));
    svg.append(cross, ...dots);
    const hit = s("rect", { x: m.l, y: m.t, width: iw, height: ih, fill: "transparent" });
    svg.append(hit);
    const move = (ev) => {
      const rect = svg.getBoundingClientRect();
      const px = ((ev.clientX - rect.left) / rect.width) * W;
      const i = Math.max(0, Math.min(n - 1, Math.floor((px - m.l) / band)));
      cross.setAttribute("x1", x(i)); cross.setAttribute("x2", x(i)); cross.setAttribute("opacity", 1);
      const rows = [];
      let li = 0, minY = H;
      for (const sr of this.series) {
        if (sr.kind === "band") { if (sr.low[i] != null) rows.push(`${sr.name}: ${this.format(sr.low[i])}–${this.format(sr.high[i])}`); continue; }
        const v = sr.values[i];
        if (sr.kind === "line") {
          const dot = dots[li++];
          dot.setAttribute("opacity", v == null ? 0 : 1);
          if (v != null) { dot.setAttribute("cx", x(i)); dot.setAttribute("cy", y(v)); }
        }
        if (v != null) { rows.push(`${sr.name}: <b>${this.format(v)}</b>`); minY = Math.min(minY, y(v)); }
      }
      const scale = rect.width / W;
      this.show(x(i) * scale, Math.max(10, minY * scale), `<b>${this.labelFormat(this.labels[i], true)}</b><br>${rows.join("<br>")}`);
    };
    hit.addEventListener("pointermove", move);
    hit.addEventListener("pointerleave", () => { this.hide(); cross.setAttribute("opacity", 0); dots.forEach((d) => d.setAttribute("opacity", 0)); });
    this.el.replaceChildren(svg, this.tooltip);
  }
}

/** Single-series bar chart, vertical or horizontal, with selective direct labels. */
export class BarChart extends Chart {
  constructor(el, { labels, values, color = "--series-1", horizontal = false, labelAll = false, ...opts }) {
    super(el, opts);
    Object.assign(this, { labels, values, color, horizontal, labelAll });
  }

  render() {
    const W = this.width, n = this.labels.length;
    const color = css(this.color) || this.color;
    const max = Math.max(1, ...this.values);
    if (this.horizontal) {
      const rowH = 34, m = { t: 4, r: 70, b: 4, l: 90 };
      const H = m.t + m.b + n * rowH;
      const iw = W - m.l - m.r;
      const svg = s("svg", { viewBox: `0 0 ${W} ${H}`, role: "img" });
      this.labels.forEach((label, i) => {
        const v = this.values[i], yy = m.t + i * rowH, bw = Math.max(2, (v / max) * iw);
        svg.append(s("text", { x: m.l - 10, y: yy + rowH / 2 + 4, "text-anchor": "end", style: `fill:${css("--ink-2")};font-weight:600` }, label));
        const bar = s("rect", { x: m.l, y: yy + 7, width: bw, height: rowH - 14, rx: 4, fill: color });
        svg.append(bar, s("text", { x: m.l + bw + 8, y: yy + rowH / 2 + 4, style: `fill:${css("--ink")};font-weight:650` }, this.format(v)));
      });
      this.el.replaceChildren(svg);
      return;
    }
    const H = this.height, m = { t: 22, r: 8, b: 28, l: 8 };
    const iw = W - m.l - m.r, ih = H - m.t - m.b, band = iw / n, bw = Math.min(56, band * 0.62);
    const svg = s("svg", { viewBox: `0 0 ${W} ${H}`, role: "img" });
    svg.append(s("line", { class: "axis", x1: m.l, x2: W - m.r, y1: m.t + ih, y2: m.t + ih }));
    const peak = this.values.indexOf(Math.max(...this.values));
    this.labels.forEach((label, i) => {
      const v = this.values[i], cx = m.l + band * (i + 0.5), hgt = (v / max) * ih;
      const bar = s("rect", { x: cx - bw / 2, y: m.t + ih - hgt, width: bw, height: Math.max(0, hgt), rx: 4, fill: color });
      svg.append(bar, s("text", { x: cx, y: H - 8, "text-anchor": "middle" }, label));
      if (this.labelAll || i === peak) svg.append(s("text", { x: cx, y: m.t + ih - hgt - 7, "text-anchor": "middle", style: `fill:${css("--ink")};font-weight:650` }, this.format(v)));
      const hit = s("rect", { x: cx - band / 2, y: m.t, width: band, height: ih, fill: "transparent" });
      hit.addEventListener("pointerenter", () => {
        const scale = svg.getBoundingClientRect().width / W;
        bar.setAttribute("opacity", ".8");
        this.show(cx * scale, (m.t + ih - hgt) * scale, `<b>${label}</b><br>${this.format(v)}`);
      });
      hit.addEventListener("pointerleave", () => { bar.removeAttribute("opacity"); this.hide(); });
      svg.append(hit);
    });
    this.el.replaceChildren(svg, this.tooltip);
  }
}

/** 7×24 sequential heatmap built from HTML cells (crisp at any size). */
export class Heatmap {
  constructor(el, { days, grid, max }) { Object.assign(this, { el, days, grid, max }); }
  mount() {
    const ramp = ["--seq-100", "--seq-250", "--seq-400", "--seq-550", "--seq-700"];
    const wrap = h("div", { class: "heatmap", role: "img", "aria-label": "Bookings by weekday and hour" });
    wrap.append(h("span"));
    for (let hr = 0; hr < 24; hr++) wrap.append(h("span", { class: "hour" }, hr % 6 === 0 ? String(hr).padStart(2, "0") : ""));
    this.grid.forEach((row, d) => {
      wrap.append(h("span", {}, this.days[d]));
      row.forEach((v, hr) => {
        const step = v === 0 ? null : ramp[Math.min(ramp.length - 1, Math.floor((v / (this.max || 1)) * ramp.length))];
        wrap.append(h("span", { class: "cell", title: `${this.days[d]} ${String(hr).padStart(2, "0")}:00, ${v} bookings`,
          style: { background: step ? `var(${step})` : "var(--bg)" } }));
      });
    });
    this.el.replaceChildren(wrap, h("div", { class: "heat-scale" }, "Fewer", h("i"), "More"));
    return this;
  }
}
