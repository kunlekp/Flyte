// Global page behaviour: theme, nav, toasts, confirms, counters, tabs, countdowns.
import { countUp, dismiss, int } from "./lib.js";
import "./search.js";

class ThemeToggle {
  constructor(button) {
    this.button = button;
    this.root = document.documentElement;
    button.addEventListener("click", () => this.toggle());
    this.paint();
  }
  get isDark() {
    const forced = this.root.getAttribute("data-theme");
    return forced ? forced === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
  }
  toggle() {
    const next = this.isDark ? "light" : "dark";
    this.root.setAttribute("data-theme", next);
    try { localStorage.setItem("flyte-theme", next); } catch (e) { /* ignore */ }
    this.paint();
    document.dispatchEvent(new CustomEvent("themechange"));
  }
  paint() {
    this.button.querySelector("use").setAttribute("href", this.isDark ? "#i-sun" : "#i-moon");
    this.button.setAttribute("aria-label", this.isDark ? "Switch to light theme" : "Switch to dark theme");
  }
}

class Countdown {
  constructor(el) {
    this.el = el;
    this.target = new Date(el.dataset.countdown);
    this.tick();
    this.timer = setInterval(() => this.tick(), 30000);
  }
  tick() {
    const ms = this.target - new Date();
    if (ms <= 0) { this.el.textContent = "Departed"; clearInterval(this.timer); return; }
    const d = Math.floor(ms / 864e5), hrs = Math.floor(ms / 36e5) % 24, m = Math.floor(ms / 6e4) % 60;
    this.el.textContent = d > 0 ? `Takes off in ${d}d ${hrs}h` : `Takes off in ${hrs}h ${m}m`;
  }
}

class Page {
  static init() {
    document.querySelectorAll("[data-theme-toggle]").forEach((b) => new ThemeToggle(b));

    const navToggle = document.querySelector("[data-nav-toggle]");
    navToggle?.addEventListener("click", () => {
      const links = document.getElementById("nav-links");
      const open = links.classList.toggle("is-open");
      navToggle.setAttribute("aria-expanded", String(open));
    });

    document.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-dismiss]");
      if (btn) dismiss(btn.closest(".toast"));
      const swap = e.target.closest("[data-swap]");
      if (swap) {
        const from = document.getElementById("from"), to = document.getElementById("to");
        [from.value, to.value] = [to.value, from.value];
      }
    });
    document.querySelectorAll(".toast").forEach((t) => setTimeout(() => dismiss(t), 6000));

    document.querySelectorAll("form[data-confirm]").forEach((form) =>
      form.addEventListener("submit", (e) => { if (!confirm(form.dataset.confirm)) e.preventDefault(); }));

    document.querySelectorAll("[data-count]").forEach((el) => countUp(el, Number(el.dataset.count), { format: int }));
    document.querySelectorAll("[data-countdown]").forEach((el) => new Countdown(el));

    document.querySelectorAll(".ring[data-progress]").forEach((ring) => {
      const bar = ring.querySelector(".bar");
      const total = Number(bar.getAttribute("stroke-dasharray"));
      requestAnimationFrame(() => requestAnimationFrame(() => {
        bar.style.strokeDashoffset = String(total * (1 - Number(ring.dataset.progress)));
      }));
    });

    const tabs = document.querySelectorAll("[data-tab]");
    tabs.forEach((tab) => tab.addEventListener("click", () => {
      tabs.forEach((t) => t.setAttribute("aria-pressed", String(t === tab)));
      document.querySelectorAll("[data-panel]").forEach((p) => { p.hidden = p.dataset.panel !== tab.dataset.tab; });
    }));
  }
}

Page.init();
