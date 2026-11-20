"""The live snapshot: a read of the four tables, joined into one row per baseline employee.

The class database is shared and has a small data-transfer (egress) allowance. Re-reading all
~45,000 rows every 20 seconds for every open tab used it up, and Supabase blocked the project.
So reads are now economical, without making the data less live:

- One read is shared by everyone using the app (kept in server memory only, never on disk).
- Every CHECK_SECONDS the app asks the database only for each table's row count: four tiny
  requests. If any count changed, it re-reads everything at once.
- Otherwise it re-reads everything every FULL_REFRESH_SECONDS, so edited values show up too.
- "Refresh now" in the sidebar forces a full read (at most once per MANUAL_REFRESH_MIN_SECONDS).

Changing a filter re-slices the latest read rather than waiting for the next one.
"""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import threading
import time

import pandas as pd
import streamlit as st

from lib.supabase_client import TABLES, Client, SupabaseError

CHECK_SECONDS = 20               # cheap row-count check (a few hundred bytes)
FULL_REFRESH_SECONDS = 300       # full re-read at least this often (about 10 MB each)
MANUAL_REFRESH_MIN_SECONDS = 30  # "Refresh now" can't force full reads more often than this
REFRESH_SECONDS = CHECK_SECONDS  # how often each page's live fragment ticks

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
    checked_at: datetime | None = None  # last time the database was asked anything (count check or read)


@st.cache_resource(show_spinner=False)
def _client_holder() -> dict:
    return {}


def client() -> Client:
    """One signed-in Supabase session for the app (a credential, not data).

    Made fresh whenever the code has been reloaded (e.g. after a push to GitHub). Otherwise an
    instance of the old class would survive in the cache and raise errors that the new code
    doesn't recognise, which crashed the app once."""
    holder = _client_holder()
    if not isinstance(holder.get("client"), Client):
        holder["client"] = Client()
    return holder["client"]


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
        checked_at=datetime.now(),
    )


class _Shared:
    """The one read shared by every viewer, plus the lock that stops two viewers reading at once."""

    def __init__(self):
        self.lock = threading.Lock()
        self.snap: Snapshot | None = None


@st.cache_resource(show_spinner=False)
def _shared() -> _Shared:
    return _Shared()


def _counts() -> dict:
    """Each table's row count, straight from the database (no rows are sent)."""
    c = client()
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {t: pool.submit(c.count, t) for t in TABLES}
        return {t: f.result() for t, f in futures.items()}


def _read(prev: Snapshot | None) -> Snapshot:
    """A full read. If it fails, keep showing the previous live read with the error noted;
    with no live read to show, use the saved outage copy."""
    try:
        snap = fetch()
    except Exception as err:   # any failure (outage, bad secrets, network) must not crash the page
        now = datetime.now()
        if prev is not None and prev.source == "live":
            prev.error, prev.failed_at, prev.checked_at = str(err), now, now
            return prev
        return fetch_fallback(str(err))
    snap.checked_at = snap.loaded_at
    return snap


def _advance(snap: Snapshot | None, force: bool) -> Snapshot:
    now = datetime.now()
    if snap is None:
        return _read(None)
    if snap.source == "fallback":
        retry_due = (now - snap.loaded_at).total_seconds() >= FALLBACK_RETRY_SECONDS
        return _read(snap) if (force or retry_due) else snap
    age = (now - snap.loaded_at).total_seconds()
    if (force and age >= MANUAL_REFRESH_MIN_SECONDS) or age >= FULL_REFRESH_SECONDS:
        return _read(snap)
    try:
        counts = _counts()
    except Exception as err:
        snap.error, snap.failed_at, snap.checked_at = str(err), now, now
        return snap
    snap.checked_at, snap.error = now, None
    if counts != snap.db_counts:   # rows were added or removed: re-read now
        return _read(snap)
    return snap


def get_snapshot(max_age: float | None = REFRESH_SECONDS - 2, force: bool = False) -> Snapshot:
    """The latest shared read, brought up to date when it was last checked over max_age seconds ago.
    max_age=None means "use the latest read if there is one" (page switches, filter changes),
    so the page redraws at once and the next timed tick does the checking.
    force=True is "Refresh now": a full read, unless one happened in the last
    MANUAL_REFRESH_MIN_SECONDS."""
    shared = _shared()
    with shared.lock:
        snap = shared.snap
        if not isinstance(snap, Snapshot):   # first read, or the code was reloaded since
            snap = None
        if snap is not None and not force:
            checked = snap.checked_at or snap.loaded_at
            if max_age is None or (datetime.now() - checked).total_seconds() < max_age:
                return snap
        shared.snap = _advance(snap, force)
        return shared.snap


def current_filters() -> dict:
    return {col: st.session_state.get(f"filter_{col}", "") for col in FILTERS}


def apply_filters(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    mask = pd.Series(True, index=df.index)
    for col, value in filters.items():
        if value:
            mask &= df[col].eq(value)
    return df[mask]
