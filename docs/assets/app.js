// Wires the sign-in page, the live data load and the charts together.
// Data lives only in memory for as long as the page is open; every load is a fresh read.
import { AuthError, TABLES, changePassword, countRows, currentUser, fetchAll, isConfigured, signIn, signOut } from "./supabase.js";
import {
  DIMENSIONS, costByDepartment, distinct, exitReasons, filterEmployees, fmt, joinTables, pretty, summary, surveyCompare, turnoverBy,
} from "./metrics.js";
import { renderBars } from "./charts.js";

const $ = (id) => document.getElementById(id);
const chart = (cardId) => document.querySelector(`#${cardId} .chart`);
const el = (tag, cls, text) => {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined) node.textContent = text;
  return node;
};

let employees = null;   // joined records from the latest live read
let lastLoad = null;    // what that read took
let loading = false;

// ---------- views ----------
function show(view) {
  $("signin-view").hidden = view !== "signin";
  $("dashboard-view").hidden = view !== "dashboard";
}

function showSignIn(note) {
  employees = null;
  lastLoad = null;
  show("signin");
  const err = $("signin-error");
  if (!isConfigured()) {
    err.textContent = "This copy isn't set up yet: the publishable key is missing from assets/config.js.";
    err.hidden = false;
    $("signin-button").disabled = true;
    return;
  }
  err.textContent = note || "";
  err.hidden = !note;
  $("email").focus();
}

async function enterDashboard() {
  show("dashboard");
  $("signed-in-as").textContent = `Signed in as ${currentUser()}`;
  await load();
}

// ---------- sign-in ----------
$("signin-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const email = $("email").value.trim();
  const password = $("password").value;
  const err = $("signin-error");
  if (!email || !password) {
    err.textContent = "Enter your email and password.";
    err.hidden = false;
    return;
  }
  const button = $("signin-button");
  button.disabled = true;
  button.textContent = "Signing in…";
  try {
    await signIn(email, password);
    $("password").value = "";
    err.hidden = true;
    await enterDashboard();
  } catch (e) {
    err.textContent = e.message;
    err.hidden = false;
  } finally {
    button.disabled = false;
    button.textContent = "Sign in";
  }
});

$("sign-out").addEventListener("click", async () => {
  await signOut();
  showSignIn("You're signed out.");
});

// ---------- live load ----------
async function load() {
  if (loading) return;
  loading = true;
  const content = $("content");
  if (employees) content.classList.add("loading");   // keep the previous render while refetching
  $("refresh").disabled = true;
  $("load-error").hidden = true;
  const status = (text) => { $("load-status").textContent = text; };
  const tables = Object.keys(TABLES);
  let pages = 0;
  status("Reading live data…");
  try {
    const started = performance.now();
    const [counts, ...rowsets] = await Promise.all([
      Promise.all(tables.map((t) => countRows(t))),
      ...tables.map((t) => fetchAll(t, () => { pages += 1; status(`Reading live data… ${pages} pages`); })),
    ]);
    employees = joinTables(Object.fromEntries(tables.map((t, i) => [t, rowsets[i]])));
    lastLoad = {
      at: new Date(),
      seconds: (performance.now() - started) / 1000,
      requests: pages + tables.length,
      tables: tables.map((t, i) => ({ table: t, rows: rowsets[i].length, count: counts[i] })),
    };
    fillFilters();
    render();
    status(`Loaded at ${lastLoad.at.toLocaleTimeString()}`);
  } catch (e) {
    if (e instanceof AuthError) {
      showSignIn(e.message);
      return;
    }
    $("load-error").textContent = employees
      ? `Refresh failed (${e.message}). The figures below are from the load at ${lastLoad.at.toLocaleTimeString()}.`
      : `Couldn't read the data: ${e.message}`;
    $("load-error").hidden = false;
    status("");
  } finally {
    loading = false;
    $("refresh").disabled = false;
    content.classList.remove("loading");
  }
}

$("refresh").addEventListener("click", load);

// ---------- filters ----------
function fillSelect(select, values, allLabel) {
  const keep = select.value;
  select.replaceChildren(new Option(allLabel, ""), ...values.map((v) => new Option(pretty(v), v)));
  select.value = values.includes(keep) ? keep : "";
}

function fillFilters() {
  fillSelect($("filter-plant"), distinct(employees, "plant"), "All plants");
  fillSelect($("filter-department"), distinct(employees, "department"), "All departments");
}

for (const id of ["filter-plant", "filter-department", "dimension"]) $(id).addEventListener("change", render);

function scopeText({ plant, department }) {
  const parts = [plant && pretty(plant), department && pretty(department)].filter(Boolean);
  return parts.length ? ` in ${parts.join(", ")}` : "";
}

