// Booking stepper: cabin → seat → cover → pay, with live quotes and the fare forecast.
import { Api, h, money, s, toast } from "./lib.js";

const STEPS = ["cabin", "seat", "bags", "cover", "pay"];
const STATE_KEY = "flyte-booking";

class SeatMap {
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

class FareSparkline {
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

class BookingFlow {
  constructor(root) {
    this.root = root;
    this.number = root.dataset.flight;
    this.state = { cabin: this.radio("cabin"), seat: null, insurance: this.radio("insurance"), bags: 0 };
    const d = root.dataset;
    this.bagRules = { first: Number(d.bagFirst), next: Number(d.bagNext), max: Number(d.bagMax), kg: Number(d.bagKg),
      included: Object.fromEntries(JSON.parse(d.cabins).map((c, i) => [c, JSON.parse(d.included)[i]])) };
    this.seatMap = new SeatMap(document.getElementById("seatmap"), (seat) => this.pickSeat(seat));
    this.spark = new FareSparkline(root.querySelector(".spark"));
    this.restore();
    this.bind();
    this.seatMap.cabin = this.state.cabin;
    this.seatMap.picked = this.state.seat;
    this.seatMap.load(`/api/flights/${this.number}/seats`).then(() => {
      if (this.state.seat && !this.seatMap.isFree(this.state.seat)) this.pickSeat(null);
    });
    this.setBags(this.state.bags || 0, false);
    this.refresh();
    this.goto(this.state.resumeAt || "cabin");
  }

  // Mirrors BaggagePolicy.fee_for() on the server, for instant feedback; the server re-prices at checkout.
  bagFee(n) { return n <= 0 ? 0 : this.bagRules.first + (n - 1) * this.bagRules.next; }

  setBags(n, refresh = true) {
    this.state.bags = Math.max(0, Math.min(this.bagRules.max, n));
    const n2 = this.state.bags;
    document.getElementById("bag-count").textContent = String(n2);
    this.root.querySelector('[data-bags="-1"]').disabled = n2 === 0;
    this.root.querySelector('[data-bags="1"]').disabled = n2 === this.bagRules.max;
    const inc = this.bagRules.included[this.state.cabin] ?? 0;
    this.$("[data-included-label]").textContent = inc ? `${inc} × ${this.bagRules.kg}kg checked bag${inc > 1 ? "s" : ""}` : "no checked bags";
    this.$("[data-bag-fee-line]").textContent = n2
      ? `${n2} extra bag${n2 > 1 ? "s" : ""}: ${money(this.bagFee(n2))} added to your total. You'll check in ${inc + n2} bag${inc + n2 !== 1 ? "s" : ""}.`
      : "No extra luggage fee.";
    this.$('[data-value="bags"]').textContent = "";
    if (refresh) this.refresh(false);
  }

  radio(name) { return this.root.querySelector(`input[name="${name}"]:checked`)?.value; }
  $(sel) { return this.root.querySelector(sel); }

  bind() {
    this.root.addEventListener("change", (e) => {
      if (e.target.name === "cabin") {
        this.state.cabin = e.target.value;
        this.seatMap.setCabin(this.state.cabin);
        if (!this.seatMap.picked) this.pickSeat(null);
        this.setBags(this.state.bags, false);
        this.refresh();
      }
      if (e.target.name === "insurance") { this.state.insurance = e.target.value; this.refresh(false); }
    });
    this.root.querySelectorAll("[data-next]").forEach((b) => b.addEventListener("click", () => this.goto(b.dataset.next)));
    this.root.querySelectorAll("[data-goto]").forEach((b) => b.addEventListener("click", () => this.goto(b.dataset.goto)));
    this.root.querySelectorAll("[data-bags]").forEach((b) => b.addEventListener("click", () => this.setBags(this.state.bags + Number(b.dataset.bags))));
    this.root.querySelectorAll("[data-keep-state]").forEach((a) => a.addEventListener("click", () => this.persist("pay")));

    const form = document.getElementById("pay-form");
    if (!form) return;
    form.addEventListener("submit", (e) => { e.preventDefault(); this.pay(); });
    const num = document.getElementById("card-number"), exp = document.getElementById("card-exp");
    num.addEventListener("input", () => { num.value = num.value.replace(/\D/g, "").slice(0, 19).replace(/(.{4})(?=.)/g, "$1 "); });
    exp.addEventListener("input", () => {
      const d = exp.value.replace(/\D/g, "").slice(0, 4);
      exp.value = d.length > 2 ? `${d.slice(0, 2)}/${d.slice(2)}` : d;
    });
    this.root.querySelectorAll("[data-card]").forEach((b) => b.addEventListener("click", () => {
      num.value = b.dataset.card.replace(/(.{4})(?=.)/g, "$1 ");
      const next = new Date(); next.setFullYear(next.getFullYear() + 2);
      exp.value = `${String(next.getMonth() + 1).padStart(2, "0")}/${String(next.getFullYear()).slice(2)}`;
      document.getElementById("card-cvc").value = "123";
    }));
  }

  pickSeat(seat) {
    this.state.seat = seat;
    this.seatMap.picked = seat;
    document.getElementById("seat-next").disabled = !seat;
    this.$('[data-value="seat"]').textContent = seat || "";
    this.$('[data-sum="seat"]').textContent = seat ? `${seat}${/[AF]$/.test(seat) ? " (window)" : /[CD]$/.test(seat) ? " (aisle)" : ""}` : "Not picked";
  }

