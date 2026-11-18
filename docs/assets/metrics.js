// Turns the four live tables into the dashboard's figures. Pure functions: no fetching,
// no storage. All three child tables have at most one row per employee_id, so the joins are 1:1.

const NAMES = {
  RandD: "R&D",
  product_mng: "Product management",
  hr: "HR",
  IT: "IT",
  plant_a: "Plant A",
  plant_b: "Plant B",
  plant_c: "Plant C",
  standard_business_hours: "Standard business hours",
};

export function pretty(value) {
  if (value === null || value === undefined || value === "") return "Unknown";
  const s = String(value);
  if (NAMES[s]) return NAMES[s];
  const t = s.replace(/_/g, " ");
  return t.charAt(0).toUpperCase() + t.slice(1);
}

const num = (v) => (v === null || v === undefined || v === "" ? null : Number(v));

export const SCORES = [
  { field: "supervisor_support_score", label: "Supervisor support" },
  { field: "schedule_predictability_score", label: "Schedule predictability" },
  { field: "career_opportunity_score", label: "Career opportunity" },
  { field: "work_life_balance_score", label: "Work–life balance" },
];

const COSTS = ["estimated_recruiting_cost_usd", "estimated_onboarding_cost_usd", "estimated_replacement_training_cost_usd"];

// One record per baseline employee, with the matching rows from the other three tables.
export function joinTables(t) {
  const byEmployee = (rows) => new Map(rows.map((r) => [r.employee_id, r]));
  const comp = byEmployee(t.compensation_training);
  const survey = byEmployee(t.employee_surveys);
  const exit = byEmployee(t.exit_interviews);
  return t.employees.map((e) => {
    const c = comp.get(e.employee_id) || null;
    return {
      ...e,
      left: num(e.left) === 1,
      comp: c,
      cost: c ? COSTS.reduce((sum, k) => sum + (num(c[k]) || 0), 0) : null,
      survey: survey.get(e.employee_id) || null,
      exit: exit.get(e.employee_id) || null,
    };
  });
}

// "View by" options for the turnover chart. `order` keeps ordinal values in their natural order;
// everything else is ranked by turnover rate.
export const DIMENSIONS = [
  { id: "department", label: "Department", get: (e) => e.department },
  { id: "plant", label: "Plant", get: (e) => e.plant, order: "natural" },
  { id: "shift", label: "Shift", get: (e) => e.shift },
  { id: "job_role", label: "Job role", get: (e) => e.job_role },
  { id: "salary_band", label: "Salary band", get: (e) => e.comp && e.comp.salary_band, order: ["low", "medium", "high"] },
  { id: "pay_basis", label: "Pay basis", get: (e) => e.comp && e.comp.pay_basis },
  { id: "tenure", label: "Tenure (years at 2024)", get: (e) => num(e.time_spend_company), order: "numeric", format: (v) => `${v} years` },
  { id: "number_project", label: "Number of projects", get: (e) => num(e.number_project), order: "numeric", format: (v) => `${v} projects` },
  { id: "training", label: "Main training type", get: (e) => e.comp && e.comp.primary_training_type },
  { id: "promotion", label: "Promotion in last 5 years", get: (e) => (num(e.promotion_last_5years) === 1 ? "promoted" : "not_promoted"), format: (v) => (v === "promoted" ? "Promoted" : "Not promoted") },
];

export function filterEmployees(emps, { plant, department }) {
  return emps.filter((e) => (!plant || e.plant === plant) && (!department || e.department === department));
}

export function distinct(emps, field) {
  return [...new Set(emps.map((e) => e[field]).filter((v) => v !== null && v !== undefined))].sort((a, b) =>
    pretty(a).localeCompare(pretty(b)),
  );
}

export function summary(emps) {
  const leavers = emps.filter((e) => e.left);
  const voluntary = leavers.filter((e) => e.separation_type === "voluntary").length;
  const involuntary = leavers.filter((e) => e.separation_type === "involuntary").length;
  const costed = leavers.filter((e) => e.cost !== null);
  const cost = costed.reduce((s, e) => s + e.cost, 0);
  const surveyed = emps.filter((e) => e.survey).length;
  const interviewed = leavers.filter((e) => e.exit).length;
  return {
    headcount: emps.length,
    leavers: leavers.length,
    voluntary,
    involuntary,
    rate: emps.length ? leavers.length / emps.length : null,
    cost,
    costPerLeaver: costed.length ? cost / costed.length : null,
    surveyed,
    surveyRate: emps.length ? surveyed / emps.length : null,
    interviewed,
    interviewRate: leavers.length ? interviewed / leavers.length : null,
  };
}

