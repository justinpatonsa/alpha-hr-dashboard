"""The live snapshot: a fresh read of the four tables, joined into one row per baseline employee.

Each browser session keeps only its latest read in memory, and a new read replaces it every
20 seconds. Changing a filter re-slices that latest read rather than waiting for the next one.
Nothing is written to disk or shared between viewers.
"""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import time

import pandas as pd
import streamlit as st

from lib.supabase_client import TABLES, Client, SupabaseError

REFRESH_SECONDS = 20

# OUTAGE FALLBACK ONLY. A saved copy of the four tables, used when Supabase can't be read
# (e.g. the instructor's project is restricted for going over its quota). Every page then
# shows a banner saying the data is not live, and the app keeps retrying the live database,
# switching back by itself when it answers. Never use these files for anything else, and
# don't add other copies of the data: the course requires live data.
FALLBACK_DIR = Path(__file__).resolve().parent.parent / "data" / "snapshot_2026-10-28"
FALLBACK_LABEL = "28 Oct 2026"
FALLBACK_RETRY_SECONDS = 60   # while on the saved copy, try the live database this often
COST_COLUMNS = {
    "estimated_recruiting_cost_usd": "Recruiting",
    "estimated_onboarding_cost_usd": "Onboarding",
    "estimated_replacement_training_cost_usd": "Replacement training",
}
SCORE_COLUMNS = {
    "supervisor_support_score": "Supervisor support",
    "schedule_predictability_score": "Schedule predictability",
    "career_opportunity_score": "Career opportunity",
    "work_life_balance_score": "Work–life balance",
}
# column -> (filter label, wording of its "all" option)
FILTERS = {"plant": ("Plant", "All plants"), "department": ("Department", "All departments"),
           "shift": ("Shift", "All shifts"), "pay_basis": ("Pay basis", "Salaried and hourly")}


@dataclass
class Snapshot:
    employees: pd.DataFrame
    rows_read: dict
    db_counts: dict
    requests: int
    seconds: float
    loaded_at: datetime
    notes: list = field(default_factory=list)
    error: str | None = None          # set when the latest refresh failed and older data is shown
    failed_at: datetime | None = None
    source: str = "live"              # "live", or "fallback" for the saved outage copy
    fallback_reason: str | None = None


@st.cache_resource(show_spinner=False)
def client() -> Client:
    """One signed-in Supabase session for the app (a credential, not data)."""
    return Client()


def _numeric(df: pd.DataFrame, columns) -> None:
    for c in columns:
        if c in df:
            df[c] = pd.to_numeric(df[c], errors="coerce")


def _one_per_employee(df: pd.DataFrame, name: str, notes: list) -> pd.DataFrame:
    dupes = int(df.duplicated("employee_id").sum()) if len(df) else 0
    if dupes:
        notes.append(f"{name}: {dupes} extra rows for the same employee were ignored")
        df = df.drop_duplicates("employee_id")
    return df


def _join(frames: dict, notes: list) -> pd.DataFrame:
    emp = frames["employees"].copy()
    comp = _one_per_employee(frames["compensation_training"], "compensation_training", notes)
    surv = _one_per_employee(frames["employee_surveys"], "employee_surveys", notes)
    exits = _one_per_employee(frames["exit_interviews"], "exit_interviews", notes)

    _numeric(emp, ["left", "satisfaction_level", "last_evaluation", "number_project", "average_monthly_hours",
                   "time_spend_company", "work_accident", "promotion_last_5years"])
    _numeric(comp, ["annual_base_pay_usd", "training_hours_2024", *COST_COLUMNS])
    _numeric(surv, list(SCORE_COLUMNS))
    for c in ("hire_date", "departure_date"):
        emp[c] = pd.to_datetime(emp[c], errors="coerce")

    df = (emp.merge(comp, on="employee_id", how="left")
             .merge(surv, on="employee_id", how="left")
             .merge(exits, on="employee_id", how="left"))
    df["left"] = df["left"].eq(1)
    df["voluntary"] = df["left"] & df["separation_type"].eq("voluntary")
    df["involuntary"] = df["left"] & df["separation_type"].eq("involuntary")
    df["surveyed"] = df["survey_id"].notna()
    df["interviewed"] = df["exit_interview_id"].notna()
    df["cost_total"] = df[list(COST_COLUMNS)].sum(axis=1, min_count=1)
    df["departure_month"] = df["departure_date"].dt.month
    return df


def fetch() -> Snapshot:
    c = client()
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=8) as pool:
        reads = {t: pool.submit(c.fetch_all, t) for t in TABLES}
        counts = {t: pool.submit(c.count, t) for t in TABLES}
        results = {t: f.result() for t, f in reads.items()}
        db_counts = {t: f.result() for t, f in counts.items()}
    frames = {t: pd.DataFrame(rows, columns=TABLES[t][1]) for t, (rows, _) in results.items()}
    notes: list = []
    return Snapshot(
        employees=_join(frames, notes),
        rows_read={t: len(rows) for t, (rows, _) in results.items()},
        db_counts=db_counts,
        requests=sum(n for _, n in results.values()) + len(db_counts),
        seconds=time.perf_counter() - started,
        loaded_at=datetime.now(),
        notes=notes,
    )


@st.cache_resource(show_spinner=False)
def _fallback_frames() -> dict:
    """The saved outage copy, read once per server process (it never changes)."""
    return {t: pd.read_csv(FALLBACK_DIR / f"{t}.csv.gz", usecols=cols, dtype={"employee_id": str})
            for t, (_, cols) in TABLES.items()}


def fetch_fallback(reason: str) -> Snapshot:
    started = time.perf_counter()
    frames = {t: df.copy() for t, df in _fallback_frames().items()}
    notes: list = []
    return Snapshot(
        employees=_join(frames, notes),
        rows_read={t: len(df) for t, df in frames.items()},
        db_counts={t: None for t in frames},
        requests=0,
        seconds=time.perf_counter() - started,
        loaded_at=datetime.now(),
        notes=notes,
        source="fallback",
        fallback_reason=reason,
    )


def get_snapshot(max_age: float | None = REFRESH_SECONDS - 2) -> Snapshot:
    """The session's latest read, refreshed when it is older than max_age seconds.
    max_age=None means "use the latest read if there is one" (page switches, filter changes),
    so the page redraws at once and the 20-second timer brings the next read.

    If a refresh fails, the previous live read stays on screen with the error noted, so the page
    never empties out because of one bad request. If there is no live read to fall back on (the
    database was already down when this session started), the saved outage copy is shown with a
    banner, and the live database is retried every FALLBACK_RETRY_SECONDS."""
    snap = st.session_state.get("snapshot")
    if snap is not None:
        age = (datetime.now() - snap.loaded_at).total_seconds()
        wait = FALLBACK_RETRY_SECONDS if snap.source == "fallback" else max_age
        if max_age is None or age < wait:
            return snap
    try:
        snap = fetch()
    except SupabaseError as err:
        if snap is not None and snap.source == "live":
            snap.error, snap.failed_at = str(err), datetime.now()
            return snap
        snap = fetch_fallback(str(err))
    st.session_state["snapshot"] = snap
    return snap


def current_filters() -> dict:
    return {col: st.session_state.get(f"filter_{col}", "") for col in FILTERS}


def apply_filters(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    mask = pd.Series(True, index=df.index)
    for col, value in filters.items():
        if value:
            mask &= df[col].eq(value)
    return df[mask]