// ---------- render ----------
function render() {
  if (!employees) return;
  const scope = { plant: $("filter-plant").value, department: $("filter-department").value };
  const emps = filterEmployees(employees, scope);
  const s = summary(emps);

  $("kpi-rate").textContent = fmt.pct(s.rate);
  $("kpi-rate-note").textContent = `${fmt.int(s.leavers)} of ${fmt.int(s.headcount)} employees left${scopeText(scope)}`;
  $("kpi-headcount").textContent = fmt.int(s.headcount);
  $("kpi-leavers").textContent = fmt.int(s.leavers);
  $("kpi-leavers-note").textContent = `${fmt.int(s.voluntary)} voluntary · ${fmt.int(s.involuntary)} involuntary`;
  $("kpi-cost").textContent = fmt.money(s.cost);
  $("kpi-cost-note").textContent = s.costPerLeaver === null ? "estimate" : `estimate · about ${fmt.money(s.costPerLeaver)} per leaver`;
  $("kpi-survey").textContent = fmt.pct(s.surveyRate);
  $("kpi-survey-note").textContent = `${fmt.int(s.surveyed)} answered in Dec 2024`;
  $("kpi-exit").textContent = fmt.pct(s.interviewRate);
  $("kpi-exit-note").textContent = `of leavers (${fmt.int(s.interviewed)} interviews)`;

  renderTurnover(emps, s);
  renderReasons(emps);
  renderSurvey(emps);
  renderCost(emps);
  renderStatus();
}

function renderTurnover(emps, s) {
  const dim = DIMENSIONS.find((d) => d.id === $("dimension").value) || DIMENSIONS[0];
  $("dimension-name").textContent = dim.label.charAt(0).toLowerCase() + dim.label.slice(1);
  const rows = turnoverBy(emps, dim);
  renderBars(chart("card-turnover"), {
    series: [{ id: "s1", label: "Turnover rate" }],
    rows: rows.map((r) => ({
      label: r.label,
      aria: `${r.label}: ${fmt.pct(r.rate)} turnover, ${fmt.int(r.leavers)} of ${fmt.int(r.headcount)} left`,
      tip: {
        title: r.label,
        lines: [{ value: fmt.pct(r.rate), label: "turnover rate", series: "s1" }],
        note: `${fmt.int(r.leavers)} of ${fmt.int(r.headcount)} employees left`,
      },
      bars: [{ value: r.rate, display: fmt.pct(r.rate), series: "s1" }],
    })),
    labelSpace: 56,
    note: s.rate === null ? "" : `Overall${scopeText({ plant: $("filter-plant").value, department: $("filter-department").value })}: ${fmt.pct(s.rate)}`,
    table: {
      columns: [{ label: dim.label }, { label: "Employees", num: true }, { label: "Left", num: true }, { label: "Turnover rate", num: true }],
      rows: rows.map((r) => [r.label, fmt.int(r.headcount), fmt.int(r.leavers), fmt.pct(r.rate)]),
    },
  });
}

function renderReasons(emps) {
  const { interviewed, rows } = exitReasons(emps);
  renderBars(chart("card-reasons"), {
    series: [{ id: "s1", label: "Voluntary" }, { id: "s2", label: "Involuntary" }],
    rows: rows.map((r) => {
      const sid = r.type === "involuntary" ? "s2" : "s1";
      const type = pretty(r.type);
      return {
        label: r.label,
        aria: `${r.label} (${type}): ${fmt.int(r.count)} leavers, ${fmt.pct(r.share)} of exit interviews`,
        tip: {
          title: `${r.label} · ${type}`,
          lines: [{ value: fmt.int(r.count), label: "leavers", series: sid }],
          note: `${fmt.pct(r.share)} of ${fmt.int(interviewed)} exit interviews`,
        },
        bars: [{ value: r.count, display: `${fmt.int(r.count)} · ${fmt.pct(r.share, 0)}`, series: sid }],
      };
    }),
    labelSpace: 96,
    note: `${fmt.int(interviewed)} interviewed leavers. Reasons are self-reported, not measured causes.`,
    table: {
      columns: [{ label: "Reason" }, { label: "Type" }, { label: "Leavers", num: true }, { label: "Share of interviews", num: true }],
      rows: rows.map((r) => [r.label, pretty(r.type), fmt.int(r.count), fmt.pct(r.share)]),
    },
  });
}