export function turnoverBy(emps, dim) {
  const groups = new Map();
  for (const e of emps) {
    const key = dim.get(e);
    const g = groups.get(key) || { key, headcount: 0, leavers: 0 };
    g.headcount++;
    if (e.left) g.leavers++;
    groups.set(key, g);
  }
  const rows = [...groups.values()].map((g) => ({
    ...g,
    label: dim.format ? dim.format(g.key) : pretty(g.key),
    rate: g.headcount ? g.leavers / g.headcount : 0,
  }));
  if (Array.isArray(dim.order)) {
    const at = (k) => (dim.order.indexOf(k) === -1 ? dim.order.length : dim.order.indexOf(k));
    rows.sort((a, b) => at(a.key) - at(b.key));
  } else if (dim.order === "numeric") {
    rows.sort((a, b) => a.key - b.key);
  } else if (dim.order === "natural") {
    rows.sort((a, b) => String(a.key).localeCompare(String(b.key)));
  } else {
    rows.sort((a, b) => b.rate - a.rate || b.headcount - a.headcount);
  }
  return rows;
}

export function exitReasons(emps) {
  const interviewed = emps.filter((e) => e.left && e.exit);
  const groups = new Map();
  for (const e of interviewed) {
    const reason = e.exit.primary_departure_reason;
    const g = groups.get(reason) || { reason, count: 0, types: new Map() };
    g.count++;
    g.types.set(e.separation_type, (g.types.get(e.separation_type) || 0) + 1);
    groups.set(reason, g);
  }
  return {
    interviewed: interviewed.length,
    rows: [...groups.values()]
      .map((g) => {
        // Each reason belongs to one separation type in this data; take the most common to be safe.
        const type = [...g.types.entries()].sort((a, b) => b[1] - a[1])[0][0];
        return { reason: g.reason, label: pretty(g.reason), count: g.count, share: g.count / interviewed.length, type };
      })
      .sort((a, b) => b.count - a.count),
  };
}

export function surveyCompare(emps) {
  const respondents = emps.filter((e) => e.survey);
  const leavers = respondents.filter((e) => e.left);
  const stayers = respondents.filter((e) => !e.left);
  const mean = (list, field) => {
    const vals = list.map((e) => num(e.survey[field])).filter((v) => v !== null && !Number.isNaN(v));
    return vals.length ? vals.reduce((s, v) => s + v, 0) / vals.length : null;
  };
  return {
    leavers: leavers.length,
    stayers: stayers.length,
    rows: SCORES.map((s) => ({ label: s.label, stayed: mean(stayers, s.field), left: mean(leavers, s.field) })),
  };
}

export function costByDepartment(emps) {
  const groups = new Map();
  for (const e of emps) {
    if (!e.left || e.cost === null) continue;
    const g = groups.get(e.department) || { key: e.department, cost: 0, leavers: 0 };
    g.cost += e.cost;
    g.leavers++;
    groups.set(e.department, g);
  }
  return [...groups.values()].map((g) => ({ ...g, label: pretty(g.key) })).sort((a, b) => b.cost - a.cost);
}

// ---- formatting ----
export const fmt = {
  int: (v) => (v === null || v === undefined ? "–" : Math.round(v).toLocaleString("en-US")),
  pct: (v, digits = 1) => (v === null || v === undefined ? "–" : `${(v * 100).toFixed(digits)}%`),
  score: (v) => (v === null || v === undefined ? "–" : v.toFixed(2)),
  money: (v) => {
    if (v === null || v === undefined) return "–";
    const a = Math.abs(v);
    if (a >= 1e6) return `$${(v / 1e6).toFixed(a >= 1e7 ? 1 : 2)}M`;
    if (a >= 1e3) return `$${(v / 1e3).toFixed(a >= 1e5 ? 0 : 1)}K`;
    return `$${Math.round(v).toLocaleString("en-US")}`;
  },
  moneyFull: (v) => (v === null || v === undefined ? "–" : `$${Math.round(v).toLocaleString("en-US")}`),
};
