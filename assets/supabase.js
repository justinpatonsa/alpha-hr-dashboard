// Read-only access to the course Supabase project, straight from the browser.
//
// Sign-in uses Supabase Auth with the viewer's own login. The session token lives in
// sessionStorage (cleared when the tab closes), and data requests are GET only.
// Nothing read from the database is stored: every load is a fresh read.
import { SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY } from "./config.js";

const STORE = "alpha-hr-session";
const PAGE_SIZE = 1000;   // Supabase returns at most 1,000 rows per request, so tables are paged.
const MAX_PAGES = 100;

// Columns each table is read with, and the unique key it is paged by (keyset paging).
export const TABLES = {
  employees: {
    key: "employee_id",
    columns: "employee_id,department,plant,job_role,shift,separation_type,left,time_spend_company,number_project,promotion_last_5years",
  },
  compensation_training: {
    key: "employee_id",
    columns: "employee_id,salary_band,pay_basis,primary_training_type,estimated_recruiting_cost_usd,estimated_onboarding_cost_usd,estimated_replacement_training_cost_usd",
  },
  employee_surveys: {
    key: "survey_id",
    columns: "survey_id,employee_id,supervisor_support_score,schedule_predictability_score,career_opportunity_score,work_life_balance_score",
  },
  exit_interviews: {
    key: "exit_interview_id",
    columns: "exit_interview_id,employee_id,primary_departure_reason",
  },
};

export class AuthError extends Error {}

export function isConfigured() {
  return Boolean(SUPABASE_PUBLISHABLE_KEY) && !SUPABASE_PUBLISHABLE_KEY.startsWith("PASTE_");
}

// ---- session ----
let memorySession = null;   // fallback when sessionStorage is blocked

function loadSession() {
  try {
    const s = JSON.parse(sessionStorage.getItem(STORE));
    if (s && s.access_token) return s;
  } catch { /* storage blocked or empty */ }
  return memorySession;
}

function saveSession(s) {
  memorySession = s;
  try {
    if (s) sessionStorage.setItem(STORE, JSON.stringify(s));
    else sessionStorage.removeItem(STORE);
  } catch { /* storage blocked: keep it in memory only */ }
}

export function currentUser() {
  const s = loadSession();
  return s ? s.email : null;
}

// ---- HTTP ----
function message(payload, status) {
  if (payload && typeof payload === "object") {
    return payload.msg || payload.message || payload.error_description || payload.error || `HTTP ${status}`;
  }
  return payload ? String(payload).slice(0, 200) : `HTTP ${status}`;
}

async function call(method, url, { headers = {}, body } = {}) {
  let res;
  try {
    res = await fetch(url, {
      method,
      headers: { apikey: SUPABASE_PUBLISHABLE_KEY, ...(body ? { "Content-Type": "application/json" } : {}), ...headers },
      body: body ? JSON.stringify(body) : undefined,
      cache: "no-store",
    });
  } catch (err) {
    throw new Error(`Can't reach Supabase (${err.message}). Check your connection and try again.`);
  }
  const text = await res.text();
  let payload = null;
  try { payload = text ? JSON.parse(text) : null; } catch { payload = text; }
  return { status: res.status, ok: res.ok, headers: res.headers, payload };
}

function storeToken(payload, fallbackEmail) {
  const session = {
    access_token: payload.access_token,
    refresh_token: payload.refresh_token,
    expires_at: Math.floor(Date.now() / 1000) + Number(payload.expires_in || 3600),
    email: (payload.user && payload.user.email) || fallbackEmail,
  };
  saveSession(session);
  return session;
}

// ---- auth ----
export async function signIn(email, password) {
  const r = await call("POST", `${SUPABASE_URL}/auth/v1/token?grant_type=password`, { body: { email, password } });
  if (!r.ok || !r.payload || !r.payload.access_token) {
    throw new AuthError(r.status === 400 ? "That email and password didn't work." : `Sign-in failed: ${message(r.payload, r.status)}`);
  }
  return storeToken(r.payload, email).email;
}

async function refresh(session) {
  const r = await call("POST", `${SUPABASE_URL}/auth/v1/token?grant_type=refresh_token`, {
    body: { refresh_token: session.refresh_token },
  });
  if (!r.ok || !r.payload || !r.payload.access_token) {
    saveSession(null);
    throw new AuthError("Your session ended. Please sign in again.");
  }
  return storeToken(r.payload, session.email);
}

async function accessToken({ forceRefresh = false } = {}) {
  let s = loadSession();
  if (!s) throw new AuthError("Please sign in.");
  if (forceRefresh || s.expires_at - 60 < Date.now() / 1000) s = await refresh(s);
  return s.access_token;
}

export async function signOut() {
  const s = loadSession();
  saveSession(null);
  if (s) {
    // Best effort: ends this session on Supabase too.
    await call("POST", `${SUPABASE_URL}/auth/v1/logout?scope=local`, {
      headers: { Authorization: `Bearer ${s.access_token}` },
    }).catch(() => {});
  }
}

export async function changePassword(newPassword) {
  const token = await accessToken();
  const r = await call("PUT", `${SUPABASE_URL}/auth/v1/user`, {
    headers: { Authorization: `Bearer ${token}` },
    body: { password: newPassword },
  });
  if (!r.ok) throw new Error(`Password not changed: ${message(r.payload, r.status)}`);
}

// ---- data (GET only) ----
async function get(path, extraHeaders = {}) {
  const url = `${SUPABASE_URL}/rest/v1/${path}`;
  let r = await call("GET", url, { headers: { Authorization: `Bearer ${await accessToken()}`, ...extraHeaders } });
  if (r.status === 401) {
    // The token may have expired mid-load: refresh once and retry.
    r = await call("GET", url, { headers: { Authorization: `Bearer ${await accessToken({ forceRefresh: true })}`, ...extraHeaders } });
  }
  if (r.status === 401) throw new AuthError("Your session ended. Please sign in again.");
  if (!r.ok) throw new Error(`${path.split("?")[0]}: ${message(r.payload, r.status)}`);
  return r;
}

// Every row of a table, in key order: ask for the rows after the last key seen until a
// page comes back empty. Doesn't rely on the page size, so a lower server cap still works.
export async function fetchAll(table, onPage) {
  const { key, columns } = TABLES[table];
  const rows = [];
  let last = null;
  for (let page = 1; page <= MAX_PAGES; page++) {
    let query = `${table}?select=${columns}&order=${key}.asc&limit=${PAGE_SIZE}`;
    if (last !== null) query += `&${key}=gt.${encodeURIComponent(last)}`;
    const { payload } = await get(query);
    if (onPage) onPage();
    if (!Array.isArray(payload) || payload.length === 0) return rows;
    rows.push(...payload);
    last = payload[payload.length - 1][key];
  }
  throw new Error(`${table}: stopped after ${MAX_PAGES} pages`);
}

// count(*) as the database reports it, from a request that returns no rows.
export async function countRows(table) {
  const r = await get(`${table}?select=${TABLES[table].key}&limit=0`, { Prefer: "count=exact" });
  const total = (r.headers.get("Content-Range") || "").split("/").pop();
  return /^\d+$/.test(total) ? Number(total) : null;
}