function renderSurvey(emps) {
  const { leavers, stayers, rows } = surveyCompare(emps);
  renderBars(chart("card-survey"), {
    series: [
      { id: "s1", label: `Stayed (${fmt.int(stayers)} answered)` },
      { id: "s2", label: `Left (${fmt.int(leavers)} answered)` },
    ],
    rows: rows.map((r) => {
      const gap = r.stayed !== null && r.left !== null ? r.left - r.stayed : null;
      return {
        label: r.label,
        aria: `${r.label}: stayed ${fmt.score(r.stayed)}, left ${fmt.score(r.left)}`,
        tip: {
          title: r.label,
          lines: [
            { value: fmt.score(r.stayed), label: "stayed", series: "s1" },
            { value: fmt.score(r.left), label: "left", series: "s2" },
          ],
          note: gap === null ? "" : `Leavers scored ${Math.abs(gap).toFixed(2)} ${gap < 0 ? "lower" : "higher"}`,
        },
        bars: [
          { value: r.stayed, display: fmt.score(r.stayed), series: "s1" },
          { value: r.left, display: fmt.score(r.left), series: "s2" },
        ],
      };
    }),
    max: 5,
    labelSpace: 44,
    note: "Bars run from 0 to 5. Scores are 1–5, with 5 assumed most favourable.",
    table: {
      columns: [{ label: "Question" }, { label: "Stayed", num: true }, { label: "Left", num: true }, { label: "Gap", num: true }],
      rows: rows.map((r) => [
        r.label, fmt.score(r.stayed), fmt.score(r.left),
        r.stayed !== null && r.left !== null ? (r.left - r.stayed).toFixed(2) : "–",
      ]),
    },
  });
}

function renderCost(emps) {
  const rows = costByDepartment(emps);
  renderBars(chart("card-cost"), {
    series: [{ id: "s1", label: "Estimated cost" }],
    rows: rows.map((r) => ({
      label: r.label,
      aria: `${r.label}: ${fmt.moneyFull(r.cost)} estimated for ${fmt.int(r.leavers)} leavers`,
      tip: {
        title: r.label,
        lines: [{ value: fmt.moneyFull(r.cost), label: "estimated", series: "s1" }],
        note: `${fmt.int(r.leavers)} leavers · about ${fmt.money(r.cost / r.leavers)} each`,
      },
      bars: [{ value: r.cost, display: fmt.money(r.cost), series: "s1" }],
    })),
    labelSpace: 64,
    note: "Estimates from the compensation_training table, not measured costs.",
    table: {
      columns: [{ label: "Department" }, { label: "Leavers", num: true }, { label: "Estimated cost", num: true }, { label: "Per leaver", num: true }],
      rows: rows.map((r) => [r.label, fmt.int(r.leavers), fmt.moneyFull(r.cost), fmt.moneyFull(r.cost / r.leavers)]),
    },
  });
}

function renderStatus() {
  const body = $("status-table").tBodies[0];
  body.replaceChildren();
  for (const t of lastLoad.tables) {
    const tr = el("tr");
    const ok = t.count !== null && t.rows === t.count;
    const check = el("td", ok ? "check-ok" : "check-bad", ok ? "Matches" : "Differs");
    tr.append(el("td", null, t.table), el("td", "num", fmt.int(t.rows)), el("td", "num", fmt.int(t.count)), check);
    body.append(tr);
  }
  $("status-line").textContent =
    `Signed in as ${currentUser()} · ${lastLoad.requests} read-only requests in ${lastLoad.seconds.toFixed(1)} s · ` +
    `loaded at ${lastLoad.at.toLocaleTimeString()}. Press Refresh data to read the database again.`;
}

// ---------- change password ----------
const dialog = $("password-dialog");
const say = (text, ok) => {
  const m = $("password-message");
  m.textContent = text;
  m.className = ok ? "ok" : "error";
  m.hidden = false;
};

$("change-password").addEventListener("click", () => {
  $("password-form").reset();
  $("password-message").hidden = true;
  dialog.showModal();
  $("new-password").focus();
});
$("password-cancel").addEventListener("click", () => dialog.close());
$("password-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const a = $("new-password").value;
  const b = $("repeat-password").value;
  if (a.length < 8) return say("Use at least 8 characters.");
  if (a !== b) return say("The two passwords don't match.");
  const save = $("password-save");
  save.disabled = true;
  try {
    await changePassword(a);
    $("password-form").reset();
    say("Password changed. Use the new one next time you sign in.", true);
  } catch (e) {
    if (e instanceof AuthError) {
      dialog.close();
      showSignIn(e.message);
      return;
    }
    say(e.message);
  } finally {
    save.disabled = false;
  }
});

// ---------- start ----------
$("dimension").replaceChildren(...DIMENSIONS.map((d) => new Option(d.label, d.id)));
if (isConfigured() && currentUser()) enterDashboard();
else showSignIn();
