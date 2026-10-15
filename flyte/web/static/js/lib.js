// Small shared helpers (ES module).

export const reducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

const naira = new Intl.NumberFormat("en-NG", { style: "currency", currency: "NGN", maximumFractionDigits: 0 });
export const money = (v) => naira.format(Math.round(v || 0)).replace("NGN", "₦").replace(/\s/g, "");
export const moneyShort = (v) => {
  const a = Math.abs(v);
  if (a >= 1e9) return `₦${(v / 1e9).toFixed(2)}B`;
  if (a >= 1e6) return `₦${(v / 1e6).toFixed(1)}M`;
  if (a >= 1e3) return `₦${Math.round(v / 1e3)}k`;
  return `₦${Math.round(v)}`;
};
export const pct = (v, d = 0) => `${((v || 0) * 100).toFixed(d)}%`;
export const int = (v) => Math.round(v || 0).toLocaleString("en-NG");

export function h(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === false || v == null) continue;
    if (k === "class") node.className = v;
    else if (k === "text") node.textContent = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else if (k === "style" && typeof v === "object") {
      for (const [prop, val] of Object.entries(v)) {
        if (prop.startsWith("--")) node.style.setProperty(prop, val);
        else node.style[prop] = val;
      }
    }
    else node.setAttribute(k, v === true ? "" : v);
  }
  for (const child of children.flat()) {
    if (child == null || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

export const svgNS = "http://www.w3.org/2000/svg";
export function s(tag, attrs = {}, ...children) {
  const node = document.createElementNS(svgNS, tag);
  for (const [k, v] of Object.entries(attrs)) if (v != null) node.setAttribute(k, v);
  for (const c of children.flat()) if (c != null) node.append(c instanceof Node ? c : document.createTextNode(String(c)));
  return node;
}

export class Api {
  static get csrf() { return document.body.dataset.csrf; }
  static async request(url, { method = "GET", body } = {}) {
    const res = await fetch(url, {
      method,
      credentials: "same-origin",
      headers: { "Accept": "application/json", ...(body ? { "Content-Type": "application/json" } : {}), "X-CSRF-Token": Api.csrf },
      body: body ? JSON.stringify(body) : undefined,
    });
    let data = {};
    try { data = await res.json(); } catch (e) { /* non-JSON */ }
    if (!res.ok) throw new Error(data.error || `Request failed (${res.status}). Try again.`);
    return data;
  }
  static get(url) { return Api.request(url); }
  static post(url, body) { return Api.request(url, { method: "POST", body }); }
}

export function toast(message, kind = "info") {
  const box = document.querySelector(".toasts");
  const node = h("div", { class: `toast toast--${kind}`, role: "status" }, h("span", { class: "toast__dot" }), message,
    h("button", { type: "button", "aria-label": "Dismiss", "data-dismiss": "" }, "×"));
  box.append(node);
  setTimeout(() => dismiss(node), 5000);
}
export function dismiss(node) {
  node.classList.add("is-leaving");
  setTimeout(() => node.remove(), 300);
}

export function countUp(el, to, { duration = 1100, format = int } = {}) {
  if (reducedMotion()) { el.textContent = format(to); return; }
  const start = performance.now();
  const tick = (now) => {
    const t = Math.min(1, (now - start) / duration);
    const eased = 1 - Math.pow(1 - t, 4);
    el.textContent = format(to * eased);
    if (t < 1) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

/** One celebratory burst – used only when a booking is confirmed. */
export function confetti() {
  if (reducedMotion()) return;
  const canvas = h("canvas", { class: "confetti", "aria-hidden": "true" });
  document.body.append(canvas);
  const ctx = canvas.getContext("2d");
  const dpr = window.devicePixelRatio || 1;
  canvas.width = innerWidth * dpr; canvas.height = innerHeight * dpr;
  ctx.scale(dpr, dpr);
  const colors = ["#ffc83d", "#5b3df5", "#e8326a", "#0f9f73", "#ffffff"];
  const parts = Array.from({ length: 160 }, () => ({
    x: innerWidth / 2 + (Math.random() - .5) * 120, y: innerHeight * .35,
    vx: (Math.random() - .5) * 16, vy: -Math.random() * 15 - 5,
    w: 6 + Math.random() * 8, h: 8 + Math.random() * 10, r: Math.random() * 6, vr: (Math.random() - .5) * .35,
    c: colors[(Math.random() * colors.length) | 0],
  }));
  const startT = performance.now();
  const frame = (t) => {
    ctx.clearRect(0, 0, innerWidth, innerHeight);
    for (const p of parts) {
      p.vy += .42; p.vx *= .99; p.x += p.vx; p.y += p.vy; p.r += p.vr;
      ctx.save(); ctx.translate(p.x, p.y); ctx.rotate(p.r); ctx.fillStyle = p.c;
      ctx.fillRect(-p.w / 2, -p.h / 2, p.w, p.h); ctx.restore();
    }
    if (t - startT < 3200) requestAnimationFrame(frame); else canvas.remove();
  };
  requestAnimationFrame(frame);
}
