// Trip checkout: one cabin, a seat per flight, bags on every flight, cover once, one payment.
import { Api, h, money, toast } from "./lib.js";
import { SeatMap } from "./seatmap.js";

const STEPS = ["cabin", "seat", "bags", "cover", "pay"];

class TripBooking {
  constructor(root) {
    this.root = root;
    this.trip = root.dataset.trip;
    this.flights = JSON.parse(root.dataset.flights);
    this.legs = JSON.parse(root.dataset.legs);
    this.state = { cabin: this.radio("cabin"), insurance: this.radio("insurance"), bags: 0, seats: this.flights.map(() => null), tab: 0 };
    this.maps = this.flights.map((number, i) => {
      const map = new SeatMap(root.querySelector(`[data-seatmap="${i}"]`), (seat) => this.pickSeat(i, seat));
      map.cabin = this.state.cabin;
      map.load(`/api/flights/${number}/seats`);
      return map;
    });
    this.bind();
    this.setBags(0, false);
    this.refresh();
    this.goto("cabin");
  }

  radio(name) { return this.root.querySelector(`input[name="${name}"]:checked`)?.value; }
  $(sel) { return this.root.querySelector(sel); }

  bind() {
    this.root.addEventListener("change", (e) => {
      if (e.target.name === "cabin") {
        this.state.cabin = e.target.value;
        this.maps.forEach((m, i) => { m.setCabin(this.state.cabin); this.state.seats[i] = m.picked; });
        this.syncSeats();
        this.setBags(this.state.bags, false);
        this.refresh();
      }
      if (e.target.name === "insurance") { this.state.insurance = e.target.value; this.refresh(); }
    });
    this.root.querySelectorAll("[data-next]").forEach((b) => b.addEventListener("click", () => this.goto(b.dataset.next)));
    this.root.querySelectorAll("[data-goto]").forEach((b) => b.addEventListener("click", () => this.goto(b.dataset.goto)));
    this.root.querySelectorAll("[data-seat-tab]").forEach((b) => b.addEventListener("click", () => this.showTab(Number(b.dataset.seatTab))));
    this.root.querySelectorAll("[data-bags]").forEach((b) => b.addEventListener("click", () => this.setBags(this.state.bags + Number(b.dataset.bags))));

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

  showTab(i) {
    this.state.tab = i;
    this.root.querySelectorAll("[data-seat-tab]").forEach((b) => b.setAttribute("aria-pressed", String(Number(b.dataset.seatTab) === i)));
    this.root.querySelectorAll("[data-seatmap]").forEach((m) => { m.hidden = Number(m.dataset.seatmap) !== i; });
    this.maps[i].render();
    this.syncSeats();
  }

  pickSeat(i, seat) {
    this.state.seats[i] = seat;
    this.syncSeats();
    const next = this.state.seats.findIndex((s) => !s);
    if (next !== -1 && next !== i) setTimeout(() => this.showTab(next), 450);
  }

  syncSeats() {
    const seats = this.state.seats;
    this.root.querySelectorAll("[data-seat-tab]").forEach((b) => {
      b.querySelector("[data-tab-seat]").textContent = seats[Number(b.dataset.seatTab)] ? `· ${seats[Number(b.dataset.seatTab)]}` : "";
    });
    seats.forEach((s, i) => { this.$(`[data-leg-seat="${i}"]`).textContent = s ? `, seat ${s}` : ""; });
    const missing = seats.findIndex((s) => !s);
    this.$("[data-seat-hint]").textContent = missing === -1 ? "Every flight has a seat." : `Pick a seat on flight ${missing + 1}.`;
    document.getElementById("seat-next").disabled = missing !== -1;
  }

  setBags(n, refresh = true) {
    this.state.bags = Math.max(0, Math.min(3, n));
    document.getElementById("bag-count").textContent = String(this.state.bags);
    this.root.querySelector('[data-bags="-1"]').disabled = this.state.bags === 0;
    this.root.querySelector('[data-bags="1"]').disabled = this.state.bags === 3;
    this.legs.forEach((leg, i) => {
      const inc = leg.included[this.state.cabin] ?? 0;
      this.$(`[data-bag-row="${i}"] [data-included]`).textContent = inc ? `${inc} × ${leg.baggage.bag_kg}kg` : "Cabin bag only";
    });
    if (refresh) this.refresh();
  }

  goto(step) {
    if (["bags", "cover", "pay"].includes(step) && this.state.seats.some((s) => !s)) step = "seat";
    const idx = STEPS.indexOf(step);
    this.root.querySelectorAll(".step").forEach((el) => {
      const i = STEPS.indexOf(el.dataset.step);
      el.classList.toggle("is-active", i === idx);
      el.classList.toggle("is-done", i < idx);
      el.querySelector(".step__head").disabled = i > idx;
    });
    this.$('[data-value="cabin"]').textContent = idx > 0 ? this.state.cabin : "";
    this.$('[data-value="seat"]').textContent = idx > 1 ? this.state.seats.join(", ") : "";
    this.$('[data-value="bags"]').textContent = idx > 2 ? (this.state.bags ? `+${this.state.bags} per flight` : "No extras") : "";
    this.$('[data-value="cover"]').textContent = idx > 3 ? ({ None: "No cover", "Existing Insurance": "Own policy" }[this.state.insurance] || this.state.insurance) : "";
    if (step === "seat") this.showTab(this.state.tab);
  }

  query() {
    const p = new URLSearchParams({ trip: this.trip, cabin: this.state.cabin, insurance: this.state.insurance, bags: String(this.state.bags) });
    this.flights.forEach((f) => p.append("f", f));
    return p.toString();
  }

  async refresh() {
    try {
      const q = await Api.get(`/api/trip/quote?${this.query()}`);
      q.legs.forEach((leg, i) => {
        this.$(`[data-leg-fare="${i}"]`).textContent = money(leg.fare);
        this.$(`[data-bag-row="${i}"] [data-fee]`).textContent = money(leg.baggage_fee);
      });
      this.$('[data-sum="bagfee"]').textContent = money(q.baggage_fee);
      const disc = this.$('[data-sum="discount"]');
      if (disc) disc.textContent = `−${money(q.discount)}`;
      this.$('[data-sum="cover"]').textContent = money(q.insurance_cost);
      this.$('[data-sum="total"]').textContent = money(q.total);
      const t = this.root.querySelector("[data-total]");
      if (t) t.textContent = money(q.total);
      this.total = q.total;
    } catch (err) { toast(err.message, "error"); }
  }

  async pay() {
    const btn = document.getElementById("pay-btn"), box = document.getElementById("pay-error");
    box.hidden = true;
    btn.disabled = true;
    const original = btn.innerHTML;
    btn.replaceChildren(h("span", { class: "spinner" }), "Processing payment…");
    try {
      const res = await Api.post(this.root.dataset.checkoutUrl, {
        trip: this.trip, flights: this.flights, seats: this.state.seats, cabin: this.state.cabin,
        insurance: this.state.insurance, extra_bags: this.state.bags,
        card: {
          holder: document.getElementById("card-holder").value,
          number: document.getElementById("card-number").value,
          expiry: document.getElementById("card-exp").value,
          cvc: document.getElementById("card-cvc").value,
        },
      });
      window.location.href = res.redirect;
    } catch (err) {
      box.textContent = err.message;
      box.hidden = false;
      btn.disabled = false;
      btn.innerHTML = original;
      if (this.total) btn.querySelector("[data-total]").textContent = money(this.total);
      if (/seat/i.test(err.message)) {
        await Promise.all(this.maps.map((m, i) => m.load(`/api/flights/${this.flights[i]}/seats`)));
        this.state.seats = this.maps.map((m) => (m.isFree(m.picked) ? m.picked : null));
        this.goto("seat");
      }
    }
  }
}

const root = document.getElementById("trip-booking");
if (root) new TripBooking(root);
