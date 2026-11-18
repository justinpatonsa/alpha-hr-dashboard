// Horizontal bar charts built from plain DOM. All text goes in with textContent, never innerHTML,
// because category names come from the database.

const el = (tag, cls, text) => {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined) node.textContent = text;
  return node;
};

// ---- tooltip (one for the page; values lead, labels follow) ----
const tooltip = () => document.getElementById("tooltip");

function showTip(tip, x, y) {
  const t = tooltip();
  t.replaceChildren();
  if (tip.title) t.append(el("div", "tip-title", tip.title));
  for (const line of tip.lines || []) {
    const row = el("div", "tip-row");
    if (line.series) row.append(el("span", `key ${line.series}`));
    row.append(el("strong", null, line.value));
    if (line.label) row.append(el("span", null, line.label));
    t.append(row);
  }
  if (tip.note) t.append(el("div", "tip-note", tip.note));
  t.hidden = false;
  const pad = 14;
  const { width, height } = t.getBoundingClientRect();
  const left = Math.min(x + pad, window.innerWidth - width - 8);
  const top = y + pad + height > window.innerHeight - 8 ? y - height - pad : y + pad;
  t.style.left = `${Math.max(8, left)}px`;
  t.style.top = `${Math.max(8, top)}px`;
}

function hideTip() {
  tooltip().hidden = true;
}

function attachTip(node, tip) {
  node.addEventListener("pointermove", (ev) => showTip(tip, ev.clientX, ev.clientY));
  node.addEventListener("pointerleave", hideTip);
  node.addEventListener("focus", () => {
    const r = node.getBoundingClientRect();
    showTip(tip, r.left + r.width / 2, r.bottom - 6);
  });
  node.addEventListener("blur", hideTip);
}

// ---- table view (every value reachable without hovering) ----
function tableView(spec) {
  const wrap = el("div", "table-wrap");
  const table = el("table");
  const head = el("thead");
  const hr = el("tr");
  for (const c of spec.columns) {
    const th = el("th", c.num ? "num" : null, c.label);
    th.scope = "col";
    hr.append(th);
  }
  head.append(hr);
  const body = el("tbody");
  for (const r of spec.rows) {
    const tr = el("tr");
    r.forEach((cell, i) => tr.append(el("td", spec.columns[i].num ? "num" : null, cell)));
    body.append(tr);
  }
  table.append(head, body);
  wrap.append(table);
  return wrap;
}

/**
 * spec = {
 *   series: [{ id: "s1", label }],      // a legend is drawn when there are two or more
 *   rows: [{ label, aria, tip, bars: [{ value, display, series }] }],
 *   max,                                // the value a full-width bar stands for
 *   labelSpace,                         // px reserved after the longest bar for its value
 *   note,                               // optional line under the chart
 *   table: { columns: [{ label, num }], rows: [[cell, ...]] },
 * }
 */
export function renderBars(container, spec) {
  hideTip();
  const open = container.dataset.tableOpen === "1";
  container.replaceChildren();

  if (!spec.rows.length) {
    container.append(el("p", "empty", "No rows match the current filters."));
    return;
  }

  if (spec.series.length >= 2) {
    const legend = el("ul", "legend");
    legend.setAttribute("aria-label", "Legend");
    for (const s of spec.series) {
      const li = el("li");
      li.append(el("span", `swatch ${s.id}`), el("span", null, s.label));
      legend.append(li);
    }
    container.append(legend);
  }

  const grouped = spec.rows.some((r) => r.bars.length > 1);
  const list = el("div", grouped ? "bars grouped" : "bars");
  list.setAttribute("role", "list");
  const reserve = spec.labelSpace || 64;
  const max = spec.max || Math.max(...spec.rows.flatMap((r) => r.bars.map((b) => b.value || 0)), 1);

  for (const r of spec.rows) {
    const row = el("div", "bar-row");
    row.setAttribute("role", "listitem");
    row.tabIndex = 0;
    row.setAttribute("aria-label", r.aria || r.label);
    const stack = el("div", "bar-stack");
    for (const b of r.bars) {
      const line = el("div", "bar-line");
      const bar = el("span", `bar ${b.series || "s1"}`);
      const frac = Math.max(0, Math.min(1, (b.value || 0) / max));
      bar.style.width = `calc((100% - ${reserve}px) * ${frac.toFixed(4)})`;
      line.append(bar, el("span", "bar-value", b.display));
      stack.append(line);
    }
    row.append(el("span", "bar-label", r.label), stack);
    if (r.tip) attachTip(row, r.tip);
    list.append(row);
  }
  container.append(list);

  if (spec.note) container.append(el("p", "axis-note", spec.note));

  if (spec.table) {
    const button = el("button", "ghost table-toggle", open ? "Hide table" : "Show table");
    button.type = "button";
    button.setAttribute("aria-expanded", String(open));
    const view = tableView(spec.table);
    view.hidden = !open;
    button.addEventListener("click", () => {
      const nowOpen = view.hidden;
      view.hidden = !nowOpen;
      container.dataset.tableOpen = nowOpen ? "1" : "0";
      button.textContent = nowOpen ? "Hide table" : "Show table";
      button.setAttribute("aria-expanded", String(nowOpen));
    });
    container.append(button, view);
  }
}

window.addEventListener("scroll", hideTip, { passive: true });
