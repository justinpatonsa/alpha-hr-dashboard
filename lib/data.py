"""The live snapshot: a fresh read of the four tables, joined into one row per baseline employee.

Each browser session keeps only its latest read in memory, and a new read replaces it every
20 seconds. Changing a filter re-slices that latest read rather than waiting for the next one.
Nothing is written to disk or shared between viewers.
"""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
import time

import pandas as pd
import streamlit as st

from lib.supabase_client import TABLES, Client, SupabaseError

REFRESH_SECONDS = 20
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


def get_snapshot(max_age: float | None = REFRESH_SECONDS - 2) -> Snapshot:
    """The session's latest read, refreshed when it is older than max_age seconds.
    max_age=None means "use the latest read if there is one" (page switches, filter changes),
    so the page redraws at once and the 20-second timer brings the next read.

    If a refresh fails, the previous read stays on screen with the error noted, so the page
    never empties out because of one bad request."""
    snap = st.session_state.get("snapshot")
    if snap is not None and (max_age is None or (datetime.now() - snap.loaded_at).total_seconds() < max_age):
        return snap
    try:
        snap = fetch()
    except SupabaseError as err:
        if snap is None:
            raise
        snap.error, snap.failed_at = str(err), datetime.now()
        return snap
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
