// Search ticket: one-way / return / multi-city switching and multi-city rows.

const iso = (d) => d.toISOString().slice(0, 10);
const addDays = (n) => { const d = new Date(); d.setDate(d.getDate() + n); return d; };

class SearchTicket {
  static MAX_LEGS = 4;
  static MIN_LEGS = 2;

  constructor(form) {
    this.form = form;
    this.simple = form.querySelector('[data-mode="simple"]');
    this.multi = form.querySelector('[data-mode="multi"]');
    this.returnCell = form.querySelector("[data-return]");
    this.list = form.querySelector("[data-legs]");
    form.querySelectorAll('input[name="trip"]').forEach((r) => r.addEventListener("change", () => this.apply()));
    form.addEventListener("click", (e) => {
      if (e.target.closest("[data-add-leg]")) this.addLeg();
      const remove = e.target.closest("[data-remove-leg]");
      if (remove) this.removeLeg(remove.closest("[data-leg]"));
    });
    this.apply(false);
  }

  get trip() { return this.form.querySelector('input[name="trip"]:checked')?.value || "oneway"; }

  show(fieldset, on) { fieldset.disabled = !on; fieldset.hidden = !on; }

  apply(fill = true) {
    const trip = this.trip;
    this.show(this.simple, trip !== "multi");
    this.show(this.multi, trip === "multi");
    this.simple.classList.toggle("is-return", trip === "return");
    const ret = this.returnCell.querySelector("input");
    this.returnCell.hidden = trip !== "return";
    ret.disabled = trip !== "return";
    if (!fill) return;
    const depart = this.form.querySelector("#date");
    if (trip === "return") {
      if (!depart.value) depart.value = iso(addDays(1));
      if (!ret.value) { const d = new Date(depart.value); d.setDate(d.getDate() + 4); ret.value = iso(d); }
    }
    if (trip === "multi") {
      const rows = this.rows();
      const from = this.form.querySelector("#from").value, to = this.form.querySelector("#to").value;
      const first = rows[0].querySelectorAll("input");
      if (!first[0].value && from) first[0].value = from;
      if (!first[1].value && to) first[1].value = to;
      if (rows[1]) { const second = rows[1].querySelectorAll("input"); if (!second[0].value) second[0].value = first[1].value; }
      rows.forEach((row, i) => { const d = row.querySelector('input[type="date"]'); if (!d.value) d.value = iso(addDays(1 + i * 3)); });
    }
    this.renumber();
  }

  rows() { return [...this.list.querySelectorAll("[data-leg]")]; }

  addLeg() {
    const rows = this.rows();
    if (rows.length >= SearchTicket.MAX_LEGS) return;
    const last = rows[rows.length - 1];
    const clone = last.cloneNode(true);
    const [lastFrom, lastTo, lastDate] = last.querySelectorAll("input");
    const [from, to, date] = clone.querySelectorAll("input");
    from.value = lastTo.value; to.value = "";
    const d = lastDate.value ? new Date(lastDate.value) : addDays(1);
    d.setDate(d.getDate() + 3); date.value = iso(d);
    this.list.append(clone);
    this.renumber();
    to.focus();
  }

  removeLeg(row) {
    if (this.rows().length <= SearchTicket.MIN_LEGS) return;
    row.remove();
    this.renumber();
  }

  renumber() {
    const rows = this.rows();
    rows.forEach((row, i) => {
      row.querySelector(".multi__no").textContent = String(i + 1);
      const [f, t, d] = row.querySelectorAll("input");
      f.setAttribute("aria-label", `Flight ${i + 1} from`);
      t.setAttribute("aria-label", `Flight ${i + 1} to`);
      d.setAttribute("aria-label", `Flight ${i + 1} date`);
      row.querySelector("[data-remove-leg]").disabled = rows.length <= SearchTicket.MIN_LEGS;
    });
    const add = this.form.querySelector("[data-add-leg]");
    if (add) add.disabled = rows.length >= SearchTicket.MAX_LEGS;
  }
}

document.querySelectorAll("form[data-search]").forEach((f) => new SearchTicket(f));