  goto(step) {
    if (step !== "cabin" && step !== "seat" && !this.state.seat) step = "seat";
    const idx = STEPS.indexOf(step);
    this.root.querySelectorAll(".step").forEach((el) => {
      const i = STEPS.indexOf(el.dataset.step);
      el.classList.toggle("is-active", i === idx);
      el.classList.toggle("is-done", i < idx);
      el.querySelector(".step__head").disabled = i > idx;
    });
    this.$('[data-value="cabin"]').textContent = idx > 0 ? this.state.cabin : "";
    this.$('[data-value="bags"]').textContent = idx > 2 ? (this.state.bags ? `+${this.state.bags} extra` : "No extras") : "";
    this.$('[data-value="cover"]').textContent = idx > 3 ? this.label(this.state.insurance) : "";
    if (step === "seat") this.seatMap.render();
    const active = this.root.querySelector(".step.is-active");
    if (active && window.scrollY > active.getBoundingClientRect().top + window.scrollY - 100) {
      active.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }

  label(tier) {
    return { None: "No cover", "Existing Insurance": "Own policy" }[tier] || tier;
  }

  async refresh(withAdvice = true) {
    const { cabin, insurance, bags } = this.state;
    try {
      const q = await Api.get(`/api/flights/${this.number}/quote?cabin=${encodeURIComponent(cabin)}&insurance=${encodeURIComponent(insurance)}&bags=${bags}`);
      this.$('[data-sum="bags"]').textContent = String(q.extra_bags);
      this.$('[data-sum="bagfee"]').textContent = money(q.baggage_fee);
      this.$('[data-sum="cabin"]').textContent = cabin;
      this.$('[data-sum="fare"]').textContent = money(q.fare);
      this.$('[data-sum="cover"]').textContent = money(q.insurance_cost);
      this.$('[data-sum="total"]').textContent = money(q.total);
      this.$('[data-sum="demand"]').textContent = `×${q.demand_multiplier.toFixed(2)}`;
      this.$('[data-sum="time"]').textContent = `×${q.time_multiplier.toFixed(2)}`;
      const total = this.root.querySelector("[data-total]");
      if (total) total.textContent = money(q.total);
      this.total = q.total;
    } catch (err) { toast(err.message, "error"); }
    if (!withAdvice) return;
    try {
      const a = await Api.get(`/api/flights/${this.number}/advice?cabin=${encodeURIComponent(cabin)}`);
      this.spark.draw(a.curve);
      const chip = { rising: ["chip--rising", "Rising"], falling: ["chip--falling", "May dip"], steady: ["chip--steady", "Steady"] }[a.verdict];
      this.$("[data-advice-chip]").replaceChildren(h("span", { class: `chip ${chip[0]}` }, chip[1]));
      this.$("[data-advice-text]").textContent = a.message;
    } catch (err) { this.$("[data-advice-text]").textContent = "Forecast unavailable right now."; }
  }

  async pay() {
    const btn = document.getElementById("pay-btn"), box = document.getElementById("pay-error");
    box.hidden = true;
    btn.disabled = true;
    btn.classList.add("is-loading");
    const original = btn.innerHTML;
    btn.replaceChildren(h("span", { class: "spinner" }), "Processing payment…");
    try {
      const res = await Api.post(this.root.dataset.checkoutUrl, {
        cabin: this.state.cabin, seat: this.state.seat, insurance: this.state.insurance, extra_bags: this.state.bags,
        card: {
          holder: document.getElementById("card-holder").value,
          number: document.getElementById("card-number").value,
          expiry: document.getElementById("card-exp").value,
          cvc: document.getElementById("card-cvc").value,
        },
      });
      this.clearSaved();
      window.location.href = res.redirect;
    } catch (err) {
      box.textContent = err.message;
      box.hidden = false;
      btn.disabled = false;
      btn.classList.remove("is-loading");
      btn.innerHTML = original;
      if (this.total) btn.querySelector("[data-total]").textContent = money(this.total);
      if (/seat/i.test(err.message)) {
        await this.seatMap.load(`/api/flights/${this.number}/seats`);
        this.pickSeat(null);
        this.goto("seat");
      }
    }
  }

  // Remember choices across the login redirect (per tab, best effort).
  persist(resumeAt) {
    try { sessionStorage.setItem(STATE_KEY, JSON.stringify({ ...this.state, number: this.number, resumeAt })); } catch (e) { /* ignore */ }
  }
  restore() {
    try {
      const saved = JSON.parse(sessionStorage.getItem(STATE_KEY) || "null");
      if (!saved || saved.number !== this.number) return;
      for (const name of ["cabin", "insurance"]) {
        const input = this.root.querySelector(`input[name="${name}"][value="${saved[name]}"]`);
        if (input && !input.disabled) { input.checked = true; this.state[name] = saved[name]; }
      }
      this.state.seat = saved.seat;
      this.state.bags = Number(saved.bags) || 0;
      this.state.resumeAt = this.root.dataset.loggedIn === "true" ? saved.resumeAt : "cabin";
      if (saved.seat) setTimeout(() => this.pickSeat(saved.seat), 0);
    } catch (e) { /* ignore */ }
  }
  clearSaved() { try { sessionStorage.removeItem(STATE_KEY); } catch (e) { /* ignore */ } }
}

const root = document.getElementById("booking");
if (root) new BookingFlow(root);
