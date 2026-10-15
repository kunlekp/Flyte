// Return / multi-city results: choose one flight per leg, check connections, continue.
import { money } from "./lib.js";

class TripPlanner {
  static MIN_CONNECTION_MS = 60 * 60 * 1000;   // mirrors ItineraryPlanner.MIN_CONNECTION

  constructor(form) {
    this.form = form;
    this.count = Number(form.dataset.legs);
    this.choice = Array(this.count).fill(null);
    document.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-select]");
      if (btn) this.select(btn.closest("[data-option]"));
    });
    form.querySelector("[data-use-picks]").addEventListener("click", () => this.usePicks());
    form.addEventListener("submit", (e) => this.submit(e));
    this.update();
  }

  select(card) {
    const leg = Number(card.dataset.leg);
    document.querySelectorAll(`[data-option][data-leg="${leg}"]`).forEach((c) => {
      const on = c === card;
      c.classList.toggle("is-selected", on);
      const b = c.querySelector("[data-select]");
      b.textContent = on ? "Selected" : "Select";
      b.setAttribute("aria-pressed", String(on));
    });
    this.choice[leg] = {
      number: card.dataset.flight, fare: Number(card.dataset.fare), label: card.dataset.label,
      dep: new Date(card.dataset.dep), arr: new Date(card.dataset.arr),
    };
    const section = document.querySelector(`[data-leg-section="${leg}"]`);
    section.querySelector("[data-chosen-label]").textContent = card.dataset.label;
    section.classList.add("is-done");
    this.update();
    // Move the eye to the next leg that still needs a flight.
    const next = this.choice.findIndex((c) => !c);
    if (next > leg) document.querySelector(`[data-leg-section="${next}"]`).scrollIntoView({ behavior: "smooth", block: "start" });
  }

  usePicks() {
    document.querySelectorAll("[data-leg-section]").forEach((section) => {
      const pick = section.dataset.pick;
      const card = pick && section.querySelector(`[data-option][data-flight="${pick}"]`);
      if (card) this.select(card);
    });
  }

  problem() {
    for (let i = 1; i < this.count; i++) {
      const a = this.choice[i - 1], b = this.choice[i];
      if (a && b && b.dep - a.arr < TripPlanner.MIN_CONNECTION_MS) {
        return `Flight ${i + 1} leaves before you can make it from flight ${i}. Pick a later flight (at least 1 hour after landing).`;
      }
    }
    return null;
  }

  update() {
    this.choice.forEach((c, i) => {
      const li = this.form.querySelector(`[data-sum-leg="${i}"] [data-sum-text]`);
      li.textContent = c ? `${c.label}, ${money(c.fare)}` : "Choose a flight";
      li.classList.toggle("muted", !c);
    });
    const all = this.choice.every(Boolean);
    const rate = Number(this.form.dataset.discount || 0);
    const total = this.choice.reduce((sum, c) => sum + (c ? Math.round(c.fare * (1 - rate) / 100) * 100 : 0), 0);
    this.form.querySelector("[data-trip-total]").textContent = this.choice.some(Boolean) ? money(total) : "—";
    const warn = this.form.querySelector("[data-trip-warning]");
    const problem = this.problem();
    warn.hidden = !problem;
    warn.textContent = problem || "";
    this.form.querySelector("[data-continue]").disabled = !all || Boolean(problem);
  }

  submit(e) {
    if (!this.choice.every(Boolean) || this.problem()) { e.preventDefault(); return; }
    this.form.querySelectorAll('input[name="f"]').forEach((i) => i.remove());
    this.choice.forEach((c) => {
      const input = document.createElement("input");
      input.type = "hidden"; input.name = "f"; input.value = c.number;
      this.form.append(input);
    });
  }
}

const form = document.querySelector("[data-trip-form]");
if (form) new TripPlanner(form);
