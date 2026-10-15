// Seat map + sparkline components shared by single-flight and trip checkout.
import { Api, h, s } from "./lib.js";

export class SeatMap {
  constructor(container, onPick) {
    this.container = container;
    this.onPick = onPick;
    this.data = null;
    this.cabin = "Economy";
    this.picked = null;
  }

  async load(url) {
    this.data = await Api.get(url);
    this.render();
  }

  setCabin(cabin) {
    this.cabin = cabin;
    if (this.picked && this.cabinOf(this.picked) !== cabin) this.picked = null;
    this.render();
  }

  cabinOf(seat) {
    for (const row of this.data?.rows || []) for (const x of row.seats) if (x.seat === seat) return x.cabin;
    return null;
  }

  isFree(seat) {
    for (const row of this.data?.rows || []) for (const x of row.seats) if (x.seat === seat) return !x.taken;
    return false;
  }

  render() {
    if (!this.data) return;
    const frag = document.createDocumentFragment();
    let lastCabin = null;
    let firstInCabin = null;
    for (const row of this.data.rows) {
      const cabin = row.seats[0].cabin;
      const line = h("div", { class: "seatrow" });
      if (cabin !== lastCabin) {
        line.append(h("div", { class: "cabin-label" }, cabin));
        lastCabin = cabin;
      }
      const bySeat = Object.fromEntries(row.seats.map((x) => [x.seat.replace(/\d+/, ""), x]));
      this.data.columns.forEach((col, i) => {
        if (i === 3) line.append(h("span", { class: "seatrow__no" }, row.row));
        const x = bySeat[col];
        if (!x) { line.append(h("span")); return; }
        const mine = x.cabin === this.cabin;
        const cls = ["seat", x.taken ? "is-taken" : mine ? "is-cabin" : "is-other", x.seat === this.picked ? "is-picked" : ""].join(" ");
        const btn = h("button", {
          type: "button", class: cls, disabled: x.taken || !mine,
          "aria-label": `Seat ${x.seat}, ${x.cabin}${x.taken ? ", taken" : ""}${col === "A" || col === "F" ? ", window" : col === "C" || col === "D" ? ", aisle" : ""}`,
          "aria-pressed": x.seat === this.picked ? "true" : "false",
          "data-seat": x.seat,
        }, x.taken ? "" : col);
        line.append(btn);
        if (mine && !firstInCabin) firstInCabin = line;
      });
      frag.append(line);
    }
    this.container.replaceChildren(frag);
    this.container.onclick = (e) => {
      const btn = e.target.closest("[data-seat]");
      if (!btn || btn.disabled) return;
      this.picked = btn.dataset.seat;
      this.render();
      this.onPick(this.picked);
    };
    const target = this.picked ? this.container.querySelector(`[data-seat="${this.picked}"]`) : firstInCabin;
    if (target) this.container.scrollTop = Math.max(0, target.offsetTop - 80);
  }
}

export class FareSparkline {
  constructor(svg) { this.svg = svg; }
  draw(points) {
    const W = 300, H = 54, pad = 5;
    const fares = points.map((p) => p.fare);
    if (fares.length < 2) { this.svg.replaceChildren(); return; }
    const lo = Math.min(...fares) * 0.98, hi = Math.max(...fares) * 1.02;
    const x = (i) => pad + (i / (fares.length - 1)) * (W - pad * 2);
    const y = (v) => H - pad - ((v - lo) / (hi - lo || 1)) * (H - pad * 2);
    const line = fares.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
    this.svg.replaceChildren(
      s("path", { class: "area", d: `${line} L${x(fares.length - 1)},${H} L${x(0)},${H} Z` }),
      s("path", { class: "line", d: line }),
      s("circle", { cx: x(0), cy: y(fares[0]), r: 4 }),
    );
  }
}
