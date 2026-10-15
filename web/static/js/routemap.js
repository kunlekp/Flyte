// Hero route map: Nigeria outline, airports, route arcs and planes in flight.
import { reducedMotion, s } from "./lib.js";

const NIGERIA = [[2.69,6.36],[2.72,7.07],[2.75,7.87],[2.73,8.51],[3.10,9.08],[3.38,9.83],[3.67,10.16],[3.57,10.58],[3.80,10.80],[3.60,11.33],[3.61,11.69],[3.85,12.26],[4.11,13.53],[4.88,13.78],[5.52,13.89],[6.45,13.59],[6.82,13.12],[7.33,13.10],[7.80,13.35],[9.01,12.83],[9.52,12.85],[10.11,13.27],[10.70,13.25],[11.53,13.33],[12.30,13.04],[13.08,13.60],[13.32,13.56],[14.07,13.08],[14.18,12.48],[14.58,12.09],[14.47,11.90],[14.18,11.25],[13.57,10.80],[13.31,10.16],[13.17,9.64],[12.96,9.42],[12.75,8.72],[12.22,8.31],[12.06,7.80],[11.84,7.40],[11.75,6.98],[11.06,6.64],[10.50,6.88],[10.12,7.04],[9.52,6.45],[8.76,5.48],[8.50,4.77],[7.46,4.41],[7.08,4.46],[6.70,4.24],[5.90,4.26],[5.36,4.89],[5.03,5.61],[4.33,6.27],[3.57,6.26],[2.69,6.36]];

// Nudge labels in the crowded south-east so codes don't collide.
const LABEL_OFFSET = { QOW: [-30, 4], PHC: [-32, 14], QUO: [8, 14], CBQ: [10, 4], ENU: [10, -6], BNI: [-30, 4], ACC: [10, 4], LOS: [-12, 20] };

class RouteMap {
  constructor(svg, data) {
    this.svg = svg;
    this.data = data;
    this.W = 520; this.H = 480; this.pad = 36;
    const lons = [...NIGERIA.map((p) => p[0]), ...data.airports.map((a) => a.lon)];
    const lats = [...NIGERIA.map((p) => p[1]), ...data.airports.map((a) => a.lat)];
    this.lon0 = Math.min(...lons); this.lon1 = Math.max(...lons);
    this.lat0 = Math.min(...lats); this.lat1 = Math.max(...lats);
    this.k = Math.min((this.W - 2 * this.pad) / (this.lon1 - this.lon0), (this.H - 2 * this.pad) / (this.lat1 - this.lat0));
    this.ox = (this.W - this.k * (this.lon1 - this.lon0)) / 2;
    this.oy = (this.H - this.k * (this.lat1 - this.lat0)) / 2 + 10;
    this.byCode = Object.fromEntries(data.airports.map((a) => [a.code, a]));
  }

  project(lon, lat) {
    return [this.ox + (lon - this.lon0) * this.k, this.oy + (this.lat1 - lat) * this.k];
  }

  arcPath(a, b) {
    const [x1, y1] = this.project(a.lon, a.lat);
    const [x2, y2] = this.project(b.lon, b.lat);
    const mx = (x1 + x2) / 2, my = (y1 + y2) / 2;
    const dx = x2 - x1, dy = y2 - y1, len = Math.hypot(dx, dy);
    const bend = 0.22 * len;
    return `M${x1},${y1} Q${mx - (dy / len) * bend},${my + (dx / len) * bend} ${x2},${y2}`;
  }

  render() {
    const svg = this.svg;
    svg.replaceChildren();
    const outline = NIGERIA.map(([lon, lat], i) => `${i ? "L" : "M"}${this.project(lon, lat).join(",")}`).join(" ") + "Z";
    svg.append(s("path", { class: "land", d: outline }));

    // Each city pair drawn once.
    const seen = new Set();
    const pairs = this.data.routes.filter(([o, d]) => {
      const key = [o, d].sort().join("-");
      if (seen.has(key) || !this.byCode[o] || !this.byCode[d]) return false;
      seen.add(key); return true;
    });
    const arcs = s("g");
    svg.append(arcs);
    this.paths = pairs.map(([o, d], i) => {
      const path = s("path", { class: "arc", d: this.arcPath(this.byCode[o], this.byCode[d]) });
      arcs.append(path);
      return { path, o, d, i };
    });

    const used = new Set(pairs.flat());
    const cities = s("g");
    for (const a of this.data.airports) {
      if (!used.has(a.code)) continue;
      const [x, y] = this.project(a.lon, a.lat);
      const big = ["LOS", "ABV", "KAN", "PHC"].includes(a.code);
      const [dx, dy] = LABEL_OFFSET[a.code] || [9, 4];
      cities.append(s("g", { class: "city" },
        s("circle", { class: "halo", cx: x, cy: y, r: big ? 11 : 7 }),
        s("circle", { cx: x, cy: y, r: big ? 4.5 : 3 }),
        s("text", { x: x + dx, y: y + dy }, a.code)));
    }
    svg.append(cities);
    this.planeLayer = s("g");
    svg.append(this.planeLayer);
    this.animateIn();
  }

  animateIn() {
    const still = reducedMotion();
    this.paths.forEach(({ path, i }) => {
      const len = path.getTotalLength();
      if (still) return;
      path.style.strokeDasharray = `${len}`;
      path.style.strokeDashoffset = `${len}`;
      path.animate([{ strokeDashoffset: len }, { strokeDashoffset: 0 }],
        { duration: 900, delay: 200 + i * 55, easing: "cubic-bezier(.2,.8,.2,1)", fill: "forwards" });
    });
    // Busiest routes get planes.
    const hot = ["LOS-ABV", "LOS-PHC", "LOS-KAN", "ABV-PHC", "ACC-LOS"];
    const flying = this.paths.filter((p) => hot.includes([p.o, p.d].sort().join("-")) || hot.includes(`${p.o}-${p.d}`)).slice(0, 3);
    flying.forEach((p, n) => {
      p.path.classList.add("arc--hot");
      this.fly(p.path, n, still);
    });
  }

  fly(path, n, still) {
    const plane = s("path", { class: "plane", d: "M0,-7 L4,5 L0,3 L-4,5 Z" });
    this.planeLayer.append(plane);
    const len = path.getTotalLength();
    const duration = 6500 + n * 1200;
    const offset = n * 0.33;
    const place = (t, back = false) => {
      const at = path.getPointAtLength(t * len);
      const ahead = path.getPointAtLength(Math.min(len, t * len + 1));
      const behind = path.getPointAtLength(Math.max(0, t * len - 1));
      const angle = Math.atan2(ahead.y - behind.y, ahead.x - behind.x) * 180 / Math.PI + (back ? 270 : 90);
      plane.setAttribute("transform", `translate(${at.x},${at.y}) rotate(${angle}) scale(1.6)`);
    };
    if (still) { place(0.5); return; }
    const start = performance.now() + 1400;
    const frame = (now) => {
      if (now >= start) {
        const t = (((now - start) / duration) + offset) % 1;
        const back = t >= 0.5;                              // there and back again
        const ping = back ? 2 - t * 2 : t * 2;
        place(0.04 + ping * 0.92, back);
      } else place(0.04 + offset * 0.92);
      requestAnimationFrame(frame);
    };
    requestAnimationFrame(frame);
  }
}

const svg = document.getElementById("route-map");
const data = document.getElementById("network-data");
if (svg && data) new RouteMap(svg, JSON.parse(data.textContent)).render();
